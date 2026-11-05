import os
import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from backend.app.browser.session_store import SessionStore
from backend.app.browser.human_actions import HumanActions
from backend.app.config import settings

def setup_display_env():
    """Ensures X11 / Xwayland DISPLAY and XAUTHORITY are configured for headed browser launches."""
    if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
        os.environ["DISPLAY"] = ":0"
    if "XAUTHORITY" not in os.environ or not os.path.exists(os.environ.get("XAUTHORITY", "")):
        try:
            uid = os.getuid()
            run_user_dir = f"/run/user/{uid}"
            if os.path.exists(run_user_dir):
                for fname in os.listdir(run_user_dir):
                    if fname.startswith(".mutter-Xwaylandauth") or "xauth" in fname.lower():
                        cand = os.path.join(run_user_dir, fname)
                        if os.path.isfile(cand) and "ice" not in fname.lower():
                            os.environ["XAUTHORITY"] = cand
                            break
            if "XAUTHORITY" not in os.environ:
                home_auth = os.path.expanduser("~/.Xauthority")
                if os.path.exists(home_auth):
                    os.environ["XAUTHORITY"] = home_auth
        except Exception:
            pass

setup_display_env()

PLATFORM_CONFIGS = {
    "linkedin": {
        "name": "LinkedIn",
        "login_url": "https://www.linkedin.com/login",
        "user_selector": "input[type='email']:visible, input[name='session_key']:visible, input#username:visible, input[autocomplete='username']:visible",
        "pass_selector": "input[type='password']:visible, input[name='session_password']:visible, input#password:visible, input[autocomplete='current-password']:visible",
        "submit_selector": "button:has-text('Sign in'):not(:has-text('Apple')):not(:has-text('Google')):visible, button[type='submit']:visible, button[data-litms-control-urn='login-submit']:visible",
        "domain_keyword": "linkedin.com",
        "success_urls": ["linkedin.com/feed", "linkedin.com/in", "linkedin.com/mynetwork", "linkedin.com/jobs", "linkedin.com/check/"],
        "success_selectors": ["nav.global-nav", "img.global-nav__me-photo", ".feed-identity-module", "#global-nav", "a[href*='/in/']"],
        "success_cookies": ["li_at"]
    },
    "indeed": {
        "name": "Indeed",
        "login_url": "https://secure.indeed.com/auth",
        "user_selector": "input[type='email']:visible, input[name='__email']:visible, input[name='email']:visible",
        "pass_selector": "input[type='password']:visible, input[name='password']:visible",
        "submit_selector": "button[type='submit']:visible, button:has-text('Sign in'):visible, button:has-text('Continue'):visible",
        "domain_keyword": "indeed.com",
        "success_urls": ["indeed.com/?", "indeed.com/jobs", "indeed.com/account"],
        "success_selectors": ["#account-menu", "button[data-gnav-element-name='Account']", ".gnav-AccountMenu"],
        "success_cookies": ["CTK"]
    },
    "naukri": {
        "name": "Naukri",
        "login_url": "https://www.naukri.com/nlogin/login",
        "user_selector": "input#usernameField, input[placeholder*='Email ID / Username'], input[placeholder*='Email']",
        "pass_selector": "input#passwordField, input[type='password']",
        "submit_selector": "button[type='submit'], .loginButton, button:has-text('Login')",
        "domain_keyword": "naukri.com",
        "success_urls": ["naukri.com/mnjuser", "naukri.com/my-naukri", "naukri.com/HomePage"],
        "success_selectors": [".user-profile", "a[title='View profile']", ".nI-gnav-portal", ".logged-in"],
        "success_cookies": ["nauk_at", "is_login", "nauk_sid", "nauk_rt"]
    }
}

class AuthService:
    """Manages multi-platform authentication (LinkedIn, Indeed, Naukri)."""

    _lock = asyncio.Lock()

    @classmethod
    def get_status(cls, platform: str) -> Dict[str, Any]:
        plat = platform.lower().strip()
        cookies = SessionStore.load_session(plat)
        connected = bool(cookies and len(cookies) > 0)
        path = SessionStore.get_session_file_path(plat)
        return {
            "platform": plat,
            "connected": connected,
            "cookie_count": len(cookies) if cookies else 0,
            "session_file": os.path.basename(path) if connected else None
        }

    @classmethod
    async def login_with_credentials(
        cls,
        platform: str,
        username: str,
        password: str,
        headless: bool = True
    ) -> Dict[str, Any]:
        plat = platform.lower().strip()
        cfg = PLATFORM_CONFIGS.get(plat)
        if not cfg:
            return {"success": False, "message": f"Unsupported platform: {platform}"}

        if cls._lock.locked():
            return {"success": False, "message": "Another authentication is currently in progress."}

        setup_display_env()

        async with cls._lock:
            browser = None
            try:
                async with async_playwright() as p:
                    args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--no-first-run",
                        "--no-zygote"
                    ]
                    effective_headless = headless
                    if plat == "naukri":
                        effective_headless = False
                        args.extend([
                            "--window-position=-3000,-3000",
                            "--window-size=1440,900"
                        ])

                    browser = await p.chromium.launch(headless=effective_headless, args=args)
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1440, "height": 900}
                    )
                    await Stealth().apply_stealth_async(context)
                    page = await context.new_page()
                    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

                    await page.goto(cfg["login_url"], timeout=30000, wait_until="domcontentloaded")
                    await HumanActions.sleep(1200, 2000)

                    # Check if page was blocked by anti-bot WAF
                    page_title = (await page.title() or "").lower()
                    if "access denied" in page_title:
                        await browser.close()
                        return {
                            "success": False,
                            "requires_interactive": True,
                            "message": f"⚠️ {cfg['name']} security checkpoint (Access Denied) blocked automated login. Please click 'Open Browser Window' below to log in directly on your desktop display."
                        }

                    username_filled = False
                    password_filled = False

                    # 1. Fill Username
                    u_loc = page.locator(cfg["user_selector"]).first
                    try:
                        await u_loc.wait_for(state="visible", timeout=7000)
                        await u_loc.click()
                        await HumanActions.sleep(200, 400)
                        await HumanActions.human_type(u_loc, username)
                        await HumanActions.sleep(400, 800)
                        username_filled = True
                    except Exception as e:
                        print(f"[AuthService] Could not locate visible username field on {plat}: {e}")

                    # Special handling for Indeed multi-step login (email first, then continue)
                    if plat == "indeed":
                        cont_btn = page.locator("button[type='submit']:has-text('Continue'), button:has-text('Continue')").first
                        if await cont_btn.count() > 0:
                            await cont_btn.click()
                            await HumanActions.sleep(1500, 2200)

                    # 2. Fill Password
                    p_loc = page.locator(cfg["pass_selector"]).first
                    try:
                        await p_loc.wait_for(state="visible", timeout=7000)
                        await p_loc.click()
                        await HumanActions.sleep(200, 400)
                        await HumanActions.human_type(p_loc, password)
                        await HumanActions.sleep(400, 800)
                        password_filled = True
                    except Exception as e:
                        print(f"[AuthService] Could not locate visible password field on {plat}: {e}")

                    if not username_filled or not password_filled:
                        await browser.close()
                        return {
                            "success": False,
                            "requires_interactive": True,
                            "message": f"⚠️ Could not locate login fields on {cfg['name']}. Please click 'Open Browser Window' below to log in directly on your desktop display."
                        }

                    # 3. Submit
                    sub_btn = page.locator(cfg["submit_selector"]).first
                    if await sub_btn.count() > 0 and await sub_btn.is_visible():
                        try:
                            await sub_btn.click()
                        except Exception:
                            if password_filled:
                                await p_loc.press("Enter")
                    elif password_filled:
                        await p_loc.press("Enter")

                    # 4. Monitor for login redirect, 2FA challenge, or error alert
                    max_seconds = 20
                    logged_in = False
                    challenge_detected = False
                    detected_error = None

                    for _ in range(max_seconds):
                        await asyncio.sleep(1)
                        curr_url = page.url.lower()

                        # Check for success URLs
                        if any(s_url in curr_url for s_url in cfg["success_urls"]):
                            logged_in = True
                            break

                        # Check cookies directly for platform auth token
                        try:
                            current_cookies = await context.cookies()
                            cookie_names = {c.get("name") for c in current_cookies}
                            success_cookies = cfg.get("success_cookies", [])
                            if success_cookies and any(ck in cookie_names for ck in success_cookies):
                                logged_in = True
                                break
                        except Exception:
                            pass

                        # Check for success DOM elements
                        for sel in cfg["success_selectors"]:
                            try:
                                loc = page.locator(sel).first
                                if await loc.count() > 0 and await loc.is_visible():
                                    logged_in = True
                                    break
                            except Exception:
                                pass
                        if logged_in:
                            break

                        # Check for 2FA / CAPTCHA / checkpoint challenges in URL
                        if any(c in curr_url for c in ["checkpoint", "challenge", "verification", "captcha", "security", "identity"]):
                            challenge_detected = True
                            break

                        # DOM check for verification code / pin inputs
                        pin_selectors = [
                            "input[name='pin']",
                            "#input__email_verification_pin",
                            "#email-pin-input",
                            "input[type='tel']",
                            "input[id*='pin']",
                            "input[id*='otp']"
                        ]
                        for ps in pin_selectors:
                            try:
                                ploc = page.locator(ps).first
                                if await ploc.count() > 0 and await ploc.is_visible():
                                    challenge_detected = True
                                    break
                            except Exception:
                                pass
                        if challenge_detected:
                            break

                        # Check visible text for error alerts or challenges
                        try:
                            page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                            lower_text = page_text.lower()
                            if "wrong email or password" in lower_text or "that's not the right password" in lower_text:
                                detected_error = "Invalid email or password. Please verify your credentials."
                                break
                            if "couldn't find a linkedin account" in lower_text or "please enter a valid email" in lower_text:
                                detected_error = "Couldn't find an account with this email address."
                                break
                            if "an unexpected error has occurred" in lower_text or "quick security check" in lower_text:
                                challenge_detected = True
                                break
                            if "verification code" in lower_text or "we've sent a code" in lower_text or "enter the 6-digit code" in lower_text:
                                challenge_detected = True
                                break
                        except Exception:
                            pass

                    # Save debug screenshot on non-success for auditability
                    os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
                    debug_screenshot = os.path.join(settings.SCREENSHOTS_DIR, f"auth_{plat}_result.png")
                    try:
                        await page.screenshot(path=debug_screenshot)
                    except Exception:
                        pass

                    if detected_error:
                        await browser.close()
                        return {
                            "success": False,
                            "message": f"❌ {detected_error}"
                        }

                    if challenge_detected and not logged_in:
                        await browser.close()
                        return {
                            "success": False,
                            "requires_interactive": True,
                            "message": f"⚠️ {cfg['name']} sent a verification code to your email or requires a security check. Please click 'Open Browser Window' below to complete login on your desktop."
                        }

                    if not logged_in:
                        await browser.close()
                        return {
                            "success": False,
                            "requires_interactive": True,
                            "message": f"⚠️ {cfg['name']} anti-bot protection or verification required. Click 'Open Browser Window' below to log in directly on your desktop display."
                        }

                    # Extract and save cookies
                    cookies = await context.cookies()
                    clean_cookies = [
                        c for c in cookies
                        if cfg["domain_keyword"] in c.get("domain", "")
                    ]
                    if not clean_cookies:
                        clean_cookies = cookies

                    SessionStore.save_session(plat, clean_cookies)
                    await browser.close()

                    return {
                        "success": True,
                        "platform": plat,
                        "cookie_count": len(clean_cookies),
                        "message": f"✓ {cfg['name']} connected successfully! Session saved."
                    }

            except Exception as e:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                return {"success": False, "message": f"Authentication error: {str(e)}"}

    @classmethod
    async def launch_interactive_login(
        cls,
        platform: str,
        timeout_seconds: int = 180,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Opens a visible browser on DISPLAY=:0 allowing the user to log in manually,
        solve any 2FA/CAPTCHA, and automatically captures cookies once complete.
        """
        plat = platform.lower().strip()
        cfg = PLATFORM_CONFIGS.get(plat)
        if not cfg:
            return {"success": False, "message": f"Unsupported platform: {platform}"}

        if cls._lock.locked():
            return {"success": False, "message": "An authentication session is already running."}

        setup_display_env()

        async with cls._lock:
            browser = None
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=False,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--window-size=1440,900"
                        ]
                    )
                    context = await browser.new_context(
                        viewport={"width": 1440, "height": 900},
                        user_agent=(
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        )
                    )
                    await Stealth().apply_stealth_async(context)
                    page = await context.new_page()

                    await page.goto(cfg["login_url"], timeout=30000)

                    # Pre-fill username if available
                    if username and username.strip():
                        try:
                            u_loc = page.locator(cfg["user_selector"]).first
                            if await u_loc.count() > 0 and await u_loc.is_visible():
                                await u_loc.fill(username.strip())
                        except Exception:
                            pass

                    # Poll for user login completion
                    logged_in = False
                    for _ in range(timeout_seconds):
                        await asyncio.sleep(1.5)
                        try:
                            curr_url = page.url.lower()
                            # Check URL redirection away from login
                            if any(s_url in curr_url for s_url in cfg["success_urls"]):
                                logged_in = True
                                break

                            # Check cookies directly for platform auth token
                            current_cookies = await context.cookies()
                            cookie_names = {c.get("name") for c in current_cookies}
                            success_cookies = cfg.get("success_cookies", [])
                            if success_cookies and any(ck in cookie_names for ck in success_cookies):
                                logged_in = True
                                break

                            for sel in cfg["success_selectors"]:
                                try:
                                    loc = page.locator(sel).first
                                    if await loc.count() > 0 and await loc.is_visible():
                                        logged_in = True
                                        break
                                except Exception:
                                    pass
                            if logged_in:
                                break
                        except Exception:
                            # Browser was closed by user
                            break

                    if not logged_in:
                        try:
                            await browser.close()
                        except Exception:
                            pass
                        return {
                            "success": False,
                            "message": f"Interactive login for {cfg['name']} was cancelled or timed out."
                        }

                    # Capture and persist cookies
                    await asyncio.sleep(1.5)
                    cookies = await context.cookies()
                    clean_cookies = [
                        c for c in cookies
                        if cfg["domain_keyword"] in c.get("domain", "")
                    ]
                    if not clean_cookies:
                        clean_cookies = cookies

                    SessionStore.save_session(plat, clean_cookies)
                    try:
                        await browser.close()
                    except Exception:
                        pass

                    return {
                        "success": True,
                        "platform": plat,
                        "cookie_count": len(clean_cookies),
                        "message": f"✓ {cfg['name']} session successfully captured and connected!"
                    }

            except Exception as e:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                return {"success": False, "message": f"Interactive browser error: {str(e)}"}

    @classmethod
    def paste_cookies(cls, platform: str, cookies: List[Dict]) -> Dict[str, Any]:
        plat = platform.lower().strip()
        cfg = PLATFORM_CONFIGS.get(plat)
        if not cfg:
            return {"success": False, "message": f"Unsupported platform: {platform}"}

        if not cookies or not isinstance(cookies, list):
            return {"success": False, "message": "Invalid cookies: JSON array of cookies expected."}

        saved = SessionStore.save_session(plat, cookies)
        if saved:
            return {
                "success": True,
                "platform": plat,
                "cookie_count": len(cookies),
                "message": f"✓ Saved {len(cookies)} cookies for {cfg['name']} successfully."
            }
        return {"success": False, "message": f"Failed to save cookies for {platform}."}

    @classmethod
    def disconnect(cls, platform: str) -> Dict[str, Any]:
        plat = platform.lower().strip()
        deleted = SessionStore.delete_session(plat)
        return {
            "success": True,
            "platform": plat,
            "connected": False,
            "message": f"Disconnected {platform.capitalize()} session."
        }
