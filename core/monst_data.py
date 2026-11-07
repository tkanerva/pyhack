"""The monster type tables of core.monst (generated; do not hand-edit).

Written by `tools/convert_monsters.py`, which reads NetHack 5.0's
`include/monsters.h` and emits one row per C `MON(...)` in the header
order.  The converter is a development tool (nothing imports it) and
this file is checked in; re-run it after a NetHack bump and then run
`python -m core.monst` for the table self-check.

This module holds the three large tables that used to live in monst.py,
all of them in C order:

- `PM_NAMES`  -- the COMPLETE C ordering of all 383 monster types
                 (default build: CHARON undefined; MAIL_STRUCTURES
                 always defined in 5.0 (global.h), so the mail daemon
                 IS in the table; all `#if 0` blocks excluded).  One
                 entry per row -- its neutral name -- so this is what
                 fixes the PM_ numbering;
- `SUBSET_PM` -- the indices of the implemented rows.  Every row is
                 implemented since the converter pass, so it is the
                 whole table; the name stayed because it is what the
                 callers (and monst._validate) mean by it: "the rows
                 that carry a table entry";
- `MONS`      -- the table itself: a PerMonst for every C index, in
                 the C order, so `MONS[PM_BAT]` is the bat.

The rows are built with the `_mon` builder, the `Attack` / `PerMonst`
dataclasses and the constants that core.monst_defs defines, so this
module imports them from there -- and only from there.  That one-way
import is what keeps the constant types inferable (see the monst_defs
docstring): monst_data -> monst_defs, and core.monst imports both.
Import core.monst, the public API; don't import this module directly.

Each row is laid out like the C it came from -- name and class, the
LVL() / geno pair, the six attack slots, SIZ() with the two resistance
columns, the three flag bitmaps, then difficulty and colour -- so a row
can be audited against monsters.h line by line.
"""

from __future__ import annotations

from .monst_defs import (
    # the row builder and its types
    _mon, _nams, Attack, NO_ATK, NUMMONS, PerMonst,
    # alignments (C: A_*)
    A_NONE,
    # monster classes (C: S_*)
    S_ANGEL, S_ANT, S_BAT, S_BLOB, S_CENTAUR, S_COCKATRICE, S_DEMON, S_DOG,
    S_DRAGON, S_EEL, S_ELEMENTAL, S_EYE, S_FELINE, S_FUNGUS, S_GHOST, S_GIANT,
    S_GNOME, S_GOLEM, S_GREMLIN, S_HUMAN, S_HUMANOID, S_IMP, S_JABBERWOCK,
    S_JELLY, S_KOBOLD, S_KOP, S_LEPRECHAUN, S_LICH, S_LIGHT, S_LIZARD, S_MIMIC,
    S_MUMMY, S_NAGA, S_NYMPH, S_OGRE, S_ORC, S_PIERCER, S_PUDDING, S_QUADRUPED,
    S_QUANTMECH, S_RODENT, S_RUSTMONST, S_SNAKE, S_SPIDER, S_TRAPPER, S_TROLL,
    S_UMBER, S_UNICORN, S_VAMPIRE, S_VORTEX, S_WORM, S_WORM_TAIL, S_WRAITH,
    S_XAN, S_XORN, S_YETI, S_ZOMBIE, S_ZRUTY,
    # attack types (C: AT_*)
    AT_BITE, AT_BOOM, AT_BREA, AT_BUTT, AT_CLAW, AT_ENGL, AT_EXPL, AT_GAZE,
    AT_HUGS, AT_KICK, AT_MAGC, AT_NONE, AT_SPIT, AT_STNG, AT_TENT, AT_TUCH,
    AT_WEAP,
    # damage types (C: AD_*)
    AD_ACID, AD_BLND, AD_CLRC, AD_COLD, AD_CONF, AD_CORR, AD_CURS, AD_DCAY,
    AD_DETH, AD_DGST, AD_DISE, AD_DISN, AD_DRCO, AD_DRDX, AD_DREN, AD_DRIN,
    AD_DRLI, AD_DRST, AD_ELEC, AD_ENCH, AD_FAMN, AD_FIRE, AD_HALU, AD_HEAL,
    AD_LEGS, AD_MAGM, AD_PEST, AD_PHYS, AD_PLYS, AD_POLY, AD_RBRE, AD_RUST,
    AD_SAMU, AD_SEDU, AD_SGLD, AD_SITM, AD_SLEE, AD_SLIM, AD_SLOW, AD_SPEL,
    AD_SSEX, AD_STCK, AD_STON, AD_STUN, AD_TLPT, AD_WERE, AD_WRAP,
    # resists and conveyances (C: MR_*, MR2_*)
    MR_ACID, MR_COLD, MR_DISINT, MR_ELEC, MR_FIRE, MR_POISON, MR_SLEEP,
    MR_STONE,
    # flag bitmaps (C: M1_*, M2_*, M3_*)
    M1_ACID, M1_AMORPHOUS, M1_AMPHIBIOUS, M1_ANIMAL, M1_BREATHLESS,
    M1_CARNIVORE, M1_CLING, M1_CONCEAL, M1_FLY, M1_HERBIVORE, M1_HIDE,
    M1_HUMANOID, M1_METALLIVORE, M1_MINDLESS, M1_NEEDPICK, M1_NOEYES,
    M1_NOHANDS, M1_NOHEAD, M1_NOLIMBS, M1_NOTAKE, M1_OMNIVORE, M1_OVIPAROUS,
    M1_POIS, M1_REGEN, M1_SEE_INVIS, M1_SLITHY, M1_SWIM, M1_THICK_HIDE,
    M1_TPORT, M1_TPORT_CNTRL, M1_TUNNEL, M1_UNSOLID, M1_WALLWALK, M2_COLLECT,
    M2_DEMON, M2_DOMESTIC, M2_DWARF, M2_ELF, M2_FEMALE, M2_GIANT, M2_GNOME,
    M2_GREEDY, M2_HOSTILE, M2_HUMAN, M2_JEWELS, M2_LORD, M2_MAGIC, M2_MALE,
    M2_MERC, M2_MINION, M2_NASTY, M2_NEUTER, M2_NOPOLY, M2_ORC, M2_PEACEFUL,
    M2_PNAME, M2_PRINCE, M2_ROCKTHROW, M2_SHAPESHIFTER, M2_STALK, M2_STRONG,
    M2_UNDEAD, M2_WANDER, M2_WERE, M3_CLOSE, M3_COVETOUS, M3_DISPLACES,
    M3_INFRAVISIBLE, M3_INFRAVISION, M3_WAITFORU, M3_WANTSAMUL, M3_WANTSARTI,
    M3_WANTSBOOK, M3_WANTSCAND,
    # sizes and sounds (C: MZ_*, MS_*)
    MS_ARREST, MS_BARK, MS_BELLOW, MS_BOAST, MS_BONES, MS_BRIBE, MS_BURBLE,
    MS_BUZZ, MS_CHIRP, MS_CUSS, MS_DJINNI, MS_GROAN, MS_GROWL, MS_GRUNT,
    MS_GUARD, MS_GUARDIAN, MS_GURGLE, MS_HISS, MS_HUMANOID, MS_IMITATE,
    MS_LAUGH, MS_LEADER, MS_MEW, MS_MOO, MS_MUMBLE, MS_NEIGH, MS_NEMESIS,
    MS_NURSE, MS_ORACLE, MS_ORC, MS_PRIEST, MS_RIDER, MS_ROAR, MS_SEDUCE,
    MS_SELL, MS_SHRIEK, MS_SILENT, MS_SOLDIER, MS_SPELL, MS_SQAWK, MS_SQEEK,
    MS_TRUMPET, MS_VAMPIRE, MS_WAIL, MS_WERE, MZ_GIGANTIC, MZ_HUGE, MZ_HUMAN,
    MZ_LARGE, MZ_MEDIUM, MZ_SMALL, MZ_TINY,
    # geno masks (C: G_*)
    G_GENO, G_HELL, G_LGROUP, G_NOCORPSE, G_NOGEN, G_NOHELL, G_SGROUP, G_UNIQ,
    # body weights (C: WT_*)
    WT_BABY_DRAGON, WT_DRAGON, WT_ELF, WT_ETHEREAL, WT_HUMAN, WT_JELLY,
    WT_NYMPH,
    # colours (C: color.h)
    CLR_BLACK, CLR_BLUE, CLR_BRIGHT_BLUE, CLR_BRIGHT_GREEN, CLR_BRIGHT_MAGENTA,
    CLR_BROWN, CLR_CYAN, CLR_GRAY, CLR_GREEN, CLR_MAGENTA, CLR_ORANGE, CLR_RED,
    CLR_WHITE, CLR_YELLOW, DRAGON_SILVER, HI_DOMESTIC, HI_GOLD, HI_LEATHER,
    HI_LORD, HI_METAL, HI_OVERLORD, HI_PAPER, HI_WOOD, HI_ZAP,
)


# ------------------------------------------------------------
# The complete C ordering: the neutral name of every row, in
# mons[] order.  This is the PM_ numbering (monst_defs holds the
# anchors the game code reads by name).
# ------------------------------------------------------------

PM_NAMES: tuple[str, ...] = (
    "giant ant", "killer bee", "soldier ant", "fire ant", "giant beetle",
    "queen bee", "acid blob", "quivering blob", "gelatinous cube",
    "chickatrice", "cockatrice", "pyrolisk", "jackal", "fox", "coyote",
    "werejackal", "little dog", "dingo", "dog", "large dog", "wolf",
    "werewolf", "winter wolf cub", "warg", "winter wolf", "hell hound pup",
    "hell hound", "gas spore", "floating eye", "freezing sphere",
    "flaming sphere", "shocking sphere", "kitten", "housecat", "jaguar",
    "lynx", "panther", "large cat", "tiger", "displacer beast", "gremlin",
    "gargoyle", "winged gargoyle", "hobbit", "dwarf", "bugbear",
    "dwarf leader", "dwarf ruler", "mind flayer", "master mind flayer",
    "manes", "homunculus", "imp", "lemure", "quasit", "tengu", "blue jelly",
    "spotted jelly", "ochre jelly", "kobold", "large kobold", "kobold leader",
    "kobold shaman", "leprechaun", "small mimic", "large mimic", "giant mimic",
    "wood nymph", "water nymph", "mountain nymph", "goblin", "hobgoblin",
    "orc", "hill orc", "Mordor orc", "Uruk-hai", "orc shaman", "orc-captain",
    "rock piercer", "iron piercer", "glass piercer", "rothe", "mumak",
    "leocrotta", "wumpus", "titanothere", "baluchitherium", "mastodon",
    "sewer rat", "giant rat", "rabid rat", "wererat", "rock mole", "woodchuck",
    "cave spider", "centipede", "giant spider", "scorpion", "lurker above",
    "trapper", "pony", "white unicorn", "gray unicorn", "black unicorn",
    "horse", "warhorse", "fog cloud", "dust vortex", "ice vortex",
    "energy vortex", "steam vortex", "fire vortex", "baby long worm",
    "baby purple worm", "long worm", "purple worm", "grid bug", "xan",
    "yellow light", "black light", "zruty", "couatl", "Aleax", "Angel",
    "ki-rin", "Archon", "bat", "giant bat", "raven", "vampire bat",
    "plains centaur", "forest centaur", "mountain centaur", "baby gray dragon",
    "baby gold dragon", "baby silver dragon", "baby red dragon",
    "baby white dragon", "baby orange dragon", "baby black dragon",
    "baby blue dragon", "baby green dragon", "baby yellow dragon",
    "gray dragon", "gold dragon", "silver dragon", "red dragon",
    "white dragon", "orange dragon", "black dragon", "blue dragon",
    "green dragon", "yellow dragon", "stalker", "air elemental",
    "fire elemental", "earth elemental", "water elemental", "lichen",
    "brown mold", "yellow mold", "green mold", "red mold", "shrieker",
    "violet fungus", "gnome", "gnome leader", "gnomish wizard", "gnome ruler",
    "giant", "stone giant", "hill giant", "fire giant", "frost giant", "ettin",
    "storm giant", "titan", "minotaur", "jabberwock", "Keystone Kop",
    "Kop Sergeant", "Kop Lieutenant", "Kop Kaptain", "lich", "demilich",
    "master lich", "arch-lich", "kobold mummy", "gnome mummy", "orc mummy",
    "dwarf mummy", "elf mummy", "human mummy", "ettin mummy", "giant mummy",
    "red naga hatchling", "black naga hatchling", "golden naga hatchling",
    "guardian naga hatchling", "red naga", "black naga", "golden naga",
    "guardian naga", "ogre", "ogre leader", "ogre tyrant", "gray ooze",
    "brown pudding", "green slime", "black pudding", "quantum mechanic",
    "genetic engineer", "rust monster", "disenchanter", "garter snake",
    "snake", "water moccasin", "python", "pit viper", "cobra", "troll",
    "ice troll", "rock troll", "water troll", "Olog-hai", "umber hulk",
    "vampire", "vampire leader", "Vlad the Impaler", "barrow wight", "wraith",
    "Nazgul", "xorn", "monkey", "ape", "owlbear", "yeti", "carnivorous ape",
    "sasquatch", "kobold zombie", "gnome zombie", "orc zombie", "dwarf zombie",
    "elf zombie", "human zombie", "ettin zombie", "ghoul", "giant zombie",
    "skeleton", "straw golem", "paper golem", "rope golem", "gold golem",
    "leather golem", "wood golem", "flesh golem", "clay golem", "stone golem",
    "glass golem", "iron golem", "human", "wererat", "werejackal", "werewolf",
    "elf", "Woodland-elf", "Green-elf", "Grey-elf", "elf-noble",
    "elven monarch", "doppelganger", "shopkeeper", "guard", "prisoner",
    "Oracle", "aligned cleric", "high cleric", "soldier", "sergeant", "nurse",
    "lieutenant", "captain", "watchman", "watch captain", "Medusa",
    "Wizard of Yendor", "Croesus", "ghost", "shade", "water demon",
    "amorous demon", "horned devil", "erinys", "barbed devil", "marilith",
    "vrock", "hezrou", "bone devil", "ice devil", "nalfeshnee", "pit fiend",
    "sandestin", "balrog", "Juiblex", "Yeenoghu", "Orcus", "Geryon",
    "Dispater", "Baalzebub", "Asmodeus", "Demogorgon", "Death", "Pestilence",
    "Famine", "mail daemon", "djinni", "jellyfish", "piranha", "shark",
    "giant eel", "electric eel", "kraken", "newt", "gecko", "iguana",
    "baby crocodile", "lizard", "chameleon", "crocodile", "salamander",
    "long worm tail", "archeologist", "barbarian", "cave dweller", "healer",
    "knight", "monk", "cleric", "ranger", "rogue", "samurai", "tourist",
    "valkyrie", "wizard", "Lord Carnarvon", "Pelias", "Shaman Karnov",
    "Hippocrates", "King Arthur", "Grand Master", "Arch Priest", "Orion",
    "Master of Thieves", "Lord Sato", "Twoflower", "Norn", "Neferet the Green",
    "Minion of Huhetotl", "Thoth Amon", "Chromatic Dragon", "Cyclops", "Ixoth",
    "Master Kaen", "Nalzok", "Scorpius", "Master Assassin", "Ashikaga Takauji",
    "Lord Surtur", "Dark One", "student", "chieftain", "neanderthal",
    "attendant", "page", "abbot", "acolyte", "hunter", "thug", "ninja",
    "roshi", "guide", "warrior", "apprentice",
)


# the implemented rows: all of them, since the converter pass
# (the depth-band table it replaced listed the indices by hand)
SUBSET_PM: tuple[int, ...] = tuple(range(NUMMONS))


# ------------------------------------------------------------
# The table (C: struct permonst mons[]; one row per MON() in
# include/monsters.h, so the index of every row is its C monnum)
# ------------------------------------------------------------

MONS: list[PerMonst | None] = [
    # ---- S_ANT ----
    # PM_GIANT_ANT
    _mon(
        0, S_ANT, "giant ant",
        2, 18, 3, 0, 0, G_GENO | G_SGROUP | 3,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_SILENT, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE, M2_HOSTILE, 0, 4,
        CLR_BROWN),
    # PM_KILLER_BEE
    _mon(
        1, S_ANT, "killer bee",
        1, 18, -1, 0, 0, G_GENO | G_LGROUP | 2,
        Attack(AT_STNG, AD_DRST, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1, 5, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
        M1_ANIMAL | M1_FLY | M1_NOHANDS | M1_POIS, M2_HOSTILE | M2_FEMALE, 0,
        6, CLR_YELLOW),
    # PM_SOLDIER_ANT
    _mon(
        2, S_ANT, "soldier ant",
        3, 18, 3, 0, 0, G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_STNG, AD_DRST, 3, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        20, 5, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
        M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
        M2_HOSTILE, 0, 7, CLR_BLUE),
    # PM_FIRE_ANT
    _mon(
        3, S_ANT, "fire ant",
        3, 18, 3, 10, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_BITE, AD_FIRE, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        30, 10, MS_SILENT, MZ_TINY, MR_FIRE, MR_FIRE,
        M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE, 6, CLR_RED),
    # PM_GIANT_BEETLE
    _mon(
        4, S_ANT, "giant beetle",
        5, 6, 4, 0, 0, G_GENO | 3,
        Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 50, MS_SILENT, MZ_LARGE, MR_POISON, MR_POISON,
        M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_CARNIVORE, M2_HOSTILE, 0, 6,
        CLR_BLACK),
    # PM_QUEEN_BEE
    _mon(
        5, S_ANT, "queen bee",
        9, 24, -4, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_STNG, AD_DRST, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1, 5, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
        M1_ANIMAL | M1_FLY | M1_NOHANDS | M1_OVIPAROUS | M1_POIS,
        M2_HOSTILE | M2_FEMALE | M2_PRINCE, 0, 12, HI_LORD),
    # ---- S_BLOB ----
    # PM_ACID_BLOB
    _mon(
        6, S_BLOB, "acid blob",
        1, 3, 8, 0, 0, G_GENO | 2,
        Attack(AT_NONE, AD_ACID, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 10, MS_SILENT, MZ_TINY, MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
        MR_ACID | MR_STONE,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID,
        M2_WANDER | M2_NEUTER, 0, 2, CLR_GREEN),
    # PM_QUIVERING_BLOB
    _mon(
        7, S_BLOB, "quivering blob",
        5, 1, 8, 0, 0, G_GENO | 2,
        Attack(AT_TUCH, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 100, MS_SILENT, MZ_SMALL, MR_SLEEP | MR_POISON, MR_POISON,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
        M2_WANDER | M2_HOSTILE | M2_NEUTER, 0, 6, CLR_WHITE),
    # PM_GELATINOUS_CUBE
    _mon(
        8, S_BLOB, "gelatinous cube",
        6, 6, 8, 0, 0, G_GENO | 2,
        Attack(AT_TUCH, AD_PLYS, 2, 4), Attack(AT_NONE, AD_PLYS, 1, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        600, 150, MS_SILENT, MZ_LARGE,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID,
        M2_WANDER | M2_HOSTILE | M2_NEUTER, 0, 8, CLR_CYAN),
    # ---- S_COCKATRICE ----
    # PM_CHICKATRICE
    _mon(
        9, S_COCKATRICE, "chickatrice",
        4, 4, 8, 30, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 1, 2), Attack(AT_TUCH, AD_STON, 0, 0),
        Attack(AT_NONE, AD_STON, 0, 0), NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_HISS, MZ_TINY, MR_POISON | MR_STONE, MR_POISON | MR_STONE,
        M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 7,
        CLR_BROWN),
    # PM_COCKATRICE
    _mon(
        10, S_COCKATRICE, "cockatrice",
        5, 6, 6, 30, 0, G_GENO | 5,
        Attack(AT_BITE, AD_PHYS, 1, 3), Attack(AT_TUCH, AD_STON, 0, 0),
        Attack(AT_NONE, AD_STON, 0, 0), NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_HISS, MZ_SMALL, MR_POISON | MR_STONE, MR_POISON | MR_STONE,
        M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE | M1_OVIPAROUS, M2_HOSTILE,
        M3_INFRAVISIBLE, 8, CLR_YELLOW),
    # PM_PYROLISK
    _mon(
        11, S_COCKATRICE, "pyrolisk",
        6, 6, 6, 30, 0, G_GENO | 1,
        Attack(AT_GAZE, AD_FIRE, 2, 6), Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_HISS, MZ_SMALL, MR_POISON | MR_FIRE, MR_POISON | MR_FIRE,
        M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE | M1_OVIPAROUS, M2_HOSTILE,
        M3_INFRAVISIBLE, 8, CLR_RED),
    # ---- S_DOG ----
    # PM_JACKAL
    _mon(
        12, S_DOG, "jackal",
        0, 12, 7, 0, 0, G_GENO | G_SGROUP | 3,
        Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 250, MS_BARK, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 1,
        CLR_BROWN),
    # PM_FOX
    _mon(
        13, S_DOG, "fox",
        0, 15, 7, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 250, MS_BARK, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 1,
        CLR_RED),
    # PM_COYOTE
    _mon(
        14, S_DOG, "coyote",
        1, 12, 7, 0, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 250, MS_BARK, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 2,
        CLR_BROWN),
    # PM_WEREJACKAL
    _mon(
        15, S_DOG, "werejackal",
        2, 12, 7, 10, -7, G_NOGEN | G_NOCORPSE,
        Attack(AT_BITE, AD_WERE, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 250, MS_BARK, MZ_SMALL, MR_POISON, 0,
        M1_NOHANDS | M1_POIS | M1_REGEN | M1_CARNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE, M3_INFRAVISIBLE, 4, CLR_BROWN),
    # PM_LITTLE_DOG
    _mon(
        16, S_DOG, "little dog",
        2, 18, 6, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        150, 150, MS_BARK, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_DOMESTIC, M3_INFRAVISIBLE, 3,
        HI_DOMESTIC),
    # PM_DINGO
    _mon(
        17, S_DOG, "dingo",
        4, 16, 5, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 200, MS_BARK, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 5,
        CLR_YELLOW),
    # PM_DOG
    _mon(
        18, S_DOG, "dog",
        4, 16, 5, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 200, MS_BARK, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_DOMESTIC, M3_INFRAVISIBLE, 5,
        HI_DOMESTIC),
    # PM_LARGE_DOG
    _mon(
        19, S_DOG, "large dog",
        6, 15, 4, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        800, 250, MS_BARK, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_STRONG | M2_DOMESTIC,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_WOLF
    _mon(
        20, S_DOG, "wolf",
        5, 12, 4, 0, 0, G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 250, MS_BARK, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 6,
        CLR_GRAY),
    # PM_WEREWOLF
    _mon(
        21, S_DOG, "werewolf",
        5, 12, 4, 20, -7, G_NOGEN | G_NOCORPSE,
        Attack(AT_BITE, AD_WERE, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 250, MS_BARK, MZ_MEDIUM, MR_POISON, 0,
        M1_NOHANDS | M1_POIS | M1_REGEN | M1_CARNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE, M3_INFRAVISIBLE, 7, CLR_GRAY),
    # PM_WINTER_WOLF_CUB
    _mon(
        22, S_DOG, "winter wolf cub",
        5, 12, 4, 0, 0, G_NOHELL | G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 1, 8), Attack(AT_BREA, AD_COLD, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        250, 200, MS_BARK, MZ_SMALL, MR_COLD, MR_COLD,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, 0, 7, CLR_CYAN),
    # PM_WARG
    _mon(
        23, S_DOG, "warg",
        7, 12, 4, 0, -5, G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        850, 350, MS_BARK, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 8,
        CLR_BLACK),
    # PM_WINTER_WOLF
    _mon(
        24, S_DOG, "winter wolf",
        7, 12, 4, 20, -5, G_NOHELL | G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 6), Attack(AT_BREA, AD_COLD, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        700, 300, MS_BARK, MZ_LARGE, MR_COLD, MR_COLD,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE | M2_STRONG, 0, 9,
        CLR_CYAN),
    # PM_HELL_HOUND_PUP
    _mon(
        25, S_DOG, "hell hound pup",
        7, 12, 4, 20, 0, G_HELL | G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 2, 6), Attack(AT_BREA, AD_FIRE, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        200, 200, MS_BARK, MZ_SMALL, MR_FIRE, MR_FIRE,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 9,
        CLR_RED),
    # PM_HELL_HOUND
    _mon(
        26, S_DOG, "hell hound",
        12, 14, 2, 20, -5, G_HELL | G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 3, 6), Attack(AT_BREA, AD_FIRE, 3, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_BARK, MZ_MEDIUM, MR_FIRE, MR_FIRE,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE | M2_STRONG,
        M3_INFRAVISIBLE, 14, CLR_RED),
    # ---- S_EYE ----
    # PM_GAS_SPORE
    _mon(
        27, S_EYE, "gas spore",
        1, 3, 10, 0, 0, G_NOCORPSE | G_GENO | 1,
        Attack(AT_BOOM, AD_PHYS, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_SILENT, MZ_SMALL, 0, 0,
        M1_FLY | M1_BREATHLESS | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
        M2_HOSTILE | M2_NEUTER, 0, 2, CLR_GRAY),
    # PM_FLOATING_EYE
    _mon(
        28, S_EYE, "floating eye",
        2, 1, 9, 10, 0, G_GENO | 5,
        Attack(AT_NONE, AD_PLYS, 0, 70), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        10, 10, MS_SILENT, MZ_SMALL, 0, 0,
        M1_FLY | M1_AMPHIBIOUS | M1_NOLIMBS | M1_NOHEAD | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 3, CLR_BLUE),
    # PM_FREEZING_SPHERE
    _mon(
        29, S_EYE, "freezing sphere",
        6, 13, 4, 0, 0, G_NOCORPSE | G_NOHELL | G_GENO | 2,
        Attack(AT_EXPL, AD_COLD, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_SILENT, MZ_SMALL, MR_COLD, MR_COLD,
        M1_FLY | M1_BREATHLESS | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 9, CLR_WHITE),
    # PM_FLAMING_SPHERE
    _mon(
        30, S_EYE, "flaming sphere",
        6, 13, 4, 0, 0, G_NOCORPSE | G_GENO | 2,
        Attack(AT_EXPL, AD_FIRE, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_SILENT, MZ_SMALL, MR_FIRE, MR_FIRE,
        M1_FLY | M1_BREATHLESS | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 9, CLR_RED),
    # PM_SHOCKING_SPHERE
    _mon(
        31, S_EYE, "shocking sphere",
        6, 13, 4, 0, 0, G_NOCORPSE | G_GENO | 2,
        Attack(AT_EXPL, AD_ELEC, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 10, MS_SILENT, MZ_SMALL, MR_ELEC, MR_ELEC,
        M1_FLY | M1_BREATHLESS | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 10, HI_ZAP),
    # ---- S_FELINE ----
    # PM_KITTEN
    _mon(
        32, S_FELINE, "kitten",
        2, 18, 6, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        150, 150, MS_MEW, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_WANDER | M2_DOMESTIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 3, HI_DOMESTIC),
    # PM_HOUSECAT
    _mon(
        33, S_FELINE, "housecat",
        4, 16, 5, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 200, MS_MEW, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_DOMESTIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, HI_DOMESTIC),
    # PM_JAGUAR
    _mon(
        34, S_FELINE, "jaguar",
        4, 15, 6, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_BITE, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE | M3_INFRAVISION, 6, CLR_BROWN),
    # PM_LYNX
    _mon(
        35, S_FELINE, "lynx",
        5, 15, 6, 0, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_BITE, AD_PHYS, 1, 10), NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_GROWL, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, CLR_CYAN),
    # PM_PANTHER
    _mon(
        36, S_FELINE, "panther",
        5, 15, 6, 0, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
        Attack(AT_BITE, AD_PHYS, 1, 10), NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, CLR_BLACK),
    # PM_LARGE_CAT
    _mon(
        37, S_FELINE, "large cat",
        6, 15, 4, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        250, 250, MS_MEW, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_STRONG | M2_DOMESTIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, HI_DOMESTIC),
    # PM_TIGER
    _mon(
        38, S_FELINE, "tiger",
        6, 12, 6, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 2, 4),
        Attack(AT_BITE, AD_PHYS, 1, 10), NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, CLR_YELLOW),
    # PM_DISPLACER_BEAST
    _mon(
        39, S_FELINE, "displacer beast",
        12, 12, -10, 0, -3, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 4, 4), Attack(AT_CLAW, AD_PHYS, 4, 4),
        Attack(AT_BITE, AD_PHYS, 2, 10), NO_ATK, NO_ATK, NO_ATK,
        750, 400, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION | M3_DISPLACES, 14, CLR_BLUE),
    # ---- S_GREMLIN ----
    # PM_GREMLIN
    _mon(
        40, S_GREMLIN, "gremlin",
        5, 12, 2, 25, -9, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
        Attack(AT_BITE, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_CURS, 0, 0), NO_ATK,
        NO_ATK,
        100, 20, MS_LAUGH, MZ_SMALL, MR_POISON, MR_POISON,
        M1_SWIM | M1_HUMANOID | M1_POIS, M2_STALK, M3_INFRAVISIBLE, 8,
        CLR_GREEN),
    # PM_GARGOYLE
    _mon(
        41, S_GREMLIN, "gargoyle",
        6, 10, -4, 0, -9, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 2, 6), Attack(AT_CLAW, AD_PHYS, 2, 6),
        Attack(AT_BITE, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK,
        1000, 200, MS_GRUNT, MZ_HUMAN, MR_STONE, MR_STONE,
        M1_HUMANOID | M1_THICK_HIDE | M1_BREATHLESS, M2_HOSTILE | M2_STRONG, 0,
        8, CLR_BROWN),
    # PM_WINGED_GARGOYLE
    _mon(
        42, S_GREMLIN, "winged gargoyle",
        9, 15, -2, 0, -12, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 3, 6), Attack(AT_CLAW, AD_PHYS, 3, 6),
        Attack(AT_BITE, AD_PHYS, 3, 4), NO_ATK, NO_ATK, NO_ATK,
        1200, 300, MS_GRUNT, MZ_HUMAN, MR_STONE, MR_STONE,
        M1_FLY | M1_HUMANOID | M1_THICK_HIDE | M1_BREATHLESS | M1_OVIPAROUS,
        M2_LORD | M2_HOSTILE | M2_STRONG | M2_MAGIC, 0, 11, HI_LORD),
    # ---- S_HUMANOID ----
    # PM_HOBBIT
    _mon(
        43, S_HUMANOID, "hobbit",
        1, 9, 10, 0, 6, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 200, MS_HUMANOID, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 2, CLR_GREEN),
    # PM_DWARF
    _mon(
        44, S_HUMANOID, "dwarf",
        2, 6, 10, 10, 4, G_GENO | 3,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        900, 300, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
        M2_DWARF | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 4, CLR_RED),
    # PM_BUGBEAR
    _mon(
        45, S_HUMANOID, "bugbear",
        3, 9, 5, 0, -6, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1250, 250, MS_GROWL, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, CLR_BROWN),
    # PM_DWARF_LEADER
    _mon(
        46, S_HUMANOID, _nams("dwarf lord", "dwarf lady", "dwarf leader"),
        4, 6, 10, 10, 5, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        900, 300, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
        M2_DWARF | M2_STRONG | M2_LORD | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 6, CLR_BLUE),
    # PM_DWARF_RULER
    _mon(
        47, S_HUMANOID, _nams("dwarf king", "dwarf queen", "dwarf ruler"),
        6, 6, 10, 20, 6, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        900, 300, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
        M2_DWARF | M2_STRONG | M2_PRINCE | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, HI_LORD),
    # PM_MIND_FLAYER
    _mon(
        48, S_HUMANOID, "mind flayer",
        9, 12, 5, 90, -8, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 4), Attack(AT_TENT, AD_DRIN, 2, 1),
        Attack(AT_TENT, AD_DRIN, 2, 1), Attack(AT_TENT, AD_DRIN, 2, 1), NO_ATK,
        NO_ATK,
        1450, 400, MS_HISS, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_FLY | M1_SEE_INVIS | M1_OMNIVORE,
        M2_HOSTILE | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 13, CLR_BRIGHT_MAGENTA),
    # PM_MASTER_MIND_FLAYER
    _mon(
        49, S_HUMANOID, "master mind flayer",
        13, 12, 0, 90, -8, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_TENT, AD_DRIN, 2, 1),
        Attack(AT_TENT, AD_DRIN, 2, 1), Attack(AT_TENT, AD_DRIN, 2, 1),
        Attack(AT_TENT, AD_DRIN, 2, 1), Attack(AT_TENT, AD_DRIN, 2, 1),
        1450, 400, MS_HISS, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_FLY | M1_SEE_INVIS | M1_OMNIVORE,
        M2_HOSTILE | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 19, CLR_BRIGHT_MAGENTA),
    # ---- S_IMP ----
    # PM_MANES
    _mon(
        50, S_IMP, "manes",
        1, 3, 7, 0, -7, G_GENO | G_LGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        100, 100, MS_SILENT, MZ_SMALL, MR_SLEEP | MR_POISON, 0,
        M1_POIS, M2_HOSTILE | M2_STALK, M3_INFRAVISIBLE | M3_INFRAVISION, 3,
        CLR_RED),
    # PM_HOMUNCULUS
    _mon(
        51, S_IMP, "homunculus",
        2, 12, 6, 10, -7, G_GENO | 2,
        Attack(AT_BITE, AD_SLEE, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        60, 100, MS_SILENT, MZ_TINY, MR_SLEEP | MR_POISON,
        MR_SLEEP | MR_POISON,
        M1_FLY | M1_POIS, M2_STALK, M3_INFRAVISIBLE | M3_INFRAVISION, 3,
        CLR_GREEN),
    # PM_IMP
    _mon(
        52, S_IMP, "imp",
        3, 12, 2, 20, -7, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        20, 10, MS_CUSS, MZ_TINY, 0, 0,
        M1_REGEN, M2_WANDER | M2_STALK, M3_INFRAVISIBLE | M3_INFRAVISION, 4,
        CLR_RED),
    # PM_LEMURE
    _mon(
        53, S_IMP, "lemure",
        3, 3, 7, 0, -7, G_HELL | G_GENO | G_LGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        150, 100, MS_SILENT, MZ_MEDIUM, MR_SLEEP | MR_POISON, MR_SLEEP,
        M1_POIS | M1_REGEN, M2_HOSTILE | M2_WANDER | M2_STALK | M2_NEUTER,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, CLR_BROWN),
    # PM_QUASIT
    _mon(
        54, S_IMP, "quasit",
        3, 15, 2, 20, -7, G_GENO | 2,
        Attack(AT_CLAW, AD_DRDX, 1, 2), Attack(AT_CLAW, AD_DRDX, 1, 2),
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        200, 200, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
        M1_REGEN, M2_STALK, M3_INFRAVISIBLE | M3_INFRAVISION, 7, CLR_BLUE),
    # PM_TENGU
    _mon(
        55, S_IMP, "tengu",
        6, 13, 5, 30, 7, G_GENO | 3,
        Attack(AT_BITE, AD_PHYS, 1, 7), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 200, MS_SQAWK, MZ_SMALL, MR_POISON, MR_POISON,
        M1_TPORT | M1_TPORT_CNTRL, M2_STALK, M3_INFRAVISIBLE | M3_INFRAVISION,
        7, CLR_CYAN),
    # ---- S_JELLY ----
    # PM_BLUE_JELLY
    _mon(
        56, S_JELLY, "blue jelly",
        4, 0, 8, 10, 0, G_GENO | 2,
        Attack(AT_NONE, AD_COLD, 0, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_COLD | MR_POISON,
        MR_COLD | MR_POISON,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 5, CLR_BLUE),
    # PM_SPOTTED_JELLY
    _mon(
        57, S_JELLY, "spotted jelly",
        5, 0, 8, 10, 0, G_GENO | 1,
        Attack(AT_NONE, AD_ACID, 0, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_ACID | MR_STONE,
        MR_ACID | MR_STONE,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 6, CLR_GREEN),
    # PM_OCHRE_JELLY
    _mon(
        58, S_JELLY, "ochre jelly",
        6, 3, 8, 20, 0, G_GENO | 2,
        Attack(AT_ENGL, AD_ACID, 3, 6), Attack(AT_NONE, AD_ACID, 3, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_JELLY, 20, MS_SILENT, MZ_MEDIUM, MR_ACID | MR_STONE,
        MR_ACID | MR_STONE,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 8, CLR_BROWN),
    # ---- S_KOBOLD ----
    # PM_KOBOLD
    _mon(
        59, S_KOBOLD, "kobold",
        0, 6, 10, 0, -2, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 100, MS_ORC, MZ_SMALL, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 1, CLR_BROWN),
    # PM_LARGE_KOBOLD
    _mon(
        60, S_KOBOLD, "large kobold",
        1, 6, 10, 0, -3, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        450, 150, MS_ORC, MZ_SMALL, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 2, CLR_RED),
    # PM_KOBOLD_LEADER
    _mon(
        61, S_KOBOLD, _nams("kobold lord", "kobold lady", "kobold leader"),
        2, 6, 10, 0, -4, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 200, MS_ORC, MZ_SMALL, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_LORD | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 3, HI_LORD),
    # PM_KOBOLD_SHAMAN
    _mon(
        62, S_KOBOLD, "kobold shaman",
        2, 6, 6, 10, -4, G_GENO | 1,
        Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        450, 150, MS_ORC, MZ_SMALL, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_OMNIVORE, M2_HOSTILE | M2_MAGIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 4, HI_ZAP),
    # ---- S_LEPRECHAUN ----
    # PM_LEPRECHAUN
    _mon(
        63, S_LEPRECHAUN, "leprechaun",
        5, 15, 8, 20, 0, G_GENO | 4,
        Attack(AT_CLAW, AD_SGLD, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        60, 30, MS_LAUGH, MZ_TINY, 0, 0,
        M1_HUMANOID | M1_TPORT, M2_HOSTILE | M2_GREEDY, M3_INFRAVISIBLE, 4,
        CLR_GREEN),
    # ---- S_MIMIC ----
    # PM_SMALL_MIMIC
    _mon(
        64, S_MIMIC, "small mimic",
        7, 3, 7, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 3, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 200, MS_SILENT, MZ_MEDIUM, MR_ACID, 0,
        M1_BREATHLESS | M1_AMORPHOUS | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOHEAD | M1_NOLIMBS | M1_THICK_HIDE | M1_CARNIVORE,
        M2_HOSTILE, 0, 8, CLR_BROWN),
    # PM_LARGE_MIMIC
    _mon(
        65, S_MIMIC, "large mimic",
        8, 3, 7, 10, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_STCK, 3, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        600, 400, MS_SILENT, MZ_LARGE, MR_ACID, 0,
        M1_CLING | M1_BREATHLESS | M1_AMORPHOUS | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOHEAD | M1_NOLIMBS | M1_THICK_HIDE | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG, 0, 9, CLR_RED),
    # PM_GIANT_MIMIC
    _mon(
        66, S_MIMIC, "giant mimic",
        9, 3, 7, 20, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_STCK, 3, 6), Attack(AT_CLAW, AD_STCK, 3, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        800, 500, MS_SILENT, MZ_LARGE, MR_ACID, 0,
        M1_CLING | M1_BREATHLESS | M1_AMORPHOUS | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOHEAD | M1_NOLIMBS | M1_THICK_HIDE | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG, 0, 11, HI_LORD),
    # ---- S_NYMPH ----
    # PM_WOOD_NYMPH
    _mon(
        67, S_NYMPH, "wood nymph",
        3, 12, 9, 20, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_SITM, 0, 0), Attack(AT_CLAW, AD_SEDU, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_NYMPH, 300, MS_SEDUCE, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_TPORT, M2_HOSTILE | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE, 5, CLR_GREEN),
    # PM_WATER_NYMPH
    _mon(
        68, S_NYMPH, "water nymph",
        3, 12, 9, 20, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_SITM, 0, 0), Attack(AT_CLAW, AD_SEDU, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_NYMPH, 300, MS_SEDUCE, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_TPORT | M1_SWIM, M2_HOSTILE | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE, 5, CLR_BLUE),
    # PM_MOUNTAIN_NYMPH
    _mon(
        69, S_NYMPH, "mountain nymph",
        3, 12, 9, 20, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_SITM, 0, 0), Attack(AT_CLAW, AD_SEDU, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_NYMPH, 300, MS_SEDUCE, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_TPORT, M2_HOSTILE | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE, 5, CLR_BROWN),
    # ---- S_ORC ----
    # PM_GOBLIN
    _mon(
        70, S_ORC, "goblin",
        0, 6, 10, 0, -3, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 100, MS_ORC, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 1, CLR_GRAY),
    # PM_HOBGOBLIN
    _mon(
        71, S_ORC, "hobgoblin",
        1, 9, 10, 0, -4, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1000, 200, MS_ORC, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 3, CLR_BROWN),
    # PM_ORC
    _mon(
        72, S_ORC, "orc",
        1, 9, 10, 0, -3, G_GENO | G_NOGEN | G_LGROUP,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        850, 150, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 3, CLR_RED),
    # PM_HILL_ORC
    _mon(
        73, S_ORC, "hill orc",
        2, 9, 10, 0, -4, G_GENO | G_LGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1000, 200, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 4, CLR_YELLOW),
    # PM_MORDOR_ORC
    _mon(
        74, S_ORC, "Mordor orc",
        3, 5, 10, 0, -5, G_GENO | G_LGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1200, 200, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, CLR_BLUE),
    # PM_URUK_HAI
    _mon(
        75, S_ORC, "Uruk-hai",
        3, 7, 10, 0, -4, G_GENO | G_LGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1300, 300, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, CLR_BLACK),
    # PM_ORC_SHAMAN
    _mon(
        76, S_ORC, "orc shaman",
        3, 9, 5, 10, -5, G_GENO | 1,
        Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1000, 300, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_ORC | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, HI_ZAP),
    # PM_ORC_CAPTAIN
    _mon(
        77, S_ORC, "orc-captain",
        5, 5, 10, 0, -5, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1350, 350, MS_ORC, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_ORC | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, HI_LORD),
    # ---- S_PIERCER ----
    # PM_ROCK_PIERCER
    _mon(
        78, S_PIERCER, "rock piercer",
        3, 1, 3, 0, 0, G_GENO | 4,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 200, MS_SILENT, MZ_SMALL, 0, 0,
        M1_CLING | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE, 0, 4, CLR_GRAY),
    # PM_IRON_PIERCER
    _mon(
        79, S_PIERCER, "iron piercer",
        5, 1, 0, 0, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 300, MS_SILENT, MZ_MEDIUM, 0, 0,
        M1_CLING | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE, 0, 6, CLR_CYAN),
    # PM_GLASS_PIERCER
    _mon(
        80, S_PIERCER, "glass piercer",
        7, 1, 0, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 300, MS_SILENT, MZ_MEDIUM, MR_ACID, 0,
        M1_CLING | M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE, 0, 9, CLR_WHITE),
    # ---- S_QUADRUPED ----
    # PM_ROTHE
    _mon(
        81, S_QUADRUPED, "rothe",
        2, 9, 7, 0, 0, G_GENO | G_SGROUP | 4,
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_BITE, AD_PHYS, 1, 3),
        Attack(AT_BITE, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK,
        400, 100, MS_MOO, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 4,
        CLR_BROWN),
    # PM_MUMAK
    _mon(
        82, S_QUADRUPED, "mumak",
        5, 9, 0, 0, -2, G_GENO | 1,
        Attack(AT_BUTT, AD_PHYS, 4, 12), Attack(AT_BITE, AD_PHYS, 2, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2500, 500, MS_TRUMPET, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_THICK_HIDE | M1_NOHANDS | M1_HERBIVORE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 7, CLR_GRAY),
    # PM_LEOCROTTA
    _mon(
        83, S_QUADRUPED, "leocrotta",
        6, 18, 4, 10, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 2, 6), Attack(AT_BITE, AD_PHYS, 2, 6),
        Attack(AT_CLAW, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1200, 500, MS_IMITATE, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE, M2_HOSTILE | M2_STRONG,
        M3_INFRAVISIBLE, 8, CLR_RED),
    # PM_WUMPUS
    _mon(
        84, S_QUADRUPED, "wumpus",
        8, 3, 2, 10, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2500, 500, MS_BURBLE, MZ_LARGE, 0, 0,
        M1_CLING | M1_ANIMAL | M1_NOHANDS | M1_OMNIVORE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 9, CLR_CYAN),
    # PM_TITANOTHERE
    _mon(
        85, S_QUADRUPED, "titanothere",
        12, 12, 6, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2650, 650, MS_BELLOW, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_THICK_HIDE | M1_NOHANDS | M1_HERBIVORE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 13, CLR_GRAY),
    # PM_BALUCHITHERIUM
    _mon(
        86, S_QUADRUPED, "baluchitherium",
        14, 12, 5, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 5, 4), Attack(AT_CLAW, AD_PHYS, 5, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        3800, 800, MS_BELLOW, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_THICK_HIDE | M1_NOHANDS | M1_HERBIVORE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 15, CLR_GRAY),
    # PM_MASTODON
    _mon(
        87, S_QUADRUPED, "mastodon",
        20, 12, 5, 0, 0, G_GENO | 1,
        Attack(AT_BUTT, AD_PHYS, 4, 8), Attack(AT_BUTT, AD_PHYS, 4, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        3800, 800, MS_TRUMPET, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_THICK_HIDE | M1_NOHANDS | M1_HERBIVORE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 22, CLR_BLACK),
    # ---- S_RODENT ----
    # PM_SEWER_RAT
    _mon(
        88, S_RODENT, "sewer rat",
        0, 12, 7, 0, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        20, 12, MS_SQEEK, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 1,
        CLR_BROWN),
    # PM_GIANT_RAT
    _mon(
        89, S_RODENT, "giant rat",
        1, 10, 7, 0, 0, G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_SQEEK, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 2,
        CLR_BROWN),
    # PM_RABID_RAT
    _mon(
        90, S_RODENT, "rabid rat",
        2, 12, 6, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_DRCO, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 5, MS_SQEEK, MZ_TINY, MR_POISON, 0,
        M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_CARNIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE, 4, CLR_BROWN),
    # PM_WERERAT
    _mon(
        91, S_RODENT, "wererat",
        2, 12, 6, 10, -7, G_NOGEN | G_NOCORPSE,
        Attack(AT_BITE, AD_WERE, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        40, 30, MS_SQEEK, MZ_TINY, MR_POISON, 0,
        M1_NOHANDS | M1_POIS | M1_REGEN | M1_CARNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE, M3_INFRAVISIBLE, 4, CLR_BROWN),
    # PM_ROCK_MOLE
    _mon(
        92, S_RODENT, "rock mole",
        3, 3, 0, 20, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_SILENT, MZ_SMALL, 0, 0,
        M1_TUNNEL | M1_ANIMAL | M1_NOHANDS | M1_METALLIVORE,
        M2_HOSTILE | M2_GREEDY | M2_JEWELS | M2_COLLECT, M3_INFRAVISIBLE, 4,
        CLR_GRAY),
    # PM_WOODCHUCK
    _mon(
        93, S_RODENT, "woodchuck",
        3, 3, 0, 20, 0, G_NOGEN | G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_SILENT, MZ_SMALL, 0, 0,
        M1_TUNNEL | M1_ANIMAL | M1_NOHANDS | M1_SWIM | M1_HERBIVORE,
        M2_WANDER | M2_HOSTILE, M3_INFRAVISIBLE, 4, CLR_BROWN),
    # ---- S_SPIDER ----
    # PM_CAVE_SPIDER
    _mon(
        94, S_SPIDER, "cave spider",
        1, 12, 3, 0, 0, G_GENO | G_SGROUP | 2,
        Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 50, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
        M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE, 0, 3, CLR_GRAY),
    # PM_CENTIPEDE
    _mon(
        95, S_SPIDER, "centipede",
        2, 4, 3, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_DRST, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 50, MS_SILENT, MZ_TINY, MR_POISON, MR_POISON,
        M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE, 0, 4, CLR_YELLOW),
    # PM_GIANT_SPIDER
    _mon(
        96, S_SPIDER, "giant spider",
        5, 15, 4, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_DRST, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 100, MS_SILENT, MZ_LARGE, MR_POISON, MR_POISON,
        M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG, 0, 7, CLR_MAGENTA),
    # PM_SCORPION
    _mon(
        97, S_SPIDER, "scorpion",
        5, 15, 3, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 2),
        Attack(AT_STNG, AD_DRST, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        50, 100, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
        M1_CONCEAL | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
        M2_HOSTILE, 0, 8, CLR_RED),
    # ---- S_TRAPPER ----
    # PM_LURKER_ABOVE
    _mon(
        98, S_TRAPPER, "lurker above",
        10, 3, 3, 0, 0, G_GENO | 2,
        Attack(AT_ENGL, AD_WRAP, 1, 6), Attack(AT_ENGL, AD_PHYS, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        800, 350, MS_SILENT, MZ_HUGE, 0, 0,
        M1_HIDE | M1_FLY | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_CARNIVORE,
        M2_HOSTILE | M2_STALK | M2_STRONG, 0, 12, CLR_GRAY),
    # PM_TRAPPER
    _mon(
        99, S_TRAPPER, "trapper",
        12, 3, 3, 0, 0, G_GENO | 2,
        Attack(AT_ENGL, AD_WRAP, 1, 8), Attack(AT_ENGL, AD_PHYS, 2, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        800, 350, MS_SILENT, MZ_HUGE, 0, 0,
        M1_HIDE | M1_ANIMAL | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_CARNIVORE,
        M2_HOSTILE | M2_STALK | M2_STRONG, 0, 14, CLR_GREEN),
    # ---- S_UNICORN ----
    # PM_PONY
    _mon(
        100, S_UNICORN, "pony",
        3, 16, 6, 0, 0, G_GENO | 2,
        Attack(AT_KICK, AD_PHYS, 1, 6), Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1300, 250, MS_NEIGH, MZ_MEDIUM, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_HERBIVORE,
        M2_WANDER | M2_STRONG | M2_DOMESTIC, M3_INFRAVISIBLE, 4, CLR_BROWN),
    # PM_WHITE_UNICORN
    _mon(
        101, S_UNICORN, "white unicorn",
        4, 24, 2, 70, 7, G_GENO | 2,
        Attack(AT_BUTT, AD_PHYS, 1, 12), Attack(AT_KICK, AD_PHYS, 1, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1300, 300, MS_NEIGH, MZ_LARGE, MR_POISON, MR_POISON,
        M1_NOHANDS | M1_HERBIVORE, M2_WANDER | M2_STRONG | M2_JEWELS,
        M3_INFRAVISIBLE, 6, CLR_WHITE),
    # PM_GRAY_UNICORN
    _mon(
        102, S_UNICORN, "gray unicorn",
        4, 24, 2, 70, 0, G_GENO | 1,
        Attack(AT_BUTT, AD_PHYS, 1, 12), Attack(AT_KICK, AD_PHYS, 1, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1300, 300, MS_NEIGH, MZ_LARGE, MR_POISON, MR_POISON,
        M1_NOHANDS | M1_HERBIVORE, M2_WANDER | M2_STRONG | M2_JEWELS,
        M3_INFRAVISIBLE, 6, CLR_GRAY),
    # PM_BLACK_UNICORN
    _mon(
        103, S_UNICORN, "black unicorn",
        4, 24, 2, 70, -7, G_GENO | 1,
        Attack(AT_BUTT, AD_PHYS, 1, 12), Attack(AT_KICK, AD_PHYS, 1, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1300, 300, MS_NEIGH, MZ_LARGE, MR_POISON, MR_POISON,
        M1_NOHANDS | M1_HERBIVORE, M2_WANDER | M2_STRONG | M2_JEWELS,
        M3_INFRAVISIBLE, 6, CLR_BLACK),
    # PM_HORSE
    _mon(
        104, S_UNICORN, "horse",
        5, 20, 5, 0, 0, G_GENO | 2,
        Attack(AT_KICK, AD_PHYS, 1, 8), Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1500, 300, MS_NEIGH, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_HERBIVORE,
        M2_WANDER | M2_STRONG | M2_DOMESTIC, M3_INFRAVISIBLE, 7, CLR_BROWN),
    # PM_WARHORSE
    _mon(
        105, S_UNICORN, "warhorse",
        7, 24, 4, 0, 0, G_GENO | 2,
        Attack(AT_KICK, AD_PHYS, 1, 10), Attack(AT_BITE, AD_PHYS, 1, 4),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1800, 350, MS_NEIGH, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_HERBIVORE,
        M2_WANDER | M2_STRONG | M2_DOMESTIC, M3_INFRAVISIBLE, 9, CLR_BROWN),
    # ---- S_VORTEX ----
    # PM_FOG_CLOUD
    _mon(
        106, S_VORTEX, "fog cloud",
        3, 1, 0, 0, 0, G_GENO | G_NOCORPSE | 2,
        Attack(AT_ENGL, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE, MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_AMORPHOUS | M1_UNSOLID,
        M2_HOSTILE | M2_NEUTER, 0, 4, CLR_GRAY),
    # PM_DUST_VORTEX
    _mon(
        107, S_VORTEX, "dust vortex",
        4, 20, 2, 30, 0, G_GENO | G_NOCORPSE | 2,
        Attack(AT_ENGL, AD_BLND, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE, MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
        M2_HOSTILE | M2_NEUTER, 0, 6, CLR_BROWN),
    # PM_ICE_VORTEX
    _mon(
        108, S_VORTEX, "ice vortex",
        5, 20, 2, 30, 0, G_NOHELL | G_GENO | G_NOCORPSE | 1,
        Attack(AT_ENGL, AD_COLD, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
        MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 7, CLR_CYAN),
    # PM_ENERGY_VORTEX
    _mon(
        109, S_VORTEX, "energy vortex",
        6, 20, 2, 30, 0, G_GENO | G_NOCORPSE | 1,
        Attack(AT_ENGL, AD_ELEC, 1, 6), Attack(AT_ENGL, AD_DREN, 2, 6),
        Attack(AT_NONE, AD_ELEC, 0, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
        MR_ELEC | MR_SLEEP | MR_DISINT | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID,
        M2_HOSTILE | M2_NEUTER, 0, 9, HI_ZAP),
    # PM_STEAM_VORTEX
    _mon(
        110, S_VORTEX, "steam vortex",
        7, 22, 2, 30, 0, G_HELL | G_GENO | G_NOCORPSE | 2,
        Attack(AT_ENGL, AD_FIRE, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
        MR_FIRE | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 9, CLR_BLUE),
    # PM_FIRE_VORTEX
    _mon(
        111, S_VORTEX, "fire vortex",
        8, 22, 2, 30, 0, G_HELL | G_GENO | G_NOCORPSE | 1,
        Attack(AT_ENGL, AD_FIRE, 1, 10), Attack(AT_NONE, AD_FIRE, 0, 4),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE,
        MR_FIRE | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 10, CLR_YELLOW),
    # ---- S_WORM ----
    # PM_BABY_LONG_WORM
    _mon(
        112, S_WORM, "baby long worm",
        5, 3, 5, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        600, 250, MS_SILENT, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE, 0, 6, CLR_BROWN),
    # PM_BABY_PURPLE_WORM
    _mon(
        113, S_WORM, "baby purple worm",
        8, 3, 5, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        600, 250, MS_SILENT, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_CARNIVORE, M2_HOSTILE, 0, 9,
        CLR_MAGENTA),
    # PM_LONG_WORM
    _mon(
        114, S_WORM, "long worm",
        9, 3, 5, 10, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1500, 500, MS_SILENT, MZ_GIGANTIC, 0, 0,
        M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_OVIPAROUS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE | M2_STRONG | M2_NASTY, 0, 10, CLR_BROWN),
    # PM_PURPLE_WORM
    _mon(
        115, S_WORM, "purple worm",
        15, 9, 6, 20, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 2, 8), Attack(AT_ENGL, AD_DGST, 1, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2700, 700, MS_SILENT, MZ_GIGANTIC, 0, 0,
        M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY, 0, 17, CLR_MAGENTA),
    # ---- S_XAN ----
    # PM_GRID_BUG
    _mon(
        116, S_XAN, "grid bug",
        0, 12, 9, 0, 0, G_GENO | G_SGROUP | G_NOCORPSE | 3,
        Attack(AT_BITE, AD_ELEC, 1, 1), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        15, 10, MS_BUZZ, MZ_TINY, MR_ELEC | MR_POISON, 0,
        M1_ANIMAL | M1_NOHANDS, M2_HOSTILE, M3_INFRAVISIBLE, 1, CLR_MAGENTA),
    # PM_XAN
    _mon(
        117, S_XAN, "xan",
        7, 18, -4, 0, 0, G_GENO | 3,
        Attack(AT_STNG, AD_LEGS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        300, 300, MS_BUZZ, MZ_TINY, MR_POISON, MR_POISON,
        M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_POIS, M2_HOSTILE, M3_INFRAVISIBLE,
        9, CLR_RED),
    # ---- S_LIGHT ----
    # PM_YELLOW_LIGHT
    _mon(
        118, S_LIGHT, "yellow light",
        3, 15, 0, 0, 0, G_NOCORPSE | G_GENO | 4,
        Attack(AT_EXPL, AD_BLND, 10, 20), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_SMALL,
        MR_FIRE | MR_COLD | MR_ELEC | MR_DISINT | MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
        0,
        M1_FLY | M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 5, CLR_YELLOW),
    # PM_BLACK_LIGHT
    _mon(
        119, S_LIGHT, "black light",
        5, 15, 0, 0, 0, G_NOCORPSE | G_GENO | 2,
        Attack(AT_EXPL, AD_HALU, 10, 12), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_SMALL,
        MR_FIRE | MR_COLD | MR_ELEC | MR_DISINT | MR_SLEEP | MR_POISON | MR_ACID | MR_STONE,
        0,
        M1_FLY | M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_UNSOLID | M1_SEE_INVIS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 7, CLR_BLACK),
    # ---- S_ZRUTY ----
    # PM_ZRUTY
    _mon(
        120, S_ZRUTY, "zruty",
        9, 8, 3, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 3, 4), Attack(AT_CLAW, AD_PHYS, 3, 4),
        Attack(AT_BITE, AD_PHYS, 3, 6), NO_ATK, NO_ATK, NO_ATK,
        1200, 600, MS_SILENT, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE, M2_HOSTILE | M2_STRONG,
        M3_INFRAVISIBLE, 11, CLR_BROWN),
    # ---- S_ANGEL ----
    # PM_COUATL
    _mon(
        121, S_ANGEL, "couatl",
        8, 10, 5, 30, 7, G_NOHELL | G_SGROUP | G_NOCORPSE | 1,
        Attack(AT_BITE, AD_DRST, 2, 4), Attack(AT_BITE, AD_PHYS, 1, 3),
        Attack(AT_HUGS, AD_WRAP, 2, 4), NO_ATK, NO_ATK, NO_ATK,
        900, 400, MS_HISS, MZ_LARGE, MR_POISON, 0,
        M1_FLY | M1_NOHANDS | M1_SLITHY | M1_POIS,
        M2_MINION | M2_STALK | M2_STRONG | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_GREEN),
    # PM_ALEAX
    _mon(
        122, S_ANGEL, "Aleax",
        10, 8, 0, 30, 7, G_NOHELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6),
        Attack(AT_KICK, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_IMITATE, MZ_HUMAN,
        MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_HUMANOID | M1_SEE_INVIS,
        M2_MINION | M2_STALK | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 12, CLR_YELLOW),
    # PM_ANGEL
    _mon(
        123, S_ANGEL, "Angel",
        14, 10, -4, 55, 12, G_NOHELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_MAGC, AD_MAGM, 2, 6), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_CUSS, MZ_HUMAN,
        MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_HUMANOID | M1_SEE_INVIS,
        M2_NOPOLY | M2_MINION | M2_STALK | M2_STRONG | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 19, CLR_WHITE),
    # PM_KI_RIN
    _mon(
        124, S_ANGEL, "ki-rin",
        16, 18, -5, 90, 15, G_NOHELL | G_NOCORPSE | 1,
        Attack(AT_KICK, AD_PHYS, 2, 4), Attack(AT_KICK, AD_PHYS, 2, 4),
        Attack(AT_BUTT, AD_PHYS, 3, 6), Attack(AT_MAGC, AD_SPEL, 2, 6), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_SPELL, MZ_LARGE, MR_POISON, 0,
        M1_FLY | M1_NOHANDS | M1_SEE_INVIS,
        M2_NOPOLY | M2_MINION | M2_STALK | M2_STRONG | M2_NASTY | M2_LORD,
        M3_INFRAVISIBLE | M3_INFRAVISION, 21, HI_GOLD),
    # PM_ARCHON
    _mon(
        125, S_ANGEL, "Archon",
        19, 16, -6, 80, 15, G_NOHELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4),
        Attack(AT_GAZE, AD_BLND, 2, 6), Attack(AT_CLAW, AD_PHYS, 1, 8),
        Attack(AT_MAGC, AD_SPEL, 4, 6), NO_ATK,
        WT_HUMAN, 400, MS_CUSS, MZ_LARGE,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_HUMANOID | M1_SEE_INVIS | M1_REGEN,
        M2_NOPOLY | M2_MINION | M2_STALK | M2_STRONG | M2_NASTY | M2_LORD | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 26, HI_LORD),
    # ---- S_BAT ----
    # PM_BAT
    _mon(
        126, S_BAT, "bat",
        0, 22, 8, 0, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        20, 20, MS_SQEEK, MZ_TINY, 0, 0,
        M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_WANDER,
        M3_INFRAVISIBLE, 2, CLR_BROWN),
    # PM_GIANT_BAT
    _mon(
        127, S_BAT, "giant bat",
        2, 22, 7, 0, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_SQEEK, MZ_SMALL, 0, 0,
        M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_WANDER | M2_HOSTILE,
        M3_INFRAVISIBLE, 3, CLR_RED),
    # PM_RAVEN
    _mon(
        128, S_BAT, "raven",
        4, 20, 6, 0, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_BLND, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        40, 20, MS_SQAWK, MZ_SMALL, 0, 0,
        M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_WANDER | M2_HOSTILE, M3_INFRAVISIBLE, 6, CLR_BLACK),
    # PM_VAMPIRE_BAT
    _mon(
        129, S_BAT, "vampire bat",
        5, 20, 6, 0, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 1, 6), Attack(AT_BITE, AD_DRST, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        30, 20, MS_SQEEK, MZ_SMALL, MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_ANIMAL | M1_NOHANDS | M1_POIS | M1_REGEN | M1_OMNIVORE,
        M2_HOSTILE, M3_INFRAVISIBLE, 7, CLR_BLACK),
    # ---- S_CENTAUR ----
    # PM_PLAINS_CENTAUR
    _mon(
        130, S_CENTAUR, "plains centaur",
        4, 18, 4, 0, 0, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_KICK, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2500, 500, MS_HUMANOID, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_STRONG | M2_GREEDY | M2_COLLECT,
        M3_INFRAVISIBLE, 6, CLR_BROWN),
    # PM_FOREST_CENTAUR
    _mon(
        131, S_CENTAUR, "forest centaur",
        5, 18, 3, 10, -1, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_KICK, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2550, 600, MS_HUMANOID, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_STRONG | M2_GREEDY | M2_COLLECT,
        M3_INFRAVISIBLE, 8, CLR_GREEN),
    # PM_MOUNTAIN_CENTAUR
    _mon(
        132, S_CENTAUR, "mountain centaur",
        6, 20, 2, 10, -3, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 10), Attack(AT_KICK, AD_PHYS, 1, 6),
        Attack(AT_KICK, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK,
        2550, 500, MS_HUMANOID, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_STRONG | M2_GREEDY | M2_COLLECT,
        M3_INFRAVISIBLE, 9, CLR_CYAN),
    # ---- S_DRAGON ----
    # PM_BABY_GRAY_DRAGON
    _mon(
        133, S_DRAGON, "baby gray dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, 0, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_GRAY),
    # PM_BABY_GOLD_DRAGON
    _mon(
        134, S_DRAGON, "baby gold dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, 0, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, M3_INFRAVISIBLE, 13,
        HI_GOLD),
    # PM_BABY_SILVER_DRAGON
    _mon(
        135, S_DRAGON, "baby silver dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, 0, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, DRAGON_SILVER),
    # PM_BABY_RED_DRAGON
    _mon(
        136, S_DRAGON, "baby red dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_FIRE, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, M3_INFRAVISIBLE, 13,
        CLR_RED),
    # PM_BABY_WHITE_DRAGON
    _mon(
        137, S_DRAGON, "baby white dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_COLD, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_WHITE),
    # PM_BABY_ORANGE_DRAGON
    _mon(
        138, S_DRAGON, "baby orange dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_SLEEP, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_ORANGE),
    # PM_BABY_BLACK_DRAGON
    _mon(
        139, S_DRAGON, "baby black dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_DISINT, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_BLACK),
    # PM_BABY_BLUE_DRAGON
    _mon(
        140, S_DRAGON, "baby blue dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_ELEC, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_BLUE),
    # PM_BABY_GREEN_DRAGON
    _mon(
        141, S_DRAGON, "baby green dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_POISON, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE | M1_POIS,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_GREEN),
    # PM_BABY_YELLOW_DRAGON
    _mon(
        142, S_DRAGON, "baby yellow dragon",
        12, 9, 2, 10, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_BABY_DRAGON, 500, MS_ROAR, MZ_HUGE, MR_ACID | MR_STONE, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE | M1_ACID,
        M2_HOSTILE | M2_STRONG | M2_GREEDY | M2_JEWELS, 0, 13, CLR_YELLOW),
    # PM_GRAY_DRAGON
    _mon(
        143, S_DRAGON, "gray dragon",
        15, 9, -1, 20, 4, G_GENO | 1,
        Attack(AT_BREA, AD_MAGM, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, 0, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_GRAY),
    # PM_GOLD_DRAGON
    _mon(
        144, S_DRAGON, "gold dragon",
        15, 9, -1, 20, 4, G_GENO | 1,
        Attack(AT_BREA, AD_FIRE, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_FIRE, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        M3_INFRAVISIBLE, 20, HI_GOLD),
    # PM_SILVER_DRAGON
    _mon(
        145, S_DRAGON, "silver dragon",
        15, 9, -1, 20, 4, G_GENO | 1,
        Attack(AT_BREA, AD_COLD, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_COLD, 0,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, DRAGON_SILVER),
    # PM_RED_DRAGON
    _mon(
        146, S_DRAGON, "red dragon",
        15, 9, -1, 20, -4, G_GENO | 1,
        Attack(AT_BREA, AD_FIRE, 6, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_FIRE, MR_FIRE,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        M3_INFRAVISION | M3_INFRAVISIBLE, 20, CLR_RED),
    # PM_WHITE_DRAGON
    _mon(
        147, S_DRAGON, "white dragon",
        15, 9, -1, 20, -5, G_GENO | 1,
        Attack(AT_BREA, AD_COLD, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_COLD, MR_COLD,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_WHITE),
    # PM_ORANGE_DRAGON
    _mon(
        148, S_DRAGON, "orange dragon",
        15, 9, -1, 20, 5, G_GENO | 1,
        Attack(AT_BREA, AD_SLEE, 4, 25), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_SLEEP, MR_SLEEP,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_ORANGE),
    # PM_BLACK_DRAGON
    _mon(
        149, S_DRAGON, "black dragon",
        15, 9, -1, 20, -6, G_GENO | 1,
        Attack(AT_BREA, AD_DISN, 1, 255), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_DISINT, MR_DISINT,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_BLACK),
    # PM_BLUE_DRAGON
    _mon(
        150, S_DRAGON, "blue dragon",
        15, 9, -1, 20, -7, G_GENO | 1,
        Attack(AT_BREA, AD_ELEC, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_ELEC, MR_ELEC,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_BLUE),
    # PM_GREEN_DRAGON
    _mon(
        151, S_DRAGON, "green dragon",
        15, 9, -1, 20, 6, G_GENO | 1,
        Attack(AT_BREA, AD_DRST, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_POISON, MR_POISON,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE | M1_POIS,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_GREEN),
    # PM_YELLOW_DRAGON
    _mon(
        152, S_DRAGON, "yellow dragon",
        15, 9, -1, 20, 7, G_GENO | 1,
        Attack(AT_BREA, AD_ACID, 4, 6), Attack(AT_BITE, AD_PHYS, 3, 8),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK,
        NO_ATK,
        WT_DRAGON, 1500, MS_ROAR, MZ_GIGANTIC, MR_ACID | MR_STONE,
        MR_ACID | MR_STONE,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_SEE_INVIS | M1_OVIPAROUS | M1_CARNIVORE | M1_ACID,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        0, 20, CLR_YELLOW),
    # ---- S_ELEMENTAL ----
    # PM_STALKER
    _mon(
        153, S_ELEMENTAL, "stalker",
        8, 12, 3, 0, 0, G_GENO | 3,
        Attack(AT_CLAW, AD_PHYS, 4, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        900, 400, MS_SILENT, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_FLY | M1_SEE_INVIS,
        M2_WANDER | M2_STALK | M2_HOSTILE | M2_STRONG, M3_INFRAVISION, 9,
        CLR_WHITE),
    # PM_AIR_ELEMENTAL
    _mon(
        154, S_ELEMENTAL, "air elemental",
        8, 36, 2, 30, 0, G_NOCORPSE | 1,
        Attack(AT_ENGL, AD_PHYS, 1, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE, MR_POISON | MR_STONE, 0,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS | M1_UNSOLID | M1_FLY,
        M2_STRONG | M2_NEUTER, 0, 10, CLR_CYAN),
    # PM_FIRE_ELEMENTAL
    _mon(
        155, S_ELEMENTAL, "fire elemental",
        8, 12, 2, 30, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_FIRE, 3, 6), Attack(AT_NONE, AD_FIRE, 0, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUGE, MR_FIRE | MR_POISON | MR_STONE, 0,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS | M1_UNSOLID | M1_FLY | M1_NOTAKE,
        M2_STRONG | M2_NEUTER, M3_INFRAVISIBLE, 10, CLR_YELLOW),
    # PM_EARTH_ELEMENTAL
    _mon(
        156, S_ELEMENTAL, "earth elemental",
        8, 6, 2, 30, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 4, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2500, 0, MS_SILENT, MZ_HUGE, MR_FIRE | MR_COLD | MR_POISON | MR_STONE,
        0,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS | M1_WALLWALK | M1_THICK_HIDE,
        M2_STRONG | M2_NEUTER, 0, 10, CLR_BROWN),
    # PM_WATER_ELEMENTAL
    _mon(
        157, S_ELEMENTAL, "water elemental",
        8, 5, 2, 30, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 5, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2500, 0, MS_SILENT, MZ_HUGE, MR_POISON | MR_STONE, 0,
        M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_BREATHLESS | M1_UNSOLID | M1_AMPHIBIOUS | M1_SWIM,
        M2_STRONG | M2_NEUTER, 0, 10, CLR_BLUE),
    # ---- S_FUNGUS ----
    # PM_LICHEN
    _mon(
        158, S_FUNGUS, "lichen",
        0, 1, 9, 0, 0, G_GENO | 4,
        Attack(AT_TUCH, AD_STCK, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        20, 200, MS_SILENT, MZ_SMALL, 0, 0,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 1, CLR_BRIGHT_GREEN),
    # PM_BROWN_MOLD
    _mon(
        159, S_FUNGUS, "brown mold",
        1, 0, 9, 0, 0, G_GENO | 1,
        Attack(AT_NONE, AD_COLD, 0, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 30, MS_SILENT, MZ_SMALL, MR_COLD | MR_POISON, MR_COLD | MR_POISON,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 2, CLR_BROWN),
    # PM_YELLOW_MOLD
    _mon(
        160, S_FUNGUS, "yellow mold",
        1, 0, 9, 0, 0, G_GENO | 2,
        Attack(AT_NONE, AD_STUN, 0, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 30, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_POIS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 2, CLR_YELLOW),
    # PM_GREEN_MOLD
    _mon(
        161, S_FUNGUS, "green mold",
        1, 0, 9, 0, 0, G_GENO | 1,
        Attack(AT_NONE, AD_ACID, 0, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 30, MS_SILENT, MZ_SMALL, MR_ACID | MR_STONE, MR_ACID | MR_STONE,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_ACID | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 2, CLR_GREEN),
    # PM_RED_MOLD
    _mon(
        162, S_FUNGUS, "red mold",
        1, 0, 9, 0, 0, G_GENO | 1,
        Attack(AT_NONE, AD_FIRE, 0, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 30, MS_SILENT, MZ_SMALL, MR_FIRE | MR_POISON, MR_FIRE | MR_POISON,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, M3_INFRAVISIBLE, 2, CLR_RED),
    # PM_SHRIEKER
    _mon(
        163, S_FUNGUS, "shrieker",
        3, 1, 7, 0, 0, G_GENO | 1,
        NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        100, 100, MS_SHRIEK, MZ_SMALL, MR_POISON, MR_POISON,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 2, CLR_MAGENTA),
    # PM_VIOLET_FUNGUS
    _mon(
        164, S_FUNGUS, "violet fungus",
        3, 1, 7, 0, 0, G_GENO | 2,
        Attack(AT_TUCH, AD_PHYS, 1, 4), Attack(AT_TUCH, AD_STCK, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        100, 100, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
        M1_BREATHLESS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_NOTAKE,
        M2_HOSTILE | M2_NEUTER, 0, 5, CLR_MAGENTA),
    # ---- S_GNOME ----
    # PM_GNOME
    _mon(
        165, S_GNOME, "gnome",
        1, 6, 10, 4, 0, G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        650, 100, MS_ORC, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_GNOME | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 3, CLR_BROWN),
    # PM_GNOME_LEADER
    _mon(
        166, S_GNOME, _nams("gnome lord", "gnome lady", "gnome leader"),
        3, 8, 10, 4, 0, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        700, 120, MS_ORC, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_GNOME | M2_LORD | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 4, CLR_BLUE),
    # PM_GNOMISH_WIZARD
    _mon(
        167, S_GNOME, "gnomish wizard",
        3, 10, 4, 10, 0, G_GENO | 1,
        Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        700, 120, MS_ORC, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_GNOME | M2_MAGIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 5, HI_ZAP),
    # PM_GNOME_RULER
    _mon(
        168, S_GNOME, _nams("gnome king", "gnome queen", "gnome ruler"),
        5, 10, 10, 20, 0, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        750, 150, MS_ORC, MZ_SMALL, 0, 0,
        M1_HUMANOID | M1_OMNIVORE, M2_GNOME | M2_PRINCE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 6, HI_LORD),
    # ---- S_GIANT ----
    # PM_GIANT
    _mon(
        169, S_GIANT, "giant",
        6, 6, 0, 0, 2, G_GENO | G_NOGEN | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        2250, 750, MS_BOAST, MZ_HUGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, CLR_RED),
    # PM_STONE_GIANT
    _mon(
        170, S_GIANT, "stone giant",
        6, 6, 0, 0, 2, G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        2250, 750, MS_BOAST, MZ_HUGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, CLR_GRAY),
    # PM_HILL_GIANT
    _mon(
        171, S_GIANT, "hill giant",
        8, 10, 6, 0, -2, G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2200, 700, MS_BOAST, MZ_HUGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 10, CLR_CYAN),
    # PM_FIRE_GIANT
    _mon(
        172, S_GIANT, "fire giant",
        9, 12, 4, 5, 2, G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        2250, 750, MS_BOAST, MZ_HUGE, MR_FIRE, MR_FIRE,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_YELLOW),
    # PM_FROST_GIANT
    _mon(
        173, S_GIANT, "frost giant",
        10, 12, 3, 10, -3, G_NOHELL | G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 12), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        2250, 750, MS_BOAST, MZ_HUGE, MR_COLD, MR_COLD,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 13, CLR_WHITE),
    # PM_ETTIN
    _mon(
        174, S_GIANT, "ettin",
        10, 12, 3, 0, 0, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 8), Attack(AT_WEAP, AD_PHYS, 3, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1700, 500, MS_GRUNT, MZ_HUGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 13, CLR_BROWN),
    # PM_STORM_GIANT
    _mon(
        175, S_GIANT, "storm giant",
        16, 12, 3, 10, -3, G_GENO | G_SGROUP | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 12), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        2250, 750, MS_BOAST, MZ_HUGE, MR_ELEC, MR_ELEC,
        M1_HUMANOID | M1_CARNIVORE,
        M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_JEWELS,
        M3_INFRAVISIBLE | M3_INFRAVISION, 19, CLR_BLUE),
    # PM_TITAN
    _mon(
        176, S_GIANT, "titan",
        16, 18, -3, 70, 9, 1,
        Attack(AT_WEAP, AD_PHYS, 2, 8), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2300, 900, MS_SPELL, MZ_HUGE, 0, 0,
        M1_FLY | M1_HUMANOID | M1_OMNIVORE,
        M2_STRONG | M2_ROCKTHROW | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE | M3_INFRAVISION, 20, CLR_MAGENTA),
    # PM_MINOTAUR
    _mon(
        177, S_GIANT, "minotaur",
        15, 15, 6, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_CLAW, AD_PHYS, 3, 10), Attack(AT_CLAW, AD_PHYS, 3, 10),
        Attack(AT_BUTT, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK,
        1500, 700, MS_MOO, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY, M3_INFRAVISIBLE | M3_INFRAVISION,
        17, CLR_BROWN),
    # ---- S_JABBERWOCK ----
    # PM_JABBERWOCK
    _mon(
        178, S_JABBERWOCK, "jabberwock",
        15, 12, -2, 50, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 10), Attack(AT_BITE, AD_PHYS, 2, 10),
        Attack(AT_CLAW, AD_PHYS, 2, 10), Attack(AT_CLAW, AD_PHYS, 2, 10),
        NO_ATK, NO_ATK,
        1300, 600, MS_BURBLE, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_FLY | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY | M2_COLLECT, M3_INFRAVISIBLE, 18,
        CLR_ORANGE),
    # ---- S_KOP ----
    # PM_KEYSTONE_KOP
    _mon(
        179, S_KOP, "Keystone Kop",
        1, 6, 10, 10, 9, G_GENO | G_LGROUP | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_ARREST, MZ_HUMAN, 0, 0,
        M1_HUMANOID, M2_HUMAN | M2_WANDER | M2_HOSTILE | M2_MALE | M2_COLLECT,
        M3_INFRAVISIBLE, 3, CLR_BLUE),
    # PM_KOP_SERGEANT
    _mon(
        180, S_KOP, "Kop Sergeant",
        2, 8, 10, 10, 10, G_GENO | G_SGROUP | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_ARREST, MZ_HUMAN, 0, 0,
        M1_HUMANOID,
        M2_HUMAN | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_MALE | M2_COLLECT,
        M3_INFRAVISIBLE, 4, CLR_BLUE),
    # PM_KOP_LIEUTENANT
    _mon(
        181, S_KOP, "Kop Lieutenant",
        3, 10, 10, 20, 11, G_GENO | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_ARREST, MZ_HUMAN, 0, 0,
        M1_HUMANOID,
        M2_HUMAN | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_MALE | M2_COLLECT,
        M3_INFRAVISIBLE, 5, CLR_CYAN),
    # PM_KOP_KAPTAIN
    _mon(
        182, S_KOP, "Kop Kaptain",
        4, 12, 10, 20, 12, G_GENO | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_ARREST, MZ_HUMAN, 0, 0,
        M1_HUMANOID,
        M2_HUMAN | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_MALE | M2_COLLECT,
        M3_INFRAVISIBLE, 6, HI_LORD),
    # ---- S_LICH ----
    # PM_LICH
    _mon(
        183, S_LICH, "lich",
        11, 6, 0, 30, -9, G_GENO | G_NOCORPSE | 1,
        Attack(AT_TUCH, AD_COLD, 1, 10), Attack(AT_MAGC, AD_SPEL, 0, 0),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1200, 100, MS_MUMBLE, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON,
        MR_COLD,
        M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_HOSTILE | M2_MAGIC, M3_INFRAVISION, 14, CLR_BROWN),
    # PM_DEMILICH
    _mon(
        184, S_LICH, "demilich",
        14, 9, -2, 60, -12, G_GENO | G_NOCORPSE | 1,
        Attack(AT_TUCH, AD_COLD, 3, 4), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1200, 100, MS_MUMBLE, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON,
        MR_COLD,
        M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_HOSTILE | M2_MAGIC, M3_INFRAVISION, 18, CLR_RED),
    # PM_MASTER_LICH
    _mon(
        185, S_LICH, "master lich",
        17, 9, -4, 90, -15, G_HELL | G_GENO | G_NOCORPSE | 1,
        Attack(AT_TUCH, AD_COLD, 3, 6), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1200, 100, MS_MUMBLE, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_SLEEP | MR_POISON, MR_FIRE | MR_COLD,
        M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_HOSTILE | M2_MAGIC, M3_WANTSBOOK | M3_INFRAVISION, 21,
        HI_LORD),
    # PM_ARCH_LICH
    _mon(
        186, S_LICH, "arch-lich",
        25, 9, -6, 90, -15, G_HELL | G_GENO | G_NOCORPSE | 1,
        Attack(AT_TUCH, AD_COLD, 5, 6), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1200, 100, MS_MUMBLE, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_SLEEP | MR_ELEC | MR_POISON, MR_FIRE | MR_COLD,
        M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_HOSTILE | M2_MAGIC, M3_WANTSBOOK | M3_INFRAVISION, 29,
        HI_LORD),
    # ---- S_MUMMY ----
    # PM_KOBOLD_MUMMY
    _mon(
        187, S_MUMMY, "kobold mummy",
        3, 8, 6, 20, -2, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 50, MS_SILENT, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE, M3_INFRAVISION, 4, CLR_BROWN),
    # PM_GNOME_MUMMY
    _mon(
        188, S_MUMMY, "gnome mummy",
        4, 10, 6, 20, -3, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        650, 50, MS_SILENT, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_GNOME, M3_INFRAVISION, 5, CLR_RED),
    # PM_ORC_MUMMY
    _mon(
        189, S_MUMMY, "orc mummy",
        5, 10, 5, 20, -4, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        850, 75, MS_SILENT, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_STRONG | M2_ORC | M2_GREEDY | M2_JEWELS,
        M3_INFRAVISION, 6, CLR_GRAY),
    # PM_DWARF_MUMMY
    _mon(
        190, S_MUMMY, "dwarf mummy",
        5, 10, 5, 20, -4, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        900, 150, MS_SILENT, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_DWARF | M2_GREEDY | M2_JEWELS,
        M3_INFRAVISION, 6, CLR_RED),
    # PM_ELF_MUMMY
    _mon(
        191, S_MUMMY, "elf mummy",
        6, 12, 4, 30, -5, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 175, MS_SILENT, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_ELF, M3_INFRAVISION, 7, CLR_GREEN),
    # PM_HUMAN_MUMMY
    _mon(
        192, S_MUMMY, "human mummy",
        6, 12, 4, 30, -5, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_SILENT, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE, M3_INFRAVISION, 7, CLR_GRAY),
    # PM_ETTIN_MUMMY
    _mon(
        193, S_MUMMY, "ettin mummy",
        7, 12, 4, 30, -6, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 6), Attack(AT_CLAW, AD_PHYS, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1700, 250, MS_SILENT, MZ_HUGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_STRONG, M3_INFRAVISION, 8, CLR_BLUE),
    # PM_GIANT_MUMMY
    _mon(
        194, S_MUMMY, "giant mummy",
        8, 14, 3, 30, -7, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 3, 4), Attack(AT_CLAW, AD_PHYS, 3, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2050, 375, MS_SILENT, MZ_HUGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_HOSTILE | M2_GIANT | M2_STRONG | M2_JEWELS,
        M3_INFRAVISION, 10, CLR_CYAN),
    # ---- S_NAGA ----
    # PM_RED_NAGA_HATCHLING
    _mon(
        195, S_NAGA, "red naga hatchling",
        3, 10, 6, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 100, MS_MUMBLE, MZ_LARGE, MR_FIRE | MR_POISON, MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, M3_INFRAVISIBLE, 4, CLR_RED),
    # PM_BLACK_NAGA_HATCHLING
    _mon(
        196, S_NAGA, "black naga hatchling",
        3, 10, 6, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 100, MS_MUMBLE, MZ_LARGE, MR_POISON | MR_ACID | MR_STONE,
        MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_ACID | M1_NOTAKE | M1_CARNIVORE,
        M2_STRONG, 0, 4, CLR_BLACK),
    # PM_GOLDEN_NAGA_HATCHLING
    _mon(
        197, S_NAGA, "golden naga hatchling",
        3, 10, 6, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 100, MS_MUMBLE, MZ_LARGE, MR_POISON, MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, 0, 4, HI_GOLD),
    # PM_GUARDIAN_NAGA_HATCHLING
    _mon(
        198, S_NAGA, "guardian naga hatchling",
        3, 10, 6, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 100, MS_MUMBLE, MZ_LARGE, MR_POISON, MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, 0, 4, CLR_GREEN),
    # PM_RED_NAGA
    _mon(
        199, S_NAGA, "red naga",
        6, 12, 4, 0, -4, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_BREA, AD_FIRE, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2600, 400, MS_MUMBLE, MZ_HUGE, MR_FIRE | MR_POISON,
        MR_FIRE | MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_OVIPAROUS | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, M3_INFRAVISIBLE, 8, CLR_RED),
    # PM_BLACK_NAGA
    _mon(
        200, S_NAGA, "black naga",
        8, 14, 2, 10, 4, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 6), Attack(AT_SPIT, AD_ACID, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2600, 400, MS_MUMBLE, MZ_HUGE, MR_POISON | MR_ACID | MR_STONE,
        MR_POISON | MR_ACID | MR_STONE,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_OVIPAROUS | M1_ACID | M1_NOTAKE | M1_CARNIVORE,
        M2_STRONG, 0, 10, CLR_BLACK),
    # PM_GOLDEN_NAGA
    _mon(
        201, S_NAGA, "golden naga",
        10, 14, 2, 70, 5, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 2, 6), Attack(AT_MAGC, AD_SPEL, 4, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2600, 400, MS_MUMBLE, MZ_HUGE, MR_POISON, MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_OVIPAROUS | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, 0, 13, HI_GOLD),
    # PM_GUARDIAN_NAGA
    _mon(
        202, S_NAGA, "guardian naga",
        12, 16, 0, 50, 7, G_GENO | 1,
        Attack(AT_SPIT, AD_DRST, 1, 6), Attack(AT_BITE, AD_PLYS, 1, 6),
        Attack(AT_TUCH, AD_PHYS, 0, 0), Attack(AT_HUGS, AD_WRAP, 2, 4), NO_ATK,
        NO_ATK,
        2600, 400, MS_MUMBLE, MZ_HUGE, MR_POISON, MR_POISON,
        M1_NOLIMBS | M1_SLITHY | M1_THICK_HIDE | M1_OVIPAROUS | M1_POIS | M1_NOTAKE | M1_OMNIVORE,
        M2_STRONG, 0, 17, CLR_GREEN),
    # ---- S_OGRE ----
    # PM_OGRE
    _mon(
        203, S_OGRE, "ogre",
        5, 10, 5, 0, -3, G_SGROUP | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 5), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1600, 500, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, CLR_BROWN),
    # PM_OGRE_LEADER
    _mon(
        204, S_OGRE, _nams("ogre lord", "ogre lady", "ogre leader"),
        7, 12, 3, 30, -5, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1700, 700, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_STRONG | M2_LORD | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 9, CLR_RED),
    # PM_OGRE_TYRANT
    _mon(
        205, S_OGRE, _nams("ogre king", "ogre queen", "ogre tyrant"),
        9, 14, 4, 60, -7, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 3, 5), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1700, 750, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_CARNIVORE,
        M2_STRONG | M2_PRINCE | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, HI_LORD),
    # ---- S_PUDDING ----
    # PM_GRAY_OOZE
    _mon(
        206, S_PUDDING, "gray ooze",
        3, 1, 8, 0, 0, G_GENO | G_NOCORPSE | 2,
        Attack(AT_BITE, AD_RUST, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 250, MS_SILENT, MZ_MEDIUM,
        MR_FIRE | MR_COLD | MR_POISON | MR_ACID | MR_STONE,
        MR_FIRE | MR_COLD | MR_POISON,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID,
        M2_HOSTILE | M2_NEUTER, 0, 4, CLR_GRAY),
    # PM_BROWN_PUDDING
    _mon(
        207, S_PUDDING, "brown pudding",
        5, 3, 8, 0, 0, G_GENO | G_NOCORPSE | 1,
        Attack(AT_BITE, AD_DCAY, 0, 0), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 250, MS_SILENT, MZ_MEDIUM,
        MR_COLD | MR_ELEC | MR_POISON | MR_ACID | MR_STONE,
        MR_COLD | MR_ELEC | MR_POISON,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID,
        M2_HOSTILE | M2_NEUTER, 0, 6, CLR_BROWN),
    # PM_GREEN_SLIME
    _mon(
        208, S_PUDDING, "green slime",
        6, 6, 6, 0, 0, G_HELL | G_GENO | G_NOCORPSE | 1,
        Attack(AT_TUCH, AD_SLIM, 1, 4), Attack(AT_NONE, AD_SLIM, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        400, 150, MS_SILENT, MZ_LARGE,
        MR_COLD | MR_ELEC | MR_POISON | MR_ACID | MR_STONE, MR_ACID | MR_STONE,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID | M1_POIS,
        M2_HOSTILE | M2_NEUTER, 0, 8, CLR_GREEN),
    # PM_BLACK_PUDDING
    _mon(
        209, S_PUDDING, "black pudding",
        10, 6, 6, 0, 0, G_GENO | G_NOCORPSE | 1,
        Attack(AT_BITE, AD_CORR, 3, 8), Attack(AT_NONE, AD_CORR, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        900, 250, MS_SILENT, MZ_LARGE,
        MR_COLD | MR_ELEC | MR_POISON | MR_ACID | MR_STONE,
        MR_COLD | MR_ELEC | MR_POISON,
        M1_BREATHLESS | M1_AMORPHOUS | M1_NOEYES | M1_NOLIMBS | M1_NOHEAD | M1_MINDLESS | M1_OMNIVORE | M1_ACID,
        M2_HOSTILE | M2_NEUTER, 0, 12, CLR_BLACK),
    # ---- S_QUANTMECH ----
    # PM_QUANTUM_MECHANIC
    _mon(
        210, S_QUANTMECH, "quantum mechanic",
        7, 12, 3, 10, 0, G_GENO | 3,
        Attack(AT_CLAW, AD_TLPT, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 20, MS_HUMANOID, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE | M1_POIS | M1_TPORT, M2_HOSTILE,
        M3_INFRAVISIBLE, 9, CLR_CYAN),
    # PM_GENETIC_ENGINEER
    _mon(
        211, S_QUANTMECH, "genetic engineer",
        12, 12, 3, 10, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_POLY, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 20, MS_HUMANOID, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE | M1_POIS | M1_TPORT, M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE, 14, CLR_GREEN),
    # ---- S_RUSTMONST ----
    # PM_RUST_MONSTER
    _mon(
        212, S_RUSTMONST, "rust monster",
        5, 18, 2, 0, 0, G_GENO | 2,
        Attack(AT_TUCH, AD_RUST, 0, 0), Attack(AT_TUCH, AD_RUST, 0, 0),
        Attack(AT_NONE, AD_RUST, 0, 0), NO_ATK, NO_ATK, NO_ATK,
        1000, 250, MS_SILENT, MZ_MEDIUM, 0, 0,
        M1_SWIM | M1_ANIMAL | M1_NOHANDS | M1_METALLIVORE, M2_HOSTILE,
        M3_INFRAVISIBLE, 8, CLR_BROWN),
    # PM_DISENCHANTER
    _mon(
        213, S_RUSTMONST, "disenchanter",
        12, 12, -10, 0, -3, G_HELL | G_GENO | 2,
        Attack(AT_CLAW, AD_ENCH, 4, 4), Attack(AT_NONE, AD_ENCH, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        750, 200, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_CARNIVORE, M2_HOSTILE, M3_INFRAVISIBLE, 14, CLR_BLUE),
    # ---- S_SNAKE ----
    # PM_GARTER_SNAKE
    _mon(
        214, S_SNAKE, "garter snake",
        1, 8, 8, 0, 0, G_LGROUP | G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        50, 60, MS_HISS, MZ_TINY, 0, 0,
        M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_OVIPAROUS | M1_CARNIVORE | M1_NOTAKE,
        0, 0, 3, CLR_GREEN),
    # PM_SNAKE
    _mon(
        215, S_SNAKE, "snake",
        4, 15, 3, 0, 0, G_GENO | 2,
        Attack(AT_BITE, AD_DRST, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        100, 80, MS_HISS, MZ_SMALL, MR_POISON, MR_POISON,
        M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS | M1_OVIPAROUS | M1_CARNIVORE | M1_NOTAKE,
        M2_HOSTILE, 0, 6, CLR_BROWN),
    # PM_WATER_MOCCASIN
    _mon(
        216, S_SNAKE, "water moccasin",
        4, 15, 3, 0, 0, G_GENO | G_NOGEN | G_LGROUP,
        Attack(AT_BITE, AD_DRST, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        150, 80, MS_HISS, MZ_SMALL, MR_POISON, MR_POISON,
        M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, 0, 7, CLR_RED),
    # PM_PYTHON
    _mon(
        217, S_SNAKE, "python",
        6, 3, 5, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 1, 4), Attack(AT_TUCH, AD_PHYS, 0, 0),
        Attack(AT_HUGS, AD_WRAP, 1, 4), Attack(AT_HUGS, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK,
        250, 100, MS_HISS, MZ_LARGE, 0, 0,
        M1_SWIM | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE | M2_STRONG, M3_INFRAVISION, 8, CLR_MAGENTA),
    # PM_PIT_VIPER
    _mon(
        218, S_SNAKE, "pit viper",
        6, 15, 2, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_DRST, 1, 4), Attack(AT_BITE, AD_DRST, 1, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        100, 60, MS_HISS, MZ_MEDIUM, MR_POISON, MR_POISON,
        M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, M3_INFRAVISION, 9, CLR_BLUE),
    # PM_COBRA
    _mon(
        219, S_SNAKE, "cobra",
        6, 18, 2, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_DRST, 2, 4), Attack(AT_SPIT, AD_BLND, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        250, 100, MS_HISS, MZ_MEDIUM, MR_POISON, MR_POISON,
        M1_SWIM | M1_CONCEAL | M1_NOLIMBS | M1_ANIMAL | M1_SLITHY | M1_POIS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, 0, 10, CLR_BLUE),
    # ---- S_TROLL ----
    # PM_TROLL
    _mon(
        220, S_TROLL, "troll",
        7, 12, 4, 0, -3, G_GENO | 2,
        Attack(AT_WEAP, AD_PHYS, 4, 2), Attack(AT_CLAW, AD_PHYS, 4, 2),
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        800, 350, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_REGEN | M1_CARNIVORE,
        M2_STRONG | M2_STALK | M2_HOSTILE, M3_INFRAVISIBLE | M3_INFRAVISION, 9,
        CLR_BROWN),
    # PM_ICE_TROLL
    _mon(
        221, S_TROLL, "ice troll",
        9, 10, 2, 20, -3, G_NOHELL | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_CLAW, AD_COLD, 2, 6),
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1000, 300, MS_GRUNT, MZ_LARGE, MR_COLD, MR_COLD,
        M1_HUMANOID | M1_REGEN | M1_CARNIVORE,
        M2_STRONG | M2_STALK | M2_HOSTILE, M3_INFRAVISIBLE | M3_INFRAVISION,
        12, CLR_WHITE),
    # PM_ROCK_TROLL
    _mon(
        222, S_TROLL, "rock troll",
        9, 12, 0, 0, -3, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 3, 6), Attack(AT_CLAW, AD_PHYS, 2, 8),
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1200, 300, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_REGEN | M1_CARNIVORE,
        M2_STRONG | M2_STALK | M2_HOSTILE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 12, CLR_CYAN),
    # PM_WATER_TROLL
    _mon(
        223, S_TROLL, "water troll",
        11, 14, 4, 40, -3, G_NOGEN | G_GENO,
        Attack(AT_WEAP, AD_PHYS, 2, 8), Attack(AT_CLAW, AD_PHYS, 2, 8),
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1200, 350, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_REGEN | M1_CARNIVORE | M1_SWIM,
        M2_STRONG | M2_STALK | M2_HOSTILE, M3_INFRAVISIBLE | M3_INFRAVISION,
        13, CLR_BLUE),
    # PM_OLOG_HAI
    _mon(
        224, S_TROLL, "Olog-hai",
        13, 12, -4, 0, -7, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 3, 6), Attack(AT_CLAW, AD_PHYS, 2, 8),
        Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1500, 400, MS_GRUNT, MZ_LARGE, 0, 0,
        M1_HUMANOID | M1_REGEN | M1_CARNIVORE,
        M2_STRONG | M2_STALK | M2_HOSTILE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 16, HI_LORD),
    # ---- S_UMBER ----
    # PM_UMBER_HULK
    _mon(
        225, S_UMBER, "umber hulk",
        9, 6, 2, 25, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 3, 4), Attack(AT_CLAW, AD_PHYS, 3, 4),
        Attack(AT_BITE, AD_PHYS, 2, 5), Attack(AT_GAZE, AD_CONF, 0, 0), NO_ATK,
        NO_ATK,
        1200, 500, MS_SILENT, MZ_LARGE, 0, 0,
        M1_TUNNEL | M1_CARNIVORE, M2_STRONG, M3_INFRAVISIBLE, 12, CLR_BROWN),
    # ---- S_VAMPIRE ----
    # PM_VAMPIRE
    _mon(
        226, S_VAMPIRE, "vampire",
        10, 12, 1, 25, -8, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_BITE, AD_DRLI, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_VAMPIRE, MZ_HUMAN, MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_SHAPESHIFTER,
        M3_INFRAVISIBLE, 12, CLR_RED),
    # PM_VAMPIRE_LEADER
    _mon(
        227, S_VAMPIRE,
        _nams("vampire lord", "vampire lady", "vampire leader"),
        12, 14, 0, 50, -9, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 8), Attack(AT_BITE, AD_DRLI, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_VAMPIRE, MZ_HUMAN, MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_LORD | M2_SHAPESHIFTER,
        M3_INFRAVISIBLE, 14, CLR_BLUE),
    # PM_VLAD_THE_IMPALER
    _mon(
        228, S_VAMPIRE, "Vlad the Impaler",
        28, 26, -6, 80, -10, G_NOGEN | G_NOCORPSE | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 2, 10), Attack(AT_BITE, AD_DRLI, 1, 12),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_VAMPIRE, MZ_HUMAN, MR_SLEEP | MR_POISON, 0,
        M1_FLY | M1_BREATHLESS | M1_HUMANOID | M1_POIS | M1_REGEN,
        M2_NOPOLY | M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_PNAME | M2_STRONG | M2_NASTY | M2_PRINCE | M2_MALE | M2_SHAPESHIFTER,
        M3_WAITFORU | M3_WANTSCAND | M3_INFRAVISIBLE, 32, HI_LORD),
    # ---- S_WRAITH ----
    # PM_BARROW_WIGHT
    _mon(
        229, S_WRAITH, "barrow wight",
        3, 12, 5, 5, -3, G_GENO | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_DRLI, 0, 0), Attack(AT_MAGC, AD_SPEL, 0, 0),
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_TUCH, AD_COLD, 1, 4), NO_ATK,
        NO_ATK,
        1200, 0, MS_SPELL, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_HUMANOID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_COLLECT, 0, 8, CLR_GRAY),
    # PM_WRAITH
    _mon(
        230, S_WRAITH, "wraith",
        6, 12, 4, 15, -6, G_GENO | 2,
        Attack(AT_TUCH, AD_DRLI, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ETHEREAL, 0, MS_SILENT, MZ_HUMAN,
        MR_COLD | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_BREATHLESS | M1_FLY | M1_HUMANOID | M1_UNSOLID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE, 0, 8, CLR_BLACK),
    # PM_NAZGUL
    _mon(
        231, S_WRAITH, "Nazgul",
        13, 12, 0, 25, -17, G_GENO | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_DRLI, 1, 4), Attack(AT_BREA, AD_SLEE, 2, 25),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 0, MS_SPELL, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_HUMANOID | M1_SEE_INVIS,
        M2_NOPOLY | M2_UNDEAD | M2_STALK | M2_STRONG | M2_HOSTILE | M2_MALE | M2_COLLECT,
        0, 17, HI_LORD),
    # ---- S_XORN ----
    # PM_XORN
    _mon(
        232, S_XORN, "xorn",
        8, 9, -2, 20, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_BITE, AD_PHYS, 4, 6), NO_ATK,
        NO_ATK,
        1200, 700, MS_ROAR, MZ_MEDIUM, MR_FIRE | MR_COLD | MR_STONE, MR_STONE,
        M1_BREATHLESS | M1_WALLWALK | M1_THICK_HIDE | M1_METALLIVORE,
        M2_HOSTILE | M2_STRONG, 0, 11, CLR_BROWN),
    # ---- S_YETI ----
    # PM_MONKEY
    _mon(
        233, S_YETI, "monkey",
        2, 12, 6, 0, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_SITM, 0, 0), Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        100, 50, MS_GROWL, MZ_SMALL, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_OMNIVORE, 0, M3_INFRAVISIBLE, 4, CLR_GRAY),
    # PM_APE
    _mon(
        234, S_YETI, "ape",
        4, 12, 6, 0, 0, G_GENO | G_SGROUP | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK,
        1100, 500, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_OMNIVORE, M2_STRONG, M3_INFRAVISIBLE, 6,
        CLR_BROWN),
    # PM_OWLBEAR
    _mon(
        235, S_YETI, "owlbear",
        5, 12, 5, 0, 0, G_GENO | 3,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
        Attack(AT_HUGS, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK,
        1700, 700, MS_ROAR, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE,
        M2_HOSTILE | M2_STRONG | M2_NASTY, M3_INFRAVISIBLE, 7, CLR_BROWN),
    # PM_YETI
    _mon(
        236, S_YETI, "yeti",
        5, 15, 6, 0, 0, G_GENO | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        1600, 700, MS_GROWL, MZ_LARGE, MR_COLD, MR_COLD,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE, M2_HOSTILE | M2_STRONG,
        M3_INFRAVISIBLE, 7, CLR_WHITE),
    # PM_CARNIVOROUS_APE
    _mon(
        237, S_YETI, "carnivorous ape",
        6, 12, 6, 0, 0, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_HUGS, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK,
        1250, 550, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_CARNIVORE, M2_HOSTILE | M2_STRONG,
        M3_INFRAVISIBLE, 8, CLR_BLACK),
    # PM_SASQUATCH
    _mon(
        238, S_YETI, "sasquatch",
        7, 15, 6, 0, 2, G_GENO | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6),
        Attack(AT_KICK, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK,
        1550, 750, MS_GROWL, MZ_LARGE, 0, 0,
        M1_ANIMAL | M1_HUMANOID | M1_SEE_INVIS | M1_OMNIVORE, M2_STRONG,
        M3_INFRAVISIBLE, 9, CLR_GRAY),
    # ---- S_ZOMBIE ----
    # PM_KOBOLD_ZOMBIE
    _mon(
        239, S_ZOMBIE, "kobold zombie",
        0, 6, 10, 0, -2, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 50, MS_GROAN, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION, 1, CLR_BROWN),
    # PM_GNOME_ZOMBIE
    _mon(
        240, S_ZOMBIE, "gnome zombie",
        1, 6, 10, 0, -2, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 5), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        650, 50, MS_GROAN, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_GNOME, M3_INFRAVISION, 2,
        CLR_BROWN),
    # PM_ORC_ZOMBIE
    _mon(
        241, S_ZOMBIE, "orc zombie",
        2, 6, 9, 0, -3, G_GENO | G_SGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        850, 75, MS_GROAN, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_ORC, M3_INFRAVISION, 3, CLR_GRAY),
    # PM_DWARF_ZOMBIE
    _mon(
        242, S_ZOMBIE, "dwarf zombie",
        2, 6, 9, 0, -3, G_GENO | G_SGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        900, 150, MS_GROAN, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_DWARF, M3_INFRAVISION, 3,
        CLR_RED),
    # PM_ELF_ZOMBIE
    _mon(
        243, S_ZOMBIE, "elf zombie",
        3, 6, 9, 0, -3, G_GENO | G_SGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 7), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 175, MS_GROAN, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_ELF, M3_INFRAVISION, 4,
        CLR_GREEN),
    # PM_HUMAN_ZOMBIE
    _mon(
        244, S_ZOMBIE, "human zombie",
        4, 6, 8, 0, -3, G_GENO | G_SGROUP | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 200, MS_GROAN, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION, 5, HI_DOMESTIC),
    # PM_ETTIN_ZOMBIE
    _mon(
        245, S_ZOMBIE, "ettin zombie",
        6, 8, 6, 0, -4, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 10), Attack(AT_CLAW, AD_PHYS, 1, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1700, 250, MS_GROAN, MZ_HUGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_STRONG, M3_INFRAVISION, 7,
        CLR_BLUE),
    # PM_GHOUL
    _mon(
        246, S_ZOMBIE, "ghoul",
        3, 6, 10, 0, -2, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PLYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 3), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        400, 50, MS_SILENT, MZ_SMALL, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_POIS | M1_OMNIVORE,
        M2_UNDEAD | M2_WANDER | M2_HOSTILE, M3_INFRAVISION, 5, CLR_BLACK),
    # PM_GIANT_ZOMBIE
    _mon(
        247, S_ZOMBIE, "giant zombie",
        8, 8, 6, 0, -4, G_GENO | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 8), Attack(AT_CLAW, AD_PHYS, 2, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        2050, 375, MS_GROAN, MZ_HUGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID,
        M2_UNDEAD | M2_STALK | M2_HOSTILE | M2_GIANT | M2_STRONG,
        M3_INFRAVISION, 9, CLR_CYAN),
    # PM_SKELETON
    _mon(
        248, S_ZOMBIE, "skeleton",
        12, 8, 4, 0, 0, G_NOCORPSE | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_TUCH, AD_SLOW, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        300, 5, MS_BONES, MZ_HUMAN, MR_COLD | MR_SLEEP | MR_POISON | MR_STONE,
        0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_UNDEAD | M2_WANDER | M2_HOSTILE | M2_STRONG | M2_COLLECT | M2_NASTY,
        M3_INFRAVISION, 14, CLR_WHITE),
    # ---- S_GOLEM ----
    # PM_STRAW_GOLEM
    _mon(
        249, S_GOLEM, "straw golem",
        3, 12, 10, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 2), Attack(AT_CLAW, AD_PHYS, 1, 2), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        400, 0, MS_SILENT, MZ_LARGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_NEUTER, 0,
        4, CLR_YELLOW),
    # PM_PAPER_GOLEM
    _mon(
        250, S_GOLEM, "paper golem",
        3, 12, 10, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        400, 0, MS_SILENT, MZ_LARGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_NEUTER, 0,
        4, HI_PAPER),
    # PM_ROPE_GOLEM
    _mon(
        251, S_GOLEM, "rope golem",
        4, 9, 8, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_HUGS, AD_PHYS, 6, 1), NO_ATK, NO_ATK, NO_ATK,
        450, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_NEUTER, 0,
        6, CLR_BROWN),
    # PM_GOLD_GOLEM
    _mon(
        252, S_GOLEM, "gold golem",
        5, 9, 6, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 3), Attack(AT_CLAW, AD_PHYS, 2, 3), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        450, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON | MR_ACID, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_HOSTILE | M2_NEUTER, 0, 6, HI_GOLD),
    # PM_LEATHER_GOLEM
    _mon(
        253, S_GOLEM, "leather golem",
        6, 6, 6, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 6), Attack(AT_CLAW, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        800, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_NEUTER, 0,
        7, HI_LEATHER),
    # PM_WOOD_GOLEM
    _mon(
        254, S_GOLEM, "wood golem",
        7, 3, 4, 0, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 3, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        900, 0, MS_SILENT, MZ_LARGE, MR_COLD | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_HOSTILE | M2_NEUTER, 0, 8, HI_WOOD),
    # PM_FLESH_GOLEM
    _mon(
        255, S_GOLEM, "flesh golem",
        9, 8, 9, 30, 0, 1,
        Attack(AT_CLAW, AD_PHYS, 2, 8), Attack(AT_CLAW, AD_PHYS, 2, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1400, 600, MS_SILENT, MZ_LARGE,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID, M2_HOSTILE | M2_STRONG, 0,
        10, CLR_RED),
    # PM_CLAY_GOLEM
    _mon(
        256, S_GOLEM, "clay golem",
        11, 7, 7, 40, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 3, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        1550, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_HOSTILE | M2_STRONG, 0, 12, CLR_BROWN),
    # PM_STONE_GOLEM
    _mon(
        257, S_GOLEM, "stone golem",
        14, 6, 5, 50, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 3, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1900, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_HOSTILE | M2_STRONG, 0, 15, CLR_GRAY),
    # PM_GLASS_GOLEM
    _mon(
        258, S_GOLEM, "glass golem",
        16, 6, 1, 50, 0, G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 2, 8), Attack(AT_CLAW, AD_PHYS, 2, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1800, 0, MS_SILENT, MZ_LARGE, MR_SLEEP | MR_POISON | MR_ACID, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE,
        M2_HOSTILE | M2_STRONG, 0, 18, CLR_CYAN),
    # PM_IRON_GOLEM
    _mon(
        259, S_GOLEM, "iron golem",
        18, 6, 3, 60, 0, G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_BREA, AD_DRST, 4, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2000, 0, MS_SILENT, MZ_LARGE,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_BREATHLESS | M1_MINDLESS | M1_HUMANOID | M1_THICK_HIDE | M1_POIS,
        M2_HOSTILE | M2_STRONG | M2_COLLECT, 0, 22, HI_METAL),
    # ---- S_HUMAN ----
    # PM_HUMAN
    _mon(
        260, S_HUMAN, "human",
        0, 12, 10, 0, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 2,
        HI_DOMESTIC),
    # PM_HUMAN_WERERAT
    _mon(
        261, S_HUMAN, "wererat",
        2, 12, 10, 10, -7, 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_WERE, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_REGEN | M1_OMNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE | M2_HUMAN | M2_COLLECT,
        M3_INFRAVISIBLE, 3, CLR_BROWN),
    # PM_HUMAN_WEREJACKAL
    _mon(
        262, S_HUMAN, "werejackal",
        2, 12, 10, 10, -7, 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_WERE, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_REGEN | M1_OMNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE | M2_HUMAN | M2_COLLECT,
        M3_INFRAVISIBLE, 3, CLR_RED),
    # PM_HUMAN_WEREWOLF
    _mon(
        263, S_HUMAN, "werewolf",
        5, 12, 10, 20, -7, 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_WERE, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_REGEN | M1_OMNIVORE,
        M2_NOPOLY | M2_WERE | M2_HOSTILE | M2_HUMAN | M2_COLLECT,
        M3_INFRAVISIBLE, 6, CLR_ORANGE),
    # PM_ELF
    _mon(
        264, S_HUMAN, "elf",
        0, 12, 10, 2, -3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS,
        M2_NOPOLY | M2_ELF | M2_COLLECT, M3_INFRAVISION | M3_INFRAVISIBLE, 1,
        HI_DOMESTIC),
    # PM_WOODLAND_ELF
    _mon(
        265, S_HUMAN, "Woodland-elf",
        4, 12, 10, 10, -5, G_GENO | G_SGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS, M2_ELF | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 6, CLR_GREEN),
    # PM_GREEN_ELF
    _mon(
        266, S_HUMAN, "Green-elf",
        5, 12, 10, 10, -6, G_GENO | G_SGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS, M2_ELF | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 7, CLR_BRIGHT_GREEN),
    # PM_GREY_ELF
    _mon(
        267, S_HUMAN, "Grey-elf",
        6, 12, 10, 10, -7, G_GENO | G_SGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS, M2_ELF | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, CLR_GRAY),
    # PM_ELF_NOBLE
    _mon(
        268, S_HUMAN, _nams("elf-lord", "elf-lady", "elf-noble"),
        8, 12, 10, 20, -9, G_GENO | G_SGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS,
        M2_ELF | M2_STRONG | M2_LORD | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_BRIGHT_BLUE),
    # PM_ELVEN_MONARCH
    _mon(
        269, S_HUMAN, _nams("Elvenking", "Elvenqueen", "elven monarch"),
        9, 12, 10, 25, -10, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_ELF, 350, MS_HUMANOID, MZ_HUMAN, MR_SLEEP, MR_SLEEP,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS,
        M2_ELF | M2_STRONG | M2_PRINCE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, HI_LORD),
    # PM_DOPPELGANGER
    _mon(
        270, S_HUMAN, "doppelganger",
        9, 12, 5, 20, 0, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 12), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_IMITATE, MZ_HUMAN, MR_SLEEP, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_HOSTILE | M2_STRONG | M2_COLLECT | M2_SHAPESHIFTER,
        M3_INFRAVISIBLE, 11, HI_DOMESTIC),
    # PM_SHOPKEEPER
    _mon(
        271, S_HUMAN, "shopkeeper",
        12, 16, 0, 50, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 4, 4), Attack(AT_WEAP, AD_PHYS, 4, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SELL, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 15, HI_DOMESTIC),
    # PM_GUARD
    _mon(
        272, S_HUMAN, "guard",
        12, 12, 10, 40, 10, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 4, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_GUARD, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 14, CLR_BLUE),
    # PM_PRISONER
    _mon(
        273, S_HUMAN, "prisoner",
        12, 12, 10, 0, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_DJINNI, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE | M3_CLOSE, 14, HI_DOMESTIC),
    # PM_ORACLE
    _mon(
        274, S_HUMAN, "Oracle",
        12, 0, 0, 50, 0, G_NOGEN | G_UNIQ,
        Attack(AT_NONE, AD_MAGM, 0, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_ORACLE, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_FEMALE, M3_INFRAVISIBLE, 13,
        HI_ZAP),
    # PM_ALIGNED_CLERIC
    _mon(
        275, S_HUMAN, _nams("priest", "priestess", "aligned cleric"),
        12, 12, 10, 50, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_KICK, AD_PHYS, 1, 4),
        Attack(AT_MAGC, AD_CLRC, 0, 0), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_PRIEST, MZ_HUMAN, MR_ELEC, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_LORD | M2_PEACEFUL | M2_COLLECT,
        M3_INFRAVISIBLE, 15, CLR_WHITE),
    # PM_HIGH_CLERIC
    _mon(
        276, S_HUMAN, _nams("high priest", "high priestess", "high cleric"),
        25, 15, 7, 70, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_KICK, AD_PHYS, 2, 8),
        Attack(AT_MAGC, AD_CLRC, 2, 8), Attack(AT_MAGC, AD_CLRC, 2, 8), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_PRIEST, MZ_HUMAN,
        MR_FIRE | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_HUMANOID | M1_SEE_INVIS | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MINION | M2_PRINCE | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 30, CLR_WHITE),
    # PM_SOLDIER
    _mon(
        277, S_HUMAN, "soldier",
        6, 10, 10, 0, -2, G_SGROUP | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 8, CLR_GRAY),
    # PM_SERGEANT
    _mon(
        278, S_HUMAN, "sergeant",
        8, 10, 10, 5, -3, G_SGROUP | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 10, CLR_RED),
    # PM_NURSE
    _mon(
        279, S_HUMAN, "nurse",
        11, 6, 0, 0, 0, G_GENO | 3,
        Attack(AT_CLAW, AD_HEAL, 2, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_NURSE, MZ_HUMAN, MR_POISON, MR_POISON,
        M1_HUMANOID | M1_OMNIVORE, M2_NOPOLY | M2_HUMAN | M2_HOSTILE,
        M3_INFRAVISIBLE, 13, HI_DOMESTIC),
    # PM_LIEUTENANT
    _mon(
        280, S_HUMAN, "lieutenant",
        10, 10, 10, 15, -4, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 3, 4), Attack(AT_WEAP, AD_PHYS, 3, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 12, CLR_GREEN),
    # PM_CAPTAIN
    _mon(
        281, S_HUMAN, "captain",
        12, 10, 10, 15, -5, G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 4, 4), Attack(AT_WEAP, AD_PHYS, 4, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_HOSTILE | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 14, CLR_BLUE),
    # PM_WATCHMAN
    _mon(
        282, S_HUMAN, "watchman",
        6, 10, 10, 0, -2, G_SGROUP | G_NOGEN | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 8, CLR_GRAY),
    # PM_WATCH_CAPTAIN
    _mon(
        283, S_HUMAN, "watch captain",
        10, 10, 10, 15, -4, G_NOGEN | G_GENO | 1,
        Attack(AT_WEAP, AD_PHYS, 3, 4), Attack(AT_WEAP, AD_PHYS, 3, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SOLDIER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_MERC | M2_STALK | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 12, CLR_GREEN),
    # PM_MEDUSA
    _mon(
        284, S_HUMAN, "Medusa",
        20, 12, 2, 50, -15, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 1, 8),
        Attack(AT_GAZE, AD_STON, 0, 0), Attack(AT_BITE, AD_DRST, 1, 6), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_HISS, MZ_LARGE, MR_POISON | MR_STONE,
        MR_POISON | MR_STONE,
        M1_FLY | M1_SWIM | M1_AMPHIBIOUS | M1_HUMANOID | M1_POIS | M1_OMNIVORE,
        M2_NOPOLY | M2_HOSTILE | M2_STRONG | M2_PNAME | M2_FEMALE,
        M3_WAITFORU | M3_INFRAVISIBLE, 25, CLR_BRIGHT_GREEN),
    # PM_WIZARD_OF_YENDOR
    _mon(
        285, S_HUMAN, "Wizard of Yendor",
        30, 12, -8, 100, A_NONE, G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_SAMU, 2, 12), Attack(AT_MAGC, AD_SPEL, 0, 0),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_CUSS, MZ_HUMAN, MR_FIRE | MR_POISON,
        MR_FIRE | MR_POISON,
        M1_FLY | M1_BREATHLESS | M1_HUMANOID | M1_REGEN | M1_SEE_INVIS | M1_TPORT | M1_TPORT_CNTRL | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_PRINCE | M2_MALE | M2_MAGIC,
        M3_COVETOUS | M3_WAITFORU | M3_INFRAVISIBLE, 34, HI_OVERLORD),
    # PM_CROESUS
    _mon(
        286, S_HUMAN, "Croesus",
        20, 15, 0, 40, 15, G_UNIQ | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 4, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_GUARD, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_SEE_INVIS | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_PNAME | M2_PRINCE | M2_MALE | M2_GREEDY | M2_JEWELS | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 22, HI_LORD),
    # ---- S_GHOST ----
    # PM_GHOST
    _mon(
        287, S_GHOST, "ghost",
        10, 3, -5, 50, -5, G_NOCORPSE | G_NOGEN,
        Attack(AT_TUCH, AD_PHYS, 1, 1), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 0, MS_SILENT, MZ_HUMAN,
        MR_COLD | MR_DISINT | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_WALLWALK | M1_HUMANOID | M1_UNSOLID,
        M2_NOPOLY | M2_UNDEAD | M2_STALK | M2_HOSTILE, M3_INFRAVISION, 12,
        CLR_GRAY),
    # PM_SHADE
    _mon(
        288, S_GHOST, "shade",
        12, 10, 10, 0, 0, G_NOCORPSE | G_NOGEN,
        Attack(AT_TUCH, AD_PLYS, 2, 6), Attack(AT_TUCH, AD_SLOW, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 0, MS_WAIL, MZ_HUMAN,
        MR_COLD | MR_DISINT | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_BREATHLESS | M1_WALLWALK | M1_HUMANOID | M1_UNSOLID | M1_SEE_INVIS,
        M2_NOPOLY | M2_UNDEAD | M2_WANDER | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISION, 14, CLR_BLACK),
    # ---- S_DEMON ----
    # PM_WATER_DEMON
    _mon(
        289, S_DEMON, "water demon",
        8, 12, -4, 30, -7, G_NOCORPSE | G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 3), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_DJINNI, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_POIS | M1_SWIM,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_BLUE),
    # PM_AMOROUS_DEMON
    _mon(
        290, S_DEMON, _nams("incubus", "succubus", "amorous demon"),
        6, 12, 0, 70, -9, G_NOCORPSE | 1,
        Attack(AT_BITE, AD_SSEX, 0, 0), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_CLAW, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SEDUCE, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_FLY | M1_POIS,
        M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 8, CLR_GRAY),
    # PM_HORNED_DEVIL
    _mon(
        291, S_DEMON, "horned devil",
        6, 9, -5, 50, 11, G_HELL | G_NOCORPSE | 2,
        Attack(AT_WEAP, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_BITE, AD_PHYS, 2, 3), Attack(AT_STNG, AD_PHYS, 1, 3), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_POIS | M1_THICK_HIDE, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 9, CLR_BROWN),
    # PM_ERINYS
    _mon(
        292, S_DEMON, "erinys",
        7, 12, 2, 30, 10, G_HELL | G_NOCORPSE | G_SGROUP | 2,
        Attack(AT_WEAP, AD_DRST, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_STRONG | M2_NASTY | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 10, CLR_RED),
    # PM_BARBED_DEVIL
    _mon(
        293, S_DEMON, "barbed devil",
        8, 12, 0, 35, 8, G_HELL | G_NOCORPSE | G_SGROUP | 2,
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_STCK, 2, 4),
        Attack(AT_STNG, AD_PHYS, 3, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_POIS | M1_THICK_HIDE, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_RED),
    # PM_MARILITH
    _mon(
        294, S_DEMON, "marilith",
        7, 12, -6, 80, -12, G_HELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 4), Attack(AT_WEAP, AD_PHYS, 2, 4),
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 2, 4),
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 2, 4),
        WT_HUMAN, 400, MS_CUSS, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_SLITHY | M1_SEE_INVIS | M1_POIS,
        M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_RED),
    # PM_VROCK
    _mon(
        295, S_DEMON, "vrock",
        8, 12, 0, 50, -9, G_HELL | G_NOCORPSE | G_SGROUP | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_CLAW, AD_PHYS, 1, 8), Attack(AT_CLAW, AD_PHYS, 1, 8),
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_POIS, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 11, CLR_GREEN),
    # PM_HEZROU
    _mon(
        296, S_DEMON, "hezrou",
        9, 6, -2, 55, -10, G_HELL | G_NOCORPSE | G_SGROUP | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 3), Attack(AT_CLAW, AD_PHYS, 1, 3),
        Attack(AT_BITE, AD_PHYS, 4, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_POIS, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 12, CLR_GREEN),
    # PM_BONE_DEVIL
    _mon(
        297, S_DEMON, "bone devil",
        9, 15, -1, 40, -9, G_HELL | G_NOCORPSE | G_SGROUP | 2,
        Attack(AT_WEAP, AD_PHYS, 3, 4), Attack(AT_STNG, AD_DRST, 2, 4), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_POIS, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 13, CLR_GRAY),
    # PM_ICE_DEVIL
    _mon(
        298, S_DEMON, "ice devil",
        11, 6, -4, 55, -12, G_HELL | G_NOCORPSE | 2,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_STNG, AD_COLD, 3, 4),
        Attack(AT_TUCH, AD_SLOW, 1, 1), NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_LARGE, MR_FIRE | MR_COLD | MR_POISON, 0,
        M1_SEE_INVIS | M1_POIS, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 15, CLR_WHITE),
    # PM_NALFESHNEE
    _mon(
        299, S_DEMON, "nalfeshnee",
        11, 9, -1, 65, -11, G_HELL | G_NOCORPSE | 1,
        Attack(AT_CLAW, AD_PHYS, 1, 4), Attack(AT_CLAW, AD_PHYS, 1, 4),
        Attack(AT_BITE, AD_PHYS, 2, 4), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_SPELL, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_HUMANOID | M1_POIS, M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION, 15, CLR_RED),
    # PM_PIT_FIEND
    _mon(
        300, S_DEMON, "pit fiend",
        13, 6, -3, 65, -13, G_HELL | G_NOCORPSE | 2,
        Attack(AT_WEAP, AD_PHYS, 4, 2), Attack(AT_WEAP, AD_PHYS, 4, 2),
        Attack(AT_HUGS, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GROWL, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_SEE_INVIS | M1_POIS,
        M2_DEMON | M2_STALK | M2_HOSTILE | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 16, CLR_RED),
    # PM_SANDESTIN
    _mon(
        301, S_DEMON, "sandestin",
        13, 12, 4, 60, -5, G_HELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_WEAP, AD_PHYS, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1500, 400, MS_CUSS, MZ_HUMAN, MR_STONE, 0,
        M1_HUMANOID,
        M2_NOPOLY | M2_STALK | M2_STRONG | M2_COLLECT | M2_SHAPESHIFTER,
        M3_INFRAVISIBLE | M3_INFRAVISION, 15, CLR_GRAY),
    # PM_BALROG
    _mon(
        302, S_DEMON, "balrog",
        16, 5, -2, 75, -14, G_HELL | G_NOCORPSE | 1,
        Attack(AT_WEAP, AD_PHYS, 8, 4), Attack(AT_WEAP, AD_PHYS, 4, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_SILENT, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_DEMON | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_COLLECT,
        M3_INFRAVISIBLE | M3_INFRAVISION, 20, CLR_RED),
    # PM_JUIBLEX
    _mon(
        303, S_DEMON, "Juiblex",
        50, 3, -7, 65, -15, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_ENGL, AD_DISE, 4, 10), Attack(AT_SPIT, AD_ACID, 3, 6),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1500, 0, MS_GURGLE, MZ_LARGE, MR_FIRE | MR_POISON | MR_ACID | MR_STONE,
        0,
        M1_AMPHIBIOUS | M1_AMORPHOUS | M1_NOHEAD | M1_FLY | M1_SEE_INVIS | M1_ACID | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_LORD | M2_MALE,
        M3_WAITFORU | M3_WANTSAMUL | M3_INFRAVISION, 26, CLR_BRIGHT_GREEN),
    # PM_YEENOGHU
    _mon(
        304, S_DEMON, "Yeenoghu",
        56, 18, -5, 80, -15, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 3, 6), Attack(AT_WEAP, AD_CONF, 2, 8),
        Attack(AT_CLAW, AD_PLYS, 1, 6), Attack(AT_MAGC, AD_MAGM, 2, 6), NO_ATK,
        NO_ATK,
        900, 500, MS_ORC, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_LORD | M2_MALE | M2_COLLECT,
        M3_WANTSAMUL | M3_INFRAVISIBLE | M3_INFRAVISION, 31, HI_LORD),
    # PM_ORCUS
    _mon(
        305, S_DEMON, "Orcus",
        66, 9, -6, 85, -20, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 3, 6), Attack(AT_CLAW, AD_PHYS, 3, 4),
        Attack(AT_CLAW, AD_PHYS, 3, 4), Attack(AT_MAGC, AD_SPEL, 8, 6),
        Attack(AT_STNG, AD_DRST, 2, 4), NO_ATK,
        1500, 500, MS_ORC, MZ_HUGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_PRINCE | M2_MALE | M2_COLLECT,
        M3_WAITFORU | M3_WANTSBOOK | M3_WANTSAMUL | M3_INFRAVISIBLE | M3_INFRAVISION,
        36, HI_LORD),
    # PM_GERYON
    _mon(
        306, S_DEMON, "Geryon",
        72, 3, -3, 75, 15, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_PHYS, 3, 6), Attack(AT_CLAW, AD_PHYS, 3, 6),
        Attack(AT_STNG, AD_DRST, 2, 4), NO_ATK, NO_ATK, NO_ATK,
        1500, 500, MS_BRIBE, MZ_HUGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS | M1_SLITHY,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_PRINCE | M2_MALE,
        M3_WANTSAMUL | M3_INFRAVISIBLE | M3_INFRAVISION, 36, HI_LORD),
    # PM_DISPATER
    _mon(
        307, S_DEMON, "Dispater",
        78, 15, -2, 80, 15, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 6), Attack(AT_MAGC, AD_SPEL, 6, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1500, 500, MS_BRIBE, MZ_HUMAN, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS | M1_HUMANOID,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_PRINCE | M2_MALE | M2_COLLECT,
        M3_WANTSAMUL | M3_INFRAVISIBLE | M3_INFRAVISION, 40, HI_LORD),
    # PM_BAALZEBUB
    _mon(
        308, S_DEMON, "Baalzebub",
        89, 9, -5, 85, 20, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_BITE, AD_DRST, 2, 6), Attack(AT_GAZE, AD_STUN, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1500, 500, MS_BRIBE, MZ_LARGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_PRINCE | M2_MALE,
        M3_WANTSAMUL | M3_WAITFORU | M3_INFRAVISIBLE | M3_INFRAVISION, 45,
        HI_LORD),
    # PM_ASMODEUS
    _mon(
        309, S_DEMON, "Asmodeus",
        105, 12, -7, 90, 20, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_PHYS, 4, 4), Attack(AT_MAGC, AD_COLD, 6, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        1500, 500, MS_BRIBE, MZ_HUGE, MR_FIRE | MR_COLD | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_HUMANOID | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_STRONG | M2_NASTY | M2_PRINCE | M2_MALE,
        M3_WANTSAMUL | M3_WAITFORU | M3_INFRAVISIBLE | M3_INFRAVISION, 53,
        HI_LORD),
    # PM_DEMOGORGON
    _mon(
        310, S_DEMON, "Demogorgon",
        106, 15, -8, 95, -20, G_HELL | G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_MAGC, AD_SPEL, 8, 6), Attack(AT_STNG, AD_DRLI, 1, 4),
        Attack(AT_CLAW, AD_DISE, 1, 6), Attack(AT_CLAW, AD_DISE, 1, 6), NO_ATK,
        NO_ATK,
        1500, 500, MS_GROWL, MZ_HUGE, MR_FIRE | MR_POISON, 0,
        M1_FLY | M1_SEE_INVIS | M1_NOHANDS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_PNAME | M2_NASTY | M2_PRINCE | M2_MALE,
        M3_WANTSAMUL | M3_INFRAVISIBLE | M3_INFRAVISION, 57, HI_LORD),
    # PM_DEATH
    _mon(
        311, S_DEMON, "Death",
        30, 12, -5, 100, 0, G_UNIQ | G_NOGEN,
        Attack(AT_TUCH, AD_DETH, 8, 8), Attack(AT_TUCH, AD_DETH, 8, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 1, MS_RIDER, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_HUMANOID | M1_REGEN | M1_SEE_INVIS | M1_TPORT_CNTRL,
        M2_NOPOLY | M2_STALK | M2_HOSTILE | M2_PNAME | M2_STRONG | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION | M3_DISPLACES, 34, HI_OVERLORD),
    # PM_PESTILENCE
    _mon(
        312, S_DEMON, "Pestilence",
        30, 12, -5, 100, 0, G_UNIQ | G_NOGEN,
        Attack(AT_TUCH, AD_PEST, 8, 8), Attack(AT_TUCH, AD_PEST, 8, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 1, MS_RIDER, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_HUMANOID | M1_REGEN | M1_SEE_INVIS | M1_TPORT_CNTRL,
        M2_NOPOLY | M2_STALK | M2_HOSTILE | M2_PNAME | M2_STRONG | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION | M3_DISPLACES, 34, HI_OVERLORD),
    # PM_FAMINE
    _mon(
        313, S_DEMON, "Famine",
        30, 12, -5, 100, 0, G_UNIQ | G_NOGEN,
        Attack(AT_TUCH, AD_FAMN, 8, 8), Attack(AT_TUCH, AD_FAMN, 8, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 1, MS_RIDER, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_HUMANOID | M1_REGEN | M1_SEE_INVIS | M1_TPORT_CNTRL,
        M2_NOPOLY | M2_STALK | M2_HOSTILE | M2_PNAME | M2_STRONG | M2_NASTY,
        M3_INFRAVISIBLE | M3_INFRAVISION | M3_DISPLACES, 34, HI_OVERLORD),
    # PM_MAIL_DAEMON
    _mon(
        314, S_DEMON, "mail daemon",
        56, 24, 10, 127, 0, G_NOGEN | G_NOCORPSE,
        NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        600, 300, MS_SILENT, MZ_HUMAN,
        MR_FIRE | MR_COLD | MR_ELEC | MR_SLEEP | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_SWIM | M1_BREATHLESS | M1_SEE_INVIS | M1_HUMANOID | M1_POIS,
        M2_NOPOLY | M2_STALK | M2_PEACEFUL, M3_INFRAVISIBLE | M3_INFRAVISION,
        26, CLR_BRIGHT_BLUE),
    # PM_DJINNI
    _mon(
        315, S_DEMON, "djinni",
        7, 12, 4, 30, 0, G_NOGEN | G_NOCORPSE,
        Attack(AT_WEAP, AD_PHYS, 2, 8), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1500, 400, MS_DJINNI, MZ_HUMAN, MR_POISON | MR_STONE, 0,
        M1_HUMANOID | M1_FLY | M1_POIS, M2_NOPOLY | M2_STALK | M2_COLLECT,
        M3_INFRAVISIBLE, 8, CLR_YELLOW),
    # ---- S_EEL ----
    # PM_JELLYFISH
    _mon(
        316, S_EEL, "jellyfish",
        3, 3, 6, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_STNG, AD_DRST, 3, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        80, 20, MS_SILENT, MZ_SMALL, MR_POISON, MR_POISON,
        M1_SWIM | M1_AMPHIBIOUS | M1_NOLIMBS | M1_NOHEAD | M1_NOTAKE | M1_POIS,
        M2_HOSTILE, 0, 5, CLR_BLUE),
    # PM_PIRANHA
    _mon(
        317, S_EEL, "piranha",
        5, 18, 4, 0, 0, G_GENO | G_NOGEN | G_SGROUP,
        Attack(AT_BITE, AD_PHYS, 2, 6), Attack(AT_BITE, AD_PHYS, 2, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        60, 30, MS_SILENT, MZ_SMALL, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_NOLIMBS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, 0, 7, CLR_RED),
    # PM_SHARK
    _mon(
        318, S_EEL, "shark",
        7, 12, 2, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_BITE, AD_PHYS, 5, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        500, 350, MS_SILENT, MZ_LARGE, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_NOLIMBS | M1_CARNIVORE | M1_OVIPAROUS | M1_THICK_HIDE | M1_NOTAKE,
        M2_HOSTILE, 0, 9, CLR_GRAY),
    # PM_GIANT_EEL
    _mon(
        319, S_EEL, "giant eel",
        5, 9, -1, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_BITE, AD_PHYS, 3, 6), Attack(AT_TUCH, AD_WRAP, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        200, 250, MS_SILENT, MZ_HUGE, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, M3_INFRAVISIBLE, 7, CLR_CYAN),
    # PM_ELECTRIC_EEL
    _mon(
        320, S_EEL, "electric eel",
        7, 10, -3, 0, 0, G_GENO | G_NOGEN,
        Attack(AT_BITE, AD_ELEC, 4, 6), Attack(AT_TUCH, AD_WRAP, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        200, 250, MS_SILENT, MZ_HUGE, MR_ELEC, MR_ELEC,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_SLITHY | M1_NOLIMBS | M1_CARNIVORE | M1_OVIPAROUS | M1_NOTAKE,
        M2_HOSTILE, M3_INFRAVISIBLE, 10, CLR_BRIGHT_BLUE),
    # PM_KRAKEN
    _mon(
        321, S_EEL, "kraken",
        20, 3, 6, 0, -3, G_GENO | G_NOGEN,
        Attack(AT_CLAW, AD_PHYS, 2, 4), Attack(AT_CLAW, AD_PHYS, 2, 4),
        Attack(AT_HUGS, AD_WRAP, 2, 6), Attack(AT_BITE, AD_PHYS, 5, 4), NO_ATK,
        NO_ATK,
        1800, 1000, MS_SILENT, MZ_HUGE, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE,
        M2_NOPOLY | M2_HOSTILE | M2_STRONG, M3_INFRAVISIBLE, 22, CLR_RED),
    # ---- S_LIZARD ----
    # PM_NEWT
    _mon(
        322, S_LIZARD, "newt",
        0, 6, 8, 0, 0, G_GENO | 5,
        Attack(AT_BITE, AD_PHYS, 1, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 20, MS_SILENT, MZ_TINY, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE, 0, 1, CLR_YELLOW),
    # PM_GECKO
    _mon(
        323, S_LIZARD, "gecko",
        1, 6, 8, 0, 0, G_GENO | 5,
        Attack(AT_BITE, AD_PHYS, 1, 3), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 20, MS_SQEEK, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, 0, 2, CLR_GREEN),
    # PM_IGUANA
    _mon(
        324, S_LIZARD, "iguana",
        2, 6, 7, 0, 0, G_GENO | 5,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        30, 30, MS_SILENT, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, 0, 3, CLR_BROWN),
    # PM_BABY_CROCODILE
    _mon(
        325, S_LIZARD, "baby crocodile",
        3, 6, 7, 0, 0, G_GENO,
        Attack(AT_BITE, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        200, 200, MS_CHIRP, MZ_MEDIUM, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE,
        M2_HOSTILE, 0, 4, CLR_BROWN),
    # PM_LIZARD
    _mon(
        326, S_LIZARD, "lizard",
        5, 6, 6, 10, 0, G_GENO | 5,
        Attack(AT_BITE, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        10, 40, MS_SILENT, MZ_TINY, MR_STONE, MR_STONE,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE, M2_HOSTILE, 0, 6, CLR_GREEN),
    # PM_CHAMELEON
    _mon(
        327, S_LIZARD, "chameleon",
        6, 5, 6, 10, 0, G_GENO | 2,
        Attack(AT_BITE, AD_PHYS, 4, 2), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        100, 100, MS_SILENT, MZ_TINY, 0, 0,
        M1_ANIMAL | M1_NOHANDS | M1_CARNIVORE,
        M2_NOPOLY | M2_HOSTILE | M2_SHAPESHIFTER, 0, 7, CLR_BROWN),
    # PM_CROCODILE
    _mon(
        328, S_LIZARD, "crocodile",
        6, 9, 5, 0, 0, G_GENO | 1,
        Attack(AT_BITE, AD_PHYS, 4, 2), Attack(AT_CLAW, AD_PHYS, 1, 12),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_BELLOW, MZ_LARGE, 0, 0,
        M1_SWIM | M1_AMPHIBIOUS | M1_ANIMAL | M1_THICK_HIDE | M1_NOHANDS | M1_OVIPAROUS | M1_CARNIVORE,
        M2_STRONG | M2_HOSTILE, 0, 7, CLR_BROWN),
    # PM_SALAMANDER
    _mon(
        329, S_LIZARD, "salamander",
        8, 12, -1, 0, -9, G_HELL | 1,
        Attack(AT_WEAP, AD_PHYS, 2, 8), Attack(AT_TUCH, AD_FIRE, 1, 6),
        Attack(AT_HUGS, AD_PHYS, 2, 6), Attack(AT_HUGS, AD_FIRE, 3, 6), NO_ATK,
        NO_ATK,
        1500, 400, MS_MUMBLE, MZ_HUMAN, MR_SLEEP | MR_FIRE, MR_FIRE,
        M1_HUMANOID | M1_SLITHY | M1_THICK_HIDE | M1_POIS,
        M2_STALK | M2_HOSTILE | M2_COLLECT | M2_MAGIC, M3_INFRAVISIBLE, 12,
        CLR_ORANGE),
    # ---- SPECIAL_PM: the G_NOGEN | M2_NOPOLY
    # ---- section -- never generated, never
    # ---- poly'd into (the quest and role rows)
    # ---- S_WORM_TAIL ----
    # PM_LONG_WORM_TAIL
    _mon(
        330, S_WORM_TAIL, "long worm tail",
        0, 0, 0, 0, 0, G_NOGEN | G_NOCORPSE | G_UNIQ,
        NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        0, 0, 0, 0, 0, 0,
        0, M2_NOPOLY, 0, 1, CLR_BROWN),
    # ---- S_HUMAN ----
    # PM_ARCHEOLOGIST
    _mon(
        331, S_HUMAN, "archeologist",
        10, 12, 10, 1, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_TUNNEL | M1_NEEDPICK | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_BARBARIAN
    _mon(
        332, S_HUMAN, "barbarian",
        10, 12, 10, 1, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_CAVE_DWELLER
    _mon(
        333, S_HUMAN, _nams("caveman", "cavewoman", "cave dweller"),
        10, 12, 10, 0, 1, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_HEALER
    _mon(
        334, S_HUMAN, "healer",
        10, 12, 10, 1, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_KNIGHT
    _mon(
        335, S_HUMAN, "knight",
        10, 12, 10, 1, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_MONK
    _mon(
        336, S_HUMAN, "monk",
        10, 12, 10, 2, 0, G_NOGEN,
        Attack(AT_CLAW, AD_PHYS, 1, 8), Attack(AT_KICK, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_HERBIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 11,
        HI_DOMESTIC),
    # PM_CLERIC
    _mon(
        337, S_HUMAN, _nams("priest", "priestess", "cleric"),
        10, 12, 10, 2, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_CLRC, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_RANGER
    _mon(
        338, S_HUMAN, "ranger",
        10, 12, 10, 2, -3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_ROGUE
    _mon(
        339, S_HUMAN, "rogue",
        10, 12, 10, 1, -3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_GREEDY | M2_JEWELS | M2_COLLECT,
        M3_INFRAVISIBLE, 12, HI_DOMESTIC),
    # PM_SAMURAI
    _mon(
        340, S_HUMAN, "samurai",
        10, 12, 10, 1, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_TOURIST
    _mon(
        341, S_HUMAN, "tourist",
        10, 12, 10, 1, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT, M3_INFRAVISIBLE, 12,
        HI_DOMESTIC),
    # PM_VALKYRIE
    _mon(
        342, S_HUMAN, "valkyrie",
        10, 12, 10, 1, 1, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, MR_COLD, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_FEMALE | M2_COLLECT,
        M3_INFRAVISIBLE, 12, HI_DOMESTIC),
    # PM_WIZARD
    _mon(
        343, S_HUMAN, "wizard",
        10, 12, 10, 3, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 12, HI_DOMESTIC),
    # PM_LORD_CARNARVON
    _mon(
        344, S_HUMAN, "Lord Carnarvon",
        20, 15, 0, 90, 20, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_MAGC, AD_SPEL, 4, 8),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_PELIAS
    _mon(
        345, S_HUMAN, "Pelias",
        20, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_WEAP, AD_PHYS, 4, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_SHAMAN_KARNOV
    _mon(
        346, S_HUMAN, "Shaman Karnov",
        20, 15, 0, 90, 20, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_MAGC, AD_CLRC, 2, 8),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_HIPPOCRATES
    _mon(
        347, S_HUMAN, "Hippocrates",
        20, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_CLRC, 3, 8),
        Attack(AT_MAGC, AD_CLRC, 3, 8), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 26, HI_LORD),
    # PM_KING_ARTHUR
    _mon(
        348, S_HUMAN, "King Arthur",
        20, 15, 0, 90, 20, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_WEAP, AD_PHYS, 4, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_GRAND_MASTER
    _mon(
        349, S_HUMAN, "Grand Master",
        25, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_PHYS, 4, 10), Attack(AT_KICK, AD_PHYS, 2, 8),
        Attack(AT_MAGC, AD_CLRC, 2, 8), Attack(AT_MAGC, AD_CLRC, 2, 8), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN,
        MR_FIRE | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_HUMANOID | M1_SEE_INVIS | M1_HERBIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_NASTY | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 30, CLR_BLACK),
    # PM_ARCH_PRIEST
    _mon(
        350, S_HUMAN, "Arch Priest",
        25, 15, 7, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_KICK, AD_PHYS, 2, 8),
        Attack(AT_MAGC, AD_CLRC, 2, 8), Attack(AT_MAGC, AD_CLRC, 2, 8), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN,
        MR_FIRE | MR_ELEC | MR_SLEEP | MR_POISON, 0,
        M1_HUMANOID | M1_SEE_INVIS | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 30, CLR_WHITE),
    # PM_ORION
    _mon(
        351, S_HUMAN, "Orion",
        20, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_MAGC, AD_SPEL, 4, 8),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        2200, 700, MS_LEADER, MZ_HUGE, 0, 0,
        M1_HUMANOID | M1_OMNIVORE | M1_SEE_INVIS | M1_SWIM | M1_AMPHIBIOUS,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISION | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_MASTER_OF_THIEVES
    _mon(
        352, S_HUMAN, "Master of Thieves",
        20, 15, 0, 90, -20, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_WEAP, AD_PHYS, 2, 6),
        Attack(AT_CLAW, AD_SAMU, 2, 4), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_GREEDY | M2_JEWELS | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_LORD_SATO
    _mon(
        353, S_HUMAN, "Lord Sato",
        20, 15, 0, 90, 20, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_WEAP, AD_PHYS, 4, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_TWOFLOWER
    _mon(
        354, S_HUMAN, "Twoflower",
        20, 15, 10, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 22, HI_DOMESTIC),
    # PM_NORN
    _mon(
        355, S_HUMAN, "Norn",
        20, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_WEAP, AD_PHYS, 4, 10),
        NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        1800, 550, MS_LEADER, MZ_HUGE, MR_COLD, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_FEMALE | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 24, HI_LORD),
    # PM_NEFERET_THE_GREEN
    _mon(
        356, S_HUMAN, "Neferet the Green",
        20, 15, 0, 90, 0, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 10), Attack(AT_MAGC, AD_SPEL, 2, 8),
        Attack(AT_MAGC, AD_SPEL, 2, 8), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_LEADER, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_FEMALE | M2_PNAME | M2_PEACEFUL | M2_STRONG | M2_COLLECT | M2_MAGIC,
        M3_CLOSE | M3_INFRAVISIBLE, 25, CLR_GREEN),
    # ---- S_DEMON ----
    # PM_MINION_OF_HUHETOTL
    _mon(
        357, S_DEMON, "Minion of Huhetotl",
        16, 12, -2, 75, -14, G_NOCORPSE | G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 8, 4), Attack(AT_WEAP, AD_PHYS, 4, 6),
        Attack(AT_MAGC, AD_SPEL, 0, 0), Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_LARGE, MR_FIRE | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_STALK | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_COLLECT,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISION | M3_INFRAVISIBLE, 23,
        CLR_ORANGE),
    # ---- S_HUMAN ----
    # PM_THOTH_AMON
    _mon(
        358, S_HUMAN, "Thoth Amon",
        16, 12, 0, 10, -14, G_NOGEN | G_UNIQ | G_NOCORPSE,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_SPEL, 0, 0),
        Attack(AT_MAGC, AD_SPEL, 0, 0), Attack(AT_CLAW, AD_SAMU, 1, 4), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_HUMAN, MR_POISON | MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_STRONG | M2_MALE | M2_STALK | M2_HOSTILE | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 22, HI_LORD),
    # ---- S_DRAGON ----
    # PM_CHROMATIC_DRAGON
    _mon(
        359, S_DRAGON, "Chromatic Dragon",
        16, 12, 0, 30, -14, G_NOGEN | G_UNIQ,
        Attack(AT_BREA, AD_RBRE, 6, 6), Attack(AT_MAGC, AD_SPEL, 0, 0),
        Attack(AT_CLAW, AD_SAMU, 2, 8), Attack(AT_BITE, AD_PHYS, 4, 8),
        Attack(AT_BITE, AD_PHYS, 4, 8), Attack(AT_STNG, AD_PHYS, 1, 6),
        WT_DRAGON, 1700, MS_NEMESIS, MZ_GIGANTIC,
        MR_FIRE | MR_COLD | MR_SLEEP | MR_DISINT | MR_ELEC | MR_POISON | MR_ACID | MR_STONE,
        MR_FIRE | MR_COLD | MR_SLEEP | MR_DISINT | MR_ELEC | MR_POISON | MR_ACID | MR_STONE,
        M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_HOSTILE | M2_FEMALE | M2_STALK | M2_STRONG | M2_NASTY | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISION | M3_INFRAVISIBLE, 23,
        HI_LORD),
    # ---- S_GIANT ----
    # PM_CYCLOPS
    _mon(
        360, S_GIANT, "Cyclops",
        18, 12, 0, 0, -15, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 4, 8), Attack(AT_WEAP, AD_PHYS, 4, 8),
        Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        1900, 700, MS_NEMESIS, MZ_HUGE, MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_GIANT | M2_STRONG | M2_ROCKTHROW | M2_STALK | M2_HOSTILE | M2_NASTY | M2_MALE | M2_JEWELS | M2_COLLECT,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISION | M3_INFRAVISIBLE, 23,
        CLR_GRAY),
    # ---- S_DRAGON ----
    # PM_IXOTH
    _mon(
        361, S_DRAGON, "Ixoth",
        15, 12, -1, 20, -14, G_NOGEN | G_UNIQ,
        Attack(AT_BREA, AD_FIRE, 8, 6), Attack(AT_BITE, AD_PHYS, 4, 8),
        Attack(AT_MAGC, AD_SPEL, 0, 0), Attack(AT_CLAW, AD_PHYS, 2, 4),
        Attack(AT_CLAW, AD_SAMU, 2, 4), NO_ATK,
        WT_DRAGON, 1600, MS_NEMESIS, MZ_GIGANTIC, MR_FIRE | MR_STONE, MR_FIRE,
        M1_FLY | M1_THICK_HIDE | M1_NOHANDS | M1_CARNIVORE | M1_SEE_INVIS,
        M2_NOPOLY | M2_MALE | M2_PNAME | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_STALK | M2_GREEDY | M2_JEWELS | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 22, CLR_RED),
    # ---- S_HUMAN ----
    # PM_MASTER_KAEN
    _mon(
        362, S_HUMAN, "Master Kaen",
        25, 12, -10, 10, -20, G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_PHYS, 16, 2), Attack(AT_CLAW, AD_PHYS, 16, 2),
        Attack(AT_MAGC, AD_CLRC, 0, 0), Attack(AT_CLAW, AD_SAMU, 1, 4), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_HUMAN, MR_POISON | MR_STONE, MR_POISON,
        M1_HUMANOID | M1_HERBIVORE | M1_SEE_INVIS,
        M2_NOPOLY | M2_HUMAN | M2_MALE | M2_PNAME | M2_HOSTILE | M2_STRONG | M2_NASTY | M2_STALK | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 31, HI_LORD),
    # ---- S_DEMON ----
    # PM_NALZOK
    _mon(
        363, S_DEMON, "Nalzok",
        16, 12, -2, 85, -127, G_NOGEN | G_UNIQ | G_NOCORPSE,
        Attack(AT_WEAP, AD_PHYS, 8, 4), Attack(AT_WEAP, AD_PHYS, 4, 6),
        Attack(AT_MAGC, AD_SPEL, 0, 0), Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_LARGE, MR_FIRE | MR_POISON | MR_STONE, 0,
        M1_FLY | M1_SEE_INVIS | M1_POIS,
        M2_NOPOLY | M2_DEMON | M2_MALE | M2_PNAME | M2_HOSTILE | M2_STRONG | M2_STALK | M2_NASTY | M2_COLLECT,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISION | M3_INFRAVISIBLE, 23,
        CLR_ORANGE),
    # ---- S_SPIDER ----
    # PM_SCORPIUS
    _mon(
        364, S_SPIDER, "Scorpius",
        15, 12, 10, 0, -15, G_NOGEN | G_UNIQ,
        Attack(AT_CLAW, AD_PHYS, 2, 6), Attack(AT_CLAW, AD_SAMU, 2, 6),
        Attack(AT_STNG, AD_DISE, 1, 4), NO_ATK, NO_ATK, NO_ATK,
        750, 350, MS_NEMESIS, MZ_HUMAN, MR_POISON | MR_STONE, MR_POISON,
        M1_ANIMAL | M1_NOHANDS | M1_OVIPAROUS | M1_POIS | M1_CARNIVORE,
        M2_NOPOLY | M2_MALE | M2_PNAME | M2_HOSTILE | M2_STRONG | M2_STALK | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU, 17, HI_LORD),
    # ---- S_HUMAN ----
    # PM_MASTER_ASSASSIN
    _mon(
        365, S_HUMAN, "Master Assassin",
        15, 12, 0, 30, 18, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_DRST, 2, 6), Attack(AT_WEAP, AD_PHYS, 2, 8),
        Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_HUMAN, MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_MALE | M2_HOSTILE | M2_STALK | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 20, HI_LORD),
    # PM_ASHIKAGA_TAKAUJI
    _mon(
        366, S_HUMAN, "Ashikaga Takauji",
        15, 12, 0, 40, -13, G_NOGEN | G_UNIQ | G_NOCORPSE,
        Attack(AT_WEAP, AD_PHYS, 2, 6), Attack(AT_WEAP, AD_PHYS, 2, 6),
        Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_HUMAN, MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PNAME | M2_HOSTILE | M2_STRONG | M2_STALK | M2_NASTY | M2_MALE | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 19, HI_LORD),
    # ---- S_GIANT ----
    # PM_LORD_SURTUR
    _mon(
        367, S_GIANT, "Lord Surtur",
        15, 12, 2, 50, 12, G_NOGEN | G_UNIQ,
        Attack(AT_WEAP, AD_PHYS, 2, 10), Attack(AT_WEAP, AD_PHYS, 2, 10),
        Attack(AT_CLAW, AD_SAMU, 2, 6), NO_ATK, NO_ATK, NO_ATK,
        2250, 850, MS_NEMESIS, MZ_HUGE, MR_FIRE | MR_STONE, MR_FIRE,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_GIANT | M2_MALE | M2_PNAME | M2_HOSTILE | M2_STALK | M2_STRONG | M2_NASTY | M2_ROCKTHROW | M2_JEWELS | M2_COLLECT,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISION | M3_INFRAVISIBLE, 19,
        HI_LORD),
    # ---- S_HUMAN ----
    # PM_DARK_ONE
    _mon(
        368, S_HUMAN, "Dark One",
        15, 12, 0, 80, -10, G_NOGEN | G_UNIQ | G_NOCORPSE,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6),
        Attack(AT_CLAW, AD_SAMU, 1, 4), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK,
        WT_HUMAN, 400, MS_NEMESIS, MZ_HUMAN, MR_STONE, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_STRONG | M2_HOSTILE | M2_STALK | M2_NASTY | M2_COLLECT | M2_MAGIC,
        M3_WANTSARTI | M3_WAITFORU | M3_INFRAVISIBLE, 20, CLR_BLACK),
    # PM_STUDENT
    _mon(
        369, S_HUMAN, "student",
        5, 12, 10, 10, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_TUNNEL | M1_NEEDPICK | M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_CHIEFTAIN
    _mon(
        370, S_HUMAN, "chieftain",
        5, 12, 10, 10, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_NEANDERTHAL
    _mon(
        371, S_HUMAN, "neanderthal",
        5, 12, 10, 10, 1, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 2, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_ATTENDANT
    _mon(
        372, S_HUMAN, "attendant",
        5, 12, 10, 10, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, MR_POISON, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_PAGE
    _mon(
        373, S_HUMAN, "page",
        5, 12, 10, 10, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_ABBOT
    _mon(
        374, S_HUMAN, "abbot",
        5, 12, 10, 20, 0, G_NOGEN,
        Attack(AT_CLAW, AD_PHYS, 8, 2), Attack(AT_KICK, AD_STUN, 3, 2),
        Attack(AT_MAGC, AD_CLRC, 0, 0), NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_HERBIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 8, HI_DOMESTIC),
    # PM_ACOLYTE
    _mon(
        375, S_HUMAN, "acolyte",
        5, 12, 10, 20, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_CLRC, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 8, HI_DOMESTIC),
    # PM_HUNTER
    _mon(
        376, S_HUMAN, "hunter",
        5, 12, 10, 10, -7, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 4), NO_ATK, NO_ATK, NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_SEE_INVIS | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISION | M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_THUG
    _mon(
        377, S_HUMAN, "thug",
        5, 12, 10, 10, -3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_WEAP, AD_PHYS, 1, 6), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_GREEDY | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_NINJA
    _mon(
        378, S_HUMAN, "ninja",
        5, 12, 10, 10, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_HUMANOID, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_HOSTILE | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_ROSHI
    _mon(
        379, S_HUMAN, "roshi",
        5, 12, 10, 10, 3, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_GUIDE
    _mon(
        380, S_HUMAN, "guide",
        5, 12, 10, 20, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 8, HI_DOMESTIC),
    # PM_WARRIOR
    _mon(
        381, S_HUMAN, "warrior",
        5, 12, 10, 10, 1, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 8), Attack(AT_WEAP, AD_PHYS, 1, 8), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT | M2_FEMALE,
        M3_INFRAVISIBLE, 7, HI_DOMESTIC),
    # PM_APPRENTICE
    _mon(
        382, S_HUMAN, "apprentice",
        5, 12, 10, 30, 0, G_NOGEN,
        Attack(AT_WEAP, AD_PHYS, 1, 6), Attack(AT_MAGC, AD_SPEL, 0, 0), NO_ATK,
        NO_ATK, NO_ATK, NO_ATK,
        WT_HUMAN, 400, MS_GUARDIAN, MZ_HUMAN, 0, 0,
        M1_HUMANOID | M1_OMNIVORE,
        M2_NOPOLY | M2_HUMAN | M2_PEACEFUL | M2_STRONG | M2_COLLECT | M2_MAGIC,
        M3_INFRAVISIBLE, 8, HI_DOMESTIC),
]
