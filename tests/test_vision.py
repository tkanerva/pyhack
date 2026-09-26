"""Tests for core/vision.py -- the port of src/vision.c.

Vision is an algorithm, so the high-value tests are algorithmic:
clear_path() (the Bresenham line of sight) is checked EXHAUSTIVELY
against an independent geometric oracle on whole maps, and the
could_see field (Algorithm C) against hand-computed tile sets.  The
gameplay wiring (monsters pursuing the hero through step()) is
covered in tests/test_step.py.
"""
from core.types import (DoorMask, Item, ObjectType, Tile, TerrainType)
from core.vision import (can_see, clear_path, could_see, do_clear_area,
                         m_can_see, m_can_see_u, set_tile, unblock_point,
                         vision_recalc, vision_reset)
from conftest import make_hero, make_map, make_monster, make_world


# ------------------------------------------------------------
# Independent line-of-sight oracle (for the exhaustive tests)
# ------------------------------------------------------------

def _segment_hits_open_square(x0, y0, x1, y1, tx, ty):
    """True if the centre-to-centre segment -- in DOUBLED tile
    coordinates, where tile (i, j) spans (2i, 2i+2) x (2j, 2j+2) --
    has a positive-length intersection with the INTERIOR of tile
    (tx, ty).

    Liang-Barsky clip against the open square: a segment that merely
    touches a tile at a corner or along an edge counts as clear --
    that is NetHack's corner-cutting rule (a single diagonal step
    never checks the corner tiles).  The independent geometric
    definition of what clear_path() must return.
    """
    dx = x1 - x0
    dy = y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - 2 * tx, 2 * tx + 2 - x0,
         y0 - 2 * ty, 2 * ty + 2 - y0)
    t0 = 0.0
    t1 = 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi <= 0:  # parallel, on or outside the boundary
                return False
        else:
            t = qi / pi
            if pi < 0:
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
    return t1 > t0  # strictly positive length inside the open square


def _los_tiles(a, b):
    """The tiles STRICTLY BETWEEN a and b on the sight line (the
    oracle's version of what the Bresenham paths check)."""
    x0, y0 = 2 * a[0] + 1, 2 * a[1] + 1
    x1, y1 = 2 * b[0] + 1, 2 * b[1] + 1
    out = []
    for ty in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
        for tx in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
            if (tx, ty) in (a, b):
                continue
            if _segment_hits_open_square(x0, y0, x1, y1, tx, ty):
                out.append((tx, ty))
    return out


def _test_maps():
    maps = [
        make_world(),  # open 12x8
        make_world(map=make_map(
            walls=((4, 3), (4, 4), (5, 2), (7, 5), (8, 3)))),
        make_world(map=make_map(width=5, height=5,
                                walls=((2, 0), (2, 1), (2, 3), (2, 4))),
                   hero=make_hero(pos=(0, 2))),
    ]
    # a closed door in an otherwise stone column
    wdoor = make_world(map=make_map(walls=[(5, y) for y in range(1, 8)]),
                       hero=make_hero(pos=(2, 4)))
    set_tile(wdoor, (5, 4), Tile(typ=TerrainType.DOOR,
                                 door_mask=DoorMask.CLOSED))
    maps.append(wdoor)
    return maps


def test_clear_path_matches_geometry_exhaustively():
    """Every tile pair on several maps: clear_path() must agree with
    the independent geometric definition (all tiles strictly between
    the endpoints are clear)."""
    for w in _test_maps():
        vision_reset(w)
        tiles = [(x, y) for y in range(w.map.height)
                 for x in range(w.map.width)]
        for a in tiles:
            for b in tiles:
                blocked = any(not w.map.viz_clear[y][x]
                              for (x, y) in _los_tiles(a, b))
                assert clear_path(w, a, b) == (not blocked), \
                    (a, b, _los_tiles(a, b))


def test_clear_path_trivial_cases():
    w = make_world()
    vision_reset(w)
    assert clear_path(w, (6, 4), (6, 4))   # same point: always clear
    assert clear_path(w, (6, 4), (7, 4))   # adjacent: nothing between
    assert clear_path(w, (7, 4), (6, 4))   # symmetric
    set_tile(w, (7, 4), Tile(typ=TerrainType.STONE))
    assert not clear_path(w, (6, 4), (8, 4))  # wall strictly between
    assert clear_path(w, (6, 4), (7, 4))      # wall at the ENDPOINT: visible
    assert clear_path(w, (7, 4), (8, 4))      # endpoints are never checked


# ------------------------------------------------------------
# Algorithm C (the hero's could_see field)
# ------------------------------------------------------------

def test_algorithm_c_wall_with_gap():
    """Hand-computed field of view: a stone column x=2 with a single
    gap at (2,2), hero at the left edge (0,2).  The hero sees the left
    half, the wall faces, the gap row straight through -- and nothing
    on the right half above/below the gap row.

        . . # . .
        . . # . .
        @ . . . .
        . . # . .
        . . # . .
    """
    w = make_world(map=make_map(width=5, height=5,
                                walls=((2, 0), (2, 1), (2, 3), (2, 4))),
                   hero=make_hero(pos=(0, 2)))
    vision_recalc(w)
    expected = {(0, 0), (1, 0), (2, 0),
                (0, 1), (1, 1), (2, 1),
                (0, 2), (1, 2), (2, 2), (3, 2), (4, 2),
                (0, 3), (1, 3), (2, 3),
                (0, 4), (1, 4), (2, 4)}
    got = {(x, y) for y in range(5) for x in range(5)
           if could_see(w, (x, y))}
    assert got == expected


def test_can_see_matches_could_see_without_lighting():
    """STUB semantics: with no light system yet, everything the hero
    could see is lit, so can_see() == could_see() (C: the IN_SIGHT
    marking comes from light.c)."""
    w = make_world(map=make_map(width=5, height=5,
                                walls=((2, 0), (2, 1), (2, 3), (2, 4))),
                   hero=make_hero(pos=(0, 2)))
    vision_recalc(w)
    for y in range(5):
        for x in range(5):
            assert can_see(w, (x, y)) == could_see(w, (x, y))


def test_hero_view_follows_the_hero():
    w = make_world(map=make_map(walls=((7, 5),)))
    vision_recalc(w)
    assert could_see(w, (9, 4))          # clear line of sight
    w.hero.pos = (9, 6)                  # (step() moves the hero this way)
    vision_recalc(w)
    assert could_see(w, (9, 6))          # own tile
    assert could_see(w, (8, 6))          # adjacent
    assert not could_see(w, (6, 4))      # old spot, now behind the wall


# ------------------------------------------------------------
# Blocking: doors, boulders
# ------------------------------------------------------------

def test_closed_door_blocks_sight_and_open_door_does_not():
    walls = [(5, y) for y in range(1, 8)]
    w = make_world(map=make_map(walls=walls), hero=make_hero(pos=(2, 4)))
    set_tile(w, (5, 4), Tile(typ=TerrainType.DOOR, door_mask=DoorMask.CLOSED))
    vision_recalc(w)
    assert could_see(w, (4, 4))          # up to the door
    assert could_see(w, (5, 4))          # the door itself (endpoint)
    assert not could_see(w, (6, 4))      # behind the closed door
    set_tile(w, (5, 4), Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.ISOPEN))
    vision_recalc(w)
    assert could_see(w, (6, 4))          # through the open door
    assert could_see(w, (10, 4))


def test_boulder_blocks_sight_until_moved():
    w = make_world()
    boulder = Item(id="boulder_0", otype=ObjectType.BOULDER,
                   name="Boulder", pos=(7, 4))
    w.items["boulder_0"] = boulder
    vision_reset(w)
    vision_recalc(w)
    assert could_see(w, (7, 4))          # the boulder tile: endpoint, visible
    assert not could_see(w, (8, 4))      # behind the boulder
    boulder.pos = None                   # picked up
    unblock_point(w, (7, 4))
    vision_recalc(w)
    assert could_see(w, (8, 4))


# ------------------------------------------------------------
# Monster sight
# ------------------------------------------------------------

def test_corner_cut_line_of_sight():
    """A single diagonal step never checks the corner: the goblin at
    (7,3) sees the hero at (6,4) even with a wall at (7,4); the goblin
    at (9,4) does not (the line passes through the wall tile)."""
    w = make_world(map=make_map(walls=((7, 4),)),
                   monsters=[make_monster(pos=(7, 3))])
    vision_recalc(w)
    assert m_can_see_u(w, w.actors["goblin_0"])

    w2 = make_world(map=make_map(walls=((7, 4),)),
                    monsters=[make_monster(pos=(9, 4))])
    vision_recalc(w2)
    assert not m_can_see_u(w2, w2.actors["goblin_0"])


def test_blind_monster_cannot_see():
    w = make_world(monsters=[make_monster(pos=(8, 4), blind=3)])
    vision_recalc(w)
    goblin = w.actors["goblin_0"]
    assert not m_can_see_u(w, goblin)
    assert not m_can_see(w, goblin, (6, 4))


# ------------------------------------------------------------
# do_clear_area (the area-of-effect engine)
# ------------------------------------------------------------

def test_do_clear_area_hero_centered_uses_circle_offsets():
    """Radius 2 has the CIRCLE_DATA offsets (2, 2, 1) per row dy."""
    w = make_world()
    seen = []
    do_clear_area(w, (6, 4), 2, lambda x, y, a: seen.append((x, y)), None)
    expected = {(4, 4), (5, 4), (6, 4), (7, 4), (8, 4),
                (4, 3), (5, 3), (6, 3), (7, 3), (8, 3),
                (4, 5), (5, 5), (6, 5), (7, 5), (8, 5),
                (5, 2), (6, 2), (7, 2),
                (5, 6), (6, 6), (7, 6)}
    assert set(seen) == expected


def test_do_clear_area_non_hero_center_runs_view_from():
    """Not centered on the hero: view_from() with the range circle,
    from the corner of an open map."""
    w = make_world()
    seen = []
    do_clear_area(w, (0, 0), 2, lambda x, y, a: seen.append((x, y)), None)
    expected = {(0, 0), (1, 0), (2, 0),
                (0, 1), (1, 1), (2, 1),
                (0, 2), (1, 2)}
    assert set(seen) == expected


def test_do_clear_area_respects_walls():
    walls = [(4, y) for y in range(2, 7)]
    w = make_world(map=make_map(walls=walls))
    seen = []
    do_clear_area(w, (6, 4), 3, lambda x, y, a: seen.append((x, y)), None)
    assert (4, 4) in seen          # the wall face itself is visible
    assert (3, 4) not in seen      # behind the wall: not visible
    assert not any(x == 3 for x, y in seen)
