"""
X (Twitter) platform integration using Tweepy and the X API v2.
Automatically threads posts that exceed 280 characters.
Supports image uploads via the v1.1 API.
"""

import time

import tweepy
from platforms.base import BasePlatform


def weighted_len(text: str) -> int:
    """Character length using X's weighted counting rules.
    Characters above U+FFFF (most emoji) count as 2; everything else counts as 1."""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in text)


def _format_error_detail(e: Exception) -> str:
    """
    Build a diagnostic string from a tweepy exception.

    str(e) alone often returns only "403 Forbidden" when the response body
    is empty or non-JSON (edge-level blocks, quota gates). This surfaces the
    HTTP status, response body snippet, and any X API error codes/messages
    so the real cause is visible in logs.
    """
    parts = [f"{type(e).__name__}: {e}"]

    response = getattr(e, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status is not None:
            parts.append(f"status={status}")
        body = getattr(response, "text", "") or ""
        if body:
            snippet = body[:500] + ("...[truncated]" if len(body) > 500 else "")
            parts.append(f"body={snippet!r}")

    api_codes = getattr(e, "api_codes", None)
    if api_codes:
        parts.append(f"api_codes={api_codes}")

    api_messages = getattr(e, "api_messages", None)
    if api_messages:
        parts.append(f"api_messages={api_messages}")

    return " | ".join(parts)


def _split_on_words(text: str, max_len: int) -> list[str]:
    """Split text on word boundaries to fit within max_len."""
    chunks = []
    words = text.split()
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if weighted_len(test) <= max_len:
            current = test
        else:
            if current:
                chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def _split_on_clauses(text: str, max_len: int) -> list[str]:
    """Split text on clause boundaries (commas, semicolons) to fit within max_len.
    Falls back to word boundaries if a single clause is still too long."""
    import re
    # Split after commas and semicolons, keeping the delimiter with the preceding clause
    clauses = re.split(r"(?<=[,;]) ", text)

    chunks = []
    current = ""
    for clause in clauses:
        if weighted_len(clause) > max_len:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_on_words(clause, max_len))
            continue

        test = f"{current} {clause}".strip() if current else clause
        if weighted_len(test) <= max_len:
            current = test
        else:
            if current:
                chunks.append(current)
            current = clause
    if current:
        chunks.append(current)
    return chunks


def split_into_thread(text: str, max_len: int = 280) -> list[str]:
    """
    Split a formatted post into tweet-sized chunks for threading.
    Keeps the header in tweet 1, splits body on sentence boundaries
    (with word-boundary fallback), puts hashtags on the last tweet.
    """
    if weighted_len(text) <= max_len:
        return [text]

    # Separate hashtags (last line where all words start with #)
    lines = text.strip().split("\n")
    hashtag_line = ""
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and all(w.startswith("#") for w in stripped.split()):
            hashtag_line = stripped
        else:
            content_lines.append(line)

    content = "\n".join(content_lines).strip()

    # Split into header and body
    parts = content.split("\n\n", 1)
    header = parts[0]
    body = parts[1] if len(parts) > 1 else ""

    # Thread numbering overhead: " [X/X]"
    overhead = 7

    # Split body into individual clause-level fragments for flexible packing.
    # This lets tweet 1 (which has less space due to the header) still get
    # body content instead of being wasted on just the header.
    import re
    usable = max_len - overhead
    raw_sentences = re.split(r"(?<=\.) (?=[A-Z])|(?<=;) ", body)

    sentences = []
    for s in raw_sentences:
        clause_parts = re.split(r"(?<=[,;]) ", s)
        for cp in clause_parts:
            if weighted_len(cp) <= usable:
                sentences.append(cp)
            else:
                sentences.extend(_split_on_words(cp, usable))

    # Build tweet 1: header + as much body as fits
    tweets = []
    space = usable - weighted_len(header) - 2  # 2 for "\n\n"
    tweet1_body = ""
    start_idx = 0

    for i, s in enumerate(sentences):
        candidate = f"{tweet1_body} {s}".strip() if tweet1_body else s
        if weighted_len(candidate) <= space:
            tweet1_body = candidate
            start_idx = i + 1
        else:
            break

    tweets.append(f"{header}\n\n{tweet1_body}".strip() if tweet1_body else header)

    # Build remaining tweets
    current = ""
    for s in sentences[start_idx:]:
        test = f"{current} {s}".strip() if current else s
        if weighted_len(test) <= usable:
            current = test
        else:
            if current:
                tweets.append(current)
            current = s
    # Don't forget the last chunk
    remaining = current

    # Attach hashtags to the last chunk or as a separate tweet
    if remaining and hashtag_line:
        if weighted_len(remaining) + 2 + weighted_len(hashtag_line) + overhead <= max_len:
            tweets.append(f"{remaining}\n\n{hashtag_line}")
        else:
            tweets.append(remaining)
            tweets.append(hashtag_line)
    elif remaining:
        tweets.append(remaining)
    elif hashtag_line:
        if weighted_len(tweets[-1]) + 2 + weighted_len(hashtag_line) + overhead <= max_len:
            tweets[-1] += f"\n\n{hashtag_line}"
        else:
            tweets.append(hashtag_line)

    # Add thread numbering
    total = len(tweets)
    if total > 1:
        tweets = [f"{t} [{i+1}/{total}]" for i, t in enumerate(tweets)]

    return tweets


def split_text_for_replies(text: str, max_len: int = 280) -> list[str]:
    """
    Split plain body text into tweet-sized reply chunks.

    Simpler than split_into_thread — no header/hashtag handling.
    Used for the reply thread below an image tweet.
    No numbering — Twitter shows reply order visually.
    """
    import re

    if weighted_len(text) <= max_len:
        return [text]

    # Split on sentence boundaries first, then clause boundaries
    raw_sentences = re.split(r"(?<=\.) (?=[A-Z])|(?<=;) ", text)

    fragments = []
    for s in raw_sentences:
        clause_parts = re.split(r"(?<=[,;]) ", s)
        for cp in clause_parts:
            if weighted_len(cp) <= max_len:
                fragments.append(cp)
            else:
                fragments.extend(_split_on_words(cp, max_len))

    # Pack fragments into tweet-sized chunks
    chunks = []
    current = ""
    for frag in fragments:
        test = f"{current} {frag}".strip() if current else frag
        if weighted_len(test) <= max_len:
            current = test
        else:
            if current:
                chunks.append(current)
            current = frag
    if current:
        chunks.append(current)

    return chunks


class XTwitterPlatform(BasePlatform):
    """Post to X (formerly Twitter) using API v2. Auto-threads long posts."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
        handle: str = "USC1787",
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._access_token = access_token
        self._access_token_secret = access_token_secret
        self._handle = handle
        self._client: tweepy.Client | None = None
        self._api_v1: tweepy.API | None = None
        self._username: str | None = None

    @property
    def name(self) -> str:
        return "X (Twitter)"

    @property
    def max_length(self) -> int:
        # Threading handles overflow, so set generous limit
        return 1400

    def validate_length(self, text: str) -> bool:
        """X counts emoji as 2 characters; use weighted length."""
        return weighted_len(text) <= self.max_length

    def authenticate(self) -> None:
        """Create authenticated Tweepy v2 client and v1.1 API for media uploads."""
        self._client = tweepy.Client(
            consumer_key=self._api_key,
            consumer_secret=self._api_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
        )

        # v1.1 API needed for media_upload() — same credentials, different API surface
        auth = tweepy.OAuth1UserHandler(
            self._api_key,
            self._api_secret,
            self._access_token,
            self._access_token_secret,
        )
        self._api_v1 = tweepy.API(auth)

        self._username = self._handle
        print(f"✅ Authenticated as @{self._username}")

    def _upload_image(self, image_path: str) -> str | None:
        """
        Upload an image via the v1.1 API.

        Returns:
            media_id string on success, None on failure.
        """
        if self._api_v1 is None:
            print("⚠️  v1.1 API not initialized — cannot upload image")
            return None

        try:
            media = self._api_v1.media_upload(filename=image_path)
            media_id = str(media.media_id)
            print(f"✅ Image uploaded (media_id: {media_id})")
            return media_id
        except tweepy.TweepyException as e:
            print(f"⚠️  Image upload failed: {_format_error_detail(e)}")
            return None

    def _create_tweet_with_retry(self, retries: int = 2, **kwargs) -> tweepy.Response:
        """
        Wrapper around create_tweet with per-tweet retry.
        Retries on transient failures so a partial thread doesn't trigger
        a full script-level re-run (which would duplicate already-posted tweets).
        """
        last_exc = None
        for attempt in range(1 + retries):
            try:
                return self._client.create_tweet(**kwargs)
            except tweepy.TweepyException as e:
                last_exc = e
                if attempt < retries:
                    wait = 5 * (attempt + 1)
                    print(f"⚠️  Tweet failed (attempt {attempt + 1}), retrying in {wait}s: {_format_error_detail(e)}")
                    time.sleep(wait)
        raise last_exc

    def _post_text_only(self, text: str, max_len: int = 280) -> dict:
        """Post using text-only flow (existing behavior). Used as fallback."""
        tweets = split_into_thread(text, max_len=max_len)

        if len(tweets) == 1:
            response = self._create_tweet_with_retry(text=tweets[0])
            tweet_id = response.data["id"]
            url = f"https://x.com/{self._username}/status/{tweet_id}"
            print(f"✅ Posted to X: {url}")
        else:
            print(f"🧵 Posting thread ({len(tweets)} tweets)...")
            first_response = self._create_tweet_with_retry(text=tweets[0])
            first_id = first_response.data["id"]
            previous_id = first_id

            for tweet_text in tweets[1:]:
                response = self._create_tweet_with_retry(
                    text=tweet_text,
                    in_reply_to_tweet_id=previous_id,
                )
                previous_id = response.data["id"]

            tweet_id = first_id
            url = f"https://x.com/{self._username}/status/{first_id}"
            print(f"✅ Posted thread to X: {url}")

        return {
            "success": True,
            "url": url,
            "tweet_id": tweet_id,
            "thread_length": len(tweets),
            "error": None,
        }

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
        Post a tweet, optionally with an image and reply thread.

        When image_path is provided:
          1. Upload image via v1.1 API
          2. Post image tweet (image_text + image)
          3. Post body_text as reply thread below the image tweet
          If image upload fails, falls back to text-only posting.

        When image_path is not provided:
          Posts text-only using existing split_into_thread() logic.

        Returns:
            dict with success, url, tweet_id, thread_length, error keys.
        """
        if self._client is None:
            raise RuntimeError("Call authenticate() before posting.")

        try:
            # --- Text-only mode (no image provided) ---
            if not image_path:
                return self._post_text_only(text, max_len=reply_char_limit)

            # --- Image mode ---
            media_id = self._upload_image(image_path)

            if media_id is None:
                # Fallback: image upload failed, post text-only
                print("⚠️  Falling back to text-only post")
                return self._post_text_only(text, max_len=reply_char_limit)

            # Post image tweet
            caption = image_text or text
            response = self._create_tweet_with_retry(
                text=caption,
                media_ids=[media_id],
            )
            first_id = response.data["id"]
            url = f"https://x.com/{self._username}/status/{first_id}"
            print(f"✅ Posted image tweet to X: {url}")

            thread_count = 1

            # Post body text as reply thread
            if body_text:
                reply_chunks = split_text_for_replies(body_text, max_len=reply_char_limit)
                previous_id = first_id

                print(f"🧵 Posting reply thread ({len(reply_chunks)} replies)...")
                for chunk in reply_chunks:
                    response = self._create_tweet_with_retry(
                        text=chunk,
                        in_reply_to_tweet_id=previous_id,
                    )
                    previous_id = response.data["id"]

                thread_count += len(reply_chunks)
                print(f"✅ Reply thread complete ({thread_count} total tweets)")

            return {
                "success": True,
                "url": url,
                "tweet_id": first_id,
                "thread_length": thread_count,
                "error": None,
            }

        except tweepy.TweepyException as e:
            detail = _format_error_detail(e)
            print(f"❌ X post failed: {detail}")
            return {
                "success": False,
                "url": None,
                "tweet_id": None,
                "thread_length": 0,
                "error": detail,
            }
