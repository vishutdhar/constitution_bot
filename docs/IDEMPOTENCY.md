# Idempotency: claim-before-post

## The problem
The bot makes an **irreversible** public action (posting to X) and then records
success. Three cron windows run per UTC day as retries. If a post lands but the
success isn't durably recorded — the run crashes after posting, or the
commit/push of the log fails — the next window sees no success and **re-posts =
a duplicate** on the public timeline.

Recording success *after* the side effect can never be fully safe. So we record
the **intent** (a claim) *before* the side effect, durably.

## The mechanism
A per-UTC-day claim file `claims/YYYY-MM-DD.json` is **committed and pushed to
`origin/main` BEFORE** the X post. The post step runs only if that push
succeeded. The fast-forward push is the mutex.

```
claims/2026-06-27.json
{ "date": "2026-06-27", "day": 54, "status": "claimed",
  "claimed_at": "...", "updated_at": "...", "run_id": "..." }
```

Statuses (finalized from the post result):
- `claimed` — intent recorded; may or may not have posted (crash before finalize).
- `posted` — lead + full thread succeeded.
- `posted_partial` — lead live, thread incomplete.
- `posted_unknown` — **ambiguous**: the lead create returned a 2xx with no tweet
  id (may be live), OR the post step ran but left no outcome record.
- `failed` — the lead create returned a **non-2xx** (the tweet was never created).
- `unknown` — the claim file is present but corrupt/unreadable.

`should_skip_for_claim()` treats `claimed | posted | posted_partial |
posted_unknown | unknown` as **consumed** (never re-post). Only `None` (no claim)
and `failed` (lead provably never landed → safe to retry) are re-postable.
Treating every ambiguous case as consumed means **no-duplicate beats no-miss**:
the worst case is a rare *missed* day, never a duplicate public post.

**Date pinning:** the claim step computes one UTC date and passes it as `--date`
to the post and finalize steps, so a midnight-UTC flip can't make them disagree.
`--post-claimed` is **fail-closed**: it refuses to post unless a live `claimed`
record exists for that exact date (no fallback to `state.json`).

## Workflow steps (`.github/workflows/daily_post.yml`)
1. **Claim today** — `python bot.py --claim` writes the claim if today is free;
   `git add claims/`; if nothing staged → skip. Else commit + `git push origin
   HEAD:main`. Push OK → `CLAIM_OK=true`; rejected (another window won) → skip.
   **No `git pull --rebase` here** — the push is the mutex; rebasing would let a
   race-loser re-stack its claim and double-post.
2. **Post today's section** — `if CLAIM_OK`: `python bot.py --post-claimed`
   (X credentials live only here). Posts the day pinned in the claim file.
3. **Finalize** — `if: always() && CLAIM_OK`: `python bot.py --finalize` records
   the outcome into the claim, then commits state/log/claims and pushes. A lost
   push here cannot duplicate — today is already fenced by step 1's claim.

`bot.py` is pure: it only reads/writes files. **All git lives in the workflow.**

## Failure modes handled
- Post lands, run crashes after (e.g. a 200-with-no-id `TypeError`): the claim
  was pushed before posting → next window sees `claimed` → skips. **No duplicate.**
  (This subsumes the prior "P1a" lead-no-id vector — no separate fix needed.)
- Post lands, finalize push fails: claim already durable → next window skips.
- Two windows race: both build a claim on the same tip; git serializes the
  fast-forward push; exactly one wins and posts, the loser is rejected and skips.
- Genuine pre-post failure (lead never landed → `failed`): re-postable next
  window (nothing public yet, so retrying is correct, not a duplicate).

## Known residual
If the **finalize push fails** after a successful post, `state.json`'s day
advance isn't persisted, so the *next day* may re-post the same section once
(a cross-day repeat, not a same-day duplicate; self-corrects on the next good
finalize). Accepted for a low-stakes bot; eliminating it would require deriving
progression purely from the claim history (a larger change).

## Manual overrides
`--day`, `--preview`, `--validate`, `--reset` bypass the claim gate exactly as
they bypass `already_posted_today()`. `already_posted_today()` is kept as a
second-line guard inside the default/post path for back-compat with legacy log
rows.
