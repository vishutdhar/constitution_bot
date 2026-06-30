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
  id, OR errored with a 5xx/429 (may have committed), OR the post step ran but
  left no outcome record. May be live → never re-posted.
- `failed` — the lead create returned a **4xx client error** (BadRequest /
  Unauthorized / Forbidden / NotFound) → the tweet was provably NOT created.
- `unknown` — the claim file is present but corrupt/unreadable.

`should_skip_for_claim()` treats `claimed | posted | posted_partial |
posted_unknown | unknown` as **consumed** (never re-post). Only `None` (no claim)
and `failed` (4xx → provably never created) are re-postable. Treating every
ambiguous case as consumed means **no-duplicate beats no-miss**: the worst case
is a rare *missed* day, never a duplicate public post.

**The lead create is never auto-retried.** X's `create_tweet` is non-idempotent
(no idempotency key), so a retry after a 5xx/429 that arrived *after* a
server-side commit would post a duplicate *within one run* — which the cross-run
claim fence cannot prevent. Only a 4xx (provably-not-created) is retryable, and
only at the day level via the next cron window. Replies are likewise not retried
(a reply error → `posted_partial`).

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

## 3-slot generalization (per-(date,slot))

The 3-slot feature (`docs/THREE-SLOT.md`) reuses this exact fence, generalized from
one claim per date to one claim per `(date, slot)`. The core helpers
(`claim_status`, `should_skip_for_claim`, the status list above) are shared, so the
no-duplicate-beats-no-miss semantics carry over unchanged. The differences:

- **Per slot claim key.** Each slot writes `claims/<date>__<slot>.json` and pushes it
  before its post. The three slots write three different keys, so they are fenced
  independently.
- **Day pin.** The section day for a date is pinned once in `claims/<date>__pin.json`
  the first time any slot for that date is claimed; later slots read it, so all three
  slots of a date post the same section even across a midnight UTC flip.
- **State advances once per date, only AFTER a slot posts.** `run_post_slot` calls
  `save_state` after a successful post, guarded by the pin record's status flipping
  from `pinned` to `advanced`, NOT by reading `state.json`'s value. Consequences: a day
  where every slot fails advances nothing and is retried the next date (so an outage
  never silently skips a section); and the advance sets the next day unconditionally,
  which self heals a wrapped `current_day` (for example `total + 1` left by the legacy
  path) instead of freezing on one section. The legacy finalize-push residual below
  still applies here: the advance is persisted only by the finalize commit, so if every
  successful slot's finalize push fails, the next date re-pins the old `current_day` and
  repeats the section (a cross-date repeat, not a same-day duplicate).
- **Finalize ignores stale log rows.** A slot's finalize only counts `post_log.json`
  rows newer than that slot's current claim (`updated_at`). So a stale `failed` row
  from an earlier attempt cannot overwrite the safe `posted_unknown` default and
  reopen a possibly live slot, which would risk a duplicate on the next retry.

**Second workflow.** `.github/workflows/daily_3slot.yml` has the same claim / post /
finalize shape as `daily_post.yml` and uses a date-wide concurrency group so the three
slots run one at a time. Its claim step stages `claims/ state.json`, but at claim time
`state.json` is unchanged: `run_claim_slot` only writes the pin and slot claims, so the
staged `state.json` is harmless (effectively pin-only). The day advance is written later
by `run_post_slot` after a successful post and becomes durable only when the finalize
step pushes. It is gated by `if: vars.ENABLE_3SLOT == 'true'`.

**Go-live coupling.** Both workflows fire on the same three crons but write different
claim keys, so the fence does NOT make them exclude each other. To switch posters
without double posting, disable `daily_post.yml` FIRST, then set `ENABLE_3SLOT=true`
(disabling first means the worst case is one missed window, never a duplicate).

## Manual overrides
`--day`, `--preview`, `--validate`, `--reset` bypass the claim gate exactly as
they bypass `already_posted_today()`. The slot modes `--claim`, `--post-claimed`,
`--finalize` (with `--slot` and `--date`) are the 3-slot CLI surface.
`already_posted_today()` is kept as a second-line guard inside the default/post path
for back-compat with legacy log rows.
