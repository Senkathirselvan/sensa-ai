"""
Week 4: Auto-Apply Agent with Human-in-the-Loop
Opens job application in a real browser only after user confirms in the sidebar.
"""

import os
import json
from typing import Dict

BROWSER_PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "browser_profile")
PENDING_APPLY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pending_apply.json")


def queue_job_for_apply(job: Dict) -> str:
    os.makedirs(os.path.dirname(PENDING_APPLY_PATH), exist_ok=True)
    with open(PENDING_APPLY_PATH, "w") as f:
        json.dump(job, f, indent=2)
    return (
        f"Job '{job.get('title')}' at '{job.get('company')}' has been queued for application. "
        f"Please review and click 'Confirm & Apply' in the sidebar."
    )


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
        os.remove(PENDING_APPLY_PATH)


def execute_apply(job: Dict) -> str:
    job_url = job.get("url", "")
    job_title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")

    if not job_url:
        return "Cannot apply - no job URL found."

    try:
        from playwright.sync_api import sync_playwright
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.new_page()
            page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            selectors = [
                "button.jobs-apply-button",
                "button:has-text('Easy Apply')",
                "button:has-text('Quick Apply')",
                "button:has-text('Apply Now')",
                "a:has-text('Apply')",
            ]
            clicked = False
            for selector in selectors:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    clicked = True
                    page.wait_for_timeout(2000)
                    break

            if not clicked:
                context.close()
                return f"No Easy Apply button found. Apply manually: {job_url}"

            page.wait_for_timeout(30000)
            context.close()

        return f"Application started for {job_title} at {company}. Please confirm you submitted the form."
    except ImportError:
        return "Playwright not installed. Run: pip install playwright && playwright install chromium"
    except Exception as e:
        return f"Apply failed: {str(e)}"
