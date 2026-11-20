"""What each call to the language model cost (ADR-0119): the tokens the API reported for it, by kind, and their price on the day.

Every call the assistant makes (ADR-0052) comes back with a `usage` block: the tokens read, the tokens written (the model's hidden
thinking included, which is billed as output though only the answer is returned), and the tokens read from or written to the
prompt cache. `measure` turns that block into a `ModelCall`, priced from the list below, and the API writes it as one row of the
`model_calls` table with who asked and the run it belongs to. Nothing here calls the model or computes a result.

The counts are the provider's own. They show what we were billed and when that changes; they cannot prove the hidden thinking count
is true (ADR-0119, Context).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# What a call is for: one name per thing the assistant does (assistant.py). A new one is a migration (the table's check).
FEATURES = (
    "explain_setup",  # words for the setup check of a coupon (ADR-0052)
    "explain_result",  # words for a coupon's result (ADR-0052)
    "explain_laminate",  # words for a laminate problem's answer (ADR-0060)
    "propose_changes",  # a chat message read into changes to the setup (ADR-0088, ADR-0101)
    "read_question",  # a question about a result read into a lookup on the page (ADR-0100)
    "answer_question",  # a "why" question answered in words from the fact sheet and the theory pages (ADR-0102)
    "choose_tools",  # the Abaqus round trip's steps chosen from a message (ADR-0094 part 8; a local command, never recorded)
)

# US dollars per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing.md read on PRICES_AS_OF:
# (input, cache write 5 minutes, cache write 1 hour, cache read, output). A model not listed is not priced: its row's cost is
# empty and the report counts it, so the list is brought up to date.
PRICES_AS_OF = "2026-11-19"
PRICES: dict[str, tuple[str, str, str, str, str]] = {
    "claude-fable-5-2": ("8", "10", "16", "0.20", "40"),
    "claude-opus-5-5": ("4", "5", "8", "0.20", "20"),
    "claude-opus-5": ("5", "6.25", "10", "0.50", "25"),
    "claude-opus-4-8": ("5", "6.25", "10", "0.50", "25"),
    "claude-sonnet-5-5": ("2", "2.50", "4", "0.10", "10"),
    "claude-sonnet-5": ("2", "2.50", "4", "0.20", "10"),
    "claude-haiku-5-5": ("0.10", "0.125", "0.20", "0.01", "0.50"),
}
# Claude Haiku 5.5 alone is priced by the prompt's length: over 100,000 tokens (cache reads and writes counted) a call pays these.
LONG_PROMPT_TOKENS = 100_000
LONG_PROMPT_PRICES: dict[str, tuple[str, str, str, str, str]] = {
    "claude-haiku-5-5": ("0.50", "0.625", "1", "0.05", "2.50"),
}
US_ONLY_FACTOR = Decimal("1.1")  # `inference_geo` "us": every price times 1.1; the default, global routing, is standard pricing
PER_TOKEN = Decimal(1_000_000)
CENT_FRACTION = Decimal("0.000001")  # costs are kept to a millionth of a dollar


@dataclass(frozen=True)
class Tokens:
    """One attempt's tokens by the price they pay."""

    model: str
    input: int
    cache_write_5m: int
    cache_write_1h: int
    cache_read: int
    output: int


@dataclass(frozen=True)
class ModelCall:
    """One call to the model as the API reported it, priced: the row the `model_calls` table keeps, less who asked and the run."""

    feature: str
    answered_at: dt.datetime
    model: str  # the model that answered, as the response names it
    effort: str | None
    input_tokens: int  # read at the input price (every attempt summed)
    output_tokens: int  # written at the output price, the hidden thinking included
    thinking_tokens: int | None  # the part of output_tokens that was hidden thinking, when the API reports it
    cache_read_tokens: int
    cache_write_tokens: int
    answer_characters: int  # the length of the answer we received: what the visible part of output_tokens wrote
    stop_reason: str | None
    seconds: float
    cost_usd: Decimal | None  # None when a model the call used is not in PRICES, or a speed the list does not price
    prices_as_of: str | None
    attempts: tuple[dict[str, Any], ...] | None = None  # each attempt's tokens when there was more than one (a refusal, then a fallback)


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _tokens(entry: Any, model: str) -> Tokens:
    """An attempt's tokens; the cache writes split by how long they are kept when the API says, else counted as 5-minute writes."""
    written = _int(getattr(entry, "cache_creation_input_tokens", 0))
    split = getattr(entry, "cache_creation", None)
    hour = min(_int(getattr(split, "ephemeral_1h_input_tokens", 0)), written) if split is not None else 0
    return Tokens(model=model, input=_int(getattr(entry, "input_tokens", 0)), cache_write_5m=written - hour, cache_write_1h=hour,
                  cache_read=_int(getattr(entry, "cache_read_input_tokens", 0)), output=_int(getattr(entry, "output_tokens", 0)))


def price(tokens: Tokens, us_only: bool = False) -> Decimal | None:
    """The attempt's cost in US dollars at the list's prices; None for a model the list does not hold."""
    prompt = tokens.input + tokens.cache_write_5m + tokens.cache_write_1h + tokens.cache_read
    row = LONG_PROMPT_PRICES.get(tokens.model) if prompt > LONG_PROMPT_TOKENS else None
    row = row or PRICES.get(tokens.model)
    if row is None:
        return None
    rates = [Decimal(rate) for rate in row]
    counts = (tokens.input, tokens.cache_write_5m, tokens.cache_write_1h, tokens.cache_read, tokens.output)
    cost = sum((Decimal(count) * rate for count, rate in zip(counts, rates)), Decimal(0)) / PER_TOKEN
    return cost * US_ONLY_FACTOR if us_only else cost


def measure(feature: str, asked_model: str, effort: str | None, response: Any, answer: str, seconds: float) -> ModelCall | None:
    """The call as its response reports it; None for a response with no usage block (a stand-in client in the tests).

    With several attempts (`usage.iterations`: a refusal, then the fallback model that answered), every attempt is counted at its own
    model's prices, and the top-level block, which covers only the attempt that answered, is not added again. Every token the API
    reports is priced, so a refusal before any output, which most refusal categories are not billed for, is counted as if it were."""
    if feature not in FEATURES:
        raise ValueError(f"unknown feature {feature!r}; it is one of {', '.join(FEATURES)}")
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    answered_by = str(getattr(response, "model", None) or asked_model)
    iterations = list(getattr(usage, "iterations", None) or [])
    attempts = [_tokens(entry, str(getattr(entry, "model", None) or asked_model)) for entry in iterations] or [_tokens(usage, answered_by)]
    us_only = str(getattr(usage, "inference_geo", "") or "").lower() == "us"
    fast = str(getattr(usage, "speed", "") or "").lower() == "fast"  # fast mode is priced apart and not on this list
    costs = [price(attempt, us_only) for attempt in attempts]
    cost = None if fast or any(c is None for c in costs) else sum(costs, Decimal(0)).quantize(CENT_FRACTION)
    details = getattr(usage, "output_tokens_details", None)
    thinking = getattr(details, "thinking_tokens", None) if details is not None else None
    return ModelCall(
        feature=feature, answered_at=dt.datetime.now(dt.timezone.utc), model=answered_by, effort=effort,
        input_tokens=sum(a.input for a in attempts), output_tokens=sum(a.output for a in attempts),
        thinking_tokens=_int(thinking) if thinking is not None else None,
        cache_read_tokens=sum(a.cache_read for a in attempts), cache_write_tokens=sum(a.cache_write_5m + a.cache_write_1h for a in attempts),
        answer_characters=len(answer), stop_reason=getattr(response, "stop_reason", None), seconds=round(seconds, 3),
        cost_usd=cost, prices_as_of=PRICES_AS_OF if cost is not None else None,
        attempts=tuple({"type": str(getattr(entry, "type", "message")), "model": a.model, "input_tokens": a.input, "output_tokens": a.output,
                        "cache_read_tokens": a.cache_read, "cache_write_tokens": a.cache_write_5m + a.cache_write_1h}
                       for entry, a in zip(iterations, attempts)) if len(iterations) > 1 else None,
    )
