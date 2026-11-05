import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from datetime import datetime, timezone
from backend.app.db.database import get_db
from backend.app.db.models import ChatSession, ChatMessage

router = APIRouter(prefix="/sessions", tags=["sessions"])

class SessionCreate(BaseModel):
    id: str = None
    title: str = "New Job Search"

class MessageCreate(BaseModel):
    id: str = None
    role: str
    content: str
    images: list = None
    tool_calls: list = None
    job_cards: list = None
    versions: list = None
    version_index: int = None

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    images: list = None
    tool_calls: list = None
    job_cards: list = None
    versions: list = None
    version_index: int = None
    created_at: datetime

class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

class SessionDetailOut(SessionOut):
    messages: List[MessageOut] = []

@router.get("", response_model=List[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()))
    sessions = result.scalars().all()
    return [
        SessionOut(
            id=s.id,
            title=s.title,
            created_at=s.created_at.replace(tzinfo=timezone.utc) if s.created_at and s.created_at.tzinfo is None else s.created_at,
            updated_at=s.updated_at.replace(tzinfo=timezone.utc) if s.updated_at and s.updated_at.tzinfo is None else s.updated_at,
        ) for s in sessions
    ]

@router.post("", response_model=SessionOut)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    sess_id = payload.id or str(uuid.uuid4())
    res = await db.execute(select(ChatSession).where(ChatSession.id == sess_id))
    existing = res.scalar_one_or_none()
    if existing:
        existing.title = payload.title
        existing.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing)
        return SessionOut(
            id=existing.id,
            title=existing.title,
            created_at=existing.created_at.replace(tzinfo=timezone.utc) if existing.created_at and existing.created_at.tzinfo is None else existing.created_at,
            updated_at=existing.updated_at.replace(tzinfo=timezone.utc) if existing.updated_at and existing.updated_at.tzinfo is None else existing.updated_at,
        )

    session = ChatSession(id=sess_id, title=payload.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at.replace(tzinfo=timezone.utc) if session.created_at and session.created_at.tzinfo is None else session.created_at,
        updated_at=session.updated_at.replace(tzinfo=timezone.utc) if session.updated_at and session.updated_at.tzinfo is None else session.updated_at,
    )

@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Load messages
    msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()
    
    return SessionDetailOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at.replace(tzinfo=timezone.utc) if session.created_at and session.created_at.tzinfo is None else session.created_at,
        updated_at=session.updated_at.replace(tzinfo=timezone.utc) if session.updated_at and session.updated_at.tzinfo is None else session.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                images=getattr(m, "images", None) or [],
                tool_calls=m.tool_calls or [],
                job_cards=m.job_cards or [],
                versions=getattr(m, "versions", None) or [],
                version_index=getattr(m, "version_index", 0) or 0,
                created_at=m.created_at.replace(tzinfo=timezone.utc) if m.created_at and m.created_at.tzinfo is None else m.created_at
            ) for m in messages
        ]
    )

@router.post("/{session_id}/messages", response_model=MessageOut)
async def add_session_message(session_id: str, payload: MessageCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = res.scalar_one_or_none()
    if not session:
        title = (payload.content[:35] + "...") if len(payload.content) > 35 else payload.content
        session = ChatSession(id=session_id, title=title)
        db.add(session)
        await db.commit()
        await db.refresh(session)
    else:
        session.updated_at = datetime.utcnow()

    existing_msg = None
    if payload.id:
        existing_res = await db.execute(select(ChatMessage).where(ChatMessage.id == payload.id))
        existing_msg = existing_res.scalar_one_or_none()

    if existing_msg:
        existing_msg.content = payload.content
        if payload.images is not None:
            existing_msg.images = payload.images
        if payload.tool_calls is not None:
            existing_msg.tool_calls = payload.tool_calls
        if payload.job_cards is not None:
            existing_msg.job_cards = payload.job_cards
        if payload.versions is not None:
            existing_msg.versions = payload.versions
        if payload.version_index is not None:
            existing_msg.version_index = payload.version_index
        await db.commit()
        await db.refresh(existing_msg)
        msg = existing_msg
    else:
        msg = ChatMessage(
            id=payload.id or str(uuid.uuid4()),
            session_id=session_id,
            role=payload.role,
            content=payload.content,
            images=payload.images or [],
            tool_calls=payload.tool_calls or [],
            job_cards=payload.job_cards or [],
            versions=payload.versions or [],
            version_index=payload.version_index or 0,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

    msg_created_at = msg.created_at.replace(tzinfo=timezone.utc) if msg.created_at and msg.created_at.tzinfo is None else msg.created_at
    return MessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        images=getattr(msg, "images", None) or [],
        tool_calls=msg.tool_calls or [],
        job_cards=msg.job_cards or [],
        versions=getattr(msg, "versions", None) or [],
        version_index=getattr(msg, "version_index", 0) or 0,
        created_at=msg_created_at
    )

@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()
    return {"status": "deleted", "id": session_id}

