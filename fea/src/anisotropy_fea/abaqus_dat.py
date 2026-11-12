"""Read the printed tables of an Abaqus/Standard `.dat`: what `*El Print` and `*Node Print` write (ADR-0066 amendment 1).

A table opens with a line that holds "THE FOLLOWING TABLE IS PRINTED", runs on until a blank line and names its set after the
word SET ("ELEMENT SET ASSEMBLY_PROBE-CENTRE", "NODE SET ASSEMBLY_RF-TOP"); the assembly prefix Abaqus adds is dropped from
the name this module reports. Then a column line ("ELEMENT  SEC FOOT-   S11  S22  S12", "NODE FOOT-  RF1 ... RM3") whose
columns are the words after FOOT-, with SEC marking a section-point column, and one or more lines of footnote headings up to
a blank line. The rows follow until the next blank line: the element or node label, the section point when the table has
one, an optional footnote tag such as OR, then the values. A `totals=YES` table ends with a TOTAL line, which is kept.
The wording was read from a real file (Abaqus 2025, 2026-11-08, `AS48552-UNT-L1-abaqus-plies.dat`). Nothing is converted or
transformed here (ADR-0002); what a line does not say is refused by its number rather than guessed (ADR-0003).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A printed number: an integer, a decimal, an exponent with E or D, or Fortran's three-digit exponent written with no letter at all
# ("1.5633561-189" is 1.5633561E-189), which Abaqus prints for a value below 1E-99 (seen 2026-11-11 in a .dat of Abaqus 2025)
NUMBER = re.compile(r"^[-+]?(?:(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?|(?:\d+\.\d*|\.\d+)[-+]\d{3})$")
SHORT_EXPONENT = re.compile(r"^([-+]?(?:\d+\.\d*|\.\d+))([-+]\d{3})$")
OPENS = "THE FOLLOWING TABLE IS PRINTED"
SET = re.compile(r"\bSET\s+(\S+)")
ASSEMBLY = "ASSEMBLY_"
VERSION = re.compile(r"^\s*Abaqus(?:/Standard)?\s+(\d{4}(?:\.\d+)?|[\d.]+-\d+)\b")


class AbaqusDatError(ValueError):
    """The `.dat` does not read as Abaqus writes one, or lacks a table that was asked for."""


@dataclass(frozen=True)
class DatRow:
    label: int  # element or node label
    point: int | None  # section point, in a table that has the column
    tag: str  # the footnote tag, "OR" for an element with an *Orientation, else ""
    values: tuple[float, ...]


@dataclass(frozen=True)
class DatTable:
    kind: str  # "element" or "node"
    set_name: str  # as the deck names it, the ASSEMBLY_ prefix dropped
    columns: tuple[str, ...]
    rows: tuple[DatRow, ...]
    total: tuple[float, ...] | None  # the TOTAL line of a totals=YES table
    line: int  # where the table opens, 1-based

    def column(self, name: str) -> int:
        try:
            return self.columns.index(name)
        except ValueError:
            raise AbaqusDatError(f"the {self.kind} table of set {self.set_name!r} (line {self.line}) has no column {name!r}; it has {', '.join(self.columns)}") from None

    def of(self, label: int) -> list[DatRow]:
        return [row for row in self.rows if row.label == label]


@dataclass(frozen=True)
class AbaqusDat:
    version: str | None  # "Abaqus 2025" as the banner says it
    tables: tuple[DatTable, ...]

    def find(self, kind: str, set_name: str, column: str) -> DatTable:
        """The last table of that kind and set that has the column: the last increment's, in a file with several."""
        hits = [t for t in self.tables if t.kind == kind and t.set_name.upper() == set_name.upper() and column in t.columns]
        if not hits:
            have = ", ".join(f"{t.kind} {t.set_name} [{t.columns[0]}..]" for t in self.tables) or "none"
            raise AbaqusDatError(f"the .dat has no {kind} table for set {set_name!r} with a column {column!r}; its tables: {have}")
        return hits[-1]

    def element_tables_with(self, column: str, label: int) -> list[DatTable]:
        """Every element table that has the column and a row for the label, in file order."""
        return [t for t in self.tables if t.kind == "element" and column in t.columns and t.of(label)]


def _number(token: str) -> float:
    short = SHORT_EXPONENT.match(token)
    if short:  # Fortran's "1.5633561-189": the letter dropped to make room for a three-digit exponent
        return float(f"{short[1]}E{short[2]}")
    return float(token.replace("D", "E").replace("d", "e"))


def _set_name(header: str) -> str:
    match = SET.search(header)
    if not match:
        raise AbaqusDatError(f"a table header names no set: {header.strip()!r}")
    name = match[1]
    return name[len(ASSEMBLY):] if name.upper().startswith(ASSEMBLY) else name


def parse_abaqus_dat(text: str) -> AbaqusDat:
    """Every printed table of the file, in order, and the solver's version from the banner."""
    lines = text.splitlines()
    version = None
    for line in lines[:60]:
        match = VERSION.match(line)
        if match:
            version = f"Abaqus {match[1]}"
            break
    tables: list[DatTable] = []
    i = 0
    while i < len(lines):
        if OPENS not in lines[i]:
            i += 1
            continue
        opened = i + 1
        header = []
        while i < len(lines) and lines[i].strip():
            header.append(lines[i].strip())
            i += 1
        header_text = " ".join(header)
        kind = "node" if "FOR NODES" in header_text else "element"
        set_name = _set_name(header_text)
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            raise AbaqusDatError(f".dat line {opened}: the table of set {set_name!r} has no column line")
        tokens = lines[i].split()
        if "FOOT-" not in tokens:
            raise AbaqusDatError(f".dat line {i + 1}: cannot read the columns of the table of set {set_name!r}: {lines[i].strip()!r}")
        at = tokens.index("FOOT-")
        has_point = "SEC" in tokens[:at]
        columns = tuple(tokens[at + 1:])
        if not columns:
            raise AbaqusDatError(f".dat line {i + 1}: the table of set {set_name!r} names no columns")
        i += 1
        while i < len(lines) and lines[i].strip():  # the footnote headings (NOTE, PT NOTE)
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        rows: list[DatRow] = []
        while i < len(lines) and lines[i].strip():
            rows.append(_row(lines[i], i + 1, has_point, len(columns), set_name))
            i += 1
        total = None
        j = i
        while j < len(lines) and OPENS not in lines[j] and "O U T P U T" not in lines[j]:
            words = lines[j].split()
            if len(words) == len(columns) + 1 and words[0] == "TOTAL" and all(NUMBER.match(w) for w in words[1:]):  # not "TOTAL CPU TIME"
                total = tuple(_number(w) for w in words[1:])
                break
            j += 1
        tables.append(DatTable(kind=kind, set_name=set_name, columns=columns, rows=tuple(rows), total=total, line=opened))
    return AbaqusDat(version=version, tables=tuple(tables))


def _row(line: str, number: int, has_point: bool, width: int, set_name: str) -> DatRow:
    tokens = line.split()
    ids = 2 if has_point else 1
    if len(tokens) < ids + width or not all(NUMBER.match(t) and "." not in t and "E" not in t.upper() for t in tokens[:ids]):
        raise AbaqusDatError(f".dat line {number}: cannot read {line.strip()!r} as a row of set {set_name!r}")
    values = tokens[-width:]
    if not all(NUMBER.match(t) for t in values):
        raise AbaqusDatError(f".dat line {number}: cannot read the values of {line.strip()!r}")
    tag = " ".join(tokens[ids:-width])
    if tag and any(NUMBER.match(t) for t in tag.split()):
        raise AbaqusDatError(f".dat line {number}: {line.strip()!r} has more numbers than the table has columns")
    return DatRow(label=int(tokens[0]), point=int(tokens[1]) if has_point else None, tag=tag, values=tuple(_number(t) for t in values))
