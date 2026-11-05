import os
import json
import httpx
from typing import Dict, List
from backend.app.core.config import settings

BROWSER_PROFILE_DIR = os.path.join(settings.DATA_DIR, "browser_profile")
PENDING_APPLY_PATH = os.path.join(settings.DATA_DIR, "pending_apply.json")

async def get_applied_jobs() -> List[Dict]:
    """
    Retrieves candidate's applied jobs history from Job Apply Agent (Port 8002)
    and the local JobTracker database, returning direct portal URLs and proof screenshots.
    """
    applied_records = []

    # 1. Fetch live records from Job Apply Agent (Port 8002)
    apply_agent_urls = [
        "http://host.docker.internal:8002/api/apply/history",
        "http://172.17.0.1:8002/api/apply/history",
        "http://localhost:8002/api/apply/history"
    ]
    for url in apply_agent_urls:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and data:
                        applied_records = data
                        break
        except Exception:
            continue

    # 2. Complement with local JobTracker DB records where status == 'APPLIED'
    try:
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import JobTracker
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(JobTracker).where(JobTracker.status == "APPLIED").order_by(JobTracker.created_at.desc()))
            db_jobs = result.scalars().all()
            for dj in db_jobs:
                exists = any(
                    (r.get("job_url") and r.get("job_url").strip() == (dj.url or "").strip()) or
                    (r.get("job_title", "").lower() == (dj.title or "").lower() and r.get("company", "").lower() == (dj.company or "").lower())
                    for r in applied_records
                )
                if not exists:
                    applied_records.append({
                        "id": dj.id,
                        "job_title": dj.title,
                        "company": dj.company,
                        "job_url": dj.url,
                        "platform": "naukri" if "naukri" in (dj.url or "").lower() else "linkedin" if "linkedin" in (dj.url or "").lower() else "external_ats",
                        "status": "submitted",
                        "screenshot_path": None,
                        "created_at": dj.applied_at.isoformat() if dj.applied_at else dj.created_at.isoformat() if dj.created_at else None
                    })
    except Exception as e:
        print(f"[get_applied_jobs] DB complement note: {e}")

    # 3. Format into structured records
    formatted = []
    seen_keys = set()

    for r in applied_records:
        job_url = r.get("job_url") or ""
        title = r.get("job_title") or "Unknown Position"
        company = r.get("company") or "Unknown Company"
        
        # Deduplication key
        dedup_key = f"{title.lower()}::{company.lower()}"
        if job_url:
            dedup_key = job_url.strip()
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        status_raw = (r.get("status") or "applied").lower()
        if status_raw in ["submitted", "verified"]:
            submission_status = "✓ Submitted & Verified"
        elif status_raw == "auth_required":
            submission_status = "⚠️ Login Session Required"
        elif status_raw == "unverified":
            submission_status = "Submitted (Pending Proof)"
        else:
            submission_status = status_raw.capitalize()

        raw_platform = (r.get("platform") or "").lower()
        if "naukri" in raw_platform or "naukri" in job_url.lower():
            platform = "Naukri"
        elif "linkedin" in raw_platform or "linkedin" in job_url.lower():
            platform = "LinkedIn"
        elif "indeed" in raw_platform or "indeed" in job_url.lower():
            platform = "Indeed"
        else:
            platform = "Direct Portal"

        screenshot_path = r.get("screenshot_path")
        screenshot_filename = os.path.basename(screenshot_path) if screenshot_path else None
        screenshot_url = f"/api/apply/screenshot/{screenshot_filename}" if screenshot_filename else None

        formatted.append({
            "id": r.get("id"),
            "title": title,
            "company": company,
            "platform": platform,
            "url": job_url,
            "status": "APPLIED",
            "submission_status": submission_status,
            "applied_at": r.get("created_at"),
            "screenshot_filename": screenshot_filename,
            "screenshot_url": screenshot_url,
            "snippet": f"Application submitted on {platform}. Status: {submission_status}."
        })

    return formatted

async def get_saved_jobs() -> List[Dict]:
    """
    Retrieves candidate's saved/bookmarked jobs from the local JobTracker database (status == 'SAVED').
    """
    saved_records = []
    try:
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import JobTracker
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(JobTracker).where(JobTracker.status == "SAVED").order_by(JobTracker.created_at.desc()))
            db_jobs = result.scalars().all()
            for dj in db_jobs:
                saved_records.append({
                    "id": dj.id,
                    "title": dj.title,
                    "company": dj.company,
                    "platform": "Naukri" if "naukri" in (dj.url or "").lower() else "LinkedIn" if "linkedin" in (dj.url or "").lower() else "Direct Portal",
                    "url": dj.url or "",
                    "location": dj.location or "Remote",
                    "score": dj.score or 0,
                    "status": "SAVED",
                    "saved_at": dj.created_at.isoformat() if dj.created_at else None,
                    "snippet": dj.snippet or f"Saved job listing for {dj.title} at {dj.company}."
                })
    except Exception as e:
        print(f"[get_saved_jobs] DB fetch note: {e}")
    return saved_records

async def get_interview_jobs() -> List[Dict]:
    """
    Retrieves candidate's interview scheduled jobs from the local JobTracker database (status == 'INTERVIEW').
    """
    interview_records = []
    try:
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import JobTracker
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(JobTracker).where(JobTracker.status == "INTERVIEW").order_by(JobTracker.created_at.desc()))
            db_jobs = result.scalars().all()
            for dj in db_jobs:
                interview_records.append({
                    "id": dj.id,
                    "title": dj.title,
                    "company": dj.company,
                    "platform": "Naukri" if "naukri" in (dj.url or "").lower() else "LinkedIn" if "linkedin" in (dj.url or "").lower() else "Direct Portal",
                    "url": dj.url or "",
                    "location": dj.location or "Remote",
                    "score": dj.score or 0,
                    "status": "INTERVIEW",
                    "created_at": dj.created_at.isoformat() if dj.created_at else None,
                    "snippet": dj.snippet or f"Interview scheduled for {dj.title} at {dj.company}."
                })
    except Exception as e:
        print(f"[get_interview_jobs] DB fetch note: {e}")
    return interview_records

def queue_job_for_apply(job: Dict) -> dict:
    os.makedirs(os.path.dirname(PENDING_APPLY_PATH), exist_ok=True)
    with open(PENDING_APPLY_PATH, "w") as f:
        json.dump(job, f, indent=2)
    return {
        "status": "queued",
        "job": job,
        "message": f"Job '{job.get('title')}' at '{job.get('company')}' has been queued. User confirmation required before applying."
    }

def get_pending_apply_job() -> Dict:
    if os.path.exists(PENDING_APPLY_PATH):
        try:
            with open(PENDING_APPLY_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def clear_pending_apply() -> None:
    if os.path.exists(PENDING_APPLY_PATH):
        try:
            os.remove(PENDING_APPLY_PATH)
        except Exception:
            pass

def execute_apply(job: Dict) -> str:
    job_url = job.get("url", "")
    job_title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")

    if not job_url:
        return "Cannot apply: Job URL missing."

    try:
        from playwright.sync_api import sync_playwright
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=False,
                args=["--start-maximized"]
            )
            page = context.new_page()
            page.goto(job_url, timeout=30000)
            page.wait_for_timeout(5000)
            context.close()
        return f"Browser opened successfully for '{job_title}' at '{company}'."
    except Exception as e:
        return f"Application link ready: {job_url}. (Auto-browser launch note: {e})"

