"""Monster type table (port of src/monst.c + include/monsters.h).

In the C source the table is built by expanding include/monsters.h
through the MON() macro in monst.c.  This module is the single Python
home for all of that:

- all the enums/constants the table uses (S_* monster classes, AT_*/
  AD_* attack and damage types, G_* geno bits, M1_*/M2_*/M3_* flag
  bitmaps, MR_* resistances, MS_* sounds, MZ_* sizes, WT_* weights,
  alignment values);
- `Attack` / `PerMonst` -- the struct attack / struct permonst rows;
- `PM_NAMES` -- the COMPLETE C ordering of all 382 monster types
  (default build: CHARON and MAIL_STRUCTURES undefined, all `#if 0`
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
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple

# ------------------------------------------------------------
# Monster classes (defsym.h MONSYM table: S_* indices and DEF_* chars)
# ------------------------------------------------------------

S_ANT = 1
S_BLOB = 2
S_COCKATRICE = 3
S_DOG = 4
S_EYE = 5
S_FELINE = 6
S_GREMLIN = 7
S_HUMANOID = 8
S_IMP = 9
S_JELLY = 10
S_KOBOLD = 11
S_LEPRECHAUN = 12
S_MIMIC = 13
S_NYMPH = 14
S_ORC = 15
S_PIERCER = 16
S_QUADRUPED = 17
S_RODENT = 18
S_SPIDER = 19
S_TRAPPER = 20
S_UNICORN = 21
S_VORTEX = 22
S_WORM = 23
S_XAN = 24
S_LIGHT = 25
S_ZRUTY = 26
S_ANGEL = 27
S_BAT = 28
S_CENTAUR = 29
S_DRAGON = 30
S_ELEMENTAL = 31
S_FUNGUS = 32
S_GNOME = 33
S_GIANT = 34
S_INVISIBLE = 35
S_JABBERWOCK = 36
S_KOP = 37
S_LICH = 38
S_MUMMY = 39
S_NAGA = 40
S_OGRE = 41
S_PUDDING = 42
S_QUANTMECH = 43
S_RUSTMONST = 44
S_SNAKE = 45
S_TROLL = 46
S_UMBER = 47
S_VAMPIRE = 48
S_WRAITH = 49
S_XORN = 50
S_YETI = 51
S_ZOMBIE = 52
S_HUMAN = 53
S_GHOST = 54
S_GOLEM = 55
S_DEMON = 56
S_EEL = 57
S_LIZARD = 58
S_WORM_TAIL = 59
S_MIMIC_DEF = 60
MAXMCLASSES = 61

# default display character per class (sym.h mon_defchars)
DEFCHARS = {
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

AT_ANY = -1
AT_NONE = 0
AT_CLAW = 1
AT_BITE = 2
AT_KICK = 3
AT_BUTT = 4
AT_TUCH = 5
AT_STNG = 6
AT_HUGS = 7
AT_SPIT = 10
AT_ENGL = 11
AT_BREA = 12
AT_EXPL = 13
AT_BOOM = 14
AT_GAZE = 15
AT_TENT = 16
AT_WEAP = 254
AT_MAGC = 255
NATTK = 6

AD_ANY = -1
AD_PHYS = 0
AD_MAGM = 1
AD_FIRE = 2
AD_COLD = 3
AD_SLEE = 4
AD_DISN = 5
AD_ELEC = 6
AD_DRST = 7
AD_ACID = 8
AD_SPC1 = 9
AD_SPC2 = 10
AD_BLND = 11
AD_STUN = 12
AD_SLOW = 13
AD_PLYS = 14
AD_DRLI = 15
AD_DREN = 16
AD_LEGS = 17
AD_STON = 18
AD_STCK = 19
AD_SGLD = 20
AD_SITM = 21
AD_SEDU = 22
AD_TLPT = 23
AD_RUST = 24
AD_CONF = 25
AD_DGST = 26
AD_HEAL = 27
AD_WRAP = 28
AD_WERE = 29
AD_DRDX = 30
AD_DRCO = 31
AD_DRIN = 32
AD_DISE = 33
AD_DCAY = 34
AD_SSEX = 35
AD_HALU = 36
AD_DETH = 37
AD_PEST = 38
AD_FAMN = 39
AD_SLIM = 40
AD_ENCH = 41
AD_CORR = 42
AD_POLY = 43
AD_CLRC = 240
AD_SPEL = 241
AD_RBRE = 242
AD_SAMU = 252
AD_CURS = 253


def distance_atk_type(atyp: int) -> bool:
    """DISTANCE_ATTK_TYPE: spit / breath / magic / gaze (monattk.h)."""
    return atyp in (AT_SPIT, AT_BREA, AT_MAGC, AT_GAZE)


# ------------------------------------------------------------
# Resists / conveyances (monflag.h MR_*)
# ------------------------------------------------------------

MR_FIRE = 0x01
MR_COLD = 0x02
MR_SLEEP = 0x04
MR_DISINT = 0x08
MR_ELEC = 0x10
MR_POISON = 0x20
MR_ACID = 0x40
MR_STONE = 0x80
MR2_SEE_INVIS = 0x0100
MR2_LEVITATE = 0x0200
MR2_WATERWALK = 0x0400
MR2_MAGBREATH = 0x0800
MR2_DISPLACED = 0x1000
MR2_STRENGTH = 0x2000
MR2_FUMBLING = 0x4000

# ------------------------------------------------------------
# Flag bitmaps (monflag.h M1_*/M2_*/M3_*)
# ------------------------------------------------------------

M1_FLY = 0x00000001
M1_SWIM = 0x00000002
M1_AMORPHOUS = 0x00000004
M1_WALLWALK = 0x00000008
M1_CLING = 0x00000010
M1_TUNNEL = 0x00000020
M1_NEEDPICK = 0x00000040
M1_CONCEAL = 0x00000080
M1_HIDE = 0x00000100
M1_AMPHIBIOUS = 0x00000200
M1_BREATHLESS = 0x00000400
M1_NOTAKE = 0x00000800
M1_NOEYES = 0x00001000
M1_NOHANDS = 0x00002000
M1_NOLIMBS = 0x00006000
M1_NOHEAD = 0x00008000
M1_MINDLESS = 0x00010000
M1_HUMANOID = 0x00020000
M1_ANIMAL = 0x00040000
M1_SLITHY = 0x00080000
M1_UNSOLID = 0x00100000
M1_THICK_HIDE = 0x00200000
M1_OVIPAROUS = 0x00400000
M1_REGEN = 0x00800000
M1_SEE_INVIS = 0x01000000
M1_TPORT = 0x02000000
M1_TPORT_CNTRL = 0x04000000
M1_ACID = 0x08000000
M1_POIS = 0x10000000
M1_CARNIVORE = 0x20000000
M1_HERBIVORE = 0x40000000
M1_OMNIVORE = 0x60000000
M1_METALLIVORE = 0x80000000

M2_NOPOLY = 0x00000001
M2_UNDEAD = 0x00000002
M2_WERE = 0x00000004
M2_HUMAN = 0x00000008
M2_ELF = 0x00000010
M2_DWARF = 0x00000020
M2_GNOME = 0x00000040
M2_ORC = 0x00000080
M2_DEMON = 0x00000100
M2_MERC = 0x00000200
M2_LORD = 0x00000400
M2_PRINCE = 0x00000800
M2_MINION = 0x00001000
M2_GIANT = 0x00002000
M2_SHAPESHIFTER = 0x00004000
M2_MALE = 0x00010000
M2_FEMALE = 0x00020000
M2_NEUTER = 0x00040000
M2_PNAME = 0x00080000
M2_HOSTILE = 0x00100000
M2_PEACEFUL = 0x00200000
M2_DOMESTIC = 0x00400000
M2_WANDER = 0x00800000
M2_STALK = 0x01000000
M2_NASTY = 0x02000000
M2_STRONG = 0x04000000
M2_ROCKTHROW = 0x08000000
M2_GREEDY = 0x10000000
M2_JEWELS = 0x20000000
M2_COLLECT = 0x40000000
M2_MAGIC = 0x80000000

M3_WANTSAMUL = 0x0001
M3_WANTSBELL = 0x0002
M3_WANTSBOOK = 0x0004
M3_WANTSCAND = 0x0008
M3_WANTSARTI = 0x0010
M3_WANTSALL = 0x001f
M3_WAITFORU = 0x0040
M3_CLOSE = 0x0080
M3_COVETOUS = 0x001f
M3_WAITMASK = 0x00c0
M3_INFRAVISION = 0x0100
M3_INFRAVISIBLE = 0x0200
M3_DISPLACES = 0x0400

# ------------------------------------------------------------
# Size, sound, weight, alignment (monflag.h / ms_sounds / weight.h /
# align.h)
# ------------------------------------------------------------

MZ_TINY = 0
MZ_SMALL = 1
MZ_MEDIUM = 2
MZ_HUMAN = 2
MZ_LARGE = 3
MZ_HUGE = 4
MZ_GIGANTIC = 7

MS_SILENT = 0
MS_BARK = 1
MS_MEW = 2
MS_ROAR = 3
MS_BELLOW = 4
MS_GROWL = 5
MS_SQEEK = 6
MS_SQAWK = 7
MS_CHIRP = 8
MS_HISS = 9
MS_BUZZ = 10
MS_GRUNT = 11
MS_NEIGH = 12
MS_MOO = 13
MS_WAIL = 14
MS_GURGLE = 15
MS_BURBLE = 16
MS_TRUMPET = 17
MS_ANIMAL = 17
MS_SHRIEK = 18
MS_BONES = 19
MS_LAUGH = 20
MS_MUMBLE = 21
MS_IMITATE = 22
MS_WERE = 23
MS_ORC = 24
MS_HUMANOID = 25
MS_ARREST = 26
MS_SOLDIER = 27
MS_GUARD = 28
MS_DJINNI = 29
MS_NURSE = 30
MS_SEDUCE = 31
MS_VAMPIRE = 32
MS_BRIBE = 33
MS_CUSS = 34
MS_RIDER = 35
MS_LEADER = 36
MS_NEMESIS = 37
MS_GUARDIAN = 38
MS_SELL = 39
MS_ORACLE = 40
MS_PRIEST = 41
MS_SPELL = 42
MS_BOAST = 43
MS_GROAN = 44
MS_FERRY = 45

WT_ETHEREAL = 0
WT_JELLY = 50
WT_ELF = 800
WT_HUMAN = 1450
WT_BABY_DRAGON = 1500
WT_DRAGON = 4500
WT_NYMPH = 600

A_NONE = -128
A_CHAOTIC = -1
A_NEUTRAL = 0
A_LAWFUL = 1

NORMAL_SPEED = 12

# ------------------------------------------------------------
# Genocide / generation masks (monflag.h G_*)
# ------------------------------------------------------------

G_UNIQ = 0x1000
G_NOHELL = 0x0800
G_HELL = 0x0400
G_NOGEN = 0x0200
G_SGROUP = 0x0080
G_LGROUP = 0x0040
G_GENO = 0x0020
G_NOCORPSE = 0x0010
G_FREQ = 0x0007
G_IGNORE = 0x8000

# mvitals flags (variant during the game)
G_KNOWN = 0x04
G_GENOD = 0x02
G_EXTINCT = 0x01
G_GONE = G_GENOD | G_EXTINCT
MV_KNOWS_EGG = 0x08

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
    aatyp: int
    adtyp: int
    damn: int
    damd: int


@dataclass(frozen=True)
class PerMonst:
    """One monster type (C: struct permonst, 5.0 field order).

    pmnames: (male, female, neutral); male/female are None for
    single-name monsters (C NAM()).
    """
    pmnames: Tuple[Optional[str], Optional[str], str]
    pmidx: int
    mlet: int                 # S_* class index (5.0)
    mlevel: int
    mmove: int
    ac: int
    mr: int
    maligntyp: int
    geno: int
    mattk: Tuple[Attack, ...]
    cwt: int
    cnutrit: int
    msound: int
    msize: int
    mresists: int
    mconveys: int
    mflags1: int
    mflags2: int
    mflags3: int
    difficulty: int
    mcolor: int


NO_ATK = Attack(0, 0, 0, 0)


def _nam(name: str) -> Tuple[Optional[str], Optional[str], str]:
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
# The complete C ordering (all 382 types, default build).
# Recorded so the PM_ numbering is fixed for the later completion
# pass of the remaining ~90% of monsters.h.
# ------------------------------------------------------------

PM_NAMES: Tuple[str, ...] = (
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

NUMMONS = 382
HIGH_PM = NUMMONS - 1
# mons[SPECIAL_PM..HIGH_PM] are never generated randomly and cannot be
# polymorphed into (permonst.h)
SPECIAL_PM = 329

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
PM_LONG_WORM_TAIL = 329

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

MONS: List[Optional[PerMonst]] = [None] * NUMMONS

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
    329, S_WORM_TAIL, "long worm tail",
    0, 0, 0, 0, 0, G_NOGEN | G_NOCORPSE | G_UNIQ,
    NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    0, 0, 0, 0, 0, 0, 0, M2_NOPOLY, 0, 1, 3)


# ------------------------------------------------------------
# Accessors
# ------------------------------------------------------------

def monsndx(data: PerMonst) -> int:
    """The mons[] index of a monster type (C: monsndx)."""
    return data.pmidx


def monclass(data: PerMonst) -> int:
    """The monster class (S_* index) of a monster type (C: monclass)."""
    return data.mlet


def defch(mcls: int) -> str:
    """The default display character of a monster class."""
    return DEFCHARS[mcls]


MALE, FEMALE, NEUTRAL = 0, 1, 2
NUM_MGENDERS = 3


def monname(data: PerMonst, mgender: int = NEUTRAL) -> str:
    """The name of a monster type for a gender (C: monname)."""
    return data.pmnames[mgender]


def is_golem(data: PerMonst) -> bool:
    return data.mlet == S_GOLEM


def is_dragon(data: PerMonst) -> bool:
    return data.mlet == S_DRAGON


# ------------------------------------------------------------
# Import-time validation
# ------------------------------------------------------------

def _validate() -> None:
    assert len(PM_NAMES) == NUMMONS, \
        f"PM_NAMES has {len(PM_NAMES)} entries, expected {NUMMONS}"
    # PM_ constants agree with the recorded ordering
    anchors = {
        PM_COCKATRICE: "cockatrice", PM_BAT: "bat",
        PM_GRAY_DRAGON: "gray dragon", PM_BLACK_DRAGON: "black dragon",
        PM_YELLOW_DRAGON: "yellow dragon", PM_GHOST: "ghost",
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
    # every implemented monster has a name and a valid class
    for idx in SUBSET_PM:
        m = MONS[idx]
        assert m.pmnames[2] == PM_NAMES[idx], (idx, m.pmnames[2])
        assert 1 <= m.mlet < MAXMCLASSES
        assert len(m.mattk) == NATTK
        assert (m.geno & ~G_UNIQ & ~G_NOHELL & ~G_HELL & ~G_NOGEN
                & ~G_SGROUP & ~G_LGROUP & ~G_GENO & ~G_NOCORPSE) \
            <= G_FREQ


_validate()


__all__ = [
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
    "AD_DISN", "AD_ELEC", "AD_DRST", "AD_ACID", "AD_BLND", "AD_STUN",
    "AD_SLOW", "AD_PLYS", "AD_DRLI", "AD_DREN", "AD_LEGS", "AD_STON",
    "AD_STCK", "AD_SGLD", "AD_SITM", "AD_SEDU", "AD_TLPT", "AD_RUST",
    "AD_CONF", "AD_DGST", "AD_HEAL", "AD_WRAP", "AD_WERE", "AD_DRDX",
    "AD_DRCO", "AD_DRIN", "AD_DISE", "AD_DCAY", "AD_SSEX", "AD_HALU",
    "AD_DETH", "AD_PEST", "AD_FAMN", "AD_SLIM", "AD_ENCH", "AD_CORR",
    "AD_POLY", "AD_CLRC", "AD_SPEL", "AD_RBRE", "AD_SAMU", "AD_CURS",
    # resists / flags / misc
    "MR_FIRE", "MR_COLD", "MR_SLEEP", "MR_DISINT", "MR_ELEC",
    "MR_POISON", "MR_ACID", "MR_STONE",
    "MZ_TINY", "MZ_SMALL", "MZ_MEDIUM", "MZ_HUMAN", "MZ_LARGE",
    "MZ_HUGE", "MZ_GIGANTIC",
    "NORMAL_SPEED",
    "A_NONE", "A_CHAOTIC", "A_NEUTRAL", "A_LAWFUL",
    "G_UNIQ", "G_NOHELL", "G_HELL", "G_NOGEN", "G_SGROUP", "G_LGROUP",
    "G_GENO", "G_NOCORPSE", "G_FREQ", "G_IGNORE",
    "G_KNOWN", "G_GENOD", "G_EXTINCT", "G_GONE", "MV_KNOWS_EGG",
    "NON_PM", "LOW_PM", "LEAVESTATUE", "HIGH_PM",
    "Attack", "PerMonst", "NO_ATK",
    "PM_NAMES", "NUMMONS", "SPECIAL_PM", "SUBSET_PM", "MONS",
    "monsndx", "monclass", "defch", "monname", "is_golem", "is_dragon",
    "MALE", "FEMALE", "NEUTRAL", "NUM_MGENDERS",
]
