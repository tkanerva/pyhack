"""Tests for the potion system."""
import random

from core.potions import quaff
from core.types import Item, ObjectType, PotionType
from conftest import make_hero, make_world


def world_with_potion(potion_type, hp=20, max_hp=25):
    w = make_world(hero=make_hero(hp=hp, max_hp=max_hp))
    pot = Item(id="pot_0", otype=ObjectType.POTION, name="Potion",
               charges=1, potion_type=potion_type, container="player")
    w.items["pot_0"] = pot
    w.hero.inventory.append(pot)
    return w


def test_healing_potion():
    w = world_with_potion(PotionType.HEALING, hp=20)
    quaff(w, "player", "pot_0", random.Random(1))
    assert w.hero.hp == 25
    assert w.hero.inventory == []  # empty potion consumed


def test_healing_caps_at_max():
    w = world_with_potion(PotionType.HEALING, hp=24)
    quaff(w, "player", "pot_0", random.Random(1))
    assert w.hero.hp == 25


def test_healing_respects_max_hp():
    w = world_with_potion(PotionType.HEALING, hp=24, max_hp=26)
    quaff(w, "player", "pot_0", random.Random(1))
    assert w.hero.hp == 26  # capped, not 24+12


def test_confusion_potion():
    w = world_with_potion(PotionType.CONFUSION)
    quaff(w, "player", "pot_0", random.Random(1))
    assert w.hero.confused == 20


def test_sleeping_sickness():
    w = world_with_potion(PotionType.SLEEPING_SICKNESS)
    quaff(w, "player", "pot_0", random.Random(1))
    assert w.hero.sleeping == 15


def test_unknown_item_is_rejected():
    w = make_world()
    ev = quaff(w, "player", "nope", random.Random(1))
    assert ev[0].text == "You don't have such a potion."
