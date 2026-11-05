import os
import shutil
import asyncio
import re
from typing import Dict, Any, Callable, Awaitable
from playwright.async_api import Page
from backend.app.adapters.base_adapter import BaseAdapter
from backend.app.browser.human_actions import HumanActions
from backend.app.services.form_mapper import FormMapper

class NaukriAdapter(BaseAdapter):
    name = "naukri"

    async def detect(self, page: Page, url: str) -> bool:
        return "naukri.com" in url.lower()

    async def execute(
        self,
        page: Page,
        candidate_data: Dict[str, Any],
        resume_pdf_path: str,
        emit_event: Callable[[str, Any], Awaitable[None]]
    ) -> Dict[str, Any]:
        result = {
            "platform": "naukri",
            "applied": False,
            "external_redirect": False,
            "external_url": None,
            "fields_filled": {},
            "screening_answers": {}
        }

        await emit_event("status", "Navigating Naukri posting with verified authentication...")
        await HumanActions.sleep(800, 1500)

        # 0. Check for Akamai Bot Manager / Access Denied block
        try:
            page_title = (await page.title() or "").lower()
            page_content = (await page.content() or "").lower()
            if "access denied" in page_title or "access denied" in page_content or "you don't have permission to access" in page_content:
                await emit_event("status", "⚠️ Naukri anti-bot firewall (Akamai Access Denied) detected. Session refresh required.")
                result["status"] = "auth_required"
                result["message"] = "Naukri security checkpoint (Akamai Access Denied) blocked automated request. Please reconnect your Naukri account with a fresh session."
                return result

            # Detect if Naukri redirected to generic search results (job expired / closed)
            current_url = page.url.lower()
            if "expjd=true" in current_url or "jobs-in-india" in current_url or "jobs in india" in page_title or "job vacancies in india" in page_title:
                await emit_event("status", "⚠️ This job opening has expired or been closed by the recruiter on Naukri.")
                result["status"] = "button_not_found"
                result["message"] = "This job posting has expired or been closed by the recruiter on Naukri."
                return result
        except Exception:
            pass

        # 1. Wait for page hydration & pre-scroll to reveal action buttons
        try:
            await page.wait_for_selector(".styles_job-header__container, #apply-button, .styles_jd-header-title__RZw0E, .styles_apply-button__uJI3A", timeout=14000)
        except Exception:
            try:
                skeleton = page.locator('.styles_skeleton, [class*="skeleton"]').first
                if await skeleton.count() > 0 and await skeleton.is_visible():
                    await skeleton.wait_for(state="hidden", timeout=8000)
            except Exception:
                pass
            await HumanActions.sleep(2000, 3000)

        await page.evaluate("window.scrollBy(0, 500);")
        await HumanActions.sleep(800, 1400)

        # 2. Check if already applied
        already_applied_locators = [
            'button:has-text("Already Applied")',
            'span:has-text("Already Applied")',
            'div:has-text("Applied to ")',
            'span:has-text("Applied to ")',
            '.already-applied',
            'button[disabled]:has-text("Applied")',
            'span[disabled]:has-text("Applied")'
        ]
        for sel in already_applied_locators:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await emit_event("status", "✓ You have already applied for this opening on Naukri.")
                result["applied"] = True
                result["status"] = "already_applied"
                return result

        # 3. Locate Apply button
        apply_buttons = [
            '#apply-button:visible',
            'button.apply-button:visible',
            '.styles_apply-button__uJI3A:visible',
            'button:has-text("Apply"):visible',
            'button:has-text("Apply on company site"):visible',
            '#apply-button',
            'button.apply-button'
        ]

        target_btn = None
        is_external = False
        for sel in apply_buttons:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                try:
                    await loc.scroll_into_view_if_needed()
                    await HumanActions.sleep(200, 400)
                except Exception:
                    pass
                if await loc.is_visible():
                    btn_text = (await loc.text_content() or "").strip()
                    if "company site" in btn_text.lower():
                        is_external = True
                    target_btn = loc
                    break

        if not target_btn:
            # Fallback deeper scroll to reveal sticky apply bar
            await HumanActions.smooth_scroll(page, 500, 4)
            for sel in apply_buttons:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    target_btn = loc
                    break

        if not target_btn:
            await emit_event("status", "No direct apply button found or job opening has expired.")
            result["status"] = "button_not_found"
            result["message"] = "Could not locate Apply button on Naukri posting (opening may be closed or requires company portal)."
            return result

        if is_external:
            await emit_event("status", "Detected 'Apply on Company Site' external redirection route...")
            result["external_redirect"] = True
            try:
                async with page.context.expect_page(timeout=8000) as new_page_info:
                    await HumanActions.human_click(target_btn, page)
                new_tab = await new_page_info.value
                await new_tab.wait_for_load_state("domcontentloaded")
                result["external_url"] = new_tab.url
                await emit_event("status", f"Opened company portal: {new_tab.url}")
            except Exception:
                await HumanActions.human_click(target_btn, page)
                result["external_url"] = page.url
            return result

        # 4. Direct Naukri Quick Apply
        await emit_event("status", "Clicking Naukri Apply button with stealth action...")
        await HumanActions.human_click(target_btn, page)
        await HumanActions.sleep(2500, 3500)

        # 5. Check if Naukri Login modal popped up
        login_modal = page.locator('.login-layer, #login_Layer, .login-modal, div:has-text("Already a member? Login"), div:has-text("Log in to apply")').first
        if await login_modal.count() > 0 and await login_modal.is_visible():
            await emit_event("status", "⚠️ Blocked by Naukri Login requirement. Authentication required.")
            result["status"] = "auth_required"
            result["message"] = "Naukri account authentication required. Please connect your Naukri account to authorize automated applications."
            return result

        # 6. Handle possible questionnaire modal / chatbot questions
        drawer_locator = page.locator('.chatbot_Drawer:visible, .chatbot_MessageContainer:visible, .chatbot_DrawerContentWrapper:visible').first
        if await drawer_locator.count() > 0:
            await emit_event("status", "Processing recruiter chatbot screening questions...")
            for turn in range(8):
                # 1. Check for visible choices (radio labels or multiselect checkboxes)
                choice_labels = await page.locator('.chatbot_Drawer label:visible, .chatbot_Drawer .mcc__label:visible, .chatbot_Drawer .ssrc__label:visible').all()
                if choice_labels:
                    bot_msgs = await page.locator('.botMsg, .botItem').all()
                    last_bot_text = (await bot_msgs[-1].text_content() or "").strip() if bot_msgs else ""
                    q_lower = last_bot_text.lower()
                    matched_label = choice_labels[0]
                    for lbl in choice_labels:
                        lbl_text = (await lbl.text_content() or "").strip().lower()
                        if "notice" in q_lower and ("15" in lbl_text or "less" in lbl_text):
                            matched_label = lbl
                            break
                        elif "location" in q_lower and (candidate_data.get("city", "chennai").lower() in lbl_text):
                            matched_label = lbl
                            break
                        elif "yes" in lbl_text:
                            matched_label = lbl
                            break

                    selected_text = (await matched_label.text_content() or "").strip()
                    await emit_event("status", f"Selecting chatbot option: '{selected_text}'...")
                    await matched_label.click()
                    await HumanActions.sleep(500, 800)

                    save_btn = page.locator('.chatbot_Drawer .sendMsg:visible, .chatbot_Drawer [class*="send"]:not(.disabled):visible').first
                    if await save_btn.count() > 0:
                        try:
                            await save_btn.click(timeout=3000)
                        except Exception:
                            pass
                        await HumanActions.sleep(2500, 3500)
                    result["screening_answers"][f"turn_{turn+1}"] = selected_text
                    continue

                # 2. Check for contenteditable text area, text input, or chatbot message box
                text_area = page.locator(
                    '.chatbot_Drawer [contenteditable="true"]:visible, '
                    '.chatbot_Drawer div.textArea:visible, '
                    '[id*="userInput"]:visible, '
                    '.chatbot_Drawer input[type="text"]:visible, '
                    'input[placeholder*="Type message"]:visible, '
                    'textarea[placeholder*="Type message"]:visible, '
                    '.chatbot_Drawer textarea:visible'
                ).first
                if await text_area.count() > 0:
                    bot_msgs = await page.locator('.botMsg, .botItem, .chatbot_Drawer p:visible').all()
                    last_bot_text = (await bot_msgs[-1].text_content() or "").strip() if bot_msgs else ""
                    ans = FormMapper.answer_screening_question(last_bot_text, candidate_data)
                    await emit_event("status", f"Answering recruiter question: '{ans}'...")
                    await text_area.click()
                    await HumanActions.sleep(200, 400)
                    await page.keyboard.type(str(ans))
                    await HumanActions.sleep(400, 700)

                    # Scoped send button inside drawer
                    send_btn = page.locator(
                        '.chatbot_Drawer .sendMsg:visible, '
                        '.chatbot_Drawer [class*="send"]:not(.disabled):visible'
                    ).first
                    clicked = False
                    if await send_btn.count() > 0 and await send_btn.is_visible():
                        try:
                            await send_btn.click(timeout=3000)
                            clicked = True
                        except Exception:
                            pass
                    if not clicked:
                        await page.keyboard.press("Enter")
                    await HumanActions.sleep(2500, 3500)
                    result["screening_answers"][f"turn_{turn+1}"] = ans
                    continue

                # If neither choice nor text area is present, screening is complete
                break

        # Also handle standard input elements if present
        chatbot_inputs = page.locator('.chatbot_Drawer input[type="text"]:visible, .custom-questionnaire input:visible')
        input_count = await chatbot_inputs.count()
        if input_count > 0:
            await emit_event("status", f"Answering {input_count} screening question(s)...")
            for i in range(input_count):
                inp = chatbot_inputs.nth(i)
                if await inp.is_visible():
                    placeholder = await inp.get_attribute("placeholder") or ""
                    ans = FormMapper.answer_screening_question(placeholder, candidate_data)
                    await HumanActions.human_type(inp, str(ans))
                    result["screening_answers"][f"question_{i+1}"] = ans
                    await HumanActions.sleep(300, 600)

        # 7. Check if resume attachment needed
        resume_upload_input = page.locator('input[type="file"]')
        if await resume_upload_input.count() > 0 and resume_pdf_path and os.path.exists(resume_pdf_path):
            await emit_event("status", "Attaching tailored PDF resume to Naukri application...")
            # Use sanitized short filename to avoid portal upload rejections
            clean_upload_path = resume_pdf_path
            try:
                candidate_name = (candidate_data.get("full_name") or "Candidate").split()[0]
                tmp_clean = f"/tmp/Resume_{candidate_name}.pdf"
                shutil.copyfile(resume_pdf_path, tmp_clean)
                clean_upload_path = tmp_clean
            except Exception:
                pass

            try:
                await resume_upload_input.first.set_input_files(clean_upload_path)
                result["fields_filled"]["resume_file"] = os.path.basename(clean_upload_path)
                await HumanActions.sleep(1500, 2000)
            except Exception as e:
                print(f"[NaukriAdapter] Resume upload error: {e}")

        result["applied"] = True
        result["status"] = "review_ready"
        return result

    @classmethod
    async def verify_submission_receipt(cls, page: Page) -> tuple[bool, str]:
        """Actively verifies Naukri application receipt or login blockage."""
        # 1. Check for genuine application confirmation in DOM elements
        confirmation_selectors = [
            'div:has-text("Applied to ")',
            'span:has-text("Applied to ")',
            'p:has-text("Applied to ")',
            'h1:has-text("Applied to ")',
            'h2:has-text("Applied to ")',
            'h3:has-text("Applied to ")',
            'div:has-text("Power up your applies with Pro")',
            'div:has-text("Send Me Jobs Like This")',
            '.apply-message:has-text("Application sent")',
            '.apply-message:has-text("successfully applied")',
            'span:has-text("Already Applied")',
            'button:has-text("Already Applied")',
            '.applied-success',
            'div:has-text("Application submitted successfully")',
            'div:has-text("Application sent")',
            'div:has-text("You were redirected to the company website")'
        ]
        for sel in confirmation_selectors:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                text = (await loc.text_content() or "").strip()
                return True, f"Naukri verified confirmation receipt: '{text[:80]}'"

        # 2. Check if login wall appeared
        login_modal = page.locator('.login-layer, #login_Layer, div:has-text("Already a member? Login")').first
        if await login_modal.count() > 0 and await login_modal.is_visible():
            return False, "Application could not be submitted: Blocked by Naukri Login requirement."

        # 3. Check if apply button changed to Applied
        apply_btn = page.locator('#apply-button, button.apply-button, .styles_apply-button__uJI3A, button:has-text("Applied"), span:has-text("Applied")').first
        if await apply_btn.count() > 0:
            txt = (await apply_btn.text_content() or "").strip().lower()
            if "applied" in txt:
                return True, f"Naukri verified application status: '{txt}'"

        # 4. Check entire page body content for applied status
        try:
            content = (await page.content() or "").lower()
            if "already applied" in content:
                return True, "Naukri verified application status: Already Applied"
            if 'applied to "' in content or "applied to '" in content or "applied to “" in content or "applied to ”" in content:
                return True, "Naukri verified application status: Applied to position"
            if "power up your applies with pro" in content and "send me jobs like this" in content:
                return True, "Naukri verified application status: Applied (Confirmation Screen)"
            if "successfully applied" in content or "application submitted successfully" in content:
                return True, "Naukri verified application status: Successfully Applied"
        except Exception:
            pass

        # 5. Check if page redirected to expired job description
        if "expjd=true" in page.url.lower():
            return False, "This job opening has expired or been closed by the recruiter."

        return False, "Could not verify genuine application confirmation receipt on Naukri."

