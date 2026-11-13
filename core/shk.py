"""The shop system -- phase 4a of PLAN-SPECIAL-ROOMS.md.

A shop in pyhack is what 4a says it is: a room whose type is
``SHOPBASE + i`` (the ``i`` index into core.shknam_data.SHOPTYPES), a
peaceful shopkeeper standing just inside its door who knows the room
(``Eshk`` on the monster, C: ``mextra->eshk``), and a floor stocked one
object per free square.  You can walk in, take what you like and walk
out again -- for free.  Prices (4b), the "you stole from me" police
(4c) and the shopkeeper's dialogue (4d) are *not* ported; every one of
them is named where it would go.

C provenance (the spans this module owns, verified against
nethack_index/symbols):

  src/shknam.c  good_shopdoor() 581-624, shkinit() 627-692,
                stock_room_goodpos() 694-714, stock_room() 717-801,
                mkshobj_at() 453-483, get_shop_item() 828-839,
                nameshk() 486-554, veggy_item() 379-405,
                shkveg() 407-439, mkveggy_at() 442-450
  src/shk.c     inside_shop() 567-576 (the "which shop owns this
                square" question stock_room() asks about the door)
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
  - ``saleable()`` (does this shop stock this item type) belongs to the
    billing half; ``getprice`` / ``billable`` / ``add_one_tobill`` /
    ``stolen_value`` / ``paybill`` are 4b-4c and not ported, so an
    ``Eshk`` carries a zeroed account and ``Room.resident`` is the only
    "who keeps this shop" record.

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
from .hacklib import distmin
from .makemon import makemon, mkclass, mkmonmoney, mongets, set_malign
from .mkobj import is_ismnum, mkobj_at, mksobj_at
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
    DoorMask,
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
        world, rng, _mons_row(PM_SHOPKEEPER), (sx, sy), MmFlags.ESHK,
        map_=map_, lev=lev, in_mklev=True,
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


def stock_goodpos(
    map_: Map, room: Room, rmno: int, door: Pos, pos: Pos
) -> bool:
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
    return mksobj_at(world, rng, shkveg(rng), pos, lev,
                     init=True, artif=True)


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
        if mimic is not None and makemon(
            world, rng, mimic, pos, NO_MM_FLAGS, map_=map_, lev=lev,
            in_mklev=True,
        ) is not None:
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
                TerrainType.ROOM if map_.room_at((m, n)) is not None
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


__all__ = [
    "get_shop_item",
    "good_shopdoor",
    "init",
    "inside_shop",
    "mkveggy_at",
    "mkshobj_at",
    "nameshk",
    "room_keeper",
    "shkveg",
    "shop_keeper",
    "stock_goodpos",
    "stock_room",
    "veggy_item",
]
