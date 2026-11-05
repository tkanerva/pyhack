"""Tests for object genesis (core.mkobj, the src/mkobj.c port).

The plan's exit check is the 480-row smoke test ("for every otyp in the
table, mksobj returns an Item whose fields are inside the C ranges"), so
that is here; the rest covers the pieces the level generator leans on --
gold, containers, corpses and the BUC lottery.
"""
import pytest

from core.mklev import blank_map, makelevel
from core.mkobj import (CORPSTAT_FEMALE, CORPSTAT_MALE, CORPSTAT_NEUTER,
                        CORPSTAT_NONE, add_to_container, bcsign, bless,
                        blessorcurse, curse, delete_contents, gold_at,
                        hero_gold, is_container, mkcorpstat, mkgold,
                        place_object, rnd_class, weight)
from core.mkobj import mkobj as make_random_object
from core.mkobj import mksobj
from core.monst import MONS
from core.objects import BASES, NUM_OBJECTS, OBJECTS, ObjClass, ObjType
from core.rnd import Rng
from core.types import ObjectType
from conftest import make_map, make_world

O = ObjType  # noqa: E741 -- the house alias for the object table


def _rng(seed: int = 1) -> Rng:
    return Rng(b"mkobj-test:%d" % seed)


def _world(width: int = 12, height: int = 8):
    w = make_world(map=make_map(width=width, height=height))
    w.hero.pos = (6, 4)
    return w


# ------------------------------------------------------------
# the 480-row smoke test (PLAN-MKOBJ.md phase B exit check)
# ------------------------------------------------------------

@pytest.mark.parametrize("otyp", range(NUM_OBJECTS))
def test_mksobj_makes_every_object_in_the_table(otyp):
    w = _world()
    item = mksobj(w, _rng(otyp % 7 + 1), otyp)
    assert item.otyp == otyp
    assert item.oclass == int(OBJECTS[otyp].oclass)
    assert item.quan >= 1
    assert item.owt >= 0
    assert isinstance(item.otype, ObjectType)
    assert item.id in w.items
    # an object is built, never placed
    assert item.pos is None and item.carrier is None


def test_mksobj_does_not_place_the_object():
    w = _world()
    item = mksobj(w, _rng(), int(O.DAGGER))
    assert item.pos is None
    assert w.items_at((6, 4)) == []


def test_the_class_tag_follows_the_otyp():
    w = _world()
    corpse = mksobj(w, _rng(), int(O.CORPSE))
    assert corpse.otype == ObjectType.CORPSE
    egg = mksobj(w, _rng(2), int(O.EGG))
    assert egg.otype == ObjectType.EGG
    statue = mksobj(w, _rng(3), int(O.STATUE))
    assert statue.otype == ObjectType.STATUE


# ------------------------------------------------------------
# weight
# ------------------------------------------------------------

def test_a_stack_weighs_its_unit_weight_times_the_count():
    w = _world()
    item = mksobj(w, _rng(), int(O.DAGGER))
    item.quan = 3
    unit = OBJECTS[item.otyp].weight
    assert weight(w, item) == 3 * unit


def test_a_container_weighs_its_contents():
    w = _world()
    chest = mksobj(w, _rng(), int(O.CHEST))
    assert is_container(chest)
    empty = weight(w, chest)
    gold = mksobj(w, _rng(2), int(O.GOLD_PIECE))
    gold.quan = 500
    add_to_container(w, chest, gold)
    assert weight(w, chest) > empty


def test_gold_weighs_one_unit_per_hundred_coins():
    w = _world()
    gold = mksobj(w, _rng(), int(O.GOLD_PIECE))
    gold.quan = 250
    assert weight(w, gold) == 3
    gold.quan = 1
    assert weight(w, gold) == 1        # C 5.0: never 0


def test_a_corpse_weighs_what_the_species_weighs():
    w = _world()
    corpse = mkcorpstat(w, _rng(), int(O.CORPSE), pos=(3, 3))
    assert corpse.corpsenm >= 0
    row = MONS[corpse.corpsenm] if corpse.corpsenm < NUM_OBJECTS else None
    if row is not None:
        assert corpse.owt == row.cwt * corpse.quan


# ------------------------------------------------------------
# containers: the three where-states are exclusive
# ------------------------------------------------------------

def test_a_contained_item_is_not_on_the_floor_and_not_carried():
    w = _world()
    # init=False: C's mkbox_cnts fills a chest with up to seven items,
    # and this test is about the where-state of the one added
    box = mksobj(w, _rng(), int(O.CHEST), init=False)
    assert box.contents == []
    thing = mksobj(w, _rng(2), int(O.DAGGER))
    place_object(w, thing, (3, 3), w.lev)
    add_to_container(w, box, thing)
    assert box.contents == [thing.id]
    assert thing.pos is None and thing.carrier is None
    assert w.items[thing.id] is thing


def test_delete_contents_removes_them_from_the_world():
    w = _world()
    box = mksobj(w, _rng(), int(O.CHEST))
    thing = mksobj(w, _rng(2), int(O.DAGGER))
    add_to_container(w, box, thing)
    delete_contents(w, box)
    assert box.contents == []
    assert thing.id not in w.items


def test_a_chest_may_hold_something():
    """mkbox_cnts is a draw from boxiprobs, so a chest is allowed to be
    empty -- but every chest it fills must hold real objects."""
    w = _world()
    for seed in range(1, 8):
        chest = mksobj(w, _rng(seed), int(O.CHEST))
        for child_id in chest.contents:
            child = w.items[child_id]
            assert child.pos is None and child.carrier is None
            assert child.quan >= 1


# ------------------------------------------------------------
# gold
# ------------------------------------------------------------

def test_mkgold_places_one_pile_and_adds_to_it():
    w = _world()
    first = mkgold(w, _rng(), 50, (3, 3), w.lev)
    assert first.quan == 50
    assert first.pos == (3, 3) and first.lev == w.lev
    second = mkgold(w, _rng(2), 25, (3, 3), w.lev)
    assert second is first            # C: added to the pile already there
    assert first.quan == 75
    assert gold_at(w, w.lev, (3, 3)) is first


def test_mkgold_with_no_amount_rolls_one():
    w = _world()
    gold = mkgold(w, _rng(3), 0, (4, 4), w.lev)
    assert gold.quan >= 2             # 1 + rnd(...) * rnd(...)


def test_hero_gold_sums_the_carried_piles():
    w = _world()
    gold = mksobj(w, _rng(), int(O.GOLD_PIECE))
    gold.quan = 120
    gold.carrier = "player"
    w.hero.inventory.append(gold)
    assert hero_gold(w) == 120


# ------------------------------------------------------------
# the BUC lottery
# ------------------------------------------------------------

def test_bless_and_curse_are_exclusive():
    w = _world()
    item = mksobj(w, _rng(), int(O.DAGGER))
    bless(item)
    assert bcsign(item) == 1
    curse(item)
    assert bcsign(item) == -1
    assert item.blessed is False


def test_blessorcurse_leaves_a_marked_object_alone():
    w = _world()
    item = mksobj(w, _rng(), int(O.DAGGER))
    curse(item)
    # a "cannot happen" roll would still not change a cursed object
    blessorcurse(_rng(1), item, 1)
    assert item.cursed is True


def test_blessorcurse_never_marks_both():
    w = _world()
    for seed in range(1, 12):
        item = mksobj(w, _rng(seed), int(O.DAGGER))
        blessorcurse(_rng(seed), item, 1)
        assert not (item.blessed and item.cursed)


# ------------------------------------------------------------
# picking a type
# ------------------------------------------------------------

def test_mkobj_returns_an_object_of_the_requested_class():
    w = _world()
    for seed in range(1, 8):
        item = make_random_object(w, _rng(seed), int(ObjClass.POTION))
        assert item.oclass == int(ObjClass.POTION)


def test_mkobj_of_a_random_class_stays_in_the_table():
    w = _world()
    for seed in range(1, 12):
        item = make_random_object(w, _rng(seed))
        assert 0 <= item.otyp < NUM_OBJECTS
        assert OBJECTS[item.otyp].name is not None


def test_rnd_class_stays_inside_the_range():
    w = _world()
    lo = BASES[int(ObjClass.GEM)]
    for seed in range(1, 8):
        otyp = rnd_class(w, _rng(seed), lo, lo + 4)
        assert lo <= otyp <= lo + 4


# ------------------------------------------------------------
# placement
# ------------------------------------------------------------

def test_place_object_puts_it_on_the_floor():
    w = _world()
    item = mksobj(w, _rng(), int(O.DAGGER))
    place_object(w, item, (2, 2), w.lev)
    assert w.items_at((2, 2)) == [item]
    assert item.carrier is None


def test_a_generated_level_carries_real_objects():
    """fill_ordinary_room() places gold, statues and a random object
    (PLAN-MKOBJ.md phase G), so a generated level has floor objects that
    were made by the object genesis."""
    w = make_world(map=blank_map(40, 20))
    w.max_lev = 5
    kinds = set()
    for seed in range(1, 6):
        makelevel(w, w.map, _rng(seed), 2)
        for item in w.items.values():
            if item.pos is not None:
                kinds.add(int(OBJECTS[item.otyp].oclass))
                assert w.map.in_bounds(item.pos)
                assert item.carrier is None
    assert kinds, "the object half of fill_ordinary_room must place items"


def test_a_statue_may_be_placed_by_the_generator():
    w = _world()
    statue = mkcorpstat(w, _rng(4), int(O.STATUE), pos=(3, 3), lev=1)
    assert statue.pos == (3, 3)
    assert statue.corpsenm >= 0
    # C: mkcorpstat records the *caller's* gender flags in the overloaded
    # spe field (`otmp->spe = corpstatflags & CORPSTAT_SPE_VAL`), so
    # CORPSTAT_NONE -- what fill_ordinary_room passes -- is 0,
    # "unspecified", and overrides the roll mksobj() made
    assert statue.spe == CORPSTAT_NONE
    female = mkcorpstat(w, _rng(4), int(O.STATUE), pos=(4, 4), lev=1,
                        spe=CORPSTAT_FEMALE)
    assert female.spe == CORPSTAT_FEMALE
    # ... while mksobj() itself does roll the gender into spe
    plain = mksobj(w, _rng(4), int(O.STATUE))
    assert plain.spe in (CORPSTAT_MALE, CORPSTAT_FEMALE, CORPSTAT_NEUTER)
