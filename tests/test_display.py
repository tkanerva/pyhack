"""Tests for core/display.py -- the port of src/display.c.

Vision decides what the hero *can* see (tests/test_vision.py); this
module decides what he *remembers* of it.  The properties pinned here
are the ones the old renderer got wrong: a square the hero has never
seen is blank (never '#' -- the reported bug), a wall is a wall only
once it has been seen, an object is remembered after it is out of
sight, a monster never is, and a blind hero sees only his memory.
"""
import random

from core import display, glyph
from core.glyph import (CMAP_CHARS, GLYPH_NOTHING, GLYPH_UNEXPLORED, Cmap,
                        cmap_to_glyph, glyph_is_cmap, glyph_is_object,
                        glyph_is_unexplored, objclass_to_glyph)
from core.objects import ObjClass
from core.types import (Item, Map, ObjectType, TerrainType, Tile, Trap,
                        TrapType)
from core.vision import can_see, vision_recalc
from core.worldgen import new_world
from conftest import make_hero, make_map, make_monster, make_world


# ------------------------------------------------------------
# The glyph space and the defsym.h symbol table
# ------------------------------------------------------------

def test_the_cmap_chars_are_the_defsym_table():
    """The characters are defsym.h's `ch` column: the walls are '|' and
    '-', a corridor is '#', a room floor '.', a door '+' closed and
    '|'/'-' open, and every trap but the web is '^'."""
    assert len(CMAP_CHARS) == len(Cmap)
    for cmap, char in ((Cmap.S_stone, " "), (Cmap.S_vwall, "|"),
                       (Cmap.S_hwall, "-"), (Cmap.S_tlcorn, "-"),
                       (Cmap.S_tuwall, "-"), (Cmap.S_tlwall, "|"),
                       (Cmap.S_ndoor, "."), (Cmap.S_vodoor, "-"),
                       (Cmap.S_hodoor, "|"), (Cmap.S_vcdoor, "+"),
                       (Cmap.S_hcdoor, "+"), (Cmap.S_room, "."),
                       (Cmap.S_corr, "#"), (Cmap.S_litcorr, "#"),
                       (Cmap.S_upstair, "<"), (Cmap.S_dnstair, ">"),
                       (Cmap.S_altar, "_"), (Cmap.S_fountain, "{"),
                       (Cmap.S_pit, "^"), (Cmap.S_web, '"')):
        assert CMAP_CHARS[int(cmap)] == char, cmap


def test_the_glyph_space_separates_cmaps_objects_and_unexplored():
    """C: display.h's glyph_is_* predicates: a cmap glyph, an object
    glyph and the two "nothing here" markers are distinct, and only the
    last two draw blank."""
    assert glyph_is_cmap(cmap_to_glyph(Cmap.S_corr))
    assert not glyph_is_cmap(GLYPH_UNEXPLORED)
    assert not glyph_is_cmap(GLYPH_NOTHING)
    assert glyph_is_object(objclass_to_glyph(ObjClass.SCROLL.value))
    assert glyph_is_object(objclass_to_glyph(99))     # clamped to RANDOM
    assert display.glyph_to_char(objclass_to_glyph(99)) == " "
    assert glyph_is_unexplored(GLYPH_UNEXPLORED)
    assert display.glyph_to_char(GLYPH_UNEXPLORED) == " "
    assert display.glyph_to_char(GLYPH_NOTHING) == " "
    assert display.glyph_to_char(cmap_to_glyph(Cmap.S_corr)) == "#"
    assert display.glyph_to_char(
        objclass_to_glyph(ObjClass.SCROLL.value)) == "?"


def test_an_unexplored_square_draws_blank():
    """`Tile.glyph` starts at GLYPH_UNEXPLORED (C: levl[][] starts
    unexplored) -- which is why a fresh level draws nothing at all."""
    assert Tile().glyph == GLYPH_UNEXPLORED
    assert glyph.glyph_is_unexplored(Tile().glyph)
    w = new_world(random.Random(42))
    assert all(t.glyph == GLYPH_UNEXPLORED
               for row in w.map.tiles for t in row)
    assert all(t.seenv == 0 for row in w.map.tiles for t in row)


# ------------------------------------------------------------
# docrt(): the memory follows the view
# ------------------------------------------------------------

def _walled_world():
    """A lit 12x8 room split by a vertical wall at x=5, the hero west
    of it, so the east half is out of sight."""
    tiles = [[Tile(typ=TerrainType.ROOM, lit=True) for _ in range(12)]
             for _ in range(8)]
    for y in range(8):
        tiles[y][5] = Tile(typ=TerrainType.VWALL)
    return make_world(map=Map(tiles), hero=make_hero(pos=(2, 4)))


def test_docrt_records_exactly_what_the_hero_can_see():
    """C: newsym() writes the memory only where cansee() is true; a
    square out of sight keeps GLYPH_UNEXPLORED."""
    w = _walled_world()
    display.docrt(w)
    for y in range(w.map.height):
        for x in range(w.map.width):
            tile = w.map.tile_at((x, y))
            if can_see(w, (x, y)):
                assert not glyph_is_unexplored(tile.glyph), (x, y)
                assert tile.seenv != 0, (x, y)
            else:
                assert tile.glyph == GLYPH_UNEXPLORED, (x, y)
                assert tile.seenv == 0, (x, y)


def test_a_wall_is_a_wall_only_once_it_has_been_seen():
    """C: back_to_glyph's `seenv ? wall_angle() : S_stone` -- the bug
    report's point: '#'/wall symbols mean "you have looked at this",
    never "this is the true terrain"."""
    tiles = [[Tile(typ=TerrainType.ROOM, lit=True) for _ in range(12)]
             for _ in range(8)]
    for y in range(8):
        tiles[y][5] = Tile(typ=TerrainType.VWALL)   # seen: it faces the hero
    tiles[4][8] = Tile(typ=TerrainType.VWALL)       # hidden behind it
    tiles[1][3] = Tile(typ=TerrainType.HWALL)       # seen, east-west
    w = make_world(map=Map(tiles), hero=make_hero(pos=(2, 4)))
    display.docrt(w)

    seen = w.map.tile_at((5, 4))
    assert seen.seenv != 0
    assert display.glyph_to_char(seen.glyph) == "|"
    assert display.glyph_to_char(w.map.tile_at((3, 1)).glyph) == "-"
    hidden = w.map.tile_at((8, 4))
    assert hidden.seenv == 0
    assert hidden.glyph == GLYPH_UNEXPLORED
    assert display.glyph_to_char(hidden.glyph) == " "


def test_a_seen_corridor_stays_in_the_memory_after_the_hero_leaves():
    """The remembered half: walking away does not erase what the hero
    saw (C: what is out of sight shows levl[].glyph)."""
    w = _walled_world()
    w.map.tiles[4][3] = Tile(typ=TerrainType.CORR)
    display.docrt(w)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "#"

    w.hero.pos = (8, 4)          # east of the wall: (3,4) is now hidden
    display.docrt(w)
    assert not can_see(w, (3, 4))
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "#"


def test_a_floor_glyph_follows_the_lit_flag():
    """STUB lighting: the square's own `lit` flag decides between the
    room glyph '.' and dark stone ' '."""
    tiles = [[Tile(typ=TerrainType.ROOM) for _ in range(12)]
             for _ in range(8)]
    tiles[4][3] = Tile(typ=TerrainType.ROOM, lit=True)
    w = make_world(map=Map(tiles), hero=make_hero(pos=(2, 4)))
    display.docrt(w)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "."
    assert display.glyph_to_char(w.map.tile_at((4, 4)).glyph) == " "


def test_a_staircase_shows_its_direction():
    """C: back_to_glyph's STAIRS case: '>' down, '<' up."""
    from core.types import STAIR_DOWN, STAIR_UP
    w = _walled_world()
    w.map.tiles[4][3] = Tile(typ=TerrainType.STAIRS, stair_dir=STAIR_DOWN)
    w.map.tiles[3][3] = Tile(typ=TerrainType.STAIRS, stair_dir=STAIR_UP)
    display.docrt(w)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == ">"
    assert display.glyph_to_char(w.map.tile_at((3, 3)).glyph) == "<"


# ------------------------------------------------------------
# Objects and traps are remembered, monsters are not
# ------------------------------------------------------------

def test_an_object_is_remembered_until_it_is_taken():
    """C: map_object() writes the object glyph into levl[].glyph, and
    the next newsym() of the square (once the object is gone) writes
    the background back."""
    w = _walled_world()
    scroll = Item(id="s_0", otype=ObjectType.SCROLL, name="blank paper",
                  oclass=ObjClass.SCROLL.value, pos=(3, 4))
    w.items[scroll.id] = scroll
    display.docrt(w)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "?"

    scroll.pos = None                 # picked up
    scroll.carrier = "player"
    w.hero.inventory.append(scroll)
    display.docrt(w)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "."  # lit floor


def test_a_known_trap_is_part_of_the_memory():
    """C: map_trap() -- a trap the hero has found shows as '^' (and
    stays remembered out of sight); an unfound one shows nothing."""
    w = _walled_world()
    known = Trap(id="t_0", trap_type=TrapType.PIT, pos=(3, 4), seen=True)
    unknown = Trap(id="t_1", trap_type=TrapType.PIT, pos=(4, 4))
    w.traps[known.id] = known
    w.traps[unknown.id] = unknown
    display.docrt(w)
    assert w.map.tile_at((3, 4)).glyph == display.trap_to_glyph(known)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "^"
    assert display.glyph_to_char(w.map.tile_at((4, 4)).glyph) == "."


def test_a_monster_is_visible_only_while_the_hero_can_see_it():
    """C: monsters float above the memory and are never stored in
    levl[].glyph" -- so a monster that steps out of sight vanishes,
    while the terrain it stood on stays."""
    w = _walled_world()
    goblin = make_monster(pos=(3, 4))
    w.actors[goblin.id] = goblin
    display.docrt(w)
    assert display.mon_visible(w, goblin)
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "."

    goblin.pos = (8, 4)               # behind the wall now
    display.docrt(w)
    assert not display.mon_visible(w, goblin)
    assert display.glyph_to_char(w.map.tile_at((8, 4)).glyph) == " "


def test_a_monster_on_another_level_never_ghosts_onto_this_map():
    """The level filter (a monster on a parked level is frozen)."""
    w = _walled_world()
    goblin = make_monster(pos=(3, 4), lev=2)
    w.actors[goblin.id] = goblin
    assert not display.mon_visible(w, goblin)


# ------------------------------------------------------------
# seenv, blindness
# ------------------------------------------------------------

def test_set_seenv_records_the_octant_the_hero_looked_from():
    """C: set_seenv -- the bits say where the *viewer* is, so a hero to
    the west of the square sets the west bit (SV7) and one to the east
    sets SV3; the vector only ever grows."""
    tile = Tile()
    display.set_seenv(tile, (6, 4), (7, 4))       # hero is west of it
    assert tile.seenv == display.SV7
    display.set_seenv(tile, (6, 4), (5, 4))       # hero is east of it
    assert tile.seenv == display.SV7 | display.SV3
    display.set_seenv(tile, (6, 4), (6, 4))       # its own square
    assert tile.seenv == display.SVALL


def test_a_blind_hero_sees_only_what_he_remembers():
    """C: vision.c marks no IN_SIGHT while the hero is blind, so the
    display falls back on the memory: the map does not change, but
    nothing new is recorded either."""
    w = _walled_world()
    display.docrt(w)
    before = [[t.glyph for t in row] for row in w.map.tiles]

    w.hero.blind = 5
    display.docrt(w)
    assert not any(can_see(w, (x, y)) for y in range(w.map.height)
                   for x in range(w.map.width))
    assert [[t.glyph for t in row] for row in w.map.tiles] == before


def test_newsym_is_the_single_square_entry_point():
    """C: newsym(x, y) -- "it is always correct"; the single-tile form
    finds what is on the square by itself (it assumes the view is
    current, as in C, where moveloop recalculates every turn)."""
    w = _walled_world()
    scroll = Item(id="s_0", otype=ObjectType.SCROLL, name="blank paper",
                  oclass=ObjClass.SCROLL.value, pos=(3, 4))
    w.items[scroll.id] = scroll
    vision_recalc(w)
    display.newsym(w, (3, 4))
    assert display.glyph_to_char(w.map.tile_at((3, 4)).glyph) == "?"
    display.newsym(w, (8, 4))          # out of sight: nothing recorded
    assert w.map.tile_at((8, 4)).glyph == GLYPH_UNEXPLORED


def test_object_at_and_trap_at_ignore_other_levels():
    """C's vobj_at() / t_at() read the CURRENT level's chains."""
    w = make_world(map=make_map(), hero=make_hero(pos=(6, 4)))
    here = Item(id="s_0", otype=ObjectType.SCROLL, name="blank paper",
                oclass=ObjClass.SCROLL.value, pos=(3, 4))
    away = Item(id="s_1", otype=ObjectType.SCROLL, name="blank paper",
                oclass=ObjClass.SCROLL.value, pos=(4, 4), lev=2)
    w.items[here.id] = here
    w.items[away.id] = away
    assert display.object_at(w, (3, 4)) is here
    assert display.object_at(w, (4, 4)) is None
    assert display.trap_at(w, (3, 4)) is None
