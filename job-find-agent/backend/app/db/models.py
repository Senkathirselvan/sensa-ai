import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), default="New Job Search")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False) # 'user', 'assistant', 'system', 'tool'
    content = Column(Text, default="")
    images = Column(JSON, nullable=True) # list of base64 dataUrls or image urls
    tool_calls = Column(JSON, nullable=True) # list of tool executions & results
    job_cards = Column(JSON, nullable=True) # structured job objects for frontend rendering
    versions = Column(JSON, nullable=True) # list of ChatMessageVersion dicts
    version_index = Column(Integer, default=0, nullable=True) # current active version index
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

class JobTracker(Base):
    __tablename__ = "tracked_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), default="Remote")
    url = Column(Text, unique=True, nullable=False)
    snippet = Column(Text, default="")
    score = Column(Integer, default=0)
    match_reasons = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    status = Column(String(50), default="SAVED") # 'SAVED', 'APPLIED', 'INTERVIEW', 'REJECTED'
    created_at = Column(DateTime, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

class ResumeProfile(Base):
    __tablename__ = "resume_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_size_kb = Column(Integer, default=0)
    parsed_skills = Column(JSON, default=list)
    full_text = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

