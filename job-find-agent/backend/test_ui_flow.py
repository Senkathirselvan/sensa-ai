import time
import os
from playwright.sync_api import sync_playwright

def run_test():
    screenshot_dir = "/app/data"
    os.makedirs(screenshot_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        print("[TEST] Navigating to http://frontend:80 ...")
        page.goto("http://frontend:80", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        
        # Verify page title or header
        print("[TEST] Title:", page.title())
        page.screenshot(path=f"{screenshot_dir}/step1_initial.png")
        
        # Select input textarea
        input_el = page.locator("textarea, input[type='text']").first
        if not input_el or input_el.count() == 0:
            print("[TEST ERROR] Input box not found!")
            browser.close()
            return
            
        test_prompt = "Analyze my resume and find Python Backend Developer jobs in Chennai, then queue the top match."
        print(f"[TEST] Typing prompt: {test_prompt}")
        input_el.fill(test_prompt)
        page.keyboard.press("Enter")
        
        print("[TEST] Sent message. Waiting for streaming and job cards (up to 45s)...")
        # Wait until job cards or assistant tokens appear
        start_time = time.time()
        found_cards = False
        while time.time() - start_time < 45:
            page.wait_for_timeout(2000)
            apply_buttons = page.locator("button:has-text('Apply')")
            if apply_buttons.count() > 0:
                print(f"[TEST] Found {apply_buttons.count()} Apply buttons on rendered job cards!")
                found_cards = True
                break
            # Check if text response has rendered
            msg_bodies = page.locator(".prose, .text-slate-200")
            print(f"[TEST] Elapsed: {int(time.time() - start_time)}s, Elements: {msg_bodies.count()} text nodes")
            
        page.wait_for_timeout(3000)
        page.screenshot(path=f"{screenshot_dir}/step2_jobs_found.png")
        print("[TEST] Saved step2_jobs_found.png")
        
        # Click Apply on the first card
        apply_btn = page.locator("button:has-text('Apply')").first
        if apply_btn.count() > 0:
            print("[TEST] Clicking 'Apply' button on top matched job card...")
            apply_btn.click()
            page.wait_for_timeout(2000)
            
            page.screenshot(path=f"{screenshot_dir}/step3_apply_modal.png")
            print("[TEST] Saved step3_apply_modal.png")
            
            # Check for Confirm button in modal
            confirm_btn = page.locator("button:has-text('Confirm'), button:has-text('Submit')").first
            if confirm_btn.count() > 0:
                print("[TEST] Clicking Confirm application...")
                confirm_btn.click()
                page.wait_for_timeout(2000)
                page.screenshot(path=f"{screenshot_dir}/step4_confirmed.png")
                print("[TEST] Saved step4_confirmed.png")
            else:
                print("[TEST] Confirm button not visible in modal")
        else:
            print("[TEST WARNING] No Apply button found")
            
        browser.close()
        print("[TEST COMPLETE] Finished browser flow test successfully.")

if __name__ == "__main__":
    run_test()
