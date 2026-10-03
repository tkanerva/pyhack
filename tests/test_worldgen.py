"""Tests for deterministic world construction."""
import random

from core.items import wielded_of
from core.monst import MONS, PM_BAT, PM_GOBLIN, PM_HILL_ORC
from core.objects import ObjClass, ObjType, W_ARM
from core.weapon import P_SKILLED, Skill
from core.worn import uac, which_armor
from core.worldgen import FLOOR_ARMOR, HERO_BASE_AC, new_world


def test_layout_counts():
    w = new_world(random.Random(42))
    assert len(w.traps) == 10
    assert w.hero.pos == (20, 10)
    monsters = [m for m in w.actors.values() if not m.is_hero]
    assert len(monsters) == 9
    assert {m.name for m in monsters} == {"Goblin", "Orc", "Bat"}
    for m in w.actors.values():
        assert w.map.is_walkable(m.pos)


def test_hero_spot_is_never_a_wall():
    """The old game.py could place a random wall (or a trap, or a
    monster) on the hero's starting tile."""
    for seed in range(20):
        w = new_world(random.Random(seed))
        assert w.map.is_walkable(w.hero.pos)
        assert not any(t.pos == w.hero.pos for t in w.traps.values())
        assert not any(m.pos == w.hero.pos
                       for m in w.actors.values() if not m.is_hero)


# ------------------------------------------------------------
# demo combat wiring (PerMonst types + the starting short sword)
# ------------------------------------------------------------

def test_demo_monsters_carry_their_permonst_types():
    """The demo's three kinds run monster->hero combat on the committed
    mhitu attack tables: each carries its PerMonst type, keeps the old
    per-instance hp, and its flat AC now mirrors the table's."""
    w = new_world(random.Random(42))
    expected = {
        "Goblin": (PM_GOBLIN, 8),
        "Orc": (PM_HILL_ORC, 15),
        "Bat": (PM_BAT, 4),
    }
    for mid, mon in w.actors.items():
        if mon.is_hero:
            continue
        pm, hp = expected[mon.name]
        assert mon.mdata is MONS[pm], mid
        assert mon.hp == hp and mon.max_hp == hp, mid
        assert mon.ac == MONS[pm].ac, mid
    assert {mon.name for mon in w.actors.values() if not mon.is_hero} == \
        {"Goblin", "Orc", "Bat"}


def test_hero_starts_with_a_wielded_short_sword():
    w = new_world(random.Random(42))
    hero = w.hero
    assert hero.wielded == "sword_0"
    sword = w.items["sword_0"]
    assert sword.container == "player"
    assert sword in hero.inventory
    assert sword.name == "short sword"
    # fine identity: ObjLike-compatible for core.weapon
    assert sword.otyp == ObjType.SHORT_SWORD.value
    assert sword.oclass == ObjClass.WEAPON.value
    assert sword.spe == 0 and not sword.blessed
    assert wielded_of(w, hero.id) is sword
    # the demo monsters go bare-handed
    assert wielded_of(w, "goblin_0") is None
    assert wielded_of(w, "orc_0") is None
    assert wielded_of(w, "bat_0") is None


def test_hero_skills_and_fixed_abilities():
    w = new_world(random.Random(42))
    hero = w.hero
    assert (hero.ulevel, hero.ustr, hero.udex) == (1, 12, 12)
    assert hero.skills is not None
    # the demo hero starts skilled with its starting weapon
    assert hero.skills.skill[int(Skill.P_SHORT_SWORD)] == P_SKILLED
    assert hero.skills.max_skill[int(Skill.P_SHORT_SWORD)] == P_SKILLED


# ------------------------------------------------------------
# defence wiring (PLAN-ARMOR.md): base AC 10 + starting kit + floor
# armour
# ------------------------------------------------------------

def test_hero_defence_is_computed():
    """The hero starts with base AC 10 (C mons[PM_HUMAN].ac; the human
    row is not in the monst subset, so HERO_BASE_AC) wearing chain
    mail: effective AC 5, the old demo's defence (PLAN-ARMOR.md
    decision 2)."""
    w = new_world(random.Random(42))
    hero = w.hero
    assert hero.ac == HERO_BASE_AC == 10  # the BASE (body) AC
    mail = which_armor(w, hero, W_ARM)
    assert mail is not None and mail.name == "chain mail"
    assert mail.owornmask == W_ARM
    assert uac(w, hero) == 5
    # the rest of the kit is carried, unworn
    by_name = {it.name: it for it in hero.inventory}
    assert by_name["leather cloak"].owornmask == 0
    assert by_name["leather gloves"].owornmask == 0
    ring = by_name["ring of protection (+1)"]
    assert ring.owornmask == 0 and ring.spe == 1
    # the inventory order is the UI's letter order:
    # a=sword b=mail c=cloak d=gloves e=ring
    assert [it.name for it in hero.inventory] == [
        "short sword", "chain mail", "leather cloak",
        "leather gloves", "ring of protection (+1)"]


def test_floor_armour_lies_on_floor_tiles():
    """The demo floor armours sit on their fixed positions (walkable,
    never the hero's tile) and are carried by nobody; the last one is
    the cursed piece (PLAN-ARMOR.md risk 3)."""
    w = new_world(random.Random(42))
    for pos, name, otyp, cursed in FLOOR_ARMOR:
        assert pos != (20, 10)
        assert w.map.is_walkable(pos)
        items = w.items_at(pos)
        assert len(items) == 1, pos
        it = items[0]
        assert it.name == name and it.otyp == otyp.value
        assert it.cursed is cursed
        assert it.pos == pos and it.container is None
        assert it.owornmask == 0


def test_new_world_makes_no_new_rng_draws():
    """The demo-combat wiring must not add a single rng draw: the
    seeded layout (walls, traps, spawns) stays exactly as before."""

    class CountingRng:
        """Wraps an rng and records the kind of every call, in order."""
        def __init__(self, rng):
            self._r = rng
            self.calls = []

        def randint(self, a, b):
            self.calls.append("randint")
            return self._r.randint(a, b)

        def choice(self, seq):
            self.calls.append("choice")
            return self._r.choice(seq)

        def shuffle(self, seq):
            self.calls.append("shuffle")
            self._r.shuffle(seq)

    rng = CountingRng(random.Random(42))
    new_world(rng)
    # the old draw sequence: 15 walls x (x, y) randint, the trap-tile
    # shuffle, the 10 trap-kind draws, the spawn shuffle -- nothing else
    assert rng.calls == ["randint"] * 30 + ["shuffle"] \
        + ["choice"] * 10 + ["shuffle"]
