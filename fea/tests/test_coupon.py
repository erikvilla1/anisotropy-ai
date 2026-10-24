"""The coupon's identity card (ADR-0038): every model names its coupon, and a code in a name means one thing everywhere. The
coupon models are local (ADR-0042), so the folder checks run over the coupons on this machine (none on CI) and the card's own
rules over the public stand-in."""

import pytest

from public_coupon import DESIGNATION, PUBLIC_COUPON

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import DESIGNATION as DESIGNATION_RULE, SpecError, coupon_card, full_angles, load_spec, parse_spec, to_si
from anisotropy_fea.write_abaqus import write_abaqus

DESIGNATION_LINE = f'designation = "{DESIGNATION}"'
TITLE_START = f'title = "{DESIGNATION}, unnotched tension: '


def model_specs() -> dict[str, list]:
    """Every spec of every coupon model on this machine, by folder."""
    return {d.name: sorted(d.glob("*.toml")) for d in paths.model_dirs()}


def test_every_model_names_its_coupon_once():
    designations = {}
    for test, specs in model_specs().items():
        cards = [coupon_card(load_spec(path)) for path in specs]
        assert all(cards), f"{test}: a spec without a [coupon] table"
        assert all(card == cards[0] for card in cards), f"{test}: the team's build and its twin are one coupon with one card"
        designations[test] = dict(cards[0])["Coupon"]
        assert designations[test] == test, f"the folder .local/fea/{test}/ is named by its coupon, {designations[test]} (ADR-0040)"
    assert len(set(designations.values())) == len(designations), designations


def test_a_code_means_one_thing_and_one_thing_has_one_code():
    seen = {"material": {}, "test": {}, "layup": {}}
    for specs in model_specs().values():
        spec = load_spec(specs[0])
        material, test, layup = DESIGNATION_RULE.match(spec.coupon.designation).group("material", "test", "layup")
        for kind, code, meaning in (("material", material, (spec.material.library, spec.material.dataset)), ("test", test, spec.kind),
                                    ("layup", layup, tuple(full_angles(spec)))):
            assert seen[kind].setdefault(code, meaning) == meaning, f"the {kind} code {code} names two different things"
    for kind, codes in seen.items():
        assert len(set(codes.values())) == len(codes), f"one {kind} has two codes: {codes}"


def test_the_card_reads_the_rest_of_the_spec_in_its_units():
    card = dict(coupon_card(parse_spec(PUBLIC_COUPON)))
    assert card["Coupon"] == DESIGNATION and card["Test"] == "unnotched tension"
    assert card["Material"].startswith("IM7 / 8552 (library record im7-8552")
    assert card["Layup"] == "[45/0/-45/90]s, 8 plies of 0.18288 mm, 1.46304 mm thick"
    assert card["Size"] == "250 mm long, 25 mm wide, 56 mm tabs at each end"
    assert card == dict(coupon_card(to_si(parse_spec(PUBLIC_COUPON))))  # the same card before and after the conversion to SI
    assert coupon_card(load_spec(paths.spec_path("unnotched-im7-8552-nodal"))) == []  # a check that is not a coupon model may have none


def test_the_deck_heading_names_the_coupon():
    heading = write_abaqus(build_model(to_si(parse_spec(PUBLIC_COUPON)))).split("*Preprint")[0]
    assert f"** {DESIGNATION}, unnotched tension: " in heading and f"** Coupon: {DESIGNATION}" in heading
    assert "** Team's model: not built yet" in heading and "** Test data: none" in heading


REFUSALS = [
    (DESIGNATION_LINE, 'designation = "im7-unt-l1"', "in capitals"),
    (DESIGNATION_LINE, 'designation = "IM7-UNT"', "in capitals"),
    (DESIGNATION_LINE, 'designation = "IM7-UNC-L1"', "test code UNT, not UNC"),
    (TITLE_START, 'title = "Tension coupon: ', "title must start with the coupon's name and test"),
    ('standard = "none"', 'standard = ""', "coupon.standard: String should have at least 1 character"),
    ('standard = "none"\n', "", "coupon.standard: Field required"),
]


@pytest.mark.parametrize("old, new, message", REFUSALS, ids=[r[2][:30] for r in REFUSALS])
def test_an_invalid_card_is_refused_by_name(old, new, message):
    assert old in PUBLIC_COUPON
    with pytest.raises(SpecError, match=message):
        parse_spec(PUBLIC_COUPON.replace(old, new, 1))
