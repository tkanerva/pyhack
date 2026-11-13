"""Core value types: map, entities, items, traps, and shared enums.

Everything in this module is plain data.  There is no I/O and no
gameplay logic here -- behaviour lives in core.rules, core.step and the
system modules (traps, zap, potions, spells, vision).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag, auto
from typing import TYPE_CHECKING, List, Optional, Tuple

from .glyph import GLYPH_UNEXPLORED
from .o_init import ObjTables
from .mondata import MonState
from .monst_defs import A_NEUTRAL
from .rnd import Rng

if TYPE_CHECKING:  # annotation only -- no runtime import cycle
    from .monst import PerMonst
    from .objects import Prop
    from .occupation import Occupation
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
    # C has no TT_STAIRS: stairs are STAIRS TERRAIN (Tile.typ +
    # Tile.stair_dir, PLAN-STAIRS.md decision 1) -- the old
    # STAIRS_DOWN / STAIRS_UP placeholders were the last two members
    # and are removed by the stairs port (no value shift).


class DamageType(Enum):
    MELEE = auto()  # new: plain physical damage (resisted by nobody)
    MAGIC_MISSILE = auto()
    FIRE = auto()
    COLD = auto()
    SLEEP = auto()
    DEATH = auto()
    LIGHTNING = auto()
    POISON = auto()
    ACID = auto()
    CANCELLATION = auto()
    STARVING = (
        auto()
    )  # new: C done(STARVING) / done(CHOKING) killers ("starvation" / "Choked on ..."); DeathEvent.by keeps them distinct


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
    # a pile of gold (added with the object genesis: mkobj.mkgold makes
    # them by the hundred, and a coin pile is the one class the demo kit
    # never had)
    COIN = auto()


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


class ScrollType(Enum):
    """C: the SCR_* scroll types (objects.h).  All 22 types a non-MAIL
    build knows; the effects pyhack implements are the five in the
    core.scrolls docstring (blank paper, enchant weapon, enchant
    armor, remove curse, teleportation) -- the rest are STUBs that
    raise NotImplementedError until their machinery is ported.
    SCR_MAIL is compiled out, as in core.objects."""

    ENCHANT_ARMOR = auto()
    DESTROY_ARMOR = auto()
    CONFUSE_MONSTER = auto()
    SCARE_MONSTER = auto()
    REMOVE_CURSE = auto()
    ENCHANT_WEAPON = auto()
    CREATE_MONSTER = auto()
    TAMING = auto()
    GENOCIDE = auto()
    LIGHT = auto()
    TELEPORTATION = auto()
    GOLD_DETECTION = auto()
    FOOD_DETECTION = auto()
    IDENTIFY = auto()
    MAGIC_MAPPING = auto()
    AMNESIA = auto()
    FIRE = auto()
    EARTH = auto()
    PUNISHMENT = auto()
    CHARGING = auto()
    STINKING_CLOUD = auto()
    BLANK_PAPER = auto()


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


class HungerState(IntEnum):
    """C: the hunger_state_types enum (include/hack.h, values kept
    exactly) -- the hero's hunger state `u.uhs`, computed by the
    thresholds in core.hunger.newuhs (src/eat.c) and shown on the
    status line (the HU_STAT texts, C botl.c)."""

    SATIATED = 0
    NOT_HUNGRY = 1
    HUNGRY = 2
    WEAK = 3
    FAINTING = 4
    FAINTED = 5
    STARVED = 6


class ZapEffect(Enum):
    """C: the shared zap effect ids -- the registry keys of the zap
    port (core.zap.ZAP_EFFECTS).

    In C NetHack, wands and spells share their effect code through one
    intermediate object: spelleffects() (src/spell.c) builds a temporary
    "pseudo" spellbook object (mksobj(spellid), quan 20 so useup() leaves
    it alone) and hands it to the SAME weffects() (src/zap.c) that dozap()
    uses for wands; weffects() then dispatches on the object type --
    bhitm()'s switch (WAN_STRIKING falls through into SPE_FORCE_BOLT: the
    wand of striking and the force bolt spell run ONE code path) and the
    dobuzz()/zhitm() damage switch for the ray wands and the zap spells.

    pyhack keeps that structure without the pseudo-object trick: this
    enum is the key space (C's zno / ZT_* damage types + the bhitm otyp
    cases) both WandType and SpellType map into, and core.zap.ZAP_EFFECTS
    maps each key to the one effect function wands and spells both call.
    The unported C zaps (opening, locking, probing, slow, speed, make
    invisible, light, ...) are absent by design: each lands with the
    machinery it needs (doors, monster speed, invisibility, ...).
    """

    FIRE = auto()  # C: ZT_FIRE (WAN_FIRE; no C spell -- fireball is area)
    COLD = auto()  # C: ZT_COLD (WAN_COLD + SPE_CONE_OF_COLD)
    LIGHTNING = auto()  # C: ZT_LIGHTNING (WAN_LIGHTNING + the 3.x lightning spell)
    MAGIC = auto()  # C: ZT_MAGIC_MISSILE (SPE_MAGIC_MISSILE + WAN_MAGIC_MISSILE)
    STRIKING = auto()  # C: bhitm WAN_STRIKING -> SPE_FORCE_BOLT (zap_punch, d(2,12))
    SLEEP = auto()  # C: ZT_SLEEP (WAN_SLEEP + SPE_SLEEP)
    DEATH = auto()  # C: ZT_DEATH (WAN_DEATH + SPE_FINGER_OF_DEATH)
    POLYMORPH = auto()  # C: bhitm WAN_POLYMORPH + SPE_POLYMORPH
    CANCELLATION = auto()  # C: bhitm WAN_CANCELLATION + SPE_CANCELLATION
    TELEPORT = auto()  # C: bhitm WAN_TELEPORTATION + SPE_TELEPORT_AWAY
    UNDEAD_TURNING = auto()  # C: bhitm WAN_UNDEAD_TURNING + SPE_TURN_UNDEAD


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
# The makemon() / goodpos() flag space (C: include/hack.h)
# ============================================================
#
# C keeps the MM_* flags that steer makemon() and the GP_* flags that
# steer goodpos() in ONE `mmflags_nht` bit space (hack.h) -- makemon
# simply passes a few of its own bits straight through.  The space is
# part of the model here too: core.makemon and core.place both read it,
# and neither owns it.  The C names are kept as module aliases so a call
# site reads like the C it came from.


class MmFlags(IntFlag):
    """Monster-creation / placement flags (C: the MM_* and GP_* bits)."""

    NO_MINVENT = 0x00000001  # suppress minvent when creating
    NOWAIT = 0x00000002  # don't set STRAT_WAITMASK flags
    NOCOUNTBIRTH = 0x00000004  # don't incr the born count (revival)
    IGNOREWATER = 0x00000008  # ignore water when positioning
    ADJACENTOK = 0x00000010  # an adjacent square is good enough
    ANGRY = 0x00000020  # created angry
    NONAME = 0x00000040  # not christened
    EGD = 0x00000080  # add egd structure
    EPRI = 0x00000100  # add epri structure
    ESHK = 0x00000200  # add eshk structure
    EMIN = 0x00000400  # add emin structure
    EDOG = 0x00000800  # add edog structure
    ASLEEP = 0x00001000  # generated asleep
    NOGRP = 0x00002000  # suppress monster groups
    NOTAIL = 0x00004000  # a long worm gets no tail
    MALE = 0x00008000  # male variation
    FEMALE = 0x00010000  # female variation
    NOMSG = 0x00020000  # no appear message
    NOEXCLAM = 0x00040000  # sedate "appears." message
    IGNORELAVA = 0x00080000  # ignore lava when positioning
    MINVIS = 0x00100000  # invisible (wizard mode)
    ALLOW_XY = 0x00200000  # GP_: enexto() may answer <x,y> itself
    ALLOW_U = 0x00400000  # GP_: don't reject the hero's square
    CHECKSCARY = 0x00800000  # GP_: check onscary()
    AVOID_MONPOS = 0x01000000  # GP_: never share a square with a monster


NO_MM_FLAGS = MmFlags(0)

MM_NOWAIT = MmFlags.NOWAIT
MM_NOCOUNTBIRTH = MmFlags.NOCOUNTBIRTH
MM_IGNOREWATER = MmFlags.IGNOREWATER
MM_ADJACENTOK = MmFlags.ADJACENTOK
MM_ANGRY = MmFlags.ANGRY
MM_ASLEEP = MmFlags.ASLEEP
MM_NOGRP = MmFlags.NOGRP
MM_NOTAIL = MmFlags.NOTAIL
MM_MALE = MmFlags.MALE
MM_FEMALE = MmFlags.FEMALE
MM_NOMSG = MmFlags.NOMSG
MM_IGNORELAVA = MmFlags.IGNORELAVA

NO_MINVENT = MmFlags.NO_MINVENT

# the goodpos() half (C: the GP_* bits)
GP_ALLOW_XY = MmFlags.ALLOW_XY
GP_ALLOW_U = MmFlags.ALLOW_U
GP_CHECKSCARY = MmFlags.CHECKSCARY
GP_AVOID_MONPOS = MmFlags.AVOID_MONPOS


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

    BROKEN = 0x1  # D_BROKEN
    ISOPEN = 0x2  # D_ISOPEN
    CLOSED = 0x4  # D_CLOSED
    LOCKED = 0x8  # D_LOCKED
    TRAPPED = 0x10  # D_TRAPPED


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


def is_room(typ: TerrainType) -> bool:
    """C: IS_ROOM -- ROOM, STAIRS, furniture ... (everything from ROOM
    up; a DOOR or a CORR is *not* a room square)."""
    return typ >= TerrainType.ROOM


def space_pos(typ: TerrainType) -> bool:
    """C: SPACE_POS -- a square a monster can be placed on (everything
    strictly above DOOR: ROOM, CORR, ICE, ...)."""
    return typ > TerrainType.DOOR


def is_furniture(typ: TerrainType) -> bool:
    """C: IS_FURNITURE -- STAIRS..ALTAR (fountain, throne, sink, grave,
    altar)."""
    return TerrainType.STAIRS <= typ <= TerrainType.ALTAR


def is_throne(typ: TerrainType) -> bool:
    """C: IS_THRONE."""
    return typ == TerrainType.THRONE


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


def is_lava(typ: TerrainType) -> bool:
    """C: IS_LAVA -- a lava pool (LAVAPOOL is *not* a pool: C's IS_POOL
    stops at DRAWBRIDGE_UP, which is why the two are separate tests)."""
    return typ in (TerrainType.LAVAPOOL, TerrainType.LAVAWALL)


# C: rm.h -- the levl[x][y].ladder mask of a STAIRS tile: which way
# the staircase goes.  A STAIRS tile with stair_dir == 0 is a bug;
# worldgen always sets it (PLAN-STAIRS.md decision 1).
STAIR_UP = 1  # C: LA_UP
STAIR_DOWN = 2  # C: LA_DOWN


# ============================================================
# Rooms (C: include/mkroom.h)
# ============================================================
#
# A level keeps its room records next to its tiles (Map.rooms, C:
# svr.rooms[]), because the rooms are part of the level: they are
# parked with the Map in World.levels when the hero leaves
# (PLAN-STAIRS.md decision 3).  Tile.roomno is the back-pointer (C:
# the 6-bit rm.roomno bitfield), and the three magic values below are
# the C NO_ROOM / SHARED / ROOMOFFSET exactly as mkroom.h spells them.

NO_ROOM = 0  # C: NO_ROOM -- no room owns this square
SHARED = 1  # C: SHARED -- a boundary square two rooms share
ROOMOFFSET = 3  # roomno - ROOMOFFSET == the Map.rooms[] index

MAXNROFROOMS = 40  # C: global.h
MAX_SUBROOMS = 24  # C: global.h


class RoomType(IntEnum):
    """Room types (C: mkroom.h roomtype_types, values kept exactly).

    SHOPBASE is the first shop type; the individual shop types
    (ARMORSHOP .. CANDLESHOP) only matter to the shop work (shk.c /
    shknam.c), which is not ported -- the demo generator never makes
    one (core.mkroom.do_mkroom is a STUB there).
    """

    OROOM = 0  # ordinary room
    THEMEROOM = 1  # like OROOM, but never converted to a special room
    COURT = 2  # contains a throne
    SWAMP = 3  # contains pools
    VAULT = 4  # detached room, usually reached by teleport
    BEEHIVE = 5  # killer bees and royal jelly
    MORGUE = 6  # corpses, undead, graves
    BARRACKS = 7  # soldiers and their gear
    ZOO = 8  # floor covered with treasure and monsters
    DELPHI = 9  # the Oracle and peripherals
    TEMPLE = 10  # a shrine (altar attended by a priest[ess])
    LEPREHALL = 11  # leprechaun hall
    COCKNEST = 12  # cockatrice nest
    ANTHOLE = 13  # ants
    SHOPBASE = 14  # everything from here up is a shop
    ARMORSHOP = 15
    SCROLLSHOP = 16
    POTIONSHOP = 17
    WEAPONSHOP = 18
    FOODSHOP = 19
    RINGSHOP = 20
    WANDSHOP = 21
    TOOLSHOP = 22
    BOOKSHOP = 23
    FODDERSHOP = 24
    CANDLESHOP = 25


# C: mkroom.h -- the two special arguments of search_special().
ANY_TYPE = -1
ANY_SHOP = -2

# C: mkroom.h -- the needfill values (struct mkroom.needfill).
FILL_NONE = 0  # do not fill this room with anything
FILL_NORMAL = 1  # fill it normally (see fill_special_room / fill_ordinary_room)


@dataclass(eq=False)
class Room:
    """One room record (C: struct mkroom, mkroom.h).

    Identity comparison only (``eq=False``): a room is a mutable piece
    of level state and Map.room_of() / Map.rooms.index() must find
    *this* room, not the first one with the same geometry.

    Geometry is inclusive: the room's *floor* runs lx..hx by ly..hy;
    the wall ring sits one square outside it (C: do_room_or_subroom).

    Deviations from the C struct, documented not accidental:

    - ``doors`` is a list of positions instead of C's
      ``doorct``/``fdoor`` slice of one level-wide ``svd.doors[]``
      array.  C shifts that array on every insertion to keep each
      room's slice contiguous; a per-room list is the same
      information without the shifting.  ``doorct`` and ``fdoor``
      remain available as read-only readings of it.
    - ``sbrooms`` holds *indices* into ``Map.subrooms`` instead of
      pointers (the pyhack rule: no object graphs inside the World).
    - ``needfill`` (mkroom.h) is carried, per PLAN-SPECIAL-ROOMS.md
      phase 2: ``mkzoo`` (and later the shop and the vault) set
      FILL_NORMAL so ``fill_special_room`` stocks the room at the end
      of makelevel; the temple sets none (C's mktemple stocks inline,
      so fill_special_room only carries its flag).  do_room_or_subroom
      resets it, because a room object is re-used on regeneration and
      a stale FILL_NORMAL would re-stock a stale room.
    """

    lx: int
    ly: int
    hx: int
    hy: int
    rtype: RoomType = RoomType.OROOM
    # C: orig_rtype -- rtype is zeroed once some room types have been
    # entered; the original value is kept here (mklev's
    # level_finalize_topology copies it).
    orig_rtype: RoomType = RoomType.OROOM
    rlit: bool = False
    needjoining: bool = True
    irregular: bool = False
    roomnoidx: int = 0
    doors: List[Pos] = field(default_factory=list)
    sbrooms: List[int] = field(default_factory=list)
    needfill: int = FILL_NONE
    # C: sroom->resident -- the monster that "lives" in this room, the
    # shopkeeper for a shop (PLAN-SPECIAL-ROOMS.md §2.9).  pyhack holds
    # the monster's id, not a pointer (the "no object graphs inside the
    # World" rule); core.shk.shop_keeper resolves it.  It is on the room
    # rather than only on the eshk extra so a revisited level (the Map
    # is parked in World.levels) still knows whose shop this is without
    # scanning the monster list.
    resident: Optional[str] = None

    # --- C-compatible readings of the door bookkeeping ---
    @property
    def doorct(self) -> int:
        """C: sroom->doorct."""
        return len(self.doors)

    @property
    def nsubrooms(self) -> int:
        """C: sroom->nsubrooms."""
        return len(self.sbrooms)

    def contains(self, pos: Pos) -> bool:
        """The room's floor rectangle, boundary walls excluded (C: the
        lowx..hix / lowy..hiy test; irregular rooms need Map-side
        roomno lookups instead, see core.mkroom.inside_room)."""
        x, y = pos
        return self.lx <= x <= self.hx and self.ly <= y <= self.hy


@dataclass
class LevelFlags:
    """The level-wide flags of C's ``svl.level.flags`` (struct level_flags,
    decl.h), reduced to the ones the ported generators and systems set.
    """

    nfountains: int = 0
    nsinks: int = 0
    has_shop: bool = False
    has_vault: bool = False
    has_zoo: bool = False
    has_court: bool = False
    has_morgue: bool = False
    graveyard: bool = False
    has_beehive: bool = False
    has_barracks: bool = False
    has_temple: bool = False
    has_swamp: bool = False
    noteleport: bool = False
    is_maze_lev: bool = False
    is_cavernous_lev: bool = False
    arboreal: bool = False
    corrmaze: bool = False


@dataclass
class Engraving:
    """One floor engraving (C: struct engr, reduced to the minimal model).

    C keeps a level-wide linked list (head_engr) of engravings keyed by
    (engr_x, engr_y), each carrying three text copies (actual /
    remembered / pristine), a tool type, a time, and read / erased
    state.  This minimal model keeps the text and the tool type on the
    Tile itself (the (engr_x, engr_y) key becomes the Tile); the
    remembered / pristine copies, the time-based wear, and the Elbereth
    guard are not ported (PLAN-SPECIAL-ROOMS.md phase 0).
    """

    text: str
    # C: engr_type (engrave.h: DUST 1, ENGRAVE 2, BURN 3, MARK 4,
    # ENGR_BLOOD 5, HEADSTONE 6 -- the E_* constants in core.engrave)
    type: int = 0


@dataclass
class Tile:
    """One level location (C: struct rm, reduced).

    STUB: the remaining rm fields (drawbridgemask, icedpool, diggable)
    are not ported yet -- they come with the drawbridge and ice work.
    door_mask is only meaningful for DOOR/SDOOR tiles; altarmask only
    for ALTAR tiles (the C `altarmask` overload of the flags field);
    stair_dir only for STAIRS tiles.
    """

    typ: TerrainType = TerrainType.ROOM
    door_mask: DoorMask = DoorMask(0)
    # the staircase direction of a STAIRS tile (C: levl[x][y].ladder,
    # LA_UP / LA_DOWN); 0 for every other terrain -- worldgen is the
    # only writer (PLAN-STAIRS.md decision 1)
    stair_dir: int = 0
    # the room this square belongs to (C: rm.h levl[x][y].roomno, a
    # 6-bit field): NO_ROOM (0) outside rooms, SHARED (1) on a boundary
    # square two rooms both claim, otherwise <room index> + ROOMOFFSET.
    # core.mklev.topologize / core.mkmap.flood_fill_rm are the writers.
    roomno: int = NO_ROOM
    # a boundary square of a room (C: levl[x][y].edge): the wall/door
    # ring flood_fill_rm and topologize mark, so an irregular room's
    # *inside* can be told from its edge.
    edge: bool = False
    # is the square lit (C: levl[x][y].lit)?  Set by the room generator
    # (do_room_or_subroom / topologize) and read by the display.
    lit: bool = False
    # wall/door orientation (C: rm.h levl[x][y].horizontal): True for
    # an east-west wall or a door in one.  Only meaningful for
    # HWALL/VWALL/DOOR/SDOOR; the door code reads it.
    horizontal: bool = False
    # --- the display memory (display.c; written by core.display) ---
    # what the HERO thinks is here (C: rm.h levl[x][y].glyph, "what the
    # hero remembers.  This will never be a monster").  It starts as
    # GLYPH_UNEXPLORED -- blank -- and only core.display.newsym()
    # replaces it, once the hero can actually see the square.
    glyph: int = GLYPH_UNEXPLORED
    # the octants the hero has seen this square from (C: rm.h
    # levl[x][y].seenv, the SV0..SV7 bits of core.display); 0 means
    # never seen -- which is how an unexplored wall still draws as
    # stone.  Never rewritten backwards (C: it is OR-ed, not set).
    seenv: int = 0
    # was the square lit when the hero last saw it (C: rm.h
    # levl[x][y].waslit, "remembered as lit")?  Written by newsym(),
    # read by back_to_glyph() for corridors.
    waslit: bool = False
    # which alignment an ALTAR answers to (C: the `altarmask` overload of
    # levl[x][y].flags, rm.h; the AM_* bits of align.h).  Written by the
    # altar generators (core.mklev.mkaltar / the temple work); 0 for
    # every non-altar tile.
    altarmask: int = 0
    # the floor engraving on this square, if any (C: the engr linked
    # list keyed by (x, y); see Engraving).  Written by core.engrave.
    engr: Optional[Engraving] = None

    def is_door_open(self) -> bool:
        """A door is passable unless closed/locked/trapped (C: the
        doormask tests in does_block() and the movement code)."""
        return not (
            self.door_mask & (DoorMask.CLOSED | DoorMask.LOCKED | DoorMask.TRAPPED)
        )


class Map:
    """Rectangular tile grid: tiles[y][x] is a Tile (C: levl[x][y]).

    Also owns the level-local sight data of core/vision.py (viz_clear
    + the left/right pointer rows).  The arrays are allocated here so
    they are never None; they hold zero/False placeholders until
    vision_reset() runs the row scan.  new_world() does that; a bare
    World built by tests is set up lazily on first vision use (see
    vision._ensure() and the vision_initialized flag).
    """

    def __init__(self, tiles: List[List[Tile]]):
        self.tiles = tiles
        # C: viz_clear[], left_ptrs[], right_ptrs[] (vision.c).  Allocated
        # up front (zeroed) so the arrays are never None; vision_reset()
        # fills them with the real row pointers.
        w = len(tiles[0]) if tiles else 0
        h = len(tiles)
        self.viz_clear: List[List[bool]] = [[False] * w for _ in range(h)]
        self.left_ptrs: List[List[int]] = [[0] * w for _ in range(h)]
        self.right_ptrs: List[List[int]] = [[0] * w for _ in range(h)]
        # True once vision_init()/vision_reset() have run; _ensure() uses
        # it to trigger the lazy setup for a bare World (tests) that
        # skipped new_world().
        self.vision_initialized: bool = False
        # --- rooms (C: svr.rooms[] / gs.subrooms[] / svd.doors[]) ---
        # The room records belong to the level, so they are parked and
        # taken back with the Map on a level change.  An empty list is a
        # level nobody has cut into rooms (the demo generator, the bare
        # test maps).
        self.rooms: List[Room] = []
        self.subrooms: List[Room] = []
        # C: svd.doors[] + gd.doorindex -- every door the generator made,
        # in creation order (rooms carry their own subset, see Room.doors).
        self.doors: List[Pos] = []
        # C: svl.level.flags (decl.h)
        self.flags = LevelFlags()

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

    # --- rooms -------------------------------------------------

    def room_at(self, pos: Pos) -> Optional[Room]:
        """The room whose floor `pos` is, if any (C: the
        levl[x][y].roomno lookup; SHARED boundary squares belong to no
        single room)."""
        roomno = self.tile_at(pos).roomno
        idx = roomno - ROOMOFFSET
        if roomno < ROOMOFFSET or not 0 <= idx < len(self.rooms):
            return None
        return self.rooms[idx]

    def room_of(self, room: Room) -> int:
        """The Tile.roomno value of `room`'s inside squares (C: the
        (sroom - svr.rooms) + ROOMOFFSET idiom)."""
        return self.rooms.index(room) + ROOMOFFSET


@dataclass(frozen=True)
class Stairway:
    """A staircase on the current level (C: one entry of the gs.stairs
    list of struct stairway, src/stairs.c; the sx / sy / up /
    u_traversed half -- isladder is dropped, no ladders, and the
    destination level is not stored: in the main dungeon it is
    ``world.lev +/- 1``, derivable from the direction, C: tolev).

    ``world.stairs`` holds ONLY the current level's stairways; it is
    rebuilt on every level entry by core.stairs.rebuild_stairs (which
    scans the map's STAIRS tiles -- the demo equivalent of the
    stairway_add calls in mkstairs / restore.c after the
    stairway_free_all of goto_level).  ``traversed`` is the C
    u_traversed, kept for C fidelity: it feeds C's
    stairs_description() branch text, which the demo doesn't have.
    """

    pos: Pos
    up: bool
    traversed: bool = False


# ============================================================
# Items
# ============================================================


@dataclass
class Item:
    """One object (C: struct obj, reduced).

    Three *mutually exclusive* where-states, by construction (C:
    obj->where; see PLAN-MKOBJ.md decisions 2-3):

    - on the floor: ``pos`` is set, ``carrier`` is None and no
      container lists it;
    - carried: ``carrier`` is the carrier's id and ``pos`` is None
      (C: OBJ_INVENT / OBJ_MINVENT);
    - contained: the parent's ``contents`` holds this id, and both
      ``pos`` and ``carrier`` are None (C: OBJ_CONTAINED).

    The field is named ``carrier``, not ``container``, because that is
    what it means -- the *containment* relation is ``Item.contents`` on
    the parent (the reader is core.mkobj.add_to_container, the only
    writer besides delete_contents).
    """

    id: str
    otype: ObjectType
    name: str
    # the inventory letter (C: obj->invlet): the a..z A..Z '#' slot the
    # item holds in its carrier's pack, assigned once by
    # core.invent.assigninvlet and kept while the item is held (the C
    # invlet_constant default, PLAN-INVENT.md decision 5); "" for an
    # item that never went through the allocator (hand-built test
    # items, floor kit before pickup)
    invlet: str = ""
    blessed: bool = False
    cursed: bool = False
    pos: Optional[Pos] = None  # where it lies on the floor, if anywhere
    carrier: Optional[str] = None  # id of the monster carrying it, if any
    # the dungeon level the item is on (see Monster.lev); a carried
    # item keeps its carrier's level
    lev: int = 1
    wand_type: Optional[WandType] = None
    potion_type: Optional[PotionType] = None
    spell_type: Optional[SpellType] = None
    scroll_type: Optional[ScrollType] = None
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
    # object-identity knowledge (C: obj->dknown / obj->known): dknown is
    # "seen up close" (the ring is on the hand / in the inventory); known
    # is "the enchantment is revealed" (a charged ring whose type is
    # known).  Both are mutated ONLY by the core choke point
    # core.rules.apply_discovery (the DiscoveryEvent), never by the ring /
    # item modules (core.rings emits the intent, the core applies it).
    dknown: bool = False
    known: bool = False
    # nutrition already eaten out of this food piece (C: obj->oeaten,
    # the eating-occupation meal bookkeeping, PLAN-OCCUPATION.md):
    # 0 for a full piece; on an interrupted meal the remainder stays
    # here so the item can be resumed with a reduced duration
    oeaten: int = 0
    # --- the struct obj fields the object genesis needs (PLAN-MKOBJ.md
    # §2; written by core.mkobj, read by weight() / the display) ---
    # how many of this type are in the stack (C: obj->quan).  A gold
    # pile, ten arrows and three daggers are each ONE Item.
    quan: int = 1
    # the monster type of a corpse / statue / egg / figurine / tin
    # (C: obj->corpsenm); NON_PM (-1) = not a monster-bearing object.
    # core.types does not import the PM table, so the C NON_PM value is
    # spelled out here (monst_defs.NON_PM is the same number).
    corpsenm: int = -1
    # the ids of the objects inside a container (C: obj->cobj, a list
    # of ids -- the pyhack rule: no object graphs inside the World).
    # core.mkobj.add_to_container / delete_contents are the only
    # writers.
    contents: List[str] = field(default_factory=list)
    # the item's weight in 1/100 lb (C: obj->owt), written by
    # core.mkobj.weight; 0 means "not computed yet" for the hand-built
    # demo kit (nothing reads it as a real weight yet).
    owt: int = 0
    # erosion counters (C: obj->oeroded / oeroded2): how many times the
    # item was damaged by fire / by acid or corrosion.  ARM_BONUS /
    # core.worn.uac read them on every query, never cache
    # (PLAN-ARMOR.md phase 4); core.worn.erode_obj is the writer, and
    # core.mkobj.mkobj_erosions seeds them at generation time.
    oeroded: int = 0
    oeroded2: int = 0
    # a container's state (C: obj->olocked / obj->otrapped / broken)
    olocked: bool = False
    otrapped: bool = False
    broken: bool = False
    # C: obj->age (a corpse's / egg's / lamp's clock; written where C
    # writes it, read nowhere yet -- there is no timeout.c) and
    # obj->recharged (the wand / ring recharge counter)
    age: int = 0
    recharged: int = 0
    # accepted and always 0: pyhack has no artifact system
    # (C: obj->oartifact)
    oartifact: int = 0


# ============================================================
# Monsters (the hero is just a monster with is_hero=True)
# ============================================================

# C: include/you.h -- the maximum character level.  Sizes the hero's
# ueninc[] bookkeeping array (core.energy) and the regen period
# (MAXULEV + 8 - ulevel).
MAXULEV = 30


@dataclass
class Epri:
    """The temple priest extra (C: struct epri, mextra.h 95-106).

    Allocated by makemon()'s MM_EPRI (the C newepri() half) and filled
    by core.priest.priestini; every other monster has ``Monster.epri``
    None.  ``shroom`` is the temple's room number (C stores
    ``sroom - svr.rooms + ROOMOFFSET``); ``shrlevel`` is the level the
    shrine stands on (C's d_level reduced to a level number: pyhack
    has one dungeon).  The message-pacing timers and
    ``cheapskate_count`` are carried as fields and never ticked
    (PLAN-SPECIAL-ROOMS.md §5.2: the priest_talk / intemple pacing
    economy is not ported).
    """

    shralign: int = A_NEUTRAL  # the alignment of the priest's shrine
    shroom: int = NO_ROOM  # the temple room's room number
    shrpos: Pos = (0, 0)  # the shrine (the blessed altar) square
    shrlevel: int = 1  # the level the shrine stands on
    cheapskate_count: int = 0  # C: the cheapskate donations
    intone_time: int = 0  # C: entry-message pacing (never ticked)
    enter_time: int = 0  # C: entry-message pacing (never ticked)
    hostile_time: int = 0  # C: forbidding-feeling pacing (never)
    peaceful_time: int = 0  # C: sense-of-peace pacing (never)


@dataclass
class Eshk:
    """The shopkeeper extra (C: struct eshk, mextra.h).

    Allocated by makemon()'s MM_ESHK (the C neweshk() half) and filled
    by core.shk.init; every other monster has ``Monster.eshk`` None.
    ``shoproom`` is the shop's room number (C stores ``sroom -
    svr.rooms + ROOMOFFSET``), ``shoptype`` the room type
    (SHOPBASE + the shop index), ``shd`` the shop door and ``shk`` the
    shopkeeper's own square (C duplicates mx/my here).

    What the *billing* half would use is carried as zeroed fields and
    named deferred (PLAN-SPECIAL-ROOMS.md: phase 4a lands the stocked,
    robbable shop; the bill is 4b, the police 4c, the dialogue 4d):
    ``debit`` / ``credit`` / ``loan`` (C's eshk account, the customer's
    running total), ``robbed`` (the "you stole from me" amount),
    ``surcharge`` (alter_cost's 1/3 markup) and ``following`` /
    ``dismiss_kops`` (the police half).  C's ``struct bill_x bill[]``
    -- the list of unpaid items -- is not a field yet: it is the model
    4b adds (a dict keyed by item id, PLAN-SPECIAL-ROOMS.md §2.3).
    None of these is read or written outside this comment yet.
    """

    parentmid: str = ""  # C: eshk.parentmid -- the owning monster's id
    shoproom: int = NO_ROOM  # the shop's room number
    shoptype: int = 0  # the shop's room type (SHOPBASE + index)
    shoplevel: int = 1  # C: shoplevel (a d_level, reduced to a number)
    shd: Pos = (0, 0)  # the shop door
    shk: Pos = (0, 0)  # the shopkeeper's square
    shknam: str = ""  # the shopkeeper's name (C: shknam[PL_NSIZ])
    robbed: int = 0  # the amount the hero stole (0 = nothing)
    debit: int = 0  # what the hero owes
    credit: int = 0  # the shopkeeper's credit to the hero (always 0)
    loan: int = 0  # a loan (always 0)
    following: bool = False  # C: the shopkeeper follows the hero out
    surcharge: bool = False  # C: the alter_cost markup
    dismiss_kops: bool = False  # C: the kops half
    billct: int = 0  # C: billct -- the number of billed items
    visitct: int = 0  # C: visitct -- the shop-visit counter
    customer: str = ""  # C: customer[] -- who is shopping here


@dataclass
class Monster:
    id: str
    name: str
    pos: Pos
    hp: int
    max_hp: int
    ac: int  # BASE (body) armor class (C: mons[].ac).
    # The effective AC is computed, never cached: core.worn.uac()
    # subtracts the worn gear (the find_ac computation, PLAN-ARMOR.md).
    damage: int = 2  # melee damage = 1d`damage`
    alive: bool = True
    is_hero: bool = False
    # the dungeon level the actor is on (C: the per-level monster
    # lists; pyhack keeps one flat list and discriminates by lev).
    # The hero's lev tracks World.lev (core.stairs.goto_level);
    # monsters on other levels are frozen (decision 3).
    lev: int = 1
    mdata: Optional["PerMonst"] = None  # permonst type (C: mtmp->data);
    # None for the flat-stat demo monsters (they use the simple melee
    # path); set for monsters that go through the C-port systems
    # (mhitu, ...)
    m_lev: int = 0  # the monster INSTANCE level (C: mtmp->m_lev):
    # pinned to mdata.mlevel at spawn (PLAN-EXPERIENCE.md decision 2; the
    # C adj_lev roll lands with the makemon port); the kill-XP formula's
    # 1 + m_lev^2 and the per-m_lev bonuses read it.  0 for the hero and
    # the flat-stat monsters.
    sleeping: int = 0  # turns of sleep remaining
    stuck: int = 0  # turns of stuck remaining (web / pit)
    poisoned: int = 0  # turns of poison remaining
    confused: int = 0  # turns of confusion remaining
    blind: int = 0  # turns of blindness remaining
    hallucinating: int = 0  # turns of hallucinating remaining
    # hunger (C: you.h u.uhunger / u.uhs -- src/eat.c).  The gauge is
    # 0..2000 (start 900, the init_uhunger value; negative = the
    # starving deficit); uhs is the computed HungerState.  fainted is
    # the C FAINTED state's unconsciousness counter (the nomul(-
    # duration) of the faint -- the Deaf half is dropped, pyhack has no
    # deafness); core.rules.tick_actor ticks it down, core.hunger.
    # newuhs sets it.
    uhunger: int = 900
    uhs: "HungerState" = HungerState.NOT_HUNGRY
    fainted: int = 0
    is_undead: bool = False
    is_demon: bool = False
    is_golem: bool = False
    is_nonliving: bool = False
    is_flying: bool = False
    inventory: List[Item] = field(default_factory=list)
    # hero combat state (the demo's weapon subset; see core.uhitm and
    # core.weapon): the hero wields a starting weapon, and its fixed
    # abilities feed the to-hit / damage bonuses
    wielded: Optional[str] = None  # id of the wielded item (C: uwep)
    ulevel: int = 1  # hero level (C: u.ulevel; the XP
    # system levels it up / losexp() drains it)
    uexp: int = 0  # XP toward the next level (C: u.uexp)
    urexp: int = 0  # XP for the score (C: u.urexp; the
    # 4*exper + rexp half of more_experienced; no score system yet)
    ulevelmax: int = 1  # highest level ever reached (C:
    # u.ulevelmax; the "back" half of the welcome message)
    ulevelpeak: int = 1  # highest level (C: u.ulevelpeak)
    ustr: int = 12  # strength (fixed; no STR18)
    ucon: int = 12  # constitution (C: A_CON base)
    udex: int = 12  # dexterity (neutral: no bonus swing)
    uwis: int = 12  # wisdom (fixed; C: the A_WIS half of
    # newpw() / regen_pw() in core.energy)
    uint: int = 15  # intelligence (fixed; C: the A_INT half;
    # the Wizard role's starting INT feeds the spell formulas in
    # core.spells)
    ucha: int = 12  # charisma (C: A_CHA base; the
    # RIN_ADORNMENT ring adjusts it -- core.rules.current_ability)
    # NOTE: the abilities a worn ring changes (RIN_GAIN_STRENGTH /
    # RIN_GAIN_CONSTITUTION / RIN_ADORNMENT) are COMPUTED, never cached:
    # core.rules.current_ability returns the base (ustr / ucon / ucha) plus
    # the spe of the worn ability ring, so don/doff changes the worn mask
    # and the next query agrees (the core.worn.uac style).  No per-ability
    # bonus is stored here.
    # spell power (C: you.h uen / uenmax / uenpeak / ueninc[MAXULEV]):
    # the demo default is 0/0/0 (the test heroes never cast); the demo
    # hero's Pw is set by energy.init_energy (C: u_init.c).  ueninc[]
    # is the per-level Pw INCREMENT (C: newpw() records
    # ueninc[old_level] on a gain, losexp() subtracts
    # ueninc[new_level]); ueninc[0] is the init record (as with
    # uhpinc[0]).  The regen period is NOT this array -- it is
    # computed from the level (C: regen_pw; core.energy.tick_energy)
    uen: int = 0
    uenmax: int = 0
    uenpeak: int = 0
    # --- the makemon fields (PLAN-MAKEMON.md §3) ---
    # the mons[] index of the type (C: mtmp->mnum); -1 (NON_PM) for a
    # monster with no table row (the flat-stat demo monsters).
    # core.mondata.set_mon_data keeps it in step with mdata; vitals,
    # corpses, statues and genocide all key off it.
    mnum: int = -1
    # C: mtmp->female -- affects the name and corpse stacking
    female: bool = False
    # C: mtmp->mpeaceful.  The C zeromonst default is hostile (0), and
    # makemon's peace_minded() is what makes a placid one, so the
    # default here is the hostile one too.
    mpeaceful: bool = False
    # C: mtmp->malign -- the alignment score set_malign() computes for
    # the kill-alignment bookkeeping (no alignment system yet; the
    # value is recorded, nothing acts on it)
    malign: int = 0
    # C: mtmp->mavenge -- a peaceful monster that was attacked
    mavenge: bool = False
    # C: mtmp->mcan -- cancelled (blocks most special attacks)
    mcan: bool = False
    # C: mtmp->mstrategy -- the STRAT_WAITFORU / STRAT_CLOSE /
    # STRAT_APPEARMSG bits of the M3_* flags
    mstrategy: int = 0
    ueninc: List[int] = field(default_factory=lambda: [0] * MAXULEV)
    # the per-level HP increment (C: u.uhpinc[MAXULEV]); newhp() records
    # uhpinc[old_level] on a level-up and losexp() subtracts
    # uhpinc[new_level]; uhpinc[0] is the init record (PLAN-EXPERIENCE.md
    # risk 4)
    uhpinc: List[int] = field(default_factory=lambda: [0] * MAXULEV)
    skills: Optional["Skills"] = None  # per-hero weapon-skill state
    # intrinsic properties (C: the u.uprops[] inherent / temp half,
    # mprops for monsters): the Prop set held without gear (species, spells,
    # potions).  The worn-gear contribution is computed, never stored
    # (core.props.worn_properties / has_property).
    intrinsics: "set[Prop]" = field(default_factory=set)
    # --- the mextra halves (PLAN-SPECIAL-ROOMS.md §2.1) ---
    # the priest extra (C: mextra->epri via newepri): allocated by
    # makemon()'s MM_EPRI and filled by core.priest.priestini; None for
    # every monster that is not a priest candidate
    epri: Optional[Epri] = None
    # C: struct monst's ispriest / isshk booleans -- the flags the
    # naming, movement and shop code reads.  A monster can carry the
    # epri extra without being a priest yet: priestini() sets the flag
    # (C does the same, after the newepri of makemon)
    ispriest: bool = False
    isshk: bool = False
    # the shopkeeper extra (C: mextra->eshk via neweshk): allocated by
    # makemon()'s MM_ESHK and filled by core.shk.init; None for every
    # monster that is not a shopkeeper.  The flag above and this extra
    # are set together by shkinit (C does the same: makemon only
    # allocates, shkinit() decides).
    eshk: Optional[Eshk] = None


# ============================================================
# Traps
# ============================================================


@dataclass
class Trap:
    id: str
    trap_type: TrapType
    pos: Pos
    # the dungeon level the trap is on (see Monster.lev)
    lev: int = 1
    triggered: bool = False
    disarmed: bool = False
    seen: bool = False


# ============================================================
# World -- the single state object
# ============================================================


@dataclass
class World:
    map: Map
    # non-CURRENT levels, keyed by level number (the getlev()
    # equivalent: a visited level's full state is kept in memory until
    # game over -- PLAN-STAIRS.md decision 3 / §4).  On a level change
    # the old world.map is parked here and the target's parked map (if
    # visited) is taken back into world.map; level 1 is parked too once
    # the hero leaves it.  world.map stays a plain field (every existing
    # system reads it unmodified).
    levels: "dict[int, Map]" = field(default_factory=dict)
    # current level number (C: u.uz.dlevel); max_lev is the bottom
    # level (C: num_dunlevs) -- reaching it wins (decision 4.8)
    lev: int = 1
    max_lev: int = 1
    # the midnight state (C: midnight(), calendar.c): main.py samples
    # the wall clock once per game and keeps it fixed for the whole
    # game (the deterministic rule); mattacku's undead double damage
    # reads it (C: hitmu)
    midnight: bool = False
    # the game's birth time in epoch seconds (C: ubirthday, the hero's
    # birth time): antholemon() reads % 3 of it for the per-level ant
    # species (same species on a level, different ones between levels
    # and between games).  main.py samples getnow() once at game start
    # (the midnight pattern); tests leave the 0 default, so seeded
    # worlds keep their draw sequences.
    birth: int = 0
    # the CURRENT level's stairways (C: gs.stairs); rebuilt on every
    # level entry by core.stairs.rebuild_stairs
    stairs: "list[Stairway]" = field(default_factory=list)
    actors: "dict[str, Monster]" = field(default_factory=dict)
    traps: "dict[str, Trap]" = field(default_factory=dict)
    items: "dict[str, Item]" = field(default_factory=dict)
    turn: int = 0
    over: bool = False
    # the hero's current view (C: gv.viz_array + gv.viz_rmin/rmax);
    # built by core.vision (vision_recalc), None until first use
    vision: Optional["HeroVision"] = None
    # per-game object-table state (C: the svb / svd globals of o_init.c):
    # oc_name_known / oc_encountered / the description shuffle / the
    # discovery order.  One instance per World (the architecture: all
    # state in the World).  It owns its own deterministic rng stream so
    # the description shuffle does NOT perturb a seeded world's layout
    # draw sequence (the demo's pinned draws stay put).
    obj_tables: "ObjTables" = field(
        default_factory=lambda: ObjTables(Rng(b"pyhack-objtables"))
    )
    # the hero's running long-duration task (C: go.occupation +
    # go.occtxt, the set_occupation mechanism): a generator whose
    # frame holds the task state (PLAN-OCCUPATION.md); None when the
    # hero is not mid-task.  Advanced by core.occupation
    # (run_occupation) at the top of the hero's turn in step().
    occupation: Optional["Occupation"] = None
    # which level generator new_world()/worldgen.generate_level use
    # ("demo" = the pinned 40x20 cave every earlier session was built
    # on, "mklev" = the ported rooms+corridors+doors generator of
    # core.mklev -- see PLAN-MKLEV.md).  It lives in the World because
    # levels 2..N generate lazily, long after new_world() returned.
    generator: str = "demo"
    # the per-game monster-type status (C: svm: the mvitals[] array of
    # born / died / flags counters the genocide, extinction and
    # rndmonst machinery share).  One instance per World, the ObjTables
    # pattern.
    mon_state: "MonState" = field(default_factory=lambda: MonState())
    # the hero's alignment (C: u.ualign.type).  There is no alignment
    # system yet, so this is the constant the demo uses -- A_NEUTRAL,
    # so a neutral monster gets C's co-aligned peace chance and any
    # aligned monster is hostile (PLAN-MAKEMON.md divergence 1);
    # peace_minded() reads it.
    hero_align: int = A_NEUTRAL
    # the id allocator (C: next_ident(), mkobj.c): one counter for
    # monsters, objects and traps.  The hand-formatted demo ids
    # ("goblin_2_1", "armor_0") are NOT produced through it -- they are
    # load-bearing for the pinned tests -- so it only serves the new
    # (generated) paths.
    ident: int = 0
    # the hero's last-assigned inventory-letter index (C: gl.lastinvnr):
    # core.invent.assigninvlet walks the a..z A..Z slots from here, so a
    # fresh letter comes out just after the one last used (the C
    # invlet_constant behaviour, PLAN-INVENT.md decision 5).  -1 before
    # the first assignment (C: reset_globals).
    lastinvnr: int = -1

    def new_id(self, prefix: str = "obj") -> str:
        """Allocate a fresh unique id (C: next_ident())."""
        self.ident += 1
        return f"{prefix}_{self.ident}"

    @property
    def hero(self) -> Monster:
        return self.actors["player"]

    @property
    def hero_or_none(self) -> Optional[Monster]:
        """The hero, or None while the game has not placed one yet.

        C's equivalent is the u.ux / u.uy pair: level 1 is generated
        (mklev()) before u_on_upstairs() puts the hero on the map, so
        every "is the hero in the way?" test during generation reads
        (0, 0) and answers "no" -- the same answer None gives here.
        The genesis (core.makemon / core.place / core.mkobj) is the
        one caller family that runs on both sides of that line.
        """
        return self.actors.get("player")

    @property
    def hero_ulevel(self) -> int:
        """C's u.ulevel, with C's value before the hero exists: 1.

        C inits u.ulevel to 1 in u_init() -- before the first mklev(),
        which is why a level-1 monster's hit points and enchantment
        rolls already see a level-1 adventurer.  The genesis reads this
        instead of World.hero.ulevel so it works during generation.
        """
        hero = self.hero_or_none
        return 1 if hero is None else hero.ulevel

    def monster_at(self, pos: Pos) -> Optional[Monster]:
        """First living actor on THIS level standing on `pos`, if any.
        The lev filter keeps other levels' actors out (decision 3: a
        missed filter is a cross-level ghost monster)."""
        return self.monster_at_lev(self.lev, pos)

    def monster_at_lev(self, lev: int, pos: Pos) -> Optional[Monster]:
        """First living actor on level `lev` standing on `pos` (C:
        MON_AT).  The one place the level-membership filter lives;
        monster_at() is the current-level form.  The level generators
        need the parameterised form: they place monsters on a level
        the hero is not standing on (core.place.goodpos)."""
        for m in self.actors.values():
            if m.alive and m.lev == lev and m.pos == pos:
                return m
        return None

    def items_at(self, pos: Pos) -> List[Item]:
        """Items lying on `pos` on THIS level (C: the
        svl.level.objects[x][y] chain; the lev filter keeps other
        levels' floor items out)."""
        return [
            it for it in self.items.values() if it.lev == self.lev and it.pos == pos
        ]
