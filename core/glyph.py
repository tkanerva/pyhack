"""The glyph identifier space and the symbol table (display.h / defsym.h).

C's display layer never talks about characters -- it talks about
*glyphs*.  A glyph is an integer that identifies one drawable thing
uniquely: a terrain/feature symbol, an object, a monster, or one of the
two "there is nothing here" markers.  `Tile.glyph` stores one, and only
the window port turns it into a character (C: `print_glyph()`; pyhack:
`ui.console.render()` via `glyph_to_char()` below).

Ported here:

  `Cmap`             C: the S_* cmap symbols (include/sym.h, expanded
                     from the defsym.h PCHAR table) -- values and the
                     character column kept exactly as defsym.h has them
  `CMAP_CHARS`       the character of each cmap symbol (defsym.h's `ch`
                     column, in the same order as the symbols)
  the glyph space    C: `enum glyph_offsets` (include/display.h) plus
                     GLYPH_UNEXPLORED / GLYPH_NOTHING, and the
                     glyph_is_* predicates that read it
  `cmap_to_glyph()` /
  `objclass_to_glyph()`   C: the same two conversion macros

Simplifications, each because the C feature behind it is not ported:

  - the monster glyphs are absent: pyhack has no per-species glyph
    table yet, so a monster is drawn as the single 'M' live overlay
    (ui/console.render) instead of being stored in `Tile.glyph` at all
    (C: `mon_to_glyph` -- a monster is never part of the memory);
  - the object block is one glyph per OBJECT CLASS, not per object
    type: `Item.oclass` is the finest identity the display needs, and
    the class glyph is what def_oc_syms[] gives C anyway for an
    unidentified object;
  - the defsym.h table stops at S_trapped_chest (index 73): the
    special-effect glyphs after it (beams, shields, explosions,
    zaps) are drawn with `tmp_at()` in C and no pyhack system emits
    them yet, so their slots are not carried;
  - the C "branch stairs" / "ladder" glyphs (S_brupstair ... ) are
    listed for completeness but no pyhack level makes one.

The layout of the glyph space, C -> pyhack (the absolute numbers differ
-- C's are derived from NUMMONS / NUM_OBJECTS -- the *order* does not):

    C                                    pyhack
    monsters, pets, detected, ridden     (absent, see above)
    GLYPH_OBJ_OFF + otyp                 GLYPH_OBJ_OFF + oclass
    GLYPH_CMAP_OFF + S_index             GLYPH_CMAP_OFF + S_index
    GLYPH_UNEXPLORED                     GLYPH_UNEXPLORED
    GLYPH_NOTHING                        GLYPH_NOTHING
"""
from __future__ import annotations

from enum import IntEnum


# ============================================================
# The cmap symbols (defsym.h PCHAR table, include/sym.h)
# ============================================================

class Cmap(IntEnum):
    """The S_* cmap symbols.  The values are defsym.h's `idx` column
    exactly (NetHack 5.0, rev 1.27), so `int(Cmap.S_corr)` is the
    cmap index the glyph space offsets."""

    S_stone = 0
    S_vwall = 1
    S_hwall = 2
    S_tlcorn = 3
    S_trcorn = 4
    S_blcorn = 5
    S_brcorn = 6
    S_crwall = 7
    S_tuwall = 8
    S_tdwall = 9
    S_tlwall = 10
    S_trwall = 11
    # --- start cmap A ---
    S_ndoor = 12
    S_vodoor = 13
    S_hodoor = 14
    S_vcdoor = 15
    S_hcdoor = 16
    S_bars = 17
    S_tree = 18
    S_room = 19
    S_darkroom = 20
    S_engroom = 21
    S_corr = 22
    S_litcorr = 23
    S_engrcorr = 24
    S_upstair = 25
    S_dnstair = 26
    S_upladder = 27
    S_dnladder = 28
    S_brupstair = 29
    S_brdnstair = 30
    S_brupladder = 31
    S_brdnladder = 32
    # --- end cmap A ---
    S_altar = 33
    # --- start cmap B ---
    S_grave = 34
    S_throne = 35
    S_sink = 36
    S_fountain = 37
    S_pool = 38
    S_ice = 39
    S_lava = 40
    S_lavawall = 41
    S_vodbridge = 42
    S_hodbridge = 43
    S_vcdbridge = 44
    S_hcdbridge = 45
    S_air = 46
    S_cloud = 47
    S_water = 48
    # --- end dungeon characters ---
    # --- start traps ---
    S_arrow_trap = 49
    S_dart_trap = 50
    S_falling_rock_trap = 51
    S_squeaky_board = 52
    S_bear_trap = 53
    S_land_mine = 54
    S_rolling_boulder_trap = 55
    S_sleeping_gas_trap = 56
    S_rust_trap = 57
    S_fire_trap = 58
    S_pit = 59
    S_spiked_pit = 60
    S_hole = 61
    S_trap_door = 62
    S_teleportation_trap = 63
    S_level_teleporter = 64
    S_magic_portal = 65
    S_web = 66
    S_statue_trap = 67
    S_magic_trap = 68
    S_anti_magic_trap = 69
    S_polymorph_trap = 70
    S_vibrating_square = 71
    S_trapped_door = 72
    S_trapped_chest = 73
    # --- end traps / end cmap B ---


# C: the defsym.h `ch` column, in `idx` order (src/drawing.c expands the
# same table into the default pchar[]).  Indexed by Cmap value, so
# CMAP_CHARS[Cmap.S_vwall] is '|'.
CMAP_CHARS: "tuple[str, ...]" = (
    #    0    1    2    3    4    5    6    7    8    9   10   11
    " ", "|", "-", "-", "-", "-", "-", "-", "-", "-", "|", "|",  # walls
    #   12   13   14   15   16   17   18   19   20   21   22   23
    ".", "-", "|", "+", "+", "#", "#", ".", ".", "`", "#", "#",  # cmap A
    #   24   25   26   27   28   29   30   31   32
    "#", "<", ">", "<", ">", "<", ">", "<", ">",
    #   33   34   35   36   37   38   39   40   41   42   43
    "_", "|", "\\", "{", "{", "}", ".", "}", "}", ".", ".",
    #   44   45   46   47   48
    "#", "#", " ", "#", "}",
    #   49   50   51   52   53   54   55   56   57   58   59
    "^", "^", "^", "^", "^", "^", "^", "^", "^", "^", "^",  # traps
    #   60   61   62   63   64   65   66   67   68   69   70
    "^", "^", "^", "^", "^", "^", '"', "^", "^", "^", "^",
    #   71   72   73
    "~", "^", "^",
)

# C: sym.h -- the size of the pchar[] table.  Pyhack's table stops at
# the trap block (see the module docstring), so this is its length, not
# C's 96.
MAXPCHARS = len(CMAP_CHARS)


# ============================================================
# The glyph space (display.h, enum glyph_offsets)
# ============================================================

# The cmap block.  In C it sits after the monster / object blocks; in
# pyhack the cmap block is first because it is the one the memory
# stores most often, and the ordering below is all the predicates need.
GLYPH_CMAP_OFF = 0
GLYPH_CMAP_MAIN_OFF = GLYPH_CMAP_OFF

# The object block: one glyph per object class (C: per object type).
# C: objclass.h MAXOCLASSES.
MAXOCLASSES = 18
GLYPH_OBJ_OFF = MAXPCHARS

# The two "nothing here" markers (display.h: GLYPH_UNEXPLORED_OFF /
# GLYPH_NOTHING_OFF).  GLYPH_UNEXPLORED is where `Tile.glyph` starts:
# the hero has never seen the square (it draws blank).
GLYPH_UNEXPLORED = GLYPH_OBJ_OFF + MAXOCLASSES
GLYPH_NOTHING = GLYPH_UNEXPLORED + 1

MAX_GLYPH = GLYPH_NOTHING + 1
NO_GLYPH = MAX_GLYPH


# ============================================================
# Predicates and conversions
# ============================================================

def cmap_to_glyph(cmap: "int | Cmap") -> int:
    """C: cmap_to_glyph(cmap_idx) (display.h)."""
    return int(cmap) + GLYPH_CMAP_OFF


def objclass_to_glyph(oclass: int) -> int:
    """The glyph of an object class (C: objnum_to_glyph over the object
    block; pyhack's object block is per class, see the module
    docstring).  A class outside the block falls back to the RANDOM
    class's glyph, which draws nothing -- that keeps the glyph space
    sound (an out-of-range offset would collide with the markers)."""
    if not 0 <= int(oclass) < MAXOCLASSES:
        return GLYPH_OBJ_OFF
    return GLYPH_OBJ_OFF + int(oclass)


def glyph_is_cmap(glyph: int) -> bool:
    """C: glyph_is_cmap -- a terrain/feature symbol."""
    return GLYPH_CMAP_OFF <= glyph < GLYPH_CMAP_OFF + MAXPCHARS


def glyph_is_object(glyph: int) -> bool:
    """C: glyph_is_object -- an object (or a remembered one)."""
    return GLYPH_OBJ_OFF <= glyph < GLYPH_UNEXPLORED


def glyph_is_unexplored(glyph: int) -> bool:
    """C: glyph_is_unexplored -- never seen by the hero."""
    return glyph == GLYPH_UNEXPLORED


def glyph_is_nothing(glyph: int) -> bool:
    """C: glyph_is_nothing -- background only (magic mapping's and
    farlook's "there is really nothing to draw here" marker)."""
    return glyph == GLYPH_NOTHING
