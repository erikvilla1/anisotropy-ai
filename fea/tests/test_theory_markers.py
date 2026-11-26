"""fea/docs/theory.md names a function for every equation and marks it, exactly as the manual build checks the engine's theory."""

import importlib
import re
from pathlib import Path

THEORY = Path(__file__).parents[1] / "docs" / "theory.md"
MODULES = ("mesh", "membrane", "shell", "kernel", "recovery", "results", "cases", "model", "abaqus_reader", "units", "test_quantities", "fields", "working",
           "wing_model", "repair_model", "repair_files", "bond_solver", "repair_bond", "ply_damage", "repair_plies", "large_displacement", "followed_plate")
# The same two patterns as docs/manual/build.py.
CODE_MARKER = re.compile(r"<!--\s*code:\s*(.+?)\s*-->")
FUNCTION_REFERENCE = re.compile(r"(?:[Cc]omputed|[Cc]hecked) by ((?:`[\w.]+`(?:,\s*|\s+and\s+)?)+)")


def _names(group: str) -> set[str]:
    return set(re.findall(r"`([\w.]+)`", group))


def test_every_named_function_has_a_marker_and_every_marker_a_sentence():
    text = THEORY.read_text(encoding="utf-8")
    marked = {name.strip() for marker in CODE_MARKER.findall(text) for name in marker.split(",")}
    named = set()
    for group in FUNCTION_REFERENCE.findall(text):
        named |= _names(group)
    assert marked, "theory.md has no code markers"
    assert named == marked, f"named but not marked: {sorted(named - marked)}; marked but not named: {sorted(marked - named)}"


def test_every_marked_name_resolves_in_the_package():
    text = THEORY.read_text(encoding="utf-8")
    for marker in CODE_MARKER.findall(text):
        for name in (part.strip() for part in marker.split(",")):
            head, _, attribute = name.partition(".")
            found = False
            for module_name in MODULES:
                module = importlib.import_module(f"anisotropy_fea.{module_name}")
                target = getattr(module, head, None)
                if target is not None and (not attribute or hasattr(target, attribute)):
                    found = True
                    break
            assert found, f"theory.md names {name}, which is not in anisotropy_fea"


def test_the_manual_build_searches_the_same_modules():
    """The manual's build resolves each marked name in its own list of modules: a module this test knows and the build does not
    passes here and stops the manual (the bond's two modules did, 2026-11-24)."""
    build = (Path(__file__).parents[2] / "docs" / "manual" / "build.py").read_text(encoding="utf-8")
    listed = re.search(r"^FEA_MODULES = \((.+?)\)$", build, flags=re.M | re.S)
    assert listed, "docs/manual/build.py no longer names FEA_MODULES"
    assert tuple(re.findall(r'"([\w.]+)"', listed.group(1))) == MODULES


def test_a_table_row_that_opens_with_a_layup_stays_text_in_the_manual():
    """LaTeX reads a bracket after a line break or a rule as its optional length, so a row that opened with `[0/90]s` stopped the
    manual with "Illegal unit of measure" (the decision records of ADR-0142, 2026-11-25). Every row of the manual's own table and
    every decision record's table is checked, as the build converts them."""
    import importlib.util

    docs = Path(__file__).parents[2] / "docs"
    found = importlib.util.spec_from_file_location("manual_build", docs / "manual" / "build.py")
    build = importlib.util.module_from_spec(found)
    found.loader.exec_module(build)
    rows = build.table(["Case", "Difference"], [["[0/90]s strip", "0.1 %"], ["plain", "[45/-45]"]]).splitlines()
    assert rows[6].startswith("{}[0/90]s strip & ") and rows[7].startswith("plain & [45/-45]")
    for record in sorted((docs / "decisions").glob("ADR-*.md")):
        for line in build.convert(record.read_text(encoding="utf-8")).splitlines():
            assert not line.lstrip().startswith("["), f"{record.name}: a line of the manual opens with a bracket: {line[:60]}"


def test_theory_has_the_sections_the_manual_expects():
    text = THEORY.read_text(encoding="utf-8")
    for heading in ("## Conventions", "## Checks", "## Not modeled yet"):
        assert heading in text
