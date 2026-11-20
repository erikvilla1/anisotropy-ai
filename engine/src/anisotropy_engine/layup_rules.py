"""Design rules of a stack: the checks a designer makes on the stacking before any load (ADR-0123).

Four rules, each judged on the plies alone:

- the 10 % rule: each of the 0, +45, -45 and 90 degree directions holds at least a share of the plies,
  so the laminate is carried by its fibers in every direction (MIL-HDBK-17-3F, Volume 3);
- plies of one angle in a row: no more than a number of plies of the same angle next to each other,
  counting across the middle of a solid laminate but not across a core;
- balance: as many plies at -theta as at +theta, so stretching does not shear the laminate (A16 = A26 = 0);
- symmetry: the stack mirrors about its middle, so stretching does not bend it (B = 0).

Where a part's stack changes along the span (ADR-0125), the change is a ply drop, judged by three more rules on the two stacks:

- plies dropped at one place: no more than a number of plies end at one place, both halves counted;
- the ply drop ratio: the plies that end need a run-out of the ratio times the change of thickness, and it must fit in the thicker side;
- the outside ply over the drop: the thinner stack is the thicker one with plies taken out, and the outside ply of each face runs on.

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

RuleName = Literal["ten_percent", "in_a_row", "balance", "symmetry", "drop_count", "drop_ratio", "drop_cover"]
RULES: tuple[RuleName, ...] = ("ten_percent", "in_a_row", "balance", "symmetry")  # the rules of one stack
DROP_RULES: tuple[RuleName, ...] = ("drop_count", "drop_ratio", "drop_cover")  # the rules of a change of stack
DIRECTIONS = (0.0, 45.0, -45.0, 90.0)  # the four directions of the 10 % rule
SOURCES: dict[RuleName, str] = {
    "ten_percent": "MIL-HDBK-17-3F, Volume 3: a laminate carried by its fibers in every direction",
    "in_a_row": "Common practice: plies of one angle together crack apart more easily; thicker plies call for fewer",
    "balance": "Laminate theory: a balanced laminate does not shear when stretched (A16 = A26 = 0)",
    "symmetry": "Laminate theory: a symmetric laminate does not bend when stretched (B = 0)",
    "drop_count": "Common practice: plies ending together leave a step where the plies start to part; end a few at a time",
    "drop_ratio": "Common practice: a change of thickness tapered over many times its height carries the load past it smoothly",
    "drop_cover": "Common practice: a ply that runs on over the ends of the dropped plies holds them down",
}
MINUS = "−"


class RuleLimits(BaseModel):
    """The limits of the rules: the least share of the plies in each of the four directions, the most plies of one angle in a row,
    the run-out of a ply drop per unit of the thickness it drops, and the most plies that end at one place, both halves counted."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    min_share: float = Field(default=0.10, gt=0, le=0.25)  # four directions cannot each hold more than a quarter
    max_in_a_row: int = Field(default=4, ge=1, strict=True)
    drop_ratio: float = Field(default=20.0, ge=1, le=200)  # run-out length over thickness dropped: 20 to 1
    max_dropped: int = Field(default=2, ge=1, strict=True)  # a symmetric drop ends a ply in each half: 2 is one each side


@dataclass(frozen=True)
class RuleCheck:
    """One rule judged on one stack: whether it is met, one plain sentence that says what was found, where the rule comes from, and the
    numbers behind the sentence (`detail`): for the 10 % rule each direction's share of the plies; for plies in a row the longest run,
    its angle and its first and last ply counted from the first ply given; for balance the plies at each off-axis angle; for symmetry
    the first ply that does not mirror its partner; for a ply drop the plies that end, the run-out they need and the room for it, and
    which plies of the thicker half stack end."""

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


def _length(value_m: float, unit: tuple[float, str]) -> str:
    value = value_m / unit[0]
    return f"{value:,.0f} {unit[1]}" if value >= 100 else f"{value:.3g} {unit[1]}"


def _kept(thick: Sequence[float], thin: Sequence[float]) -> list[int] | None:
    """The plies of the thicker half stack that the thinner one keeps, matched in order from the outside, by fiber direction; None
    when the thinner stack is not the thicker one with plies taken out."""
    kept, k = [], 0
    for angle in thin:
        direction = _direction(angle)
        while k < len(thick) and _direction(thick[k]) != direction:
            k += 1
        if k == len(thick):
            return None
        kept.append(k)
        k += 1
    return kept


def ply_drop_rules(inboard: Sequence[float], outboard: Sequence[float], ply_thickness_m: float, room_m: tuple[float, float], where: str,
                   limits: RuleLimits | None = None, unit: tuple[float, str] = (1e-3, "mm")) -> tuple[RuleCheck, RuleCheck, RuleCheck]:
    """The three rules of a change of half stack from `inboard` to `outboard` (outside ply first) at `where` (words: "40 % of the
    span"). `room_m` is how far each side runs from the change before its stack changes again, inboard and outboard, metres; the
    run-out of the plies that end lies on the thicker side. Lengths in the words are in `unit` (metres per unit, its label)."""
    limits = RuleLimits() if limits is None else limits
    if not inboard or not outboard:
        raise ValueError("A ply drop needs a stack on each side")
    thicker_inboard = len(inboard) >= len(outboard)
    thick, thin = (inboard, outboard) if thicker_inboard else (outboard, inboard)
    room = room_m[0] if thicker_inboard else room_m[1]
    half = len(thick) - len(thin)
    dropped = 2 * half  # both halves of the symmetric laminate
    kept = _kept(thick, thin)
    ending = [] if kept is None else [k + 1 for k in range(len(thick)) if k not in kept]
    side = "inboard" if thicker_inboard else "outboard"

    detail = {"dropped": dropped, "max_dropped": limits.max_dropped}
    if dropped == 0:
        count = RuleCheck("drop_count", True, f"No plies end at {where}: the stack keeps its number of plies.", SOURCES["drop_count"], detail)
    elif dropped <= limits.max_dropped:
        count = RuleCheck("drop_count", True, f"{dropped} plies end at {where}, {half} each side of the middle; at most {limits.max_dropped} "
                          "at one place.", SOURCES["drop_count"], detail)
    else:
        count = RuleCheck("drop_count", False, f"{dropped} plies end at {where}; at most {limits.max_dropped} at one place: end the others "
                          "a little further along.", SOURCES["drop_count"], detail)

    change = dropped * ply_thickness_m
    run_out = limits.drop_ratio * change
    detail = {"thickness_change_m": change, "run_out_m": run_out, "room_m": room, "drop_ratio": limits.drop_ratio, "thicker": side}
    ratio = f"{limits.drop_ratio:g} to 1"
    if dropped == 0:
        taper = RuleCheck("drop_ratio", True, f"Nothing tapers at {where}: no plies end there.", SOURCES["drop_ratio"], detail)
    elif run_out <= room:
        taper = RuleCheck("drop_ratio", True, f"The plies ending at {where} need {_length(run_out, unit)} of run-out at {ratio}; the thicker side "
                          f"runs {_length(room, unit)}.", SOURCES["drop_ratio"], detail)
    else:
        taper = RuleCheck("drop_ratio", False, f"The plies ending at {where} need {_length(run_out, unit)} of run-out at {ratio}, more than the "
                          f"{_length(room, unit)} of the thicker side.", SOURCES["drop_ratio"], detail)

    detail = {"ending": ending, "thicker": side, "pure": kept is not None}
    if kept is None:
        cover = RuleCheck("drop_cover", False, f"At {where} the plies change angle or order, not only end: the thinner stack should be the "
                          "thicker one with plies taken out.", SOURCES["drop_cover"], detail)
    elif dropped == 0:
        cover = RuleCheck("drop_cover", True, f"The same plies run on past {where}.", SOURCES["drop_cover"], detail)
    elif 1 in ending:
        cover = RuleCheck("drop_cover", False, f"The outside ply ends at {where}: keep a ply running on over the ends of the others.",
                          SOURCES["drop_cover"], detail)
    else:
        plies = f"ply {ending[0]}" if half == 1 else f"plies {_and([str(k) for k in ending])}"
        cover = RuleCheck("drop_cover", True, f"The outside ply runs on over the plies ending at {where} ({plies} of the {side} half "
                          "stack).", SOURCES["drop_cover"], detail)
    return count, taper, cover
