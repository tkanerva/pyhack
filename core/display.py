"""The display layer: what the hero remembers of the level (src/display.c).

Vision (core/vision.py) decides which locations the hero can see right
now.  This module decides *what is remembered* at each of them, and the
window port (`ui.console.render`) draws the result.  That is C's split
between vision.c, display.c and the window port, kept intact.

The model is C's exactly: every location carries a *glyph* -- the
hero's memory of what is there (`Tile.glyph`, C: `levl[x][y].glyph`).
It is never a monster ("monsters float above the map"); it is the
terrain, a remembered object, or a known trap.  A location the hero has
never seen keeps GLYPH_UNEXPLORED, which draws blank.  So a map square
is drawn, in order:

    the hero's own square  '@'   (render; the hero always shows up)
    a visible monster      'M'   (render; never remembered)
    memory: terrain / a remembered object / a known trap
                                 (`Tile.glyph`, written here)

and nothing at all for the parts of the level the hero has not been to
yet.  That is the whole point of the module: before it, the renderer
drew `Tile.typ` -- the *true* terrain -- for every square of the level,
so the hero looked through every wall, and unexplored stone (a wall
test includes stone) came out as '#' just like a real corridor.

Ported:

  the glyph space       core.glyph (C: display.h + defsym.h)
  seenv / SV0..SV7      the "seen vector" -- the octants a square has
                        been seen from (C: rm.h seenv, set by
                        set_seenv() and the vision_recalc() update
                        loop)
  set_seenv()           the seen-vector update
  back_to_glyph()       terrain -> glyph (C's switch over rm.typ,
                        including "a wall you have not seen is stone")
  wall_angle()          which wall symbol a seen wall draws as
                        (STUB: the plain per-type symbol -- see below)
  trap_to_glyph()       trap -> glyph (C: trap_to_defsym[ttyp])
  map_background() /
  map_object() /
  map_trap() /
  map_location()        record what is at a location into the memory
  newsym()              the workhorse: one location, in or out of sight
  docrt()               the full redraw: recalc the view, then newsym()
                        every location (C: the window port's docrt(),
                        which pyhack's ui.render calls before a frame)
  mon_visible()         "does this monster show on the map?" (C:
                        canseemon, reduced)
  glyph_to_char()       glyph -> the character to print (C: the window
                        port's print_glyph)

Stubs (marked STUB; each needs machinery that is not ported yet):

  - lighting (light.c): the hero's view treats every location he could
    see as lit, so `Tile.lit` is the only "is this floor visible as
    floor" information there is, and `back_to_glyph()` reads it for
    ROOM ('.' when lit, ' ' when dark).  C decides that from IN_SIGHT
    and the room's lighting;
  - wall_angle(): C picks the wall symbol from the terrain type, the
    seen vector AND the wall_info mode (set_wall()/set_corn()/
    set_twall()/set_crosswall() bake "which way is this corner open"
    in at generation time).  The mode is not ported, so a seen wall
    draws with the plain per-type symbol -- C's WM_MASK == 0 branch of
    wall_angle().  The seenv half *is* ported, so an unseen wall still
    draws as stone, never as a wall;
  - the monster glyph table (mon_to_glyph / MONSTERSYMS): a monster is
    the single 'M' the renderer overlays, never part of the memory;
  - regions (gas clouds), engravings, mimicry, levitation ("feel
    location"), hallucination, the rogue level;
  - C's `flags.hero_memory` switch (the memory is always on) and the
    `dark_room` display option (S_darkroom is defined but never
    written: an unlit floor draws as stone -- the no-color build).
"""
from __future__ import annotations

from typing import Dict, Optional

from .glyph import (CMAP_CHARS, GLYPH_CMAP_OFF, GLYPH_OBJ_OFF, Cmap,
                    cmap_to_glyph, glyph_is_cmap, glyph_is_object,
                    objclass_to_glyph)
from .objects import class_glyph
from .types import (DoorMask, Item, Monster, Pos, STAIR_DOWN, TerrainType,
                    Tile, Trap, TrapType, World, is_wall)
from .vision import can_see, vision_recalc

# ============================================================
# The seen vector (C: rm.h SV0..SV7)
# ============================================================
#
# Eight bits, one per octant around a location:
#
#               0 1 2
#               7 x 3
#               6 5 4
#
# "the vector's primary use is determining how walls are seen.  E.g. a
# wall sometimes looks like stone on one side, but is seen as wall from
# the other" (display.c).  It is also the record of *whether* a square
# was ever seen at all (seenv == 0).

SV0 = 0x01
SV1 = 0x02
SV2 = 0x04
SV3 = 0x08
SV4 = 0x10
SV5 = 0x20
SV6 = 0x40
SV7 = 0x80
SVALL = 0xFF

# C: display.c seenv_matrix[3][3], indexed [sign(dy) + 1][sign(dx) + 1].
SEENV_MATRIX = (
    (SV2, SV1, SV0),
    (SV3, SVALL, SV7),
    (SV4, SV5, SV6),
)


def _sign(value: int) -> int:
    """C: sign(x) -- -1, 0 or 1."""
    if value > 0:
        return 1
    return -1 if value < 0 else 0


def set_seenv(tile: Tile, frm: Pos, to: Pos) -> None:
    """C: set_seenv -- remember that the hero at `frm` saw `to`, by
    OR-ing the octant he saw it from into the seen vector.

    The bits say where the *viewer* is relative to the square (the C
    diagram's 0..7 positions around the centre), which is why the row
    index is sign(frm_y - to_y) -- C's `dy = y0 - y`, i.e. up the
    screen is negative row."""
    dx = to[0] - frm[0]
    dy = frm[1] - to[1]
    tile.seenv |= SEENV_MATRIX[_sign(dy) + 1][_sign(dx) + 1]


# ============================================================
# Terrain -> glyph (C: back_to_glyph / wall_angle)
# ============================================================

# C: wall_angle(), the WM_MASK == 0 branch: a wall draws with the
# symbol of its own type (C's refined version also reads the wall_info
# mode -- not ported, see the module docstring).
_WALL_CMAP: Dict[TerrainType, Cmap] = {
    TerrainType.VWALL: Cmap.S_vwall,
    TerrainType.HWALL: Cmap.S_hwall,
    TerrainType.TLCORNER: Cmap.S_tlcorn,
    TerrainType.TRCORNER: Cmap.S_trcorn,
    TerrainType.BLCORNER: Cmap.S_blcorn,
    TerrainType.BRCORNER: Cmap.S_brcorn,
    TerrainType.CROSSWALL: Cmap.S_crwall,
    TerrainType.TUWALL: Cmap.S_tuwall,
    TerrainType.TDWALL: Cmap.S_tdwall,
    TerrainType.TLWALL: Cmap.S_tlwall,
    TerrainType.TRWALL: Cmap.S_trwall,
}

# C: trap_to_defsym[] (display.h) -- the trap -> cmap mapping.
_TRAP_CMAP: Dict[TrapType, Cmap] = {
    TrapType.PIT: Cmap.S_pit,
    TrapType.SPIKED_PIT: Cmap.S_spiked_pit,
    TrapType.TRAPDOOR: Cmap.S_trap_door,
    TrapType.ARROW_TRAP: Cmap.S_arrow_trap,
    TrapType.DART_TRAP: Cmap.S_dart_trap,
    TrapType.FIRE_TRAP: Cmap.S_fire_trap,
    TrapType.SLEEPING_GAS: Cmap.S_sleeping_gas_trap,
    TrapType.TELEPORTATION: Cmap.S_teleportation_trap,
    TrapType.ANTI_MAGIC: Cmap.S_anti_magic_trap,
    TrapType.WEB: Cmap.S_web,
    TrapType.ROLLING_BOULDER: Cmap.S_rolling_boulder_trap,
    TrapType.MAGIC_PORTAL: Cmap.S_magic_portal,
    TrapType.LEVEL_TELEPORTER: Cmap.S_level_teleporter,
}


def wall_angle(tile: Tile) -> Cmap:
    """C: wall_angle -- the symbol a seen wall draws as.  C refines it
    with the wall_info mode; that half is a STUB, so this is the plain
    per-type symbol (C's WM_MASK == 0 branch).  A secret door wears the
    wall symbol of its orientation, as in C."""
    if tile.typ == TerrainType.SDOOR:
        return Cmap.S_hwall if tile.horizontal else Cmap.S_vwall
    return _WALL_CMAP.get(tile.typ, Cmap.S_stone)


def back_to_glyph(world: World, pos: Pos) -> int:
    """C: back_to_glyph(x, y) -- the glyph of a location the hero can
    see: the real background, or the wall symbol the seen vector
    allows."""
    tile = world.map.tile_at(pos)
    typ = tile.typ
    if typ in (TerrainType.SCORR, TerrainType.STONE):
        # C: an arboreal level draws its stone as tree
        idx = Cmap.S_tree if world.map.flags.arboreal else Cmap.S_stone
    elif typ == TerrainType.ROOM:
        # STUB: C returns S_room and lets the lighting decide whether
        # the floor is visible; with no light sources ported, the
        # square's own `lit` flag is that decision ('.' lit, ' ' dark).
        idx = Cmap.S_room if tile.lit else Cmap.S_stone
    elif typ == TerrainType.CORR:
        idx = Cmap.S_litcorr if tile.waslit else Cmap.S_corr
    elif typ == TerrainType.DBWALL:
        # the raised drawbridge (rm.h: a DBWALL *is* a drawbridge wall);
        # checked before the wall branch, where is_wall() would catch it
        idx = Cmap.S_hcdbridge if tile.horizontal else Cmap.S_vcdbridge
    elif typ == TerrainType.SDOOR or is_wall(typ):
        # "a wall sometimes looks like stone on one side": a wall the
        # hero has never seen draws as stone, never as a wall
        idx = wall_angle(tile) if tile.seenv else Cmap.S_stone
    elif typ == TerrainType.DOOR:
        if tile.door_mask & DoorMask.BROKEN:
            idx = Cmap.S_ndoor
        elif tile.is_door_open():
            idx = Cmap.S_hodoor if tile.horizontal else Cmap.S_vodoor
        else:
            idx = Cmap.S_hcdoor if tile.horizontal else Cmap.S_vcdoor
    elif typ == TerrainType.DRAWBRIDGE_UP:
        # STUB: C reads the drawbridgemask underneath (moat / lava /
        # ice / floor); no drawbridge is generated yet, so it is water
        idx = Cmap.S_pool
    elif typ == TerrainType.DRAWBRIDGE_DOWN:
        idx = Cmap.S_hodbridge if tile.horizontal else Cmap.S_vodbridge
    elif typ == TerrainType.IRONBARS:
        idx = Cmap.S_bars
    elif typ == TerrainType.TREE:
        idx = Cmap.S_tree
    elif typ in (TerrainType.POOL, TerrainType.MOAT):
        idx = Cmap.S_pool
    elif typ == TerrainType.STAIRS:
        idx = (Cmap.S_dnstair if tile.stair_dir == STAIR_DOWN
               else Cmap.S_upstair)
    elif typ == TerrainType.LADDER:
        idx = (Cmap.S_dnladder if tile.stair_dir == STAIR_DOWN
               else Cmap.S_upladder)
    elif typ == TerrainType.FOUNTAIN:
        idx = Cmap.S_fountain
    elif typ == TerrainType.SINK:
        idx = Cmap.S_sink
    elif typ == TerrainType.ALTAR:
        idx = Cmap.S_altar
    elif typ == TerrainType.GRAVE:
        idx = Cmap.S_grave
    elif typ == TerrainType.THRONE:
        idx = Cmap.S_throne
    elif typ == TerrainType.ICE:
        idx = Cmap.S_ice
    elif typ == TerrainType.LAVAPOOL:
        idx = Cmap.S_lava
    elif typ == TerrainType.LAVAWALL:
        idx = Cmap.S_lavawall
    elif typ == TerrainType.AIR:
        idx = Cmap.S_air
    elif typ == TerrainType.CLOUD:
        idx = Cmap.S_cloud
    elif typ == TerrainType.WATER:
        idx = Cmap.S_water
    else:
        # C lists every type; an unknown one must not leak the true
        # terrain, so it draws as stone
        idx = Cmap.S_stone
    return cmap_to_glyph(idx)


def trap_to_glyph(trap: Trap) -> int:
    """C: trap_to_glyph(trap) -- the symbol of a known trap (every trap
    type has one in defsym.h; all but the web are '^')."""
    return cmap_to_glyph(_TRAP_CMAP.get(trap.trap_type, Cmap.S_stone))


def obj_to_glyph(item: Item) -> int:
    """C: obj_to_glyph -- the glyph of an object lying on the floor.

    Pyhack's object block is per class (see core.glyph), and a
    hand-built Item may have no class (`oclass` 0 == C's RANDOM class,
    which def_oc_syms[] draws as nothing)."""
    return objclass_to_glyph(item.oclass)


# ============================================================
# Recording what is at a location (C: the map_* routines)
# ============================================================

def map_background(world: World, pos: Pos) -> None:
    """C: map_background -- the real background becomes the memory (the
    hero can see the location)."""
    world.map.tile_at(pos).glyph = back_to_glyph(world, pos)


def map_object(world: World, pos: Pos, item: Item) -> None:
    """C: map_object -- a visible object becomes the memory."""
    world.map.tile_at(pos).glyph = obj_to_glyph(item)


def map_trap(world: World, pos: Pos, trap: Trap) -> None:
    """C: map_trap -- a known trap becomes the memory."""
    world.map.tile_at(pos).glyph = trap_to_glyph(trap)


def map_location(world: World, pos: Pos, item: Optional[Item] = None,
                 trap: Optional[Trap] = None) -> None:
    """C: map_location -- record whatever is at a location the hero can
    see: an object, else a known trap, else the background (an
    engraving sits between the trap and the background in C; there are
    no engravings yet)."""
    if item is not None:
        map_object(world, pos, item)
    elif trap is not None and trap.seen:
        map_trap(world, pos, trap)
    else:
        map_background(world, pos)


# ============================================================
# newsym / docrt (C: the workhorses)
# ============================================================

def _newsym(world: World, pos: Pos, item: Optional[Item],
            trap: Optional[Trap]) -> None:
    """C: newsym -- update one location, given what is on it."""
    if not can_see(world, pos):
        # C: out of sight -- the memory (lev->glyph) is what shows.  In
        # C this branch can also *edit* the memory (the "darkened while
        # unseen" corrections); those need light.c: STUB.
        return
    tile = world.map.tile_at(pos)
    # C: lev->waslit = (lev->lit != 0) -- remember the lit condition
    tile.waslit = tile.lit
    # C sets the seen vector in vision_recalc()'s update loop; this port
    # records it here, at the one place that knows both the hero and the
    # square (docrt() refreshes the whole visible area every frame).
    set_seenv(tile, world.hero.pos, pos)
    map_location(world, pos, item, trap)


def newsym(world: World, pos: Pos) -> None:
    """C: newsym(x, y) -- "possibly put a new glyph at the given
    location.  It is always correct".  The single-location entry point:
    it looks up what is on the square (C: vobj_at() / t_at(), O(1)
    there; docrt() is the bulk path and indexes the level once)."""
    _newsym(world, pos, object_at(world, pos), trap_at(world, pos))


def object_at(world: World, pos: Pos) -> Optional[Item]:
    """The object on top of the pile at `pos` on this level (C:
    vobj_at -- the pile's top; pyhack keeps no pile order, so the last
    one registered wins, as the old renderer had it)."""
    found: Optional[Item] = None
    for item in world.items.values():
        if item.pos == pos and item.carrier is None and item.lev == world.lev:
            found = item
    return found


def trap_at(world: World, pos: Pos) -> Optional[Trap]:
    """The trap at `pos` on this level (C: t_at)."""
    for trap in world.traps.values():
        if trap.pos == pos and trap.lev == world.lev:
            return trap
    return None


def docrt(world: World) -> None:
    """C: docrt() -- the full redraw.  Recalculate the hero's view, then
    newsym() every location: what the hero can see is recorded, the
    rest keeps (and shows) its memory.

    C paints the remembered glyphs into the screen buffer first, then
    vision_recalc(0) updates the memory and the buffer (per changed
    square, through newsym()); pyhack has no screen buffer --
    `ui.console.render` reads the memory after this call -- so only the
    memory half is here, and it refreshes the whole map instead of only
    the squares whose view changed (same result, simpler).

    This is also the seam a headless driver has to call before it reads
    `Tile.glyph`: the memory is only updated here, once per frame, not
    inside step()."""
    vision_recalc(world)
    objects: Dict[Pos, Item] = {}
    for item in world.items.values():
        if (item.pos is not None and item.carrier is None
                and item.lev == world.lev):
            objects[item.pos] = item
    traps: Dict[Pos, Trap] = {t.pos: t for t in world.traps.values()
                              if t.lev == world.lev}
    m = world.map
    for y in range(m.height):
        for x in range(m.width):
            pos = (x, y)
            _newsym(world, pos, objects.get(pos), traps.get(pos))


# ============================================================
# Queries for the window port
# ============================================================

def mon_visible(world: World, mon: Monster) -> bool:
    """C: mon_visible() / canseemon() -- does this monster show on the
    map right now?  STUB: invisibility, mimicry, infravision and the
    "sensed" cases are not ported; what is left is "the hero can see
    the square it stands on".  The level filter is pyhack's own (a
    monster on another level is frozen there and must never ghost onto
    this map)."""
    return bool(mon.alive and mon.lev == world.lev
                and can_see(world, mon.pos))


def glyph_to_char(glyph: int) -> str:
    """The character the window port prints for a glyph (C: the
    defsym.h `ch` column for a cmap glyph, def_oc_syms[] for an object).
    GLYPH_UNEXPLORED and GLYPH_NOTHING draw blank -- which is what makes
    never-seen rock invisible instead of a wall of '#'."""
    if glyph_is_cmap(glyph):
        return CMAP_CHARS[glyph - GLYPH_CMAP_OFF]
    if glyph_is_object(glyph):
        return class_glyph(glyph - GLYPH_OBJ_OFF) or " "
    return " "
