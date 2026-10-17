"""Tests for the wand system."""
from core import Direction
from core.events import MessageEvent
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


def test_fire_wand_deals_flat_six_damage():
    # the first draw is the beam range (C: 7 + rnd(7)), then the
    # damage: six d6 (C: ubuzz(BZ_U_WAND(WAN_FIRE), 6)), all ones
    w = world_with_wand(WandType.FIRE)
    use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng(1, 1, 1, 1, 1, 1, 1))
    assert w.actors["goblin_0"].hp == 2
    assert w.items == {}  # charge consumed, item removed


def test_death_wand_resisted_by_undead():
    """The ported simplification (zap.py docstring): the C
    nonliving / demon / magic-resist "unaffected" set maps onto
    rules.resists(DEATH) (undead / demon / golem); the old demo's
    "undead absorb the death ray" heal is dropped (C heals only the
    Death monster itself, which the demo has no)."""
    w = world_with_wand(WandType.DEATH, is_undead=True, hp=3, max_hp=20)
    ev = use_wand(w, "player", WandType.DEATH, Direction.E, SeqRng(1))
    assert w.actors["goblin_0"].hp == 3   # resisted: neither healed nor hurt
    # the resistance is tested before the damage roll (C): no dice drawn
    assert any("is unaffected" in e.text
               for e in ev if isinstance(e, MessageEvent))


def test_sleep_wand_puts_to_sleep():
    w = world_with_wand(WandType.SLEEP)
    use_wand(w, "player", WandType.SLEEP, Direction.E, SeqRng(1))
    assert w.actors["goblin_0"].sleeping == 25


def test_demon_resists_fire_wand():
    w = world_with_wand(WandType.FIRE, is_demon=True)
    use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng(1))
    assert w.actors["goblin_0"].hp == 8


def test_no_target_still_consumes_charge():
    w = world_with_wand(WandType.FIRE)
    w.actors["goblin_0"].pos = (50, 4)  # off the 12-wide map
    use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng(1))
    assert w.items == {}
    assert w.actors["goblin_0"].hp == 8


def test_missing_wand_is_a_message_not_a_crash():
    w = make_world(monsters=[make_monster(pos=(8, 4))])
    ev = use_wand(w, "player", WandType.FIRE, Direction.E, SeqRng())
    assert "wand" in ev[0].text.lower()
