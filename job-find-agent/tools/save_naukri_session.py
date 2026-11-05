#!/usr/bin/env python3
"""
Naukri Session Cookie Generator & Verifier
==========================================
Generates and manages `naukri_session.json` to allow Playwright scrapers
to bypass Akamai/Cloudflare bot defense and fetch live job postings.

Usage:
  1. Interactive GUI Login (recommended):
     uv run --with playwright python3 tools/save_naukri_session.py --login

  2. Verify existing session:
     uv run --with playwright python3 tools/save_naukri_session.py --verify

  3. Import from exported JSON file:
     python3 tools/save_naukri_session.py --import path/to/cookies.json
"""
import sys
import os
import json
import argparse
import time

# Ensure repo root and shared are on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(REPO_ROOT, "shared")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from session_manager import (
    get_naukri_session_path,
    save_naukri_cookies,
    load_naukri_cookies,
    sanitize_cookies_list
)


def interactive_login(output_path: str):
    """Launches Chromium to let the user log into Naukri and captures the session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Error] Playwright is required. Run with:")
        print("  uv run --with playwright python3 tools/save_naukri_session.py --login")
        return False

    print("\n" + "=" * 60)
    print("🚀 NAUKRI INTERACTIVE LOGIN SESSION CAPTURE")
    print("=" * 60)
    print("1. A Chromium browser window will open.")
    print("2. Enter your Naukri email/phone and password, and complete login.")
    print("3. Once logged in, return to this terminal and press [ENTER] to save cookies.")
    print("=" * 60 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport=None
        )
        page = context.new_page()

        print("Navigating to https://www.naukri.com/nlogin/login ...")
        page.goto("https://www.naukri.com/nlogin/login", timeout=30000)

        # Wait for user confirmation in terminal or auto-detect login redirect
        print("\n👉 Waiting for you to complete login in the browser window...")
        print("   (When done, press [ENTER] here in the terminal to save your session)")
        
        try:
            input()
        except KeyboardInterrupt:
            print("\nCancelled by user.")
            browser.close()
            return False

        # Grab all cookies from context
        cookies = context.cookies()
        naukri_cookies = [c for c in cookies if "naukri.com" in c.get("domain", "")]
        
        if not naukri_cookies:
            print("⚠️ No naukri.com cookies detected! Saving all domain cookies instead...")
            naukri_cookies = cookies

        saved_path = save_naukri_cookies(naukri_cookies, output_path)
        print(f"\n✅ SUCCESS: Captured {len(naukri_cookies)} session cookies!")
        print(f"📁 Saved to: {saved_path}")

        browser.close()
        return True


def verify_session(cookie_path: str):
    """Tests the saved session in headless mode."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Error] Playwright is required. Run with:")
        print("  uv run --with playwright python3 tools/save_naukri_session.py --verify")
        return False

    cookies = load_naukri_cookies()
    target_path = get_naukri_session_path()

    if not cookies:
        print(f"❌ No session cookies found at {target_path}!")
        print("   Run interactive login first:")
        print("   uv run --with playwright python3 tools/save_naukri_session.py --login")
        return False

    print(f"\n🔍 Verifying session with {len(cookies)} cookies from {target_path}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        test_url = "https://www.naukri.com/python-developer-jobs-in-chennai"
        print(f"Navigating to {test_url} ...")
        page.goto(test_url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)

        title = page.title()
        print(f"Page Title: {title}")

        if "access denied" in title.lower() or "blocked" in title.lower():
            print("❌ Verification Failed: Blocked by Akamai/Cloudflare. Cookies may be expired.")
            browser.close()
            return False

        cards = page.locator("article.jobTuple, div.cust-job-tuple, .srp-jobtuple-wrapper, div[class*='styles_job-tuple-container']").all()
        print(f"✅ SUCCESS: Session is LIVE! Found {len(cards)} live job cards on Naukri!")

        if cards:
            first_title = cards[0].locator("a.title").first.inner_text() if cards[0].locator("a.title").count() > 0 else "N/A"
            print(f"   Example Job: {first_title}")

        browser.close()
        return True


def import_cookies(json_file: str, output_path: str):
    """Imports cookies from an exported JSON file (e.g. from Cookie-Editor extension)."""
    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        return False

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cookies = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        print("❌ Invalid JSON format: expected a list of cookie objects.")
        return False

    saved_path = save_naukri_cookies(cookies, output_path)
    print(f"✅ Successfully imported {len(cookies)} cookies to {saved_path}!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Naukri Session Cookie Manager")
    parser.add_argument("--login", action="store_true", help="Launch interactive browser to log in and capture session")
    parser.add_argument("--verify", action="store_true", help="Verify existing saved session in headless mode")
    parser.add_argument("--import-file", type=str, help="Import cookies from a JSON file")
    parser.add_argument("--output", type=str, default=None, help="Custom output path for naukri_session.json")

    args = parser.parse_args()
    target_path = args.output or get_naukri_session_path()

    if args.login:
        interactive_login(target_path)
    elif args.verify:
        verify_session(target_path)
    elif args.import_file:
        import_cookies(args.import_file, target_path)
    else:
        # Default interactive menu
        print("\n" + "=" * 50)
        print("  💼 NAUKRI SESSION COOKIE HELPER")
        print("=" * 50)
        print("Select an option:")
        print("  [1] Interactive Login (open Chromium & log in)")
        print("  [2] Verify current session")
        print("  [3] Paste exported cookies JSON directly")
        print("  [4] Exit")
        choice = input("\nEnter choice [1-4]: ").strip()

        if choice == "1":
            interactive_login(target_path)
        elif choice == "2":
            verify_session(target_path)
        elif choice == "3":
            print("\nPaste your JSON cookie array below, then press Enter:")
            raw = input().strip()
            try:
                cookies = json.loads(raw)
                import_cookies_from_obj = save_naukri_cookies(cookies, target_path)
                print(f"✅ Saved to {import_cookies_from_obj}")
            except Exception as e:
                print(f"❌ Failed to parse JSON: {e}")
        else:
            print("Exiting.")


if __name__ == "__main__":
    main()
