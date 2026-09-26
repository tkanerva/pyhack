"""Item helpers: inventory manipulation and charge consumption."""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .types import Item, Monster, World


def consume_item(world: World, monster_id: str, item_id: str) -> None:
    """Remove an item from the world and from its carrier's inventory."""
    item = world.items.pop(item_id, None)
    if item is None:
        return
    carrier = world.actors.get(monster_id)
    if carrier is not None:
        carrier.inventory = [i for i in carrier.inventory if i.id != item_id]


def cancel_items(world: World, monster: Monster) -> List[Event]:
    """Cancel all charged items in a monster's inventory (cancellation
    zap / anti-magic trap / potion of cancellation)."""
    changed = False
    for item in monster.inventory:
        if item.charges > 0:
            item.charges = 0
            changed = True
    if changed:
        text = ("Your magical items are cancelled!" if monster.is_hero
                else f"{monster.name}'s magical items are cancelled!")
        return [MessageEvent(text)]
    text = "Nothing happens." if monster.is_hero \
        else f"Nothing happens to {monster.name}."
    return [MessageEvent(text)]


def wielded_of(world: World, monster_id: str) -> Optional[Item]:
    """The item a monster is wielding (C: uwep for the hero), or None.

    Reads ``monster.wielded`` (an item id) and returns the item only if
    it is actually in the monster's inventory; a dangling id (the item
    was consumed / dropped) counts as bare hands.
    """
    mon = world.actors.get(monster_id)
    if mon is None or mon.wielded is None:
        return None
    for item in mon.inventory:
        if item.id == mon.wielded:
            return item
    return None
