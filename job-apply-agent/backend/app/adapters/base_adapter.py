from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Awaitable
from playwright.async_api import Page

class BaseAdapter(ABC):
    """Abstract interface for platform-specific job application handlers."""

    name: str = "base"

    @abstractmethod
    async def detect(self, page: Page, url: str) -> bool:
        """Determines if this adapter is applicable to the current page/URL."""
        pass

    @abstractmethod
    async def execute(
        self,
        page: Page,
        candidate_data: Dict[str, Any],
        resume_pdf_path: str,
        emit_event: Callable[[str, Any], Awaitable[None]]
    ) -> Dict[str, Any]:
        """
        Executes the application workflow.
        Returns a dictionary containing execution details, filled fields, and status.
        """
        pass

