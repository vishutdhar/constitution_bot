# Constitution Bot — Plan

Last updated: 2026-04-23
Current state: Day 63/77 (text-only). Bot loops back to Day 1 around 2026-05-07, which is when new media formats go live.

## This Weekend (2026-04-25 / 2026-04-26)

Goal: finish every asset needed for the Day 78+ relaunch so the next loop posts text + image + short video automatically.

### Phase 1 — Images: one unique picture per tweet (V2 regeneration)

Decision (2026-04-23): regenerate **all 77 images from scratch** for v2 — not extend the existing 55. Reason: the v1 set reuses images across multiple days, and the whole point of v2 is one image per tweet so each post's picture matches its specific text exactly. Also, v1 images use a more illustrated/cartoon style; v2 targets a photorealistic look.

**Source of truth:** `chatgpt_image_prompts_v2.txt` — regenerated 2026-04-23 to contain exactly 77 prompts (one per day in `constitution_posts.json`). Each prompt embeds that day's actual constitutional text. Old 51-prompt version backed up at `chatgpt_image_prompts_v2.txt.bak`.

**Prompt template (already baked into all 77):**
- Parchment scroll on wooden desk + American flags + oil lamp + leather books + pocket watch + quill template
- Title and Text from that day's `constitution_posts.json` entry
- Trailing instruction: "The text must be completely readable — every single word must be accurate and legible."
- Final instruction (added 2026-04-23): "Research how the constitution looks like in reality and make it look as close to real as possible." — V confirmed via testing that ChatGPT will not produce the realistic style without this exact phrasing.

**Generation method:** ChatGPT Pro UI manually, prompt-by-prompt. Codex CLI / OpenAI API not used because (a) Codex CLI is text-only, no image gen, (b) free image APIs like Pollinations can't reliably render long quoted constitutional text legibly, (c) OpenAI Images API would be paid per image and V wants to avoid paid APIs unless necessary.

**Output workflow (V's V2-then-archive rule):**
- Nothing in the project folder gets deleted mid-process.
- New PNGs land in `images_v2/` (created 2026-04-23) using filenames from each prompt section's FILENAME line (e.g. `day_01_preamble.png`).
- The existing `images/` folder stays untouched — bot keeps using v1 images while v2 regeneration is in flight.
- Once all 77 v2 images are generated and reviewed, V will give the green light to archive: move `images/` and v1 prompt files to `archive/`, then promote `images_v2/` and `image_mapping_v2.json` to canonical names.

**Tasks:**
- Generate all 77 images in ChatGPT Pro UI (in progress — Day 11 test 2026-04-23 confirmed the realistic style works).
- Save each as the exact filename specified in the corresponding section's FILENAME line, into `images_v2/`.
- Build `image_mapping_v2.json` — straight 1:1 day → filename map (no reuse).
- Verify with `python bot.py --preview --day N` once mapping is in place (will need a flag or symlink to point bot at v2 during testing).
- After full review: promote v2 to canonical, archive v1.

Note: "one image per tweet" = one per day (77 images), since each daily post is one tweet (X Premium long tweets / Phase 3). Thread replies are not in scope.

### Phase 2a — AI voice (ElevenLabs, Creator tier)

V already has the ElevenLabs Creator subscription, so generation cost is covered.

Tasks:
- Pick a voice. Shortlist candidates: a grounded American baritone for the body text, optional second voice for the `📜 Day N/77 — [Section]` header. Lock one voice for the series so it sounds consistent.
- Write a small script (`scripts/generate_audio.py`) that:
  - Reads `constitution_posts.json`
  - Calls the ElevenLabs API with the chosen voice_id
  - Writes `audio/day_{N}.mp3` per day
  - Skips if file already exists (idempotent re-runs)
- Store the ElevenLabs API key in `.env` + GitHub Secrets (`ELEVENLABS_API_KEY`).
- Generate all 77 files in one batch. Spot-check 5–10 for pronunciation of 18th-century spellings ("Senatours", "chuse") — the Creator tier supports pronunciation dictionaries if needed.
- Commit audio files to the repo (check size — if >1GB cumulative, switch to Git LFS or S3).

### Phase 2b — Short video: still image + subtle motion + voice

The look V wants: the existing parchment image stays on screen with the tweet text overlaid, AI voice reads it aloud, and small elements animate — the paper flutters slightly as if in a breeze, and the quill/feather moves. It is a still image that feels alive, not a full AI-generated video.

Recommended approach (free + deterministic, no paid video API needed):
1. Start with the Phase 1 parchment image.
2. Use ffmpeg to composite:
   - Base layer: subtle loop of the image with a low-amplitude displacement map (simulates paper flutter) — a simple 2–4px horizontal sine wave over 3–5 seconds, looped.
   - Optional overlay: small feather PNG with a gentle rotation + translation keyframe loop.
   - Text overlay: tweet text using `drawtext` filter, burned-in subtitles synced to the audio.
   - Audio track: the MP3 from Phase 2a.
3. Output: vertical 1080x1920 MP4 (X/TikTok/Reels/Shorts friendly).

Why ffmpeg vs Runway/Sora/Veo: zero cost, zero rate limits, fully reproducible, and the "still-with-subtle-motion" look is exactly what ffmpeg displacement + overlay filters do well. Heavy AI video tools would be overkill and would burn the subscription budget.

Tasks:
- Add `scripts/generate_video.py` that orchestrates ffmpeg for one day.
- Create a reusable feather overlay PNG (transparent background).
- Build one prototype video for Day 1 (Preamble) before batching all 77.
- Review prototype with V. If the motion looks right, batch-generate all 77.
- Commit to repo (or S3 bucket if size forces it).

### Phase 2c — Wire it into the bot

- Extend `platforms/x_twitter.py` to post media: attach the video (primary) and fall back to the image if video upload fails.
- Add a feature flag in `state.json` (`media_mode`: `text` | `image` | `video`) so we can roll out gradually.
- Default to `video` once Phase 2 lands. Keep `text` as a fallback path.
- Update the GitHub Actions workflow to ensure ffmpeg is available in the runner (use `setup-ffmpeg` action or the default ubuntu-latest image).

## Strategic Phase Context (unchanged)

These are the longer-horizon phases this work feeds into. Not in scope for this weekend — kept here so the weekend work stays aligned with the destination.

- **Phase 3 — X Premium + long tweets.** Every section fits in a single post, no threading needed. Subscribe once impressions justify it (~$8/mo).
- **Phase 4 — Monetization.** X Creator Revenue Sharing (500 verified followers, 5M impressions/90 days). Newsletter and companion iOS app are later revenue paths.
- **Phase 5 — Multi-platform.** Bluesky, Threads, TikTok, YouTube Shorts. The short video format generated this weekend is the asset that unlocks this without extra work.
- **Phase 6 — Companion iOS app.** Long-term. Uses X audience for distribution.

See `FUTURE_PLANNING.md` for detail on Phases 3–6.

## Architecture (current)

- **Bot:** `bot.py` — loads section, formats tweet, posts via platform
- **Platform:** `platforms/x_twitter.py` — X API v2 via Tweepy, auto-threading
- **State:** `state.json` — tracks current day, auto-loops after 77
- **Content:** `constitution_posts.json` — 77 daily sections
- **Automation:** GitHub Actions cron at 10:00 UTC (5 AM ET)
- **Secrets:** GitHub Secrets (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET). Add `ELEVENLABS_API_KEY` in Phase 2a.
- **Repo:** https://github.com/vishutdhar/constitution_bot (private)
- **X Account:** @USC1787
