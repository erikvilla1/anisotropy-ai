"""fea/docs/theory.md names a function for every equation and marks it, exactly as the manual build checks the engine's theory."""

import importlib
import re
from pathlib import Path

THEORY = Path(__file__).parents[1] / "docs" / "theory.md"
MODULES = ("mesh", "membrane", "results", "cases", "model", "abaqus_reader", "units")
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


def test_theory_has_the_sections_the_manual_expects():
    text = THEORY.read_text(encoding="utf-8")
    for heading in ("## Conventions", "## Checks", "## Not modeled yet"):
        assert heading in text
