# 📜 Daily Constitution Bot

Posts one section of the U.S. Constitution every day to X (Twitter), covering the full document and all 27 amendments over **77 days**.

Built to be extensible — add Bluesky, Threads, Mastodon, or any platform by dropping in a new file.

## Quick Start

### 1. Get X API Credentials

1. Go to [developer.x.com](https://developer.x.com/en/portal/dashboard)
2. Create a **Project** and an **App** inside it
3. Set app permissions to **Read and Write**
4. Generate your keys:
   - API Key & Secret (under "Consumer Keys")
   - Access Token & Secret (under "Authentication Tokens")

### 2. Set Up Locally

```bash
git clone <your-repo-url>
cd constitution_bot

# Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your API keys
```

### 3. Preview & Test

```bash
# Preview today's post without tweeting
python bot.py --preview

# Preview a specific day
python bot.py --preview --day 46   # Amendment I
```

### 4. Post Manually

```bash
# Load env vars and post
export $(cat .env | xargs)   # or use python-dotenv
python bot.py
```

## Automate It (Free)

### Option A: GitHub Actions (Recommended)

The included workflow (`.github/workflows/daily_post.yml`) runs daily at 9 AM ET for free.

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add these **Repository Secrets**:
   - `X_API_KEY`
   - `X_API_SECRET`
   - `X_ACCESS_TOKEN`
   - `X_ACCESS_TOKEN_SECRET`
4. The bot will run automatically. You can also trigger it manually from the **Actions** tab.

State is committed back to the repo so it remembers where it left off.

### Option B: Cron Job (Your Own Server)

```bash
# Run daily at 9 AM Eastern
0 9 * * * cd /path/to/constitution_bot && source .env && /usr/bin/python3 bot.py
```

### Option C: AWS Lambda

Package the bot with its dependencies and trigger with EventBridge (CloudWatch Events) on a daily schedule. The state file would need to be stored in S3 or DynamoDB instead of locally.

## CLI Reference

| Command | Description |
|---------|-------------|
| `python bot.py` | Post the next day's section |
| `python bot.py --preview` | Preview without posting |
| `python bot.py --day 1` | Post (or preview) a specific day |
| `python bot.py --reset` | Reset progress back to day 1 |

## Adding a New Platform

1. Create `platforms/your_platform.py`
2. Inherit from `BasePlatform` and implement `name`, `max_length`, `authenticate()`, and `post()`
3. Add initialization in `bot.py → init_platforms()`
4. Add env vars to `.env.example`

Example skeleton:

```python
from platforms.base import BasePlatform

class BlueskyPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "Bluesky"

    @property
    def max_length(self) -> int:
        return 300

    def authenticate(self) -> None:
        # Connect to AT Protocol
        pass

    def post(self, text: str) -> dict:
        # Publish and return {"success": bool, "url": str, "error": str}
        pass
```

## Content: 77 Days

| Days | Content |
|------|---------|
| 1 | Preamble |
| 2–26 | Article I (Congress) |
| 27–35 | Article II (President) |
| 36–39 | Article III (Judiciary) |
| 40–42 | Article IV (States) |
| 43 | Article V (Amendments Process) |
| 44 | Article VI (Supremacy Clause) |
| 45 | Article VII (Ratification) |
| 46–55 | Bill of Rights (Amendments I–X) |
| 56–77 | Amendments XI–XXVII |

## Project Structure

```
constitution_bot/
├── bot.py                        # Main script
├── constitution_posts.json       # All 77 daily posts
├── state.json                    # Auto-generated: tracks progress
├── post_log.json                 # Auto-generated: history of posts
├── requirements.txt
├── .env.example
├── .gitignore
├── platforms/
│   ├── __init__.py
│   ├── base.py                   # Abstract base class
│   └── x_twitter.py              # X/Twitter implementation
└── .github/
    └── workflows/
        └── daily_post.yml        # GitHub Actions daily schedule
```

## License

The U.S. Constitution is in the public domain. The bot code is yours to use however you like.
