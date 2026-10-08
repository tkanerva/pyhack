"""Wand zaps and the shared zap engine (C: zap.c).

In C NetHack, wands and spells share their effect code through one
intermediate object: spelleffects() (src/spell.c) builds a temporary
"pseudo" spellbook object (mksobj(spellid), quan 20 so useup() leaves
it alone) and hands it to the SAME weffects() (src/zap.c) that dozap()
uses for wands; weffects() then dispatches on the object type -- bhitm()'
switch (WAN_STRIKING falls through into SPE_FORCE_BOLT: the wand of
striking and the force bolt spell run ONE code path) and the
dobuzz()/zhitm() damage switch for the ray wands and the zap spells,
with the beam traversal in bhit() / dobuzz().

pyhack keeps that structure without the pseudo-object trick:

- `ZAP_EFFECTS` -- the registry keyed by `ZapEffect` (C's zno / ZT_*
  damage types + the bhitm otyp cases).  Each entry is an effect
  function `effect(world, caster, target, spec, rng) -> [Event]` --
  the (caster, power_source) pair the design calls for, with the beam
  direction already resolved into `target` by the engine.  Wands and
  spells call the SAME functions: `use_wand()` and `cast_spell()`
  (core.spells) build a `ZapSpec` and hand it to `zap()` (the beam
  engine, C: the dobuzz()/bhit() traversal -- the C `7 + rnd(7)` beam
  range, the first-monster stop, the wall / astray lines), or invoke
  the registry directly for the self-targeted spell effects (C: the
  atme / zapyourself paths).
- the caster-side differences STAY in the caster: the wand's power
  (C weffects: `ubuzz(BZ_U_WAND(...), 6)` -- six d6 dice) and the
  consume-a-charge-even-when-you-miss behaviour in `use_wand()`; the
  spell's power (C: `u.ulevel / 2 + 1` dice), its spell damage bonus
  (zap.c spell_damage_bonus, the INT/level bonus) and its failure roll
  (spelleffects_check: `rnd(100) > percent_success`) in
  `cast_spell()`.  The spec carries only the VALUES the caster
  computed (power, damage_bonus) -- never the decision.

The ported subset (the ZAP_EFFECTS table); the remaining C zaps
(opening, locking, probing, slow, speed, make invisible, light, ...)
land with the machinery they need (doors, monster speed,
invisibility, ...).

Simplifications (documented, not bugs):

- no AC-based zap_hit() miss (C 5.0's dobuzz hit roll): the beam
  always reaches the first monster in the line, as in C 3.x's zap()
  and the old pyhack beam -- resistance (rules.resists) is the defence
- the beam range IS the C roll: `7 + rnd(7)` (C: rn1(7, 7) in dobuzz;
  3.x: `7 + rnd(7)`) -- one randint per beam, auditable with SeqRng
- the sleep ray sleeps for a flat 25 turns (C: d(nd, 25)) -- no draw,
  the demo's established value
- the fire / cold extra damage vs the opposite resistance, the armor
  burn / destroy (burnarmor / destroy_items), the force bolt's
  `rnd(20) < 10 + mac` hit check, the polymorph system shock (1/25
  death) and the turning flee (monflee) are dropped: the demo
  monsters carry no gear, no mac, and no flee AI
- the death ray: C's nonliving / demon / magic-resist "unaffected" set
  maps onto rules.resists(DEATH) (undead / demon / golem); the old
  demo's "undead absorb the death ray" heal is dropped (C heals only
  the Death monster itself, which the demo has no)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .events import Event, MessageEvent, ZapEvent
from .items import cancel_items, consume_item
from .rules import (apply_damage, can_polymorph, find_target_in_line,
                    put_to_sleep, resists, roll, teleport_to_floor)
from .types import (DamageType, Direction, Item, Monster, ObjectType,
                    WandType, ZapEffect, World)

# C: dobuzz's `range = rn1(7, 7)` (3.x: `7 + rnd(7)`) -- 8..14
BEAM_RANGE_BASE = 7
BEAM_RANGE_RND = 7


@dataclass(frozen=True)
class ZapSpec:
    """One zap: the shared intermediate the caster builds (C: the
    `struct zap` of 3.x / the pseudo spellbook object of 5.0).

    `power` is the number of d6 damage dice (C: the `nd` of
    dobuzz()/zhitm()); the damage effects roll `d(power, 6)`.
    `damage_bonus` is the caster's post-roll damage bonus (C:
    spell_damage_bonus -- the INT/level bonus the SPELL side adds;
    wands pass 0).  STRIKING ignores both (C's force bolt is a fixed
    d(2,12)); SLEEP and the non-damage effects ignore them too.
    `source` is the power source (C: the otmp -- the wand, or the book
    for a spell) carried for provenance; the effect code never reads
    it (the caster-side differences stay in the caster).
    """
    effect: ZapEffect
    power: int = 0
    damage_bonus: int = 0
    range: int = 0                    # 0 = the C 7 + rnd(7) roll (in zap())
    noun: str = "bolt"                # beam noun for the miss lines (C: zap_str)
    source: Optional[Item] = None


# effect(world, caster, target, spec, rng) -> [Event]
EffectFn = Callable[[World, Monster, Monster, ZapSpec, Any], List[Event]]


# ------------------------------------------------------------
# The effect functions (C: the bhitm() otyp cases + the zhitm()
# damage cases -- one function per ZapEffect, wands and spells both
# dispatch here)
# ------------------------------------------------------------

def _zap_damage(world: World, target: Monster, spec: ZapSpec, rng,
                dmg_type: DamageType, source: str) -> List[Event]:
    """C: the zhitm() damage cases (d(nd, 6) + the spell bonus).  The
    resists() pre-check comes BEFORE the roll, as in C (resistance is
    tested before d(nd,6) is drawn) -- a resisted zap draws no dice."""
    if resists(target, dmg_type):
        return [MessageEvent(f"{target.name} is unaffected.")]
    dmg = roll(rng, 6, spec.power) + spec.damage_bonus
    return apply_damage(world, target.id, dmg, dmg_type, source)


def _zap_fire(world: World, caster: Monster, target: Monster, spec: ZapSpec,
              rng) -> List[Event]:
    """C: zhitm ZT_FIRE (WAN_FIRE)."""
    return _zap_damage(world, target, spec, rng, DamageType.FIRE,
                       "zap:fire")


def _zap_cold(world: World, caster: Monster, target: Monster, spec: ZapSpec,
              rng) -> List[Event]:
    """C: zhitm ZT_COLD (WAN_COLD + SPE_CONE_OF_COLD -- one effect,
    C 3.x's "a cold stream")."""
    return _zap_damage(world, target, spec, rng, DamageType.COLD,
                       "zap:cold")


def _zap_lightning(world: World, caster: Monster, target: Monster,
                   spec: ZapSpec, rng) -> List[Event]:
    """C: zhitm ZT_LIGHTNING (WAN_LIGHTNING + the lightning spell)."""
    return _zap_damage(world, target, spec, rng, DamageType.LIGHTNING,
                       "zap:lightning")


def _zap_magic(world: World, caster: Monster, target: Monster, spec: ZapSpec,
               rng) -> List[Event]:
    """C: zhitm ZT_MAGIC_MISSILE (SPE_MAGIC_MISSILE + WAN_MAGIC_MISSILE;
    the demo's undead-resist table stands in for C's magic
    resistance)."""
    return _zap_damage(world, target, spec, rng, DamageType.MAGIC_MISSILE,
                       "zap:magic")


def _zap_striking(world: World, caster: Monster, target: Monster,
                  spec: ZapSpec, rng) -> List[Event]:
    """C: bhitm WAN_STRIKING -> SPE_FORCE_BOLT (zap_punch) -- the
    force bolt / striking bolt, a fixed d(2,12) for BOTH the wand and
    the spell (C: `dmg = d(2, 12)`; the spell adds its bonus, which
    the spec carries)."""
    if resists(target, DamageType.MAGIC_MISSILE):
        return [MessageEvent(f"{target.name} is unaffected.")]
    dmg = roll(rng, 12, 2) + spec.damage_bonus
    return apply_damage(world, target.id, dmg, DamageType.MAGIC_MISSILE,
                        "zap:striking")


def _zap_sleep(world: World, caster: Monster, target: Monster, spec: ZapSpec,
               rng) -> List[Event]:
    """C: zhitm ZT_SLEEP -> sleep_monst (WAN_SLEEP + SPE_SLEEP).  The
    demo's flat 25-turn sleep (C: d(nd, 25)) is kept."""
    if resists(target, DamageType.SLEEP):
        return [MessageEvent(f"{target.name} resists sleep!")]
    return put_to_sleep(world, target.id, 25)


def _zap_death(world: World, caster: Monster, target: Monster, spec: ZapSpec,
               rng) -> List[Event]:
    """C: zhitm ZT_DEATH (WAN_DEATH + SPE_FINGER_OF_DEATH).  C's
    nonliving / demon / magic-resist unaffected set is the demo's
    resists(DEATH) table (undead / demon / golem)."""
    return _zap_damage(world, target, spec, rng, DamageType.DEATH,
                       "zap:death")


def _zap_polymorph(world: World, caster: Monster, target: Monster,
                   spec: ZapSpec, rng) -> List[Event]:
    """C: bhitm WAN_POLYMORPH + SPE_POLYMORPH (+ POT_POLYMORPH).  The
    system shock (C: 1/25 death) is dropped -- no corpse system."""
    if not can_polymorph(target):
        return [MessageEvent(f"{target.name} cannot be polymorphed!")]
    target.name = f"Polymorphed {target.name}"
    return [MessageEvent(f"{target.name} shudders and transforms!")]


def _zap_cancellation(world: World, caster: Monster, target: Monster,
                      spec: ZapSpec, rng) -> List[Event]:
    """C: bhitm WAN_CANCELLATION + SPE_CANCELLATION -> cancel_monst.
    The wand cancels the TARGET's items; the spell cancels the
    CASTER's (the caster side picks the actor)."""
    return cancel_items(world, target)


def _zap_teleport(world: World, caster: Monster, target: Monster,
                  spec: ZapSpec, rng) -> List[Event]:
    """C: bhitm WAN_TELEPORTATION + SPE_TELEPORT_AWAY ->
    u_teleport_mon.  The wand teleports the TARGET; the spell
    teleports the CASTER (the caster side picks the actor)."""
    return teleport_to_floor(world, target.id, rng)


def _zap_undead_turning(world: World, caster: Monster, target: Monster,
                        spec: ZapSpec, rng) -> List[Event]:
    """C: bhitm WAN_UNDEAD_TURNING + SPE_TURN_UNDEAD -> unturn_dead:
    the undead take `rnd(8)` (+ the spell bonus, carried in the
    spec) and flee; the living are unaffected.  The monflee() flee is
    message-only (no flee AI in the demo)."""
    if not target.is_undead:
        return [MessageEvent(f"{target.name} is unaffected.")]
    dmg = roll(rng, 8, 1) + spec.damage_bonus
    events: List[Event] = [MessageEvent(f"{target.name} is turned and flees!")]
    events += apply_damage(world, target.id, dmg, DamageType.MELEE,
                           "zap:undead_turning")
    return events


# ------------------------------------------------------------
# The registry (C: the bhitm()/zhitm() dispatch on the object type)
# ------------------------------------------------------------

ZAP_EFFECTS: Dict[ZapEffect, EffectFn] = {
    ZapEffect.FIRE: _zap_fire,
    ZapEffect.COLD: _zap_cold,
    ZapEffect.LIGHTNING: _zap_lightning,
    ZapEffect.MAGIC: _zap_magic,
    ZapEffect.STRIKING: _zap_striking,
    ZapEffect.SLEEP: _zap_sleep,
    ZapEffect.DEATH: _zap_death,
    ZapEffect.POLYMORPH: _zap_polymorph,
    ZapEffect.CANCELLATION: _zap_cancellation,
    ZapEffect.TELEPORT: _zap_teleport,
    ZapEffect.UNDEAD_TURNING: _zap_undead_turning,
}


# ------------------------------------------------------------
# The beam engine (C: the dobuzz() / bhit() traversal)
# ------------------------------------------------------------

def zap(world: World, caster_id: str, direction: Direction, spec: ZapSpec,
        rng) -> List[Event]:
    """Fire one zap in `direction` (C: the dobuzz()/bhit() beam):
    roll the beam range (C: `7 + rnd(7)`), walk the line, stop at the
    first monster (C behaviour, kept from the old beam), and dispatch
    to `ZAP_EFFECTS[spec.effect]`.  No monster in range: the wall /
    astray line (C: the zap_miss output)."""
    caster = world.actors[caster_id]
    range_ = spec.range if spec.range > 0 else \
        BEAM_RANGE_BASE + rng.randint(1, BEAM_RANGE_RND)  # C: 7 + rnd(7)
    target, hit_wall = find_target_in_line(world, caster.pos, direction,
                                           range_)
    events: List[Event] = [ZapEvent(caster_id, spec.effect,
                                    target.id if target else None)]
    if target is None:
        events.append(MessageEvent(
            f"💥 The {spec.noun} hits a wall." if hit_wall
            else f"The {spec.noun} goes astray."))
        return events
    return events + ZAP_EFFECTS[spec.effect](world, caster, target, spec,
                                             rng)


# ------------------------------------------------------------
# The wand side (C: dozap() -> zappable() -> weffects())
# ------------------------------------------------------------

# C: weffects() -- the wand -> (ZapEffect, d6 dice count) table.  The
# ray wands are `ubuzz(BZ_U_WAND(...), 6)` (six d6 dice, C's `nd`);
# the striking wand's d(2,12) is fixed in the effect (C bhitm
# WAN_STRIKING -> SPE_FORCE_BOLT), so it carries power 0.  The
# unported wands (make invisible, slow, speed, opening, locking,
# probing, digging, nothing) are absent: they land with their
# machinery (the C weffects() cases stay the provenance list).
WAND_ZAPS: Dict[WandType, Tuple[ZapEffect, int]] = {
    WandType.FIRE: (ZapEffect.FIRE, 6),
    WandType.COLD: (ZapEffect.COLD, 6),
    WandType.LIGHTNING: (ZapEffect.LIGHTNING, 6),
    WandType.SLEEP: (ZapEffect.SLEEP, 6),
    WandType.DEATH: (ZapEffect.DEATH, 6),
    WandType.STRIKING: (ZapEffect.STRIKING, 0),
    WandType.CANCELLATION: (ZapEffect.CANCELLATION, 0),
    WandType.TELEPORTATION: (ZapEffect.TELEPORT, 0),
    WandType.POLYMORPH: (ZapEffect.POLYMORPH, 0),
    WandType.UNDEAD_TURNING: (ZapEffect.UNDEAD_TURNING, 0),
}


def _find_wand(caster: Monster, wand_type: WandType) -> Optional[Item]:
    for item in caster.inventory:
        if (item.otype == ObjectType.WAND
                and item.wand_type == wand_type
                and item.charges > 0):
            return item
    return None


def use_wand(world: World, caster_id: str, wand_type: WandType,
             direction: Direction, rng) -> List[Event]:
    """C: dozap() -> zappable() -> weffects(): fire a wand of
    `wand_type` in `direction` and return the events.

    Caster-side differences (kept here, not in the effect): the wand's
    power (C weffects: `ubuzz(BZ_U_WAND(...), 6)` -- six d6 dice, the
    WAND_ZAPS table) and the discharge consuming a charge even when
    the bolt hits a wall (C: useup in dozap after weffects).
    """
    caster = world.actors[caster_id]
    wand = _find_wand(caster, wand_type)
    if wand is None:
        name = wand_type.name.lower().replace("_", " ")
        return [MessageEvent(f"You don't have a charged {name} wand.")]

    # C: the discharge happens -- a charge is consumed even when the
    # bolt hits a wall
    wand.charges -= 1
    if wand.charges <= 0:
        consume_item(world, caster_id, wand.id)

    if wand_type not in WAND_ZAPS:
        # not ported yet (C: the remaining weffects() cases)
        name = wand_type.name.lower().replace("_", " ")
        return [MessageEvent(f"The {name} wand does nothing.")]

    effect, power = WAND_ZAPS[wand_type]
    spec = ZapSpec(effect=effect, power=power, source=wand, noun="bolt")
    return zap(world, caster_id, direction, spec, rng)
