import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class ApplicationRecord(Base):
    __tablename__ = "application_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(100), nullable=True, index=True)
    job_title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    job_url = Column(Text, nullable=False)
    platform = Column(String(50), default="generic")  # naukri, linkedin, indeed, greenhouse, lever, workday
    status = Column(String(50), default="in_progress")  # in_progress, waiting_review, submitted, failed, aborted
    
    tailored_resume_path = Column(Text, nullable=True)
    cover_letter_text = Column(Text, nullable=True)
    
    fields_filled = Column(JSON, default=dict)
    screening_answers = Column(JSON, default=dict)
    
    screenshot_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    logs = relationship("AuditLog", back_populates="application", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("application_records.id"), nullable=False, index=True)
    step = Column(String(100), nullable=False)
    status = Column(String(50), default="success")  # success, info, warning, error
    details = Column(Text, nullable=True)
    screenshot_url = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    application = relationship("ApplicationRecord", back_populates="logs")

