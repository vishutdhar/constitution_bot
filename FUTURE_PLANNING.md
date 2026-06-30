# Future Planning, @USC1787

> Status note (2026-06-30): the 77-day series has completed at least one loop
> (state.json day 57). The current operating model is the **3-slot revamp**: the
> same 77 sections recirculate, each posted three ways per day (morning text,
> afternoon image, night video). That code is built and merged but gated off. For
> the authoritative state and the go-live runbook, read `docs/STATE.md`. The growth,
> monetization, and multi-platform thinking below remains the long horizon plan.

## Phase 1: Complete the 77-Day Series (done, now looping)
- All 77 sections post and the series loops, giving a permanent browsable archive.
- The post-series strategy is no longer "replace the series with new content types".
  It is to recirculate the 77 sections across three formats per day (3-slot), which
  triples placements without new content. The content ideas in Phase 2 below are
  additive options on top of that, not a replacement for the series.

## Phase 2: Post-Day 77 Content Strategy
Ideas for ongoing daily content after the initial series:

- **"On this day" constitutional history** — Supreme Court decisions, ratification dates, historical events tied to specific clauses
- **Current events tie-ins** — When something happens in government, post the relevant clause ("Here's what the Constitution actually says about [topic]"). This is the highest-virality format.
- **Amendments explained** — Plain-language breakdowns as reply threads under the original text posts
- **Quizzes/polls** — "Which amendment protects this right?" — high engagement format, boosts reply count (algorithm signal)
- **Weekly threads** — Deep dives into a single clause's history and court cases. Threads get 3x more engagement than single tweets and are the #1 growth driver on X in 2026.
- **Collaborations** — Con law professors, civics teachers, legal commentators. Quote-tweet their takes with the relevant constitutional text.

### Content Calendar (Post-Day 77)
| Day | Content Type |
|-----|-------------|
| Mon | "On this day" constitutional history |
| Tue | Thread: deep dive on a clause or amendment |
| Wed | Current events tie-in (if relevant) or quiz/poll |
| Thu | Plain-language explainer of a section |
| Fri | Quote-tweet a legal/civic educator with relevant text |
| Sat-Sun | Rest (weekends have lowest engagement) |

## Phase 3: Audience Growth

### Targets
- **500 followers** — first milestone (unlocks monetization eligibility path)
- **500 verified followers** — required for X revenue sharing
- **5M impressions in 90 days** — required for X revenue sharing
- **10K+ followers** — opens sponsorship opportunities

### Algorithm Insights (2026 Research)
- **Engagement velocity in the first 30 minutes** is the single biggest algorithm signal. Early likes/replies/retweets push the post to more people.
- **Bookmarks carry a 5x multiplier** (+10 weight vs +0.5 for likes). Constitution text is inherently "save-worthy" — lean into this.
- **Threads get 3x more engagement** than single tweets. 1-2 threads per week is the sweet spot.
- **Native long-form text** is boosted over short posts — the Premium 4000-char limit works in our favor.
- **External links get 50-90% reach reduction** — keep everything native on X. No linking out.
- **Native video** gets the strongest algorithmic push of any format.
- **Replies matter** — X saw +21% reply growth in 2026. Engaging in replies builds community and signals to the algorithm.

### Posting Schedule
- Current live schedule: three off the hour UTC crons, 12:23 / 16:47 / 20:11. On the
  live single poster these are one post plus two idempotent retries. Under 3-slot they
  become three distinct posts (text 12:23, image 16:47, video 20:11).
- Best days: Tuesday, Wednesday, Thursday have highest engagement
- Best times: 9 AM - 11 AM audience timezone
- Worst days: Saturday and Friday — consider skipping or posting lighter content
- Consider shifting to weekday-only posting for Phase 2 content

### Growth Tactics
- Leverage section-specific and community hashtags (#LawTwitter, #APGov, #EdTwitter, #ConLaw)
- Engage with legal/civics community on X — reply to conversations about government with the relevant clause
- Current events relevance is the fastest organic growth lever
- Create "save-worthy" content (infographics, reference threads) to drive bookmarks
- Pin a thread explaining the 77-day series for new profile visitors
- Add a bio call-to-action: "Follow for the full U.S. Constitution, one section per day"

## Phase 4: Monetization

### X Revenue Sharing (Exact Requirements)
- Active X Premium subscription (already have this)
- 500 verified followers (followers who also have X Premium)
- 5M organic impressions in the last 90 days
- Stripe account connected in a supported country
- Account in good standing with X Creator Monetization Standards
- Minimum payout threshold: $30 USD per bi-weekly cycle
- Revenue comes from ads shown in replies to your posts from verified users

### Other Revenue Paths
- **Newsletter** — Substack or Beehiiv for deeper constitutional analysis. Don't link from X posts (kills reach). Use bio link and pinned post.
- **Companion iOS app** — daily Constitution widget/app. Leverages iOS dev skills + built-in X audience for distribution. Civic education is massively underserved ($4M national funding vs $3B for STEM). National Constitution Center has an app but it's basic. Education apps market projected at $124.7B by 2027.
- **Sponsored content** — legal education platforms (Bill of Rights Institute, civics orgs). Need 10K+ followers to attract interest.
- **Merchandise** — Constitution-themed, linked from bio. Low effort, low return. Better as a supplement than a primary strategy.

### Revenue Timeline Estimate
| Milestone | Est. Timeline | Unlocks |
|-----------|--------------|---------|
| 500 followers | 3-6 months | Credibility, community recognition |
| 500 verified followers | 6-12 months | X revenue sharing eligibility |
| 5M impressions/quarter | 12-18 months | X revenue sharing activation |
| 10K followers | 12-18 months | Sponsorship opportunities |
| iOS app launch | When audience exists | Direct revenue + App Store presence |

## Phase 5: Multi-Platform Expansion
- **Bluesky** — bot architecture already supports it, low effort to add
- **Threads** — Meta's X competitor, growing civic audience
- **TikTok/Reels** — short-form video explainers of each clause (highest growth potential but highest effort)
- **YouTube Shorts** — same content as TikTok, different audience

Note: multi-platform should wait until X audience is established. Spreading too thin early dilutes effort.

## Phase 6: Companion iOS App (Long-Term)
- Daily Constitution widget showing today's clause
- Full searchable Constitution text
- "On this day" constitutional history push notifications
- Quiz/flashcard mode for civics students
- Leverage X audience for App Store downloads
- Monetize via premium tier or one-time purchase
- Competitive landscape: National Constitution Center app exists but is basic; ASU's CivEd app covers broader civics

## Technical Backlog
Done since this list was written:
- Native video generation: done. 77 Remotion videos render from the per day assets.
- Decide what the bot does after day 77: decided. It loops and recirculates via 3-slot.

Open, ordered by what unblocks the most (see `docs/STATE.md` for detail):
- Video storage for CI: the rendered videos are gitignored and absent on the runner,
  so the 3-slot night slot falls back to image. Publish `video/videos/` as a GitHub
  Release asset and download per day in the workflow. Options in `docs/VIDEO-POSTING.md`.
- Go live with 3-slot: set `ENABLE_3SLOT=true` AND disable `daily_post.yml` (both, or
  it double posts).
- Deferred, needs budget: regenerate the 21 wrong-content images and audio (baked from
  pre-correction text) and re-render their videos. No-spend rule blocks this until
  approved. Playbook preserved in `plan.md`.
- Add alt text to images for accessibility and reach (note: editing images is fine;
  re-baking their text content is the part gated by no-spend).
- Add Bluesky platform integration (separate unmerged branch).
- Add artifact retention policies to workflows to prevent GitHub storage buildup.
- Build "on this day" content database for the Phase 2 additive content.
- Pin an introductory thread on the profile explaining the series.

Note for the monetization math below: 3-slot roughly triples daily post volume, which
changes the impression and engagement assumptions in the timeline.

## Sources
- [Buffer: Best Time to Post on X 2026](https://buffer.com/resources/best-time-to-post-on-twitter-x/)
- [Sprout Social: How the Twitter Algorithm Works 2026](https://sproutsocial.com/insights/twitter-algorithm/)
- [X Help: Creator Revenue Sharing](https://help.x.com/en/using-x/creator-revenue-sharing)
- [X Creator Revenue Sharing Requirements 2026](https://www.xpayoutcalculator.com/updates/x-creator-revenue-sharing-requirements-2026-complete-guide/)
- [SocialRails: X Marketing Strategy 2026](https://socialrails.com/blog/x-twitter-marketing-strategy)
- [Metricool: X Twitter Statistics 2026](https://metricool.com/x-twitter-statistics/)
