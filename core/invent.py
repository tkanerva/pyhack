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
  ``let_to_name`` (the C names[] class table);
- the display group (the non-menu half, phase F): ``doname`` /
  ``worn_suffix`` (the reduced objnam.c naming -- phase C replaces
  them), ``xprname``, ``display_inventory`` (the `i` list and its
  per-class subsets), ``is_inuse`` / ``display_in_use`` (the `*`
  list), ``money_cnt`` / ``currency`` / ``doprgold`` (the `$` line).
  All of them are pure readings of the pack: a listing is a RENDER and
  costs no turn (C: ECMD_OK).

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

from typing import List, Optional

from .hacklib_inflection import makeplural
from .objects import (DEF_OC_SYMS, MAXOCLASSES, ObjClass, W_ACCESSORY,
                      W_AMUL, W_ARMOR, W_RINGL, W_RINGR, W_WEAPONS)
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


# ------------------------------------------------------------
# The display group (C: the non-menu half of src/invent.c's display
# functions -- PLAN-INVENT.md phase F)
# ------------------------------------------------------------
#
# A listing is a RENDER.  Every function below reads the pack and
# returns text; none touches the world, so the console can answer the
# `i` family of commands and the turn is not spent (C: ddoinv & co.
# return ECMD_OK, and core.step has a matching early return).  The menu
# half of C's display_pickinv (selecting an entry to act on it, the
# persistent-inventory window) is not here: the console has no window
# and there is nothing to select yet (phases F/G).
#
# `doname` is the reduced objnam.c slice.  The naming module proper
# (phase C) brings the article ("a sword" / "an apple"), the BUC
# prefix, the +N and the erosion words; until it lands, `Item.name` is
# the whole noun phrase (the hand-written demo kit) and every line
# below reads it.  `doname` is the one function phase C replaces.

# C: options.c def_inv_order -- flags.inv_order, the class order the
# sortpack display groups by (coins, then the pack's likely contents).
# options.c is unported, so the default (sortpack On, include/optlist.h)
# is fixed here.
INV_ORDER = (
    int(ObjClass.COIN), int(ObjClass.AMULET), int(ObjClass.WEAPON),
    int(ObjClass.ARMOR), int(ObjClass.FOOD), int(ObjClass.SCROLL),
    int(ObjClass.SPBOOK), int(ObjClass.POTION), int(ObjClass.RING),
    int(ObjClass.WAND), int(ObjClass.TOOL), int(ObjClass.GEM),
    int(ObjClass.ROCK), int(ObjClass.BALL), int(ObjClass.CHAIN),
)


def currency(amount: int) -> str:
    """C: currency (src/objnam.c 4204-4206): the money noun.  It
    belongs to the objnam slice (phase C); it lives here while
    ``doprgold`` is its only caller."""
    return "zorkmid" if amount == 1 else "zorkmids"


def worn_suffix(mon: Monster, item: Item) -> str:
    """The tail C's xname appends to an item that is in use: the
    ``(being worn)`` / ``(on left hand)`` / ``(wielded)`` wording of
    src/objnam.c (the reduced slice; phase C owns the full set).

    The hero's wielded weapon is still the bare ``Monster.wielded`` id
    rather than the ``W_WEP`` bit (PLAN-DROP.md phase C moves it), so
    both are read: an item is wielded when either says so.
    """
    mask = item.owornmask
    if mask & W_ARMOR:
        return " (being worn)"
    if mask & W_AMUL:
        return " (around neck)"
    if mask & W_RINGL:
        return " (on left hand)"
    if mask & W_RINGR:
        return " (on right hand)"
    if (mask & W_WEAPONS) or mon.wielded == item.id:
        # C: "(weapon in right hand)" / "(alternate weapon; not wielded)";
        # the handedness-free "(wielded)" is the plan's simplification
        # (there is no left/right hand in the subset)
        return " (wielded)"
    return ""


def doname(mon: Monster, item: Item, quan: int = 0) -> str:
    """C: doname (src/objnam.c) -- the item's name as one line shows
    it: the stack count when there is one (C: "3 arrows"), then the
    worn / wielded suffix.

    ``quan`` overrides the item's own count for a partial stack, the
    way C's ``prinv`` hands a count to ``xprname`` (which temporarily
    writes ``obj->quan``); 0 means "use ``Item.quan``".

    The rest of C's doname -- the article, the BUC prefix ("a cursed"),
    the enchantment ("+1"), the erosion words -- is PLAN-INVENT.md
    phase C's ``core/objnam.py``.  Nothing here draws from the rng or
    writes to the item: ``xname`` must stay a pure function of the
    item plus the object tables (PLAN-INVENT.md §6).
    """
    count = quan if quan else item.quan
    name = item.name
    if count > 1:
        name = f"{count} {makeplural(name)}"
    return name + worn_suffix(mon, item)


def xprname(mon: Monster, item: Item, let: str,
            txt: Optional[str] = None, dot: bool = False,
            quan: int = 0) -> str:
    """C: xprname (src/invent.c 2936-2995) -- the ``<let> - <text>.``
    line every inventory listing (and every "you pick up" message) is
    built from.  ``txt`` replaces the item's own name; ``dot`` appends
    C's period.

    C's ``cost`` branch (the unpaid-item column of the Iu/Ix listings)
    needs the shop; it is dropped with PLAN-SPECIAL-ROOMS, and the
    ``CONTAINED_SYM`` / ``HANDS_SYM`` pseudo-letters come with the
    container and wield work.
    """
    text = doname(mon, item, quan) if txt is None else txt
    return let + " - " + text + ("." if dot else "")


def is_inuse(mon: Monster, item: Item) -> bool:
    """C: is_inuse (src/invent.c 2166-2170): a carried item the hero
    is wearing or wielding.  C also counts an active lamp / leash
    (``tool_being_used``), which needs the tool port."""
    return (bool(item.owornmask & (W_ARMOR | W_ACCESSORY | W_WEAPONS))
            or mon.wielded == item.id)


def _class_rank(oclass: int) -> int:
    """The sortpack sort key of a class (C: sortloot's ``orderclass``,
    the position in ``flags.inv_order``); a class outside the order
    sorts after the listed ones, in class-number order (C's
    ``k = 1 + strlen(classorder)`` fallback)."""
    if oclass in INV_ORDER:
        return INV_ORDER.index(oclass)
    return len(INV_ORDER) + oclass


def _class_sym(item: Item) -> str:
    """C: def_oc_syms[(int) otmp->oclass].sym -- the class glyph the
    `lets` filter is written in."""
    if 0 <= item.oclass < len(DEF_OC_SYMS):
        return DEF_OC_SYMS[item.oclass].sym
    return ""


def _display_lines(mon: Monster, items: List[Item]) -> List[str]:
    """The body of the display: group the items by class in the
    sortpack order, print C's ``let_to_name`` heading for each class,
    then one ``xprname`` line per item, letters ascending.

    A copy is sorted, never ``Monster.inventory`` itself: the pack is
    kept in invlet order by ``addinv`` and the display must not
    re-order it (C: sortloot returns a loot array, and unsortloot puts
    the chain back).
    """
    out: List[str] = []
    for oclass in sorted({it.oclass for it in items}, key=_class_rank):
        out.append(let_to_name(oclass))
        group = [it for it in items if it.oclass == oclass]
        for it in sorted(group, key=lambda i: invletter_value(i.invlet)):
            out.append(xprname(mon, it, obj_to_let(it)))
    return out


def display_inventory(mon: Monster, lets: str = "") -> List[str]:
    """C: display_inventory (src/invent.c 3473-3499) through the
    non-menu path of ``display_pickinv`` (3098-3464): the `i` list.

    ``lets`` is a string of CLASS GLYPHS -- C's "list all objects with
    object classes that match the order in lets" (the ``)` `[` `"` `=`
    `(` refresh commands): "" (or None in C) lists the whole pack.

    The two empty answers are C's own: ``Not carrying anything.`` from
    ``display_pickinv`` and ``You have no such objects.`` from
    ``dotypeinv``.
    """
    items = [it for it in mon.inventory
             if not lets or _class_sym(it) in lets]
    if not items:
        return ["You have no such objects." if lets
                else "Not carrying anything."]
    return _display_lines(mon, items)


def display_in_use(mon: Monster) -> List[str]:
    """C: doprinuse (src/invent.c 4789-4809) -- the `*` command: the
    items the hero is wearing or wielding, in the same listing shape.
    """
    items = [it for it in mon.inventory if is_inuse(mon, it)]
    if not items:
        return ["You are not wearing or wielding anything."]
    return _display_lines(mon, items)


def money_cnt(mon: Monster) -> int:
    """C: money_cnt (src/invent.c 1545-1554): the gold in the pack.
    A gold pile is ONE item whose ``quan`` is the amount, so this is a
    sum over the coin stacks (C: plus carried containers --
    ``hidden_gold``, phase E)."""
    return sum(it.quan for it in mon.inventory
               if it.oclass == int(ObjClass.COIN))


def doprgold(mon: Monster) -> str:
    """C: doprgold (src/invent.c 4553-4598), the verbose branch: the
    `$` command's wallet line.  The shop report and ``hidden_gold``
    (gold stashed in a carried container) are PLAN-SPECIAL-ROOMS /
    phase E."""
    money = money_cnt(mon)
    if not money:
        return "Your wallet is empty."
    return f"Your wallet contains {money} {currency(money)}."


__all__ = [
    "CONTAINED_SYM", "GOLD_SYM", "HANDS_SYM", "INV_ORDER", "NOINVSYM",
    "addinv", "assigninvlet", "carry_obj_effects", "consume_obj_charge",
    "currency", "delobj", "display_in_use", "display_inventory",
    "doname", "doprgold", "freeinv", "invlet_basic", "invletter_value",
    "is_inuse", "let_to_name", "money_cnt", "obj_to_let", "reorder_invent",
    "useup", "useupall", "worn_suffix", "xprname",
]
