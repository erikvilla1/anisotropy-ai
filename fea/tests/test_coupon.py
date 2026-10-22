"""The coupon's identity card (ADR-0038): every model names its coupon, and a code in a name means one thing everywhere."""

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import DESIGNATION, SpecError, coupon_card, full_angles, load_spec, parse_spec
from anisotropy_fea.write_abaqus import write_abaqus

TEAM = paths.spec_path("X840PW-UNT-L1").read_text(encoding="utf-8")
DESIGNATION_LINE = 'designation = "X840PW-UNT-L1"'
TITLE_START = 'title = "X840PW-UNT-L1, unnotched tension: '


def model_specs() -> dict[str, list]:
    """Every spec under fea/models/, by test folder."""
    return {d.name: sorted(d.glob("*.toml")) for d in sorted(paths.MODELS.iterdir()) if d.is_dir()}


def test_every_model_names_its_coupon_once():
    designations = {}
    for test, specs in model_specs().items():
        cards = [coupon_card(load_spec(path)) for path in specs]
        assert all(cards), f"{test}: a spec without a [coupon] table"
        assert all(card == cards[0] for card in cards), f"{test}: the team's build and its twin are one coupon with one card"
        designations[test] = dict(cards[0])["Coupon"]
        assert designations[test] == test, f"the folder fea/models/{test}/ is named by its coupon, {designations[test]} (ADR-0040)"
    assert len(set(designations.values())) == len(designations), designations


def test_a_code_means_one_thing_and_one_thing_has_one_code():
    seen = {"material": {}, "test": {}, "layup": {}}
    for specs in model_specs().values():
        spec = load_spec(specs[0])
        material, test, layup = DESIGNATION.match(spec.coupon.designation).group("material", "test", "layup")
        for kind, code, meaning in (("material", material, (spec.material.library, spec.material.dataset)), ("test", test, spec.kind),
                                    ("layup", layup, tuple(full_angles(spec)))):
            assert seen[kind].setdefault(code, meaning) == meaning, f"the {kind} code {code} names two different things"
    for kind, codes in seen.items():
        assert len(set(codes.values())) == len(codes), f"one {kind} has two codes: {codes}"


def test_the_card_reads_the_rest_of_the_spec_in_its_units():
    card = dict(coupon_card(load_spec(paths.spec_path("X840PW-UNT-L1"))))
    assert card["Coupon"] == "X840PW-UNT-L1" and card["Test"] == "unnotched tension"
    assert card["Material"].startswith("X840 / Z60 plain weave 6K (library record x840-z60-pw")
    assert card["Layup"] == "[0/45/-45/45/0]s, 10 plies of 0.1 mm, 1 mm thick"
    assert card["Size"] == "80 mm long, 10 mm wide, 15 mm tabs at each end"
    assert card == dict(coupon_card(parse_spec(TEAM)))  # the same card before and after the conversion to SI
    assert coupon_card(load_spec(paths.spec_path("unnotched-im7-8552-nodal"))) == []  # a check that is not a team model may have none


def test_the_deck_heading_names_the_coupon():
    heading = write_abaqus(build_model(load_spec(paths.spec_path("X840PW-UNT-L1")))).split("*Preprint")[0]
    assert "** X840PW-UNT-L1, unnotched tension: " in heading and "** Coupon: X840PW-UNT-L1" in heading
    assert "** Team's model: Tension-test" in heading and "** Test data: none yet" in heading


REFUSALS = [
    (DESIGNATION_LINE, 'designation = "x840pw-unt-l1"', "in capitals"),
    (DESIGNATION_LINE, 'designation = "X840PW-UNT"', "in capitals"),
    (DESIGNATION_LINE, 'designation = "X840PW-UNC-L1"', "test code UNT, not UNC"),
    (TITLE_START, 'title = "Tension coupon: ', "title must start with the coupon's name and test"),
    ('standard = "none"', 'standard = ""', "coupon.standard: String should have at least 1 character"),
    ('standard = "none"\n', "", "coupon.standard: Field required"),
]


@pytest.mark.parametrize("old, new, message", REFUSALS, ids=[r[2][:30] for r in REFUSALS])
def test_an_invalid_card_is_refused_by_name(old, new, message):
    assert old in TEAM
    with pytest.raises(SpecError, match=message):
        parse_spec(TEAM.replace(old, new, 1))
