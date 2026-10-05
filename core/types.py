"""Core value types: map, entities, items, traps, and shared enums.

Everything in this module is plain data.  There is no I/O and no
gameplay logic here -- behaviour lives in core.rules, core.step and the
system modules (traps, zap, potions, spells, vision).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag, auto
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # annotation only -- no runtime import cycle
    from .monst import PerMonst
    from .objects import Prop
    from .vision import HeroVision
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
# Map (C: levl[][] of struct rm, rm.h)
# ============================================================
#
# The dungeon is a rectangular grid of Tile -- one per level location,
# the port of C's levl[x][y] (struct rm).  pyhack keeps the row-major
# indexing it has always used (tiles[y][x], y = row), exactly like the
# (y,x) convention C's vision code works in.
#
# TerrainType keeps the C levl_typ_types VALUES, not auto numbers: the
# IS_* predicates below are range comparisons, just like the C macros,
# and must stay in the same order.
#
# Level *generation* is still the small demo generator (core/worldgen);
# the full mklev.c (rooms + corridors + doors + furniture) will later
# be ported onto this same grid.  Until then the demo level is: STONE
# boundary ring, ROOM floor, a few scattered STONE obstacles.

class TerrainType(IntEnum):
    """Level location types (C: levl_typ_types, rm.h)."""
    STONE = 0
    VWALL = 1
    HWALL = 2
    TLCORNER = 3
    TRCORNER = 4
    BLCORNER = 5
    BRCORNER = 6
    CROSSWALL = 7
    TUWALL = 8
    TDWALL = 9
    TLWALL = 10
    TRWALL = 11
    DBWALL = 12
    TREE = 13
    SDOOR = 14
    SCORR = 15
    POOL = 16
    MOAT = 17
    WATER = 18
    DRAWBRIDGE_UP = 19
    LAVAPOOL = 20
    LAVAWALL = 21
    IRONBARS = 22
    DOOR = 23
    CORR = 24
    ROOM = 25
    STAIRS = 26
    LADDER = 27
    FOUNTAIN = 28
    THRONE = 29
    SINK = 30
    GRAVE = 31
    ALTAR = 32
    ICE = 33
    DRAWBRIDGE_DOWN = 34
    AIR = 35
    CLOUD = 36
    # C also has MAX_TYPE = 37, MATCH_WALL = 38 (special levels) and the
    # xFLOOR..xSEA feedback indices (39..46) -- not tile types; they
    # come with the work that needs them.


class DoorMask(IntFlag):
    """Door state bits (C: rm.flags doormask overloads, rm.h)."""
    BROKEN = 0x1     # D_BROKEN
    ISOPEN = 0x2     # D_ISOPEN
    CLOSED = 0x4     # D_CLOSED
    LOCKED = 0x8     # D_LOCKED
    TRAPPED = 0x10   # D_TRAPPED


def is_wall(typ: TerrainType) -> bool:
    """C: IS_WALL -- a wall type (VWALL..DBWALL), stone excluded."""
    return typ != TerrainType.STONE and typ <= TerrainType.DBWALL


def is_stwall(typ: TerrainType) -> bool:
    """C: IS_STWALL -- stone or a wall type (STONE..DBWALL)."""
    return typ <= TerrainType.DBWALL


def is_obstructed(typ: TerrainType) -> bool:
    """C: IS_OBSTRUCTED -- absolutely non-accessible terrain
    (STONE..SCORR)."""
    return typ < TerrainType.POOL


def is_door(typ: TerrainType) -> bool:
    """C: IS_DOOR."""
    return typ == TerrainType.DOOR


def is_sdoor(typ: TerrainType) -> bool:
    """C: IS_SDOOR.  A secret door is part of the wall (IS_OBSTRUCTED),
    so it is never a position you can stand on."""
    return typ == TerrainType.SDOOR


def is_tree(typ: TerrainType) -> bool:
    """C: IS_TREE -- trees (and stone on arboreal levels; STUB: no
    arboreal levels yet)."""
    return typ == TerrainType.TREE


def accessible(typ: TerrainType) -> bool:
    """C: ACCESSIBLE -- a good position (DOOR and up)."""
    return typ >= TerrainType.DOOR


def is_pool(typ: TerrainType) -> bool:
    """C: IS_POOL."""
    return TerrainType.POOL <= typ <= TerrainType.DRAWBRIDGE_UP


@dataclass
class Tile:
    """One level location (C: struct rm, reduced).

    STUB: the remaining rm fields (glyph, seenv, lit, waslit, roomno,
    edge, candig) are not ported yet -- they come with the display
    (glyph/seenv), lighting (lit/waslit) and room-aware (roomno/edge)
    work.  door_mask is only meaningful for DOOR/SDOOR tiles.
    """
    typ: TerrainType = TerrainType.ROOM
    door_mask: DoorMask = DoorMask(0)

    def is_door_open(self) -> bool:
        """A door is passable unless closed/locked/trapped (C: the
        doormask tests in does_block() and the movement code)."""
        return not (self.door_mask
                    & (DoorMask.CLOSED | DoorMask.LOCKED | DoorMask.TRAPPED))


class Map:
    """Rectangular tile grid: tiles[y][x] is a Tile (C: levl[x][y]).

    Also owns the level-local sight data of core/vision.py (viz_clear
    + the left/right pointer rows).  It stays None until vision_init() /
    vision_reset() have run: new_world() does that, and a bare World
    built by tests is set up lazily on first vision use.
    """

    def __init__(self, tiles: List[List[Tile]]):
        self.tiles = tiles
        # C: viz_clear[], left_ptrs[], right_ptrs[] (vision.c)
        self.viz_clear: Optional[List[List[bool]]] = None
        self.left_ptrs: Optional[List[List[int]]] = None
        self.right_ptrs: Optional[List[List[int]]] = None

    @property
    def width(self) -> int:
        return len(self.tiles[0])

    @property
    def height(self) -> int:
        return len(self.tiles)

    def in_bounds(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def tile_at(self, pos: Pos) -> Tile:
        return self.tiles[pos[1]][pos[0]]

    def is_wall(self, pos: Pos) -> bool:
        """Stone or wall at pos (the old 0/1 grid: 1 meant this)."""
        return is_stwall(self.tile_at(pos).typ)

    def is_walkable(self, pos: Pos) -> bool:
        """A good position: in bounds, accessible terrain, and (for a
        door) not closed/locked.  STUB: NetHack also lets you wade into
        pools, step onto ice, etc. -- that comes with the water work."""
        if not self.in_bounds(pos):
            return False
        tile = self.tile_at(pos)
        if not accessible(tile.typ):
            return False
        if is_door(tile.typ):
            return tile.is_door_open()
        return True

    def floor_tiles(self) -> List[Pos]:
        """All walkable positions (spawns, teleports)."""
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.is_walkable((x, y))
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
    # worn state (C: obj->owornmask, prop.h bitmask): the W_* slot bits
    # this item currently occupies (0 = not worn).  The slot occupant is
    # found by scanning the carrier's inventory (core.worn.which_armor /
    # setworn) -- one mechanism for hero and future monsters.
    owornmask: int = 0
    # greased (C: obj->greased): the item is coated with oil.  A greased
    # worn cloak / suit / shirt (or the helmet, against brain drain) sheds
    # hug / wrap attacks (core.mhitu.u_slip_free), and the grease wears off
    # 1/2 of the time it protects.
    greased: bool = False


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
    ac: int                    # BASE (body) armor class (C: mons[].ac).
    # The effective AC is computed, never cached: core.worn.uac()
    # subtracts the worn gear (the find_ac computation, PLAN-ARMOR.md).
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
    # intrinsic properties (C: the u.uprops[] inherent / temp half,
    # mprops for monsters): the Prop set held without gear (species,
    # spells, potions).  The worn-gear contribution is computed, never
    # stored (core.props.worn_properties / has_property).
    intrinsics: "set[Prop]" = field(default_factory=set)


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
    # the hero's current view (C: gv.viz_array + gv.viz_rmin/rmax);
    # built by core.vision (vision_recalc), None until first use
    vision: Optional["HeroVision"] = None

    @property
    def hero(self) -> Monster:
        return self.actors["player"]

    def monster_at(self, pos: Pos) -> Optional[Monster]:
        """First living actor standing on `pos`, if any."""
        for m in self.actors.values():
            if m.alive and m.pos == pos:
                return m
        return None

    def items_at(self, pos: Pos) -> List[Item]:
        """Items lying on `pos` (C: the svl.level.objects[x][y] chain)."""
        return [it for it in self.items.values() if it.pos == pos]
