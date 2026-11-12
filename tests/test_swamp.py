"""Tests for the swamp (core.mkroom.mkswamp) -- PLAN-SPECIAL-ROOMS.md
phase 3.

What must hold: up to five rooms are flooded, each set to SWAMP and
stocked inline (the swamp, like the temple, sets no needfill, so the
end-of-level fill_special_room refuses it); pools land only on the
(sx+sy) % 2 checkerboard squares, never in a doorway (the nexttodoor
guard) and never on an occupied square; the pools run over any
engraving (del_engr_at); the pool squares get eels (the first one
always, the rest by a 1-in-4 roll -- giant eel / piranha / electric
eel) standing in the water; the dry squares get S_FUNGUS by a 1-in-4
roll; and flags.has_swamp is set iff at least one room was swamped.
"""

from typing import Tuple

from core import mkroom
from core.mklev import add_door, add_room, blank_map, topologize
from core.monst_defs import S_EEL, S_FUNGUS
from core.rnd import Rng
from core.types import (
    DoorMask,
    FILL_NONE,
    Map,
    Room,
    RoomType,
    TerrainType,
    Tile,
    World,
)
from conftest import assert_item_locations, make_hero

W, H = 40, 20
LX, LY, HX, HY = 5, 4, 14, 10  # a 10x7 floor: 70 squares
DOOR = (LX, LY - 1)  # the top-wall door (5, 3)


def _rng(seed: int = 1) -> Rng:
    return Rng(b"swamp-test:%d" % seed)


def _room_map(door: bool = True) -> Tuple[Map, Room]:
    """A single lit 10x7 room (floor 5..14 by 4..10) with one door on
    the top wall (the shape the other room tests use).  The door tile
    keeps the stamped roomno / edge / lit of the wall it replaces."""
    m = blank_map(W, H)
    room = add_room(m, LX, LY, HX, HY, True, RoomType.OROOM, False)
    topologize(m, room)
    if door:
        wall = m.tiles[LY - 1][LX]
        m.tiles[LY - 1][LX] = Tile(
            typ=TerrainType.DOOR,
            door_mask=DoorMask.CLOSED,
            roomno=wall.roomno,
            edge=wall.edge,
            lit=wall.lit,
        )
        add_door(m, LX, LY - 1, room)
    return m, room


def _world(m: Map, lev: int) -> World:
    w = World(map=m)
    w.lev = lev
    w.actors["player"] = make_hero(pos=(1, 1))
    return w


def _pools(m: Map):
    return [
        (x, y)
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.POOL
    ]


def _mons(w: World, lev: int, mlet):
    return [
        a
        for a in w.actors.values()
        if not a.is_hero
        and a.lev == lev
        and a.pos is not None
        and a.mdata is not None
        and a.mdata.mlet == mlet
    ]


# ------------------------------------------------------------
# the terrain (pools on the checkerboard, never in a doorway)
# ------------------------------------------------------------


def test_pools_land_only_on_checkerboard_squares_not_in_doorways():
    """PLAN-SPECIAL-ROOMS.md phase 3: a pool is written only on a
    (sx+sy) % 2 square (the other half stays floor) and never in a
    doorway (the nexttodoor guard); the room is set to SWAMP and
    flags.has_swamp is set."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    assert room.rtype == RoomType.SWAMP
    assert m.flags.has_swamp
    pools = _pools(m)
    assert pools  # the room has checkerboard squares
    for (x, y) in pools:
        assert (x + y) % 2 == 1, (x, y)
        assert not mkroom.nexttodoor(m, x, y), (x, y)
    # the door is still a door (the pool ran past it, not over it)
    assert m.tile_at(DOOR).typ == TerrainType.DOOR
    assert_item_locations(w)


def test_pools_run_over_an_engraving():
    """C: del_engr_at before the pool write -- the pool square's
    engraving is removed (the pools run over it)."""
    from core import engrave

    m, room = _room_map()
    w = _world(m, 5)
    # (6, 5): 6 + 5 = 11 (odd) -- a checkerboard square, free, and not
    # next to the door (5, 3), so it becomes a pool
    engrave.make_engr_at(m, LX + 1, LY + 1, "Elbereth")
    assert m.tile_at((LX + 1, LY + 1)).engr is not None
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    assert m.tile_at((LX + 1, LY + 1)).typ == TerrainType.POOL
    assert m.tile_at((LX + 1, LY + 1)).engr is None
    assert_item_locations(w)


# ------------------------------------------------------------
# the stocking (eels in the water, fungus on the dry squares)
# ------------------------------------------------------------


def test_eels_are_in_the_water():
    """C: a pool square gets an eel when it is the first (eelct == 0)
    or by a 1-in-4 roll; the species is the giant eel / piranha /
    electric eel (all S_EEL -- mkclass() "won't do, as we might get
    kraken").  Every eel stands in the water."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    eels = _mons(w, 5, S_EEL)
    assert eels  # the first pool square always gets one
    for eel in eels:
        assert m.tile_at(eel.pos).typ == TerrainType.POOL, eel.pos
    assert_item_locations(w)


def test_fungus_are_on_the_dry_squares():
    """C: the non-checkerboard square gets a S_FUNGUS monster by a
    1-in-4 roll ("swamps tend to be moldy").  Every fungus stands on a
    dry (ROOM) square, never in the water."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    fungus = _mons(w, 5, S_FUNGUS)
    assert fungus  # ~1 in 4 of the ~35 dry squares, seed 1 has some
    for f in fungus:
        assert m.tile_at(f.pos).typ == TerrainType.ROOM, f.pos
    assert_item_locations(w)


# ------------------------------------------------------------
# the two-phase model (the swamp is stocked inline, not by the dispatcher)
# ------------------------------------------------------------


def test_the_swamp_is_stocked_inline_not_by_the_dispatcher():
    """PLAN-SPECIAL-ROOMS.md: the swamp, like the temple, is stocked in
    its mk* handler (no needfill), so the end-of-level
    fill_special_room refuses it (needfill == FILL_NONE) and adds
    nothing."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    assert room.needfill == FILL_NONE
    before = len(_pools(m))
    mkroom.fill_special_room(w, _rng(), m, [], room, 5)
    assert len(_pools(m)) == before
    assert_item_locations(w)


def test_the_room_stays_walkable_after_the_swamp():
    """PLAN-SPECIAL-ROOMS.md phase 3: the swamp turns floor into POOL
    (and puts eels / fungus on it) but the room's floor stays
    walkable terrain and the door stays a door."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkswamp(w, m, [], [], _rng(), 5)
    for sx in range(LX, HX + 1):
        for sy in range(LY, HY + 1):
            typ = m.tile_at((sx, sy)).typ
            assert typ in (TerrainType.ROOM, TerrainType.POOL), (sx, sy, typ)
    assert m.tile_at(DOOR).typ == TerrainType.DOOR
    assert_item_locations(w)
