"""Tests for the console front-end (ui/console.py render()).

The demo cave's floor items -- the five item classes the demo plays
(wands, scrolls, weapons, armours, spell books) -- and the hero's
spell power (Pw) both have to show up on the rendered screen.
"""
import random
from typing import List

from core.objects import ObjClass
from core.types import Item, ObjectType, World
from core.worldgen import new_world
from conftest import make_hero, make_world
from ui import render

# The floor glyphs of render(), by item class -- the defsym.h
# OBJCLASS table's characters (core.objects.DEF_OC_SYMS), pinned here
# so a wrong transcription of the table fails loudly.
GLYPHS = {
    ObjectType.SCROLL: "?",   # SCROLL_SYM
    ObjectType.WEAPON: ")",   # WEAPON_SYM
    ObjectType.ARMOR: "[",    # ARMOR_SYM
    ObjectType.BOOK: "+",     # SPBOOK_SYM
    ObjectType.WAND: "/",     # WAND_SYM
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
    """Each floor item of the seed-42 cave wears its class glyph
    unless a hero / monster / triggered trap shares its tile."""
    w = new_world(random.Random(42))
    rows = _map_rows(render(w, []), w.map.height)
    for it in w.items.values():
        if it.pos is None or it.container is not None:
            continue
        x, y = it.pos
        if not _covered(w, it.pos):
            assert rows[y][x] == GLYPHS[it.otype], (it.name, it.pos)


def test_render_shows_all_five_floor_item_classes():
    """The demo cave carries all five floor item classes and every one
    is visible on the seed-42 screen."""
    w = new_world(random.Random(42))
    rows = _map_rows(render(w, []), w.map.height)
    shown = {it.otype for it in w.items.values()
             if it.pos is not None and it.container is None
             and not _covered(w, it.pos)}
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
    it.container = "player"
    w.hero.inventory.append(it)
    assert _map_rows(render(w, []), w.map.height)[2][3] == " "


def test_render_status_line_shows_power_points():
    """The status line carries the hero's spell power, Pw uen/uenmax."""
    w = make_world(hero=make_hero(uen=7, uenmax=8))
    assert "⚡ Pw: 7/8" in render(w, [])

