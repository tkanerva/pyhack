"""Tests for the hacklib utility port (core.hacklib).

C idioms that now use stdlib/inflect (digit -> str.isdigit, highc ->
str.upper, strncmpi -> str.lower comparisons, isqrt -> math.isqrt,
makeplural -> inflect.plural, ...) are tested through the stdlib/
inflect itself, so the suite covers only what this module still
implements: the NetHack-specific and stdlib-less helpers.
"""
from core import hacklib as h


def test_letter_includes_at():
    # NetHack quirk: inventory letters range '@'..'z'
    assert h.letter("@")
    assert h.letter("Z") and h.letter("z")
    assert not h.letter("[") and not h.letter("0")


def test_mungspaces():
    assert h.mungspaces("  a   b\tc  \n d") == "a b c"
    assert h.mungspaces("   ") == ""
    assert h.mungspaces("\n") == ""
    assert h.mungspaces("a\n b") == "a"  # stops at the newline


def test_visctrl():
    assert h.visctrl("\x01") == "^A"
    assert h.visctrl("\x1f") == "^_"
    assert h.visctrl("\x7f") == "^?"
    assert h.visctrl("A") == "A"
    assert h.visctrl("\x81") == "M-^A"
    assert h.visctrl("\xff") == "M-?"


def test_findword():
    assert h.findword("goblin orc", "orc") == "orc"
    assert h.findword("Goblin ORC", "orc", ignorecase=True) == "ORC"
    assert h.findword("goblin orc", "or") is None  # not a whole word
    assert h.findword("  orc  ", "orc") == "orc"
    assert h.findword("orc", "orcs") is None


def test_fuzzymatch():
    assert h.fuzzymatch("potion of healing", "potionofhealing", " ", False)
    assert h.fuzzymatch("Potion of Healing", "potion of healing", " ", True)
    assert not h.fuzzymatch("potion of healing", "potion of cure", " ", True)
    assert h.fuzzymatch("", "", " ", False)
    assert not h.fuzzymatch("a", "", " ", False)


def test_makeplural_makesingular():
    assert h.makeplural("potion") == "potions"
    assert h.makeplural("knife") == "knives"
    assert h.makeplural("box") == "boxes"
    assert h.makesingular("potions") == "potion"
    assert h.makesingular("knives") == "knife"


def test_s_suffix():
    # the two NetHack-specific cases
    assert h.s_suffix("it") == "its"
    assert h.s_suffix("IT") == "ITs"
    assert h.s_suffix("you") == "your"
    # inflect handles the rest
    assert h.s_suffix("goblin") == "goblin's"
    assert h.s_suffix("goblins") == "goblins'"


def test_ing_suffix():
    assert h.ing_suffix("tip") == "tipping"
    assert h.ing_suffix("run") == "running"
    assert h.ing_suffix("vie") == "vying"
    assert h.ing_suffix("grease") == "greasing"
    assert h.ing_suffix("slither") == "slithering"
    assert h.ing_suffix("eat") == "eating"
    assert h.ing_suffix("jump on") == "jumping on"
    assert h.ing_suffix("climb off") == "climbing off"
    assert h.ing_suffix("walk with") == "walking with"


def test_ordin():
    assert h.ordin(1) == "st"
    assert h.ordin(2) == "nd"
    assert h.ordin(3) == "rd"
    assert h.ordin(4) == "th"
    assert h.ordin(10) == "th"
    for n in (11, 12, 13, 111):
        assert h.ordin(n) == "th"
    assert h.ordin(21) == "st"
    assert h.ordin(100) == "th"
    assert h.ordin(101) == "st"
    assert h.ordin(0) == "th"


def test_geometry():
    assert h.sgn(-5) == -1 and h.sgn(0) == 0 and h.sgn(3) == 1
    assert h.distmin((0, 0), (3, 4)) == 4     # king moves
    assert h.distmin((0, 0), (0, 0)) == 0
    assert h.dist2((0, 0), (3, 4)) == 25
    assert h.online2((0, 0), (2, 2))
    assert h.online2((0, 0), (-3, 0))
    assert h.online2((1, 1), (1, 5))
    assert not h.online2((0, 0), (1, 2))
    assert h.isqrt(0) == 0
    assert h.isqrt(15) == 3
    assert h.isqrt(16) == 4
    assert h.swapbits(0b1001, 0, 3) == 0b1001  # both set: no change
    assert h.swapbits(0b0001, 0, 3) == 0b1000
    assert h.swapbits(0b1000, 0, 3) == 0b0001
