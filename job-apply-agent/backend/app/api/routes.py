import os
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.config import settings
from backend.app.api.schemas import (
    ApplyRequest,
    ConfirmApplyRequest,
    AbortApplyRequest,
    PlatformSessionStatus,
    ApplicationItem,
    AuthLoginRequest,
    AuthPasteRequest
)
from backend.app.agent.orchestrator import ApplyOrchestrator
from backend.app.agent.memory import ApplicationMemory
from backend.app.browser.session_store import SessionStore
from backend.app.services.auth_service import AuthService
from backend.app.db.database import get_db
from backend.app.db.models import ApplicationRecord

router = APIRouter(prefix="/api/apply", tags=["Apply Agent"])

@router.post("/stream")
async def stream_apply_endpoint(req: ApplyRequest):
    """Initiates autonomous job application pipeline with real-time SSE telemetry."""

    async def event_generator():
        async for packet in ApplyOrchestrator.stream_application(
            job_url=req.job_url,
            job_title=req.job_title,
            company=req.company,
            job_id=req.job_id,
            tailored_resume_path=req.tailored_resume_path,
            cover_letter_text=req.cover_letter_text,
            headless=req.headless if req.headless is not None else settings.BROWSER_HEADLESS,
            session_id=req.session_id,
            auto_submit=bool(req.auto_submit)
        ):
            event_type = packet.get("event", "message")
            data = packet.get("data", "")
            payload = json.dumps(data)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/confirm")
async def confirm_application(req: ConfirmApplyRequest):
    """Human-in-the-Loop approval gate release."""
    success = ApplicationMemory.confirm_session(req.session_id)
    if not success:
        raise HTTPException(status_code=404, detail="No active session found awaiting confirmation")
    return {"status": "confirmed", "session_id": req.session_id}

@router.post("/abort")
async def abort_application(req: AbortApplyRequest):
    """Safely aborts active browser execution."""
    success = ApplicationMemory.abort_session(req.session_id)
    return {"status": "aborted", "session_id": req.session_id}

@router.get("/sessions/status")
async def get_sessions_status():
    """Reports persistent authentication session availability across platforms."""
    platforms = ["naukri", "linkedin", "indeed"]
    statuses = []
    for p in platforms:
        avail = SessionStore.is_session_available(p)
        path = SessionStore.get_session_file_path(p)
        statuses.append({
            "platform": p,
            "available": avail,
            "session_file": os.path.basename(path) if avail else None
        })
    return statuses

@router.get("/history", response_model=List[ApplicationItem])
async def get_application_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Retrieves chronological job application tracking records."""
    stmt = select(ApplicationRecord).order_by(desc(ApplicationRecord.created_at)).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    return [
        ApplicationItem(
            id=r.id,
            job_id=r.job_id,
            job_title=r.job_title,
            company=r.company,
            job_url=r.job_url,
            platform=r.platform,
            status=r.status,
            tailored_resume_path=r.tailored_resume_path,
            screenshot_path=os.path.basename(r.screenshot_path) if r.screenshot_path else None,
            created_at=r.created_at.isoformat()
        )
        for r in records
    ]

@router.delete("/history/clear")
async def clear_application_history(db: AsyncSession = Depends(get_db)):
    """Clears all application audit history and logs."""
    from sqlalchemy import delete
    from backend.app.db.models import AuditLog
    await db.execute(delete(ApplicationRecord))
    await db.execute(delete(AuditLog))
    await db.commit()
    return {"success": True, "message": "Application audit history cleared."}

@router.get("/screenshot/{filename}")
async def get_screenshot_image(filename: str):
    """Serves verification screenshot images."""
    file_path = os.path.join(settings.SCREENSHOTS_DIR, os.path.basename(filename))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(file_path, media_type="image/png")

@router.get("/auth/{platform}/status")
async def get_platform_auth_status(platform: str):
    """Checks whether the specified platform has an active authenticated session."""
    return AuthService.get_status(platform)

@router.post("/auth/{platform}/login")
async def login_platform(platform: str, req: AuthLoginRequest):
    """Authenticates to the specified platform using credentials."""
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    res = await AuthService.login_with_credentials(
        platform=platform,
        username=req.username,
        password=req.password,
        headless=req.headless if req.headless is not None else True
    )
    return res

@router.post("/auth/{platform}/interactive")
async def launch_interactive_platform_login(platform: str, req: Optional[AuthLoginRequest] = None):
    """Launches headed browser on DISPLAY=:0 for manual login / 2FA / CAPTCHA completion."""
    username = req.username if req else None
    res = await AuthService.launch_interactive_login(platform=platform, username=username)
    return res

@router.post("/auth/{platform}/paste-cookies")
async def paste_platform_cookies(platform: str, req: AuthPasteRequest):
    """Saves exported JSON cookies for the platform."""
    res = AuthService.paste_cookies(platform=platform, cookies=req.cookies)
    return res

@router.post("/auth/{platform}/disconnect")
async def disconnect_platform(platform: str):
    """Deletes saved session cookies for the specified platform."""
    return AuthService.disconnect(platform=platform)


