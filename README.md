# Daily Constitution Bot

Posts the U.S. Constitution to X (@USC1787), one section per day, covering the full
document and all 27 amendments over **77 days**, then loops. The text is verbatim
(exact, complete clauses) and in the public domain.

New here? Read **`docs/STATE.md`** first: it is the single source of truth for the
current state and direction.

## Posting modes

There are two posting workflows. Only one should be active at a time.

- **Single post (live today): `.github/workflows/daily_post.yml`.** One section per
  UTC day. An image plus a verbatim reply thread.
- **3-slot (built, gated off): `.github/workflows/daily_3slot.yml`.** The same
  section posted three ways at three times: morning text, afternoon image, night
  video. Gated behind the repo variable `ENABLE_3SLOT`. See `docs/THREE-SLOT.md`.

The 3-slot workflow runs only when `ENABLE_3SLOT == 'true'`. Until then the single
poster is live. See `docs/STATE.md` for the go-live runbook (you must also disable
`daily_post.yml`, because both use the same crons and would otherwise double post).

## How it stays duplicate free

Posting to X is irreversible, so the bot records **intent before the side effect**:
it writes and pushes a claim file (`claims/<date>.json`, or `claims/<date>__<slot>.json`
for 3-slot) to `origin/main` BEFORE posting, and the fast forward push is the mutex.
The non-idempotent `create_tweet` lead is never auto-retried. Full model in
`docs/IDEMPOTENCY.md`.

## Quick start

### 1. Get X API credentials

1. Go to [developer.x.com](https://developer.x.com/en/portal/dashboard)
2. Create a **Project** and an **App** inside it
3. Set app permissions to **Read and Write**
4. Generate: API Key and Secret (Consumer Keys), Access Token and Secret
   (Authentication Tokens)

### 2. Set up locally

```bash
git clone <your-repo-url>
cd constitution_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your API keys
```

### 3. Preview and post

```bash
python bot.py --preview                 # preview the single post for the next day
python bot.py --preview --day 46        # preview a specific day (Amendment I)
python bot.py --preview --slot morning  # preview a 3-slot variant (morning|afternoon|night)
python bot.py                           # post the next day's section
```

`bot.py` loads the credentials from `.env` automatically (via python-dotenv), so no
manual `export` is needed. In GitHub Actions the same variables come from repository
secrets instead.

## Automation (free, GitHub Actions)

1. Push the repo to GitHub.
2. Add **Repository Secrets** under Settings, Secrets and variables, Actions:
   `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.
3. The live workflow (`daily_post.yml`) runs on three off the hour UTC crons
   (`23 12`, `47 16`, `11 20`); the first window to win the day's claim posts, the
   others are idempotent retries. State and claims are committed back to the repo.

To switch to 3-slot, see the go-live runbook in `docs/STATE.md`.

## CLI reference

| Command | Description |
|---|---|
| `python bot.py` | Post the next day's section (single post path) |
| `python bot.py --preview` | Preview without posting |
| `python bot.py --day N` | Target a specific day |
| `python bot.py --video` | Use the day's video instead of the image (single post path) |
| `python bot.py --reset` | Reset progress back to day 1 |
| `python bot.py --validate` | Verify all 77 days load |
| `python bot.py --claim --slot <slot> --date <YYYY-MM-DD>` | Claim a 3-slot slot |
| `python bot.py --post-claimed --slot <slot> --date <YYYY-MM-DD>` | Post a claimed slot |
| `python bot.py --finalize --slot <slot> --date <YYYY-MM-DD>` | Record a slot's outcome |
| `python bot.py --preview --slot <slot> [--day N]` | Preview a slot, no post |

`<slot>` is `morning` (text), `afternoon` (image), or `night` (video).

## Adding a new platform

1. Create `platforms/your_platform.py`, inherit `BasePlatform`, implement `name`,
   `max_length`, `authenticate()`, and `post()`.
2. Register it in `bot.py` -> `init_platforms()`.
3. Add env vars to `.env.example`.

If your `post()` takes media, accept `video_path`, `image_path`, `image_text`,
`body_text`, and `reply_char_limit` keyword arguments (see `platforms/base.py`).

## Content: 77 days

| Days | Content |
|------|---------|
| 1 | Preamble |
| 2-26 | Article I (Congress) |
| 27-35 | Article II (President) |
| 36-39 | Article III (Judiciary) |
| 40-42 | Article IV (States) |
| 43 | Article V (Amendments Process) |
| 44 | Article VI (Supremacy Clause) |
| 45 | Article VII (Ratification) |
| 46-55 | Bill of Rights (Amendments I-X) |
| 56-77 | Amendments XI-XXVII |

## Project structure

```
constitution_bot/
├── bot.py                       # main script: state, formatting, claim/post/finalize, slots
├── constitution_posts.json      # 77 daily sections (verbatim corrected)
├── state.json                   # auto: current day
├── post_log.json                # auto: post history
├── claims/                      # auto: durable claim fence (<date> and <date>__<slot>)
├── platforms/                   # base.py + x_twitter.py
├── images_v2/                   # per day parchment cards
├── audio_male/ , audio_female/  # ElevenLabs narration
├── video/                       # Remotion video generator (rendered mp4s gitignored)
├── tests/                       # dependency free regression tests
├── docs/                        # STATE, THREE-SLOT, IDEMPOTENCY, VIDEO-POSTING
└── .github/workflows/           # daily_post.yml (live) + daily_3slot.yml (gated)
```

## Docs

| Doc | What it covers |
|---|---|
| `docs/STATE.md` | Current state and direction (start here) |
| `docs/THREE-SLOT.md` | The 3-slot feature spec |
| `docs/IDEMPOTENCY.md` | The claim before post safety model |
| `docs/VIDEO-POSTING.md` | Video upload mechanics and the storage blocker |
| `video/README.md` | How to render the videos |

## License

The U.S. Constitution is in the public domain. The bot code is yours to use.
