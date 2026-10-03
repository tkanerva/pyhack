"""Worn equipment: the hero's armor slots and the AC computation
(port of src/do_wear.c's AC half + the slot half of src/worn.c /
src/invent.c + the armor macros of include/obj.h + include/prop.h).

The worn state is the C mechanism: every item carries an
``Item.owornmask`` (prop.h bitmask), and the slot occupant is found by
scanning the carrier's inventory for the mask --
``which_armor()``/``setworn()`` over the list, exactly C's
``which_armor()``/``setworn()`` over ``minvent``/``worn[]``.  One
mechanism for hero and (future) monsters; there are no per-slot
fields on the monster.

``Monster.ac`` is the BASE (body) armor class (C: ``mons[u.umonnum].ac``);
the effective AC is computed, never cached: ``uac()`` is C's
``find_ac()`` computation (base - the ARM_BONUS of the seven armor
slots - the spe of worn rings of protection - 2 for a worn amulet of
guarding - intrinsic/spell Protection), clamped to +/-AC_MAX (99,
you.h).  Gear changes and the next query agree by construction.

Included (implemented and tested):

- the obj.h armor predicates (is_armor / is_suit / is_cloak / is_shirt /
  is_helmet / is_shield / is_gloves / is_boots) as otyp-range checks
  over the fine identity (core.objects.OBJECTS keeps the C numbering);
- ``armor_slot`` -- the W_* bit of an armor item from its oc_armcat
  (C: the wornmask() macro, armor branch), 0 for non-armor;
- ``setworn`` / ``setnotworn`` (C worn.c, over the inventory scan),
  ``which_armor`` (C worn.c), ``wearing_armor`` / ``is_worn``
  (C invent.c);
- ``arm_bonus`` (C hack.h ARM_BONUS), ``ac_bonus`` (the find_ac gear
  sum), ``uac`` (C find_ac minus the AC_VALUE randomisation),
  ``ac_value`` (C hack.h AC_VALUE -- the single auditable draw for
  negative AC);
- donning / doffing (Phase 2 of PLAN-ARMOR.md): ``can_wear`` (C
  canwearobj + the accessory checks of accessory_or_armor_on),
  ``dowear`` (C dowear/doputon -> accessory_or_armor_on),
  ``dotakeoff`` (C dotakeoff/doremring -> armor_or_accessory_off +
  the select_off subset).

STUBs (raise ``NotImplementedError``; the fill-in replaces a stub, not
a call site -- the C API surface stays visible):

- the per-type ``<Type>_on()`` / ``<Type>_off()`` side effects
  (Boots / Cloak / Helmet / Shield / Shirt / Gloves / Armor / Amulet /
  Ring) -- intrinsic-property work, the prop-system port (PLAN-ARMOR.md
  decision 7); the don/doff paths call the ``_type_on`` / ``_type_off``
  hooks, which are no-ops until then;
- ``welded`` / ``stop_donning`` -- the welded-weapon and multi-turn
  don/doff machinery (no welding / occupations in the subset);
- ``disintegrate_arm`` / ``destroy_arm`` -- the destroy-armor scroll
  (Phase 4 of PLAN-ARMOR.md);
- ``inaccessible_equipment`` / ``count_worn_stuff`` / ``doddoremarm`` --
  the 'A' take-off-all command (PLAN-ARMOR.md phase 5).

Simplifications (documented, not bugs):

- Donning / doffing consumes one turn each (PLAN-ARMOR.md decision 4);
  C's ``oc_delay`` occupations (nomul / set_occupation) are not
  modelled.  Failed commands also consume a turn (consistent with the
  quaff / cast behaviour).
- Ring hand selection: the left hand is filled first, then the right
  (C asks "Which ring-finger, Right or Left?" when both are free; the
  console UI has no prompt machinery).
- Refusal / layering messages quote the WORN item's full name
  ("...over your leather cloak.") where C quotes a simple-name word
  (cloak_simple_name / suit_simple_name).
- The polyform checks of canwearobj (verysmall / nohands / horns /
  hooves / foot-traps), the Glib (slippery fingers) checks and the
  two-weapon checks are dead without polymorph / intrinsics /
  twoweap -- dropped, not faked.  The gloves-vs-welded-weapon and
  boot-trap checks of select_off are dead for the same reasons.
- The ``cursed()`` block applies to armor only (C calls cursed() from
  armoroff(); cursed rings are removable in C -- no welded weapons in
  the subset).
- The ``u.uprops[]`` extrinsic / blocked / artifact bookkeeping of C
  setworn() is not modelled (no intrinsic system yet); the AC effect
  of gear is covered by the computed uac().
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .items import wielded_of
from .objects import (ARM_BOOTS, ARM_CLOAK, ARM_GLOVES, ARM_HELM,
                      ARM_SHIELD, ARM_SHIRT, ARM_SUIT, FIRST_AMULET,
                      LAST_AMULET, OBJECTS, ObjType, W_AMUL, W_ARM,
                      W_ARMC, W_ARMF, W_ARMG, W_ARMH, W_ARMOR,
                      W_ACCESSORY, W_ARMS, W_ARMU, W_WEAPONS, W_RING,
                      W_RINGL, W_RINGR)
from .types import Monster, World
from .weapon import bimanual, greatest_erosion

O = ObjType

# you.h
AC_MAX = 99  # abs(u.uac) <= 99; likewise for monster AC

# C: the ring / amulet otyp ranges (obj.h is_ring / is_amulet)
_RING_FIRST = O.RIN_ADORNMENT.value
_RING_LAST = O.RIN_PROTECTION_FROM_SHAPE_CHAN.value
_AMULET_FIRST = FIRST_AMULET
_AMULET_LAST = LAST_AMULET


# ------------------------------------------------------------
# The armor predicates (C: include/obj.h macros)
# ------------------------------------------------------------

def _otyp(item) -> int:
    """The fine object type (C: otmp->otyp); 0 = not fine."""
    return int(getattr(item, "otyp", 0))


def _range(item, first: ObjType, last: ObjType) -> bool:
    o = _otyp(item)
    return int(first.value) <= o <= int(last.value)


def is_armor(item) -> bool:
    """C: is_armor -- the otyp range ELVEN_LEATHER_HELM ..
    LEVITATION_BOOTS."""
    return _range(item, O.ELVEN_LEATHER_HELM, O.LEVITATION_BOOTS)


def is_suit(item) -> bool:
    """C: is_suit -- the otyp range GRAY_DRAGON_SCALE_MAIL ..
    LEATHER_JACKET (the armor category ARM_SUIT)."""
    return _range(item, O.GRAY_DRAGON_SCALE_MAIL, O.LEATHER_JACKET)


def is_shirt(item) -> bool:
    """C: is_shirt -- the otyp range HAWAIIAN_SHIRT .. T_SHIRT."""
    return _range(item, O.HAWAIIAN_SHIRT, O.T_SHIRT)


def is_cloak(item) -> bool:
    """C: is_cloak -- the otyp range MUMMY_WRAPPING ..
    CLOAK_OF_DISPLACEMENT."""
    return _range(item, O.MUMMY_WRAPPING, O.CLOAK_OF_DISPLACEMENT)


def is_helmet(item) -> bool:
    """C: is_helmet -- the otyp range ELVEN_LEATHER_HELM ..
    HELM_OF_TELEPATHY."""
    return _range(item, O.ELVEN_LEATHER_HELM, O.HELM_OF_TELEPATHY)


def is_shield(item) -> bool:
    """C: is_shield -- the otyp range SMALL_SHIELD ..
    SHIELD_OF_REFLECTION."""
    return _range(item, O.SMALL_SHIELD, O.SHIELD_OF_REFLECTION)


def is_gloves(item) -> bool:
    """C: is_gloves -- the otyp range LEATHER_GLOVES ..
    GAUNTLETS_OF_DEXTERITY."""
    return _range(item, O.LEATHER_GLOVES, O.GAUNTLETS_OF_DEXTERITY)


def is_boots(item) -> bool:
    """C: is_boots -- the otyp range LOW_BOOTS .. LEVITATION_BOOTS."""
    return _range(item, O.LOW_BOOTS, O.LEVITATION_BOOTS)


# ------------------------------------------------------------
# The slot machinery (C: src/worn.c over the inventory)
# ------------------------------------------------------------

# C: the wornmask() macro, armor branch (oc_armcat -> W_* bit)
_ARMCAT_TO_MASK = {
    ARM_SUIT: W_ARM,
    ARM_CLOAK: W_ARMC,
    ARM_HELM: W_ARMH,
    ARM_SHIRT: W_ARMU,
    ARM_BOOTS: W_ARMF,
    ARM_GLOVES: W_ARMG,
    ARM_SHIELD: W_ARMS,
}


def armor_slot(item) -> int:
    """The W_* slot bit of an armor item from its oc_armcat
    (C: the wornmask() macro, armor branch); 0 for non-armor and for
    items without a fine identity."""
    o = _otyp(item)
    if not o or not is_armor(item):
        return 0
    return _ARMCAT_TO_MASK.get(int(OBJECTS[o].subtyp), 0)


def setworn(mon: Monster, item, mask: int) -> None:
    """C: setworn (src/worn.c), over the inventory scan.

    Clears the slot bits of ``mask`` on whatever item in
    ``mon.inventory`` currently wears them (the displaced item), then
    sets them on ``item`` (pass ``None`` to empty the slot).  The
    ``u.uprops[]`` extrinsic / blocked / artifact side effects of C
    setworn() are STUBs (the prop-system port).
    """
    if not mask:
        return
    for it in mon.inventory:
        if it.owornmask & mask:
            it.owornmask &= ~mask
    if item is not None:
        item.owornmask |= mask
    # STUB (prop-system port): the u.uprops[p].extrinsic / .blocked
    # updates, w_blocks(), set_artifact_intrinsic(), cancel_doff(),
    # update_inventory(), recalc_telepat_range() of C setworn().


def setnotworn(mon: Monster, item) -> None:
    """C: setnotworn (src/worn.c): clear every worn bit of ``item``
    (called e.g. when a worn item is destroyed)."""
    if item is None:
        return
    if item.owornmask:
        setworn(mon, None, item.owornmask)


def which_armor(world: World, mon: Monster, mask: int):
    """The item ``mon`` wears in the slot(s) ``mask`` selects (C:
    which_armor, src/worn.c -- the ``minvent`` scan applied uniformly
    to hero and monsters; PLAN-ARMOR.md decision 1)."""
    for it in mon.inventory:
        if it.owornmask & mask:
            return it
    return None


def wearing_armor(mon: Monster) -> bool:
    """C: wearing_armor (src/invent.c) -- any of the seven armor
    slots is occupied."""
    return which_armor(None, mon, W_ARMOR) is not None


def is_worn(item) -> bool:
    """C: is_worn (src/invent.c) -- the item occupies a worn slot
    (armor, accessory or weapon; W_SADDLE has no home in the
    subset)."""
    return bool(item.owornmask & (W_ARMOR | W_ACCESSORY | W_WEAPONS))


# ------------------------------------------------------------
# The AC computation (C: src/do_wear.c find_ac + hack.h ARM_BONUS /
# AC_VALUE)
# ------------------------------------------------------------

def arm_bonus(item) -> int:
    """C: ARM_BONUS (include/hack.h): a_ac + spe -
    min(greatest_erosion, a_ac).  0 for non-armor (C applies the macro
    to worn armor only; this guard keeps the sum well-defined)."""
    o = _otyp(item)
    if not o or not is_armor(item):
        return 0
    a = int(OBJECTS[o].oc1)  # a_ac
    return a + int(getattr(item, "spe", 0)) \
        - min(greatest_erosion(item), a)


def ac_bonus(world: World, mon: Monster) -> int:
    """The AC bonus of everything ``mon`` wears (the gear half of C
    find_ac): the ARM_BONUS of the seven armor slots, plus the spe of
    each worn RIN_PROTECTION ring, plus 2 for a worn amulet of
    guarding."""
    total = 0
    for mask in (W_ARM, W_ARMC, W_ARMH, W_ARMF, W_ARMS, W_ARMG, W_ARMU):
        it = which_armor(world, mon, mask)
        if it is not None:
            total += arm_bonus(it)
    for mask in (W_RINGL, W_RINGR):
        it = which_armor(world, mon, mask)
        if it is not None and _otyp(it) == O.RIN_PROTECTION.value:
            total += int(getattr(it, "spe", 0))
    amul = which_armor(world, mon, W_AMUL)
    if amul is not None and _otyp(amul) == O.AMULET_OF_GUARDING.value:
        total += 2  # fixed amount; main benefit is to MC (C comment)
    return total


def uac(world: World, mon: Monster, ublessed: int = 0,
        uspellprot: int = 0) -> int:
    """The effective armor class (C: find_ac, src/do_wear.c): the base
    ``mon.ac`` minus the gear bonus of ``ac_bonus``(), minus
    ``ublessed`` (intrinsic Protection) and ``uspellprot`` (SPE_
    PROTECTION), clamped to +/-AC_MAX.

    Computed on every call and never cached (PLAN-ARMOR.md decision
    2): gear changes and the next query agree by construction.
    ``ublessed`` / ``uspellprot`` are 0 until the priest / spell
    ports land (decision 7).
    """
    ac = mon.ac - ac_bonus(world, mon) - ublessed - uspellprot
    if abs(ac) > AC_MAX:
        ac = AC_MAX if ac > 0 else -AC_MAX
    return ac


def ac_value(ac: int, rng) -> int:
    """C: AC_VALUE (include/hack.h): a negative armor class is
    randomly weakened to prevent invulnerability (``-rnd(-AC)``).

    No rng draw when ``ac >= 0`` -- the determinism note of
    PLAN-ARMOR.md: this is the single auditable draw of the defence
    system, made only when the hero has pushed its AC negative.
    """
    if ac >= 0:
        return ac
    return -rng.randint(1, -ac)


# ------------------------------------------------------------
# Donning / doffing (Phase 2 of PLAN-ARMOR.md; the don/doff half of
# do_wear.c)
# ------------------------------------------------------------

def _carried(mon: Monster, item_id: str) -> bool:
    return any(it.id == item_id for it in mon.inventory)


def _wear_mask(world: World, mon: Monster, item) -> int:
    """The slot bit ``item`` will take (the armor branch of C's
    wornmask(); rings fill the left hand first -- the documented
    simplification; the amulet has its own bit)."""
    mask = armor_slot(item)
    if mask:
        return mask
    o = _otyp(item)
    if _RING_FIRST <= o <= _RING_LAST:
        if which_armor(world, mon, W_RINGL) is None:
            return W_RINGL
        return W_RINGR
    if _AMULET_FIRST <= o <= _AMULET_LAST:
        return W_AMUL
    return 0


# C: the already_wearing() slot words (do_wear.c)
_SLOT_NAME = {
    W_ARM: "some armor",
    W_ARMC: "a cloak",
    W_ARMH: "a helmet",
    W_ARMS: "a shield",
    W_ARMG: "gloves",
    W_ARMF: "boots",
    W_ARMU: "a shirt",
}


def can_wear(world: World, mon: Monster, item) -> Optional[str]:
    """Whether ``mon`` may wear ``item`` (C: canwearobj + the
    accessory checks of accessory_or_armor_on).  Returns the refusal
    message, or None if the item may be worn.

    The polyform checks (verysmall / nohands / horns / hooves /
    foot-traps), the welded / Glib checks and the two-weapon checks of
    C are dead in the subset (module docstring).
    """
    if item.owornmask & (W_ARMOR | W_ACCESSORY):
        return "You are already wearing that."

    mask = armor_slot(item)
    if mask:
        if which_armor(world, mon, mask) is not None:
            return f"You are already wearing {_SLOT_NAME[mask]}."
        if mask == W_ARMS:
            wep = wielded_of(world, mon.id)
            if wep is not None and bimanual(wep):
                return ("You cannot wear a shield while wielding a "
                        "two-handed weapon.")
        if mask == W_ARM:
            cloak = which_armor(world, mon, W_ARMC)
            if cloak is not None:
                return f"You cannot wear armor over a {cloak.name}."
        if mask == W_ARMU:
            cloak = which_armor(world, mon, W_ARMC)
            if cloak is not None:
                return (f"You can't wear that over your {cloak.name}.")
            suit = which_armor(world, mon, W_ARM)
            if suit is not None:
                return f"You can't wear that over your {suit.name}."
        return None

    o = _otyp(item)
    if _RING_FIRST <= o <= _RING_LAST:
        if (which_armor(world, mon, W_RINGL) is not None
                and which_armor(world, mon, W_RINGR) is not None):
            return "There are no more ring-fingers to fill."
        return None
    if _AMULET_FIRST <= o <= _AMULET_LAST:
        if which_armor(world, mon, W_AMUL) is not None:
            return "You are already wearing an amulet."
        return None
    return "You cannot wear that!"


def _on_msg(item, mask: int) -> str:
    """C: on_msg / the prinv suffix of accessory_or_armor_on."""
    if mask & W_RING:
        hand = "left" if (mask & W_RINGL) else "right"
        return f"{item.name} (on {hand} hand)"
    if mask == W_AMUL:
        return f"{item.name} (being worn)"
    return f"You are now wearing the {item.name}."


def _off_msg(item, mask: int) -> str:
    """C: off_msg (the ring hand suffix comes from C's doname)."""
    if mask & W_RING:
        hand = "left" if (mask & W_RINGL) else "right"
        return f"You were wearing the {item.name} (on {hand} hand)."
    return f"You were wearing the {item.name}."


def _type_on(world: World, mon: Monster, item, mask: int) -> List[Event]:
    """The per-type ``<Type>_on()`` side-effect hook (C: the switch in
    accessory_or_armor_on after setworn()).  STUB: the individual
    ``<Type>_on()`` functions below raise NotImplementedError until the
    prop-system port; the hook returns [] in the meantime (no
    intrinsics in the subset)."""
    return []


def _type_off(world: World, mon: Monster, item, mask: int) -> List[Event]:
    """The per-type ``<Type>_off()`` side-effect hook (C: the
    armoroff / Ring_off / Amulet_off switch after the slot is
    cleared).  STUB as in _type_on()."""
    return []


def dowear(world: World, mon_id: str, item_id: str, rng) -> List[Event]:
    """Put on an armor, ring or amulet (C: dowear / doputon ->
    accessory_or_armor_on, the one-turn subset).

    The item must be in the carrier's inventory; ``can_wear`` gates it;
    the slot is set by ``setworn``; the message is C's on_msg (the
    prinv-style lines for rings and the amulet).
    """
    mon = world.actors.get(mon_id)
    item = world.items.get(item_id)
    if mon is None or item is None or not _carried(mon, item_id):
        return [MessageEvent("You don't have that.")]
    err = can_wear(world, mon, item)
    if err is not None:
        return [MessageEvent(err)]
    mask = _wear_mask(world, mon, item)
    setworn(mon, item, mask)
    events = [MessageEvent(_on_msg(item, mask))]
    events += _type_on(world, mon, item, mask)
    return events


def dotakeoff(world: World, mon_id: str, item_id: str, rng) -> List[Event]:
    """Take off an armor, ring or amulet (C: dotakeoff / doremring ->
    armor_or_accessory_off + the select_off subset, the one-turn
    version).

    Layering: a suit under a cloak and a shirt under a suit or cloak
    cannot come off first (C: the suit / shirt branch of
    armor_or_accessory_off).  Cursed armor refuses (C: the cursed()
    check in armoroff).  The gloves-vs-welded-weapon and boot-trap
    checks of select_off are dead in the subset.
    """
    mon = world.actors.get(mon_id)
    item = world.items.get(item_id)
    if mon is None or item is None or not _carried(mon, item_id):
        return [MessageEvent("You don't have that.")]
    if not (item.owornmask & (W_ARMOR | W_ACCESSORY)):
        return [MessageEvent("You are not wearing that.")]
    if item.owornmask & W_ARM:
        cloak = which_armor(world, mon, W_ARMC)
        if cloak is not None:
            return [MessageEvent(f"You can't take that off without "
                                 f"taking off your {cloak.name} first.")]
    if item.owornmask & W_ARMU:
        cloak = which_armor(world, mon, W_ARMC)
        suit = which_armor(world, mon, W_ARM)
        if cloak is not None or suit is not None:
            if cloak is not None and suit is not None:
                why = f"your {cloak.name} and {suit.name}"
            elif cloak is not None:
                why = f"your {cloak.name}"
            else:
                why = f"your {suit.name}"
            return [MessageEvent(f"You can't take that off without "
                                 f"taking off {why} first.")]
    if (item.owornmask & W_ARMOR) and item.cursed:
        return [MessageEvent("You can't. It is cursed.")]
    mask = item.owornmask & (W_ARMOR | W_ACCESSORY)
    off = _off_msg(item, mask)
    setworn(mon, None, mask)
    events = [MessageEvent(off)]
    events += _type_off(world, mon, item, mask)
    return events


# ------------------------------------------------------------
# STUBs -- the C API surface, filled by the named ports
# ------------------------------------------------------------

def Boots_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Boots_on): the footwear side effects (speed /
    levitation / stealth / water walking).  Needs the prop-system
    port."""
    raise NotImplementedError("Boots_on: the property system is not ported yet")


def Boots_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Boots_off): the footwear side effects."""
    raise NotImplementedError("Boots_off: the property system is not ported yet")


def Cloak_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Cloak_on): the cloak side effects (stealth,
    invisibility, displacement, protection)."""
    raise NotImplementedError("Cloak_on: the property system is not ported yet")


def Cloak_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Cloak_off): the cloak side effects."""
    raise NotImplementedError("Cloak_off: the property system is not ported yet")


def Helmet_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Helmet_on): the helmet side effects (telepathy,
    warning, clairvoyance)."""
    raise NotImplementedError("Helmet_on: the property system is not ported yet")


def Helmet_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Helmet_off): the helmet side effects."""
    raise NotImplementedError("Helmet_off: the property system is not ported yet")


def Shield_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Shield_on): the shield side effects (drain / shock
    resistance)."""
    raise NotImplementedError("Shield_on: the property system is not ported yet")


def Shield_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Shield_off): the shield side effects."""
    raise NotImplementedError("Shield_off: the property system is not ported yet")


def Shirt_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Shirt_on): the shirt side effects (none in the C
    table today, but the hook exists)."""
    raise NotImplementedError("Shirt_on: the property system is not ported yet")


def Shirt_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Shirt_off): the shirt side effects."""
    raise NotImplementedError("Shirt_off: the property system is not ported yet")


def Gloves_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Gloves_on): the gauntlet side effects (fumbling,
    power, dexterity)."""
    raise NotImplementedError("Gloves_on: the property system is not ported yet")


def Gloves_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Gloves_off): the gauntlet side effects."""
    raise NotImplementedError("Gloves_off: the property system is not ported yet")


def Armor_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Armor_on): the suit side effects (dragon-scale
    resistances / antimagic / reflection)."""
    raise NotImplementedError("Armor_on: the property system is not ported yet")


def Armor_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Armor_off): the suit side effects."""
    raise NotImplementedError("Armor_off: the property system is not ported yet")


def Amulet_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Amulet_on): the amulet side effects (ESP, life
    saving, ...)."""
    raise NotImplementedError("Amulet_on: the property system is not ported yet")


def Amulet_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Amulet_off): the amulet side effects."""
    raise NotImplementedError("Amulet_off: the property system is not ported yet")


def Ring_on(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Ring_on): the ring side effects (the adjust_attrib /
    learnring / toggle_stealth switch)."""
    raise NotImplementedError("Ring_on: the property system is not ported yet")


def Ring_off(world: World, mon: Monster) -> List[Event]:
    """STUB (C: Ring_off): the ring side effects."""
    raise NotImplementedError("Ring_off: the property system is not ported yet")


def welded(item) -> bool:
    """STUB (C: welded): whether a weapon is welded to the hero's
    hand (cursed + the weapon-weapon rules).  Needs the
    remove-curse / welding machinery; the demo has no welding."""
    raise NotImplementedError("welded: the welding machinery is not ported yet")


def stop_donning(world: World, mon: Monster) -> List[Event]:
    """STUB (C: stop_donning): abort a multi-turn don/doff.  Needs the
    occupation / nomul machinery (PLAN-ARMOR.md phase 5)."""
    raise NotImplementedError("stop_donning: the occupation system is not ported yet")


def disintegrate_arm(world: World, mon_id: str, rng) -> List[Event]:
    """STUB (C: disintegrate_arm, do_wear.c): the destroy-armor
    scroll disintegrates all worn armor.  PLAN-ARMOR.md Phase 4."""
    raise NotImplementedError("disintegrate_arm: Phase 4 of PLAN-ARMOR.md")


def destroy_arm(world: World, mon_id: str, item_id: str, rng) -> List[Event]:
    """STUB (C: destroy_arm, do_wear.c): destroy one worn piece of
    armor.  PLAN-ARMOR.md Phase 4."""
    raise NotImplementedError("destroy_arm: Phase 4 of PLAN-ARMOR.md")


def inaccessible_equipment(mon: Monster) -> bool:
    """STUB (C: inaccessible_equipment): whether the hero's equipment
    is inaccessible (swallowed / in a container the hero cannot
    reach).  Needs the swallow machinery."""
    raise NotImplementedError(
        "inaccessible_equipment: the swallow machinery is not ported yet")


def count_worn_stuff(mon: Monster, verbose: bool = False) -> int:
    """STUB (C: count_worn_stuff, do_wear.c): count the worn pieces
    for the 'A' take-off-all command.  PLAN-ARMOR.md phase 5."""
    raise NotImplementedError("count_worn_stuff: the 'A' command is not ported yet")


def doddoremarm(world: World, mon_id: str, rng) -> List[Event]:
    """STUB (C: doddoremarm, do_wear.c): the 'A' command -- take off
    all armor and accessories in takeoff_order.  PLAN-ARMOR.md
    phase 5."""
    raise NotImplementedError("doddoremarm: the 'A' command is not ported yet")
