import os
import re
import asyncio
from typing import Dict, Any, Callable, Awaitable, Tuple
from playwright.async_api import Page, Locator
from backend.app.adapters.base_adapter import BaseAdapter
from backend.app.browser.human_actions import HumanActions
from backend.app.services.form_mapper import FormMapper

class ExternalATSAdapter(BaseAdapter):
    """
    Universal External ATS Adapter.
    Intelligently analyzes any company career portal (Greenhouse, Lever, Workday,
    SmartRecruiters, Ashby, BambooHR, or custom forms) and auto-populates all inputs using Playwright.
    """
    name = "external_ats"

    async def detect(self, page: Page, url: str) -> bool:
        # Default universal adapter for all company career portals
        return True

    @staticmethod
    def identify_ats_platform(url: str, html_snippet: str) -> str:
        """Fingerprints the ATS platform based on URL and DOM cues."""
        url_lower = url.lower()
        html_lower = html_snippet.lower()

        if "greenhouse.io" in url_lower or "gh_jid" in url_lower or "greenhouse" in html_lower:
            return "Greenhouse ATS"
        elif "lever.co" in url_lower or "lever" in html_lower:
            return "Lever ATS"
        elif "myworkdayjobs.com" in url_lower or "workday" in html_lower:
            return "Workday ATS"
        elif "smartrecruiters.com" in url_lower or "smartrecruiters" in html_lower:
            return "SmartRecruiters"
        elif "ashbyhq.com" in url_lower or "ashby" in html_lower:
            return "Ashby ATS"
        elif "bamboohr.com" in url_lower or "bamboohr" in html_lower:
            return "BambooHR"
        elif "icims.com" in url_lower or "icims" in html_lower:
            return "iCIMS"
        elif "taleo.net" in url_lower or "taleo" in html_lower:
            return "Oracle Taleo"
        return "Company Career Portal"

    async def execute(
        self,
        page: Page,
        candidate_data: Dict[str, Any],
        resume_pdf_path: str,
        emit_event: Callable[[str, Any], Awaitable[None]]
    ) -> Dict[str, Any]:
        result = {
            "platform": "external_ats",
            "applied": False,
            "ats_type": "Universal ATS",
            "fields_filled": {},
            "screening_answers": {}
        }

        current_url = page.url
        # Guard: Reject platform login / signup pages if ever reached
        current_url_lower = current_url.lower()
        if any(auth_kw in current_url_lower for auth_kw in [
            "linkedin.com/signup", "linkedin.com/login", "linkedin.com/checkpoint", "linkedin.com/uas",
            "naukri.com/nlogin", "indeed.com/account/login"
        ]):
            await emit_event("status", f"⚠️ Reached portal login wall at {current_url[:60]} instead of company application form.")
            result["status"] = "auth_required"
            result["message"] = f"Application redirect hit an authentication wall at {current_url[:60]} instead of a company career form. Platform login required."
            return result

        await emit_event("status", f"Landed on company portal ({current_url[:70]}...). Analyzing page...")
        await HumanActions.sleep(1500, 2500)

        # 1. Dismiss common Cookie / GDPR banners if present
        try:
            cookie_selectors = [
                '#onetrust-accept-btn-handler',
                'button#accept-cookie',
                'button[id*="cookie-accept" i]',
                'button[id*="accept-cookie" i]',
                'button[aria-label*="accept cookie" i]',
                'button:has-text("Accept All Cookies")',
                'button:has-text("Accept All")',
                'button:has-text("Accept Cookies")',
                'button:has-text("Allow All")',
                'button:has-text("I Agree to Cookies")',
                'button.cookie-banner__accept:visible'
            ]
            for c_sel in cookie_selectors:
                c_btn = page.locator(c_sel).first
                if await c_btn.count() > 0 and await c_btn.is_visible():
                    await c_btn.click(timeout=2000)
                    await HumanActions.sleep(400, 800)
                    break
        except Exception:
            pass

        # 2. Fingerprint ATS type
        try:
            body_preview = (await page.content())[:4000]
            ats_name = self.identify_ats_platform(current_url, body_preview)
            result["ats_type"] = ats_name
            await emit_event("status", f"Recognized form architecture: {ats_name}. Inspecting DOM structure...")
        except Exception:
            ats_name = "Company Career Portal"

        # 3. Check if we need to click "Apply" / "Apply Now" to reveal the application form
        # Often company landing pages show the job description first with an "Apply" button
        try:
            visible_inputs = page.locator('input[type="text"]:visible, input[type="email"]:visible, input[type="tel"]:visible')
            if await visible_inputs.count() == 0:
                apply_ctas = [
                    'a:has-text("Apply Now"):visible',
                    'button:has-text("Apply Now"):visible',
                    'a:has-text("Apply for this job"):visible',
                    'button:has-text("Apply for this job"):visible',
                    'a:has-text("Apply"):visible',
                    'button:has-text("Apply"):visible',
                    'a[href*="#apply"]:visible',
                    'button[data-automation-id*="apply"]:visible'
                ]
                for cta_sel in apply_ctas:
                    cta = page.locator(cta_sel).first
                    if await cta.count() > 0 and await cta.is_visible():
                        await emit_event("status", "Clicking 'Apply Now' to open company application form...")
                        await HumanActions.human_click(cta, page)
                        await HumanActions.sleep(2000, 3000)
                        break
        except Exception as e:
            print(f"[ExternalATSAdapter] CTA click error: {e}")

        # Smooth scroll downward to ensure lazy-loaded forms render
        await HumanActions.smooth_scroll(page, 600, 4)
        await HumanActions.sleep(800, 1500)

        # 4. Multi-step form completion loop (handles single-page forms & multi-step wizards up to 5 steps)
        max_wizard_steps = 5
        for step in range(1, max_wizard_steps + 1):
            await emit_event("status", f"Processing application form (Step {step})...")

            # A. Process Text / Email / Phone / Number Inputs
            inputs = page.locator('input[type="text"]:visible, input[type="email"]:visible, input[type="tel"]:visible, input[type="number"]:visible')
            input_count = await inputs.count()

            for i in range(input_count):
                inp = inputs.nth(i)
                try:
                    if not await inp.is_visible():
                        continue
                    current_val = await inp.input_value()
                    if current_val:
                        continue

                    name = await inp.get_attribute("name") or ""
                    inp_id = await inp.get_attribute("id") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    aria = await inp.get_attribute("aria-label") or ""

                    # Label lookup via <label for="..."> or parent text
                    label_text = ""
                    if inp_id:
                        lbl = page.locator(f'label[for="{inp_id}"]').first
                        if await lbl.count() > 0:
                            label_text = await lbl.text_content() or ""
                    if not label_text:
                        try:
                            parent_text = await inp.evaluate("el => el.closest('div, label, fieldset') ? el.closest('div, label, fieldset').innerText : ''")
                            label_text = (parent_text or "").split("\n")[0][:60]
                        except Exception:
                            pass

                    field_key, val_to_fill = FormMapper.match_field(
                        name=name,
                        label=label_text,
                        placeholder=placeholder,
                        aria_label=aria,
                        candidate=candidate_data
                    )

                    if not val_to_fill:
                        comb = f"{name} {label_text} {placeholder} {aria}".lower()
                        val_to_fill = FormMapper.answer_screening_question(comb, candidate_data)

                    if val_to_fill:
                        await HumanActions.human_type(inp, str(val_to_fill))
                        field_display = field_key or name or inp_id or f"field_{i}"
                        result["fields_filled"][field_display.strip()[:40]] = str(val_to_fill)
                        await HumanActions.sleep(120, 250)
                except Exception as e_field:
                    print(f"[ExternalATSAdapter] Field error on input {i}: {e_field}")

            # B. Process File Upload (Tailored Resume PDF)
            file_inputs = page.locator('input[type="file"]')
            if await file_inputs.count() > 0 and resume_pdf_path and os.path.exists(resume_pdf_path):
                try:
                    await file_inputs.first.set_input_files(resume_pdf_path)
                    result["fields_filled"]["resume_file"] = os.path.basename(resume_pdf_path)
                    await emit_event("status", f"✓ Uploaded tailored resume: {os.path.basename(resume_pdf_path)}")
                    await HumanActions.sleep(1000, 1800)
                except Exception as e_file:
                    print(f"[ExternalATSAdapter] File attachment error: {e_file}")

            # C. Process Textareas (Cover Letter / Summary / Additional info)
            textareas = page.locator('textarea:visible')
            for i in range(await textareas.count()):
                ta = textareas.nth(i)
                try:
                    if not await ta.is_visible():
                        continue
                    current_val = await ta.input_value()
                    if current_val:
                        continue

                    ta_name = await ta.get_attribute("name") or ""
                    ta_id = await ta.get_attribute("id") or ""
                    ta_ph = await ta.get_attribute("placeholder") or ""
                    comb = f"{ta_name} {ta_id} {ta_ph}".lower()

                    if any(k in comb for k in ["cover", "letter", "note", "why", "additional", "summary", "about"]):
                        cl_text = candidate_data.get("cover_letter") or (
                            f"Dear Hiring Team,\n\nI am writing to express my strong interest in this position. "
                            f"With over 2.5+ years of experience developing scalable Python backends, FastAPI microservices, "
                            f"and event-driven architectures, I am eager to contribute to your team.\n\nBest regards,\n"
                            f"{candidate_data.get('full_name', 'S. Senkathirselvan')}"
                        )
                        await ta.fill(cl_text)
                        result["fields_filled"]["cover_letter"] = "Attached cover letter"
                        await emit_event("status", "Attached tailored cover letter to application.")
                        await HumanActions.sleep(400, 800)
                except Exception as e_ta:
                    print(f"[ExternalATSAdapter] Textarea error: {e_ta}")

            # D. Handle Common Dropdown (<select>) Elements
            selects = page.locator('select:visible')
            for i in range(await selects.count()):
                sel = selects.nth(i)
                try:
                    if not await sel.is_visible():
                        continue
                    sel_text = (await sel.evaluate("el => el.closest('div, label') ? el.closest('div, label').innerText : ''")).lower()
                    options = await sel.locator('option').all_text_contents()
                    
                    target_opt = None
                    if "authorized" in sel_text or "authorization" in sel_text or "eligible" in sel_text:
                        target_opt = next((o for o in options if "yes" in o.lower()), None)
                    elif "sponsorship" in sel_text or "visa" in sel_text:
                        target_opt = next((o for o in options if "no" in o.lower()), None)
                    elif "gender" in sel_text:
                        target_opt = next((o for o in options if "male" in o.lower()), None)
                    elif "experience" in sel_text:
                        target_opt = next((o for o in options if "2" in o or "3" in o), None)
                    elif "country" in sel_text:
                        target_opt = next((o for o in options if "india" in o.lower()), None)

                    if target_opt:
                        await sel.select_option(label=target_opt)
                        result["screening_answers"][f"select_{i}"] = target_opt
                        await HumanActions.sleep(200, 400)
                except Exception as e_sel:
                    print(f"[ExternalATSAdapter] Select error: {e_sel}")

            # E. Check for Checkboxes (e.g. Consent, Policy, Acknowledgment)
            checkboxes = page.locator('input[type="checkbox"]:visible')
            for i in range(await checkboxes.count()):
                cb = checkboxes.nth(i)
                try:
                    if not await cb.is_checked():
                        cb_text = (await cb.evaluate("el => el.closest('label, div') ? el.closest('label, div').innerText : ''")).lower()
                        # Auto-accept standard terms, privacy policies, and declarations
                        if any(k in cb_text for k in ["agree", "consent", "privacy", "policy", "declare", "certify", "terms", "accurate"]):
                            await cb.check()
                            await HumanActions.sleep(150, 300)
                except Exception:
                    pass

            # F. Check if final submission button is already ready
            final_submits = page.locator(
                'button:has-text("Submit application"):visible, '
                'button:has-text("Submit Application"):visible, '
                'button:has-text("Submit"):visible, '
                'button[type="submit"]:has-text("Apply"):visible, '
                'input[type="submit"]:visible'
            )
            if await final_submits.count() > 0:
                await emit_event("status", f"Application form completed and ready for submission.")
                result["applied"] = True
                result["status"] = "review_ready"
                return result

            # G. Check for multi-step "Next" / "Continue" buttons
            next_btns = page.locator(
                'button:has-text("Next"):visible, '
                'button:has-text("Continue"):visible, '
                'button:has-text("Save & Continue"):visible, '
                'button[aria-label*="next" i]:visible'
            )
            if await next_btns.count() > 0:
                await emit_event("status", f"Advancing to next step in application wizard...")
                await HumanActions.human_click(next_btns.first, page)
                await HumanActions.sleep(2000, 3000)
            else:
                # No next button, form is filled
                break

        result["applied"] = True
        result["status"] = "review_ready"
        return result

    @classmethod
    async def verify_submission_receipt(cls, page: Page) -> Tuple[bool, str]:
        """
        Actively verifies company ATS application confirmation message or URL redirect.
        Waits for up to 15 seconds to ensure server confirmation.
        """
        for _ in range(12):
            url = page.url.lower()
            if any(w in url for w in ["thank_you", "thank-you", "confirmation", "applied", "success", "submitted", "application-received"]):
                return True, f"Company portal navigated to verified confirmation URL: {page.url}"

            success_selectors = [
                ':has-text("Thank you for applying")',
                ':has-text("Your application has been received")',
                ':has-text("Application submitted")',
                ':has-text("Application Received")',
                ':has-text("Application successfully submitted")',
                ':has-text("Thanks for applying")',
                ':has-text("We have received your application")',
                'h1:has-text("Thank you")',
                'h2:has-text("Thank you")',
                'h3:has-text("Thank you")'
            ]
            for sel in success_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        text = (await loc.text_content() or "").strip()
                        return True, f"Company portal verified receipt: '{text[:80]}'"
                except Exception:
                    pass

            await asyncio.sleep(1.0)

        # Fallback inspection of body text
        try:
            body_text = (await page.evaluate("() => document.body ? document.body.innerText : ''")).lower()
            if any(k in body_text for k in ["thank you for applying", "application has been received", "application submitted"]):
                return True, "Application receipt confirmed in page body content."
        except Exception:
            pass

        return False, "Submission could not be verified on the portal DOM."
