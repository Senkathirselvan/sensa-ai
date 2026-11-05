import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from backend.app.db.database import get_db
from backend.app.db.models import JobTracker
from backend.app.services.apply_service import (
    get_pending_apply_job,
    clear_pending_apply,
    execute_apply
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobSaveRequest(BaseModel):
    title: str
    company: str
    location: Optional[str] = "Remote"
    url: str
    snippet: Optional[str] = ""
    score: Optional[int] = 0
    match_reasons: Optional[list] = []
    missing_skills: Optional[list] = []
    status: Optional[str] = "SAVED"

class ApplyRequest(BaseModel):
    job: dict

@router.get("")
async def list_jobs(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(JobTracker).order_by(JobTracker.created_at.desc())
    if status:
        query = query.where(JobTracker.status == status.upper())
    result = await db.execute(query)
    jobs = result.scalars().all()
    return jobs

@router.get("/counts")
async def job_counts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobTracker))
    all_jobs = result.scalars().all()
    counts = {"SAVED": 0, "APPLIED": 0, "INTERVIEW": 0}
    for j in all_jobs:
        if j.status in counts:
            counts[j.status] += 1
    return counts

@router.post("/save")
async def save_job(payload: JobSaveRequest, db: AsyncSession = Depends(get_db)):
    # Check if URL already exists
    res = await db.execute(select(JobTracker).where(JobTracker.url == payload.url))
    existing = res.scalar_one_or_none()
    if existing:
        existing.status = payload.status
        existing.score = payload.score
        await db.commit()
        return {"status": "updated", "id": existing.id}

    job = JobTracker(
        id=str(uuid.uuid4()),
        title=payload.title,
        company=payload.company,
        location=payload.location,
        url=payload.url,
        snippet=payload.snippet,
        score=payload.score,
        match_reasons=payload.match_reasons,
        missing_skills=payload.missing_skills,
        status=payload.status
    )
    db.add(job)
    await db.commit()
    return {"status": "saved", "id": job.id}

@router.get("/pending-apply")
async def pending_apply():
    return get_pending_apply_job()

@router.post("/confirm-apply")
async def confirm_apply(payload: ApplyRequest, db: AsyncSession = Depends(get_db)):
    job = payload.job
    # Execute browser apply
    result_message = execute_apply(job)
    
    # Save/update in DB as APPLIED
    res = await db.execute(select(JobTracker).where(JobTracker.url == job.get("url", "")))
    existing = res.scalar_one_or_none()
    if existing:
        existing.status = "APPLIED"
        existing.applied_at = datetime.utcnow()
    else:
        new_job = JobTracker(
            id=str(uuid.uuid4()),
            title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            location=job.get("location", "Remote"),
            url=job.get("url", ""),
            snippet=job.get("snippet", ""),
            score=job.get("score", 0),
            status="APPLIED",
            applied_at=datetime.utcnow()
        )
        db.add(new_job)

    await db.commit()
    clear_pending_apply()
    return {"status": "applied", "message": result_message}

@router.post("/cancel-apply")
async def cancel_apply():
    clear_pending_apply()
    return {"status": "cancelled"}

@router.delete("/clear")
async def clear_jobs(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Clears tracked jobs from PostgreSQL.
    If status is given ('SAVED', 'APPLIED', 'INTERVIEW'), clears only that status.
    If status is None or 'ALL', clears all tracked jobs.
    """
    from sqlalchemy import delete
    stmt = delete(JobTracker)
    if status and status.upper() != "ALL":
        stmt = stmt.where(JobTracker.status == status.upper())
    result = await db.execute(stmt)
    await db.commit()
    return {
        "success": True,
        "deleted_count": result.rowcount,
        "status_cleared": status or "ALL",
        "message": f"Successfully cleared {result.rowcount} job(s) from tracker."
    }

@router.delete("/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Deletes a single tracked job from the database by ID.
    """
    from sqlalchemy import delete
    stmt = delete(JobTracker).where(JobTracker.id == job_id)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tracked job not found")
    return {
        "success": True,
        "message": "Tracked job removed successfully."
    }


