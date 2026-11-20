"""Tests for core.rings -- PLAN-RING.md phase 6 (the ring spec).

The architecture under test:

- ``ring_on`` / ``ring_off`` are *producers*: they return events and
  mutate no object-identity state.  The discovery mutation
  (``Item.dknown`` / ``Item.known`` + the per-game ``oc_name_known`` /
  ``oc_encountered``) happens only in the core choke point
  ``rules.apply_discovery``, reached through ``process_events`` (from
  ``worn.dowear`` / ``worn.dotakeoff``) or directly here.
- the ability a worn ring changes is COMPUTED on every query
  (``rules.current_ability``) and a protection ring's AC is read from
  the worn mask by ``worn.uac`` -- neither is cached, so a don/doff and
  the next query agree by construction.
- ``tick_rings`` is the per-turn upkeep ``core.step`` runs for every
  actor, and it draws the rng only when a wearing actually needs a roll
  (the determinism house rule).

Ring items are built from the REAL ``core.objects`` rows (``_ring``), so
``is_ring``, ``oprop`` and the ``charged`` flag the discovery reads are
the C values.  A ring whose identity the C code hides behind a shuffled
description (every ring with a ``descr``) starts with
``oc_name_known == 0`` -- ``core.o_init`` enforces that at import time.

Deferred with their systems (not tested here, by design): ring
generation (the mksobj RING branch), the *active* effect of the feel-it
rings (levitation / stealth / invisibility / see-invisible), per-turn
hunger and polymorph, conflict routing, and the UI wiring of
``ring_name`` (the console still shows ``Item.name``).
"""

from __future__ import annotations

import itertools
import random

from core import TakeOffCommand, WaitCommand, WearCommand, step
from core.events import DamageEvent, DiscoveryEvent, MessageEvent, StatusEvent
from core.monst import MONS, PM_GOBLIN
from core.o_init import typename
from core.objects import (
    OBJECTS,
    ObjClass,
    ObjType,
    Prop,
    W_ARMC,
    W_RING,
    W_RINGL,
    W_RINGR,
)
from core.props import has_property, worn_properties
from core.rings import (
    RING_FIRST,
    RING_LAST,
    is_ring,
    learnring,
    ring_name,
    ring_off,
    ring_on,
    tick_rings,
)
from core.rules import apply_discovery, current_ability, process_events
from core.types import Item, Monster, ObjectType
from core.uhitm import uhitm
from core.weapon import P_SKILLED, Skill, Skills
from core.worn import _type_off, _type_on, dotakeoff, dowear, uac
from conftest import SeqRng, make_hero, make_world

_ids = itertools.count()


# ------------------------------------------------------------
# fixtures
# ------------------------------------------------------------


def _ring(otyp: ObjType, spe: int = 0, owornmask: int = 0, name=None) -> Item:
    """A runtime Item with the fine identity of the ring table row
    `otyp` (so ``is_ring`` / ``oprop`` / ``charged`` are the C values)."""
    row = OBJECTS[otyp.value]
    return Item(
        id=f"ring_{next(_ids)}",
        otype=ObjectType.RING,
        name=name if name is not None else f"ring of {row.name}",
        otyp=otyp.value,
        oclass=int(ObjClass.RING),
        spe=spe,
        owornmask=owornmask,
    )


def _armor(otyp: ObjType, owornmask: int = 0) -> Item:
    """A runtime Item with the fine identity of an armour row (only the
    worn-mask dispatch of core.worn needs one)."""
    row = OBJECTS[otyp.value]
    return Item(
        id=f"armor_{next(_ids)}",
        otype=ObjectType.ARMOR,
        name=row.name,
        otyp=otyp.value,
        oclass=int(ObjClass.ARMOR),
        owornmask=owornmask,
    )


def _add(w, mon, item) -> Item:
    """Carry `item` in `mon`'s inventory (and the world registry)."""
    item.carrier = mon.id
    mon.inventory.append(item)
    w.items[item.id] = item
    return item


def _discover(w, otyp: ObjType, item_id=None) -> None:
    """Learn the type the way the core does (through apply_discovery)."""
    apply_discovery(
        w,
        DiscoveryEvent(
            otyp=otyp.value,
            item_id=item_id,
            mark_known=True,
            mark_encountered=True,
        ),
    )


class CountingRng:
    """A SeqRng that counts its draws (the per-turn determinism audit)."""

    def __init__(self, *values):
        self._values = list(values)
        self.draws = 0

    def randint(self, a, b):
        self.draws += 1
        return self._values.pop(0)

    def choice(self, seq):
        self.draws += 1
        return self._values.pop(0)

    def shuffle(self, seq):
        self.draws += 1


class CountingRandom:
    """random.Random behind a draw counter (the step() audit)."""

    def __init__(self, seed):
        self._inner = random.Random(seed)
        self.draws = 0

    def randint(self, a, b):
        self.draws += 1
        return self._inner.randint(a, b)

    def choice(self, seq):
        self.draws += 1
        return self._inner.choice(seq)

    def shuffle(self, seq):
        self.draws += 1
        self._inner.shuffle(seq)


def _typed_goblin() -> Monster:
    data = MONS[PM_GOBLIN]
    assert data is not None
    return Monster(
        id="gob_0",
        name=data.pmnames[2],
        pos=(7, 4),
        hp=8,
        max_hp=8,
        ac=data.ac,
        mdata=data,
    )


def _hero_with_sword(**kw):
    """The demo hero's weapon wiring (test_uhitm's helper): the short
    sword wielded, P_SKILLED with it, ulevel 1 / ustr 12 / udex 12 -> the
    to-hit bonus is weapon_hit_bonus(+2) + abon(12,12,1)(+1) + 0 = +3."""
    hero = make_hero(**kw)
    hero.ulevel, hero.ustr, hero.udex = 1, 12, 12
    skills = Skills()
    skills.skill[int(Skill.P_SHORT_SWORD)] = P_SKILLED
    skills.max_skill[int(Skill.P_SHORT_SWORD)] = P_SKILLED
    hero.skills = skills
    sword = Item(
        id="sword_0",
        otype=ObjectType.WEAPON,
        name="short sword",
        otyp=ObjType.SHORT_SWORD.value,
        oclass=int(ObjClass.WEAPON),
    )
    hero.inventory.append(sword)
    hero.wielded = sword.id
    return hero, sword


# ------------------------------------------------------------
# A. The discovery contract (the headline)
# ------------------------------------------------------------


def test_ring_on_is_a_pure_producer():
    """The KEY architectural test: ring_on DECIDES, the core APPLIES."""
    w = make_world()
    hero = w.hero
    ring = _add(w, hero, _ring(ObjType.RIN_PROTECTION, spe=1))

    ev = ring_on(w, hero, ring)
    assert len(ev) == 1
    assert isinstance(ev[0], DiscoveryEvent)
    d = ev[0]
    assert d.otyp == ring.otyp
    assert d.item_id == ring.id
    assert d.mark_known is True
    assert d.mark_encountered is True
    assert d.reveal_spe is True

    # nothing mutated: not the item, not the object table
    assert ring.dknown is False
    assert ring.known is False
    assert ring.otyp not in w.obj_tables.name_known
    assert ring.otyp not in w.obj_tables.encountered

    # the core applies it (no further events: a discovery is silent)
    assert process_events(w, ev, SeqRng()) == []
    assert ring.dknown is True
    assert ring.known is True  # a charged ring whose type is now known
    assert ring.otyp in w.obj_tables.name_known
    assert ring.otyp in w.obj_tables.encountered


def test_wearing_marks_seen():
    """Any ring, after dowear (which applies the event), is seen."""
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_FIRE_RESISTANCE))
    dowear(w, "player", ring.id, SeqRng())
    assert ring.dknown is True
    assert ring.owornmask & W_RING
    assert ring.otyp in w.obj_tables.encountered


def test_learnring_branches():
    """C's learnring branches, as emitted flags AND post-apply state."""
    # observed + type unknown -> the type is discovered
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    ev = learnring(w, w.hero, ring, observed=True)
    assert len(ev) == 1
    assert ev[0].mark_known is True
    assert ev[0].mark_encountered is True
    process_events(w, ev, SeqRng())
    assert ring.otyp in w.obj_tables.name_known
    assert ring.dknown is True

    # observed + type ALREADY known -> idempotent (the type stays known,
    # the item is still marked seen)
    w2 = make_world()
    ring2 = _add(w2, w2.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    _discover(w2, ObjType.RIN_PROTECTION)
    ev = learnring(w2, w2.hero, ring2, observed=True)
    assert ev[0].mark_known is True
    process_events(w2, ev, SeqRng())
    assert ring2.dknown is True
    assert [t for t in w2.obj_tables.disco if t == ring2.otyp] == [ring2.otyp]

    # NOT observed (a passive ring) + type unknown -> seen only
    w3 = make_world()
    ring3 = _add(w3, w3.hero, _ring(ObjType.RIN_WARNING))
    ev = learnring(w3, w3.hero, ring3, observed=False)
    assert ev[0].mark_known is False
    assert ev[0].mark_encountered is True
    process_events(w3, ev, SeqRng())
    assert ring3.dknown is True
    assert ring3.otyp not in w3.obj_tables.name_known


def test_enchantment_revealed_only_for_charged_known():
    # a charged ring (protection) seen + type known -> Item.known
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=2))
    _discover(w, ObjType.RIN_PROTECTION)
    ev = learnring(w, w.hero, ring, observed=False)
    assert ev[0].mark_known is True
    assert ev[0].reveal_spe is True
    process_events(w, ev, SeqRng())
    assert ring.known is True

    # ...but a charged ring whose TYPE is still unknown keeps it hidden
    w2 = make_world()
    ring2 = _add(w2, w2.hero, _ring(ObjType.RIN_PROTECTION, spe=2))
    ev = learnring(w2, w2.hero, ring2, observed=False)
    assert ev[0].mark_known is False
    assert ev[0].reveal_spe is False
    process_events(w2, ev, SeqRng())
    assert ring2.known is False

    # a NON-charged ring never reveals an enchantment there is none of
    w3 = make_world()
    ring3 = _add(w3, w3.hero, _ring(ObjType.RIN_FIRE_RESISTANCE))
    _discover(w3, ObjType.RIN_FIRE_RESISTANCE)
    ev = learnring(w3, w3.hero, ring3, observed=False)
    assert ev[0].reveal_spe is False
    process_events(w3, ev, SeqRng())
    assert ring3.known is False
    assert OBJECTS[ObjType.RIN_FIRE_RESISTANCE.value].charged == 0


def test_apply_discovery_is_idempotent():
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=1))
    ev = learnring(w, w.hero, ring, observed=True)
    apply_discovery(w, ev[0])
    snap = (
        set(w.obj_tables.name_known),
        set(w.obj_tables.encountered),
        list(w.obj_tables.disco),
    )
    assert apply_discovery(w, ev[0]) == []
    assert (
        set(w.obj_tables.name_known),
        set(w.obj_tables.encountered),
        list(w.obj_tables.disco),
    ) == snap
    assert ring.dknown is True and ring.known is True


def test_apply_discovery_looks_item_up_by_id():
    """An event naming an item that is not in the world still updates the
    table and touches no item (C's makeknown is type-level)."""
    w = make_world()
    e = DiscoveryEvent(
        otyp=ObjType.RIN_WARNING.value,
        item_id="not_in_the_world",
        mark_known=True,
        mark_encountered=True,
        reveal_spe=True,
    )
    assert apply_discovery(w, e) == []
    assert ObjType.RIN_WARNING.value in w.obj_tables.name_known
    assert "not_in_the_world" not in w.items


# ------------------------------------------------------------
# B. Ability rings (computed, never cached)
# ------------------------------------------------------------


def test_current_ability_is_computed():
    w = make_world()
    hero = w.hero
    assert current_ability(hero, "str") == 12
    assert current_ability(hero, "con") == 12
    assert current_ability(hero, "cha") == 12

    left = _add(w, hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=2, owornmask=W_RINGL))
    assert current_ability(hero, "str") == 14
    right = _add(w, hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=2, owornmask=W_RINGR))
    assert current_ability(hero, "str") == 16  # the second worn ring adds on

    left.owornmask = 0  # doffed
    assert current_ability(hero, "str") == 14
    right.owornmask = 0
    assert current_ability(hero, "str") == 12

    # a CARRIED (unworn) ring contributes nothing
    carried = _add(w, hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=5))
    assert carried.owornmask == 0
    assert current_ability(hero, "str") == 12

    # the other two ability rings
    con = _add(w, hero, _ring(ObjType.RIN_GAIN_CONSTITUTION, spe=1, owornmask=W_RINGL))
    cha = _add(w, hero, _ring(ObjType.RIN_ADORNMENT, spe=1, owornmask=W_RINGR))
    assert current_ability(hero, "con") == 13
    assert current_ability(hero, "cha") == 13
    assert current_ability(hero, "str") == 12  # they do not leak
    con.owornmask = cha.owornmask = 0

    # an unknown ability is a programming error, not a silent 0
    try:
        current_ability(hero, "luck")
    except ValueError:
        pass
    else:  # pragma: no cover - the assertion IS the test
        raise AssertionError("current_ability accepted an unknown ability")


def test_attribute_messages():
    """The C adjattrib feedback, with "very " for |spe| > 1."""
    rows = [
        (ObjType.RIN_GAIN_STRENGTH, 1, "You feel strong!", "You feel weak!"),
        (ObjType.RIN_GAIN_STRENGTH, 2, "You feel very strong!", "You feel very weak!"),
        (ObjType.RIN_GAIN_STRENGTH, -1, "You feel weak!", "You feel strong!"),
        (ObjType.RIN_GAIN_CONSTITUTION, 1, "You feel tough!", "You feel fragile!"),
        (
            ObjType.RIN_ADORNMENT,
            2,
            "You feel very charismatic!",
            "You feel very repulsive!",
        ),
    ]
    for otyp, spe, on_msg, off_msg in rows:
        w = make_world()
        ring = _add(w, w.hero, _ring(otyp, spe=spe))
        on = [e.text for e in ring_on(w, w.hero, ring) if isinstance(e, MessageEvent)]
        assert on == [on_msg], (otyp, spe)
        off = [e.text for e in ring_off(w, w.hero, ring) if isinstance(e, MessageEvent)]
        assert off == [off_msg], (otyp, spe)

    # spe 0 moves nothing -> no message at all, and the ring is seen only
    w = make_world()
    flat = _add(w, w.hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=0))
    ev = ring_on(w, w.hero, flat)
    assert [e for e in ev if isinstance(e, MessageEvent)] == []
    assert [e for e in ev if isinstance(e, DiscoveryEvent)][0].mark_known is False
    process_events(w, ev, SeqRng())
    assert flat.dknown is True
    assert flat.otyp not in w.obj_tables.name_known


def test_str_ring_feeds_to_hit():
    """The core.uhitm integration point: a worn ring of gain strength
    feeds abon() through current_ability (STR 12 -> 17 crosses the
    bonus threshold, so a roll of 14 hits only WITH the ring)."""
    # without the ring: threshold = 20 - 10 + 3 = 13 -> a 14 misses
    hero, sword = _hero_with_sword()
    w = make_world(hero=hero)
    w.items[sword.id] = sword
    gob = _typed_goblin()
    w.actors[gob.id] = gob
    assert current_ability(hero, "str") == 12
    assert uhitm(w, gob.id, SeqRng(14)) == [MessageEvent("🛡️ You miss.")]

    # with a +5 STR ring: STR 17 -> abon +1 more -> threshold 14 -> hits
    hero2, sword2 = _hero_with_sword()
    w2 = make_world(hero=hero2)
    w2.items[sword2.id] = sword2
    _add(w2, hero2, _ring(ObjType.RIN_GAIN_STRENGTH, spe=5, owornmask=W_RINGL))
    gob2 = _typed_goblin()
    w2.actors[gob2.id] = gob2
    assert current_ability(hero2, "str") == 17
    ev = uhitm(w2, gob2.id, SeqRng(14, 3))
    assert any(isinstance(e, DamageEvent) and e.amount == 3 for e in ev)


# ------------------------------------------------------------
# C. Protection ring (the AC is free via worn.uac)
# ------------------------------------------------------------


def test_protection_ring_moves_ac():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    left = _add(w, hero, _ring(ObjType.RIN_PROTECTION, spe=2))
    assert uac(w, hero) == 10
    assert [e.text for e in dowear(w, "player", left.id, SeqRng())] == [
        "ring of protection (on left hand)"
    ]
    assert uac(w, hero) == 8

    right = _add(w, hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    dowear(w, "player", right.id, SeqRng())
    assert uac(w, hero) == 7

    dotakeoff(w, "player", left.id, SeqRng())
    assert uac(w, hero) == 9
    dotakeoff(w, "player", right.id, SeqRng())
    assert uac(w, hero) == 10

    # a spe 0 protection ring: no AC change, seen only (C: observed =
    # spe != 0)
    w2 = make_world(hero=make_hero(ac=10))
    flat = _add(w2, w2.hero, _ring(ObjType.RIN_PROTECTION, spe=0))
    dowear(w2, "player", flat.id, SeqRng())
    assert uac(w2, w2.hero) == 10
    assert flat.dknown is True
    assert flat.otyp not in w2.obj_tables.name_known


def test_two_protection_rings_stack():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    left = _add(w, hero, _ring(ObjType.RIN_PROTECTION, spe=2, owornmask=W_RINGL))
    right = _add(w, hero, _ring(ObjType.RIN_PROTECTION, spe=1, owornmask=W_RINGR))
    # the discovery fires once per hand (one DiscoveryEvent per ring),
    # while the type is learned only once
    ev_l = [e for e in ring_on(w, hero, left) if isinstance(e, DiscoveryEvent)]
    ev_r = [e for e in ring_on(w, hero, right) if isinstance(e, DiscoveryEvent)]
    assert [e.item_id for e in ev_l] == [left.id]
    assert [e.item_id for e in ev_r] == [right.id]
    process_events(w, ev_l + ev_r, SeqRng())
    assert [t for t in w.obj_tables.disco if t == left.otyp] == [left.otyp]
    assert left.dknown and right.dknown
    # 2 + 1 = 3 off the base 10
    assert uac(w, hero) == 7


# ------------------------------------------------------------
# D. Per-turn effects (tick_rings)
# ------------------------------------------------------------


def test_regen_tick():
    w = make_world(hero=make_hero(hp=10))
    hero = w.hero
    hero.hp = 5
    _add(w, hero, _ring(ObjType.RIN_REGENERATION, owornmask=W_RINGL))
    # silent (C: the botl update) and no draw at all
    ev = tick_rings(w, "player", SeqRng())
    assert hero.hp == 6
    assert ev == []
    # at full hp: nothing happens, no draw
    hero.hp = hero.max_hp
    assert tick_rings(w, "player", SeqRng()) == []
    assert hero.hp == hero.max_hp


def test_teleport_tick():
    w = make_world()
    hero = w.hero
    _add(w, hero, _ring(ObjType.RIN_TELEPORTATION, owornmask=W_RINGL))
    ev = tick_rings(w, "player", SeqRng(1, (9, 6)))
    assert hero.pos == (9, 6)
    assert any(isinstance(e, StatusEvent) and e.effect == "teleport" for e in ev)
    assert any(isinstance(e, MessageEvent) and "teleported" in e.text for e in ev)
    # a miss (C: !rn2(85)) -> no move, no event
    w2 = make_world()
    h2 = w2.hero
    _add(w2, h2, _ring(ObjType.RIN_TELEPORTATION, owornmask=W_RINGL))
    start = h2.pos
    assert tick_rings(w2, "player", SeqRng(85)) == []
    assert h2.pos == start


def test_tick_rings_draws_only_when_needed():
    # a ring-less hero: zero draws (the ring-less demo path)
    w = make_world()
    rng = CountingRng()
    assert tick_rings(w, "player", rng) == []
    assert rng.draws == 0
    # with a teleport ring: exactly ONE draw (the 1-in-85 roll) on a miss
    _add(w, w.hero, _ring(ObjType.RIN_TELEPORTATION, owornmask=W_RINGL))
    rng = CountingRng(85)
    tick_rings(w, "player", rng)
    assert rng.draws == 1


def test_hunger_and_polymorph_are_stubs():
    """The deferred systems: tick_rings does nothing (and draws nothing)
    for them, while the worn mask still conveys the property."""
    for otyp in (ObjType.RIN_HUNGER, ObjType.RIN_POLYMORPH):
        w = make_world()
        hero = w.hero
        _add(w, hero, _ring(otyp, owornmask=W_RINGL))
        before = (hero.pos, hero.hp, hero.uhunger)
        rng = CountingRng()
        assert tick_rings(w, "player", rng) == []
        assert rng.draws == 0
        assert (hero.pos, hero.hp, hero.uhunger) == before
        prop = OBJECTS[otyp.value].oprop
        assert prop  # the row does convey something
        assert has_property(w, hero, Prop(prop))
        assert Prop(prop) in worn_properties(hero)


# ------------------------------------------------------------
# E. The passive / feel-it rings
# ------------------------------------------------------------

_PASSIVE_RINGS = (
    ObjType.RIN_POISON_RESISTANCE,
    ObjType.RIN_FIRE_RESISTANCE,
    ObjType.RIN_COLD_RESISTANCE,
    ObjType.RIN_SHOCK_RESISTANCE,
    ObjType.RIN_FREE_ACTION,
    ObjType.RIN_SLOW_DIGESTION,
    ObjType.RIN_SUSTAIN_ABILITY,
    ObjType.RIN_AGGRAVATE_MONSTER,
    ObjType.RIN_CONFLICT,
    ObjType.RIN_WARNING,
    ObjType.RIN_SEARCHING,
    ObjType.RIN_REGENERATION,
    ObjType.RIN_TELEPORTATION,
    ObjType.RIN_LEVITATION,
    ObjType.RIN_STEALTH,
)


def test_passive_ring_conveys_its_prop():
    for otyp in _PASSIVE_RINGS:
        prop = OBJECTS[otyp.value].oprop
        assert prop, otyp  # every row in the list conveys something
        w = make_world()
        hero = w.hero
        ring = _add(w, hero, _ring(otyp))
        assert not has_property(w, hero, Prop(prop)), otyp  # carried != worn
        ring.owornmask = W_RINGL
        assert has_property(w, hero, Prop(prop)), otyp
        ring.owornmask = 0
        assert not has_property(w, hero, Prop(prop)), otyp


def test_feelit_rings_discover_on_wear():
    for otyp in (
        ObjType.RIN_LEVITATION,
        ObjType.RIN_STEALTH,
        ObjType.RIN_INVISIBILITY,
        ObjType.RIN_SEE_INVISIBLE,
    ):
        w = make_world()
        hero = w.hero
        ring = _add(w, hero, _ring(otyp))
        ev = dowear(w, "player", ring.id, SeqRng())
        # the discovery is real (C: learnring(obj, TRUE))
        assert ring.dknown is True, otyp
        assert ring.otyp in w.obj_tables.name_known, otyp
        # ...but no ACTIVE state is toggled (the effect is a STUB)
        assert not hero.intrinsics, otyp
        assert len([e for e in ev if isinstance(e, MessageEvent)]) == 1
        assert hero.pos == (6, 4)


def test_ring_range():
    assert is_ring(_ring(ObjType.RIN_ADORNMENT))
    assert is_ring(_ring(ObjType.RIN_PROTECTION))
    assert is_ring(_ring(ObjType.RIN_PROTECTION_FROM_SHAPE_CHAN))
    assert not is_ring(_ring(ObjType.AMULET_OF_GUARDING))
    assert not is_ring(_ring(ObjType.CHAIN_MAIL))
    # an item with no fine identity (the coarse demo object) is no ring
    coarse = Item(id="coarse_0", otype=ObjectType.RING, name="ring")
    assert coarse.otyp == 0
    assert not is_ring(coarse)
    assert RING_FIRST == ObjType.RIN_ADORNMENT.value
    assert RING_LAST == ObjType.RIN_PROTECTION_FROM_SHAPE_CHAN.value


# ------------------------------------------------------------
# F. Naming (ring_name -- the RING_CLASS half of objnam xname)
# ------------------------------------------------------------


def test_ring_name_unknown():
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    assert ring_name(w, ring) == "ring"
    assert ring.otyp not in w.obj_tables.name_known


def test_ring_name_type_known():
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    _discover(w, ObjType.RIN_PROTECTION, ring.id)
    assert ring_name(w, ring) == "ring of protection"


def test_ring_name_reveals_enchantment():
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    _discover(w, ObjType.RIN_PROTECTION, ring.id)
    ring.known = True  # the discovery's reveal_spe (charged + type known)
    assert ring_name(w, ring) == "ring of protection (+1)"
    ring.spe = -2
    assert ring_name(w, ring) == "ring of protection (-2)"
    # a non-charged ring shows no (+N) even when "known"
    w2 = make_world()
    fire = _add(w2, w2.hero, _ring(ObjType.RIN_FIRE_RESISTANCE))
    _discover(w2, ObjType.RIN_FIRE_RESISTANCE, fire.id)
    fire.known = True
    assert ring_name(w2, fire) == "ring of fire resistance"


def test_ring_name_reads_the_table():
    """The name comes from the per-game table: the type's identity is
    hidden behind the shuffled description until it is discovered (and
    the description is never leaked as a name -- C's bare "ring")."""
    w = make_world()
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION))
    descr = typename(w.obj_tables, ring.otyp)
    assert descr is not None
    assert descr == w.obj_tables.descr[ring.otyp]
    assert ring_name(w, ring) == "ring"

    _discover(w, ObjType.RIN_PROTECTION, ring.id)
    assert typename(w.obj_tables, ring.otyp) == OBJECTS[ring.otyp].name
    assert ring_name(w, ring) == "ring of protection"


# ------------------------------------------------------------
# G. Don/doff wiring & the event stream
# ------------------------------------------------------------


def test_type_on_off_dispatch_rings():
    w = make_world()
    hero = w.hero
    ring = _add(w, hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=1))
    assert _type_on(w, hero, ring, W_RINGL) == ring_on(w, hero, ring)
    assert _type_off(w, hero, ring, W_RINGL) == ring_off(w, hero, ring)
    # non-ring gear still goes to the no-op STUB hooks
    cloak = _add(w, hero, _armor(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    assert _type_on(w, hero, cloak, W_ARMC) == []
    assert _type_off(w, hero, cloak, W_ARMC) == []


def test_dowear_applies_discovery():
    w = make_world()
    hero = w.hero
    ring = _add(w, hero, _ring(ObjType.RIN_GAIN_STRENGTH, spe=2))
    ev = dowear(w, "player", ring.id, SeqRng())
    # the DiscoveryEvent is consumed by the core, not returned
    assert [e.text for e in ev] == [
        "ring of gain strength (on left hand)",
        "You feel very strong!",
    ]
    assert not [e for e in ev if isinstance(e, DiscoveryEvent)]
    assert ring.dknown is True
    assert ring.known is True
    assert ring.otyp in w.obj_tables.name_known
    assert current_ability(hero, "str") == 14


def test_dowear_dotakeoff_round_trip():
    """Wear then doff a protection ring through step() (WearCommand /
    TakeOffCommand): the AC goes down then back and the discovery state
    is consistent."""
    w = make_world(hero=make_hero(ac=10))
    ring = _add(w, w.hero, _ring(ObjType.RIN_PROTECTION, spe=1))
    assert uac(w, w.hero) == 10

    ev = step(w, WearCommand(ring.id), CountingRandom(3))
    assert uac(w, w.hero) == 9
    assert any(
        isinstance(e, MessageEvent) and e.text == "ring of protection (on left hand)"
        for e in ev
    )
    assert ring.dknown is True and ring.known is True
    assert ring.otyp in w.obj_tables.name_known

    ev = step(w, TakeOffCommand(ring.id), CountingRandom(3))
    assert uac(w, w.hero) == 10
    assert ring.owornmask == 0
    assert any(
        isinstance(e, MessageEvent)
        and e.text == "You were wearing the ring of protection (on left hand)."
        for e in ev
    )


# ------------------------------------------------------------
# H. Determinism / regression
# ------------------------------------------------------------


def test_an_unworn_ring_costs_no_draws():
    """A ring in the pack that is not on a finger changes nothing -- not
    the state and not one rng draw (the seeded-suite guard)."""
    w1 = make_world()
    w2 = make_world()
    _add(w2, w2.hero, _ring(ObjType.RIN_TELEPORTATION))  # carried, NOT worn
    r1, r2 = CountingRandom(42), CountingRandom(42)
    e1 = step(w1, WaitCommand(), r1)
    e2 = step(w2, WaitCommand(), r2)
    assert [type(e) for e in e1] == [type(e) for e in e2]
    assert r1.draws == r2.draws == 0
