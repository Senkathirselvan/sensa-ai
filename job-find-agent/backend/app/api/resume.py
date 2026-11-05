import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.app.core.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import ResumeProfile
from backend.app.services.resume_service import (
    get_resume_status,
    read_resume_text,
    extract_resume_skills,
    RESUME_PATH
)

router = APIRouter(prefix="/resume", tags=["resume"])

@router.get("/status")
async def resume_status(db: AsyncSession = Depends(get_db)):
    status = get_resume_status()
    # Check if we have parsed skills in DB
    result = await db.execute(select(ResumeProfile).order_by(ResumeProfile.updated_at.desc()))
    profile = result.scalars().first()
    skills = profile.parsed_skills if profile else []
    return {
        **status,
        "skills": skills
    }

@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.lower().endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported.")

    os.makedirs(os.path.dirname(RESUME_PATH), exist_ok=True)
    content = await file.read()
    with open(RESUME_PATH, "wb") as f:
        f.write(content)

    size_kb = round(len(content) / 1024, 1)
    raw_text = read_resume_text()
    skills = await extract_resume_skills(raw_text)

    # Save to database
    profile = ResumeProfile(
        id=str(uuid.uuid4()),
        filename=file.filename,
        file_size_kb=int(size_kb),
        parsed_skills=skills,
        full_text=raw_text[:4000]
    )
    db.add(profile)
    await db.commit()

    # Automatically synchronize uploaded master resume to Resume Prep Agent (Port 8001)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "http://172.17.0.1:8001/api/resume/parse",
                files={"file": (file.filename, content, file.content_type or "application/pdf")},
                data={"save_as_master": "true"}
            )
    except Exception as sync_err:
        print(f"[UploadSync] Warning: Failed syncing to resume-prep-agent: {sync_err}")

    return {
        "status": "success",
        "filename": file.filename,
        "size_kb": size_kb,
        "skills": skills,
        "message": f"Resume '{file.filename}' uploaded and parsed successfully."
    }

@router.delete("")
@router.delete("/")
async def delete_resume(db: AsyncSession = Depends(get_db)):
    if os.path.exists(RESUME_PATH):
        try:
            os.remove(RESUME_PATH)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete resume file: {str(e)}")

    await db.execute(delete(ResumeProfile))
    await db.commit()

    return {
        "status": "success",
        "message": "Resume deleted successfully."
    }

