"""Room records and the room-primitive layer around them.

Port of the NetHack 5.0 room module -- the *geometry* half of level
generation.  The room records themselves live on the level (Map.rooms,
C: svr.rooms[]; see core.types.Room) and are made by core.mklev; this
module answers the questions everybody else asks about them ("a free
square in this room", "which room is this?", "does this room own a
staircase?") and holds the do_mkroom dispatch that turns an ordinary
room into a special one.

C provenance:

  src/mkroom.c  pick_room(), somex(), somey(), somexy(),
                somexyspace(), inside_room(), nexttodoor(),
                has_dnstairs(), has_upstairs(), search_special(),
                do_mkroom() and its mkshop()/mkzoo()/mkswamp()/
                mktemple() handlers, isbig(), invalid_shop_shape(),
                shrine_pos(), fill_zoo() and the zoo pickers
                courtmon()/squadmon()/morguemon()/antholemon(),
                mk_zoo_thronemon(), mkundead()
  src/sp_lev.c  fill_special_room() -- the end-of-level room-stocking
                dispatcher.  C lives in sp_lev.c 2732, NOT mkroom.c
                (PLAN-SPECIAL-ROOMS.md trap 1); it is ported here
                because this module owns the do_mkroom handlers, and
                PLAN-SPLEV.md will call the same function for
                des.room({type="zoo"}).
  src/minion.c  ndemon() -- the morgue's demon half (ported to
                core.makemon, which already owns mkclass_aligned)
  src/mklev.c   occupied() (declared in hack.h; it lives here because
                somexyspace() is its main caller)

Included (the parts that need nothing beyond the ported terrain):

  isbig, pick_room, do_mkroom dispatch, mkzoo (the room *selection*
  and the rtype / needfill bookkeeping -- C: "the room does not get
  stocked at this time -- it will get stocked at the end of
  makelevel()"), fill_zoo (the zoo family in C order: the throne /
  queen-square / gold-budget setup, the per-square monsters and
  objects, the royal coffers, the level flags -- PLAN-SPECIAL-ROOMS.md
  phase 2), fill_special_room (the dispatcher: subroom recursion,
  the OROOM / THEMEROOM / FILL_NONE refusal, the VAULT gold-per-
  square branch, the zoo family, the trailing flag switch),
  mktemple (the room pick, the shrine altar with its
  induced alignment and the priest, through core.priest.priestini --
  PLAN-SPECIAL-ROOMS.md phase 1), the zoo pickers (courtmon /
  squadmon / morguemon / antholemon / mk_zoo_thronemon / mkundead),
  somex/somey/somexy/somexyspace, inside_room, nexttodoor,
  has_dnstairs, has_upstairs, search_special, occupied, shrine_pos,
  invalid_shop_shape, room_of_stair.

STUBs (raise NotImplementedError, each with the machinery it waits for):

  - mkshop(): needs the shknam.c shop-type table (shtypes[]) and then
    the shk.c stock_room() billing side (phase 4).
  - fill_special_room's shop branch (C: stock_room): the same
    stock_room(); the branch is unreachable while mkshop is a STUB
    (no shop room can exist), and phase 4 replaces the body.
  - mkswamp(): needs the engraving removal (C: del_engr_at) and the
    eel / fungus stocking (phase 3); set_levltyp and makemon are in.
  - cmap_to_type(): needs the display symbol table (S_* -> terrain).

Simplifications (documented, not bugs):

  - the temple is the only special room C stocks in its mk* handler
    (mktemple: altar + priest, no needfill) -- fill_special_room
    only carries its flag.  The zoo family is stocked by fill_zoo
    through the needfill model (mkzoo sets FILL_NORMAL, the
    end-of-level fill_special_room loop stocks it); the shop (phase
    4) and the swamp (phase 3) are the two unstocked rooms left.
    Every handler states its C provenance so the next phase can land
    without re-reading the C.
  - do_mkroom is only reached when the generator is asked for special
    rooms (core.mklev.makelevel(specials=True)); the demo level has
    none, and the default level generator passes specials=False.
  - the C functions take the ambient level state (svr.rooms,
    gs.stairs, svl.level.objects); here everything is a parameter --
    Map + the staircase / trap lists of the level being worked on.
    That is what lets the same code number a level that is *not* the
    current one (levels 2..N generate lazily, PLAN-STAIRS.md §2.6).
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from .hacklib import dist2, distmin
from .makemon import makemon, mkclass, mongets, ndemon, set_malign
from .mkobj import (
    RANDOM_CLASS,
    add_to_container,
    mkgold,
    mkobj,
    mkobj_at,
    mksobj,
    mksobj_at,
    sobj_at,
    weight,
)
from .monst import (
    MONS,
    PM_BUGBEAR,
    PM_CAPTAIN,
    PM_COCKATRICE,
    PM_DWARF_RULER,
    PM_ELVEN_MONARCH,
    PM_FIRE_ANT,
    PM_GHOST,
    PM_GIANT_ANT,
    PM_GNOME_RULER,
    PM_HOBGOBLIN,
    PM_KILLER_BEE,
    PM_LEPRECHAUN,
    PM_LIEUTENANT,
    PM_OGRE_TYRANT,
    PM_QUEEN_BEE,
    PM_SERGEANT,
    PM_SOLDIER,
    PM_SOLDIER_ANT,
    PM_WRAITH,
    PerMonst,
)
from .monst_defs import (
    A_NONE,
    G_GONE,
    S_CENTAUR,
    S_DRAGON,
    S_GIANT,
    S_GNOME,
    S_KOBOLD,
    S_ORC,
    S_TROLL,
    S_VAMPIRE,
    S_ZOMBIE,
)
from .objects import O, ObjClass
from .place import enexto
from .priest import induced_align, priestini
from .rules import level_difficulty
from .types import (
    ANY_SHOP,
    ANY_TYPE,
    FILL_NONE,
    FILL_NORMAL,
    Map,
    MmFlags,
    MM_ASLEEP,
    MM_NOGRP,
    NO_MM_FLAGS,
    Pos,
    Room,
    RoomType,
    Stairway,
    TerrainType,
    World,
    is_door,
    is_furniture,
    is_pool,
    is_sdoor,
    is_throne,
    is_wall,
    space_pos,
)

# ============================================================
# Small predicates
# ============================================================


def isbig(room: Room) -> bool:
    """C: mkroom.c#isbig -- more than 20 squares makes a "big" room
    (too small for a wand or book shop: mkshop turns those into
    general stores)."""
    area = (room.hx - room.lx + 1) * (room.hy - room.ly + 1)
    return area > 20


def occupied(map_: Map, traps: Iterable, pos: Pos) -> bool:
    """C: mklev.c#occupied -- is a map feature already on this square?

    C checks traps, furniture terrain, lava, pools and the invocation
    position; it does *not* check monsters or objects (the callers add
    those tests themselves).  The invocation position is unported (no
    invocation level), so the test stops after the pools.
    """
    tile = map_.tile_at(pos)
    if is_furniture(tile.typ) or is_pool(tile.typ):
        return True
    return any(t.pos == pos and not t.disarmed for t in traps)


def nexttodoor(map_: Map, sx: int, sy: int) -> bool:
    """C: mkroom.c#nexttodoor -- a door or secret door among the eight
    neighbours (used to keep swamp pools out of doorways)."""
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            pos = (sx + dx, sy + dy)
            if not map_.in_bounds(pos):
                continue
            typ = map_.tile_at(pos).typ
            if is_door(typ) or is_sdoor(typ):
                return True
    return False


def has_dnstairs(map_: Map, stairs: Iterable[Stairway], room: Room) -> bool:
    """C: mkroom.c#has_dnstairs -- the room owns a down staircase."""
    return any(not s.up and inside_room(map_, room, s.pos) for s in stairs)


def has_upstairs(map_: Map, stairs: Iterable[Stairway], room: Room) -> bool:
    """C: mkroom.c#has_upstairs -- the room owns an up staircase."""
    return any(s.up and inside_room(map_, room, s.pos) for s in stairs)


# ============================================================
# Room geometry
# ============================================================


def somex(room: Room, rng) -> int:
    """C: mkroom.c#somex -- a random column inside the room."""
    return rng.rn1(room.hx - room.lx + 1, room.lx)


def somey(room: Room, rng) -> int:
    """C: mkroom.c#somey -- a random row inside the room."""
    return rng.rn1(room.hy - room.ly + 1, room.ly)


def inside_room(map_: Map, room: Room, pos: Pos) -> bool:
    """C: mkroom.c#inside_room -- is `pos` in the room?

    An irregular room is tested through the terrain (`roomno` +
    `edge`); a rectangular one by its rectangle *including* the wall
    ring (the C `lx-1 .. hx+1` test), which is what "a staircase in
    this room" means to the stair generator.
    """
    x, y = pos
    if not map_.in_bounds(pos):
        return False
    if room.irregular:
        tile = map_.tile_at(pos)
        return not tile.edge and tile.roomno == map_.room_of(room)
    return room.lx - 1 <= x <= room.hx + 1 and room.ly - 1 <= y <= room.hy + 1


def somexy(map_: Map, room: Room, rng) -> Optional[Pos]:
    """C: mkroom.c#somexy -- a square inside the room, but not in a
    subroom.  May return a wall square when a room is not irregular
    but holds non-room terrain (C behaviour).

    The irregular branch tries 100 random points and then scans the
    room's rectangle exhaustively, exactly like C.
    """
    if room.irregular:
        idx = map_.room_of(room)
        for _ in range(100):
            pos = (somex(room, rng), somey(room, rng))
            tile = map_.tile_at(pos)
            if not tile.edge and tile.roomno == idx:
                return pos
        for x in range(room.lx, room.hx + 1):
            for y in range(room.ly, room.hy + 1):
                tile = map_.tile_at((x, y))
                if not tile.edge and tile.roomno == idx:
                    return (x, y)
        return None

    if not room.sbrooms:
        return (somex(room, rng), somey(room, rng))

    for _ in range(100):
        pos = (somex(room, rng), somey(room, rng))
        if is_wall(map_.tile_at(pos).typ):
            continue
        in_sub = any(
            sl.lx - 1 <= pos[0] <= sl.hx + 1 and sl.ly - 1 <= pos[1] <= sl.hy + 1
            for sl in (map_.subrooms[i] for i in room.sbrooms)
        )
        if in_sub:
            continue
        return pos
    return None


def somexyspace(map_: Map, traps: Iterable, room: Room, rng) -> Optional[Pos]:
    """C: mkroom.c#somexyspace -- a *free, standable* square inside the
    room (somexy's answer filtered by "not occupied and ROOM/CORR/ICE").

    C is a do/while: after 100 failed tries the last answer is returned
    anyway, so a full room still yields a position (the callers then do
    whatever C does with a bad one).
    """
    pos: Optional[Pos] = None
    for _ in range(101):
        pos = somexy(map_, room, rng)
        if (
            pos is not None
            and not occupied(map_, traps, pos)
            and map_.tile_at(pos).typ
            in (TerrainType.ROOM, TerrainType.CORR, TerrainType.ICE)
        ):
            return pos
    return pos


def shrine_pos(map_: Map, traps: Iterable, room: Room, rng) -> Optional[Pos]:
    """C: mkroom.c#shrine_pos -- the center of the room, or a random
    free square when the center is blocked (the temple shrine spot).

    `rn2(2)` bumps the column / row on an even-sized room, so the
    shrine lands next to the hypothetical center, exactly as C does.
    """
    delta = room.hx - room.lx
    x = room.lx + delta // 2
    if delta % 2 and rng.rn2(2):
        x += 1
    delta = room.hy - room.ly
    y = room.ly + delta // 2
    if delta % 2 and rng.rn2(2):
        y += 1
    pos = (x, y)
    tile = map_.tile_at(pos) if map_.in_bounds(pos) else None
    if (
        tile is None
        or tile.roomno != map_.room_of(room)
        or tile.typ not in (TerrainType.ROOM, TerrainType.ICE, TerrainType.CLOUD)
    ):
        return somexyspace(map_, traps, room, rng)
    return pos


def invalid_shop_shape(map_: Map, room: Room) -> bool:
    """C: mkroom.c#invalid_shop_shape -- reject the shapes where a
    shopkeeper standing just inside the door would have nowhere to
    move (the themed-room "one square past the door" shape).

    Pure terrain arithmetic, ported here because mkshop() needs it the
    moment the shop work lands.
    """
    if not room.doors:
        return False
    doorx, doory = room.doors[0]
    inside: List[Pos] = []
    for x in range(max(doorx - 1, room.lx), min(doorx + 1, room.hx) + 1):
        for y in range(max(doory - 1, room.ly), min(doory + 1, room.hy) + 1):
            if map_.tile_at((x, y)).typ == TerrainType.ROOM:
                inside.append((x, y))
    if not inside:
        return True
    if len(inside) > 1:
        return False
    insidex, insidey = inside[0]
    count = 0
    for x in range(max(insidex - 1, room.lx), min(insidex + 1, room.hx) + 1):
        for y in range(max(insidey - 1, room.ly), min(insidey + 1, room.hy) + 1):
            if (x, y) != (insidex, insidey) and map_.tile_at(
                (x, y)
            ).typ == TerrainType.ROOM:
                count += 1
    return count == 1


# ============================================================
# Room lookup
# ============================================================


def pick_room(
    map_: Map, stairs: Iterable[Stairway], rng, strict: bool
) -> Optional[Room]:
    """C: mkroom.c#pick_room -- an unused ORDINARY room, preferring one
    with a single door.

    C starts at a random room and walks the array (wrapping), so every
    room gets a fair chance; the door preference is the `doorct == 1 ||
    !rn2(5)` test -- i.e. 1 in 5 multi-door rooms is accepted anyway.
    """
    stairs = list(stairs)
    rooms = map_.rooms
    if not rooms:
        return None
    start = rng.rn2(len(rooms))
    for i in range(len(rooms)):
        room = rooms[(start + i) % len(rooms)]
        if room.rtype != RoomType.OROOM:
            continue
        if not strict:
            if has_upstairs(map_, stairs, room) or (
                has_dnstairs(map_, stairs, room) and rng.rn2(3)
            ):
                continue
        elif has_upstairs(map_, stairs, room) or has_dnstairs(map_, stairs, room):
            continue
        if room.doorct == 1 or not rng.rn2(5):
            return room
    return None


def search_special(map_: Map, rtype: int) -> Optional[Room]:
    """C: mkroom.c#search_special -- find a special room by type.

    `rtype` is a RoomType or one of the two special keys ANY_TYPE /
    ANY_SHOP (C: -1 / -2 -- the C signature takes a signed char, hence
    the int).  C searches svr.rooms[] and then gs.subrooms[]; both
    lists are searched here too.
    """
    for room in list(map_.rooms) + list(map_.subrooms):
        if (
            (rtype == ANY_TYPE and room.rtype != RoomType.OROOM)
            or (rtype == ANY_SHOP and room.rtype >= RoomType.SHOPBASE)
            or room.rtype == rtype
        ):
            return room
    return None


def room_of_stair(map_: Map, stairs: Iterable[Stairway], up: bool) -> Optional[Room]:
    """The room the first staircase of the given direction stands in,
    if any (the demo helper behind "don't make a special room out of
    the room the stairs are in")."""
    for stair in stairs:
        if stair.up == up:
            return map_.room_at(stair.pos)
    return None


# ============================================================
# Special rooms (C: mkroom.c do_mkroom and the mk* handlers)
# ============================================================


def do_mkroom(
    world: World,
    map_: Map,
    stairs: Iterable[Stairway],
    traps: Iterable,
    rng,
    lev: int,
    roomtype: RoomType,
) -> Optional[Room]:
    """C: mkroom.c#do_mkroom -- make and stock a room of the given type.

    Returns the room that was claimed, or None when no eligible room
    was found (C returns void and leaves the level alone).

    `world` / `lev` say which level is being stocked (a lazily
    generated level is built while the hero stands on another one,
    PLAN-MKLEV.md decision 3); `traps` is that level's traps (the
    temple's shrine keeps off trapped squares through them).

    The zoo family is the room *selection* only (see mkzoo) and the
    temple is fully stocked here (mktemple); the shop and the swamp
    are STUBs, so asking for one raises NotImplementedError naming the
    C it waits for.
    """
    if roomtype >= RoomType.SHOPBASE:
        return mkshop(map_, stairs, rng)
    if roomtype == RoomType.TEMPLE:
        return mktemple(world, map_, stairs, traps, rng, lev)
    if roomtype == RoomType.SWAMP:
        return mkswamp(map_, stairs, rng)
    if roomtype in (
        RoomType.COURT,
        RoomType.ZOO,
        RoomType.BEEHIVE,
        RoomType.MORGUE,
        RoomType.BARRACKS,
        RoomType.LEPREHALL,
        RoomType.COCKNEST,
        RoomType.ANTHOLE,
    ):
        return mkzoo(map_, stairs, rng, roomtype)
    raise ValueError(f"Tried to make a room of type {roomtype}.")


def mkzoo(
    map_: Map, stairs: Iterable[Stairway], rng, rtype: RoomType
) -> Optional[Room]:
    """C: mkroom.c#mkzoo -- claim a random room for a zoo-like special
    room (COURT / ZOO / BEEHIVE / MORGUE / BARRACKS / LEPREHALL /
    COCKNEST / ANTHOLE).

    C sets the rtype and the needfill bookkeeping here and only:
    "the room does not get stocked at this time -- it will get stocked
    at the end of makelevel()" -- the end-of-level fill_special_room()
    loop does the stocking (PLAN-SPECIAL-ROOMS.md phase 2).
    """
    room = pick_room(map_, stairs, rng, False)
    if room is None:
        return None
    room.rtype = rtype
    room.needfill = FILL_NORMAL
    return room


def _mons_row(mndx: int) -> PerMonst:
    """A fixed mons[] row (the zoo's named species); the 383-row table
    is complete, so a None row is a table bug, not a runtime state."""
    row = MONS[mndx]
    assert row is not None, f"mons[{mndx}] is missing from the table"
    return row


def fill_zoo(
    world: World, rng, map_: Map, traps: Iterable, room: Room, lev: int
) -> None:
    """C: mkroom.c#fill_zoo -- stock a zoo-like special room, in C's
    order: the per-type setup (the court's throne square, the
    beehive's queen square, the ZOO / LEPREHALL gold budget), then one
    pass over the room's squares (a monster per square from the type's
    picker, then the type's objects / gold), then the type's
    post-processing (the court's THRONE terrain + the royal coffers,
    the level flags).

    C: "This doesn't check needfill; it assumes the caller has already
    done that" -- fill_special_room() is the caller.

    The gold budget (the fiddly part, kept verbatim): goldlim =
    500 * level_difficulty() for ZOO / LEPREHALL; per square, i = the
    squared distance to the first door (i = goldlim when the room has
    no door); when i >= goldlim the square gets the flat
    5 * level_difficulty() instead; goldlim -= i; the square gets
    mkgold(rn1(i, 10)) -- the budget can go negative and the flat
    value keeps the squares stocked.

    A picker that answers None (C: NULL -- e.g. antholemon() after all
    three ant species are genocided) makes C's makemon() take its
    anymon path, and pyhack's makemon(ptr=None) does the same.
    """
    # local imports: mklev imports this module (see mktemple)
    from .mklev import make_grave, set_levltyp

    sh = room.doors[0] if room.doors else None
    typ = room.rtype
    goldlim = 0
    tx = ty = 0
    rmno = map_.room_of(room)

    if typ == RoomType.COURT:
        # C: a maze level reuses a pre-placed THRONE in the room; pyhack
        # has no maze levels (LevelFlags.is_maze_lev stays False), so
        # that scan never runs and the throne square is always picked
        # here (a free square -- `don't place throne on top of stairs`).
        tries = 100
        while True:
            mm = somexyspace(map_, traps, room, rng)
            if mm is None:  # the pyhack refusal: no free square at all
                return
            tx, ty = mm
            if not occupied(map_, traps, (tx, ty)) or tries <= 0:
                break
            tries -= 1
        mk_zoo_thronemon(world, rng, map_, lev, (tx, ty))
    elif typ == RoomType.BEEHIVE:
        tx = room.lx + (room.hx - room.lx + 1) // 2
        ty = room.ly + (room.hy - room.ly + 1) // 2
        if room.irregular:
            # the center might not be valid, so put the queen elsewhere
            tile = map_.tile_at((tx, ty))
            if tile.roomno != rmno or tile.edge:
                mm = somexyspace(map_, traps, room, rng)
                if mm is not None:
                    tx, ty = mm
    elif typ in (RoomType.ZOO, RoomType.LEPREHALL):
        goldlim = 500 * level_difficulty(world)

    for sx in range(room.lx, room.hx + 1):
        for sy in range(room.ly, room.hy + 1):
            pos = (sx, sy)
            if room.irregular:
                tile = map_.tile_at(pos)
                if (
                    tile.roomno != rmno
                    or tile.edge
                    or (room.doorct and sh is not None
                        and distmin(pos, sh) <= 1)
                ):
                    continue
            elif (
                not space_pos(map_.tile_at(pos).typ)
                or (room.doorct and sh is not None and (
                    (sx == room.lx and sh[0] == sx - 1)
                    or (sx == room.hx and sh[0] == sx + 1)
                    or (sy == room.ly and sh[1] == sy - 1)
                    or (sy == room.hy and sh[1] == sy + 1)))
            ):
                continue
            # don't place a monster on an explicitly placed throne
            if typ == RoomType.COURT and is_throne(map_.tile_at(pos).typ):
                continue
            if typ == RoomType.COURT:
                pm = courtmon(world, rng)
            elif typ == RoomType.BARRACKS:
                pm = squadmon(world, rng)
            elif typ == RoomType.MORGUE:
                pm = morguemon(world, rng)
            elif typ == RoomType.BEEHIVE:
                pm = _mons_row(PM_QUEEN_BEE if (sx, sy) == (tx, ty)
                               else PM_KILLER_BEE)
            elif typ == RoomType.LEPREHALL:
                pm = _mons_row(PM_LEPRECHAUN)
            elif typ == RoomType.COCKNEST:
                pm = _mons_row(PM_COCKATRICE)
            elif typ == RoomType.ANTHOLE:
                pm = antholemon(world)
            else:
                pm = None
            mon = makemon(world, rng, pm, pos, MM_ASLEEP | MM_NOGRP,
                          map_, lev, in_mklev=True)
            if mon is not None:
                mon.sleeping = 1
                if typ == RoomType.COURT and mon.mpeaceful:
                    mon.mpeaceful = False
                    set_malign(world, mon)
            if typ in (RoomType.ZOO, RoomType.LEPREHALL):
                if room.doorct and sh is not None:
                    i = dist2(pos, sh) ** 2
                else:
                    i = goldlim
                if i >= goldlim:
                    i = 5 * level_difficulty(world)
                goldlim -= i
                mkgold(world, rng, rng.rn1(i, 10), pos, lev)
            elif typ == RoomType.MORGUE:
                if not rng.rn2(5):
                    # C: mk_tt_object(CORPSE, ...) = mksobj_at with init
                    mksobj_at(world, rng, int(O.CORPSE), pos, lev)
                if not rng.rn2(10):  # lots of treasure buried with dead
                    mksobj_at(
                        world, rng,
                        int(O.LARGE_BOX) if rng.rn2(3) else int(O.CHEST),
                        pos, lev)
                if not rng.rn2(5):
                    make_grave(world, map_, list(traps), pos)
            elif typ == RoomType.BEEHIVE:
                if not rng.rn2(3):
                    mksobj_at(world, rng, int(O.LUMP_OF_ROYAL_JELLY),
                              pos, lev)
            elif typ == RoomType.BARRACKS:
                if not rng.rn2(20):  # the payroll and some loot
                    mksobj_at(
                        world, rng,
                        int(O.LARGE_BOX) if rng.rn2(3) else int(O.CHEST),
                        pos, lev)
            elif typ == RoomType.COCKNEST:
                if not rng.rn2(3):
                    # C: mk_tt_object(STATUE, ...) = mksobj_at with
                    # init=FALSE (player statues never contain books)
                    statue = mksobj_at(world, rng, int(O.STATUE), pos,
                                       lev, init=False)
                    for _ in range(rng.rn2(5)):
                        add_to_container(
                            world, statue,
                            mkobj(world, rng, RANDOM_CLASS, False))
                    statue.owt = weight(world, statue)
            elif typ == RoomType.ANTHOLE:
                if not rng.rn2(3):
                    mkobj_at(world, rng, int(ObjClass.FOOD), pos, lev)

    if typ == RoomType.COURT:
        set_levltyp(map_, tx, ty, TerrainType.THRONE)
        mm = somexyspace(map_, traps, room, rng)
        if mm is not None:
            gold = mksobj(world, rng, int(O.GOLD_PIECE))
            gold.quan = rng.rn1(50 * level_difficulty(world), 10)
            gold.owt = weight(world, gold)
            # the royal coffers
            chest = mksobj_at(world, rng, int(O.CHEST), mm, lev)
            add_to_container(world, chest, gold)
            chest.owt = weight(world, chest)
            chest.spe = 2  # so it can be found later
        map_.flags.has_court = True
    elif typ == RoomType.BARRACKS:
        map_.flags.has_barracks = True
    elif typ == RoomType.ZOO:
        map_.flags.has_zoo = True
    elif typ == RoomType.MORGUE:
        map_.flags.has_morgue = True
    elif typ == RoomType.SWAMP:
        map_.flags.has_swamp = True
    elif typ == RoomType.BEEHIVE:
        map_.flags.has_beehive = True


def fill_special_room(
    world: World, rng, map_: Map, traps: Iterable, room: Room, lev: int
) -> None:
    """C: sp_lev.c#fill_special_room -- the end-of-level room-stocking
    dispatcher, called by makelevel for every top-level room (C: the
    "Fill all special rooms now" loop).

    C provenance (PLAN-SPECIAL-ROOMS.md trap 1): in C the dispatcher
    lives in *sp_lev.c* 2732, not mkroom.c -- a grep of mkroom.c will
    not find it.  It is ported here because this module owns the
    do_mkroom handlers, and PLAN-SPLEV.md will call the same function
    for des.room({type="zoo"}).

    The order is C's: the subrooms first (the recursion), the
    OROOM / THEMEROOM / FILL_NONE refusal, then the FILL_NORMAL
    stocking (the shop branch first -- C's `rtype >= SHOPBASE`; the
    VAULT gold-per-square; the zoo family through fill_zoo), then the
    level-flag switch, which runs even for a room that was only
    carried (the temple's stocking comes from mktemple; its flag here
    is the special-level half).
    """
    for sidx in room.sbrooms:
        fill_special_room(world, rng, map_, traps, map_.subrooms[sidx],
                          lev)
    if (room.rtype in (RoomType.OROOM, RoomType.THEMEROOM)
            or room.needfill == FILL_NONE):
        return
    if room.needfill == FILL_NORMAL:
        if room.rtype >= RoomType.SHOPBASE:
            _stock_room(world, rng, map_, traps, room, lev)
            map_.flags.has_shop = True
            return
        if room.rtype == RoomType.VAULT:
            for sx in range(room.lx, room.hx + 1):
                for sy in range(room.ly, room.hy + 1):
                    mkgold(world, rng, rng.rn1(abs(lev) * 100, 51),
                           (sx, sy), lev)
        elif room.rtype in (
            RoomType.COURT,
            RoomType.ZOO,
            RoomType.BEEHIVE,
            RoomType.ANTHOLE,
            RoomType.COCKNEST,
            RoomType.LEPREHALL,
            RoomType.MORGUE,
            RoomType.BARRACKS,
        ):
            fill_zoo(world, rng, map_, traps, room, lev)
    if room.rtype == RoomType.VAULT:
        map_.flags.has_vault = True
    elif room.rtype == RoomType.ZOO:
        map_.flags.has_zoo = True
    elif room.rtype == RoomType.COURT:
        map_.flags.has_court = True
    elif room.rtype == RoomType.MORGUE:
        map_.flags.has_morgue = True
    elif room.rtype == RoomType.BEEHIVE:
        map_.flags.has_beehive = True
    elif room.rtype == RoomType.BARRACKS:
        map_.flags.has_barracks = True
    elif room.rtype == RoomType.TEMPLE:
        map_.flags.has_temple = True
    elif room.rtype == RoomType.SWAMP:
        map_.flags.has_swamp = True


def _stock_room(
    world: World, rng, map_: Map, traps: Iterable, room: Room, lev: int
) -> None:
    """C: shk.c#stock_room -- the shop's stock and the shopkeeper
    (C's signature: stock_room(int type, struct mkroom *r), `type` =
    rtype - SHOPBASE).

    STUB (PLAN-SPECIAL-ROOMS.md phase 4): needs the shknam.c shtypes[]
    table and the shk.c billing side.  The dispatcher's branch is
    unreachable while mkshop() is a STUB (no shop room can exist), and
    phase 4 replaces this body.
    """
    raise NotImplementedError(
        "shop stocking needs the shknam.c shtypes[] table and shk.c "
        "stock_room() (C: src/shk.c stock_room(); PLAN-SPECIAL-ROOMS.md "
        "phase 4)"
    )


def mkshop(map_: Map, stairs: Iterable[Stairway], rng) -> Optional[Room]:
    """C: mkroom.c#mkshop -- turn an unused one-door room into a shop.

    STUB: the shop *type* comes from the shknam.c shtypes[] table
    (name / symbol / probability) and the stocking from shk.c
    stock_room(); neither is ported.  The eligibility rules (rtype ==
    OROOM, no stairs, exactly one door, not an invalid shop shape) are
    already available in pick_room / invalid_shop_shape for when this
    lands.
    """
    raise NotImplementedError(
        "shops need the shknam.c shop-type table and shk.c stock_room() "
        "(C: src/mkroom.c mkshop())"
    )


def mktemple(
    world: World, map_: Map, stairs: Iterable[Stairway], traps: Iterable, rng, lev: int
) -> Optional[Room]:
    """C: mkroom.c#mktemple -- a temple: a shrine (blessed altar) in
    the room's center and a priest standing next to it.

    The order is C's, draw for draw: the strict room pick, the rtype,
    the shrine square (shrine_pos), the altar write (C writes levl[]
    directly; here it is the sanctioned set_levltyp, which has no side
    effect on an ALTAR destination), the induced_align(80) mask,
    priestini (which reads the mask *before* AM_SHRINE is set), the
    AM_SHRINE bit and the level flag.

    Unlike the zoo family and the shop, the temple is fully stocked
    here -- C's mktemple() sets no needfill, so fill_special_room()
    only carries its flag when it lands (phase 2).  A room with no
    standable square at all (shrine_pos gives up) keeps the rtype but
    the altar and the priest stay unmade: C's shrine_pos() never
    answers NULL, so the branch is the pyhack refusal for a level edge
    case.
    """
    from .mklev import set_levltyp  # local import: mklev imports this module
    from .monst_defs import AM_SHRINE

    room = pick_room(map_, stairs, rng, True)
    if room is None:
        return None
    room.rtype = RoomType.TEMPLE
    # In temples, shrines are blessed altars located in the center of
    # the room (C's comment)
    pos = shrine_pos(map_, traps, room, rng)
    if pos is None:
        return room
    if not set_levltyp(map_, pos[0], pos[1], TerrainType.ALTAR):
        return room
    map_.tile_at(pos).altarmask = induced_align(rng)
    priestini(world, map_, room, pos, False, lev, rng)
    map_.tile_at(pos).altarmask |= AM_SHRINE
    map_.flags.has_temple = True
    return room


def mkswamp(map_: Map, stairs: Iterable[Stairway], rng) -> Optional[Room]:
    """C: mkroom.c#mkswamp -- flood up to five rooms with pools.

    STUB: the sanctioned terrain mutator (C: set_levltyp) and the
    monster generation (makemon) have landed; what is still needed is
    the engraving removal (C: del_engr_at) the pools run over.  The
    checkerboard rule ((sx+sy) % 2) and the nexttodoor() guard are the
    ported part of the shape.
    """
    raise NotImplementedError(
        "swamps need engraving removal and eel / fungus monster "
        "generation (C: src/mkroom.c mkswamp())"
    )


def courtmon(world: World, rng) -> Optional[PerMonst]:
    """C: mkroom.c#courtmon -- a court monster by depth:
    i = rn2(60) + rn2(3 * level_difficulty()), then C's ladder (i > 100
    dragon, > 95 giant, > 85 troll, > 75 centaur, > 60 orc, > 45
    bugbear, > 30 hobgoblin, > 15 gnome, else kobold) -- the mkclass()
    answers and the two fixed rows kept, C's order of the two draws
    kept.
    """
    i = rng.rn2(60) + rng.rn2(3 * level_difficulty(world))
    if i > 100:
        return mkclass(world, rng, S_DRAGON, 0)
    if i > 95:
        return mkclass(world, rng, S_GIANT, 0)
    if i > 85:
        return mkclass(world, rng, S_TROLL, 0)
    if i > 75:
        return mkclass(world, rng, S_CENTAUR, 0)
    if i > 60:
        return mkclass(world, rng, S_ORC, 0)
    if i > 45:
        return _mons_row(PM_BUGBEAR)
    if i > 30:
        return _mons_row(PM_HOBGOBLIN)
    if i > 15:
        return mkclass(world, rng, S_GNOME, 0)
    return mkclass(world, rng, S_KOBOLD, 0)


# C: mkroom.c 817-823 -- the squadprob[] table, kept as data.
_SQUADPROB: List[Tuple[int, int]] = [
    (PM_SOLDIER, 80),
    (PM_SERGEANT, 15),
    (PM_LIEUTENANT, 4),
    (PM_CAPTAIN, 1),
]


def squadmon(world: World, rng) -> Optional[PerMonst]:
    """C: mkroom.c#squadmon -- a barracks soldier by a
    rnd(80 + level_difficulty()) roll over the squadprob[] table
    (soldier 80 / sergeant 15 / lieutenant 4 / captain 1).

    The walk is C's (the cumulative cpro > sel_prob test, the
    ROLL_FROM uniform fallback when the walk falls through), and a
    genocided type answers None (C: the G_GONE test answers NULL).
    """
    sel_prob = rng.rnd(80 + level_difficulty(world))
    cpro = 0
    mndx = _SQUADPROB[-1][0]
    for pm, prob in _SQUADPROB:
        cpro += prob
        if cpro > sel_prob:
            mndx = pm
            break
    if world.mon_state.mvitals[mndx].mvflags & G_GONE:
        return None
    return _mons_row(mndx)


def morguemon(world: World, rng) -> Optional[PerMonst]:
    """C: mkroom.c#morguemon -- a morgue undead by depth:
    i = rn2(100), hd = rn2(level_difficulty()); the deep-and-low-i
    branch wants a demon (C: Inhell / In_endgame -> mkclass(S_DEMON),
    else ndemon(A_NONE) -- pyhack has no hell or endgame level, so the
    ndemon() half is taken, and a failed ndemon() drops to the ladder,
    C's comment); the deep-and-high-i branch is a vampire; the ladder
    is ghost / wraith / zombie by i.
    """
    i = rng.rn2(100)
    hd = rng.rn2(level_difficulty(world))
    if hd > 10 and i < 10:
        mndx = ndemon(world, rng, A_NONE)
        if mndx is not None:
            return _mons_row(mndx)
    if hd > 8 and i > 85:
        return mkclass(world, rng, S_VAMPIRE, 0)
    if i < 20:
        return _mons_row(PM_GHOST)
    if i < 40:
        return _mons_row(PM_WRAITH)
    return mkclass(world, rng, S_ZOMBIE, 0)


def antholemon(world: World) -> Optional[PerMonst]:
    """C: mkroom.c#antholemon -- the ant species of the level: the
    same species on every square of the level, a different one on
    another level.  C seeds it with the hero's birth time
    (ubirthday % 3); pyhack reads World.birth (the game start time,
    the midnight pattern).  The C is a pure computation -- no rng
    draws -- so the roll-side pre-check in _roll_special_room and the
    per-square calls here agree for free.

    A genocided species rotates (up to the other two); all three gone
    answers None (C: NULL).
    """
    ants = (PM_SOLDIER_ANT, PM_FIRE_ANT, PM_GIANT_ANT)
    indx = world.birth % 3 + level_difficulty(world)
    mtyp = ants[indx % 3]
    for trycnt in range(1, 3):
        if not (world.mon_state.mvitals[mtyp].mvflags & G_GONE):
            break
        mtyp = ants[(indx + trycnt) % 3]
    if world.mon_state.mvitals[mtyp].mvflags & G_GONE:
        return None
    return _mons_row(mtyp)


def mkundead(
    world: World, rng, map_: Map, lev: int, pos: Pos,
    revive_corpses: bool, mm_flags: MmFlags,
) -> None:
    """C: mkroom.c#mkundead -- a swarm of undead around `pos`
    ((level_difficulty() + 1) / 10 + rnd(5) of them, each a
    morguemon() on an enexto() square), setting the level's graveyard
    flag (the reduced-chance-for-an-undead-corpse marker).

    The signature is C's (coord, revive_corpses, mm_flags) -- the S32
    note had (pos, rng), which was wrong (PLAN-SPECIAL-ROOMS.md
    ground-truth).  The C callers (spell.c / apply.c, the raise-dead
    and create-undead entry points) pass NO_MINVENT; pyhack has no
    spell system yet, so this is a standalone fill-in for it.

    The revive() half (C: spell.c) is not ported: a corpse on the
    target square counts as revived (no new undead appears there) until
    the spell system lands.
    """
    cnt = (level_difficulty(world) + 1) // 10 + rng.rnd(5)
    while cnt > 0:
        cnt -= 1
        mdat = morguemon(world, rng)
        cc = enexto(world, rng, map_, lev, pos, mdat)
        if mdat is None or cc is None:
            continue
        if revive_corpses and sobj_at(world, int(O.CORPSE), lev, cc):
            continue  # the corpse is revived instead (see docstring)
        makemon(world, rng, mdat, cc, mm_flags, map_, lev)
    map_.flags.graveyard = True


def mk_zoo_thronemon(
    world: World, rng, map_: Map, lev: int, pos: Pos
) -> None:
    """C: mkroom.c#mk_zoo_thronemon -- the throne-room monarch: a gnome
    ruler / dwarf ruler / elven monarch / ogre tyrant by a
    rnd(level_difficulty()) roll, asleep and hostile (mpeaceful forced
    off + set_malign) and carrying a mace ("Give him a sceptre to
    pound in judgment").
    """
    i = rng.rnd(level_difficulty(world))
    pm = (
        PM_OGRE_TYRANT if i > 9
        else PM_ELVEN_MONARCH if i > 5
        else PM_DWARF_RULER if i > 2
        else PM_GNOME_RULER
    )
    mon = makemon(world, rng, _mons_row(pm), pos, NO_MM_FLAGS,
                  map_, lev, in_mklev=True)
    if mon is not None:
        mon.sleeping = 1
        mon.mpeaceful = False
        set_malign(world, mon)
        mongets(world, rng, mon, int(O.MACE))


# The public surface, kept explicit so the STUBs announce themselves.
__all__ = [
    "ANY_SHOP",
    "ANY_TYPE",
    "antholemon",
    "courtmon",
    "do_mkroom",
    "fill_special_room",
    "fill_zoo",
    "has_dnstairs",
    "has_upstairs",
    "inside_room",
    "invalid_shop_shape",
    "isbig",
    "mk_zoo_thronemon",
    "mkshop",
    "mkswamp",
    "mktemple",
    "mkundead",
    "mkzoo",
    "morguemon",
    "nexttodoor",
    "occupied",
    "pick_room",
    "room_of_stair",
    "search_special",
    "shrine_pos",
    "somex",
    "somexy",
    "somexyspace",
    "somey",
    "squadmon",
]
