# Project state and direction (read this first)

This is the single source of truth for where the Constitution Bot stands and
where it is going. If you are picking this up in a new session, read this file,
then `docs/THREE-SLOT.md` for the feature detail and `docs/IDEMPOTENCY.md` for
the posting safety model.

Repo: `vishutdhar/constitution_bot` (private). X account: **@USC1787**.
Last updated: 2026-06-30. Main tip at that time: `7dff8be`.

## TL;DR

- The bot posts the U.S. Constitution one section per day across **77 days**, then loops.
- Two posting workflows exist. The **live** one is the original single daily post
  (`.github/workflows/daily_post.yml`). A new **3-slot** workflow
  (`.github/workflows/daily_3slot.yml`) is built and merged but **gated OFF**.
- The plan we are moving toward: **3 posts per day** of the same section, in three
  formats at three times: **morning text, afternoon image, night video**.
- Text policy is **verbatim in full**: every post carries the exact, complete,
  corrected Constitution clause. This is the load bearing accuracy mechanism.
- Hard constraint: **no spend**. We do not pay to regenerate images (OpenAI
  gpt-image-2) or audio (ElevenLabs). We make the best of the assets we already have.
- Nothing about live posting changes until someone flips the gate (see Go-live).

## What we want (the strategy)

One Constitution section per day, posted three ways so the same content earns
three placements and we get a built in format test without producing new content:

| Slot | Time (UTC) | Format | Asset | Copy hook |
|---|---|---|---|---|
| morning | 12:23 | text only | none, the clause itself is the post | "Read today's clause" |
| afternoon | 16:47 | image | `images_v2/day_NN_*.png` | "See today's clause" |
| night | 20:11 | video | `video/videos/day_NN.mp4` | "Hear today's clause" |

The corrected verbatim text rides in the copy of every slot: it is the morning
post body, and the caption plus reply thread on the image and video posts. Even
where a baked image or narration is imperfect, the words a reader reads are correct.

## Current reality (what is actually running)

- **Live poster: `daily_post.yml`** posts ONE section per UTC day. It fires on three
  off the hour crons (`23 12`, `47 16`, `11 20` UTC); the first window to win the
  per day claim posts, the other two are idempotent retries.
- **`daily_3slot.yml` is gated by the repo variable `ENABLE_3SLOT`** (`if:
  vars.ENABLE_3SLOT == 'true'`). That variable is currently **unset**, so the
  3-slot job triggers on schedule but skips. Verified empty via
  `gh api repos/vishutdhar/constitution_bot/actions/variables`.
- Both workflows use the **same three crons**. They write **different** claim keys
  (`<date>.json` for legacy, `<date>__<slot>.json` for 3-slot), so the claim fence
  does NOT make them exclude each other. Running both at once double posts. This is
  why go-live requires disabling `daily_post.yml`, not just enabling the variable.
- `state.json` is at day 57 (it loops 1..77).

## The accuracy situation (why the copy matters)

- Earlier work (PR #8, `9245e13`) corrected `constitution_posts.json` to complete
  verbatim text for **25 days** that had been abridged, paraphrased, or mislabeled.
- The `images_v2` parchment cards and the ElevenLabs `audio_male` / `audio_female`
  narration (and therefore the rendered videos) were **baked from the OLD
  pre-correction text**. So **21 of those 25 corrected days have wrong baked
  content** (days 10, 23, 25, 29, 30, 37, 38, 41, 42, 43, 58, 60, 61, 62, 63, 66,
  68, 69, 70, 73, 75). About five of those are materially wrong (10, 23, 58, 69, 75);
  the rest are subtle (a dropped phrase or a single word).
- Under the no-spend rule we do **not** re-bake these. Instead the corrected text is
  carried in every slot's caption and reply, so the read words are always right.
- **Worst-5 night exception:** days **{10, 23, 58, 69, 75}** post the IMAGE at night
  instead of the video, because their narration is materially wrong and we will not
  broadcast wrong audio. See `WORST5_NIGHT_DAYS` in `bot.py`.

## Go-live runbook (when ready to switch to 3-slot)

Order matters: **disable the old poster BEFORE enabling the new one**, or a cron that
fires in between runs both and double posts.

1. Decide video storage (see below) or accept that night posts the image until then.
2. **Disable `daily_post.yml` first** (Actions tab, or remove its `schedule:`). The two
   workflows share the same crons but write different claim keys, so they do not fence
   each other; whenever both are active a shared window double posts.
3. Then set the repo variable **`ENABLE_3SLOT=true`** (Settings, Variables, Actions).

In this order the worst case between the two changes is a single missed window (neither
poster active for one cron), never a duplicate.

Preview any slot first without posting:

```bash
python bot.py --preview --slot morning|afternoon|night [--day N]
```

## What we want to do next (intentions and backlog)

Ordered by what unblocks the most:

1. **Video storage for CI (blocks real night video).** The 77 rendered videos
   (~1.1 GB) are gitignored and absent on the GitHub Actions runner, so the night
   slot currently falls back to the image even for non worst-5 days. To post real
   video, publish `video/videos/` as a **GitHub Release asset** and have the
   workflow download the day's file before posting. Options compared in
   `docs/VIDEO-POSTING.md` (Release asset vs LFS vs render in CI).
2. **Flip to 3-slot** once video storage is decided (the runbook above).
3. **Deferred, needs budget: regenerate the 21 wrong-content assets.** This is the
   real fix for the baked errors. It requires paid OpenAI gpt-image-2 (images) and
   ElevenLabs (audio), then re-rendering those videos. The image generation
   playbook (prompt template, one image per day, ChatGPT UI to avoid API spend) is
   preserved in `plan.md`. After regeneration the worst-5 nights and the image-only
   fallbacks can revert to video. Do NOT do this without explicit budget approval.
4. **Accuracy review of the 77 videos** (owner side) before enabling video at scale.
5. **Post day 77 content engine** (the account's longer term growth plan lives in
   `FUTURE_PLANNING.md`).

## Invariants and gotchas (do not regress these)

- **The X `create_tweet` lead is never auto-retried.** It is non-idempotent; a retry
  after a 5xx/429 that committed server side would duplicate within one run. Only a
  4xx (provably never created) is retryable, at the day level via the next window.
  See `docs/IDEMPOTENCY.md`.
- **Claim before post.** Each slot writes and pushes its claim
  (`claims/<date>__<slot>.json`) BEFORE the irreversible post; the fast forward push
  is the mutex. No `git pull --rebase` before the claim push.
- **State advances once per date, only AFTER a slot posts**, guarded by the pin
  record's status flipping to `advanced` (not by reading `state.json`'s value). A day
  whose every slot fails is retried the next date, not skipped. The advance also self
  heals a wrapped `current_day` (for example `total + 1` left by the legacy path).
- **Finalize ignores stale log rows.** A slot's finalize only counts log rows newer
  than the current claim, so a stale `failed` row from an earlier attempt cannot
  reopen a possibly live slot and cause a duplicate.
- **Night degrades in three layers:** worst-5 day posts image; no video file present
  posts image; a video that is rejected at upload degrades to the day's image (passed
  as an upload fallback) rather than to text only.
- **Caption hook follows the media kind chosen at compose time**, not the slot name,
  so a night that downgrades to an image because it is a worst-5 day or has no video
  file says "See", not "Hear". The rarer runtime upload-fallback image keeps the
  "Hear" caption (a known minor cosmetic mismatch; see `docs/THREE-SLOT.md`).

## Key files

| Path | What it is |
|---|---|
| `bot.py` | The whole bot: state, formatting, claim/post/finalize, slot composers |
| `constitution_posts.json` | 77 daily sections, verbatim corrected |
| `platforms/x_twitter.py` | X API v2 via Tweepy, threading, chunked video upload |
| `images_v2/` | per day parchment cards (baked from old text for 21 days) |
| `audio_male/`, `audio_female/` | ElevenLabs narration (same caveat) |
| `video/` | Remotion video generator; rendered mp4s in `video/videos/` (gitignored) |
| `claims/` | durable claim fence, one file per `<date>` and per `<date>__<slot>` |
| `.github/workflows/daily_post.yml` | live single poster |
| `.github/workflows/daily_3slot.yml` | gated 3-slot poster |
| `docs/THREE-SLOT.md` | 3-slot feature spec |
| `docs/IDEMPOTENCY.md` | claim fence safety model (legacy + per slot) |
| `docs/VIDEO-POSTING.md` | video upload mechanics + storage blocker |
| `video/README.md` | how to render the videos |

## Recent history

- PR #3 video generator, #4 opt-in X video posting, #5 partial-post hardening,
  #6 durable claim fence (`17f7b01`).
- PR #7 day 36 image typo fix. PR #8 verbatim text correction of 25 days (`9245e13`).
- **PR #9 the 3-slot feature (squash `7dff8be`, 2026-06-29).** Seven Codex findings
  fixed before merge (long text threading, slot concurrency, advance timing, wrapped
  state, stale finalize logs, video image fallback, caption hook).
