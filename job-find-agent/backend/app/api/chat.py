import json
import uuid
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from backend.app.db.database import get_db, AsyncSessionLocal
from backend.app.db.models import ChatSession, ChatMessage
from backend.app.agent.orchestrator import stream_agent_reasoning

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    session_id: str
    message: str
    images: Optional[List[str]] = []
    model: Optional[str] = "auto"
    anthropic_key: Optional[str] = None
    gemini_key: Optional[str] = None
    nvidia_key: Optional[str] = None

@router.post("/stream")
async def chat_stream(payload: ChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint:
    Streams status updates, text tokens, job cards, and finishes by persisting
    both user prompt and final assistant response to the database.
    """
    # Load session history
    history = []
    async with AsyncSessionLocal() as db:
        # Check or create session
        res = await db.execute(select(ChatSession).where(ChatSession.id == payload.session_id))
        session = res.scalar_one_or_none()
        if not session:
            # Create session with user query as initial title
            title = (payload.message[:35] + "...") if len(payload.message) > 35 else payload.message
            session = ChatSession(id=payload.session_id, title=title)
            db.add(session)
            await db.commit()

        # Load past messages
        msg_res = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == payload.session_id).order_by(ChatMessage.created_at.asc())
        )
        for m in msg_res.scalars().all():
            if m.role in ["user", "assistant"]:
                content = m.content or ""
                # Retain memory of jobs found in this conversation so the LLM remembers every returned job
                if m.role == "assistant" and getattr(m, "job_cards", None) and len(m.job_cards) > 0:
                    jobs_summary = "\n\n[Active Job Opportunities Returned in this Session]:\n"
                    for idx, j in enumerate(m.job_cards, 1):
                        jobs_summary += (
                            f"{idx}. Title: {j.get('title')} | Company: {j.get('company')} | Location: {j.get('location')} "
                            f"| Experience: {j.get('experience')} | Salary: {j.get('salary')} | Posted: {j.get('posted_date')} "
                            f"| Platform: {j.get('platform')} | Key Skills & Snippet: {j.get('snippet')} | URL: {j.get('url')}\n"
                        )
                    content = content + jobs_summary

                msg_entry = {"role": m.role, "content": content}
                if getattr(m, "images", None):
                    msg_entry["images"] = m.images
                history.append(msg_entry)

        # Save current user message
        print(f"[DEBUG CHAT] model={payload.model}, images_count={len(payload.images or [])}", flush=True)
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=payload.session_id,
            role="user",
            content=payload.message,
            images=payload.images or []
        )
        db.add(user_msg)
        await db.commit()

    history.append({
        "role": "user",
        "content": payload.message,
        "images": payload.images or []
    })

    async def event_generator():
        final_content = ""
        final_job_cards = []

        async for event in stream_agent_reasoning(
            history,
            model=payload.model,
            anthropic_key=payload.anthropic_key,
            gemini_key=payload.gemini_key,
            nvidia_key=payload.nvidia_key
        ):
            event_type = event.get("type")
            event_data = event.get("data")

            if event_type == "token":
                final_content += event_data
            elif event_type == "job_cards":
                final_job_cards = event_data
            elif event_type == "done":
                final_content = event_data.get("content", final_content)
                final_job_cards = event_data.get("job_cards", final_job_cards)

            yield {
                "event": event_type,
                "data": json.dumps(event_data)
            }

        # Persist assistant message
        async with AsyncSessionLocal() as db:
            asst_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=payload.session_id,
                role="assistant",
                content=final_content,
                job_cards=final_job_cards
            )
            db.add(asst_msg)
            # Update session timestamp
            res = await db.execute(select(ChatSession).where(ChatSession.id == payload.session_id))
            sess = res.scalar_one_or_none()
            if sess:
                from datetime import datetime
                sess.updated_at = datetime.utcnow()
            await db.commit()

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive"
        }
    )

