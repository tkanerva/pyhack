#!/usr/bin/env python3
"""One-off converter: ``include/monsters.h`` -> ``core/monst_data.py``.

PLAN-MAKEMON.md phase A (§4.5) calls for exactly this tool: the monster
table is 383 rows of ``MON(...)`` in NetHack 5.0's ``include/monsters.h``
and every row has the same eight-line shape, so it is *data* -- a
mechanical pass, not 383 hand transcriptions.  The rows are written in C
order, so the index of every row equals its ``mons[]`` index (the
``PM_*`` numbering) and nothing has to be renumbered.

It is a development tool, not part of the game: ``core`` never imports
it, no build step depends on it, and the generated file is checked in.
Run it from the repository root:

    python tools/convert_monsters.py            # rewrite core/monst_data.py
    python tools/convert_monsters.py --check    # compare, write nothing

The C build it reproduces is the *default* one, i.e. the same one the
hand-written ``PM_NAMES`` recorded:

- ``CHARON`` undefined -- the ferryman's two rows are ``#ifdef``'d out
  (``monst_defs`` notes the missing ``MS_FERRY`` number for a later
  pass that adds him);
- ``MAIL_STRUCTURES`` defined (5.0's ``global.h`` always defines it) --
  so the mail daemon *is* a row, between Famine and the djinni;
- every ``#if 0`` block excluded: the beholder, the vorpal jabberwock
  and the 3.1.x/3.2.x elf-quest leaders/nemesis/guardian.

Two more header features it does reproduce: the ``SEDUCTION_ATTACKS_YES``
macro (one amorous-demon row uses it, so object-like macros are
expanded), and the ``NAMS("male", "female", "neutral")`` rows (the
gendered names live in ``PerMonst.pmnames``).

Before anything is written, the parse is checked in four ways, and a
wrong answer aborts the run instead of emitting a plausible-looking
table:

- exactly ``NUMMONS`` (383) rows, each with 14 ``MON`` arguments;
- the C enum name of a row (``GIANT_ANT``) agrees with the row's own
  neutral name at that index (``PM_NAMES[i] == "giant ant"``), and the
  special section (``SPECIAL_PM`` and up) is really ``G_NOGEN |
  M2_NOPOLY``;
- every identifier used by a row is a constant ``core.monst_defs``
  declares -- a missing ``M1_*`` / ``CLR_*`` / ``MR_*`` name is a
  *conversion* error, not a table one, and would otherwise surface as
  an ImportError in a generated file;
- the hand-written ``PM_*`` anchors in ``monst_defs`` agree with the
  indices this parse produced (they are what the game code reads, so a
  drift there is a silent mis-identification of every monster).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
C_HEADER = REPO_ROOT.parent / "NetHack" / "include" / "monsters.h"
TARGET = REPO_ROOT / "core" / "monst_data.py"

# the C `MON` macro's parameter count (monsters.h, MONS_ENUM branch)
MON_ARGS = 14
# the widest line the generated file aims for (flake8's E501 is off,
# but the table stays diffable against the C)
MAX_LINE = 79
# the `#ifdef`d sections this build defines; everything else is off
DEFINED_SECTIONS = ("MAIL_STRUCTURES",)
# the C helper macros a row is built from (everything else is a constant)
ROW_MACROS = ("MON", "NAM", "NAMS", "LVL", "A", "ATTK", "SIZ", "NO_ATTK")


class Row(NamedTuple):
    """One C ``MON(...)`` row, already translated to Python field text."""

    idx: int                        # the mons[] index == PM_* value
    enum: str                       # the C enum name, e.g. GIANT_ANT
    cname: str                      # the neutral name, e.g. giant ant
    name: str                       # `"giant ant"` or `_nams(...)`
    mlet: str                       # S_ANT
    lvl: Tuple[str, ...]            # level, move, ac, mr, alignment
    geno: str                       # G_GENO | G_SGROUP | 3
    atks: Tuple[str, ...]           # six Attack(...) / NO_ATK
    siz: Tuple[str, ...]            # cwt, cnutrit, msound, msize
    mr1: str                        # mresists
    mr2: str                        # mconveys
    f1: str                         # mflags1
    f2: str                         # mflags2
    f3: str                         # mflags3
    diff: str                       # difficulty
    col: str                        # mcolor


# ------------------------------------------------------------
# C source -> rows
# ------------------------------------------------------------

def _strip_comments(text: str) -> str:
    """Drop every ``/* ... */`` comment (the rows carry prose asides)."""
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def _logical_lines(text: str) -> List[str]:
    """Join the backslash continuations, so one macro definition is one
    line (``SEDUCTION_ATTACKS_YES`` spans two)."""
    out: List[str] = []
    pending = ""
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        out.append(pending + stripped)
        pending = ""
    if pending:
        out.append(pending)
    return out


def _directive(line: str, macros: Dict[str, str],
               active: List[bool]) -> None:
    """Handle one preprocessor line: record macros, track the sections.

    The header only uses the simple forms (``#ifdef`` / ``#if 0`` /
    ``#elif`` / ``#endif``) and never nests them, so a plain stack of
    booleans is the whole model.
    """
    kind = line.split()[0]
    if kind == "#define":
        if re.match(r"#define\s+\w+\(", line):
            return                      # function-like (MON, MON3): unused
        m = re.match(r"#define\s+(\w+)\s+(.*)", line)
        if m is None:
            raise ValueError(f"unparsed #define: {line}")
        macros[m.group(1)] = m.group(2).strip()
    elif kind == "#ifdef":
        active.append(line.split()[1] in DEFINED_SECTIONS)
    elif kind == "#ifndef":
        active.append(line.split()[1] not in DEFINED_SECTIONS)
    elif kind == "#if":
        active.append(False)            # `#if 0` / `#if defined(MONS_ENUM)`
    elif kind in ("#else", "#elif"):
        active[-1] = not active[-1]
    elif kind == "#endif":
        active.pop()
    elif kind in ("#undef", "#error", "#include"):
        pass
    else:
        raise ValueError(f"unparsed preprocessor line: {line}")


def _expand(text: str, macros: Dict[str, str]) -> str:
    """Expand the object-like macros (``SEDUCTION_ATTACKS_YES``)."""
    for _ in range(8):
        before = text
        for name, body in macros.items():
            text = re.sub(rf"\b{re.escape(name)}\b", body, text)
        if text == before:
            return text
    raise ValueError(f"macro expansion did not settle: {text[:60]}")


def _balanced(text: str, start: int) -> str:
    """The text between the ``(`` at ``start - 1`` and its match."""
    depth = 1
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    raise ValueError(f"unbalanced parentheses: {text[start - 12:start + 40]}")


def _calls(text: str, name: str) -> List[str]:
    """Every ``name(...)`` invocation in ``text``, as its inner text."""
    out: List[str] = []
    i = 0
    while True:
        j = text.find(name + "(", i)
        if j < 0:
            return out
        if j and (text[j - 1].isalnum() or text[j - 1] == "_"):
            i = j + 1
            continue
        out.append(_balanced(text, j + len(name) + 1))
        i = j + len(name) + 1


def _split_top(text: str) -> List[str]:
    """Split on the commas outside parentheses and string literals."""
    parts: List[str] = []
    depth = 0
    i = 0
    start = 0
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    tail = text[start:]
    if tail.strip():
        parts.append(tail)
    return [p.strip() for p in parts]


def _expr(text: str) -> str:
    """One C expression as Python: collapse the whitespace, drop the C
    integer suffixes (``0L`` is a long) and the outer parentheses the
    geno column is written with."""
    out = re.sub(r"\s+", " ", text).strip()
    out = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", out)
    if (out.startswith("(") and out.endswith(")")
            and _balanced(out, 1) == out[1:-1]):
        out = out[1:-1].strip()
    return out


def _call_args(text: str, name: str, count: int) -> List[str]:
    """The arguments of the single ``name(...)`` heading ``text``."""
    if not text.startswith(name + "("):
        raise ValueError(f"expected {name}(...) but found: {text[:40]}")
    args = _split_top(_balanced(text, len(name) + 1))
    if len(args) != count:
        raise ValueError(f"{name}() takes {count} arguments, got "
                         f"{len(args)} in: {text[:60]}")
    return args


def _int(text: str, where: str) -> str:
    """A plain C integer literal (dice, levels, difficulty)."""
    if not re.fullmatch(r"-?\d+", text.strip()):
        raise ValueError(f"{where}: expected an integer, found {text!r}")
    return str(int(text))


def _quoted(text: str, where: str) -> str:
    """A C string literal -> Python source for the same string."""
    m = re.fullmatch(r'"([^"]*)"', text.strip())
    if m is None:
        raise ValueError(f"{where}: expected a string, found {text!r}")
    name = m.group(1)
    if '"' in name or "\\" in name:
        raise ValueError(f"{where}: unsupported name {name!r}")
    return f'"{name}"'


def _parse_name(nam: str, idx: int) -> Tuple[str, str]:
    """The name column: C's ``NAM()`` or ``NAMS()`` -> Python, and the
    neutral name (the one ``PM_NAMES`` records)."""
    if nam.startswith("NAMS("):
        names = [_quoted(a, f"row {idx} NAMS") for a in
                 _split_top(_balanced(nam, len("NAMS") + 1))]
        if len(names) != 3:
            raise ValueError(f"row {idx}: NAMS() needs three names")
        return f"_nams({', '.join(names)})", names[2].strip('"')
    if nam.startswith("NAM("):
        args = _split_top(_balanced(nam, len("NAM") + 1))
        if len(args) != 1:
            raise ValueError(f"row {idx}: NAM() takes one name")
        one = _quoted(args[0], f"row {idx} NAM")
        return one, one.strip('"')
    raise ValueError(f"row {idx}: unparsed name column {nam!r}")


def _parse_attack(text: str, idx: int) -> str:
    """One attack slot: ``ATTK(...)`` -> ``Attack(...)``, or ``NO_ATK``."""
    if text == "NO_ATTK":
        return "NO_ATK"
    aatyp, adtyp, damn, damd = _call_args(text, "ATTK", 4)
    return ("Attack({}, {}, {}, {})"
            .format(_expr(aatyp), _expr(adtyp),
                    _int(damn, f"row {idx} ATTK dice"),
                    _int(damd, f"row {idx} ATTK sides")))


def _parse_row(idx: int, args_text: str) -> Row:
    """One ``MON(...)`` argument list -> a `Row`."""
    args = _split_top(args_text)
    if len(args) != MON_ARGS:
        raise ValueError(f"row {idx}: {len(args)} MON arguments")
    (nam, sym, lvl, gen, atk, siz, mr1, mr2,
     f1, f2, f3, diff, col, enum) = args

    name, cname = _parse_name(nam, idx)

    # LVL(level, move, ac, mr, alignment)
    level, move, ac, mr, align = _call_args(lvl, "LVL", 5)
    lvl_col = (_int(level, f"row {idx} LVL level"),
               _int(move, f"row {idx} LVL move"),
               _int(ac, f"row {idx} LVL ac"),
               _int(mr, f"row {idx} LVL mr"),
               _expr(align))

    # A(...) -- exactly six attack slots
    atks = tuple(_parse_attack(a, idx) for a in _call_args(atk, "A", 6))

    # SIZ(weight, nutrition, sound, size)
    weight, nutrit, sound, size = _call_args(siz, "SIZ", 4)
    siz_col = (weight, _int(nutrit, f"row {idx} SIZ nutrition"),
               _expr(sound), _expr(size))

    return Row(
        idx=idx,
        enum=enum.strip(),
        cname=cname,
        name=name,
        mlet=_expr(sym),
        lvl=lvl_col,
        geno=_expr(gen),
        atks=atks,
        siz=siz_col,
        mr1=_expr(mr1),
        mr2=_expr(mr2),
        f1=_expr(f1),
        f2=_expr(f2),
        f3=_expr(f3),
        diff=_int(_expr(diff), f"row {idx} difficulty"),
        col=_expr(col),
    )


def parse(path: Path = C_HEADER) -> List[Row]:
    """Read ``include/monsters.h`` and return its ``mons[]`` rows."""
    text = _strip_comments(path.read_text(encoding="latin-1"))
    macros: Dict[str, str] = {}
    active: List[bool] = []
    body: List[str] = []
    for line in _logical_lines(text):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            _directive(stripped, macros, active)
            continue
        if all(active):
            body.append(_expand(stripped, macros))
    return [_parse_row(i, call)
            for i, call in enumerate(_calls(" ".join(body), "MON"))]


# ------------------------------------------------------------
# Checks (they abort the run; a converter bug must not be silent)
# ------------------------------------------------------------

def check_rows(rows: Sequence[Row], nummons: int,
               special_pm: int) -> List[str]:
    """The table-shape checks; returns the report lines, raises on a
    wrong answer."""
    if len(rows) != nummons:
        raise ValueError(f"parsed {len(rows)} rows, expected {nummons}")
    for i, row in enumerate(rows):
        if row.idx != i:
            raise ValueError(f"row {i} carries index {row.idx}")
    if rows[0].cname != "giant ant":
        raise ValueError(f"row 0 is {rows[0].cname!r}; the table starts "
                         "with the giant ant")
    if rows[special_pm].enum != "LONG_WORM_TAIL":
        raise ValueError(f"row {special_pm} is {rows[special_pm].enum!r}; "
                         "SPECIAL_PM expects the worm tail")
    # the special section is the G_NOGEN | M2_NOPOLY tail of the table
    for row in rows[special_pm:]:
        if "G_NOGEN" not in row.geno:
            raise ValueError(f"{row.enum}: the special section is G_NOGEN")
        if "M2_NOPOLY" not in row.f2:
            raise ValueError(f"{row.enum}: the special section is M2_NOPOLY")
    return [f"{len(rows)} rows; SPECIAL_PM is {rows[special_pm].enum}"]


def check_identifiers(rows: Sequence[Row]) -> List[str]:
    """Every identifier a row uses must be declared by core.monst_defs,
    and every PM_* anchor there must be the C index of its row."""
    sys.path.insert(0, str(REPO_ROOT))
    from core import monst_defs                       # noqa: E402

    known = {name for name in dir(monst_defs)
             if not name.startswith("__")} | set(ROW_MACROS)
    missing: Dict[str, str] = {}
    pattern = re.compile(r"[A-Za-z_]\w*")
    for row in rows:
        for field in _row_fields(row):
            for token in pattern.findall(field):
                if token not in known:
                    missing.setdefault(token, row.enum)
    if missing:
        raise ValueError(
            "identifiers core.monst_defs does not declare: "
            + ", ".join(f"{name} ({where})"
                        for name, where in sorted(missing.items())))

    anchors = {name: getattr(monst_defs, name) for name in dir(monst_defs)
               if re.fullmatch(r"PM_[A-Z0-9_]+", name)}
    expected = {"PM_" + row.enum: row.idx for row in rows}
    bad = [f"{name}={value} (the table says {expected[name]})"
           for name, value in sorted(anchors.items())
           if name in expected and value != expected[name]]
    if bad:
        raise ValueError("PM_* anchors disagree with monsters.h: "
                         + ", ".join(bad))
    report = [f"{len(anchors)} PM_* anchors agree with the C numbering"]
    stale = sorted(name for name in anchors if name not in expected)
    if stale:
        report.append("anchors with no C row (renamed in 5.0?): "
                      + ", ".join(stale))
    return report


# ------------------------------------------------------------
# Rows -> Python source
# ------------------------------------------------------------

MODULE_DOCSTRING = '''"""The monster type tables of core.monst (generated; do not hand-edit).

Written by `tools/convert_monsters.py`, which reads NetHack 5.0's
`include/monsters.h` and emits one row per C `MON(...)` in the header
order.  The converter is a development tool (nothing imports it) and
this file is checked in; re-run it after a NetHack bump and then run
`python -m core.monst` for the table self-check.

This module holds the three large tables that used to live in monst.py,
all of them in C order:

- `PM_NAMES`  -- the COMPLETE C ordering of all 383 monster types
                 (default build: CHARON undefined; MAIL_STRUCTURES
                 always defined in 5.0 (global.h), so the mail daemon
                 IS in the table; all `#if 0` blocks excluded).  One
                 entry per row -- its neutral name -- so this is what
                 fixes the PM_ numbering;
- `SUBSET_PM` -- the indices of the implemented rows.  Every row is
                 implemented since the converter pass, so it is the
                 whole table; the name stayed because it is what the
                 callers (and monst._validate) mean by it: "the rows
                 that carry a table entry";
- `MONS`      -- the table itself: a PerMonst for every C index, in
                 the C order, so `MONS[PM_BAT]` is the bat.

The rows are built with the `_mon` builder, the `Attack` / `PerMonst`
dataclasses and the constants that core.monst_defs defines, so this
module imports them from there -- and only from there.  That one-way
import is what keeps the constant types inferable (see the monst_defs
docstring): monst_data -> monst_defs, and core.monst imports both.
Import core.monst, the public API; don't import this module directly.

Each row is laid out like the C it came from -- name and class, the
LVL() / geno pair, the six attack slots, SIZ() with the two resistance
columns, the three flag bitmaps, then difficulty and colour -- so a row
can be audited against monsters.h line by line.
"""'''


def _pack(chunks: Sequence[str], indent: str,
          last_suffix: str = "") -> List[str]:
    """Greedily wrap `chunks` into lines, appending `last_suffix` to the
    last one (the closing paren of a call)."""
    lines: List[str] = []
    cur = ""
    for chunk in chunks:
        if cur and len(indent) + len(cur) + 1 + len(chunk) > MAX_LINE:
            lines.append(indent + cur)
            cur = chunk
        else:
            cur = chunk if not cur else cur + " " + chunk
    lines.append(indent + cur + last_suffix)
    return lines


# the constants the generated rows use, grouped for the import block
IMPORT_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("the row builder and its types",
     ("_mon", "_nams", "Attack", "NO_ATK", "NUMMONS", "PerMonst")),
    ("alignments (C: A_*)", ("A_",)),
    ("monster classes (C: S_*)", ("S_",)),
    ("attack types (C: AT_*)", ("AT_",)),
    ("damage types (C: AD_*)", ("AD_",)),
    ("resists and conveyances (C: MR_*, MR2_*)", ("MR_", "MR2_")),
    ("flag bitmaps (C: M1_*, M2_*, M3_*)", ("M1_", "M2_", "M3_")),
    ("sizes and sounds (C: MZ_*, MS_*)", ("MZ_", "MS_")),
    ("geno masks (C: G_*)", ("G_",)),
    ("body weights (C: WT_*)", ("WT_",)),
    ("colours (C: color.h)", ("CLR_", "HI_", "NO_COLOR", "DRAGON_SILVER")),
)

_TOKEN = re.compile(r"[A-Za-z_]\w*")


def _row_fields(row: Row) -> List[str]:
    """Every constant-bearing text field of a row (what the import
    block must cover).  The name column is a string literal, not a
    constant, so it is not one of them."""
    return (list(row.lvl) + [row.geno] + list(row.siz)
            + [row.mr1, row.mr2, row.f1, row.f2, row.f3, row.col,
               row.mlet, *row.atks])


def _emit_imports(rows: Sequence[Row]) -> str:
    """The ``from .monst_defs import (...)`` block: only the names the
    generated rows use, so nothing is unused (flake8 F401)."""
    used: set[str] = {"_mon", "NO_ATK", "NUMMONS", "PerMonst"}
    if any(row.name.startswith("_nams(") for row in rows):
        used.add("_nams")
    for row in rows:
        for field in _row_fields(row):
            used.update(_TOKEN.findall(field))

    out = ["from .monst_defs import ("]
    claimed: set[str] = set()
    for label, prefixes in IMPORT_GROUPS:
        if label.startswith("the row"):
            # the builder first, then the row types: an explicit order,
            # because sorting puts the two _-prefixed helpers last
            names = [n for n in prefixes if n in used]
        else:
            names = sorted(n for n in used
                           if n not in claimed
                           and n.startswith(tuple(prefixes)))
        claimed.update(names)
        if not names:
            continue
        out.append(f"    # {label}")
        out.extend(_pack([f"{n}," for n in names], "    "))
    left = sorted(used - claimed)
    if left:                            # a name that matched no group
        raise ValueError(f"unclassified imports: {left}")
    out.append(")")
    return "\n".join(out)


def _emit_pm_names(rows: Sequence[Row]) -> str:
    out = [
        "",
        "",
        "# ------------------------------------------------------------",
        "# The complete C ordering: the neutral name of every row, in",
        "# mons[] order.  This is the PM_ numbering (monst_defs holds the",
        "# anchors the game code reads by name).",
        "# ------------------------------------------------------------",
        "",
        "PM_NAMES: tuple[str, ...] = (",
    ]
    out.extend(_pack([f'"{row.cname}",' for row in rows], "    "))
    out.append(")")
    return "\n".join(out)


def _emit_subset() -> str:
    return "\n".join([
        "",
        "",
        "# the implemented rows: all of them, since the converter pass",
        "# (the depth-band table it replaced listed the indices by hand)",
        'SUBSET_PM: tuple[int, ...] = tuple(range(NUMMONS))',
    ])


def _emit_mons(rows: Sequence[Row], special_pm: int) -> str:
    out = [
        "",
        "",
        "# ------------------------------------------------------------",
        "# The table (C: struct permonst mons[]; one row per MON() in",
        "# include/monsters.h, so the index of every row is its C monnum)",
        "# ------------------------------------------------------------",
        "",
        "MONS: list[PerMonst | None] = [",
    ]
    prev_mlet = ""
    for row in rows:
        if row.idx == special_pm:
            out.append("    # ---- SPECIAL_PM: the G_NOGEN | M2_NOPOLY")
            out.append("    # ---- section -- never generated, never")
            out.append("    # ---- poly'd into (the quest and role rows)")
            prev_mlet = ""
        if row.mlet != prev_mlet:
            out.append(f"    # ---- {row.mlet} ----")
            prev_mlet = row.mlet
        out.append(f"    # PM_{row.enum}")
        out.append("    _mon(")
        out.extend(_pack([f"{row.idx},", f"{row.mlet},", f"{row.name},"],
                         "        "))
        out.extend(_pack([f"{v}," for v in row.lvl] + [f"{row.geno},"],
                         "        "))
        out.extend(_pack([f"{a}," for a in row.atks], "        "))
        out.extend(_pack([f"{v}," for v in row.siz]
                         + [f"{row.mr1},", f"{row.mr2},"], "        "))
        out.extend(_pack([f"{row.f1},", f"{row.f2},", f"{row.f3},",
                          f"{row.diff},", row.col], "        ",
                         last_suffix="),"))
    out.append("]")
    return "\n".join(out)


def render(rows: Sequence[Row], special_pm: int) -> str:
    """The whole generated module."""
    parts = [
        MODULE_DOCSTRING,
        "",
        "from __future__ import annotations",
        "",
        _emit_imports(rows),
        _emit_pm_names(rows),
        _emit_subset(),
        _emit_mons(rows, special_pm),
        "",
    ]
    return "\n".join(parts)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def main(argv: Sequence[str] = ()) -> int:
    if not C_HEADER.exists():
        print(f"no C header at {C_HEADER}\n"
              "the converter reads NetHack 5.0's include/monsters.h from "
              "the checkout next to pyhack (../NetHack/include)",
              file=sys.stderr)
        return 2
    sys.path.insert(0, str(REPO_ROOT))
    from core import monst_defs                       # noqa: E402

    rows = parse()
    notes = check_rows(rows, monst_defs.NUMMONS, monst_defs.SPECIAL_PM)
    notes += check_identifiers(rows)
    text = render(rows, monst_defs.SPECIAL_PM)
    for note in notes:
        print(note)

    if "--check" in argv:
        current = TARGET.read_text(encoding="utf-8")
        if current == text:
            print(f"{TARGET.name} is up to date")
            return 0
        print(f"{TARGET.name} is out of date: "
              f"{len(current)} bytes on disk, {len(text)} generated")
        return 1

    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
