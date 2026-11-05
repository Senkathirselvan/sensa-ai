"""
Week 3: Resume Scoring via Local Ollama
Scores each job listing against the user's resume (0-100 match score).
"""

import os
import json
import ollama
from typing import List, Dict

MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen2.5")


def _load_resume_text() -> str:
    resume_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resume.pdf")
    if not os.path.exists(resume_path):
        return "ERROR: data/resume.pdf not found."
    try:
        from pypdf import PdfReader
        reader = PdfReader(resume_path)
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        return text[:3500]
    except Exception as e:
        return f"ERROR reading resume: {e}"


def score_job_against_resume(job: Dict) -> Dict:
    resume_text = _load_resume_text()
    if resume_text.startswith("ERROR"):
        return {**job, "score": 0, "match_reasons": [], "missing_skills": [], "apply": False, "error": resume_text}

    job_desc = f"Title: {job.get('title','')}\nCompany: {job.get('company','')}\nDescription: {job.get('snippet','')}"
    prompt = f"""
You are a career advisor. Compare this resume against the job posting.

--- RESUME ---
{resume_text}

--- JOB POSTING ---
{job_desc}

Respond ONLY with valid JSON:
{{
  "score": <integer 0 to 100>,
  "match_reasons": ["reason 1", "reason 2"],
  "missing_skills": ["missing skill 1"],
  "apply": <true if score >= 70 else false>
}}
"""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response["message"]["content"].strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        analysis = json.loads(content[start:end]) if start != -1 and end > start else {}
        return {
            **job,
            "score": analysis.get("score", 0),
            "match_reasons": analysis.get("match_reasons", []),
            "missing_skills": analysis.get("missing_skills", []),
            "apply": analysis.get("apply", False),
        }
    except Exception as e:
        return {**job, "score": 0, "match_reasons": [], "missing_skills": [], "apply": False, "error": str(e)}


def score_and_rank_jobs(jobs: List[Dict], min_score: int = 70) -> List[Dict]:
    if not jobs:
        return []
    scored = []
    for i, job in enumerate(jobs):
        print(f"[Scorer] Scoring {i+1}/{len(jobs)}: {job.get('title','Unknown')}...")
        result = score_job_against_resume(job)
        scored.append(result)
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored
