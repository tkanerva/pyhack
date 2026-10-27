"""Monster type table (port of src/monst.c + include/monsters.h).

In the C source the table is built by expanding include/monsters.h
through the MON() macro in monst.c.  A Python port has to respect the
same order -- the rows are built from the declarations -- so it is
three modules:

- `monst_defs` -- the declarations: the enums (`MonsterClass`,
                   `AtkType`, `DmgType`, `MR`, `M1`/`M2`/`M3`,
                   `Geno`, `MvitalsFlag`, `MSize`, `MSound`,
                   `MGender`), the C-style aliases (S_ANT, AT_BITE,
                   MR_POISON, ...), the `Attack` / `PerMonst` row
                   types and the `_mon` MON() builder.  It imports
                   nothing from the rest of the package, so the
                   constants there are plain inferred ints/enums;
- `monst_data` -- the three large tables, kept verbatim:
                   `PM_NAMES` / `SUBSET_PM` / `MONS`;
- this module  -- the public API: the accessors (monsndx, monclass,
                   defch, monname, is_golem, is_dragon) and the
                   table check `_validate()`.

Table policy (monst_data.py): `PM_NAMES` records the COMPLETE C
ordering of all 383 monster types (default build: CHARON undefined;
MAIL_STRUCTURES always defined in 5.0 (global.h), so the mail daemon
IS in the table; all `#if 0` blocks excluded), `SUBSET_PM` the
indices of the implemented subset, and `MONS` the (sparse) table
itself: PerMonst at the C index for the implemented subset, None
elsewhere.  The ordering is recorded even though only a subset of the
table is implemented, so the PM_ numbering is fixed once and the
remaining ~90% can be completed later without renumbering anything.

Core-subset policy (per project decision): only the ~10% of monsters
needed to build and play the core game is transcribed (the demo's
goblin/orc/bat, low-level dungeon staples, and the carriers of the
special-attack mechanics: petrify, drain, steal, stick, breath,
...).  The subset is `SUBSET_PM` (in monst_data.py).

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
  excludes.  Kept with this note so a later pass that adds
  Charon doesn't have to invent a number.
"""

from .monst_defs import (
    MonsterClass, AtkType, DmgType, MR, M1, M2, M3, Geno, MvitalsFlag, MSize,
    MSound, MGender, S_ANT, S_BLOB, S_COCKATRICE, S_DOG, S_EYE, S_FELINE,
    S_GREMLIN, S_HUMANOID, S_IMP, S_JELLY, S_KOBOLD, S_LEPRECHAUN, S_MIMIC,
    S_NYMPH, S_ORC, S_PIERCER, S_QUADRUPED, S_RODENT, S_SPIDER, S_TRAPPER,
    S_UNICORN, S_VORTEX, S_WORM, S_XAN, S_LIGHT, S_ZRUTY, S_ANGEL, S_BAT,
    S_CENTAUR, S_DRAGON, S_ELEMENTAL, S_FUNGUS, S_GNOME, S_GIANT, S_INVISIBLE,
    S_JABBERWOCK, S_KOP, S_LICH, S_MUMMY, S_NAGA, S_OGRE, S_PUDDING,
    S_QUANTMECH, S_RUSTMONST, S_SNAKE, S_TROLL, S_UMBER, S_VAMPIRE, S_WRAITH,
    S_XORN, S_YETI, S_ZOMBIE, S_HUMAN, S_GHOST, S_GOLEM, S_DEMON, S_EEL,
    S_LIZARD, S_WORM_TAIL, S_MIMIC_DEF, MAXMCLASSES, DEFCHARS, AT_ANY, AT_NONE,
    AT_CLAW, AT_BITE, AT_KICK, AT_BUTT, AT_TUCH, AT_STNG, AT_HUGS, AT_SPIT,
    AT_ENGL, AT_BREA, AT_EXPL, AT_BOOM, AT_GAZE, AT_TENT, AT_WEAP, AT_MAGC,
    NATTK, distance_atk_type, AD_ANY, AD_PHYS, AD_MAGM, AD_FIRE, AD_COLD,
    AD_SLEE, AD_DISN, AD_ELEC, AD_DRST, AD_ACID, AD_SPC1, AD_SPC2, AD_BLND,
    AD_STUN, AD_SLOW, AD_PLYS, AD_DRLI, AD_DREN, AD_LEGS, AD_STON, AD_STCK,
    AD_SGLD, AD_SITM, AD_SEDU, AD_TLPT, AD_RUST, AD_CONF, AD_DGST, AD_HEAL,
    AD_WRAP, AD_WERE, AD_DRDX, AD_DRCO, AD_DRIN, AD_DISE, AD_DCAY, AD_SSEX,
    AD_HALU, AD_DETH, AD_PEST, AD_FAMN, AD_SLIM, AD_ENCH, AD_CORR, AD_POLY,
    AD_CLRC, AD_SPEL, AD_RBRE, AD_SAMU, AD_CURS, MR_FIRE, MR_COLD, MR_SLEEP,
    MR_DISINT, MR_ELEC, MR_POISON, MR_ACID, MR_STONE, MR2_SEE_INVIS,
    MR2_LEVITATE, MR2_WATERWALK, MR2_MAGBREATH, MR2_DISPLACED, MR2_STRENGTH,
    MR2_FUMBLING, M1_FLY, M1_SWIM, M1_AMORPHOUS, M1_WALLWALK, M1_CLING,
    M1_TUNNEL, M1_NEEDPICK, M1_CONCEAL, M1_HIDE, M1_AMPHIBIOUS, M1_BREATHLESS,
    M1_NOTAKE, M1_NOEYES, M1_NOHANDS, M1_NOLIMBS, M1_NOHEAD, M1_MINDLESS,
    M1_HUMANOID, M1_ANIMAL, M1_SLITHY, M1_UNSOLID, M1_THICK_HIDE, M1_OVIPAROUS,
    M1_REGEN, M1_SEE_INVIS, M1_TPORT, M1_TPORT_CNTRL, M1_ACID, M1_POIS,
    M1_CARNIVORE, M1_HERBIVORE, M1_OMNIVORE, M1_METALLIVORE, M2_NOPOLY,
    M2_UNDEAD, M2_WERE, M2_HUMAN, M2_ELF, M2_DWARF, M2_GNOME, M2_ORC, M2_DEMON,
    M2_MERC, M2_LORD, M2_PRINCE, M2_MINION, M2_GIANT, M2_SHAPESHIFTER, M2_MALE,
    M2_FEMALE, M2_NEUTER, M2_PNAME, M2_HOSTILE, M2_PEACEFUL, M2_DOMESTIC,
    M2_WANDER, M2_STALK, M2_NASTY, M2_STRONG, M2_ROCKTHROW, M2_GREEDY,
    M2_JEWELS, M2_COLLECT, M2_MAGIC, M3_WANTSAMUL, M3_WANTSBELL, M3_WANTSBOOK,
    M3_WANTSCAND, M3_WANTSARTI, M3_WANTSALL, M3_WAITFORU, M3_CLOSE,
    M3_COVETOUS, M3_WAITMASK, M3_INFRAVISION, M3_INFRAVISIBLE, M3_DISPLACES,
    MZ_TINY, MZ_SMALL, MZ_MEDIUM, MZ_HUMAN, MZ_LARGE, MZ_HUGE, MZ_GIGANTIC,
    MS_SILENT, MS_BARK, MS_MEW, MS_ROAR, MS_BELLOW, MS_GROWL, MS_SQEEK,
    MS_SQAWK, MS_CHIRP, MS_HISS, MS_BUZZ, MS_GRUNT, MS_NEIGH, MS_MOO, MS_WAIL,
    MS_GURGLE, MS_BURBLE, MS_TRUMPET, MS_ANIMAL, MS_SHRIEK, MS_BONES, MS_LAUGH,
    MS_MUMBLE, MS_IMITATE, MS_WERE, MS_ORC, MS_HUMANOID, MS_ARREST, MS_SOLDIER,
    MS_GUARD, MS_DJINNI, MS_NURSE, MS_SEDUCE, MS_VAMPIRE, MS_BRIBE, MS_CUSS,
    MS_RIDER, MS_LEADER, MS_NEMESIS, MS_GUARDIAN, MS_SELL, MS_ORACLE,
    MS_PRIEST, MS_SPELL, MS_BOAST, MS_GROAN, MS_FERRY, WT_ETHEREAL, WT_JELLY,
    WT_ELF, WT_HUMAN, WT_BABY_DRAGON, WT_DRAGON, WT_NYMPH, NORMAL_SPEED,
    A_NONE, A_CHAOTIC, A_NEUTRAL, A_LAWFUL, G_UNIQ, G_NOHELL, G_HELL, G_NOGEN,
    G_SGROUP, G_LGROUP, G_GENO, G_NOCORPSE, G_FREQ, G_IGNORE, G_KNOWN, G_GENOD,
    G_EXTINCT, G_GONE, MV_KNOWS_EGG, MALE, FEMALE, NEUTRAL, NUM_MGENDERS,
    MH_HUMAN, MH_ELF, MH_DWARF, MH_GNOME, MH_ORC, NON_PM, LOW_PM, LEAVESTATUE,
    HIGH_PM, Attack, PerMonst, NO_ATK, NUMMONS, SPECIAL_PM,
)

# The PM_* anchors (C: enum monnums) are re-exported here: the game
# code and the tests look the numbering up by name (PM_BAT,
# PM_OGRE, ...).  They stay out of __all__ -- they are just indices
# into PM_NAMES, not part of the C header's own API.
from .monst_defs import (  # noqa: F401
    PM_COCKATRICE, PM_IMP, PM_QUASIT, PM_KOBOLD, PM_LARGE_KOBOLD,
    PM_LEPRECHAUN, PM_LARGE_MIMIC, PM_WOOD_NYMPH, PM_GOBLIN, PM_HOBGOBLIN,
    PM_HILL_ORC, PM_SEWER_RAT, PM_GIANT_RAT, PM_CAVE_SPIDER, PM_CENTIPEDE,
    PM_GIANT_SPIDER, PM_XAN, PM_YELLOW_LIGHT, PM_ZRUTY, PM_BAT, PM_GIANT_BAT,
    PM_GRAY_DRAGON, PM_BLACK_DRAGON, PM_YELLOW_DRAGON, PM_FIRE_ELEMENTAL,
    PM_HILL_GIANT, PM_OGRE, PM_GARTER_SNAKE, PM_SNAKE, PM_TROLL, PM_VAMPIRE,
    PM_WRAITH, PM_OWLBEAR, PM_KOBOLD_ZOMBIE, PM_HUMAN_ZOMBIE, PM_GHOUL,
    PM_SKELETON, PM_FLESH_GOLEM, PM_STONE_GOLEM, PM_GHOST, PM_MAIL_DAEMON,
    PM_LONG_WORM_TAIL,
)

from .monst_data import MONS, PM_NAMES, SUBSET_PM


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
    """The name of a monster type for a gender (C: monname).

    Single-name (NAM()) monsters store only the neutral name (the
    male/female slots are None); a request for male/female falls back
    to the neutral name, matching C (where NAM() sets all three slots
    to the same string)."""
    name = data.pmnames[mgender]
    if name is None:
        name = data.pmnames[2]  # NEUTRAL
    return name


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
    # the special section anchor (SPECIAL_PM is always implemented)
    worm_tail = MONS[SPECIAL_PM]
    assert worm_tail is not None
    assert worm_tail.mlet == S_WORM_TAIL
    assert worm_tail.pmnames[2] == "long worm tail"
    # adult dragon block: gray first, yellow last (defended() relies
    # on the range being 10 entries)
    assert PM_YELLOW_DRAGON - PM_GRAY_DRAGON + 1 == 10
    # every implemented monster has a name and a valid class, and
    # its fields fit the C field widths
    for idx in SUBSET_PM:
        m = MONS[idx]
        # SUBSET_PM is exactly the set of indices that carry a table
        # row (checked just above: present == set(SUBSET_PM)), so this
        # is never None; the assert narrows the sparse-table type.
        assert m is not None
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
    "S_LICH", "S_MUMMY", "S_NAGA", "S_OGRE", "S_PUDDING", "S_QUANTMECH",
    "S_RUSTMONST", "S_SNAKE", "S_TROLL", "S_UMBER", "S_VAMPIRE",
    "S_WRAITH", "S_XORN", "S_YETI", "S_ZOMBIE",
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
    "MZ_TINY", "MZ_SMALL", "MZ_MEDIUM", "MZ_HUMAN",
    "MZ_LARGE", "MZ_HUGE", "MZ_GIGANTIC",
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
