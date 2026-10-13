"""Tests for the spell system."""
from core import Direction
from core.spells import cast_spell
from core.types import Item, ObjectType, SpellType, Tile, TerrainType
from core.vision import set_tile
from conftest import SeqRng, make_monster, make_world


def world_with_book(spell_type, monsters=(), uen=10):
    w = make_world(monsters=monsters)
    w.hero.uen = w.hero.uenmax = uen
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
    # draws: the failure check (2 <= 78), the beam range (3), the damage
    # (1d6 = 5: the level-1 caster's spell power is ulevel/2 + 1 = 1 die)
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3, 5))
    assert w.actors["goblin_0"].hp == 3
    assert w.actors["orc_0"].hp == 15


def test_wall_stops_beam():
    w = world_with_book(SpellType.MAGIC_MISSILE,
                        monsters=[make_monster(pos=(10, 4))])
    # wall at (x=8, y=4): replace the tile and refresh the sight rows
    set_tile(w, (8, 4), Tile(typ=TerrainType.STONE))
    # draws: the failure check (2 <= 78), the beam range (3) -- the beam
    # stops at the wall before reaching the monster
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.actors["goblin_0"].hp == 8


def test_sleep_spell():
    # SLEEP is level 3 -> cost 15 Pw
    w = world_with_book(SpellType.SLEEP,
                        monsters=[make_monster(pos=(8, 4))], uen=15)
    # draws: the failure check (2 <= 74), the beam range (3) -- the sleep
    # ray itself draws nothing (the flat 25 turns)
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.actors["goblin_0"].sleeping == 25


def test_healing_spell():
    w = world_with_book(SpellType.HEALING)
    w.hero.hp = 10
    w.hero.uen = 20
    # draw: only the failure check (2 <= 82) -- the flat healing draws
    # nothing
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2))
    assert w.hero.hp == 22


def test_death_spell_ignored_by_undead():
    # DEATH (finger of death) is level 7 -> cost 35 Pw
    w = world_with_book(SpellType.DEATH,
                        monsters=[make_monster(is_undead=True, pos=(8, 4))],
                        uen=35)
    # draws: the failure check (2 <= 58), the beam range (3) -- the
    # resistance check comes before the damage roll, so a resisted zap
    # draws no dice
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.actors["goblin_0"].hp == 8


def test_book_consumed_after_last_charge():
    w = world_with_book(SpellType.MAGIC_MISSILE,
                        monsters=[make_monster(pos=(8, 4))])
    # draws: the failure check (2 <= 78), the beam range (3), the damage
    # (1d6 = 5)
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3, 5))
    assert w.items == {}


# ------------------------------------------------------------
# Energy system integration (Phase 3)
# ------------------------------------------------------------

def test_cast_spell_drains_energy():
    """Casting a spell drains the appropriate Pw from the caster."""
    # MAGIC_MISSILE is level 2 -> cost 10
    w = world_with_book(SpellType.MAGIC_MISSILE, uen=15)
    # draws: the failure check (2 <= 78), the beam range (3) -- no monster
    # in the line, the beam goes astray and draws no dice
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.hero.uen == 5  # 15 - 10 = 5


def test_cast_high_level_spell_drains_more():
    """Higher level spells cost more Pw."""
    # POLYMORPH is level 6 -> cost 30
    w = world_with_book(SpellType.POLYMORPH, uen=35)
    # draws: the failure check (2 <= 62), the beam range (3) -- no monster
    # in the line, the beam goes astray
    cast_spell(w, "player", "book_0", Direction.E, SeqRng(2, 3))
    assert w.hero.uen == 5  # 35 - 30 = 5


def test_cast_fails_without_enough_energy():
    """Casting fails with a message if the caster lacks Pw."""
    # FIREBALL is level 4 -> cost 20
    w = world_with_book(SpellType.FIREBALL, uen=19)  # not enough
    ev = cast_spell(w, "player", "book_0", Direction.E, SeqRng())
    assert len(ev) == 1
    assert "enough energy" in ev[0].text
    assert w.hero.uen == 19  # energy unchanged


def test_cast_fails_when_energy_at_zero():
    """A caster with zero energy cannot cast spells."""
    w = world_with_book(SpellType.MAGIC_MISSILE, uen=0)
    ev = cast_spell(w, "player", "book_0", Direction.E, SeqRng())
    assert len(ev) == 1
    assert "enough energy" in ev[0].text
