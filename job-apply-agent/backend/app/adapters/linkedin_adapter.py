import re
import asyncio
from typing import Dict, Any, Callable, Awaitable, Tuple
from playwright.async_api import Page
from backend.app.adapters.base_adapter import BaseAdapter
from backend.app.browser.human_actions import HumanActions
from backend.app.services.form_mapper import FormMapper

class LinkedInAdapter(BaseAdapter):
    name = "linkedin"

    async def detect(self, page: Page, url: str) -> bool:
        return "linkedin.com" in url.lower()

    async def execute(
        self,
        page: Page,
        candidate_data: Dict[str, Any],
        resume_pdf_path: str,
        emit_event: Callable[[str, Any], Awaitable[None]]
    ) -> Dict[str, Any]:
        result = {
            "platform": "linkedin",
            "applied": False,
            "easy_apply": False,
            "status": "in_progress",
            "fields_filled": {},
            "screening_answers": {}
        }

        await emit_event("status", "Inspecting LinkedIn job posting & authentication status...")
        await HumanActions.sleep(1000, 1800)

        # 1. Check if user is logged into LinkedIn
        is_logged_in = False
        logged_in_selectors = [
            'nav.global-nav',
            'img.global-nav__me-photo',
            'button.global-nav__primary-link-me-menu-trigger',
            '#global-nav',
            'a.global-nav__primary-link--active',
            'div.profile-rail-card',
            '.feed-identity-module',
            'button.jobs-apply-button:has-text("Easy Apply")',
            'button:has-text("Easy Apply")'
        ]

        # Give LinkedIn SPA up to 5 seconds to mount global navigation and profile elements
        for _ in range(5):
            for sel in logged_in_selectors:
                if await page.locator(sel).count() > 0:
                    is_logged_in = True
                    break
            if is_logged_in:
                break
            await asyncio.sleep(1.0)

        # Context cookie verification fallback
        if not is_logged_in:
            try:
                ctx_cookies = await page.context.cookies()
                has_li_cookie = any(c.get("name") == "li_at" and c.get("value") for c in ctx_cookies)
                # If li_at cookie is present and there is no full-page sign-in wall or checkpoint
                is_sign_in_page = "login" in page.url or "signup" in page.url or "checkpoint" in page.url
                if has_li_cookie and not is_sign_in_page:
                    is_logged_in = True
            except Exception:
                pass

        # Check for guest indicators (sign in / join now buttons)
        has_easy_apply_quick = await page.locator('button:has-text("Easy Apply"):visible').count() > 0
        if not has_easy_apply_quick and not is_logged_in:
            guest_selectors = [
                'a:has-text("Sign in")',
                'button:has-text("Sign in")',
                'a:has-text("Join now")',
                'a[href*="/login"]',
                'a[href*="/signup"]',
                '#joinUrlWithRedirect'
            ]
            for g_sel in guest_selectors:
                if await page.locator(g_sel).count() > 0:
                    is_logged_in = False
                    break

        # 2. Check if job posting is closed
        page_content = (await page.content() or "").lower()
        if "no longer accepting applications" in page_content:
            await emit_event("status", "⚠️ This LinkedIn job is closed and no longer accepting applications.")
            result["status"] = "closed"
            result["message"] = "This job posting has been closed by the recruiter on LinkedIn ('No longer accepting applications')."
            return result

        # 3. Dismiss any intrusive modal overlays (e.g. guest login prompt overlay)
        try:
            overlay_dismiss = page.locator('button[aria-label="Dismiss"]:visible, button.modal__dismiss:visible, button[data-modal="dismiss"]:visible').first
            if await overlay_dismiss.count() > 0:
                await overlay_dismiss.click(timeout=1500)
                await HumanActions.sleep(300, 600)
        except Exception:
            pass

        # 4. Mandatory LinkedIn Authentication Check
        # CRITICAL: LinkedIn blocks BOTH Easy Apply and external employer redirects behind a login wall for guests.
        # If the user is not authenticated, clicking any button redirects to linkedin.com/signup or a login popup.
        if not is_logged_in:
            await emit_event("status", "⚠️ LinkedIn Authentication Wall: No active LinkedIn session detected.")
            # NEVER auto-delete user session cookies on runtime check failure
            result["status"] = "auth_required"
            result["message"] = (
                "LinkedIn session required: You are currently not signed in to LinkedIn. "
                "LinkedIn locks Easy Apply and hides external company career links behind a login/signup wall for guest visitors. "
                "Please click 'Connect' next to LinkedIn Easy Apply in Career Agent Tools on the left sidebar to log into your LinkedIn account."
            )
            return result

        # 5. Check for Easy Apply button
        easy_apply_btn = page.locator('button.jobs-apply-button:has-text("Easy Apply"), button:has-text("Easy Apply"):visible').first
        has_easy_apply = (await easy_apply_btn.count() > 0) and (await easy_apply_btn.is_visible())

        # 6. Check for External Company Career Portal link ("Apply on company website", "Apply", or offsite redirect)
        external_apply_btn = page.locator(
            'a[data-tracking-control-name*="apply-link-offsite"]:visible, '
            'button[data-tracking-control-name*="apply-link-offsite"]:visible, '
            'a[data-tracking-control-name*="apply"]:visible, '
            'button[data-tracking-control-name*="apply"]:visible, '
            'button.jobs-apply-button:visible, '
            'a.jobs-apply-button:visible, '
            'button.apply-button:visible, '
            'a.apply-button:visible, '
            'a:has-text("Apply"):visible, '
            'button:has-text("Apply"):visible'
        ).first
        has_external_apply = (await external_apply_btn.count() > 0) and (await external_apply_btn.is_visible())

        # If Easy Apply is available and user is authenticated: proceed with in-modal Easy Apply
        if has_easy_apply:
            result["easy_apply"] = True
            await emit_event("status", "Launching LinkedIn Easy Apply modal...")
            await HumanActions.human_click(easy_apply_btn, page)
            await HumanActions.sleep(1500, 2200)

            # Check if clicking easy apply opened a sign-in dialog
            signin_in_dialog = page.locator('div[role="dialog"]:has-text("Sign in"), div[role="dialog"]:has-text("Continue with Google")')
            if await signin_in_dialog.count() > 0 and await signin_in_dialog.first.is_visible():
                await emit_event("status", "⚠️ LinkedIn Sign-In Required: Cannot proceed without login.")
                result["status"] = "auth_required"
                result["message"] = "LinkedIn blocked the application behind a Sign-In wall. Please log into LinkedIn."
                return result

        # If External Company Career Portal is detected: follow link to company site and use Universal ATS Engine
        elif has_external_apply:
            await emit_event("status", "🌐 Company Career Site application detected. Navigating to employer portal...")
            company_page = page
            try:
                # Check if clicking external apply opens a new tab
                async with page.context.expect_page(timeout=7000) as new_page_info:
                    await HumanActions.human_click(external_apply_btn, page)
                company_page = await new_page_info.value
                await company_page.wait_for_load_state("domcontentloaded")
            except Exception:
                # If no new tab fired, check if href is direct URL
                try:
                    href = await external_apply_btn.get_attribute("href")
                    if href and href.startswith("http") and "linkedin.com" not in href:
                        company_page = await page.context.new_page()
                        await company_page.goto(href, wait_until="domcontentloaded", timeout=30000)
                    else:
                        await HumanActions.human_click(external_apply_btn, page)
                        await HumanActions.sleep(2500, 3500)
                        company_page = page
                except Exception:
                    company_page = page

            # Check for LinkedIn redirection interstitial modal ("You are going to an external site... Continue")
            try:
                interstitial_cta = company_page.locator('button:has-text("Continue"):visible, a:has-text("Continue"):visible, button:has-text("Go to website"):visible').first
                if await interstitial_cta.count() > 0:
                    await emit_event("status", "Confirming external redirect prompt on LinkedIn...")
                    await interstitial_cta.click(timeout=3000)
                    await HumanActions.sleep(2000, 3000)
            except Exception:
                pass

            # Wait up to 10 seconds for URL to transition away from LinkedIn to employer portal
            for _ in range(10):
                c_url = company_page.url.lower()
                if "linkedin.com" not in c_url:
                    break
                # If redirected to a login wall
                if any(w in c_url for w in ["signup", "login", "checkpoint", "uas"]):
                    await emit_event("status", "⚠️ LinkedIn redirected to authentication wall.")
                    result["status"] = "auth_required"
                    result["message"] = "LinkedIn session expired or authentication checkpoint triggered. Please reconnect LinkedIn."
                    return result
                await asyncio.sleep(1.0)

            # If still on LinkedIn, cannot proceed to company ATS
            if "linkedin.com" in company_page.url.lower():
                await emit_event("status", f"⚠️ Could not navigate to external company portal (Still on {company_page.url[:60]}).")
                result["status"] = "failed"
                result["message"] = f"Failed to redirect from LinkedIn to company career portal (remained on {company_page.url[:60]})."
                return result

            await HumanActions.sleep(2000, 3500)
            await emit_event("status", f"🌐 Landed on external company portal ({company_page.url[:60]}...). Handing off to Universal ATS Engine...")

            from backend.app.adapters.external_ats_adapter import ExternalATSAdapter
            ats_adapter = ExternalATSAdapter()
            ats_result = await ats_adapter.execute(company_page, candidate_data, resume_pdf_path, emit_event)
            ats_result["target_page"] = company_page
            ats_result["active_adapter"] = ats_adapter
            return ats_result

        else:
            await emit_event("status", "No Easy Apply or external application button found on this posting.")
            result["status"] = "button_not_found"
            result["message"] = "No Easy Apply or external application button found on this LinkedIn posting."
            return result

        # 3. Multi-step modal navigation loop
        max_steps = 8
        step_idx = 0
        dialog_selector = 'dialog, [role="dialog"], .jobs-easy-apply-modal, div.artdeco-modal'

        while step_idx < max_steps:
            step_idx += 1
            dialog = page.locator(dialog_selector).first
            if await dialog.count() == 0 or not await dialog.is_visible():
                break

            # If dialog has an active loader/spinner, wait for it to finish
            try:
                loader = dialog.locator('.artdeco-loader, .inline-spinner, svg.artdeco-loader__bars').first
                if await loader.count() > 0 and await loader.is_visible():
                    await loader.wait_for(state="hidden", timeout=7000)
                    await HumanActions.sleep(500, 1000)
            except Exception:
                pass

            await emit_event("status", f"Processing Easy Apply step {step_idx}...")
            await HumanActions.sleep(400, 800)

            # Check if we already reached final Review screen with Submit application button
            submit_direct = dialog.locator('button:has-text("Submit application"), button:has-text("Submit Application")').first
            if await submit_direct.count() > 0 and await submit_direct.is_visible():
                await emit_event("status", "Final review page reached in Easy Apply.")
                result["applied"] = True
                result["status"] = "review_ready"
                return result

            # Fill any text, number, tel inputs or textareas in dialog
            inputs = dialog.locator('input[type="text"], input[type="tel"], input[type="number"], textarea')
            for i in range(await inputs.count()):
                inp = inputs.nth(i)
                try:
                    if not await inp.is_visible():
                        continue
                    val = await inp.input_value()
                    if not val:
                        iid = await inp.get_attribute("id") or ""
                        name = await inp.get_attribute("name") or ""
                        placeholder = await inp.get_attribute("placeholder") or ""
                        aria = await inp.get_attribute("aria-label") or ""
                        label_el = dialog.locator(f'label[for="{iid}"]').first if iid else None
                        label_text = await label_el.text_content() if label_el and await label_el.count() > 0 else ""

                        combined_text = f"{aria} {label_text} {placeholder} {name}".lower()

                        # LinkedIn input validation strictly requires pure digits for CTC, notice period, and years
                        if "ctc" in combined_text or "salary" in combined_text or "compensation" in combined_text:
                            raw = str(candidate_data.get("current_ctc", "600000"))
                            fill_val = re.sub(r"[^\d]", "", raw) or "600000"
                        elif "notice" in combined_text:
                            raw = str(candidate_data.get("notice_period", "15"))
                            fill_val = re.sub(r"[^\d]", "", raw) or "15"
                        elif "experience" in combined_text or "year" in combined_text:
                            raw = str(candidate_data.get("years_of_experience", "2"))
                            fill_val = re.sub(r"[^\d]", "", raw) or "2"
                        else:
                            field_key, fill_val = FormMapper.match_field(
                                name=name,
                                label=label_text,
                                placeholder=placeholder,
                                aria_label=aria,
                                candidate=candidate_data
                            )
                            if not fill_val:
                                fill_val = FormMapper.answer_screening_question(combined_text, candidate_data)

                        if fill_val:
                            await inp.fill(fill_val)
                            field_name = aria or label_text or name or f"step_{step_idx}_field_{i}"
                            result["fields_filled"][field_name.strip()[:40]] = fill_val
                            await HumanActions.sleep(200, 400)
                except Exception as e:
                    print(f"[LinkedInAdapter] Field processing error: {e}")

            # Check radio buttons (e.g. for resume selection or yes/no questions)
            try:
                radios = await dialog.locator('input[type="radio"]').all()
                if radios:
                    checked = [await r.is_checked() for r in radios]
                    if not any(checked):
                        await radios[0].check()
            except Exception as e:
                print(f"[LinkedInAdapter] Radio processing error: {e}")

            # Handle Resume Upload step if file input is present
            file_input = dialog.locator('input[type="file"]')
            if await file_input.count() > 0 and resume_pdf_path:
                try:
                    await file_input.first.set_input_files(resume_pdf_path)
                    result["fields_filled"]["resume_file"] = resume_pdf_path
                    await emit_event("status", "Tailored PDF resume attached to LinkedIn modal.")
                except Exception as e:
                    print(f"[LinkedInAdapter] File upload error: {e}")

            # Advance: Click Review if ready, or Next
            review_btn = page.locator('button:has-text("Review"):visible').first
            next_btn = page.locator('button:has-text("Next"):visible, button[aria-label*="next" i]:visible, button[aria-label*="continue" i]:visible').first

            if await review_btn.count() > 0 and await review_btn.is_visible():
                await emit_event("status", "Reviewing completed Easy Apply application...")
                await HumanActions.human_click(review_btn, page)
                await HumanActions.sleep(1500, 2500)
                # Check if we landed on the final review page
                submit_direct = page.locator('button:has-text("Submit application"):visible, button:has-text("Submit Application"):visible').first
                if await submit_direct.count() > 0 and await submit_direct.is_visible():
                    result["applied"] = True
                    result["status"] = "review_ready"
                    return result
            elif await next_btn.count() > 0 and await next_btn.is_visible():
                await HumanActions.human_click(next_btn, page)
                await HumanActions.sleep(1200, 2000)
            else:
                break

        result["applied"] = True
        result["status"] = "review_ready"
        return result

    @classmethod
    async def verify_submission_receipt(cls, page: Page) -> Tuple[bool, str]:
        """
        Actively inspects the DOM for verifiable proof that LinkedIn submitted the application.
        Waits for in-flight submission loaders and polls confirmation receipts for up to 20 seconds.
        """
        # 1. Wait for in-flight submission spinner / loader to finish (up to 15s)
        loader_selectors = [
            '.artdeco-loader',
            '.inline-spinner',
            'svg.artdeco-loader__bars',
            '[role="progressbar"]',
            '.artdeco-modal__content--loading',
            '.jobs-easy-apply-modal svg'
        ]
        for _ in range(15):
            is_loading = False
            for l_sel in loader_selectors:
                try:
                    l_loc = page.locator(l_sel).first
                    if await l_loc.count() > 0 and await l_loc.is_visible():
                        is_loading = True
                        break
                except Exception:
                    pass
            if is_loading:
                await asyncio.sleep(1.0)
            else:
                break

        # 2. Poll for genuine LinkedIn confirmation modal or status changes (up to 15s)
        confirmation_selectors = [
            'dialog:has-text("Application sent")',
            'div:has-text("Application sent")',
            'h3:has-text("Application sent")',
            'h2:has-text("Application sent")',
            'div:has-text("Your application was sent to")',
            'p:has-text("Your application was sent to")',
            'div:has-text("Application submitted")',
            'p:has-text("Application submitted")',
            'span:has-text("Application submitted")',
            ':has-text("Application submitted")',
            'button:has-text("Done")',
            'button:has-text("View application")',
            'a:has-text("View resume")'
        ]

        for _ in range(12):
            for sel in confirmation_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        text = (await loc.text_content() or "").strip()
                        # Dismiss confirmation modal cleanly if Done button exists
                        try:
                            done_btn = page.locator('button:has-text("Done"):visible, button[aria-label*="Dismiss"]:visible').first
                            if await done_btn.count() > 0:
                                await done_btn.click()
                        except Exception:
                            pass
                        return True, f"LinkedIn verified confirmation receipt: '{text[:80]}'"
                except Exception:
                    pass

            # Check if button on underlying page turned into "Applied" or "Application submitted"
            try:
                applied_badge = page.locator('span:has-text("Applied"), button:has-text("Applied"), :has-text("Application submitted")').first
                if await applied_badge.count() > 0 and await applied_badge.is_visible():
                    return True, "Job application permanently confirmed as 'Applied' on LinkedIn."
            except Exception:
                pass

            # Check if blocked by login
            try:
                signin_prompt = page.locator('div:has-text("Sign in"), button:has-text("Sign in with email")').first
                if await signin_prompt.count() > 0 and await signin_prompt.is_visible():
                    return False, "Application could not be submitted: Blocked by LinkedIn Sign-In wall."
            except Exception:
                pass

            await asyncio.sleep(1.0)

        # 3. Fallback body text inspection
        try:
            body_text = (await page.evaluate("() => document.body ? document.body.innerText : ''")).lower()
            if "application sent" in body_text or "your application was sent" in body_text or "application submitted" in body_text:
                return True, "Job application verified in page content receipt."
        except Exception:
            pass

        return False, "Submission could not be verified on the portal DOM."
