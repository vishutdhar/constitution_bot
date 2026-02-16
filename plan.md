# Constitution Bot — Plan

## Phase 1: Text-Only (Days 1-77)
- **Status:** Active
- **Start date:** Feb 16, 2026
- **End date:** ~May 4, 2026
- Posts one section of the U.S. Constitution daily at 5 AM ET
- Text-only, auto-threads long sections (62 of 77 need threading)
- Automated via GitHub Actions — fully hands-off
- Goal: Build audience, establish consistent posting history
- Cost: ~$1.40 total (140 tweets x $0.01)

## Phase 2: Text + Images (Days 78-154)
- Bot auto-loops back to Day 1 after Day 77
- Add ChatGPT-generated parchment images to each section (55 images)
- Images generated manually in ChatGPT using prompts in `chatgpt_image_prompts.txt`
- Drop images into `images/` folder, wire up `image_mapping.json`
- Higher engagement from visual content
- Goal: Grow followers, build toward monetization

## Phase 3: X Premium + Long Tweets
- Once impressions/followers justify it, subscribe to X Premium (~$8/month)
- Character limit increases from 280 to 25,000
- Every section fits in a single tweet — no threading needed
- Cleaner retweets, lower API costs (77 tweets instead of 140)
- Checkmark adds credibility
- X Creator Revenue Sharing requires: 500+ followers, 5M impressions in 3 months

## Architecture
- **Bot:** `bot.py` — loads section, formats tweet, posts via platform
- **Platform:** `platforms/x_twitter.py` — X API v2 via Tweepy, auto-threading
- **State:** `state.json` — tracks current day, auto-loops after 77
- **Content:** `constitution_posts.json` — 77 daily sections
- **Automation:** GitHub Actions cron at 10:00 UTC (5 AM ET)
- **Secrets:** GitHub Secrets (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
- **Repo:** https://github.com/vishutdhar/constitution_bot (private)
- **X Account:** @USC1787
