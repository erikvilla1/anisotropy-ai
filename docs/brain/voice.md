# Voice

How Anisotropy writes in public, on X first. The copy editor in the posting workflow reads this note before polishing a draft ([x.md](x.md)).

**Status: first draft, 2026-11-04, drafted by Claude Code from the repository's documentation rules and the kickoff notes. Not yet confirmed by the team.** Edit freely and log the change below.

## Who we are talking to

Engineers who analyze composite laminates and coupons: stress engineers in aerospace and automotive, test-lab engineers, graduate students in composites. They distrust tools that hide the math. They respect sources, units and tolerances.

## What we sound like

- A careful engineer showing their work. Confident, plain, specific.
- Evidence first. A claim about the product names what backs it: a validation case, a comparison record, a decision record.
- Numbers only when an engine run record or a validation case backs them (ADR-0028). No rounded-up marketing numbers. State the tolerance when one exists.
- We say what the model does not do as readily as what it does: first-ply failure only, flat laminates, the known limitations in the system overview.
- Short sentences. Technical words used correctly, never as decoration. No hype, no "revolutionary", no exclamation marks, no emoji, no hashtags unless the post is about an event that uses one.
- Building in public: what shipped, what was validated against what, and what broke. A failure that was found and fixed is a good post.

## Rules for a post

1. 280 X-weighted characters per post. Over that, a thread, each post standing on its own, the first carrying the point.
2. One idea per post. The first line is the point, not a warm-up.
3. Link the evidence when there is some: a public page of the repository or the site. A URL counts 23 characters.
4. Name the material, test, standard or source when the post is about a result. A licensed source is named, never quoted (ADR-0010, ADR-0018).
5. Never name a customer, a customer's part, the team's coupons or a course problem (ADR-0042).
6. Never announce a date, a price, funding or a hire unless the founder put it in the draft.
7. The copy editor polishes wording, order and length. It adds no claim, number or link the draft did not have, and it never replaces the original: the original stays on the draft page beside the polished version.

## Examples

Good shape, from a result already in the changelog (ADR-0053): "Our first bending coupon, IM7/8552 in ASTM D7264 proportions, against CalculiX S8R: 100 numbers within 3 %, the nose reaction within 0.12 %. Both faces of every ply recovered. Decks and record in the repo." Then the link.

Avoid: "Excited to announce our revolutionary AI-powered composites platform! 🚀 #AI #Composites"

## Log
- 2026-11-04: First draft. Unconfirmed.
