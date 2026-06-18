"""
Bluesky platform integration via the AT Protocol (atproto Python SDK).

The AT Protocol API is fully free — no per-post charges, generous rate limits
(11,666 posts/day per account; 3,000 HTTP req per 5 min per IP). Posts have a
hard 300-character limit per item; longer body text is split across a reply
thread, mirroring the X platform's behavior.

Image uploads use the AT Protocol blob endpoint, which has a ~1 MB per-blob
limit. The bot's parchment images are ~3 MB, so this implementation skips the
image on Bluesky and posts text-only when the source image exceeds the limit.
A future change can add on-the-fly compression (Pillow) if image-on-Bluesky
becomes desired.
"""

from atproto import Client, models
from atproto.exceptions import AtProtocolError

from platforms.base import BasePlatform
from platforms.x_twitter import split_text_for_replies, weighted_len

# Hard limits documented by Bluesky:
# - Post text: 300 graphemes (we use weighted_len as a conservative approximation)
# - Blob upload (images): ~1 MB
BLUESKY_POST_LIMIT = 300
BLUESKY_BLOB_LIMIT = 1_000_000


class BlueskyPlatform(BasePlatform):
    """Post to Bluesky via the AT Protocol. Free API, threads long body text."""

    def __init__(self, handle: str, app_password: str):
        self._handle = handle
        self._app_password = app_password
        self._client: Client | None = None

    @property
    def name(self) -> str:
        return "Bluesky"

    @property
    def max_length(self) -> int:
        return BLUESKY_POST_LIMIT

    def validate_length(self, text: str) -> bool:
        # Bluesky's post() splits long content across a reply thread, so the
        # bot.py pre-flight gate (`platform.validate_length(fallback_tweet)`)
        # should always pass for this platform. Returning False would cause
        # bot.py to skip Bluesky AND mark the whole run as all_success=False,
        # blocking state advancement on every entry > 300 chars (i.e. nearly
        # all of them). The 300-char limit still applies per individual post,
        # enforced inside post() by the per-chunk splitter.
        return True

    def authenticate(self) -> None:
        self._client = Client()
        self._client.login(self._handle, self._app_password)
        print(f"✅ Authenticated as @{self._handle} on Bluesky")

    def _upload_image_embed(self, image_path: str, alt: str):
        """
        Upload image as a blob and return an embed object.

        Returns None (caller posts text-only) when the image exceeds Bluesky's
        blob size limit, or if the upload itself fails.
        """
        try:
            with open(image_path, "rb") as f:
                img_data = f.read()
        except OSError as e:
            print(f"⚠️  Bluesky image read failed: {e}")
            return None

        if len(img_data) > BLUESKY_BLOB_LIMIT:
            print(
                f"⚠️  Bluesky image too large ({len(img_data)} > {BLUESKY_BLOB_LIMIT} bytes); "
                "posting text-only on Bluesky"
            )
            return None

        try:
            blob = self._client.upload_blob(img_data).blob
        except AtProtocolError as e:
            print(f"⚠️  Bluesky image upload failed: {e}")
            return None

        print(f"✅ Bluesky image uploaded ({len(img_data)} bytes)")
        alt_text = (alt or "Constitution image").strip()[:300]
        return models.AppBskyEmbedImages.Main(
            images=[
                models.AppBskyEmbedImages.Image(image=blob, alt=alt_text),
            ],
        )

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
        Post to Bluesky with optional image and reply thread.

        `reply_char_limit` is clamped to Bluesky's 300-char hard limit. When an
        image is provided, the first post is `image_text` (or `text` as fallback)
        and `body_text` becomes the reply thread. When no image is provided
        (or upload skipped/failed), the first post is `text` and the same
        threading applies.
        """
        if self._client is None:
            raise RuntimeError("Call authenticate() before posting.")

        limit = min(reply_char_limit, BLUESKY_POST_LIMIT)

        try:
            embed = None
            if image_path:
                alt_seed = (image_text or text).split("\n")[0]
                embed = self._upload_image_embed(image_path, alt_seed)

            first_text = image_text if (image_path and embed) else text
            if weighted_len(first_text) > limit:
                first_text = first_text[: limit - 1].rstrip() + "…"

            first_response = self._client.send_post(text=first_text, embed=embed)
            root_ref = models.create_strong_ref(first_response)
            post_id = first_response.uri.rsplit("/", 1)[-1]
            url = f"https://bsky.app/profile/{self._handle}/post/{post_id}"
            print(f"✅ Posted to Bluesky: {url}")

            thread_count = 1

            if body_text:
                chunks = split_text_for_replies(body_text, max_len=limit)
                parent_ref = root_ref
                print(f"🧵 Posting Bluesky reply thread ({len(chunks)} replies)...")
                for chunk in chunks:
                    response = self._client.send_post(
                        text=chunk,
                        reply_to=models.AppBskyFeedPost.ReplyRef(
                            parent=parent_ref,
                            root=root_ref,
                        ),
                    )
                    parent_ref = models.create_strong_ref(response)
                thread_count += len(chunks)
                print(f"✅ Bluesky thread complete ({thread_count} total posts)")

            return {
                "success": True,
                "url": url,
                "tweet_id": first_response.uri,
                "thread_length": thread_count,
                "error": None,
            }

        except AtProtocolError as e:
            detail = f"{type(e).__name__}: {e}"
            print(f"❌ Bluesky post failed: {detail}")
            return {
                "success": False,
                "url": None,
                "tweet_id": None,
                "thread_length": 0,
                "error": detail,
            }
