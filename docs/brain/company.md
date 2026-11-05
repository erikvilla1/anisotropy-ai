# Anisotropy

Anisotropy AI helps engineers analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests. Tested, deterministic code computes every number; a language model may draft inputs and explain results but never produces a number in a result (ADR-0001). The full picture, layer by layer, is the [system overview](../00_system_overview.md).

## Who builds it

- **Christopher Valerio**, CEO. Prompt engineering and AI evaluation.
- **Erik Villa**, founder of the repository; AI architecture and operations; documentation and records. Decides the decision records.
- **Kai Saucedo**, software and UI/UX; marketing and communications.
- **Jusung Park**, reference modeling and validation; operations and logistics.
- **Tabassum Zaman**, fabrication, prototypes and mechanical testing; partnerships and outreach.

Roles only; see [people.md](people.md). Working rule (2026-11-03): reversible decisions are quick, irreversible ones go to the board.

## Where things live

| Thing | Where |
| --- | --- |
| Code, documentation, this brain | github.com/erikvilla1/anisotropy-ai, public |
| Decisions | `docs/decisions/`, indexed in `docs/README.md` |
| Rules for agents | `AGENTS.md` first, then the skills in `docs/agents/skills/` |
| Team notes and X drafts | The team's Notion workspace, private; its page ids stay out of this repository |
| Team chat and post approvals | The team's Discord server, channel `#x-posts` |
| Product | anisotropy.dev, the hosted tier, an invite-only closed beta (ADR-0056) |

## Rules that bind every agent here

- Work on a branch and open a pull request. Only this `docs/brain/` folder may be written to `main` directly (ADR-0057).
- Every choice between alternatives gets a decision record in `docs/decisions/`, from `_template.md`.
- Never quote a number in public unless an engine run record or a validation case backs it (ADR-0028).
- Nothing posts to X without an explicit yes from Kai, Erik or Christopher in `#x-posts` ([x.md](x.md)).
- No secrets, customer data, course material or the team's coupon models in the repository (`AGENTS.md`, ADR-0042).

## Log
- 2026-11-04: Brain created (ADR-0057). First shared workflow: X posting ([x.md](x.md)).
- 2026-11-05: Team of five and the seats from the 2026-11-03 weekly meeting recorded in [people.md](people.md). Team Notion: the Anisotropy workspace with Tasks Tracker, Meetings, X, Team and Resources at the top level.
