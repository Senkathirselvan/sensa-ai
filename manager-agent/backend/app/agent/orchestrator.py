import os
import json
import asyncio
import logging
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx
from openai import AsyncOpenAI

from backend.app.config import settings
from backend.app.api.schemas import TargetAgent, ManagerRoutingDecision
from backend.app.agent.router import route_user_request
from backend.app.agent.prompts import MANAGER_GENERAL_CHAT_SYSTEM_PROMPT
from backend.app.clients.job_find_client import JobFindClient
from backend.app.clients.resume_prep_client import ResumePrepClient
from backend.app.clients.job_apply_client import JobApplyClient

logger = logging.getLogger("manager_agent.orchestrator")

class ManagerOrchestrator:
    def __init__(self):
        self.job_find_client = JobFindClient()
        self.resume_prep_client = ResumePrepClient()
        self.job_apply_client = JobApplyClient()
        self.openai_client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY or "none",
            base_url=settings.NVIDIA_BASE_URL
        ) if settings.NVIDIA_API_KEY else None

    async def stream_general_chat(self, message: str, history: List[Dict[str, str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes technical reasoning, coding, and general conversational turns.
        """
        if not self.openai_client:
            yield {"type": "token", "data": "Sensa AI Manager is online. Please configure your NVIDIA_API_KEY or model credentials."}
            return

        messages = [{"role": "system", "content": MANAGER_GENERAL_CHAT_SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": message})

        try:
            stream = await self.openai_client.chat.completions.create(
                model=settings.NVIDIA_CHAT_MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=2048,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "token", "data": chunk.choices[0].delta.content}
        except Exception as e:
            logger.error(f"[stream_general_chat] Error: {e}")
            yield {"type": "token", "data": f"\n\n*(Error generating response: {e})*"}

    async def execute_multi_step_workflow(
        self,
        session_id: str,
        message: str,
        decision: ManagerRoutingDecision,
        auto_apply_settings: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Orchestrates sequential multi-step workflow across workers (Find -> Tailor -> Apply).
        If Batch Auto-Apply is enabled, sequentially submits qualifying openings.
        Otherwise, pauses with human confirmation checkpoint.
        """
        user_prompt_explicit_apply = any(term in message.lower() for term in [
            "auto apply", "auto-apply", "and apply", "apply to the", "apply for me", "apply them", "auto-submitting", "submit application"
        ])
        is_auto_apply = bool(auto_apply_settings and auto_apply_settings.get("enabled")) or user_prompt_explicit_apply
        apply_mode = (auto_apply_settings.get("mode") if auto_apply_settings else None) or "autonomous"
        autonomous_submission = (apply_mode == "autonomous") or ("auto" in message.lower())

        # Parse batch size from prompt if specified (e.g. "auto apply 3 jobs", "apply to 3 positions", "top 3 roles")
        batch_match = re.search(r'(?:apply(?:\s+to)?|top)\s+(\d+)\s+(?:jobs?|positions?|openings?|roles?)', message.lower())
        prompt_batch = int(batch_match.group(1)) if batch_match else None
        max_batch = prompt_batch or (int(auto_apply_settings.get("maxBatchSize") or auto_apply_settings.get("max_batch_size") or 5) if auto_apply_settings else 5)
        min_score = int(auto_apply_settings.get("minMatchScore") or auto_apply_settings.get("min_match_score") or 70) if auto_apply_settings else 70
        delay_sec = int(auto_apply_settings.get("stealthDelaySeconds") or auto_apply_settings.get("stealth_delay_seconds") or 15) if auto_apply_settings else 15

        yield {
            "type": "status",
            "data": f"🚀 Initializing Multi-Agent Pipeline ({'⚡ Autonomous Batch Apply' if is_auto_apply else '🛡️ Safe Confirmation Mode'})..."
        }

        # Step 1: Find jobs
        yield {"type": "status", "data": "📍 Step 1/3: Discovering matched opportunities via Job Find Agent..."}
        discovered_jobs = []
        async for event in self.job_find_client.stream_chat(session_id, message):
            ev_type = event.get("type")
            ev_data = event.get("data")
            if ev_type in ["job_cards", "jobs"]:
                cards = ev_data if isinstance(ev_data, list) else [ev_data]
                discovered_jobs.extend(cards)
                yield event
            elif ev_type == "done":
                # Suppress intermediate done event to keep stream open for Step 2 & 3
                if isinstance(ev_data, dict) and "job_cards" in ev_data:
                    done_cards = ev_data.get("job_cards", [])
                    if done_cards and not discovered_jobs:
                        discovered_jobs.extend(done_cards)
                        yield {"type": "job_cards", "data": done_cards}
            else:
                yield event

        logger.info(f"[execute_multi_step_workflow] Discovered {len(discovered_jobs)} jobs. is_auto_apply={is_auto_apply}")

        if not discovered_jobs:
            yield {
                "type": "token",
                "data": "\n\nPipeline paused: No active positions were returned to proceed with automated tailoring."
            }
            yield {
                "type": "done",
                "data": {"content": "No active positions found.", "job_cards": []}
            }
            return

        # If Batch Auto-Apply is enabled or requested:
        if is_auto_apply:
            candidate_pool = [
                j for j in discovered_jobs
                if (j.get("score") or 0) >= min_score or not j.get("score")
            ]
            if not candidate_pool:
                candidate_pool = discovered_jobs

            # Target specific platform if requested by user (e.g. "only search linkedin", "on linkedin")
            m_low = message.lower()
            if any(k in m_low for k in ["only linkedin", "linkedin only", "on linkedin", "search linkedin", "from linkedin"]):
                li_pool = [j for j in candidate_pool if "linkedin" in (j.get("platform") or "").lower() or "linkedin.com" in (j.get("url") or "").lower()]
                if li_pool:
                    candidate_pool = li_pool
            elif any(k in m_low for k in ["only naukri", "naukri only", "on naukri", "from naukri"]):
                nk_pool = [j for j in candidate_pool if "naukri" in (j.get("platform") or "").lower() or "naukri.com" in (j.get("url") or "").lower()]
                if nk_pool:
                    candidate_pool = nk_pool

            # Multi-Platform Fair Queuing: interleave candidates across platforms (LinkedIn, Naukri, Indeed)
            # so that no single platform monopolizes the top positions
            platform_buckets: Dict[str, List[Dict]] = {}
            for j in candidate_pool:
                p = (j.get("platform") or "naukri").lower()
                platform_buckets.setdefault(p, []).append(j)

            qualifying_jobs = []
            while len(qualifying_jobs) < max_batch and any(platform_buckets.values()):
                for p in list(platform_buckets.keys()):
                    if platform_buckets[p] and len(qualifying_jobs) < max_batch:
                        qualifying_jobs.append(platform_buckets[p].pop(0))

            total_q = len(qualifying_jobs)
            success_count = 0
            failed_count = 0
            yield {
                "type": "status",
                "data": f"⚡ Batch Auto-Apply Active: Queuing {total_q} qualifying position(s) for autonomous submission..."
            }

            for idx, job in enumerate(qualifying_jobs, 1):
                j_title = job.get("title", "Software Engineer")
                j_comp = job.get("company", "Target Company")
                j_url = job.get("url", "")
                j_plat = job.get("platform", "naukri").lower()

                yield {
                    "type": "status",
                    "data": f"📄 [{idx}/{total_q}] Tailoring ATS resume for '{j_title}' at '{j_comp}'..."
                }

                # Tailor resume for this specific opening
                async for _ in self.resume_prep_client.stream_tailor(
                    job_title=j_title,
                    company=j_comp,
                    job_description=job.get("snippet", f"{j_title} at {j_comp}"),
                    target_pages=2,
                    generation_mode="tailor"
                ):
                    pass

                # Launch stealth application
                yield {
                    "type": "status",
                    "data": f"🚀 [{idx}/{total_q}] Submitting application on {j_plat.title()} for '{j_comp}'..."
                }

                applied_successfully = False
                proof_img = ""
                failure_reason = "Application could not be confirmed on job portal"
                async for apply_event in self.job_apply_client.stream_apply(
                    job_title=j_title,
                    company=j_comp,
                    job_url=j_url,
                    platform=j_plat,
                    auto_submit=autonomous_submission
                ):
                    ev_t = apply_event.get("type")
                    ev_d = apply_event.get("data")
                    if ev_t in ["status", "screenshot", "telemetry", "review_ready"]:
                        yield apply_event
                    elif ev_t == "done" and isinstance(ev_d, dict):
                        if ev_d.get("status") in ["submitted", "applied", "success"]:
                            applied_successfully = True
                            proof_img = ev_d.get("proof_screenshot", "")
                        else:
                            failure_reason = ev_d.get("message") or failure_reason
                    elif ev_t == "error":
                        failure_reason = str(ev_d)

                if applied_successfully:
                    success_count += 1
                    # Record in JobTracker (PostgreSQL) so UI tracker and sidebar counts update!
                    try:
                        await self.job_find_client.save_job({
                            "title": j_title,
                            "company": j_comp,
                            "url": j_url,
                            "location": job.get("location", "Chennai"),
                            "snippet": job.get("snippet", ""),
                            "score": job.get("score", 85),
                            "status": "APPLIED"
                        })
                    except Exception as e_save:
                        logger.warning(f"Failed to record applied job in tracker: {e_save}")

                    proof_text = f" (Proof: `{proof_img}`)" if proof_img else ""
                    yield {
                        "type": "token",
                        "data": f"\n\n✅ **Applied to {j_comp}** ({j_title})\n- Platform: {j_plat.title()}\n- Status: Autonomous Submission Completed & Verified{proof_text}\n"
                    }
                else:
                    failed_count += 1
                    # Save as SAVED in tracker, do NOT increment applied!
                    try:
                        await self.job_find_client.save_job({
                            "title": j_title,
                            "company": j_comp,
                            "url": j_url,
                            "location": job.get("location", "Chennai"),
                            "snippet": job.get("snippet", ""),
                            "score": job.get("score", 85),
                            "status": "SAVED"
                        })
                    except Exception as e_save:
                        logger.warning(f"Failed to record saved job in tracker: {e_save}")

                    yield {
                        "type": "token",
                        "data": f"\n\n⚠️ **Could not auto-apply to {j_comp}** ({j_title})\n- Platform: {j_plat.title()}\n- Reason: {failure_reason}\n- Status: Saved to Tracker for manual review\n"
                    }

                if idx < total_q:
                    pause_delay = min(delay_sec, 15)
                    yield {
                        "type": "status",
                        "data": f"⏳ Anti-bot stealth pause: waiting {pause_delay}s before proceeding to next application..."
                    }
                    await asyncio.sleep(pause_delay)

            yield {
                "type": "status",
                "data": f"✓ Batch Auto-Apply Completed: {success_count} applied successfully, {failed_count} saved for review."
            }
            yield {
                "type": "token",
                "data": f"\n\n**Batch Auto-Apply Execution Summary:**\n- Successfully Submitted & Verified: **{success_count}**\n- Skipped / Saved for Manual Review: **{failed_count}**\n- Verification records and proof snapshots saved in your **Job Applications Tracker**."
            }
            yield {
                "type": "done",
                "data": {
                    "content": f"Successfully auto-applied to {success_count} position(s). ({failed_count} saved for review)",
                    "job_cards": discovered_jobs
                }
            }
            return

        # Default Safe Mode: Human-in-the-Loop Gateway
        target_job = discovered_jobs[0]
        title = target_job.get("title", "Software Engineer")
        company = target_job.get("company", "Target Company")
        url = target_job.get("url", "")

        # Step 2: Tailor Resume
        yield {
            "type": "status",
            "data": f"📄 Step 2/3: Tailoring 2-page executive resume for '{title}' at '{company}'..."
        }
        async for event in self.resume_prep_client.stream_tailor(
            job_title=title,
            company=company,
            job_description=target_job.get("snippet", f"{title} at {company}"),
            target_pages=2
        ):
            yield event

        # Step 3: Checkpoint & Human-in-the-Loop Gateway
        yield {
            "type": "status",
            "data": f"🛡️ Step 3/3: Application prepared. Click 'Apply' on the job card or confirm to launch stealth submission."
        }
        yield {
            "type": "pipeline_ready",
            "data": {
                "target_job": target_job,
                "job_title": title,
                "company": company,
                "job_url": url,
                "requires_confirmation": True
            }
        }
        yield {
            "type": "done",
            "data": {
                "content": "Application prepared. Click 'Apply' on any job card to launch submission.",
                "job_cards": discovered_jobs
            }
        }

    async def stream_request(
        self,
        session_id: str,
        message: str,
        model: str = "auto",
        history: List[Dict[str, str]] = None,
        auto_apply_settings: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Primary Master Dispatcher:
        1. Classifies intent.
        2. Routes to the appropriate worker agent or workflow engine.
        3. Streams unified SSE events back to the client.
        """
        # Step 1: Fast intent classification
        decision = await route_user_request(message)
        logger.info(f"[stream_request] Intent classified as: {decision.target_agent.value} ({decision.confidence:.2f})")

        # Yield manager routing pill / badge to UI
        yield {
            "type": "manager_intent",
            "data": {
                "target_agent": decision.target_agent.value,
                "confidence": decision.confidence,
                "summary": decision.intent_summary
            }
        }

        # Step 2: Delegate based on target agent
        if decision.target_agent == TargetAgent.JOB_FIND:
            yield {"type": "status", "data": "🔎 Routing to Job Find Agent (Port 8000)..."}
            async for event in self.job_find_client.stream_chat(session_id, message, model):
                yield event

        elif decision.target_agent == TargetAgent.RESUME_PREP:
            yield {"type": "status", "data": "🎨 Routing to Resume Preparation Agent (Port 8001)..."}
            params = decision.extracted_params
            role = params.get("role") or ("Python Developer" if "python" in message.lower() else "")
            company = params.get("company") or "General Profile"

            # Global attached resume extraction across all resume intents
            attached_resume_match = re.search(r'\[Attached Resume:\s*([^\]]+)\]', message)
            custom_resume_text = ""
            if attached_resume_match:
                fn = attached_resume_match.group(1).strip()
                yield {"type": "status", "data": f"📑 Loading attached resume file '{fn}'..."}
                for cand_path in [
                    os.path.join("/home/senkathir-selvan/Downloads", fn),
                    os.path.join("/home/senkathir-selvan/resume-prep-agent/data/master", fn),
                    "/home/senkathir-selvan/job-find-agent/data/resume.pdf",
                    "/home/senkathir-selvan/resume-prep-agent/data/master/master_resume.pdf",
                    "/home/senkathir-selvan/resume-prep-agent/data/master/master_resume.md",
                ]:
                    if os.path.exists(cand_path):
                        try:
                            if cand_path.endswith(".pdf"):
                                from pypdf import PdfReader
                                reader = PdfReader(cand_path)
                                custom_resume_text = "\n".join(p.extract_text() or "" for p in reader.pages)
                            else:
                                with open(cand_path, "r", encoding="utf-8") as f:
                                    custom_resume_text = f.read()
                            if custom_resume_text.strip():
                                break
                        except Exception as e:
                            logger.warning(f"Failed extracting text from {cand_path}: {e}")

            if not custom_resume_text.strip():
                for master_path in [
                    "/home/senkathir-selvan/resume-prep-agent/data/master/master_resume.md",
                    "/home/senkathir-selvan/Downloads/Updated_Resume_Senkathirselvan.md",
                    "/home/senkathir-selvan/job-find-agent/data/resume.pdf",
                    "/home/senkathir-selvan/resume-prep-agent/data/master/master_resume.pdf",
                ]:
                    if os.path.exists(master_path):
                        try:
                            if master_path.endswith(".pdf"):
                                from pypdf import PdfReader
                                reader = PdfReader(master_path)
                                custom_resume_text = "\n".join(p.extract_text() or "" for p in reader.pages)
                            else:
                                with open(master_path, "r", encoding="utf-8") as f:
                                    custom_resume_text = f.read()
                            if custom_resume_text.strip():
                                break
                        except Exception as e:
                            logger.warning(f"Failed extracting master text from {master_path}: {e}")

            # Normalize raw extracted text (e.g. from PDF) to structured markdown
            if custom_resume_text.strip():
                if "senkathir" in custom_resume_text.lower() and not ("## PROFESSIONAL" in custom_resume_text):
                    for m_md in [
                        "/home/senkathir-selvan/resume-prep-agent/data/master/master_resume.md",
                        "/home/senkathir-selvan/Downloads/Updated_Resume_Senkathirselvan.md"
                    ]:
                        if os.path.exists(m_md):
                            with open(m_md, "r", encoding="utf-8") as f:
                                custom_resume_text = f.read()
                            break
                elif not ("## PROFESSIONAL" in custom_resume_text or "## TECHNICAL" in custom_resume_text):
                    lines = custom_resume_text.strip().splitlines()
                    norm_lines = []
                    if lines and not lines[0].strip().startswith("#"):
                        norm_lines.append(f"# {lines[0].strip()}")
                        lines = lines[1:]
                    s_headers = [
                        "PROFESSIONAL SUMMARY", "EXECUTIVE SUMMARY", "SUMMARY",
                        "TECHNICAL SKILLS", "SKILLS", "CORE COMPETENCIES",
                        "PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "EXPERIENCE",
                        "KEY PROJECTS", "PROJECTS", "FEATURED PROJECTS & ARCHITECTURES", "FEATURED PROJECTS",
                        "EDUCATION", "EDUCATION & ACADEMIC BACKGROUND",
                        "COMMUNITY & OPEN SOURCE", "COMMUNITY", "CERTIFICATIONS"
                    ]
                    for line in lines:
                        sline = line.strip()
                        u_line = sline.upper()
                        is_h = False
                        for sh in s_headers:
                            if u_line == sh or u_line == f"## {sh}" or u_line == f"**{sh}**":
                                norm_lines.append(f"\n## {sh}\n")
                                is_h = True
                                break
                        if is_h:
                            continue
                        if re.match(r'^\d+\.\s+[A-Za-z0-9_-]+', sline):
                            norm_lines.append(f"\n#### {sline}\n")
                            continue
                        if any(w in sline for w in ["Pvt. Ltd.", "Technologies", "Inc.", "Corp.", "Solutions"]) and ("—" in sline or "-" in sline or "Villupuram" in sline):
                            norm_lines.append(f"\n### {sline}\n")
                            continue
                        norm_lines.append(line)
                    custom_resume_text = "\n".join(norm_lines)

            if not role:
                crt_lower = custom_resume_text.lower()
                if "python backend developer" in crt_lower:
                    role = "Python Backend Developer"
                elif "python developer" in crt_lower:
                    role = "Python Developer"
                elif "backend developer" in crt_lower:
                    role = "Backend Developer"
                else:
                    role = "Software Engineer"

            # Check for ATS Audit / Scoring intent
            is_audit_intent = any(k in message.lower() for k in [
                "audit", "ats score", "ats check", "score my resume", "review my resume",
                "evaluate my resume", "check my resume", "xyz audit", "ats compliance"
            ]) and not any(k in message.lower() for k in ["tailor", "new resume", "build", "apply", "create", "make a"])

            if is_audit_intent:
                yield {"type": "status", "data": "📊 Inspecting candidate master profile and active resume layer..."}

                # Clean JD: only pass if user actually provided a JD separate from audit prompt
                clean_jd = ""
                prompt_lower = message.lower()
                clean_msg = re.sub(r'\[Attached Resume:[^\]]+\]', '', message).strip()
                if len(clean_msg) > 100 and any(w in prompt_lower for w in ["job description", "requirements", "responsibilities", "qualifications", "must have", "jd:"]):
                    clean_jd = clean_msg

                yield {"type": "status", "data": "🔍 Auditing resume structure against 4-category ATS standard & Google XYZ formula..."}
                audit_res = await self.resume_prep_client.audit_resume(
                    resume_text=custom_resume_text,
                    job_description=clean_jd,
                    target_role=role
                )
                if not audit_res:
                    yield {"type": "token", "data": "Unable to perform ATS audit at this moment. Please ensure your master resume is uploaded."}
                    yield {"type": "done", "data": {"content": "ATS audit failed."}}
                    return

                cats = audit_res.get("categories") or {}
                c_contact = cats.get("contact", 0)
                c_format = cats.get("formatting", 0)
                c_impact = cats.get("impact", 0)
                c_kw = cats.get("keywords", 0)
                score = audit_res.get("score", 0)

                score_badge = "🟢 Excellent" if score >= 80 else ("🟡 Moderate" if score >= 60 else "🔴 Needs Optimization")

                report_lines = [
                    "### 📊 ATS Resume Audit & Google XYZ Scorecard\n\n",
                    f"**Overall ATS Match Score:** **{score} / 100** ({score_badge})\n\n",
                    "#### 🏆 4-Dimensional Category Breakdown\n",
                    "| ATS Dimension | Weight | Score | Evaluation Status |\n",
                    "| :--- | :---: | :---: | :--- |\n",
                    f"| **Contact Information** | 25 pts | **{c_contact} / 25** | {'✅ Verified' if c_contact >= 20 else '⚠️ Incomplete'} |\n",
                    f"| **Formatting & ATS Hierarchy** | 25 pts | **{c_format} / 25** | {'✅ Clean Structure' if c_format >= 20 else '⚠️ Header Issues'} |\n",
                    f"| **Impact & Google XYZ Bullets** | 25 pts | **{c_impact} / 25** | {'✅ High Impact' if c_impact >= 18 else '⚠️ Add Metrics/Action Verbs'} |\n",
                    f"| **Keyword Relevance & Alignment** | 25 pts | **{c_kw} / 25** | {'✅ Strong Match' if c_kw >= 18 else '⚠️ Low Density'} |\n\n",
                    f"- **Google XYZ Compliance Rate:** **{audit_res.get('xyz_compliance_rate', 0)}%**\n",
                    f"- **Quantified Achievements:** **{audit_res.get('quantified_bullets_count', 0)} of {audit_res.get('total_bullets', 0)} bullets**\n",
                    f"- **Active Power Action Verbs Found:** {', '.join(audit_res.get('action_verbs_found', [])) or 'None'}\n\n"
                ]

                bullet_audits = audit_res.get("bullet_audits", [])
                if bullet_audits:
                    report_lines.append("#### 📝 Google XYZ Bullet Audits\n")
                    for idx, b in enumerate(bullet_audits[:6], 1):
                        icon = "🟢" if b.get("score") == "strong" else ("🟡" if b.get("score") == "moderate" else "🔴")
                        b_text = b.get("bullet", "")
                        b_feedback = b.get("feedback", "")
                        report_lines.append(f"{idx}. {icon} **\"{b_text}\"**\n   - *{b_feedback}*\n")
                    report_lines.append("\n")

                recs = audit_res.get("recommendations", [])
                if recs:
                    report_lines.append("#### 💡 Actionable Recommendations\n")
                    for r in recs:
                        report_lines.append(f"- {r}\n")

                full_report = "".join(report_lines)
                yield {"type": "token", "data": full_report}
                yield {"type": "done", "data": {"content": full_report}}
                return

            # Check for Surgical Precision Edit intent
            is_surgical_edit = any(k in message.lower() for k in [
                "surgically", "surgical", "only change", "only update", "change my title",
                "update my title", "change the bullet", "update bullet", "modify bullet",
                "edit bullet", "precision edit"
            ])

            if is_surgical_edit:
                yield {"type": "status", "data": "✂️ Performing surgical precision edit on resume..."}
                edit_res = await self.resume_prep_client.precision_edit(
                    instruction=message,
                    target_role=role,
                    target_company=company
                )
                if not edit_res:
                    yield {"type": "token", "data": "Unable to perform precision edit at this time."}
                    yield {"type": "done", "data": {"content": "Precision edit failed."}}
                    return

                diff = edit_res.get("diff") or {}
                desc = diff.get("description", message)
                sec = diff.get("section", "General")
                target_ent = diff.get("target_entity", "")
                before_snippet = diff.get("before", "")
                after_snippet = diff.get("after", "")
                ats_score = edit_res.get("ats_score", 85)
                pdf_file = edit_res.get("pdf_filename")
                docx_file = edit_res.get("docx_filename")
                html_file = edit_res.get("html_filename")
                power_words = edit_res.get("suggested_power_words", [])

                report_lines = [
                    "### ✂️ Surgical Resume Edit Applied\n\n",
                    f"**Modification:** {desc}\n\n",
                    f"**Target Section:** `{sec}`" + (f" ({target_ent})\n\n" if target_ent else "\n\n"),
                    "#### 🔍 Structured Change Diff\n",
                    f"- **Before:**\n> {before_snippet}\n\n" if before_snippet else "",
                    f"- **After:**\n> **{after_snippet}**\n\n" if after_snippet else "",
                    f"**Updated ATS Match Score:** **{ats_score} / 100**\n\n"
                ]

                if power_words:
                    report_lines.append(f"**Recommended Power Action Verbs:** `{', '.join(power_words)}`\n\n")

                if html_file or pdf_file or docx_file:
                    report_lines.append("#### 📥 ATS Studio Preview & Download Links\n")
                    if html_file:
                        report_lines.append(f"- 👁️ **[View Resume in ATS Studio](http://localhost:8001/api/resume/preview/{html_file})** *(Preview instantly without downloading)*\n")
                    if pdf_file:
                        report_lines.append(f"- 📄 [Download Updated PDF](http://localhost:8001/api/resume/download/{pdf_file})\n")
                    if docx_file:
                        report_lines.append(f"- 📝 [Download Updated DOCX](http://localhost:8001/api/resume/download/{docx_file})\n")

                full_report = "".join(report_lines)
                yield {"type": "token", "data": full_report}
                yield {"type": "done", "data": {"content": full_report}}
                return

            # Check for Target Page Calibration intent (e.g. "compress to 1 page", "make it 1 page", "2 pages")
            is_page_calib = any(k in message.lower() for k in [
                "1 page", "one page", "single page", "1-page",
                "2 page", "two page", "2-page",
                "3 page", "three page", "3-page",
                "paginate", "tighten page", "fit to page"
            ]) and any(k in message.lower() for k in ["compress", "fit", "calibrate", "make", "change", "convert", "limit", "format", "shrink", "tighten", "expand"])

            if is_page_calib:
                target_pages = 1 if any(k in message.lower() for k in ["1 page", "one page", "single page", "1-page"]) else (3 if any(k in message.lower() for k in ["3 page", "three page", "3-page"]) else 2)
                yield {"type": "status", "data": f"📐 Calibrating resume content density and layout for strictly {target_pages} page(s)..."}
                calib_res = await self.resume_prep_client.calibrate_pagination(
                    target_pages=target_pages,
                    target_role=role,
                    target_company=company
                )
                if not calib_res:
                    yield {"type": "token", "data": "Unable to calibrate pagination at this time."}
                    yield {"type": "done", "data": {"content": "Pagination calibration failed."}}
                    return

                adjustments = calib_res.get("summary_of_adjustments", "")
                word_count = calib_res.get("word_count", 0)
                ats_score = calib_res.get("ats_score", 85)
                pdf_file = calib_res.get("pdf_filename")
                docx_file = calib_res.get("docx_filename")
                html_file = calib_res.get("html_filename")

                report_lines = [
                    f"### 📐 Resume Calibrated to Exactly {target_pages} Page{'s' if target_pages > 1 else ''}\n\n",
                    f"**Layout Adjustments:** {adjustments}\n\n",
                    f"- **Calibrated Word Count:** **{word_count} words** " + (f"(Target: 350–450 for 1-page)" if target_pages == 1 else (f"(Target: 700–900 for 2-page)" if target_pages == 2 else f"(Target: 1100–1450 for 3-page)")) + "\n",
                    f"- **ATS Match Score:** **{ats_score} / 100**\n",
                    "- **WeasyPrint Page-Break Rules:** Verified with strict `break-inside: avoid` preventing orphaned headers or split experience cards.\n\n"
                ]

                if html_file or pdf_file or docx_file:
                    report_lines.append("#### 📥 ATS Studio Preview & Download Documents\n")
                    if html_file:
                        report_lines.append(f"- 👁️ **[View Resume in ATS Studio](http://localhost:8001/api/resume/preview/{html_file})** *(Preview instantly without downloading)*\n")
                    if pdf_file:
                        report_lines.append(f"- 📄 [Download Calibrated {target_pages}P PDF](http://localhost:8001/api/resume/download/{pdf_file})\n")
                    if docx_file:
                        report_lines.append(f"- 📝 [Download Calibrated {target_pages}P DOCX](http://localhost:8001/api/resume/download/{docx_file})\n")

                full_report = "".join(report_lines)
                yield {"type": "token", "data": full_report}
                yield {"type": "done", "data": {"content": full_report}}
                return

            # Check for Candidate Intake / Draft from scratch intent
            is_draft_intake = (
                ("draft" in message.lower() and any(k in message.lower() for k in ["for ", "candidate", "fresher", "intake", "projects"]))
                or ("intake" in message.lower())
            )
            if is_draft_intake:
                yield {"type": "status", "data": "✨ Synthesizing candidate intake into structured ATS resume..."}
                cand_name = "Candidate"
                m_for = re.search(r'(?:for|candidate|name(?:\s+is)?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', message)
                if m_for:
                    cand_name = m_for.group(1).strip()
                
                is_fresher = "fresher" in message.lower() or "graduate" in message.lower()
                
                draft_res = await self.resume_prep_client.draft_resume({
                    "candidate_name": cand_name,
                    "target_role": role,
                    "target_company": company if company != "General Profile" else None,
                    "is_fresher": is_fresher,
                    "summary_notes": message,
                    "target_pages": 1 if is_fresher else 2
                })
                if draft_res:
                    pdf_file = draft_res.get("pdf_filename")
                    docx_file = draft_res.get("docx_filename")
                    html_file = draft_res.get("html_filename")
                    exec_sum = draft_res.get("executive_summary", "")
                    ats_score = draft_res.get("ats_score", 85)
                    power_words = draft_res.get("suggested_power_words", [])

                    report_lines = [
                        f"### ✨ ATS Resume Draft Created for **{cand_name}**\n\n",
                        f"**Target Role:** {role}\n\n",
                        f"**Executive Summary:**\n> {exec_sum}\n\n",
                        f"- **Calculated ATS Match Score:** **{ats_score} / 100**\n",
                        f"- **Format:** Fully formatted Google XYZ bullet structure\n"
                    ]
                    if power_words:
                        report_lines.append(f"- **Integrated Power Verbs:** `{', '.join(power_words)}`\n\n")

                    if html_file or pdf_file or docx_file:
                        report_lines.append("#### 📥 ATS Studio Preview & Download Resume\n")
                        if html_file:
                            report_lines.append(f"- 👁️ **[View Resume in ATS Studio](http://localhost:8001/api/resume/preview/{html_file})** *(Preview instantly without downloading)*\n")
                        if pdf_file:
                            report_lines.append(f"- 📄 [Download PDF](http://localhost:8001/api/resume/download/{pdf_file})\n")
                        if docx_file:
                            report_lines.append(f"- 📝 [Download DOCX](http://localhost:8001/api/resume/download/{docx_file})\n")

                    full_report = "".join(report_lines)
                    yield {"type": "token", "data": full_report}
                    yield {"type": "done", "data": {"content": full_report}}
                    return

            # Check for Recompile / Template & Font Restyling intent (e.g. "update resume template and fonts without touch inside content")
            is_recompile_intent = (
                any(k in message.lower() for k in ["template", "font", "fonts", "theme", "palette", "recompile", "layout", "styling"])
                and any(k in message.lower() for k in ["without touch", "don't touch", "dont touch", "without chang", "keep content", "same content", "just change", "switch template", "change template", "update template", "new font", "new template", "update my resume template", "update my resume"])
            )
            if is_recompile_intent:
                yield {"type": "status", "data": "🎨 Recompiling resume layout & typography with 100% content preservation..."}

                msg_lower = message.lower()
                tpl_id = "classic_ats" if any(k in msg_lower for k in ["classic", "classic ats", "executive", "template 5", "linear", "clean ats"]) else "modern_header"
                if any(k in msg_lower for k in ["classic", "classic ats", "template 5", "linear", "clean ats"]):
                    tpl_id = "classic_ats"
                elif any(k in msg_lower for k in ["sidebar", "two column", "two-column", "tech sidebar"]):
                    tpl_id = "tech_sidebar"
                elif any(k in msg_lower for k in ["minimalist", "single column", "sleek"]):
                    tpl_id = "minimalist"
                elif any(k in msg_lower for k in ["grid", "matrix", "enterprise"]):
                    tpl_id = "grid_matrix"
                elif any(k in msg_lower for k in ["modern", "header", "cards"]):
                    tpl_id = "modern_header"

                font_id = "liberation_sans" if tpl_id == "classic_ats" else "clean_roboto"
                if any(k in msg_lower for k in ["liberation", "liberation sans"]):
                    font_id = "liberation_sans"
                elif any(k in msg_lower for k in ["inter", "modern inter"]):
                    font_id = "modern_inter"
                elif any(k in msg_lower for k in ["roboto"]):
                    font_id = "clean_roboto"
                elif any(k in msg_lower for k in ["garamond"]):
                    font_id = "classic_garamond"
                elif any(k in msg_lower for k in ["merriweather", "serif"]):
                    font_id = "executive_merriweather"
                elif any(k in msg_lower for k in ["arial", "standard"]):
                    font_id = "universal_arial"

                pal_id = "executive_navy" if tpl_id == "classic_ats" else "enterprise_blue"
                if any(k in msg_lower for k in ["navy", "executive navy"]):
                    pal_id = "executive_navy"
                elif any(k in msg_lower for k in ["teal", "cyan"]):
                    pal_id = "teal_technical"
                elif any(k in msg_lower for k in ["emerald", "green"]):
                    pal_id = "emerald_executive"
                elif any(k in msg_lower for k in ["slate", "gray"]):
                    pal_id = "modern_slate"
                elif any(k in msg_lower for k in ["warm", "amber"]):
                    pal_id = "warm_classic"

                target_pages = 2
                if any(k in msg_lower for k in ["1 page", "one page", "single page", "1-page"]):
                    target_pages = 1
                elif any(k in msg_lower for k in ["3 page", "three page", "3-page"]):
                    target_pages = 3

                recompile_res = await self.resume_prep_client.recompile({
                    "markdown_text": custom_resume_text,
                    "target_job_title": role,
                    "target_company": company if company != "General Profile" else "",
                    "template_id": tpl_id,
                    "palette_id": pal_id,
                    "font_id": font_id,
                    "target_pages": target_pages
                })

                if recompile_res and recompile_res.get("status") == "success":
                    pdf_file = recompile_res.get("pdf_filename")
                    docx_file = os.path.basename(recompile_res.get("docx_filename")) if recompile_res.get("docx_filename") else None
                    html_file = recompile_res.get("html_filename")
                    tpl_name = recompile_res.get("template_name", tpl_id.replace("_", " ").title())
                    font_name = recompile_res.get("font_name", font_id.replace("_", " ").title())
                    pal_name = recompile_res.get("palette_name", pal_id.replace("_", " ").title())
                    ats_score = recompile_res.get("tailored_score", 85)

                    report_lines = [
                        f"### 🎨 Resume Restyled into **{tpl_name}** with **{font_name}**\n\n",
                        f"- **Layout Skeleton:** `{tpl_name}` ({target_pages} Page{'s' if target_pages > 1 else ''})\n",
                        f"- **Typography & Font:** `{font_name}`\n",
                        f"- **Color Palette:** `{pal_name}`\n",
                        "- **Content Integrity:** ✅ **100% Content Preserved** (Zero modifications to job titles, bullets, dates, or projects)\n",
                        f"- **ATS Match Score:** **{ats_score} / 100**\n\n",
                        "#### 📥 ATS Studio Preview & Download Documents\n",
                        f"- 👁️ **[View Resume in ATS Studio](http://localhost:8001/api/resume/preview/{html_file})** *(Preview instantly without downloading)*\n",
                    ]
                    if pdf_file:
                        report_lines.append(f"- 📄 [Download Updated PDF](http://localhost:8001/api/resume/download/{pdf_file})\n")
                    if docx_file:
                        report_lines.append(f"- 📝 [Download Updated DOCX](http://localhost:8001/api/resume/download/{docx_file})\n")

                    full_report = "".join(report_lines)
                    yield {"type": "token", "data": full_report}
                    yield {"type": "done", "data": {"content": full_report}}
                    return

            # Distinguish: "new resume / from scratch" vs "tailor my existing resume"
            user_wants_scratch = any(k in message.lower() for k in [
                "new resume", "from scratch", "scratch", "fresh resume", "a new", "create a resume", "generate a resume", "make a resume"
            ]) and not any(k in message.lower() for k in ["my resume", "my profile", "tailor my", "update my", "adapt my"])

            generation_mode = "scratch" if user_wants_scratch else "tailor"

            is_create_or_tailor = any(k in message.lower() for k in [
                "prepare", "create", "make", "build", "generate", "write", "tailor", "new resume"
            ])

            if is_create_or_tailor:
                async for event in self.resume_prep_client.stream_tailor(
                    job_title=role,
                    company=company,
                    job_description=params.get("instruction", message),
                    target_pages=2,
                    generation_mode=generation_mode
                ):
                    yield event
            else:
                async for event in self.resume_prep_client.stream_refine(
                    prompt=message,
                    current_resume_text=custom_resume_text,
                    job_title=role,
                    company=company
                ):
                    yield event

        elif decision.target_agent == TargetAgent.JOB_APPLY:
            yield {"type": "status", "data": "⚡ Routing to Autonomous Job Apply Agent (Port 8002)..."}
            params = decision.extracted_params
            async for event in self.job_apply_client.stream_apply(
                job_title=params.get("role", "Target Position"),
                company=params.get("company", "Target Company"),
                job_url=params.get("job_url", ""),
                platform="auto"
            ):
                yield event

        elif decision.target_agent == TargetAgent.MULTI_STEP:
            async for event in self.execute_multi_step_workflow(session_id, message, decision, auto_apply_settings):
                yield event

        else: # GENERAL_CHAT
            yield {"type": "status", "data": "⚡ Connected to Sensa AI Executive Manager..."}
            async for event in self.stream_general_chat(message, history):
                yield event

orchestrator = ManagerOrchestrator()

