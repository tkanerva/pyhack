"""Tests for the ported level generator (core.mklev): rooms, corridors,
doors, walls, stairs.

These assert *structure*, not exact layouts: the C draw sequence uses
the level size (COLNO/ROWNO in C, map.width/height here), so a byte
comparison against NetHack's own output is not meaningful.  What must
hold is what makes a level playable -- every room reachable, every room
entered through a door, the stairs standing on free floor, and the whole
thing reproducible from a seed.
"""

from typing import Set, Tuple

import pytest

from core import mklev as M
from core.mklev import (
    Rect,
    RectManager,
    add_room,
    blank_map,
    check_room,
    dig_corridor,
    makelevel,
    sort_rooms,
    topologize,
)
from core.rnd import Rng
from core.types import (
    DoorMask,
    Map,
    ROOMOFFSET,
    RoomType,
    SHARED,
    STAIR_DOWN,
    STAIR_UP,
    TerrainType,
    World,
)
from conftest import make_hero

W, H = 40, 20


def _rng(seed: int = 1) -> Rng:
    """The level generators draw through the NetHack rng API (rn2 / rnd
    / rn1 / rnl), i.e. core.rnd.Rng -- not random.Random."""
    return Rng(b"mklev-test:%d" % seed)


def _gen(seed: int = 1, lev: int = 2, max_lev: int = 5) -> Tuple[World, Map]:
    """A generated level in a bare World (no hero needed by makelevel)."""
    rng = _rng(seed)
    w = World(map=blank_map(W, H))
    w.max_lev = max_lev
    w.actors["player"] = make_hero(pos=(1, 1))
    m = makelevel(w, w.map, rng, lev)
    return w, m


def _passable(map_: Map, pos: Tuple[int, int]) -> bool:
    """Walkable, or a door the hero could open (a closed door is not
    walkable, but it is never a dead end)."""
    tile = map_.tile_at(pos)
    if tile.typ == TerrainType.DOOR:
        return True
    return map_.is_walkable(pos)


_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def _reachable(map_: Map, start: Tuple[int, int]) -> Set[Tuple[int, int]]:
    """Flood over the squares the hero can walk to, diagonals included
    (NetHack heroes move in eight directions, and both the room-based
    and the cavern generator do connect floor diagonally -- the C
    flood_fill_rm() recurses through diagonals too)."""
    seen = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx, dy in _DIRS:
            pos = (x + dx, y + dy)
            if pos in seen or not map_.in_bounds(pos):
                continue
            if _passable(map_, pos):
                seen.add(pos)
                frontier.append(pos)
    return seen


# ------------------------------------------------------------
# the building blocks
# ------------------------------------------------------------


def test_blank_map_is_all_stone():
    m = blank_map(10, 6)
    assert m.width == 10 and m.height == 6
    assert all(t.typ == TerrainType.STONE for row in m.tiles for t in row)
    assert m.rooms == [] and m.subrooms == [] and m.doors == []


def test_add_room_paints_walls_corners_and_floor():
    """C: do_room_or_subroom -- the wall ring, the four corner types and
    the ROOM inside; the record is registered on the map."""
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, True, RoomType.OROOM, False)
    assert m.rooms == [room]
    assert (room.lx, room.ly, room.hx, room.hy) == (5, 4, 10, 8)
    assert room.rlit is True
    assert m.tile_at((5, 3)).typ == TerrainType.HWALL  # top wall
    assert m.tile_at((5, 9)).typ == TerrainType.HWALL  # bottom wall
    assert m.tile_at((4, 5)).typ == TerrainType.VWALL  # left wall
    assert m.tile_at((11, 5)).typ == TerrainType.VWALL  # right wall
    assert m.tile_at((4, 3)).typ == TerrainType.TLCORNER
    assert m.tile_at((11, 3)).typ == TerrainType.TRCORNER
    assert m.tile_at((4, 9)).typ == TerrainType.BLCORNER
    assert m.tile_at((11, 9)).typ == TerrainType.BRCORNER
    for x in range(5, 11):
        for y in range(4, 9):
            assert m.tile_at((x, y)).typ == TerrainType.ROOM
    # the light covers the wall ring too (C lights lowx-1 .. hix+1)
    assert m.tile_at((4, 3)).lit and m.tile_at((7, 6)).lit
    assert room.needjoining is True
    assert room.doorct == 0


def test_add_room_special_only_records_geometry():
    """`special` rooms are recorded, never painted (C: the caller drew
    the terrain)."""
    m = blank_map(W, H)
    add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, True)
    assert all(t.typ == TerrainType.STONE for row in m.tiles for t in row)


def test_topologize_stamps_roomno_and_edges():
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    topologize(m, room)
    roomno = ROOMOFFSET + 0
    assert m.room_at((7, 6)) is room
    assert m.tile_at((7, 6)).roomno == roomno
    # the wall ring is the room's edge
    assert m.tile_at((5, 3)).edge and m.tile_at((4, 5)).edge
    assert m.tile_at((5, 3)).roomno == roomno
    # outside the room nothing was stamped
    assert m.tile_at((1, 1)).roomno == 0
    assert m.room_at((1, 1)) is None


def test_topologize_marks_a_shared_boundary():
    """A wall square two rooms both claim becomes SHARED (C: the
    `if (levl[x][y].roomno) ... else SHARED` branch)."""
    m = blank_map(W, H)
    left = add_room(m, 4, 4, 9, 8, False, RoomType.OROOM, False)
    right = add_room(m, 11, 4, 16, 8, False, RoomType.OROOM, False)
    topologize(m, left)
    topologize(m, right)
    assert m.tile_at((10, 4)).roomno == SHARED
    assert m.room_at((10, 4)) is None  # SHARED belongs to no single room


def test_sort_rooms_orders_left_to_right_and_renumbers():
    m = blank_map(W, H)
    far = add_room(m, 20, 4, 25, 8, False, RoomType.OROOM, False)
    near = add_room(m, 4, 4, 9, 8, False, RoomType.OROOM, False)
    topologize(m, far)
    topologize(m, near)
    sort_rooms(m)
    assert m.rooms == [near, far]
    assert m.room_at((5, 5)) is near
    assert m.tile_at((5, 5)).roomno == ROOMOFFSET
    assert m.tile_at((22, 5)).roomno == ROOMOFFSET + 1


def test_check_room_refuses_a_taken_spot():
    m = blank_map(W, H)
    add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    assert check_room(m, 6, 5, 4, 3, _rng()) is None


def test_check_room_accepts_free_rock():
    m = blank_map(W, H)
    out = check_room(m, 12, 6, 4, 3, _rng())
    assert out is not None
    lowx, lowy, ddx, ddy = out
    assert lowx == 12 and lowy == 6 and ddx >= 1 and ddy >= 1


def test_dig_corridor_connects_two_points():
    m = blank_map(W, H)
    ok, npoints = dig_corridor(
        m, _rng(), 3, (3, 3), (12, 8), False, TerrainType.CORR, TerrainType.STONE
    )
    assert ok and npoints > 0
    # the corridor is a connected run of dug squares from org to dest
    # (C digs an L and turns whenever the two axis distances balance)
    seen = {(3, 3)}
    frontier = [(3, 3)]
    while frontier:
        x, y = frontier.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pos = (x + dx, y + dy)
            if pos in seen or not m.in_bounds(pos):
                continue
            if m.tile_at(pos).typ != TerrainType.STONE:
                seen.add(pos)
                frontier.append(pos)
    assert (12, 8) in seen
    assert npoints >= len(seen) - 1


def test_rect_manager_splits_a_room_out_of_the_level():
    """C: rect.c -- a room carves its box (plus margin) out of a free
    rectangle; the remainder stays available."""
    m = blank_map(W, H)
    rects = RectManager(m)
    assert rects.rects == [Rect(0, 0, W - 1, H - 1)]
    r1 = rects.rnd_rect(_rng(1))
    assert r1 is not None
    rects.split_rects(r1, Rect(10, 5, 20, 10))
    assert Rect(10, 5, 20, 10) not in rects.rects
    assert all(not r.contains(Rect(10, 5, 20, 10)) for r in rects.rects)


# ------------------------------------------------------------
# the finished level
# ------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 1337])
def test_makelevel_builds_rooms_and_corridors(seed):
    world, m = _gen(seed)
    assert m.rooms, "the generator must make rooms"
    assert m.flags.is_cavernous_lev is False
    # every room is a real rectangle of standable floor
    for room in m.rooms:
        assert room.rtype == RoomType.OROOM
        # the corner is ROOM floor -- or one of the furniture kinds
        # fill_ordinary_room() places, because find_okay_roompos() draws
        # somexyspace() over the whole room rectangle, corners included
        # (C: rnd_loc); a wall there would be a bug, a fountain is not
        assert m.tile_at((room.lx, room.ly)).typ in (
            TerrainType.ROOM,
            TerrainType.FOUNTAIN,
            TerrainType.SINK,
            TerrainType.ALTAR,
            TerrainType.GRAVE,
        )
        assert room.hx > room.lx and room.hy > room.ly
    # and the level is not a solid block: corridors exist
    corrs = [
        (x, y)
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ in (TerrainType.CORR, TerrainType.SCORR)
    ]
    assert corrs, "makecorridors() must dig at least one corridor"


@pytest.mark.parametrize("seed", list(range(1, 11)) + [42, 1337])
def test_every_room_is_reachable_from_the_hero_side(seed):
    """The whole point of makecorridors(): no room may be sealed off."""
    world, m = _gen(seed)
    stairs = [
        (x, y)
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ == TerrainType.STAIRS
    ]
    assert stairs, "the level must have staircases"
    reach = _reachable(m, stairs[0])
    for room in m.rooms:
        inside = [
            (x, y)
            for x in range(room.lx, room.hx + 1)
            for y in range(room.ly, room.hy + 1)
        ]
        assert any(
            pos in reach for pos in inside
        ), f"room {room.lx},{room.ly} is walled off"


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 1337])
def test_every_room_is_entered_through_a_door(seed):
    """Rooms connect through doors, not through holes in the wall."""
    world, m = _gen(seed)
    for room in m.rooms:
        assert room.doorct >= 1, f"room {room.lx},{room.ly} has no door"
        for door in room.doors:
            assert m.tile_at(door).typ in (TerrainType.DOOR, TerrainType.SDOOR)
    # doors are level-wide bookkeeping too (C: svd.doors[])
    assert len(m.doors) >= len(m.rooms)


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 1337])
def test_doors_carry_a_valid_state(seed):
    world, m = _gen(seed)
    for y in range(m.height):
        for x in range(m.width):
            tile = m.tiles[y][x]
            if tile.typ == TerrainType.DOOR:
                assert tile.door_mask in (
                    DoorMask(0),
                    DoorMask.ISOPEN,
                    DoorMask.CLOSED,
                    DoorMask.LOCKED,
                    DoorMask.CLOSED | DoorMask.TRAPPED,
                    DoorMask.LOCKED | DoorMask.TRAPPED,
                )
            elif tile.typ == TerrainType.SDOOR:
                # a secret door is part of the wall until it is found
                assert tile.door_mask & (DoorMask.CLOSED | DoorMask.LOCKED)


def test_level_has_a_down_stair_and_an_up_stair():
    """C: generate_stairs -- the down staircase first, then the up one;
    level 1 gets no upstairs, the bottom level no downstairs."""
    world, m = _gen(1, lev=2, max_lev=5)
    downs = [
        (x, y)
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ == TerrainType.STAIRS
        and m.tile_at((x, y)).stair_dir == STAIR_DOWN
    ]
    ups = [
        (x, y)
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ == TerrainType.STAIRS
        and m.tile_at((x, y)).stair_dir == STAIR_UP
    ]
    assert len(downs) == 1 and len(ups) == 1

    world, m = _gen(1, lev=1, max_lev=5)
    assert not any(
        m.tile_at((x, y)).stair_dir == STAIR_UP
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ == TerrainType.STAIRS
    )

    world, m = _gen(1, lev=5, max_lev=5)
    assert not any(
        m.tile_at((x, y)).stair_dir == STAIR_DOWN
        for y in range(m.height)
        for x in range(m.width)
        if m.tile_at((x, y)).typ == TerrainType.STAIRS
    )


def test_stairs_stand_on_free_room_floor():
    world, m = _gen(42, lev=3, max_lev=5)
    for y in range(m.height):
        for x in range(m.width):
            tile = m.tiles[y][x]
            if tile.typ != TerrainType.STAIRS:
                continue
            assert m.is_walkable((x, y))
            assert m.room_at((x, y)) is not None


def test_same_seed_same_level():
    """Determinism: the generator is a pure function of (seed, size,
    depth) -- only the injected rng drives it."""
    _, a = _gen(99)
    _, b = _gen(99)
    assert [[t.typ for t in row] for row in a.tiles] == [
        [t.typ for t in row] for row in b.tiles
    ]
    assert [(r.lx, r.ly, r.hx, r.hy) for r in a.rooms] == [
        (r.lx, r.ly, r.hx, r.hy) for r in b.rooms
    ]
    assert a.doors == b.doors
    _, c = _gen(100)
    assert [[t.typ for t in row] for row in a.tiles] != [
        [t.typ for t in row] for row in c.tiles
    ]


def test_the_generator_stocks_the_level():
    """fill_ordinary_room(): monsters and the demo trap kit land on the
    level (gold / chests / fountains wait for the object port).

    C puts a sleeping monster in two rooms out of three and runs the
    trap loop after that, so a *single* level can legitimately come out
    empty -- and the demo's 40x20 grid only holds 2..6 rooms, because
    the free-rectangle margins (XLIM 4 / YLIM 3) are NetHack's and a
    NetHack-sized map makes twice as many (80x21 gives 8 rooms).  The
    check therefore spans a handful of seeds and asserts the invariants
    of whatever was placed instead of pinning one lucky level.
    """
    monsters = traps = 0
    for seed in range(1, 11):
        world, m = _gen(seed, lev=2, max_lev=5)
        for mon in world.actors.values():
            if mon.is_hero:
                continue
            monsters += 1
            assert mon.lev == 2
            assert m.is_walkable(mon.pos)
            assert m.room_at(mon.pos) is not None, "C: inside a room"
            assert mon.sleeping, "C: a placed monster sleeps (MM_ASLEEP)"
        for trap in world.traps.values():
            traps += 1
            assert trap.lev == 2
            assert m.in_bounds(trap.pos)
            assert m.is_walkable(trap.pos)
    assert monsters, "the room filler must place monsters"
    assert traps, "the room filler must place traps"


def test_level_size_comes_from_the_map():
    """The C generators are COLNO/ROWNO bound; this port reads the map,
    so a small grid works (and stays inside its bounds)."""
    rng = _rng(4)
    w = World(map=blank_map(24, 12))
    w.max_lev = 3
    m = makelevel(w, w.map, rng, 2)
    assert m.width == 24 and m.height == 12
    assert m.rooms
    for x, y in [
        (x, y)
        for room in m.rooms
        for x in (room.lx, room.hx)
        for y in (room.ly, room.hy)
    ]:
        assert 0 < x < 24 and 0 < y < 12


def test_makelevel_is_idempotent_over_an_existing_level():
    """clear_level_structures() wipes the map, the rooms, the flags and
    the level's items / traps / monsters (C frees the level's object and
    monster lists in the same call), so generating twice into the same
    Map over the same World is safe."""
    world, m = _gen(11)
    first = [[t.typ for t in row] for row in m.tiles]
    makelevel(world, m, _rng(11), 2)
    second = [[t.typ for t in row] for row in m.tiles]
    assert first == second
    assert len(m.doors) == len(set(m.doors))


# ------------------------------------------------------------
# the special-room hooks (STUBs, deliberately)
# ------------------------------------------------------------


def test_special_room_handlers_are_stubs():
    """The zoo / shop / swamp stocking half needs its machinery; each
    STUB names the C it waits for instead of silently doing nothing.
    (The temple is in: core.mkroom.mktemple + core.priest,
    PLAN-SPECIAL-ROOMS.md phase 1 -- tests/test_priest.py.)"""
    from core import mkroom

    m = blank_map(W, H)
    add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    with pytest.raises(NotImplementedError):
        mkroom.fill_zoo(m, [], m.rooms[0], _rng())
    with pytest.raises(NotImplementedError):
        mkroom.mkshop(m, [], _rng())
    with pytest.raises(NotImplementedError):
        mkroom.mkswamp(m, [], _rng())


def test_mkzoo_only_records_the_room_type():
    """mkzoo is the one special-room handler that needs no stocking: it
    picks a room and sets its type (C sets needfill and stocks later).

    pick_room() wants a single-door room (C: `doorct == 1 || !rn2(5)`),
    so the room gets its door first.
    """
    from core import mkroom

    m = blank_map(W, H)
    room = add_room(m, 5, 4, 10, 8, False, RoomType.OROOM, False)
    M.add_door(m, 5, 3, room)
    claimed = mkroom.mkzoo(m, [], _rng(), RoomType.ZOO)
    assert claimed is room
    assert room.rtype == RoomType.ZOO
