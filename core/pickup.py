"""Pick up items from the floor (port of the top-item subset of
src/pickup.c pickobj()).

C's pickobj() is a big function (containers, merging, the INV_MAX
inventory cap, leashes, the "pick up all" 'G' variant, the
pick-up-while-swallowed cases).  This is the deliberately tiny subset
(PLAN-ARMOR.md decision 10): take the topmost item on the actor's
tile, "You pick up the X."; an empty tile gets "You see nothing here
to pick up."

Simplifications (documented, not bugs):

- No merging (C merges compatible items into stacks), no inventory
  cap (C INV_MAX), no leashes / containers / food checks.
- "Topmost" is the item C's per-tile chain head would be: the most
  recently placed (C add_lev() inserts at the head), i.e. the last
  entry in ``world.items_at()``'s insertion order.  Unobservable in
  the subset while every tile holds at most one item.
"""
from __future__ import annotations

from typing import List

from .events import Event, MessageEvent
from .types import World


def pickup(world: World, mon_id: str, rng) -> List[Event]:
    """C: pickobj() -- take the topmost item on the actor's tile into
    the actor's inventory."""
    mon = world.actors.get(mon_id)
    if mon is None:
        return []
    here = world.items_at(mon.pos)
    if not here:
        return [MessageEvent("You see nothing here to pick up.")]
    top = here[-1]
    top.pos = None
    top.container = mon_id
    mon.inventory.append(top)
    return [MessageEvent(f"You pick up the {top.name}.")]
