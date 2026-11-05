import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), nullable=True) # ID of job from tracked_jobs or external
    session_id = Column(String(36), nullable=True)
    target_job_title = Column(String(255), nullable=False)
    target_company = Column(String(255), nullable=False)
    original_score = Column(Integer, default=0)
    tailored_score = Column(Integer, default=0)
    matched_keywords = Column(JSON, default=list)
    missing_keywords = Column(JSON, default=list)
    markdown_content = Column(Text, nullable=False)
    pdf_path = Column(String(512), nullable=True)
    docx_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cover_letter = relationship("CoverLetter", back_populates="tailored_resume", uselist=False, cascade="all, delete-orphan")

class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tailored_resume_id = Column(String(36), ForeignKey("tailored_resumes.id", ondelete="CASCADE"), nullable=False)
    target_company = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    recruiter_outreach_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tailored_resume = relationship("TailoredResume", back_populates="cover_letter")

