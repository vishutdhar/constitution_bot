"""
X (Twitter) platform integration using Tweepy and the X API v2.
Automatically threads posts that exceed 280 characters.
"""

import tweepy
from platforms.base import BasePlatform


def _split_on_words(text: str, max_len: int) -> list[str]:
    """Split text on word boundaries to fit within max_len."""
    chunks = []
    words = text.split()
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_len:
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
        if len(clause) > max_len:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_on_words(clause, max_len))
            continue

        test = f"{current} {clause}".strip() if current else clause
        if len(test) <= max_len:
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
    if len(text) <= max_len:
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
            if len(cp) <= usable:
                sentences.append(cp)
            else:
                sentences.extend(_split_on_words(cp, usable))

    # Build tweet 1: header + as much body as fits
    tweets = []
    space = usable - len(header) - 2  # 2 for "\n\n"
    tweet1_body = ""
    start_idx = 0

    for i, s in enumerate(sentences):
        candidate = f"{tweet1_body} {s}".strip() if tweet1_body else s
        if len(candidate) <= space:
            tweet1_body = candidate
            start_idx = i + 1
        else:
            break

    tweets.append(f"{header}\n\n{tweet1_body}".strip() if tweet1_body else header)

    # Build remaining tweets
    current = ""
    for s in sentences[start_idx:]:
        test = f"{current} {s}".strip() if current else s
        if len(test) <= usable:
            current = test
        else:
            if current:
                tweets.append(current)
            current = s
    # Don't forget the last chunk
    remaining = current

    # Attach hashtags to the last chunk or as a separate tweet
    if remaining and hashtag_line:
        if len(remaining) + 2 + len(hashtag_line) + overhead <= max_len:
            tweets.append(f"{remaining}\n\n{hashtag_line}")
        else:
            tweets.append(remaining)
            tweets.append(hashtag_line)
    elif remaining:
        tweets.append(remaining)
    elif hashtag_line:
        if len(tweets[-1]) + 2 + len(hashtag_line) + overhead <= max_len:
            tweets[-1] += f"\n\n{hashtag_line}"
        else:
            tweets.append(hashtag_line)

    # Add thread numbering
    total = len(tweets)
    if total > 1:
        tweets = [f"{t} [{i+1}/{total}]" for i, t in enumerate(tweets)]

    return tweets


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
        self._username: str | None = None

    @property
    def name(self) -> str:
        return "X (Twitter)"

    @property
    def max_length(self) -> int:
        # Threading handles overflow, so set generous limit
        return 1400

    def authenticate(self) -> None:
        """Create an authenticated Tweepy v2 client."""
        self._client = tweepy.Client(
            consumer_key=self._api_key,
            consumer_secret=self._api_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
        )
        self._username = self._handle
        print(f"✅ Authenticated as @{self._username}")

    def post(self, text: str) -> dict:
        """
        Post a tweet or auto-thread.

        Returns:
            dict with success, url, tweet_id, thread_length, error keys.
        """
        if self._client is None:
            raise RuntimeError("Call authenticate() before posting.")

        try:
            tweets = split_into_thread(text)

            if len(tweets) == 1:
                response = self._client.create_tweet(text=tweets[0])
                tweet_id = response.data["id"]
                url = f"https://x.com/{self._username}/status/{tweet_id}"
                print(f"✅ Posted to X: {url}")
            else:
                print(f"🧵 Posting thread ({len(tweets)} tweets)...")
                first_response = self._client.create_tweet(text=tweets[0])
                first_id = first_response.data["id"]
                previous_id = first_id

                for tweet_text in tweets[1:]:
                    response = self._client.create_tweet(
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

        except tweepy.TweepyException as e:
            print(f"❌ X post failed: {e}")
            return {
                "success": False,
                "url": None,
                "tweet_id": None,
                "thread_length": 0,
                "error": str(e),
            }
