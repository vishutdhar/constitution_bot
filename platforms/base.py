"""
Base class for social media platforms.
To add a new platform, create a new file in platforms/ that inherits from this class.
"""

from abc import ABC, abstractmethod


class BasePlatform(ABC):
    """Abstract base class for social media platform integrations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable platform name."""
        pass

    @property
    @abstractmethod
    def max_length(self) -> int:
        """Maximum character count for a single post."""
        pass

    @abstractmethod
    def authenticate(self) -> None:
        """Set up authentication with the platform API."""
        pass

    @abstractmethod
    def post(self, text: str) -> dict:
        """
        Publish a post to the platform.

        Args:
            text: The text content to post.

        Returns:
            dict with at least {"success": bool, "url": str | None, "error": str | None}
        """
        pass

    def validate_length(self, text: str) -> bool:
        """Check if text fits within the platform's character limit."""
        return len(text) <= self.max_length
