"""What both halves of the real-model check share (ADR-0121, check 2): the store of the model's answers, keyed by the exact request, so a
request answered once is never paid for again; the prices, so a run stops before its budget is spent; and the sending, in one batch at
half price or one by one. Imported by `scripts/assistant-live.py` (the API's readers, the judge, the report) and
`scripts/assistant-live-mcp.py` (an MCP client on our tools)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

# Dollars per million tokens, input and output (the claude-api reference, read 2026-11-19). A batch costs half of each. A cache read
# costs a twentieth of the input price on the 5.5 models named here, a tenth elsewhere; a cache write a quarter more.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
UNKNOWN_PRICE = (15.0, 75.0)  # a model not listed is budgeted as an expensive one
CACHE_READ = {"claude-opus-5-5": 0.05, "claude-sonnet-5-5": 0.05}
CACHE_WRITE = 1.25
CHARS_PER_TOKEN = 3.0  # an estimate on the high side, for the budget only
OUTPUT_GUESS = 800  # tokens an answer is budgeted at, or its max_tokens when lower


class OverBudget(RuntimeError):
    """The requests still to send would pass the run's budget; nothing was sent."""


def key_of(params: dict[str, Any]) -> str:
    """The request's name in the store: any change to the model, the instructions, the schema or the words gives a new one."""
    return hashlib.sha256(json.dumps(params, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


class Store:
    """The model's answers, one file per request under `folder/answers/`, kept between runs (the workflow keeps the folder)."""

    def __init__(self, folder: Path):
        self.folder = folder / "answers"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.used: set[str] = set()  # every request this run needed
        self.sent: set[str] = set()  # those it sent to the model

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.folder / f"{key}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def put(self, key: str, answer: dict[str, Any]) -> None:
        (self.folder / f"{key}.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")


class Spend:
    """What the run has spent, from the usage each answer reports, against its budget."""

    def __init__(self, budget: float, spent: float = 0.0):
        self.budget = budget
        self.dollars = spent

    @staticmethod
    def estimate(params: dict[str, Any], batch: bool) -> float:
        price_in, price_out = PRICES.get(params["model"], UNKNOWN_PRICE)
        tokens_in = len(json.dumps(params, ensure_ascii=False)) / CHARS_PER_TOKEN
        tokens_out = min(int(params.get("max_tokens", OUTPUT_GUESS)), OUTPUT_GUESS)
        return (tokens_in * price_in + tokens_out * price_out) / 1e6 * (0.5 if batch else 1.0)

    def add(self, model: str, usage: dict[str, Any], batch: bool) -> None:
        price_in, price_out = PRICES.get(model, UNKNOWN_PRICE)
        dollars = ((usage.get("input_tokens") or 0) * price_in + (usage.get("output_tokens") or 0) * price_out
                   + (usage.get("cache_read_input_tokens") or 0) * price_in * CACHE_READ.get(model, 0.1)
                   + (usage.get("cache_creation_input_tokens") or 0) * price_in * CACHE_WRITE) / 1e6
        self.dollars += dollars * (0.5 if batch else 1.0)


def for_sending(params: dict[str, Any]) -> dict[str, Any]:
    """The request as this run sends it: the model, instructions, schema and words the site sends, with the instructions marked for the
    prompt cache (they are the same in every request of a reader, so after the first they are read at a twentieth of the price), and
    without the site's fallback to another model on a decline, which a batch cannot carry. The store keys the site's own request."""
    sent = {key: value for key, value in params.items() if key not in ("betas", "fallbacks")}
    if isinstance(sent.get("system"), str):
        sent["system"] = [{"type": "text", "text": sent["system"], "cache_control": {"type": "ephemeral"}}]
    return sent


def kept(message: Any) -> dict[str, Any]:
    """An answer as the store keeps it: the content blocks, why it stopped and the tokens it used."""
    return {"model": message.model, "stop_reason": message.stop_reason, "content": [block.model_dump(mode="json", exclude_none=True) for block in message.content],
            "usage": message.usage.model_dump(mode="json")}


def _attributes(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _attributes(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_attributes(item) for item in value]
    return value


def reply(answer: dict[str, Any]) -> SimpleNamespace:
    """A kept answer in the shape the SDK returns it, read by attribute all the way down (`content[i].text`, `usage.cache_creation`),
    as the API's readers and its record of each call's cost (ADR-0120) read a response. A tool call's `input` stays a dict."""
    content = [SimpleNamespace(**{key: (item if key == "input" else _attributes(item)) for key, item in block.items()}) for block in answer["content"]]
    return SimpleNamespace(model=answer["model"], stop_reason=answer["stop_reason"], content=content, usage=_attributes(answer["usage"]))


def resolve(client: Any, wanted: dict[str, dict[str, Any]], store: Store, spend: Spend, *, batch: bool, log: Callable[[str], None] = print,
            poll: float = 20.0, wait: float = 3 * 3600) -> None:
    """Asks the model every request in `wanted` the store has no answer to, and keeps each answer. Nothing is sent when the estimate
    would pass the budget. A request the model did not answer is not kept, so the next run asks it again."""
    store.used.update(wanted)
    missing = {key: params for key, params in wanted.items() if store.get(key) is None}
    if not missing:
        return
    batch = batch and len(missing) > 1
    estimate = sum(Spend.estimate(params, batch) for params in missing.values())
    if spend.dollars + estimate > spend.budget:
        raise OverBudget(f"{len(missing)} new requests would cost about ${estimate:.2f}, with ${spend.dollars:.2f} spent and a budget of "
                         f"${spend.budget:.2f}: raise the budget or run fewer features")
    store.sent.update(missing)
    import anthropic  # here, so the module loads where the SDK is not installed

    if batch:
        try:
            created = client.messages.batches.create(requests=[{"custom_id": key, "params": for_sending(p)} for key, p in missing.items()])
        except anthropic.BadRequestError as exc:
            log(f"The batch was refused ({exc.message}); sending the requests one by one.")
        else:
            log(f"Batch {created.id}: {len(missing)} requests at half price; checking every {poll:.0f} s.")
            deadline = time.monotonic() + wait
            while client.messages.batches.retrieve(created.id).processing_status != "ended":
                if time.monotonic() > deadline:
                    client.messages.batches.cancel(created.id)
                    raise RuntimeError(f"batch {created.id} did not end in {wait / 3600:.0f} h; it was cancelled")
                time.sleep(poll)
            for result in client.messages.batches.results(created.id):
                if result.result.type == "succeeded":
                    message = result.result.message
                    spend.add(missing[result.custom_id]["model"], message.usage.model_dump(mode="json"), batch=True)
                    store.put(result.custom_id, kept(message))
                else:
                    log(f"A request of the batch came back {result.result.type}; it is asked again next run.")
            return
    for key, params in missing.items():
        try:
            message = client.messages.create(**for_sending(params))
        except anthropic.APIStatusError as exc:
            log(f"A request was refused ({exc.status_code}: {exc.message}); it is asked again next run.")
            continue
        spend.add(params["model"], message.usage.model_dump(mode="json"), batch=False)
        store.put(key, kept(message))
