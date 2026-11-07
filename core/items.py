"""Item helpers: the carried-item queries the systems share.

The item LOCATION writers (where an item is: floor / pack / container /
gone) live in core.invent (the pack half) and core.mkobj (the
place_object / add_to_container half) -- the PLAN-INVENT.md
"single writer" rule.  This module is query-only.
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .types import Item, Monster, World


def cancel_items(world: World, monster: Monster) -> List[Event]:
    """Cancel all charged items in a monster's inventory (cancellation
    zap / anti-magic trap / potion of cancellation).

    C: cancel_items (src/zap.c) -- the charged half zeroes `spe` (the
    wand / book / tool charge field), not a separate counter.
    """
    changed = False
    for item in monster.inventory:
        if item.spe > 0:
            item.spe = 0
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
