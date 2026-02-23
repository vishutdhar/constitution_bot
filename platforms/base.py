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
    def post(
        self,
        text: str,
        *,
        image_path: str | None = None,
        image_text: str | None = None,
        body_text: str | None = None,
        reply_char_limit: int = 280,
    ) -> dict:
        """
        Publish a post to the platform.

        Args:
            text: Full text content (used as fallback if image upload fails).
            image_path: Optional path to an image file to attach.
            image_text: Optional caption for the image tweet (used as tweet 1).
            body_text: Optional constitutional text posted as reply thread.
            reply_char_limit: Max chars per reply tweet (280 free, 4000 Premium).

        Returns:
            dict with at least {"success": bool, "url": str | None, "error": str | None}
        """
        pass

    def validate_length(self, text: str) -> bool:
        """Check if text fits within the platform's character limit."""
        return len(text) <= self.max_length
