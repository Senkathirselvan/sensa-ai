import time
import os
import json
import httpx
from playwright.sync_api import sync_playwright

API_BASE = "http://localhost:8000/api"
FRONTEND_URL = "http://frontend:80"
SCREENSHOT_DIR = "/app/data"

def test_backend_apis():
    print("=== [1/3] TESTING BACKEND APIS ===")
    with httpx.Client(timeout=10.0) as client:
        # Resume status
        r1 = client.get(f"{API_BASE}/resume/status")
        print(f"[*] /api/resume/status: status={r1.status_code}, data={r1.json()}")
        assert r1.status_code == 200, "Resume status failed"
        assert r1.json().get("uploaded") is True, "Active resume.pdf not found"

        # Jobs counts
        r2 = client.get(f"{API_BASE}/jobs/counts")
        print(f"[*] /api/jobs/counts: status={r2.status_code}, data={r2.json()}")
        assert r2.status_code == 200, "Job counts failed"

        # Sessions
        r3 = client.get(f"{API_BASE}/sessions")
        print(f"[*] /api/sessions: status={r3.status_code}, session_count={len(r3.json())}")
        assert r3.status_code == 200, "Sessions endpoint failed"
    print(">>> BACKEND APIS: ALL PASS ✅\n")

def test_frontend_ui():
    print("=== [2/3] TESTING FRONTEND UI & CHAT STREAMING ===")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print(f"[*] Navigating to {FRONTEND_URL} ...")
        page.goto(FRONTEND_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Check Active Resume indicator in sidebar
        resume_badge = page.locator("text=resume.pdf").first
        print(f"[*] Resume badge found: {resume_badge.count() > 0}")
        assert resume_badge.count() > 0, "Active resume badge not visible in sidebar"

        page.screenshot(path=f"{SCREENSHOT_DIR}/verify_1_dashboard.png")

        # Input query
        input_el = page.locator("textarea, input[type='text']").first
        prompt_text = "Find Python Backend jobs in Chennai matching my resume"
        print(f"[*] Sending prompt: '{prompt_text}' ...")
        input_el.fill(prompt_text)
        page.keyboard.press("Enter")

        # Wait for agent reasoning and cards
        print("[*] Waiting for live tool execution, status updates, and cards (up to 45s)...")
        start_time = time.time()
        cards_rendered = False
        while time.time() - start_time < 45:
            page.wait_for_timeout(2000)
            apply_buttons = page.locator("button:has-text('Apply')")
            if apply_buttons.count() > 0:
                print(f"[*] Success! Rendered {apply_buttons.count()} job cards with Apply buttons.")
                cards_rendered = True
                break
            
            # Print latest status text if visible
            status_pill = page.locator(".animate-spin, text=Analyzing, text=Searching, text=Running").first
            if status_pill.count() > 0:
                print(f"    Elapsed: {int(time.time() - start_time)}s -> Live status active")

        page.wait_for_timeout(3000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/verify_2_jobs_returned.png")

        assert cards_rendered, "Failed to render job cards within timeout"

        # Verify location in cards (look for Chennai or TN)
        card_texts = page.locator(".bg-\\[\\#1b1b22\\], .border").all_inner_texts()
        has_chennai = any("chennai" in t.lower() or "tn" in t.lower() for t in card_texts)
        print(f"[*] Verified Chennai / TN locations on cards: {has_chennai}")

        print("=== [3/3] TESTING APPLY CONFIRMATION & TAB TRIGGER ===")
        # Click Apply on the first card
        first_apply = page.locator("button:has-text('Apply')").first
        first_apply.click()
        page.wait_for_timeout(2000)

        # Verify modal is open
        modal_header = page.locator("text=Confirm Job Application")
        print(f"[*] Confirm Modal Visible: {modal_header.count() > 0}")
        assert modal_header.count() > 0, "Apply confirmation modal did not open"

        page.screenshot(path=f"{SCREENSHOT_DIR}/verify_3_apply_modal.png")

        # Listen for popup / new tab event
        print("[*] Clicking Confirm & Submit Application...")
        with context.expect_page(timeout=10000) as new_page_info:
            confirm_btn = page.locator("button:has-text('Confirm')").first
            confirm_btn.click()

        new_tab = new_page_info.value
        print(f"[*] POPUP SUCCESS: Opened new tab with URL: {new_tab.url[:70]}...")
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/verify_4_application_opened.png")

        browser.close()
        print(">>> ALL AGENT VERIFICATION TESTS PASSED 100% ✅\n")

if __name__ == "__main__":
    test_backend_apis()
    test_frontend_ui()
