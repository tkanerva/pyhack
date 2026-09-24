"""Monster data accessors and per-game monster status (port of
src/mondata.c + include/mondata.h).

The pure permonst predicates (mondata.h macros) and the type-level
queries (attacktype, dmgtype, noattacks, zombie_form, genus, ...) take
a PerMonst from core.monst.  The per-game state lives in one
`MonState` object (C: svm -- struct monst_vars with the mvitals[]
array plus the global move counter), per the pyhack architecture of no
globals.

Dropped / deferred (documented, not bugs):

- name_to_mon / name_to_monplus / name_to_monclass: need the title
  system and the completed monster table; ported with cmd.c.
- same_race: needs big_to_little / little_to_big growth tables (mon.c).
- defended / Resists_Elem / resists_* / can_blnd / max_passive_dmg:
  need the object/equipment machinery (objects' oc_oprop, artifacts).
- can_blow / can_chant / can_be_strangled: need hero state (Strangled);
  the type-level halves are trivial and come with those systems.
- mstrength: developer-only (makedefs / #mondifficulty).
- The C sv* functions (svinit/svcount/svdestroyed/svflags/svflags_free)
  are not in 5.0's mondata.c (relocated); MonState implements the long
  standing sv* contract -- mvitals[mndx] with mvflags (G_KNOWN /
  G_GENOD / G_EXTINCT / MV_KNOWS_EGG), mvcount (living population) and
  mvlastseen (last move the type was seen).  A diff against the 5.0
  implementation in mon.c is due with the mon.c port.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .monst import (
    PerMonst, Attack, MONS, PM_NAMES, NUMMONS, SPECIAL_PM,
    G_KNOWN, G_GENOD, G_EXTINCT, G_GONE, MV_KNOWS_EGG,
    S_ANT, S_BLOB, S_COCKATRICE, S_DOG, S_EYE, S_FELINE, S_GREMLIN,
    S_HUMANOID, S_IMP, S_JELLY, S_KOBOLD, S_LEPRECHAUN, S_MIMIC,
    S_NYMPH, S_ORC, S_PIERCER, S_QUADRUPED, S_RODENT, S_SPIDER,
    S_TRAPPER, S_UNICORN, S_VORTEX, S_WORM, S_XAN, S_LIGHT, S_ZRUTY,
    S_ANGEL, S_BAT, S_CENTAUR, S_DRAGON, S_ELEMENTAL, S_FUNGUS,
    S_GNOME, S_GIANT, S_INVISIBLE, S_JABBERWOCK, S_KOP, S_LICH,
    S_MUMMY, S_NAGA, S_OGRE, S_PUDDING, S_QUANTMECH, S_RUSTMONST,
    S_SNAKE, S_TROLL, S_UMBER, S_VAMPIRE, S_WRAITH, S_XORN, S_YETI,
    S_ZOMBIE, S_HUMAN, S_GHOST, S_GOLEM, S_DEMON, S_EEL, S_LIZARD,
    S_WORM_TAIL, S_MIMIC_DEF, MAXMCLASSES,
    AT_ANY, AT_NONE, AT_CLAW, AT_BITE, AT_KICK, AT_BUTT, AT_TUCH,
    AT_STNG, AT_HUGS, AT_SPIT, AT_ENGL, AT_BREA, AT_EXPL, AT_BOOM,
    AT_GAZE, AT_TENT, AT_WEAP, AT_MAGC, NATTK, distance_atk_type,
    AD_ANY, AD_PHYS, AD_MAGM, AD_FIRE, AD_COLD, AD_SLEE, AD_DISN,
    AD_ELEC, AD_DRST, AD_ACID, AD_BLND, AD_STUN, AD_SLOW, AD_PLYS,
    AD_DRLI, AD_DREN, AD_LEGS, AD_STON, AD_STCK, AD_SGLD, AD_SITM,
    AD_SEDU, AD_TLPT, AD_RUST, AD_CONF, AD_DGST, AD_HEAL, AD_WRAP,
    AD_WERE, AD_DRDX, AD_DRCO, AD_DRIN, AD_DISE, AD_DCAY, AD_SSEX,
    AD_HALU, AD_DETH, AD_PEST, AD_FAMN, AD_SLIM, AD_ENCH, AD_CORR,
    AD_POLY, AD_CLRC, AD_SPEL, AD_RBRE, AD_SAMU, AD_CURS,
    M1_FLY, M1_SWIM, M1_AMORPHOUS, M1_WALLWALK, M1_CLING, M1_TUNNEL,
    M1_NEEDPICK, M1_CONCEAL, M1_HIDE, M1_AMPHIBIOUS, M1_BREATHLESS,
    M1_NOTAKE, M1_NOEYES, M1_NOHANDS, M1_NOLIMBS, M1_NOHEAD,
    M1_MINDLESS, M1_HUMANOID, M1_ANIMAL, M1_SLITHY, M1_UNSOLID,
    M1_THICK_HIDE, M1_OVIPAROUS, M1_REGEN, M1_SEE_INVIS, M1_TPORT,
    M1_TPORT_CNTRL, M1_ACID, M1_POIS, M1_CARNIVORE, M1_HERBIVORE,
    M1_OMNIVORE, M1_METALLIVORE,
    M2_NOPOLY, M2_UNDEAD, M2_WERE, M2_HUMAN, M2_ELF, M2_DWARF,
    M2_GNOME, M2_ORC, M2_DEMON, M2_MERC, M2_LORD, M2_PRINCE,
    M2_MINION, M2_GIANT, M2_SHAPESHIFTER, M2_MALE, M2_FEMALE,
    M2_NEUTER, M2_PNAME, M2_HOSTILE, M2_PEACEFUL, M2_DOMESTIC,
    M2_WANDER, M2_STALK, M2_NASTY, M2_STRONG, M2_ROCKTHROW,
    M2_GREEDY, M2_JEWELS, M2_COLLECT, M2_MAGIC,
    M3_WANTSAMUL, M3_WANTSBELL, M3_WANTSBOOK, M3_WANTSCAND,
    M3_WANTSARTI, M3_WANTSALL, M3_WAITFORU, M3_CLOSE, M3_COVETOUS,
    M3_WAITMASK, M3_INFRAVISION, M3_INFRAVISIBLE, M3_DISPLACES,
    MZ_SMALL, MZ_LARGE, MS_SILENT, MS_BUZZ, MS_BURBLE,
    monsndx, monclass, monname, is_golem, is_dragon,
)

# ------------------------------------------------------------
# PM_ anchors referenced by name-specific predicates below.  Resolved
# from PM_NAMES at import time so a renumbering would break loudly.
# ------------------------------------------------------------

def _pm(name: str) -> int:
    return PM_NAMES.index(name)

PM_AIR_ELEMENTAL = _pm("air elemental")
PM_BABY_GOLD_DRAGON = _pm("baby gold dragon")
PM_BABY_LONG_WORM = _pm("baby long worm")
PM_BABY_PURPLE_WORM = _pm("baby purple worm")
PM_BLACK_LIGHT = _pm("black light")
PM_BLACK_PUDDING = _pm("black pudding")
PM_BLACK_UNICORN = _pm("black unicorn")
PM_CHICKATRICE = _pm("chickatrice")
PM_CYCLOPS = _pm("Cyclops")
PM_DEATH = _pm("Death")
PM_DWARF = _pm("dwarf")
PM_ELF = _pm("elf")
PM_FAMINE = _pm("Famine")
PM_FIRE_ELEMENTAL = _pm("fire elemental")
PM_FIRE_VORTEX = _pm("fire vortex")
PM_FLAMING_SPHERE = _pm("flaming sphere")
PM_FLOATING_EYE = _pm("floating eye")
PM_GOLD_DRAGON = _pm("gold dragon")
PM_GOLD_GOLEM = _pm("gold golem")
PM_HORNED_DEVIL = _pm("horned devil")
PM_HUMAN = _pm("human")
PM_KI_RIN = _pm("ki-rin")
PM_LEATHER_GOLEM = _pm("leather golem")
PM_LONG_WORM = _pm("long worm")
PM_MASTER_MIND_FLAYER = _pm("master mind flayer")
PM_MEDUSA = _pm("Medusa")
PM_MIND_FLAYER = _pm("mind flayer")
PM_MINOTAUR = _pm("minotaur")
PM_MANES = _pm("manes")
PM_BALROG = _pm("balrog")
PM_ASMODEUS = _pm("Asmodeus")
PM_GREMLIN = _pm("gremlin")
PM_HORSE = _pm("horse")
PM_WARHORSE = _pm("warhorse")
PM_PONY = _pm("pony")
PM_PIRANHA = _pm("piranha")
PM_PURPLE_WORM = _pm("purple worm")
PM_ROCK_MOLE = _pm("rock mole")
PM_WOODCHUCK = _pm("woodchuck")
PM_RAVEN = _pm("raven")
PM_SALAMANDER = _pm("salamander")
PM_SHADE = _pm("shade")
PM_SHOCKING_SPHERE = _pm("shocking sphere")
PM_STALKER = _pm("stalker")
PM_STRAW_GOLEM = _pm("straw golem")
PM_PAPER_GOLEM = _pm("paper golem")
PM_WOOD_GOLEM = _pm("wood golem")
PM_IRON_GOLEM = _pm("iron golem")
PM_FLESH_GOLEM = _pm("flesh golem")
PM_GHOUL = _pm("ghoul")
PM_SKELETON = _pm("skeleton")
PM_TENGU = _pm("tengu")
PM_VAMPIRE_BAT = _pm("vampire bat")
PM_WHITE_UNICORN = _pm("white unicorn")
PM_GRAY_UNICORN = _pm("gray unicorn")
PM_GIANT = _pm("giant")
PM_ORC = _pm("orc")
PM_ETTIN = _pm("ettin")
PM_GNOME = _pm("gnome")
PM_KOBOLD = _pm("kobold")
PM_KOBOLD_ZOMBIE = _pm("kobold zombie")
PM_KOBOLD_MUMMY = _pm("kobold mummy")
PM_DWARF_ZOMBIE = _pm("dwarf zombie")
PM_DWARF_MUMMY = _pm("dwarf mummy")
PM_GNOME_ZOMBIE = _pm("gnome zombie")
PM_GNOME_MUMMY = _pm("gnome mummy")
PM_ORC_ZOMBIE = _pm("orc zombie")
PM_ORC_MUMMY = _pm("orc mummy")
PM_ELF_ZOMBIE = _pm("elf zombie")
PM_ELF_MUMMY = _pm("elf mummy")
PM_HUMAN_ZOMBIE = _pm("human zombie")
PM_HUMAN_MUMMY = _pm("human mummy")
PM_ETTIN_ZOMBIE = _pm("ettin zombie")
PM_ETTIN_MUMMY = _pm("ettin mummy")
PM_GIANT_ZOMBIE = _pm("giant zombie")
PM_GIANT_MUMMY = _pm("giant mummy")
PM_WATCHMAN = _pm("watchman")
PM_WATCH_CAPTAIN = _pm("watch captain")
PM_ARCHEOLOGIST = _pm("archeologist")
PM_WIZARD = _pm("wizard")
PM_BAT = _pm("bat")
PM_GIANT_BAT = _pm("giant bat")
PM_VAMPIRE = _pm("vampire")
PM_VAMPIRE_LEADER = _pm("vampire leader")


def mons(pm: int) -> Optional[PerMonst]:
    """mons[pm] (C: mons[] array; None for not-yet-implemented types)."""
    return MONS[pm]


# ------------------------------------------------------------
# Per-game monster status (C: svm / struct monst_vars, sv* contract)
# ------------------------------------------------------------

@dataclass
class MonVitals:
    """One type's population state (C: struct mvitals)."""
    mvflags: int = 0
    mvcount: int = 0
    mvlastseen: int = 0


class MonState:
    """C: svm -- per-game monster type status + the move counter."""

    def __init__(self) -> None:
        self.mvitals: list[MonVitals] = [MonVitals() for _ in range(NUMMONS)]
        self.moves: int = 0

    # C: svinit
    def svinit(self) -> None:
        self.mvitals = [MonVitals() for _ in range(NUMMONS)]

    # C: svcount
    def svcount(self, pm: int, delta: int) -> None:
        if pm > SPECIAL_PM:
            return
        v = self.mvitals[pm]
        v.mvcount += delta
        v.mvlastseen = self.moves
        if delta < 0:
            if v.mvcount < 0:
                raise ValueError(f"svcount went negative on {pm}")
            if v.mvcount == 0 and v.mvflags & G_KNOWN:
                v.mvflags |= G_EXTINCT  # population control: no more

    # C: svdestroyed (last of the type died)
    def svdestroyed(self, pm: int) -> None:
        if pm > SPECIAL_PM:
            return
        self.mvitals[pm].mvflags |= G_EXTINCT

    # C: svflags
    def svflags(self, pm: int, flags: int, add: bool) -> None:
        if add:
            self.mvitals[pm].mvflags |= flags
        else:
            self.mvitals[pm].mvflags &= ~flags

    # C: svflags_free
    def svflags_free(self, pm: int, flags: int) -> None:
        self.svflags(pm, flags, False)


# ------------------------------------------------------------
# set_mon_data (C: set_mon_data)
# ------------------------------------------------------------

def set_mon_data(mon, data: PerMonst, movement: int) -> int:
    """Set a monster's base type (initial creation, shapechange) and
    prorate its unused movement if the new form is slower (C:
    set_mon_data).

    `mon` is duck-typed: it gets `.mdata` (PerMonst) and `.mnum`
    (mons index) attributes.  Returns the movement points to store
    (mon.movement / u.umovement).
    """
    old_speed = mon.mdata.mmove if getattr(mon, "mdata", None) is not None \
        else 0
    new_speed = data.mmove
    if movement:
        if new_speed < old_speed:
            # prorate unused movement if new form is slower so that it
            # doesn't get extra moves leftover from the previous form;
            # if the new form is faster, leave unused movement as is
            movement = movement * new_speed
            if old_speed > 0:
                movement //= old_speed
    mon.mdata = data
    mon.mnum = monsndx(data)
    return movement


# ------------------------------------------------------------
# Attack/damage queries (C: mondata.c)
# ------------------------------------------------------------

def attacktype_fordmg(ptr: PerMonst, atyp: int, dtyp: int) -> Optional[Attack]:
    """The first attack of type `atyp` doing damage `dtyp`, or None
    (C: attacktype_fordmg)."""
    for a in ptr.mattk:
        if a.aatyp == atyp and (dtyp == AD_ANY or a.adtyp == dtyp):
            return a
    return None


def attacktype(ptr: PerMonst, atyp: int) -> bool:
    return attacktype_fordmg(ptr, atyp, AD_ANY) is not None


def dmgtype_fromattack(ptr: PerMonst, dtyp: int, atyp: int) -> Optional[Attack]:
    """The first attack of type `atyp` doing damage `dtyp`, or None
    (C: dmgtype_fromattack)."""
    for a in ptr.mattk:
        if a.adtyp == dtyp and (atyp == AT_ANY or a.aatyp == atyp):
            return a
    return None


def dmgtype(ptr: PerMonst, dtyp: int) -> bool:
    return dmgtype_fromattack(ptr, dtyp, AT_ANY) is not None


def noattacks(ptr: PerMonst) -> bool:
    """True if the monster has no attacks (C: noattacks).  AT_BOOM
    (passive death explosion) doesn't count."""
    for a in ptr.mattk:
        if a.aatyp == AT_BOOM:
            continue
        if a.aatyp:
            return False
    return True


def ranged_attk(ptr: PerMonst) -> bool:
    """True if the monster can attack at range (C: ranged_attk)."""
    return any(distance_atk_type(a.aatyp) for a in ptr.mattk)


def sticks(ptr: PerMonst) -> bool:
    """The creature sticks other creatures it hits (C: sticks)."""
    return (dmgtype(ptr, AD_STCK)
            or (dmgtype(ptr, AD_WRAP) and not attacktype(ptr, AT_ENGL))
            or attacktype(ptr, AT_HUGS))


def is_armed(ptr: PerMonst) -> bool:
    return attacktype(ptr, AT_WEAP)


def can_breathe(ptr: PerMonst) -> bool:
    return attacktype(ptr, AT_BREA)


def could_twoweap(ptr: PerMonst) -> bool:
    """Multiple weapon attacks -> two-weapon combat (C: could_twoweap)."""
    n = sum(1 for a in ptr.mattk[:3] if a.aatyp == AT_WEAP)
    return n > 1


# ------------------------------------------------------------
# mondata.h predicates (pure functions of a PerMonst)
# ------------------------------------------------------------

def verysmall(ptr: PerMonst) -> bool:
    return ptr.msize < MZ_SMALL


def bigmonst(ptr: PerMonst) -> bool:
    return ptr.msize >= MZ_LARGE


def pm_resistance(ptr: PerMonst, typ: int) -> bool:
    return bool(ptr.mresists & typ)


def is_flyer(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_FLY)


def is_floater(ptr: PerMonst) -> bool:
    return ptr.mlet in (S_EYE, S_LIGHT)


def is_clinger(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_CLING)


def grounded(ptr: PerMonst, has_ceiling: bool) -> bool:
    """C: grounded -- the level-ceiling bit is an explicit parameter."""
    return (not is_flyer(ptr) and not is_floater(ptr)
            and (not is_clinger(ptr) or not has_ceiling))


def is_swimmer(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_SWIM)


def breathless(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_BREATHLESS)


def amphibious(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_AMPHIBIOUS)


def cant_drown(ptr: PerMonst) -> bool:
    return is_swimmer(ptr) or amphibious(ptr) or breathless(ptr)


def passes_walls(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_WALLWALK)


def amorphous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_AMORPHOUS)


def noncorporeal(ptr: PerMonst) -> bool:
    return ptr.mlet == S_GHOST


def tunnels(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_TUNNEL)


def needspick(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_NEEDPICK)


def hides_under(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_CONCEAL)


def is_hider(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_HIDE)


def ceiling_hider(ptr: PerMonst) -> bool:
    return (is_hider(ptr)
            and ((is_clinger(ptr) and ptr.mlet != S_MIMIC)
                 or is_flyer(ptr)))


def haseyes(ptr: PerMonst) -> bool:
    return not (ptr.mflags1 & M1_NOEYES)


def eyecount(ptr: PerMonst) -> int:
    if not haseyes(ptr):
        return 0
    if ptr.pmidx in (PM_CYCLOPS, PM_FLOATING_EYE):
        return 1
    return 2


def nohands(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_NOHANDS)


def nolimbs(ptr: PerMonst) -> bool:
    return (ptr.mflags1 & M1_NOLIMBS) == M1_NOLIMBS


def notake(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_NOTAKE)


def has_head(ptr: PerMonst) -> bool:
    return not (ptr.mflags1 & M1_NOHEAD)


def has_horns(ptr: PerMonst) -> bool:
    return num_horns(ptr) > 0


def is_whirly(ptr: PerMonst) -> bool:
    return ptr.mlet == S_VORTEX or ptr.pmidx == PM_AIR_ELEMENTAL


def flaming(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_FIRE_VORTEX, PM_FLAMING_SPHERE,
                         PM_FIRE_ELEMENTAL, PM_SALAMANDER)


def is_silent(ptr: PerMonst) -> bool:
    return ptr.msound == MS_SILENT


def unsolid(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_UNSOLID)


def mindless(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_MINDLESS)


def humanoid(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_HUMANOID)


def is_animal(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_ANIMAL)


def slithy(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_SLITHY)


def is_wooden(ptr: PerMonst) -> bool:
    return ptr.pmidx == PM_WOOD_GOLEM


def thick_skinned(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_THICK_HIDE)


def hug_throttles(ptr: PerMonst) -> bool:
    # rope golem
    return ptr.pmidx == _pm("rope golem")


def digests(ptr: PerMonst) -> bool:
    return dmgtype_fromattack(ptr, AD_DGST, AT_ENGL) is not None


def enfolds(ptr: PerMonst) -> bool:
    return dmgtype_fromattack(ptr, AD_WRAP, AT_ENGL) is not None


def slimeproof(ptr: PerMonst) -> bool:
    return (ptr.pmidx == _pm("green slime") or flaming(ptr)
            or noncorporeal(ptr))


def lays_eggs(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_OVIPAROUS)


def eggs_in_water(ptr: PerMonst) -> bool:
    return lays_eggs(ptr) and ptr.mlet == S_EEL and is_swimmer(ptr)


def regenerates(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_REGEN)


def perceives(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_SEE_INVIS)


def can_teleport(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_TPORT)


def control_teleport(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_TPORT_CNTRL)


def telepathic(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_FLOATING_EYE, PM_MIND_FLAYER,
                         PM_MASTER_MIND_FLAYER)


def acidic(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_ACID)


def poisonous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_POIS)


def carnivorous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_CARNIVORE)


def herbivorous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_HERBIVORE)


def metallivorous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags1 & M1_METALLIVORE)


def polyok(ptr: PerMonst) -> bool:
    return not (ptr.mflags2 & M2_NOPOLY)


def is_shapeshifter(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_SHAPESHIFTER)


def is_undead(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_UNDEAD)


def is_were(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_WERE)


def is_elf(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_ELF)


def is_dwarf(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_DWARF)


def is_gnome(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_GNOME)


def is_orc(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_ORC)


def is_human(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_HUMAN)


def is_bat(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_BAT, PM_GIANT_BAT, PM_VAMPIRE_BAT)


def is_bird(ptr: PerMonst) -> bool:
    return ptr.mlet == S_BAT and not is_bat(ptr)


def is_giant(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_GIANT)


def is_domestic(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_DOMESTIC)


def is_demon(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_DEMON)


def is_mercenary(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_MERC)


def is_male(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_MALE)


def is_female(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_FEMALE)


def is_neuter(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_NEUTER)


def is_wanderer(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_WANDER)


def always_hostile(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_HOSTILE)


def always_peaceful(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_PEACEFUL)


def extra_nasty(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_NASTY)


def strongmonst(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_STRONG)


def cantwield(ptr: PerMonst) -> bool:
    return nohands(ptr) or verysmall(ptr)


def sliparm(ptr: PerMonst) -> bool:
    return is_whirly(ptr) or ptr.msize <= MZ_SMALL or noncorporeal(ptr)


def breakarm(ptr: PerMonst) -> bool:
    if sliparm(ptr):
        return False
    return (bigmonst(ptr)
            or (ptr.msize > MZ_SMALL and not humanoid(ptr))
            or ptr.pmidx == _pm("marilith")
            or ptr.pmidx == _pm("winged gargoyle"))


def cantweararm(ptr: PerMonst) -> bool:
    return breakarm(ptr) or sliparm(ptr)


def throws_rocks(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_ROCKTHROW)


def type_is_pname(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_PNAME)


def is_lord(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_LORD)


def is_prince(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_PRINCE)


def is_ndemon(ptr: PerMonst) -> bool:
    return is_demon(ptr) and not (ptr.mflags2 & (M2_LORD | M2_PRINCE))


def is_dlord(ptr: PerMonst) -> bool:
    return is_demon(ptr) and is_lord(ptr)


def is_dprince(ptr: PerMonst) -> bool:
    return is_demon(ptr) and is_prince(ptr)


def is_minion(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_MINION)


def likes_gold(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_GREEDY)


def likes_gems(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_JEWELS)


def likes_objs(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_COLLECT) or is_armed(ptr)


def likes_magic(ptr: PerMonst) -> bool:
    return bool(ptr.mflags2 & M2_MAGIC)


def webmaker(ptr: PerMonst) -> bool:
    return ptr.pmidx in (_pm("cave spider"), _pm("giant spider"))


def is_unicorn(ptr: PerMonst) -> bool:
    return ptr.mlet == S_UNICORN and likes_gems(ptr)


def is_longworm(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_BABY_LONG_WORM, PM_LONG_WORM,
                         _pm("long worm tail"))


def is_covetous(ptr: PerMonst) -> bool:
    return bool(ptr.mflags3 & M3_COVETOUS)


def infravision(ptr: PerMonst) -> bool:
    return bool(ptr.mflags3 & M3_INFRAVISION)


def infravisible(ptr: PerMonst) -> bool:
    return bool(ptr.mflags3 & M3_INFRAVISIBLE)


def is_displacer(ptr: PerMonst) -> bool:
    return bool(ptr.mflags3 & M3_DISPLACES)


def is_mplayer(ptr: PerMonst) -> bool:
    return PM_ARCHEOLOGIST <= ptr.pmidx <= PM_WIZARD


def is_watch(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_WATCHMAN, PM_WATCH_CAPTAIN)


def is_rider(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_DEATH, PM_FAMINE, PM_PESTILENCE)


def is_placeholder(ptr: PerMonst) -> bool:
    """Placeholder monsters used for corpses of zombies/mummies."""
    return ptr.pmidx in (PM_ORC, PM_GIANT, PM_ELF, PM_HUMAN)


def is_reviver(ptr: PerMonst) -> bool:
    return is_rider(ptr) or ptr.mlet == S_TROLL


def unique_corpstat(ptr: PerMonst) -> bool:
    return bool(ptr.geno & 0x1000)  # G_UNIQ


def emits_light(ptr: PerMonst) -> int:
    """Light range (1) or 0 (C: emits_light)."""
    if (ptr.mlet == S_LIGHT
            or ptr.pmidx in (PM_FLAMING_SPHERE, PM_SHOCKING_SPHERE,
                             PM_BABY_GOLD_DRAGON, PM_FIRE_VORTEX)):
        return 1
    if ptr.pmidx in (PM_FIRE_ELEMENTAL, PM_GOLD_DRAGON):
        return 1
    return 0


def pm_invisible(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_STALKER, PM_BLACK_LIGHT)


def likes_lava(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_FIRE_ELEMENTAL, PM_SALAMANDER)


def likes_fire(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_FIRE_VORTEX, PM_FLAMING_SPHERE) or likes_lava(ptr)


PM_COCKATRICE = _pm("cockatrice")


def touch_petrifies(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_COCKATRICE, PM_CHICKATRICE)


def flesh_petrifies(ptr: PerMonst) -> bool:
    """Medusa doesn't pass touch_petrifies() but petrifies if eaten."""
    return touch_petrifies(ptr) or ptr.pmidx == PM_MEDUSA


def passes_rocks(ptr: PerMonst) -> bool:
    return passes_walls(ptr) and not unsolid(ptr)


def is_mind_flayer(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_MIND_FLAYER, PM_MASTER_MIND_FLAYER)


def is_vampire(ptr: PerMonst) -> bool:
    return ptr.mlet == S_VAMPIRE


def hates_light(ptr: PerMonst) -> bool:
    return ptr.pmidx == PM_GREMLIN


def weirdnonliving(ptr: PerMonst) -> bool:
    return is_golem(ptr) or ptr.mlet == S_VORTEX


def nonliving(ptr: PerMonst) -> bool:
    return is_undead(ptr) or ptr.pmidx == PM_MANES or weirdnonliving(ptr)


def completelyburns(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_PAPER_GOLEM, PM_STRAW_GOLEM)


def completelyrots(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_WOOD_GOLEM, PM_LEATHER_GOLEM)


def completelyrusts(ptr: PerMonst) -> bool:
    return ptr.pmidx == PM_IRON_GOLEM


def vegan(ptr: PerMonst) -> bool:
    if ptr.mlet in (S_BLOB, S_JELLY, S_FUNGUS, S_VORTEX, S_LIGHT):
        return True
    if ptr.mlet == S_ELEMENTAL and ptr.pmidx != PM_STALKER:
        return True
    if (ptr.mlet == S_GOLEM
            and ptr.pmidx not in (PM_FLESH_GOLEM, PM_LEATHER_GOLEM)):
        return True
    return noncorporeal(ptr)


def vegetarian(ptr: PerMonst) -> bool:
    return vegan(ptr) or (ptr.mlet == S_PUDDING
                          and ptr.pmidx != PM_BLACK_PUDDING)


def corpse_eater(ptr: PerMonst) -> bool:
    return ptr.pmidx in (PM_PURPLE_WORM, PM_BABY_PURPLE_WORM,
                         PM_GHOUL, PM_PIRANHA)


def cantvomit(ptr: PerMonst) -> bool:
    if ptr.mlet == S_RODENT and ptr.pmidx not in (PM_ROCK_MOLE, PM_WOODCHUCK):
        return True
    return ptr.pmidx in (PM_WARHORSE, PM_HORSE, PM_PONY)


def num_horns(ptr: PerMonst) -> int:
    if ptr.pmidx in (PM_HORNED_DEVIL, PM_MINOTAUR, PM_ASMODEUS, PM_BALROG):
        return 2
    if ptr.pmidx in (PM_WHITE_UNICORN, PM_GRAY_UNICORN, PM_BLACK_UNICORN,
                     PM_KI_RIN):
        return 1
    return 0


def hates_silver(ptr: PerMonst) -> bool:
    return (is_were(ptr) or ptr.mlet == S_VAMPIRE or is_demon(ptr)
            or ptr.pmidx == PM_SHADE
            or (ptr.mlet == S_IMP and ptr.pmidx != PM_TENGU))


def hates_blessings(ptr: PerMonst) -> bool:
    return is_undead(ptr) or is_demon(ptr)


def passes_bars(ptr: PerMonst) -> bool:
    return (passes_walls(ptr) or amorphous(ptr) or unsolid(ptr)
            or is_whirly(ptr) or verysmall(ptr)
            or dmgtype(ptr, AD_RUST) or dmgtype(ptr, AD_CORR)
            or metallivorous(ptr)
            or (slithy(ptr) and not bigmonst(ptr)))


def olfaction(ptr: PerMonst) -> bool:
    """Presumed sense of smell (C: olfaction)."""
    if (is_golem(ptr) or ptr.mlet in (S_EYE, S_JELLY, S_BLOB, S_VORTEX,
                                      S_ELEMENTAL, S_FUNGUS, S_LIGHT)):
        return False
    return True


# ------------------------------------------------------------
# Zombie/undead type mapping (C: zombie_maker, zombie_form,
# undead_to_corpse, genus, pm_to_cham)
# ------------------------------------------------------------

def zombie_maker(mon) -> bool:
    """True if mon can turn others into zombies (C: zombie_maker)."""
    pm = mon.mdata
    if getattr(mon, "mcan", 0):
        return False
    if pm.mlet == S_ZOMBIE:
        # Z-class monsters that aren't actually zombies go here
        if pm.pmidx in (PM_GHOUL, PM_SKELETON):
            return False
        return True
    if pm.mlet == S_LICH:
        return True
    return False


def zombie_form(pm: PerMonst) -> int:
    """Zombie counterpart of pm, or -1 (NON_PM) (C: zombie_form)."""
    if pm.mlet == S_ZOMBIE:
        return -1  # already a zombie/ghoul/skeleton: stays as is
    if pm.mlet == S_KOBOLD:
        return PM_KOBOLD_ZOMBIE
    if pm.mlet == S_ORC:
        return PM_ORC_ZOMBIE
    if pm.mlet == S_GIANT:
        if pm.pmidx == PM_ETTIN:
            return PM_ETTIN_ZOMBIE
        return PM_GIANT_ZOMBIE
    if pm.mlet in (S_HUMAN, S_KOP):
        if is_elf(pm):
            return PM_ELF_ZOMBIE
        return PM_HUMAN_ZOMBIE
    if pm.mlet == S_HUMANOID:
        if is_dwarf(pm):
            return PM_DWARF_ZOMBIE
        return -1
    if pm.mlet == S_GNOME:
        return PM_GNOME_ZOMBIE
    return -1


def undead_to_corpse(mndx: int) -> int:
    """Living counterpart of an undead (C: undead_to_corpse)."""
    mapping = {
        PM_KOBOLD_ZOMBIE: PM_KOBOLD, PM_KOBOLD_MUMMY: PM_KOBOLD,
        PM_DWARF_ZOMBIE: PM_DWARF, PM_DWARF_MUMMY: PM_DWARF,
        PM_GNOME_ZOMBIE: PM_GNOME, PM_GNOME_MUMMY: PM_GNOME,
        PM_ORC_ZOMBIE: PM_ORC, PM_ORC_MUMMY: PM_ORC,
        PM_ELF_ZOMBIE: PM_ELF, PM_ELF_MUMMY: PM_ELF,
        PM_VAMPIRE: PM_HUMAN, PM_VAMPIRE_LEADER: PM_HUMAN,
        PM_HUMAN_ZOMBIE: PM_HUMAN,
        PM_HUMAN_MUMMY: PM_HUMAN,
        PM_GIANT_ZOMBIE: PM_GIANT, PM_GIANT_MUMMY: PM_GIANT,
        PM_ETTIN_ZOMBIE: PM_ETTIN, PM_ETTIN_MUMMY: PM_ETTIN,
    }
    return mapping.get(mndx, mndx)


def genus(mndx: int, mode: int = 0) -> int:
    """Quest guardians -> their generic species (C: genus).

    mode 1: return the character-class monster instead of the species.
    """
    if mndx in _GENUS_MAP:
        species, player = _GENUS_MAP[mndx]
        return player if mode else species
    if 0 <= mndx < NUMMONS:
        ptr = MONS[mndx]
        if ptr is not None:
            if is_human(ptr):
                return PM_HUMAN
            if is_elf(ptr):
                return PM_ELF
            if is_dwarf(ptr):
                return PM_DWARF
            if is_gnome(ptr):
                return PM_GNOME
            if is_orc(ptr):
                return PM_ORC
    return mndx


# quest guardian -> (species, player-class monster) (C: genus)
_GENUS_MAP = {
    _pm("student"): (PM_HUMAN, PM_ARCHEOLOGIST),
    _pm("chieftain"): (PM_HUMAN, _pm("barbarian")),
    _pm("neanderthal"): (PM_HUMAN, _pm("cave dweller")),
    _pm("attendant"): (PM_HUMAN, _pm("healer")),
    _pm("page"): (PM_HUMAN, _pm("knight")),
    _pm("abbot"): (PM_HUMAN, _pm("monk")),
    _pm("acolyte"): (PM_HUMAN, _pm("cleric")),
    _pm("hunter"): (PM_HUMAN, _pm("ranger")),
    _pm("thug"): (PM_HUMAN, _pm("rogue")),
    _pm("roshi"): (PM_HUMAN, _pm("samurai")),
    _pm("guide"): (PM_HUMAN, _pm("tourist")),
    _pm("apprentice"): (PM_HUMAN, PM_WIZARD),
    _pm("warrior"): (PM_HUMAN, _pm("valkyrie")),
}


def pm_to_cham(mndx: int) -> int:
    """mndx if chameleon (shapeshifter), else -1 (C: pm_to_cham)."""
    if 0 <= mndx < NUMMONS:
        ptr = MONS[mndx]
        if ptr is not None and is_shapeshifter(ptr):
            return mndx
    return -1


# ------------------------------------------------------------
# Resistances seen by monsters (C: M_SEEN_*, cvt_*, monstseesu)
# ------------------------------------------------------------

M_SEEN_NOTHING = 0x0000
M_SEEN_MAGR = 0x0001
M_SEEN_FIRE = 0x0002
M_SEEN_COLD = 0x0004
M_SEEN_SLEEP = 0x0008
M_SEEN_DISINT = 0x0010
M_SEEN_ELEC = 0x0020
M_SEEN_POISON = 0x0040
M_SEEN_ACID = 0x0080
M_SEEN_REFL = 0x0100


def cvt_adtyp_to_mseenres(adtyp: int) -> int:
    table = {
        AD_MAGM: M_SEEN_MAGR, AD_FIRE: M_SEEN_FIRE, AD_COLD: M_SEEN_COLD,
        AD_SLEE: M_SEEN_SLEEP, AD_DISN: M_SEEN_DISINT,
        AD_ELEC: M_SEEN_ELEC, AD_DRST: M_SEEN_POISON,
        AD_ACID: M_SEEN_ACID,
    }
    return table.get(adtyp, M_SEEN_NOTHING)


def cvt_prop_to_mseenres(prop: int) -> int:
    table = {
        1: M_SEEN_MAGR,    # ANTIMAGIC
        2: M_SEEN_FIRE,    # FIRE_RES
        3: M_SEEN_COLD,    # COLD_RES
        4: M_SEEN_SLEEP,   # SLEEP_RES
        5: M_SEEN_DISINT,  # DISINT_RES
        6: M_SEEN_POISON,  # POISON_RES
        7: M_SEEN_ELEC,    # SHOCK_RES
        8: M_SEEN_ACID,    # ACID_RES
        9: M_SEEN_REFL,    # REFLECTING
    }
    return table.get(prop, M_SEEN_NOTHING)


# ------------------------------------------------------------
# Trap knowledge (C: mon_knows_traps / mon_learns_traps) -- pure over
# the monster's mtrapseen bitmap.
# ------------------------------------------------------------

NO_TRAP = 0
ALL_TRAPS = -1


def mon_knows_traps(mon, ttyp: int) -> bool:
    if ttyp == ALL_TRAPS:
        return bool(mon.mtrapseen)
    if ttyp == NO_TRAP:
        return not mon.mtrapseen
    return bool(mon.mtrapseen & (1 << (ttyp - 1)))


def mon_learns_traps(mon, ttyp: int) -> None:
    if ttyp == ALL_TRAPS:
        mon.mtrapseen = ~0
    elif ttyp == NO_TRAP:
        mon.mtrapseen = 0
    else:
        mon.mtrapseen |= (1 << (ttyp - 1))


# ------------------------------------------------------------
# Breath damage randomization (C: get_atkdam_type)
# ------------------------------------------------------------

_RND_BREATH_TYP = (AD_MAGM, AD_FIRE, AD_COLD, AD_SLEE,
                   AD_DISN, AD_ELEC, AD_DRST, AD_ACID)


def get_atkdam_type(adtyp: int, rng) -> int:
    """AD_RBRE rolls one of the real breath types (C: get_atkdam_type)."""
    if adtyp == AD_RBRE:
        return _RND_BREATH_TYP[rng.rn2(len(_RND_BREATH_TYP))]
    return adtyp


# ------------------------------------------------------------
# poly_when_stoned (C: poly_when_stoned)
# ------------------------------------------------------------

def poly_when_stoned(ptr: PerMonst, state: MonState) -> bool:
    """Non-stone golems turn into stone golems unless the latter are
    genocided (C: poly_when_stoned)."""
    return (is_golem(ptr) and ptr.pmidx != _pm("stone golem")
            and not (state.mvitals[_pm("stone golem")].mvflags & G_GENOD))


__all__ = [
    "MonVitals", "MonState", "mons", "set_mon_data",
    "attacktype_fordmg", "attacktype", "dmgtype_fromattack", "dmgtype",
    "noattacks", "ranged_attk", "sticks", "is_armed", "can_breathe",
    "could_twoweap",
    "verysmall", "bigmonst", "pm_resistance",
    "is_flyer", "is_floater", "is_clinger", "grounded", "is_swimmer",
    "breathless", "amphibious", "cant_drown", "passes_walls", "amorphous",
    "noncorporeal", "tunnels", "needspick", "hides_under", "is_hider",
    "ceiling_hider", "haseyes", "eyecount", "nohands", "nolimbs", "notake",
    "has_head", "has_horns", "is_whirly", "flaming", "is_silent", "unsolid",
    "mindless", "humanoid", "is_animal", "slithy", "is_wooden",
    "thick_skinned", "hug_throttles", "digests", "enfolds", "slimeproof",
    "lays_eggs", "eggs_in_water", "regenerates", "perceives",
    "can_teleport", "control_teleport", "telepathic", "acidic",
    "poisonous", "carnivorous", "herbivorous", "metallivorous", "polyok",
    "is_shapeshifter", "is_undead", "is_were", "is_elf", "is_dwarf",
    "is_gnome", "is_orc", "is_human", "is_bat", "is_bird", "is_giant",
    "is_domestic", "is_demon", "is_mercenary", "is_male", "is_female",
    "is_neuter", "is_wanderer", "always_hostile", "always_peaceful",
    "extra_nasty", "strongmonst", "cantwield", "sliparm", "breakarm",
    "cantweararm", "throws_rocks", "type_is_pname", "is_lord", "is_prince",
    "is_ndemon", "is_dlord", "is_dprince", "is_minion", "likes_gold",
    "likes_gems", "likes_objs", "likes_magic", "webmaker", "is_unicorn",
    "is_longworm", "is_covetous", "infravision", "infravisible",
    "is_displacer", "is_mplayer", "is_watch", "is_rider",
    "is_placeholder", "is_reviver", "unique_corpstat", "emits_light",
    "pm_invisible", "likes_lava", "likes_fire", "touch_petrifies",
    "flesh_petrifies", "passes_rocks", "is_mind_flayer", "is_vampire",
    "hates_light", "weirdnonliving", "nonliving", "completelyburns",
    "completelyrots", "completelyrusts", "vegan", "vegetarian",
    "corpse_eater", "cantvomit", "num_horns", "hates_silver",
    "hates_blessings", "passes_bars", "olfaction",
    "zombie_maker", "zombie_form", "undead_to_corpse", "genus",
    "pm_to_cham",
    "M_SEEN_NOTHING", "M_SEEN_MAGR", "M_SEEN_FIRE", "M_SEEN_COLD",
    "M_SEEN_SLEEP", "M_SEEN_DISINT", "M_SEEN_ELEC", "M_SEEN_POISON",
    "M_SEEN_ACID", "M_SEEN_REFL",
    "cvt_adtyp_to_mseenres", "cvt_prop_to_mseenres",
    "NO_TRAP", "ALL_TRAPS", "mon_knows_traps", "mon_learns_traps",
    "get_atkdam_type", "poly_when_stoned",
]
