import os
import re
import httpx
from typing import Optional, Dict, Any, List
from pypdf import PdfReader
from backend.app.config import settings
from backend.app.services.document_parser import DocumentParserService

class MasterProfileService:
    @staticmethod
    def get_candidate_master_paths() -> List[str]:
        """Locates master resume files across both agents, sorted by most recently modified."""
        primary_candidates = [
            os.path.join(settings.MASTER_RESUME_DIR, "master_resume.md"),
            os.path.join(settings.MASTER_RESUME_DIR, "master_resume.txt"),
            os.path.join(settings.MASTER_RESUME_DIR, "master_resume.pdf"),
            os.path.join(settings.MASTER_RESUME_DIR, "master_resume.docx"),
            "/home/senkathir-selvan/job-find-agent/data/resume.pdf",
        ]
        existing = [p for p in primary_candidates if os.path.exists(p)]
        # Sort by modification time descending so newly updated files are prioritized immediately
        existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return existing

    @staticmethod
    async def fetch_master_resume_text() -> str:
        """Extracts text from local master resume file or queries Agent 1's API."""
        # 1. Check local files
        valid_paths = MasterProfileService.get_candidate_master_paths()
        if valid_paths:
            for path in valid_paths:
                try:
                    with open(path, "rb") as f:
                        file_bytes = f.read()
                    text = DocumentParserService.extract_text(file_bytes, os.path.basename(path))
                    if text and text.strip():
                        return text.strip()
                except Exception as e:
                    print(f"[ProfileService] Failed reading local file {path}: {e}")

        # 2. Try fetching from Agent 1 (job-find-agent) API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{settings.JOB_AGENT_URL}/api/resume/status")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("full_text"):
                        return data["full_text"]
                    # If skills exist but no full text, construct profile string
                    if data.get("skills"):
                        return f"Candidate Profile\nSkills: {', '.join(data['skills'])}"
        except Exception as e:
            print(f"[ProfileService] Failed querying Agent 1 resume status: {e}")

        # Fallback profile if no resume uploaded yet
        return (
            "S. Senkathirselvan\n"
            "Python Backend & AI Engineer\n"
            "Email: senkathir.selvan@example.com\n"
            "Skills: Python, FastAPI, Django, PostgreSQL, Docker, Redis, Celery, REST APIs, Git, Playwright, LLM Agent Workflows, Prompt Engineering\n"
            "Experience:\n"
            "- Senior Backend Developer: Designed and deployed high-throughput FastAPI microservices and asynchronous Celery workers.\n"
            "- Full Stack & Automation Engineer: Built multi-source web scrapers, automated authentication sessions, and real-time SSE streaming architectures."
        )

    @staticmethod
    def parse_profile_matrix(raw_text: str) -> Dict[str, Any]:
        """Extracts verified skills, experience sections, and contact for zero-hallucination grounding."""
        # Basic email and phone extraction
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
        phone = phone_match.group(0) if phone_match else None

        # Common tech skills dictionary for quick anchor extraction
        common_tech = [
            "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "AWS", "GCP", "Celery", "Kafka", "RabbitMQ", "Git", "CI/CD",
            "REST API", "GraphQL", "Linux", "Playwright", "Selenium", "Pandas", "NumPy",
            "LangChain", "LLM", "Generative AI", "React", "TypeScript", "JavaScript", "HTML/CSS"
        ]
        found_skills = [s for s in common_tech if re.search(r'\b' + re.escape(s) + r'\b', raw_text, re.IGNORECASE)]

        return {
            "email": email,
            "phone": phone,
            "verified_skills": found_skills,
            "raw_text": raw_text
        }

