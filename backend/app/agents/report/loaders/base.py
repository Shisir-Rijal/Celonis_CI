"""Abstract base class for all report data loaders."""

from abc import ABC, abstractmethod


class BaseReportLoader(ABC):
    """Each topic implements this to fetch and shape its own data."""

    def __init__(self, companies: list[str] | None = None):
        # None means all active competitors (used by Branding)
        self.companies = companies

    @abstractmethod
    async def fetch(self) -> dict:
        """Fetch and return data as a dict passed to the prompt builder."""
        ...