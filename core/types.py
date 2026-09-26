"""Core value types: map, entities, items, traps, and shared enums.

Everything in this module is plain data.  There is no I/O and no
gameplay logic here -- behaviour lives in core.rules, core.step and the
system modules (traps, zap, potions, spells).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # annotation only -- no runtime import cycle
    from .monst import PerMonst
    from .weapon import Skills

Pos = Tuple[int, int]


# ============================================================
# Enums (single home for all of them -- previously duplicated across
# contracts.py, trap.py and zap.py)
# ============================================================

class TrapType(Enum):
    PIT = auto()
    SPIKED_PIT = auto()
    TRAPDOOR = auto()
    ARROW_TRAP = auto()
    DART_TRAP = auto()
    FIRE_TRAP = auto()
    SLEEPING_GAS = auto()
    TELEPORTATION = auto()
    ANTI_MAGIC = auto()
    WEB = auto()
    ROLLING_BOULDER = auto()
    MAGIC_PORTAL = auto()
    LEVEL_TELEPORTER = auto()
    STAIRS_DOWN = auto()
    STAIRS_UP = auto()


class DamageType(Enum):
    MELEE = auto()          # new: plain physical damage (resisted by nobody)
    MAGIC_MISSILE = auto()
    FIRE = auto()
    COLD = auto()
    SLEEP = auto()
    DEATH = auto()
    LIGHTNING = auto()
    POISON = auto()
    ACID = auto()
    CANCELLATION = auto()


class ObjectType(Enum):
    WAND = auto()
    SCROLL = auto()
    POTION = auto()
    WEAPON = auto()
    ARMOR = auto()
    TOOL = auto()
    FOOD = auto()
    CORPSE = auto()
    EGG = auto()
    STATUE = auto()
    RING = auto()
    AMULET = auto()
    GEM = auto()
    BOULDER = auto()
    BOOK = auto()


class WandType(Enum):
    STRIKING = auto()
    CANCELLATION = auto()
    TELEPORTATION = auto()
    MAKE_INVISIBLE = auto()
    POLYMORPH = auto()
    SLEEP = auto()
    SLOW_MONSTER = auto()
    SPEED_MONSTER = auto()
    UNDEAD_TURNING = auto()
    OPENING = auto()
    LOCKING = auto()
    PROBING = auto()
    FIRE = auto()
    COLD = auto()
    LIGHTNING = auto()
    DEATH = auto()
    DIGGING = auto()
    NOTHING = auto()


class PotionType(Enum):
    HEALING = auto()
    CONFUSION = auto()
    POLYMORPH = auto()
    SLEEPING_SICKNESS = auto()
    CANCELLATION = auto()
    INCREASE_AC = auto()


class SpellType(Enum):
    MAGIC_MISSILE = auto()
    FIREBALL = auto()
    CONE_OF_COLD = auto()
    LIGHTNING = auto()
    SLEEP = auto()
    DEATH = auto()
    POLYMORPH = auto()
    CANCELLATION = auto()
    TELEPORT = auto()
    HEALING = auto()


class Direction(Enum):
    N = (0, -1)
    S = (0, 1)
    E = (1, 0)
    W = (-1, 0)
    NE = (1, -1)
    NW = (-1, -1)
    SE = (1, 1)
    SW = (-1, 1)

    @property
    def delta(self) -> Pos:
        return self.value


# ============================================================
# Map
# ============================================================

class Map:
    """Rectangular tile grid.  0 = floor, 1 = wall (old convention kept)."""

    def __init__(self, tiles: List[List[int]]):
        self.tiles = tiles

    @property
    def width(self) -> int:
        return len(self.tiles[0])

    @property
    def height(self) -> int:
        return len(self.tiles)

    def in_bounds(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def is_wall(self, pos: Pos) -> bool:
        return self.tiles[pos[1]][pos[0]] == 1

    def is_walkable(self, pos: Pos) -> bool:
        return self.in_bounds(pos) and not self.is_wall(pos)

    def floor_tiles(self) -> List[Pos]:
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.tiles[y][x] == 0
        ]


# ============================================================
# Items
# ============================================================

@dataclass
class Item:
    id: str
    otype: ObjectType
    name: str
    charges: int = 1
    blessed: bool = False
    cursed: bool = False
    pos: Optional[Pos] = None          # where it lies on the floor, if anywhere
    container: Optional[str] = None    # id of the monster carrying it, if any
    wand_type: Optional[WandType] = None
    potion_type: Optional[PotionType] = None
    spell_type: Optional[SpellType] = None
    # fine object identity (C: struct obj's otyp / oclass / spe): the
    # coarse `otype` above stays the class-level tag; these carry the
    # exact core.objects.OBJECTS row (0 = "not fine").  An Item with
    # them set is directly ObjLike-compatible for core.weapon (it has
    # otyp / oclass / spe / blessed).
    otyp: int = 0
    oclass: int = 0
    spe: int = 0


# ============================================================
# Monsters (the hero is just a monster with is_hero=True)
# ============================================================

@dataclass
class Monster:
    id: str
    name: str
    pos: Pos
    hp: int
    max_hp: int
    ac: int
    damage: int = 2            # melee damage = 1d`damage`
    alive: bool = True
    is_hero: bool = False
    mdata: Optional["PerMonst"] = None  # permonst type (C: mtmp->data);
    # None for the flat-stat demo monsters (they use the simple melee
    # path); set for monsters that go through the C-port systems
    # (mhitu, ...)
    sleeping: int = 0          # turns of sleep remaining
    stuck: int = 0             # turns of stuck remaining (web / pit)
    poisoned: int = 0          # turns of poison remaining
    confused: int = 0          # turns of confusion remaining
    blind: int = 0             # turns of blindness remaining
    hallucinating: int = 0     # turns of hallucination remaining
    is_undead: bool = False
    is_demon: bool = False
    is_golem: bool = False
    is_nonliving: bool = False
    is_flying: bool = False
    inventory: List[Item] = field(default_factory=list)
    # hero combat state (the demo's weapon subset; see core.uhitm and
    # core.weapon): the hero wields a starting weapon, and its fixed
    # abilities feed the to-hit / damage bonuses
    wielded: Optional[str] = None    # id of the wielded item (C: uwep)
    ulevel: int = 1                  # hero level (fixed in the demo)
    ustr: int = 12                   # strength (fixed; no STR18)
    udex: int = 12                   # dexterity (neutral: no bonus swing)
    skills: Optional["Skills"] = None  # per-hero weapon-skill state


# ============================================================
# Traps
# ============================================================

@dataclass
class Trap:
    id: str
    trap_type: TrapType
    pos: Pos
    triggered: bool = False
    disarmed: bool = False
    seen: bool = False


# ============================================================
# World -- the single state object
# ============================================================

@dataclass
class World:
    map: Map
    actors: "dict[str, Monster]" = field(default_factory=dict)
    traps: "dict[str, Trap]" = field(default_factory=dict)
    items: "dict[str, Item]" = field(default_factory=dict)
    turn: int = 0
    over: bool = False

    @property
    def hero(self) -> Monster:
        return self.actors["player"]

    def monster_at(self, pos: Pos) -> Optional[Monster]:
        """First living actor standing on `pos`, if any."""
        for m in self.actors.values():
            if m.alive and m.pos == pos:
                return m
        return None
