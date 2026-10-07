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
  the select_off subset);
- erosion / armour destruction (Phase 4 of PLAN-ARMOR.md): the
  ``ERODE_*`` / ``EF_*`` / ``ER_*`` constants and ``MAX_ERODE``
  (obj.h), the material predicates (``is_flammable`` / ``is_rottable``
  / ``is_rustprone`` / ``is_crackable`` / ``is_corrodeable`` /
  ``is_damageable``, obj.h + mkobj.c), ``erosion_matters`` (objnam.c),
  ``obj_erode_type`` (do_wear.c), ``erode_obj`` (the hero-facing
  subset of trap.c: grease protection, the blessed 1/4 resistance,
  the oeroded / oeroded2 counters, destruction at MAX_ERODE with slot
  clearing), ``erode_armor`` (uhitm.c: the rust / acid / rot 5-way
  pick), ``burnarmor`` (trap.c: the fire-trap 5-way pick),
  ``disintegrate_arm`` / ``destroy_arm`` (do_wear.c: the destroy-
  armor scroll; no live call site yet -- the scroll port).  The AC /
  damage effect of erosion is free: ``arm_bonus`` caps the bonus by
  ``greatest_erosion`` and ``uac`` is computed on every query.

STUBs (raise ``NotImplementedError``; the fill-in replaces a stub, not
a call site -- the C API surface stays visible):

- the per-type ``<Type>_on()`` / ``<Type>_off()`` side effects
  (Boots / Cloak / Helmet / Shield / Shirt / Gloves / Armor / Amulet /
  Ring) -- intrinsic-property work, the prop-system port (PLAN-ARMOR.md
  decision 7); the don/doff paths call the ``_type_on`` / ``_type_off``
  hooks, which are no-ops until then;
- ``welded`` / ``stop_donning`` -- the welded-weapon and multi-turn
  don/doff machinery (no welding / occupations in the subset);
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
- Erosion messages (erode_obj) are hero-only: C's vismon / visobj
  branches (monster-carried / floor-item visibility) are dropped, and
  the monster-carried case is unreachable anyway (mon.c port,
  decision 9).  EF_PAY (costly_alteration) is accepted but ignored --
  no shops.  C's early ER_NOTHING for a FIRE_RES / ACID_RES hero and
  the rknown identification split of the oerodeproof test are skipped
  (phase 5 / identification ports).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .events import Event, MessageEvent
from .items import wielded_of
from .objects import (ARM_BOOTS, ARM_CLOAK, ARM_GLOVES, ARM_HELM,
                      ARM_SHIELD, ARM_SHIRT, ARM_SUIT, FIRST_AMULET,
                      LAST_AMULET, Material, ObjClass, OBJECTS, ObjType,
                      Prop, W_AMUL, W_ARM, W_ARMC, W_ARMF, W_ARMG,
                      W_ARMH, W_ARMOR, W_ACCESSORY, W_ARMS, W_ARMU,
                      W_WEAPONS, W_RING, W_RINGL, W_RINGR)
from .types import Monster, World
from .weapon import bimanual, greatest_erosion, is_weptool

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
# Erosion and armour destruction (Phase 4 of PLAN-ARMOR.md; the
# erode_obj / grease_protect of src/trap.c, the burnarmor of
# src/trap.c, the erode_armor of src/uhitm.c, the obj_erode_type /
# disintegrate_arm / destroy_arm of src/do_wear.c, the material
# predicates of include/obj.h + src/mkobj.c and the erosion_matters
# of src/objnam.c)
# ------------------------------------------------------------

# obj.h
ERODE_NONE = -1
ERODE_BURN = 0
ERODE_RUST = 1
ERODE_ROT = 2
ERODE_CORRODE = 3
ERODE_CRACK = 4  # crystal armor

# obj.h: the ef_flags of erode_obj()
EF_NONE = 0
EF_GREASE = 0x1   # check for a greased object
EF_DESTROY = 0x2  # potentially destroy the object
EF_VERBOSE = 0x4  # print extra messages
EF_PAY = 0x8      # it's the player's fault (costly_alteration: no shops yet)

# obj.h: the return values of erode_obj()
ER_NOTHING = 0    # nothing happened
ER_GREASED = 1    # protected by grease
ER_DAMAGED = 2    # object was damaged in some way
ER_DESTROYED = 3  # object was destroyed

# obj.h: the erosion counters saturate here
MAX_ERODE = 3

# trap.c erode_obj: the message words, indexed by ERODE_* (C: the
# action / msg / bythe arrays; the "s" endings are C's vtense()
# conjugation of every one of these verbs)
_ERODE_ACTION = ("smoulder", "rust", "rot", "corrode", "crack")
_ERODE_MSG = ("burnt", "rusted", "rotten", "corroded", "cracked")
_ERODE_BYTHE = ("heat", "oxidation", "decay", "corrosion", "impact")


def _rn2(rng, n: int) -> int:
    """C rn2(n): a roll in 0..n-1 (the house rng duck-type exposes
    randint only -- the same adapter core.mhitu uses)."""
    return rng.randint(1, n) - 1


def _row(item):
    """The table row of the item's fine identity, or None (no fine
    identity -- the item is subject to no erosion)."""
    o = _otyp(item)
    return OBJECTS[o] if o else None


# ------------------------------------------------------------
# The material predicates (C: include/obj.h macros + the
# is_flammable / is_rottable functions of src/mkobj.c)
# ------------------------------------------------------------

def is_flammable(item) -> bool:
    """C: is_flammable (src/mkobj.c): WAX..BONE (LIQUID excluded) and
    PLASTIC; the FIRE_RES property and the wand of fire are not
    flammable.  (C's candle exclusion is dead here: no candle row in
    the table, and erosion_matters() already excludes plain tools.)"""
    row = _row(item)
    if row is None or int(_otyp(item)) == O.WAN_FIRE.value:
        return False
    if row.oprop == int(Prop.FIRE_RES):
        return False
    mat = row.material
    return (mat <= Material.WOOD and mat != Material.LIQUID
            or mat == Material.PLASTIC)


def is_rottable(item) -> bool:
    """C: is_rottable (src/mkobj.c): WAX..BONE (LIQUID excluded) and
    DRAGON_HIDE."""
    row = _row(item)
    if row is None:
        return False
    mat = row.material
    return (mat <= Material.WOOD and mat != Material.LIQUID
            or mat == Material.DRAGON_HIDE)


def is_rustprone(item) -> bool:
    """C: is_rustprone (include/obj.h): material IRON (includes
    steel)."""
    row = _row(item)
    return row is not None and row.material == Material.IRON


def is_crackable(item) -> bool:
    """C: is_crackable (include/obj.h): GLASS armour (crystal plate
    mail)."""
    row = _row(item)
    return (row is not None and row.material == Material.GLASS
            and int(row.oclass) == int(ObjClass.ARMOR))


def is_corrodeable(item) -> bool:
    """C: is_corrodeable (include/obj.h): material COPPER or IRON."""
    row = _row(item)
    return row is not None and row.material in (Material.COPPER,
                                                Material.IRON)


def is_damageable(item) -> bool:
    """C: is_damageable (include/obj.h): subject to any erosion."""
    return (is_rustprone(item) or is_flammable(item) or is_rottable(item)
            or is_corrodeable(item) or is_crackable(item))


def erosion_matters(item) -> bool:
    """C: erosion_matters (src/objnam.c): WEAPON / ARMOR / BALL / CHAIN
    are erodeable; TOOL only as a weptool; everything else (potions,
    scrolls, food, ...) never."""
    row = _row(item)
    if row is None:
        return False
    ocls = int(row.oclass)
    if ocls in (int(ObjClass.WEAPON), int(ObjClass.ARMOR),
                int(ObjClass.BALL), int(ObjClass.CHAIN)):
        return True
    if ocls == int(ObjClass.TOOL):
        return is_weptool(item)
    return False


def obj_erode_type(item) -> int:
    """C: obj_erode_type (src/do_wear.c): the ERODE_* type that applies
    to the item, in C's priority order (burn, rust, crack, rot,
    corrode), or ERODE_NONE."""
    if is_flammable(item):
        return ERODE_BURN
    if is_rustprone(item):
        return ERODE_RUST
    if is_crackable(item):
        return ERODE_CRACK
    if is_rottable(item):
        return ERODE_ROT
    if is_corrodeable(item):
        return ERODE_CORRODE
    return ERODE_NONE


def _remove_destroyed(world: World, mon: Optional[Monster], item) -> None:
    """C: the erode_obj destruction branch (remove_worn_item + delobj):
    clear the worn slots, drop the item from the carrier's inventory
    and the world registry.  C's <Type>_off() side effects stay the
    no-op STUB hooks (_type_off)."""
    if mon is not None and item.owornmask:
        setworn(mon, None, item.owornmask)
    if mon is not None:
        mon.inventory = [i for i in mon.inventory if i.id != item.id]
    world.items.pop(item.id, None)


def erode_obj(world: World, item, ostr: Optional[str], type: int,
              ef_flags: int, rng=None) -> Tuple[List[Event], int]:
    """Erode one item (C: erode_obj, src/trap.c -- the hero-facing
    subset).

    ``type`` is an ERODE_* value; ``ef_flags`` an or-ed EF_* list;
    ``ostr`` an alternate name for the messages (C's xname; the call
    sites pass ``item.name``).  Returns ``(events, code)``: the
    message events and the ER_* result.  The item's ``oeroded`` /
    ``oeroded2`` counter (primary: burn / rust / crack, secondary:
    rot / corrode) goes up one; at MAX_ERODE the item takes the
    EF_DESTROY destruction -- the worn slot is cleared and the item
    leaves the world.  The AC / damage effect is free: ``uac`` and
    ``arm_bonus`` read the erosion on every query (greatest_erosion).

    Subset simplifications (documented, not bugs):

    - No monster / floor visibility: messages are emitted for the
      hero only (C's vismon / visobj branches); floor items are
      silent.  The live call sites (burnarmor / erode_armor /
      destroy-armor) only ever touch the hero, or monsters that carry
      no gear yet.
    - No ``costly_alteration`` (shops unported): EF_PAY is accepted
      and ignored.
    - No inventory resistance (the intrinsic system, phase 5): C's
      early ER_NOTHING for a FIRE_RES / ACID_RES hero is skipped.
    - No identification bookkeeping (rknown / update_inventory): the
      C ``oerodeproof && rknown`` split collapses into the plain
      oerodeproof test.
    - The blessed resistance is C's ``!rnl(4)`` at zero luck: one
      draw in 0..3, resist on 0 (one in four).
    """
    if item is None:
        return [], ER_NOTHING
    mon = world.actors.get(item.container) if item.container else None
    uvictim = mon is world.hero
    name = item.name if ostr is None else ostr
    print_ = (ef_flags & EF_VERBOSE) != 0
    events: List[Event] = []

    is_primary = True
    check_grease = (ef_flags & EF_GREASE) != 0
    crackers = False
    if type == ERODE_BURN:
        vulnerable = is_flammable(item)
        check_grease = False
    elif type == ERODE_RUST:
        vulnerable = is_rustprone(item)
    elif type == ERODE_ROT:
        vulnerable = is_rottable(item)
        check_grease = False
        is_primary = False
    elif type == ERODE_CORRODE:
        vulnerable = is_corrodeable(item)
        is_primary = False
    elif type == ERODE_CRACK:  # crystal armor
        vulnerable = is_crackable(item)
        crackers = True
    else:
        raise ValueError(f"Invalid erosion type in erode_obj: {type}")

    erosion = item.oeroded if is_primary else item.oeroded2

    if check_grease and item.greased:
        events.append(MessageEvent(
            f"Your {name} is protected by the layer of grease!"))
        # the grease wears off 1/2 of the time it protects (C: !rn2(2))
        if not _rn2(rng, 2):
            item.greased = False
            events.append(MessageEvent("The grease dissolves."))
        return events, ER_GREASED
    if not erosion_matters(item):
        return events, ER_NOTHING
    if not vulnerable or item.oerodeproof:
        if print_ and uvictim:
            events.append(MessageEvent(
                f"Your {name} is not affected by {_ERODE_BYTHE[type]}."))
        return events, ER_NOTHING
    if item.oerodeproof or (item.blessed and not _rn2(rng, 4)):
        if uvictim and (print_ or item.oerodeproof):
            events.append(MessageEvent(
                f"Somehow, your {name} is not affected by the "
                f"{_ERODE_BYTHE[type]}."))
        return events, ER_NOTHING
    if erosion < MAX_ERODE:
        adverb = (" completely" if erosion + 1 == MAX_ERODE
                  else " further" if erosion else "")
        if uvictim:
            events.append(MessageEvent(
                f"Your {name} {_ERODE_ACTION[type]}s{adverb}!"))
        if is_primary:
            item.oeroded += 1
        else:
            item.oeroded2 += 1
        return events, ER_DAMAGED
    if ef_flags & EF_DESTROY:
        if uvictim:
            if crackers:
                events.append(MessageEvent(f"Your {name} shatters!"))
            else:
                events.append(MessageEvent(
                    f"Your {name} {_ERODE_ACTION[type]}s away!"))
        _remove_destroyed(world, mon, item)
        return events, ER_DESTROYED
    if print_ and uvictim:
        events.append(MessageEvent(
            f"Your {name} looks completely {_ERODE_MSG[type]}."))
    return events, ER_NOTHING


def erode_armor(world: World, mon: Monster, hurt: int,
                rng) -> List[Event]:
    """C: erode_armor (src/uhitm.c): a rust / acid / rot attack erodes
    one of ``mon``'s worn armour pieces.  C's loop keeps picking a
    random slot (helm / cloak-suit-shirt / shield / gloves / boots)
    until an attempt affects something; the torso tier exits after a
    single attempt, exactly as in C.  A carrier with no worn armour
    gets [] (C's callers guarantee worn gear; the guard keeps the
    loop honest for the subset's bare monsters).  ``hurt`` is the
    ERODE_* type of the attack (ERODE_RUST / ERODE_CORRODE /
    ERODE_ROT)."""
    if not wearing_armor(mon):
        return []
    events: List[Event] = []
    while True:
        case = _rn2(rng, 5)
        if case == 1:  # cloak, else suit, else shirt: one attempt, done
            target = (which_armor(world, mon, W_ARMC)
                      or which_armor(world, mon, W_ARM)
                      or which_armor(world, mon, W_ARMU))
            if target is not None:
                events += erode_obj(world, target, target.name, hurt,
                                    EF_GREASE | EF_VERBOSE, rng)[0]
            return events
        mask = {0: W_ARMH, 2: W_ARMS, 3: W_ARMG, 4: W_ARMF}[case]
        target = which_armor(world, mon, mask)
        if target is not None:
            ev, code = erode_obj(world, target, target.name, hurt,
                                 EF_GREASE, rng)
            events += ev
            if code != ER_NOTHING:
                return events
        # C: continue the loop while the attempt affected nothing


def burnarmor(world: World, mon: Monster, rng) -> List[Event]:
    """C: burnarmor (src/trap.c): hit by fire (fire trap, lava,
    explosion) -- one random worn piece takes burn damage (C's
    burn_dmg macro: ERODE_BURN + EF_GREASE).  The loop exits when
    something is affected; the torso tier (cloak / suit / shirt)
    always exits after its attempt, as in C.  C's wet-towel drying
    prefix is omitted (no towels in the demo; the mechanics exist in
    weapon.dry_a_towel), and C's torso-hit boolean has no consumer in
    the subset.  Returns the message events.
    """
    events: List[Event] = []
    while True:
        case = _rn2(rng, 5)
        if case == 1:  # cloak, else suit, else shirt
            target = (which_armor(world, mon, W_ARMC)
                      or which_armor(world, mon, W_ARM)
                      or which_armor(world, mon, W_ARMU))
            if target is not None:
                events, _ = erode_obj(world, target, target.name,
                                      ERODE_BURN, EF_GREASE, rng)
            return events
        mask = (W_ARMH if case == 0 else W_ARMS if case == 2
                else W_ARMG if case == 3 else W_ARMF)
        target = which_armor(world, mon, mask)
        if target is not None:
            ev, code = erode_obj(world, target, target.name,
                                 ERODE_BURN, EF_GREASE, rng)
            if code != ER_NOTHING:
                return ev
        # C: keep rolling while the attempt affected nothing


def disintegrate_arm(world: World, mon_id: str, rng) -> List[Event]:
    """C: disintegrate_arm (src/do_wear.c): the (blessed) destroy-armor
    scroll and the black dragon's breath disintegrate the first armor
    piece in C's order -- cloak, suit, shirt, helmet, gloves, boots,
    shield -- that fails the resistance check.

    C's maybe_destroy_armor targets the scroll's chosen piece (atmp)
    and gates on obj_resists(armor, 0, 90): for ordinary (non-)
    artifact gear the check never resists (an artifact would resist
    90%), so with no artifacts in the subset the first worn piece in
    order goes.  The item is unworn and removed (C
    wornarm_destroyed: the <Type>_off() hooks stay the no-op STUBs;
    the glove-loss selftouch has no consumer -- no weapon welding).
    Returns the events; an empty list is C's "could not destroy
    anything" 0.  No live call site yet: the destroy-armor scroll
    (read.c seffect_destroy_armor) lands with the scroll port.
    """
    mon = world.actors.get(mon_id)
    if mon is None:
        return []
    # C order + the C messages (the full item name in place of C's
    # simple-name words -- the don/doff simplification)
    for mask, verb in (
            (W_ARMC, "crumbles and turns to dust!"),
            (W_ARM, "turns to dust and falls to the floor!"),
            (W_ARMU, "crumbles into tiny threads and falls apart!"),
            (W_ARMH, "turns to dust and is blown away!"),
            (W_ARMG, "vanish!"),
            (W_ARMF, "disintegrate!"),
            (W_ARMS, "crumbles away!")):
        it = which_armor(world, mon, mask)
        if it is None:
            continue
        # maybe_destroy_armor: no artifact in the subset, so the
        # resistance check (obj_resists(armor, 0, 90)) never fires
        events = [MessageEvent(f"Your {it.name} {verb}")]
        _remove_destroyed(world, mon, it)
        return events
    return []


def destroy_arm(world: World, mon_id: str, rng) -> List[Event]:
    """C: destroy_arm (src/do_wear.c): the (cursed) destroy-armor
    scroll erodes 1..4 random hits on the worn armour: each hit picks
    a random worn piece (C gathers W_ARM, W_ARMC, W_ARMH, W_ARMS,
    W_ARMG, W_ARMF, W_ARMU) and erodes it with its own
    obj_erode_type (EF_PAY | EF_DESTROY), stopping when a piece is
    destroyed.  Non-erodeable pieces (erosion_matters / is_damageable
    / oerodeproof / ERODE_NONE) take no hit.  EF_PAY is accepted but
    ignored (no shops).  Returns the events; an empty list is C's 0.
    No live call site yet (the scroll port, read.c).
    """
    mon = world.actors.get(mon_id)
    if mon is None:
        return []
    armors = [a for a in (which_armor(world, mon, mask)
                          for mask in (W_ARM, W_ARMC, W_ARMH, W_ARMS,
                                       W_ARMG, W_ARMF, W_ARMU))
              if a is not None]
    if not armors:
        return []
    hits = _rn2(rng, 4) + 1
    events: List[Event] = []
    for _ in range(hits):
        otmp = armors[_rn2(rng, len(armors))]
        if (erosion_matters(otmp) and is_damageable(otmp)
                and not otmp.oerodeproof):
            erosion = obj_erode_type(otmp)
            if erosion != ERODE_NONE:
                ev, r = erode_obj(world, otmp, otmp.name, erosion,
                                  EF_PAY | EF_DESTROY, rng)
                events += ev
                if r == ER_DESTROYED:
                    break
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
