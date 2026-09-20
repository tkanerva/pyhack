"""Trap system.

Traps are data (core.types.Trap).  Triggering is one function:
check_traps() rolls the 30% chance (same as the old demo) and dispatches
to a per-type effect function in TRAP_EFFECTS.  Adding a trap type now
means adding one function and one registry entry -- no more 200-line
if/elif in TrapActor._apply_trap_effect.
"""
from __future__ import annotations

from typing import Callable, List

from .events import Event, MessageEvent, TrapSeenEvent, TrapTriggeredEvent
from .items import cancel_items
from .rules import (apply_damage, apply_stuck, put_to_sleep, resists, roll,
                    teleport_to_floor)
from .types import DamageType, Monster, Trap, TrapType, World

TrapEffect = Callable[[World, Trap, str, object], List[Event]]


def _pit_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    a = world.actors[actor_id]
    dmg = roll(rng, 6)
    flavor = (f"⚡ A pit hits you for {dmg} damage!" if a.is_hero
              else f"⚡ {a.name} triggers a pit and takes {dmg} damage!")
    events: List[Event] = [MessageEvent(flavor)]
    events += apply_damage(world, actor_id, dmg, DamageType.MELEE,
                           f"trap:{trap.id}", message=False)
    events += apply_stuck(world, actor_id, 10, message=False)
    return events


def _spiked_pit_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    a = world.actors[actor_id]
    dmg = roll(rng, 12)
    flavor = (f"⚡ A spiked pit hits you for {dmg} damage!" if a.is_hero
              else f"⚡ {a.name} triggers a spiked pit and takes {dmg} damage!")
    events: List[Event] = [MessageEvent(flavor)]
    events += apply_damage(world, actor_id, dmg, DamageType.MELEE,
                           f"trap:{trap.id}", message=False)
    events += apply_stuck(world, actor_id, 10, message=False)
    return events


def _fire_trap_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    a = world.actors[actor_id]
    if resists(a, DamageType.FIRE):
        text = ("You resist the fire trap." if a.is_hero
                else f"{a.name} resists the fire trap.")
        return [MessageEvent(text)]
    dmg = roll(rng, 6)
    flavor = (f"🔥 A fire trap hits you for {dmg} damage!" if a.is_hero
              else f"🔥 {a.name} is hit by a fire trap for {dmg} damage!")
    events: List[Event] = [MessageEvent(flavor)]
    events += apply_damage(world, actor_id, dmg, DamageType.FIRE,
                           f"trap:{trap.id}", message=False)
    return events


def _ranged_trap_effect(world: World, trap: Trap, actor_id: str, rng,
                        projectile: str) -> List[Event]:
    """Arrow / dart trap with an AC-based hit check (old trap_hit())."""
    a = world.actors[actor_id]
    die = 6 if projectile == "arrow" else 4
    hit_chance = max(5, 20 - a.ac)
    if rng.randint(1, 20) <= hit_chance:
        dmg = roll(rng, die)
        flavor = (f"🏹 A {projectile} trap hits you for {dmg} damage!" if a.is_hero
                  else f"🏹 {a.name} is hit by a {projectile} trap for {dmg} damage!")
        events: List[Event] = [MessageEvent(flavor)]
        events += apply_damage(world, actor_id, dmg, DamageType.ACID,
                               f"trap:{trap.id}", message=False)
        return events
    if a.is_hero:
        return [MessageEvent(f"🏹 The {projectile} trap misses you.")]
    return [MessageEvent(f"🏹 The {projectile} trap misses {a.name}.")]


def _sleeping_gas_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    return put_to_sleep(world, actor_id, 25)


def _teleport_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    return teleport_to_floor(world, actor_id, rng)


def _trapdoor_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    a = world.actors[actor_id]
    flavor = ("🕳️ You fall through a trap door!" if a.is_hero
              else f"🕳️ {a.name} falls through a trap door!")
    events: List[Event] = [MessageEvent(flavor)]
    events += teleport_to_floor(world, actor_id, rng)
    return events


def _anti_magic_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    return cancel_items(world, world.actors[actor_id])


def _web_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    return apply_stuck(world, actor_id, 10)


def _boulder_effect(world: World, trap: Trap, actor_id: str, rng) -> List[Event]:
    a = world.actors[actor_id]
    dmg = rng.randint(4, 20)
    flavor = (f"💥 A rolling boulder hits you for {dmg} damage!" if a.is_hero
              else f"💥 {a.name} is crushed by a rolling boulder for {dmg} damage!")
    events: List[Event] = [MessageEvent(flavor)]
    events += apply_damage(world, actor_id, dmg, DamageType.MELEE,
                           f"trap:{trap.id}", message=False)
    return events


TRAP_EFFECTS: "dict[TrapType, TrapEffect]" = {
    TrapType.PIT: _pit_effect,
    TrapType.SPIKED_PIT: _spiked_pit_effect,
    TrapType.FIRE_TRAP: _fire_trap_effect,
    TrapType.ARROW_TRAP: lambda w, t, a, r: _ranged_trap_effect(w, t, a, r, "arrow"),
    TrapType.DART_TRAP: lambda w, t, a, r: _ranged_trap_effect(w, t, a, r, "dart"),
    TrapType.SLEEPING_GAS: _sleeping_gas_effect,
    TrapType.TELEPORTATION: _teleport_effect,
    TrapType.ANTI_MAGIC: _anti_magic_effect,
    TrapType.WEB: _web_effect,
    TrapType.ROLLING_BOULDER: _boulder_effect,
    TrapType.MAGIC_PORTAL: _teleport_effect,
    TrapType.LEVEL_TELEPORTER: _teleport_effect,
    TrapType.TRAPDOOR: _trapdoor_effect,
    TrapType.STAIRS_DOWN: _trapdoor_effect,
    TrapType.STAIRS_UP: _teleport_effect,
}


def check_traps(world: World, actor_id: str, rng) -> List[Event]:
    """Called after an actor moves: 30% chance to trigger each trap under
    their feet (same roll as the old demo); otherwise the trap is seen."""
    actor = world.actors[actor_id]
    events: List[Event] = []
    for trap in world.traps.values():
        if trap.pos != actor.pos or trap.triggered or trap.disarmed:
            continue
        if rng.randint(1, 100) <= 30:
            trap.triggered = True
            events.append(TrapTriggeredEvent(trap.id, actor_id))
            effect = TRAP_EFFECTS.get(trap.trap_type)
            if effect is not None:
                events.extend(effect(world, trap, actor_id, rng))
        elif not trap.seen:
            trap.seen = True
            events.append(TrapSeenEvent(trap.id))
            if actor.is_hero:
                events.append(MessageEvent(
                    "👣 You feel something underfoot but don't trigger it."))
            else:
                events.append(MessageEvent(f"👣 {actor.name} feels something underfoot."))
    return events


def disarm_trap(world: World, trap_id: str, source_id: str) -> List[Event]:
    trap = world.traps.get(trap_id)
    if trap is None or trap.disarmed or trap.triggered:
        return [MessageEvent("You fail to find a way to disarm the trap.")]
    trap.disarmed = True
    source = world.actors.get(source_id)
    if source is not None and source.is_hero:
        return [MessageEvent("You disarm the trap.")]
    return [MessageEvent(f"{source.name} disarms the trap." if source
                         else "The trap is disarmed.")]
