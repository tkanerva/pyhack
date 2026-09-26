"""Monster type table (port of src/monst.c + include/monsters.h).

In the C source the table is built by expanding include/monsters.h
through the MON() macro in monst.c.  This module is the single Python
home for all of that:

- all the constants the table uses, as real enum types where C has an
  enum or a bit-mask family: `MonsterClass` (S_*), `AtkType` /
  `DmgType` (AT_*/AD_*), the `M1` / `M2` / `M3` flag bitmaps, `MR`
  (resists/conveyances), `Geno` and `MvitalsFlag` (the two G_* bit
  spaces), `MSize` (MZ_*), `MSound` (MS_*), `MGender`.  The C-style
  names (S_ANT, M1_FLY, MR_POISON, ...) are kept as module-level
  aliases of the enum members so the transcribed code reads like the
  C it came from; plain ints are kept only where C has no enum
  either (WT_* body weights, the A_* alignment bounds, G_FREQ which
  is a mask, and the table indices/counts);
- `Attack` / `PerMonst` -- the struct attack / struct permonst rows;
- `PM_NAMES` -- the COMPLETE C ordering of all 383 monster types
  (default build: CHARON undefined; MAIL_STRUCTURES always defined in
  5.0 (global.h), so the mail daemon IS in the table; all `#if 0`
  blocks excluded).  This is recorded even though only a subset of the
  table is implemented, so the PM_ numbering is fixed once and the
  remaining ~90% can be completed later without renumbering anything;
- `MONS` -- the (sparse) table itself: PerMonst at the C index for the
  implemented subset, None elsewhere;
- table accessors (monsndx, monclass, monname, defch, is_golem,
  is_dragon).

Core-subset policy (per project decision): only the ~10% of monsters
needed to build and play the core game is transcribed here (the demo's
goblin/orc/bat, low-level dungeon staples, and the carriers of the
special-attack mechanics: petrify, drain, steal, stick, breath, ...).
The subset is `SUBSET_PM` below.

The table is checked by `_validate()`.  It runs from the test suite
(tests/test_monst.py) and via `python -m core.monst`, NOT at import
time, so importing this module has no side effects.

5.0 adaptations (documented, not bugs):

- `mlet` holds the S_* class INDEX (1..60), not the character; the
  display character comes from DEFCHARS (C: defsyms / mon_defchars).
  C code compares mlet to S_foo (e.g. olfaction() checks
  mdat->mlet == S_EYE).
- The C fencepost mons[NUMMONS] terminator is omitted.
- pmnames[0]/[1] (male/female) are None for NAM() monsters; all
  subset entries are NAM() (single name).
- Rule #1 (class contiguity) is intentionally NOT enforced: 5.0 puts
  the quest nemeses and guardians (several of them S_HUMAN) after the
  worm tail, so classes are not contiguous in the table.
- MSound.FERRY (45) is not in the pinned monflag.h (rev 1.33): its
  only user is the #ifdef CHARON ferryman, which the default build
  excludes.  Kept (with this note) so a later pass that adds
  Charon doesn't have to invent a number.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag

# ------------------------------------------------------------
# Monster classes (defsym.h MONSYM table: S_* indices 1..60)
# ------------------------------------------------------------

class MonsterClass(IntEnum):
    """Monster class index (C: S_*; defsym.h MONSYM table)."""
    ANT = 1
    BLOB = 2
    COCKATRICE = 3
    DOG = 4
    EYE = 5
    FELINE = 6
    GREMLIN = 7
    HUMANOID = 8
    IMP = 9
    JELLY = 10
    KOBOLD = 11
    LEPRECHAUN = 12
    MIMIC = 13
    NYMPH = 14
    ORC = 15
    PIERCER = 16
    QUADRUPED = 17
    RODENT = 18
    SPIDER = 19
    TRAPPER = 20
    UNICORN = 21
    VORTEX = 22
    WORM = 23
    XAN = 24
    LIGHT = 25
    ZRUTY = 26
    ANGEL = 27
    BAT = 28
    CENTAUR = 29
    DRAGON = 30
    ELEMENTAL = 31
    FUNGUS = 32
    GNOME = 33
    GIANT = 34
    INVISIBLE = 35
    JABBERWOCK = 36
    KOP = 37
    LICH = 38
    MUMMY = 39
    NAGA = 40
    OGRE = 41
    PUDDING = 42
    QUANTMECH = 43
    RUSTMONST = 44
    SNAKE = 45
    TROLL = 46
    UMBER = 47
    VAMPIRE = 48
    WRAITH = 49
    XORN = 50
    YETI = 51
    ZOMBIE = 52
    HUMAN = 53
    GHOST = 54
    GOLEM = 55
    DEMON = 56
    EEL = 57
    LIZARD = 58
    WORM_TAIL = 59
    MIMIC_DEF = 60


# C-style aliases (kept for parallelism with include/*.h; the
# transcribed code refers to constants by their C names)
S_ANT = MonsterClass.ANT
S_BLOB = MonsterClass.BLOB
S_COCKATRICE = MonsterClass.COCKATRICE
S_DOG = MonsterClass.DOG
S_EYE = MonsterClass.EYE
S_FELINE = MonsterClass.FELINE
S_GREMLIN = MonsterClass.GREMLIN
S_HUMANOID = MonsterClass.HUMANOID
S_IMP = MonsterClass.IMP
S_JELLY = MonsterClass.JELLY
S_KOBOLD = MonsterClass.KOBOLD
S_LEPRECHAUN = MonsterClass.LEPRECHAUN
S_MIMIC = MonsterClass.MIMIC
S_NYMPH = MonsterClass.NYMPH
S_ORC = MonsterClass.ORC
S_PIERCER = MonsterClass.PIERCER
S_QUADRUPED = MonsterClass.QUADRUPED
S_RODENT = MonsterClass.RODENT
S_SPIDER = MonsterClass.SPIDER
S_TRAPPER = MonsterClass.TRAPPER
S_UNICORN = MonsterClass.UNICORN
S_VORTEX = MonsterClass.VORTEX
S_WORM = MonsterClass.WORM
S_XAN = MonsterClass.XAN
S_LIGHT = MonsterClass.LIGHT
S_ZRUTY = MonsterClass.ZRUTY
S_ANGEL = MonsterClass.ANGEL
S_BAT = MonsterClass.BAT
S_CENTAUR = MonsterClass.CENTAUR
S_DRAGON = MonsterClass.DRAGON
S_ELEMENTAL = MonsterClass.ELEMENTAL
S_FUNGUS = MonsterClass.FUNGUS
S_GNOME = MonsterClass.GNOME
S_GIANT = MonsterClass.GIANT
S_INVISIBLE = MonsterClass.INVISIBLE
S_JABBERWOCK = MonsterClass.JABBERWOCK
S_KOP = MonsterClass.KOP
S_LICH = MonsterClass.LICH
S_MUMMY = MonsterClass.MUMMY
S_NAGA = MonsterClass.NAGA
S_OGRE = MonsterClass.OGRE
S_PUDDING = MonsterClass.PUDDING
S_QUANTMECH = MonsterClass.QUANTMECH
S_RUSTMONST = MonsterClass.RUSTMONST
S_SNAKE = MonsterClass.SNAKE
S_TROLL = MonsterClass.TROLL
S_UMBER = MonsterClass.UMBER
S_VAMPIRE = MonsterClass.VAMPIRE
S_WRAITH = MonsterClass.WRAITH
S_XORN = MonsterClass.XORN
S_YETI = MonsterClass.YETI
S_ZOMBIE = MonsterClass.ZOMBIE
S_HUMAN = MonsterClass.HUMAN
S_GHOST = MonsterClass.GHOST
S_GOLEM = MonsterClass.GOLEM
S_DEMON = MonsterClass.DEMON
S_EEL = MonsterClass.EEL
S_LIZARD = MonsterClass.LIZARD
S_WORM_TAIL = MonsterClass.WORM_TAIL
S_MIMIC_DEF = MonsterClass.MIMIC_DEF

MAXMCLASSES = 61

# default display character per class (sym.h mon_defchars)
DEFCHARS: dict[MonsterClass, str] = {
    S_ANT: 'a', S_BLOB: 'b', S_COCKATRICE: 'c', S_DOG: 'd', S_EYE: 'e',
    S_FELINE: 'f', S_GREMLIN: 'g', S_HUMANOID: 'h', S_IMP: 'i',
    S_JELLY: 'j', S_KOBOLD: 'k', S_LEPRECHAUN: 'l', S_MIMIC: 'm',
    S_NYMPH: 'n', S_ORC: 'o', S_PIERCER: 'p', S_QUADRUPED: 'q',
    S_RODENT: 'r', S_SPIDER: 's', S_TRAPPER: 't', S_UNICORN: 'u',
    S_VORTEX: 'v', S_WORM: 'w', S_XAN: 'x', S_LIGHT: 'y', S_ZRUTY: 'z',
    S_ANGEL: 'A', S_BAT: 'B', S_CENTAUR: 'C', S_DRAGON: 'D',
    S_ELEMENTAL: 'E', S_FUNGUS: 'F', S_GNOME: 'G', S_GIANT: 'H',
    S_INVISIBLE: 'I', S_JABBERWOCK: 'J', S_KOP: 'K', S_LICH: 'L',
    S_MUMMY: 'M', S_NAGA: 'N', S_OGRE: 'O', S_PUDDING: 'P',
    S_QUANTMECH: 'Q', S_RUSTMONST: 'R', S_SNAKE: 'S', S_TROLL: 'T',
    S_UMBER: 'U', S_VAMPIRE: 'V', S_WRAITH: 'W', S_XORN: 'X',
    S_YETI: 'Y', S_ZOMBIE: 'Z', S_HUMAN: '@', S_GHOST: ' ',
    S_GOLEM: "'", S_DEMON: '&', S_EEL: ';', S_LIZARD: ':',
    S_WORM_TAIL: '~', S_MIMIC_DEF: ']',
}

# ------------------------------------------------------------
# Attack types and damage types (monattk.h)
# ------------------------------------------------------------

class AtkType(IntEnum):
    """Attack type (C: AT_*; monattk.h)."""
    ANY = -1
    NONE = 0
    CLAW = 1
    BITE = 2
    KICK = 3
    BUTT = 4
    TUCH = 5
    STNG = 6
    HUGS = 7
    SPIT = 10
    ENGL = 11
    BREA = 12
    EXPL = 13
    BOOM = 14
    GAZE = 15
    TENT = 16
    WEAP = 254
    MAGC = 255


AT_ANY = AtkType.ANY
AT_NONE = AtkType.NONE
AT_CLAW = AtkType.CLAW
AT_BITE = AtkType.BITE
AT_KICK = AtkType.KICK
AT_BUTT = AtkType.BUTT
AT_TUCH = AtkType.TUCH
AT_STNG = AtkType.STNG
AT_HUGS = AtkType.HUGS
AT_SPIT = AtkType.SPIT
AT_ENGL = AtkType.ENGL
AT_BREA = AtkType.BREA
AT_EXPL = AtkType.EXPL
AT_BOOM = AtkType.BOOM
AT_GAZE = AtkType.GAZE
AT_TENT = AtkType.TENT
AT_WEAP = AtkType.WEAP
AT_MAGC = AtkType.MAGC

NATTK = 6


class DmgType(IntEnum):
    """Damage type (C: AD_*; monattk.h)."""
    ANY = -1
    PHYS = 0
    MAGM = 1
    FIRE = 2
    COLD = 3
    SLEE = 4
    DISN = 5
    ELEC = 6
    DRST = 7
    ACID = 8
    SPC1 = 9
    SPC2 = 10
    BLND = 11
    STUN = 12
    SLOW = 13
    PLYS = 14
    DRLI = 15
    DREN = 16
    LEGS = 17
    STON = 18
    STCK = 19
    SGLD = 20
    SITM = 21
    SEDU = 22
    TLPT = 23
    RUST = 24
    CONF = 25
    DGST = 26
    HEAL = 27
    WRAP = 28
    WERE = 29
    DRDX = 30
    DRCO = 31
    DRIN = 32
    DISE = 33
    DCAY = 34
    SSEX = 35
    HALU = 36
    DETH = 37
    PEST = 38
    FAMN = 39
    SLIM = 40
    ENCH = 41
    CORR = 42
    POLY = 43
    CLRC = 240
    SPEL = 241
    RBRE = 242
    SAMU = 252
    CURS = 253


AD_ANY = DmgType.ANY
AD_PHYS = DmgType.PHYS
AD_MAGM = DmgType.MAGM
AD_FIRE = DmgType.FIRE
AD_COLD = DmgType.COLD
AD_SLEE = DmgType.SLEE
AD_DISN = DmgType.DISN
AD_ELEC = DmgType.ELEC
AD_DRST = DmgType.DRST
AD_ACID = DmgType.ACID
AD_SPC1 = DmgType.SPC1
AD_SPC2 = DmgType.SPC2
AD_BLND = DmgType.BLND
AD_STUN = DmgType.STUN
AD_SLOW = DmgType.SLOW
AD_PLYS = DmgType.PLYS
AD_DRLI = DmgType.DRLI
AD_DREN = DmgType.DREN
AD_LEGS = DmgType.LEGS
AD_STON = DmgType.STON
AD_STCK = DmgType.STCK
AD_SGLD = DmgType.SGLD
AD_SITM = DmgType.SITM
AD_SEDU = DmgType.SEDU
AD_TLPT = DmgType.TLPT
AD_RUST = DmgType.RUST
AD_CONF = DmgType.CONF
AD_DGST = DmgType.DGST
AD_HEAL = DmgType.HEAL
AD_WRAP = DmgType.WRAP
AD_WERE = DmgType.WERE
AD_DRDX = DmgType.DRDX
AD_DRCO = DmgType.DRCO
AD_DRIN = DmgType.DRIN
AD_DISE = DmgType.DISE
AD_DCAY = DmgType.DCAY
AD_SSEX = DmgType.SSEX
AD_HALU = DmgType.HALU
AD_DETH = DmgType.DETH
AD_PEST = DmgType.PEST
AD_FAMN = DmgType.FAMN
AD_SLIM = DmgType.SLIM
AD_ENCH = DmgType.ENCH
AD_CORR = DmgType.CORR
AD_POLY = DmgType.POLY
AD_CLRC = DmgType.CLRC
AD_SPEL = DmgType.SPEL
AD_RBRE = DmgType.RBRE
AD_SAMU = DmgType.SAMU
AD_CURS = DmgType.CURS


def distance_atk_type(atyp: AtkType) -> bool:
    """DISTANCE_ATTK_TYPE: spit / breath / magic / gaze (monattk.h)."""
    return atyp in (AT_SPIT, AT_BREA, AT_MAGC, AT_GAZE)


# ------------------------------------------------------------
# Resists / conveyances (monflag.h MR_*/MR2_*).
# C shares one bit space between mons[].mresists (resists) and
# mons[].mconveys (conveyed by eating).
# ------------------------------------------------------------

class MR(IntFlag):
    """Resistance/conveyance bits (C: MR_* resists, MR2_* conveys)."""
    FIRE = 0x01
    COLD = 0x02
    SLEEP = 0x04
    DISINT = 0x08
    ELEC = 0x10
    POISON = 0x20
    ACID = 0x40
    STONE = 0x80
    SEE_INVIS = 0x0100
    LEVITATE = 0x0200
    WATERWALK = 0x0400
    MAGBREATH = 0x0800
    DISPLACED = 0x1000
    STRENGTH = 0x2000
    FUMBLING = 0x4000


MR_FIRE = MR.FIRE
MR_COLD = MR.COLD
MR_SLEEP = MR.SLEEP
MR_DISINT = MR.DISINT
MR_ELEC = MR.ELEC
MR_POISON = MR.POISON
MR_ACID = MR.ACID
MR_STONE = MR.STONE
MR2_SEE_INVIS = MR.SEE_INVIS
MR2_LEVITATE = MR.LEVITATE
MR2_WATERWALK = MR.WATERWALK
MR2_MAGBREATH = MR.MAGBREATH
MR2_DISPLACED = MR.DISPLACED
MR2_STRENGTH = MR.STRENGTH
MR2_FUMBLING = MR.FUMBLING

# ------------------------------------------------------------
# Flag bitmaps (monflag.h M1_*/M2_*/M3_*).
# The C-defined combined masks (M1_NOLIMBS, M1_OMNIVORE,
# M3_WANTSALL, M3_COVETOUS, M3_WAITMASK) are kept as members too:
# in IntFlag a value that is a combination of earlier members is a
# named alias of that combination, exactly like the C #defines.
# ------------------------------------------------------------

class M1(IntFlag):
    """mflags1 bits (C: M1_*)."""
    FLY = 0x00000001
    SWIM = 0x00000002
    AMORPHOUS = 0x00000004
    WALLWALK = 0x00000008
    CLING = 0x00000010
    TUNNEL = 0x00000020
    NEEDPICK = 0x00000040
    CONCEAL = 0x00000080
    HIDE = 0x000100
    AMPHIBIOUS = 0x000200
    BREATHLESS = 0x000400
    NOTAKE = 0x000800
    NOEYES = 0x00001000
    NOHANDS = 0x00002000
    NOLIMBS = NOEYES | NOHANDS
    NOHEAD = 0x00008000
    MINDLESS = 0x00010000
    HUMANOID = 0x00020000
    ANIMAL = 0x00040000
    SLITHY = 0x00080000
    UNSOLID = 0x00100000
    THICK_HIDE = 0x00200000
    OVIPAROUS = 0x00400000
    REGEN = 0x00800000
    SEE_INVIS = 0x01000000
    TPORT = 0x02000000
    TPORT_CNTRL = 0x04000000
    ACID = 0x08000000
    POIS = 0x10000000
    CARNIVORE = 0x20000000
    HERBIVORE = 0x40000000
    OMNIVORE = CARNIVORE | HERBIVORE
    METALLIVORE = 0x80000000


M1_FLY = M1.FLY
M1_SWIM = M1.SWIM
M1_AMORPHOUS = M1.AMORPHOUS
M1_WALLWALK = M1.WALLWALK
M1_CLING = M1.CLING
M1_TUNNEL = M1.TUNNEL
M1_NEEDPICK = M1.NEEDPICK
M1_CONCEAL = M1.CONCEAL
M1_HIDE = M1.HIDE
M1_AMPHIBIOUS = M1.AMPHIBIOUS
M1_BREATHLESS = M1.BREATHLESS
M1_NOTAKE = M1.NOTAKE
M1_NOEYES = M1.NOEYES
M1_NOHANDS = M1.NOHANDS
M1_NOLIMBS = M1.NOLIMBS
M1_NOHEAD = M1.NOHEAD
M1_MINDLESS = M1.MINDLESS
M1_HUMANOID = M1.HUMANOID
M1_ANIMAL = M1.ANIMAL
M1_SLITHY = M1.SLITHY
M1_UNSOLID = M1.UNSOLID
M1_THICK_HIDE = M1.THICK_HIDE
M1_OVIPAROUS = M1.OVIPAROUS
M1_REGEN = M1.REGEN
M1_SEE_INVIS = M1.SEE_INVIS
M1_TPORT = M1.TPORT
M1_TPORT_CNTRL = M1.TPORT_CNTRL
M1_ACID = M1.ACID
M1_POIS = M1.POIS
M1_CARNIVORE = M1.CARNIVORE
M1_HERBIVORE = M1.HERBIVORE
M1_OMNIVORE = M1.OMNIVORE
M1_METALLIVORE = M1.METALLIVORE


class M2(IntFlag):
    """mflags2 bits (C: M2_*)."""
    NOPOLY = 0x00000001
    UNDEAD = 0x00000002
    WERE = 0x00000004
    HUMAN = 0x00000008
    ELF = 0x00000010
    DWARF = 0x00000020
    GNOME = 0x00000040
    ORC = 0x00000080
    DEMON = 0x00000100
    MERC = 0x00000200
    LORD = 0x00000400
    PRINCE = 0x00000800
    MINION = 0x00001000
    GIANT = 0x00002000
    SHAPESHIFTER = 0x00004000
    MALE = 0x00010000
    FEMALE = 0x00020000
    NEUTER = 0x00040000
    PNAME = 0x00080000
    HOSTILE = 0x00100000
    PEACEFUL = 0x00200000
    DOMESTIC = 0x00400000
    WANDER = 0x00800000
    STALK = 0x01000000
    NASTY = 0x02000000
    STRONG = 0x04000000
    ROCKTHROW = 0x08000000
    GREEDY = 0x10000000
    JEWELS = 0x20000000
    COLLECT = 0x40000000
    MAGIC = 0x80000000


M2_NOPOLY = M2.NOPOLY
M2_UNDEAD = M2.UNDEAD
M2_WERE = M2.WERE
M2_HUMAN = M2.HUMAN
M2_ELF = M2.ELF
M2_DWARF = M2.DWARF
M2_GNOME = M2.GNOME
M2_ORC = M2.ORC
M2_DEMON = M2.DEMON
M2_MERC = M2.MERC
M2_LORD = M2.LORD
M2_PRINCE = M2.PRINCE
M2_MINION = M2.MINION
M2_GIANT = M2.GIANT
M2_SHAPESHIFTER = M2.SHAPESHIFTER
M2_MALE = M2.MALE
M2_FEMALE = M2.FEMALE
M2_NEUTER = M2.NEUTER
M2_PNAME = M2.PNAME
M2_HOSTILE = M2.HOSTILE
M2_PEACEFUL = M2.PEACEFUL
M2_DOMESTIC = M2.DOMESTIC
M2_WANDER = M2.WANDER
M2_STALK = M2.STALK
M2_NASTY = M2.NASTY
M2_STRONG = M2.STRONG
M2_ROCKTHROW = M2.ROCKTHROW
M2_GREEDY = M2.GREEDY
M2_JEWELS = M2.JEWELS
M2_COLLECT = M2.COLLECT
M2_MAGIC = M2.MAGIC


class M3(IntFlag):
    """mflags3 bits (C: M3_*)."""
    WANTSAMUL = 0x0001
    WANTSBELL = 0x0002
    WANTSBOOK = 0x0004
    WANTSCAND = 0x0008
    WANTSARTI = 0x0010
    WANTSALL = WANTSAMUL | WANTSBELL | WANTSBOOK | WANTSCAND | WANTSARTI
    WAITFORU = 0x0040
    CLOSE = 0x0080
    COVETOUS = 0x001f  # == WANTSALL (C defines the same value twice)
    WAITMASK = WAITFORU | CLOSE
    INFRAVISION = 0x0100
    INFRAVISIBLE = 0x0200
    DISPLACES = 0x0400


M3_WANTSAMUL = M3.WANTSAMUL
M3_WANTSBELL = M3.WANTSBELL
M3_WANTSBOOK = M3.WANTSBOOK
M3_WANTSCAND = M3.WANTSCAND
M3_WANTSARTI = M3.WANTSARTI
M3_WANTSALL = M3.WANTSALL
M3_WAITFORU = M3.WAITFORU
M3_CLOSE = M3.CLOSE
M3_COVETOUS = M3.COVETOUS
M3_WAITMASK = M3.WAITMASK
M3_INFRAVISION = M3.INFRAVISION
M3_INFRAVISIBLE = M3.INFRAVISIBLE
M3_DISPLACES = M3.DISPLACES

# ------------------------------------------------------------
# Size, sound, weight, alignment, gender (monflag.h / ms_sounds /
# weight.h / align.h)
# ------------------------------------------------------------

class MSize(IntEnum):
    """Physical size (C: MZ_*; permonst.msize is 3 bits)."""
    TINY = 0
    SMALL = 1
    MEDIUM = 2
    HUMAN = MEDIUM  # human-sized (C: MZ_HUMAN MZ_MEDIUM)
    LARGE = 3
    HUGE = 4
    GIGANTIC = 7


MZ_TINY = MSize.TINY
MZ_SMALL = MSize.SMALL
MZ_MEDIUM = MSize.MEDIUM
MZ_HUMAN = MSize.HUMAN
MZ_LARGE = MSize.LARGE
MZ_HUGE = MSize.HUGE
MZ_GIGANTIC = MSize.GIGANTIC


class MSound(IntEnum):
    """Sound made (C: enum ms_sounds; permonst.msound is 6 bits)."""
    SILENT = 0
    BARK = 1
    MEW = 2
    ROAR = 3
    BELLOW = 4
    GROWL = 5
    SQEEK = 6
    SQAWK = 7
    CHIRP = 8
    HISS = 9
    BUZZ = 10
    GRUNT = 11
    NEIGH = 12
    MOO = 13
    WAIL = 14
    GURGLE = 15
    BURBLE = 16
    TRUMPET = 17
    ANIMAL = TRUMPET  # "up to here are animal noises" (C: MS_ANIMAL)
    SHRIEK = 18
    BONES = 19
    LAUGH = 20
    MUMBLE = 21
    IMITATE = 22
    WERE = 23
    ORC = 24
    HUMANOID = 25
    ARREST = 26
    SOLDIER = 27
    GUARD = 28
    DJINNI = 29
    NURSE = 30
    SEDUCE = 31
    VAMPIRE = 32
    BRIBE = 33
    CUSS = 34
    RIDER = 35
    LEADER = 36
    NEMESIS = 37
    GUARDIAN = 38
    SELL = 39
    ORACLE = 40
    PRIEST = 41
    SPELL = 42
    BOAST = 43
    GROAN = 44
    FERRY = 45  # see module docstring: not in the pinned monflag.h


MS_SILENT = MSound.SILENT
MS_BARK = MSound.BARK
MS_MEW = MSound.MEW
MS_ROAR = MSound.ROAR
MS_BELLOW = MSound.BELLOW
MS_GROWL = MSound.GROWL
MS_SQEEK = MSound.SQEEK
MS_SQAWK = MSound.SQAWK
MS_CHIRP = MSound.CHIRP
MS_HISS = MSound.HISS
MS_BUZZ = MSound.BUZZ
MS_GRUNT = MSound.GRUNT
MS_NEIGH = MSound.NEIGH
MS_MOO = MSound.MOO
MS_WAIL = MSound.WAIL
MS_GURGLE = MSound.GURGLE
MS_BURBLE = MSound.BURBLE
MS_TRUMPET = MSound.TRUMPET
MS_ANIMAL = MSound.ANIMAL
MS_SHRIEK = MSound.SHRIEK
MS_BONES = MSound.BONES
MS_LAUGH = MSound.LAUGH
MS_MUMBLE = MSound.MUMBLE
MS_IMITATE = MSound.IMITATE
MS_WERE = MSound.WERE
MS_ORC = MSound.ORC
MS_HUMANOID = MSound.HUMANOID
MS_ARREST = MSound.ARREST
MS_SOLDIER = MSound.SOLDIER
MS_GUARD = MSound.GUARD
MS_DJINNI = MSound.DJINNI
MS_NURSE = MSound.NURSE
MS_SEDUCE = MSound.SEDUCE
MS_VAMPIRE = MSound.VAMPIRE
MS_BRIBE = MSound.BRIBE
MS_CUSS = MSound.CUSS
MS_RIDER = MSound.RIDER
MS_LEADER = MSound.LEADER
MS_NEMESIS = MSound.NEMESIS
MS_GUARDIAN = MSound.GUARDIAN
MS_SELL = MSound.SELL
MS_ORACLE = MSound.ORACLE
MS_PRIEST = MSound.PRIEST
MS_SPELL = MSound.SPELL
MS_BOAST = MSound.BOAST
MS_GROAN = MSound.GROAN
MS_FERRY = MSound.FERRY

# monster body weights (weight.h; named constants, not an enum)
WT_ETHEREAL = 0
WT_JELLY = 50
WT_ELF = 800
WT_HUMAN = 1450
WT_BABY_DRAGON = 1500
WT_DRAGON = 4500
WT_NYMPH = 600

# alignment (align.h).  A_* are the bounds of the aligntyp scale, not
# a closed set: permonst.maligntyp stores degrees (e.g. -7, 4), so it
# stays a plain int.
A_NONE = -128
A_CHAOTIC = -1
A_NEUTRAL = 0
A_LAWFUL = 1

NORMAL_SPEED = 12


class MGender(IntEnum):
    """Name gender (C: enum mgender)."""
    MALE = 0
    FEMALE = 1
    NEUTRAL = 2


MALE = MGender.MALE
FEMALE = MGender.FEMALE
NEUTRAL = MGender.NEUTRAL
NUM_MGENDERS = 3

# monster race aliases (monflag.h MH_*, == the M2_* kind bits)
MH_HUMAN = M2.HUMAN
MH_ELF = M2.ELF
MH_DWARF = M2.DWARF
MH_GNOME = M2.GNOME
MH_ORC = M2.ORC

# ------------------------------------------------------------
# Genocide / generation masks (monflag.h G_*) -- two bit spaces:
# mons[].geno (constant during the game) and mvitals[].mvflags
# (variant during the game, along with G_NOCORPSE).
# ------------------------------------------------------------

class Geno(IntFlag):
    """mons[].geno bits (C: G_*, the constant part)."""
    UNIQ = 0x1000
    NOHELL = 0x0800
    HELL = 0x0400
    NOGEN = 0x0200
    SGROUP = 0x0080
    LGROUP = 0x0040
    GENO = 0x0020
    NOCORPSE = 0x0010
    IGNORE = 0x8000  # mkclass() argument; never stored in mons[].geno


G_UNIQ = Geno.UNIQ
G_NOHELL = Geno.NOHELL
G_HELL = Geno.HELL
G_NOGEN = Geno.NOGEN
G_SGROUP = Geno.SGROUP
G_LGROUP = Geno.LGROUP
G_GENO = Geno.GENO
G_NOCORPSE = Geno.NOCORPSE
G_IGNORE = Geno.IGNORE
G_FREQ = 0x0007  # creation frequency mask, not a flag

# mvitals flags (variant during the game)
class MvitalsFlag(IntFlag):
    """mvitals[].mvflags bits (C: G_KNOWN & friends, monflag.h)."""
    EXTINCT = 0x01
    GENOD = 0x02
    KNOWN = 0x04
    KNOWS_EGG = 0x08  # C: MV_KNOWS_EGG
    GONE = GENOD | EXTINCT


G_KNOWN = MvitalsFlag.KNOWN
G_GENOD = MvitalsFlag.GENOD
G_EXTINCT = MvitalsFlag.EXTINCT
G_GONE = MvitalsFlag.GONE
MV_KNOWS_EGG = MvitalsFlag.KNOWS_EGG

# ------------------------------------------------------------
# Monster numbering (permonst.h enum monnums)
# ------------------------------------------------------------

NON_PM = -1
LOW_PM = NON_PM + 1          # 0
LEAVESTATUE = NON_PM - 1     # -2


# ------------------------------------------------------------
# Structures (permonst.h)
# ------------------------------------------------------------

@dataclass(frozen=True)
class Attack:
    """One attack form (C: struct attack)."""
    aatyp: AtkType
    adtyp: DmgType
    damn: int
    damd: int


@dataclass(frozen=True)
class PerMonst:
    """One monster type (C: struct permonst, 5.0 field order).

    pmnames: (male, female, neutral); male/female are None for
    single-name monsters (C NAM()).
    maligntyp: alignment degree, not just A_* (the table stores
    values like -7 and 4), so a plain int.
    geno: Geno bits | G_FREQ (C: unsigned short).
    """
    pmnames: tuple[str | None, str | None, str]
    pmidx: int
    mlet: MonsterClass        # S_* class index (5.0)
    mlevel: int
    mmove: int
    ac: int
    mr: int
    maligntyp: int
    geno: int
    mattk: tuple[Attack, ...]
    cwt: int
    cnutrit: int
    msound: MSound
    msize: MSize
    mresists: MR
    mconveys: MR
    mflags1: M1
    mflags2: M2
    mflags3: M3
    difficulty: int
    mcolor: int


NO_ATK = Attack(AtkType.NONE, DmgType.NONE, 0, 0)


def _nam(name: str) -> tuple[str | None, str | None, str]:
    return (None, None, name)


def _mon(pmidx, mlet, name, lvl, mov, ac, mr, aln, geno,
         a1, a2, a3, a4, a5, a6, wt, nut, snd, siz, res, conv,
         f1, f2, f3, diff, col) -> PerMonst:
    return PerMonst(
        _nam(name), pmidx, mlet, lvl, mov, ac, mr, aln, geno,
        (a1, a2, a3, a4, a5, a6), wt, nut, snd, siz, res, conv,
        f1, f2, f3, diff, col,
    )


# ------------------------------------------------------------
# The complete C ordering (all 383 types, default build).
# Recorded so the PM_ numbering is fixed for the later completion
# pass of the remaining ~90% of monsters.h.
# ------------------------------------------------------------

PM_NAMES: tuple[str, ...] = (
    "giant ant", "killer bee", "soldier ant", "fire ant",
    "giant beetle", "queen bee",
    "acid blob", "quivering blob", "gelatinous cube",
    "chickatrice", "cockatrice", "pyrolisk",
    "jackal", "fox", "coyote", "werejackal", "little dog", "dingo",
    "dog", "large dog", "wolf", "werewolf", "winter wolf cub", "warg",
    "winter wolf", "hell hound pup", "hell hound",
    "gas spore", "floating eye", "freezing sphere", "flaming sphere",
    "shocking sphere",
    "kitten", "housecat", "jaguar", "lynx", "panther", "large cat",
    "tiger", "displacer beast",
    "gremlin", "gargoyle", "winged gargoyle",
    "hobbit", "dwarf", "bugbear", "dwarf leader", "dwarf ruler",
    "mind flayer", "master mind flayer",
    "manes", "homunculus", "imp", "lemure", "quasit", "tengu",
    "blue jelly", "spotted jelly", "ochre jelly",
    "kobold", "large kobold", "kobold leader", "kobold shaman",
    "leprechaun",
    "small mimic", "large mimic", "giant mimic",
    "wood nymph", "water nymph", "mountain nymph",
    "goblin", "hobgoblin", "orc", "hill orc", "Mordor orc",
    "Uruk-hai", "orc shaman", "orc-captain",
    "rock piercer", "iron piercer", "glass piercer",
    "rothe", "mumak", "leocrotta", "wumpus", "titanothere",
    "baluchitherium", "mastodon",
    "sewer rat", "giant rat", "rabid rat", "wererat", "rock mole",
    "woodchuck",
    "cave spider", "centipede", "giant spider", "scorpion",
    "lurker above", "trapper",
    "pony", "white unicorn", "gray unicorn", "black unicorn",
    "horse", "warhorse",
    "fog cloud", "dust vortex", "ice vortex", "energy vortex",
    "steam vortex", "fire vortex",
    "baby long worm", "baby purple worm", "long worm", "purple worm",
    "grid bug", "xan",
    "yellow light", "black light",
    "zruty",
    "couatl", "Aleax", "Angel", "ki-rin", "Archon",
    "bat", "giant bat", "raven", "vampire bat",
    "plains centaur", "forest centaur", "mountain centaur",
    "baby gray dragon", "baby gold dragon", "baby silver dragon",
    "baby red dragon", "baby white dragon", "baby orange dragon",
    "baby black dragon", "baby blue dragon", "baby green dragon",
    "baby yellow dragon",
    "gray dragon", "gold dragon", "silver dragon", "red dragon",
    "white dragon", "orange dragon", "black dragon", "blue dragon",
    "green dragon", "yellow dragon",
    "stalker", "air elemental", "fire elemental", "earth elemental",
    "water elemental",
    "lichen", "brown mold", "yellow mold", "green mold", "red mold",
    "shrieker", "violet fungus",
    "gnome", "gnome leader", "gnomish wizard", "gnome ruler",
    "giant", "stone giant", "hill giant", "fire giant", "frost giant",
    "ettin", "storm giant", "titan", "minotaur",
    "jabberwock",
    "Keystone Kop", "Kop Sergeant", "Kop Lieutenant", "Kop Kaptain",
    "lich", "demilich", "master lich", "arch-lich",
    "kobold mummy", "gnome mummy", "orc mummy", "dwarf mummy",
    "elf mummy", "human mummy", "ettin mummy", "giant mummy",
    "red naga hatchling", "black naga hatchling",
    "golden naga hatchling", "guardian naga hatchling", "red naga",
    "black naga", "golden naga", "guardian naga",
    "ogre", "ogre leader", "ogre tyrant",
    "gray ooze", "brown pudding", "green slime", "black pudding",
    "quantum mechanic", "genetic engineer",
    "rust monster", "disenchanter",
    "garter snake", "snake", "water moccasin", "python", "pit viper",
    "cobra",
    "troll", "ice troll", "rock troll", "water troll", "Olog-hai",
    "umber hulk",
    "vampire", "vampire leader", "Vlad the Impaler",
    "barrow wight", "wraith", "Nazgul",
    "xorn",
    "monkey", "ape", "owlbear", "yeti", "carnivorous ape",
    "sasquatch",
    "kobold zombie", "gnome zombie", "orc zombie", "dwarf zombie",
    "elf zombie", "human zombie", "ettin zombie", "ghoul",
    "giant zombie", "skeleton",
    "straw golem", "paper golem", "rope golem", "gold golem",
    "leather golem", "wood golem", "flesh golem", "clay golem",
    "stone golem", "glass golem", "iron golem",
    "human", "wererat", "werejackal", "werewolf", "elf",
    "Woodland-elf", "Green-elf", "Grey-elf", "elf-noble",
    "elven monarch", "doppelganger", "shopkeeper", "guard",
    "prisoner", "Oracle", "aligned cleric", "high cleric",
    "soldier", "sergeant", "nurse", "lieutenant", "captain",
    "watchman", "watch captain", "Medusa", "Wizard of Yendor",
    "Croesus",
    "ghost", "shade",
    "water demon", "amorous demon", "horned devil", "erinys",
    "barbed devil", "marilith", "vrock", "hezrou", "bone devil",
    "ice devil", "nalfeshnee", "pit fiend", "sandestin", "balrog",
    "Juiblex", "Yeenoghu", "Orcus", "Geryon", "Dispater",
    "Baalzebub", "Asmodeus", "Demogorgon",
    "Death", "Pestilence", "Famine",
    "mail daemon",  # MAIL_STRUCTURES is always defined in 5.0
    "djinni",
    "jellyfish", "piranha", "shark", "giant eel", "electric eel",
    "kraken",
    "newt", "gecko", "iguana", "baby crocodile", "lizard",
    "chameleon", "crocodile", "salamander",
    "long worm tail",
    # ---- from here on: G_NOGEN | M2_NOPOLY (special) section ----
    "archeologist", "barbarian", "cave dweller", "healer", "knight",
    "monk", "cleric", "ranger", "rogue", "samurai", "tourist",
    "valkyrie", "wizard",
    "Lord Carnarvon", "Pelias", "Shaman Karnov", "Hippocrates",
    "King Arthur", "Grand Master", "Arch Priest", "Orion",
    "Master of Thieves", "Lord Sato", "Twoflower", "Norn",
    "Neferet the Green",
    "Minion of Huhetotl", "Thoth Amon", "Chromatic Dragon",
    "Cyclops", "Ixoth", "Master Kaen", "Nalzok", "Scorpius",
    "Master Assassin", "Ashikaga Takauji", "Lord Surtur",
    "Dark One",
    "student", "chieftain", "neanderthal", "attendant", "page",
    "abbot", "acolyte", "hunter", "thug", "ninja", "roshi", "guide",
    "warrior", "apprentice",
)

NUMMONS = 383
HIGH_PM = NUMMONS - 1
# mons[SPECIAL_PM..HIGH_PM] are never generated randomly and cannot be
# polymorphed into (permonst.h)
SPECIAL_PM = 330

# PM_ identifiers the game code refers to (subset + anchors)
PM_COCKATRICE = 10
PM_IMP = 52
PM_QUASIT = 54
PM_KOBOLD = 59
PM_LARGE_KOBOLD = 60
PM_LEPRECHAUN = 63
PM_LARGE_MIMIC = 65
PM_WOOD_NYMPH = 67
PM_GOBLIN = 70
PM_HOBGOBLIN = 71
PM_HILL_ORC = 73
PM_SEWER_RAT = 88
PM_GIANT_RAT = 89
PM_CAVE_SPIDER = 94
PM_CENTIPEDE = 95
PM_GIANT_SPIDER = 96
PM_XAN = 117
PM_YELLOW_LIGHT = 118
PM_ZRUTY = 120
PM_BAT = 126
PM_GIANT_BAT = 127
PM_GRAY_DRAGON = 143
PM_BLACK_DRAGON = 149
PM_YELLOW_DRAGON = 152
PM_FIRE_ELEMENTAL = 155
PM_HILL_GIANT = 171
PM_OGRE = 203
PM_GARTER_SNAKE = 214
PM_SNAKE = 215
PM_TROLL = 220
PM_VAMPIRE = 226
PM_WRAITH = 230
PM_OWLBEAR = 235
PM_KOBOLD_ZOMBIE = 239
PM_HUMAN_ZOMBIE = 244
PM_GHOUL = 246
PM_SKELETON = 248
PM_FLESH_GOLEM = 255
PM_STONE_GOLEM = 257
PM_GHOST = 287
PM_MAIL_DAEMON = 314
PM_LONG_WORM_TAIL = 330

SUBSET_PM = (
    PM_COCKATRICE, PM_IMP, PM_QUASIT, PM_KOBOLD, PM_LARGE_KOBOLD,
    PM_LEPRECHAUN, PM_LARGE_MIMIC, PM_WOOD_NYMPH, PM_GOBLIN,
    PM_HOBGOBLIN, PM_HILL_ORC, PM_SEWER_RAT, PM_GIANT_RAT,
    PM_CAVE_SPIDER, PM_CENTIPEDE, PM_GIANT_SPIDER, PM_XAN,
    PM_YELLOW_LIGHT, PM_ZRUTY, PM_BAT, PM_GIANT_BAT, PM_GRAY_DRAGON,
    PM_BLACK_DRAGON, PM_FIRE_ELEMENTAL, PM_HILL_GIANT, PM_OGRE,
    PM_GARTER_SNAKE, PM_SNAKE, PM_TROLL, PM_VAMPIRE, PM_WRAITH,
    PM_OWLBEAR, PM_KOBOLD_ZOMBIE, PM_HUMAN_ZOMBIE, PM_GHOUL,
    PM_SKELETON, PM_FLESH_GOLEM, PM_STONE_GOLEM, PM_GHOST,
    PM_LONG_WORM_TAIL,
)

# ------------------------------------------------------------
# The table (core subset; C field order, auditable vs monsters.h)
# ------------------------------------------------------------

MONS: list[PerMonst | None] = [None] * NUMMONS

MONS[PM_COCKATRICE] = _mon(
    10, S_COCKATRICE, "cockatrice",
    5, 6, 6, 30, 0, G_GENO | 5,
    Attack(AT_BITE, AD_PHYS, 1, 3), Attack(AT_TUCH, AD_STON, 0, 0),
    Attack(AT_NONE, AD_STON, 0, 0), NO_ATK, NO_ATK, NO_ATK,
    30, 30, MS_HISS, MZ_SMALL,
    MR_POISON | MR_STONE, MR_POISON | MR_STONE,
    M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS, M2_HOSTILE,
    M3_INFRAVISIBLE, 8, 11)

MONS[PM_IMP] = _mon(
    52, S_IMP, "imp",
    3, 12, 2, 20, -7, G_GENO | 1,
    Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    20, 10, MS_CUSS, MZ_TINY, 0, 0,
    M1_REGEN, M2_WANDER | M2_STALK,
    M3_INFRAVISIBLE | M3_INFRAVISION, 4, 1)

MONS[PM_QUASIT] = _mon(
    54, S_IMP, "quasit",
    3, 15, 2, 20, -7, G_GENO | 2,
    Attack(AT_CLAW, AD_DRDX, 1, 2), Attack(AT_CLAW, AD_DRDX, 1, 2),
    Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK,
    200, 200, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
    M1_REGEN, M2_STALK,
    M3_INFRAVISIBLE | M3_INFRAVISION, 7, 4)

MONS[PM_KOBOLD] = _mon(
    59, S_KOBOLD, "kobold",
    0, 6, 10, 0, -2, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    400, 100, MS_ORC, MZ_SMALL, MR_POISON, 0,
    M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 1, 3)

MONS[PM_LARGE_KOBOLD] = _mon(
    60, S_KOBOLD, "large kobold",
    1, 6, 10, 0, -3, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    450, 150, MS_ORC, MZ_SMALL, MR_POISON, 0,
    M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 2, 1)

MONS[PM_LEPRECHAUN] = _mon(
    63, S_LEPRECHAUN, "leprechaun",
    5, 15, 8, 20, 0, G_GENO | 4,
    Attack(AT_CLAW, AD_SGLD, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    60, 30, MS_LAUGH, MZ_TINY, 0, 0,
    M1_HUMANOID | M1_TPORT, M2_HOSTILE | M2_GREEDY,
    M3_INFRAVISIBLE, 4, 2)

MONS[PM_LARGE_MIMIC] = _mon(
    65, S_MIMIC, "large mimic",
    8, 3, 7, 10, 0, G_GENO | 1,
    Attack(AT_CLAW, AD_STCK, 3, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    600, 400, MS_SILENT, MZ_LARGE, MR_ACID, 0,
    M1_CLING | M1_BREATHLESS | M1_AMORPHOUS | M1_HIDE | M1_ANIMAL
        | M1_NOEYES | M1_NOHEAD | M1_NOLIMBS | M1_THICK_HIDE
        | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG, 0, 9, 1)

MONS[PM_WOOD_NYMPH] = _mon(
    67, S_NYMPH, "wood nymph",
    3, 12, 9, 20, 0, G_GENO | 2,
    Attack(AT_CLAW, AD_SITM, 0, 0), Attack(AT_CLAW, AD_SEDU, 0, 0),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_NYMPH, 300, MS_SEDUCE, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_TPORT, M2_HOSTILE | M2_FEMALE | M2_COLLECT,
    M3_INFRAVISIBLE, 5, 2)

MONS[PM_GOBLIN] = _mon(
    70, S_ORC, "goblin",
    0, 6, 10, 0, -3, G_GENO | 2,
    Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    400, 100, MS_ORC, MZ_SMALL, 0, 0,
    M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 1, 7)

MONS[PM_HOBGOBLIN] = _mon(
    71, S_ORC, "hobgoblin",
    1, 9, 10, 0, -4, G_GENO | 2,
    Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1000, 200, MS_ORC, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 3, 3)

MONS[PM_HILL_ORC] = _mon(
    73, S_ORC, "hill orc",
    2, 9, 10, 0, -4, G_GENO | G_LGROUP | 2,
    Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1000, 200, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 4, 11)

MONS[PM_SEWER_RAT] = _mon(
    88, S_RODENT, "sewer rat",
    0, 12, 7, 0, 0, G_GENO | G_SGROUP | 1,
    Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    20, 12, MS_SQEEK, MZ_TINY, 0, 0,
    M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
    M3_INFRAVISIBLE, 1, 3)

MONS[PM_GIANT_RAT] = _mon(
    89, S_RODENT, "giant rat",
    1, 10, 7, 0, 0, G_GENO | G_SGROUP | 2,
    Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 30, MS_SQEEK, MZ_TINY, 0, 0,
    M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
    M3_INFRAVISIBLE, 2, 3)

MONS[PM_CAVE_SPIDER] = _mon(
    94, S_SPIDER, "cave spider",
    1, 12, 3, 0, 0, G_GENO | G_SGROUP | 2,
    Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    50, 50, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
    M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
    M2_HOSTILE, 0, 3, 7)

MONS[PM_CENTIPEDE] = _mon(
    95, S_SPIDER, "centipede",
    2, 4, 3, 0, 0, G_GENO | 1,
    Attack(AT_BITE, AD_DRST, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    50, 50, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
    M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
    M2_HOSTILE, 0, 4, 11)

MONS[PM_GIANT_SPIDER] = _mon(
    96, S_SPIDER, "giant spider",
    5, 15, 4, 0, 0, G_GENO | 1,
    Attack(AT_BITE, AD_DRST, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    200, 100, MS_SILENT, MZ_LARGE, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG, 0, 7, 5)

MONS[PM_XAN] = _mon(
    117, S_XAN, "xan",
    7, 18, -4, 0, 0, G_GENO | 3,
    Attack(AT_STNG, AD_LEGS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    300, 300, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
    M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_POIS, M2_HOSTILE,
    M3_INFRAVISIBLE, 9, 1)

MONS[PM_YELLOW_LIGHT] = _mon(
    118, S_LIGHT, "yellow light",
    3, 15, 0, 0, 0, G_NOCORPSE | G_GENO | 4,
    Attack(AT_EXPL, AD_BLND, 10, 20), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_ETHEREAL, 0, MS_SILENT, MZ_SMALL,
    MR_FIRE | MR_COLD | MR_ELEC | MR_DISINT | MR_SLEEP | MR_POISON
        | MR_ACID | MR_STONE,
    0,
    M1_FLY | M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS
        | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID | M1_NOTAKE,
    M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 5, 11)

MONS[PM_ZRUTY] = _mon(
    120, S_ZRUTY, "zruty",
    9, 8, 3, 0, 0, G_GENO | 2,
    Attack(AT_CLAW, AD_PHYS, 3, 4), Attack(AT_CLAW, AD_PHYS, 3, 4),
    Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK,
    1200, 600, MS_SILENT, MZ_LARGE, 0, 0,
    M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE, M2_HOSTILE | M2_STRONG,
    M3_INFRAVISIBLE, 11, 3)

MONS[PM_BAT] = _mon(
    126, S_BAT, "bat",
    0, 22, 8, 0, 0, G_GENO | G_SGROUP | 1,
    Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    20, 20, MS_SQEEK, MZ_TINY, 0, 0,
    M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_WANDER,
    M3_INFRAVISIBLE, 2, 3)

MONS[PM_GIANT_BAT] = _mon(
    127, S_BAT, "giant bat",
    2, 22, 7, 0, 0, G_GENO | 2,
    Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 30, MS_SQEEK, MZ_SMALL, 0, 0,
    M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE,
    M2_WANDER | M2_HOSTILE, M3_INFRAVISIBLE, 3, 1)

MONS[PM_GRAY_DRAGON] = _mon(
    143, S_DRAGON, "gray dragon",
    15, 9, -1, 20, 4, G_GENO | 1,
    Attack(AT_BREA, AD_MAGM, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
    Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
    NO_ATK, NO_ATK,
    WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, 0, 0,
    M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS
        | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS
        | M2_MAGIC,
    0, 20, 7)

MONS[PM_BLACK_DRAGON] = _mon(
    149, S_DRAGON, "black dragon",
    15, 9, -1, 20, -6, G_GENO | 1,
    Attack(AT_BREA, AD_DISN, 1, 255), Attack(AT_BITE, AD_PHYS, 3, 8),
    Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
    NO_ATK, NO_ATK,
    WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_DISINT, MR_DISINT,
    M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS
        | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS
        | M2_MAGIC,
    0, 20, 0)

MONS[PM_FIRE_ELEMENTAL] = _mon(
    155, S_ELEMENTAL, "fire elemental",
    8, 12, 2, 30, 0, G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_FIRE, 3, 6), Attack(AT_NONE, AD_FIRE, 0, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
    MR_FIRE | MR_POISON | MR_STONE, 0,
    M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS
        | M1_UNSOLID | M1_FLY | M1_NOTAKE,
    M2_STRONG | M2_NEUTER, M3_INFRAVISIBLE, 10, 11)

MONS[PM_HILL_GIANT] = _mon(
    171, S_GIANT, "hill giant",
    8, 10, 6, 0, -2, G_GENO | G_SGROUP | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    2200, 700, MS_BOAST, MZ_HUGE, 0, 0,
    M1_HUMANOID | M1_CARNIVORE,
    M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT
        | M2_JEWELS,
    M3_INFRAVISIBLE | M3_INFRAVISION, 10, 6)

MONS[PM_OGRE] = _mon(
    203, S_OGRE, "ogre",
    5, 10, 5, 0, -3, G_SGROUP | G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 5), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1600, 500, MS_GRUNT, MZ_LARGE, 0, 0,
    M1_HUMANOID | M1_CARNIVORE,
    M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 7, 3)

MONS[PM_GARTER_SNAKE] = _mon(
    214, S_SNAKE, "garter snake",
    1, 8, 8, 0, 0, G_LGROUP | G_GENO | 1,
    Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    50, 60, MS_HISS, MZ_TINY, 0, 0,
    M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY
        | M1_OVIPAROUS | M1_CARNIVORE | M1_NOTAKE,
    0, 0, 3, 2)

MONS[PM_SNAKE] = _mon(
    215, S_SNAKE, "snake",
    4, 15, 3, 0, 0, G_GENO | 2,
    Attack(AT_BITE, AD_DRST, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    100, 80, MS_HISS, MZ_SMALL, MR_POISON, MR_POISON,
    M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS
        | M1_OVIPAROUS | M1_CARNIVORE | M1_NOTAKE,
    M2_HOSTILE, 0, 6, 3)

MONS[PM_TROLL] = _mon(
    220, S_TROLL, "troll",
    7, 12, 4, 0, -3, G_GENO | 2,
    Attack(AT_WEAP, AD_PHYS, 4, 2), Attack(AT_CLAW, AD_PHYS, 4, 2),
    Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
    800, 350, MS_GRUNT, MZ_LARGE, 0, 0,
    M1_HUMANOID | M1_REGEN | M1_CARNIVORE,
    M2_STRONG | M2_STALK | M2_HOSTILE,
    M3_INFRAVISIBLE | M3_INFRAVISION, 9, 3)

MONS[PM_VAMPIRE] = _mon(
    226, S_VAMPIRE, "vampire",
    10, 12, 1, 25, -8, G_GENO | G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_BITE, AD_DRLI, 1, 6),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_HUMAN, 400, MS_VAMPIRE, MZ_HUMAN, MR_SLEEP | MR_POISON, 0,
    M1_FLY | M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
    M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY
        | M2_SHAPESHIFTER,
    M3_INFRAVISIBLE, 12, 1)

MONS[PM_WRAITH] = _mon(
    230, S_WRAITH, "wraith",
    6, 12, 4, 15, -6, G_GENO | 2,
    Attack(AT_TUCH, AD_DRLI, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_ETHEREAL, 0, MS_SILENT, MZ_HUMAN,
    MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_BREATHLESS | M1_FLY | M1_HUMANOID | M1_UNSOLID,
    M2_UNDEAD | M2_STALK | M2_HOSTILE, 0, 8, 0)

MONS[PM_OWLBEAR] = _mon(
    235, S_YETI, "owlbear",
    5, 12, 5, 0, 0, G_GENO | 3,
    Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
    Attack(AT_HUGS, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK,
    1700, 700, MS_ROAR, MZ_LARGE, 0, 0,
    M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG | M2_NASTY, M3_INFRAVISIBLE, 7, 3)

MONS[PM_KOBOLD_ZOMBIE] = _mon(
    239, S_ZOMBIE, "kobold zombie",
    0, 6, 10, 0, -2, G_GENO | G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    400, 50, MS_GROAN, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
    M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION, 1, 3)

MONS[PM_HUMAN_ZOMBIE] = _mon(
    244, S_ZOMBIE, "human zombie",
    4, 6, 8, 0, -3, G_GENO | G_SGROUP | G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_HUMAN, 200, MS_GROAN, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON,
    0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
    M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION, 5, 15)

MONS[PM_GHOUL] = _mon(
    246, S_ZOMBIE, "ghoul",
    3, 6, 10, 0, -2, G_GENO | G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PLYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 3),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    400, 50, MS_SILENT, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS | M1_OMNIVORE,
    M2_UNDEAD | M2_WANDER | M2_HOSTILE, M3_INFRAVISION, 5, 0)

MONS[PM_SKELETON] = _mon(
    248, S_ZOMBIE, "skeleton",
    12, 8, 4, 0, 0, G_NOCORPSE | G_NOGEN,
    Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_TUCH, AD_SLOW, 1, 6),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    300, 5, MS_BONES, MZ_HUMAN,
    MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
    M2_UNDEAD | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_COLLECT
        | M2_NASTY,
    M3_INFRAVISION, 14, 15)

MONS[PM_FLESH_GOLEM] = _mon(
    255, S_GOLEM, "flesh golem",
    9, 8, 9, 30, 0, 1,
    Attack(AT_CLAW, AD_PHYS, 2, 8), Attack(AT_CLAW, AD_PHYS, 2, 8),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    1400, 600, MS_SILENT, MZ_LARGE,
    MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON,
    MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_STRONG,
    0, 10, 1)

MONS[PM_STONE_GOLEM] = _mon(
    257, S_GOLEM, "stone golem",
    14, 6, 5, 50, 0, G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PHYS, 3, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1900, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
    M2_HOSTILE | M2_STRONG, 0, 15, 7)

MONS[PM_GHOST] = _mon(
    287, S_GHOST, "ghost",
    10, 3, -5, 50, -5, G_NOCORPSE | G_NOGEN,
    Attack(AT_TUCH, AD_PHYS, 1, 1), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_HUMAN, 0, MS_SILENT, MZ_HUMAN,
    MR_COLD | MR_DISINT | MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_FLY | M1_BREATHLESS | M1_WALLWALK | M1_HUMANOID | M1_UNSOLID,
    M2_NOPOLY | M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION,
    12, 7)

# dummy monster for the visual interface; the anchor of the
# "never generated randomly" section (permonst.h SPECIAL_PM)
MONS[PM_LONG_WORM_TAIL] = _mon(
    330, S_WORM_TAIL, "long worm tail",
    0, 0, 0, 0, 0, G_NOGEN | G_NOCORPSE | G_UNIQ,
    NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    0, 0, 0, 0, 0, 0, 0, M2_NOPOLY, 0, 1, 3)


# ------------------------------------------------------------
# Accessors
# ------------------------------------------------------------

def monsndx(data: PerMonst) -> int:
    """The mons[] index of a monster type (C: monsndx)."""
    return data.pmidx


def monclass(data: PerMonst) -> MonsterClass:
    """The monster class (S_* index) of a monster type (C: monclass)."""
    return data.mlet


def defch(mcls: MonsterClass) -> str:
    """The default display character of a monster class."""
    return DEFCHARS[mcls]


def monname(data: PerMonst, mgender: MGender = NEUTRAL) -> str:
    """The name of a monster type for a gender (C: monname)."""
    return data.pmnames[mgender]


def is_golem(data: PerMonst) -> bool:
    return data.mlet == S_GOLEM


def is_dragon(data: PerMonst) -> bool:
    return data.mlet == S_DRAGON


# ------------------------------------------------------------
# Table validation (run by the test suite and `python -m core.monst`;
# deliberately NOT at import time)
# ------------------------------------------------------------

# bits a mons[].geno field may hold: the Geno flags plus the G_FREQ
# low bits (G_IGNORE is a mkclass() argument, never stored in the table)
_GENO_FIELD = (G_UNIQ | G_NOHELL | G_HELL | G_NOGEN | G_SGROUP
               | G_LGROUP | G_GENO | G_NOCORPSE | G_FREQ)
# the whole MR bit space (8 MR_* bits + 7 MR2_* bits; mresists/
# mconveys are uchar in C)
_MR_FIELD = 0x7FFF


def _validate() -> None:
    assert len(PM_NAMES) == NUMMONS, \
        f"PM_NAMES has {len(PM_NAMES)} entries, expected {NUMMONS}"
    # PM_ constants agree with the recorded ordering
    anchors = {
        PM_COCKATRICE: "cockatrice", PM_BAT: "bat",
        PM_GRAY_DRAGON: "gray dragon", PM_BLACK_DRAGON: "black dragon",
        PM_YELLOW_DRAGON: "yellow dragon", PM_GHOST: "ghost",
        PM_MAIL_DAEMON: "mail daemon",
        PM_LONG_WORM_TAIL: "long worm tail", PM_SKELETON: "skeleton",
    }
    for idx, name in anchors.items():
        assert PM_NAMES[idx] == name, (idx, PM_NAMES[idx], name)
    # the sparse table is consistent with its indices
    for idx, mon in enumerate(MONS):
        if mon is not None:
            assert mon.pmidx == idx, (idx, mon.pmidx)
    # exactly the subset is present
    present = {i for i, m in enumerate(MONS) if m is not None}
    assert present == set(SUBSET_PM)
    # the special section anchor
    assert MONS[SPECIAL_PM].mlet == S_WORM_TAIL
    assert MONS[SPECIAL_PM].pmnames[2] == "long worm tail"
    # adult dragon block: gray first, yellow last (defended() relies
    # on the range being 10 entries)
    assert PM_YELLOW_DRAGON - PM_GRAY_DRAGON + 1 == 10
    # every implemented monster has a name and a valid class, and
    # its fields fit the C field widths
    for idx in SUBSET_PM:
        m = MONS[idx]
        assert m.pmnames[2] == PM_NAMES[idx], (idx, m.pmnames[2])
        assert isinstance(m.mlet, MonsterClass)
        assert 1 <= m.mlet < MAXMCLASSES
        assert len(m.mattk) == NATTK
        for a in m.mattk:
            assert 0 <= a.aatyp <= 255
            assert 0 <= a.adtyp <= 255
        assert m.geno & ~_GENO_FIELD == 0
        assert m.mresists & ~_MR_FIELD == 0
        assert m.mconveys & ~_MR_FIELD == 0
        assert 0 <= m.mflags1 <= 0xFFFFFFFF
        assert 0 <= m.mflags2 <= 0xFFFFFFFF
        assert 0 <= m.mflags3 <= 0xFFFF
        assert 0 <= m.msound <= 63
        assert 0 <= m.msize <= 7
        for v in (m.mlevel, m.mmove, m.ac, m.mr):
            assert -128 <= v <= 127
        assert 0 <= m.cwt <= 0xFFFFFFFF
        assert 0 <= m.cnutrit <= 0xFFFF
        assert 0 <= m.difficulty <= 0xFF
        assert 0 <= m.mcolor <= 0xFF


if __name__ == "__main__":
    _validate()


__all__ = [
    # enum types
    "MonsterClass", "AtkType", "DmgType", "MR", "M1", "M2", "M3",
    "Geno", "MvitalsFlag", "MSize", "MSound", "MGender",
    # classes
    "S_ANT", "S_BLOB", "S_COCKATRICE", "S_DOG", "S_EYE", "S_FELINE",
    "S_GREMLIN", "S_HUMANOID", "S_IMP", "S_JELLY", "S_KOBOLD",
    "S_LEPRECHAUN", "S_MIMIC", "S_NYMPH", "S_ORC", "S_PIERCER",
    "S_QUADRUPED", "S_RODENT", "S_SPIDER", "S_TRAPPER", "S_UNICORN",
    "S_VORTEX", "S_WORM", "S_XAN", "S_LIGHT", "S_ZRUTY", "S_ANGEL",
    "S_BAT", "S_CENTAUR", "S_DRAGON", "S_ELEMENTAL", "S_FUNGUS",
    "S_GNOME", "S_GIANT", "S_INVISIBLE", "S_JABBERWOCK", "S_KOP",
    "S_LICH", "S_MUMMY", "S_NAGA", "S_OGRE", "S_PUDDING",
    "S_QUANTMECH", "S_RUSTMONST", "S_SNAKE", "S_TROLL", "S_UMBER",
    "S_VAMPIRE", "S_WRAITH", "S_XORN", "S_YETI", "S_ZOMBIE",
    "S_HUMAN", "S_GHOST", "S_GOLEM", "S_DEMON", "S_EEL", "S_LIZARD",
    "S_WORM_TAIL", "S_MIMIC_DEF", "MAXMCLASSES", "DEFCHARS",
    # attacks
    "AT_ANY", "AT_NONE", "AT_CLAW", "AT_BITE", "AT_KICK", "AT_BUTT",
    "AT_TUCH", "AT_STNG", "AT_HUGS", "AT_SPIT", "AT_ENGL", "AT_BREA",
    "AT_EXPL", "AT_BOOM", "AT_GAZE", "AT_TENT", "AT_WEAP", "AT_MAGC",
    "NATTK", "distance_atk_type",
    "AD_ANY", "AD_PHYS", "AD_MAGM", "AD_FIRE", "AD_COLD", "AD_SLEE",
    "AD_DISN", "AD_ELEC", "AD_DRST", "AD_ACID", "AD_SPC1", "AD_SPC2",
    "AD_BLND", "AD_STUN", "AD_SLOW", "AD_PLYS", "AD_DRLI", "AD_DREN",
    "AD_LEGS", "AD_STON", "AD_STCK", "AD_SGLD", "AD_SITM", "AD_SEDU",
    "AD_TLPT", "AD_RUST", "AD_CONF", "AD_DGST", "AD_HEAL", "AD_WRAP",
    "AD_WERE", "AD_DRDX", "AD_DRCO", "AD_DRIN", "AD_DISE", "AD_DCAY",
    "AD_SSEX", "AD_HALU", "AD_DETH", "AD_PEST", "AD_FAMN", "AD_SLIM",
    "AD_ENCH", "AD_CORR", "AD_POLY", "AD_CLRC", "AD_SPEL", "AD_RBRE",
    "AD_SAMU", "AD_CURS",
    # resists / flags / misc
    "MR_FIRE", "MR_COLD", "MR_SLEEP", "MR_DISINT", "MR_ELEC",
    "MR_POISON", "MR_ACID", "MR_STONE",
    "MR2_SEE_INVIS", "MR2_LEVITATE", "MR2_WATERWALK", "MR2_MAGBREATH",
    "MR2_DISPLACED", "MR2_STRENGTH", "MR2_FUMBLING",
    "M1_FLY", "M1_SWIM", "M1_AMORPHOUS", "M1_WALLWALK", "M1_CLING",
    "M1_TUNNEL", "M1_NEEDPICK", "M1_CONCEAL", "M1_HIDE",
    "M1_AMPHIBIOUS", "M1_BREATHLESS", "M1_NOTAKE", "M1_NOEYES",
    "M1_NOHANDS", "M1_NOLIMBS", "M1_NOHEAD", "M1_MINDLESS",
    "M1_HUMANOID", "M1_ANIMAL", "M1_SLITHY", "M1_UNSOLID",
    "M1_THICK_HIDE", "M1_OVIPAROUS", "M1_REGEN", "M1_SEE_INVIS",
    "M1_TPORT", "M1_TPORT_CNTRL", "M1_ACID", "M1_POIS",
    "M1_CARNIVORE", "M1_HERBIVORE", "M1_OMNIVORE", "M1_METALLIVORE",
    "M2_NOPOLY", "M2_UNDEAD", "M2_WERE", "M2_HUMAN", "M2_ELF",
    "M2_DWARF", "M2_GNOME", "M2_ORC", "M2_DEMON", "M2_MERC",
    "M2_LORD", "M2_PRINCE", "M2_MINION", "M2_GIANT",
    "M2_SHAPESHIFTER", "M2_MALE", "M2_FEMALE", "M2_NEUTER",
    "M2_PNAME", "M2_HOSTILE", "M2_PEACEFUL", "M2_DOMESTIC",
    "M2_WANDER", "M2_STALK", "M2_NASTY", "M2_STRONG",
    "M2_ROCKTHROW", "M2_GREEDY", "M2_JEWELS", "M2_COLLECT", "M2_MAGIC",
    "M3_WANTSAMUL", "M3_WANTSBELL", "M3_WANTSBOOK", "M3_WANTSCAND",
    "M3_WANTSARTI", "M3_WANTSALL", "M3_WAITFORU", "M3_CLOSE",
    "M3_COVETOUS", "M3_WAITMASK", "M3_INFRAVISION",
    "M3_INFRAVISIBLE", "M3_DISPLACES",
    "MZ_TINY", "MZ_SMALL", "MZ_MEDIUM", "MZ_HUMAN", "MZ_LARGE",
    "MZ_HUGE", "MZ_GIGANTIC",
    "MS_SILENT", "MS_BARK", "MS_MEW", "MS_ROAR", "MS_BELLOW",
    "MS_GROWL", "MS_SQEEK", "MS_SQAWK", "MS_CHIRP", "MS_HISS",
    "MS_BUZZ", "MS_GRUNT", "MS_NEIGH", "MS_MOO", "MS_WAIL",
    "MS_GURGLE", "MS_BURBLE", "MS_TRUMPET", "MS_ANIMAL", "MS_SHRIEK",
    "MS_BONES", "MS_LAUGH", "MS_MUMBLE", "MS_IMITATE", "MS_WERE",
    "MS_ORC", "MS_HUMANOID", "MS_ARREST", "MS_SOLDIER", "MS_GUARD",
    "MS_DJINNI", "MS_NURSE", "MS_SEDUCE", "MS_VAMPIRE", "MS_BRIBE",
    "MS_CUSS", "MS_RIDER", "MS_LEADER", "MS_NEMESIS", "MS_GUARDIAN",
    "MS_SELL", "MS_ORACLE", "MS_PRIEST", "MS_SPELL", "MS_BOAST",
    "MS_GROAN", "MS_FERRY",
    "WT_ETHEREAL", "WT_JELLY", "WT_ELF", "WT_HUMAN",
    "WT_BABY_DRAGON", "WT_DRAGON", "WT_NYMPH",
    "NORMAL_SPEED",
    "A_NONE", "A_CHAOTIC", "A_NEUTRAL", "A_LAWFUL",
    "G_UNIQ", "G_NOHELL", "G_HELL", "G_NOGEN", "G_SGROUP", "G_LGROUP",
    "G_GENO", "G_NOCORPSE", "G_FREQ", "G_IGNORE",
    "G_KNOWN", "G_GENOD", "G_EXTINCT", "G_GONE", "MV_KNOWS_EGG",
    "MALE", "FEMALE", "NEUTRAL", "NUM_MGENDERS",
    "MH_HUMAN", "MH_ELF", "MH_DWARF", "MH_GNOME", "MH_ORC",
    "NON_PM", "LOW_PM", "LEAVESTATUE", "HIGH_PM",
    "Attack", "PerMonst", "NO_ATK",
    "PM_NAMES", "NUMMONS", "SPECIAL_PM", "SUBSET_PM", "MONS",
    "monsndx", "monclass", "defch", "monname", "is_golem", "is_dragon",
]
