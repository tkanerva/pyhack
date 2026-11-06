"""Tests for the console front-end (ui/console.py render()).

The demo cave's floor items -- the six item classes the demo plays
(wands, scrolls, weapons, armours, spell books, foods) -- and the
hero's spell power (Pw) both have to show up on the rendered screen.

Since the display layer landed (core/display.py) the map half of the
screen is the hero's MEMORY of the level: a square he has never seen is
blank, a wall is only a wall once it was seen, and a monster or an item
shows only while it is in sight.  So the map assertions below ask
core.vision.can_see() which squares they may talk about.
"""
import random
from typing import List

from core.commands import QuaffCommand, WaitCommand
from core.objects import ObjClass
from core.rnd import Rng
from core.types import (DoorMask, Item, ObjectType, PotionType, TerrainType,
                        Tile, World)
from core.vision import can_see
from core.worldgen import MKLEV, new_world
from conftest import make_hero, make_world
from ui import read_command, render

# The floor glyphs of render(), by item class -- the defsym.h
# OBJCLASS table's characters (core.objects.DEF_OC_SYMS), pinned here
# so a wrong transcription of the table fails loudly.
GLYPHS = {
    ObjectType.SCROLL: "?",   # SCROLL_SYM
    ObjectType.WEAPON: ")",   # WEAPON_SYM
    ObjectType.ARMOR: "[",    # ARMOR_SYM
    ObjectType.BOOK: "+",     # SPBOOK_SYM
    ObjectType.WAND: "/",     # WAND_SYM
    ObjectType.FOOD: "%",     # FOOD_SYM
    ObjectType.POTION: "!",   # POTION_SYM
}


def _map_rows(out: str, height: int) -> List[str]:
    """The map rows of the rendered screen: line 0 is the title,
    lines 1-2 the legend, line 3 blank, then the map."""
    return out.splitlines()[4:4 + height]


def _covered(world: World, pos) -> bool:
    """A tile a floor-item glyph must yield to: the hero, a monster
    or a triggered trap share it."""
    return (pos == world.hero.pos
            or world.monster_at(pos) is not None
            or any(t.pos == pos and t.triggered for t in world.traps.values()))


def test_render_shows_every_floor_item_with_its_glyph():
    """Each floor item the hero can see wears its class glyph unless a
    hero / monster / triggered trap shares its tile; an item he cannot
    see is not drawn at all."""
    w = new_world(random.Random(42))
    rows = _map_rows(render(w, []), w.map.height)
    shown = 0
    for it in w.items.values():
        if it.pos is None or it.carrier is not None:
            continue
        x, y = it.pos
        if not can_see(w, it.pos):
            assert rows[y][x] == " ", (it.name, it.pos)
        elif not _covered(w, it.pos):
            assert rows[y][x] == GLYPHS[it.otype], (it.name, it.pos)
            shown += 1
    assert shown > 0


def test_render_shows_all_seven_floor_item_classes():
    """The demo cave carries all seven floor item classes and the
    seed-42 hero sees at least one item of each on his screen."""
    w = new_world(random.Random(42))
    shown = {it.otype for it in w.items.values()
             if it.pos is not None and it.carrier is None
             and can_see(w, it.pos) and not _covered(w, it.pos)}
    assert shown == set(GLYPHS)


def test_render_floor_glyph_follows_pickup():
    """An item on the floor wears its class glyph; picked up (position
    cleared, a carrier set) it vanishes from the floor."""
    w = make_world()
    it = Item(id="s_0", otype=ObjectType.SCROLL, name="blank paper",
              oclass=ObjClass.SCROLL.value, pos=(3, 2))
    w.items[it.id] = it
    assert _map_rows(render(w, []), w.map.height)[2][3] == "?"
    it.pos = None
    it.carrier = "player"
    w.hero.inventory.append(it)
    assert _map_rows(render(w, []), w.map.height)[2][3] == " "


def test_render_status_line_shows_power_points():
    """The status line carries the hero's spell power, Pw uen/uenmax."""
    w = make_world(hero=make_hero(uen=7, uenmax=8))
    assert "⚡ Pw: 7/8" in render(w, [])


def test_read_command_quaff_key(monkeypatch):
    """C's key pair: lowercase q<letter> quaffs a carried potion,
    capital Q quits, a lone q (like a lone z/c) is a wait, and
    q<letter> on a non-potion is a wait."""
    w = make_world()
    pot = Item(id="p_0", otype=ObjectType.POTION, name="healing potion",
               oclass=ObjClass.POTION.value, potion_type=PotionType.HEALING,
               charges=1)
    w.items[pot.id] = pot
    w.hero.inventory.append(pot)
    scroll = Item(id="s_0", otype=ObjectType.SCROLL, name="blank paper",
                  oclass=ObjClass.SCROLL.value)
    w.items[scroll.id] = scroll
    w.hero.inventory.append(scroll)

    def press(key: str):
        monkeypatch.setattr("builtins.input", lambda prompt: key)
        return read_command(w)

    assert press("qa") == QuaffCommand("p_0")
    assert isinstance(press("qb"), WaitCommand)  # a scroll is no potion
    assert isinstance(press("q"), WaitCommand)   # lone q: a wait
    assert press("Q") is None                    # capital Q quits


def test_render_draws_nothing_where_the_hero_has_not_looked():
    """The bug this layer fixes: an unexplored square is blank.  The old
    renderer drew `Tile.typ` for the whole level, and its wall test
    included stone, so every unseen rock square came out as '#' --
    indistinguishable from a corridor the hero had actually seen."""
    w = new_world(random.Random(42))
    rows = _map_rows(render(w, []), w.map.height)
    unseen = [rows[y][x] for y in range(w.map.height)
              for x in range(w.map.width) if not can_see(w, (x, y))]
    assert unseen, "the seed-42 hero does not see the whole level"
    assert set(unseen) == {" "}


def test_render_shows_open_and_closed_doors():
    """C's door glyphs (defsym.h): '+' for a closed door, and for an
    open one '|' in a horizontal (east-west) wall and '-' in a vertical
    one -- the leaf stands across the wall.  (The old renderer used
    "'" for an open door, which no defsym.h symbol has.)"""
    w = make_world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.CLOSED)
    w.map.tiles[3][4] = Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.ISOPEN, horizontal=True)
    w.map.tiles[3][5] = Tile(typ=TerrainType.DOOR,
                             door_mask=DoorMask.ISOPEN)
    rows = _map_rows(render(w, []), w.map.height)
    assert rows[3][3] == "+"
    assert rows[3][4] == "|"
    assert rows[3][5] == "-"


def test_render_shows_a_secret_door_as_a_wall():
    """An undiscovered secret door is part of the wall: it wears the
    wall symbol of its orientation (C: wall_angle's SDOOR case)."""
    w = make_world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.SDOOR,
                             door_mask=DoorMask.LOCKED)
    w.map.tiles[3][4] = Tile(typ=TerrainType.SDOOR,
                             door_mask=DoorMask.LOCKED, horizontal=True)
    rows = _map_rows(render(w, []), w.map.height)
    assert rows[3][3] == "|"
    assert rows[3][4] == "-"


def test_render_shows_corridors_as_hash_and_lit_floor_as_dot():
    """C's map glyphs: a seen corridor is '#', a lit room floor is '.',
    an unlit one stays blank (no light sources yet -- see
    core.display's STUB)."""
    w = make_world()
    w.map.tiles[3][3] = Tile(typ=TerrainType.CORR)
    w.map.tiles[3][4] = Tile(typ=TerrainType.ROOM, lit=True)
    rows = _map_rows(render(w, []), w.map.height)
    assert rows[3][3] == "#"
    assert rows[3][4] == "."
    assert rows[4][4] == " "   # unlit floor


def test_render_a_generated_level_is_all_glyphs():
    """A mklev level renders its defsym.h glyphs: the lit room floor
    around the hero is '.', a seen wall is '|' or '-', a seen corridor
    is '#' -- and every square the hero cannot see is blank (the
    regression test for the unexplored-rock bug)."""
    w = new_world(Rng(b"console:mklev"), generator=MKLEV)
    rows = _map_rows(render(w, []), w.map.height)
    text = "".join(rows)
    assert "." in text and ("|" in text or "-" in text)
    assert len(rows) == w.map.height
    unseen = [rows[y][x] for y in range(w.map.height)
              for x in range(w.map.width) if not can_see(w, (x, y))]
    assert unseen and set(unseen) == {" "}


def test_a_hash_on_the_screen_is_always_a_seen_corridor():
    """The other half of the regression test: '#' is the corridor glyph,
    so a '#' on the screen must be a corridor tile the hero has actually
    looked at -- never bare stone (the old renderer's `typ == CORR or
    is_wall(pos)` test painted every square of rock as '#')."""
    w = new_world(Rng(b"console:mklev"), generator=MKLEV)
    rows = _map_rows(render(w, []), w.map.height)
    hashes = [(x, y) for y in range(w.map.height)
              for x in range(w.map.width) if rows[y][x] == "#"]
    assert hashes, "the hero starts next to a corridor on this seed"
    for pos in hashes:
        assert w.map.tile_at(pos).typ == TerrainType.CORR, pos
        assert can_see(w, pos), pos
