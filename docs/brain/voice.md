# Voice

How Anisotropy writes in public, everywhere: X, LinkedIn, and the website's own marketing copy. A reviewer for any channel reads this note before polishing a draft. The X posting workflow, with its approval loop, is in [x.md](x.md).

**Status: draft, 2026-11-04, drafted by Claude Code from the repository's documentation rules, the kickoff notes, and the live website copy. Expanded 2026-11-04 to cover every channel, not only X, at Kai's request. Not yet confirmed by the team.** Edit freely and log the change below.

## Who we are talking to

Engineers who analyze composite laminates and coupons: stress engineers in aerospace and automotive, test-lab engineers, graduate students in composites. They distrust tools that hide the math. They respect sources, units and tolerances. On LinkedIn the same engineers may be reading alongside a partner or a hiring audience, but the voice does not change for them.

## What we sound like, on every channel

- A careful engineer showing their work. Confident, plain, specific.
- Evidence first. A claim about the product names what backs it: a validation case, a comparison record, a decision record.
- Numbers only when an engine run record or a validation case backs them (ADR-0028). No rounded-up marketing numbers. State the tolerance when one exists.
- We say what the model does not do as readily as what it does: first-ply failure only, flat laminates, the known limitations in the system overview.
- Technical words used correctly, never as decoration. No hype, no "revolutionary", no exclamation marks, no emoji, no hashtags unless the post is about an event that uses one.
- Building in public: what shipped, what was validated against what, and what broke. A failure that was found and fixed is a good post.
- Never name a customer, a customer's part, the team's coupons or a course problem (ADR-0042).
- Never announce a date, a price, funding or a hire unless the founder put it in the draft.
- A reviewer polishes wording, order and length. It adds no claim, number or link the draft did not have, and it never replaces the original: the original stays beside the polished version.

## By channel

### X

Short sentences, one idea per post.

1. 280 X-weighted characters per post. Over that, a thread, each post standing on its own, the first carrying the point.
2. The first line is the point, not a warm-up.
3. Link the evidence when there is some: a public page of the repository or the site. A URL counts 23 characters.
4. Name the material, test, standard or source when the post is about a result. A licensed source is named, never quoted (ADR-0010, ADR-0018).

### Website (landing and marketing copy)

Longer breath than X: short lines can carry a mood, not only a fact, as long as nothing in them is a claim that needs backing. The live site already does this — "From material to understanding", "Coupons first. Evidence always." — and names the workflow (define the coupon, analyze with physics, build and test, make it traceable) without inventing a number anywhere in it. New landing copy should read like that: evocative about the problem and the process, exact about any result.

### LinkedIn

No established presence yet — unknown until the team opens one. Until then: the core voice above applies as-is. Expect longer form than X (room for two or three sentences of context before the point) but the same restraint: no emoji, no hashtag chains, no customer names, no number without a record behind it.

## Examples

Good shape for X, from a result already in the changelog (ADR-0053): "Our first bending coupon, IM7/8552 in ASTM D7264 proportions, against CalculiX S8R: 100 numbers within 3 %, the nose reaction within 0.12 %. Both faces of every ply recovered. Decks and record in the repo." Then the link.

Good shape for the website, already live (app/page.tsx): "From material to understanding." / "A clearer path from composite coupon to confident design. Connecting physics, physical testing, and research—one layer at a time." / "COUPONS FIRST. EVIDENCE ALWAYS." Quoted here only as a voice reference.

Avoid, on any channel: "Excited to announce our revolutionary AI-powered composites platform! 🚀 #AI #Composites"

## Log
- 2026-11-04: First draft, X-only. Unconfirmed.
- 2026-11-04: Expanded to cover the website and LinkedIn alongside X, at Kai's request. Pulled the website example from the live homepage copy (app/page.tsx). LinkedIn has no established presence yet, so that section states the core voice holds until a page exists. Still unconfirmed by the team.
