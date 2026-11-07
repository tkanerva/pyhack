"""Inventory: the pack and its letters (port of the inventory-side
half of src/invent.c, PLAN-INVENT.md wave 6a).

This module is the single writer of the PACK half of an item's
where-state: nothing else in the tree may set ``Item.carrier``, append
to or filter a ``Monster.inventory``, or pop a carried item out of
``World.items``.  The floor / container half lives in core.mkobj
(``place_object`` / ``add_to_container`` / ``delete_contents``) --
exactly C's split, where invent.c owns the ``gi.invent`` chain and
mkobj.c owns the level placement.  The two halves stay mutually
exclusive: an item is on the floor, carried or contained
(``Item``'s docstring), and the three states are what
``conftest.assert_item_locations`` asserts.

Included (C spans in the function docstrings; the full function map
is PLAN-INVENT.md §1):

- the location group: ``addinv`` (C addinv / addinv_core0, minus the
  merge half -- phase B), ``freeinv`` (+ the drop path's
  place_object, composed), ``useup`` / ``useupall``, ``delobj``
  (C delobj / delobj_core, the contents go with it),
  ``consume_obj_charge`` (the ``spe`` decrement),
  ``carry_obj_effects`` (the C call site; a no-op hook -- no timers);
- the letter group: ``assigninvlet`` (the a..z A..Z '$' '#'
  allocation, the C gl.lastinvnr walk on ``World.lastinvnr``),
  ``invletter_value``, ``reorder_invent``, ``obj_to_let``,
  ``let_to_name`` (the C names[] class table).

Callers (C: the same functions, the same order).  ``pickup`` ->
addinv (pickobj), ``worldgen._starting_kit`` -> addinv (u_init's
ini_inv), ``makemon.mongets`` / ``mkmonmoney`` -> addinv (the
monster's pocket -- a monster's pack carries no letters, so the
letter half is a no-op there), ``hunger`` / ``potions`` / ``scrolls``
/ ``spells`` / ``zap`` -> useup + consume_obj_charge,
``worn._remove_destroyed`` -> delobj.

Deliberate divergences (PLAN-INVENT.md §5): no linked list (the pack
is a list kept sorted by letter), ``invlet_constant`` is unconditional
(no #adjust / reassign / compactify -- those are the #adjust half,
phase H), the C ``how_lost`` / ``bypass`` / ``nomerge`` / glob halves
are dropped with the throwing system, and ``update_inventory`` does
not exist (the UI redraws every turn).

STUB / no-op hooks (named so the C call sites have a home):
``carry_obj_effects`` (the cursed-figurine transform timeout needs
timeout.c), the ``maybe_unpaid`` half of ``consume_obj_charge`` (the
shop, PLAN-SPECIAL-ROOMS).
"""
from __future__ import annotations

from typing import Optional

from .objects import DEF_OC_SYMS, MAXOCLASSES, ObjClass
from .types import Item, Monster, World

# C: hack.h -- the invlet space (the defsym.h GOLD_SYM lives in
# core.objects_defs; the rest are hack.h)
GOLD_SYM = "$"      # C: GOLD_SYM -- the one coin stack's letter
NOINVSYM = "#"      # C: NOINVSYM -- overflow, all 52 letters are in use
CONTAINED_SYM = ">"  # C: CONTAINED_SYM -- designator for inside a container
HANDS_SYM = "-"      # C: HANDS_SYM -- hands|fingers|self, per context
invlet_basic = 52    # C: invlet_basic -- a..z A..Z

# C: invent.c names[] (4841-4845) -- let_to_name's class table,
# indexed by oclass (C passes the oclass id AS the menu "letter")
_CLASS_NAMES = (
    "",                  # 0: C's NULL slot
    "Illegal objects",   # 1: ILLOBJ_CLASS
    "Weapons", "Armor", "Rings", "Amulets", "Tools", "Comestibles",
    "Potions", "Scrolls", "Spellbooks", "Wands", "Coins",
    "Gems/Stones", "Boulders/Statues", "Iron balls", "Chains", "Venoms",
)


# ------------------------------------------------------------
# The letter group (C: the invlet allocation of src/invent.c)
# ------------------------------------------------------------

def invletter_value(letter: str) -> int:
    """C: invletter_value (src/invent.c 391-399): the sort rank of an
    inventory letter -- gold first, then a..z, A..Z, the '#' overflow
    and (C: "shouldn't happen") everything else last."""
    if "a" <= letter <= "z":
        return ord(letter) - ord("a") + 2
    if "A" <= letter <= "Z":
        return ord(letter) - ord("A") + 2 + 26
    if letter == GOLD_SYM:
        return 1
    if letter == NOINVSYM:
        return 1 + invlet_basic + 1
    return 1 + invlet_basic + 1 + 1  # C: none of the above


def _inv_rank(letter: str) -> int:
    """C: inv_rank (src/invent.c 735, `invlet ^ 040`): the
    reorder_invent key -- '#' and '$' ahead of the letters, lowercase
    before uppercase (the C code assumes ASCII; 040 is the octal case
    bit).  An empty letter (an item that never went through the
    allocator) sorts first."""
    return ord(letter) ^ 0x20 if letter else 0


def assigninvlet(world: World, mon: Monster, item: Item) -> str:
    """C: assigninvlet (src/invent.c 693-732): the letter of ``item``
    in ``mon``'s pack.

    The coin stack is always '$' (C: the COIN_CLASS early return).
    A letter the item already holds survives (C: the "keep it" branch)
    -- that is what keeps a dropped-and-re-picked-up item on its
    learned letter; a letter held by ANOTHER item is cleared first (C:
    the collision branch).  Otherwise the walk starts just after
    ``world.lastinvnr`` (C: gl.lastinvnr) in a..z A..Z order, skipping
    the '#' slot (C: the `i == invlet_basic` jump), and takes the
    first free slot; a full pack gets '#' (C: the `inuse[i] ?
    NOINVSYM` answer).  Note the C walk can spin on a full pack
    (lastinvnr at the last letter, every slot in use) -- unreachable
    there because C refuses a 53rd pickup first; this port answers
    '#' in that case instead of looping.
    """
    if item.oclass == int(ObjClass.COIN):
        item.invlet = GOLD_SYM
        return item.invlet
    inuse = [False] * invlet_basic
    for other in mon.inventory:
        if other is item:
            continue
        let = other.invlet
        if "a" <= let <= "z":
            inuse[ord(let) - ord("a")] = True
        elif "A" <= let <= "Z":
            inuse[ord(let) - ord("A") + 26] = True
        if let == item.invlet:
            item.invlet = ""
    let = item.invlet
    if "a" <= let <= "z" or "A" <= let <= "Z":
        return let
    # C: `for (i = gl.lastinvnr + 1; i != gl.lastinvnr; i++)` -- the
    # wrap-around walk over the 52 letters, '#' (slot 52) skipped
    n = invlet_basic + 1
    i = (world.lastinvnr + 1) % n
    free = -1
    steps = 0
    while steps < n:
        if i == invlet_basic:
            i = (i + 1) % n  # C: i = -1; the loop increment lands on 0
        elif not inuse[i]:
            free = i
            break
        i = (i + 1) % n
        steps += 1
    if free >= 0:
        item.invlet = (chr(ord("a") + free) if free < 26
                       else chr(ord("A") + free - 26))
        world.lastinvnr = free
    else:
        item.invlet = NOINVSYM
    return item.invlet


def reorder_invent(mon: Monster) -> None:
    """C: reorder_invent (src/invent.c 738-767): sort the pack by
    letter (the inv_rank key: '$' / '#' first, then a..z, then A..Z).
    C's insertion sort is stable; the built-in sort is too, so a
    re-inserted item settles in the same slot it had.  Called from
    addinv (C: the invlet_constant branch)."""
    mon.inventory.sort(key=lambda it: _inv_rank(it.invlet))


def obj_to_let(item: Item) -> str:
    """C: obj_to_let (src/invent.c 2902-2909): the item's letter.  C's
    !invlet_constant branch (re-letter the whole pack with reassign())
    is the #adjust half, out of scope -- the constant-letter behaviour
    is unconditional here (PLAN-INVENT.md decision 5)."""
    return item.invlet


def let_to_name(let: int, unpaid: bool = False,
                showsym: bool = False) -> str:
    """C: let_to_name (src/invent.c 4852-4891): the menu heading for a
    class -- the C names[] table (the oclass id is the "letter"), the
    CONTAINED_SYM "Bagged/Boxed items" case, the "Unpaid " prefix, and
    (showsym) the class-glyph suffix with C's 8-column padding
    (7 - len spaces, then `  ('%c')`)."""
    if 1 <= let < MAXOCLASSES:
        class_name = _CLASS_NAMES[let]
    elif let == ord(CONTAINED_SYM):
        class_name = "Bagged/Boxed items"
    else:
        class_name = _CLASS_NAMES[1]
    out = ("Unpaid " if unpaid else "") + class_name
    if 1 <= let < MAXOCLASSES and showsym:
        out += " " * max(7 - len(class_name), 0) \
            + "  ('%s')" % DEF_OC_SYMS[let].sym
    return out


# ------------------------------------------------------------
# The location group (C: the gi.invent chain operations)
# ------------------------------------------------------------

def addinv(world: World, mon_id: str, item: Item) -> Item:
    """C: addinv -> addinv_core0 (src/invent.c 1151-1155, 1055-1148):
    put ``item`` into ``mon``'s pack.

    The item must be free to go in: not carried, inside no container,
    and at most lying on the floor -- which is the C
    ``obj_extract_self(obj)`` the pickup path does before the
    ``obj->where != OBJ_FREE`` panic, spelled as "clear ``pos``" here
    because the floor half of the where-state *is* ``pos``.  The
    letter is assigned and the pack re-sorted for the hero (C:
    gi.invent is the hero's pack; a monster's minvent carries no
    letters); ``World.items`` is the registry, so the item is
    registered here whether or not it was already in it.  The merge
    half of C's addinv (merged() into the quiver, then the pack) is
    phase B; until it lands this never merges.  Returns the item (C:
    the possibly-merged survivor).
    """
    mon = world.actors[mon_id]
    if item.carrier is not None:
        raise ValueError(f"addinv: {item.id} is already carried "
                         f"by {item.carrier}")
    for other in world.items.values():
        if other is not item and item.id in other.contents:
            raise ValueError(f"addinv: {item.id} is inside {other.id}")
    item.pos = None                      # C: obj_extract_self(obj)
    item.carrier = mon_id
    item.lev = mon.lev
    if mon.is_hero:
        assigninvlet(world, mon, item)
    mon.inventory.append(item)
    if mon.is_hero:
        reorder_invent(mon)
    world.items[item.id] = item
    carry_obj_effects(item)
    return item


def freeinv(world: World, mon_id: str, item: Item) -> None:
    """C: freeinv (src/invent.c 1402-1409) + the drop path's
    place_object (do.c dropx): remove ``item`` from ``mon``'s pack and
    set it on ``mon``'s square.  C's freeinv only unlinks the item
    from the gi.invent chain; the where-state here is DERIVED (pos /
    carrier / contents), so the two C steps compose into one.  The
    worn mask is not touched (C: freeinv leaves owornmask; the
    take-off path clears it), and C's freeinv_core side effects are
    the no-op subset (no amulet / luck / timer bookkeeping)."""
    mon = world.actors[mon_id]
    mon.inventory = [i for i in mon.inventory if i.id != item.id]
    item.carrier = None
    item.pos = mon.pos
    item.lev = mon.lev
    world.items[item.id] = item


def useup(world: World, mon_id: str, item: Item) -> None:
    """C: useup (src/invent.c 1320-1333): an item in the pack is going
    away after being used, one at a time.  A stack drops one and
    recomputes its weight (C: `obj->owt = weight(obj)`); a lone item
    takes the whole useupall path.  (C: "This works correctly for
    containers because they (containers) don't merge.")"""
    if item.quan > 1:
        item.quan -= 1
        from .mkobj import weight  # local import: mkobj imports worn
        item.owt = weight(world, item)
    else:
        useupall(world, mon_id, item)


def useupall(world: World, mon_id: str, item: Item) -> None:
    """C: useupall (src/invent.c 1311-1317): setnotworn + freeinv +
    obfree -- the item (and its contents) go.  pyhack's delobj carries
    the setnotworn (see its docstring), so this IS the delobj path."""
    delobj(world, item.id)


def delobj(world: World, item_id: str, force: bool = False) -> Optional[Item]:
    """C: delobj / delobj_core (src/invent.c 1429-1462): delete the
    item from WHEREVER it is -- floor, pack or container -- and take
    its contents with it (C: obfree "frees contents also", recursively
    here: a bag of holding's chest takes the chest's loot with it).

    C's obj_resists(obj, 0, 0) guard (the Amulet, the invocation
    tools, Rider corpses) is dead in the no-artifact subset; ``force``
    is accepted for the C call sites and ignored (nothing resists).
    C spreads the worn-slot clearing across useupall and the per-type
    off hooks; pyhack's delobj does it once here -- BEFORE the item
    leaves the pack, because the scan that clears the bit reads the
    carrier's inventory (C: useupall's setnotworn then freeinv order).
    A contained item leaves its parent's ``contents`` (C:
    obj_extract_self) and the parent's weight is recomputed.
    ``Monster.wielded`` is deliberately left alone -- a dangling id
    reads as bare hands (core.items.wielded_of) until PLAN-DROP
    phase C replaces the field with wield.setuwep.

    Returns the deleted item, or None if the id was not in the world.
    """
    item = world.items.get(item_id)
    if item is None:
        return None
    mon = world.actors.get(item.carrier) if item.carrier else None
    if mon is not None:
        if item.owornmask:
            from .worn import setnotworn  # local import: worn imports this
            setnotworn(mon, item)         # C: setnotworn before freeinv
        mon.inventory = [i for i in mon.inventory if i.id != item_id]
    else:
        for parent in world.items.values():
            if item_id in parent.contents:
                parent.contents.remove(item_id)  # C: obj_extract_self
                from .mkobj import weight      # local import: mkobj imports worn
                parent.owt = weight(world, parent)
                break
    for child_id in list(item.contents):
        delobj(world, child_id, force)
    item.contents = []
    world.items.pop(item_id, None)
    return item


def consume_obj_charge(world: World, mon_id: str, item: Item,
                       maybe_unpaid: bool = False) -> None:
    """C: consume_obj_charge (src/invent.c 1336-1346): spend one
    charge on a wand / book / tool -- the ``spe`` decrement.  The
    ``maybe_unpaid`` shop half (check_unpaid) is accepted and ignored
    (the shop is PLAN-SPECIAL-ROOMS' business, PLAN-INVENT.md
    decision 11)."""
    item.spe -= 1


def carry_obj_effects(item: Item) -> None:
    """C: carry_obj_effects (src/invent.c 1186-1196): the side effects
    of CARRYING the item -- in C, the cursed-figurine transform
    timeout.  pyhack has no timers (no timeout.c), so this is the
    named hook that does nothing; the call site stays where C calls
    it (addinv)."""


__all__ = [
    "CONTAINED_SYM", "GOLD_SYM", "HANDS_SYM", "NOINVSYM",
    "addinv", "assigninvlet", "carry_obj_effects", "consume_obj_charge",
    "delobj", "freeinv", "invlet_basic", "invletter_value",
    "let_to_name", "obj_to_let", "reorder_invent", "useup", "useupall",
]
