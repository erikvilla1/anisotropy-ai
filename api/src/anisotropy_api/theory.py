"""Our own theory pages as sections that can be found by a question's words (ADR-0102, proposed). The two documents the manual prints,
`engine/docs/theory.md` (the laminate engine) and `fea/docs/theory.md` (the finite element kernel), and the page of reasons in words
that rests on them, `engine/docs/reasons.md`, are split at their headings; a question is matched to sections by the words they share,
each word weighted by how few sections hold it. Nothing here calls a model, and nothing is computed about a result: the sections are the
documents' own text, cut and ranked.

The ranking is BM25 over words (k1 = 1.5, b = 0.75), with a section's title counted three times. It is the same for the same question
and documents, so a test can pin which section a question finds.

The wing's sections (a `##` heading that names a file of the wing, as `wing/` or `wing_model.py`, and the sections under it) are read but
not searched by default (ADR-0102 amendment 1): no chat answers a question about a wing yet, and their words would change how every other
section ranks. The wing's chat will search them by its own subject (ADR-0125).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SOURCES: dict[str, tuple[str, Path]] = {  # by id: the name an engineer reads, and the file
    "engine": ("Laminate theory", REPO / "engine" / "docs" / "theory.md"),
    "fea": ("Finite element theory", REPO / "fea" / "docs" / "theory.md"),
    "reasons": ("Reasons behind a result", REPO / "engine" / "docs" / "reasons.md"),  # reasons in words, each from the theory above
}
HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*$")
MARKER = re.compile(r"^<!-- code: .*? -->\n?", re.MULTILINE)  # the line that pairs an equation with its function: the code's, not a reader's
WORD = re.compile(r"[a-z][a-z0-9]+|σ|τ|ε")
# words that say nothing about the subject: the question's own grammar and the documents' most common words
STOP = frozenset("""a an and are as at be by can could do does for from had has have how if in into is it its may more most of on or our so than
that the their then there these this to under was we what when where which while why will with would you your not no each every all any
also only one two both here ply plies value values""".split())
# two spellings or forms of one word, so a question in one finds a page in the other
SAME = {"max": "maximum", "min": "minimum", "tied": "tie", "fiber": "fibre", "sigma": "σ", "tau": "τ", "epsilon": "ε", "meshe": "mesh"}
K1, B, TITLE_WEIGHT = 1.5, 0.75, 3
WING_FILE = re.compile(r"\(`wing[/_][^`]*`\)\s*$")  # a heading that names a file of the wing: `wing/`, `wing_model.py`
MAX_SECTION_CHARS = 6000  # what one section may hand a model; a longer one is cut at a paragraph


@dataclass(frozen=True)
class Section:
    id: str  # "engine:5-failure"
    source: str  # "engine" or "fea"
    document: str  # "Laminate theory"
    title: str  # "5. Failure", without the file named in the heading
    text: str  # the section's own text, with its sub-headings' text apart (each is its own section)
    subject: str = ""  # "wing" for the wing's sections, found only when asked for by subject; "" for every other

    @property
    def words(self) -> list[str]:
        return words_of(self.text) + words_of(self.title) * TITLE_WEIGHT

    def cited(self) -> str:
        """How an answer names it: the document and the section."""
        return f"{self.document}, {self.title}"

    @property
    def shown(self) -> str:
        """The text a reader or a model is handed: the section without the lines that pair its equations with functions."""
        return re.sub(r"\n{3,}", "\n\n", MARKER.sub("", self.text)).strip()


def words_of(text: str) -> list[str]:
    """The words a text is matched by: lower case, no stop word, a plural's s dropped so that "stresses" finds "stress", and one spelling
    for a word written two ways ("fiber" and "fibre", "max" and "maximum")."""
    found = []
    for word in WORD.findall(text.lower()):
        if word in STOP:
            continue
        if word.endswith("sses"):
            word = word[:-2]  # stresses
        elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        found.append(SAME.get(word, word))
    return found


def split(source: str, document: str, text: str) -> list[Section]:
    """A document's sections: one per `##` or `###` heading, holding the text up to the next heading of either level. A sub-section's
    title carries its parent's ("5. Failure: Fixed and variable loading")."""
    sections: list[Section] = []
    parent, title, subject, lines = "", "", "", []

    def close() -> None:
        body = "\n".join(lines).strip()
        if title and body:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            cut = body[:MAX_SECTION_CHARS].rsplit("\n\n", 1)[0] if len(body) > MAX_SECTION_CHARS else body
            sections.append(Section(f"{source}:{slug}", source, document, title, cut, subject))

    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading is None:
            lines.append(line)
            continue
        close()
        name = re.sub(r"\s*\(`[^`]*`\)\s*$", "", heading.group(2))  # the file a heading names is the code's, not the reader's
        if heading.group(1) == "##":
            parent, title = name, name
            subject = "wing" if WING_FILE.search(heading.group(2)) else ""
        else:
            title = f"{parent}: {name}" if parent else name
        lines = []
    close()
    return sections


@lru_cache(maxsize=1)
def sections() -> tuple[Section, ...]:
    """Every section of the theory pages, in the documents' order. Read once per process: the pages change only with a deploy."""
    found: list[Section] = []
    for source, (document, path) in SOURCES.items():
        found.extend(split(source, document, path.read_text(encoding="utf-8")))
    return tuple(found)


def of_subject(subject: str = "") -> tuple[Section, ...]:
    """The sections of one subject: by default every section but the wing's, which only the wing's chat will search (ADR-0102 amendment 1)."""
    return tuple(section for section in sections() if section.subject == subject)


def find(question: str, among: tuple[Section, ...] | None = None, limit: int = 2) -> list[tuple[Section, float]]:
    """The sections a question's words find, best first, each with its score; none when no word of the question is in any section. The
    sections searched are `among`, by default every section but the wing's."""
    among = of_subject() if among is None else among
    asked = set(words_of(question))
    if not asked or not among:
        return []
    bags = [section.words for section in among]
    average = sum(len(bag) for bag in bags) / len(bags)
    holding = {word: sum(word in bag for bag in map(set, bags)) for word in asked}
    scored: list[tuple[Section, float]] = []
    for section, bag in zip(among, bags):
        score = 0.0
        for word in asked:
            count = bag.count(word)
            if not count:
                continue
            rarity = math.log(1 + (len(among) - holding[word] + 0.5) / (holding[word] + 0.5))
            score += rarity * count * (K1 + 1) / (count + K1 * (1 - B + B * len(bag) / average))
        if score > 0:
            scored.append((section, round(score, 6)))
    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    return scored[:limit]
