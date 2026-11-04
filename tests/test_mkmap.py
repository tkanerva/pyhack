"""Tests for the cavern generator (core.mkmap).

The cellular automaton is deterministic, small, and its output has a
flat shape: a blob of floor in solid rock, optionally cut into irregular
rooms and joined by corridors.  The tests pin the invariants a playable
level needs, the tuning constants, and the two helpers the room-based
generator shares (flood_fill_rm, litstate_rnd).
"""
from typing import Set, Tuple

import pytest

from core import mkmap as MM
from core.mkmap import (flood_fill_rm, get_map, init_fill, init_map,
                        litstate_rnd, mkmap)
from core.rnd import Rng
from core.types import (NO_ROOM, ROOMOFFSET, Map, RoomType, TerrainType,
                        Tile)

W, H = 40, 20


def _rng(seed: int = 1) -> Rng:
    return Rng(b"mkmap-test:%d" % seed)


def _blank(width: int = W, height: int = H) -> Map:
    return Map([[Tile(typ=TerrainType.STONE) for _ in range(width)]
                for _ in range(height)])


def _passable(m: Map, pos: Tuple[int, int]) -> bool:
    return m.tile_at(pos).typ in (TerrainType.ROOM, TerrainType.CORR,
                                  TerrainType.DOOR, TerrainType.STAIRS)


_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1),
         (1, 1), (1, -1), (-1, 1), (-1, -1))


def _reachable(m: Map, start: Tuple[int, int]) -> Set[Tuple[int, int]]:
    """Flood over the squares the hero can walk to -- diagonals
    included, because that is how a hero moves and how the C flood fill
    groups a cavern (a diagonal-only link is a real passage)."""
    seen = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx, dy in _DIRS:
            pos = (x + dx, y + dy)
            if pos in seen or not m.in_bounds(pos):
                continue
            if _passable(m, pos):
                seen.add(pos)
                frontier.append(pos)
    return seen


# ------------------------------------------------------------
# the small pieces
# ------------------------------------------------------------

def test_litstate_rnd_resolves_the_minus_one_draw():
    """C: `lit < 0` -> `rnd(1 + depth) < 11 && rn2(77)`, and the
    short-circuit matters (the second draw only happens when the first
    test passes)."""
    assert litstate_rnd(_rng(), 1, 5) is True
    assert litstate_rnd(_rng(), 0, 5) is False

    class Counting:
        def __init__(self) -> None:
            self.runs = 0
            self.rands = 0

        def rnd(self, n: int) -> int:
            self.runs += 1
            return 1

        def rn2(self, n: int) -> int:
            self.rands += 1
            return 1

    counting = Counting()
    assert litstate_rnd(counting, -1, 3) is True
    assert counting.runs == 1 and counting.rands == 1

    class Deep(Counting):
        def rnd(self, n: int) -> int:
            self.runs += 1
            return 11   # 11 < 11 is false -> never reaches rn2

    deep = Deep()
    assert litstate_rnd(deep, -1, 10) is False
    assert deep.runs == 1 and deep.rands == 0


def test_init_map_resets_every_square():
    m = _blank()
    m.tiles[5][5] = Tile(typ=TerrainType.ROOM, roomno=7, lit=True, edge=True)
    init_map(m, TerrainType.STONE)
    for x in range(1, m.width):
        for y in range(m.height):
            tile = m.tiles[y][x]
            assert tile.typ == TerrainType.STONE
            assert tile.roomno == NO_ROOM and not tile.lit and not tile.edge


def test_init_fill_puts_about_forty_percent_floor_down():
    m = _blank()
    init_map(m, TerrainType.STONE)
    init_fill(m, _rng(3), TerrainType.STONE, TerrainType.ROOM)
    floor = sum(1 for row in m.tiles for t in row
                if t.typ == TerrainType.ROOM)
    width, height = m.width - 2, m.height - 1
    # init_fill always lands on exactly the limit
    assert floor == (width * height * 2) // 5


def test_get_map_reads_outside_the_level_as_background():
    m = _blank()
    assert get_map(m, 0, 5, TerrainType.STONE) == TerrainType.STONE
    assert get_map(m, m.width - 1, 5, TerrainType.STONE) == TerrainType.STONE
    assert get_map(m, 5, m.height - 1, TerrainType.STONE) == TerrainType.STONE


def test_pass_one_kills_a_lone_square_and_fills_a_gap():
    """C: <= 2 foreground neighbours -> background, >= 5 -> foreground."""
    m = _blank()
    init_map(m, TerrainType.STONE)
    m.tiles[5][5].typ = TerrainType.ROOM          # a lone dot: dies
    for x in range(10, 15):                        # a hole in the blob
        m.tiles[5][x].typ = TerrainType.ROOM
    for y in (4, 6):
        for x in range(10, 15):
            m.tiles[y][x].typ = TerrainType.ROOM
    m.tiles[5][12].typ = TerrainType.STONE         # the gap
    MM.pass_one(m, TerrainType.STONE, TerrainType.ROOM)
    assert m.tile_at((5, 5)).typ == TerrainType.STONE
    assert m.tile_at((12, 5)).typ == TerrainType.ROOM


# ------------------------------------------------------------
# flood fill
# ------------------------------------------------------------

def test_flood_fill_marks_one_region_and_reports_its_extents():
    m = _blank()
    for x in range(5, 9):
        for y in range(4, 7):
            m.tiles[y][x].typ = TerrainType.ROOM
    filled = flood_fill_rm(m, 5, 4, ROOMOFFSET, True, False)
    assert (filled.min_rx, filled.max_rx) == (5, 8)
    assert (filled.min_ry, filled.max_ry) == (4, 6)
    assert filled.count == 12
    for x in range(5, 9):
        for y in range(4, 7):
            tile = m.tiles[y][x]
            assert tile.roomno == ROOMOFFSET and tile.lit is True


def test_flood_fill_marks_the_walls_around_an_anyroom_fill():
    """With `anyroom` the wall ring joins the room as its edge (that is
    how an irregular room learns its own outline)."""
    m = _blank()
    for x in range(5, 9):
        for y in range(4, 7):
            m.tiles[y][x].typ = TerrainType.ROOM
    for x in range(4, 10):
        m.tiles[3][x].typ = TerrainType.HWALL
    filled = flood_fill_rm(m, 6, 5, ROOMOFFSET, False, True)
    assert filled.count == 12
    assert m.tile_at((5, 3)).edge is True
    assert m.tile_at((5, 3)).roomno == ROOMOFFSET


def test_flood_fill_marks_a_shared_wall():
    m = _blank()
    for x in range(2, 6):
        m.tiles[5][x].typ = TerrainType.ROOM
    for x in range(6, 12):
        m.tiles[5][x].typ = TerrainType.ROOM
    m.tiles[4][5].typ = TerrainType.HWALL
    flood_fill_rm(m, 2, 5, ROOMOFFSET, False, True)
    flood_fill_rm(m, 2, 5, ROOMOFFSET + 1, False, True)


# ------------------------------------------------------------
# the finished cavern
# ------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3, 42, 1337])
def test_mkmap_builds_a_walkable_cavern(seed):
    m = _blank()
    mkmap(m, _rng(seed), depth=3)
    floor = [(x, y) for y in range(m.height) for x in range(m.width)
             if m.tile_at((x, y)).typ == TerrainType.ROOM]
    assert len(floor) > 100, "the cavern should be a real level"
    # walled + joined -> a cavernous (not mazelike) level
    assert m.flags.is_cavernous_lev is True
    assert m.flags.is_maze_lev is False
    # rooms exist and every one is irregular (a blob, not a rectangle)
    assert m.rooms
    for room in m.rooms:
        assert room.irregular is True
        assert room.rtype == RoomType.OROOM


@pytest.mark.parametrize("seed", list(range(1, 11)) + [42, 1337])
def test_every_room_of_a_cavern_is_joined(seed):
    """join_map() digs a corridor between consecutive rooms, so no blob
    may be sealed off.  (A tiny hole is erased instead of becoming a
    room -- C: "avoid having the player end up here with no way out".)"""
    m = _blank()
    mkmap(m, _rng(seed), depth=3)
    start = None
    for y in range(m.height):
        for x in range(m.width):
            if m.tile_at((x, y)).typ == TerrainType.ROOM:
                start = (x, y)
                break
        if start:
            break
    assert start is not None
    reach = _reachable(m, start)
    for room in m.rooms:
        inside = [(x, y) for x in range(room.lx, room.hx + 1)
                  for y in range(room.ly, room.hy + 1)
                  if m.tile_at((x, y)).typ == TerrainType.ROOM]
        assert any(pos in reach for pos in inside), "a blob is walled off"


def test_walled_cavern_is_surrounded_by_walls():
    m = _blank()
    mkmap(m, _rng(7), depth=3, walled=True)
    walls = sum(1 for row in m.tiles for t in row
                if t.typ in (TerrainType.HWALL, TerrainType.VWALL))
    assert walls > 0


def test_lit_cavern_lights_the_floor_and_the_rooms():
    m = _blank()
    mkmap(m, _rng(8), depth=3, lit=1)
    lit = sum(1 for row in m.tiles for t in row if t.lit)
    assert lit > 0
    assert any(room.rlit for room in m.rooms)


def test_unlit_cavern_stays_dark():
    m = _blank()
    mkmap(m, _rng(8), depth=3, lit=0)
    assert not any(t.lit for row in m.tiles for t in row)


def test_mkmap_is_deterministic():
    a = _blank()
    b = _blank()
    mkmap(a, _rng(99), depth=3)
    mkmap(b, _rng(99), depth=3)
    assert [[t.typ for t in row] for row in a.tiles] == \
        [[t.typ for t in row] for row in b.tiles]
    c = _blank()
    mkmap(c, _rng(100), depth=3)
    assert [[t.typ for t in row] for row in a.tiles] != \
        [[t.typ for t in row] for row in c.tiles]


def test_remove_rooms_is_a_stub():
    """Overlaying a special level's MAP is the only caller; there are no
    special levels yet, so the STUB says what it waits for."""
    m = _blank()
    with pytest.raises(NotImplementedError):
        MM.remove_rooms(m, 0, 0, 10, 10)
