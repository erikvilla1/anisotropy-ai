"""Design rules of a stack: the checks a designer makes on the stacking before any load (ADR-0123).

Four rules, each judged on the plies alone:

- the 10 % rule: each of the 0, +45, -45 and 90 degree directions holds at least a share of the plies,
  so the laminate is carried by its fibers in every direction (MIL-HDBK-17-3F, Volume 3);
- plies of one angle in a row: no more than a number of plies of the same angle next to each other,
  counting across the middle of a solid laminate but not across a core;
- balance: as many plies at -theta as at +theta, so stretching does not shear the laminate (A16 = A26 = 0);
- symmetry: the stack mirrors about its middle, so stretching does not bend it (B = 0).

A rule not met is a warning, not a failure: nothing else in the engine reads these results, and no
number of an analysis changes with them. The limits are the designer's to set (`RuleLimits`); the
defaults are common practice, and thicker plies usually call for fewer of one angle in a row. Plies are
counted, not weighed by thickness, as the rules are stated. Balance and symmetry are the stack's own
facts from `summary.py`, so material and thickness count there as well as the angle.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .laminate import Ply
from .summary import ANGLE_TOLERANCE_DEG, RELATIVE_TOLERANCE, is_balanced, is_symmetric

RuleName = Literal["ten_percent", "in_a_row", "balance", "symmetry"]
RULES: tuple[RuleName, ...] = ("ten_percent", "in_a_row", "balance", "symmetry")
DIRECTIONS = (0.0, 45.0, -45.0, 90.0)  # the four directions of the 10 % rule
SOURCES: dict[RuleName, str] = {
    "ten_percent": "MIL-HDBK-17-3F, Volume 3: a laminate carried by its fibers in every direction",
    "in_a_row": "Common practice: plies of one angle together crack apart more easily; thicker plies call for fewer",
    "balance": "Laminate theory: a balanced laminate does not shear when stretched (A16 = A26 = 0)",
    "symmetry": "Laminate theory: a symmetric laminate does not bend when stretched (B = 0)",
}
MINUS = "−"


class RuleLimits(BaseModel):
    """The limits of the rules: the least share of the plies in each of the four directions, and the most plies of one angle in a row."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    min_share: float = Field(default=0.10, gt=0, le=0.25)  # four directions cannot each hold more than a quarter
    max_in_a_row: int = Field(default=4, ge=1, strict=True)


@dataclass(frozen=True)
class RuleCheck:
    """One rule judged on one stack: whether it is met, one plain sentence that says what was found, where the rule comes from, and the
    numbers behind the sentence (`detail`): for the 10 % rule each direction's share of the plies; for plies in a row the longest run,
    its angle and its first and last ply counted from the first ply given; for balance the plies at each off-axis angle; for symmetry
    the first ply that does not mirror its partner."""

    rule: RuleName
    met: bool
    words: str
    source: str
    detail: dict = field(default_factory=dict)


def _direction(angle_deg: float) -> float:
    """The fiber direction between -90 (exclusive) and 90 degrees: a fiber at theta is the fiber at theta + 180."""
    folded = (angle_deg + 90.0) % 180.0 - 90.0
    if abs(folded + 90.0) <= ANGLE_TOLERANCE_DEG:
        return 90.0
    for exact in DIRECTIONS:
        if abs(folded - exact) <= ANGLE_TOLERANCE_DEG:
            return exact
    return folded


def angle_words(angle_deg: float) -> str:
    """An angle as a page prints it: 0°, +45°, −45°, 90°."""
    direction = _direction(angle_deg)
    if direction in (0.0, 90.0):
        return f"{direction:g}°"
    return f"{'+' if direction > 0 else MINUS}{abs(direction):g}°"


def _percent(share: float) -> str:
    return f"{100 * share:.1f}".rstrip("0").rstrip(".") + " %"


def _and(items: Sequence[str], word: str = "and") -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {word} " + items[-1]


def _or(items: Sequence[str]) -> str:
    return _and(items, "or")


def ten_percent_rule(plies: Sequence[Ply], limits: RuleLimits) -> RuleCheck:
    """Each of 0, +45, -45 and 90 degrees holds at least `min_share` of the plies; a ply at any other angle counts only in the total."""
    directions = [_direction(p.angle_deg) for p in plies]
    shares = {d: sum(1 for x in directions if x == d) / len(plies) for d in DIRECTIONS}
    none = [angle_words(d) for d, share in shares.items() if share == 0]
    low = [f"{_percent(share)} at {angle_words(d)}" for d, share in shares.items() if 0 < share < limits.min_share - RELATIVE_TOLERANCE]
    found = ", and ".join(([f"no plies at {_or(none)}"] if none else []) + ([f"only {_and(low)}"] if low else []))
    words = f"Every direction has at least {_percent(limits.min_share)} of the plies." if not found else \
        f"{found[0].upper()}{found[1:]}: each of 0°, +45°, {MINUS}45° and 90° should have at least {_percent(limits.min_share)}."
    return RuleCheck("ten_percent", not found, words, SOURCES["ten_percent"], {"shares": {f"{d:g}": share for d, share in shares.items()}, "min_share": limits.min_share})


def in_a_row_rule(plies: Sequence[Ply], limits: RuleLimits, core_after: int | None = None) -> RuleCheck:
    """No more than `max_in_a_row` plies of the same angle next to each other. A core after ply `core_after` separates its neighbours."""
    directions = [_direction(p.angle_deg) for p in plies]
    longest, first = 1, 0
    start = 0
    for k in range(1, len(directions) + 1):
        ends = k == len(directions) or directions[k] != directions[k - 1] or k == core_after
        if ends:
            if k - start > longest:
                longest, first = k - start, start
            start = k
    angle = angle_words(directions[first])
    detail = {"longest": longest, "angle": directions[first], "first": first + 1, "last": first + longest, "plies": len(plies),
              "max_in_a_row": limits.max_in_a_row}
    if longest <= limits.max_in_a_row:
        words = (f"No two plies of one angle next to each other; the limit is {limits.max_in_a_row}." if longest == 1
                 else f"At most {longest} plies of one angle in a row; the limit is {limits.max_in_a_row}.")
        return RuleCheck("in_a_row", True, words, SOURCES["in_a_row"], detail)
    words = f"{longest} plies at {angle} in a row (plies {first + 1} to {first + longest} of {len(plies)}); at most {limits.max_in_a_row}."
    return RuleCheck("in_a_row", False, words, SOURCES["in_a_row"], detail)


def balance_rule(plies: Sequence[Ply]) -> RuleCheck:
    """As many plies at -theta as at +theta for every off-axis theta, of the same material and thickness (`summary.is_balanced`)."""
    counts: dict[float, int] = {}
    for p in plies:
        direction = _direction(p.angle_deg)
        if direction not in (0.0, 90.0):
            counts[direction] = counts.get(direction, 0) + 1
    detail = {"plies": {f"{d:g}": n for d, n in sorted(counts.items(), key=lambda item: (abs(item[0]), -item[0]))}}
    if is_balanced(list(plies)):
        words = "Balanced: no plies off 0° and 90°." if not counts else "Balanced: every angled ply has a partner at the opposite angle."
        return RuleCheck("balance", True, words, SOURCES["balance"], detail)
    unpaired = []
    for size in sorted({abs(d) for d in counts}):
        plus, minus = counts.get(size, 0), counts.get(-size, 0)
        if plus != minus:
            unpaired.append(f"{plus} {'ply' if plus == 1 else 'plies'} at {angle_words(size)} and {minus} at {angle_words(-size)}")
    words = f"Not balanced: {'; '.join(unpaired)}." if unpaired \
        else "Not balanced: plies at opposite angles differ in material or thickness."
    return RuleCheck("balance", False, words, SOURCES["balance"], detail)


def symmetry_rule(plies: Sequence[Ply], core_after: int | None = None) -> RuleCheck:
    """The stack mirrors about its middle (`summary.is_symmetric`), and a core sits in the middle."""
    n = len(plies)
    if core_after is not None and 2 * core_after != n:
        words = f"Not symmetric: the core has {core_after} {'ply' if core_after == 1 else 'plies'} on one side and {n - core_after} on the other."
        return RuleCheck("symmetry", False, words, SOURCES["symmetry"], {"core_after": core_after, "plies": n})
    if is_symmetric(list(plies)):
        words = "Symmetric about the core." if core_after is not None else "Symmetric about the middle."
        return RuleCheck("symmetry", True, words, SOURCES["symmetry"], {"plies": n})
    k = next(k for k in range(n // 2) if not is_symmetric([plies[k], plies[n - 1 - k]]))  # an odd count's middle ply mirrors itself
    p, q = plies[k], plies[n - 1 - k]
    same_angle = _direction(p.angle_deg) == _direction(q.angle_deg)
    words = f"Not symmetric: ply {k + 1} and its mirror, ply {n - k}, differ in material or thickness." if same_angle \
        else f"Not symmetric: ply {k + 1} is at {angle_words(p.angle_deg)} and its mirror, ply {n - k}, at {angle_words(q.angle_deg)}."
    return RuleCheck("symmetry", False, words, SOURCES["symmetry"], {"ply": k + 1, "mirror": n - k, "plies": n})


def layup_rules(plies: Sequence[Ply], limits: RuleLimits | None = None, core_after: int | None = None) -> tuple[RuleCheck, ...]:
    """The four rules on a stack listed from one face to the other, with a core after ply `core_after` when there is one."""
    if not plies:
        raise ValueError("A stack needs at least one ply for its design rules")
    if core_after is not None and not 0 < core_after < len(plies):
        raise ValueError("The core must have plies on both sides")
    limits = RuleLimits() if limits is None else limits
    return (ten_percent_rule(plies, limits), in_a_row_rule(plies, limits, core_after), balance_rule(plies), symmetry_rule(plies, core_after))
