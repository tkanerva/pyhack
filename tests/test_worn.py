"""Tests for core.worn: the worn data model + AC core (Phase 1 of
PLAN-ARMOR.md) and the donning / doffing half (Phase 2).

The item builder uses the real core.objects table (fine identity), so
the predicates and the ARM_BONUS math are checked against the C values
(a_ac = the table's oc1 = 10 - the macro's ac argument).
"""
import itertools

from core.objects import (OBJECTS, ObjClass, ObjType, W_AMUL, W_ARM,
                          W_ARMC, W_ARMF, W_ARMG, W_ARMH, W_ARMOR,
                          W_ARMS, W_ARMU, W_RING, W_RINGL, W_RINGR)
from core.types import Item, Monster, ObjectType
from core.worn import (AC_MAX, ac_bonus, ac_value, arm_bonus, armor_slot,
                       can_wear, dotakeoff, dowear, is_armor, is_boots,
                       is_cloak, is_gloves, is_helmet, is_shield, is_shirt,
                       is_suit, is_worn, setnotworn, setworn, uac,
                       wearing_armor, which_armor)
from conftest import SeqRng, make_hero, make_world

_ids = itertools.count()

# fine oclass -> coarse ObjectType for the Item field
_COARSE = {
    int(ObjClass.ARMOR): ObjectType.ARMOR,
    int(ObjClass.RING): ObjectType.RING,
    int(ObjClass.AMULET): ObjectType.AMULET,
    int(ObjClass.WEAPON): ObjectType.WEAPON,
}


def _item(otyp: ObjType, name=None, spe=0, cursed=False, owornmask=0) -> Item:
    """A runtime Item with the fine identity of table row `otyp`."""
    o = OBJECTS[otyp.value]
    oclass = int(o.oclass)
    return Item(
        id=f"it_{next(_ids)}", otype=_COARSE[oclass],
        name=name if name is not None else (o.name or o.descr),
        otyp=otyp.value, oclass=oclass, spe=spe, cursed=cursed,
        owornmask=owornmask)


def _add(w, mon, item) -> Item:
    """Carry `item` in `mon`'s inventory (and the world registry)."""
    item.container = mon.id
    mon.inventory.append(item)
    w.items[item.id] = item
    return item


# ------------------------------------------------------------
# the obj.h predicates
# ------------------------------------------------------------

def test_armor_predicates_against_real_rows():
    rows = {
        ObjType.LEATHER_ARMOR: is_suit,
        ObjType.LEATHER_JACKET: is_suit,
        ObjType.GRAY_DRAGON_SCALE_MAIL: is_suit,
        ObjType.HAWAIIAN_SHIRT: is_shirt,
        ObjType.ROBE: is_cloak,
        ObjType.LEATHER_CLOAK: is_cloak,
        ObjType.MUMMY_WRAPPING: is_cloak,
        ObjType.SMALL_SHIELD: is_shield,
        ObjType.LEATHER_GLOVES: is_gloves,
        ObjType.LOW_BOOTS: is_boots,
        ObjType.ELVEN_LEATHER_HELM: is_helmet,
        ObjType.HELMET: is_helmet,
    }
    for otyp, pred in rows.items():
        it = _item(otyp)
        assert is_armor(it), otyp
        assert pred(it), otyp
    # cross-predicates fail
    assert not is_suit(_item(ObjType.ROBE))
    assert not is_cloak(_item(ObjType.CHAIN_MAIL))
    assert not is_shirt(_item(ObjType.LEATHER_ARMOR))
    assert not is_helmet(_item(ObjType.SMALL_SHIELD))
    # non-armor is not armor
    assert not is_armor(_item(ObjType.SHORT_SWORD))
    assert not is_armor(_item(ObjType.RIN_PROTECTION))


# ------------------------------------------------------------
# armor_slot (the wornmask macro, armor branch)
# ------------------------------------------------------------

def test_armor_slot_maps_armcat_to_mask():
    expect = {
        ObjType.CHAIN_MAIL: W_ARM,
        ObjType.LEATHER_JACKET: W_ARM,
        ObjType.LEATHER_CLOAK: W_ARMC,
        ObjType.ROBE: W_ARMC,
        ObjType.HELMET: W_ARMH,
        ObjType.SMALL_SHIELD: W_ARMS,
        ObjType.LEATHER_GLOVES: W_ARMG,
        ObjType.LOW_BOOTS: W_ARMF,
        ObjType.HAWAIIAN_SHIRT: W_ARMU,
    }
    for otyp, mask in expect.items():
        assert armor_slot(_item(otyp)) == mask, otyp
    assert armor_slot(_item(ObjType.RIN_PROTECTION)) == 0
    assert armor_slot(_item(ObjType.AMULET_OF_GUARDING)) == 0


# ------------------------------------------------------------
# arm_bonus (C ARM_BONUS)
# ------------------------------------------------------------

def test_arm_bonus():
    # a_ac (the table's oc1 = 10 - ac): leather 2 / chain 5 / plate 7
    assert arm_bonus(_item(ObjType.LEATHER_ARMOR)) == 2
    assert arm_bonus(_item(ObjType.CHAIN_MAIL)) == 5
    assert arm_bonus(_item(ObjType.PLATE_MAIL)) == 7
    # +N enchantment (spe) adds on
    assert arm_bonus(_item(ObjType.CHAIN_MAIL, spe=3)) == 8
    # negative enchantment subtracts
    assert arm_bonus(_item(ObjType.CHAIN_MAIL, spe=-2)) == 3
    # erosion caps the bonus at a_ac - erosion
    it = _item(ObjType.CHAIN_MAIL)
    it.oeroded = 4
    assert arm_bonus(it) == 1
    it2 = _item(ObjType.CHAIN_MAIL)
    it2.oeroded = 9  # min(greatest_erosion, a_ac)
    assert arm_bonus(it2) == 0
    # non-armor is 0
    assert arm_bonus(_item(ObjType.SHORT_SWORD)) == 0


# ------------------------------------------------------------
# ac_bonus (the gear half of find_ac)
# ------------------------------------------------------------

def test_ac_bonus_sums_the_seven_slots():
    w = make_world()
    hero = w.hero
    slots = [
        (W_ARM, ObjType.CHAIN_MAIL, 5),
        (W_ARMC, ObjType.ELVEN_CLOAK, 1),
        (W_ARMH, ObjType.HELMET, 1),
        (W_ARMS, ObjType.SMALL_SHIELD, 1),
        (W_ARMG, ObjType.LEATHER_GLOVES, 1),
        (W_ARMF, ObjType.LOW_BOOTS, 1),
        (W_ARMU, ObjType.HAWAIIAN_SHIRT, 0),
    ]
    total = 0
    for mask, otyp, bonus in slots:
        _add(w, hero, _item(otyp, owornmask=mask))
        total += bonus
        assert ac_bonus(w, hero) == total, (mask, otyp)


def test_ac_bonus_protection_rings():
    w = make_world()
    hero = w.hero
    left = _add(w, hero, _item(ObjType.RIN_PROTECTION, spe=2,
                               owornmask=W_RINGL))
    right = _add(w, hero, _item(ObjType.RIN_PROTECTION, spe=1,
                                owornmask=W_RINGR))
    assert ac_bonus(w, hero) == 3
    # a negative-spe protection ring worsens AC
    right.spe = -1
    assert ac_bonus(w, hero) == 1
    # a non-protection ring gives nothing
    w2 = make_world()
    _add(w2, w2.hero, _item(ObjType.RIN_ADORNMENT, spe=9,
                            owornmask=W_RINGL))
    assert ac_bonus(w2, w2.hero) == 0


def test_ac_bonus_amulet_of_guarding():
    w = make_world()
    hero = w.hero
    _add(w, hero, _item(ObjType.AMULET_OF_GUARDING, owornmask=W_AMUL))
    assert ac_bonus(w, hero) == 2
    # another amulet type gives nothing
    w2 = make_world()
    _add(w2, w2.hero, _item(ObjType.AMULET_OF_ESP, owornmask=W_AMUL))
    assert ac_bonus(w2, w2.hero) == 0


# ------------------------------------------------------------
# uac (C find_ac) and ac_value (C AC_VALUE)
# ------------------------------------------------------------

def test_uac_full_set_and_clamp():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    full = [
        (W_ARM, ObjType.CHAIN_MAIL),        # 5
        (W_ARMC, ObjType.ELVEN_CLOAK),      # 1
        (W_ARMH, ObjType.HELMET),           # 1
        (W_ARMS, ObjType.SMALL_SHIELD),     # 1
        (W_ARMG, ObjType.LEATHER_GLOVES),   # 1
        (W_ARMF, ObjType.LOW_BOOTS),        # 1
        (W_ARMU, ObjType.HAWAIIAN_SHIRT),   # 0
    ]
    for mask, otyp in full:
        _add(w, hero, _item(otyp, owornmask=mask))
    assert uac(w, hero) == 0  # 10 - 10
    # the ublessed / uspellprot arguments (zero until the priest /
    # spell ports land)
    assert uac(w, hero, ublessed=2, uspellprot=1) == -3
    # clamp to +/-AC_MAX (the clamp step, unit-tested)
    w2 = make_world(hero=make_hero(ac=200))
    assert uac(w2, w2.hero) == AC_MAX
    w3 = make_world(hero=make_hero(ac=-200))
    assert uac(w3, w3.hero) == -AC_MAX


def test_ac_value_positive_is_identity_without_draw():
    rng = SeqRng(7, 8)
    assert ac_value(0, rng) == 0
    assert ac_value(13, rng) == 13
    assert rng._values == [7, 8]  # no draw


def test_ac_value_negative_rolls():
    assert ac_value(-2, SeqRng(2)) == -2
    assert ac_value(-2, SeqRng(1)) == -1
    assert ac_value(-1, SeqRng(1)) == -1


# ------------------------------------------------------------
# the slot machinery (setworn / which_armor / wearing_armor)
# ------------------------------------------------------------

def test_setworn_which_armor_wearing_armor():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL))
    assert which_armor(w, hero, W_ARM) is None
    assert not wearing_armor(hero)
    assert not is_worn(mail)

    setworn(hero, mail, W_ARM)
    assert mail.owornmask == W_ARM
    assert which_armor(w, hero, W_ARM) is mail
    assert wearing_armor(hero)
    assert is_worn(mail)

    # replacing: the old mask is cleared from the displaced item
    jacket = _add(w, hero, _item(ObjType.LEATHER_JACKET))
    setworn(hero, jacket, W_ARM)
    assert mail.owornmask == 0
    assert jacket.owornmask == W_ARM
    assert which_armor(w, hero, W_ARM) is jacket
    assert len([it for it in hero.inventory if it.owornmask & W_ARM]) == 1

    # emptying the slot
    setworn(hero, None, W_ARM)
    assert jacket.owornmask == 0
    assert which_armor(w, hero, W_ARM) is None
    assert not wearing_armor(hero)

    # rings / amulets are accessories, not armor
    ring = _add(w, hero, _item(ObjType.RIN_PROTECTION))
    amul = _add(w, hero, _item(ObjType.AMULET_OF_GUARDING))
    setworn(hero, ring, W_RINGL)
    setworn(hero, amul, W_AMUL)
    assert which_armor(w, hero, W_RING) is ring
    assert which_armor(w, hero, W_AMUL) is amul
    assert not wearing_armor(hero)
    assert is_worn(ring) and is_worn(amul)

    # setnotworn clears every bit of a gone item
    setworn(hero, mail, W_ARM)
    setnotworn(hero, mail)
    assert mail.owornmask == 0


def test_worn_scan_reuses_for_monsters():
    """The same scan works for a non-hero carrier (future monster
    armour -- PLAN-ARMOR.md decision 1)."""
    w = make_world()
    mon = Monster(id="m1", name="Orc", pos=(7, 4), hp=10, max_hp=10,
                  ac=5)
    w.actors["m1"] = mon
    mail = _add(w, mon, _item(ObjType.CHAIN_MAIL))
    setworn(mon, mail, W_ARM)
    assert which_armor(w, mon, W_ARM) is mail
    assert uac(w, mon) == 5 - 5  # base minus the chain bonus


# ------------------------------------------------------------
# can_wear (C canwearobj + the accessory checks)
# ------------------------------------------------------------

def test_can_wear_table():
    w = make_world()
    hero = w.hero
    # bare hero: everything is fine
    for otyp in (ObjType.LEATHER_ARMOR, ObjType.LEATHER_CLOAK,
                 ObjType.HELMET, ObjType.SMALL_SHIELD,
                 ObjType.LEATHER_GLOVES, ObjType.LOW_BOOTS,
                 ObjType.HAWAIIAN_SHIRT, ObjType.RIN_PROTECTION,
                 ObjType.AMULET_OF_GUARDING):
        assert can_wear(w, hero, _item(otyp)) is None, otyp

    # fill every slot
    cloak = _add(w, hero, _item(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    _add(w, hero, _item(ObjType.HELMET, owornmask=W_ARMH))
    _add(w, hero, _item(ObjType.SMALL_SHIELD, owornmask=W_ARMS))
    _add(w, hero, _item(ObjType.LEATHER_GLOVES, owornmask=W_ARMG))
    _add(w, hero, _item(ObjType.LOW_BOOTS, owornmask=W_ARMF))
    _add(w, hero, _item(ObjType.HAWAIIAN_SHIRT, owornmask=W_ARMU))
    _add(w, hero, _item(ObjType.RIN_PROTECTION, owornmask=W_RINGL))
    _add(w, hero, _item(ObjType.RIN_ADORNMENT, owornmask=W_RINGR))
    _add(w, hero, _item(ObjType.AMULET_OF_GUARDING, owornmask=W_AMUL))

    assert can_wear(w, hero, _item(ObjType.LEATHER_ARMOR)) == \
        "You are already wearing some armor."
    assert can_wear(w, hero, _item(ObjType.LEATHER_CLOAK)) == \
        "You are already wearing a cloak."
    assert can_wear(w, hero, _item(ObjType.HELMET)) == \
        "You are already wearing a helmet."
    assert can_wear(w, hero, _item(ObjType.SMALL_SHIELD)) == \
        "You are already wearing a shield."
    assert can_wear(w, hero, _item(ObjType.LEATHER_GLOVES)) == \
        "You are already wearing gloves."
    assert can_wear(w, hero, _item(ObjType.LOW_BOOTS)) == \
        "You are already wearing boots."
    assert can_wear(w, hero, _item(ObjType.HAWAIIAN_SHIRT)) == \
        "You are already wearing a shirt."
    assert can_wear(w, hero, _item(ObjType.RIN_PROTECTION)) == \
        "There are no more ring-fingers to fill."
    assert can_wear(w, hero, _item(ObjType.AMULET_OF_GUARDING)) == \
        "You are already wearing an amulet."
    # non-wearable
    assert can_wear(w, hero, _item(ObjType.SHORT_SWORD)) == \
        "You cannot wear that!"
    # an item that is already worn itself
    assert can_wear(w, hero, cloak) == "You are already wearing that."


def test_can_wear_layering():
    w = make_world()
    hero = w.hero
    # a suit over a cloak
    _add(w, hero, _item(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    assert can_wear(w, hero, _item(ObjType.CHAIN_MAIL)) == \
        "You cannot wear armor over a leather cloak."
    # a shirt under a cloak / a suit
    assert can_wear(w, hero, _item(ObjType.HAWAIIAN_SHIRT)) == \
        "You can't wear that over your leather cloak."
    w2 = make_world()
    _add(w2, w2.hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    assert can_wear(w2, w2.hero, _item(ObjType.HAWAIIAN_SHIRT)) == \
        "You can't wear that over your chain mail."


def test_can_wear_shield_vs_two_handed_weapon():
    w = make_world()
    hero = w.hero
    twoh = _add(w, hero, _item(ObjType.TWO_HANDED_SWORD))
    hero.wielded = twoh.id
    assert can_wear(w, hero, _item(ObjType.SMALL_SHIELD)) == \
        "You cannot wear a shield while wielding a two-handed weapon."
    # a one-handed weapon does not block the shield
    w2 = make_world()
    one = _add(w2, w2.hero, _item(ObjType.SHORT_SWORD))
    w2.hero.wielded = one.id
    assert can_wear(w2, w2.hero, _item(ObjType.SMALL_SHIELD)) is None


# ------------------------------------------------------------
# dowear (C dowear/doputon -> accessory_or_armor_on)
# ------------------------------------------------------------

def test_dowear_suit():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL))
    ev = dowear(w, "player", mail.id, SeqRng())
    assert [e.text for e in ev] == ["You are now wearing the chain mail."]
    assert mail.owornmask == W_ARM
    assert which_armor(w, hero, W_ARM) is mail
    assert uac(w, hero) == 5


def test_dowear_rejects_without_mutating():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    cloak = _add(w, hero, _item(ObjType.LEATHER_CLOAK))
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL))
    dowear(w, "player", cloak.id, SeqRng())
    # the suit is blocked by the cloak; nothing mutates
    ev = dowear(w, "player", mail.id, SeqRng())
    assert [e.text for e in ev] == \
        ["You cannot wear armor over a leather cloak."]
    assert mail.owornmask == 0
    assert uac(w, hero) == 9
    # a floor item is not "had"
    floor = _item(ObjType.HELMET)
    floor.pos = (7, 4)
    w.items[floor.id] = floor
    ev = dowear(w, "player", floor.id, SeqRng())
    assert [e.text for e in ev] == ["You don't have that."]


def test_dowear_rings_fill_left_then_right():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    r1 = _add(w, hero, _item(ObjType.RIN_PROTECTION,
                             name="ring of protection (+1)", spe=1))
    r2 = _add(w, hero, _item(ObjType.RIN_PROTECTION,
                             name="ring of protection (+1)", spe=1))
    ev = dowear(w, "player", r1.id, SeqRng())
    assert [e.text for e in ev] == ["ring of protection (+1) (on left hand)"]
    ev = dowear(w, "player", r2.id, SeqRng())
    assert [e.text for e in ev] == ["ring of protection (+1) (on right hand)"]
    assert uac(w, hero) == 8  # 10 - 2
    # no more fingers
    r3 = _add(w, hero, _item(ObjType.RIN_PROTECTION, spe=1))
    ev = dowear(w, "player", r3.id, SeqRng())
    assert [e.text for e in ev] == \
        ["There are no more ring-fingers to fill."]
    assert uac(w, hero) == 8


def test_dowear_amulet():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    amul = _add(w, hero, _item(ObjType.AMULET_OF_GUARDING))
    ev = dowear(w, "player", amul.id, SeqRng())
    assert [e.text for e in ev] == ["amulet of guarding (being worn)"]
    assert amul.owornmask == W_AMUL
    assert uac(w, hero) == 8


# ------------------------------------------------------------
# dotakeoff (C dotakeoff/doremring -> armor_or_accessory_off)
# ------------------------------------------------------------

def test_dotakeoff_suit():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    assert uac(w, hero) == 5
    ev = dotakeoff(w, "player", mail.id, SeqRng())
    assert [e.text for e in ev] == ["You were wearing the chain mail."]
    assert mail.owornmask == 0
    assert uac(w, hero) == 10


def test_dotakeoff_layering():
    w = make_world(hero=make_hero(ac=10))
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL, owornmask=W_ARM))
    cloak = _add(w, hero, _item(ObjType.LEATHER_CLOAK, owornmask=W_ARMC))
    shirt = _add(w, hero, _item(ObjType.HAWAIIAN_SHIRT,
                                owornmask=W_ARMU))
    # the suit is under the cloak
    ev = dotakeoff(w, "player", mail.id, SeqRng())
    assert [e.text for e in ev] == \
        ["You can't take that off without taking off "
         "your leather cloak first."]
    assert mail.owornmask == W_ARM
    # the shirt is under both
    ev = dotakeoff(w, "player", shirt.id, SeqRng())
    assert [e.text for e in ev] == \
        ["You can't take that off without taking off "
         "your leather cloak and chain mail first."]
    # the cloak itself comes off
    ev = dotakeoff(w, "player", cloak.id, SeqRng())
    assert [e.text for e in ev] == ["You were wearing the leather cloak."]
    # the shirt is still under the suit
    ev = dotakeoff(w, "player", shirt.id, SeqRng())
    assert [e.text for e in ev] == \
        ["You can't take that off without taking off "
         "your chain mail first."]
    # now the suit comes off...
    assert [e.text for e in dotakeoff(w, "player", mail.id, SeqRng())] == \
        ["You were wearing the chain mail."]
    # ...and the shirt (now under nothing)
    assert [e.text for e in dotakeoff(w, "player", shirt.id, SeqRng())] == \
        ["You were wearing the Hawaiian shirt."]


def test_dotakeoff_cursed_armor_refuses():
    w = make_world()
    hero = w.hero
    cloak = _add(w, hero, _item(ObjType.LEATHER_CLOAK,
                                owornmask=W_ARMC, cursed=True))
    ev = dotakeoff(w, "player", cloak.id, SeqRng())
    assert [e.text for e in ev] == ["You can't. It is cursed."]
    assert cloak.owornmask == W_ARMC  # still on


def test_dotakeoff_not_worn_or_not_carried():
    w = make_world()
    hero = w.hero
    mail = _add(w, hero, _item(ObjType.CHAIN_MAIL))
    ev = dotakeoff(w, "player", mail.id, SeqRng())
    assert [e.text for e in ev] == ["You are not wearing that."]
    # a floor item is not "had" (even if it claims a worn mask)
    floor = _item(ObjType.HELMET, owornmask=W_ARMH)
    floor.pos = (7, 4)
    w.items[floor.id] = floor
    ev = dotakeoff(w, "player", floor.id, SeqRng())
    assert [e.text for e in ev] == ["You don't have that."]
