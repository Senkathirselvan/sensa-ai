from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.config import settings
from backend.app.clients.base_client import BaseWorkerClient

class JobFindClient(BaseWorkerClient):
    def __init__(self):
        super().__init__(base_url=settings.JOB_FIND_AGENT_URL, timeout=120.0)

    async def stream_chat(self, session_id: str, message: str, model: str = "auto") -> AsyncGenerator[Dict[str, Any], None]:
        payload = {
            "session_id": session_id,
            "message": message,
            "model": model
        }
        async for event in self.stream_sse("/api/chat/stream", payload):
            yield event

    async def get_jobs(self, status: Optional[str] = None) -> List[Dict]:
        params = {"status": status} if status else {}
        res = await self.get_json("/api/jobs", params=params)
        return res if isinstance(res, list) else []

    async def get_job_counts(self) -> Dict[str, int]:
        res = await self.get_json("/api/jobs/counts")
        return res if isinstance(res, dict) else {"SAVED": 0, "APPLIED": 0, "INTERVIEW": 0}

    async def save_job(self, job_data: Dict[str, Any]) -> Optional[Dict]:
        return await self.post_json("/api/jobs/save", job_data)

    async def get_resume_status(self) -> Optional[Dict]:
        return await self.get_json("/api/resume/status")

