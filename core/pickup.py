"""Pick up items from the floor (port of the top-item subset of
src/pickup.c pickobj()).

C's pickobj() is a big function (containers, merging, the INV_MAX
inventory cap, leashes, the "pick up all" 'G' variant, the
pick-up-while-swallowed cases).  This is the deliberately tiny subset
(PLAN-ARMOR.md decision 10): take the topmost item on the actor's
tile, "You pick up the X."; an empty tile gets "You see nothing here
to pick up."  The move itself is core.invent.addinv (C: pickobj ->
pick_obj -> hold_another_object -> addinv) -- the pack half of the
item's where-state has exactly one writer.

Simplifications (documented, not bugs):

- No merging (C merges compatible items into stacks --
  PLAN-INVENT.md phase B), no inventory cap (C INV_MAX), no leashes /
  containers / food checks, no encumbrance refusal (C's
  hold_another_object near_capacity branch -- PLAN-INVENT.md
  phase D).
- "Topmost" is the item C's per-tile chain head would be: the most
  recently placed (C add_lev() inserts at the head), i.e. the last
  entry in ``world.items_at()``'s insertion order.  Unobservable in
  the subset while every tile holds at most one item.
"""

from __future__ import annotations

from typing import List

from .events import Event, MessageEvent
from .invent import addinv
from .objects import ObjClass
from .types import World


def pickup(world: World, mon_id: str, rng) -> List[Event]:
    """C: pickobj() -- take the topmost item on the actor's tile into
    the actor's inventory (core.invent.addinv).

    The shop billing half (C: pickobj -> addtobill, shk.c 3510+): when
    the hero picks up an item on a costly_spot that is not a coin and
    not no_charge, it goes on the shopkeeper's bill (core.shk
    .add_one_tobill) -- no extra message, C's pickup line is the only
    one.
    """
    mon = world.actors.get(mon_id)
    if mon is None:
        return []
    here = world.items_at(mon.pos)
    if not here:
        return [MessageEvent("You see nothing here to pick up.")]
    top = here[-1]
    addinv(world, mon_id, top)
    events: List[Event] = [MessageEvent(f"You pick up the {top.name}.")]
    if mon.is_hero:
        events += _shop_billing(world, mon, top)
    return events


def _shop_billing(world: World, mon, top) -> List[Event]:
    """The pickup billing hook (C: pickobj -> addtobill).  A picked-up
    item on a costly_spot that is not a coin and not no_charge goes on
    the shopkeeper's bill."""
    from .shk import add_one_tobill, costly_spot, inside_shop, shop_keeper

    x, y = mon.pos
    if (
        costly_spot(world, x, y)
        and top.oclass != int(ObjClass.COIN)
        and not top.no_charge
    ):
        roomno = inside_shop(world.map, mon.pos)
        shkp = shop_keeper(world, world.lev, roomno)
        return add_one_tobill(world, shkp, top)
    return []
