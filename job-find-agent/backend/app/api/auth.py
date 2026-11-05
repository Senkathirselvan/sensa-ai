"""
Authentication & Session Management API for Job Platforms (Naukri, LinkedIn).
Handles:
  - Checking platform connection status
  - Automatic Xvfb virtual display management inside Docker
  - Headed browser emulation to bypass Akamai bot detection
  - Credential authentication, error parsing, and cookie extraction
  - Direct JSON cookie import & deletion
"""
import os
import sys
import json
import asyncio
import subprocess
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Ensure shared is importable across container and host
for candidate in [
    "/app/shared",
    "/app",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
]:
    if os.path.exists(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

try:
    from session_manager import (
        load_naukri_cookies,
        save_naukri_cookies,
        get_naukri_session_path,
        sanitize_cookies_list
    )
except ImportError:
    from shared.session_manager import (
        load_naukri_cookies,
        save_naukri_cookies,
        get_naukri_session_path,
        sanitize_cookies_list
    )

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


class PasteCookiesRequest(BaseModel):
    cookies: List[Dict[str, Any]]


_login_lock = asyncio.Lock()


def ensure_display() -> str:
    """
    Ensures an active X display is available.
    If no host display is found, automatically spawns Xvfb on :99.
    """
    # Check if host display socket exists
    curr_display = os.environ.get("DISPLAY")
    if curr_display:
        disp_num = curr_display.replace(":", "").split(".")[0]
        if os.path.exists(f"/tmp/.X11-unix/X{disp_num}"):
            return curr_display

    # Spawn Xvfb on display :99 if not running
    if not os.path.exists("/tmp/.X11-unix/X99"):
        try:
            subprocess.Popen(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            import time
            time.sleep(1)
        except Exception as e:
            print(f"[Xvfb Start Warning] {e}")

    os.environ["DISPLAY"] = ":99"
    return ":99"


@router.get("/naukri/status")
async def get_naukri_status():
    """Checks whether a valid Naukri session cookie is stored."""
    cookies = load_naukri_cookies()
    path = get_naukri_session_path()
    connected = bool(cookies and len(cookies) > 0)
    return {
        "platform": "naukri",
        "connected": connected,
        "cookie_count": len(cookies) if cookies else 0,
        "path": path
    }


@router.post("/naukri/login")
async def start_naukri_login(payload: LoginRequest):
    """
    Authenticates with Naukri using Playwright on an Xvfb virtual display.
    Bypasses Akamai/Cloudflare bot challenges, fills credentials, and extracts session cookies.
    """
    if _login_lock.locked():
        return {
            "success": False,
            "message": "A login operation is already in progress. Please wait a moment."
        }

    async with _login_lock:
        ensure_display()

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Playwright is not installed inside the backend environment."
            )

        try:
            async with async_playwright() as p:
                disp = ensure_display()
                browser_env = dict(os.environ)
                browser_env["DISPLAY"] = disp

                browser = await p.chromium.launch(
                    headless=False,
                    env=browser_env,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--window-size=1920,1080"
                    ]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-IN"
                )
                page = await context.new_page()
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

                # Navigate to Naukri login
                await page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)

                # Check if page is blocked
                title = await page.title()
                if "access denied" in title.lower():
                    await browser.close()
                    return {
                        "success": False,
                        "message": "Naukri Akamai blocked connection. Please paste cookies directly using Cookie-Editor."
                    }

                # Auto-fill credentials if provided
                if payload.username and payload.password:
                    user_input = page.locator("#usernameField, input[placeholder*='Email']").first
                    pass_input = page.locator("#passwordField, input[type='password']").first
                    submit_btn = page.locator("button[type='submit'], .loginButton").first

                    if await user_input.count() > 0 and await pass_input.count() > 0:
                        await user_input.fill(payload.username)
                        await pass_input.fill(payload.password)
                        await page.wait_for_timeout(500)
                        if await submit_btn.count() > 0:
                            await submit_btn.click()

                # Poll for result: either navigation away from login OR error message
                max_checks = 18  # ~18-20 seconds
                logged_in = False
                detected_error = None

                for _ in range(max_checks):
                    await asyncio.sleep(1)
                    curr_url = page.url

                    # Check for successful login redirect
                    if "nlogin/login" not in curr_url and "naukri.com" in curr_url:
                        logged_in = True
                        break

                    # Check for error elements on page
                    body_text = await page.inner_text("body")
                    for line in body_text.split("\n"):
                        clean_line = line.strip()
                        if any(err_word in clean_line.lower() for err_word in [
                            "invalid details", "incorrect password", "please check the email",
                            "user does not exist", "account has been locked"
                        ]):
                            detected_error = clean_line
                            break
                        if "use otp to login" in clean_line.lower() and "invalid" in body_text.lower():
                            detected_error = "Invalid Email or Password. Please double-check your credentials."
                            break

                    if detected_error:
                        break

                if detected_error:
                    await browser.close()
                    return {
                        "success": False,
                        "detail": detected_error
                    }

                if not logged_in:
                    await browser.close()
                    return {
                        "success": False,
                        "message": "Login timed out or requires manual verification (OTP/CAPTCHA). Please check credentials or paste cookies."
                    }

                # Success: grab all session cookies
                await asyncio.sleep(2)
                all_cookies = await context.cookies()
                naukri_cookies = [c for c in all_cookies if "naukri.com" in c.get("domain", "")]
                if not naukri_cookies:
                    naukri_cookies = all_cookies

                saved_path = save_naukri_cookies(naukri_cookies)
                await browser.close()

                return {
                    "success": True,
                    "message": "Naukri account connected successfully! Session saved.",
                    "cookie_count": len(naukri_cookies),
                    "path": saved_path
                }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/naukri/paste-cookies")
async def paste_naukri_cookies(payload: PasteCookiesRequest):
    """Imports cookies pasted directly from Cookie-Editor JSON."""
    if not payload.cookies or not isinstance(payload.cookies, list):
        raise HTTPException(status_code=400, detail="Invalid cookie array")

    saved_path = save_naukri_cookies(payload.cookies)
    return {
        "success": True,
        "message": f"Saved {len(payload.cookies)} cookies successfully.",
        "path": saved_path
    }


@router.post("/naukri/disconnect")
async def disconnect_naukri():
    """Disconnects Naukri by removing stored session cookies."""
    path = get_naukri_session_path()
    if os.path.exists(path):
        os.remove(path)
    return {"success": True, "connected": False, "message": "Naukri session disconnected."}
