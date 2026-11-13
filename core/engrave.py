"""Floor engravings -- the minimal engraving model.

Port of the create / look-up / delete half of the NetHack 5.0 engraving
system (src/engrave.c), the part the level generators and the shop door
sign need.  C keeps a level-wide linked list (``head_engr``) of
``struct engr`` keyed by (engr_x, engr_y); this port keeps the engraving
on the Tile itself (``Tile.engr``, see core.types.Engraving), so the
list and its walk are replaced by a tile field.

C provenance (the spans, verified against nethack_index/symbols):

  src/engrave.c  engr_at() 231-242, make_engr_at() 408-458,
                 del_engr_at() 461-468 (which calls del_engr() 1666-1685)

Included:

  engr_at(map_, x, y)   -- the engraving at the square, if any
  make_engr_at(...)     -- make (or replace) the engraving at the square
  del_engr_at(map_, x, y) -- remove the engraving at the square (the
                 half the swamp pools run over and the shop door sign
                 and the graves use)

Not ported, each named: the three text copies (actual / remembered /
pristine) collapse to one (the hero never re-reads or repairs an
engraving in this wave); the time-based wear (engr_time, the "the
engraving wears away" path) is not ported; the Elbereth special case in
make_engr_at (C: ``guardobjects`` / exercise(A_WIS)) is not ported; the
doengrave() / read_engr_at() / wipe_engr_at() player-facing half (the
``-e`` command, the "You feel a surge of power" path) is not ported.

The engraving types (C: engrave.h DUST .. HEADSTONE, the values of the
``type`` field) are the E_* constants below.
"""

from __future__ import annotations

from typing import Optional

from .types import Engraving, Map, Tile

# C: engrave.h -- the engraving types (struct engr.engr_type).  These
# are this NetHack's names and values: DUST 1, ENGRAVE 2, BURN 3, MARK 4,
# ENGR_BLOOD 5, HEADSTONE 6, N_ENGRAVE 6 (engrave.h rev 1.22).  The
# E_* spelling is the port's; C spells them DUST / ENGRAVE / BURN / ...
# (a bare DUST would collide with nothing here, but the E_ prefix keeps
# the call sites readable next to the E_-less engrave_type field).
E_DUST = 1  # C: DUST -- a finger, a wand of digging, a tool tip
E_ENGRAVE = 2  # C: ENGRAVE -- a hard tool (the rnd(5) default range)
E_BURN = 3  # C: BURN -- a wand of fire / a lit torch
E_MARK = 4  # C: MARK -- a wand of striking / a weapon point
E_ENGR_BLOOD = 5  # C: ENGR_BLOOD -- written in blood
E_HEADSTONE = 6  # C: HEADSTONE -- a grave's headstone
N_ENGRAVE = 6  # C: N_ENGRAVE -- the count (rnd(N_ENGRAVE - 1) is the
#                     roll C would make for an unknown tool: 1..5)


def engr_at(map_: Map, x: int, y: int) -> Optional[Engraving]:
    """C: engrave.c#engr_at -- the engraving at (x, y), if any.

    C walks the level-wide ``head_engr`` list for a matching
    (engr_x, engr_y); here the key is the Tile, so it is a tile read.
    """
    if not map_.in_bounds((x, y)):
        return None
    return map_.tile_at((x, y)).engr


def make_engr_at(
    map_: Map, x: int, y: int, text: str, engr_type: int = E_DUST
) -> Optional[Engraving]:
    """C: engrave.c#make_engr_at -- make the engraving ``text`` at
    (x, y), replacing any engraving already there.

    C deletes the existing engraving first (``engr_at`` + ``del_engr``)
    and then news a fresh one; here that is a single tile write.  The
    engraving type is stored as given; C rolls ``rnd(N_ENGRAVE - 1)``
    (1..5 -- never HEADSTONE) whenever the caller passes a non-positive
    type, and that roll is a named simplification, so callers pass an
    explicit ``E_*`` value and the default is the plainest one, DUST.
    The Elbereth special case (C: ``guardobjects`` when ``in_mklev``,
    exercise(A_WIS) otherwise) is not ported.
    """
    if not map_.in_bounds((x, y)):
        return None
    tile: Tile = map_.tile_at((x, y))
    engraving = Engraving(text=text, type=engr_type)
    tile.engr = engraving
    return engraving


def del_engr_at(map_: Map, x: int, y: int) -> None:
    """C: engrave.c#del_engr_at -- remove the engraving at (x, y) (the
    half the swamp pools run over and the shop door sign and the graves
    use).  C looks the engraving up and unlinks it; here it is a tile
    write.  A square with no engraving is left alone (C: the ``if (ep)``
    guard)."""
    if not map_.in_bounds((x, y)):
        return
    map_.tile_at((x, y)).engr = None
