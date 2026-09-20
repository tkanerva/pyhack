"""Potion system: quaff() applies the potion's effect and returns events.

Ported from the old potion.py.  Simplifications (documented in
ARCHITECTURE.md): effects are keyed by an explicit PotionType, and the
broken blessed/cursed inversion logic from the old PotionActor (which
flipped blessed/cursed on *every* quaff unconditionally) is dropped.
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .items import cancel_items, consume_item
from .rules import apply_confusion, can_polymorph, heal, put_to_sleep
from .types import Item, ObjectType, PotionType, World

HEALING_POWER = 12


def _find_potion(world: World, monster_id: str, item_id: str) -> Optional[Item]:
    item = world.items.get(item_id)
    if item is None or item.otype != ObjectType.POTION or item.container != monster_id:
        return None
    return item


def quaff(world: World, monster_id: str, item_id: str, rng) -> List[Event]:
    item = _find_potion(world, monster_id, item_id)
    if item is None:
        return [MessageEvent("You don't have such a potion.")]
    if item.charges <= 0:
        return [MessageEvent("The potion is empty.")]

    actor = world.actors[monster_id]
    ptype = item.potion_type or PotionType.HEALING
    events: List[Event] = []
    if ptype == PotionType.HEALING:
        events += heal(world, monster_id, HEALING_POWER)
    elif ptype == PotionType.CONFUSION:
        events += apply_confusion(world, monster_id, 20)
    elif ptype == PotionType.SLEEPING_SICKNESS:
        events += put_to_sleep(world, monster_id, 15)
    elif ptype == PotionType.POLYMORPH:
        if not can_polymorph(actor):
            events.append(MessageEvent("You are unaffected." if actor.is_hero
                                       else f"{actor.name} is unaffected."))
        else:
            actor.name = f"Polymorphed {actor.name}"
            events.append(MessageEvent("You shudder and transform!" if actor.is_hero
                                       else f"{actor.name} shudders and transforms!"))
    elif ptype == PotionType.CANCELLATION:
        events += cancel_items(world, actor)
    elif ptype == PotionType.INCREASE_AC:
        actor.ac -= 1
        events.append(MessageEvent("You feel stronger." if actor.is_hero
                                   else f"{actor.name} feels stronger."))

    item.charges -= 1
    if item.charges <= 0:
        consume_item(world, monster_id, item.id)
    return events
