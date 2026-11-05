import asyncio
import random
from typing import Union
from playwright.async_api import Page, Locator

class HumanActions:
    """Simulates realistic human-like browsing patterns to avoid bot-behavior heuristics."""

    @staticmethod
    async def sleep(min_ms: int = 400, max_ms: int = 1200):
        """Randomized sleep between actions."""
        delay = random.uniform(min_ms / 1000.0, max_ms / 1000.0)
        await asyncio.sleep(delay)

    @staticmethod
    async def human_type(target: Union[Page, Locator], text: str, min_delay: int = 35, max_delay: int = 90):
        """Types string character by character with randomized typing cadence."""
        for char in text:
            if isinstance(target, Locator):
                await target.press_sequentially(char)
            else:
                await target.keyboard.press(char)
            await asyncio.sleep(random.uniform(min_delay / 1000.0, max_delay / 1000.0))

    @staticmethod
    async def smooth_scroll(page: Page, target_y: int = 600, steps: int = 5):
        """Smoothly scrolls page downward in human-like micro-steps."""
        current_y = await page.evaluate("window.scrollY")
        delta = (target_y - current_y) / steps
        for _ in range(steps):
            current_y += delta
            await page.evaluate(f"window.scrollTo(0, {current_y})")
            await asyncio.sleep(random.uniform(0.05, 0.12))

    @staticmethod
    async def human_click(target: Locator, page: Page = None):
        """Hovers slightly before clicking to emulate human cursor focus."""
        try:
            await target.scroll_into_view_if_needed(timeout=5000)
            await asyncio.sleep(random.uniform(0.15, 0.35))
            await target.click(delay=random.randint(40, 110))
        except Exception:
            # Fallback direct click if scroll into view times out
            await target.click()

