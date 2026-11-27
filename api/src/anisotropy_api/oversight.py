"""What the AI does, read for the founders' AI activity page (ADR-0145).

Three readings of records the API already keeps, and nothing else: no write, no call to a model.

- `activity`: every call to the model (`model_calls`, ADR-0120), every plan (`agent_plans`, ADR-0144) and every approval of one,
  newest first, each with who it was for, what for, which model answered and whether that model had passed the assistant check, how it
  ended, how long it took and what it cost.
- `plan_story`: one plan as it happened: the sentence, each answer the checks turned back and why, each call, the approval, the version
  it made, the job it started and each step as the page reported it.
- `weekly`: the guards' view (ADR-0139) and the costs' view (ADR-0120) as they stand, with the plans of each week by how they ended,
  the reasons plans were refused, and the calls answered by a model outside the checked list.

What a person wrote stays theirs (ADR-0104). On a row of anyone who is not a founder, what happened is shown (the feature, the model,
the outcome, the time, the cost, each step's tool and state) and what they wrote is not (the sentence, a step's words, values and notes,
the answers turned back, the changes, the job's messages). No free text of such a row leaves here: a reason the server's checks wrote
is given as one of the fixed lines of `REASON_KINDS`, and any other reason, the model's own sentence above all, as `REASON_HIDDEN`
(`reason_shown`, `reason_kind`). Such a person is named by a tag that
tells their rows apart and keeps their email off the page. The tag is a pseudonym, not anonymity: it is the start of the email's SHA-256
with nothing added, so whoever knows an email can work out its tag, and a founder can read the database. A row with no email is a
robot's (a service token, ADR-0138) or, on a machine with no sign-in, its one user's.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, and_, case, false, func, literal_column, or_, select, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, load_only

from . import planner
from .records import AgentPlanRow, JobRow, ModelCallRow, ModelVersionRow, Run

HIDDEN = "a customer's words, not shown"  # in place of what a person who is not a founder wrote
REASON_HIDDEN = "a reason in the customer's or the model's own words, not shown"  # in place of a reason that is no fixed line
TAG_LENGTH = 10  # hex digits of the email's SHA-256 a tag shows: 40 bits, so two people of ten thousand share one about once in 22,000 times
FEED_MAX = 200
PLAN_STEP_PUBLIC = ("n", "role", "tool", "state")  # what a step shows whoever's plan it is
WEEKS = 8


# ----------------------------------------------------------------------------------------------------------------- who a row is

def tag_of(email: str) -> str:
    """A short tag for a person who is not a founder: the same person, the same tag, and no email on the page. A pseudonym, not
    anonymity: the hash has nothing added, so an email gives its tag, and the database holds the email beside every row."""
    return "customer " + hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:TAG_LENGTH]


def is_founder(email: str | None, founders: Collection[str]) -> bool:
    """Whether an email is one of the founders', for this page: the founders' list holds plain lower-case emails, and an email is one
    of them only when it is the same but for the case of its ASCII letters. An email with any character outside ASCII is none (`K`, the
    Kelvin sign, lower-cases to `k`, so "Kate@…" written with it would read as kate@…), and neither is one with space around it
    (`.strip()` would take a tab, a line end or a no-break space off)."""
    return email is not None and email.isascii() and email == email.strip() and email.lower() in founders


def who(email: str | None, founders: Collection[str], *, local: bool) -> tuple[str, bool]:
    """Who a row is for, as the page names them, and whether what they wrote may be shown: a founder's email and theirs in full; a
    robot or the machine's one user with no email, in full; anyone else as a tag, without their words."""
    if email is None:
        return ("this machine" if local else "robot"), True
    if is_founder(email, founders):
        return email, True
    return tag_of(email), False


# ------------------------------------------------------------------------------------------------- a reason without its words

def _kind(template: str, line: str) -> tuple[re.Pattern[str], str]:
    """A reason of the planner's, `{}` where it writes a value, a name or quoted words, and the fixed line that stands for it."""
    return re.compile(".+".join(re.escape(part) for part in template.split("{}")), re.DOTALL), line


def _same(*lines: str) -> list[tuple[re.Pattern[str], str]]:
    """Reasons that hold no word of the sentence or the model: each stands as it is."""
    return [_kind(line, line) for line in lines]


# Each reason the planner's checks give (planner.py, planner_kinds.py), the day's limits and why a writer gave no answer (assistant.py),
# as the fixed line shown on a row whose words are not shown. What a reason writes of the sentence, the setup or the model's answer (a
# number, a unit, a region, a material, quoted words) is in no line. A reason that matches none, a tool's own refusal among them, is
# REASON_HIDDEN. tests/test_oversight.py holds the planner's reasons to this list. Only a reason the server wrote is read against the
# list (`reason_shown` says which those are): the model can write a sentence that matches a line.
REASON_KINDS: tuple[tuple[re.Pattern[str], str], ...] = (
    *_same("the value or the unit given is longer than any a step takes", "it quotes no words of the sentence",
           "its quote is not words of the sentence", "an answer names the question it answers",
           "its question is not a question: an answer asks the engineer's question of the result, ending in a question mark",
           planner.NOT_A_QUESTION, "no step on offer does what the sentence asks", "the plan has no step and asks no question",
           "it is not a step", "the plan runs the analysis once", "an answer reads the result of the plan's run, so it comes after a run",
           "a change after the run would not be in it: the changes come before the run", planner.PLAN_LIMIT_REASON,
           "the plan works the wing by hand once", "the plan runs the check once",
           "an answer reads the result of the hand calculation or the check, so it comes after one of them",
           "a change after the hand calculation or the check would not be in it: the changes come first",
           "an answer reads the result of the sweep, the solve or the bond, so it comes after one of them",
           "the plan solves the slice once", "the plan follows the bond once",
           "a change or a sweep after the solve or the bond would not be in it: they come first",
           "use_pick takes the pick of the sweep just before it, and there is none",
           "the sweep before it names no load, so it picks nothing: a pick is the smallest repair whose adhesive stays elastic at a load",
           "the plan sweeps once", "the model could not be reached", "the model is rate limited", "the model declined the request",
           "the model's answer was cut short", "the model answered with no text", "the model's answer was not the JSON asked for",
           "the model gave no answer", "the day's limit of free-text readings for this sign-in is reached"),
    _kind("{} is not a number the sentence writes; a value is copied as written and the tools convert it",
          "a value that is not a number the sentence writes"),
    _kind("the unit {} is not written in the sentence", "a unit the sentence does not write"),
    _kind("the sentence writes {}, and the step gives it in {}", "a value given in another unit than the sentence writes"),
    _kind("the sentence writes {}, and the step gives it with no unit", "a value the sentence writes with a unit, given with none"),
    _kind("{} is not a material of the library; the materials are given by id", "a material that is not in the library"),
    _kind("the sentence does not name {}; a material is set only when the sentence names it", "a material the sentence does not name"),
    _kind("the sentence does not name {} for {}; a choice is set only when the sentence names it", "a choice the sentence does not name"),
    _kind("the sentence names {}, not {}", "another material than the one the sentence names"),
    _kind("{} takes only words the sentence writes", "a row given words the sentence does not write"),
    _kind("its question is longer than {} characters", "its question is too long"),
    _kind("its question writes {}, which the sentence does not", "its question writes a number the sentence does not"),
    _kind("its question tells the answer what to say ({}): it asks, and the result answers", "its question tells the answer what to say"),
    _kind("its question states a verdict ({}) before anything has run: it asks, and the result answers",
          "its question states a verdict before anything has run"),
    _kind("the question back is longer than {} characters", "the question back is too long"),
    _kind("the question back writes {}, which the sentence does not", "the question back writes a number the sentence does not"),
    _kind("the question back decides ({}): it only asks which one is meant", "the question back decides, where it should only ask"),
    _kind("{} is not a tool on offer here; the tools are {}", "a tool that is not on offer"),
    _kind("{} is not a row on offer", "a row that is not on offer"),
    _kind("{} is not a region of this model; it has {}", "a region the model does not have"),
    _kind("the plan has {} steps with the checks the software adds; a plan has at most {}", "more steps than a plan may have"),
    _kind("the plan has {} steps; a plan has at most {}", "more steps than a plan may have"),
    _kind("the sentence asks for a change the plan leaves out ({}): ask for it rather than run without it",
          "the sentence asks for a change the plan leaves out"),
    _kind("the sentence asks for changes the plan leaves out ({}): ask for them rather than run without them",
          "the sentence asks for a change the plan leaves out"),
    _kind("the plan would run the setup as it stands, though the sentence asks for a change no step makes ({})",
          "the plan would run the setup as it stands, though the sentence asks for a change no step makes"),
    _kind("{} is not a placement; plies go beside those of the same angle, or at the middle", "a placement that is none"),
    _kind("{} is not a choice of the cut faces; they are open or bonded", "a choice of the cut faces that is none"),
    _kind("the pick is the sweep's own: use_pick takes no value, and this one gives {}", "use_pick given a value, and it takes none"),
    _kind("the sweep picks nothing to use: {}", "the sweep picks nothing to use"),
    _kind("the model's credential was refused: {}", "the model's credential was refused"),
    _kind("the model answered with an error ({}): {}", "the model answered with an error"),
)
REASON_LINES = frozenset(line for _, line in REASON_KINDS) | {REASON_HIDDEN}
_OF_A_STEP = re.compile(r"step (\d{1,4}): (.*)", re.DOTALL)


def reason_kind(reason: str, steps: int = 0) -> str:
    """One reason the server's checks wrote, as a row whose words are not shown gives it: a fixed line of REASON_KINDS, after
    "step N: " when the reason is one step's, or REASON_HIDDEN. `steps` is how many steps the answer the reason is about has: a step's
    number is given only when it is one of them, 1 to `steps`, which is the number the server itself gave that step. Any other number
    could be a number of the sentence (a model can write "step 7313: …" back), so a reason that leads with one is hidden whole."""
    step = _OF_A_STEP.fullmatch(reason)
    head, body = "", reason
    if step:
        if not 1 <= int(step.group(1)) <= steps:
            return REASON_HIDDEN
        head, body = f"step {int(step.group(1))}: ", step.group(2)
    for pattern, line in REASON_KINDS:
        if pattern.fullmatch(body):
            return head + line
    return REASON_HIDDEN


def steps_of(answer: Any) -> int:
    """How many steps an answer of the model has, as it is kept in `agent_plans.attempts`; 0 for anything that is no such answer."""
    steps = answer.get("steps") if isinstance(answer, dict) else None
    return len(steps) if isinstance(steps, list) else 0


def reasons_shown(reasons: Any, open_: bool, steps: int = 0) -> list[str]:
    """The reasons the checks gave for one answer of `steps` steps (`agent_plans.attempts` keeps them, and the checks alone write
    them): as they are for a founder, a robot or this machine; each as its fixed line otherwise."""
    kept = [reason for reason in (reasons if isinstance(reasons, list) else []) if isinstance(reason, str)]
    return kept if open_ else [reason_kind(reason, steps) for reason in kept]


def reason_shown(reason: str | None, state: str, last_reasons: Any, last_steps: int, open_: bool) -> str | None:
    """Why a plan came to nothing, as its row may give it. In full when the words may be shown. Otherwise it depends on who wrote it,
    which the records tell:

    - A refused plan's reason is either the checks' reasons for the last answer turned back, joined (`planner.reason_of`), or the
      model's own sentence in their place (`Checked.said`, ADR-0144 amendment 1). `last_reasons` are those checks' reasons as
      `agent_plans.attempts` keeps them, so the reason is the checks' when it is exactly their joining, and then each is given as its
      fixed line. When it is not, it is the model's sentence, or the plan is older than `attempts` and nothing tells which: it is
      REASON_HIDDEN and is never read against the fixed lines, since a model can write a sentence that matches one.
    - Any other plan's reason is the server's own from when the plan was made (no model answered, or a day's limit): its fixed line,
      with no step's number, or REASON_HIDDEN."""
    if reason is None or open_:
        return reason
    if state != "refused":
        return reason_kind(reason)
    reasons = reasons_shown(last_reasons, True)
    if not reasons or reason != planner.reason_of(reasons):
        return REASON_HIDDEN
    lines = list(dict.fromkeys(reason_kind(one, last_steps) for one in reasons[:planner.MAX_REASONS]))
    return "; ".join(lines) + ("; and more like them" if len(reasons) > planner.MAX_REASONS else "")


# ------------------------------------------------------------------------------------------------------------- how a call ended

def call_outcome(stop_reason: str | None, response: dict[str, Any] | None, plan_state: str | None,
                 turned_back: bool | None = False) -> str:
    """How a call to the model ended, in the page's words: declined or cut short by the model; else, for a plan's call, `turned back`
    when the checks turned its answer back, the plan's state when its answer is the one the plan came to, and `plan <state>` when the
    records do not say which of the two it was (`turned_back` None); else what became of the words from the run record's answer
    (ADR-0139's reading): set aside by a guard, partly dropped, kept, or not used. Every route but a plan's makes one call for a request,
    so a run's reading is its one call's."""
    if stop_reason == "refusal":
        return "declined"
    if stop_reason == "max_tokens":
        return "cut short"
    if plan_state is not None:
        if turned_back:
            return "turned back"
        return plan_state if turned_back is False else f"plan {plan_state}"
    response = response or {}
    if response.get("withheld") is True:
        return "set aside"
    dropped = response.get("dropped")
    if isinstance(dropped, list) and dropped:
        return "partly dropped"
    return "kept" if response.get("model") else "not used"


def turned_back_calls(state: str, turned: int, calls: Sequence[uuid.UUID]) -> dict[uuid.UUID, bool | None]:
    """Which of a plan's calls, given in the order they were answered, had their answer turned back by the checks. The planner asks
    again after each answer it turns back and keeps each in `agent_plans.attempts`, so the first `turned` calls are those, when the
    plan has the calls its attempts say it must: one more than the answers turned back for a plan that came to an answer, and that many
    or one more (a last call that gave no answer to check) for a refused one. With any other count a row is missing or the plan is older
    than these records, and no call is said to be either: each is None."""
    n = len(calls)
    told = 1 <= turned <= n <= turned + 1 if state == "refused" else n == turned + 1
    return {call: (index < turned if told else None) for index, call in enumerate(calls)}


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _at(value: dt.datetime | None) -> str | None:
    return None if value is None else value.astimezone(dt.timezone.utc).isoformat()


# ------------------------------------------------------------------------------------------------------------------------- the feed

KINDS = ("approval", "call", "plan")  # an event's kinds, in the order two events of one instant are told apart


@dataclass(frozen=True)
class Cursor:
    """A place in the feed: an instant alone, or one event's key (its time, kind and row). Events are ordered by key, so no two share a
    place and a page can start or end exactly at one."""

    at: dt.datetime
    kind: str | None = None
    row: uuid.UUID | None = None


def key_of(at: dt.datetime, kind: str, row: uuid.UUID) -> str:
    """An event's key as the routes give and take it."""
    return f"{_at(at)}|{kind}|{row}"


def cursor(value: str) -> Cursor:
    """A time with its offset, or an event's key, read; ValueError says what is wrong with anything else. A place is plain text: the
    time's reader takes any one character between the date and the hour, a NUL or half of a surrogate pair among them, and a view
    of the page keeps the place as it was asked, which the records cannot do with those."""
    if not (value.isascii() and value.isprintable()):
        raise ValueError("a place is written in plain characters")
    stamp, bar, rest = value.partition("|")
    at = dt.datetime.fromisoformat(stamp)
    if at.tzinfo is None:
        raise ValueError("the time has no offset")
    if not bar:
        return Cursor(at)
    kind, _, row = rest.partition("|")
    if kind not in KINDS:
        raise ValueError(f"an event is one of {', '.join(KINDS)}")
    return Cursor(at, kind, uuid.UUID(row))


def _bound(time, row, kind: str, place: Cursor, side: str):
    """The rows of one kind on one side of a place: `before` it, `after` it, or `from` it on (the place itself included)."""
    strict = time < place.at if side == "before" else time > place.at
    if place.kind is None:  # an instant alone: nothing at that instant is before or after it, and everything at it is from it on
        return time >= place.at if side == "from" else strict
    if kind == place.kind:
        tie = row < place.row if side == "before" else row >= place.row if side == "from" else row > place.row
    else:  # another kind at the same instant: wholly on one side, by the order of KINDS
        tie = true() if (kind < place.kind) == (side == "before") else false()
    return or_(strict, and_(time == place.at, tie))


# What `call_outcome` reads of a run's answer, picked in the database: a run's whole answer can be large, and the page reads often.
RUN_READING = literal_column("jsonb_build_object('withheld', response -> 'withheld', 'dropped', response -> 'dropped', "
                             "'model', response -> 'model')", type_=JSONB)
TURNED = case((func.jsonb_typeof(AgentPlanRow.attempts) == "array", func.jsonb_array_length(AgentPlanRow.attempts)), else_=0)


def _plans_of_calls(session: Session, plan_ids: Collection[uuid.UUID]) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, bool | None]]:
    """For the plans some calls were made for: each plan's state, and for every call of those plans whether its answer was turned back."""
    if not plan_ids:
        return {}, {}
    plans = {plan: (state, turned) for plan, state, turned in
             session.execute(select(AgentPlanRow.id, AgentPlanRow.state, TURNED).where(AgentPlanRow.id.in_(plan_ids)))}
    calls: dict[uuid.UUID, list[uuid.UUID]] = {}
    for plan, call in session.execute(select(ModelCallRow.plan_id, ModelCallRow.id).where(ModelCallRow.plan_id.in_(plan_ids))
                                      .order_by(ModelCallRow.called_at, ModelCallRow.id)):
        calls.setdefault(plan, []).append(call)
    turned_back: dict[uuid.UUID, bool | None] = {}
    for plan, (state, turned) in plans.items():
        turned_back.update(turned_back_calls(state, turned, calls.get(plan, [])))
    return {plan: state for plan, (state, _) in plans.items()}, turned_back


# What the feed shows of a call and of a plan: a plan's steps and the answers turned back are large and are no part of it.
CALL_SHOWN = (ModelCallRow.called_at, ModelCallRow.user_email, ModelCallRow.actor, ModelCallRow.feature, ModelCallRow.model,
              ModelCallRow.checked, ModelCallRow.stop_reason, ModelCallRow.seconds, ModelCallRow.cost_usd, ModelCallRow.plan_id,
              ModelCallRow.run_id)
PLAN_SHOWN = (AgentPlanRow.created_at, AgentPlanRow.approved_at, AgentPlanRow.user_email, AgentPlanRow.actor, AgentPlanRow.kind,
              AgentPlanRow.model, AgentPlanRow.state, AgentPlanRow.ask)


def activity(engine: Engine, founders: Collection[str], *, local: bool, limit: int = 50, before: Cursor | None = None,
             since: Cursor | None = None, start: Cursor | None = None) -> tuple[list[dict[str, Any]], bool]:
    """The newest events, at most `limit` of them, and whether there are older ones the same reading would give: calls, plans and
    approvals, merged by key (time, then kind, then row), newest first. Each carries its `key`. `before` reads what is before a
    place and `since` what is after it; `start` reads from a place on, that place included. When there are older ones, the next page
    is the one `before` the last event's key. Reading from the oldest event shown on, page by page, gives everything there is from
    it on, however late a row was written: that is the page's refresh. Each kind is read newest first by its time and row, which
    `model_calls_called_at_idx` and migration 0018's two indexes on `agent_plans` give without a sort."""
    limit = max(1, min(limit, FEED_MAX))
    sources = (("call", ModelCallRow, ModelCallRow.called_at, None, CALL_SHOWN), ("plan", AgentPlanRow, AgentPlanRow.created_at, None, PLAN_SHOWN),
               ("approval", AgentPlanRow, AgentPlanRow.approved_at, AgentPlanRow.approved_at.is_not(None), PLAN_SHOWN))
    found: dict[str, list] = {}
    with Session(engine) as session:
        for kind, table, time, only, shown in sources:
            # one more than asked of each kind: the event past the page, if there is one, says there are older ones
            query = select(table).options(load_only(*shown, raiseload=True)).order_by(time.desc(), table.id.desc()).limit(limit + 1)
            if only is not None:
                query = query.where(only)
            for place, side in ((before, "before"), (since, "after"), (start, "from")):
                if place is not None:
                    query = query.where(_bound(time, table.id, kind, place, side))
            found[kind] = list(session.scalars(query))
        calls = found["call"]
        run_ids = {c.run_id for c in calls if c.run_id is not None}
        answers = dict(session.execute(select(Run.id, RUN_READING).where(Run.id.in_(run_ids))).all()) if run_ids else {}
        states, turned_back = _plans_of_calls(session, {c.plan_id for c in calls if c.plan_id is not None})

    events: list[tuple[tuple[dt.datetime, str, uuid.UUID], dict[str, Any]]] = []
    for c in calls:
        name, open_ = who(c.user_email, founders, local=local)
        events.append(((c.called_at, "call", c.id), {
            "kind": "call", "at": _at(c.called_at), "who": name, "words_shown": open_, "actor": c.actor, "what": c.feature,
            "model": c.model, "checked": c.checked,
            "outcome": call_outcome(c.stop_reason, answers.get(c.run_id), states.get(c.plan_id), turned_back.get(c.id)),
            "seconds": c.seconds, "cost_usd": _money(c.cost_usd), "plan": None if c.plan_id is None else str(c.plan_id),
            "run": None if c.run_id is None else str(c.run_id), "ask": None}))
    for p in found["plan"]:
        name, open_ = who(p.user_email, founders, local=local)
        events.append(((p.created_at, "plan", p.id), {
            "kind": "plan", "at": _at(p.created_at), "who": name, "words_shown": open_, "actor": p.actor, "what": f"plan on a {p.kind}",
            "model": p.model, "checked": None, "outcome": p.state, "seconds": None, "cost_usd": None, "plan": str(p.id), "run": None,
            "ask": p.ask if open_ else HIDDEN}))
    for p in found["approval"]:
        name, open_ = who(p.user_email, founders, local=local)
        events.append(((p.approved_at, "approval", p.id), {
            "kind": "approval", "at": _at(p.approved_at), "who": name, "words_shown": open_, "actor": p.actor, "what": "approve",
            "model": None, "checked": None, "outcome": p.state, "seconds": None, "cost_usd": None, "plan": str(p.id), "run": None,
            "ask": p.ask if open_ else HIDDEN}))
    events.sort(key=lambda pair: pair[0], reverse=True)
    return [{**event, "key": key_of(*key)} for key, event in events[:limit]], len(events) > limit


# ------------------------------------------------------------------------------------------------------------------- a plan's story

def _step(step: dict[str, Any], open_: bool) -> dict[str, Any]:
    shown = {key: step.get(key) for key in PLAN_STEP_PUBLIC}
    shown["line"] = step.get("line") if open_ else None
    shown["note"] = step.get("note") if open_ else None
    return shown


def plan_story(engine: Engine, plan_id: uuid.UUID, founders: Collection[str], *, local: bool) -> dict[str, Any] | None:
    """One plan from its records, or None when there is no such plan."""
    with Session(engine) as session:
        plan = session.get(AgentPlanRow, plan_id)
        if plan is None:
            return None
        calls = list(session.scalars(select(ModelCallRow).where(ModelCallRow.plan_id == plan_id)
                                     .order_by(ModelCallRow.called_at, ModelCallRow.id)))
        version = (session.get(ModelVersionRow, (plan.project_id, plan.version_n))
                   if plan.project_id is not None and plan.version_n is not None else None)
        job = None
        if plan.job_id:
            try:
                job = session.get(JobRow, uuid.UUID(plan.job_id))
            except ValueError:
                job = None
    name, open_ = who(plan.user_email, founders, local=local)
    tried = [t for t in plan.attempts or [] if isinstance(t, dict)]
    turned_back = turned_back_calls(plan.state, len(tried), [c.id for c in calls])
    return {
        "id": str(plan.id), "kind": plan.kind, "who": name, "words_shown": open_, "actor": plan.actor, "state": plan.state,
        "ask": plan.ask if open_ else HIDDEN, "question": plan.question if open_ else None,
        "reason": reason_shown(plan.reason, plan.state, tried[-1].get("reasons") if tried else None,
                               steps_of(tried[-1].get("plan")) if tried else 0, open_),
        "unread": len(plan.unread or []), "writer": plan.writer, "model": plan.model,
        "created_at": _at(plan.created_at), "approved_at": _at(plan.approved_at), "updated_at": _at(plan.updated_at),
        "turned_back": [{"plan": t.get("plan") if open_ else None, "reasons": reasons_shown(t.get("reasons"), open_, steps_of(t.get("plan")))}
                        for t in tried],
        "calls": [{"at": _at(c.called_at), "what": c.feature, "model": c.model, "checked": c.checked, "input_tokens": c.input_tokens,
                   "output_tokens": c.output_tokens, "seconds": c.seconds, "cost_usd": _money(c.cost_usd), "stop_reason": c.stop_reason,
                   "outcome": call_outcome(c.stop_reason, None, plan.state, turned_back[c.id]),
                   "sent": None if c.sent_sha256 is None else c.sent_sha256[:12], "run": None if c.run_id is None else str(c.run_id)}
                  for c in calls],
        "steps": [_step(step, open_) for step in plan.steps or []],
        "version": None if version is None else {
            "n": version.n, "made_by": version.made_by, "why": version.why if open_ else None, "changes": len(version.changes or []),
            "change_lines": [str(change) for change in version.changes or []] if open_ else [], "at": _at(version.created_at)},
        "job": None if job is None else {
            "id": str(job.id), "state": job.state, "stage": job.stage if open_ else None, "stages_done": len(job.stages_done or []),
            "stages": len(job.stages or []), "started_at": _at(job.started_at), "finished_at": _at(job.finished_at),
            "message": job.message if open_ else None},
    }


# ---------------------------------------------------------------------------------------------------------------------- the week

GUARDS = text("SELECT week_of, feature, asked, kept, set_aside, with_dropped, no_answer, capped, set_aside_pct, usual_set_aside_pct, flag "
              "FROM assistant_guards_by_feature WHERE week_of >= :since ORDER BY week_of DESC, asked DESC, feature")
COSTS = text("SELECT week_of, feature, calls, cost_usd, cost_per_call_usd, usual_cost_per_call_usd, models, flag "
             "FROM model_costs_by_feature WHERE week_of >= :since ORDER BY week_of DESC, cost_usd DESC NULLS LAST, feature")
PLANS = text("SELECT date_trunc('week', created_at AT TIME ZONE 'UTC')::date AS week_of, kind, state, count(*) AS plans "
             "FROM agent_plans WHERE created_at >= :since GROUP BY 1, 2, 3 ORDER BY 1 DESC, 2, 4 DESC")
REFUSED = text("SELECT reason, user_email, attempts -> -1 -> 'reasons' AS last_reasons, "
               "CASE WHEN jsonb_typeof(attempts -> -1 -> 'plan' -> 'steps') = 'array' "
               "THEN jsonb_array_length(attempts -> -1 -> 'plan' -> 'steps') ELSE 0 END AS last_steps "
               "FROM agent_plans WHERE state = 'refused' AND created_at >= :since AND reason IS NOT NULL")
UNCHECKED = text("SELECT date_trunc('week', called_at AT TIME ZONE 'UTC')::date AS week_of, model, count(*) AS calls "
                 "FROM model_calls WHERE checked IS FALSE AND called_at >= :since GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC")


def _rows(session: Session, query, since: dt.datetime) -> list[dict[str, Any]]:
    out = []
    for row in session.execute(query, {"since": since}).mappings():
        out.append({key: (value.isoformat() if isinstance(value, dt.date) else float(value) if isinstance(value, Decimal) else value)
                    for key, value in row.items()})
    return out


def weekly(engine: Engine, founders: Collection[str], *, now: dt.datetime | None = None) -> dict[str, Any]:
    """The last `WEEKS` weeks, this one counted (UTC, from Monday, as the views count them): the guards and the costs per feature as
    their views read them, plans per kind and state, the reasons plans were refused (a customer's as fixed lines, `reason_shown`), and
    the calls a model outside the checked list answered. Every table starts on the same Monday, so each shows whole weeks."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    monday = (now - dt.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    since = monday - dt.timedelta(weeks=WEEKS - 1)
    with Session(engine) as session:
        guards, costs = _rows(session, GUARDS, since.date()), _rows(session, COSTS, since.date())
        plans, unchecked = _rows(session, PLANS, since), _rows(session, UNCHECKED, since)
        refused: dict[str, int] = {}
        for reason, email, last_reasons, last_steps in session.execute(REFUSED, {"since": since}).all():
            _, open_ = who(email, founders, local=False)
            words = reason_shown(reason, "refused", last_reasons, last_steps or 0, open_)
            refused[words] = refused.get(words, 0) + 1
    reasons = [{"reason": r, "plans": n} for r, n in sorted(refused.items(), key=lambda pair: (-pair[1], pair[0]))[:10]]
    return {"since": since.date().isoformat(), "guards": guards, "costs": costs, "plans": plans, "refused": reasons, "unchecked": unchecked}
