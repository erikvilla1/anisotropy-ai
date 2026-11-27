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
the answers turned back, the changes, the job's messages). Such a person is named by a tag that tells their rows apart and names
nobody. A row with no email is a robot's (a service token, ADR-0138) or, on a machine with no sign-in, its one user's.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from collections.abc import Collection
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from .records import AgentPlanRow, JobRow, ModelCallRow, ModelVersionRow, Run

HIDDEN = "a customer's words, not shown"  # in place of what a person who is not a founder wrote
QUOTED = re.compile(r"“[^”]*”")  # a refusal's reason quotes the sentence's words between curly quotes
FEED_MAX = 200
PLAN_STEP_PUBLIC = ("n", "role", "tool", "state")  # what a step shows whoever's plan it is
WEEKS = 8


# ----------------------------------------------------------------------------------------------------------------- who a row is

def tag_of(email: str) -> str:
    """A short tag for a person who is not a founder: the same person, the same tag; it names nobody."""
    return "customer " + hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:6]


def who(email: str | None, founders: Collection[str], *, local: bool) -> tuple[str, bool]:
    """Who a row is for, as the page names them, and whether what they wrote may be shown: a founder's email and theirs in full; a
    robot or the machine's one user with no email, in full; anyone else as a tag, without their words."""
    if email is None:
        return ("this machine" if local else "robot"), True
    if email.strip().lower() in founders:
        return email, True
    return tag_of(email), False


def unquoted(reason: str | None) -> str | None:
    """A refusal's reason with the sentence's words it quotes taken out, for a person whose words are not shown."""
    return None if reason is None else QUOTED.sub("“…”", reason)


# ------------------------------------------------------------------------------------------------------------- how a call ended

def call_outcome(stop_reason: str | None, response: dict[str, Any] | None, plan_state: str | None) -> str:
    """How a call to the model ended, in the page's words: declined or cut short by the model; else the plan's state when the call was
    a plan's; else what became of the words from the run record's answer (ADR-0139's reading): set aside by a guard, partly dropped,
    kept, or not used."""
    if stop_reason == "refusal":
        return "declined"
    if stop_reason == "max_tokens":
        return "cut short"
    if plan_state is not None:
        return plan_state
    response = response or {}
    if response.get("withheld") is True:
        return "set aside"
    dropped = response.get("dropped")
    if isinstance(dropped, list) and dropped:
        return "partly dropped"
    return "kept" if response.get("model") else "not used"


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _at(value: dt.datetime | None) -> str | None:
    return None if value is None else value.astimezone(dt.timezone.utc).isoformat()


# ------------------------------------------------------------------------------------------------------------------------- the feed

def activity(engine: Engine, founders: Collection[str], *, local: bool, limit: int = 50, before: dt.datetime | None = None,
             since: dt.datetime | None = None) -> list[dict[str, Any]]:
    """The newest events, at most `limit` of them: calls, plans and approvals, merged by time. `before` pages back; `since` reads only
    what came after it (the page's refresh)."""
    limit = max(1, min(limit, FEED_MAX))
    with Session(engine) as session:
        calls_q = select(ModelCallRow).order_by(ModelCallRow.called_at.desc()).limit(limit)
        plans_q = select(AgentPlanRow).order_by(AgentPlanRow.created_at.desc()).limit(limit)
        approvals_q = (select(AgentPlanRow).where(AgentPlanRow.approved_at.is_not(None))
                       .order_by(AgentPlanRow.approved_at.desc()).limit(limit))
        if before is not None:
            calls_q = calls_q.where(ModelCallRow.called_at < before)
            plans_q = plans_q.where(AgentPlanRow.created_at < before)
            approvals_q = approvals_q.where(AgentPlanRow.approved_at < before)
        if since is not None:
            calls_q = calls_q.where(ModelCallRow.called_at > since)
            plans_q = plans_q.where(AgentPlanRow.created_at > since)
            approvals_q = approvals_q.where(AgentPlanRow.approved_at > since)
        calls = list(session.scalars(calls_q))
        plans = list(session.scalars(plans_q))
        approvals = list(session.scalars(approvals_q))
        run_ids = {c.run_id for c in calls if c.run_id is not None}
        answers = dict(session.execute(select(Run.id, Run.response).where(Run.id.in_(run_ids))).all()) if run_ids else {}
        plan_ids = {c.plan_id for c in calls if c.plan_id is not None}
        states = dict(session.execute(select(AgentPlanRow.id, AgentPlanRow.state).where(AgentPlanRow.id.in_(plan_ids))).all()) if plan_ids else {}

    events: list[tuple[dt.datetime, dict[str, Any]]] = []
    for c in calls:
        name, open_ = who(c.user_email, founders, local=local)
        events.append((c.called_at, {
            "kind": "call", "at": _at(c.called_at), "who": name, "words_shown": open_, "actor": c.actor, "what": c.feature,
            "model": c.model, "checked": c.checked, "outcome": call_outcome(c.stop_reason, answers.get(c.run_id), states.get(c.plan_id)),
            "seconds": c.seconds, "cost_usd": _money(c.cost_usd), "plan": None if c.plan_id is None else str(c.plan_id),
            "run": None if c.run_id is None else str(c.run_id), "ask": None}))
    for p in plans:
        name, open_ = who(p.user_email, founders, local=local)
        events.append((p.created_at, {
            "kind": "plan", "at": _at(p.created_at), "who": name, "words_shown": open_, "actor": p.actor, "what": f"plan on a {p.kind}",
            "model": p.model, "checked": None, "outcome": p.state, "seconds": None, "cost_usd": None, "plan": str(p.id), "run": None,
            "ask": p.ask if open_ else HIDDEN}))
    for p in approvals:
        name, open_ = who(p.user_email, founders, local=local)
        events.append((p.approved_at, {
            "kind": "approval", "at": _at(p.approved_at), "who": name, "words_shown": open_, "actor": p.actor, "what": "approve",
            "model": None, "checked": None, "outcome": p.state, "seconds": None, "cost_usd": None, "plan": str(p.id), "run": None,
            "ask": p.ask if open_ else HIDDEN}))
    events.sort(key=lambda pair: pair[0], reverse=True)
    return [event for _, event in events[:limit]]


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
        calls = list(session.scalars(select(ModelCallRow).where(ModelCallRow.plan_id == plan_id).order_by(ModelCallRow.called_at)))
        version = (session.get(ModelVersionRow, (plan.project_id, plan.version_n))
                   if plan.project_id is not None and plan.version_n is not None else None)
        job = None
        if plan.job_id:
            try:
                job = session.get(JobRow, uuid.UUID(plan.job_id))
            except ValueError:
                job = None
    name, open_ = who(plan.user_email, founders, local=local)
    tried = plan.attempts or []
    return {
        "id": str(plan.id), "kind": plan.kind, "who": name, "words_shown": open_, "actor": plan.actor, "state": plan.state,
        "ask": plan.ask if open_ else HIDDEN, "question": plan.question if open_ else None,
        "reason": plan.reason if open_ else unquoted(plan.reason),
        "unread": len(plan.unread or []), "writer": plan.writer, "model": plan.model,
        "created_at": _at(plan.created_at), "approved_at": _at(plan.approved_at), "updated_at": _at(plan.updated_at),
        "turned_back": [{"plan": t.get("plan") if open_ else None,
                         "reasons": list(t.get("reasons") or []) if open_ else [unquoted(r) for r in t.get("reasons") or []]} for t in tried],
        "calls": [{"at": _at(c.called_at), "what": c.feature, "model": c.model, "checked": c.checked, "input_tokens": c.input_tokens,
                   "output_tokens": c.output_tokens, "seconds": c.seconds, "cost_usd": _money(c.cost_usd), "stop_reason": c.stop_reason,
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
REFUSED = text("SELECT reason, user_email FROM agent_plans WHERE state = 'refused' AND created_at >= :since AND reason IS NOT NULL")
UNCHECKED = text("SELECT date_trunc('week', called_at AT TIME ZONE 'UTC')::date AS week_of, model, count(*) AS calls "
                 "FROM model_calls WHERE checked IS FALSE AND called_at >= :since GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC")


def _rows(session: Session, query, since: dt.datetime) -> list[dict[str, Any]]:
    out = []
    for row in session.execute(query, {"since": since}).mappings():
        out.append({key: (value.isoformat() if isinstance(value, dt.date) else float(value) if isinstance(value, Decimal) else value)
                    for key, value in row.items()})
    return out


def weekly(engine: Engine, founders: Collection[str], *, now: dt.datetime | None = None) -> dict[str, Any]:
    """The last `WEEKS` weeks: the guards and the costs per feature as their views read them, plans per kind and state, the reasons
    plans were refused (a customer's quoted words taken out), and the calls a model outside the checked list answered."""
    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(weeks=WEEKS)).replace(hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as session:
        guards, costs = _rows(session, GUARDS, since.date()), _rows(session, COSTS, since.date())
        plans, unchecked = _rows(session, PLANS, since), _rows(session, UNCHECKED, since)
        refused: dict[str, int] = {}
        for reason, email in session.execute(REFUSED, {"since": since}).all():
            _, open_ = who(email, founders, local=False)
            words = reason if open_ else unquoted(reason)
            refused[words] = refused.get(words, 0) + 1
    reasons = [{"reason": r, "plans": n} for r, n in sorted(refused.items(), key=lambda pair: (-pair[1], pair[0]))[:10]]
    return {"since": since.date().isoformat(), "guards": guards, "costs": costs, "plans": plans, "refused": reasons, "unchecked": unchecked}
