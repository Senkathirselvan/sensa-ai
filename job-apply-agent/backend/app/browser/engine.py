import os
import time
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import Stealth
from backend.app.config import settings
from backend.app.browser.session_store import SessionStore
from backend.app.services.auth_service import setup_display_env

class BrowserEngine:
    """Core browser automation engine with Playwright and stealth anti-detection."""

    def __init__(self, headless: Optional[bool] = None):
        self.headless = headless if headless is not None else settings.BROWSER_HEADLESS
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(
        self,
        platform: Optional[str] = None,
        viewport: Dict[str, int] = {"width": 1440, "height": 900}
    ) -> Page:
        """Launches Chromium with stealth evasions and platform session cookies."""
        setup_display_env()
        self.playwright = await async_playwright().start()

        # Stealth user-agent
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        # Locate installed Google Chrome binary for modern --headless=new background execution
        chrome_candidates = [
            "/opt/google/chrome/chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium"
        ]
        executable_path = next((p for p in chrome_candidates if os.path.exists(p) and os.access(p, os.X_OK)), None)

        launch_args = [
            "--headless=new",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-zygote",
            "--window-size=1440,900"
        ]

        # Use modern new headless mode which runs 100% in the background without creating a desktop window,
        # while passing anti-bot firewalls (Akamai on Naukri/LinkedIn) via genuine Chrome binaries and stealth evasions.
        launch_kwargs: Dict[str, Any] = {
            "headless": True,
            "args": launch_args
        }
        if executable_path:
            launch_kwargs["executable_path"] = executable_path

        self.browser = await self.playwright.chromium.launch(**launch_kwargs)

        self.context = await self.browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            has_touch=False,
            is_mobile=False,
            device_scale_factor=1,
            permissions=["clipboard-read", "clipboard-write"]
        )

        # Apply stealth scripts to context
        await Stealth().apply_stealth_async(self.context)

        # Load platform session cookies if available
        if platform:
            cookies = SessionStore.load_session(platform)
            if cookies:
                try:
                    await self.context.add_cookies(cookies)
                except Exception as e:
                    print(f"[BrowserEngine] Error injecting cookies for {platform}: {e}")

        self.page = await self.context.new_page()
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)
        return self.page

    async def capture_screenshot(self, prefix: str = "apply_step", target_page: Optional[Page] = None) -> str:
        """Captures a screenshot of the current or specified target page and returns relative path."""
        p = target_page or self.page
        if not p:
            return ""
        os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
        filename = f"{prefix}_{int(time.time() * 1000)}.png"
        filepath = os.path.join(settings.SCREENSHOTS_DIR, filename)
        try:
            await p.screenshot(path=filepath, full_page=False)
            return filepath
        except Exception as e:
            print(f"[BrowserEngine] Screenshot capture error: {e}")
            return ""

    async def attach_file_to_chooser(self, file_path: str, trigger_locator) -> bool:
        """Uploads local PDF file to file-chooser or file-input reliably."""
        if not os.path.exists(file_path):
            print(f"[BrowserEngine] Resume file not found at {file_path}")
            return False

        try:
            async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                await trigger_locator.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(file_path)
            return True
        except Exception:
            # Fallback: Find input[type=file] directly
            try:
                file_input = self.page.locator('input[type="file"]').first
                if await file_input.count() > 0:
                    await file_input.set_input_files(file_path)
                    return True
            except Exception as e2:
                print(f"[BrowserEngine] Fallback file input error: {e2}")
        return False

    async def close(self):
        """Safely shuts down browser and playwright instances."""
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
