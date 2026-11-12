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

The tool-type constants (C: engrave.h E_PLAIN .. E_MAGICAL) are the
values of the ``type`` field.
"""

from __future__ import annotations

from typing import Optional

from .types import Engraving, Map, Tile

# C: engrave.h -- the engraving tool types (struct engr.engr_type).
E_PLAIN = 0
E_PEN = 1
E_SABER = 2
E_STYLUS = 3
E_HEADSTONE = 4
E_RUNIC = 5
E_MAGICAL = 6
N_ENGRAVE = 7


def engr_at(map_: Map, x: int, y: int) -> Optional[Engraving]:
    """C: engrave.c#engr_at -- the engraving at (x, y), if any.

    C walks the level-wide ``head_engr`` list for a matching
    (engr_x, engr_y); here the key is the Tile, so it is a tile read.
    """
    if not map_.in_bounds((x, y)):
        return None
    return map_.tile_at((x, y)).engr


def make_engr_at(
    map_: Map, x: int, y: int, text: str, engr_type: int = E_PLAIN
) -> Optional[Engraving]:
    """C: engrave.c#make_engr_at -- make the engraving ``text`` at
    (x, y), replacing any engraving already there.

    C deletes the existing engraving first (``engr_at`` + ``del_engr``)
    and then news a fresh one; here that is a single tile write.  The
    tool type is stored as given (C draws ``rnd(N_ENGRAVE - 1)`` when
    the caller passes a non-positive type -- that roll is a named
    simplification, so callers pass an explicit type).  The Elbereth
    special case (C: ``guardobjects`` / exercise(A_WIS)) is not ported.
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
