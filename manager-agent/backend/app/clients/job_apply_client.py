from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.config import settings
from backend.app.clients.base_client import BaseWorkerClient

class JobApplyClient(BaseWorkerClient):
    def __init__(self):
        super().__init__(base_url=settings.JOB_APPLY_AGENT_URL, timeout=120.0)

    async def stream_apply(
        self,
        job_title: str,
        company: str,
        job_url: str,
        platform: str = "auto",
        resume_path: Optional[str] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        headless: bool = True,
        auto_submit: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        payload = {
            "job_title": job_title,
            "company": company,
            "job_url": job_url,
            "platform": platform,
            "resume_path": resume_path,
            "candidate_profile": candidate_profile or {},
            "headless": headless,
            "auto_submit": auto_submit
        }
        async for event in self.stream_sse("/api/apply/stream", payload):
            yield event

    async def confirm_apply(self, session_id: str, form_overrides: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        return await self.post_json("/api/apply/confirm", {
            "session_id": session_id,
            "action": "proceed",
            "overrides": form_overrides or {}
        })

    async def abort_apply(self, session_id: str, reason: str = "User cancelled") -> Optional[Dict]:
        return await self.post_json("/api/apply/abort", {
            "session_id": session_id,
            "reason": reason
        })

    async def get_apply_history(self) -> List[Dict]:
        res = await self.get_json("/api/apply/history")
        return res if isinstance(res, list) else []

    async def get_session_status(self) -> Optional[Dict]:
        return await self.get_json("/api/apply/sessions/status")

