"""The document of a model sent from Abaqus, docs/models/upload.py (ADR-0094 step 7): "Compared with the uploaded Abaqus model",
written from a comparison as `fea/tools/abaqus_upload.py compare` wrote it and from nothing else. The comparisons are the four of
tests/fixtures/abaqus, which `test_abaqus_upload.py` pins to the command and the page's card is tested with. The LaTeX is checked here;
it is compiled where Tectonic is installed."""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
UPLOAD = ROOT / "docs/models/upload.py"
FIXTURES = ROOT / "tests/fixtures/abaqus"
NAMES = ("agrees", "differs", "another-mesh", "incomplete")
SECTIONS = ("What was compared, and by which rule", "The model, item by item", "The pull force", "The results, zone by zone",
            "What this shows and what it does not", "The file you sent")


@pytest.fixture(scope="module")
def upload():
    spec = importlib.util.spec_from_file_location("anisotropy_models_upload", UPLOAD)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def comparison(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def balanced(tex: str) -> bool:
    """Every brace that is not an escaped one closes, and none closes before it opens."""
    depth = 0
    for brace in re.findall(r"(?<!\\)(?:\\\\)*([{}])", tex.split(r"\begin{document}", 1)[1]):
        depth += 1 if brace == "{" else -1
        if depth < 0:
            return False
    return depth == 0


@pytest.mark.parametrize("name", NAMES)
def test_each_comparison_becomes_one_document_with_its_six_sections_and_the_answer_first(upload, name):
    result = comparison(name)
    tex = upload.document(result, upload="0b6f", run="our run 0f3a", compared="2026-11-13 09:30 UTC")
    assert tex.startswith(r"\documentclass[11pt,letterpaper]{article}") and tex.rstrip().endswith(r"\end{document}") and balanced(tex)
    assert re.findall(r"\\section\{([^}]*)\}", tex) == list(SECTIONS)
    body = tex.split(r"\begin{document}", 1)[1]
    assert body.index("Compared with the uploaded Abaqus model") < body.index(r"\verdict{") < body.index(r"\section{")  # the answer before any section
    assert rf"\verdict{{\textbf{{{upload.verdict_words(result)}.}}" in tex
    for c in result["criteria"]:  # each criterion with its evidence, in the answer and in the table
        assert tex.count(upload.text(c["evidence"])) >= 2
    for item in result["model"]["items"]:  # every item of the model, yours beside ours
        assert " & ".join(upload.text(item[key]) for key in ("item", "yours", "ours")) in tex
    assert tex.count(r"\textcolor{accent}{\textbf{differs}}") == result["summary"]["model"]["different"]
    for role, entry in result["bundle"]["files"].items():
        assert upload.digest(entry["sha256"]) in tex and str(entry["bytes"]) in tex
    assert "0b6f" in tex and "our run 0f3a" in tex and "2026-11-13 09:30 UTC" in tex and result["bundle"]["sha256"] in tex
    # one model beside another is compared and verified; "validated" stays for a coupon test (ADR-0089), and the document says so
    assert re.findall(r"validat\w*", tex) == ["validated", "validation"] and "not validated against a coupon test" in tex and "It is not a validation" in tex
    assert "only you and the Anisotropy team can see it" in tex and "Nothing in it was executed" in tex
    assert not re.search(r"\d(?:\.\d+)?e[+-]\d", body)  # no exponent in letters


def test_the_numbers_printed_are_the_comparisons_own(upload):
    result = comparison("differs")
    tex = upload.document(result)
    assert r"\textbf{Differs in 2 places.} The model, compared item by item: 1 of 20 items judged differ" in tex
    assert "20 of the 22 items were judged, and 1 differ." in tex
    rf = result["reaction"]
    assert (rf["yours"], rf["ours"]) == (17021.792417479777, 16211.230873790264)
    assert r"17021.8 N, the reaction along the coupon summed over 373 nodes of the top grip" in tex and "16211.2 N, over the same edge" in tex
    assert r"ours $-$4.762\,\% from yours" in tex and r"Reaction within 1 \%: not met (ours $-$4.762 \% from yours)" in tex
    gauge = result["zones"]["gauge"]["S11"]
    assert f"S11 & {gauge['values']} & {gauge['within_1']} & {gauge['within_3']} & 0\\,\\% & 673, ply 1 & 413.639 & 413.639" in tex
    assert "Pressure & 5376 & 5376 & 5376 & 0\\,\\% & 1, ply 1 & 0 & 0" in tex  # under the grips: a zero is 0, whatever its sign
    assert tex.count(r"\subsection*{") == 5 and [m for m in re.findall(r"\\subsection\*\{([^}]*)\}", tex)] == [upload.ZONE_WORDS[z] for z in upload.ZONES]
    assert tex.count("; judged.") == 2 and tex.count("; reported, not judged.") == 3  # the gauge and between gauge and tabs are judged
    assert "The two meshes are one mesh: 1488 elements were paired by element number: your elements are ours." in tex
    assert r"within that share of 2\,\% of the quantity's largest magnitude" in tex and r"the reaction at the top grip, within 1\,\%" in tex
    assert r"between gauge and tabs, the free length, within 3\,\%" in tex and "Stresses are in MPa; strains have no unit." in tex


def test_two_meshes_are_said_and_what_was_not_judged_is_not_called_agreement(upload):
    other = comparison("another-mesh")
    tex = upload.document(other)
    assert r"\textbf{Agrees with ours.} The model, compared without its mesh: the same as ours on every one of 16 items judged." in tex
    assert "The two meshes are not one mesh (your model has 372 elements and ours 1488" in tex
    assert "On two meshes the values between gauge and tabs are reported and not judged." in tex
    assert "compared without their meshes, because" in tex and r"\textcolor{muted}{reported}" in tex
    assert "The two models are on different meshes, so a value of yours stands beside the value of ours nearest its place" in tex
    assert tex.count("; judged.") == 1 and re.search(r"\d+ \(ours \d+\), ply \d", tex)  # our element is named where its number is another
    assert "Free length: every value within 3 \\%: reported, not judged on another mesh" in tex  # said once, in the evidence's own words

    open_ = comparison("incomplete")
    tex = upload.document(open_)
    assert r"\textbf{Not every part could be compared.}" in tex and r"\textcolor{muted}{not judged}" in tex
    assert "The pull force was not compared: no reactions read" in tex
    assert "a part that was not compared is neither agreement nor difference" in tex


def test_a_text_of_the_upload_cannot_write_latex(upload):
    """A job's name, an item's value and a file's path are the user's own text: each reaches the document escaped."""
    result = comparison("agrees")
    hostile = "Job_1 & 50% \\input{/etc/passwd} $x^2$ #~\x07\nend"
    result["bundle"]["job"] = hostile
    result["model"]["items"][0]["yours"] = "\\end{document} {{{"
    result["bundle"]["files"]["deck"]["path"] = "model/}\\write18{rm}.inp"
    result["bundle"]["files"]["deck"]["sha256"] = "}\\input{x}"
    tex = upload.document(result)
    assert balanced(tex) and tex.count(r"\end{document}") == 1
    assert r"Job\_1 \& 50\% \textbackslash{}input\{/etc/passwd\} \$x\textasciicircum{}2\$ \#\textasciitilde{} end" in tex
    assert r"\input{" not in tex and r"\write18" not in tex and "\x07" not in tex
    assert r"\textbackslash{}end\{document\} \{\{\{" in tex


def test_a_file_that_is_no_comparison_or_one_that_was_refused_has_no_document(upload, tmp_path):
    for found, said in (([], "not a comparison written by"), ({"verdict": "refused", "problems": ["no manifest.json in the zip", "plies differ"]},
                                                              "the comparison was refused, so there is nothing to print: no manifest.json in the zip; plies differ"),
                        ({"verdict": "perhaps"}, "which this document does not know")):
        with pytest.raises(upload.NoDocument, match=re.escape(said)):
            upload.document(found)
    older = copy.deepcopy(comparison("agrees"))
    del older["summary"]
    with pytest.raises(upload.NoDocument, match="has no summary: it was written by an older"):
        upload.document(older)

    source, answer = tmp_path / "refused.json", tmp_path / "answer.json"
    source.write_text(json.dumps({"verdict": "refused", "problems": ["plies differ"]}), encoding="utf-8")
    assert upload.main([str(source), "--out", str(tmp_path / "out"), "--json", str(answer)]) == 2
    assert json.loads(answer.read_text(encoding="utf-8")) == {"written": None, "reason": "the comparison was refused, so there is nothing to print: plies differ"}
    assert not (tmp_path / "out").exists()  # nothing is written for it
    assert upload.main([str(tmp_path / "missing.json"), "--out", str(tmp_path / "out"), "--json", str(answer)]) == 2
    assert json.loads(answer.read_text(encoding="utf-8"))["written"] is None


def test_the_command_writes_the_latex_and_says_whether_a_pdf_was_compiled(upload, tmp_path, monkeypatch):
    source, answer, out = FIXTURES / "differs.json", tmp_path / "answer.json", tmp_path / "out"
    assert upload.main([str(source), "--out", str(out), "--no-pdf", "--upload", "0b6f", "--json", str(answer)]) == 0
    tex = out / "comparison.tex"
    assert json.loads(answer.read_text(encoding="utf-8")) == {"written": str(tex), "pdf": False}
    assert tex.read_text(encoding="utf-8") == upload.document(comparison("differs"), upload="0b6f") and sorted(p.name for p in out.iterdir()) == ["comparison.tex"]

    monkeypatch.setattr(upload.manual, "tectonic", lambda: None)  # as the API's container would be without it
    assert upload.main([str(source), "--out", str(out), "--json", str(answer)]) == 0
    assert json.loads(answer.read_text(encoding="utf-8")) == {"written": str(tex), "pdf": False, "reason": "Tectonic is not installed, so no PDF was written"}

    ran = []  # the text in it came with a user's file, so Tectonic is told the input is untrusted
    monkeypatch.setattr(upload.manual, "tectonic", lambda: "tectonic")
    monkeypatch.setattr(upload.subprocess, "run", lambda command, check: ran.append((command, check)))
    assert upload.build(comparison("agrees"), out) == out / "comparison.pdf"
    assert ran == [(["tectonic", "--untrusted", "--outdir", str(out), str(tex)], True)]


@pytest.mark.parametrize("name", NAMES)
def test_the_document_compiles_where_tectonic_is_installed(upload, tmp_path, name):
    """The other tests read the LaTeX only. Skipped where Tectonic is absent (CI's fea job); the image's job compiles one with the
    network off."""
    if upload.manual.tectonic() is None:
        pytest.skip("Tectonic is not installed")
    answer = tmp_path / "answer.json"
    assert upload.main([str(FIXTURES / f"{name}.json"), "--out", str(tmp_path), "--json", str(answer)]) == 0
    pdf = tmp_path / "comparison.pdf"
    assert json.loads(answer.read_text(encoding="utf-8")) == {"written": str(pdf), "pdf": True} and pdf.read_bytes().startswith(b"%PDF")


def test_the_document_and_the_card_say_the_same_words(upload):
    """The answer and the zones are named on the page's card first (step 6); the document uses those words, read here from the page's source."""
    card = (ROOT / "components/studio/abaqus-card.tsx").read_text(encoding="utf-8")
    for zone, words in upload.ZONE_WORDS.items():
        key = zone if " " not in zone else f'"{zone}"'
        assert f'{key}: "{words}"' in card
    words = (ROOT / "lib/abaqus-exchange.ts").read_text(encoding="utf-8")
    result = comparison("differs")
    said = {upload.verdict_words(comparison("agrees")), upload.verdict_words(comparison("incomplete")), upload.verdict_words(result)}
    assert said == {"Agrees with ours", "Not every part could be compared", "Differs in 2 places"}
    assert '"Agrees with ours"' in words and '"Not every part could be compared"' in words and "`Differs in ${places} places`" in words
    result["summary"]["places"] = 1
    assert upload.verdict_words(result) == "Differs in 1 place" and '"Differs in 1 place"' in words
    assert "only you and the Anisotropy team can see it" in card
