"""Tests for monster genesis (core.makemon, the src/makemon.c port).

Two kinds of test: the *selection* rules (which species a level may
draw, what mkclass answers, how a monster's level and hit points grow
with depth) and the *creation* rules (makemon places a legal monster,
honours its MM_ flags, and answers None instead of raising when it
cannot).
"""
import pytest

from core import makemon, mkobj
from core.makemon import (MongenOrder, adj_lev, makemon as spawn,
                          mbirth_limit, mkclass, mkclass_aligned,
                          monmax_difficulty, monmin_difficulty, mongen_order,
                          newmonhp, peace_minded, rndmonst, set_malign,
                          uncommon)
from core.mklev import blank_map, makelevel
from core.monst import (A_LAWFUL, G_GENOD, MONS, PM_GIANT_ANT, PM_GOBLIN,
                        PM_KILLER_BEE, PM_SOLDIER, S_ANT, S_CENTAUR, S_HUMAN,
                        PerMonst, monsndx)
from core.rnd import Rng
from core.rules import level_difficulty
from core.types import MmFlags
from conftest import make_map, make_monster, make_world


def _rng(seed: int = 1) -> Rng:
    return Rng(b"makemon-test:%d" % seed)


def _mon(pm: int) -> PerMonst:
    """The PerMonst row for a PM index (the table has these rows)."""
    ptr = MONS[pm]
    assert ptr is not None
    return ptr


def _world(lev: int = 1, width: int = 12, height: int = 8):
    w = make_world(map=make_map(width=width, height=height))
    w.hero.pos = (6, 4)
    w.lev = lev
    w.max_lev = 5
    return w


# ------------------------------------------------------------
# level_difficulty and the difficulty band
# ------------------------------------------------------------

def test_level_difficulty_is_the_level_number():
    """The one depth helper: pyhack's dungeon is linear, so it is
    world.lev -- and every caller reads it through the helper."""
    w = _world(lev=7)
    assert level_difficulty(w) == 7


def test_the_difficulty_band_macros_are_the_c_ones():
    # monst.h: monmin = levdif / 6, monmax = (levdif + ulevel) / 2
    assert monmin_difficulty(12) == 2
    assert monmax_difficulty(12, 6) == 9


# ------------------------------------------------------------
# selecting a species
# ------------------------------------------------------------

@pytest.mark.parametrize("seed", range(1, 6))
def test_rndmonst_stays_inside_the_difficulty_band(seed):
    w = _world(lev=6)
    rng = _rng(seed)
    lo = monmin_difficulty(level_difficulty(w))
    hi = monmax_difficulty(level_difficulty(w), w.hero.ulevel)
    for _ in range(40):
        ptr = rndmonst(w, rng)
        assert ptr is not None
        assert lo <= ptr.difficulty <= hi
        assert not uncommon(w, ptr.pmidx)


def test_rndmonst_returns_none_when_every_species_is_gone():
    """C: "no more monsters!" -- the callers treat that as a normal
    result, so it must be None, not an exception."""
    w = _world(lev=3)
    for i in range(len(MONS)):
        w.mon_state.svflags(i, int(G_GENOD), True)
    assert rndmonst(w, _rng()) is None


def test_uncommon_filters_the_never_generated_species():
    w = _world()
    # the killer bee is a common species...
    assert uncommon(w, PM_KILLER_BEE) is False
    # ... and a genocided one is gone
    w.mon_state.svflags(PM_GOBLIN, int(G_GENOD), True)
    assert uncommon(w, PM_GOBLIN) is True


def test_mongen_order_is_a_pure_function_of_the_table():
    """C caches it behind a boolean; here it is derived from the frozen
    monster table, so two calls agree and the class runs are
    contiguous."""
    a = mongen_order()
    b = mongen_order()
    assert a is b
    assert isinstance(a, MongenOrder)
    # every listed index is an implemented row below the special section
    assert all(MONS[i] is not None for i in a.order)
    assert a.maxf[S_ANT] > 0


def test_mkclass_returns_the_requested_class():
    w = _world(lev=10)
    for seed in range(1, 8):
        ptr = mkclass(w, _rng(seed), S_ANT)
        assert ptr is not None
        assert ptr.mlet == S_ANT


def test_mkclass_of_an_unimplemented_class_is_none():
    """S_CENTAUR has no table rows yet: C would impossible(), the port
    answers None (a level may not put a monster there)."""
    w = _world(lev=10)
    assert mkclass(w, _rng(), S_CENTAUR) is None


def test_mkclass_aligned_respects_the_alignment():
    w = _world(lev=10)
    for seed in range(1, 6):
        ptr = mkclass_aligned(w, _rng(seed), S_HUMAN, 0, A_LAWFUL)
        # the soldiers are chaotic (maligntyp -2), so a lawful request
        # must not answer one
        if ptr is not None:
            assert ptr.maligntyp >= 0


# ------------------------------------------------------------
# how strong
# ------------------------------------------------------------

def test_adj_lev_grows_with_depth():
    ptr = _mon(PM_GIANT_ANT)
    shallow = adj_lev(_world(lev=1), ptr)
    deep = adj_lev(_world(lev=30), ptr)
    assert deep > shallow


def test_adj_lev_never_exceeds_the_crude_upper_limit():
    ptr = _mon(PM_GIANT_ANT)
    assert adj_lev(_world(lev=50), ptr) <= (3 * ptr.mlevel) // 2


def test_newmonhp_gives_at_least_two_hit_points():
    """C's "all ones" boost: a level-0 monster's d4 floor is 2."""
    w = _world(lev=1)
    mon = makemon.Monster(id="m", name="m", pos=(3, 3), hp=0, max_hp=0, ac=10)
    newmonhp(w, _rng(3), mon, PM_GOBLIN)
    assert mon.max_hp >= 2
    assert mon.hp == mon.max_hp


def test_mbirth_limit_is_the_population_cap():
    assert mbirth_limit(PM_GOBLIN) == makemon.MAXMONNO


# ------------------------------------------------------------
# creating one
# ------------------------------------------------------------

def test_makemon_places_a_specific_monster():
    w = _world()
    mon = spawn(w, _rng(), _mon(PM_GIANT_ANT), (8, 4))
    assert mon is not None
    assert mon.pos == (8, 4)
    assert mon.lev == w.lev
    assert mon.mdata is _mon(PM_GIANT_ANT)
    assert mon.mnum == PM_GIANT_ANT
    assert mon.hp == mon.max_hp >= 2
    assert w.actors[mon.id] is mon


def test_makemon_never_lands_on_the_hero_or_another_monster():
    w = _world()
    for seed in range(1, 12):
        mon = spawn(w, _rng(seed), _mon(PM_GIANT_ANT))
        assert mon is not None
        assert w.map.is_walkable(mon.pos)
        assert mon.pos != w.hero.pos


def test_makemon_returns_none_on_a_level_with_no_legal_square():
    """C's NULL for "cannot place it": a solid-stone level refuses land
    monsters instead of crashing (PLAN-MAKEMON.md §7)."""
    m = blank_map(10, 6)
    w = make_world(map=m)
    assert spawn(w, _rng(), _mon(PM_GIANT_ANT)) is None
    assert spawn(w, _rng(), _mon(PM_GIANT_ANT), (3, 3)) is None


def test_makemon_honours_mm_asleep_and_mm_angry():
    w = _world()
    asleep = spawn(w, _rng(2), _mon(PM_GIANT_ANT), (2, 2),
                   MmFlags.ASLEEP)
    assert asleep is not None and asleep.sleeping
    w2 = _world()
    angry = spawn(w2, _rng(2), _mon(PM_GIANT_ANT), (2, 2), MmFlags.ANGRY)
    assert angry is not None and angry.mpeaceful is False


def test_makemon_refuses_a_genocided_species():
    w = _world()
    w.mon_state.svflags(PM_GIANT_ANT, int(G_GENOD), True)
    assert spawn(w, _rng(), _mon(PM_GIANT_ANT), (3, 3)) is None


def test_makemon_mm_adjacentok_moves_off_an_occupied_square():
    w = _world()
    first = spawn(w, _rng(4), _mon(PM_GIANT_ANT), (4, 4))
    assert first is not None
    assert spawn(w, _rng(5), _mon(PM_GIANT_ANT), (4, 4)) is None
    second = spawn(w, _rng(5), _mon(PM_GIANT_ANT), (4, 4),
                   MmFlags.ADJACENTOK)
    assert second is not None and second.pos != (4, 4)


def test_makemon_records_the_birth_for_the_vitals():
    w = _world()
    spawn(w, _rng(6), _mon(PM_GIANT_ANT), (3, 3))
    assert w.mon_state.mvitals[PM_GIANT_ANT].born == 1


def test_makemon_gives_a_monster_money_and_gear():
    """The inventory mechanism (C: mongets / mkmonmoney) -- the species
    tables of m_initweap are phase E, the plumbing is here."""
    w = _world()
    mon = spawn(w, _rng(7), _mon(PM_SOLDIER), (3, 3),
                MmFlags.NO_MINVENT)
    assert mon is not None
    assert mon.inventory == []
    makemon.mkmonmoney(w, _rng(8), mon, 40)
    gold = [it for it in mon.inventory if it.quan == 40]
    assert gold and gold[0].carrier == mon.id
    otyp = mkobj.mkgold(w, _rng(9), 10, (5, 5), w.lev).otyp
    assert makemon.mongets(w, _rng(10), mon, otyp) is not None
    assert len(mon.inventory) == 2


# ------------------------------------------------------------
# mood
# ------------------------------------------------------------

def test_peace_minded_follows_the_always_flags():
    w = _world()
    for seed in range(1, 5):
        # the soldier is M2_HOSTILE (always_hostile)
        assert peace_minded(w, _mon(PM_SOLDIER), _rng(seed)) is False


def test_set_malign_records_the_c_score():
    w = _world()
    mon = make_monster("goblin", pos=(8, 4))
    mon.mdata = _mon(PM_GIANT_ANT)
    mon.mpeaceful = True
    set_malign(w, mon)
    # a peaceful, co-aligned-neutral monster is bad to kill (negative)
    assert mon.malign <= 0


# ------------------------------------------------------------
# the level generator now uses all of it
# ------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_generated_level_is_populated_from_the_real_table(seed):
    """fill_ordinary_room() calls makemon(), so every monster on a
    generated level carries a PerMonst type, a mons[] index, its
    instance level and at least two hit points."""
    w = make_world(map=blank_map(40, 20))
    w.max_lev = 5
    makelevel(w, w.map, _rng(seed), 2)
    monsters = [m for m in w.actors.values() if not m.is_hero]
    assert monsters, "the room filler must place monsters"
    for mon in monsters:
        assert mon.mdata is not None
        assert mon.mnum == monsndx(mon.mdata)
        assert mon.lev == 2
        assert mon.max_hp >= 2 and mon.hp == mon.max_hp
        assert w.map.is_walkable(mon.pos)
        assert mon.pos != w.hero.pos
