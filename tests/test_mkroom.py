"""Tests for the room-primitive layer (core.mkroom).

The room records are plain data on the level (core.types.Room); this
module is what everybody else asks about them.  The interesting
behaviour is the geometry: which square is "free" inside a room, which
room a square belongs to, and the shop-shape rejection.
"""

from typing import List

import pytest

from core import mkroom
from core.mklev import add_room, add_subroom, blank_map, topologize
from core.mkroom import (
    ANY_SHOP,
    ANY_TYPE,
    courtmon,
    has_dnstairs,
    has_upstairs,
    inside_room,
    invalid_shop_shape,
    isbig,
    nexttodoor,
    occupied,
    pick_room,
    search_special,
    shrine_pos,
    somex,
    somexy,
    somexyspace,
    somey,
)
from core.rnd import Rng
from core.types import (
    DoorMask,
    Pos,
    Room,
    RoomType,
    Stairway,
    TerrainType,
    Tile,
    Trap,
    TrapType,
    World,
)

W, H = 40, 20


def _rng(seed: int = 1) -> Rng:
    return Rng(b"mkroom-test:%d" % seed)


def _room_map(lx=5, ly=4, hx=12, hy=9) -> "object":
    m = blank_map(W, H)
    room = add_room(m, lx, ly, hx, hy, True, RoomType.OROOM, False)
    topologize(m, room)
    return m, room


def _door(m, pos: Pos, room: Room) -> None:
    """Write a door tile and register it (the tests write the terrain
    themselves, so this only does the bookkeeping)."""
    from core.mklev import add_door

    m.tiles[pos[1]][pos[0]] = Tile(typ=TerrainType.DOOR, door_mask=DoorMask.CLOSED)
    add_door(m, pos[0], pos[1], room)


# ------------------------------------------------------------
# geometry
# ------------------------------------------------------------


def test_isbig_is_the_c_area_test():
    m = blank_map(W, H)
    small = add_room(m, 2, 2, 7, 6, False)  # 6x5 = 30 > 20
    big = add_room(m, 14, 2, 30, 12, False)  # 17x11
    tiny = add_room(m, 2, 10, 5, 13, False)  # 4x4 = 16
    assert not isbig(tiny)
    assert isbig(small) and isbig(big)


def test_somex_somey_stay_inside_the_room():
    m, room = _room_map()
    rng = _rng()
    for _ in range(50):
        x = somex(room, rng)
        y = somey(room, rng)
        assert room.lx <= x <= room.hx
        assert room.ly <= y <= room.hy


def test_inside_room_includes_the_wall_ring():
    """C: inside_room for a rectangular room is the lx-1 .. hx+1 test --
    a staircase on the room's doorway square still counts as "in the
    room" for the stair generator."""
    m, room = _room_map()
    assert inside_room(m, room, (7, 6))
    assert inside_room(m, room, (4, 3))  # a corner of the wall ring
    assert not inside_room(m, room, (1, 1))
    assert not inside_room(m, room, (40, 20))


def test_somexy_returns_a_square_in_the_room():
    m, room = _room_map()
    rng = _rng()
    for _ in range(20):
        pos = somexy(m, room, rng)
        assert pos is not None
        assert room.lx <= pos[0] <= room.hx
        assert room.ly <= pos[1] <= room.hy


def test_somexy_skips_subrooms():
    m, room = _room_map(2, 2, 20, 12)
    sub = add_subroom(m, room, 6, 5, 12, 9, False)
    rng = _rng()
    for _ in range(50):
        pos = somexy(m, room, rng)
        assert pos is not None
        assert not (
            sub.lx - 1 <= pos[0] <= sub.hx + 1 and sub.ly - 1 <= pos[1] <= sub.hy + 1
        )


def test_somexy_for_an_irregular_room_uses_the_room_number():
    """C: irregular rooms are found through levl[].roomno + edge, not
    through a rectangle."""
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, True)
    room.irregular = True
    roomno = m.room_of(room)
    for x in range(5, 11):
        for y in range(4, 9):
            m.tiles[y][x].typ = TerrainType.ROOM
            m.tiles[y][x].roomno = roomno
    m.tiles[4][5].edge = True  # one edge square must never be picked
    rng = _rng()
    for _ in range(50):
        pos = somexy(m, room, rng)
        assert pos is not None
        assert pos != (5, 4)
        assert m.tile_at(pos).roomno == roomno


def test_somexyspace_avoids_occupied_squares():
    """C: somexyspace = somexy filtered by !occupied and ROOM/CORR/ICE."""
    m, room = _room_map(5, 4, 7, 6)  # a 3x3 room, one free square left
    traps: List[Trap] = []
    for i, pos in enumerate(
        [(5, 4), (6, 4), (7, 4), (5, 5), (7, 5), (5, 6), (6, 6), (7, 6)]
    ):
        traps.append(Trap(id=f"t{i}", trap_type=TrapType.PIT, pos=pos))
    rng = _rng()
    pos = somexyspace(m, traps, room, rng)
    assert pos == (6, 5)


def test_occupied_checks_traps_and_furniture_but_not_monsters():
    """C: occupied() is traps + furniture + lava/pool (+ the unported
    invocation position); monsters and items are the caller's job."""
    m, room = _room_map()
    traps = [Trap(id="t0", trap_type=TrapType.PIT, pos=(6, 5))]
    assert occupied(m, traps, (6, 5))
    assert not occupied(m, traps, (7, 5))
    m.tiles[5][7] = Tile(typ=TerrainType.FOUNTAIN)
    assert occupied(m, [], (7, 5))


def test_nexttodoor_looks_at_the_eight_neighbours():
    m, room = _room_map()
    m.tiles[4][6] = Tile(typ=TerrainType.DOOR, door_mask=DoorMask.CLOSED)
    assert nexttodoor(m, 5, 5)
    assert not nexttodoor(m, 8, 8)


def test_has_stairs_asks_the_stairway_list():
    m, room = _room_map()
    down = Stairway(pos=(7, 6), up=False)
    up = Stairway(pos=(9, 7), up=True)
    assert has_dnstairs(m, [down], room)
    assert not has_dnstairs(m, [up], room)
    assert has_upstairs(m, [up], room)
    outside = Stairway(pos=(1, 1), up=False)
    assert not has_dnstairs(m, [outside], room)


# ------------------------------------------------------------
# room lookup
# ------------------------------------------------------------


def test_pick_room_prefers_an_unused_ordinary_room():
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    topologize(m, room)
    _door(m, (5, 3), room)
    add_room(m, 14, 4, 20, 8, False, RoomType.ZOO, False)  # not a candidate
    repicked = pick_room(m, [], _rng(), False)
    assert repicked is room


def test_pick_room_will_take_a_multi_door_room_occasionally():
    """C: `doorct == 1 || !rn2(5)` -- 1 in 5 multi-door rooms is
    accepted anyway, and a room with no door at all never is."""
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    topologize(m, room)
    _door(m, (5, 3), room)
    _door(m, (5, 9), room)
    picks = {pick_room(m, [], _rng(s), False) for s in range(30)}
    assert picks == {room, None}


def test_pick_room_refuses_the_room_the_stairs_are_in():
    """C: an up staircase disqualifies a room outright; a down one only
    2 times in 3 (`has_dnstairs(sroom) && rn2(3)`), so a shop can still
    land on the down-staircase room now and then."""
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    topologize(m, room)
    _door(m, (5, 3), room)
    up = [Stairway(pos=(7, 6), up=True)]
    assert pick_room(m, up, _rng(), True) is None
    assert pick_room(m, up, _rng(), False) is None
    down = [Stairway(pos=(7, 6), up=False)]
    assert pick_room(m, down, _rng(), True) is None
    picks = {pick_room(m, down, _rng(s), False) for s in range(30)}
    assert picks == {room, None}


def test_search_special_finds_by_type_and_by_the_two_wildcards():
    m = blank_map(W, H)
    ordinary = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    zoo = add_room(m, 14, 4, 20, 8, False, RoomType.ZOO, False)
    shop = add_room(m, 24, 4, 30, 8, False, RoomType.ARMORSHOP, False)
    assert search_special(m, RoomType.ZOO) is zoo
    assert search_special(m, RoomType.OROOM) is ordinary
    assert search_special(m, ANY_TYPE) is zoo
    assert search_special(m, ANY_SHOP) is shop
    assert search_special(m, RoomType.TEMPLE) is None


def test_room_of_stair_resolves_through_the_room_number():
    m, room = _room_map()
    stairs = [Stairway(pos=(7, 6), up=False)]
    assert mkroom.room_of_stair(m, stairs, False) is room
    assert mkroom.room_of_stair(m, stairs, True) is None


# ------------------------------------------------------------
# shapes and shrine placement
# ------------------------------------------------------------


def test_shrine_pos_is_the_room_center_when_it_is_free():
    m, room = _room_map(5, 4, 11, 8)  # 7x5 -> odd, exact center 8,6
    pos = shrine_pos(m, [], room, _rng())
    assert pos == (8, 6)


def test_shrine_pos_falls_back_to_a_free_square():
    """A blocked center (the square is not the room's, or is not ROOM)
    means a random free square instead."""
    m, room = _room_map(5, 4, 11, 8)
    m.tiles[6][8] = Tile(typ=TerrainType.FOUNTAIN)
    pos = shrine_pos(m, [], room, _rng())
    assert pos is not None and pos != (8, 6)


def test_invalid_shop_shape_rejects_the_dead_end_square():
    """The shopkeeper must have somewhere to stand inside the door: a
    room whose only square next to the door leads to one other square
    cannot be a shop (C: the themed-room shape

        ---
        +..
        ---

    where the door opens onto a single square with one square past
    it)."""
    m = blank_map(W, H)
    # a 2x1 room, door on the west wall: one square inside the door,
    # one square beyond it -- the dead-end shape
    room = add_room(m, 6, 4, 7, 4, False, RoomType.OROOM, False)
    topologize(m, room)
    _door(m, (5, 4), room)
    assert invalid_shop_shape(m, room) is True
    # a 2x3 room: three squares sit inside the door, so the keeper can
    # step around a customer
    room2 = add_room(m, 10, 4, 14, 6, False, RoomType.OROOM, False)
    topologize(m, room2)
    _door(m, (9, 5), room2)
    assert invalid_shop_shape(m, room2) is False


def test_invalid_shop_shape_needs_a_door():
    m, room = _room_map()
    assert invalid_shop_shape(m, room) is False


# ------------------------------------------------------------
# the special-room dispatch
# ------------------------------------------------------------


def test_do_mkroom_routes_the_zoo_family_and_refuses_the_rest():
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    topologize(m, room)
    _door(m, (5, 3), room)
    w = World(map=m)
    claimed = mkroom.do_mkroom(w, m, [], [], _rng(), 1, RoomType.COURT)
    assert claimed is room and room.rtype == RoomType.COURT
    with pytest.raises(ValueError):
        mkroom.do_mkroom(w, m, [], [], _rng(), 1, RoomType.DELPHI)


def test_monster_producing_handlers_are_stubs():
    """courtmon / squadmon / morguemon / antholemon / mkundead all need
    mkclass() or the monster tables; each names the C it waits for."""
    for call in (
        lambda: courtmon(_rng()),
        lambda: mkroom.squadmon(_rng()),
        lambda: mkroom.morguemon(_rng()),
        lambda: mkroom.antholemon(_rng()),
        lambda: mkroom.mkundead((3, 3), _rng()),
        lambda: mkroom.mk_zoo_thronemon((3, 3), _rng()),
    ):
        with pytest.raises(NotImplementedError):
            call()
