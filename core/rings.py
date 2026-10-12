"""Worn rings (port of the ring half of src/do_wear.c: Ring_on /
Ring_off_or_gone / adjust_attrib / learnring, plus the per-turn ring
effects of src/allmain.c + src/eat.c gethungry).

The ring's worn state is the C mechanism (Item.owornmask, core.worn);
this module owns the ring side effects and the discovery.  Two
conventions, per the architecture (ARCHITECTURE.md, "Why not the old
broadcast/actor model"):

- The side effects are CONCENTRATED IN THE CORE.  Wearing / doffing a
  ring is a *producer*: ``ring_on`` / ``ring_off`` decide what happened
  and emit events (MessageEvent + DiscoveryEvent) without touching the
  object-identity state.  The discovery mutation (Item.dknown /
  Item.known + the per-game oc_name_known / oc_encountered of
  core.o_init) is applied by the core choke point
  ``core.rules.apply_discovery`` through ``process_events`` -- exactly
  the DamageEvent / StatusEvent pattern.  This module never mutates
  ``Item.dknown`` / ``Item.known`` or the object table directly; it
  emits the intent and the core applies it.
- The ability a ring changes (RIN_GAIN_STRENGTH / RIN_GAIN_CONSTITUTION /
  RIN_ADORNMENT) is COMPUTED, NEVER CACHED: ``core.rules.current_ability``
  returns the base plus the spe of the worn ability ring, so donning /
  doffing changes the worn mask and the next query agrees (the
  ``core.worn.uac`` style).  The AC of a worn RIN_PROTECTION ring is
  likewise free -- ``core.worn.uac`` reads its spe on every query.

Included (implemented and tested, tests/test_rings.py):

- ``learnring`` -- the do_wear.c discovery logic, as a producer: it
  reads the current knowledge to pick C's branch and emits ONE
  DiscoveryEvent (mark the item seen; discover the type when the effect
  is observable; reveal the enchantment of a charged ring once both the
  type and the item are known);
- ``ring_on`` / ``ring_off`` -- the C Ring_on / Ring_off_or_gone switch,
  as a producer (the attribute "You feel ..." messages + discovery; the
  AC of RIN_PROTECTION is free via uac);
- ``tick_rings`` -- the per-turn effects, called from core.step for each
  actor after the status tick: RIN_REGENERATION (heal 1, silent) and
  RIN_TELEPORTATION (a 1/85 chance to teleport);
- ``ring_name`` -- the RING_CLASS half of objnam.c xname / doname
  ("ring of <name>" once the type is known, else "ring"; the ``+N``
  enchantment once Item.known -- the demo's "(+N)" convention).

STUBs (the ACTIVE effect is deferred to the named port; discovery still
works -- wearing the ring is still "seen" and, where C discovers it, the
type is learned):

- RIN_LEVITATION -- float_up / float_down (the water / sink / flying
  work);
- RIN_STEALTH -- the stealth system (core.props has the query; the
  "move very quietly" feedback and the monster-stealth interaction are
  deferred);
- RIN_INVISIBILITY / RIN_SEE_INVISIBLE -- the invisibility /
  see-invisible + mimic system;
- RIN_WARNING / RIN_SEARCHING -- the monster-warning / search system;
- RIN_HUNGER / RIN_SLOW_DIGESTION -- the hunger system (u.uhunger,
  eat.c gethungry) is not ported; the property is conveyed by the worn
  gear but nothing consumes it yet;
- RIN_POLYMORPH / RIN_POLYMORPH_CONTROL / RIN_AGGRAVATE_MONSTER /
  RIN_CONFLICT -- the polymorph / monster-aggravation systems;
- RIN_PROTECTION_FROM_SHAPE_CHAN -- the chameleon (restartcham) system;
- RIN_INCREASE_ACCURACY / RIN_INCREASE_DAMAGE -- the u.uhitinc /
  u.udaminc melee bonuses (the full uhitm port).

Simplifications (documented, not bugs):

- Wearing a ring marks it seen (Item.dknown) -- C sets dknown on close
  observation; we approximate "on the hand" = seen.  A ring whose effect
  is observable on wear (an attribute change with spe != 0,
  RIN_PROTECTION with spe != 0, or the levitation / stealth /
  invisibility / see-invisible rings) discovers its type on that wear;
  the passive / per-turn rings (C's ``break`` cases) are seen only.
- The ability clamp (C's extremeattr / ATTRMIN limits) is not modelled:
  a ring's spe applies unclamped (the base abilities have no hard
  minimum in the subset).
- tick_rings is hero-and-monster uniform (PLAN-ARMOR.md decision 1);
  the demo monsters carry no rings, so it is a no-op for them.
"""
from __future__ import annotations

from typing import List

from .events import DiscoveryEvent, Event, MessageEvent
from .o_init import typename
from .objects import O, OBJECTS, Prop
from .props import worn_properties
from .rules import heal, teleport_to_floor
from .types import Item, Monster, World

# C: the ring otyp range (do_wear.c is_ring; core.worn._RING_FIRST..LAST):
# RIN_ADORNMENT .. RIN_PROTECTION_FROM_SHAPE_CHAN.
RING_FIRST = O.RIN_ADORNMENT.value
RING_LAST = O.RIN_PROTECTION_FROM_SHAPE_CHAN.value


def is_ring(item) -> bool:
    """C: is_ring -- the item's fine otyp is in the ring range."""
    o = int(getattr(item, "otyp", 0))
    return RING_FIRST <= o <= RING_LAST


# The rings whose effect you "feel" put on / take off (C: the Ring_on
# cases that call learnring(obj, TRUE) -- levitation, stealth,
# invisibility, see-invisible).  Discovery works; the ACTIVE effect is a
# STUB (module docstring).
_FEEL_IT = (O.RIN_LEVITATION, O.RIN_STEALTH, O.RIN_INVISIBILITY,
            O.RIN_SEE_INVISIBLE)

# C: adjattrib's plusattr / minusattr (src/attrib.c), indexed by the
# ability -- the three the rings change.
_ABILITY_WORD = {
    "str": ("strong", "weak"),
    "con": ("tough", "fragile"),
    "cha": ("charismatic", "repulsive"),
}

# C: the do_wear.c RIN_* -> adjust_attrib(A_*, spe) cases.
_ABILITY_RING = {
    O.RIN_GAIN_STRENGTH: "str",
    O.RIN_GAIN_CONSTITUTION: "con",
    O.RIN_ADORNMENT: "cha",
}


# ------------------------------------------------------------
# Discovery (C: learnring) -- a producer
# ------------------------------------------------------------

def _type_known(world: World, otyp: int) -> bool:
    """C: objects[otyp].oc_name_known -- the type's name is known (either
    pre-known in the table or discovered this game)."""
    if world.obj_tables is not None and otyp in world.obj_tables.name_known:
        return True
    return bool(OBJECTS[otyp].name_known)


def learnring(world: World, mon: Monster, ring: Item,
              observed: bool) -> List[Event]:
    """C: learnring (src/do_wear.c) -- the ring discovery logic, as a
    producer.

    Wearing a ring means you have seen it: the item is marked seen
    (``Item.dknown``).  If the effect is ``observed`` (the ring's
    strength / constitution / charisma actually moved, RIN_PROTECTION
    with spe != 0, or one of the "feel it" rings), the type is discovered
    (``oc_name_known``) -- C's ``makeknown(ringtype)``.  Once both the
    type and the item are known, a charged ring reveals its enchantment
    (``Item.known``).

    This function READS the current knowledge (to pick C's branch) and
    EMITS a single DiscoveryEvent; it never mutates the item or the
    object table -- ``core.rules.apply_discovery`` does.
    """
    otyp = int(ring.otyp)
    row = OBJECTS[otyp]
    known_before = _type_known(world, otyp)
    # An observable effect + a seen item (on the hand) discovers the type;
    # otherwise the type stays as it was.  Either way the ring is seen.
    mark_known = known_before or observed
    reveal = bool(row.charged) and mark_known
    return [DiscoveryEvent(otyp=otyp, item_id=ring.id, mark_known=mark_known,
                           mark_encountered=True, reveal_spe=reveal)]


# ------------------------------------------------------------
# The attribute feedback (C: the adjattrib message, src/attrib.c)
# ------------------------------------------------------------

def _ability_message(mon: Monster, which: str, delta: int) -> List[Event]:
    """C: the adjattrib message (src/attrib.c): "You feel <word>!" with
    "very " for |delta| > 1.  ``delta`` is the signed change (+spe on
    donning, -spe on doffing); 0 is silent (a +0 ring moves nothing)."""
    if delta == 0:
        return []
    plus, minus = _ABILITY_WORD[which]
    word = plus if delta > 0 else minus
    prefix = "very " if abs(delta) > 1 else ""
    text = (f"You feel {prefix}{word}!" if mon.is_hero
            else f"{mon.name} feels {prefix}{word}!")
    return [MessageEvent(text)]


# ------------------------------------------------------------
# Donning / doffing (C: Ring_on / Ring_off_or_gone) -- producers
# ------------------------------------------------------------

def ring_on(world: World, mon: Monster, ring: Item) -> List[Event]:
    """C: Ring_on (src/do_wear.c) -- the side effects of putting on
    ``ring`` (the caller has already set the owornmask via
    core.worn.setworn), as a producer.

    The AC of a worn RIN_PROTECTION ring is free -- core.worn.uac reads
    the spe on every query (C's find_ac, which this subset recomputes on
    demand).  The ability a gain ring changes is computed (
    core.rules.current_ability).  The active effects of the "feel it"
    rings (levitate / stealth / invisibility / see-invisible) are STUBs
    (module docstring); their discovery is real.
    """
    otyp = int(ring.otyp)
    events: List[Event] = []
    if otyp in _ABILITY_RING:
        which = _ABILITY_RING[otyp]
        events += _ability_message(mon, which, ring.spe)
        events += learnring(world, mon, ring, observed=(ring.spe != 0))
    elif otyp == O.RIN_PROTECTION.value:
        # C: observable = (obj->spe != 0); learnring + find_ac (free --
        # uac reads the spe).  The "you feel more protected" feedback is
        # the protection system the subset defers.
        events += learnring(world, mon, ring, observed=(ring.spe != 0))
    elif otyp in _FEEL_IT:
        # STUB: the active effect (float up / move quietly / go invisible
        # / see the invisible) is deferred; discovery only.
        events += learnring(world, mon, ring, observed=True)
    else:
        # The passive / per-turn rings (resistances, free action,
        # conflict, regeneration, teleport, hunger, polymorph, ...): the
        # effect is conveyed by the worn mask (core.props) or ticked in
        # tick_rings; C's switch just ``break``s, so no discovery -- the
        # ring is seen only.
        events += learnring(world, mon, ring, observed=False)
    return events


def ring_off(world: World, mon: Monster, ring: Item) -> List[Event]:
    """C: Ring_off_or_gone (src/do_wear.c) -- the side effects of taking
    off (or losing) ``ring``.  The caller has already cleared the
    owornmask (core.worn.setworn(mon, None, mask)); the AC and ability
    values are recomputed from the (now smaller) worn set.  Mirrors
    ring_on with the attribute delta negated.
    """
    otyp = int(ring.otyp)
    events: List[Event] = []
    if otyp in _ABILITY_RING:
        which = _ABILITY_RING[otyp]
        events += _ability_message(mon, which, -ring.spe)
        events += learnring(world, mon, ring, observed=(ring.spe != 0))
    elif otyp == O.RIN_PROTECTION.value:
        # C: observable = (obj->spe != 0); learnring + find_ac (free).
        events += learnring(world, mon, ring, observed=(ring.spe != 0))
    elif otyp in _FEEL_IT:
        # C: learnring(obj, TRUE) once the effect ends (levitation /
        # invisibility); the active effect is a STUB.
        events += learnring(world, mon, ring, observed=True)
    else:
        events += learnring(world, mon, ring, observed=False)
    return events


# ------------------------------------------------------------
# Per-turn effects (C: the RIN_* cases of allmain.c + eat.c gethungry)
# ------------------------------------------------------------

def tick_rings(world: World, mon_id: str, rng) -> List[Event]:
    """Per-turn ring effects, called from core.step for each actor after
    the status tick.

    Implemented: RIN_REGENERATION (heal 1 per turn, the ring half of
    allmain.c regen_hp, silent like C's botl update) and
    RIN_TELEPORTATION (a 1/85 chance per turn to teleport, allmain.c
    ``Teleportation && !rn2(85)``).  STUBs: RIN_HUNGER (the hunger system,
    eat.c gethungry, is unported) and RIN_POLYMORPH (the polymorph system
    is unported) -- the properties are conveyed by the worn gear but
    nothing consumes them yet.

    Uniform for hero and monsters (PLAN-ARMOR.md decision 1); the demo
    monsters carry no rings, so it is a no-op for them.  Draws the rng
    only when a teleport ring is actually worn, so a ring-less world's
    draw sequence is unchanged (determinism).
    """
    mon = world.actors.get(mon_id)
    if mon is None or not mon.alive:
        return []
    props = worn_properties(mon)
    events: List[Event] = []
    # RIN_REGENERATION: heal 1 (C: the U_CAN_REGEN ring half); silent.
    if Prop.REGENERATION in props and mon.hp < mon.max_hp:
        events += heal(world, mon_id, 1, message=False)
    # RIN_TELEPORTATION: a 1/85 chance (C: !rn2(85)).
    if Prop.TELEPORT in props and rng.randint(1, 85) == 1:
        events += teleport_to_floor(world, mon_id, rng)
    # STUB: RIN_HUNGER -- the hunger system (eat.c gethungry) is unported.
    # STUB: RIN_POLYMORPH -- the polymorph system is unported.
    return events


# ------------------------------------------------------------
# Naming (C: the RING_CLASS half of objnam.c xname / doname)
# ------------------------------------------------------------

def ring_name(world: World, item: Item) -> str:
    """The RING_CLASS half of objnam.c xname / doname: "ring of <name>"
    once the type's name is known (or pre-known), else the bare "ring";
    the enchantment (``+N`` / ``-N``) is shown once ``Item.known`` (a
    charged ring whose type is known), in the demo's "(+N)" convention
    (matching the hardcoded starting "ring of protection (+1)").  The
    worn-hand suffix ("(on left hand)") is added by the don/doff
    messages (core.worn), not here.
    """
    otyp = int(item.otyp)
    state = world.obj_tables
    if state is not None and otyp in state.name_known:
        name = typename(state, otyp)
    elif OBJECTS[otyp].name_known:
        name = OBJECTS[otyp].name
    else:
        return "ring"
    if item.known and OBJECTS[otyp].charged:
        suffix = f" ({'+' if item.spe >= 0 else ''}{item.spe})"
        return f"ring of {name}{suffix}"
    return f"ring of {name}"


__all__ = [
    "RING_FIRST", "RING_LAST", "is_ring", "learnring", "ring_on",
    "ring_off", "tick_rings", "ring_name",
]
