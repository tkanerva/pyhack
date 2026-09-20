"""Unit tests for the pure rules in core.rules."""
import random

from core.events import DamageEvent, DeathEvent
from core.rules import (apply_damage, heal, hit_chance, melee_attack,
                        resists, roll, tick_actor, teleport_to_floor)
from core.types import DamageType
from conftest import SeqRng, make_hero, make_monster, make_world


def test_roll_sums_dice():
    assert roll(SeqRng(3, 5), 6, 2) == 8
    assert roll(SeqRng(6), 6) == 6


def test_hit_chance_is_twenty_minus_ac():
    hero = make_hero()
    assert hit_chance(make_monster(), hero) == 15
    assert hit_chance(make_monster(), make_hero(ac=25)) == -5  # always misses


def test_melee_miss_then_hit():
    hero = make_hero(ac=19)  # hit chance 1
    mon = make_monster(damage=2)
    assert melee_attack(SeqRng(2), mon, hero) == 0     # d20 = 2 > 1
    assert melee_attack(SeqRng(1, 2), mon, hero) == 2  # d20 = 1, 1d2 = 2


def test_resistance_flags():
    assert not resists(make_monster(), DamageType.FIRE)
    assert resists(make_monster(is_undead=True), DamageType.COLD)
    assert resists(make_monster(is_undead=True), DamageType.DEATH)
    assert resists(make_monster(is_demon=True), DamageType.FIRE)
    assert resists(make_monster(is_golem=True), DamageType.SLEEP)
    assert not resists(make_monster(is_golem=True), DamageType.FIRE)


def test_apply_damage_single_path_and_death():
    w = make_world(monsters=[make_monster(pos=(8, 4))])
    ev = apply_damage(w, "goblin_0", 3, DamageType.MELEE, "player")
    assert w.actors["goblin_0"].hp == 5
    assert isinstance(ev[0], DamageEvent)

    ev2 = apply_damage(w, "goblin_0", 5, DamageType.MELEE, "player")
    assert not w.actors["goblin_0"].alive
    assert any(isinstance(e, DeathEvent) for e in ev2)


def test_resisted_damage_deals_nothing():
    w = make_world(monsters=[make_monster(is_undead=True, pos=(8, 4))])
    apply_damage(w, "goblin_0", 4, DamageType.COLD, "zap:cold")
    assert w.actors["goblin_0"].hp == 8


def test_heal_caps_at_max_hp():
    w = make_world()
    w.hero.hp = 20
    heal(w, "player", 12)
    assert w.hero.hp == 25
    heal(w, "player", 12)
    assert w.hero.hp == 25


def test_teleport_lands_on_a_floor_tile():
    w = make_world()
    old = w.hero.pos
    teleport_to_floor(w, "player", random.Random(1))
    assert w.hero.pos != old
    assert w.map.is_walkable(w.hero.pos)


def test_tick_actor_poison_deals_one_damage():
    w = make_world()
    w.hero.poisoned = 2
    events = tick_actor(w, "player", SeqRng())
    assert w.hero.hp == 24
    assert w.hero.poisoned == 1
    assert any(isinstance(e, DamageEvent) and e.damage_type == DamageType.POISON
               for e in events)
