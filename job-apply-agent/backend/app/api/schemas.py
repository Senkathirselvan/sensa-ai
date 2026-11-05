from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class ApplyRequest(BaseModel):
    job_url: str
    job_title: str
    company: str
    job_id: Optional[str] = None
    tailored_resume_path: Optional[str] = None
    cover_letter_text: Optional[str] = None
    headless: Optional[bool] = True
    session_id: Optional[str] = None
    auto_submit: Optional[bool] = False

class ConfirmApplyRequest(BaseModel):
    session_id: str

class AbortApplyRequest(BaseModel):
    session_id: str

class PlatformSessionStatus(BaseModel):
    platform: str
    available: bool
    session_file: Optional[str] = None

class AuthLoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    headless: Optional[bool] = True

class AuthPasteRequest(BaseModel):
    cookies: List[Dict[str, Any]]

class ApplicationItem(BaseModel):
    id: str
    job_id: Optional[str] = None
    job_title: str
    company: str
    job_url: str
    platform: str
    status: str
    tailored_resume_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    created_at: str
