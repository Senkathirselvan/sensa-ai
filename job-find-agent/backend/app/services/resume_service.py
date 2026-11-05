import os
import json
import httpx
from pypdf import PdfReader
from backend.app.core.config import settings

RESUME_PATH = os.path.join(settings.DATA_DIR, "resume.pdf")

def get_active_resume_path() -> str:
    candidate_paths = [
        RESUME_PATH,
        "/app/data/resume.pdf",
        "/home/senkathir-selvan/job-find-agent/data/resume.pdf",
        "/home/senkathir-selvan/resume-prep-agent/data/master/resume.pdf",
        "/home/senkathir-selvan/Downloads/Senkathir_Selvan_Resume.pdf",
        "/home/senkathir-selvan/senkathir_datas/senkathir folders/senkathir Documents/Senkathir_Selvan_Resume.pdf"
    ]
    for p in candidate_paths:
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            return p
    return RESUME_PATH

def get_resume_status() -> dict:
    active_path = get_active_resume_path()
    if os.path.exists(active_path):
        size_kb = os.path.getsize(active_path) / 1024
        return {
            "uploaded": True,
            "filename": os.path.basename(active_path),
            "size_kb": round(size_kb, 1),
            "path": active_path
        }
    return {"uploaded": False, "filename": None, "size_kb": 0}

def read_resume_text() -> str:
    active_path = get_active_resume_path()
    if not os.path.exists(active_path):
        return "No resume uploaded yet. Please upload resume.pdf."
    try:
        reader = PdfReader(active_path)
        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"--- Page {i+1} ---\n{text}")
        extracted = "\n".join(full_text)
        # Return the complete text without truncating page 2 (education and certifications)
        return extracted if extracted else "Resume file appears empty."
    except Exception as e:
        return f"Failed to parse resume: {str(e)}"

async def extract_resume_skills(text: str) -> list:
    prompt = f"""
Analyze this resume text and extract the top 10 core technical skills, programming languages, and target job titles.
Respond ONLY with a valid JSON array of strings, e.g. ["Python", "FastAPI", "React", "PostgreSQL", "Backend Developer"].
No explanation.

--- RESUME ---
{text[:2500]}
"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{settings.OLLAMA_HOST}/api/chat",
                json={
                    "model": settings.DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json"
                }
            )
            if res.status_code == 200:
                data = res.json()
                raw = data.get("message", {}).get("content", "[]")
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "skills" in parsed:
                    return parsed["skills"]
    except Exception as e:
        print(f"[Resume Skills Extraction Error] {e}")
    return ["Python", "Backend Development", "APIs"]

