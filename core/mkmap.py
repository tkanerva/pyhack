"""The cavern level generator (C: src/mkmap.c, plus the shared
sp_lev.c / rect helper it leans on).

`mkmap()` is NetHack's second level generator: a cellular-automaton
blob of floor carved out of solid rock, optionally smoothed, optionally
cut into separate irregular rooms that are then joined by corridors
(Nethack's "cavernous" levels -- the Mines, the big room, ...).  It is
a small, self-contained algorithm (488 C lines) and the cheapest way to
get a *second* map shape into the demo after core.mklev's rooms.

C provenance:

  src/mkmap.c    init_map(), init_fill(), get_map(), pass_one(),
                 pass_two(), pass_three(), flood_fill_rm(),
                 join_map_cleanup(), join_map(), finish_map(),
                 remove_rooms(), remove_room(), litstate_rnd(),
                 mkmap()
  src/sp_lev.c   wallify_map() (ported in core.mklev -- the `walled`
                 flag of mkmap is its main caller)

Included: everything except the room removal pair (see STUBs).

STUBs:

  - remove_rooms() / remove_room(): they exist so a special level's MAP
    can be overlaid on a generated cavern and the affected rooms
    dropped; with no special levels there is nothing to remove.  The
    port is mechanical (swap-with-last in Map.rooms plus a roomno
    rewrite) and belongs with the sp_lev work.

Simplifications (documented, not bugs):

  - the C grid is 80x21 with column 0 unused; pyhack maps are fully
    real, so the generator keeps the C *inset* (column 0 stays rock,
    the last row/column stay rock) but works on the actual map size.
    For the demo's 40x20 level that is WIDTH = 38, HEIGHT = 19, exactly
    the C expressions COLNO-2 / ROWNO-1 evaluated on the demo size.
  - `gn.new_locations` is a flat scratch buffer in C; here each pass
    builds a fresh list-of-lists (same result, no global).
  - flood_fill_rm() recurses in C; here it runs on an explicit stack.
    The fill, the roomno/edge marking and the tracked extents are the
    same -- only the recursion is gone (no Python recursion limit).
  - join_map_cleanup() is a deliberate no-op: C throws the temporary
    rooms it just used to dig the corridors away, which leaves a
    cavern with no room records; pyhack keeps them (they are what
    somexyspace / room_at / the special rooms read).
  - join_map() retries a failed corridor with a plain L.  C leaves the
    cavern split when dig_corridor() gives up, and a demo level must
    stay walkable.
  - `icedpools` is carried but ICE is never generated yet (no water
    work), so the icedpool half of finish_map() has nothing to mark.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .types import (MAXNROFROOMS, NO_ROOM, ROOMOFFSET, SHARED, Map, Pos,
                    RoomType, TerrainType, is_door, is_obstructed, is_room,
                    is_wall)


# The cellular-automaton tuning constants, verbatim from mkmap.c.
N_P1_ITER = 1   # tune map generation via this value
N_P2_ITER = 1   # tune map generation via this value
N_P3_ITER = 2   # tune map smoothing via this value

# The eight neighbour offsets, as the C dirs[16] table pairs them.
_DIRS = ((-1, -1), (-1, 0), (-1, 1), (0, -1),
         (0, 1), (1, -1), (1, 0), (1, 1))


class FillResult:
    """The extents flood_fill_rm() reports (C: the gm.min_rx / max_rx /
    min_ry / max_ry / gn.n_loc_filled globals)."""

    __slots__ = ("min_rx", "max_rx", "min_ry", "max_ry", "count")

    def __init__(self, x: int, y: int) -> None:
        self.min_rx = x
        self.max_rx = x
        self.min_ry = y
        self.max_ry = y
        self.count = 0

    @property
    def width(self) -> int:
        return self.max_rx - self.min_rx + 1

    @property
    def height(self) -> int:
        return self.max_ry - self.min_ry + 1


def _geo(map_: Map) -> Tuple[int, int]:
    """C: the WIDTH / HEIGHT macros -- COLNO-2 and ROWNO-1."""
    return map_.width - 2, map_.height - 1


def litstate_rnd(rng, litstate: int, depth: int) -> bool:
    """C: mkmap.c#litstate_rnd -- resolve the `lit` argument of a level
    definition: < 0 means "random, rarely at depth".

    C: `rnd(1 + abs(depth)) < 11 && rn2(77)`, i.e. roughly 14% of
    shallow levels are lit, fewer deeper down, and one roll in 77 on
    top of that.  NOTE the short-circuit: when the first test fails
    the second draw never happens, so the rng stream differs between
    the two cases -- keep the `and` order.
    """
    if litstate < 0:
        return rng.rnd(1 + abs(depth)) < 11 and bool(rng.rn2(77))
    return bool(litstate)


# ============================================================
# The passes
# ============================================================

def init_map(map_: Map, bg_typ: TerrainType) -> None:
    """C: mkmap.c#init_map -- every square becomes the background
    terrain, unlit and owned by no room."""
    for x in range(1, map_.width):
        for y in range(map_.height):
            tile = map_.tiles[y][x]
            tile.roomno = NO_ROOM
            tile.typ = bg_typ
            tile.lit = False
            tile.edge = False


def init_fill(map_: Map, rng, bg_typ: TerrainType,
              fg_typ: TerrainType) -> None:
    """C: mkmap.c#init_fill -- scatter the foreground terrain until
    about 40% of the level is foreground."""
    width, height = _geo(map_)
    limit = (width * height * 2) // 5
    count = 0
    while count < limit:
        x = rng.rn1(width - 1, 2)
        y = rng.rnd(height - 1)
        if map_.tiles[y][x].typ == bg_typ:
            map_.tiles[y][x].typ = fg_typ
            count += 1


def get_map(map_: Map, col: int, row: int,
            bg_typ: TerrainType) -> TerrainType:
    """C: mkmap.c#get_map -- the terrain, with everything off the level
    reading as the background."""
    width, height = _geo(map_)
    if col <= 0 or row < 0 or col > width or row >= height:
        return bg_typ
    return map_.tiles[row][col].typ


def _count_neighbours(map_: Map, x: int, y: int, bg_typ: TerrainType,
                      fg_typ: TerrainType) -> int:
    """The 8-neighbour foreground count both pass_one and the later
    passes take (C computes it inline, the same eight dirs entries)."""
    count = 0
    for dx, dy in _DIRS:
        if get_map(map_, x + dx, y + dy, bg_typ) == fg_typ:
            count += 1
    return count


def pass_one(map_: Map, bg_typ: TerrainType, fg_typ: TerrainType) -> None:
    """C: mkmap.c#pass_one -- death (0..2 neighbours) or birth (5..8).

    Written in place, in scan order: a square's neighbours include the
    ones already changed by this pass (C does the same, which is why
    the pass is not symmetric).
    """
    width, height = _geo(map_)
    for x in range(2, width + 1):
        for y in range(1, height):
            count = _count_neighbours(map_, x, y, bg_typ, fg_typ)
            if count <= 2:
                map_.tiles[y][x].typ = bg_typ
            elif count >= 5:
                map_.tiles[y][x].typ = fg_typ


def _pass_from_scratch(map_: Map, bg_typ: TerrainType, fg_typ: TerrainType,
                       drop_below: Optional[int]) -> None:
    """pass_two / pass_three share everything but the rule: they write
    into a scratch buffer and copy back, so the whole level is judged
    against the *previous* pass (C: gn.new_locations).

    `drop_below` is the C rule: pass_two drops squares with exactly 5
    foreground neighbours, pass_three drops everything below 3.
    """
    width, height = _geo(map_)
    new = [[map_.tiles[y][x].typ for x in range(map_.width)]
           for y in range(map_.height)]
    for x in range(2, width + 1):
        for y in range(1, height):
            count = _count_neighbours(map_, x, y, bg_typ, fg_typ)
            if drop_below is not None and count < drop_below:
                new[y][x] = bg_typ
            elif drop_below is None and count == 5:
                new[y][x] = bg_typ
            else:
                new[y][x] = get_map(map_, x, y, bg_typ)
    for x in range(2, width + 1):
        for y in range(1, height):
            map_.tiles[y][x].typ = new[y][x]


def pass_two(map_: Map, bg_typ: TerrainType, fg_typ: TerrainType) -> None:
    """C: mkmap.c#pass_two -- exactly 5 foreground neighbours becomes
    background (smoothing), read from the pre-pass state."""
    _pass_from_scratch(map_, bg_typ, fg_typ, None)


def pass_three(map_: Map, bg_typ: TerrainType, fg_typ: TerrainType) -> None:
    """C: mkmap.c#pass_three -- fewer than 3 foreground neighbours
    becomes background (the extra smoothing of `smoothed` levels)."""
    _pass_from_scratch(map_, bg_typ, fg_typ, 3)


# ============================================================
# Flood fill (shared with the room-based generator)
# ============================================================

def flood_fill_rm(map_: Map, sx: int, sy: int, rmno: int, lit: bool,
                  anyroom: bool) -> FillResult:
    """C: mkmap.c#flood_fill_rm -- flood the connected region of
    foreground terrain around (sx, sy), stamping it with `rmno` and
    `lit`, and report its extents.

    Two different notions of "in the room" are at work, exactly as in
    C: the *filled run* is the maximal stretch of the same terrain as
    the start square (fg_typ, captured on entry), while the *backup
    step* -- and the `anyroom` wall marking -- use IS_ROOM when
    `anyroom` is set, so a room's furniture and its own wall ring join
    the room.  Walls / doors around each filled run are marked as the
    room's edge (Tile.edge), and a wall two rooms both touch becomes
    SHARED -- that is what "shared boundary" means.

    C recurses; the stack here is explicit.  The fill, the marking and
    the reported extents are the same; only the visit order differs,
    and nothing the callers read depends on it.
    """
    width, _ = _geo(map_)
    fg_typ = map_.tiles[sy][sx].typ
    result = FillResult(sx, sy)

    def region_ok(x: int, y: int) -> bool:
        typ = map_.tiles[y][x].typ
        return is_room(typ) if anyroom else typ == fg_typ

    def mark_walls(x0: int, x1: int, y: int) -> None:
        """C: the `if (anyroom)` block of the fill loop."""
        for i in range(x0, x1 + 1):
            first = i - 1 if i == x0 else i
            for ii in range(first, i + 2):
                for jj in range(y - 1, y + 2):
                    if not (0 <= ii < map_.width
                            and 0 <= jj < map_.height):
                        continue
                    tile = map_.tiles[jj][ii]
                    if not (is_wall(tile.typ) or is_door(tile.typ)
                            or tile.typ == TerrainType.SDOOR):
                        continue
                    tile.edge = True
                    if lit:
                        tile.lit = True
                    if tile.roomno == NO_ROOM:
                        tile.roomno = rmno
                    elif tile.roomno != rmno:
                        tile.roomno = SHARED

    stack: List[Tuple[int, int]] = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        if map_.tiles[y][x].roomno == rmno:
            continue  # C never recurses into a filled square
        # C backs up to the leftmost square of the run it landed in
        while x > 0 and region_ok(x, y) and map_.tiles[y][x].roomno != rmno:
            x -= 1
        x += 1
        # fill the maximal run of the entry terrain
        i = x
        while i <= width and map_.tiles[y][i].typ == fg_typ:
            tile = map_.tiles[y][i]
            tile.roomno = rmno
            tile.lit = lit
            result.count += 1
            i += 1
        nx = i
        if anyroom:
            mark_walls(x, nx - 1, y)
        result.min_rx = min(result.min_rx, x)
        result.min_ry = min(result.min_ry, y)
        result.max_rx = max(result.max_rx, nx - 1)
        result.max_ry = max(result.max_ry, y)
        # the rows above and below, exactly as C walks them: straight
        # down/up, plus the two diagonals at a run boundary
        for yy in (y - 1, y + 1):
            if not 0 <= yy < map_.height:
                continue
            for i in range(x, nx):
                row = map_.tiles[yy]
                if row[i].typ == fg_typ:
                    if row[i].roomno != rmno:
                        stack.append((i, yy))
                    continue
                if (i > x or 0 < i - 1 < map_.width) \
                        and row[i - 1].typ == fg_typ \
                        and row[i - 1].roomno != rmno:
                    stack.append((i - 1, yy))
                if (i < nx - 1 or 0 < i + 1 < map_.width) \
                        and row[i + 1].typ == fg_typ \
                        and row[i + 1].roomno != rmno:
                    stack.append((i + 1, yy))
    return result


# ============================================================
# Joining the blobs into rooms
# ============================================================

def join_map_cleanup(map_: Map) -> None:
    """C: mkmap.c#join_map_cleanup -- the end of join_map().

    C uses its rooms as *temporary* scaffolding and then throws them
    away (`svn.nroom = gn.nsubroom = 0` plus a roomno wipe), which
    leaves a cavern level with no room records at all.  pyhack keeps
    them: the room records are what somexyspace(), Map.room_at() and
    the special-room work read, and the numbers the flood fill stamped
    are exactly the indices the rooms ended up with -- so there is
    nothing to recompute and this function deliberately only exists to
    keep the C call graph readable.
    """
    # (no-op on purpose -- see the docstring)
    del map_


def _dig_direct(map_: Map, org: Pos, dest: Pos, ftyp: TerrainType,
                btyp: TerrainType) -> None:
    """Fallback corridor: a plain L from org to dest.

    C has no such fallback: dig_corridor() can run out of steps and
    give up, which leaves a cavern region cut off from the rest of the
    level.  A demo level must stay walkable -- the stairs and the hero
    are placed on floor_tiles() -- so a failed join is retried with
    this deterministic L, which always gets through (it only ever digs
    background, never breaks a wall).
    """
    x, y = org
    tx, ty = dest
    step = 1 if tx >= x else -1
    for xx in range(x, tx + step, step):
        pos = (xx, y)
        if map_.in_bounds(pos) and map_.tile_at(pos).typ == btyp:
            map_.tile_at(pos).typ = ftyp
    step = 1 if ty >= y else -1
    for yy in range(y, ty + step, step):
        pos = (tx, yy)
        if map_.in_bounds(pos) and map_.tile_at(pos).typ == btyp:
            map_.tile_at(pos).typ = ftyp


def join_map(map_: Map, rng, depth: int, bg_typ: TerrainType,
             fg_typ: TerrainType) -> None:
    """C: mkmap.c#join_map -- cut the cavern into irregular rooms and
    connect them with corridors.

    Every region bigger than 3 squares becomes a room (irregular: its
    shape is the blob, not a rectangle); tiny holes are filled back in
    so the hero can never be stranded in one.  The rooms are then
    joined in creation order by dig_corridor(), which is the C
    behaviour (no sort_rooms(): the flood fill already numbers them in
    scan order, and sorting would invalidate the roomno values).
    """
    # local import: core.mklev is the room/wall/corridor primitive
    # layer and it imports this module (litstate_rnd) at module level.
    from .mklev import add_room, dig_corridor
    from .mkroom import somexy

    width, height = _geo(map_)
    for x in range(2, width + 1):
        for y in range(1, height):
            tile = map_.tiles[y][x]
            if tile.typ != fg_typ or tile.roomno != NO_ROOM:
                continue
            if len(map_.rooms) >= MAXNROFROOMS * 2:
                return
            rmno = len(map_.rooms) + ROOMOFFSET
            filled = flood_fill_rm(map_, x, y, rmno, False, False)
            if filled.count > 3:
                room = add_room(map_, filled.min_rx, filled.min_ry,
                                filled.max_rx, filled.max_ry, False,
                                RoomType.OROOM, True)
                room.irregular = True
            else:
                # a tiny hole: erase it so nobody ends up there
                for sx in range(filled.min_rx, filled.max_rx + 1):
                    for sy in range(filled.min_ry, filled.max_ry + 1):
                        tile = map_.tiles[sy][sx]
                        if tile.roomno == rmno:
                            tile.typ = bg_typ
                            tile.roomno = NO_ROOM

    # join the rooms: `i` is the room the corridor starts in, `j` the
    # one it aims at.  C advances `j` every iteration but `i` only when
    # the two rooms do not overlap, so a room that overlaps its
    # neighbour is reached from the one before it instead.
    i, j = 0, 1
    while j < len(map_.rooms):
        croom = map_.rooms[i]
        croom2 = map_.rooms[j]
        sm = somexy(map_, croom, rng)
        em = somexy(map_, croom2, rng)
        if sm is None or em is None:
            # C's impossible() fallback: the room centers
            sm = (croom.lx + (croom.hx - croom.lx) // 2,
                  croom.ly + (croom.hy - croom.ly) // 2)
            em = (croom2.lx + (croom2.hx - croom2.lx) // 2,
                  croom2.ly + (croom2.hy - croom2.ly) // 2)
        dug, _ = dig_corridor(map_, rng, depth, sm, em, False, fg_typ, bg_typ)
        if not dug:
            # C leaves the cavern split here; keep the level walkable
            _dig_direct(map_, sm, em, fg_typ, bg_typ)
        # choose the next region to join: only move on when the two do
        # not overlap horizontally or vertically
        if croom2.lx > croom.hx or (
                (croom2.ly > croom.hy or croom2.hy < croom.ly)
                and rng.rn2(3)):
            i = j
        j += 1
    join_map_cleanup(map_)


# ============================================================
# Finishing touches
# ============================================================

def finish_map(map_: Map, rng, fg_typ: TerrainType, bg_typ: TerrainType,
               lit: bool, walled: bool, icedpools: bool) -> None:
    """C: mkmap.c#finish_map -- wall the blobs in and light the level.

    Lava is always lit; ice records whether it is a frozen pool or a
    frozen moat (STUB: no ice is generated yet, so that half has
    nothing to do).
    """
    # local import, same cycle as join_map()
    from .mklev import wallify_map

    if walled:
        wallify_map(map_, 1, 0, map_.width - 1, map_.height - 1)
    if lit:
        for x in range(1, map_.width):
            for y in range(map_.height):
                typ = map_.tiles[y][x].typ
                if (not is_obstructed(fg_typ) and typ == fg_typ) \
                        or (not is_obstructed(bg_typ) and typ == bg_typ) \
                        or (bg_typ == TerrainType.TREE
                            and typ == bg_typ) \
                        or (walled and is_wall(typ)):
                    map_.tiles[y][x].lit = True
        for room in map_.rooms:
            room.rlit = True
    for x in range(1, map_.width):
        for y in range(map_.height):
            if map_.tiles[y][x].typ == TerrainType.LAVAPOOL:
                map_.tiles[y][x].lit = True


def remove_rooms(map_: Map, lx: int, ly: int, hx: int, hy: int) -> None:
    """C: mkmap.c#remove_rooms -- drop the rooms a special-level MAP was
    laid over.

    STUB: only special levels overlay a generated map, and none exist
    yet.  C walks the rooms backwards so remove_room()'s swap-with-last
    cannot skip an entry; the port needs that same order plus the
    roomno rewrite of the moved room.
    """
    raise NotImplementedError(
        "special-level maps need room removal (C: src/mkmap.c "
        "remove_rooms())")


def mkmap(map_: Map, rng, depth: int = 1, bg_typ: TerrainType = TerrainType.STONE,
          fg_typ: TerrainType = TerrainType.ROOM, smoothed: bool = True,
          joined: bool = True, lit: int = -1, walled: bool = True,
          icedpools: bool = False) -> None:
    """C: mkmap.c#mkmap -- build a cavern on `map_` in place.

    The C `lev_init` structure collapses into keyword arguments; the
    defaults are the classic cavern look (smoothed, joined, walled, lit
    resolved by depth).
    """
    is_lit = litstate_rnd(rng, lit, depth)
    init_map(map_, bg_typ)
    init_fill(map_, rng, bg_typ, fg_typ)
    for _ in range(N_P1_ITER):
        pass_one(map_, bg_typ, fg_typ)
    for _ in range(N_P2_ITER):
        pass_two(map_, bg_typ, fg_typ)
    if smoothed:
        for _ in range(N_P3_ITER):
            pass_three(map_, bg_typ, fg_typ)
    if joined:
        join_map(map_, rng, depth, bg_typ, fg_typ)
    finish_map(map_, rng, fg_typ, bg_typ, is_lit, walled, icedpools)
    # a walled, joined level is cavernous, not mazelike
    if walled and joined:
        map_.flags.is_maze_lev = False
        map_.flags.is_cavernous_lev = True


__all__ = [
    "FillResult", "finish_map", "flood_fill_rm", "get_map", "init_fill",
    "init_map", "join_map", "join_map_cleanup", "litstate_rnd", "mkmap",
    "pass_one", "pass_three", "pass_two", "remove_rooms",
]
