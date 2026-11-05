import os
import uuid
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.config import settings
from backend.app.browser.engine import BrowserEngine
from backend.app.browser.human_actions import HumanActions
from backend.app.services.candidate_profile import CandidateProfileService
from backend.app.adapters import NaukriAdapter, LinkedInAdapter, ExternalATSAdapter
from backend.app.agent.memory import ApplicationMemory
from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import ApplicationRecord, AuditLog

class ApplyOrchestrator:
    """Orchestrates end-to-end browser application pipeline with real-time SSE streaming."""

    @classmethod
    async def stream_application(
        cls,
        job_url: str,
        job_title: str,
        company: str,
        job_id: Optional[str] = None,
        tailored_resume_path: Optional[str] = None,
        cover_letter_text: Optional[str] = None,
        headless: bool = True,
        session_id: Optional[str] = None,
        auto_submit: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not session_id:
            session_id = str(uuid.uuid4())

        ApplicationMemory.register_session(session_id, {
            "job_title": job_title,
            "company": company,
            "job_url": job_url
        })

        engine = BrowserEngine(headless=headless)
        application_record_id = str(uuid.uuid4())

        async def emit(event_type: str, data: Any):
            # Helper inside generator
            pass

        try:
            # Stage 1: Initialization
            yield {"event": "telemetry", "data": {"stage": "INIT", "progress": 15}}
            yield {"event": "status", "data": f"Launching stealth browser context for {company}..."}

            # Determine platform
            platform = "external_ats"
            url_lower = job_url.lower()
            if "naukri.com" in url_lower:
                platform = "naukri"
                adapter = NaukriAdapter()
            elif "linkedin.com" in url_lower:
                platform = "linkedin"
                adapter = LinkedInAdapter()
            else:
                adapter = ExternalATSAdapter()

            page = await engine.initialize(platform=platform)

            # Stage 2: Navigation
            yield {"event": "telemetry", "data": {"stage": "NAVIGATING", "progress": 30}}
            yield {"event": "status", "data": f"Navigating to job portal [{platform.upper()}]..."}

            try:
                # Naukri is a heavy React SPA that displays a loading spinner until networkidle
                wait_state = "networkidle" if platform == "naukri" else "domcontentloaded"
                await page.goto(job_url, wait_until=wait_state, timeout=settings.BROWSER_TIMEOUT_MS)
            except Exception as e:
                yield {"event": "status", "data": f"Page load warning: {e}. Attempting recovery..."}

            await HumanActions.sleep(1500, 2500)

            # Stage 3: Resolve Candidate Profile & Resume PDF
            yield {"event": "telemetry", "data": {"stage": "PREPARING_DATA", "progress": 45}}
            yield {"event": "status", "data": "Resolving candidate profile and matching tailored PDF resume..."}

            candidate_data = await CandidateProfileService.get_candidate_data()
            if cover_letter_text:
                candidate_data["cover_letter"] = cover_letter_text

            resume_pdf = CandidateProfileService.resolve_resume_pdf(
                company=company,
                job_title=job_title,
                provided_path=tailored_resume_path
            )

            if resume_pdf:
                yield {"event": "status", "data": f"✓ Selected tailored resume: {os.path.basename(resume_pdf)}"}
            else:
                yield {"event": "status", "data": "Notice: No tailored PDF found on disk. Proceeding with form fields."}

            # Stage 4: Form Execution
            yield {"event": "telemetry", "data": {"stage": "FILLING_FORM", "progress": 65}}
            
            queue: asyncio.Queue = asyncio.Queue()

            async def event_callback(evt_type: str, evt_data: Any):
                await queue.put({"event": evt_type, "data": evt_data})

            # Run adapter execution
            adapter_task = asyncio.create_task(
                adapter.execute(page, candidate_data, resume_pdf, event_callback)
            )

            while not adapter_task.done() or not queue.empty():
                try:
                    packet = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield packet
                except asyncio.TimeoutError:
                    await asyncio.sleep(0.05)

            exec_result = await adapter_task

            # Check if authentication was required or form could not be applied
            if exec_result.get("status") == "auth_required":
                auth_screenshot = await engine.capture_screenshot(f"login_required_{company}".replace(" ", "_"))
                yield {"event": "telemetry", "data": {"stage": "AUTH_REQUIRED", "progress": 100}}
                yield {"event": "status", "data": f"⚠️ {exec_result.get('message', 'Login session required.')}"}

                # Persist to DB as auth_required
                async with AsyncSessionLocal() as db:
                    record = ApplicationRecord(
                        id=application_record_id,
                        job_id=job_id,
                        job_title=job_title,
                        company=company,
                        job_url=job_url,
                        platform=platform,
                        status="auth_required",
                        tailored_resume_path=resume_pdf,
                        screenshot_path=auth_screenshot,
                        error_message=exec_result.get("message")
                    )
                    db.add(record)
                    await db.commit()

                yield {
                    "event": "done",
                    "data": {
                        "status": "auth_required",
                        "session_id": session_id,
                        "platform": platform,
                        "proof_screenshot": os.path.basename(auth_screenshot) if auth_screenshot else "",
                        "message": exec_result.get("message", "Login required on portal before application can be submitted."),
                        "is_verified": False
                    }
                }
                return

            if not exec_result.get("applied") or exec_result.get("status") in ["button_not_found", "error"]:
                fail_screenshot = await engine.capture_screenshot(f"fail_{company}".replace(" ", "_"))
                err_msg = exec_result.get("message", "Could not complete application on this opening.")
                yield {"event": "telemetry", "data": {"stage": "DONE", "progress": 100}}
                yield {"event": "status", "data": f"⚠️ {err_msg}"}

                async with AsyncSessionLocal() as db:
                    record = ApplicationRecord(
                        id=application_record_id,
                        job_id=job_id,
                        job_title=job_title,
                        company=company,
                        job_url=job_url,
                        platform=platform,
                        status="failed",
                        tailored_resume_path=resume_pdf,
                        screenshot_path=fail_screenshot,
                        error_message=err_msg
                    )
                    db.add(record)
                    await db.commit()

                yield {
                    "event": "done",
                    "data": {
                        "status": "failed",
                        "session_id": session_id,
                        "platform": platform,
                        "proof_screenshot": os.path.basename(fail_screenshot) if fail_screenshot else "",
                        "message": err_msg,
                        "is_verified": False
                    }
                }
                return

            # Stage 5: Screenshot & Review Gate
            yield {"event": "telemetry", "data": {"stage": "REVIEW_GATE", "progress": 85}}
            screenshot_path = await engine.capture_screenshot(f"{company}_{job_title}".replace(" ", "_"))
            screenshot_filename = os.path.basename(screenshot_path) if screenshot_path else ""

            yield {
                "event": "review_ready",
                "data": {
                    "session_id": session_id,
                    "platform": platform,
                    "screenshot_filename": screenshot_filename,
                    "fields_filled": exec_result.get("fields_filled", {}),
                    "screening_answers": exec_result.get("screening_answers", {}),
                    "resume_attached": bool(resume_pdf),
                    "resume_filename": os.path.basename(resume_pdf) if resume_pdf else None,
                    "message": "Human-in-the-Loop Gate: Review the completed form before final submission."
                }
            }

            if not auto_submit:
                yield {"event": "status", "data": "Waiting for user confirmation to submit application..."}

                # Stage 6: Human-in-the-Loop Wait
                user_event = ApplicationMemory.get_event(session_id)
                if user_event:
                    try:
                        # Wait up to 120 seconds for user approval
                        await asyncio.wait_for(user_event.wait(), timeout=120.0)
                    except asyncio.TimeoutError:
                        yield {"event": "status", "data": "Verification timeout (120s reached). Application held safely."}
                        ApplicationMemory.abort_session(session_id)

                if ApplicationMemory.is_aborted(session_id):
                    yield {"event": "status", "data": "Application cancelled by user."}
                    yield {
                        "event": "done",
                        "data": {
                            "status": "aborted",
                            "session_id": session_id,
                            "message": "Application was safely aborted."
                        }
                    }
                    return
            else:
                yield {"event": "status", "data": f"⚡ Autonomous Mode: Auto-approving application for {company}..."}

            # Stage 7: Final Submit & Receipt Proof
            active_page = exec_result.get("target_page") or page
            active_adapter = exec_result.get("active_adapter") or adapter
            yield {"event": "telemetry", "data": {"stage": "SUBMITTING", "progress": 95}}
            yield {"event": "status", "data": f"Submitting finalized application to {active_adapter.name.replace('_', ' ').title()}..."}
            await HumanActions.sleep(800, 1500)

            # Look for final submit button if present on page
            final_submit_btns = [
                '[role="dialog"] footer button:has-text("Submit application")',
                '[role="dialog"] button:has-text("Submit application")',
                'dialog footer button:has-text("Submit application")',
                'dialog button:has-text("Submit application")',
                'button:has-text("Submit application"):visible',
                'button:has-text("Submit Application"):visible',
                'button[aria-label*="Submit application" i]:visible',
                'button[type="submit"]:has-text("Apply"):visible',
                'button[type="submit"]:has-text("Submit"):visible',
                'dialog button:has-text("Submit")',
                'button:has-text("Submit"):visible',
                'input[type="submit"]:visible',
                'button.btn-submit:visible'
            ]
            for sel in final_submit_btns:
                loc = active_page.locator(sel).first
                if await loc.count() > 0:
                    try:
                        await loc.scroll_into_view_if_needed()
                        await HumanActions.sleep(200, 400)
                        if await loc.is_visible():
                            await HumanActions.human_click(loc, active_page)
                            await HumanActions.sleep(2500, 3500)
                            break
                    except Exception:
                        pass

            # Active Proof Verification
            await HumanActions.sleep(1500, 2500)
            is_verified, receipt_proof = await active_adapter.verify_submission_receipt(active_page)
            proof_screenshot = await engine.capture_screenshot(f"proof_{company}_{job_title}".replace(" ", "_"), target_page=active_page)

            final_status = "submitted" if is_verified else "unverified"
            if "blocked" in receipt_proof.lower() or "login" in receipt_proof.lower():
                final_status = "auth_required"

            final_msg = (
                f"✓ Verified Application Receipt: Successfully applied for {job_title} at {company}!"
                if is_verified
                else f"⚠️ {receipt_proof}"
            )

            # Persist to DB
            async with AsyncSessionLocal() as db:
                record = ApplicationRecord(
                    id=application_record_id,
                    job_id=job_id,
                    job_title=job_title,
                    company=company,
                    job_url=job_url,
                    platform=platform,
                    status=final_status,
                    tailored_resume_path=resume_pdf,
                    cover_letter_text=cover_letter_text,
                    fields_filled=exec_result.get("fields_filled", {}),
                    screening_answers=exec_result.get("screening_answers", {}),
                    screenshot_path=proof_screenshot,
                    error_message=receipt_proof if not is_verified else None
                )
                db.add(record)
                await db.commit()

            yield {"event": "telemetry", "data": {"stage": "DONE", "progress": 100}}
            yield {
                "event": "done",
                "data": {
                    "status": final_status,
                    "application_id": application_record_id,
                    "session_id": session_id,
                    "platform": platform,
                    "proof_screenshot": os.path.basename(proof_screenshot) if proof_screenshot else "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": final_msg,
                    "is_verified": is_verified
                }
            }

        except Exception as e:
            yield {"event": "error", "data": f"Application error: {str(e)}"}
        finally:
            ApplicationMemory.cleanup(session_id)
            await engine.close()

