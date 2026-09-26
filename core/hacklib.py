"""Core text / geometry utilities (home of the hacklib.c port).

Policy (per the porting guidelines): where Python's stdlib or the
`inflect` package does the job, we use those instead of porting the C
idiom:

- C ``digit()``      -> ``str.isdigit()``
- C ``highc/lowc/
   lcase/ucase/
   strncmpi/
   str_start_is/
   str_end_is/
   trimspaces/
   onlyspace/
   tabexpand/
   copynchars/
   stripchars/
   stripdigits``     -> ``str`` methods / ``re`` / ``str.translate``
- C ``isqrt()``      -> ``math.isqrt``
- C ``makeplural`` /
   ``makesingular``  -> ``inflect`` (plural / singular)
- C ``s_suffix``     -> ``inflect.to_possessive`` (with the two
   NetHack-specific cases "it"->"its" and "you"->"your" kept)
- C ``ing_suffix``   -> ``inflect.verb_gerund``

What remains in this module are the pieces that are genuinely
NetHack-specific or have no stdlib equivalent: the '@-is-a-letter'
rule, whitespace munging of input lines, control-character display,
word-boundary lookup, fuzzy name matching, ordinals, the small
geometry helpers (distmin / dist2 / online2), and the status query
functions (is_blind / is_confused / can_see / ...) -- the single home
for every "is this actor in status X?" question.
"""
from __future__ import annotations

import re
from math import isqrt  # noqa: F401  (stdlib replacement for C isqrt)
from typing import Optional, Tuple

import inflect

from .types import Monster

Pos = Tuple[int, int]

_inflect_engine = inflect.engine()

# C mungspaces(): collapse space/tab runs to one space, stop at \n,
# drop the trailing space.
_MUNG_RE = re.compile(r"[ \t]+")


# ------------------------------------------------------------
# Characters
# ------------------------------------------------------------

def letter(c: str) -> bool:
    """NetHack letter test (C: letter): '@' through 'Z' and 'a' through
    'z'.  '@' counts as a letter because inventory letters range
    @..z -- keep this; str.isalpha() does NOT include '@'."""
    return '@' <= c <= 'Z' or 'a' <= c <= 'z'


# ------------------------------------------------------------
# Input-line handling (no stdlib equivalent)
# ------------------------------------------------------------

def mungspaces(s: str) -> str:
    """C: mungspaces -- collapse runs of spaces/tabs to a single space,
    stop at a newline, drop the trailing space."""
    line = s.split('\n', 1)[0]
    return _MUNG_RE.sub(' ', line).rstrip(' ')


def visctrl(c: str) -> str:
    """C: visctrl -- printable representation of a control character:
    ^A, ^?, M-^A, ..."""
    o = ord(c)
    out = ""
    if o & 0x80:
        out = "M-"
        o &= 0x7F
    if o < 0x20:
        return out + "^" + chr(o | 0x40)
    if o == 0x7F:
        return out + "^?"
    return out + chr(o)


# ------------------------------------------------------------
# Name matching (no stdlib equivalent)
# ------------------------------------------------------------

def findword(word_list: str, word: str, ignorecase: bool = False) -> Optional[str]:
    """C: findword -- find an exact word in a space-separated list.

    Returns the word (as it appears in the list) or None.
    """
    for tok in word_list.split(' '):
        if not tok:
            continue
        if ignorecase:
            if tok.lower() == word.lower():
                return tok
        elif tok == word:
            return tok
    return None


def fuzzymatch(s1: str, s2: str, ignore_chars: str, caseblind: bool = False) -> bool:
    """C: fuzzymatch -- equal after dropping any characters in
    `ignore_chars`, optionally ignoring case.  Used to match player
    input against object/monster names."""
    i = j = 0
    n1, n2 = len(s1), len(s2)
    c1 = c2 = ''
    while True:
        while i < n1 and s1[i] in ignore_chars:
            i += 1
        while j < n2 and s2[j] in ignore_chars:
            j += 1
        c1 = s1[i] if i < n1 else ''
        c2 = s2[j] if j < n2 else ''
        if not c1 or not c2:
            break
        if caseblind:
            c1, c2 = c1.lower(), c2.lower()
        if c1 != c2:
            return False
        i += 1
        j += 1
    return not c1 and not c2


# ------------------------------------------------------------
# Word transformations (inflect-backed)
# ------------------------------------------------------------

def makeplural(s: str) -> str:
    """Pluralize (C: makeplural, objnam.c) -- via inflect."""
    return _inflect_engine.plural(s)


def makesingular(s: str) -> str:
    """Singularize (C: makesingular, objnam.c) -- via inflect."""
    return _inflect_engine.singular(s)


def s_suffix(s: str) -> str:
    """Possessive (C: s_suffix, hacklib.c) -- via inflect, with the two
    NetHack-specific cases kept: it -> "its" (not "it's") and
    you -> "your"."""
    low = s.lower()
    if low == "it":
        return s + "s"
    if low == "you":
        return s + "r"
    return _inflect_engine.to_possessive(s)


def ing_suffix(s: str) -> str:
    """Gerund (C: ing_suffix, hacklib.c) -- via inflect:
    tip -> "tipping", vie -> "vying", grease -> "greasing",
    "jump on" -> "jumping on"."""
    return _inflect_engine.verb_gerund(s)


def ordin(n: int) -> str:
    """Ordinal suffix: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st,
    101st, ... (C: ordin -- returns the suffix only)."""
    dd = n % 10
    if dd == 0 or dd > 3 or (n % 100) // 10 == 1:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}[dd]


# ------------------------------------------------------------
# Geometry
# ------------------------------------------------------------

def sgn(n: int) -> int:
    """Sign of n: -1, 0, or 1 (C: sgn)."""
    return (n > 0) - (n < 0)


def distmin(a: Pos, b: Pos) -> int:
    """Minimum number of moves (king-moves) between two points:
    max(|dx|, |dy|) (C: distmin)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def dist2(a: Pos, b: Pos) -> int:
    """Square of the Euclidean distance (C: dist2)."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def online2(a: Pos, b: Pos) -> bool:
    """Are the two points on a straight line -- orthogonal or diagonal?
    (C: online2)"""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dy == 0 or dx == 0 or dy == dx or dy == -dx


def swapbits(val: int, bita: int, bitb: int) -> int:
    """Swap bit `bita` with bit `bitb` in val (C: swapbits)."""
    tmp = ((val >> bita) & 1) ^ ((val >> bitb) & 1)
    return val ^ ((tmp << bita) | (tmp << bitb))


# ------------------------------------------------------------
# Status queries (the single home for actor-state questions)
# ------------------------------------------------------------
#
# NetHack C answers "is the hero in status X?" by testing global
# variables through macros scattered all over the code base:
#
#     if (Blind) { ... }
#     if (Confusion) { ... }
#     if (Hallucination) { ... }
#
# This port keeps the state on the Monster itself (each status is a
# counter of turns remaining, see core.types.Monster) and forbids
# reading those counters directly: every status question goes through
# one of the functions below, and mutation stays in core.rules (the
# state-mutation choke points).  These functions only answer
# questions; they never change state.

def is_asleep(m: Monster) -> bool:
    """True while the actor is asleep (C: Sleeping)."""
    return m.sleeping > 0


def is_stuck(m: Monster) -> bool:
    """True while the actor is stuck in a web / pit."""
    return m.stuck > 0


def is_poisoned(m: Monster) -> bool:
    """True while the actor is poisoned (C: poisoned())."""
    return m.poisoned > 0


def is_confused(m: Monster) -> bool:
    """True while the actor is confused (C: Confusion)."""
    return m.confused > 0


def is_blind(m: Monster) -> bool:
    """True while the actor is blind (C: Blind)."""
    return m.blind > 0


def is_hallucinating(m: Monster) -> bool:
    """True while the actor is hallucinating (C: Hallucination)."""
    return m.hallucinating > 0


def can_see(m: Monster) -> bool:
    """True while the actor's vision is functional (C: !Blind).

    NetHack's cansee() (vision.c) is a full line-of-sight test over
    tiles; this port has no light, fog or line-of-sight yet, so the
    only thing that blocks vision is blindness.  Hallucination
    distorts what the actor sees but does not prevent seeing, so it
    deliberately does not affect this answer.
    """
    return not is_blind(m)
