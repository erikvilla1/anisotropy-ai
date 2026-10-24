"""A public stand-in for a coupon model (ADR-0042). Our models of the team's coupons stay on the founder's machine, so the tests
of what only those models had (an identity card, a [names] table, a mesh seeded by segment) read this instead: the IM7/8552
unnotched check's coupling spec, given all three. Its names and partitions are ours, not the team's."""

from anisotropy_fea import paths

BASE = paths.spec_path("unnotched-im7-8552-coupling").read_text(encoding="utf-8")
DESIGNATION = "IM7-UNT-L1"
TITLE = f'title = "{DESIGNATION}, unnotched tension: IM7/8552 [45/0/-45/90]s, coupled grips with reference nodes, 1 mm pull"'
CARD = f"""[coupon]
designation = "{DESIGNATION}"
standard = "none"
size_from = "the public IM7/8552 check fea/checks/unnotched-im7-8552/"
team_model = "not built yet"
test_data = "none"
"""
SEEDS = ("y_partitions = [56.0, 110.0, 140.0, 194.0]", "y_seeds = [28, 27, 10, 27, 28]")  # the tab lines and a gauge band; 2 mm rows, 3 mm in the band
NAMES = """[names]
part = "Strip"
instance = "Strip-1"
material = "IM7-8552-Lamina"
layup = "Layup-A"
section_set = "Layup-A-1"
"""


def public_coupon() -> str:
    title = next(line for line in BASE.splitlines() if line.startswith("title = "))
    for part in (title, "[geometry]", "ny = 125", "[output]"):
        assert BASE.count(part) == 1, f"the IM7/8552 coupling spec no longer holds one {part!r}"
    return (BASE.replace(title, TITLE).replace("[geometry]", CARD + "\n[geometry]").replace("ny = 125", "\n".join(SEEDS))
            .replace("[output]", NAMES + "\n[output]"))


PUBLIC_COUPON = public_coupon()
