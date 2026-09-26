"""Line of sight: the port of src/vision.c (Dean Luick's "Algorithm C").

This module is what lets monsters see the hero: m_can_see_u() answers
"can this monster see the hero right now?", clear_path() is the raw
line-of-sight query (C: m_cansee()), and vision_recalc() computes the
hero's current view (the could_see array behind can_see()/could_see()).

Ported faithfully:
  does_block()            terrain/boulder sight blocking
  vision_reset()          the per-row viz_clear + left/right pointer
                          build (C's row scan, verbatim)
  view_from()             Algorithm C: right_side()/left_side() plus the
                          four Bresenham quadrant paths -- the
                          MACRO_CPATH variant the default build
                          compiles (the non-macro function variants in
                          vision.c carry swapped parameter names; the
                          bodies are the same algorithm)
  clear_path()            the line-of-sight query monsters use
  vision_recalc()         the hero's current could-see view (the
                          control = 0 path; C's "adjacent recalculation"
                          is unimplemented in C as well)
  can_see()/could_see()   hero tile queries (C: vision.h macros)
  m_can_see()/m_can_see_u()  monster queries (C: vision.h macros)
  do_clear_area()         the area-of-effect engine (spells / wands)
  block_point()/
  unblock_point()         the terrain-change hooks
  CIRCLE_DATA / CIRCLE_START (the range circles)

Stubbed (STUB comments; to be filled in later):
  - light sources and room lighting (light.c): until then every tile
    the hero *could* see is treated as lit, so IN_SIGHT == COULD_SEE;
  - xray / night vision / rogue level / underwater / pit vision;
  - seenv "seen angle" bookkeeping (display.c) -- Tile has no seenv
    yet, and there is no display to update;
  - the O(1) pointer updates of dig_point()/fill_point():
    block_point()/unblock_point() rescan the whole row instead (same
    result, O(width) per change);
  - does_block(): mimics disguised as doors/boulders, clouds,
    waterwalls;
  - m_can_see_u(): invisibility / underwater.

State layout (C -> pyhack):
  levl[x][y]               -> world.map.tiles[y][x]   (core/types.py)
  viz_clear[][]            -> world.map.viz_clear
  left_ptrs[][] /
  right_ptrs[][]           -> world.map.left_ptrs / .right_ptrs
  gv.viz_array / rmin/rmax -> world.vision (a HeroVision)
  Algorithm-C file statics -> one _VisionC instance per view_from() call
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .hacklib import is_blind
from .types import (DoorMask, Map, Monster, ObjectType, Pos, TerrainType,
                    Tile, World, is_door, is_obstructed)

# C: vision.h
COULD_SEE = 0x1  # location could be seen, if it were lit
IN_SIGHT = 0x2   # location can be seen
TEMP_LIT = 0x4   # location is temporarily lit (STUB: unused until light.c)

# C: vision.h
MAX_RADIUS = 15

# C: vision.c -- limit offsets for one quadrant of a circle of a given
# radius (the first number of each block); radius r has r+1 entries,
# and the final 16 terminates the range loops.
CIRCLE_DATA = (
    0,
    1,  1,
    2,  2,  1,
    3,  3,  2,  1,
    4,  4,  4,  3,  2,
    5,  5,  5,  4,  3,  2,
    6,  6,  6,  5,  5,  4,  2,
    7,  7,  7,  6,  6,  5,  4,  2,
    8,  8,  8,  7,  7,  6,  6,  4,  2,
    9,  9,  9,  9,  8,  8,  7,  6,  5,  3,
    10, 10, 10, 10, 9,  9,  8,  7,  6,  5,  3,
    11, 11, 11, 11, 10, 10, 9,  9,  8,  7,  5,  3,
    12, 12, 12, 12, 11, 11, 10, 10, 9,  8,  7,  5,  3,
    13, 13, 13, 13, 12, 12, 12, 11, 10, 10, 9,  7,  6, 3,
    14, 14, 14, 14, 13, 13, 13, 12, 12, 11, 10, 9,  8, 6, 3,
    15, 15, 15, 15, 14, 14, 14, 13, 13, 12, 11, 10, 9, 8, 6, 3,
    16,
)

# C: vision.c -- starting indexes into CIRCLE_DATA for each radius.
CIRCLE_START = (
    0, 1, 3, 6, 10, 15, 21, 28, 36, 45,
    55, 66, 78, 91, 105, 120,
)


def circle_ptr(radius: int) -> tuple:
    """C: circle_ptr(z) -- the per-row x offsets of a circle of the
    given radius, dy=0 first (radius+1 values)."""
    if not 1 <= radius <= MAX_RADIUS:
        raise ValueError(f"circle_ptr: illegal range {radius}")
    start = CIRCLE_START[radius]
    return CIRCLE_DATA[start:start + radius + 1]


# ============================================================
# State
# ============================================================

@dataclass
class HeroVision:
    """The hero's current view (C: gv.viz_array + gv.viz_rmin/rmax).

    could_see is indexed [row][col] and holds the COULD_SEE / IN_SIGHT
    bit flags.  A row that was never marked keeps row_min > row_max
    (C: COLNO-1 / 1 initialisation).
    """
    could_see: List[List[int]]
    row_min: List[int]
    row_max: List[int]


def _fresh_hero_vision(m: Map) -> HeroVision:
    """C: get_unused_cs() -- an empty work area: see nothing, and the
    per-row min/max set to the "empty" values."""
    return HeroVision(
        could_see=[[0] * m.width for _ in range(m.height)],
        row_min=[m.width - 1] * m.height,
        row_max=[1] * m.height,
    )


def _ensure(world: World) -> None:
    """Lazily run vision_init() + vision_reset().  C does that in
    newgame()/mklev(); a bare World built by tests gets it on first
    vision use."""
    if world.map.viz_clear is None:
        vision_reset(world)


def vision_init(world: World) -> None:
    """C: vision_init.  One-time allocation of the sight data.  C calls
    this before mklev() in newgame(); here it is called from
    worldgen.new_world (and lazily through _ensure())."""
    m = world.map
    m.viz_clear = [[False] * m.width for _ in range(m.height)]
    m.left_ptrs = [[0] * m.width for _ in range(m.height)]
    m.right_ptrs = [[0] * m.width for _ in range(m.height)]
    world.vision = _fresh_hero_vision(m)


# ============================================================
# Blocking
# ============================================================

def does_block(world: World, pos: Pos) -> int:
    """C: does_block.  Returns 0 if nothing at pos blocks sight, 1 if a
    blocking feature does (opaque terrain, closed door, tree, boulder),
    or 2 for an opaque region (cloud).  The rest of the code only
    distinguishes 0 from non-0 -- same as C."""
    tile = world.map.tile_at(pos)
    if (is_obstructed(tile.typ)
            or tile.typ == TerrainType.TREE
            or (is_door(tile.typ)
                and tile.door_mask
                & (DoorMask.CLOSED | DoorMask.LOCKED | DoorMask.TRAPPED))):
        return 1
    # STUB: CLOUD / waterwall / lavawall / moat blocking -- no such
    # terrain is generated yet.
    # STUB: mimics mimicking a door or boulder block light -- mimic
    # handling is not ported yet.
    # Boulders block light (C: the svl.level.objects scan).
    for item in world.items_at(pos):
        if item.otype == ObjectType.BOULDER:
            return 1
    return 0


def _blocked(world: World, pos: Pos) -> bool:
    return does_block(world, pos) != 0


# ============================================================
# The row scan (viz_clear + left/right pointers)
# ============================================================
#
# Pointer rules (C: the "LEFT and RIGHT pointer rules" comment in
# vision.c, unchanged since 4/4/90):
#
#   clear tile:  left -> first stone to the left (0 if none),
#                right -> first stone to the right (COLNO-1 if none)
#   blocked tile: left -> left-most blocked tile connected to it
#                (a left edge points at itself),
#                right -> right-most blocked tile connected to it
#                (a right edge points at itself)

def _rescan_row(world: World, y: int) -> None:
    """Rebuild one row of viz_clear + left/right pointers from the
    current terrain and boulders -- C's vision_reset() row scan.

    C seeds the scan with "column 0 is always stone" because column 0
    is off-level there; pyhack grids are fully real, so the scan seeds
    from the actual tile at (0, y).
    """
    m = world.map
    w = m.width
    clear = m.viz_clear
    left = m.left_ptrs
    right = m.right_ptrs
    dig_left = 0
    block = _blocked(world, (0, y))
    x = 1
    while x < w:
        if block != _blocked(world, (x, y)):
            if block:
                for i in range(dig_left, x):
                    left[y][i] = dig_left
                    right[y][i] = x - 1
            else:
                i = dig_left
                if dig_left:
                    dig_left -= 1  # point at first blocked point
                # the clear run spans [i, x) -- i is captured BEFORE
                # the dig_left decrement (as in C)
                for j in range(i, x):
                    left[y][j] = dig_left
                    right[y][j] = x
                    clear[y][j] = True
            dig_left = x
            block = not block
        x += 1
    # handle right boundary; almost identical for blocked/unblocked
    i = dig_left
    if not block and dig_left:
        dig_left -= 1  # point at first blocked point
    for j in range(i, w):
        left[y][j] = dig_left
        right[y][j] = w - 1
        clear[y][j] = not block


def vision_reset(world: World) -> None:
    """C: vision_reset.  Rebuild viz_clear + the left/right pointer rows
    from the current terrain and boulders, and reset the hero's view.
    Call after level generation (C: after mklev()) and after a bulk
    terrain change.  Must run after the level's objects are in place."""
    m = world.map
    if m.viz_clear is None:
        vision_init(world)
    m.viz_clear = [[False] * m.width for _ in range(m.height)]
    m.left_ptrs = [[0] * m.width for _ in range(m.height)]
    m.right_ptrs = [[0] * m.width for _ in range(m.height)]
    for y in range(m.height):
        _rescan_row(world, y)
    world.vision = _fresh_hero_vision(m)


def block_point(world: World, pos: Pos) -> None:
    """C: block_point (fill_point).  Make a location opaque to sight
    (a boulder was placed there, a door closed, ...).  The terrain /
    object state must already reflect the change.

    STUB: C updates the row pointers in O(1) (fill_point); this port
    rescans the whole row (same result, O(width)).  The faithful
    dig_point()/fill_point() port is deferred."""
    _ensure(world)
    if world.map.viz_clear[pos[1]][pos[0]]:
        _rescan_row(world, pos[1])


def unblock_point(world: World, pos: Pos) -> None:
    """C: unblock_point (dig_point).  Make a location transparent to
    sight (a boulder was moved away, a door opened, ...).  STUB: row
    rescan, see block_point()."""
    _ensure(world)
    if not world.map.viz_clear[pos[1]][pos[0]]:
        _rescan_row(world, pos[1])


def recalc_block_point(world: World, pos: Pos) -> None:
    """C: recalc_block_point -- block or unblock, whichever the current
    state requires."""
    if does_block(world, pos):
        block_point(world, pos)
    else:
        unblock_point(world, pos)


def set_tile(world: World, pos: Pos, tile: Tile) -> None:
    """Replace a tile and refresh that row's sight data (C: terrain
    changes flow through block_point()/unblock_point()/
    recalc_block_point()).  Use for doors and boulder-like changes;
    call vision_reset() for full rebuilds."""
    world.map.tiles[pos[1]][pos[0]] = tile
    recalc_block_point(world, pos)


# ============================================================
# Bresenham line of sight (C: the q?_path macros)
# ============================================================
#
# "Draw" a line from the start to the destination and report whether
# every tile STRICTLY BETWEEN the endpoints is clear.  The start and
# finish points themselves are never checked (a wall IS visible, a
# boulder IS visible until it is on you).  Generalised integer
# Bresenham's algorithm, per quadrant, from _Procedural Elements for
# Computer Graphics_ (Rogers, McGraw-Hill, 1985).

def _q1_path(m: Map, srow: int, scol: int, row: int, col: int) -> bool:
    """C: q1_path, quadrant I -- destination up-right of the start."""
    x, y = scol, srow
    dx, dy = col - x, y - row
    dxs, dys = dx << 1, dy << 1
    if dy > dx:
        err = dxs - dy
        for _ in range(dy - 1, 0, -1):
            if err >= 0:
                x += 1
                err -= dys
            y -= 1
            err += dxs
            if not m.viz_clear[y][x]:
                return False
    else:
        err = dys - dx
        for _ in range(dx - 1, 0, -1):
            if err >= 0:
                y -= 1
                err -= dxs
            x += 1
            err += dys
            if not m.viz_clear[y][x]:
                return False
    return True


def _q2_path(m: Map, srow: int, scol: int, row: int, col: int) -> bool:
    """C: q2_path, quadrant II -- destination up-left of the start."""
    x, y = scol, srow
    dx, dy = x - col, y - row
    dxs, dys = dx << 1, dy << 1
    if dy > dx:
        err = dxs - dy
        for _ in range(dy - 1, 0, -1):
            if err >= 0:
                x -= 1
                err -= dys
            y -= 1
            err += dxs
            if not m.viz_clear[y][x]:
                return False
    else:
        err = dys - dx
        for _ in range(dx - 1, 0, -1):
            if err >= 0:
                y -= 1
                err -= dxs
            x -= 1
            err += dys
            if not m.viz_clear[y][x]:
                return False
    return True


def _q3_path(m: Map, srow: int, scol: int, row: int, col: int) -> bool:
    """C: q3_path, quadrant III -- destination down-left of the start."""
    x, y = scol, srow
    dx, dy = x - col, row - y
    dxs, dys = dx << 1, dy << 1
    if dy > dx:
        err = dxs - dy
        for _ in range(dy - 1, 0, -1):
            if err >= 0:
                x -= 1
                err -= dys
            y += 1
            err += dxs
            if not m.viz_clear[y][x]:
                return False
    else:
        err = dys - dx
        for _ in range(dx - 1, 0, -1):
            if err >= 0:
                y += 1
                err -= dxs
            x -= 1
            err += dys
            if not m.viz_clear[y][x]:
                return False
    return True


def _q4_path(m: Map, srow: int, scol: int, row: int, col: int) -> bool:
    """C: q4_path, quadrant IV -- destination down-right of the start."""
    x, y = scol, srow
    dx, dy = col - x, row - y
    dxs, dys = dx << 1, dy << 1
    if dy > dx:
        err = dxs - dy
        for _ in range(dy - 1, 0, -1):
            if err >= 0:
                x += 1
                err -= dys
            y += 1
            err += dxs
            if not m.viz_clear[y][x]:
                return False
    else:
        err = dys - dx
        for _ in range(dx - 1, 0, -1):
            if err >= 0:
                y += 1
                err -= dxs
            x += 1
            err += dys
            if not m.viz_clear[y][x]:
                return False
    return True


def clear_path(world: World, a: Pos, b: Pos) -> bool:
    """C: clear_path(col1, row1, col2, row2).  Is there an unobstructed
    straight line of sight between the two positions?  Endpoints are
    never checked.  Used by the m_cansee() family and do_clear_area()."""
    _ensure(world)
    col1, row1 = a
    col2, row2 = b
    m = world.map
    if col1 < col2:
        if row1 > row2:
            return _q1_path(m, row1, col1, row2, col2)
        return _q4_path(m, row1, col1, row2, col2)
    if row1 > row2:
        return _q2_path(m, row1, col1, row2, col2)
    if row1 == row2 and col1 == col2:
        return True
    return _q3_path(m, row1, col1, row2, col2)


# ============================================================
# Algorithm C (C: view_from / right_side / left_side)
# ============================================================

class _VisionC:
    """Algorithm C state for one view_from() call.

    C keeps this in file-statics (start_row, start_col, step, cs_rows,
    cs_left, cs_right, vis_func, varg); one instance per call is the
    Python equivalent.  The recursion depth is bounded by the map's row
    count.
    """

    def __init__(self, m: Map, srow: int, scol: int,
                 cs_rows: Optional[List[List[int]]],
                 row_min: Optional[List[int]],
                 row_max: Optional[List[int]],
                 range_: int,
                 func: Optional[Callable[[int, int, object], None]],
                 arg):
        self.map = m
        self.start_row = srow
        self.start_col = scol
        self.step = 1            # +1 = down, -1 = up (set per side)
        self.cs_rows = cs_rows
        self.row_min = row_min
        self.row_max = row_max
        self.range = range_
        self.func = func
        self.arg = arg
        self.limits = None
        self.limits_idx = 0
        if range_:
            if not 1 <= range_ <= MAX_RADIUS:
                raise ValueError(f"view_from called with range {range_}")
            # C: circle_ptr(range) + 1 -- the start row (dy = 0) is
            # handled by run() itself; the slice keeps the terminator
            # the `deeper` test peeks at.
            start = CIRCLE_START[range_]
            self.limits = CIRCLE_DATA[start + 1:start + range_ + 2]

    def run(self) -> None:
        """C: view_from -- mark all locations visible from the start.
        NOTE this is (y, x), as in C."""
        m = self.map
        w, h = m.width, m.height
        srow, scol = self.start_row, self.start_col
        clear = m.viz_clear
        if clear[srow][scol]:
            left = m.left_ptrs[srow][scol]
            right = m.right_ptrs[srow][scol]
        else:
            # When in stone, you can only see your adjacent squares,
            # unless you are on a boundary or a stone/clear boundary.
            left = 0 if scol == 0 else (
                m.left_ptrs[srow][scol - 1] if clear[srow][scol - 1]
                else scol - 1)
            right = w - 1 if scol == w - 1 else (
                m.right_ptrs[srow][scol + 1] if clear[srow][scol + 1]
                else scol + 1)
        if self.range:
            if left < scol - self.range:
                left = scol - self.range
            if right > scol + self.range:
                right = scol + self.range
        if self.func is not None:
            for i in range(left, right + 1):
                self.func(i, srow, self.arg)
        else:
            rowp = self.cs_rows[srow]
            for i in range(left, right + 1):
                rowp[i] = COULD_SEE
            self.row_min[srow] = left
            self.row_max[srow] = right
        # Check what could be seen in the quadrants.  We need to check
        # for valid rows here, since right_side()/left_side() don't.
        nrow = srow + 1
        if nrow < h:  # move down
            self.step = 1
            if scol < w - 1:
                self.right_side(nrow, scol, right)
            if scol > 0:
                self.left_side(nrow, left, scol)
        nrow = srow - 1
        if nrow >= 0:  # move up
            self.step = -1
            if scol < w - 1:
                self.right_side(nrow, scol, right)
            if scol > 0:
                self.left_side(nrow, left, scol)

    def _mark(self, row: int, a: int, b: int) -> None:
        """Set COULD_SEE (or call func) for a..b on `row`, and keep the
        row min/max (C: set_cs / set_min / set_max)."""
        if self.func is not None:
            for i in range(a, b + 1):
                self.func(i, row, self.arg)
            return
        rowp = self.cs_rows[row]
        for i in range(a, b + 1):
            rowp[i] = COULD_SEE
        if a < self.row_min[row]:
            self.row_min[row] = a
        if b > self.row_max[row]:
            self.row_max[row] = b

    def _qpath(self, row: int, col: int) -> bool:
        """Clear line of sight from the start to (row, col) on the
        right side (C: q1_path when step < 0, q4_path when step > 0)."""
        if self.step < 0:
            return _q1_path(self.map, self.start_row, self.start_col,
                            row, col)
        return _q4_path(self.map, self.start_row, self.start_col, row, col)

    def _qpath_left(self, row: int, col: int) -> bool:
        """Clear line of sight from the start to (row, col) on the left
        side (C: q2_path when step < 0, q3_path when step > 0)."""
        if self.step < 0:
            return _q2_path(self.map, self.start_row, self.start_col,
                            row, col)
        return _q3_path(self.map, self.start_row, self.start_col, row, col)

    def _deeper(self, nrow: int) -> bool:
        """Can the recursion go one row deeper: the row is in bounds and
        (when range-limited) the next row is still within the circle.
        C tells the latter by checking that the next limit value is not
        the start of a new circle radius (it depends on the structure
        of CIRCLE_DATA)."""
        if not 0 <= nrow < self.map.height:
            return False
        if self.limits is None:
            return True
        return (self.limits[self.limits_idx]
                >= self.limits[self.limits_idx + 1])

    def right_side(self, row: int, left: int, right_mark: int) -> None:
        """C: right_side.  Mark the visible locations on one quadrant
        of the right side; the quadrant comes from self.step."""
        m = self.map
        w = m.width
        clear = m.viz_clear
        nrow = row + self.step
        deeper = self._deeper(nrow)
        if self.limits is not None:
            lim_max = min(self.start_col + self.limits[self.limits_idx],
                          w - 1)
            if right_mark > lim_max:
                right_mark = lim_max
            self.limits_idx += 1  # prepare for next row
        else:
            lim_max = w - 1

        while left <= right_mark:
            right_edge = m.right_ptrs[row][left]
            if right_edge > lim_max:
                right_edge = lim_max

            if not clear[row][left]:
                # Jump to the far side of a stone wall: everything up to
                # the edge is visible (a wall IS visible).
                if right_edge > right_mark:
                    # If the mark on the previous row was a clear
                    # position, the odds are that we can actually see
                    # part of the wall beyond the mark on this row.  If
                    # so, then see one beyond the mark.  (C: a kludge so
                    # corners with an adjacent doorway show up.)
                    right_edge = (right_mark + 1
                                  if clear[row - self.step][right_mark]
                                  else right_mark)
                self._mark(row, left, right_edge)
                left = right_edge + 1  # no limit check necessary
                continue

            # No checking needed if our left side is the start column.
            if left != self.start_col:
                # Find the left side: move right until we can see it or
                # we run into a wall.
                while left <= right_edge:
                    if self._qpath(row, left):
                        break
                    left += 1
                # Check for boundary conditions.  Check (2) is needed to
                # break an infinite loop where left == right_edge ==
                # right_mark == lim_max.
                if left > lim_max:
                    return
                if left == lim_max:
                    self._mark(row, left, left)
                    return
                # Check if we can see any spots in the opening.  We
                # might (left == right_edge) or might not (left ==
                # right_edge+1) have been able to see the far wall.
                # Make sure we *can* see the wall (remember, we can see
                # the spot above/below this one) by backing up.
                if left >= right_edge:
                    left = right_edge  # for the case left == right_edge+1
                    continue

            # Find the right side.  If the marker from the previous row
            # is closer than the edge on this row, we have to check how
            # far we can see around the corner (under the overhang):
            # stop at the first non-visible spot or the far wall.
            # Otherwise we can see the right edge of the current row.
            # This must be a strict "less than" so that we can always
            # see a horizontal wall, even if it is adjacent to us.
            if right_mark < right_edge:
                right = right_mark
                while right <= right_edge:
                    if not self._qpath(row, right):
                        break
                    right += 1
                right -= 1  # get rid of the last increment
            else:
                right = right_edge

            # We have the range that we want.  Set the bits.
            if left <= right:
                # An ugly special case.  If you are adjacent to a
                # vertical wall and it has a break in it, the right mark
                # is set to be start_col.  We *want* to be able to see
                # adjacent vertical walls, so set it back.
                if (left == right and left == self.start_col
                        and self.start_col < w - 1
                        and not clear[row][self.start_col + 1]):
                    right = self.start_col + 1
                if right > lim_max:
                    right = lim_max
                self._mark(row, left, right)
                # Recursive call for the next finger of light.
                if deeper:
                    self.right_side(nrow, left, right)
                left = right + 1  # no limit check necessary

    def left_side(self, row: int, left_mark: int, right: int) -> None:
        """C: left_side.  The mirror image of right_side()."""
        m = self.map
        clear = m.viz_clear
        nrow = row + self.step
        deeper = self._deeper(nrow)
        if self.limits is not None:
            lim_min = max(self.start_col - self.limits[self.limits_idx], 0)
            if left_mark < lim_min:
                left_mark = lim_min
            self.limits_idx += 1  # prepare for next row
        else:
            lim_min = 0

        while right >= left_mark:
            left_edge = m.left_ptrs[row][right]
            if left_edge < lim_min:
                left_edge = lim_min

            if not clear[row][right]:
                # Jump to the far side of a stone wall.
                if left_edge < left_mark:
                    # Maybe see more (C: the same doorway kludge).
                    left_edge = (left_mark - 1
                                 if clear[row - self.step][left_mark]
                                 else left_mark)
                self._mark(row, left_edge, right)
                right = left_edge - 1  # no limit check necessary
                continue

            if right != self.start_col:
                # Find the right side.
                while right >= left_edge:
                    if self._qpath_left(row, right):
                        break
                    right -= 1
                # Check for boundary conditions.
                if right < lim_min:
                    return
                if right == lim_min:
                    self._mark(row, right, right)
                    return
                # Check if we can see any spots in the opening.
                if right <= left_edge:
                    right = left_edge
                    continue

            # Find the left side.
            if left_mark > left_edge:
                left = left_mark
                while left >= left_edge:
                    if not self._qpath_left(row, left):
                        break
                    left -= 1
                left += 1  # get rid of the last decrement
            else:
                left = left_edge

            if left <= right:
                # An ugly special case.
                if (left == right and right == self.start_col
                        and self.start_col > 0
                        and not clear[row][self.start_col - 1]):
                    left = self.start_col - 1
                if left < lim_min:
                    left = lim_min
                self._mark(row, left, right)
                # Recurse.
                if deeper:
                    self.left_side(nrow, left, right)
                right = left - 1  # no limit check necessary


def view_from(world: World, origin: Pos, range_: int = 0) -> HeroVision:
    """C: view_from, as a standalone query: a fresh HeroVision holding
    the locations visible from `origin` (range_ = 0: unlimited; 1..15:
    the CIRCLE_DATA circle).  Does NOT touch world.vision."""
    _ensure(world)
    hv = _fresh_hero_vision(world.map)
    _VisionC(world.map, origin[1], origin[0], hv.could_see, hv.row_min,
             hv.row_max, range_, None, None).run()
    return hv


# ============================================================
# The hero's current view
# ============================================================

def vision_recalc(world: World) -> None:
    """C: vision_recalc (the control = 0 path).  Recompute the hero's
    current view from the hero's position.  C calls this after the hero
    moves and after the monster move (moveloop); step() calls it once
    per turn, before the monster phase.

    Even a blind hero gets a valid array -- C computes it so that
    monsters can see the hero even when the hero cannot see them; the
    queries below (like C's cansee/couldsee macros) do not check
    blindness.  "Can this actor see at all?" is core.hacklib.can_see.
    """
    _ensure(world)
    m = world.map
    hx, hy = world.hero.pos
    hv = _fresh_hero_vision(m)
    _VisionC(m, hy, hx, hv.could_see, hv.row_min, hv.row_max, 0, None,
             None).run()
    # STUB: no light sources yet (light.c) -- everything the hero could
    # see is treated as lit, so IN_SIGHT gets every COULD_SEE cell.  C
    # sets IN_SIGHT from room lighting, xray and night vision instead;
    # all of that is deferred.
    for row in range(m.height):
        lo, hi = hv.row_min[row], hv.row_max[row]
        if hi < lo:
            continue
        rowp = hv.could_see[row]
        for col in range(max(0, lo), min(m.width - 1, hi) + 1):
            if rowp[col] & COULD_SEE:
                rowp[col] |= IN_SIGHT
    world.vision = hv


def can_see(world: World, pos: Pos) -> bool:
    """C: cansee(x, y).  Can the hero *see* this location (IN_SIGHT)?
    Requires vision_recalc() to have run (new_world() and step() do)."""
    return world.vision.could_see[pos[1]][pos[0]] & IN_SIGHT


def could_see(world: World, pos: Pos) -> bool:
    """C: couldsee(x, y).  Does the hero have a clear line of sight to
    this location (COULD_SEE), lit or not?"""
    return world.vision.could_see[pos[1]][pos[0]] & COULD_SEE


# ============================================================
# Monster sight (C: the m_cansee / m_canseeu macros in vision.h)
# ============================================================

def m_can_see(world: World, mon: Monster, pos: Pos) -> bool:
    """C: m_cansee(m, x, y) == clear_path(m->mx, m->my, x, y).  Can the
    monster see the location?  C leaves the blindness check to the
    caller (mcansee); this port checks it here, at the choke point."""
    if is_blind(mon):
        return False
    return clear_path(world, mon.pos, pos)


def m_can_see_u(world: World, mon: Monster) -> bool:
    """C: m_canseeu(m).  Could the monster see the hero?  C's
    assumption: if the hero has a clear line of sight to the monster's
    location and the hero is visible, then the monster can see the hero
    -- hence the couldsee() on the MONSTER's tile.  STUB:
    invisibility / underwater are not ported yet, so the hero is
    always visible."""
    if is_blind(mon):
        return False
    return could_see(world, mon.pos)


# ============================================================
# Area of effect (C: do_clear_area)
# ============================================================

def do_clear_area(world: World, origin: Pos, range_: int,
                  func: Callable[[int, int, object], None], arg) -> None:
    """C: do_clear_area -- the area-of-effect "engine".  Call
    func(x, y, arg) for each location within `range_` of `origin` that
    has a clear line of sight from `origin` (the CIRCLE_DATA offsets).
    If `origin` is the hero's location, the hero's could_see array is
    reused (C: the vision-matrix fast path); otherwise view_from()
    runs directly.

    STUB: C's `override_vision` (detection spells see through water
    and clouds) is always False -- no water/air levels and no
    detection spells yet."""
    if not 1 <= range_ <= MAX_RADIUS:
        raise ValueError(f"do_clear_area: illegal range {range_}")
    x, y = origin
    if (x, y) != world.hero.pos:
        _ensure(world)
        _VisionC(world.map, y, x, None, None, None, range_, func, arg).run()
        return
    # C: if (gv.vision_full_recalc) vision_recalc(0) -- here the recalc
    # is unconditional (it is cheap at demo map sizes and keeps the
    # array fresh after any move).
    vision_recalc(world)
    m = world.map
    limits = circle_ptr(range_)
    max_y = min(y + range_, m.height - 1)
    for row in range(max(0, y - range_), max_y + 1):
        offset = limits[abs(row - y)]
        # C clamps the column to 1 because column 0 is off-level there;
        # pyhack's column 0 is a real tile.
        for col in range(max(0, x - offset), min(x + offset, m.width - 1) + 1):
            if could_see(world, (col, row)):
                func(col, row, arg)
