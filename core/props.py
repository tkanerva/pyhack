"""Intrinsic / extrinsic properties: the query half of the prop-system
port (the include/prop.h hasprop() macro + the src/intr.c query side;
PLAN-ARMOR.md: the u.uprops[] work that unlocks the core.worn
``<Type>_on()`` / ``<Type>_off()`` side-effect stubs).

The C model is u.uprops[] -- one struct uprop per P_* value with an
active bitmask (UP_INHERENT / UP_EXTRINSIC / UP_ARTIFACT / UP_TEMP /
UP_BLOCKED) kept updated by set_intrinsic() / clear_intrinsic() as
gear is donned and doffed and spells and potions kick in.  pyhack
splits that in two, matching the rest of the port (computed, never
cached -- the uac() style of core.worn, PLAN-ARMOR.md decision 2):

- the *intrinsic* state lives on the monster: ``mon.intrinsics``, a
  set of core.objects.Prop (the UP_INHERENT / UP_TEMP half of C's
  uprops; artifacts have no home in the subset yet).  The set IS the
  state -- no per-source counters.
- the *extrinsic* contribution of the worn gear is derived on every
  query: the OBJECTS row oprop of each item carrying a worn mask
  (Item.owornmask) -- the same inventory scan which_armor() uses
  (core.worn).  Donning / doffing needs no property bookkeeping: the
  worn mask changes and the next query agrees.

Included (implemented and tested, tests/test_props.py):

- ``has_property(world, mon, prop)`` -- C hasprop(): the prop is in
  ``mon.intrinsics`` or is the oprop of a worn item;
- ``worn_properties(mon)`` -- the prop set the worn gear conveys
  (the extrinsic half); the scan is over the carrier's inventory,
  like which_armor() (no level state needed).

STUBs / not ported (they come with the systems that need them):

- the UP_BLOCKED bookkeeping (maskprop / unmaskprop / w_blocks) --
  the block interactions (a shield of shock resistance blocking the
  cloak's);
- the per-type ``<Type>_on()`` / ``<Type>_off()`` don/doff side
  effects (the core.worn stubs: the adjust_attrib speed changes, the
  stealth toggle, the recalc) -- the property *queries* work without
  them;
- UP_TEMP (addtimed_intrinsic: the timed prop effects of spells and
  potions) and UP_ARTIFACT (artifact intrinsics) -- needs the spell /
  potion / artifact ports.

Simplifications (documented, not bugs):

- the ``world`` argument of has_property() is accepted for the C
  hasprop()-shaped call sites but unused by the current halves (the
  scan is local to the carrier) -- the future blocked / artifact
  halves that need level state fit the signature without changes;
- a worn item with no fine identity (Item.otyp == 0, the coarse-only
  demo items) conveys no prop -- the oprop comes from the OBJECTS
  row, which needs the fine identity (the test_worn.py _item()
  pattern).
"""
from __future__ import annotations

from typing import Set

from .objects import OBJECTS, Prop
from .types import Monster, World


def worn_properties(mon: Monster) -> Set[Prop]:
    """The props the worn gear conveys (C: the u.uprops[p].extrinsic
    counters, derived from the worn masks on every query).

    The scan is over ``mon.inventory`` for the Item.owornmask bits --
    the which_armor() mechanism (core.worn): armor, accessories and
    the wielded weapon alike.  An item with a fine identity
    (Item.otyp) contributes its OBJECTS row oprop (0 = conveys
    nothing).  One carrier, one mechanism -- hero and future
    monsters alike (PLAN-ARMOR.md decision 1).
    """
    props: Set[Prop] = set()
    for it in mon.inventory:
        if not it.owornmask or not it.otyp:
            continue
        p = OBJECTS[it.otyp].oprop
        if p:
            props.add(Prop(p))
    return props


def has_property(world: World, mon: Monster, prop: Prop) -> bool:
    """C: hasprop() -- whether ``mon`` has the property ``prop``: in
    ``mon.intrinsics`` (the inherent / temp half, e.g. a potion of
    cold resistance or a species trait) or conveyed by worn gear (the
    extrinsic half, e.g. a worn ring of fire resistance).

    Carrying an item does not count -- only worn gear (the
    Item.owornmask bits), exactly C's extrinsic bookkeeping.
    """
    prop = Prop(prop)
    return prop in mon.intrinsics or prop in worn_properties(mon)


__all__ = ["has_property", "worn_properties"]
