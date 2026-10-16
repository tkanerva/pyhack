"""Tests for the wand system."""
from core import Direction
from core.types import Item, ObjectType, WandType
from core.zap import use_wand
from conftest import SeqRng, make_monster, make_world


def world_with_wand(wand_type, **monster_kw):
    mon = make_monster(pos=(8, 4), **monster_kw)
    w = make_world(monsters=[mon])
    wand = Item(id="wand_0", otype=ObjectType.WAND, name="Wand",
                charges=1, wand_type=wand_type, container="player")
    w.items["wand_0"] = wand
    w.hero.inventory.append(wand)
    return w


def test_fire_wand_deals_6d6_damage():
    # C: the wand of fire is ubuzz(BZ_U_WAND(WAN_FIRE), 6) -> d(6, 6).
    # The beam-range roll (7 + rnd(7)) is drawn first, then the six
    # damage dice.  All-ones is the minimum 6d6: 6 damage, 8 -> 2.
    w = world_with_wand(WandType.FIRE)
    use_wand(w, "player", WandType.FIRE, Direction.E,
             SeqRng(5, 1, 1, 1, 1, 1, 1))
    assert w.actors["goblin_0"].hp == 2
    assert w.items == {}  # charge consumed, item removed


def test_death_wand_undead_unaffected():
    # C: the death ray heals ONLY the Death monster itself (zap.c
    # ZT_DEATH: mon->data == &mons[PM_DEATH]); any other monster -- a
    # generic undead included -- is unaffected in the demo
    # (rules.resists(DEATH)).  No heal; the charge is still consumed.
    w = world_with_wand(WandType.DEATH, is_undead=True, hp=3, max_hp=20)
    use_wand(w, "player", WandType.DEATH, Direction.E, SeqRng(5))
    assert w.actors["goblin_0"].hp == 3
    assert w.items == {}


def test_sleep_wand_puts_to_sleep():
    # C: the sleep ray draws only the beam-range roll; the sleep is a
    # flat 25 turns (no damage dice), so one preset value suffices.
    w = world_with_wand(WandType.SLEEP)
    use_wand(w, "player", WandType.SLEEP, Direction.E, SeqRng(5))
    assert w.actors["goblin_0"].sleeping == 25


def test_demon_resists_fire_wand():
    # C: resistance is tested before the damage roll, so a resisted zap
    # draws no dice -- only the beam-range roll (one preset value).
    w = world_with_wand(WandType.FIRE, is_demon=True)
    use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng(5))
    assert w.actors["goblin_0"].hp == 8


def test_no_target_still_consumes_charge():
    w = world_with_wand(WandType.FIRE)
    w.actors["goblin_0"].pos = (50, 4)  # off the 12-wide map
    use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng(5))
    assert w.items == {}
    assert w.actors["goblin_0"].hp == 8


def test_missing_wand_is_a_message_not_a_crash():
    w = make_world(monsters=[make_monster(pos=(8, 4))])
    ev = use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng())
    assert "wand" in ev[0].text.lower()
