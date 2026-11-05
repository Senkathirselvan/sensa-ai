import json
import logging
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.app.config import settings
from backend.app.api.schemas import (
    ChatStreamRequest,
    DispatchRequest,
    DispatchResponse
)
from backend.app.agent.router import route_user_request
from backend.app.agent.orchestrator import orchestrator
from backend.app.agent.memory import memory_manager

logger = logging.getLogger("manager_agent.routes")

router = APIRouter(tags=["manager"])

@router.post("/api/chat/stream")
@router.post("/chat/stream")
async def chat_stream_endpoint(payload: ChatStreamRequest):
    """
    Unified Server-Sent Events (SSE) streaming endpoint:
    Classifies intent, delegates to downstream worker agents, and streams responses.
    Persists all user prompts and completed assistant responses to the database.
    """
    session_id = payload.session_id
    user_msg = payload.message
    model = payload.model or "auto"

    # Recover past history from DB if in-memory history is fresh or empty
    if len(memory_manager.get_history(session_id)) == 0:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{settings.JOB_FIND_AGENT_URL}/api/sessions/{session_id}")
                if res.status_code == 200:
                    data = res.json()
                    for m in data.get("messages", []):
                        memory_manager.add_message(session_id, m["role"], m["content"])
        except Exception as e:
            logger.warning(f"[chat_stream_endpoint] Could not load previous session messages from DB: {e}")

    # Add user message to session memory
    memory_manager.add_message(session_id, "user", user_msg)
    history = memory_manager.get_history(session_id)

    # Persist current user message to persistent DB (Job Find Agent on port 8000)
    try:
        user_msg_data = {
            "role": "user",
            "content": user_msg,
            "images": payload.images or []
        }
        if payload.edit_message_id:
            user_msg_data["id"] = payload.edit_message_id
        if payload.versions:
            user_msg_data["versions"] = payload.versions
        if payload.version_index is not None:
            user_msg_data["version_index"] = payload.version_index

        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{settings.JOB_FIND_AGENT_URL}/api/sessions/{session_id}/messages",
                json=user_msg_data
            )
    except Exception as e:
        logger.warning(f"[chat_stream_endpoint] Could not persist user message to DB: {e}")

    async def event_generator():
        collected_tokens = []
        collected_jobs = []
        has_done = False
        try:
            async for event in orchestrator.stream_request(
                session_id, user_msg, model, history, auto_apply_settings=payload.auto_apply_settings
            ):
                if isinstance(event, dict):
                    ev_type = event.get("type", "message")
                    ev_data = event.get("data")
                    if ev_type == "token":
                        collected_tokens.append(str(ev_data or ""))
                    elif ev_type in ["jobs", "job_cards"]:
                        ev_type = "job_cards"
                        collected_jobs = ev_data if isinstance(ev_data, list) else [ev_data]
                    elif ev_type == "done":
                        has_done = True
                        if isinstance(ev_data, dict):
                            if ev_data.get("content") and not collected_tokens:
                                collected_tokens.append(str(ev_data["content"]))
                            if ev_data.get("job_cards") and not collected_jobs:
                                collected_jobs = ev_data["job_cards"]

                    yield {
                        "event": ev_type,
                        "data": json.dumps(ev_data)
                    }
                else:
                    yield {
                        "event": "token",
                        "data": json.dumps(str(event))
                    }

            if not has_done:
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "content": "".join(collected_tokens),
                        "job_cards": collected_jobs
                    })
                }

            # Record final assistant response in session memory and persist to DB
            full_response = "".join(collected_tokens)
            if full_response:
                memory_manager.add_message(session_id, "assistant", full_response)
                
                # If this was an edit / rerun, update the user message version with the assistant response
                if payload.edit_message_id and payload.versions:
                    try:
                        v_list = [dict(v) for v in payload.versions]
                        v_idx = payload.version_index if payload.version_index is not None else len(v_list) - 1
                        if 0 <= v_idx < len(v_list):
                            v_list[v_idx]["assistantResponse"] = {
                                "content": full_response,
                                "jobCards": collected_jobs or [],
                                "createdAt": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                            }
                            async with httpx.AsyncClient(timeout=3.0) as client:
                                await client.post(
                                    f"{settings.JOB_FIND_AGENT_URL}/api/sessions/{session_id}/messages",
                                    json={
                                        "id": payload.edit_message_id,
                                        "role": "user",
                                        "content": user_msg,
                                        "images": payload.images or [],
                                        "versions": v_list,
                                        "version_index": v_idx
                                    }
                                )
                    except Exception as e:
                        logger.warning(f"[chat_stream_endpoint] Could not update versions with assistant response: {e}")

                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        await client.post(
                            f"{settings.JOB_FIND_AGENT_URL}/api/sessions/{session_id}/messages",
                            json={
                                "role": "assistant",
                                "content": full_response,
                                "job_cards": collected_jobs or []
                            }
                        )
                except Exception as e:
                    logger.warning(f"[chat_stream_endpoint] Could not persist assistant message to DB: {e}")

        except Exception as e:
            logger.error(f"[chat_stream_endpoint] Stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps(f"Internal Manager Error: {e}")
            }

    return EventSourceResponse(event_generator())

@router.post("/api/v1/dispatch")
async def dispatch_endpoint(payload: DispatchRequest):
    """
    Direct JSON Fast-Path intent classification & delegation plan.
    """
    decision = await route_user_request(payload.message)
    return DispatchResponse(
        routing_decision=decision,
        status="success",
        message=f"Request routed to {decision.target_agent.value} with confidence {decision.confidence:.2f}"
    )

@router.get("/api/health")
@router.get("/health")
async def health_endpoint():
    """
    Health check endpoint reporting manager and worker statuses.
    """
    find_ok = False
    prep_ok = False
    apply_ok = False

    try:
        counts = await orchestrator.job_find_client.get_job_counts()
        find_ok = bool(counts)
    except Exception:
        pass

    try:
        templates = await orchestrator.resume_prep_client.get_templates()
        prep_ok = bool(templates)
    except Exception:
        pass

    try:
        history = await orchestrator.job_apply_client.get_apply_history()
        apply_ok = isinstance(history, list)
    except Exception:
        pass

    return {
        "status": "healthy",
        "agent": "manager-agent",
        "port": 8005,
        "workers": {
            "job_find_agent_8000": "online" if find_ok else "unreachable",
            "resume_prep_agent_8001": "online" if prep_ok else "unreachable",
            "job_apply_agent_8002": "online" if apply_ok else "unreachable"
        }
    }
