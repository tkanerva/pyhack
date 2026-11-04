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
                shrine_pos(), courtmon()/squadmon()/morguemon()/
                antholemon(), mkundead()
  src/mklev.c   occupied() (declared in hack.h; it lives here because
                somexyspace() is its main caller)

Included (the parts that need nothing beyond the ported terrain):

  isbig, pick_room, do_mkroom dispatch, mkzoo (the room *selection*
  and the rtype bookkeeping -- C: "the shop used to be stocked here
  ... all we do is set its rtype, and it gets stocked at the end of
  makelevel()"), somex/somey/somexy/somexyspace, inside_room,
  nexttodoor, has_dnstairs, has_upstairs, search_special, occupied,
  shrine_pos, invalid_shop_shape, room_of_stair.

STUBs (raise NotImplementedError, each with the machinery it waits for):

  - mkshop(): needs the shknam.c shop-type table (shtypes[]) and then
    the shk.c stock_room() billing side.
  - mktemple(): needs the altar altarmask *and* priest.c (priestini())
    -- the shrine square itself is the ported part (shrine_pos).
  - mkswamp(): needs the sanctioned terrain mutator (set_levltyp), the
    engraving removal and eel/fungus generation.
  - fill_zoo() (COURT / ZOO / BEEHIVE / MORGUE / BARRACKS / LEPREHALL /
    COCKNEST / ANTHOLE): needs makemon()/mksobj()/mkgold()/make_grave()
    -- i.e. the monster and object distribution, the same machinery
    the worldgen docstring documents as deferred (PLAN-STAIRS.md §5).
  - courtmon()/squadmon()/morguemon()/antholemon()/mkundead(): need
    mkclass() and the monster-generation tables.
  - cmap_to_type(): needs the display symbol table (S_* -> terrain).

Simplifications (documented, not bugs):

  - the room *contents* of a special room are not stocked at all: the
    level generator only records the room type, so a ZOO is a room
    that knows it is a zoo.  Every handler states its C provenance so
    the stocking half can land later without re-reading the C.
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

from typing import Iterable, List, Optional

from .types import (ANY_SHOP, ANY_TYPE, Map, Pos, Room, RoomType, Stairway,
                    TerrainType, is_door, is_furniture, is_pool, is_sdoor,
                    is_wall)


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
    return (room.lx - 1 <= x <= room.hx + 1
            and room.ly - 1 <= y <= room.hy + 1)


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
        in_sub = any(sl.lx - 1 <= pos[0] <= sl.hx + 1
                     and sl.ly - 1 <= pos[1] <= sl.hy + 1
                     for sl in (map_.subrooms[i] for i in room.sbrooms))
        if in_sub:
            continue
        return pos
    return None


def somexyspace(map_: Map, traps: Iterable, room: Room,
                rng) -> Optional[Pos]:
    """C: mkroom.c#somexyspace -- a *free, standable* square inside the
    room (somexy's answer filtered by "not occupied and ROOM/CORR/ICE").

    C is a do/while: after 100 failed tries the last answer is returned
    anyway, so a full room still yields a position (the callers then do
    whatever C does with a bad one).
    """
    pos: Optional[Pos] = None
    for _ in range(101):
        pos = somexy(map_, room, rng)
        if pos is not None \
                and not occupied(map_, traps, pos) \
                and map_.tile_at(pos).typ in (TerrainType.ROOM,
                                              TerrainType.CORR,
                                              TerrainType.ICE):
            return pos
    return pos


def shrine_pos(map_: Map, traps: Iterable, room: Room,
               rng) -> Optional[Pos]:
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
    if (tile is None or tile.roomno != map_.room_of(room)
            or tile.typ not in (TerrainType.ROOM, TerrainType.ICE,
                                TerrainType.CLOUD)):
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
        for y in range(max(insidey - 1, room.ly),
                       min(insidey + 1, room.hy) + 1):
            if (x, y) != (insidex, insidey) \
                    and map_.tile_at((x, y)).typ == TerrainType.ROOM:
                count += 1
    return count == 1


# ============================================================
# Room lookup
# ============================================================

def pick_room(map_: Map, stairs: Iterable[Stairway], rng,
              strict: bool) -> Optional[Room]:
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
            if has_upstairs(map_, stairs, room) \
                    or (has_dnstairs(map_, stairs, room) and rng.rn2(3)):
                continue
        elif has_upstairs(map_, stairs, room) \
                or has_dnstairs(map_, stairs, room):
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
        if (rtype == ANY_TYPE and room.rtype != RoomType.OROOM) \
                or (rtype == ANY_SHOP and room.rtype >= RoomType.SHOPBASE) \
                or room.rtype == rtype:
            return room
    return None


def room_of_stair(map_: Map, stairs: Iterable[Stairway],
                  up: bool) -> Optional[Room]:
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

def do_mkroom(map_: Map, stairs: Iterable[Stairway], traps: Iterable,
              rng, roomtype: RoomType) -> Optional[Room]:
    """C: mkroom.c#do_mkroom -- make and stock a room of the given type.

    Returns the room that was claimed, or None when no eligible room
    was found (C returns void and leaves the level alone).

    Only the room *selection* is ported (see mkzoo); the stocking
    handlers are STUBs, so a shop / temple / swamp raises
    NotImplementedError naming the C it waits for.
    """
    if roomtype >= RoomType.SHOPBASE:
        return mkshop(map_, stairs, rng)
    if roomtype == RoomType.TEMPLE:
        return mktemple(map_, stairs, traps, rng)
    if roomtype == RoomType.SWAMP:
        return mkswamp(map_, stairs, rng)
    if roomtype in (RoomType.COURT, RoomType.ZOO, RoomType.BEEHIVE,
                    RoomType.MORGUE, RoomType.BARRACKS,
                    RoomType.LEPREHALL, RoomType.COCKNEST,
                    RoomType.ANTHOLE):
        return mkzoo(map_, stairs, rng, roomtype)
    raise ValueError(f"Tried to make a room of type {roomtype}.")


def mkzoo(map_: Map, stairs: Iterable[Stairway], rng,
          rtype: RoomType) -> Optional[Room]:
    """C: mkroom.c#mkzoo -- claim a random room for a zoo-like special
    room (COURT / ZOO / BEEHIVE / MORGUE / BARRACKS / LEPREHALL /
    COCKNEST / ANTHOLE).

    C only sets the rtype here and leaves the stocking to fill_zoo() at
    the end of makelevel(); pyhack does the same, so the model of the
    level is complete even though the contents are not.
    """
    room = pick_room(map_, stairs, rng, False)
    if room is None:
        return None
    room.rtype = rtype
    return room


def fill_zoo(map_: Map, traps: Iterable, room: Room, rng) -> None:
    """C: mkroom.c#fill_zoo -- stock a zoo-like special room.

    STUB: needs makemon(), mksobj(), mkgold() and make_grave() -- the
    monster / object distribution that is not ported yet (the same
    reason new levels carry no floor items, PLAN-STAIRS.md §5).  The
    per-type contents: COURT -> a throne + courtmon() + the royal
    coffers; ZOO/LEPREHALL -> gold per square; MORGUE -> corpses,
    chests, graves, undead; BEEHIVE -> queen bee + killer bees + royal
    jelly; BARRACKS -> squadmon() + pay chests; COCKNEST -> cockatrices
    + statue eggs; ANTHOLE -> ants + food.
    """
    raise NotImplementedError(
        "special-room stocking needs makemon/mksobj/mkgold (C: "
        "src/mkroom.c fill_zoo())")


def mkshop(map_: Map, stairs: Iterable[Stairway],
           rng) -> Optional[Room]:
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
        "(C: src/mkroom.c mkshop())")


def mktemple(map_: Map, stairs: Iterable[Stairway], traps: Iterable,
             rng) -> Optional[Room]:
    """C: mkroom.c#mktemple -- a temple: a shrine (blessed altar) in
    the room's center and a priest standing on it.

    STUB: the altar needs the ALTAR altarmask (not ported) and the
    priest needs src/priest.c priestini(); shrine_pos() above is the
    ported half (it picks the square).
    """
    raise NotImplementedError(
        "temples need the altar altarmask and priest.c priestini() "
        "(C: src/mkroom.c mktemple())")


def mkswamp(map_: Map, stairs: Iterable[Stairway],
            rng) -> Optional[Room]:
    """C: mkroom.c#mkswamp -- flood up to five rooms with pools.

    STUB: needs the sanctioned terrain mutator (C: set_levltyp), the
    engraving removal (C: del_engr_at) and monster generation for the
    eels / fungus.  The checkerboard rule ((sx+sy) % 2) and the
    nexttodoor() guard are the ported part of the shape.
    """
    raise NotImplementedError(
        "swamps need set_levltyp and monster generation (C: "
        "src/mkroom.c mkswamp())")


def courtmon(rng) -> None:
    """C: mkroom.c#courtmon -- a random court monster (dragon / giant /
    troll / centaur / orc / bugbear / hobgoblin / gnome / kobold by
    depth).

    STUB: needs mkclass() and the monster tables.
    """
    raise NotImplementedError(
        "court monsters need mkclass() (C: src/mkroom.c courtmon())")


def squadmon(rng) -> None:
    """C: mkroom.c#squadmon -- soldier / sergeant / lieutenant /
    captain by a rnd(80 + depth) roll.

    STUB: needs mkclass() and the per-monster "genocided" vitals table
    (svm.mvitals).
    """
    raise NotImplementedError(
        "squad monsters need mkclass()/mvitals (C: src/mkroom.c "
        "squadmon())")


def morguemon(rng) -> None:
    """C: mkroom.c#morguemon -- ghost / wraith / zombie / vampire /
    demon by depth.

    STUB: needs mkclass() and ndemon().
    """
    raise NotImplementedError(
        "morgue monsters need mkclass()/ndemon() (C: src/mkroom.c "
        "morguemon())")


def antholemon(rng) -> None:
    """C: mkroom.c#antholemon -- one of the three ant types, the same
    one for the whole level (derived from the game birth time plus the
    depth).

    STUB: needs the monster tables (PM_SOLDIER_ANT / PM_FIRE_ANT /
    PM_GIANT_ANT) and the genocide vitals.
    """
    raise NotImplementedError(
        "ant-hill monsters need the monster tables (C: src/mkroom.c "
        "antholemon())")


def mkundead(pos: Pos, rng) -> None:
    """C: mkroom.c#mkundead -- a swarm of undead around a position
    ((depth + 1) / 10 + rnd(5) of them), which also sets the level's
    graveyard flag.

    STUB: needs morguemon(), enexto() and makemon().
    """
    raise NotImplementedError(
        "undead swarms need morguemon()/makemon() (C: src/mkroom.c "
        "mkundead())")


def mk_zoo_thronemon(pos: Pos, rng) -> None:
    """C: mkroom.c#mk_zoo_thronemon -- the throne-room monarch (gnome
    ruler / dwarf ruler / elven monarch / ogre tyrant by depth), asleep
    and hostile, carrying a mace.

    STUB: needs makemon() / mongets().
    """
    raise NotImplementedError(
        "the throne monarch needs makemon() (C: src/mkroom.c "
        "mk_zoo_thronemon())")


# The public surface, kept explicit so the STUBs announce themselves.
__all__ = [
    "ANY_SHOP", "ANY_TYPE",
    "antholemon", "courtmon", "do_mkroom", "fill_zoo", "has_dnstairs",
    "has_upstairs", "inside_room", "invalid_shop_shape", "isbig",
    "mk_zoo_thronemon", "mkshop", "mkswamp", "mktemple", "mkundead",
    "mkzoo", "morguemon", "nexttodoor", "occupied", "pick_room",
    "room_of_stair", "search_special", "shrine_pos", "somex", "somexy",
    "somexyspace", "somey", "squadmon",
]
