# Daily Constitution Bot — Project Overview

## What Is This?

This is an automated bot that posts the entire U.S. Constitution to X (Twitter), one section per day, over the course of 77 days. It starts with the Preamble on Day 1 and works through every Article, Section, and all 27 Amendments, finishing with Amendment XXVII on Day 77.

The goal is simple: share the full text of the Constitution with your followers in digestible, daily pieces — no commentary, no editorializing, just the document itself.

## How It Works

The bot runs once per day on a schedule. Each time it runs, it:

1. Checks a `state.json` file to see which day it's on (e.g., Day 14)
2. Pulls the corresponding section from `constitution_posts.json`
3. Formats it into a post with a header (`📜 Day 14/77 — Article I, Section 6`), the constitutional text, and hashtags
4. Posts it to X using the Twitter/X API v2
5. Advances the state to the next day and logs the result

When a post exceeds Twitter's 280-character limit (which most do, since constitutional language is verbose), the bot automatically splits it into a threaded reply chain. It breaks on sentence boundaries so the text reads naturally, and adds numbering like `[1/3]`, `[2/3]`, `[3/3]` to each tweet in the thread.

After all 77 days are posted, the bot stops and lets you know the full Constitution has been shared. You can reset it to start over at any time.

## What's in the 77 Days?

| Days   | Content                                    |
|--------|--------------------------------------------|
| 1      | The Preamble                               |
| 2–26   | Article I — The Legislative Branch         |
| 27–35  | Article II — The Executive Branch          |
| 36–39  | Article III — The Judicial Branch          |
| 40–42  | Article IV — Relations Among the States    |
| 43     | Article V — The Amendment Process          |
| 44     | Article VI — The Supremacy Clause          |
| 45     | Article VII — Ratification                 |
| 46–55  | The Bill of Rights (Amendments I–X)        |
| 56–77  | Amendments XI–XXVII (1795–1992)            |

The text is sourced from the official Constitution and is in the public domain.

## How It's Automated

The bot is designed to run daily via **GitHub Actions** at no cost. A workflow file (`.github/workflows/daily_post.yml`) triggers the bot every day at 9:00 AM Eastern. After posting, the workflow commits the updated state back to the repository so it always knows where it left off — even across runs.

You can also run it manually from the command line, preview any day's post without publishing, or jump to a specific day.

## Tech Stack

- **Python 3.12** — Core language
- **Tweepy** — Official Python library for the X/Twitter API v2
- **GitHub Actions** — Free daily scheduling and execution
- **JSON files** — Simple state tracking and post storage (no database needed)

## Platform Extensibility

The project is built with a plugin-style architecture. The X/Twitter integration is one implementation of an abstract `BasePlatform` class. To add a new social media platform (Bluesky, Threads, Mastodon, LinkedIn, etc.), you create a new Python file in the `platforms/` folder that implements four things: a platform name, a character limit, an authentication method, and a post method. The main bot script will pick it up and post to all configured platforms simultaneously.

## Cost

Zero. The X API free tier allows 500 posts per month, and this bot uses roughly 60–90 (depending on how many posts require threading). GitHub Actions is free for this level of usage. There are no servers to maintain and no databases to pay for.

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Main script — handles scheduling logic, formatting, state management, and orchestrates posting |
| `constitution_posts.json` | All 77 daily posts with day number, section name, and constitutional text |
| `platforms/base.py` | Abstract base class that defines what a platform integration must implement |
| `platforms/x_twitter.py` | X/Twitter integration with auto-threading for long posts |
| `platforms/__init__.py` | Package init that exports available platforms |
| `.env.example` | Template for API credentials (copy to `.env` and fill in) |
| `.gitignore` | Keeps `.env`, `__pycache__`, and virtual environments out of version control |
| `requirements.txt` | Python dependencies (tweepy, python-dotenv) |
| `.github/workflows/daily_post.yml` | GitHub Actions workflow for daily automated posting |
| `state.json` | Auto-generated at runtime — tracks which day to post next |
| `post_log.json` | Auto-generated at runtime — history of every post with timestamps, URLs, and success/failure |

## CLI Commands

| Command | What It Does |
|---------|--------------|
| `python bot.py` | Posts the next day's section to all configured platforms |
| `python bot.py --preview` | Shows what would be posted without actually posting |
| `python bot.py --day 46` | Posts (or previews) a specific day (e.g., Amendment I) |
| `python bot.py --reset` | Resets progress back to Day 1 |

## Prerequisites

To run this bot, you need:

1. **Python 3.10+** installed
2. **X API credentials** — a free developer account at [developer.x.com](https://developer.x.com) with a project/app configured for Read and Write access
3. **A GitHub repository** (if using GitHub Actions for automation)

That's it. No cloud infrastructure, no Docker, no databases.
