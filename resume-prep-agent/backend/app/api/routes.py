import os
import re
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import TailoredResume, CoverLetter
from backend.app.api.schemas import (
    TailorRequest,
    TailorResponse,
    CoverLetterRequest,
    RecompileRequest,
    RefineRequest,
    AuditRequest,
    ATSScoreReport,
    PrecisionEditRequest,
    PrecisionEditResponse,
    DiffChange,
    PaginateRequest,
    PaginateResponse,
    ParseTextRequest,
    ParseResumeResponse,
    DraftResumeRequest,
    DraftResumeResponse
)
from backend.app.agent.orchestrator import ResumeOrchestrator
from backend.app.services.profile_service import MasterProfileService
from backend.app.services.html_generator import HTMLResumeGenerator
from backend.app.services.docx_generator import DOCXResumeGenerator
from backend.app.services.document_parser import DocumentParserService
from backend.app.tools.ats_scorer import ATSScorer

router = APIRouter(prefix="/api/resume", tags=["Resume Preparation"])

@router.get("/templates")
async def get_templates_and_palettes():
    """Returns available modular HTML resume templates, CSS palettes, and typography font families."""
    return {
        "templates": list(HTMLResumeGenerator.TEMPLATES.values()),
        "palettes": list(HTMLResumeGenerator.PALETTES.values()),
        "fonts": list(HTMLResumeGenerator.FONTS.values())
    }

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": "resume-prep-agent",
        "version": "1.1.0",
        "ports": {"service": settings.PORT}
    }

@router.post("/audit", response_model=ATSScoreReport)
async def audit_resume(req: AuditRequest):
    """
    Evaluates resume against 4 distinct mathematical ATS categories (25 points each):
    1. Contact Score (25 pts): Name, email, phone, location, LinkedIn link.
    2. Formatting & Structure (25 pts): Standard ATS section headers, semantic ordering.
    3. Impact & Google XYZ Formula (25 pts): Action verbs & quantifiable metrics per bullet.
    4. Keyword Relevance (25 pts): Matching against target JD or industry baselines.
    Returns complete scorecard, category breakdown, recommendations, and per-bullet XYZ audits.
    """
    resume_text = req.resume_text.strip()
    if not resume_text:
        resume_text = await MasterProfileService.fetch_master_resume_text()

    jd_keywords = []
    if req.job_description:
        jd_keywords = ATSScorer.extract_keywords_from_jd(req.job_description)

    return ATSScorer.evaluate_match(
        resume_text=resume_text,
        jd_keywords=jd_keywords,
        target_role=req.target_role
    )

@router.post("/edit", response_model=PrecisionEditResponse)
async def precision_edit_resume(req: PrecisionEditRequest):
    """
    Surgically modifies a candidate's resume based on user instruction.
    Alters ONLY the requested field, bullet point, or section without rewriting past facts.
    Returns the updated markdown, structured diff (before/after/section/description),
    updated ATS score, and compiled PDF/DOCX documents.
    """
    current_md = req.current_markdown
    if not current_md or not current_md.strip():
        current_md = await MasterProfileService.fetch_master_resume_text()

    target_role = req.target_role or "Senior Python Backend Developer"
    target_company = req.target_company or "Target Company"

    edit_res = await ResumeOrchestrator.run_precision_edit(
        current_markdown=current_md,
        instruction=req.instruction,
        target_role=target_role,
        target_company=target_company,
        model_preference=req.model or "auto"
    )

    updated_md = edit_res["updated_markdown"]
    diff_data = edit_res["diff"]
    suggested_words = edit_res.get("suggested_power_words", [])

    eval_report = ATSScorer.evaluate_match(updated_md, target_role=target_role)

    pdf_filename = None
    html_filename = None
    docx_filename = None

    if req.recompile_documents:
        clean_company = "".join(c for c in target_company if c.isalnum() or c in (' ', '_', '-')).strip()
        clean_title = "".join(c for c in target_role if c.isalnum() or c in (' ', '_', '-')).strip()
        prefix = f"Resume_{clean_company}_{clean_title}".replace(" ", "_").strip("_")
        if not prefix:
            prefix = "Tailored_Resume"

        res_meta = HTMLResumeGenerator.generate_html_and_pdf(
            markdown_text=updated_md,
            filename_prefix=prefix,
            target_title=target_role,
            target_company=target_company,
            template_id=req.template_id or "grid_matrix",
            palette_id=req.palette_id or "enterprise_blue",
            font_id=req.font_id or "modern_inter",
            target_pages=req.target_pages or 2
        )
        pdf_filename = res_meta.get("pdf_filename")
        html_filename = res_meta.get("html_filename")
        full_docx_path = DOCXResumeGenerator.generate_docx(updated_md, prefix)
        docx_filename = os.path.basename(full_docx_path)

        # Persist updated markdown into master_resume so subsequent requests reflect the surgical change
        try:
            with open(os.path.join(settings.MASTER_RESUME_DIR, "master_resume.md"), "w", encoding="utf-8") as f:
                f.write(updated_md)
            with open(os.path.join(settings.MASTER_RESUME_DIR, "master_resume.txt"), "w", encoding="utf-8") as f:
                f.write(updated_md)
        except Exception as e:
            print(f"[PrecisionEdit] Warning updating master resume files: {e}")

    return PrecisionEditResponse(
        status="success",
        instruction=req.instruction,
        diff=DiffChange(
            section=diff_data.get("section", "General"),
            target_entity=diff_data.get("target_entity"),
            before=diff_data.get("before", ""),
            after=diff_data.get("after", ""),
            description=diff_data.get("description", req.instruction)
        ),
        updated_markdown=updated_md,
        ats_score=eval_report.score,
        pdf_filename=pdf_filename,
        html_filename=html_filename,
        docx_filename=docx_filename,
        suggested_power_words=suggested_words
    )

@router.post("/paginate", response_model=PaginateResponse)
async def calibrate_resume_pagination(req: PaginateRequest):
    """
    Calibrates candidate's resume content depth, bullet count, and summary detail
    to cleanly and completely fill EXACTLY 1, 2, or 3 pages without awkward trailing entries,
    stranded headers, or empty voids. Recompiles corresponding A4 PDF, styled HTML, and DOCX.
    """
    current_md = req.current_markdown
    if not current_md or not current_md.strip():
        current_md = await MasterProfileService.fetch_master_resume_text()

    target_role = req.target_role or "Senior Python Backend Developer"
    target_company = req.target_company or "Target Company"

    calib_res = await ResumeOrchestrator.run_page_calibration(
        current_markdown=current_md,
        target_pages=req.target_pages,
        target_role=target_role,
        target_company=target_company,
        model_preference=req.model or "auto"
    )

    calibrated_md = calib_res["calibrated_markdown"]
    adjustments = calib_res["summary_of_adjustments"]
    word_count = calib_res["word_count"]

    eval_report = ATSScorer.evaluate_match(calibrated_md, target_role=target_role)

    clean_company = "".join(c for c in target_company if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_title = "".join(c for c in target_role if c.isalnum() or c in (' ', '_', '-')).strip()
    prefix = f"Resume_{clean_company}_{clean_title}".replace(" ", "_").strip("_")
    if not prefix:
        prefix = "Calibrated_Resume"

    res_meta = HTMLResumeGenerator.generate_html_and_pdf(
        markdown_text=calibrated_md,
        filename_prefix=prefix,
        target_title=target_role,
        target_company=target_company,
        template_id=req.template_id or "grid_matrix",
        palette_id=req.palette_id or "enterprise_blue",
        font_id=req.font_id or "modern_inter",
        target_pages=req.target_pages
    )
    pdf_filename = res_meta.get("pdf_filename")
    html_filename = res_meta.get("html_filename")
    full_docx_path = DOCXResumeGenerator.generate_docx(calibrated_md, prefix)
    docx_filename = os.path.basename(full_docx_path)

    return PaginateResponse(
        status="success",
        target_pages=req.target_pages,
        calibrated_markdown=calibrated_md,
        word_count=word_count,
        summary_of_adjustments=adjustments,
        ats_score=eval_report.score,
        pdf_filename=pdf_filename,
        html_filename=html_filename,
        docx_filename=docx_filename
    )

@router.post("/parse", response_model=ParseResumeResponse)
async def parse_uploaded_resume(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    save_as_master: bool = Form(False),
    target_role: Optional[str] = Form(None)
):
    """
    Parses and extracts clean text & structured metadata from PDF, DOCX, or text files.
    Runs deep structural audit, extracts contact info & verified skills, and
    optionally registers the document as the candidate's active master profile.
    """
    if file is not None and file.filename:
        filename = file.filename
        file_bytes = await file.read()
        extracted_text = DocumentParserService.extract_text(file_bytes, filename)
    elif raw_text and raw_text.strip():
        filename = "pasted_resume.txt"
        file_bytes = raw_text.strip().encode("utf-8")
        extracted_text = raw_text.strip()
    else:
        raise HTTPException(status_code=400, detail="Must provide either an uploaded file or raw_text form field.")

    parsed = DocumentParserService.heuristic_parse_resume(extracted_text)

    eval_report = ATSScorer.evaluate_match(
        resume_text=extracted_text,
        target_role=target_role or parsed.get("headline") or "Software Engineer"
    )

    master_saved = False
    if save_as_master:
        os.makedirs(settings.MASTER_RESUME_DIR, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = ".pdf"
        target_path = os.path.join(settings.MASTER_RESUME_DIR, f"master_resume{ext}")
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        with open(os.path.join(settings.MASTER_RESUME_DIR, "master_resume.txt"), "w", encoding="utf-8") as f:
            f.write(extracted_text)
        master_saved = True

    return ParseResumeResponse(
        status="success",
        filename=filename,
        parsed_profile=parsed,
        raw_text=extracted_text,
        ats_score=eval_report.score,
        char_count=len(extracted_text),
        word_count=len(extracted_text.split()),
        master_saved=master_saved
    )

@router.post("/parse-text", response_model=ParseResumeResponse)
async def parse_resume_text(req: ParseTextRequest):
    """
    Parses and extracts structured profile data from raw resume text.
    Evaluates ATS score and optionally saves as master profile.
    """
    raw_text = req.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text cannot be empty.")

    parsed = DocumentParserService.heuristic_parse_resume(raw_text)
    eval_report = ATSScorer.evaluate_match(
        resume_text=raw_text,
        target_role=req.target_role or parsed.get("headline") or "Software Engineer"
    )

    master_saved = False
    if req.save_as_master:
        os.makedirs(settings.MASTER_RESUME_DIR, exist_ok=True)
        with open(os.path.join(settings.MASTER_RESUME_DIR, "master_resume.txt"), "w", encoding="utf-8") as f:
            f.write(raw_text)
        master_saved = True

    return ParseResumeResponse(
        status="success",
        filename="resume_text.txt",
        parsed_profile=parsed,
        raw_text=raw_text,
        ats_score=eval_report.score,
        char_count=len(raw_text),
        word_count=len(raw_text.split()),
        master_saved=master_saved
    )

@router.post("/draft", response_model=DraftResumeResponse)
async def draft_resume_from_intake(req: DraftResumeRequest):
    """
    Synthesizes candidate intake notes, project descriptions, skills, and education
    into a professional, fully-formatted ATS resume from scratch.
    Compiles matching A4 PDF and DOCX exports.
    """
    target_role = req.target_role or "Software Engineer"
    target_company = req.target_company or "Target Company"

    draft_res = await ResumeOrchestrator.run_draft_synthesis(
        candidate_name=req.candidate_name,
        target_role=target_role,
        is_fresher=req.is_fresher,
        summary_notes=req.summary_notes or "",
        experience=req.experience,
        education=req.education,
        skills=req.skills,
        projects=req.projects,
        certifications=req.certifications,
        target_company=target_company,
        model_preference="auto"
    )

    markdown_content = draft_res["markdown_content"]
    exec_summary = draft_res.get("executive_summary", "")
    suggested_words = draft_res.get("suggested_power_words", [])

    eval_report = ATSScorer.evaluate_match(
        resume_text=markdown_content,
        target_role=target_role
    )

    clean_name = "".join(c for c in req.candidate_name if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_role = "".join(c for c in target_role if c.isalnum() or c in (' ', '_', '-')).strip()
    prefix = f"Resume_Draft_{clean_name}_{clean_role}".replace(" ", "_").strip("_")
    if not prefix:
        prefix = "Draft_Resume"

    res_meta = HTMLResumeGenerator.generate_html_and_pdf(
        markdown_text=markdown_content,
        filename_prefix=prefix,
        target_title=target_role,
        target_company=target_company,
        template_id=req.template_id or "grid_matrix",
        palette_id=req.palette_id or "enterprise_blue",
        font_id=req.font_id or "modern_inter",
        target_pages=req.target_pages or (1 if req.is_fresher else 2)
    )
    pdf_filename = res_meta.get("pdf_filename")
    html_filename = res_meta.get("html_filename")
    full_docx_path = DOCXResumeGenerator.generate_docx(markdown_content, prefix)
    docx_filename = os.path.basename(full_docx_path)

    return DraftResumeResponse(
        status="success",
        candidate_name=req.candidate_name,
        target_role=target_role,
        markdown_content=markdown_content,
        executive_summary=exec_summary,
        ats_score=eval_report.score,
        pdf_filename=pdf_filename,
        html_filename=html_filename,
        docx_filename=docx_filename,
        suggested_power_words=suggested_words
    )

@router.post("/tailor/stream")
async def stream_tailor_resume(
    req: TailorRequest,
    db: AsyncSession = Depends(get_db)
):
    """Real-time SSE stream tailoring candidate resume for a target job."""
    # Ensure master resume text is available only if in tailor mode
    generation_mode = req.generation_mode or "tailor"
    master_text = ""
    if generation_mode == "tailor":
        master_text = req.master_resume_text
        if not master_text:
            master_text = await MasterProfileService.fetch_master_resume_text()

    target_title = req.job_title or "Senior Backend Engineer"
    target_company = req.company or "Target Company"
    job_desc = req.job_description or f"Senior Backend Engineer role at {target_company} requiring Python, FastAPI, and PostgreSQL."

    async def event_generator():
        tailored_data = None
        async for packet in ResumeOrchestrator.stream_tailoring(
            target_title=target_title,
            target_company=target_company,
            job_description=job_desc,
            master_resume_text=master_text,
            target_pages=req.target_pages or 2,
            model_preference=req.model or "auto",
            template_id=req.template_id,
            palette_id=req.palette_id,
            font_id=req.font_id or "modern_inter",
            generation_mode=generation_mode,
            anthropic_key=req.anthropic_key,
            gemini_key=req.gemini_key,
            nvidia_key=req.nvidia_key
        ):
            event_type = packet.get("event", "message")
            data = packet.get("data", "")
            
            if event_type == "done":
                tailored_data = data
                
            payload = json.dumps(data)
            yield f"event: {event_type}\ndata: {payload}\n\n"

        # Persist to database upon successful completion
        if tailored_data:
            try:
                record = TailoredResume(
                    id=str(uuid.uuid4()),
                    job_id=req.job_id,
                    session_id=req.session_id,
                    target_job_title=target_title,
                    target_company=target_company,
                    original_score=tailored_data.get("original_score", 0),
                    tailored_score=tailored_data.get("tailored_score", 0),
                    matched_keywords=tailored_data.get("matched_keywords", []),
                    missing_keywords=tailored_data.get("missing_keywords", []),
                    markdown_content=tailored_data.get("markdown_content", ""),
                    pdf_path=tailored_data.get("pdf_filename"),
                    docx_path=tailored_data.get("docx_filename")
                )
                db.add(record)
                await db.commit()
            except Exception as e:
                print(f"[Routes] Database save error: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/recompile")
async def recompile_resume(req: RecompileRequest):
    """
    Instantly re-renders an existing tailored resume into a newly selected
    layout skeleton and/or CSS theme palette in <300ms without LLM lag.
    """
    target_title = req.target_job_title or "Python Backend Developer"
    target_company = req.target_company or "General Profile"
    safe_company = target_company.replace(" ", "_")
    safe_title = target_title.replace(" ", "_")
    filename_prefix = f"Resume_{safe_company}_{safe_title}"

    resolved_pages = req.target_pages if (req.target_pages and req.target_pages >= 1) else (2 if req.template_id == "grid_matrix" else 1)
    resolved_tpl = req.template_id or ("grid_matrix" if resolved_pages >= 2 else "tech_sidebar")
    resolved_pal = req.palette_id or "enterprise_blue"
    resolved_font = req.font_id or "modern_inter"

    res_meta = HTMLResumeGenerator.generate_html_and_pdf(
        markdown_text=req.markdown_text,
        filename_prefix=filename_prefix,
        target_title=target_title,
        target_company=target_company,
        target_pages=resolved_pages,
        template_id=resolved_tpl,
        palette_id=resolved_pal,
        font_id=resolved_font
    )
    docx_font = HTMLResumeGenerator.FONTS.get(resolved_font, {}).get("docx_font", "Calibri")
    docx_filename = DOCXResumeGenerator.generate_docx(req.markdown_text, filename_prefix, font_name=docx_font)

    jd_keywords = ATSScorer.extract_keywords_from_jd(req.job_description or "")
    eval_report = ATSScorer.evaluate_match(req.markdown_text, jd_keywords)

    return {
        "status": "success",
        "original_score": eval_report.score,
        "tailored_score": eval_report.score,
        "matched_keywords": eval_report.matched_skills,
        "missing_keywords": eval_report.missing_skills,
        "markdown_content": req.markdown_text,
        "pdf_filename": res_meta["pdf_filename"],
        "html_filename": res_meta["html_filename"],
        "docx_filename": os.path.basename(docx_filename),
        "template_id": res_meta["template_id"],
        "template_name": res_meta["template_name"],
        "palette_id": res_meta["palette_id"],
        "palette_name": res_meta["palette_name"],
        "font_id": res_meta.get("font_id", "modern_inter"),
        "font_name": res_meta.get("font_name", "Inter")
    }

@router.post("/refine/stream")
async def stream_refine_resume(
    req: RefineRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Interactive SSE endpoint allowing users to chat directly with Resume Prep Agent (Agent 2)
    to refine content, change layout skeletons, swap theme palettes, or adjust bullet points.
    """
    target_title = req.job_title or "Python Backend Developer"
    target_company = req.company or "Target Company"
    job_desc = req.job_description or ""
    current_md = req.current_markdown
    if not current_md or not current_md.strip():
        current_md = await MasterProfileService.fetch_master_resume_text()

    async def event_generator():
        tailored_data = None
        async for packet in ResumeOrchestrator.stream_refinement(
            user_instruction=req.user_instruction,
            current_markdown=current_md,
            target_title=target_title,
            target_company=target_company,
            job_description=job_desc,
            target_pages=req.target_pages,
            template_id=req.template_id,
            palette_id=req.palette_id,
            model_preference=req.model or "auto",
            anthropic_key=req.anthropic_key,
            gemini_key=req.gemini_key,
            nvidia_key=req.nvidia_key
        ):
            event_type = packet.get("event", "message")
            data = packet.get("data", "")

            if event_type == "done":
                tailored_data = data

            payload = json.dumps(data)
            yield f"event: {event_type}\ndata: {payload}\n\n"

        if tailored_data and req.job_id:
            try:
                record = TailoredResume(
                    id=str(uuid.uuid4()),
                    job_id=req.job_id,
                    target_job_title=target_title,
                    target_company=target_company,
                    original_score=tailored_data.get("original_score", 0),
                    tailored_score=tailored_data.get("tailored_score", 0),
                    matched_keywords=tailored_data.get("matched_keywords", []),
                    missing_keywords=tailored_data.get("missing_keywords", []),
                    markdown_content=tailored_data.get("markdown_content", ""),
                    pdf_path=tailored_data.get("pdf_filename"),
                    docx_path=tailored_data.get("docx_filename")
                )
                db.add(record)
                await db.commit()
            except Exception as e:
                print(f"[Routes] Database save error during refine: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Serves compiled ATS PDF, styled HTML, or editable DOCX files."""
    file_path = os.path.join(settings.EXPORTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested export file not found.")

    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".html") or filename.endswith(".htm"):
        media_type = "text/html"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )

@router.get("/preview/{filename}")
async def preview_file(filename: str):
    """Serves the rendered 2-page HTML resume inline for interactive browser preview."""
    file_path = os.path.join(settings.EXPORTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file not found.")

    media_type = "text/html" if filename.endswith((".html", ".htm")) else "application/pdf"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.get("/info/{filename}")
async def get_resume_info(filename: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves metadata, active template/palette/font, and markdown content for an exported resume file.
    Enables ATS Studio (ResumeTailorModal) to immediately load full state for live customization & editing.
    """
    clean_fn = filename.split("?")[0].strip()
    base_name = re.sub(r'\.(?:html|pdf|docx|md)$', '', clean_fn, flags=re.IGNORECASE)

    # 1. Try reading matching .md file
    md_file = os.path.join(settings.EXPORTS_DIR, f"{base_name}.md")
    md_content = ""
    if os.path.exists(md_file):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception as e:
            print(f"[Routes] Error reading markdown {md_file}: {e}")

    # 2. If not found on disk, fallback to master resume text
    if not md_content.strip():
        md_content = await MasterProfileService.fetch_master_resume_text()

    # 3. Detect active layout template
    tpl_id = "classic_ats" if "classic_ats" in clean_fn else "grid_matrix"
    for tpl in ["classic_ats", "tech_sidebar", "minimalist", "grid_matrix", "modern_header"]:
        if tpl in clean_fn:
            tpl_id = tpl
            break

    # 4. Detect active palette
    pal_id = "executive_navy" if "executive_navy" in clean_fn else "enterprise_blue"
    for pal in ["executive_navy", "enterprise_blue", "emerald_executive", "modern_slate", "teal_technical", "warm_classic"]:
        if pal in clean_fn:
            pal_id = pal
            break

    # 5. Detect active font
    font_id = "liberation_sans" if "liberation_sans" in clean_fn else "modern_inter"
    for fnt in ["liberation_sans", "modern_inter", "clean_roboto", "universal_arial", "executive_merriweather", "classic_garamond"]:
        if fnt in clean_fn:
            font_id = fnt
            break

    target_pages = 1 if ("_1p." in clean_fn or "-1p." in clean_fn) else 2

    return {
        "status": "success",
        "filename": clean_fn,
        "html_filename": f"{base_name}.html",
        "pdf_filename": f"{base_name}.pdf",
        "docx_filename": f"{base_name}.docx",
        "template_id": tpl_id,
        "palette_id": pal_id,
        "font_id": font_id,
        "target_pages": target_pages,
        "markdown_content": md_content,
        "ats_score": 85
    }

@router.get("/tailored/{job_id}")
async def get_tailored_resume_for_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves previously generated tailored resume for a given job."""
    result = await db.execute(
        select(TailoredResume)
        .where(TailoredResume.job_id == job_id)
        .order_by(TailoredResume.created_at.desc())
    )
    record = result.scalars().first()
    if not record:
        return {"exists": False}

    return {
        "exists": True,
        "id": record.id,
        "job_id": record.job_id,
        "target_job_title": record.target_job_title,
        "target_company": record.target_company,
        "original_score": record.original_score,
        "tailored_score": record.tailored_score,
        "matched_keywords": record.matched_keywords,
        "missing_keywords": record.missing_keywords,
        "markdown_content": record.markdown_content,
        "pdf_url": f"/api/resume/download/{record.pdf_path}" if record.pdf_path else None,
        "docx_url": f"/api/resume/download/{record.docx_path}" if record.docx_path else None,
        "created_at": record.created_at.isoformat()
    }

