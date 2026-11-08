"""Level generation: rooms, corridors, doors.

The third level generator in pyhack and the first one that *looks* like
NetHack: rectangular rooms laid out on a shrinking free-rectangle list,
walls and corners painted around them, corridors dug between them, and
doors (including secret and locked ones) punched where a corridor meets
a wall.  Niches -- the one-tile alcoves with a secret door -- come last.

C provenance:

  src/mklev.c    sort_rooms(), mkroom_cmp(), good_rm_wall_doorpos(),
                 finddpos_shift(), finddpos(), do_room_or_subroom(),
                 add_room(), add_subroom(), makerooms(), join(),
                 makecorridors(), add_door(), dosdoor(), dodoor(),
                 bydoor(), okdoor(), maybe_sdoor(), occupied() (in
                 core.mkroom), cardinal_nextto_room(), place_niche(),
                 makeniche(), make_niches(), makevtele(),
                 count_level_features(), clear_level_structures(),
                 fill_ordinary_room(), topologize(),
                 level_finalize_topology(), mktrap() (the demo subset),
                 mkstairs(), generate_stairs_room_good(),
                 generate_stairs_find_room(), generate_stairs() and
                 makelevel() -- the rooms + corridors branch
  src/sp_lev.c   check_room(), create_room(), create_subroom(),
                 dig_corridor(), wallify_map()
  src/rect.c     init_rect(), get_rect(), rnd_rect(), remove_rect(),
                 add_rect(), split_rects(), intersect() -- the
                 RectManager class below
  src/mkmap.c    litstate_rnd() (used by create_room; ported in
                 core.mkmap)

Included: the whole rooms/corridors/doors pipeline, in the C draw
order, so a later port of the stocking half does not have to re-derive
the sequence.

STUBs (announced where they are, never silently skipped):

  - the Lua themed-room hook of makerooms() (themerms_generate and
    friends): C loads dat/*.lua per dungeon; pyhack has no Lua and no
    themed rooms, so makerooms() is the plain rectangle loop.
  - the vault (create_vault() / do_vault() / mk_knox_portal()): needs
    the special-room stocking (fill_special_room, mkgold) plus the
    portal machinery.  makelevel() never asks for one.
  - fill_ordinary_room()'s contents: the monster comes from the real
    distribution (core.makemon -- the old three-demo-kind subset is
    gone) and the traps from the demo trap kit (mktrap() below).  The
    object half places gold, a fountain, a sink, an altar, a grave, a
    statue and a final random object (core.mkobj + the mkfount / mksink /
    mkaltar / mkgrave terrain writers below); the bonus item, the chest
    and the engravings (make_engr_at) are the remaining STUBs, their
    rolls not taken (see _fill_room_objects).
  - mktrap(): C's traptype_rnd() depth table, the dead adventurer
    (mktrap_victim), the rolling-boulder launch path and the
    once/impossible flags.  The trap types the demo implements are
    placed.
  - makeniche()'s treasure (the teleportation scroll, the random
    object, the iron bars + corpse, the dungeon branch): no mkobj.
  - the shop / temple / zoo stocking: see core.mkroom.

Simplifications (documented, not bugs):

  - the C functions read the ambient level state (svr.rooms,
    gs.smeq[], gd.doorindex, svd.doors[]); here the Map is a parameter
    and the transient per-level arrays (smeq, the stairways placed so
    far) are explicit arguments.  That is what makes it possible to
    generate a level that is *not* the current one -- levels 2..N come
    out of goto_level lazily while the hero still stands on level N-1.
  - the level's size comes from the Map, not COLNO/ROWNO: the C
    expressions are evaluated on map.width / map.height, so the demo
    grid stays 40x20 and a bigger grid needs no change.
  - `create_room`'s xlim/ylim are only widened for VAULT in C; with no
    vault the two constants are XLIM / YLIM throughout.
  - C's impossible() calls become refusals (None / False): a generated
    level must never abort the game over a geometry edge case, and
    every refusal is commented with the C branch it stands for.
  - sort_rooms() sorts stably (Python's sorted) where C uses qsort:
    the order of two rooms with the same left edge may differ, which
    changes nothing but which corridor is dug first.
  - create_room() numbers its room immediately (topologize), where
    the C classic path leaves roomno alone until
    level_finalize_topology() -- which runs after makecorridors(),
    whose good_rm_wall_doorpos() needs the number.  C's sp_lev path
    does exactly this explicitly ("topologize(aroom); /* set roomno
    */"), so the result is the level C would build.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .mkmap import litstate_rnd
from .mkroom import (do_mkroom, has_dnstairs, has_upstairs, occupied,
                     somexyspace)
from .monst_defs import align2amask
from .types import (LevelFlags, MAXNROFROOMS, ROOMOFFSET, SHARED, DoorMask,
                    Map, Pos, Room, RoomType, STAIR_DOWN, STAIR_UP, Stairway,
                    TerrainType, Tile, Trap, TrapType, World, is_door,
                    is_furniture, is_lava, is_obstructed, is_pool, is_room,
                    is_wall)


# C: sp_lev.c -- the minimum distance kept between a room and anything
# else / the level edge, and the alignment codes of create_room().
XLIM = 4
YLIM = 3
SPLEV_LEFT = 1
SPLEV_CENTER = 3
SPLEV_RIGHT = 5
TOP = 1
BOTTOM = 5

# C: global.h -- doors are allocated in blocks of DOORINC; a Python list
# grows by itself, the constant is kept for the docstring's sake.
DOORINC = 20

# The four compass directions, as the C xdir/ydir tables spell them.
DIR_N = "n"
DIR_S = "s"
DIR_E = "e"
DIR_W = "w"
_DIR_VEC = {DIR_N: (0, -1), DIR_S: (0, 1), DIR_E: (1, 0), DIR_W: (-1, 0)}
_DIR_180 = {DIR_N: DIR_S, DIR_S: DIR_N, DIR_E: DIR_W, DIR_W: DIR_E}


# ============================================================
# The free-rectangle manager (C: src/rect.c)
# ============================================================

@dataclass
class Rect:
    """C: struct NhRect -- an inclusive rectangle."""
    lx: int
    ly: int
    hx: int
    hy: int

    def contains(self, other: "Rect") -> bool:
        return (other.lx >= self.lx and other.ly >= self.ly
                and other.hx <= self.hx and other.hy <= self.hy)


class RectManager:
    """The list of free rectangles a level is cut out of (C: rect.c's
    static rect[] / rect_cnt / n_rects triple, which is per-level
    global state in C and an object here).

    Every room carves its bounding box (plus a margin) out of one free
    rectangle; split_rects() then slices that rectangle into up to four
    remainders.  This is what keeps rooms from overlapping without any
    collision search.
    """

    def __init__(self, map_: Map):
        self.width = map_.width
        self.height = map_.height
        self.rects: List[Rect] = [Rect(0, 0, map_.width - 1,
                                       map_.height - 1)]

    def rnd_rect(self, rng) -> Optional[Rect]:
        """C: rect.c#rnd_rect -- some free rectangle, or None when the
        level is used up."""
        if not self.rects:
            return None
        return self.rects[rng.rn2(len(self.rects))]

    def get_rect(self, r: Rect) -> Optional[Rect]:
        """C: rect.c#get_rect -- the free rectangle that contains `r`."""
        for rect in self.rects:
            if rect.contains(r):
                return rect
        return None

    def remove_rect(self, r: Rect) -> None:
        """C: rect.c#remove_rect -- drop a rectangle by value (C finds
        its index with get_rect_ind() and swaps the last entry in)."""
        for i, rect in enumerate(self.rects):
            if rect == r:
                self.rects[i] = self.rects[-1]
                self.rects.pop()
                return

    def add_rect(self, r: Rect) -> None:
        """C: rect.c#add_rect -- register a free rectangle (skipped when
        an existing one already contains it)."""
        if self.get_rect(r) is not None:
            return
        self.rects.append(r)

    def split_rects(self, r1: Rect, r2: Rect) -> None:
        """C: rect.c#split_rects -- r2 was allocated inside r1: drop r1
        and re-add its four remainders around r2.

        The `> margin + 4` tests are C's "is there enough room left to
        be worth a rectangle"; the margin widens to 2*LIM when the old
        rectangle stops short of the level edge, because a room placed
        there needs the full gap and not just the edge allowance.
        """
        old_r = r1
        self.remove_rect(r1)
        for rect in list(reversed(self.rects)):
            inter = _intersect(rect, r2)
            if inter is not None:
                self.split_rects(rect, inter)
        if r2.ly - old_r.ly - 1 > (
                2 * YLIM if old_r.hy < self.height - 1 else YLIM + 1) + 4:
            self.add_rect(Rect(old_r.lx, old_r.ly, old_r.hx, r2.ly - 2))
        if r2.lx - old_r.lx - 1 > (
                2 * XLIM if old_r.hx < self.width - 1 else XLIM + 1) + 4:
            self.add_rect(Rect(old_r.lx, old_r.ly, r2.lx - 2, old_r.hy))
        if old_r.hy - r2.hy - 1 > (
                2 * YLIM if old_r.ly > 0 else YLIM + 1) + 4:
            self.add_rect(Rect(old_r.lx, r2.hy + 2, old_r.hx, old_r.hy))
        if old_r.hx - r2.hx - 1 > (
                2 * XLIM if old_r.lx > 0 else XLIM + 1) + 4:
            self.add_rect(Rect(r2.hx + 2, old_r.ly, old_r.hx, old_r.hy))


def _intersect(r1: Rect, r2: Rect) -> Optional[Rect]:
    """C: rect.c#intersect -- the overlap of two rectangles, if any."""
    if r2.lx > r1.hx or r2.ly > r1.hy or r2.hx < r1.lx or r2.hy < r1.ly:
        return None
    out = Rect(max(r2.lx, r1.lx), max(r2.ly, r1.ly),
               min(r2.hx, r1.hx), min(r2.hy, r1.hy))
    if out.lx > out.hx or out.ly > out.hy:
        return None
    return out


# ============================================================
# Rooms on the map (C: mklev.c do_room_or_subroom / add_room)
# ============================================================

def blank_map(width: int, height: int) -> Map:
    """A fresh all-STONE level (C: clear_level_structures() -- every
    location is stone, owned by no room, unlit)."""
    return Map([[Tile(typ=TerrainType.STONE) for _ in range(width)]
                for _ in range(height)])


def _set(map_: Map, x: int, y: int, typ: TerrainType,
         horizontal: Optional[bool] = None) -> None:
    """Write a terrain type, clamped to the level (the generators work
    on rectangles that may touch the edge)."""
    if not map_.in_bounds((x, y)):
        return
    tile = map_.tiles[y][x]
    tile.typ = typ
    if horizontal is not None:
        tile.horizontal = horizontal


def do_room_or_subroom(map_: Map, room: Room, lowx: int, lowy: int,
                       hix: int, hiy: int, lit: bool, rtype: RoomType,
                       special: bool, whole_room: bool) -> None:
    """C: mklev.c#do_room_or_subroom -- record the room and paint it.

    `special` rooms are only recorded (their terrain is drawn by the
    caller); an ordinary room gets its wall ring (HWALL top and bottom,
    VWALL left and right), its ROOM floor, and -- for a whole room (C's
    `is_room` argument; the other case is a subroom) -- the four corner
    types.  A subroom inside another room runs wallify_map() over its
    ring instead, because its ring is already surrounded by room floor
    (C calls the fancier wallification() of mkmaze.c there; see the
    module docstring).
    """
    if not lowx:
        lowx += 1
    if not lowy:
        lowy += 1
    if hix >= map_.width - 1:
        hix = map_.width - 2
    if hiy >= map_.height - 1:
        hiy = map_.height - 2

    if lit:
        for x in range(lowx - 1, hix + 2):
            for y in range(max(lowy - 1, 0), hiy + 2):
                if map_.in_bounds((x, y)):
                    map_.tiles[y][x].lit = True
        room.rlit = True
    else:
        room.rlit = False

    room.roomnoidx = 0  # set by the caller (add_room / add_subroom)
    room.lx, room.hx = lowx, hix
    room.ly, room.hy = lowy, hiy
    room.rtype = rtype
    room.orig_rtype = rtype
    room.doors = []
    room.irregular = False
    room.sbrooms = []
    if special:
        return

    room.needjoining = True
    for x in range(lowx - 1, hix + 2):
        for y in (lowy - 1, hiy + 1):
            _set(map_, x, y, TerrainType.HWALL, horizontal=True)
    for x in (lowx - 1, hix + 1):
        for y in range(lowy, hiy + 1):
            _set(map_, x, y, TerrainType.VWALL, horizontal=False)
    for x in range(lowx, hix + 1):
        for y in range(lowy, hiy + 1):
            _set(map_, x, y, TerrainType.ROOM)
    if whole_room:
        _set(map_, lowx - 1, lowy - 1, TerrainType.TLCORNER)
        _set(map_, hix + 1, lowy - 1, TerrainType.TRCORNER)
        _set(map_, lowx - 1, hiy + 1, TerrainType.BLCORNER)
        _set(map_, hix + 1, hiy + 1, TerrainType.BRCORNER)
    else:
        wallify_map(map_, lowx - 1, lowy - 1, hix + 1, hiy + 1)


def add_room(map_: Map, lowx: int, lowy: int, hix: int, hiy: int,
             lit: bool, rtype: RoomType = RoomType.OROOM,
             special: bool = False,
             smeq: Optional[List[int]] = None) -> Room:
    """C: mklev.c#add_room -- append a room to the level.

    `smeq` is C's gs.smeq[] ("same corridor component"): an entry per
    room, initialised to the room's own index so makecorridors() can
    tell which rooms are already connected.
    """
    room = Room(lx=lowx, ly=lowy, hx=hix, hy=hiy)
    idx = len(map_.rooms)
    map_.rooms.append(room)
    do_room_or_subroom(map_, room, lowx, lowy, hix, hiy, lit, rtype,
                       special, True)
    room.roomnoidx = idx
    if smeq is not None:
        smeq.append(idx)
    return room


def add_subroom(map_: Map, proom: Room, lowx: int, lowy: int, hix: int,
                hiy: int, lit: bool, rtype: RoomType = RoomType.OROOM,
                special: bool = False) -> Room:
    """C: mklev.c#add_subroom -- a room inside a room (themed rooms,
    shops with a back room).  Nothing generates one yet; the geometry
    is here so sp_lev can."""
    room = Room(lx=lowx, ly=lowy, hx=hix, hy=hiy)
    idx = len(map_.subrooms)
    map_.subrooms.append(room)
    do_room_or_subroom(map_, room, lowx, lowy, hix, hiy, lit, rtype,
                       special, False)
    room.roomnoidx = idx
    proom.sbrooms.append(idx)
    return room


def create_subroom(map_: Map, proom: Room, rng, depth: int, x: int = -1,
                   y: int = -1, w: int = -1, h: int = -1,
                   rtype: int = -1, rlit: int = 1) -> Optional[Room]:
    """C: sp_lev.c#create_subroom -- a subroom of `proom` with random
    position / size where the arguments are -1."""
    width = proom.hx - proom.lx + 1
    height = proom.hy - proom.ly + 1
    if width < 4 or height < 4:
        return None
    if w == -1:
        w = rng.rnd(width - 3)
    if h == -1:
        h = rng.rnd(height - 3)
    if x == -1:
        x = rng.rnd(width - w)
    if y == -1:
        y = rng.rnd(height - h)
    if x == 1:
        x = 0
    if y == 1:
        y = 0
    if x + w + 1 == width:
        x += 1
    if y + h + 1 == height:
        y += 1
    if rtype == -1:
        rtype = int(RoomType.OROOM)
    lit = litstate_rnd(rng, rlit, depth)
    return add_subroom(map_, proom, proom.lx + x, proom.ly + y,
                       proom.lx + x + w - 1, proom.ly + y + h - 1,
                       lit, RoomType(rtype), False)


def sort_rooms(map_: Map) -> None:
    """C: mklev.c#sort_rooms -- order the rooms left to right and
    renumber the level, so makecorridors() can link room N to N+1."""
    n = len(map_.rooms)
    order = sorted(range(n), key=lambda i: map_.rooms[i].lx)
    remap = {}
    for new, old in enumerate(order):
        remap[map_.rooms[old].roomnoidx] = new
    map_.rooms = [map_.rooms[old] for old in order]
    for i, room in enumerate(map_.rooms):
        room.roomnoidx = i
    for x in range(1, map_.width):
        for y in range(map_.height):
            rno = map_.tiles[y][x].roomno
            if ROOMOFFSET <= rno < MAXNROFROOMS + 1:
                idx = remap.get(rno - ROOMOFFSET)
                if idx is not None:
                    map_.tiles[y][x].roomno = idx + ROOMOFFSET


# ============================================================
# Room placement (C: sp_lev.c check_room / create_room)
# ============================================================

def check_room(map_: Map, lowx: int, lowy: int, ddx: int, ddy: int,
               rng) -> Optional[Tuple[int, int, int, int]]:
    """C: sp_lev.c#check_room -- is the (lowx, lowy) + (ddx, ddy) box
    clear of everything else?

    Returns the *clamped / shrunk* (lowx, lowy, ddx, ddy) the room
    should use, or None when the spot is taken.  C shrinks the box
    around the offending terrain and re-checks, with a 1-in-3 bail-out
    each time -- that is why rooms can end up smaller than asked for.
    """
    width, height = map_.width, map_.height
    hix = lowx + ddx
    hiy = lowy + ddy
    if lowx < 3:
        lowx = 3
    if lowy < 2:
        lowy = 2
    if hix > width - 3:
        hix = width - 3
    if hiy > height - 3:
        hiy = height - 3
    while True:
        if hix <= lowx or hiy <= lowy:
            return None
        shrunk = False
        for x in range(lowx - XLIM, hix + XLIM + 1):
            if x <= 0 or x >= width:
                continue
            y0 = max(lowy - YLIM, 0)
            ymax = min(hiy + YLIM, height - 1)
            for y in range(y0, ymax + 1):
                if map_.tiles[y][x].typ == TerrainType.STONE:
                    continue
                # C: "strange area in check_room" -- something is
                # already here; maybe give up, otherwise shrink
                if not rng.rn2(3):
                    return None
                if x < lowx:
                    lowx = x + XLIM + 1
                else:
                    hix = x - XLIM - 1
                if y < lowy:
                    lowy = y + YLIM + 1
                else:
                    hiy = y - YLIM - 1
                shrunk = True
                break
            if shrunk:
                break
        if not shrunk:
            break
    return lowx, lowy, hix - lowx, hiy - lowy


def create_room(map_: Map, rects: RectManager, rng, depth: int,
                x: int = -1, y: int = -1, w: int = -1, h: int = -1,
                xal: int = -1, yal: int = -1, rtype: int = -1,
                rlit: int = 1,
                smeq: Optional[List[int]] = None) -> Optional[Room]:
    """C: sp_lev.c#create_room -- make a room, all parameters random
    where they are -1.

    Two paths, exactly as in C: with *every* parameter random the room
    is carved out of a random free rectangle (the classic NetHack
    layout), otherwise the position comes from the 5x5 alignment grid
    and the free-rectangle list only has to contain it.
    """
    width, height = map_.width, map_.height
    if rtype == -1:
        rtype = int(RoomType.OROOM)
    is_lit = litstate_rnd(rng, rlit, depth)

    xabs = yabs = 0
    wtmp = htmp = 0
    r1: Optional[Rect] = None
    r2 = Rect(0, 0, 0, 0)
    trycnt = 0
    while True:
        wtmp, htmp = w, h
        xtmp, ytmp = x, y
        xaltmp, yaltmp = xal, yal
        r1 = None
        if xtmp < 0 and ytmp < 0 and wtmp < 0 and xaltmp < 0 and yaltmp < 0:
            # totally random room, from a free rectangle
            cand = rects.rnd_rect(rng)
            if cand is not None:
                hx, hy, lx, ly = cand.hx, cand.hy, cand.lx, cand.ly
                dx = 2 + rng.rn2(12 if hx - lx > 28 else 8)
                dy = 2 + rng.rn2(4)
                if dx * dy > 50:
                    dy = 50 // dx
                xborder = 2 * XLIM if (lx > 0 and hx < width - 1) \
                    else XLIM + 1
                yborder = 2 * YLIM if (ly > 0 and hy < height - 1) \
                    else YLIM + 1
                if hx - lx < dx + 3 + xborder or hy - ly < dy + 3 + yborder:
                    cand = None
                else:
                    xbase = lx if lx > 0 else 3
                    ybase = ly if ly > 0 else 2
                    xabs = lx + (XLIM if lx > 0 else 3) + rng.rn2(
                        hx - xbase - dx - xborder + 1)
                    yabs = ly + (YLIM if ly > 0 else 2) + rng.rn2(
                        hy - ybase - dy - yborder + 1)
                    if (ly == 0 and hy >= height - 1
                            and (not map_.rooms
                                 or not rng.rn2(len(map_.rooms)))
                            and yabs + dy > height // 2):
                        yabs = rng.rn1(3, 2)
                        if len(map_.rooms) < 4 and dy > 1:
                            dy -= 1
                    res = check_room(map_, xabs, yabs, dx, dy, rng)
                    if res is None:
                        cand = None
                    else:
                        xabs, yabs, dx, dy = res
                        wtmp = dx + 1
                        htmp = dy + 1
                        r2 = Rect(xabs - 1, yabs - 1, xabs + wtmp,
                                  yabs + htmp)
                        r1 = cand
        else:
            # only some parameters are random
            rndpos = 0
            if xtmp < 0 and ytmp < 0:
                xtmp = rng.rnd(5)
                ytmp = rng.rnd(5)
                rndpos = 1
            if wtmp < 0 or htmp < 0:
                wtmp = rng.rn1(15, 3)
                htmp = rng.rn1(8, 2)
            if xaltmp == -1:
                xaltmp = rng.rnd(3)
            if yaltmp == -1:
                yaltmp = rng.rnd(3)
            xabs = ((xtmp - 1) * width) // 5 + 1
            yabs = ((ytmp - 1) * height) // 5 + 1
            if xaltmp == SPLEV_RIGHT:
                xabs += (width // 5) - wtmp
            elif xaltmp == SPLEV_CENTER:
                xabs += ((width // 5) - wtmp) // 2
            if yaltmp == BOTTOM:
                yabs += (height // 5) - htmp
            elif yaltmp == SPLEV_CENTER:
                yabs += ((height // 5) - htmp) // 2
            if xabs + wtmp - 1 > width - 2:
                xabs = width - wtmp - 3
            if xabs < 2:
                xabs = 2
            if yabs + htmp - 1 > height - 2:
                yabs = height - htmp - 3
            if yabs < 2:
                yabs = 2
            r2 = Rect(xabs - 1, yabs - 1, xabs + wtmp + rndpos,
                      yabs + htmp + rndpos)
            cand = rects.get_rect(r2)
            dx, dy = wtmp, htmp
            if cand is not None:
                res = check_room(map_, xabs, yabs, dx, dy, rng)
                if res is None:
                    cand = None
                else:
                    # NOTE: C keeps wtmp/htmp here (unlike the random
                    # branch above), so a shrunk box only moves
                    xabs, yabs, _, _ = res
                    r1 = cand
        trycnt += 1
        if r1 is not None or trycnt > 100:
            break
    if r1 is None:
        # C: "creation of room failed?"
        return None
    rects.split_rects(r1, r2)
    room = add_room(map_, xabs, yabs, xabs + wtmp - 1, yabs + htmp - 1,
                    is_lit, RoomType(rtype), False, smeq)
    # Number the room now (C: sp_lev.c's lspo_room calls topologize()
    # right after creating a room -- "set roomno"; the classic path
    # only numbers the level in level_finalize_topology(), which runs
    # *after* makecorridors()).  good_rm_wall_doorpos() reads the
    # roomno of the square inside a wall, so without this every door /
    # corridor placement would fail and the level would have no
    # corridors at all.  sort_rooms() renumbers afterwards, and the
    # final level_finalize_topology() pass is then a no-op.
    topologize(map_, room)
    return room


def makerooms(map_: Map, rects: RectManager, rng, depth: int,
              smeq: List[int]) -> None:
    """C: mklev.c#makerooms -- fill the level with rooms.

    C first gives the dungeon's Lua themed-room script a chance on every
    iteration and takes a detour into the vault once (create_vault);
    neither is ported (see the module docstring), so this is the plain
    `while there is free space: create_room()` loop.
    """
    while len(map_.rooms) < MAXNROFROOMS - 1 \
            and rects.rnd_rect(rng) is not None:
        if create_room(map_, rects, rng, depth, smeq=smeq) is None:
            break


# ============================================================
# Doors (C: mklev.c bydoor / okdoor / dodoor / dosdoor / add_door)
# ============================================================

def bydoor(map_: Map, x: int, y: int) -> bool:
    """C: mklev.c#bydoor -- a door or secret door on a cardinal
    neighbour (keeps doors from clustering)."""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pos = (x + dx, y + dy)
        if not map_.in_bounds(pos):
            continue
        typ = map_.tile_at(pos).typ
        if is_door(typ) or typ == TerrainType.SDOOR:
            return True
    return False


def okdoor(map_: Map, x: int, y: int) -> bool:
    """C: mklev.c#okdoor -- may a door be made here?

    A vertical or horizontal wall (not a corner), with at least one
    open square next to it and no door already adjacent.
    """
    if map_.tile_at((x, y)).typ not in (TerrainType.HWALL,
                                        TerrainType.VWALL):
        return False
    if bydoor(map_, x, y):
        return False
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pos = (x + dx, y + dy)
        if map_.in_bounds(pos) and not is_obstructed(map_.tile_at(pos).typ):
            return True
    return False


def maybe_sdoor(rng, depth: int, chance: int) -> bool:
    """C: mklev.c#maybe_sdoor -- a secret door instead of a real one:
    never on the first two levels, then 1-in-max(2, chance)."""
    return depth > 2 and not rng.rn2(max(2, chance))


def add_door(map_: Map, x: int, y: int, room: Room) -> None:
    """C: mklev.c#add_door -- record a door for the room (and for the
    level).

    C keeps one array with a per-room index range and shifts it on
    every insertion; pyhack keeps the per-room list plus the level-wide
    Map.doors list, which carries the same information (see
    core.types.Room).
    """
    if (x, y) in room.doors:
        return
    room.doors.append((x, y))
    map_.doors.append((x, y))


def dosdoor(map_: Map, rng, depth: int, x: int, y: int, room: Room,
            typ: TerrainType) -> None:
    """C: mklev.c#dosdoor -- make a door (or secret door) at x,y.

    The state is C's doormask lottery: 2/3 of doors are plain doorways,
    the rest are 1-in-5 open, 1-in-6 locked, else closed; closed doors
    can be trapped from depth 5.  A trap deep enough becomes a mimic in
    C -- that needs makemon() (not ported), so the square is left as an
    empty doorway and the roll is kept (the draws stay in C order).
    """
    tile = map_.tile_at((x, y))
    shdoor = False
    shop = map_.room_at((x, y))
    if shop is not None and shop.rtype >= RoomType.SHOPBASE:
        shdoor = True
    if not is_wall(tile.typ):  # C: avoid S.doors on already made doors
        typ = TerrainType.DOOR
    horizontal = tile.horizontal
    mask = DoorMask(0)
    if typ == TerrainType.DOOR:
        if not rng.rn2(3):
            if not rng.rn2(5):
                mask = DoorMask.ISOPEN
            elif not rng.rn2(6):
                mask = DoorMask.LOCKED
            else:
                mask = DoorMask.CLOSED
            if mask != DoorMask.ISOPEN and not shdoor and depth >= 5 \
                    and not rng.rn2(25):
                mask |= DoorMask.TRAPPED
        else:
            mask = DoorMask.ISOPEN if shdoor else DoorMask(0)  # D_NODOOR
        if mask & DoorMask.TRAPPED and depth >= 9 and not rng.rn2(5):
            # C: a mimic takes the doorway's place (mkclass(S_MIMIC) +
            # set_mimic_sym); monster generation is not ported yet
            mask = DoorMask(0)
    else:  # SDOOR
        if shdoor or not rng.rn2(5):
            mask = DoorMask.LOCKED
        else:
            mask = DoorMask.CLOSED
        if not shdoor and depth >= 4 and not rng.rn2(20):
            mask |= DoorMask.TRAPPED
    new = Tile(typ=typ, door_mask=mask, horizontal=horizontal)
    new.lit = tile.lit
    new.roomno = tile.roomno
    new.edge = tile.edge
    map_.tiles[y][x] = new
    add_door(map_, x, y, room)


def dodoor(map_: Map, rng, depth: int, x: int, y: int, room: Room) -> None:
    """C: mklev.c#dodoor -- a door, secret on the deeper levels."""
    dosdoor(map_, rng, depth, x, y, room,
            TerrainType.SDOOR if maybe_sdoor(rng, depth, 8)
            else TerrainType.DOOR)


# ============================================================
# Corridors (C: mklev.c finddpos / join / makecorridors)
# ============================================================

def good_rm_wall_doorpos(map_: Map, room: Room, x: int, y: int,
                         direction: str) -> bool:
    """C: mklev.c#good_rm_wall_doorpos -- is x,y a good door into
    `room`, looking *into* the room along `direction`?"""
    if not map_.in_bounds((x, y)) or not room.needjoining:
        return False
    typ = map_.tile_at((x, y)).typ
    if typ not in (TerrainType.HWALL, TerrainType.VWALL) \
            and not is_door(typ) and typ != TerrainType.SDOOR:
        return False
    if bydoor(map_, x, y):
        return False
    dx, dy = _DIR_VEC[direction]
    tx, ty = x + dx, y + dy
    if not map_.in_bounds((tx, ty)) \
            or is_obstructed(map_.tile_at((tx, ty)).typ):
        return False
    return map_.tile_at((tx, ty)).roomno == map_.room_of(room)


def finddpos_shift(map_: Map, room: Room, x: int, y: int,
                   direction: str) -> Optional[Pos]:
    """C: mklev.c#finddpos_shift -- walk from x,y towards the room until
    a good door spot turns up.

    For an irregular room the walk starts outside the room's bounding
    box, so it steps through STONE / corridor until it meets the room's
    own wall.
    """
    direction = _DIR_180[direction]
    dx, dy = _DIR_VEC[direction]
    if good_rm_wall_doorpos(map_, room, x, y, direction):
        return (x, y)
    if not room.irregular:
        return None
    rx, ry = x, y
    while map_.in_bounds((rx, ry)) \
            and map_.tile_at((rx, ry)).typ in (TerrainType.STONE,
                                               TerrainType.CORR):
        rx += dx
        ry += dy
        if good_rm_wall_doorpos(map_, room, rx, ry, direction):
            return (rx, ry)
        if map_.tile_at((rx, ry)).typ not in (TerrainType.STONE,
                                              TerrainType.CORR):
            break
        if rx < room.lx or rx > room.hx or ry < room.ly or ry > room.hy:
            break
    return None


def finddpos(map_: Map, room: Room, rng,
             direction: str) -> Optional[Pos]:
    """C: mklev.c#finddpos -- a valid door position on the room's
    `direction` edge: 20 random tries, then an exhaustive scan."""
    if direction == DIR_N:
        x1, x2, y1, y2 = room.lx, room.hx, room.ly - 1, room.ly - 1
    elif direction == DIR_S:
        x1, x2, y1, y2 = room.lx, room.hx, room.hy + 1, room.hy + 1
    elif direction == DIR_W:
        x1, x2, y1, y2 = room.lx - 1, room.lx - 1, room.ly, room.hy
    else:  # DIR_E
        x1, x2, y1, y2 = room.hx + 1, room.hx + 1, room.ly, room.hy
    for _ in range(20):
        x = rng.rn1(x2 - x1 + 1, x1) if x2 != x1 else x1
        y = rng.rn1(y2 - y1 + 1, y1) if y2 != y1 else y1
        pos = finddpos_shift(map_, room, x, y, direction)
        if pos is not None:
            return pos
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            pos = finddpos_shift(map_, room, x, y, direction)
            if pos is not None:
                return pos
    return None


def dig_corridor(map_: Map, rng, depth: int, org: Pos, dest: Pos,
                 nxcor: bool, ftyp: TerrainType,
                 btyp: TerrainType) -> Tuple[bool, int]:
    """C: sp_lev.c#dig_corridor -- dig an L-shaped corridor from org to
    dest, one step at a time, turning when it has to.

    Returns (reached the destination, squares dug).  A `nxcor`
    corridor may stop early: one chance in 35 per step it gives up
    ("a corridor which may be blocked off"), and the STONE it digs
    through sometimes holds a boulder in C (no object creation yet, the
    roll is kept so the draw order stays C's).
    """
    dx = dy = 0
    xx, yy = org
    tx, ty = dest
    if (xx <= 0 or yy <= 0 or tx <= 0 or ty <= 0
            or xx > map_.width - 1 or tx > map_.width - 1
            or yy > map_.height - 1 or ty > map_.height - 1):
        return False, 0
    if tx > xx:
        dx = 1
    elif ty > yy:
        dy = 1
    elif tx < xx:
        dx = -1
    else:
        dy = -1
    xx -= dx
    yy -= dy
    cct = 0
    npoints = 0
    while xx != tx or yy != ty:
        cct += 1
        if cct > 500 or (nxcor and not rng.rn2(35)):
            return False, npoints
        xx += dx
        yy += dy
        if (xx >= map_.width - 1 or xx <= 0 or yy <= 0
                or yy >= map_.height - 1):
            return False, npoints  # C: "impossible"
        tile = map_.tile_at((xx, yy))
        if tile.typ == btyp:
            if ftyp == TerrainType.CORR and maybe_sdoor(rng, depth, 100):
                npoints += 1
                tile.typ = TerrainType.SCORR
            else:
                npoints += 1
                tile.typ = ftyp
                if nxcor and not rng.rn2(50):
                    pass  # C: mksobj_at(BOULDER, ...) -- no objects yet
        elif tile.typ != ftyp and tile.typ != TerrainType.SCORR:
            return False, npoints  # C: "strange ..."
        dix = abs(xx - tx)
        diy = abs(yy - ty)
        if dix > diy and diy and not rng.rn2(dix - diy + 1):
            dix = 0
        elif diy > dix and dix and not rng.rn2(diy - dix + 1):
            diy = 0
        if dy and dix > diy:
            ddx = -1 if xx > tx else 1
            nxt = map_.tile_at((xx + ddx, yy))
            if nxt.typ in (btyp, ftyp, TerrainType.SCORR):
                dx = ddx
                dy = 0
                continue
        elif dx and diy > dix:
            ddy = -1 if yy > ty else 1
            nxt = map_.tile_at((xx, yy + ddy))
            if nxt.typ in (btyp, ftyp, TerrainType.SCORR):
                dy = ddy
                dx = 0
                continue
    return True, npoints


def join(map_: Map, rng, depth: int, smeq: List[int], a: int, b: int,
         nxcor: bool) -> None:
    """C: mklev.c#join -- connect rooms a and b with a corridor.

    The direction is decided by the relative position of the rooms, the
    two door positions by finddpos() on the facing edges, and the
    corridor by dig_corridor().  Both ends get a door.  C's gs.smeq[]
    bookkeeping marks the two rooms as connected.
    """
    croom, troom = map_.rooms[a], map_.rooms[b]
    if not croom.needjoining or not troom.needjoining:
        return
    if troom.lx > croom.hx:
        direction, back = DIR_E, DIR_W
        dx, dy = 1, 0
    elif troom.hy < croom.ly:
        direction, back = DIR_N, DIR_S
        dx, dy = 0, -1
    elif troom.hx < croom.lx:
        direction, back = DIR_W, DIR_E
        dx, dy = -1, 0
    else:
        direction, back = DIR_S, DIR_N
        dx, dy = 0, 1
    cc = finddpos(map_, croom, rng, direction)
    if cc is None:
        return
    tt = finddpos(map_, troom, rng, back)
    if tt is None:
        return
    xx, yy = cc
    tx, ty = tt[0] - dx, tt[1] - dy
    if nxcor and map_.tile_at((xx + dx, yy + dy)).typ != TerrainType.STONE:
        return
    org = (xx + dx, yy + dy)
    dest = (tx, ty)
    dug, npoints = dig_corridor(
        map_, rng, depth, org, dest, nxcor,
        TerrainType.ROOM if map_.flags.arboreal else TerrainType.CORR,
        TerrainType.STONE)
    if npoints > 0 and (okdoor(map_, xx, yy) or not nxcor):
        dodoor(map_, rng, depth, xx, yy, croom)
    if not dug:
        return
    if okdoor(map_, tt[0], tt[1]) or not nxcor:
        dodoor(map_, rng, depth, tt[0], tt[1], troom)
    if smeq[a] < smeq[b]:
        smeq[b] = smeq[a]
    else:
        smeq[a] = smeq[b]


def makecorridors(map_: Map, rng, depth: int, smeq: List[int]) -> None:
    """C: mklev.c#makecorridors -- connect the level.

    Three passes, in C's order: the sorted neighbours (N to N+1), then
    the ones that skipping one room leaves apart (N to N+2), then a
    fix-up pass until every room shares a component with every other.
    A final handful of extra `nxcor` corridors may end in a dead end --
    those are the corridors that stop short in real NetHack levels.
    """
    n = len(map_.rooms)
    for a in range(n - 1):
        join(map_, rng, depth, smeq, a, a + 1, False)
        if not rng.rn2(50):
            break  # allow some randomness
    for a in range(n - 2):
        if smeq[a] != smeq[a + 2]:
            join(map_, rng, depth, smeq, a, a + 2, False)
    a = 0
    any_join = True
    while any_join and a < n:
        any_join = False
        for b in range(n):
            if smeq[a] != smeq[b]:
                join(map_, rng, depth, smeq, a, b, False)
                any_join = True
        a += 1
    if n > 2:
        for _ in range(rng.rn2(n) + 4, 0, -1):
            a = rng.rn2(n)
            b = rng.rn2(n - 2)
            if b >= a:
                b += 2
            join(map_, rng, depth, smeq, a, b, True)


# ============================================================
# Niches (C: mklev.c place_niche / makeniche / make_niches)
# ============================================================

def cardinal_nextto_room(map_: Map, room: Room, x: int, y: int) -> bool:
    """C: mklev.c#cardinal_nextto_room -- is a cardinal neighbour
    inside `room` (and not a boundary square)?"""
    target = map_.room_of(room)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        pos = (x + dx, y + dy)
        if not map_.in_bounds(pos):
            continue
        tile = map_.tile_at(pos)
        if not tile.edge and tile.roomno == target:
            return True
    return False


def place_niche(map_: Map, room: Room, rng) -> Optional[Tuple[int, int, int]]:
    """C: mklev.c#place_niche -- find a wall square with solid rock
    behind it and room floor in front.

    Returns (dy, x, y) where (x, y) is the door square and (x, y + dy)
    the niche itself, or None.
    """
    if rng.rn2(2):
        dy = 1
        dd = finddpos(map_, room, rng, DIR_S)
    else:
        dy = -1
        dd = finddpos(map_, room, rng, DIR_N)
    if dd is None:
        return None
    xx, yy = dd
    back = (xx, yy + dy)
    front = (xx, yy - dy)
    if not (map_.in_bounds(back) and map_.in_bounds(front)):
        return None
    if map_.tile_at(back).typ != TerrainType.STONE:
        return None
    front_typ = map_.tile_at(front).typ
    if is_furniture(front_typ) or is_pool(front_typ):
        return None
    return (dy, xx, yy) if cardinal_nextto_room(map_, room, xx, yy) else None


def makeniche(world: World, map_: Map, rng, depth: int, lev: int,
              trap_type: Optional[TrapType] = None) -> None:
    """C: mklev.c#makeniche -- an alcove behind a (secret) door in a
    room's wall, sometimes with a trap in it.

    STUBs: the treasure half of the "inaccessible niche" branch (the
    teleportation scroll, the random object, the iron bars with a
    corpse) needs mkobj and is skipped; the trap and the secret door --
    the parts that change how the level plays -- are real.

    `map_` is a parameter (not world.map): a lazily generated level is
    built while the hero still stands on the previous one, and the
    niche must be carved in the level being generated.
    """
    for _ in range(8):
        if not map_.rooms:
            return
        room = map_.rooms[rng.rn2(len(map_.rooms))]
        if room.rtype != RoomType.OROOM:
            continue
        if room.doorct == 1 and rng.rn2(5):
            continue
        placed = place_niche(map_, room, rng)
        if placed is None:
            continue
        dy, xx, yy = placed
        niche = map_.tile_at((xx, yy + dy))
        if trap_type is not None or not rng.rn2(4):
            niche.typ = TerrainType.SCORR
            if trap_type is not None:
                mktrap(world, rng, lev, depth, (xx, yy + dy), trap_type)
            dosdoor(map_, rng, depth, xx, yy, room, TerrainType.SDOOR)
        else:
            niche.typ = TerrainType.CORR
            if rng.rn2(7):
                dosdoor(map_, rng, depth, xx, yy, room,
                        TerrainType.SDOOR if rng.rn2(5)
                        else TerrainType.DOOR)
            else:
                # C: an inaccessible niche with a teleport scroll and
                # a random object (plus sometimes iron bars and a
                # corpse) -- no object creation yet
                pass
        return


def make_niches(world: World, map_: Map, rng, depth: int,
                lev: int) -> None:
    """C: mklev.c#make_niches -- a random handful of niches, with the
    level-teleport and trapdoor specials on the deep levels.

    `map_` is a parameter (not world.map): a lazily generated level is
    built while the hero still stands on the previous one.
    """
    ct = rng.rnd((len(map_.rooms) >> 1) + 1)
    ltptr = depth > 15
    vamp = 5 < depth < 25
    while ct:
        ct -= 1
        if ltptr and not rng.rn2(6):
            ltptr = False
            makeniche(world, map_, rng, depth, lev,
                      TrapType.LEVEL_TELEPORTER)
        elif vamp and not rng.rn2(6):
            vamp = False
            makeniche(world, map_, rng, depth, lev, TrapType.TRAPDOOR)
        else:
            makeniche(world, map_, rng, depth, lev)


def makevtele(world: World, map_: Map, rng, depth: int, lev: int) -> None:
    """C: mklev.c#makevtele -- the vault's teleportation trap (the way
    into an otherwise sealed vault)."""
    makeniche(world, map_, rng, depth, lev, TrapType.TELEPORTATION)


# ============================================================
# Level-wide housekeeping (C: mklev.c)
# ============================================================

def set_levltyp(map_: Map, x: int, y: int, newtyp: TerrainType) -> bool:
    """C: mkmaze.c#set_levltyp -- the sanctioned terrain mutator.

    Every change to a square's terrain type goes through here (the
    swamps, the digging, the doors, the destruction, the furniture all
    use it), so the side effects C bakes in live in exactly one place:

      - a STAIRS / LADDER tile is never overwritten (C:
        CAN_OVERWRITE_TERRAIN); the write is refused and False returned;
      - a LAVA destination is always lit (C: IS_LAVA -> .lit = 1);
      - crossing the FOUNTAIN / SINK boundary recounts the level's
        fountain / sink flags (C: count_level_features()).

    Refusals (out of bounds, a type outside STONE..CLOUD, a stair in the
    way) return False instead of C's impossible(): a generator must
    never abort over a geometry edge case.

    Not ported, each named: the secret-door-in-a-garden-theme-room hack
    (C: oldtyp == SDOOR && newtyp == AIR sets arboreal_sdoor; there are
    no arboreal / themed rooms), and the ice-melt follow-through (C:
    was_ice && newtyp != ICE runs obj_ice_effects() + spot_stop_timers()
    -- pyhack has no item timers, so a melting ice tile just changes
    type).
    """
    if not map_.in_bounds((x, y)):
        return False
    if not TerrainType.STONE <= newtyp <= TerrainType.CLOUD:
        return False  # C: newtyp < STONE || newtyp >= MAX_TYPE
    tile = map_.tiles[y][x]
    oldtyp = tile.typ
    if oldtyp in (TerrainType.STAIRS, TerrainType.LADDER):
        return False  # C: CAN_OVERWRITE_TERRAIN refuses stairs
    tile.typ = newtyp
    if is_lava(newtyp):
        tile.lit = True  # C: IS_LAVA(newtyp) -> levl[x][y].lit = 1
    if (oldtyp == TerrainType.FOUNTAIN) != (newtyp == TerrainType.FOUNTAIN) \
            or (oldtyp == TerrainType.SINK) != (newtyp == TerrainType.SINK):
        count_level_features(map_)
    return True


def count_level_features(map_: Map) -> None:
    """C: mklev.c#count_level_features -- (re)count the fountains and
    sinks, which several systems read from the level flags."""
    map_.flags.nfountains = 0
    map_.flags.nsinks = 0
    for y in range(map_.height):
        for x in range(1, map_.width):
            typ = map_.tiles[y][x].typ
            if typ == TerrainType.FOUNTAIN:
                map_.flags.nfountains += 1
            elif typ == TerrainType.SINK:
                map_.flags.nsinks += 1


def clear_level_structures(world: World, map_: Map, lev: int) -> None:
    """C: mklev.c#clear_level_structures -- wipe the level back to bare
    rock: tiles, room records, doors and the level flags.

    C wipes the level's object and monster state in the same call (the
    per-square svl.level.objects[x][y] / monsters[x][y] arrays, the
    objlist and monlist chains); here those live on the World and are
    filtered by level, so the call also drops level `lev`'s items,
    traps and monsters (a carried item goes with its carrier: it keeps
    its carrier's level).  Regenerating a level therefore starts from
    a clean slate, as C's does, and a seeded generation is repeatable
    over an already-stocked level.
    """
    for y in range(map_.height):
        for x in range(map_.width):
            map_.tiles[y][x] = Tile(typ=TerrainType.STONE)
    map_.rooms = []
    map_.subrooms = []
    map_.doors = []
    map_.flags = LevelFlags()
    for it in list(world.items.values()):
        if it.lev == lev:
            del world.items[it.id]
    for trap in list(world.traps.values()):
        if trap.lev == lev:
            del world.traps[trap.id]
    for mid, mon in list(world.actors.items()):
        if mon.lev == lev and not mon.is_hero:
            del world.actors[mid]


def wallify_map(map_: Map, x1: int, y1: int, x2: int, y2: int) -> None:
    """C: sp_lev.c#wallify_map -- turn the STONE squares that touch a
    room into walls.

    A stone square next to room floor becomes an HWALL when the
    neighbour is above or below it and a VWALL when it is to the side.
    C is careful about the loop bounds (the outer edges are not
    examined); the clamps are kept.
    """
    y1 = max(y1, 0)
    x1 = max(x1, 1)
    y2 = min(y2, map_.height - 1)
    x2 = min(x2, map_.width - 1)
    for y in range(y1, y2 + 1):
        lo_yy = y - 1 if y > 0 else 0
        hi_yy = y + 1 if y < y2 else y2
        for x in range(x1, x2 + 1):
            if map_.tiles[y][x].typ != TerrainType.STONE:
                continue
            lo_xx = x - 1 if x > 1 else 1
            hi_xx = x + 1 if x < x2 else x2
            done = False
            for yy in range(lo_yy, hi_yy + 1):
                for xx in range(lo_xx, hi_xx + 1):
                    typ = map_.tiles[yy][xx].typ
                    if is_room(typ) or typ == TerrainType.CROSSWALL:
                        _set(map_, x, y,
                             TerrainType.HWALL if yy != y
                             else TerrainType.VWALL,
                             horizontal=yy != y)
                        done = True
                        break
                if done:
                    break


def topologize(map_: Map, room: Room) -> None:
    """C: mklev.c#topologize -- stamp the room number onto the room's
    squares and mark its wall ring as `edge`, so room membership can be
    answered from the terrain.

    A boundary square another room already owns becomes SHARED.  An
    irregular room is skipped: its numbering came from the flood fill.
    The C SPECIALIZATION build's `do_ordinary` switch is not ported
    (there is only one build here).
    """
    roomno = map_.room_of(room)
    if map_.tiles[room.ly][room.lx].roomno == roomno or room.irregular:
        return
    for x in range(room.lx, room.hx + 1):
        for y in range(room.ly, room.hy + 1):
            map_.tiles[y][x].roomno = roomno
    for x in range(room.lx - 1, room.hx + 2):
        for y in (room.ly - 1, room.hy + 1):
            if not map_.in_bounds((x, y)):
                continue
            tile = map_.tiles[y][x]
            tile.edge = True
            tile.roomno = SHARED if tile.roomno else roomno
    for x in (room.lx - 1, room.hx + 1):
        for y in range(room.ly, room.hy + 1):
            if not map_.in_bounds((x, y)):
                continue
            tile = map_.tiles[y][x]
            tile.edge = True
            tile.roomno = SHARED if tile.roomno else roomno
    for sidx in room.sbrooms:
        topologize(map_, map_.subrooms[sidx])


def level_finalize_topology(map_: Map) -> None:
    """C: mklev.c#level_finalize_topology -- the per-room topologize()
    pass, then the original room types are remembered (some room types
    are zeroed when the hero enters them, orig_rtype is not).

    The C wall-state update (set_wall_state() -> set_wall()) has no
    port yet: it draws the wall glyphs, and pyhack renders straight
    from the terrain type.
    """
    if not map_.flags.is_maze_lev:
        for room in map_.rooms:
            topologize(map_, room)
    for room in map_.rooms:
        room.orig_rtype = room.rtype


# ============================================================
# Stocking the rooms (C: mklev.c fill_ordinary_room + mktrap)
# ============================================================

# The trap kinds the demo implements (every one of them has an entry in
# core.traps.TRAP_EFFECTS).  C's traptype_rnd() picks from the whole
# trap.h table by depth; see mktrap().
DEMO_TRAP_KINDS: Tuple[TrapType, ...] = (
    TrapType.PIT, TrapType.SPIKED_PIT, TrapType.FIRE_TRAP,
    TrapType.ARROW_TRAP, TrapType.DART_TRAP, TrapType.SLEEPING_GAS,
    TrapType.TELEPORTATION, TrapType.WEB, TrapType.ANTI_MAGIC,
)


def mktrap(world: World, rng, lev: int, depth: int, pos: Pos,
           kind: Optional[TrapType] = None) -> Trap:
    """C: mklev.c#mktrap (the demo subset) -- place a trap.

    STUB: C's traptype_rnd() depth table (which trap types are allowed
    at which depth), the "dead adventurer" the trap already killed
    (mktrap_victim), the rolling-boulder launch search and the
    once/impossible flags.  What is here: the trap record, the demo's
    trap kinds, and the level/depth tagging the trap effects need.
    """
    if kind is None:
        kind = DEMO_TRAP_KINDS[rng.rn2(len(DEMO_TRAP_KINDS))]
    i = len(world.traps)
    while f"trap_{lev}_{i}" in world.traps:
        i += 1
    trap = Trap(id=f"trap_{lev}_{i}", trap_type=kind, pos=pos, lev=lev)
    world.traps[trap.id] = trap
    return trap


def _spawn_monster(world: World, map_: Map, rng, pos: Pos, lev: int,
                   asleep: bool) -> None:
    """C: makemon() -- one monster from the real monster distribution.

    This is the call that replaced the three hand-tuned demo kinds
    (_spawn_monster used to be `rng.rn2(3)` -> goblin / orc / bat): the
    species, its level, its hit points, its gender and its mood all come
    from core.makemon, so a generated level is populated the way NetHack
    populates one (PLAN-MAKEMON.md phase D).

    MM_NOGRP is passed until m_initgrp lands (phase F) and MM_NOMSG is
    implicit -- there is no monster message layer.  The monster sleeps
    because C's fill_ordinary_room asks for a sleeping one (MM_ASLEEP),
    which is what makes a generated level start quiet.
    """
    from .makemon import makemon  # local import: cycle (makemon -> mkobj)
    from .types import MmFlags as _Flags

    flags = _Flags.NOGRP
    if asleep:
        flags |= _Flags.ASLEEP
    # `map_` and not world.map: a lazy level is built while the hero
    # still stands on the previous one (PLAN-MKLEV.md decision 3)
    makemon(world, rng, None, pos, flags, map_=map_, lev=lev,
            in_mklev=True)


def find_okay_roompos(map_: Map, traps: List[Trap], room: Room,
                      rng) -> Optional[Pos]:
    """C: mklev.c#find_okay_roompos -- a free room square that is not by
    a door, up to 200 tries (the furniture placement point).

    somexyspace() already answers "free and standable" (not occupied,
    ROOM/CORR/ICE), so the loop only adds the bydoor() test C keeps
    (furniture does not crowd a doorway).  A full room (somexyspace gives
    up) or 200 door-adjacent answers returns None.
    """
    for _ in range(200):
        pos = somexyspace(map_, traps, room, rng)
        if pos is None:
            return None
        if not bydoor(map_, pos[0], pos[1]):
            return pos
    return None


def mkfount(map_: Map, traps: List[Trap], room: Room, rng) -> None:
    """C: mklev.c#mkfount -- a fountain in a room, blessed 1 in 7.

    The level's fountain flag is kept by set_levltyp's recount, not a
    separate nfountains++ here: C also increments the flag after
    set_levltyp, which double-counts (set_levltyp already recounted the
    new fountain), so pyhack counts once.
    """
    pos = find_okay_roompos(map_, traps, room, rng)
    if pos is None:
        return
    if not set_levltyp(map_, pos[0], pos[1], TerrainType.FOUNTAIN):
        return
    if not rng.rn2(7):
        map_.tile_at(pos).horizontal = True  # C: blessedftn = horizontal


def mksink(map_: Map, traps: List[Trap], room: Room, rng) -> None:
    """C: mklev.c#mksink -- a sink in a room.  (The nsinks flag is the
    set_levltyp recount, see mkfount.)"""
    pos = find_okay_roompos(map_, traps, room, rng)
    if pos is None:
        return
    if not set_levltyp(map_, pos[0], pos[1], TerrainType.SINK):
        return


def mkaltar(map_: Map, traps: List[Trap], room: Room, rng) -> None:
    """C: mklev.c#mkaltar -- an altar in an ordinary room, its alignment
    the C three-way roll (chaotic / neutral / lawful)."""
    if room.rtype != RoomType.OROOM:
        return
    pos = find_okay_roompos(map_, traps, room, rng)
    if pos is None:
        return
    if not set_levltyp(map_, pos[0], pos[1], TerrainType.ALTAR):
        return
    al = rng.rn2(3) - 1  # C: rn2(A_LAWFUL + 2) - 1 -> -1, 0, 1
    map_.tile_at(pos).altarmask = align2amask(al)


def make_grave(world: World, map_: Map, traps: List[Trap], pos: Pos) -> None:
    """C: engrave.c#make_grave -- a grave on a ROOM (or GRAVE) square
    with no trap there.

    STUB: the headstone engraving (C: del_engr_at + make_engr_at HEADSTONE
    and get_rnd_text(EPITAPHFILE)) needs the engraving system, so the
    epitaph roll is not taken.
    """
    tile = map_.tile_at(pos)
    if tile.typ not in (TerrainType.ROOM, TerrainType.GRAVE):
        return  # C: "Can we put a grave here?"
    if any(t.pos == pos and not t.disarmed for t in traps):
        return  # C: t_at(x, y) -- a trap blocks the grave
    set_levltyp(map_, pos[0], pos[1], TerrainType.GRAVE)


def mkgrave(world: World, map_: Map, traps: List[Trap], room: Room,
            lev: int, rng) -> None:
    """C: mklev.c#mkgrave -- a grave in an ordinary room, sometimes with
    a bell and a buried load of cursed loot.

    C buries the objects (add_to_buried) until the grave is kicked open
    (dig.c).  pyhack has no grave-digging, so the objects are placed on
    the GRAVE square as ordinary floor items instead -- the only way they
    can ever be reached.  The draw sequence (the dobell roll, the gold
    amount, the rn2(5) loot loop) is C's.
    """
    from . import rules
    from .mkobj import (RANDOM_CLASS, curse, mksobj, mksobj_at, mkobj,
                        place_object, weight)
    from .objects import ObjType

    dobell = not rng.rn2(10)  # C: rolled before the rtype test
    if room.rtype != RoomType.OROOM:
        return
    pos = find_okay_roompos(map_, traps, room, rng)
    if pos is None:
        return
    make_grave(world, map_, traps, pos)
    if not rng.rn2(3):
        gold = mksobj(world, rng, int(ObjType.GOLD_PIECE))
        gold.quan = rng.rnd(20) + rules.level_difficulty(world) * rng.rnd(5)
        gold.owt = weight(world, gold)
        place_object(world, gold, pos, lev)
    for _ in range(rng.rn2(5)):
        item = mkobj(world, rng, RANDOM_CLASS, True)
        curse(item)
        place_object(world, item, pos, lev)
    if dobell:
        mksobj_at(world, rng, int(ObjType.BELL), pos, lev)


def fill_ordinary_room(world: World, map_: Map, rng, room: Room, lev: int,
                       depth: int) -> None:
    """C: mklev.c#fill_ordinary_room -- put things inside a normal room.

    Included: the sleeping monster (C: 2/3 of rooms), the trap loop
    (C: `while (!rn2(8 - depth/6))`), and the object half in C's order
    (gold pile, fountain, sink, altar, grave, statue, the final random
    object -- see _fill_room_objects; the object genesis and the
    terrain writers are in, PLAN-MKOBJ.md G).

    STUB (each in C order, each naming its C call): the bonus item and
    the box / chest (!rn2(nroom*5/2)), and the random engraving
    (make_engr_at).  Their rolls are not taken, so landing them shifts
    a level's draw sequence -- a deliberate change, with the seeded
    snapshot test as the tripwire.

    `map_` is a parameter (not `world.map`) because a lazily generated
    level is built while the hero still stands on the previous one.
    """
    if room.rtype not in (RoomType.OROOM, RoomType.THEMEROOM):
        return
    for sidx in room.sbrooms:
        fill_ordinary_room(world, map_, rng, map_.subrooms[sidx], lev, depth)

    traps = [t for t in world.traps.values() if t.lev == lev]
    if not rng.rn2(3):
        pos = somexyspace(map_, traps, room, rng)
        if pos is not None:
            _spawn_monster(world, map_, rng, pos, lev, asleep=True)
    # C: put traps and mimics inside
    x = 8 - depth // 6
    if x <= 1:
        x = 2
    trycnt = 0
    while not rng.rn2(x) and trycnt < 1000:
        trycnt += 1
        pos = somexyspace(map_, traps, room, rng)
        if pos is not None and not occupied(map_, traps, pos):
            mktrap(world, rng, lev, depth, pos)
            traps = [t for t in world.traps.values() if t.lev == lev]
    _fill_room_objects(world, map_, rng, room, lev, depth, traps)


def _fill_room_objects(world: World, map_: Map, rng, room: Room, lev: int,
                       depth: int, traps: List[Trap]) -> None:
    """C: the object half of fill_ordinary_room, in C's order.

    Included (the object genesis and the terrain writers are in --
    PLAN-MKOBJ.md phase G): the gold pile (!rn2(3)), the fountain
    (!rn2(10)), the sink (!rn2(60)), the altar (!rn2(60)) and the grave
    (!rn2(80 - 2*depth), the C mkfount / mksink / mkaltar / mkgrave),
    the statue (!rn2(20)) and the final random object (!rn2(3), C's
    `mkobj_at(RANDOM_CLASS, ...)`).

    STUB, still in C order and each naming its C call: the bonus item,
    the box / chest (!rn2(nroom*5/2)) and the graffiti (make_engr_at).
    The rolls that belong to those STUBs are not taken, so landing them
    will shift a level's draw sequence -- exactly the kind of change
    PLAN-MKLEV.md §2.7 asks a port to make deliberately, with the
    seeded snapshot test as the tripwire.
    """
    from .mkobj import (RANDOM_CLASS, mkgold, mkobj_at, mkcorpstat)
    from .objects import ObjType

    if not rng.rn2(3):                      # C: gold
        pos = somexyspace(map_, traps, room, rng)
        if pos is not None:
            mkgold(world, rng, 0, pos, lev)

    if not rng.rn2(10):                     # C: a fountain
        mkfount(map_, traps, room, rng)
    if not rng.rn2(60):                     # C: a sink
        mksink(map_, traps, room, rng)
    if not rng.rn2(60):                     # C: an altar
        mkaltar(map_, traps, room, rng)
    x = 80 - depth * 2                      # C: a grave, rarer the deeper
    if x < 2:
        x = 2
    if not rng.rn2(x):
        mkgrave(world, map_, traps, room, lev, rng)

    if not rng.rn2(20):                     # C: a statue
        pos = somexyspace(map_, traps, room, rng)
        if pos is not None:
            mkcorpstat(world, rng, int(ObjType.STATUE), pos=pos, lev=lev)

    if not rng.rn2(3):                      # C: the final object
        pos = somexyspace(map_, traps, room, rng)
        if pos is not None:
            mkobj_at(world, rng, RANDOM_CLASS, pos, lev)


# ============================================================
# Stairs (C: mklev.c mkstairs / generate_stairs)
# ============================================================

def mkstairs(map_: Map, stairs: List[Stairway], x: int, y: int,
             up: bool, force: bool = False) -> Optional[Stairway]:
    """C: mklev.c#mkstairs -- a staircase at x,y.

    The stairway record is appended to the *generation* list (C:
    stairway_add() into gs.stairs); core.stairs.rebuild_stairs() later
    rebuilds the world's list from the map, which is what makes a
    lazily generated level's stairs appear when the hero arrives.
    """
    if not x or not map_.in_bounds((x, y)):
        return None  # C: impossible("bogus stair attempt")
    tile = map_.tiles[y][x]
    if force:
        tile.typ = TerrainType.ROOM
    if tile.typ not in (TerrainType.ROOM, TerrainType.CORR,
                        TerrainType.ICE):
        return None  # C: impossible("placing stairs on ...")
    stair = Stairway(pos=(x, y), up=up)
    stairs.append(stair)
    tile.typ = TerrainType.STAIRS
    tile.stair_dir = STAIR_UP if up else STAIR_DOWN
    return stair


def _stairs_room_good(map_: Map, stairs: List[Stairway], room: Room,
                      phase: int) -> bool:
    """C: mklev.c#generate_stairs_room_good.

    Lower phases relax the criteria: 2 = no relaxing, 1 = a themed room
    will do, 0 = the room may already hold a staircase, -1 = an
    unjoined room will do.
    """
    return (room.needjoining or phase < 0) \
        and ((not has_dnstairs(map_, stairs, room)
              and not has_upstairs(map_, stairs, room)) or phase < 1) \
        and (room.rtype == RoomType.OROOM
             or (phase < 2 and room.rtype == RoomType.THEMEROOM))


def _stairs_find_room(map_: Map, stairs: List[Stairway], rng) -> Optional[Room]:
    """C: mklev.c#generate_stairs_find_room -- the best room for a
    staircase, relaxing the criteria in four phases."""
    if not map_.rooms:
        return None
    for phase in (2, 1, 0, -1):
        picks = [i for i, room in enumerate(map_.rooms)
                 if _stairs_room_good(map_, stairs, room, phase)]
        if picks:
            return map_.rooms[picks[rng.rn2(len(picks))]]
    return map_.rooms[rng.rn2(len(map_.rooms))]


def generate_stairs(map_: Map, stairs: List[Stairway], rng, lev: int,
                    max_lev: int) -> None:
    """C: mklev.c#generate_stairs -- up and down, in different rooms
    when the level allows it.

    C order: the DOWN staircase first (unless this is the bottom
    level), then the UP one (unless this is level 1) -- so level 1 has
    only a down staircase and the bottom level only an up one.
    """
    traps: List[Trap] = []
    if lev < max_lev:
        room = _stairs_find_room(map_, stairs, rng)
        if room is not None:
            pos = somexyspace(map_, traps, room, rng)
            if pos is None:
                pos = (rng.rn1(room.hx - room.lx + 1, room.lx),
                       rng.rn1(room.hy - room.ly + 1, room.ly))
            mkstairs(map_, stairs, pos[0], pos[1], False)
    if lev != 1:
        room = _stairs_find_room(map_, stairs, rng)
        if room is not None:
            pos = somexyspace(map_, traps, room, rng)
            if pos is None:
                pos = (rng.rn1(room.hx - room.lx + 1, room.lx),
                       rng.rn1(room.hy - room.ly + 1, room.ly))
            mkstairs(map_, stairs, pos[0], pos[1], True)


# ============================================================
# makelevel -- the whole rooms+corridors flow
# ============================================================

def _roll_special_room(map_: Map, rng, depth: int,
                       stairs: List[Stairway]) -> None:
    """C: the special-room roll of makelevel() -- at most one special
    room per level, its type chosen by depth.

    The odds chain is C's verbatim.  Every handler is a core.mkroom
    STUB except mkzoo (which only sets the room type), so asking for
    specials on a level that rolls a shop / temple / swamp raises
    NotImplementedError -- that is why the demo generator passes
    specials=False.
    """
    nrooms = len(map_.rooms)
    threshold = 3
    if depth > 1 and nrooms >= threshold and rng.rn2(depth) < 3:
        do_mkroom(map_, stairs, [], rng, RoomType.SHOPBASE)
    elif depth > 4 and not rng.rn2(6):
        do_mkroom(map_, stairs, [], rng, RoomType.COURT)
    elif depth > 5 and not rng.rn2(8):
        do_mkroom(map_, stairs, [], rng, RoomType.LEPREHALL)
    elif depth > 6 and not rng.rn2(7):
        do_mkroom(map_, stairs, [], rng, RoomType.ZOO)
    elif depth > 8 and not rng.rn2(5):
        do_mkroom(map_, stairs, [], rng, RoomType.TEMPLE)
    elif depth > 9 and not rng.rn2(5):
        do_mkroom(map_, stairs, [], rng, RoomType.BEEHIVE)
    elif depth > 11 and not rng.rn2(6):
        do_mkroom(map_, stairs, [], rng, RoomType.MORGUE)
    elif depth > 12 and not rng.rn2(8):
        do_mkroom(map_, stairs, [], rng, RoomType.ANTHOLE)
    elif depth > 14 and not rng.rn2(4):
        do_mkroom(map_, stairs, [], rng, RoomType.BARRACKS)
    elif depth > 15 and not rng.rn2(6):
        do_mkroom(map_, stairs, [], rng, RoomType.SWAMP)
    elif depth > 16 and not rng.rn2(8):
        do_mkroom(map_, stairs, [], rng, RoomType.COCKNEST)


def makelevel(world: World, map_: Map, rng, lev: int,
              specials: bool = False) -> Map:
    """C: mklev.c#makelevel + mklev() -- generate one rooms+corridors
    level into `map_` (which arrives all STONE).

    The order is C's and is the interesting part of this function:

      1. makerooms()      -- rooms out of the free rectangles
      2. sort_rooms()     -- left to right, so neighbours get corridors
      3. generate_stairs()-- INSIDE rooms, before the corridors exist
      4. makecorridors()  -- the doors and the corridors between them
      5. make_niches()    -- the alcoves in the outer walls
      6. [special room]   -- at most one, by depth (STUBs, see above)
      7. fill_ordinary_room() for every room -- monsters and traps
      8. level_finalize_topology() -- stamp the room numbers

    Steps 7 and 8 are in that order only because C splits them between
    makelevel() and mklev(); filling does not need the room numbers.
    """
    clear_level_structures(world, map_, lev)
    depth = lev
    rects = RectManager(map_)
    smeq: List[int] = []
    stairs: List[Stairway] = []
    makerooms(map_, rects, rng, depth, smeq)
    if not map_.rooms:
        # C panics; a level with no rooms cannot be walked on
        raise RuntimeError("makelevel: no rooms were created")
    sort_rooms(map_)
    generate_stairs(map_, stairs, rng, lev, world.max_lev)
    makecorridors(map_, rng, depth, smeq)
    make_niches(world, map_, rng, depth, lev)
    if specials:
        _roll_special_room(map_, rng, depth, stairs)
    for room in list(map_.rooms):
        fill_ordinary_room(world, map_, rng, room, lev, depth)
    level_finalize_topology(map_)
    count_level_features(map_)
    return map_


def mklev(world: World, map_: Map, rng, lev: int,
          specials: bool = False) -> Map:
    """C: mklev.c#mklev -- the "make a level" entry point (the name the
    C callers use).  Kept as an alias of makelevel so the ported call
    graph reads the same."""
    return makelevel(world, map_, rng, lev, specials)


__all__ = [
    "DOORINC", "Rect", "RectManager", "SPLEV_CENTER", "SPLEV_LEFT",
    "SPLEV_RIGHT", "TOP", "BOTTOM", "XLIM", "YLIM",
    "add_door", "add_room", "add_subroom", "blank_map", "bydoor",
    "cardinal_nextto_room", "check_room", "clear_level_structures",
    "count_level_features", "create_room", "create_subroom", "dig_corridor",
    "do_room_or_subroom", "dodoor", "dosdoor", "fill_ordinary_room",
    "find_okay_roompos", "finddpos", "finddpos_shift",
    "generate_stairs", "good_rm_wall_doorpos",
    "join", "make_grave", "make_niches", "makecorridors", "makelevel",
    "makeniche", "makerooms", "makevtele", "maybe_sdoor", "mkaltar",
    "mkfount", "mkgrave", "mklev", "mksink", "mkstairs", "mktrap",
    "okdoor", "place_niche", "set_levltyp", "sort_rooms", "topologize",
    "wallify_map",
]
