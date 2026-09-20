"""Wand zaps: directional beams that hit the first monster in line.

Ported from the old zap.py (which was target-based) into the event
architecture: a wand is an Item in the caster's inventory and
use_wand() returns events.  A discharge consumes a charge even when the
bolt hits a wall (NetHack behaviour).  Undead absorb the death ray,
as in the old zap.py.
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent, ZapEvent
from .items import cancel_items, consume_item
from .rules import (apply_damage, can_polymorph, find_target_in_line, heal,
                    put_to_sleep, resists, teleport_to_floor)
from .types import DamageType, Direction, Item, Monster, ObjectType, WandType, World

WAND_DAMAGE = {
    WandType.FIRE: DamageType.FIRE,
    WandType.COLD: DamageType.COLD,
    WandType.LIGHTNING: DamageType.LIGHTNING,
    WandType.DEATH: DamageType.DEATH,
    WandType.STRIKING: DamageType.MAGIC_MISSILE,
}

WAND_POWER = 6  # flat power, same as the old zap.py
BEAM_RANGE = 7


def _find_wand(caster: Monster, wand_type: WandType) -> Optional[Item]:
    for item in caster.inventory:
        if (item.otype == ObjectType.WAND
                and item.wand_type == wand_type
                and item.charges > 0):
            return item
    return None


def use_wand(world: World, caster_id: str, wand_type: WandType,
             direction: Direction, rng) -> List[Event]:
    caster = world.actors[caster_id]
    wand = _find_wand(caster, wand_type)
    if wand is None:
        name = wand_type.name.lower().replace("_", " ")
        return [MessageEvent(f"You don't have a charged {name} wand.")]

    target, hit_wall = find_target_in_line(world, caster.pos, direction, BEAM_RANGE)

    wand.charges -= 1
    if wand.charges <= 0:
        consume_item(world, caster_id, wand.id)
    events: List[Event] = [ZapEvent(caster_id, wand_type,
                                    target.id if target else None)]

    if target is None:
        events.append(MessageEvent("💥 The bolt hits a wall." if hit_wall
                                   else "The bolt goes astray."))
        return events

    if wand_type in WAND_DAMAGE:
        dmg_type = WAND_DAMAGE[wand_type]
        if dmg_type == DamageType.DEATH and target.is_undead:
            events += heal(world, target.id, WAND_POWER)
        else:
            events += apply_damage(world, target.id, WAND_POWER, dmg_type,
                                   f"zap:{wand_type.name.lower()}")
    elif wand_type == WandType.SLEEP:
        if resists(target, DamageType.SLEEP):
            events.append(MessageEvent(f"{target.name} resists sleep!"))
        else:
            events += put_to_sleep(world, target.id, 25)
    elif wand_type == WandType.CANCELLATION:
        events += cancel_items(world, target)
    elif wand_type == WandType.TELEPORTATION:
        events += teleport_to_floor(world, target.id, rng)
    elif wand_type == WandType.POLYMORPH:
        if not can_polymorph(target):
            events.append(MessageEvent(f"{target.name} cannot be polymorphed!"))
        else:
            target.name = f"Polymorphed {target.name}"
            events.append(MessageEvent(f"{target.name} shudders and transforms!"))
    elif wand_type == WandType.UNDEAD_TURNING:
        if target.is_undead:
            events.append(MessageEvent(f"{target.name} is turned and flees!"))
        else:
            events.append(MessageEvent(f"{target.name} is unaffected."))
    else:
        name = wand_type.name.lower().replace("_", " ")
        events.append(MessageEvent(f"The {name} wand does nothing."))
    return events
