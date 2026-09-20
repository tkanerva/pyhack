"""Tests for the spell system."""
from core import Direction
from core.spells import cast_spell
from core.types import Item, ObjectType, SpellType
from conftest import SeqRng, make_monster, make_world


def world_with_book(spell_type, monsters=()):
    w = make_world(monsters=monsters)
    book = Item(id="book_0", otype=ObjectType.BOOK, name="Book",
                charges=1, spell_type=spell_type, container="player")
    w.items["book_0"] = book
    w.hero.inventory.append(book)
    return w


def test_beam_hits_first_monster_only():
    """NetHack beams stop at the first hit monster; the monster behind
    is untouched (the old spell.py beam hit everything in range)."""
    w = world_with_book(SpellType.MAGIC_MISSILE, monsters=[
        make_monster(pos=(7, 4)),
        make_monster(kind="orc", pos=(9, 4)),
    ])
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))  # 2d6 = 5
    assert w.actors["goblin_0"].hp == 3
    assert w.actors["orc_0"].hp == 15


def test_wall_stops_beam():
    w = world_with_book(SpellType.MAGIC_MISSILE,
                        monsters=[make_monster(pos=(10, 4))])
    # wall at (x=8, y=4); Map.tiles is indexed as tiles[y][x]
    w.map.tiles[4][8] = 1
    cast_spell(w, "player", "book_0", Direction.E, SeqRng())
    assert w.actors["goblin_0"].hp == 8


def test_sleep_spell():
    w = world_with_book(SpellType.SLEEP, monsters=[make_monster(pos=(8, 4))])
    cast_spell(w, "player", "book_0", Direction.E, SeqRng())
    assert w.actors["goblin_0"].sleeping == 25


def test_healing_spell():
    w = world_with_book(SpellType.HEALING)
    w.hero.hp = 10
    cast_spell(w, "player", "book_0", Direction.E, SeqRng())
    assert w.hero.hp == 22


def test_death_spell_ignored_by_undead():
    w = world_with_book(SpellType.DEATH,
                        monsters=[make_monster(is_undead=True, pos=(8, 4))])
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.actors["goblin_0"].hp == 8


def test_book_consumed_after_last_charge():
    w = world_with_book(SpellType.MAGIC_MISSILE,
                        monsters=[make_monster(pos=(8, 4))])
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.items == {}
