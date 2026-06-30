# Daily Constitution Bot, Project Overview

## What is this?

An automated bot that posts the entire U.S. Constitution to X (@USC1787), one
section per day over 77 days, then loops. It starts with the Preamble on day 1 and
works through every Article and all 27 Amendments. No commentary, just the document
itself, in exact verbatim text.

For the current state and direction, read `docs/STATE.md`.

## How it works

Each run handles one section. The bot reads `state.json` for the current day, pulls
that section from `constitution_posts.json`, formats it, posts it, records the
outcome, and advances the day.

Two posting models exist:

- **Single post (live today).** One post per UTC day: a header, the clause, and a
  verbatim reply thread when the text exceeds one tweet. Defined in
  `.github/workflows/daily_post.yml`.
- **3-slot (built, gated off).** The same section posted three ways at three UTC
  times: morning text, afternoon image, night video, each with its own copy hook
  (Read, See, Hear). Defined in `.github/workflows/daily_3slot.yml`, gated by the
  repo variable `ENABLE_3SLOT`. See `docs/THREE-SLOT.md`.

Long posts are split into a numbered reply thread on sentence boundaries. With X
Premium, a corrected clause usually fits a single reply.

### Posting is duplicate free by design

The scheduled workflows post through a claim fence. Because posting is irreversible,
the workflow runs `--claim` first, which writes and pushes a claim file
(`claims/<date>.json`, or `claims/<date>__<slot>.json` for 3-slot) to `origin/main`
BEFORE posting; the push is the mutex. It then runs `--post-claimed`. State advances
only after a slot actually posts, and the non-idempotent `create_tweet` lead is never
auto-retried. A bare local `python bot.py` does not claim; it uses the simpler log
based `already_posted_today()` guard. Full model in `docs/IDEMPOTENCY.md`.

## What is in the 77 days?

| Days | Content |
|------|---------|
| 1 | The Preamble |
| 2-26 | Article I, the Legislative Branch |
| 27-35 | Article II, the Executive Branch |
| 36-39 | Article III, the Judicial Branch |
| 40-42 | Article IV, Relations Among the States |
| 43 | Article V, the Amendment Process |
| 44 | Article VI, the Supremacy Clause |
| 45 | Article VII, Ratification |
| 46-55 | the Bill of Rights, Amendments I-X |
| 56-77 | Amendments XI-XXVII |

The text policy is **verbatim in full**. A correction pass (PR #8) fixed 25 days that
had been abridged, paraphrased, or mislabeled. The corrected verbatim text is the
load bearing accuracy mechanism: it is carried in every slot's copy.

## The media pipeline

- **Images:** `images_v2/day_NN_*.png`, one parchment card per day with that day's
  text in calligraphy.
- **Audio:** ElevenLabs narration in `audio_male/` and `audio_female/`.
- **Video:** a Remotion generator in `video/` renders one vertical 1080x1920 video
  per day from the image plus audio. Rendered mp4s live in `video/videos/`
  (gitignored).

Important caveat: the images and audio (and therefore the videos) were baked from the
pre-correction text, so 21 of the 25 corrected days carry imperfect baked content.
Under a no-spend rule we do not re-bake them; the corrected words are carried in the
captions and replies instead. Days {10, 23, 58, 69, 75} post the image at night
instead of the wrong-narration video. Detail in `docs/STATE.md`.

## How it is automated

GitHub Actions runs the live workflow on three off the hour UTC crons (`23 12`,
`47 16`, `11 20`); the first window to win the day's claim posts, the others are
idempotent retries. After posting, the workflow commits state, log, and claims back
to the repo. You can also run any command manually from the CLI.

## Tech stack

- **Python 3.12** core.
- **Tweepy** for the X API v2 (threading plus chunked video upload).
- **Remotion** (Node) for the video generator.
- **GitHub Actions** for free scheduling.
- **JSON files** for state, posts, log, and the claim fence. No database.

## Platform extensibility

The X integration is one implementation of an abstract `BasePlatform`. To add a
platform, create a file in `platforms/` implementing a name, a character limit, an
authenticate method, and a post method. The bot posts to all configured platforms.

## Cost

The code and infrastructure are free (X API free tier, GitHub Actions). The standing
constraint is **no spend on asset regeneration**: no paid OpenAI image generation and
no paid ElevenLabs audio. Note that enabling 3-slot roughly triples daily post volume
against the X free tier cap of 500 posts per month, so check headroom before going
live.

## Files

| File or folder | Purpose |
|------|---------|
| `bot.py` | Main script: state, formatting, claim/post/finalize, slot composers |
| `constitution_posts.json` | 77 daily sections, verbatim corrected |
| `platforms/base.py` | Abstract platform base class |
| `platforms/x_twitter.py` | X integration, threading, chunked video upload |
| `images_v2/` | Per day parchment cards |
| `audio_male/`, `audio_female/` | ElevenLabs narration |
| `video/` | Remotion video generator (rendered mp4s gitignored) |
| `claims/` | Durable claim fence (`<date>` and `<date>__<slot>`) |
| `state.json` | Auto: current day |
| `post_log.json` | Auto: post history |
| `.github/workflows/daily_post.yml` | Live single poster |
| `.github/workflows/daily_3slot.yml` | Gated 3-slot poster |
| `docs/` | STATE, THREE-SLOT, IDEMPOTENCY, VIDEO-POSTING |

## CLI commands

| Command | What it does |
|---------|--------------|
| `python bot.py` | Post the next day's section |
| `python bot.py --preview` | Show what would be posted, no post |
| `python bot.py --day N` | Target a specific day |
| `python bot.py --video` | Use the day's video instead of the image (single post path) |
| `python bot.py --reset` | Reset progress to day 1 |
| `python bot.py --validate` | Verify all 77 days load |
| `python bot.py --claim --slot <slot> --date <YYYY-MM-DD>` | Claim a slot (3-slot) |
| `python bot.py --post-claimed --slot <slot> --date <YYYY-MM-DD>` | Post a claimed slot |
| `python bot.py --finalize --slot <slot> --date <YYYY-MM-DD>` | Record a slot outcome |
| `python bot.py --preview --slot <slot> [--day N]` | Preview a slot, no post |

## Prerequisites

1. Python 3.10 or newer.
2. X API credentials (free developer account, Read and Write).
3. A GitHub repository if using Actions for automation.
4. Node plus Remotion only if you render videos (see `video/README.md`).
