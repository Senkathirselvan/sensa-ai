from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.config import settings
from backend.app.clients.base_client import BaseWorkerClient

class ResumePrepClient(BaseWorkerClient):
    def __init__(self):
        super().__init__(base_url=settings.RESUME_PREP_AGENT_URL, timeout=120.0)

    async def stream_tailor(
        self,
        job_title: str,
        company: str,
        job_description: str = "",
        target_pages: int = 2,
        template_id: Optional[str] = None,
        theme_id: Optional[str] = None,
        font_id: Optional[str] = None,
        generation_mode: Optional[str] = "tailor"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        payload = {
            "job_title": job_title,
            "company": company,
            "job_description": job_description or f"{job_title} at {company}",
            "target_pages": target_pages,
            "generation_mode": generation_mode
        }
        if template_id:
            payload["template_id"] = template_id
        if theme_id:
            payload["theme_id"] = theme_id
        if font_id:
            payload["font_id"] = font_id

        async for event in self.stream_sse("/api/resume/tailor/stream", payload):
            yield event

    async def stream_refine(
        self,
        prompt: str,
        current_resume_text: str = "",
        template_id: Optional[str] = None,
        theme_id: Optional[str] = None,
        font_id: Optional[str] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        job_description: Optional[str] = None,
        target_pages: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        payload = {
            "user_instruction": prompt,
            "current_markdown": current_resume_text,
            "job_title": job_title or "Python Backend Developer",
            "company": company or "General Profile",
            "job_description": job_description or ""
        }
        if template_id:
            payload["template_id"] = template_id
        if theme_id:
            payload["palette_id"] = theme_id
        if font_id:
            payload["font_id"] = font_id
        if target_pages:
            payload["target_pages"] = target_pages

        async for event in self.stream_sse("/api/resume/refine/stream", payload):
            yield event

    async def recompile(self, payload: Dict[str, Any]) -> Optional[Dict]:
        return await self.post_json("/api/resume/recompile", payload)

    async def audit_resume(self, resume_text: str = "", job_description: str = "", target_role: str = "") -> Optional[Dict]:
        payload = {
            "resume_text": resume_text,
            "job_description": job_description,
            "target_role": target_role
        }
        return await self.post_json("/api/resume/audit", payload)

    async def precision_edit(
        self,
        instruction: str,
        current_markdown: str = "",
        target_role: str = "",
        target_company: str = ""
    ) -> Optional[Dict]:
        payload = {
            "instruction": instruction,
            "current_markdown": current_markdown,
            "target_role": target_role,
            "target_company": target_company,
            "recompile_documents": True
        }
        return await self.post_json("/api/resume/edit", payload)

    async def calibrate_pagination(
        self,
        target_pages: int,
        current_markdown: str = "",
        target_role: str = "",
        target_company: str = ""
    ) -> Optional[Dict]:
        payload = {
            "target_pages": target_pages,
            "current_markdown": current_markdown,
            "target_role": target_role,
            "target_company": target_company
        }
        return await self.post_json("/api/resume/paginate", payload)

    async def draft_resume(self, payload: Dict[str, Any]) -> Optional[Dict]:
        """Synthesizes candidate intake notes and projects into a complete ATS resume."""
        return await self.post_json("/api/resume/draft", payload)

    async def parse_resume_text(self, raw_text: str, target_role: str = "", save_as_master: bool = False) -> Optional[Dict]:
        """Parses raw text resume, extracting metadata and evaluating ATS score."""
        payload = {
            "raw_text": raw_text,
            "target_role": target_role,
            "save_as_master": save_as_master
        }
        return await self.post_json("/api/resume/parse-text", payload)

    async def get_templates(self) -> Dict[str, Any]:
        res = await self.get_json("/api/resume/templates")
        return res if isinstance(res, dict) else {}
