"""Tests for the erosion half of core.worn -- PLAN-ARMOR.md phase 4.

Phase 4 landed as code with no test pinning it (the plan's own
"Phase 4's test suite is pending"); this file is that suite, plus the
``fire-trap-erodes-armour`` regression PLAN-MKOBJ.md's Definition of
Done names (before ``Item`` grew its erosion fields the fire trap hit
``AttributeError`` on a hero in worn armour).

What is under test, in C's order:

- the material predicates (obj.h + mkobj.c ``is_flammable`` /
  ``is_rustprone`` / ``is_crackable`` / ``is_rottable`` /
  ``is_corrodeable`` / ``is_damageable``) over REAL table rows;
- ``erosion_matters`` (objnam.c) and ``obj_erode_type`` (do_wear.c);
- ``erode_obj`` (the hero-facing subset of trap.c): the ``oeroded`` /
  ``oeroded2`` counters, the message ladder (plain / further /
  completely), the grease protection with its 1/2 wear-off, the blessed
  1/4 resistance, ``oerodeproof``, and the ``EF_DESTROY`` destruction
  (the worn slot is cleared and the item leaves the world);
- the two live call sites: ``burnarmor`` (trap.c, the fire trap) and
  ``erode_armor`` (uhitm.c, the acid passive attack);
- the destroy-armour scroll's two entry points ``disintegrate_arm`` /
  ``destroy_arm`` (do_wear.c).

The AC effect is free and gets its own assertion: ``arm_bonus`` reads
``greatest_erosion`` and ``worn.uac`` is computed on every query, so an
eroded suit lowers the hero's AC with no cache to invalidate.
"""

from __future__ import annotations

import itertools

from core.mkobj import may_generate_eroded, mkobj_erosions
from core.objects import OBJECTS, ObjClass, ObjType, W_ARM, W_ARMC, W_ARMH
from core.types import Item, ObjectType, Trap, TrapType
from core.worn import (
    EF_DESTROY,
    EF_GREASE,
    EF_NONE,
    EF_VERBOSE,
    ER_DAMAGED,
    ER_DESTROYED,
    ER_GREASED,
    ER_NOTHING,
    ERODE_BURN,
    ERODE_CORRODE,
    ERODE_CRACK,
    ERODE_ROT,
    ERODE_RUST,
    MAX_ERODE,
    arm_bonus,
    burnarmor,
    destroy_arm,
    disintegrate_arm,
    erode_armor,
    erode_obj,
    erosion_matters,
    is_corrodeable,
    is_crackable,
    is_damageable,
    is_flammable,
    is_rottable,
    is_rustprone,
    obj_erode_type,
    uac,
)
from core.traps import TRAP_EFFECTS, check_traps
from conftest import SeqRng, make_hero, make_world

_ids = itertools.count()

_COARSE = {
    int(ObjClass.ARMOR): ObjectType.ARMOR,
    int(ObjClass.WEAPON): ObjectType.WEAPON,
    int(ObjClass.POTION): ObjectType.POTION,
    int(ObjClass.SCROLL): ObjectType.SCROLL,
}


def _item(otyp: ObjType, owornmask: int = 0, name=None, **kw) -> Item:
    """A runtime Item with the fine identity of table row `otyp`."""
    row = OBJECTS[otyp.value]
    return Item(
        id=f"it_{next(_ids)}",
        otype=_COARSE[int(row.oclass)],
        name=name if name is not None else str(row.name),
        otyp=otyp.value,
        oclass=int(row.oclass),
        owornmask=owornmask,
        **kw,
    )


def _add(w, mon, item) -> Item:
    item.carrier = mon.id
    mon.inventory.append(item)
    w.items[item.id] = item
    return item


def _messages(events):
    return [e.text for e in events if hasattr(e, "text")]


# ------------------------------------------------------------
# the material predicates (obj.h + mkobj.c)
# ------------------------------------------------------------


def test_material_predicates_against_real_rows():
    leather = _item(ObjType.LEATHER_ARMOR)
    assert is_flammable(leather) and is_rottable(leather)
    assert not is_rustprone(leather)
    assert not is_corrodeable(leather)
    assert not is_crackable(leather)
    assert is_damageable(leather)

    mail = _item(ObjType.CHAIN_MAIL)  # IRON
    assert is_rustprone(mail) and is_corrodeable(mail)
    assert not is_flammable(mail)
    assert not is_rottable(mail)
    assert not is_crackable(mail)
    assert is_damageable(mail)

    crystal = _item(ObjType.CRYSTAL_PLATE_MAIL)  # GLASS armour
    assert is_crackable(crystal)
    assert not is_rustprone(crystal)
    assert not is_corrodeable(crystal)
    assert not is_flammable(crystal)
    assert is_damageable(crystal)

    robe = _item(ObjType.ROBE)  # CLOTH
    assert is_flammable(robe) and is_rottable(robe)


def test_erosion_matters_only_for_weapon_and_armor():
    assert erosion_matters(_item(ObjType.LEATHER_ARMOR))
    assert erosion_matters(_item(ObjType.SHORT_SWORD))
    # a potion / a scroll / food never erodes (C: objnam.c erosion_matters)
    assert not erosion_matters(_item(ObjType.POT_OIL))
    assert not erosion_matters(_item(ObjType.SCR_TELEPORTATION))


def test_obj_erode_type_priority():
    # C's do_wear.c priority order is burn, rust, crack, rot, corrode
    assert obj_erode_type(_item(ObjType.LEATHER_ARMOR)) == ERODE_BURN
    assert obj_erode_type(_item(ObjType.CHAIN_MAIL)) == ERODE_RUST
    assert obj_erode_type(_item(ObjType.CRYSTAL_PLATE_MAIL)) == ERODE_CRACK


# ------------------------------------------------------------
# erode_obj: the counters and the message ladder
# ------------------------------------------------------------


def test_erode_obj_counts_and_messages():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    assert arm_bonus(mail) == 5
    assert uac(w, hero) == 0  # base 5 - 5

    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng())
    assert code == ER_DAMAGED
    assert _messages(ev) == ["Your chain mail rusts!"]
    assert mail.oeroded == 1
    assert arm_bonus(mail) == 4  # the AC follows for free

    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng())
    assert _messages(ev) == ["Your chain mail rusts further!"]
    assert mail.oeroded == 2

    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng())
    assert _messages(ev) == ["Your chain mail rusts completely!"]
    assert mail.oeroded == MAX_ERODE
    assert arm_bonus(mail) == 2

    # at MAX_ERODE without EF_DESTROY nothing more happens; only a
    # verbose call says so (C: the "looks completely rusted" line)
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_NONE, SeqRng())
    assert (ev, code) == ([], ER_NOTHING)
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng())
    assert code == ER_NOTHING
    assert _messages(ev) == ["Your chain mail looks completely rusted."]


def test_erode_obj_secondary_counter():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    ev, code = erode_obj(w, mail, None, ERODE_CORRODE, EF_VERBOSE, SeqRng())
    assert code == ER_DAMAGED
    assert _messages(ev) == ["Your chain mail corrodes!"]
    assert (mail.oeroded, mail.oeroded2) == (0, 1)  # the SECOND counter
    # rot is secondary too
    robe = _add(w, hero, _item(ObjType.ROBE, owornmask=W_ARMC))
    ev, code = erode_obj(w, robe, None, ERODE_ROT, EF_VERBOSE, SeqRng())
    assert _messages(ev) == ["Your robe rots!"]
    assert (robe.oeroded, robe.oeroded2) == (0, 1)


def test_erode_obj_destroys_at_max():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    mail.oeroded = MAX_ERODE
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_DESTROY, SeqRng())
    assert code == ER_DESTROYED
    assert _messages(ev) == ["Your chain mail rusts away!"]
    assert mail.id not in w.items
    assert mail not in hero.inventory
    assert mail.owornmask == 0
    assert uac(w, hero) == 5  # nothing worn any more

    # crystal armour SHATTERS instead (C: the crackers branch)
    crystal = _add(w, hero, _item(ObjType.CRYSTAL_PLATE_MAIL, owornmask=W_ARM))
    crystal.oeroded = MAX_ERODE
    ev, code = erode_obj(w, crystal, None, ERODE_CRACK, EF_DESTROY, SeqRng())
    assert code == ER_DESTROYED
    assert _messages(ev) == ["Your crystal plate mail shatters!"]
    assert crystal.id not in w.items


def test_erode_obj_grease_protection():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM, greased=True))
    # the grease protects; the 1/2 wear-off roll says "keep it" (0, 1, 2 -> rn2 = 1)
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_GREASE, SeqRng(2))
    assert code == ER_GREASED
    assert _messages(ev) == ["Your chain mail is protected by the layer of grease!"]
    assert mail.greased is True
    assert mail.oeroded == 0
    # ...and this time it dissolves (rn2(2) == 0)
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_GREASE, SeqRng(1))
    assert code == ER_GREASED
    assert _messages(ev) == [
        "Your chain mail is protected by the layer of grease!",
        "The grease dissolves.",
    ]
    assert mail.greased is False


def test_erode_obj_blessed_resistance():
    # C: the blessed 1/4 resistance (`!rnl(4)` at zero luck) -> one draw
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM, blessed=True))
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng(1))
    assert code == ER_NOTHING
    assert _messages(ev) == [
        "Somehow, your chain mail is not affected by the oxidation."
    ]
    assert mail.oeroded == 0
    # a non-resisting roll erodes as usual
    ev, code = erode_obj(w, mail, None, ERODE_RUST, EF_VERBOSE, SeqRng(2))
    assert code == ER_DAMAGED
    assert mail.oeroded == 1


def test_erode_obj_oerodeproof_and_non_erodeable():
    w = make_world()
    hero = w.hero
    proof = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM, oerodeproof=True))
    ev, code = erode_obj(w, proof, None, ERODE_RUST, EF_VERBOSE, SeqRng())
    assert code == ER_NOTHING
    assert proof.oeroded == 0
    assert _messages(ev) == ["Your chain mail is not affected by oxidation."]
    # silent without EF_VERBOSE (C: the print_ gate)
    assert erode_obj(w, proof, None, ERODE_RUST, EF_NONE, SeqRng()) == (
        [],
        ER_NOTHING,
    )

    # a potion is not erodeable at all
    potion = _add(w, hero, _item(ObjType.POT_OIL))
    ev, code = erode_obj(w, potion, None, ERODE_BURN, EF_VERBOSE, SeqRng())
    assert (ev, code) == ([], ER_NOTHING)

    # a non-vulnerable item under an explicit (verbose) call says so
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    ev, code = erode_obj(w, mail, None, ERODE_BURN, EF_VERBOSE, SeqRng())
    assert code == ER_NOTHING
    assert _messages(ev) == ["Your chain mail is not affected by heat."]


def test_erode_obj_invalid_type_raises():
    w = make_world()
    mail = _add(w, w.hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    try:
        erode_obj(w, mail, None, 99, EF_NONE, SeqRng())
    except ValueError:
        pass
    else:  # pragma: no cover - the raise IS the assertion
        raise AssertionError("erode_obj accepted an invalid erosion type")


def test_mkobj_erosions_generates_the_proof_flag():
    """C: mkobj_erosions -- the erodeproof roll (rn2(100) == 0) sets
    Item.oerodeproof and SKIPS the erosion / grease rolls."""
    w = make_world()
    mail = _add(w, w.hero, _item(ObjType.CHAIN_MAIL))
    assert may_generate_eroded(mail)
    mkobj_erosions(w, SeqRng(0), mail)
    assert mail.oerodeproof is True
    assert mail.oeroded == 0 and mail.greased is False

    # the ordinary path: two flammability hits, then no grease
    w2 = make_world()
    leather = _add(w2, w2.hero, _item(ObjType.LEATHER_ARMOR))
    mkobj_erosions(w2, SeqRng(50, 80, 9, 1, 500), leather)
    assert leather.oerodeproof is False
    assert leather.oeroded == 2
    assert leather.greased is False

    # non-erodable classes take no rolls at all
    potion = _add(w2, w2.hero, _item(ObjType.POT_OIL))
    assert not may_generate_eroded(potion)
    mkobj_erosions(w2, SeqRng(), potion)
    assert potion.oeroded == 0


# ------------------------------------------------------------
# the two live call sites
# ------------------------------------------------------------


def test_erode_armor_picks_a_worn_piece():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    # case = 1 (the torso tier): cloak, else suit, else shirt -> the suit
    ev = erode_armor(w, hero, ERODE_RUST, SeqRng(2))
    assert _messages(ev) == ["Your chain mail rusts!"]
    assert mail.oeroded == 1

    # a carrier with nothing worn gets no events at all
    bare = make_world()
    assert erode_armor(bare, bare.hero, ERODE_RUST, SeqRng()) == []


def test_burnarmor_picks_a_worn_piece():
    w = make_world()
    hero = w.hero
    leather = _add(w, hero, _item(ObjType.LEATHER_ARMOR, owornmask=W_ARM))
    ev = burnarmor(w, hero, SeqRng(2))  # case = 1 -> the torso tier
    assert _messages(ev) == ["Your leather armor smoulders!"]
    assert leather.oeroded == 1


def test_fire_trap_erodes_the_worn_armour():
    """The PLAN-MKOBJ.md DoD regression: a fire trap on a hero in worn
    armour erodes it.  This path used to raise ``AttributeError`` (Item
    had no ``oeroded`` / ``oerodeproof`` -- PLAN-MKOBJ §2's live defect)."""
    w = make_world()
    hero = w.hero
    leather = _add(w, hero, _item(ObjType.LEATHER_ARMOR, owornmask=W_ARM))
    # the trap effect directly: 1d6 damage, then the burnarmor 5-way pick
    ev = TRAP_EFFECTS[TrapType.FIRE_TRAP](w, _fire_trap(), "player", SeqRng(3, 2, 2))
    assert any("fire trap" in text for text in _messages(ev))
    assert any("smoulders" in text for text in _messages(ev))
    assert leather.oeroded == 1

    # ...and through the whole trigger path (the 30% roll first)
    w2 = make_world()
    hero2 = w2.hero
    cloak = _add(w2, hero2, _item(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    trap = _fire_trap()
    w2.traps[trap.id] = trap
    ev = check_traps(w2, "player", SeqRng(30, 4, 2, 2, 2))
    assert any("smoulders" in text for text in _messages(ev))
    assert cloak.oeroded == 1


def _fire_trap() -> Trap:
    return Trap(id="trap_fire", trap_type=TrapType.FIRE_TRAP, pos=(6, 4))


# ------------------------------------------------------------
# the destroy-armour scroll's two entry points
# ------------------------------------------------------------


def test_disintegrate_arm_takes_the_first_piece_in_c_order():
    w = make_world()
    hero = w.hero
    cloak = _add(w, hero, _item(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    suit = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    ev = disintegrate_arm(w, "player", SeqRng())
    # C's order is cloak, suit, shirt, helmet, gloves, boots, shield
    assert _messages(ev) == ["Your leather cloak crumbles and turns to dust!"]
    assert cloak.id not in w.items
    assert suit.id in w.items
    assert suit.owornmask == W_ARM  # untouched

    # with no cloak, the suit goes next
    ev = disintegrate_arm(w, "player", SeqRng())
    assert _messages(ev) == ["Your chain mail turns to dust and falls to the floor!"]
    assert suit.id not in w.items

    # nothing worn -> C's 0 (an empty event list)
    assert disintegrate_arm(w, "player", SeqRng()) == []


def test_destroy_arm_erodes_and_stops_at_destruction():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    mail.oeroded = MAX_ERODE  # one more rust destroys it
    # hits = _rn2(4) + 1 = 4 ; the only worn piece is picked every time
    ev = destroy_arm(w, "player", SeqRng(4, 1))
    assert _messages(ev) == ["Your chain mail rusts away!"]
    assert mail.id not in w.items

    # nothing worn -> no events
    bare = make_world()
    assert destroy_arm(bare, "player", SeqRng()) == []
    # a helmet-only hero still takes a hit on a non-erodeable... no:
    # every armour row erodes, so the hit lands on the helmet.
    w2 = make_world(hero=make_hero())
    helm = _add(w2, w2.hero, _item(ObjType.HELMET, owornmask=W_ARMH))
    ev = destroy_arm(w2, "player", SeqRng(1, 1))
    assert _messages(ev) == ["Your helmet rusts!"]
    assert helm.oeroded == 1
