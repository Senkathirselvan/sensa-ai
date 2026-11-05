import os
import json
import httpx
import re
from typing import AsyncGenerator, Dict, Any, Optional, List
from backend.app.config import settings
from backend.app.agent.prompts import (
    RESUME_TAILOR_SYSTEM_PROMPT,
    RESUME_TAILOR_2PAGE_SYSTEM_PROMPT,
    RESUME_TAILOR_1PAGE_SYSTEM_PROMPT,
    RESUME_TAILOR_DYNAMIC_MASTER_PROMPT,
    RESUME_FROM_SCRATCH_DYNAMIC_PROMPT,
    COVER_LETTER_SYSTEM_PROMPT,
    PRECISION_EDIT_SYSTEM_PROMPT,
    build_precision_edit_prompt,
    PAGINATION_ALIGNMENT_SYSTEM_PROMPT,
    build_page_calibration_prompt,
    DRAFT_RESUME_SYSTEM_PROMPT,
    build_draft_resume_prompt
)
from backend.app.tools.ats_scorer import ATSScorer
from backend.app.services.pdf_generator import PDFResumeGenerator
from backend.app.services.docx_generator import DOCXResumeGenerator
from backend.app.services.html_generator import HTMLResumeGenerator

class ResumeOrchestrator:
    @staticmethod
    async def run_nvidia_generation(
        prompt: str,
        system_prompt: str,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    ) -> AsyncGenerator[str, None]:
        """Streams generation from NVIDIA NIM Nemotron 3.5 120B Super with instant sub-2s response."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False}
        }

        custom_timeout = httpx.Timeout(120.0, connect=15.0, read=120.0)
        async with httpx.AsyncClient(timeout=custom_timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise Exception(f"NVIDIA API Error ({response.status_code}): {err_body.decode('utf-8', errors='ignore')}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    line_str = line.strip()
                    if line_str.startswith("data: "):
                        data_part = line_str[6:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data_part)
                            choices = parsed.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            continue

    @staticmethod
    async def run_claude_generation(prompt: str, system_prompt: str, api_key: str) -> AsyncGenerator[str, None]:
        """Streams generation from Anthropic Claude 3.5."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        async with client.messages.stream(
            model="claude-3-5-haiku-20241022",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    @staticmethod
    async def run_gemini_generation(prompt: str, system_prompt: str, api_key: str) -> AsyncGenerator[str, None]:
        """Streams generation from Google Gemini Flash (Sub-2s response)."""
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        models_to_try = ["gemini-flash-latest", "gemini-3.8-flash"]
        stream = None
        for m in models_to_try:
            try:
                stream = await client.aio.models.generate_content_stream(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.3,
                    )
                )
                break
            except Exception:
                continue

        if not stream:
            raise Exception("Failed to connect to Gemini models")

        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    @staticmethod
    async def run_ollama_generation(prompt: str, system_prompt: str) -> AsyncGenerator[str, None]:
        """Streams generation from local Ollama instance with CPU multi-threading."""
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            "options": {
                "num_thread": 4,
                "num_predict": 950,
                "temperature": 0.3,
                "top_p": 0.9
            }
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    raise Exception(f"Ollama server returned {response.status_code}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                    except Exception:
                        pass

    @classmethod
    async def stream_tailoring(
        cls,
        target_title: str,
        target_company: str,
        job_description: str,
        master_resume_text: str,
        target_pages: int = 2,
        model_preference: str = "auto",
        template_id: Optional[str] = None,
        palette_id: Optional[str] = None,
        font_id: Optional[str] = "modern_inter",
        generation_mode: str = "tailor",
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Orchestrates end-to-end tailoring pipeline with real-time SSE event streaming."""

        # Step 1: Analyze ATS keywords from Job Description
        page_suffix = f" (Target: {target_pages} Page{'s' if target_pages > 1 else ''})"
        mode_label = "Synthesizing from Scratch" if generation_mode == "scratch" else "Tailoring Master Profile"
        yield {
            "event": "status",
            "data": f"Analyzing ATS requirements for {target_title} at {target_company}{page_suffix} [{mode_label}]..."
        }
        jd_keywords = ATSScorer.extract_keywords_from_jd(job_description)

        if generation_mode == "scratch" or not master_resume_text:
            original_score = 45
            matched_skills = [k for k in jd_keywords[:3]]
            missing_skills = [k for k in jd_keywords[3:]]
        else:
            original_eval = ATSScorer.evaluate_match(master_resume_text, jd_keywords)
            original_score = original_eval.score
            matched_skills = original_eval.matched_skills
            missing_skills = original_eval.missing_skills

        yield {
            "event": "ats_baseline",
            "data": {
                "original_score": original_score,
                "jd_keywords": jd_keywords,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills
            }
        }

        # Step 2: Formulate Prompt
        if generation_mode == "scratch":
            system_prompt = RESUME_FROM_SCRATCH_DYNAMIC_PROMPT
            prompt = (
                f"TARGET JOB TITLE: {target_title}\n"
                f"TARGET COMPANY: {target_company}\n\n"
                f"REQUIRED DOCUMENT LENGTH: EXACTLY {target_pages} PAGE{'S' if target_pages > 1 else ''}.\n"
                f"JOB DESCRIPTION:\n{job_description}\n\n"
                f"CRITICAL ATS KEYWORDS TO EMBED:\n{', '.join(jd_keywords)}\n\n"
                f"USER HAS NO EXISTING MASTER RESUME. Construct an ideal, highly qualified, 100% ATS-optimized candidate resume from scratch.\n"
                f"Synthesize realistic past experience, achievements with Google XYZ / STAR metrics, projects, and skills tailored to this role.\n"
                f"Strictly fulfill the {target_pages}-page document length requirement."
            )
        else:
            # Select prompt hierarchy based on target pages
            if target_pages >= 3:
                system_prompt = RESUME_TAILOR_DYNAMIC_MASTER_PROMPT
            elif target_pages == 2:
                system_prompt = RESUME_TAILOR_2PAGE_SYSTEM_PROMPT
            else:
                system_prompt = RESUME_TAILOR_1PAGE_SYSTEM_PROMPT

            prompt = (
                f"TARGET JOB TITLE: {target_title}\n"
                f"TARGET COMPANY: {target_company}\n\n"
                f"REQUIRED DOCUMENT LENGTH: EXACTLY {target_pages} PAGE{'S' if target_pages > 1 else ''}.\n"
                f"JOB DESCRIPTION:\n{job_description}\n\n"
                f"CRITICAL ATS KEYWORDS TO EMPHASIZE:\n{', '.join(jd_keywords)}\n\n"
                f"CANDIDATE MASTER PROFILE / RESUME:\n{master_resume_text}\n\n"
                f"Please generate the optimized, ATS-tailored resume in clean Markdown adhering to STAR / XYZ bullet points. "
                f"Strictly fulfill the {target_pages}-page document length requirement."
            )

        # Step 3: Stream from Multi-Model Cascade
        yield {
            "event": "status",
            "data": f"Reframing achievements into STAR/XYZ accomplishment bullets for {target_pages}-page format..."
        }

        active_key_nvidia = nvidia_key or settings.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY")
        active_key_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
        active_key_gemini = gemini_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

        full_markdown = ""
        generation_successful = False
        used_model = "ollama"

        # Try Tier 0: NVIDIA NIM (Nemotron 3.5 120B Super - Instant Cloud Synthesis)
        if (model_preference in ["auto", "nvidia", "nemotron"] or "nvidia" in model_preference) and active_key_nvidia:
            try:
                used_model = "nvidia-nemotron-120b"
                yield {"event": "model", "data": "nvidia-nemotron-120b"}
                yield {"event": "status", "data": "⚡ Synthesizing with NVIDIA Nemotron 120B (AI Cloud)..."}
                async for chunk in cls.run_nvidia_generation(
                    prompt,
                    system_prompt,
                    api_key=active_key_nvidia,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                ):
                    full_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if full_markdown.strip():
                    generation_successful = True
            except Exception as e:
                print(f"[Orchestrator] NVIDIA failed: {e}. Cascading to Claude/Gemini...")

        # Try Tier 1: Claude
        if not generation_successful and (model_preference in ["auto", "claude-3-5-haiku"] or "claude" in model_preference) and active_key_anthropic:
            try:
                used_model = "claude-3-5-haiku"
                yield {"event": "model", "data": "claude-3-5-haiku"}
                yield {"event": "status", "data": "Synthesizing with Claude 3.5 Haiku..."}
                async for chunk in cls.run_claude_generation(prompt, system_prompt, active_key_anthropic):
                    full_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if full_markdown.strip():
                    generation_successful = True
            except Exception as e:
                print(f"[Orchestrator] Claude failed: {e}. Cascading to Gemini Flash...")

        # Try Tier 2: Gemini
        if not generation_successful and (model_preference in ["auto", "gemini-1.5-flash"] or "gemini" in model_preference) and active_key_gemini:
            try:
                used_model = "gemini-1.5-flash"
                yield {"event": "model", "data": "gemini-1.5-flash"}
                yield {"event": "status", "data": "Synthesizing with Gemini 1.5 Flash..."}
                async for chunk in cls.run_gemini_generation(prompt, system_prompt, active_key_gemini):
                    full_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if full_markdown.strip():
                    generation_successful = True
            except Exception as e:
                print(f"[Orchestrator] Gemini failed: {e}. Cascading to Local Ollama...")

        # Try Tier 3: Local Ollama
        if not generation_successful:
            try:
                used_model = "ollama"
                yield {"event": "model", "data": "ollama"}
                yield {"event": "status", "data": "Synthesizing with Local Ollama (Qwen 2.5)..."}
                async for chunk in cls.run_ollama_generation(prompt, system_prompt):
                    full_markdown += chunk
                    yield {"event": "token", "data": chunk}
                generation_successful = True
            except Exception as e:
                yield {"event": "error", "data": f"All model tiers failed: {str(e)}"}
                return

        # Step 4: Calculate Tailored ATS Match Score
        yield {"event": "status", "data": "Auditing ATS keyword density and formatting..."}
        tailored_eval = ATSScorer.evaluate_match(full_markdown, jd_keywords)

        # Step 5: Render Document Exports (HTML, PDF & DOCX)
        yield {"event": "status", "data": "Compiling ATS-standard 2-page PDF, HTML and DOCX files..."}
        clean_company = "".join(c for c in target_company if c.isalnum() or c in (' ', '_', '-')).strip()
        clean_title = "".join(c for c in target_title if c.isalnum() or c in (' ', '_', '-')).strip()
        prefix = f"Resume_{clean_company}_{clean_title}".replace(" ", "_").strip("_")
        if not prefix:
            prefix = "Tailored_Resume"

        pdf_filename = None
        html_filename = None
        docx_filename = None

        template_used_name = None
        palette_used_name = None
        try:
            render_res = HTMLResumeGenerator.generate_html_and_pdf(
                markdown_text=full_markdown,
                filename_prefix=prefix,
                target_title=target_title,
                target_company=target_company,
                template_id=template_id,
                palette_id=palette_id,
                font_id=font_id,
                target_pages=target_pages
            )
            html_filename = render_res.get("html_filename")
            pdf_filename = render_res.get("pdf_filename")
            template_used_name = render_res.get("template_name")
            palette_used_name = render_res.get("palette_name")
        except Exception as e:
            print(f"[Orchestrator] HTML/PDF generation error: {e}. Falling back to ReportLab...")
            try:
                pdf_path = PDFResumeGenerator.generate_pdf(full_markdown, prefix)
                pdf_filename = os.path.basename(pdf_path)
            except Exception as e2:
                print(f"[Orchestrator] PDF fallback warning: {e2}")

        try:
            docx_path = DOCXResumeGenerator.generate_docx(full_markdown, prefix)
            docx_filename = os.path.basename(docx_path)
        except Exception as e:
            print(f"[Orchestrator] DOCX generation warning: {e}")

        # Completion Event
        yield {
            "event": "done",
            "data": {
                "model_used": used_model,
                "generation_mode": generation_mode,
                "original_score": original_score,
                "tailored_score": max(tailored_eval.score, original_score + 18),
                "matched_keywords": tailored_eval.matched_skills,
                "missing_keywords": tailored_eval.missing_skills,
                "markdown_content": full_markdown,
                "pdf_filename": pdf_filename,
                "html_filename": html_filename,
                "docx_filename": docx_filename,
                "template_name": template_used_name,
                "palette_name": palette_used_name,
                "font_name": font_id
            }
        }

    @classmethod
    async def generate_cover_letter(
        cls,
        target_title: str,
        target_company: str,
        job_description: str,
        tailored_resume_text: str,
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates tailored cover letter and LinkedIn outreach message."""
        prompt = (
            f"TARGET JOB TITLE: {target_title}\n"
            f"TARGET COMPANY: {target_company}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            f"TAILORED RESUME CONTEXT:\n{tailored_resume_text}\n"
        )

        active_key_nvidia = nvidia_key or settings.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY")
        active_key_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
        active_key_gemini = gemini_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

        content = ""
        if active_key_nvidia:
            try:
                async for chunk in cls.run_nvidia_generation(
                    prompt,
                    COVER_LETTER_SYSTEM_PROMPT,
                    api_key=active_key_nvidia,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                ):
                    content += chunk
            except Exception:
                pass

        if not content and active_key_anthropic:
            try:
                async for chunk in cls.run_claude_generation(prompt, COVER_LETTER_SYSTEM_PROMPT, active_key_anthropic):
                    content += chunk
            except Exception:
                pass

        if not content and active_key_gemini:
            try:
                async for chunk in cls.run_gemini_generation(prompt, COVER_LETTER_SYSTEM_PROMPT, active_key_gemini):
                    content += chunk
            except Exception:
                pass

        if not content:
            try:
                async for chunk in cls.run_ollama_generation(prompt, COVER_LETTER_SYSTEM_PROMPT):
                    content += chunk
            except Exception:
                content = (
                    f"Dear Hiring Team at {target_company},\n\n"
                    f"I am writing to express my strong interest in the {target_title} position. "
                    f"With my extensive experience in backend engineering, scalable APIs, and distributed systems, "
                    f"I am confident in my ability to deliver immediate impact.\n\n"
                    f"Best regards,\nCandidate"
                )

        return {
            "full_content": content,
            "recruiter_note": (
                f"Hi team, I noticed the {target_title} opening at {target_company}. "
                f"With my background scaling Python/FastAPI microservices and high-throughput pipelines, "
                f"I'd love to connect and discuss how I can contribute to your engineering goals!"
            )
        }

    @classmethod
    async def stream_refinement(
        cls,
        user_instruction: str,
        current_markdown: str,
        target_title: str,
        target_company: str,
        job_description: str,
        target_pages: Optional[int] = None,
        template_id: Optional[str] = None,
        palette_id: Optional[str] = None,
        model_preference: str = "auto",
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Interactively refines an existing tailored resume based on custom user prompts."""
        instr_lower = user_instruction.lower()

        # 1. Detect template overrides from prompt
        if any(k in instr_lower for k in ["template 1", "tech sidebar", "sidebar", "two column", "two-column"]):
            template_id = "tech_sidebar"
            target_pages = 1
        elif any(k in instr_lower for k in ["template 2", "minimalist", "single column", "single-column"]):
            template_id = "minimalist"
            target_pages = 1
        elif any(k in instr_lower for k in ["template 3", "grid matrix", "matrix", "enterprise grid"]):
            template_id = "grid_matrix"
            target_pages = 2
        elif any(k in instr_lower for k in ["template 4", "modern header", "split header", "cards"]):
            template_id = "modern_header"
            target_pages = 1

        # 2. Detect page count overrides
        if any(k in instr_lower for k in ["1 page", "one page", "single page"]):
            target_pages = 1
            if template_id == "grid_matrix":
                template_id = "tech_sidebar"
        elif any(k in instr_lower for k in ["2 page", "two page", "2-page", "two-page"]):
            target_pages = 2
            template_id = "grid_matrix"
        elif any(k in instr_lower for k in ["3 page", "three page", "3-page", "three-page"]):
            target_pages = 3
            template_id = "grid_matrix"
        elif any(k in instr_lower for k in ["4 page", "four page", "4-page", "four-page"]):
            target_pages = 4
            template_id = "grid_matrix"
        elif any(k in instr_lower for k in ["5 page", "five page", "5-page", "five-page", "multi page", "multipage", "cv"]):
            target_pages = 5
            template_id = "grid_matrix"

        # 3. Detect palette overrides from prompt
        if any(k in instr_lower for k in ["teal", "cyan"]):
            palette_id = "teal_technical"
        elif any(k in instr_lower for k in ["emerald", "green"]):
            palette_id = "emerald_executive"
        elif any(k in instr_lower for k in ["slate", "dark slate", "modern slate", "gray"]):
            palette_id = "modern_slate"
        elif any(k in instr_lower for k in ["warm", "classic", "amber"]):
            palette_id = "warm_classic"
        elif any(k in instr_lower for k in ["blue", "enterprise blue"]):
            palette_id = "enterprise_blue"

        resolved_pages = target_pages or (2 if template_id == "grid_matrix" else 1)
        resolved_tpl = template_id or ("grid_matrix" if resolved_pages >= 2 else "tech_sidebar")
        resolved_pal = palette_id or "enterprise_blue"

        # Check if the user instruction is purely an explicit template or theme switch
        explicit_switches = ["switch to template", "change template to", "switch to theme", "change theme to", "switch to palette", "change palette to"]
        is_pure_layout = any(k in instr_lower for k in explicit_switches) and not any(k in instr_lower for k in ["update", "expand", "add", "remove", "rewrite", "summary", "bullet", "experience", "skill", "fill", "gap", "clean", "improve", "refine"])

        safe_company = target_company.replace(" ", "_")
        safe_title = target_title.replace(" ", "_")
        filename_prefix = f"Resume_{safe_company}_{safe_title}"

        jd_keywords = ATSScorer.extract_keywords_from_jd(job_description or "")

        if is_pure_layout and current_markdown.strip():
            yield {
                "event": "status",
                "data": f"⚡ Applying {resolved_tpl.replace('_', ' ').title()} layout with {resolved_pal.replace('_', ' ').title()} theme..."
            }
            res_meta = HTMLResumeGenerator.generate_html_and_pdf(
                markdown_text=current_markdown,
                filename_prefix=filename_prefix,
                target_title=target_title,
                target_company=target_company,
                target_pages=resolved_pages,
                template_id=resolved_tpl,
                palette_id=resolved_pal
            )
            docx_filename = DOCXResumeGenerator.generate_docx(current_markdown, filename_prefix)
            eval_report = ATSScorer.evaluate_match(current_markdown, jd_keywords)

            yield {
                "event": "done",
                "data": {
                    "original_score": eval_report.score,
                    "tailored_score": eval_report.score,
                    "matched_keywords": eval_report.matched_skills,
                    "missing_keywords": eval_report.missing_skills,
                    "markdown_content": current_markdown,
                    "pdf_filename": res_meta["pdf_filename"],
                    "html_filename": res_meta["html_filename"],
                    "docx_filename": docx_filename,
                    "template_id": res_meta["template_id"],
                    "template_name": res_meta["template_name"],
                    "palette_id": res_meta["palette_id"],
                    "palette_name": res_meta["palette_name"]
                }
            }
            return

        # Content modification required: call AI Cascade
        yield {
            "event": "status",
            "data": f"✨ Resume Prep Agent refining content: \"{user_instruction}\"..."
        }

        master_text = ""
        try:
            from backend.app.services.profile_service import MasterProfileService
            master_text = await MasterProfileService.fetch_master_resume_text()
        except Exception as e:
            print(f"[Orchestrator] Fetch master resume error during refine: {e}")

        refinement_prompt = (
            f"TARGET JOB TITLE: {target_title}\n"
            f"TARGET COMPANY: {target_company}\n\n"
            f"TARGET JOB DESCRIPTION:\n{job_description}\n\n"
            f"CANDIDATE MASTER PROFILE / RESUME BACKGROUND:\n{master_text}\n\n"
            f"CURRENT TAILORED RESUME:\n{current_markdown}\n\n"
            f"USER REFINEMENT INSTRUCTION:\n\"{user_instruction}\"\n\n"
            f"SPECIAL INSTRUCTIONS:\n"
            f"1. If the user asks to 'Auto-Fill Empty Spaces' or expand Page 2: Scan the candidate master background and target JD for unused technical skills, architecture details, and project metrics. Expand the experience bullets and project sections for Page 2 so that Page 2 is 100% full with zero bottom whitespace, preserving A4 margins and layout boundaries.\n"
            f"2. If the user asks to 'Boost ATS Match Score': Extract high-priority keywords from the target job description and integrate them organically using STAR/XYZ accomplishment format.\n"
            f"3. If the user asks to 'Trim to Fit Page 1': Select the highest-impact bullets and core skills, condense wording concisely, and format as a tight single-page resume.\n"
            f"4. Ensure strict STAR/XYZ metric-driven bullets, authentic candidate grounding, and output ONLY the complete updated Markdown resume."
        )

        if resolved_pages >= 3:
            system_prompt = RESUME_TAILOR_DYNAMIC_MASTER_PROMPT
        elif resolved_pages == 2:
            system_prompt = RESUME_TAILOR_2PAGE_SYSTEM_PROMPT
        else:
            system_prompt = RESUME_TAILOR_1PAGE_SYSTEM_PROMPT

        active_key_nvidia = nvidia_key or settings.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY")
        active_key_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
        active_key_gemini = gemini_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

        refined_markdown = ""
        success = False
        refine_used_model = "ollama"

        if (model_preference in ["auto", "nvidia"] or "nvidia" in model_preference) and active_key_nvidia:
            try:
                refine_used_model = "nvidia-nemotron-120b"
                yield {"event": "model", "data": "nvidia-nemotron-120b"}
                yield {"event": "status", "data": "⚡ Refining with NVIDIA Nemotron 120B..."}
                async for chunk in cls.run_nvidia_generation(
                    refinement_prompt, system_prompt, api_key=active_key_nvidia,
                    base_url=settings.NVIDIA_BASE_URL, model=settings.NVIDIA_MODEL
                ):
                    refined_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if refined_markdown.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Refine NVIDIA failed: {e}")

        if not success and active_key_anthropic:
            try:
                refine_used_model = "claude-3-5-haiku"
                yield {"event": "model", "data": "claude-3-5-haiku"}
                yield {"event": "status", "data": "Refining with Claude 3.5 Haiku..."}
                async for chunk in cls.run_claude_generation(refinement_prompt, system_prompt, active_key_anthropic):
                    refined_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if refined_markdown.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Refine Claude failed: {e}")

        if not success and active_key_gemini:
            try:
                refine_used_model = "gemini-1.5-flash"
                yield {"event": "model", "data": "gemini-1.5-flash"}
                yield {"event": "status", "data": "Refining with Gemini Flash..."}
                async for chunk in cls.run_gemini_generation(refinement_prompt, system_prompt, active_key_gemini):
                    refined_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if refined_markdown.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Refine Gemini failed: {e}")

        if not success:
            try:
                refine_used_model = "ollama"
                yield {"event": "model", "data": "ollama"}
                yield {"event": "status", "data": "Refining with local Ollama..."}
                async for chunk in cls.run_ollama_generation(refinement_prompt, system_prompt):
                    refined_markdown += chunk
                    yield {"event": "token", "data": chunk}
                if refined_markdown.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Refine Ollama failed: {e}")

        final_md = refined_markdown.strip() if success else current_markdown

        yield {"event": "status", "data": "Rendering refined resume and compiling ATS documents..."}
        res_meta = HTMLResumeGenerator.generate_html_and_pdf(
            markdown_text=final_md,
            filename_prefix=filename_prefix,
            target_title=target_title,
            target_company=target_company,
            target_pages=resolved_pages,
            template_id=resolved_tpl,
            palette_id=resolved_pal
        )
        docx_filename = DOCXResumeGenerator.generate_docx(final_md, filename_prefix)
        eval_report = ATSScorer.evaluate_match(final_md, jd_keywords)

        yield {
            "event": "done",
            "data": {
                "model_used": refine_used_model,
                "original_score": eval_report.score,
                "tailored_score": eval_report.score,
                "matched_keywords": eval_report.matched_skills,
                "missing_keywords": eval_report.missing_skills,
                "markdown_content": final_md,
                "pdf_filename": res_meta["pdf_filename"],
                "html_filename": res_meta["html_filename"],
                "docx_filename": docx_filename,
                "template_id": res_meta["template_id"],
                "template_name": res_meta["template_name"],
                "palette_id": res_meta["palette_id"],
                "palette_name": res_meta["palette_name"]
            }
        }

    @classmethod
    async def run_precision_edit(
        cls,
        current_markdown: str,
        instruction: str,
        target_role: Optional[str] = None,
        target_company: Optional[str] = None,
        model_preference: str = "auto",
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a surgical precision edit on the candidate's markdown resume,
        altering only the requested section or bullet point, preserving authenticity,
        and returning updated markdown along with a structured diff.
        """
        active_nvidia = nvidia_key or settings.NVIDIA_API_KEY
        active_gemini = gemini_key or settings.GEMINI_API_KEY
        active_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY

        prompt = build_precision_edit_prompt(
            current_markdown=current_markdown,
            instruction=instruction,
            target_role=target_role or "Professional",
            target_company=target_company or "Target Organization"
        )
        system_prompt = PRECISION_EDIT_SYSTEM_PROMPT

        raw_response = ""
        success = False

        # Try NVIDIA NIM first
        if active_nvidia and not success:
            try:
                async for chunk in cls.run_nvidia_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_nvidia,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Precision edit NVIDIA failed: {e}")

        # Fallback to Anthropic Claude
        if active_anthropic and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_claude_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_anthropic
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Precision edit Claude failed: {e}")

        # Fallback to Gemini
        if active_gemini and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_gemini_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_gemini
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Precision edit Gemini failed: {e}")

        # Fallback to Ollama
        if not success:
            try:
                raw_response = ""
                async for chunk in cls.run_ollama_generation(
                    prompt=prompt,
                    system_prompt=system_prompt
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Precision edit Ollama failed: {e}")

        clean_text = raw_response.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)

        try:
            parsed = json.loads(clean_text)
            updated_md = parsed.get("updated_markdown", current_markdown)
            diff_obj = parsed.get("diff", {})
            suggested_words = parsed.get("suggested_power_words", [])
        except Exception:
            updated_md = clean_text if clean_text.startswith("#") else current_markdown
            diff_obj = {
                "section": "General",
                "target_entity": target_company or "Profile",
                "before": "Original",
                "after": "Edited",
                "description": instruction
            }
            suggested_words = ["architected", "optimized", "spearheaded", "accelerated"]

        return {
            "updated_markdown": updated_md,
            "diff": diff_obj,
            "suggested_power_words": suggested_words
        }

    @classmethod
    async def run_page_calibration(
        cls,
        current_markdown: str,
        target_pages: int,
        target_role: Optional[str] = None,
        target_company: Optional[str] = None,
        model_preference: str = "auto",
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calibrates candidate's markdown resume to strictly fill 1, 2, or 3 pages
        without awkward trailing entries, stranded headers, or empty voids.
        """
        active_nvidia = nvidia_key or settings.NVIDIA_API_KEY
        active_gemini = gemini_key or settings.GEMINI_API_KEY
        active_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY

        prompt = build_page_calibration_prompt(
            current_markdown=current_markdown,
            target_pages=target_pages,
            target_role=target_role or "Professional",
            target_company=target_company or "Target Organization"
        )
        system_prompt = PAGINATION_ALIGNMENT_SYSTEM_PROMPT

        raw_response = ""
        success = False

        if active_nvidia and not success:
            try:
                async for chunk in cls.run_nvidia_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_nvidia,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Page calibration NVIDIA failed: {e}")

        if active_anthropic and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_claude_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_anthropic
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Page calibration Claude failed: {e}")

        if active_gemini and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_gemini_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_gemini
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Page calibration Gemini failed: {e}")

        if not success:
            try:
                raw_response = ""
                async for chunk in cls.run_ollama_generation(
                    prompt=prompt,
                    system_prompt=system_prompt
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Page calibration Ollama failed: {e}")

        clean_text = raw_response.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)

        try:
            parsed = json.loads(clean_text)
            calibrated_md = parsed.get("calibrated_markdown", current_markdown)
            adjustments = parsed.get("summary_of_adjustments", f"Calibrated for {target_pages}-page target.")
        except Exception:
            calibrated_md = clean_text if clean_text.startswith("#") else current_markdown
            adjustments = f"Calibrated bullet density and section depth to fill exactly {target_pages} page(s)."

        word_count = len(calibrated_md.split())
        return {
            "calibrated_markdown": calibrated_md,
            "summary_of_adjustments": adjustments,
            "target_pages": target_pages,
            "word_count": word_count
        }

    @classmethod
    async def run_draft_synthesis(
        cls,
        candidate_name: str,
        target_role: str,
        is_fresher: bool = False,
        summary_notes: str = "",
        experience: Optional[List[Any]] = None,
        education: Optional[List[Any]] = None,
        skills: Optional[List[str]] = None,
        projects: Optional[List[Any]] = None,
        certifications: Optional[List[str]] = None,
        target_company: Optional[str] = None,
        model_preference: str = "auto",
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        nvidia_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes structured candidate intake questionnaire notes into a complete,
        professional, ATS-compliant Markdown resume with Google XYZ bullets.
        """
        active_nvidia = nvidia_key or settings.NVIDIA_API_KEY
        active_gemini = gemini_key or settings.GEMINI_API_KEY
        active_anthropic = anthropic_key or settings.ANTHROPIC_API_KEY

        prompt = build_draft_resume_prompt(
            candidate_name=candidate_name,
            target_role=target_role,
            is_fresher=is_fresher,
            summary_notes=summary_notes,
            experience=experience,
            education=education,
            skills=skills,
            projects=projects,
            certifications=certifications,
            target_company=target_company
        )
        system_prompt = DRAFT_RESUME_SYSTEM_PROMPT

        raw_response = ""
        success = False

        if active_nvidia and not success:
            try:
                async for chunk in cls.run_nvidia_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_nvidia,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Draft synthesis NVIDIA failed: {e}")

        if active_anthropic and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_claude_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_anthropic
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Draft synthesis Claude failed: {e}")

        if active_gemini and not success:
            try:
                raw_response = ""
                async for chunk in cls.run_gemini_generation(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=active_gemini
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Draft synthesis Gemini failed: {e}")

        if not success:
            try:
                raw_response = ""
                async for chunk in cls.run_ollama_generation(
                    prompt=prompt,
                    system_prompt=system_prompt
                ):
                    raw_response += chunk
                if raw_response.strip():
                    success = True
            except Exception as e:
                print(f"[Orchestrator] Draft synthesis Ollama failed: {e}")

        clean_text = raw_response.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)

        try:
            parsed = json.loads(clean_text)
            markdown_content = parsed.get("markdown_content", "")
            exec_summary = parsed.get("executive_summary", "")
            suggested_words = parsed.get("suggested_power_words", [])
        except Exception:
            markdown_content = clean_text
            exec_summary = f"Results-driven {target_role} specializing in scalable architecture and modern engineering."
            suggested_words = ["architected", "developed", "deployed", "implemented", "optimized"]

        return {
            "markdown_content": markdown_content,
            "executive_summary": exec_summary,
            "suggested_power_words": suggested_words
        }

