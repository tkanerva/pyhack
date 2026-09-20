"""Item helpers: inventory manipulation and charge consumption."""
from __future__ import annotations

from typing import List

from .events import Event, MessageEvent
from .types import Monster, World


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
