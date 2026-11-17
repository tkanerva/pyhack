"""The shop system -- phases 4a (the stocked shop) and 4b (prices, the
bill, the Pay) of PLAN-SPECIAL-ROOMS.md.

A shop in pyhack is what 4a says it is: a room whose type is
``SHOPBASE + i`` (the ``i`` index into core.shknam_data.SHOPTYPES), a
shopkeeper standing just inside its door who knows the room (``Eshk``
on the monster, C: ``mextra->eshk``), and a floor stocked one object
per free square.  4b adds the billing half: you can walk in, take what
you like (it goes on the keeper's bill, core.shk.add_one_tobill), and
pay (the ``PayCommand``, core.shk.do_pay).  4c adds the police: leaving
with an unpaid bill is a robbery (``stolen_value`` -> ``eshk.robbed``,
the keeper turns hostile via ``rile_shk`` / ``hot_pursuit`` / the
``surcharge``), the keeper blocks the shop door while it is owed
something (``block_door``), an item whose cost changes on the bill is
repriced (``alter_cost``, the EF_PAY half of the enchant scrolls), and
a dead hero's pack may pass to a keeper (``paybill`` / ``inherits``).
Only the shopkeeper's *dialogue* (4d: ``shk_talk`` / the ``shkname``
honorific / ``shk_move`` the keeper's movement) is not ported; each is
named where it would go.

C provenance (the spans this module owns, verified against
nethack_index/symbols):

  src/shknam.c  good_shopdoor() 581-624, shkinit() 627-692,
                stock_room_goodpos() 694-714, stock_room() 717-801,
                mkshobj_at() 453-483, get_shop_item() 828-839,
                nameshk() 486-554, veggy_item() 379-405,
                shkveg() 407-439, mkveggy_at() 442-450
  src/shk.c     inside_shop() 567-576 (the "which shop owns this
                square" question stock_room() asks about the door);
                the 4c police: stolen_value() 3775-3894, rob_shop()
                687-719, setpaid() 399-434, rile_shk() 1374-1390,
                hot_pursuit() 1461-1476, block_door() 5812-5843,
                alter_cost() 3258-3278, paybill() 2506-2592, inherits()
                2598-2701, addupbill() 495-507, check_credit() 1290-1307
                (the credit half of the robbery)
  src/mkroom.c  mkshop() -- the room pick and the shop-type roll; it
                lives in core.mkroom (it is a room handler), and calls
                back into this module only through stock_room()
  src/detect.c  cvt_sdoor_to_door() 1588-1604 -- ported to core.mklev
                (a terrain writer) and used by stock_room()'s door
                fix-up

The two-phase model (PLAN-SPECIAL-ROOMS.md trap 5): mkshop() *claims*
the room -- rtype, rlit, needfill -- and the end-of-level
``fill_special_room`` loop calls ``stock_room()`` with the claimed
room.  Nothing is created while the room is picked, so the rng stands
exactly where C leaves it.

What this phase deliberately leaves out (each named at its call site):

  - the tribute-system "special spot" (C: `svc.context.tribute.enabled`
    picks one stockable square for the novel of the Book of the Dead).
    pyhack has no tribute system, so the roll is not taken and
    ``mkshobj_at`` is always called with ``mkspecl=False`` -- there are
    no novels and no bookstock flag;
  - ``set_tin_variety(obj, HEALTHY_TIN)`` (the health-food store's
    tins): tins have no variety field yet, so such a tin is an
    ordinary tin;
  - the C ``newsym()`` calls of stock_room()'s door fix-up: the level
    is being *generated*, so nothing is on the screen and
    core.display.newsym has nothing to remember (the same reason
    mklev's door writers do not call it);
  - ``mon_learns_traps(shk, ALL_TRAPS)``: pyhack monsters have no
    per-monster trap knowledge (the priest's skip, core.priest);
  - ``saleable()`` (does this shop stock this item type) is the sell
    half, deferred; the 4b bill is keyed by the pickup, not by saleable;
  - the 4c police are IN (``stolen_value`` / ``rob_shop`` / ``rile_shk``
    / ``hot_pursuit`` / ``surcharge`` / ``alter_cost`` / ``block_door`` /
    ``paybill`` / ``inherits`` / ``setpaid``); what they do NOT reach:
    the Keystone Kop system (C: call_kops / makekops -- no kops in
    pyhack, the keeper chases alone), the keeper's movement / chase
    (``shk_move`` / the ``following`` follow, 4d -- ``following`` is
    carried and read by block_door but the keeper does not move yet),
    the cross-level keeper migration (C: migrate_to_level / home_shk),
    and the level-change / teleport leave (C: u_left_shop's newlev / the
    leavestring half) -- the robbery fires on a *tracked* leave
    (core.shk.track_shop, a hero move), so a scroll of teleportation out
    of a shop is a named escape the police do not see;
  - the 4d dialogue: ``shk_talk`` (the greeting, the "please pay" line),
    the ``shkname`` honorific (the messages use the bare name), and
    ``shk_move`` (the keeper's movement).

Named divergences (documented, not bugs):

  - ``nameshk()`` reads ``World.birth`` for C's ``ubirthday`` and the
    level number for C's ``ledger_no(&u.uz)`` (pyhack has one dungeon
    and no ledger), and the monster's numeric id for C's ``m_id``;
    the "already in use on this level" walk is the level's monster
    list.  The name-prefix gender codes ('-', '_', '+', '|', '=') are
    carried verbatim; interpreting them is ``shkname()`` (4d).
  - the minetown special case in ``nameshk`` (a lighting-store keeper
    in a town named Izchak) has no pyhack counterpart: there are no
    towns.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .engrave import E_DUST, make_engr_at
from .events import Event, MessageEvent
from .hacklib import distmin
from .invent import currency, delobj, money_cnt
from .makemon import makemon, mkclass, mkmonmoney, mongets, set_malign
from .mkobj import coarse_otype, is_ismnum, mkobj_at, mksobj_at
from .mondata import vegetarian
from .monst import MONS, NON_PM, PerMonst
from .monst_defs import PM_LICHEN, PM_SHOPKEEPER, S_MIMIC
from .objects import BASES, NUM_OBJECTS, OBJECTS, O, ObjClass
from .objects_defs import Material
from .place import enexto
from .shknam_data import (
    SHKGENERAL,
    SHKRINGS,
    SHKTOOLS,
    SHKWANDS,
    SHOPTYPES,
    VEGETARIAN_CLASS,
)
from .types import (
    NO_MM_FLAGS,
    NO_ROOM,
    ROOMOFFSET,
    BillEntry,
    DoorMask,
    Eshk,
    HungerState,
    Item,
    Map,
    MmFlags,
    Monster,
    Pos,
    Room,
    RoomType,
    TerrainType,
    World,
)

# ============================================================
# Small predicates
# ============================================================


def _mons_row(mndx: int) -> PerMonst:
    """A fixed mons[] row (the shopkeeper); the 383-row table is
    complete, so a None row is a table bug, not a runtime state."""
    row = MONS[mndx]
    assert row is not None, f"mons[{mndx}] is missing from the table"
    return row


def _id_number(mon: Monster) -> int:
    """The numeric part of a monster id -- the pyhack stand-in for C's
    ``monst->m_id`` (a long, unique per monster and stable for its
    lifetime).  ``nameshk()`` uses it as the per-shopkeeper variation
    seed, exactly as C does."""
    tail = mon.id.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def inside_shop(map_: Map, pos: Pos) -> int:
    """C: shk.c#inside_shop -- the room number of the shop square
    strictly inside a shop, or NO_ROOM.

    C tests ``levl[x][y].roomno`` (not the hero's ``u.ushops`` string):
    the square must not be a boundary square (``edge``) and its room
    must be a shop.  stock_room()'s door fix-up uses it to find which
    side of a locked door is the shop, and then engraves "Closed for
    inventory" on the *other* side -- the corridor square, where a
    passer-by can read it.
    """
    if not map_.in_bounds(pos):
        return NO_ROOM
    tile = map_.tile_at(pos)
    if tile.edge or tile.roomno < ROOMOFFSET:
        return NO_ROOM
    room = map_.room_at(pos)
    if room is None or room.rtype < RoomType.SHOPBASE:
        return NO_ROOM
    return tile.roomno


def shop_keeper(world: World, lev: int, roomno: int) -> Optional[Monster]:
    """C: shk.c#shop_keeper -- the shopkeeper tending room `roomno` on
    level `lev`.

    C walks the level's monster list looking for ``isshk`` with a
    matching ``eshk->shoproom``; here the flat world list is filtered by
    level, which is the same read.  ``Room.resident`` answers the same
    question for a room in hand without a scan (it is the id this
    function would find).
    """
    for mon in world.actors.values():
        if not mon.isshk or mon.eshk is None or mon.lev != lev:
            continue
        if mon.eshk.shoproom == roomno:
            return mon
    return None


def room_keeper(world: World, room: Room) -> Optional[Monster]:
    """The keeper of `room`, through ``Room.resident`` (C: the
    ``sroom->resident`` pointer; here an id, so it is one dict read)."""
    if room.resident is None:
        return None
    mon = world.actors.get(room.resident)
    return mon if mon is not None and mon.isshk else None


# ============================================================
# The shopkeeper's name (C: shknam.c nameshk)
# ============================================================


def nameshk(world: World, rng, shk: Monster, nlp, lev: int) -> str:
    """C: shknam.c#nameshk -- give the shopkeeper a name from the shop
    type's list, avoiding a name already in use on this level.

    The seed is C's: ``name_wanted = m_id + ledger_no - (nseed % 13) +
    (nseed % 5)`` with ``nseed = ubirthday / 257``, so the name varies
    from game to game without needing save/restore support.  Here the
    ledger number is the level number (one dungeon, no ledger) and
    ``ubirthday`` is ``World.birth``.

    The list is indexed straight when the seed lands inside it, and
    otherwise drawn with ``rn2`` -- C's two arms of the loop.  A name
    already carried by another shopkeeper on the level retries with a
    random pick; the tools list is always random (its names are the
    jokes), and a name that runs out of luck falls back to the general
    store's list and finally to Lucrezia / Dirk.

    The gender bits C's prefix characters encode are recorded on the
    monster (``Monster.female``) but not otherwise interpreted here --
    the "Mr." / "Ms." honorific belongs to ``shkname()`` (phase 4d).
    """
    name_wanted = _id_number(shk)
    nseed = world.birth // 257
    name_wanted += lev + (nseed % 13) - (nseed % 5)
    if name_wanted < 0:
        name_wanted += 13 + 5
    shk.female = bool(name_wanted & 1)

    names_avail = len(nlp)
    name_wanted %= names_avail
    shname = nlp[0]
    for _ in range(50):
        if nlp is SHKTOOLS:
            shname = SHKTOOLS[rng.rn2(names_avail)]
            shk.female = False  # reversed below for the '_' prefix
        elif name_wanted < names_avail:
            shname = nlp[name_wanted]
        else:
            i = rng.rn2(names_avail)
            if i != 0:
                shname = nlp[i - 1]
            elif nlp is not SHKGENERAL:
                nlp = SHKGENERAL  # try the general store's names
                names_avail = len(nlp)
                continue  # next `trycnt` iteration
            else:
                shname = "-Lucrezia" if shk.female else "+Dirk"
        if shname[0] in "_-":
            shk.female = True
        elif shname[0] in "|+":
            shk.female = False

        # is the name already in use on this level?
        if not _name_in_use(world, shk, shname, lev):
            break
        name_wanted = names_avail  # try a random name
    assert shk.eshk is not None  # the MM_ESHK of makemon allocated it
    shk.eshk.shknam = shname
    return shname


def _name_in_use(world: World, shk: Monster, shname: str, lev: int) -> bool:
    """The C conflict walk: another shopkeeper on this level already
    carries `shname` (C compares ``ESHK(mtmp)->shknam``)."""
    for mon in world.actors.values():
        if mon is shk or not mon.isshk or mon.lev != lev or not mon.alive:
            continue
        assert mon.eshk is not None
        if mon.eshk.shknam == shname:
            return True
    return False


# ============================================================
# The door the shopkeeper stands behind (C: shknam.c good_shopdoor)
# ============================================================


def good_shopdoor(map_: Map, room: Room) -> Optional[Tuple[int, Pos]]:
    """C: shknam.c#good_shopdoor -- the door a shopkeeper can be placed
    behind: the door square stepped one square towards the room's
    inside.

    Returns ``(index of that door in room.doors, the inside square)``,
    or None when no door of the room has an inside neighbour (C
    answers -1).  A rectangular room moves the door along the wall it
    sits in; an irregular one moves it to the adjacent square the flood
    fill gave the room (C: the ``roomno`` + ``edge`` test).  A shop is
    picked with exactly one door (mkshop), so the index is the same as
    C's ``fdoor`` in the normal flow -- the list walk is kept because
    the special-level loader can build a room with more.
    """
    rmno = map_.room_of(room)
    for i, (x, y) in enumerate(room.doors):
        sx, sy = x, y
        if room.irregular:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                cand = (sx + dx, sy + dy)
                if not map_.in_bounds(cand):
                    continue
                tile = map_.tile_at(cand)
                if not tile.edge and tile.roomno == rmno:
                    return (i, cand)
            continue
        if sx == room.lx - 1:
            sx += 1
        elif sx == room.hx + 1:
            sx -= 1
        elif sy == room.ly - 1:
            sy += 1
        elif sy == room.hy + 1:
            sy -= 1
        else:
            continue
        return (i, (sx, sy))
    return None


# ============================================================
# The shopkeeper (C: shknam.c shkinit)
# ============================================================


def init(
    world: World, rng, map_: Map, room: Room, shop_index: int, lev: int
) -> Optional[int]:
    """C: shknam.c#shkinit -- put a shopkeeper in the room and fill in
    its ``Eshk``.

    The order is C's, draw for draw: the door square (good_shopdoor),
    the rloc() insurance for a monster already standing there,
    ``makemon(PM_SHOPKEEPER, MM_ESHK)``, the peaceful / shopkeeper
    flags, ``set_malign``, the eshk fields (shoproom, shoptype, shd,
    shk, shoplevel), the initial capital ``1000 + 30 * rnd(100)``
    through mkmonmoney, the two ``mongets`` gifts (a touchstone for the
    jewellers; a scroll of charging for the tools / wands shops, half
    the jewellers and a fifth of the general stores), and finally
    ``nameshk``.

    Returns the index of the door the keeper stands behind (C returns
    it), or None when the room has no usable door or no shopkeeper
    could be made -- C's -1, which makes stock_room() give up and leave
    the room empty.
    """
    shp = SHOPTYPES[shop_index]
    found = good_shopdoor(map_, room)
    if found is None:
        return None  # C: -1, "Where is shopdoor?"
    di, (sx, sy) = found

    occupant = world.monster_at_lev(lev, (sx, sy))
    if occupant is not None:
        # C: rloc(m_at(sx, sy), RLOC_NOMSG) -- insurance
        spot = enexto(world, rng, map_, lev, (sx, sy), occupant.mdata)
        if spot is not None:
            occupant.pos = spot

    shk = makemon(
        world,
        rng,
        _mons_row(PM_SHOPKEEPER),
        (sx, sy),
        MmFlags.ESHK,
        map_=map_,
        lev=lev,
        in_mklev=True,
    )
    if shk is None:
        return None
    eshk = shk.eshk
    assert eshk is not None  # the MM_ESHK above allocated it

    shk.isshk = True
    shk.mpeaceful = True
    set_malign(world, shk)  # C: mpeaceful may have changed
    shk.sleeping = 0
    # C: mon_learns_traps(shk, ALL_TRAPS) -- no per-monster trap
    # knowledge in pyhack (the call is named, not ported)
    eshk.shoproom = map_.room_of(room)
    room.resident = shk.id
    eshk.shoptype = int(room.rtype)
    eshk.shoplevel = lev
    eshk.shd = room.doors[di]
    eshk.shk = (sx, sy)
    mkmonmoney(world, rng, shk, 1000 + 30 * rng.rnd(100))  # initial capital
    if shp.shknms is SHKRINGS:
        mongets(world, rng, shk, int(O.TOUCHSTONE))
    if (
        shp.shknms is SHKTOOLS
        or shp.shknms is SHKWANDS
        or (shp.shknms is SHKRINGS and rng.rn2(2))
        or (shp.shknms is SHKGENERAL and rng.rn2(5))
    ):
        mongets(world, rng, shk, int(O.SCR_CHARGING))
    nameshk(world, rng, shk, shp.shknms, lev)
    return di


# ============================================================
# The stock (C: shknam.c stock_room_goodpos / mkshobj_at / stock_room)
# ============================================================


def stock_goodpos(map_: Map, room: Room, rmno: int, door: Pos, pos: Pos) -> bool:
    """C: shknam.c#stock_room_goodpos -- may this square be stocked?

    C's rules, in C's order: an irregular room rejects its boundary
    squares, other rooms' squares and the ring around the shop door
    (``distmin <= 1``); a rectangular one rejects the whole side of the
    room the door stands on (the ``sx == lx && door.x == sx - 1``
    family of tests, which empties the door row); and either way only a
    floor-type square (C: ``IS_ROOM``, i.e. ``typ >= ROOM``) can hold
    stock.  Monsters are *not* excluded -- the shopkeeper's own square
    gets an object too (the mimic roll checks MON_AT, not this).
    """
    sx, sy = pos
    dx, dy = door
    if room.irregular:
        tile = map_.tile_at(pos)
        if tile.edge or tile.roomno != rmno or distmin(pos, door) <= 1:
            return False
    elif (
        (sx == room.lx and dx == sx - 1)
        or (sx == room.hx and dx == sx + 1)
        or (sy == room.ly and dy == sy - 1)
        or (sy == room.hy and dy == sy + 1)
    ):
        return False
    if map_.tile_at(pos).typ < TerrainType.ROOM:
        return False
    return True


def get_shop_item(rng, shop_index: int) -> int:
    """C: shknam.c#get_shop_item -- roll the shop's item kind: a
    positive ``itype`` is an object CLASS, a negative one a specific
    object type (C's unary-minus convention), and the health-food
    store's ``VEGETARIAN_CLASS`` is the pseudo-class (a class value
    that does not exist in objects[]).

    The walk is C's: ``rnd(100)`` then subtract each ``iprob`` until it
    is spent.  The trailing zero-probability slots keep the index from
    running off the array, exactly as in C.
    """
    shp = SHOPTYPES[shop_index]
    j = rng.rnd(100)
    i = 0
    while True:
        j -= shp.iprobs[i][0]
        if j <= 0:
            break
        i += 1
    return shp.iprobs[i][1]


def veggy_item(obj: Optional[Item], otyp: int = 0) -> bool:
    """C: shknam.c#veggy_item -- is an object (or an object *type*)
    vegetarian?

    A FOOD_CLASS object whose material is VEGGY, or an egg.  A tin is
    vegetarian when it is the spinach kind (``spe == 1``: 0 = empty,
    1 = spinach) and the type-only call cannot know, so a tin / corpse
    is judged by its corpsenm -- which C seeds with PM_LICHEN for the
    type-only call ("veggy standin"), the same trick here.

    Called with ``obj is None`` for a type and a real object for the
    billing half's ``saleable()``; only the type arm is live in 4a.
    """
    if obj is not None:
        otyp = obj.otyp
        oclass = obj.oclass
        corpsenm = obj.corpsenm
    else:
        oclass = int(OBJECTS[otyp].oclass)
        corpsenm = PM_LICHEN

    if oclass == int(ObjClass.FOOD):
        if OBJECTS[otyp].material == Material.VEGGY or otyp == int(O.EGG):
            return True
        if otyp == int(O.TIN) and corpsenm == NON_PM:
            # implies obj is non-NULL (the type-only call is seeded
            # with PM_LICHEN)
            return obj is not None and obj.spe == 1
        if otyp in (int(O.TIN), int(O.CORPSE)):
            if not is_ismnum(corpsenm):
                return False
            ptr = MONS[corpsenm]
            return ptr is not None and vegetarian(ptr)
    return False


def shkveg(rng) -> int:
    """C: shknam.c#shkveg -- a random vegetarian FOOD_CLASS object type
    (the health-food store's ``VEGETARIAN_CLASS``).

    The table walk collects the vegetarian rows with their ``oc_prob``,
    rolls ``rnd(total)`` and walks again, C's two passes.
    """
    oclass = int(ObjClass.FOOD)
    ok: List[int] = []
    maxprob = 0
    for i in range(BASES[oclass], NUM_OBJECTS):
        if int(OBJECTS[i].oclass) != oclass:
            break
        if veggy_item(None, i):
            ok.append(i)
            maxprob += OBJECTS[i].prob
    if maxprob < 1:
        # C panics here ("shkveg no veggy objects"); a table that lost
        # every vegetarian food row is a build error, not a game state
        raise RuntimeError("shkveg: no vegetarian food objects")
    prob = rng.rnd(maxprob)
    j = 0
    i = ok[0]
    while True:
        prob -= OBJECTS[i].prob
        if prob <= 0:
            break
        j += 1
        i = ok[j]
    return i


def mkveggy_at(world: World, rng, pos: Pos, lev: int) -> Item:
    """C: shknam.c#mkveggy_at -- a vegetarian food object, placed.

    C also marks a tin as the healthy variety (``set_tin_variety(obj,
    HEALTHY_TIN)``); tins carry no variety field in pyhack yet, so that
    fix-up is a named skip and the tin is an ordinary one.
    """
    return mksobj_at(world, rng, shkveg(rng), pos, lev, init=True, artif=True)


def mkshobj_at(
    world: World,
    rng,
    map_: Map,
    shop_index: int,
    pos: Pos,
    lev: int,
    mkspecl: bool = False,
) -> None:
    """C: shknam.c#mkshobj_at -- make the object for one shop square.

    C's order: the tribute novel (``mkspecl`` -- pyhack has no tribute
    system, so it is a named skip and the flag is never true), then the
    mimic roll (``rn2(100) < depth && !MON_AT && mkclass(S_MIMIC)``,
    short-circuited exactly as C does, so the rng stream does not
    drift), and otherwise the shop's item kind through
    ``get_shop_item``: the vegetarian pseudo-class, a specific object
    type (the negative ``itype``), or a whole object class.
    """
    if mkspecl:
        # C: the TRIBUTE build's novel for the rare-books / bookstore
        # shops.  pyhack has no tribute system at all (no novel object,
        # no bookstock flag), so the branch is a named skip.
        return
    if rng.rn2(100) < lev and world.monster_at_lev(lev, pos) is None:
        mimic = mkclass(world, rng, S_MIMIC, 0)
        if (
            mimic is not None
            and makemon(
                world,
                rng,
                mimic,
                pos,
                NO_MM_FLAGS,
                map_=map_,
                lev=lev,
                in_mklev=True,
            )
            is not None
        ):
            return  # a mimic took the square
    atype = get_shop_item(rng, shop_index)
    if atype == VEGETARIAN_CLASS:
        mkveggy_at(world, rng, pos, lev)
    elif atype < 0:
        mksobj_at(world, rng, -atype, pos, lev, init=True, artif=True)
    else:
        mkobj_at(world, rng, atype, pos, lev, artif=True)


def stock_room(world: World, rng, map_: Map, room: Room, lev: int) -> None:
    """C: shknam.c#stock_room -- the shopkeeper, the door fix-up and one
    object per stockable square.

    Called by ``fill_special_room`` at the end of makelevel (C:
    ``stock_room(croom->rtype - SHOPBASE, croom)``), never by mkshop --
    that split is what keeps the rng where C leaves it (PLAN-SPECIAL-
    ROOMS.md trap 5).

    The order is C's: the shopkeeper first (shkinit -- a room with no
    usable door leaves the shop empty), then the doorway repair (a
    doorway without a door becomes an open door; a secret door becomes
    a real one; a trapped door becomes locked), then the "Closed for
    inventory" engraving for a locked door, then the stock loop.  The
    engraving needs inside_shop() to tell the shop side from the
    corridor side: C steps the engraving square *away* from the shop
    (into the corridor, where a customer reads it) and forces that
    square to floor terrain when it is neither ROOM nor CORR.

    C's tribute "special spot" scan (the extra `rnd(stockcount)` draw)
    is not taken: no tribute system, so every square is stocked
    normally (mkspecl is always false).
    """
    # local imports: mklev imports mkroom, which imports this module
    from .mklev import cvt_sdoor_to_door, set_levltyp

    shop_index = int(room.rtype) - int(RoomType.SHOPBASE)
    if not 0 <= shop_index < len(SHOPTYPES):
        raise ValueError(f"not a shop room type: {room.rtype!r}")
    rmno = map_.room_of(room)

    di = init(world, rng, map_, room, shop_index, lev)
    if di is None:
        return

    # --- the doorway: no doorways without doors, no trapped doors ---
    # C reads svd.doors[sroom->fdoor] -- the room's FIRST door -- for
    # this fix-up, and svd.doors[sh] (shkinit's door) for the stock
    # loop; a shop has one door, so the two agree (mkshop).
    door = room.doors[0]
    tile = map_.tile_at(door)
    if tile.typ == TerrainType.DOOR and not tile.door_mask:
        tile.door_mask = DoorMask.ISOPEN  # C: D_NODOOR -> D_ISOPEN
        # C: newsym(sx, sy) -- the level is not on screen yet
    if tile.typ == TerrainType.SDOOR:
        cvt_sdoor_to_door(map_, door)  # C: .typ = DOOR
    if tile.door_mask & DoorMask.TRAPPED:
        tile.door_mask = DoorMask.LOCKED

    if tile.door_mask == DoorMask.LOCKED:
        m, n = door
        if inside_shop(map_, (door[0] + 1, door[1])):
            m -= 1
        elif inside_shop(map_, (door[0] - 1, door[1])):
            m += 1
        if inside_shop(map_, (door[0], door[1] + 1)):
            n -= 1
        elif inside_shop(map_, (door[0], door[1] - 1)):
            n += 1
        make_engr_at(map_, m, n, "Closed for inventory", E_DUST)
        spot = map_.tile_at((m, n))
        if spot.typ not in (TerrainType.CORR, TerrainType.ROOM):
            # C: Is_special(&u.uz) || *in_rooms(m, n, 0) ? ROOM : CORR
            # -- there are no special levels here, so the room test is
            # the whole answer
            target = (
                TerrainType.ROOM
                if map_.room_at((m, n)) is not None
                else TerrainType.CORR
            )
            set_levltyp(map_, m, n, target)

    # --- one object per stockable square (C's row-major double loop) ---
    stock_door = room.doors[di]
    for sx in range(room.lx, room.hx + 1):
        for sy in range(room.ly, room.hy + 1):
            if stock_goodpos(map_, room, rmno, stock_door, (sx, sy)):
                mkshobj_at(world, rng, map_, shop_index, (sx, sy), lev)

    # C's Orcus-town "get rid of shopkeepers" hack has no counterpart
    # (there is no Orcus level).
    map_.flags.has_shop = True


# ============================================================
# Prices (PLAN-SPECIAL-ROOMS.md phase 4b; C: shk.c getprice / get_cost)
# ============================================================

# C: BILLSZ (mextra.h 114) -- a keeper's bill holds at most this many
# entries; the 201st pickup in a shop is free.
BILLSZ = 200


def _type_name_known(world: World, otyp: int) -> bool:
    """C: objects[otyp].oc_name_known -- the type's name is known (either
    pre-known in the table or discovered this game; the per-game half is
    world.obj_tables.name_known, the same read core.rings uses)."""
    state = world.obj_tables
    if state is not None and otyp in state.name_known:
        return True
    return bool(OBJECTS[otyp].name_known)


def getprice(world: World, item: Item, shk_buying: bool) -> int:
    """C: shk.c#getprice (4339-4379) -- the BASE price of an object; no
    RNG.  `shk_buying` is True when the shopkeeper is buying (the hero
    selling); the buy side (the hero buying) passes False.

    The base is `objects[otyp].oc_cost`, then C's five-branch switch:

    - FOOD: + the corpse subject's price adjustment (pyhack has no
      monster corpses, so 0); the hunger multiplier -- when the hero is
      at least HUNGRY (uhs >= 2) and BUYING (not shk_buying) the price
      is multiplied by `uhs` (2..6, core.hunger's HungerState); a
      partly-eaten piece (oeaten) is worth 0.
    - WAND: a cancelled / empty wand (spe == -1) is worth 0.
    - POTION: plain water (POT_WATER, neither blessed nor cursed) is 0.
    - ARMOR / WEAPON: an enchant bonus (spe > 0) adds 10 * spe.
    - TOOL: a candle (tallow / wax) younger than 20 * its cost is half.

    Artifacts (oartifact) take arti_cost and are quartered when the
    keeper is buying -- pyhack has no artifacts (oartifact is always 0),
    so the branch is a named no-op, kept for the shape.
    """
    tmp = OBJECTS[item.otyp].cost
    if item.oartifact:
        # C: tmp = arti_cost(obj); if (shk_buying) tmp /= 4 -- no
        # artifacts in pyhack (oartifact always 0): a named no-op
        pass
    oclass = item.oclass
    if oclass == int(ObjClass.FOOD):
        # C: tmp += corpsenm_price_adj(obj) -- pyhack has no monster
        # corpses, so the adjustment is 0
        hero = world.hero_or_none
        uhs = int(hero.uhs) if hero is not None else int(HungerState.NOT_HUNGRY)
        if uhs >= int(HungerState.HUNGRY) and not shk_buying:
            tmp *= uhs
        if item.oeaten:
            tmp = 0
    elif oclass == int(ObjClass.WAND):
        if item.spe == -1:
            tmp = 0
    elif oclass == int(ObjClass.POTION):
        if item.otyp == int(O.POT_WATER) and not item.blessed and not item.cursed:
            tmp = 0
    elif oclass in (int(ObjClass.ARMOR), int(ObjClass.WEAPON)):
        if item.spe > 0:
            tmp += 10 * item.spe
    elif oclass == int(ObjClass.TOOL):
        if (
            item.otyp in (int(O.TALLOW_CANDLE), int(O.WAX_CANDLE))
            and item.age < 20 * OBJECTS[item.otyp].cost
        ):
            tmp //= 2
    return tmp


def get_cost(world: World, item: Item, shkp: Optional[Monster]) -> int:
    """C: shk.c#get_cost (2898-3009) -- the price that goes on the bill
    (the buy side; add_one_tobill calls it).

    Starts from getprice(obj, FALSE) with the 0->5 floor, applies the
    un-ID'd surcharge (x4/3), then C's round-half-up combine, the
    <=0 -> 1 floor, and (for 4c) the anger surcharge.

    Named skips (the plan's 4b list): the glass-gem re-pricing (pyhack
    has no oc_material, so an un-ID'd glass gem takes the plain
    surcharge), the DUNCE_CAP / tourist-shirt x4/3 (no role system), the
    CHA table (no ability scores), and artifacts (oartifact always 0).

    The un-ID'd surcharge follows the plan's reading of C's
    `!dknown || !oc_name_known` arm (the 0->5 floor already ran, so a
    fresh, un-ID'd item is billed x4/3).
    """
    tmp = getprice(world, item, False)
    if not tmp:
        tmp = 5  # C: `if (!tmp) tmp = 5L` -- the 0->5 floor
    mult = 1
    div = 1
    if (not item.dknown) or (not _type_name_known(world, item.otyp)):
        # C: `else if (oid_price_adjustment(obj, obj->o_id) > 0)`: the
        # un-ID'd x4/3.  (C additionally gates it on o_id % 4 == 0;
        # the plan applies the surcharge on the !dknown arm, so a fresh
        # item is always billed up -- see PLAN-SPECIAL-ROOMS.md 4b.)
        mult *= 4
        div *= 3
    # C: the DUNCE_CAP / tourist x4/3 and the CHA table -- named skips
    # (no role system, no ability scores)
    # the combine, C's round-half-up, transcribed statement for
    # statement (a plain floor division disagrees at the .5 cases)
    tmp *= mult
    if div > 1:
        tmp = ((tmp * 10) // div + 5) // 10
    if tmp <= 0:
        tmp = 1
    if item.oartifact:
        tmp *= 4  # C: the artifact x4 -- never fires
    if shkp is not None and shkp.eshk is not None and shkp.eshk.surcharge:
        # C: the anger surcharge (4c sets the flag; the line is ported
        # now, it is harmless while surcharge stays False)
        tmp += (tmp + 2) // 3
    return tmp


# ============================================================
# The bill (PLAN-SPECIAL-ROOMS.md 4b; C: shk.c's bill_x machinery)
# ============================================================


def onbill(item: Item, eshk: Optional[Eshk]) -> Optional[BillEntry]:
    """C: shk.c#onbill (1148-1167) -- the bill entry for `item` on
    `eshk`'s bill, or None.  C walks the array comparing bo_id; here it
    is a dict lookup by item id."""
    if eshk is None:
        return None
    return eshk.bill.get(item.id)


def inhishop(world: World, shkp: Monster) -> bool:
    """C: shk.c#inhishop (1038-1048) -- is this shopkeeper "at home"?

    The keeper's shop level is the current level AND the keeper's square
    sits inside the shop room it keeps (inside_shop at the keeper's pos
    answering eshk.shoproom).  A dead / moved / cross-level keeper is
    not at home, so nothing it stocked is billable.
    """
    eshkp = shkp.eshk
    if eshkp is None:
        return False
    if eshkp.shoplevel != world.lev:
        return False
    return inside_shop(world.map, shkp.pos) == eshkp.shoproom


def billable(world: World, shkp: Optional[Monster], item: Item) -> bool:
    """C: shk.c#billable (3472-3508) -- does this shopkeeper bill for
    this item?

    The keeper must exist and be at home (inhishop); the item must not be
    already on the bill, not a partly-eaten food (FOOD + oeaten), and not
    no_charge (the hero's own gear).  C's container arm (a no_charge
    container whose contents are still billable) is a named skip (the
    demo has no containers).
    """
    if shkp is None or shkp.eshk is None:
        return False
    if not inhishop(world, shkp):
        return False
    if onbill(item, shkp.eshk) is not None:
        return False
    if item.oclass == int(ObjClass.FOOD) and item.oeaten:
        return False
    if item.no_charge:
        return False
    return True


def add_one_tobill(world: World, shkp: Optional[Monster], item: Item) -> List[Event]:
    """C: shk.c#add_one_tobill (3330-3384) -- put `item` on `shkp`'s
    bill.

    Not billable -> free (no entry, no message).  A full bill
    (billct >= BILLSZ) -> "You got that for free!" (no entry).  Otherwise
    the entry is added -- price = get_cost, bquan = item.quan, name =
    item.name -- and item.unpaid is set.  C does NOT merge entries (one
    per item id), so there is no merging here; the glob and
    record_price_quote arms are named skips.
    """
    if shkp is None or shkp.eshk is None:
        return []
    eshkp = shkp.eshk
    if not billable(world, shkp, item):
        return []  # the keeper does not want it: free
    if eshkp.billct >= BILLSZ:
        return [MessageEvent("You got that for free!")]
    eshkp.bill[item.id] = BillEntry(
        price=get_cost(world, item, shkp), bquan=item.quan, name=item.name
    )
    eshkp.billct = len(eshkp.bill)
    item.unpaid = True
    return []


def sub_one_frombill(eshk: Eshk, item: Item) -> None:
    """C: shk.c#sub_one_frombill (3683-3711) -- take `item` off the bill.

    A paid item: the entry is deleted and item.unpaid cleared.  A
    partly-used-up item (bquan > quan -- C splits the difference into a
    dummy object that stays on the bill) is marked useup on the entry:
    the debt survives in shop_debt and the name is preserved for the pay
    message (the item itself is deleted by the useup path, not here).  An
    item not on the bill but flagged unpaid gets the flag cleared (C's
    impossible()).
    """
    entry = eshk.bill.get(item.id)
    if entry is None:
        if item.unpaid:
            item.unpaid = False  # C: impossible("not on bill"), clear
        return
    if not entry.useup and entry.bquan > item.quan:
        # C's split: the used-up part stays billed as useup; the item
        # (the remaining part) is deleted by the caller
        entry.useup = True
        return
    eshk.bill.pop(item.id, None)
    eshk.billct = len(eshk.bill)
    item.unpaid = False


def shop_debt(eshk: Eshk) -> int:
    """C: shk.c#shop_debt (989-999) -- what the hero owes this keeper:
    debit + the sum of price * bquan over the bill.

    In the demo debit stays 0 (the bill IS the debt; C's debit channel is
    for used-up items and borrowed gold, and pyhack counts used-up entries
    on the bill instead), so this is the bill total.
    """
    debt = eshk.debit
    for entry in eshk.bill.values():
        debt += entry.price * entry.bquan
    return debt


def costly_spot(world: World, x: int, y: int) -> bool:
    """C: shk.c#costly_spot (5370-5384) -- may an item on this square
    cost money?

    The level has a shop; the square is strictly inside a shop whose
    keeper is at home (inhishop); and the square is not the keeper's own
    (a keeper stocking its own counter is not a sale).
    """
    if not world.map.flags.has_shop:
        return False
    roomno = inside_shop(world.map, (x, y))
    if roomno == NO_ROOM:
        return False
    shkp = shop_keeper(world, world.lev, roomno)
    if shkp is None or not inhishop(world, shkp):
        return False
    eshkp = shkp.eshk
    assert eshkp is not None  # the MM_ESHK of makemon allocated it
    return (x, y) != eshkp.shk


# ============================================================
# The police (PLAN-SPECIAL-ROOMS.md phase 4c; C: shk.c's robbery,
# anger, door-block and death-inheritance machinery)
# ============================================================


def _shk_bare_name(eshkp: Eshk) -> str:
    """The shopkeeper's name without the gender-prefix code (the
    '-' / '_' / '+' / '|' / '=' character).  The honorific (Mr. / Ms.)
    is ``shkname()`` (4d); until then the bare name is what the messages
    use (do_pay's closing line, the door block, the robbery)."""
    name = eshkp.shknam
    if name and name[0] in "-_+|=":
        name = name[1:]
    return name


def addupbill(eshkp: Eshk) -> int:
    """C: shk.c#addupbill (495-507) -- the bill total: the sum of
    price * bquan over the entries.  The debit is added by the callers,
    as in C (``addupbill + eshk->debit``)."""
    return sum(entry.price * entry.bquan for entry in eshkp.bill.values())


def stolen_value(world: World, shkp: Monster) -> int:
    """C: shk.c#stolen_value (3775-3894), reduced to the 4b model where
    the bill IS the unpaid goods: the value the hero owes this keeper is
    the bill total (the debit plus price * bquan).  C's per-item sum
    (get_pricing_units * get_cost for each unpaid obj, the container /
    gold halves) collapses to the bill total because 4b bills every
    picked item at get_cost the moment it is taken."""
    eshkp = shkp.eshk
    assert eshkp is not None  # the MM_ESHK of makemon allocated it
    return shop_debt(eshkp)


def setpaid(world: World, shkp: Monster) -> None:
    """C: shk.c#setpaid (399-434) -- settle the shopkeeper's account:
    the bill is cleared, the debit / credit / loan zeroed, and the
    ``unpaid`` mark lifted off every item that was on the bill (the
    goods are now either paid for or stolen -- either way they are no
    longer on a bill).

    The no_charge marks are left to track_shop (the enter / leave hooks
    own them); C clears them here too, but in the 4b model they are set
    and cleared on every shop crossing, so a setpaid in the middle of a
    shop would undo the next pickup's protection.
    """
    eshkp = shkp.eshk
    assert eshkp is not None
    for item_id in list(eshkp.bill.keys()):
        item = world.items.get(item_id)
        if item is not None:
            item.unpaid = False
    eshkp.bill.clear()
    eshkp.billct = 0
    eshkp.debit = 0
    eshkp.credit = 0
    eshkp.loan = 0


def rile_shk(shkp: Monster) -> None:
    """C: shk.c#rile_shk (1374-1390) -- make the shopkeeper angry:
    ``NOTANGRY(shkp) = FALSE`` (mpeaceful IS the C NOTANGRY, so False is
    angry) and, once, the surcharge: the flag is set and every bill
    entry's price is marked up by (price + 2) // 3 (the same (tmp+2)/3
    the get_cost anger surcharge adds, applied to the billed prices so
    the bill and the pricing agree).
    """
    eshkp = shkp.eshk
    assert eshkp is not None
    shkp.mpeaceful = False  # C: NOTANGRY(shkp) = FALSE
    if not eshkp.surcharge:
        eshkp.surcharge = True
        for entry in eshkp.bill.values():
            entry.price += (entry.price + 2) // 3


def hot_pursuit(world: World, shkp: Monster) -> None:
    """C: shk.c#hot_pursuit (1461-1476) -- the shopkeeper gives chase:
    rile_shk (angry + the surcharge) and ``following = True`` (the keeper
    will pursue the hero; the chase itself is shk_move, 4d).

    C also clears no_charge for every floor item on the level (shopkeeper
    networking: a stolen item is not for sale in any shop); the 4b model
    scopes no_charge to the hero's own gear, so that cross-shop clear is
    a named skip (the pickup already bills per shop).
    """
    if not shkp.isshk:
        return
    rile_shk(shkp)
    eshkp = shkp.eshk
    assert eshkp is not None
    eshkp.following = True


def rob_shop(world: World, shkp: Monster) -> List[Event]:
    """C: shk.c#rob_shop (687-719) -- the hero left the shop with an
    unpaid bill: the bill becomes a debt, and if it is not covered by
    credit the shopkeeper is robbed and turns hostile.

    total = stolen_value (the bill total); the hero's credit is applied
    (a credit that covers the bill pays it off, no robbery); the bill is
    settled (setpaid); and when there is a net robbery the value goes to
    ``robbed``, the messages come out ("You escaped the shop without
    paying!" / "You stole N ... worth of merchandise.") and the keeper
    gives chase (hot_pursuit).  The Keystone Kops (C: call_kops) are a
    named skip -- the keeper chases alone.
    """
    eshkp = shkp.eshk
    assert eshkp is not None
    events: List[Event] = []
    total = stolen_value(world, shkp)
    if eshkp.credit >= total:
        events.append(
            MessageEvent(
                f"Your credit of {eshkp.credit} {currency(eshkp.credit)} "
                "is used to cover your shopping bill."
            )
        )
        total = 0  # C: the credit is cleared by setpaid
    else:
        events.append(MessageEvent("You escaped the shop without paying!"))
        total -= eshkp.credit
    setpaid(world, shkp)
    if not total:
        return events
    eshkp.robbed += total
    name = _shk_bare_name(eshkp)
    shop_name = SHOPTYPES[int(eshkp.shoptype) - int(RoomType.SHOPBASE)].name
    events.append(
        MessageEvent(
            f"You stole {total} {currency(total)} worth of merchandise "
            f"from {name} {shop_name}."
        )
    )
    hot_pursuit(world, shkp)
    return events


def block_door(world: World, x: int, y: int) -> Optional[MessageEvent]:
    """C: shk.c#block_door (5812-5843) -- the hero is trying to move
    onto the square (x, y); does the shopkeeper block the way?

    The square must be the shop's own door (the door tile's room is a
    shop and (x, y) is eshk.shd), the hero must be inside that shop, and
    the keeper must be alive, at home on its own square, with something
    to collect (debit, a bill or a robbery).  Then the keeper "blocks
    your way" and the move is refused.

    A closed shop (no keeper at home, or a dead keeper) does not block;
    the Invis half of C's message is a named skip (no invisibility).
    """
    tile = world.map.tile_at((x, y))
    if tile.typ != TerrainType.DOOR:
        return None
    roomno = tile.roomno
    if roomno < ROOMOFFSET:
        return None
    idx = roomno - ROOMOFFSET
    if not 0 <= idx < len(world.map.rooms):
        return None
    room = world.map.rooms[idx]
    if room.rtype < RoomType.SHOPBASE:
        return None
    if world.hero.in_shop != roomno:
        return None  # the hero is not in this shop (entering, not leaving)
    shkp = room_keeper(world, room)
    if shkp is None or not shkp.alive or not inhishop(world, shkp):
        return None  # a closed shop does not block
    eshkp = shkp.eshk
    assert eshkp is not None
    if shkp.pos != eshkp.shk:
        return None  # the keeper left its square
    if (x, y) != eshkp.shd:
        return None  # not the shop's door
    if not (eshkp.debit or eshkp.billct or eshkp.robbed):
        return None  # nothing owed, the way is open
    return MessageEvent(f"{_shk_bare_name(eshkp)} blocks your way!")


def alter_cost(world: World, item: Item, amt: int = 0) -> None:
    """C: shk.c#alter_cost (3258-3278) -- the item's cost changed (an
    enchantment, a trap) while it is on a shop bill: update the billed
    price.

    ``amt`` 0 means "reprice at the regular shop price" (get_cost); a
    positive amt forces that price; a negative amt forces abs(amt) even
    when it is below the old cost.  The price only goes UP unless amt is
    negative (C: ``if (new_price > bp->price || amt < 0)``), so a
    de-enchantment never refunds the bill.

    Called from the enchant-weapon / enchant-armor scroll effects (C: the
    EF_PAY half of read.c -- the scroll marks the billed item up) and a
    no-op when the item is not on a bill.
    """
    for mon in world.actors.values():
        if not mon.isshk or mon.eshk is None:
            continue
        entry = mon.eshk.bill.get(item.id)
        if entry is None:
            continue
        if amt == 0:
            new_price = get_cost(world, item, mon)
        elif amt < 0:
            new_price = -amt
        else:
            new_price = amt
        if new_price > entry.price or amt < 0:
            entry.price = new_price
        break  # C: done (one bill per item)


def _move_pack(world: World, hero: Monster, keeper: Monster) -> None:
    """The death-inheritance move of a whole pack (C: paybill's inherits
    taking gi.invent): every item the hero carries becomes the keeper's.
    The carrier is rewritten directly (a death event, not a pickup /
    drop) -- the conftest.assert_item_locations invariant (one place per
    item) still holds.
    """
    for item in list(hero.inventory):
        hero.inventory.remove(item)
        item.carrier = keeper.id
        keeper.inventory.append(item)


def paybill(world: World, croaked: int = 1) -> List[Event]:
    """C: shk.c#paybill (2506-2592) -- when the hero dies (croaked 1),
    quits (0) or escapes (-1), a shopkeeper may take the hero's
    possessions.

    The priority (C's): 1) the keeper of the shop the hero is inside who
    is owed something, 2) that keeper even when not owed, 3) any keeper
    the hero owes, 4) an angry / following keeper, 5) a local keeper.
    The highest-priority keeper takes first (inherits); the rest are
    settled (the C ``mongone`` of a non-local keeper is a named skip -- a
    dead hero's game is over).
    """
    if croaked < 0:
        return []  # C: escaped the dungeon, no inheritance
    events: List[Event] = []
    resident = creditor = hostile = localshk = None
    for mon in world.actors.values():
        if not mon.isshk or mon.eshk is None or not mon.alive:
            continue
        eshkp = mon.eshk
        local = eshkp.shoplevel == world.lev
        in_this = world.hero.in_shop == eshkp.shoproom
        if in_this:
            # C: the resident (preferring one who is owed money)
            if resident is None or eshkp.billct or eshkp.debit or eshkp.robbed:
                resident = mon
        elif eshkp.billct or eshkp.debit or eshkp.robbed:
            if creditor is None:
                creditor = mon
        elif eshkp.following or not mon.mpeaceful:
            if hostile is None:
                hostile = mon
        elif local:
            if localshk is None:
                localshk = mon
    first = resident or creditor or hostile or localshk
    if first is None:
        return events
    numsk = 1
    events += inherits(world, first, numsk, croaked)
    for mon in world.actors.values():
        if not mon.isshk or mon.eshk is None or not mon.alive:
            continue
        if mon is first:
            continue
        numsk += 1
        events += inherits(world, mon, numsk, croaked)
    return events


def inherits(
    world: World, shkp: Monster, numsk: int, croaked: int
) -> List[Event]:
    """C: shk.c#inherits (2598-2701), reduced -- does this shopkeeper
    take the hero's inventory when the hero dies?

    The first shopkeeper (numsk 1) decides: die in the shop with a
    peaceful keeper and nothing owed -> it gratefully inherits all; a
    debt / robbery -> it takes the owed amount (or all, when the debt
    exceeds the gold or the hero is in the shop), the gold moves to the
    keeper (money2mon), and a paid-in-full keeper is pacified.  A second
    shopkeeper (numsk > 1) only records its share (the first already took
    the pack -- C's "first-come already took everything").  The bill is
    settled (setpaid) either way.
    """
    eshkp = shkp.eshk
    assert eshkp is not None
    hero = world.hero
    events: List[Event] = []
    uinshop = hero.in_shop == eshkp.shoproom
    name = _shk_bare_name(eshkp)

    if numsk > 1:
        return events  # C: the first shopkeeper already took everything

    # die in the shop, a peaceful keeper, nothing owed: inherit all
    if (
        uinshop
        and inhishop(world, shkp)
        and not eshkp.billct
        and not eshkp.robbed
        and not eshkp.debit
        and shkp.mpeaceful
        and not eshkp.following
    ):
        if hero.inventory:
            _move_pack(world, hero, shkp)
            events.append(
                MessageEvent(
                    f"{name} gratefully inherits all your possessions."
                )
            )
        setpaid(world, shkp)
        return events

    loss = 0
    take = False
    if eshkp.billct or eshkp.debit or eshkp.robbed:
        if uinshop and inhishop(world, shkp):
            loss = addupbill(eshkp) + eshkp.debit
        if loss < eshkp.robbed:
            loss = eshkp.robbed
        take = True

    if eshkp.following or not shkp.mpeaceful or take:
        if hero.inventory:
            umoney = money_cnt(hero)
            if loss > umoney or not loss or uinshop:
                # C: take everything (the gold moves with the pack)
                eshkp.robbed = max(0, eshkp.robbed - umoney)
                _move_pack(world, hero, shkp)
                events.append(
                    MessageEvent(f"{name} takes all your possessions.")
                )
            elif loss > 0:
                # C: take the owed amount (money2mon(loss))
                _spend_gold(world, hero, loss)
                _give_gold(world, shkp, loss)
                # the shopkeeper has now been paid in full
                shkp.mpeaceful = True
                eshkp.following = False
                eshkp.robbed = 0
                events.append(
                    MessageEvent(
                        f"{name} takes the {loss} {currency(loss)} "
                        f"you owed it."
                    )
                )
    setpaid(world, shkp)
    return events


# ============================================================
# The hero's shop presence (C: check_special_room's u.ushops half)
# ============================================================


def track_shop(world: World, newpos: Pos) -> List[Event]:
    """C: check_special_room()'s shop half (hack.c) -- update the hero's
    `in_shop` and mark / clear no_charge on entering / leaving a shop.

    Called from core.step's room-entry hook on every hero move.  On entry
    the hero's carried non-coin gear is marked no_charge (your own gear is
    never billed, C 3094-3098); on leave the no_charge marks are cleared
    (unpaid items stay).  The 4c police: leaving with an unpaid bill is a
    robbery (rob_shop -- the bill becomes eshk.robbed and the keeper turns
    hostile).  The C entry / leave *dialogue* (the greeting, "please pay")
    is the shopkeeper's behaviour half (phase 4d); a level-change /
    teleport leave does not re-run this hook (a named skip, see the module
    docstring).
    """
    hero = world.hero
    old_in_shop = hero.in_shop
    new_in_shop = inside_shop(world.map, newpos)
    if new_in_shop == old_in_shop:
        return []
    events: List[Event] = []
    if new_in_shop == NO_ROOM:
        # leaving a shop: the no_charge marks are cleared (unpaid stays)
        for it in hero.inventory:
            it.no_charge = False  # C: clear_no_charge
        # the 4c police: an unsettled bill (billct / debit) is a robbery
        if old_in_shop != NO_ROOM:
            shkp = shop_keeper(world, world.lev, old_in_shop)
            if (
                shkp is not None
                and shkp.eshk is not None
                and inhishop(world, shkp)
                and (shkp.eshk.billct or shkp.eshk.debit)
            ):
                events += rob_shop(world, shkp)
        hero.in_shop = NO_ROOM
    else:
        hero.in_shop = new_in_shop  # entering a shop
        for it in hero.inventory:
            # C: your own gear is never billed (the !unpaid guard keeps
            # an already-stolen item off the no_charge mark)
            if it.oclass != int(ObjClass.COIN) and not it.unpaid:
                it.no_charge = True
    return events


# ============================================================
# The Pay command (PLAN-SPECIAL-ROOMS.md 4b; C: shk.c dopay, simplified
# to pay-all)
# ============================================================


def _spend_gold(world: World, mon: Monster, amount: int) -> int:
    """Reduce `mon`'s gold by `amount` (C: money2mon's source half).
    A gold pile is one item whose quan is the amount; reduce the
    stack(s) and delete a pile that empties.  Returns what could not be
    spent (0 when the pack held enough)."""
    remaining = amount
    for it in list(mon.inventory):
        if it.oclass != int(ObjClass.COIN) or remaining <= 0:
            continue
        take = min(it.quan, remaining)
        it.quan -= take
        remaining -= take
        if it.quan <= 0:
            delobj(world, it.id)
    return remaining


def _give_gold(world: World, mon: Monster, amount: int) -> None:
    """Add `amount` gold to `mon`, merging into its existing coin pile
    (C: money2mon's destination half).  The keeper always carries its
    4a capital as one pile, so the merge is the live path; the bare
    fallback builds a pile without an rng draw (4b is pure
    arithmetic)."""
    for it in mon.inventory:
        if it.oclass == int(ObjClass.COIN):
            it.quan += amount
            return
    gold = Item(
        id=world.new_id("gold"),
        otype=coarse_otype(int(O.GOLD_PIECE)),
        name="gold piece",
        otyp=int(O.GOLD_PIECE),
        oclass=int(ObjClass.COIN),
        quan=amount,
    )
    gold.carrier = mon.id
    gold.lev = mon.lev
    mon.inventory.append(gold)
    world.items[gold.id] = gold


def pay_debt(eshkp: Eshk, amount: int) -> None:
    """C: shk.c's pay arithmetic (the debit / loan / credit branches at
    3903-3931) -- settle `amount` against the keeper's account.

    Against a clean account (debit 0, the 4b case) the whole amount
    becomes credit: buying in this model establishes credit (the plan's
    4b override of the 4a "credit stays 0" note, which was true of
    stocking, not of paying).  The debit / loan branches are ported for
    4c (the robbery ledger) reuse.
    """
    if eshkp.debit >= amount:
        if eshkp.loan:
            if eshkp.loan > amount:
                eshkp.loan -= amount
            else:
                eshkp.loan = 0
        eshkp.debit -= amount
        return
    delta = amount - eshkp.debit
    eshkp.credit += delta
    if eshkp.debit:
        eshkp.debit = 0
        eshkp.loan = 0  # C: the debt (and the borrowed gold) is settled


def do_pay(world: World, rng) -> List[Event]:
    """C: shk.c#dopay (1758-2043), simplified to pay-all (the plan's
    4b): the hero pays every item on the bill of the shop they stand in.

    The named simplifications: C hunts for the nearest keeper and offers
    an itemized `y` menu; here the keeper is the room keeper of the shop
    room the hero stands in and every entry is paid at once.  No stashed
    gold, no loan channel, no `$` financial report.
    """
    hero = world.hero
    roomno = inside_shop(world.map, hero.pos)
    if roomno == NO_ROOM:
        return [MessageEvent("You are not in a shop.")]
    room = world.map.room_at(hero.pos)
    shkp = room_keeper(world, room) if room is not None else None
    if shkp is None:
        shkp = shop_keeper(world, world.lev, roomno)
    if shkp is None:
        return [MessageEvent("You are not in a shop.")]
    eshkp = shkp.eshk
    assert eshkp is not None  # the MM_ESHK of makemon allocated it
    total = shop_debt(eshkp)
    if total == 0:
        # C: the shopper_financial_report wording (1033)
        return [MessageEvent("You don't owe any gold here.")]
    money = money_cnt(hero)
    if money + eshkp.credit < total:
        # C 2495-2498, simplified (no menu, no partial pay -- named)
        return [
            MessageEvent(
                "You don't have enough gold to pay for the items on your bill."
            )
        ]
    events: List[Event] = []
    for item_id, entry in list(eshkp.bill.items()):
        ltmp = entry.price * entry.bquan  # C 2274
        # C 2314: "bought %s for %ld gold piece%s" (the money noun is
        # pyhack's currency(), the zorkmid)
        events.append(
            MessageEvent(
                f"You bought {entry.bquan} {entry.name} for "
                f"{ltmp} {currency(ltmp)}."
            )
        )
        pay_debt(eshkp, ltmp)
        _spend_gold(world, hero, ltmp)
        _give_gold(world, shkp, ltmp)
        item = world.items.get(item_id)
        if item is not None and not entry.useup:
            sub_one_frombill(eshkp, item)  # paid: off the bill
        else:
            eshkp.bill.pop(item_id, None)  # a useup entry: the item is gone
    eshkp.billct = len(eshkp.bill)
    # C 2029: the closing line (the Deaf / muteshk checks are named
    # skips; the Mr. / Ms. honorific is 4d, so the bare name)
    shop_name = SHOPTYPES[int(eshkp.shoptype) - int(RoomType.SHOPBASE)].name
    events.append(
        MessageEvent(
            f"Thank you for shopping in {_shk_bare_name(eshkp)} {shop_name}!"
        )
    )
    return events


__all__ = [
    "BILLSZ",
    "add_one_tobill",
    "addupbill",
    "alter_cost",
    "billable",
    "block_door",
    "costly_spot",
    "do_pay",
    "get_cost",
    "get_shop_item",
    "getprice",
    "good_shopdoor",
    "hot_pursuit",
    "inherits",
    "inhishop",
    "init",
    "inside_shop",
    "mkveggy_at",
    "mkshobj_at",
    "nameshk",
    "onbill",
    "paybill",
    "pay_debt",
    "rile_shk",
    "rob_shop",
    "room_keeper",
    "setpaid",
    "shkveg",
    "shop_debt",
    "shop_keeper",
    "stolen_value",
    "stock_goodpos",
    "stock_room",
    "sub_one_frombill",
    "track_shop",
    "veggy_item",
]
