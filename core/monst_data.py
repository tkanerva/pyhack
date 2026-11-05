"""The monster type tables of core.monst (extracted for readability).

This module holds the three large tables that used to live in
monst.py, kept verbatim:

- `PM_NAMES`  -- the COMPLETE C ordering of all 383 monster types
                 (default build: CHARON undefined; MAIL_STRUCTURES
                 always defined in 5.0 (global.h), so the mail daemon
                 IS in the table; all `#if 0` blocks excluded);
                 recorded so the PM_ numbering is fixed once and the
                 remaining ~90% of monsters.h can be completed later
                 without renumbering anything
- `SUBSET_PM` -- the indices of the implemented core subset of the
                 table
- `MONS`      -- the (sparse) table itself: PerMonst at the C index
                 for the implemented subset, None elsewhere

The rows are built with the `_mon` builder, the `Attack` / `PerMonst`
dataclasses and the constants that core.monst_defs defines, so this
module imports them from there -- and only from there.  That one-way
import is what keeps the constant types inferable (see the monst_defs
docstring): monst_data -> monst_defs, and core.monst imports both.
Import core.monst, the public API; don't import this module directly.
"""
from __future__ import annotations

from .monst_defs import (
    _mon,
    Attack,
    NO_ATK,
    NUMMONS,
    PerMonst,
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
    S_COCKATRICE, S_IMP, S_KOBOLD, S_LEPRECHAUN, S_MIMIC, S_NYMPH,
    S_ORC, S_RODENT, S_SPIDER, S_XAN, S_LIGHT, S_ZRUTY, S_BAT,
    S_DRAGON, S_ELEMENTAL, S_GIANT, S_OGRE, S_SNAKE, S_TROLL,
    S_VAMPIRE, S_WRAITH, S_YETI, S_ZOMBIE, S_GOLEM, S_GHOST,
    S_WORM_TAIL,
    AT_BITE, AT_TUCH, AT_NONE, AT_CLAW, AT_WEAP, AT_STNG, AT_HUGS,
    AT_BREA, AT_EXPL,
    AD_PHYS, AD_STON, AD_DRDX, AD_SGLD, AD_SITM, AD_SEDU, AD_DRST, AD_STCK,
    AD_LEGS, AD_BLND, AD_MAGM, AD_DISN, AD_FIRE, AD_DRLI, AD_PLYS,
    AD_SLOW,
    G_GENO, G_NOCORPSE, G_NOGEN, G_SGROUP, G_LGROUP, G_UNIQ,
    M1_FLY, M1_SWIM, M1_AMORPHOUS, M1_BREATHLESS, M1_CONCEAL,
    M1_HIDE, M1_CLING, M1_NOEYES, M1_NOHANDS, M1_NOLIMBS, M1_NOHEAD,
    M1_MINDLESS, M1_HUMANOID, M1_ANIMAL, M1_SLITHY, M1_UNSOLID,
    M1_THICK_HIDE, M1_OVIPAROUS, M1_REGEN, M1_SEE_INVIS, M1_POIS,
    M1_WALLWALK, M1_CARNIVORE, M1_OMNIVORE, M1_TPORT, M1_NOTAKE,
    M2_NOPOLY, M2_UNDEAD, M2_SHAPESHIFTER, M2_ORC, M2_FEMALE,
    M2_GIANT, M2_HOSTILE, M2_STALK, M2_NASTY, M2_STRONG, M2_WANDER,
    M2_GREEDY, M2_JEWELS, M2_COLLECT, M2_MAGIC, M2_NEUTER,
    M2_ROCKTHROW,
    M3_INFRAVISION, M3_INFRAVISIBLE,
    MR_FIRE, MR_COLD, MR_SLEEP, MR_DISINT, MR_ELEC, MR_POISON,
    MR_ACID, MR_STONE,
    MZ_TINY, MZ_SMALL, MZ_LARGE, MZ_HUMAN, MZ_HUGE, MZ_GIGANTIC,
    MS_SILENT, MS_HISS, MS_CUSS, MS_LAUGH, MS_SEDUCE, MS_SQEEK,
    MS_BUZZ, MS_ROAR, MS_BOAST, MS_GRUNT, MS_VAMPIRE, MS_WAIL,
    MS_GROAN, MS_BONES, MS_SQAWK, MS_ORC,
    WT_ETHEREAL, WT_NYMPH, WT_HUMAN, WT_DRAGON,
)

# The names the depth 1..8 band (the rows appended below) adds.
from .monst_defs import (
    _nams,
    PM_GIANT_ANT, PM_KILLER_BEE, PM_SOLDIER_ANT, PM_FIRE_ANT,
    PM_GIANT_BEETLE, PM_QUEEN_BEE, PM_ACID_BLOB, PM_QUIVERING_BLOB,
    PM_GELATINOUS_CUBE, PM_GAS_SPORE, PM_FLOATING_EYE, PM_HOBBIT, PM_DWARF,
    PM_BUGBEAR, PM_BLUE_JELLY, PM_SPOTTED_JELLY, PM_OCHRE_JELLY,
    PM_KOBOLD_LEADER, PM_KOBOLD_SHAMAN, PM_ORC, PM_MORDOR_ORC, PM_URUK_HAI,
    PM_ORC_SHAMAN, PM_ORC_CAPTAIN, PM_ROCK_PIERCER, PM_ROTHE, PM_RABID_RAT,
    PM_ROCK_MOLE, PM_WOODCHUCK, PM_SCORPION, PM_PONY, PM_WHITE_UNICORN,
    PM_SOLDIER, PM_SERGEANT, PM_LIEUTENANT, PM_CAPTAIN,
    S_ANT, S_BLOB, S_EYE, S_JELLY, S_QUADRUPED, S_UNICORN, S_PIERCER,
    S_HUMANOID, S_HUMAN,
    AT_BOOM, AT_BUTT, AT_ENGL, AT_KICK, AT_MAGC,
    AD_ACID, AD_COLD, AD_DRCO, AD_SPEL,
    M1_ACID, M1_AMPHIBIOUS, M1_HERBIVORE,
    M1_METALLIVORE, M1_NEEDPICK, M1_TUNNEL,
    M2_DOMESTIC, M2_DWARF, M2_HUMAN, M2_LORD, M2_MERC, M2_PRINCE,
    MS_GROWL, MS_HUMANOID, MS_MOO, MS_NEIGH, MS_SOLDIER,
    MZ_MEDIUM, WT_JELLY,
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

# the implemented core subset of the table
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
    # the depth 1..8 band (see the rows appended below)
    PM_GIANT_ANT, PM_KILLER_BEE, PM_SOLDIER_ANT, PM_FIRE_ANT,
    PM_GIANT_BEETLE, PM_QUEEN_BEE, PM_ACID_BLOB, PM_QUIVERING_BLOB,
    PM_GELATINOUS_CUBE, PM_GAS_SPORE, PM_FLOATING_EYE, PM_HOBBIT, PM_DWARF,
    PM_BUGBEAR, PM_BLUE_JELLY, PM_SPOTTED_JELLY, PM_OCHRE_JELLY,
    PM_KOBOLD_LEADER, PM_KOBOLD_SHAMAN, PM_ORC, PM_MORDOR_ORC, PM_URUK_HAI,
    PM_ORC_SHAMAN, PM_ORC_CAPTAIN, PM_ROCK_PIERCER, PM_ROTHE, PM_RABID_RAT,
    PM_ROCK_MOLE, PM_WOODCHUCK, PM_SCORPION, PM_PONY, PM_WHITE_UNICORN,
    PM_SOLDIER, PM_SERGEANT, PM_LIEUTENANT, PM_CAPTAIN,
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
    M1_CLING | M1_BREATHLESS | M1_AMORPHOUS | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOHEAD | M1_NOLIMBS | M1_THICK_HIDE | M1_CARNIVORE,
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
    M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_POIS, M2_HOSTILE,
    M3_INFRAVISIBLE, 4, 11)

MONS[PM_GIANT_SPIDER] = _mon(
    96, S_SPIDER, "giant spider",
    5, 15, 4, 0, 0, G_GENO | 1,
    Attack(AT_BITE, AD_DRST, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    200, 100, MS_SILENT, MZ_LARGE, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_CARNIVORE,
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
    MR_FIRE | MR_COLD | MR_ELEC | MR_DISINT | MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
    0,
    M1_FLY | M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID | M1_NOTAKE,
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
    M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
    0, 20, 7)

MONS[PM_BLACK_DRAGON] = _mon(
    149, S_DRAGON, "black dragon",
    15, 9, -1, 20, -6, G_GENO | 1,
    Attack(AT_BREA, AD_DISN, 1, 255), Attack(AT_BITE, AD_PHYS, 3, 8),
    Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
    NO_ATK, NO_ATK,
    WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_DISINT, MR_DISINT,
    M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
    M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
    0, 20, 0)

MONS[PM_FIRE_ELEMENTAL] = _mon(
    155, S_ELEMENTAL, "fire elemental",
    8, 12, 2, 30, 0, G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_FIRE, 3, 6), Attack(AT_NONE, AD_FIRE, 0, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
    MR_FIRE | MR_POISON | MR_STONE, 0,
    M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS | M1_UNSOLID | M1_FLY | M1_NOTAKE,
    M2_STRONG | M2_NEUTER, M3_INFRAVISIBLE, 10, 11)

MONS[PM_HILL_GIANT] = _mon(
    171, S_GIANT, "hill giant",
    8, 10, 6, 0, -2, G_GENO | G_SGROUP | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    2200, 700, MS_BOAST, MZ_HUGE, 0, 0,
    M1_HUMANOID | M1_CARNIVORE,
    M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
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
    M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_CARNIVORE | M1_NOTAKE,
    0, 0, 3, 2)

MONS[PM_SNAKE] = _mon(
    215, S_SNAKE, "snake",
    4, 15, 3, 0, 0, G_GENO | 2,
    Attack(AT_BITE, AD_DRST, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    100, 80, MS_HISS, MZ_SMALL, MR_POISON, MR_POISON,
    M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS | M1_CARNIVORE | M1_NOTAKE,
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
    M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_SHAPESHIFTER,
    M3_INFRAVISIBLE, 12, 1)

MONS[PM_WRAITH] = _mon(
    230, S_WRAITH, "wraith",
    6, 12, 4, 15, -6, G_GENO | 2,
    Attack(AT_TUCH, AD_DRLI, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_ETHEREAL, 0, MS_WAIL, MZ_HUMAN,
    MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_BREATHLESS | M1_FLY | M1_HUMANOID | M1_UNSOLID,
    M2_UNDEAD | M2_STALK | M2_HOSTILE, 0, 8, 0)

MONS[PM_OWLBEAR] = _mon(
    235, S_YETI, "owlbear",
    5, 12, 5, 0, 0, G_GENO | 3,
    Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
    Attack(AT_HUGS, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK,
    1700, 700, MS_GRUNT, MZ_LARGE, 0, 0,
    M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE,
    M2_STRONG | M2_NASTY, M3_INFRAVISIBLE, 7, 3)

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
    3, 6, 10, 0, -2, G_GENO | G_SGROUP | G_NOCORPSE | 1,
    Attack(AT_CLAW, AD_PLYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 3),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    400, 50, MS_SILENT, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
    M2_UNDEAD | M2_WANDER | M2_HOSTILE, M3_INFRAVISION, 5, 0)

MONS[PM_SKELETON] = _mon(
    248, S_ZOMBIE, "skeleton",
    12, 8, 4, 0, 0, G_NOCORPSE | G_NOGEN,
    Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_TUCH, AD_SLOW, 1, 6),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    300, 5, MS_BONES, MZ_HUMAN,
    MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
    M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
    M2_UNDEAD | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_COLLECT | M2_NASTY,
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
    WT_HUMAN, 0, MS_SQAWK, MZ_HUMAN,
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
# The depth 1..8 band (PLAN-MAKEMON.md phase A)
# ------------------------------------------------------------
#
# The rows below fill the low-level half of mons[] -- the region
# rndmonst_adj() draws from on a young dungeon level, plus the species
# the special rooms ask for by class (the ants and the bees for
# ANTHOLE / BEEHIVE, the S_HUMAN soldiers for BARRACKS).  They are in C
# index order and are assigned by index, so a later completion pass
# (the monsters.h -> monst_data.py converter of PLAN-MAKEMON.md §4.5)
# inserts rows above and below them without renumbering anything.
#
# Values are transcribed from include/monsters.h, one row per MON()
# expansion, same field order.

MONS[PM_GIANT_ANT] = _mon(
    0, S_ANT, "giant ant",
    2, 18, 3, 0, 0, G_GENO | G_SGROUP | 3,
    Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    10, 10, MS_SILENT, MZ_TINY, 0, 0,
    M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE, M2_HOSTILE,
    0, 4, 3)

MONS[PM_KILLER_BEE] = _mon(
    1, S_ANT, "killer bee",
    1, 18, -1, 0, 0, G_GENO | G_LGROUP | 2,
    Attack(AT_STNG, AD_DRST, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1, 5, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_FLY | M1_NOHANDS | M1_POIS,
    M2_HOSTILE | M2_FEMALE, 0, 6, 11)

MONS[PM_SOLDIER_ANT] = _mon(
    2, S_ANT, "soldier ant",
    3, 18, 3, 0, 0, G_GENO | G_SGROUP | 2,
    Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_STNG, AD_DRST, 3, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    20, 5, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
    M2_HOSTILE, 0, 7, 4)

MONS[PM_FIRE_ANT] = _mon(
    3, S_ANT, "fire ant",
    3, 18, 3, 10, 0, G_GENO | G_SGROUP | 1,
    Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_BITE, AD_FIRE, 2, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    30, 10, MS_SILENT, MZ_TINY, MR_FIRE, MR_FIRE,
    M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE, M2_HOSTILE,
    M3_INFRAVISIBLE, 6, 1)

MONS[PM_GIANT_BEETLE] = _mon(
    4, S_ANT, "giant beetle",
    5, 6, 4, 0, 0, G_GENO | 3,
    Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    200, 50, MS_SILENT, MZ_LARGE, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_CARNIVORE, M2_HOSTILE, 0,
    6, 0)

MONS[PM_QUEEN_BEE] = _mon(
    5, S_ANT, "queen bee",
    9, 24, -4, 0, 0, G_GENO | G_NOGEN,
    Attack(AT_STNG, AD_DRST, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1, 5, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
    M1_ANIMAL | M1_FLY | M1_NOHANDS | M1_OVIPAROUS | M1_POIS,
    M2_HOSTILE | M2_FEMALE | M2_PRINCE, 0, 12, 5)

MONS[PM_ACID_BLOB] = _mon(
    6, S_BLOB, "acid blob",
    1, 3, 8, 0, 0, G_GENO | 2,
    Attack(AT_NONE, AD_ACID, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 10, MS_SILENT, MZ_TINY,
    MR_SLEEP | MR_POISON | MR_ACID | MR_STONE, MR_ACID | MR_STONE,
    M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID,
    M2_WANDER | M2_NEUTER, 0, 2, 2)

MONS[PM_QUIVERING_BLOB] = _mon(
    7, S_BLOB, "quivering blob",
    5, 1, 8, 0, 0, G_GENO | 2,
    Attack(AT_TUCH, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    200, 100, MS_SILENT, MZ_SMALL, MR_SLEEP | MR_POISON, MR_POISON,
    M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
    M2_WANDER | M2_HOSTILE | M2_NEUTER, 0, 6, 15)

MONS[PM_GELATINOUS_CUBE] = _mon(
    8, S_BLOB, "gelatinous cube",
    6, 6, 8, 0, 0, G_GENO | 2,
    Attack(AT_TUCH, AD_PLYS, 2, 4), Attack(AT_NONE, AD_PLYS, 1, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    600, 150, MS_SILENT, MZ_LARGE,
    MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
    MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP,
    M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID,
    M2_WANDER | M2_HOSTILE | M2_NEUTER, 0, 8, 6)

MONS[PM_GAS_SPORE] = _mon(
    27, S_EYE, "gas spore",
    1, 3, 10, 0, 0, G_NOCORPSE | G_GENO | 1,
    Attack(AT_BOOM, AD_PHYS, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    10, 10, MS_SILENT, MZ_SMALL, 0, 0,
    M1_FLY | M1_BREATHLESS | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
    M2_HOSTILE | M2_NEUTER, 0, 2, 7)

MONS[PM_FLOATING_EYE] = _mon(
    28, S_EYE, "floating eye",
    2, 1, 9, 10, 0, G_GENO | 5,
    Attack(AT_NONE, AD_PLYS, 0, 70), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    10, 10, MS_SILENT, MZ_SMALL, 0, 0,
    M1_FLY | M1_AMPHIBIOUS | M1_NOLIMBS | M1_NOHEAD | M1_NOTAKE,
    M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 3, 4)

MONS[PM_HOBBIT] = _mon(
    43, S_HUMANOID, "hobbit",
    1, 9, 10, 0, 6, G_GENO | 2,
    Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    500, 200, MS_HUMANOID, MZ_SMALL, 0, 0,
    M1_HUMANOID | M1_OMNIVORE, M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 2, 2)

MONS[PM_DWARF] = _mon(
    44, S_HUMANOID, "dwarf",
    2, 6, 10, 10, 4, G_GENO | 3,
    Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    900, 300, MS_HUMANOID, MZ_HUMAN, 0, 0,
    M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
    M2_DWARF | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 4, 1)

MONS[PM_BUGBEAR] = _mon(
    45, S_HUMANOID, "bugbear",
    3, 9, 5, 0, -6, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1250, 250, MS_GROWL, MZ_LARGE, 0, 0,
    M1_HUMANOID | M1_OMNIVORE, M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 5, 3)

MONS[PM_BLUE_JELLY] = _mon(
    56, S_JELLY, "blue jelly",
    4, 0, 8, 10, 0, G_GENO | 2,
    Attack(AT_NONE, AD_COLD, 0, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_COLD | MR_POISON,
    MR_COLD | MR_POISON,
    M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
    M2_HOSTILE | M2_NEUTER, 0, 5, 4)

MONS[PM_SPOTTED_JELLY] = _mon(
    57, S_JELLY, "spotted jelly",
    5, 0, 8, 10, 0, G_GENO | 1,
    Attack(AT_NONE, AD_ACID, 0, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_ACID | MR_STONE,
    MR_ACID | MR_STONE,
    M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID | M1_NOTAKE,
    M2_HOSTILE | M2_NEUTER, 0, 6, 2)

MONS[PM_OCHRE_JELLY] = _mon(
    58, S_JELLY, "ochre jelly",
    6, 3, 8, 20, 0, G_GENO | 2,
    Attack(AT_ENGL, AD_ACID, 3, 6), Attack(AT_NONE, AD_ACID, 3, 6),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_ACID | MR_STONE,
    MR_ACID | MR_STONE,
    M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID | M1_NOTAKE,
    M2_HOSTILE | M2_NEUTER, 0, 8, 3)

MONS[PM_KOBOLD_LEADER] = _mon(
    61, S_KOBOLD, _nams("kobold lord", "kobold lady", "kobold leader"),
    2, 6, 10, 0, -4, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    500, 200, MS_ORC, MZ_SMALL, MR_POISON, 0,
    M1_HUMANOID | M1_POIS | M1_OMNIVORE,
    M2_HOSTILE | M2_LORD | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 3, 5)

MONS[PM_KOBOLD_SHAMAN] = _mon(
    62, S_KOBOLD, "kobold shaman",
    2, 6, 6, 10, -4, G_GENO | 1,
    Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    450, 150, MS_ORC, MZ_SMALL, MR_POISON, 0,
    M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_MAGIC,
    M3_INFRAVISIBLE | M3_INFRAVISION, 4, 12)

MONS[PM_ORC] = _mon(
    72, S_ORC, "orc",
    1, 9, 10, 0, -3, G_GENO | G_NOGEN | G_LGROUP,
    Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    850, 150, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_NOPOLY | M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 3, 1)

MONS[PM_MORDOR_ORC] = _mon(
    74, S_ORC, "Mordor orc",
    3, 5, 10, 0, -5, G_GENO | G_LGROUP | 1,
    Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1200, 200, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 5, 4)

MONS[PM_URUK_HAI] = _mon(
    75, S_ORC, "Uruk-hai",
    3, 7, 10, 0, -4, G_GENO | G_LGROUP | 1,
    Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1300, 300, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 5, 0)

MONS[PM_ORC_SHAMAN] = _mon(
    76, S_ORC, "orc shaman",
    3, 9, 5, 10, -5, G_GENO | 1,
    Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    1000, 300, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_GREEDY | M2_JEWELS | M2_MAGIC,
    M3_INFRAVISIBLE | M3_INFRAVISION, 5, 12)

MONS[PM_ORC_CAPTAIN] = _mon(
    77, S_ORC, "orc-captain",
    5, 5, 10, 0, -5, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    1350, 350, MS_ORC, MZ_HUMAN, MR_POISON, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
    M3_INFRAVISIBLE | M3_INFRAVISION, 7, 5)

MONS[PM_ROCK_PIERCER] = _mon(
    78, S_PIERCER, "rock piercer",
    3, 1, 3, 0, 0, G_GENO | 4,
    Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    200, 200, MS_SILENT, MZ_SMALL, 0, 0,
    M1_CLING | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_CARNIVORE | M1_NOTAKE,
    M2_HOSTILE, 0, 4, 7)

MONS[PM_ROTHE] = _mon(
    81, S_QUADRUPED, "rothe",
    2, 9, 7, 0, 0, G_GENO | G_SGROUP | 4,
    Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_BITE, AD_PHYS, 1, 3),
    Attack(AT_BITE, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK,
    400, 100, MS_MOO, MZ_LARGE, 0, 0,
    M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE, M2_HOSTILE, M3_INFRAVISIBLE,
    4, 3)

MONS[PM_RABID_RAT] = _mon(
    90, S_RODENT, "rabid rat",
    2, 12, 6, 0, 0, G_GENO | 1,
    Attack(AT_BITE, AD_DRCO, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 5, MS_SQEEK, MZ_TINY, MR_POISON, 0,
    M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_CARNIVORE, M2_HOSTILE,
    M3_INFRAVISIBLE, 4, 3)

MONS[PM_ROCK_MOLE] = _mon(
    92, S_RODENT, "rock mole",
    3, 3, 0, 20, 0, G_GENO | 2,
    Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 30, MS_SILENT, MZ_SMALL, 0, 0,
    M1_TUNNEL | M1_ANIMAL | M1_NOHANDS | M1_METALLIVORE,
    M2_HOSTILE | M2_GREEDY | M2_JEWELS | M2_COLLECT, M3_INFRAVISIBLE,
    4, 7)

MONS[PM_WOODCHUCK] = _mon(
    93, S_RODENT, "woodchuck",
    3, 3, 0, 20, 0, G_NOGEN | G_GENO,
    Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    30, 30, MS_SILENT, MZ_SMALL, 0, 0,
    M1_TUNNEL | M1_ANIMAL | M1_NOHANDS | M1_SWIM | M1_HERBIVORE,
    M2_WANDER | M2_HOSTILE, M3_INFRAVISIBLE, 4, 3)

MONS[PM_SCORPION] = _mon(
    97, S_SPIDER, "scorpion",
    5, 15, 3, 0, 0, G_GENO | 2,
    Attack(AT_CLAW, AD_PHYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 2),
    Attack(AT_STNG, AD_DRST, 1, 4), NO_ATK, NO_ATK, NO_ATK,
    50, 100, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
    M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
    M2_HOSTILE, 0, 8, 1)

MONS[PM_PONY] = _mon(
    100, S_UNICORN, "pony",
    3, 16, 6, 0, 0, G_GENO | 2,
    Attack(AT_KICK, AD_PHYS, 1, 6), Attack(AT_BITE, AD_PHYS, 1, 2),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    1300, 250, MS_NEIGH, MZ_MEDIUM, 0, 0,
    M1_ANIMAL | M1_NOHANDS | M1_HERBIVORE,
    M2_WANDER | M2_STRONG | M2_DOMESTIC, M3_INFRAVISIBLE, 4, 3)

MONS[PM_WHITE_UNICORN] = _mon(
    101, S_UNICORN, "white unicorn",
    4, 24, 2, 70, 7, G_GENO | 2,
    Attack(AT_BUTT, AD_PHYS, 1, 12), Attack(AT_KICK, AD_PHYS, 1, 6),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    1300, 300, MS_NEIGH, MZ_LARGE, MR_POISON, MR_POISON,
    M1_NOHANDS | M1_HERBIVORE, M2_WANDER | M2_STRONG | M2_JEWELS,
    M3_INFRAVISIBLE, 6, 15)

MONS[PM_SOLDIER] = _mon(
    277, S_HUMAN, "soldier",
    6, 10, 10, 0, -2, G_SGROUP | G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE, 8, 7)

MONS[PM_SERGEANT] = _mon(
    278, S_HUMAN, "sergeant",
    8, 10, 10, 5, -3, G_SGROUP | G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    NO_ATK,
    WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE, 10, 1)

MONS[PM_LIEUTENANT] = _mon(
    280, S_HUMAN, "lieutenant",
    10, 10, 10, 15, -4, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 3, 4), Attack(AT_WEAP, AD_PHYS, 3, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE, 12, 2)

MONS[PM_CAPTAIN] = _mon(
    281, S_HUMAN, "captain",
    12, 10, 10, 15, -5, G_GENO | 1,
    Attack(AT_WEAP, AD_PHYS, 4, 4), Attack(AT_WEAP, AD_PHYS, 4, 4),
    NO_ATK, NO_ATK, NO_ATK, NO_ATK,
    WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
    M1_HUMANOID | M1_OMNIVORE,
    M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
    M3_INFRAVISIBLE, 14, 4)
