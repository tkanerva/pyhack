"""Tests for the scroll system (core/scrolls.py, the read.c port).

House conventions: table-driven over the C branches, SeqRng presets
the exact dice (the draws are the commented C rn2 / rnd sites in
core/scrolls.py, in C order), and every test asserts world state
*and* the event list.
"""
import pytest

from core import ReadCommand, step
from core.events import MessageEvent
from core.objects import (ObjClass, ObjType, W_ARMC, W_ARM, W_ARMH,
                          object_type)
from core.scrolls import read_scroll
from core.types import Item, ObjectType, ScrollType
from core.worn import which_armor
from conftest import SeqRng, make_world

O = ObjType

# the demo's elven suit / helm (C 5.0's elven armor subset)
ELVEN_SUIT = O.ELVEN_MITHRIL_COAT
ELVEN_HELM = O.ELVEN_LEATHER_HELM


def make_scroll(scroll_type, id="scr_0", blessed=False, cursed=False):
    it = Item(id=id, otype=ObjectType.SCROLL,
              name=scroll_type.name.lower().replace("_", " "),
              charges=1, blessed=blessed, cursed=cursed,
              scroll_type=scroll_type, container="player")
    return it


def add_scroll(world, scroll):
    world.items[scroll.id] = scroll
    world.hero.inventory.append(scroll)
    return scroll


def sword(spe=0, cursed=False):
    sw = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
              otyp=O.SHORT_SWORD.value, oclass=ObjClass.WEAPON.value,
              spe=spe, cursed=cursed)
    return sw


def armor(otyp, spe=0, cursed=False, mask=W_ARM, id="arm_0",
          blessed=False):
    it = Item(id=id, otype=ObjectType.ARMOR, name=object_type(otyp).name,
              otyp=otyp.value, oclass=ObjClass.ARMOR.value, spe=spe,
              blessed=blessed, cursed=cursed)
    it.owornmask = mask
    return it


def wear(hero, item):
    hero.inventory.append(item)
    return item


def read(w, scroll, rng):
    return read_scroll(w, "player", scroll.id, rng)


def texts(ev):
    return [e.text for e in ev if isinstance(e, MessageEvent)]


# ------------------------------------------------------------
# doread plumbing (find, consume, the "you read" line)
# ------------------------------------------------------------

def test_blank_paper_not_consumed():
    """C: doread skips useup for SCR_BLANK_PAPER."""
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.BLANK_PAPER))
    ev = read(w, scr, SeqRng())
    assert texts(ev) == ["This scroll seems to be blank."]
    assert scr in w.hero.inventory      # still carried
    assert w.items[scr.id] is scr


def test_no_scroll_rejected():
    w = make_world()
    ev = read_scroll(w, "player", "nope", SeqRng())
    assert texts(ev) == ["You don't have such a scroll."]


def test_floor_scroll_rejected():
    """A scroll lying on the floor (not carried) is not readable."""
    w = make_world()
    scr = make_scroll(ScrollType.BLANK_PAPER)
    scr.container = None
    scr.pos = (3, 3)
    w.items[scr.id] = scr
    ev = read_scroll(w, "player", scr.id, SeqRng())
    assert texts(ev) == ["You don't have such a scroll."]
    assert scr.pos == (3, 3)


def test_untyped_scroll_rejected():
    """A scroll item without an effect tag has nothing to read."""
    w = make_world()
    scr = Item(id="scr_0", otype=ObjectType.SCROLL, name="scroll",
               charges=1, container="player")
    add_scroll(w, scr)
    ev = read(w, scr, SeqRng())
    assert texts(ev) == ["You have nothing to read."]
    assert scr in w.hero.inventory


def test_unported_scroll_is_a_stub():
    """STUB: the remaining C seffect_* handlers raise loudly (the
    demo never carries such a scroll)."""
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.GENOCIDE))
    with pytest.raises(NotImplementedError, match="genocide"):
        read(w, scr, SeqRng())


def test_read_line_precedes_the_effect():
    w = make_world()
    wear(w.hero, armor(O.CHAIN_MAIL))
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng(2))
    assert ev[0].text == "As you read the scroll, it disappears."
    assert scr not in w.hero.inventory   # consumed after the effect


# ------------------------------------------------------------
# SCR_ENCHANT_WEAPON (seffect_enchant_weapon + chwepon)
# ------------------------------------------------------------

def _weapon_world(spe=0, cursed=False):
    w = make_world()
    sw = sword(spe=spe, cursed=cursed)
    w.items[sw.id] = sw
    w.hero.inventory.append(sw)
    w.hero.wielded = sw.id
    return w, sw


def test_enchant_weapon_no_weapon():
    """C: chwepon -> strange_feeling + useup (no weapon to enchant)."""
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON))
    ev = read(w, scr, SeqRng())
    assert texts(ev) == ["As you read the scroll, it disappears.",
                         "Your hands itch."]
    assert scr not in w.hero.inventory


def test_enchant_weapon_no_weapon_cursed_twitches():
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON, cursed=True))
    ev = read(w, scr, SeqRng())
    assert "Your hands twitch." in texts(ev)


def test_enchant_weapon_uncursed():
    """The flat +1: no dice at all (no C branch draws)."""
    w, sw = _weapon_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON))
    ev = read(w, scr, SeqRng())
    assert sw.spe == 1
    assert "Your short sword glows for a moment." in texts(ev)
    assert scr not in w.hero.inventory


def test_enchant_weapon_blessed():
    """C: rnd(3 - spe/3) for a blessed scroll (spe 0 -> rnd(3))."""
    w, sw = _weapon_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON,
                                    blessed=True))
    ev = read(w, scr, SeqRng(3))
    assert sw.spe == 3
    assert any("glows for a while" in t for t in texts(ev))


def test_enchant_weapon_cursed_disenchants():
    """C: s = -1 for a cursed scroll; chwepon does NOT curse the
    weapon (unlike the armor scroll's BUC transfer)."""
    w, sw = _weapon_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON,
                                    cursed=True))
    ev = read(w, scr, SeqRng())
    assert sw.spe == -1
    assert not sw.cursed
    assert any("glows for a moment" in t for t in texts(ev))


def test_enchant_weapon_high_spe_violently():
    """C: spe >= 9 -> s = (rn2(spe) == 0), here 0 -> the violent
    no-change glow; the soft-limit and vibration draws are audited
    (no evaporate: rn2(3) == 0; no vibration: rn2(7) == 0)."""
    w, sw = _weapon_world(spe=9)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON))
    ev = read(w, scr, SeqRng(1, 1, 1))
    assert sw.spe == 9
    assert any("violently glows for a while." in t for t in texts(ev))
    assert not any("vibrate" in t for t in texts(ev))


def test_enchant_weapon_evaporates_past_the_limit():
    """C: chwepon's soft limit -- a +6 weapon enchanted again
    (rn2(3) != 0, 2/3) evaporates; the wielded slot empties."""
    w, sw = _weapon_world(spe=6)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_WEAPON))
    ev = read(w, scr, SeqRng(2))       # rn2(3) != 0 -> evaporate
    assert w.items.get(sw.id) is None
    assert sw not in w.hero.inventory
    assert w.hero.wielded is None
    assert any("violently glows for a while and then evaporates." in t for t in texts(ev))
    assert scr not in w.hero.inventory


# ------------------------------------------------------------
# SCR_ENCHANT_ARMOR (seffect_enchant_armor + some_armor)
# ------------------------------------------------------------

def _armor_world(otyp, spe=0, cursed=False, mask=W_ARM, blessed=False):
    w = make_world()
    a = armor(otyp, spe=spe, cursed=cursed, mask=mask, blessed=blessed)
    w.items[a.id] = a
    wear(w.hero, a)
    return w, a


def test_enchant_armor_no_armor():
    """C: some_armor finds nothing -> strange_feeling + useup."""
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng())
    assert texts(ev) == ["As you read the scroll, it disappears.",
                         "Your skin glows then fades."]
    assert scr not in w.hero.inventory


def test_enchant_armor_chain_mail():
    """Base power (4-0)/2 = 2, +1 nonmagical (chain mail is not
    oc_magic) = rnd(3)."""
    w, a = _armor_world(O.CHAIN_MAIL)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng(2))
    assert a.spe == 2
    assert "Your chain mail glows for a while." in texts(ev)


def test_enchant_armor_blessed():
    """Base 2 + nonmagical 1 + blessed 1 = rnd(4); the armor gets
    the scroll's blessing (C's BUC transfer)."""
    w, a = _armor_world(O.CHAIN_MAIL)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR,
                                    blessed=True))
    ev = read(w, scr, SeqRng(4, 1))
    assert a.spe == 4
    assert a.blessed
    assert not a.cursed


def test_enchant_armor_cursed_disenchants_and_curses():
    """C: the sign flips (s = rnd(3 + 1) for chain at spe 3, here 2
    -> -2), and the cursed scroll curses the armor."""
    w, a = _armor_world(O.CHAIN_MAIL, spe=3)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR,
                                    cursed=True))
    ev = read(w, scr, SeqRng(2))
    assert a.spe == 1
    assert a.cursed
    assert any("glows for a while" in t for t in texts(ev))


def test_enchant_armor_elven_evaporates():
    """C: elven armor past the limit (elven 5) with rn2(s) != 0
    evaporates; the slot clears and the armor is consumed."""
    w, a = _armor_world(ELVEN_SUIT, spe=7)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng(2))
    assert w.items.get(a.id) is None
    assert a not in w.hero.inventory
    assert which_armor(w, w.hero, W_ARM) is None
    assert any("violently glows for a while, then evaporates." in t for t in texts(ev))
    assert scr not in w.hero.inventory


def test_enchant_armor_elven_high_spe_violently():
    """C: elven mithril coat at spe 8: (4-8)/2 = -2 + elven 1 +
    nonmagical 1 (C 5.0's row is not oc_magic) = 0 -> the rare
    +1 draw (rn2(8) == 0, here no) -> the violent no-change glow,
    and the elven trailing vibration clue (short-circuits the draw)."""
    w, a = _armor_world(ELVEN_SUIT, spe=8)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng(1, 1))
    assert a.spe == 8
    assert any("violently glows for a while." in t for t in texts(ev))
    assert any("suddenly vibrates unexpectedly." in t for t in texts(ev))


def test_enchant_armor_prefers_helmet_by_roll():
    """C: some_armor -- the suit is picked, then a worn helmet takes
    over 3/4 of the time (here it does).  The elven leather helm is
    both special and nonmagical (C 5.0: not oc_magic): (4-0)/2 = 2
    + 1 + 1 = rnd(4)."""
    w = make_world()
    chain = armor(O.CHAIN_MAIL, id="arm_0")
    helm = armor(ELVEN_HELM, mask=W_ARMH, id="arm_1")
    for it in (chain, helm):
        w.items[it.id] = it
        wear(w.hero, it)
    scr = add_scroll(w, make_scroll(ScrollType.ENCHANT_ARMOR))
    ev = read(w, scr, SeqRng(3, 4))
    assert helm.spe == 4
    assert chain.spe == 0
    assert any("elven leather helm glows for a while" in t for t in texts(ev))


# ------------------------------------------------------------
# SCR_REMOVE_CURSE
# ------------------------------------------------------------

def test_remove_curse_ancurses_worn_gear():
    """C: the wornmask condition -- the worn cursed cloak is
    uncursed (silently, as C's uncurse() does)."""
    w, cloak = _armor_world(O.LEATHER_CLOAK, cursed=True, mask=W_ARMC)
    scr = add_scroll(w, make_scroll(ScrollType.REMOVE_CURSE))
    ev = read(w, scr, SeqRng())
    assert cloak.cursed is False
    assert texts(ev) == ["As you read the scroll, it disappears.",
                         "You feel like someone is helping you."]
    assert scr not in w.hero.inventory


def test_remove_curse_uncursed_ignores_carried_gear():
    """C-faithful detail: an uncursed scroll only touches WORN items
    (a blessed one touches the whole pack)."""
    w = make_world()
    ring = armor(O.RIN_PROTECTION, spe=1, cursed=True, mask=0)
    ring.otype = ObjectType.RING
    ring.oclass = ObjClass.RING.value
    w.items[ring.id] = ring
    wear(w.hero, ring)
    scr = add_scroll(w, make_scroll(ScrollType.REMOVE_CURSE))
    read(w, scr, SeqRng())
    assert ring.cursed is True          # carried, not worn


def test_remove_curse_blessed_ancurses_carried_gear():
    w = make_world()
    ring = armor(O.RIN_PROTECTION, spe=1, cursed=True, mask=0)
    ring.otype = ObjectType.RING
    ring.oclass = ObjClass.RING.value
    w.items[ring.id] = ring
    wear(w.hero, ring)
    scr = add_scroll(w, make_scroll(ScrollType.REMOVE_CURSE,
                                    blessed=True))
    read(w, scr, SeqRng())
    assert ring.cursed is False


def test_remove_curse_cursed_scroll_disintegrates():
    """C: a cursed remove curse only disintegrates (the nodisappear
    "you read the scroll" line, no uncurse at all)."""
    w, cloak = _armor_world(O.LEATHER_CLOAK, cursed=True, mask=W_ARMC)
    scr = add_scroll(w, make_scroll(ScrollType.REMOVE_CURSE, cursed=True))
    ev = read(w, scr, SeqRng())
    assert texts(ev) == ["You read the scroll.",
                         "You feel like someone is helping you.",
                         "The scroll disintegrates."]
    assert cloak.cursed is True         # nothing was uncursed
    assert scr not in w.hero.inventory


# ------------------------------------------------------------
# SCR_TELEPORTATION
# ------------------------------------------------------------

def test_teleportation_moves_the_hero():
    """The demo's single-level teleport: a random walkable floor tile
    (rules.teleport_to_floor -- the same dungeon tile check the demo
    trap / monster placement uses)."""
    w = make_world()                    # 12x8 all-floor, hero (6,4)
    scr = add_scroll(w, make_scroll(ScrollType.TELEPORTATION))
    ev = read(w, scr, SeqRng((3, 2)))
    assert w.hero.pos == (3, 2)
    assert any("teleported" in t for t in texts(ev))
    assert scr not in w.hero.inventory


# ------------------------------------------------------------
# the step() wiring
# ------------------------------------------------------------

def test_step_wires_read_command():
    w = make_world()
    scr = add_scroll(w, make_scroll(ScrollType.TELEPORTATION))
    ev = step(w, ReadCommand(scr.id), SeqRng((3, 2)))
    assert w.hero.pos == (3, 2)
    assert scr not in w.hero.inventory
    assert w.items.get(scr.id) is None
    assert w.turn == 1
    assert any(isinstance(e, MessageEvent)
               and e.text == "As you read the scroll, it disappears."
               for e in ev)
