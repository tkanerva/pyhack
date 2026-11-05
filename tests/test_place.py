"""Tests for the placement layer (core.place): goodpos / enexto.

C provenance: src/teleport.c.  The interesting properties are the ones
the level generator depends on: a monster never lands on a wall, on the
hero, on another monster, or in water it cannot survive -- and the
"nearest legal square" search always terminates, even on a level with no
legal square at all.
"""
import pytest

from core import place
from core.mklev import blank_map
from core.monst import (MONS, PM_BAT, PM_BLUE_JELLY, PM_FLOATING_EYE,
                        PM_GIANT_SPIDER, PM_GOBLIN)
from core.rnd import Rng
from core.types import (DoorMask, GP_ALLOW_U, GP_AVOID_MONPOS,
                        GP_CHECKSCARY, MM_IGNOREWATER, TerrainType, Tile)
from conftest import make_map, make_monster, make_world


def _rng(seed: int = 1) -> Rng:
    return Rng(b"place-test:%d" % seed)


def _world(width: int = 12, height: int = 8):
    """A bare all-floor level with the hero in the middle."""
    w = make_world(map=make_map(width=width, height=height))
    w.hero.pos = (6, 4)
    return w


# ------------------------------------------------------------
# goodpos
# ------------------------------------------------------------

def test_a_floor_square_is_good():
    w = _world()
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3))


def test_a_wall_is_never_good():
    w = make_world(map=make_map(walls=((3, 3),)))
    assert not place.goodpos(w, _rng(), w.map, 1, (3, 3))
    assert not place.goodpos(w, _rng(), w.map, 1, (-1, 0))


def test_the_hero_square_is_not_good_unless_allowed():
    w = _world()
    assert not place.goodpos(w, _rng(), w.map, 1, w.hero.pos)
    assert place.goodpos(w, _rng(), w.map, 1, w.hero.pos, None, GP_ALLOW_U)


def test_an_occupied_square_is_not_good():
    w = _world()
    mon = make_monster("goblin", pos=(3, 3))
    w.actors[mon.id] = mon
    assert not place.goodpos(w, _rng(), w.map, 1, (3, 3), None,
                             GP_AVOID_MONPOS)
    # without the flag the square is "good" -- C only checks it when the
    # caller asks (an object may share a monster's square)
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3))


def test_a_monster_on_another_level_does_not_block():
    """The occupancy test is per level: the hero standing on level 1 must
    not stop level 2 from using the same coordinate."""
    w = _world()
    mon = make_monster("goblin", pos=(3, 3), lev=2)
    w.actors[mon.id] = mon
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3), None, GP_AVOID_MONPOS)


def test_water_refuses_a_land_monster():
    w = _world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.POOL)
    goblin = MONS[PM_GOBLIN]
    assert not place.goodpos(w, _rng(), w.map, 1, (3, 3), goblin)
    # a swimmer may, and so may a flyer
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3), MONS[PM_BAT])


def test_water_is_ignorable():
    w = _world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.POOL)
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3), MONS[PM_GOBLIN],
                         MM_IGNOREWATER)


def test_a_closed_door_blocks_a_land_monster():
    """C: accessible() is ACCESSIBLE() *and* !closed_door(), so a door
    in its closed D_CLOSED state is not a good position -- while an
    open door (D_ISOPEN) and a doorway (D_NODOOR, doormask 0) are."""
    w = _world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.CLOSED)
    assert not place.goodpos(w, _rng(), w.map, 1, (3, 3), MONS[PM_GOBLIN])
    w.map.tiles[3][3] = Tile(typ=TerrainType.DOOR, door_mask=DoorMask.ISOPEN)
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3), MONS[PM_GOBLIN])


def test_an_amorphous_monster_squeezes_under_a_closed_door():
    """C: `if (amorphous(mdat) && closed_door(x, y)) return TRUE` --
    before the accessible() test, so a jelly may be placed in a closed
    doorway."""
    w = _world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.CLOSED)
    assert place.goodpos(w, _rng(), w.map, 1, (3, 3),
                         MONS[PM_BLUE_JELLY])


def test_enexto_finds_an_adjacent_square():
    w = _world()
    got = place.enexto(w, _rng(2), w.map, 1, (6, 6))
    assert got is not None
    assert abs(got[0] - 6) <= 1 and abs(got[1] - 6) <= 1


def test_enexto_never_answers_the_occupied_origin_square():
    w = _world()
    mon = make_monster("goblin", pos=(6, 6))
    w.actors[mon.id] = mon
    got = place.enexto_gpflags(w, _rng(3), w.map, 1, (6, 6),
                               MONS[PM_GOBLIN], GP_AVOID_MONPOS)
    assert got is not None and got != (6, 6)


def test_enexto_gives_up_on_a_level_with_no_good_square():
    """A level of solid stone: C's "no legal square" answer, which the
    callers turn into a None monster rather than an exception."""
    m = blank_map(10, 6)
    w = make_world(map=m)
    assert place.enexto(w, _rng(4), m, 1, (5, 3), MONS[PM_GOBLIN]) is None


# ------------------------------------------------------------
# the GP_ flags are C's hack.h bit space
# ------------------------------------------------------------

def test_the_flag_values_are_the_c_ones():
    assert GP_ALLOW_U == 0x00400000
    assert GP_CHECKSCARY == 0x00800000
    assert GP_AVOID_MONPOS == 0x01000000
    assert MM_IGNOREWATER == 0x00000008


def test_onscary_is_a_stub_that_never_scares():
    """No scroll of scare monster on the floor, no Elbereth: nothing is
    scary yet, so GP_CHECKSCARY changes nothing."""
    w = _world()
    assert place.onscary(w, w.map, 1, (3, 3), MONS[PM_GOBLIN]) is False


@pytest.mark.parametrize("pos", [(1, 1), (6, 4), (10, 6)])
def test_enexto_is_deterministic_for_a_seed(pos):
    w = _world()
    a = place.enexto(w, _rng(9), w.map, 1, pos, MONS[PM_GIANT_SPIDER])
    b = place.enexto(w, _rng(9), w.map, 1, pos, MONS[PM_GIANT_SPIDER])
    assert a == b


def test_floating_eye_avoids_lava():
    w = _world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.LAVAPOOL)
    assert not place.goodpos(w, _rng(), w.map, 1, (3, 3),
                             MONS[PM_FLOATING_EYE])
