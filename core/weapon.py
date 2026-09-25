"""Weapon hit/damage bonuses, weapon predicates, and the weapon-skill
system (port of src/weapon.c + include/skills.h + the weapon macros of
include/obj.h + include/objclass.h + include/weight.h + include/attrib.h).

Per the subset-first policy this implements the whole HERO side of
weapon.c (what the player's attacks and the skill system need) plus the
weapon-type predicates and the monster weapon preference tables.  The
functions that need machinery not yet ported are stubs that raise
NotImplementedError (marked STUB), so the C file's API surface is
visible and the fill-in replaces a stub rather than a call site.

Included:

- the skills.h constants (skill levels, ranges, the practice curve,
  P_SKILL_LIMIT) on top of the Skill enum from core.objects;
- `Skills` -- the per-game hero skill state (C: u.weapon_skills[] plus
  u.weapon_slots / u.skills_advanced / u.skill_record); one object, no
  globals (the MonState/ObjTables pattern);
- the obj.h weapon predicates as functions over a duck-typed object
  (ObjLike): weapon_type, is_ammo, is_launcher, is_weptool, is_blade,
  is_sword, is_axe, is_pick, is_spear, is_pole, is_missile, is_multigen,
  is_blunt_weapon, is_wet_towel, is_graystone, is_poisonable, bimanual,
  matching_launcher, ammo_and_launcher, greatest_erosion;
- hitval() and dmgval().  Written per the architecture decision: C's
  15-case extra-damage switch is two auditable otyp tables
  (_DMG_EXTRA_LARGE / _DMG_EXTRA_SMALL with a roll spec), and the
  independent "weapon vs. monster" bonuses are an ordered list of named
  source functions that the caller SUMS (all sources may fire; the C
  ifs are independent, and the list order is the RNG draw order);
- the skill system: skill_name / skill_level_name / weapon_descr,
  slots_required, can_advance, could_advance, peaked_skill,
  advance_skill, use_skill, add_weapon_skill, lose_weapon_skill,
  drain_weapon_skill, unrestrict_weapon_skill, skill_init;
- weapon_hit_bonus / weapon_dam_bonus / uwep_skill_type (the level
  switches are dicts keyed by skill level);
- abon() / dbon() (C 5.0: STR18(x) == 18 + x, i.e. 18/50 is stored as
  68; the effective ability values are explicit parameters, as with
  rnd.rnl/rne);
- towels: wet_a_towel / dry_a_towel;
- the monster weapon preference tables RWERP / PWERP / HWEP / ARWEP
  (data for the mon.c port) with autoreturn_weapon() and
  monmightthrowwep(), plus the weapon_check state constants.

5.0 note (observed, not a bug): the 5.0 WEPTOOL macro puts the strike
mode (WHACK/PIERCE) in the oc_hitbon slot, so a wielded pick-axe or
grappling hook adds WHACK (4) to hit and a unicorn horn adds PIERCE (1)
in hitval().  The 3.6 table had 0 there; the port follows 5.0.

STUBs (raise NotImplementedError; filled by the named port):

- the artifact-dependent parts of hitval/dmgval: spec_abon / spec_dbon /
  artifact_light / shade_glare (artifact.c);
- select_rwep / select_hwep / possibly_unwield / mon_wield_item /
  mwepgone / setmnotwielded: need the per-instance monster model
  (minvent, mw, weapon_check, misc_worn_check, LOS) -- mon.c;
- special_dmgval / silver_sears: need the hero equipment (which_armor,
  uleft/uright) -- do_wear.c / worn.c;
- add_skills_to_menu / show_skills / enhance_weapon_skill: need the
  menu system -- cmd.c;
- the skill_based_spellbook_id() calls: books -- read.c / spell.c;
- the handle_tip(TIP_ENHANCE) call: tips -- cmd.c;
- the gu.unweapon / update_inventory() hooks in the towel change:
  do_wear.c / invent.c / objnam.c.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Protocol, Set, Tuple

from .hacklib import makesingular
from .mondata import (bigmonst, hates_blessings, hates_silver, is_swimmer,
                      is_wooden, passes_walls, thick_skinned)
from .monst import (MAXMCLASSES, PM_NAMES, PerMonst,
                    S_DRAGON, S_EEL, S_GIANT, S_JABBERWOCK, S_NAGA,
                    S_SNAKE, S_XORN)
from .objects import (Material, NUM_OBJECTS, ObjClass, OBJECTS, ObjType,
                      P_NUM_SKILLS, PIERCE, Skill, WHACK)

O = ObjType  # short alias for table lookups


# ------------------------------------------------------------
# Structural shapes (the "traits" of the port: named, checkable, no
# inheritance -- see ARCHITECTURE.md)
# ------------------------------------------------------------

class ObjLike(Protocol):
    """The shape of an object instance as far as weapon.c cares
    (C: struct obj).  The real instance model arrives with the mkobj.c
    port; until then callers pass small stand-ins with these
    attributes.  Optional instance attributes (owt, oeroded, oeroded2,
    globby) are read via getattr with C's zero defaults."""
    otyp: int
    oclass: int
    spe: int
    blessed: bool


class MonLike(Protocol):
    """A monster instance as far as hitval()/dmgval() care (C:
    struct monst): it needs its base type (C: mon->data)."""
    mdata: PerMonst


# ------------------------------------------------------------
# Skill levels and the practice curve (skills.h)
# ------------------------------------------------------------

P_ISRESTRICTED = 0
P_UNSKILLED = 1
P_BASIC = 2
P_SKILLED = 3
P_EXPERT = 4
P_MASTER = 5          # unarmed combat / martial arts only
P_GRAND_MASTER = 6    # ditto

P_FIRST_WEAPON = int(Skill.P_DAGGER)
P_LAST_WEAPON = int(Skill.P_UNICORN_HORN)
P_FIRST_SPELL = int(Skill.P_ATTACK_SPELL)
P_LAST_SPELL = int(Skill.P_MATTER_SPELL)
P_FIRST_H_TO_H = int(Skill.P_BARE_HANDED_COMBAT)
P_LAST_H_TO_H = int(Skill.P_RIDING)

P_SKILL_LIMIT = 60  # C: P_SKILL_LIMIT -- max number of skill advancements


def practice_needed_to_advance(level: int) -> int:
    """C: practice_needed_to_advance(level) == level*level*20."""
    return level * level * 20


@dataclass(frozen=True)
class DefSkill:
    """One row of a role's initial skill table (C: struct def_skill).

    C terminates the array with a P_NONE row; Python sequences have a
    length, so callers simply pass the real rows.
    """
    skill: int
    skmax: int


# ------------------------------------------------------------
# Per-game hero skill state (C: u.weapon_skills + friends)
# ------------------------------------------------------------

class Skills:
    """Mutable weapon-skill state for one hero (see module docstring).

    The lists are indexed by Skill (C: the P_SKILL / P_MAX_SKILL /
    P_ADVANCE macros read u.weapon_skills[type].skill / .max_skill /
    .advance).
    """

    def __init__(self) -> None:
        self.skill: List[int] = [P_ISRESTRICTED] * P_NUM_SKILLS
        self.max_skill: List[int] = [P_ISRESTRICTED] * P_NUM_SKILLS
        self.advance: List[int] = [0] * P_NUM_SKILLS
        # C: u_init.c starts the hero with one skill slot
        self.weapon_slots: int = 1
        self.skills_advanced: int = 0
        # most recently advanced skill LAST (C: u.skill_record[])
        self.skill_record: List[int] = []


def _restricted(skills: Skills, skill: int) -> bool:
    """C: P_RESTRICTED(type)."""
    return skills.skill[skill] == P_ISRESTRICTED


# ------------------------------------------------------------
# Skill names (C: skill_names_indices / odd_skill_names / P_NAME)
# ------------------------------------------------------------

# positive: the object type whose name is the skill name; negative:
# index into _ODD_SKILL_NAMES (C: skill_names_indices)
_SKILL_NAME_INDICES: Tuple[int, ...] = (
    0, O.DAGGER.value, O.KNIFE.value, O.AXE.value, O.PICK_AXE.value,
    O.SHORT_SWORD.value, O.BROADSWORD.value, O.LONG_SWORD.value,
    O.TWO_HANDED_SWORD.value, -5, O.CLUB.value, O.MACE.value,
    O.MORNING_STAR.value, O.FLAIL.value, -6, O.QUARTERSTAFF.value, -4,
    O.SPEAR.value, O.TRIDENT.value, O.LANCE.value, O.BOW.value,
    O.SLING.value, O.CROSSBOW.value, O.DART.value, O.SHURIKEN.value,
    O.BOOMERANG.value, -7, O.UNICORN_HORN.value,
    -8, -9, -10, -11, -12, -13, -14,
    -1, -2, -3,
)

# entry [0] isn't used (C: odd_skill_names)
_ODD_SKILL_NAMES: Tuple[str, ...] = (
    "no skill", "bare hands", "two weapon combat", "riding", "polearms",
    "saber", "hammer", "whip", "attack spells", "healing spells",
    "divination spells", "enchantment spells", "clerical spells",
    "escape spells", "matter spells",
)

# indexed by martial_bonus() (C: barehands_or_martial)
_BAREHANDS_OR_MARTIAL = ("bare handed combat", "martial arts")

# defsym.h OBJCLASS_PARSE, singular names (C: def_oc_syms[].name)
_OC_NAMES: Tuple[str, ...] = (
    "strange object", "weapon", "armor", "ring", "amulet", "tool",
    "food", "potion", "scroll", "spell book", "wand", "coin", "gem",
    "large rock", "iron ball", "iron chain", "venom",
)


def skill_name(skill: int, martial: bool = False) -> str:
    """The name of a skill category (C: skill_name / P_NAME).

    `martial` is C's martial_bonus() (Role_if(PM_SAMURAI) ||
    Role_if(PM_MONK)); the role is explicit here because it is not
    ported yet.
    """
    idx = _SKILL_NAME_INDICES[skill]
    if idx > 0:
        return OBJECTS[idx].name
    if skill == int(Skill.P_BARE_HANDED_COMBAT):
        return _BAREHANDS_OR_MARTIAL[1 if martial else 0]
    return _ODD_SKILL_NAMES[-idx]


def skill_level_name(level: int) -> str:
    """C: skill_level_name (switch on P_SKILL(skill)); takes the level
    directly because the level lives in the caller's Skills state."""
    return {
        P_UNSKILLED: "Unskilled",
        P_BASIC: "Basic",
        P_SKILLED: "Skilled",
        P_EXPERT: "Expert",
        P_MASTER: "Master",
        P_GRAND_MASTER: "Grand Master",
    }.get(level, "Unknown")


# ------------------------------------------------------------
# Object type predicates (C: the weapon macros of include/obj.h)
# ------------------------------------------------------------

def weapon_type(otmp: Optional[ObjLike]) -> int:
    """C: weapon_type -- the skill category of an object (positive for
    hand weapons/launchers/weptools, the launcher skill for ammo), or
    P_NONE; None (no weapon) is bare-handed combat."""
    if otmp is None:
        return int(Skill.P_BARE_HANDED_COMBAT)
    ocls = int(otmp.oclass)
    if ocls not in (int(ObjClass.WEAPON), int(ObjClass.TOOL),
                    int(ObjClass.GEM)):
        return int(Skill.P_NONE)
    t = OBJECTS[int(otmp.otyp)].subtyp
    return -t if t < 0 else t


def _weapon_type_otyp(otyp: int) -> int:
    """Table-level weapon_type() (for skill_init over otypes)."""
    o = OBJECTS[otyp]
    ocls = int(o.oclass)
    if ocls not in (int(ObjClass.WEAPON), int(ObjClass.TOOL),
                    int(ObjClass.GEM)):
        return int(Skill.P_NONE)
    return -o.subtyp if o.subtyp < 0 else o.subtyp


def is_ammo(otmp: ObjLike) -> bool:
    """C: is_ammo -- launcher ammunition (arrows, bolts, sling
    stones/gems)."""
    ocls = int(otmp.oclass)
    if ocls not in (int(ObjClass.WEAPON), int(ObjClass.GEM)):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return -int(Skill.P_CROSSBOW) <= t <= -int(Skill.P_BOW)


def _is_ammo_otyp(otyp: int) -> bool:
    o = OBJECTS[otyp]
    ocls = int(o.oclass)
    if ocls not in (int(ObjClass.WEAPON), int(ObjClass.GEM)):
        return False
    return -int(Skill.P_CROSSBOW) <= o.subtyp <= -int(Skill.P_BOW)


def is_launcher(otmp: ObjLike) -> bool:
    """C: is_launcher -- bow / sling / crossbow."""
    if int(otmp.oclass) != int(ObjClass.WEAPON):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return int(Skill.P_BOW) <= t <= int(Skill.P_CROSSBOW)


def is_weptool(otmp: ObjLike) -> bool:
    """C: is_weptool -- a tool usable as a weapon.  A towel is NOT a
    weptool (oc_skill P_NONE): its spe is wetness, not enchantment."""
    return (int(otmp.oclass) == int(ObjClass.TOOL)
            and OBJECTS[int(otmp.otyp)].subtyp != int(Skill.P_NONE))


def is_blade(otmp: ObjLike) -> bool:
    """C: is_blade."""
    if int(otmp.oclass) != int(ObjClass.WEAPON):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return int(Skill.P_DAGGER) <= t <= int(Skill.P_SABER)


def is_sword(otmp: ObjLike) -> bool:
    """C: is_sword."""
    if int(otmp.oclass) != int(ObjClass.WEAPON):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return int(Skill.P_SHORT_SWORD) <= t <= int(Skill.P_SABER)


def is_axe(otmp: ObjLike) -> bool:
    """C: is_axe (weapons and tools)."""
    if int(otmp.oclass) not in (int(ObjClass.WEAPON), int(ObjClass.TOOL)):
        return False
    return OBJECTS[int(otmp.otyp)].subtyp == int(Skill.P_AXE)


def is_pick(otmp: ObjLike) -> bool:
    """C: is_pick (weapons and tools; the mattock is a pick)."""
    if int(otmp.oclass) not in (int(ObjClass.WEAPON), int(ObjClass.TOOL)):
        return False
    return OBJECTS[int(otmp.otyp)].subtyp == int(Skill.P_PICK_AXE)


def is_spear(otmp: ObjLike) -> bool:
    """C: is_spear (5.0: the spear skill only; the dwarvish mattock is
    NOT a spear)."""
    return (int(otmp.oclass) == int(ObjClass.WEAPON)
            and OBJECTS[int(otmp.otyp)].subtyp == int(Skill.P_SPEAR))


def is_pole(otmp: ObjLike, snickersnee: bool = False) -> bool:
    """C: is_pole -- Snickersnee is not a polearm but hits from a
    distance.  `snickersnee` is the artifact check (C:
    is_art(otmp, ART_SNICKERSNEE)); STUB: callers pass False until the
    artifact port."""
    if int(otmp.oclass) not in (int(ObjClass.WEAPON), int(ObjClass.TOOL)):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return (t in (int(Skill.P_POLEARMS), int(Skill.P_LANCE))
            or snickersnee)


def is_missile(otmp: ObjLike) -> bool:
    """C: is_missile -- hand-thrown missiles (darts, shuriken,
    boomerangs), not launcher ammo."""
    if int(otmp.oclass) not in (int(ObjClass.WEAPON), int(ObjClass.TOOL)):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return -int(Skill.P_BOOMERANG) <= t <= -int(Skill.P_DART)


def is_multigen(otmp: ObjLike) -> bool:
    """C: is_multigen -- weapons that can come in stacks (multi-gen
    missiles plus launcher ammo)."""
    if int(otmp.oclass) != int(ObjClass.WEAPON):
        return False
    t = OBJECTS[int(otmp.otyp)].subtyp
    return -int(Skill.P_SHURIKEN) <= t <= -int(Skill.P_BOW)


def is_blunt_weapon(otmp: ObjLike) -> bool:
    """C: is_blunt_weapon -- strike mode includes WHACK."""
    if not (int(otmp.oclass) == int(ObjClass.WEAPON) or is_weptool(otmp)):
        return False
    return (OBJECTS[int(otmp.otyp)].dir & WHACK) != 0


def bimanual(otmp: ObjLike) -> bool:
    """C: bimanual -- the oc_big bit for weapons and tools."""
    if int(otmp.oclass) not in (int(ObjClass.WEAPON), int(ObjClass.TOOL)):
        return False
    return bool(OBJECTS[int(otmp.otyp)].big)


def is_wet_towel(otmp: ObjLike) -> bool:
    """C: is_wet_towel -- a towel with spe > 0."""
    return int(otmp.otyp) == O.TOWEL.value and otmp.spe > 0


def is_graystone(otmp: ObjLike) -> bool:
    """C: is_graystone -- the four wishable gray stones."""
    return int(otmp.otyp) in (O.LUCKSTONE.value, O.LOADSTONE.value,
                              O.FLINT.value, O.TOUCHSTONE.value)


def is_poisonable(otmp: ObjLike, permapoisoned: bool = False) -> bool:
    """C: is_poisonable.  `permapoisoned` is the attached-poison-vial
    check (C: permapoisoned(otmp), object oextra); STUB: False until
    the mkobj.c port."""
    if int(otmp.oclass) == int(ObjClass.WEAPON):
        t = OBJECTS[int(otmp.otyp)].subtyp
        if -int(Skill.P_SHURIKEN) <= t <= -int(Skill.P_BOW):
            return True
    return permapoisoned


def matching_launcher(ammo: ObjLike, launcher) -> bool:
    """C: matching_launcher -- the ammo's skill is the negation of the
    launcher's (arrows<->bows, bolts<->crossbows, stones<->slings)."""
    if launcher is None:
        return False
    return (OBJECTS[int(ammo.otyp)].subtyp
            == -OBJECTS[int(launcher.otyp)].subtyp)


def ammo_and_launcher(ammo: ObjLike, launcher) -> bool:
    """C: ammo_and_launcher."""
    return is_ammo(ammo) and matching_launcher(ammo, launcher)


def greatest_erosion(otmp: ObjLike) -> int:
    """C: greatest_erosion -- max(oeroded, oeroded2); the instance
    fields default to 0 until the mkobj.c port."""
    a = int(getattr(otmp, "oeroded", 0))
    b = int(getattr(otmp, "oeroded2", 0))
    return a if a > b else b


# ------------------------------------------------------------
# To-hit and damage bonuses (C: hitval / dmgval)
# ------------------------------------------------------------

@dataclass(frozen=True)
class CombatCtx:
    """What a bonus source may look at (C: the locals of hitval() /
    dmgval()).  Frozen data -- sources are pure in (ctx, rng)."""
    obj: ObjLike
    pm: PerMonst
    in_pool: bool = False  # C: is_pool(mon->mx, mon->my); map query


# targets that provide a +2 to-hit bonus when using a spear
# (C: kebabable[])
_KEBABABLE: FrozenSet[int] = frozenset(
    {S_XORN, S_DRAGON, S_JABBERWOCK, S_NAGA, S_GIANT})

# the shade, by import-time-resolved PM anchor (C: &mons[PM_SHADE])
PM_SHADE = PM_NAMES.index("shade")


def _shade_glare(otmp: ObjLike) -> bool:
    """C: shade_glare -- is_art(otmp, ART_SHADELITE).
    STUB: artifact identity is not ported yet (artifact.c)."""
    return False


def _blessed_hit(ctx: CombatCtx) -> int:
    # blessed weapons used against undead or demons
    if ctx.obj.blessed and hates_blessings(ctx.pm):
        return 2
    return 0


def _kebab_hit(ctx: CombatCtx) -> int:
    if is_spear(ctx.obj) and ctx.pm.mlet in _KEBABABLE:
        return 2
    return 0


def _trident_hit(ctx: CombatCtx) -> int:
    # trident is highly effective against swimmers
    if int(ctx.obj.otyp) == O.TRIDENT.value and is_swimmer(ctx.pm):
        if ctx.in_pool:
            return 4
        if ctx.pm.mlet in (S_EEL, S_SNAKE):
            return 2
    return 0


def _pick_hit(ctx: CombatCtx) -> int:
    # picks used against xorns and earth elementals
    if is_pick(ctx.obj) and passes_walls(ctx.pm) and thick_skinned(ctx.pm):
        return 2
    return 0


# C order: the list order is the order the bonuses are applied.
HIT_BONUS_SOURCES = (_blessed_hit, _kebab_hit, _trident_hit, _pick_hit)
# STUB (artifact port): a final source
# `otmp->oartifact && spec_abon(otmp, mon)`.


def hitval(otmp: ObjLike, mon: MonLike, in_pool: bool = False) -> int:
    """The "to hit" bonus of weapon `otmp` against monster `mon`
    (C: hitval).

    `mon` needs `.mdata` (PerMonst); the monster's position is a map
    query the caller resolves and passes as `in_pool` (C:
    is_pool(mon->mx, mon->my)).  Note the 5.0 weptool quirk in the
    module docstring: the table's oc1 (oc_hitbon) slot holds the strike
    mode for weptools, so they add it here.
    """
    ctx = CombatCtx(otmp, mon.mdata, in_pool)
    is_weapon = (int(otmp.oclass) == int(ObjClass.WEAPON)
                 or is_weptool(otmp))
    tmp = 0
    if is_weapon:
        tmp += otmp.spe
    # weapon-specific "to hit" bonus (C: objects[otyp].oc_hitbon)
    tmp += OBJECTS[int(otmp.otyp)].oc1
    # all sources may fire; the bonuses are additive (C: plain ifs,
    # not elifs)
    for src in HIT_BONUS_SOURCES:
        tmp += src(ctx)
    # STUB (artifact port): if oartifact: tmp += spec_abon(otmp, mon)
    return tmp


@dataclass(frozen=True)
class _Extra:
    """One of C's dmgval switch-case extras: a roll spec, not a lambda.
    kind 'one' -> +1; 'rnd' -> +rng.rnd(n); 'dice' -> +rng.d(n, d)."""
    kind: str
    n: int = 0
    d: int = 0


def _roll_extra(extra: _Extra, rng) -> int:
    if extra.kind == "one":
        return 1
    if extra.kind == "rnd":
        return rng.rnd(extra.n)
    return rng.d(extra.n, extra.d)


# C: the bigmonst switch in dmgval() -- extra damage when the target is
# LARGE (the data structure can't say 3d6 or 1d6+1, so the extra is
# added here; see the C historical note)
_DMG_EXTRA_LARGE: Dict[int, _Extra] = {
    O.IRON_CHAIN.value: _Extra("one"),
    O.CROSSBOW_BOLT.value: _Extra("one"),
    O.MORNING_STAR.value: _Extra("one"),
    O.PARTISAN.value: _Extra("one"),
    O.RUNESWORD.value: _Extra("one"),
    O.ELVEN_BROADSWORD.value: _Extra("one"),
    O.BROADSWORD.value: _Extra("one"),
    O.FLAIL.value: _Extra("rnd", 4),
    O.RANSEUR.value: _Extra("rnd", 4),
    O.VOULGE.value: _Extra("rnd", 4),
    O.ACID_VENOM.value: _Extra("rnd", 6),
    O.HALBERD.value: _Extra("rnd", 6),
    O.SPETUM.value: _Extra("rnd", 6),
    O.BATTLE_AXE.value: _Extra("dice", 2, 4),
    O.BARDICHE.value: _Extra("dice", 2, 4),
    O.TRIDENT.value: _Extra("dice", 2, 4),
    O.TSURUGI.value: _Extra("dice", 2, 6),
    O.DWARVISH_MATTOCK.value: _Extra("dice", 2, 6),
    O.TWO_HANDED_SWORD.value: _Extra("dice", 2, 6),
}

# C: the !bigmonst switch
_DMG_EXTRA_SMALL: Dict[int, _Extra] = {
    O.IRON_CHAIN.value: _Extra("one"),
    O.CROSSBOW_BOLT.value: _Extra("one"),
    O.MACE.value: _Extra("one"),
    O.SILVER_MACE.value: _Extra("one"),
    O.WAR_HAMMER.value: _Extra("one"),
    O.FLAIL.value: _Extra("one"),
    O.SPETUM.value: _Extra("one"),
    O.TRIDENT.value: _Extra("one"),
    O.BATTLE_AXE.value: _Extra("rnd", 4),
    O.BARDICHE.value: _Extra("rnd", 4),
    O.BILL_GUISARME.value: _Extra("rnd", 4),
    O.GUISARME.value: _Extra("rnd", 4),
    O.LUCERN_HAMMER.value: _Extra("rnd", 4),
    O.MORNING_STAR.value: _Extra("rnd", 4),
    O.RANSEUR.value: _Extra("rnd", 4),
    O.BROADSWORD.value: _Extra("rnd", 4),
    O.ELVEN_BROADSWORD.value: _Extra("rnd", 4),
    O.RUNESWORD.value: _Extra("rnd", 4),
    O.VOULGE.value: _Extra("rnd", 4),
    O.ACID_VENOM.value: _Extra("rnd", 6),
}

# weight.h
WT_IRON_BALL_INCR = 160  # weight increment of heavy iron ball
WT_IRON_BALL_BASE = 480  # base starting weight of iron ball


def _blessed_dmg(ctx: CombatCtx, rng) -> int:
    if ctx.obj.blessed and hates_blessings(ctx.pm):
        return rng.rnd(4)
    return 0


def _axe_dmg(ctx: CombatCtx, rng) -> int:
    if is_axe(ctx.obj) and is_wooden(ctx.pm):
        return rng.rnd(4)
    return 0


def _silver_dmg(ctx: CombatCtx, rng) -> int:
    if (OBJECTS[int(ctx.obj.otyp)].material == Material.SILVER
            and hates_silver(ctx.pm)):
        return rng.rnd(20)
    return 0


# C order == RNG draw order: blessed first, then axe, then silver.
DMG_BONUS_SOURCES = (_blessed_dmg, _axe_dmg, _silver_dmg)
# STUB (artifact port): _light_dmg (artifact_light(otmp) && otmp->lamplit
# && hates_light(ptr) -> rnd(8)) and the double-damage halving
# (bonus > 1 && oartifact && spec_dbon(otmp, mon, 25) >= 25
#  -> bonus = (bonus + 1) / 2).


def dmgval(otmp: ObjLike, mon: MonLike, rng) -> int:
    """The damage bonus of weapon `otmp` against monster `mon`
    (C: dmgval).  `rng` is the game RNG (C: the global RNG); rolls
    happen only when the corresponding bonus actually applies.
    """
    pm = mon.mdata
    otyp = int(otmp.otyp)
    ctx = CombatCtx(otmp, pm)
    is_weapon = (int(otmp.oclass) == int(ObjClass.WEAPON)
                 or is_weptool(otmp))

    if otyp == O.CREAM_PIE.value:
        return 0

    tmp = 0
    # base damage: an exact die of the table's max small/large damage
    if bigmonst(pm):
        base = OBJECTS[otyp].wldam
        if base:
            tmp = rng.rnd(base)
        extra = _DMG_EXTRA_LARGE.get(otyp)
    else:
        base = OBJECTS[otyp].wsdam
        if base:
            tmp = rng.rnd(base)
        extra = _DMG_EXTRA_SMALL.get(otyp)
    if extra is not None:
        tmp += _roll_extra(extra, rng)

    if is_weapon:
        tmp += otmp.spe
        # negative enchantment mustn't produce negative damage
        if tmp < 0:
            tmp = 0

    if OBJECTS[otyp].material <= Material.LEATHER and thick_skinned(pm):
        # thick-skinned or scaled creatures don't feel it
        tmp = 0
    if pm.pmidx == PM_SHADE and not _shade_glare(otmp):
        tmp = 0

    # "very heavy iron ball"; weight increase is in increments
    if otyp == O.HEAVY_IRON_BALL.value and tmp > 0:
        wt = OBJECTS[otyp].weight
        owt = int(getattr(otmp, "owt", wt))
        if owt > wt:
            wt = (owt - wt) // WT_IRON_BALL_INCR
            if wt > 0:  # C would call rnd(0) here; owt only grows in
                tmp += rng.rnd(4 * wt)  # WT_IRON_BALL_INCR steps
                if tmp > 25:  # objects[].oc_wldam
                    tmp = 25

    if (is_weapon or int(otmp.oclass) in (int(ObjClass.GEM),
                                          int(ObjClass.BALL),
                                          int(ObjClass.CHAIN))):
        # weapon vs. monster type damage bonuses: all sources may fire
        tmp += sum(src(ctx, rng) for src in DMG_BONUS_SOURCES)

    if tmp > 0:
        # it ought to be some penalty for using damaged gear, so always
        # subtract erosion even for blunt weapons (C comment)
        tmp -= greatest_erosion(otmp)
        if tmp < 1:
            tmp = 1
    return tmp


# ------------------------------------------------------------
# Strength / dexterity combat bonuses (C: abon / dbon)
# ------------------------------------------------------------

def STR18(x: int) -> int:
    """C: STR18(x) -- 18/xx on the 5.0 linear ability scale
    (attrib.h: 18 + x, i.e. 18/50 == 68, 18/100 == 118)."""
    return 18 + x


def abon(str: int, dex: int, ulevel: int, upolyd: bool = False,
         poly_lev: int = 0) -> int:
    """Attack bonus for strength & dexterity (C: abon).

    C reads the globals u.*; the effective values are explicit
    parameters here (`str` is ACURR(A_STR) on the 5.0 scale).  When
    polymorphed the bonus is C's adj_lev(&mons[u.umonnum]) - 3, passed
    as `poly_lev`.
    """
    if upolyd:
        return poly_lev - 3

    # '< 18/50' (not '<=') so 18/50 gives a bonus of 2; gnome and orc
    # players have max Str 18/50
    if str < 6:
        sbon = -2
    elif str < 8:
        sbon = -1
    elif str < 17:
        sbon = 0
    elif str < STR18(50):
        sbon = 1  # up to 18/49
    elif str < STR18(100):
        sbon = 2
    else:
        sbon = 3

    # game tuning kludge: make it a bit easier for a low level
    # character to hit
    sbon += 1 if ulevel < 3 else 0

    if dex < 4:
        return sbon - 3
    elif dex < 6:
        return sbon - 2
    elif dex < 8:
        return sbon - 1
    elif dex < 14:
        return sbon
    else:
        return sbon + dex - 14


def dbon(str: int, upolyd: bool = False) -> int:
    """Damage bonus for strength (C: dbon)."""
    if upolyd:
        return 0
    if str < 6:
        return -1
    elif str < 16:
        return 0
    elif str < 18:
        return 1
    elif str == 18:
        return 2  # up to 18/00
    elif str <= STR18(75):
        return 3  # up to 18/75
    elif str <= STR18(90):
        return 4  # up to 18/90
    elif str < STR18(100):
        return 5  # up to 18/99
    else:
        return 6


# ------------------------------------------------------------
# Towels (C: wet_a_towel / dry_a_towel / finish_towel_change)
# ------------------------------------------------------------

def _finish_towel_change(obj: ObjLike, newspe: int) -> None:
    # towel wetness is always between 0 (dry) and 7, inclusive
    newspe = min(newspe, 7)
    obj.spe = max(newspe, 0)
    # STUB (do_wear.c port): if the hero wields this towel,
    # gu.unweapon = !is_wet_towel(obj);
    # STUB (invent.c/objnam.c port): if carried, update_inventory()
    # (the "towel"/"moist towel"/"wet towel" description).


def wet_a_towel(obj: ObjLike, amt: int, verbose: bool = False) -> Optional[str]:
    """Increase a towel's wetness (C: wet_a_towel).  `amt` > 0 sets the
    new wetness, `amt` < 0 adds -amt, 0 is a no-op.  Returns the
    message to show (None if none) instead of printing (no-I/O rule);
    the hero-carried phrasing is used -- the monster-carried branch
    (C: mcarried/canseemon) comes with the mon.c port."""
    newspe = obj.spe - amt if amt <= 0 else amt
    msg = None
    # new state is only reported if it's an increase
    if newspe > obj.spe and verbose:
        if newspe < 3:
            wetness = "damp" if not obj.spe else "damper"
        else:
            wetness = "wet" if not obj.spe else "wetter"
        msg = f"Your towel gets {wetness}."
    if newspe != obj.spe:
        _finish_towel_change(obj, newspe)
    return msg


def dry_a_towel(obj: ObjLike, amt: int, verbose: bool = False) -> Optional[str]:
    """Decrease a towel's wetness (C: dry_a_towel); unlike when
    wetting, 0 is not a no-op (it dries the towel out)."""
    newspe = obj.spe + amt if amt < 0 else amt
    msg = None
    if newspe < obj.spe and verbose:
        msg = f"Your towel dries{' out' if not newspe else ''}."
    if newspe != obj.spe:
        _finish_towel_change(obj, newspe)
    return msg


# ------------------------------------------------------------
# The skill system (C: weapon.c)
# ------------------------------------------------------------

def slots_required(skills: Skills, skill: int) -> int:
    """C: slots_required -- the cost depends on the skill's CURRENT
    level (C reads P_SKILL(skill)).

    weapons: unskilled->basic 1, basic->skilled 2, skilled->expert 3;
    unarmed/martial: 1, 1, 2, 2, 3.
    """
    tmp = skills.skill[skill]
    if skill <= P_LAST_WEAPON or skill == int(Skill.P_TWO_WEAPON_COMBAT):
        return tmp
    return (tmp + 1) // 2


def can_advance(skills: Skills, skill: int, wizard: bool = False,
                speedy: bool = False) -> bool:
    """C: can_advance."""
    if (_restricted(skills, skill)
            or skills.skill[skill] >= skills.max_skill[skill]
            or skills.skills_advanced >= P_SKILL_LIMIT):
        return False
    if wizard and speedy:
        return True
    return (skills.advance[skill]
            >= practice_needed_to_advance(skills.skill[skill])
            and skills.weapon_slots >= slots_required(skills, skill))


def could_advance(skills: Skills, skill: int) -> bool:
    """C: could_advance -- advanceable if more slots were available."""
    if (_restricted(skills, skill)
            or skills.skill[skill] >= skills.max_skill[skill]
            or skills.skills_advanced >= P_SKILL_LIMIT):
        return False
    return (skills.advance[skill]
            >= practice_needed_to_advance(skills.skill[skill]))


def peaked_skill(skills: Skills, skill: int) -> bool:
    """C: peaked_skill -- at max, with enough practice for the next
    step if it had been possible."""
    if _restricted(skills, skill):
        return False
    return (skills.skill[skill] >= skills.max_skill[skill]
            and skills.advance[skill]
            >= practice_needed_to_advance(skills.skill[skill]))


def advance_skill(skills: Skills, skill: int) -> str:
    """C: skill_advance (the #enhance action).  Returns the message;
    the caller must ensure can_advance()."""
    skills.weapon_slots -= slots_required(skills, skill)
    skills.skill[skill] += 1
    skills.skill_record.append(skill)
    skills.skills_advanced += 1
    most = "most" if skills.skill[skill] >= skills.max_skill[skill] \
        else "more"
    # STUB (read.c/spell.c port): C also calls skill_based_spellbook_id()
    # for spell skills (wizard book-id discovery).
    return f"You are now {most} skilled in {skill_name(skill)}."


def _may_advance_msg(skill: int) -> str:
    """C: give_may_advance_msg.  STUB: the handle_tip(TIP_ENHANCE) call
    comes with the cmd.c port."""
    if skill == int(Skill.P_NONE):
        prefix = ""
    elif skill <= P_LAST_WEAPON:
        prefix = "weapon "
    elif skill <= P_LAST_SPELL:
        prefix = "spell casting "
    else:
        prefix = "fighting "
    return f"You feel more confident in your {prefix}skills."


def use_skill(skills: Skills, skill: int, degree: int) -> Optional[str]:
    """C: use_skill -- add practice to a skill; returns the
    "more confident" message when the advance threshold is crossed."""
    if skill != int(Skill.P_NONE) and not _restricted(skills, skill):
        advance_before = can_advance(skills, skill)
        skills.advance[skill] += degree
        if not advance_before and can_advance(skills, skill):
            return _may_advance_msg(skill)
    return None


def add_weapon_skill(skills: Skills, n: int) -> Optional[str]:
    """C: add_weapon_skill -- gain `n` skill slots (normally one, from
    a level-up); returns the message if that unlocks a skill."""
    before = sum(1 for i in range(P_NUM_SKILLS) if can_advance(skills, i))
    skills.weapon_slots += n
    after = sum(1 for i in range(P_NUM_SKILLS) if can_advance(skills, i))
    return _may_advance_msg(int(Skill.P_NONE)) if before < after else None


def lose_weapon_skill(skills: Skills, n: int) -> None:
    """C: lose_weapon_skill -- lose `n` slots, deducting first from
    unused slots then from the last placed skill."""
    while n > 0:
        n -= 1
        if skills.weapon_slots:
            skills.weapon_slots -= 1
        elif skills.skills_advanced:
            skill = skills.skill_record[skills.skills_advanced - 1]
            skills.skills_advanced -= 1
            skills.skill_record.pop()
            if skills.skill[skill] <= P_UNSKILLED:
                raise ValueError(f"lose_weapon_skill({skill})")
            skills.skill[skill] -= 1  # drop skill one level
            # lost skill might have taken more than one slot; refund
            # the rest
            skills.weapon_slots = slots_required(skills, skill) - 1


def drain_weapon_skill(skills: Skills, n: int, rng) -> List[str]:
    """C: drain_weapon_skill -- lose `n` skills (randomly chosen);
    returns the "you forget" messages."""
    msgs: List[str] = []
    drained: Set[int] = set()
    while n > 0:
        n -= 1
        if skills.skills_advanced:
            i = rng.rn2(skills.skills_advanced)
            skill = skills.skill_record[i]
            drained.add(skill)
            del skills.skill_record[i]
            skills.skills_advanced -= 1
            if skills.skill[skill] <= P_UNSKILLED:
                raise ValueError(f"drain_weapon_skill({skill})")
            skills.skill[skill] -= 1  # drop skill one level
            # refund slots used for the skill
            skills.weapon_slots += slots_required(skills, skill)
            # drain training to a value appropriate for the new level
            curradv = practice_needed_to_advance(skills.skill[skill])
            prevadv = practice_needed_to_advance(skills.skill[skill] - 1)
            if skills.advance[skill] >= curradv:
                skills.advance[skill] = (prevadv
                                         + rng.rn2(curradv - prevadv))
    for skill in sorted(drained):
        prefix = "some of " if skills.skill[skill] >= P_BASIC else ""
        msgs.append(f"You forget {prefix}your training in "
                    f"{skill_name(skill)}.")
    return msgs


def unrestrict_weapon_skill(skills: Skills, skill: int) -> None:
    """C: unrestrict_weapon_skill -- change from restricted to
    unrestricted, allowing P_BASIC as max.  C calls it with P_NONE
    (see skill_init); that is preserved."""
    if skill < P_NUM_SKILLS and _restricted(skills, skill):
        skills.skill[skill] = P_UNSKILLED
        skills.max_skill[skill] = P_BASIC
        skills.advance[skill] = 0


def skill_init(skills: Skills, class_skills: Tuple[DefSkill, ...],
               held: Tuple[int, ...] = (), role: str = "",
               pet_is_pony: bool = False,
               spell_skill: int = int(Skill.P_NONE)) -> None:
    """C: skill_init(const struct def_skill *class_skill).

    `class_skills` is the role's skill-max table (C: the per-role
    def_skill array in u_init.c).  `held` is the otype of everything
    in the hero's starting inventory; carried ammo is skipped here (C
    comment: don't give skill just because of carried ammo).  `role`
    is the C role name for the Role_if() checks ("healer"/"monk"/
    "cleric"/"wizard").  `spell_skill` is C's
    spell_skilltype(gu.urole.spelspec) (P_NONE when the role has no
    special spell).
    """
    for i in range(P_NUM_SKILLS):
        skills.skill[i] = P_ISRESTRICTED
        skills.max_skill[i] = P_ISRESTRICTED
        skills.advance[i] = 0

    # set skill for all weapons in inventory to basic
    for otyp in held:
        if _is_ammo_otyp(otyp):
            continue
        skill = _weapon_type_otyp(otyp)
        if skill != int(Skill.P_NONE):
            skills.skill[skill] = P_BASIC

    # set skills for magic
    if role in ("healer", "monk"):
        skills.skill[int(Skill.P_HEALING_SPELL)] = P_BASIC
    elif role == "cleric":
        skills.skill[int(Skill.P_CLERIC_SPELL)] = P_BASIC
    elif role == "wizard":
        skills.skill[int(Skill.P_ATTACK_SPELL)] = P_BASIC
        skills.skill[int(Skill.P_ENCHANTMENT_SPELL)] = P_BASIC

    # walk through the table to set skill maximums
    for ds in class_skills:
        skills.max_skill[ds.skill] = ds.skmax
        if skills.skill[ds.skill] == P_ISRESTRICTED:  # skill pre-set
            skills.skill[ds.skill] = P_UNSKILLED

    # high potential fighters already know how to use their hands
    if skills.max_skill[int(Skill.P_BARE_HANDED_COMBAT)] > P_EXPERT:
        skills.skill[int(Skill.P_BARE_HANDED_COMBAT)] = P_BASIC

    # roles that start with a horse know how to ride it
    if pet_is_pony:
        skills.skill[int(Skill.P_RIDING)] = P_BASIC

    # make sure we haven't missed setting the max on a skill & set advance
    for i in range(P_NUM_SKILLS):
        if not _restricted(skills, i):
            if skills.max_skill[i] < skills.skill[i]:
                raise ValueError(
                    f"skill_init: curr > max: {skill_name(i)}")
            skills.advance[i] = practice_needed_to_advance(
                skills.skill[i] - 1)

    # each role has a special spell; allow at least basic for its type
    # (despite the function name, this works for spell skills too)
    unrestrict_weapon_skill(skills, spell_skill)
    # STUB (read.c/spell.c port): C's final skill_based_spellbook_id()
    # (skipped for paupers) -- wizard book-id discovery.


# ------------------------------------------------------------
# Skill-based attack bonuses (C: weapon_hit_bonus / weapon_dam_bonus)
# ------------------------------------------------------------

# level -> bonus tables (C: the switches); the C default case is
# impossible() then falls through to the unskilled value, so the table
# default is that same value
_WPN_HIT_BY_LEVEL = {P_ISRESTRICTED: -4, P_UNSKILLED: -4, P_BASIC: 0,
                     P_SKILLED: 2, P_EXPERT: 3}
_TWC_HIT_BY_LEVEL = {P_ISRESTRICTED: -9, P_UNSKILLED: -9, P_BASIC: -7,
                     P_SKILLED: -5, P_EXPERT: -3}
_WPN_DAM_BY_LEVEL = {P_ISRESTRICTED: -2, P_UNSKILLED: -2, P_BASIC: 0,
                     P_SKILLED: 1, P_EXPERT: 2}
_TWC_DAM_BY_LEVEL = {P_ISRESTRICTED: -3, P_UNSKILLED: -3, P_BASIC: -1,
                     P_SKILLED: 0, P_EXPERT: 1}


def weapon_hit_bonus(skills: Skills, otmp, twoweap: bool = False,
                     in_hands: bool = False, mounted: bool = False,
                     martial: bool = False) -> int:
    """Hit bonus/penalty based on skill of weapon (C:
    weapon_hit_bonus).  `otmp` may be None (bare-handed combat).
    `in_hands` is C's (weapon == uwep || weapon == uswapwep);
    `mounted` is C's u.usteed; `martial` is C's martial_bonus().
    Restricted weapons are treated as unskilled."""
    wep_type = weapon_type(otmp)
    # use the two-weapon skill only if attacking with one of the
    # wielded weapons
    type_ = (int(Skill.P_TWO_WEAPON_COMBAT)
             if (twoweap and in_hands) else wep_type)
    if type_ == int(Skill.P_NONE):
        bonus = 0
    elif type_ <= P_LAST_WEAPON:
        bonus = _WPN_HIT_BY_LEVEL.get(skills.skill[type_], -4)
    elif type_ == int(Skill.P_TWO_WEAPON_COMBAT):
        skill = skills.skill[int(Skill.P_TWO_WEAPON_COMBAT)]
        if skills.skill[wep_type] < skill:
            skill = skills.skill[wep_type]
        bonus = _TWC_HIT_BY_LEVEL.get(skill, -9)
    elif type_ == int(Skill.P_BARE_HANDED_COMBAT):
        #        b.h. m.a.
        # unskl:  +1  n/a
        # basic:  +1   +3
        # skild:  +2   +4
        # exprt:  +2   +5
        # mastr:  +3   +6
        # grand:  +3   +7
        bonus = max(skills.skill[type_], P_UNSKILLED) - 1
        bonus = ((bonus + 2) * (2 if martial else 1)) // 2
    else:
        bonus = 0

    # it's harder to hit while you are riding
    if mounted:
        riding = skills.skill[int(Skill.P_RIDING)]
        if riding in (P_ISRESTRICTED, P_UNSKILLED):
            bonus -= 2
        elif riding == P_BASIC:
            bonus -= 1
        if twoweap:
            bonus -= 2
    return bonus


def weapon_dam_bonus(skills: Skills, otmp, twoweap: bool = False,
                     in_hands: bool = False, mounted: bool = False,
                     martial: bool = False) -> int:
    """Damage bonus/penalty based on skill of weapon (C:
    weapon_dam_bonus); parameters as in weapon_hit_bonus()."""
    wep_type = weapon_type(otmp)
    type_ = (int(Skill.P_TWO_WEAPON_COMBAT)
             if (twoweap and in_hands) else wep_type)
    if type_ == int(Skill.P_NONE):
        bonus = 0
    elif type_ <= P_LAST_WEAPON:
        bonus = _WPN_DAM_BY_LEVEL.get(skills.skill[type_], -2)
    elif type_ == int(Skill.P_TWO_WEAPON_COMBAT):
        skill = skills.skill[int(Skill.P_TWO_WEAPON_COMBAT)]
        if skills.skill[wep_type] < skill:
            skill = skills.skill[wep_type]
        bonus = _TWC_DAM_BY_LEVEL.get(skill, -3)
    elif type_ == int(Skill.P_BARE_HANDED_COMBAT):
        #        b.h. m.a.
        # unskl:   0  n/a
        # basic:  +1   +3
        # skild:  +1   +4
        # exprt:  +2   +6
        # mastr:  +2   +7
        # grand:  +3   +9
        bonus = max(skills.skill[type_], P_UNSKILLED) - 1
        bonus = ((bonus + 1) * (3 if martial else 1)) // 2
    else:
        bonus = 0

    # riding gives some thrusting damage (not in two-weapon combat)
    if mounted and type_ != int(Skill.P_TWO_WEAPON_COMBAT):
        riding = skills.skill[int(Skill.P_RIDING)]
        if riding == P_SKILLED:
            bonus += 1
        elif riding == P_EXPERT:
            bonus += 2
    return bonus


def uwep_skill_type(twoweap: bool, uwep) -> int:
    """C: uwep_skill_type."""
    if twoweap:
        return int(Skill.P_TWO_WEAPON_COMBAT)
    return weapon_type(uwep)


def weapon_descr(otmp: ObjLike, martial: bool = False) -> str:
    """Weapon's skill category name as a generalized description of the
    weapon (C: weapon_descr) -- mostly to shorten "you drop your
    <weapon>" messages when slippery fingers or polymorph cause the
    hero to involuntarily drop the wielded weapon."""
    skill = weapon_type(otmp)
    descr = skill_name(skill, martial=martial)
    otyp = int(otmp.otyp)
    ocls = int(otmp.oclass)
    if skill == int(Skill.P_NONE):
        # not a weapon or weptool: use the item class name, with
        # overrides where the class name sounds strange or the item
        # is unexpected to find being wielded
        if otyp in (O.CORPSE.value, O.TIN.value, O.EGG.value,
                    O.STATUE.value, O.BOULDER.value, O.TOWEL.value,
                    O.TIN_OPENER.value):
            descr = OBJECTS[otyp].name
        elif getattr(otmp, "globby", False):
            descr = "glob"
        else:
            descr = _OC_NAMES[ocls]
    elif skill == int(Skill.P_SLING) and is_ammo(otmp):
        descr = ("stone" if (otyp == O.ROCK.value or is_graystone(otmp))
                 else "gem" if ocls == int(ObjClass.GEM)
                 else _OC_NAMES[ocls])
    elif skill == int(Skill.P_BOW) and is_ammo(otmp):
        descr = "arrow"
    elif skill == int(Skill.P_CROSSBOW) and is_ammo(otmp):
        descr = "bolt"
    elif skill == int(Skill.P_FLAIL) and otyp == O.GRAPPLING_HOOK.value:
        descr = "hook"
    elif skill == int(Skill.P_PICK_AXE) and otyp == O.DWARVISH_MATTOCK.value:
        descr = "mattock"
    return makesingular(descr)


# ------------------------------------------------------------
# Monster weapon selection (C: weapon.c).  The preference tables are
# data for the mon.c port; the selection functions are stubs until the
# per-instance monster model (minvent, mw, weapon_check,
# misc_worn_check, LOS) exists.
# ------------------------------------------------------------

# weapon_check states (C: monst.h) -- consumed by the mon.c port
NEED_WEAPON = 0
NEED_HTH_WEAPON = 1
NEED_RANGED_WEAPON = 2
NEED_PICK_AXE = 3
NEED_AXE = 4
NEED_PICK_OR_AXE = 5
NO_WEAPON_WANTED = 6

# "weapons" a monster knows how to throw, in order of preference
# (C: rwep[]); the gray stones are GEM_CLASS in the 5.0 table
RWERP: Tuple[int, ...] = (
    O.DWARVISH_SPEAR.value, O.SILVER_SPEAR.value, O.ELVEN_SPEAR.value,
    O.SPEAR.value, O.ORCISH_SPEAR.value, O.JAVELIN.value,
    O.SHURIKEN.value, O.YA.value, O.SILVER_ARROW.value,
    O.ELVEN_ARROW.value, O.ARROW.value, O.ORCISH_ARROW.value,
    O.CROSSBOW_BOLT.value, O.SILVER_DAGGER.value, O.ELVEN_DAGGER.value,
    O.DAGGER.value, O.ORCISH_DAGGER.value, O.KNIFE.value,
    O.FLINT.value, O.ROCK.value, O.LOADSTONE.value, O.LUCKSTONE.value,
    O.DART.value, O.CREAM_PIE.value,
)

# polearms (C: pwep[])
PWERP: Tuple[int, ...] = (
    O.HALBERD.value, O.BARDICHE.value, O.SPETUM.value,
    O.BILL_GUISARME.value, O.VOULGE.value, O.RANSEUR.value,
    O.GUISARME.value, O.GLAIVE.value, O.LUCERN_HAMMER.value,
    O.BEC_DE_CORBIN.value, O.FAUCHARD.value, O.PARTISAN.value,
    O.LANCE.value,
)

# hand-to-hand weapons, in order of preference (C: hwep[])
HWEP: Tuple[int, ...] = (
    O.CORPSE.value,  # cockatrice corpse
    O.TSURUGI.value, O.RUNESWORD.value, O.DWARVISH_MATTOCK.value,
    O.TWO_HANDED_SWORD.value, O.BATTLE_AXE.value,
    O.KATANA.value, O.UNICORN_HORN.value, O.CRYSKNIFE.value,
    O.TRIDENT.value, O.LONG_SWORD.value, O.ELVEN_BROADSWORD.value,
    O.BROADSWORD.value, O.SCIMITAR.value, O.SILVER_SABER.value,
    O.MORNING_STAR.value, O.ELVEN_SHORT_SWORD.value,
    O.DWARVISH_SHORT_SWORD.value, O.SHORT_SWORD.value,
    O.ORCISH_SHORT_SWORD.value, O.SILVER_MACE.value, O.MACE.value,
    O.AXE.value, O.DWARVISH_SPEAR.value, O.SILVER_SPEAR.value,
    O.ELVEN_SPEAR.value, O.SPEAR.value, O.ORCISH_SPEAR.value,
    O.FLAIL.value,
    O.BULLWHIP.value, O.QUARTERSTAFF.value, O.JAVELIN.value,
    O.AKLYS.value, O.CLUB.value, O.PICK_AXE.value, O.RUBBER_HOSE.value,
    O.WAR_HAMMER.value, O.SILVER_DAGGER.value, O.ELVEN_DAGGER.value,
    O.DAGGER.value, O.ORCISH_DAGGER.value, O.ATHAME.value,
    O.SCALPEL.value, O.KNIFE.value, O.WORM_TOOTH.value,
)

# C: hack.h -- crossbow bolt max range (dist2 units); re-verify with
# the mthrowu.c port
BOLT_LIM = 34
AKLYS_LIM = BOLT_LIM // 2


@dataclass(frozen=True)
class ThrowAndReturnWeapon:
    """C: struct throw_and_return_weapon (range in dist2 units)."""
    otyp: int
    range: int
    tethered: int


# throw-and-return weapons (C: arwep[]; the BOOMERANG entry is
# commented out in C)
ARWEP: Tuple[ThrowAndReturnWeapon, ...] = (
    ThrowAndReturnWeapon(O.AKLYS.value, AKLYS_LIM * AKLYS_LIM, 1),
)


def autoreturn_weapon(otmp: ObjLike) -> Optional[ThrowAndReturnWeapon]:
    """C: autoreturn_weapon."""
    otyp = int(otmp.otyp)
    for arw in ARWEP:
        if otyp == arw.otyp:
            return arw
    return None


def monmightthrowwep(otmp: ObjLike) -> bool:
    """C: monmightthrowwep -- is `otmp` a type of weapon any monster
    knows how to throw?"""
    return int(otmp.otyp) in RWERP


def select_rwep(mon, rng=None):
    """STUB (mon.c port): select a ranged weapon for the monster (C:
    select_rwep).  Needs the per-instance monster model: minvent,
    mw/weapon_check, misc_worn_check, mux/muy, couldsee, the
    propellor.  The preference order is the RWERP/PWERP/ARWEP tables
    above; the C logic (polearms first within dist2 <= 13, then
    throw-and-return, then RWERP in order with the gem-sling and
    propellor rules) is transcribed there."""
    raise NotImplementedError("select_rwep: stub until the mon.c port")


def select_hwep(mon):
    """STUB (mon.c port): select a hand-to-hand weapon for the monster
    (C: select_hwep; the preference order is HWEP above)."""
    raise NotImplementedError("select_hwep: stub until the mon.c port")


def possibly_unwield(mon, polyspot: bool = False):
    """STUB (mon.c port) -- C: possibly_unwield (called after
    polymorphing a monster, robbing it, etc.)."""
    raise NotImplementedError("possibly_unwield: stub until the mon.c port")


def mon_wield_item(mon) -> int:
    """STUB (mon.c port) -- C: mon_wield_item (returns 1 if the
    monster took time to wield)."""
    raise NotImplementedError("mon_wield_item: stub until the mon.c port")


def mwepgone(mon):
    """STUB (mon.c port) -- C: mwepgone (force a monster to stop
    wielding its current weapon)."""
    raise NotImplementedError("mwepgone: stub until the mon.c port")


def setmnotwielded(mon, obj):
    """STUB (mon.c port) -- C: setmnotwielded."""
    raise NotImplementedError("setmnotwielded: stub until the mon.c port")


def special_dmgval(magr, mdef, armask, silverhit_p=None):
    """STUB (do_wear.c/worn.c port): blessed/silver damage for a
    non-weapon hit (C: special_dmgval).  Needs the hero equipment
    (which_armor, uleft/uright)."""
    raise NotImplementedError(
        "special_dmgval: stub until the equipment port")


def silver_sears(magr, mdef, silverhit):
    """STUB (do_wear.c/worn.c port) -- C: silver_sears message."""
    raise NotImplementedError(
        "silver_sears: stub until the equipment port")


# skill ranges for the (future) skill menu (C: skill_ranges[])
SKILL_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (P_FIRST_H_TO_H, P_LAST_H_TO_H, "Fighting Skills"),
    (P_FIRST_WEAPON, P_LAST_WEAPON, "Weapon Skills"),
    (P_FIRST_SPELL, P_LAST_SPELL, "Spellcasting Skills"),
)


def add_skills_to_menu(win, selectable: bool, speedy: bool):
    """STUB (cmd.c port): write the skills onto a menu (C:
    add_skills_to_menu).  The pure parts it uses (can_advance /
    could_advance / peaked_skill / skill_level_name) are real here."""
    raise NotImplementedError(
        "add_skills_to_menu: stub until the cmd.c port")


def show_skills():
    """STUB (cmd.c port) -- C: show_skills (the #skills dump)."""
    raise NotImplementedError("show_skills: stub until the cmd.c port")


def enhance_weapon_skill():
    """STUB (cmd.c port) -- C: enhance_weapon_skill (#enhance).  Uses
    advance_skill() once the menu machinery exists."""
    raise NotImplementedError(
        "enhance_weapon_skill: stub until the cmd.c port")


# ------------------------------------------------------------
# Import-time validation
# ------------------------------------------------------------

def _validate() -> None:
    assert len(_SKILL_NAME_INDICES) == P_NUM_SKILLS
    for skill, idx in enumerate(_SKILL_NAME_INDICES):
        assert -len(_ODD_SKILL_NAMES) <= idx < NUM_OBJECTS, (skill, idx)
        if idx > 0:
            assert OBJECTS[idx].name is not None, (skill, idx)
        elif idx < 0 and idx != -1:  # -1 is the bare-handed special case
            assert 1 <= -idx < len(_ODD_SKILL_NAMES), (skill, idx)
    # the monster preference tables are real weapon/tool/food/gem types
    # (the gray stones in RWERP are GEM_CLASS in the 5.0 table)
    for otyp in RWERP + PWERP + HWEP:
        assert 0 <= otyp < NUM_OBJECTS, otyp
        assert int(OBJECTS[otyp].oclass) in (int(ObjClass.WEAPON),
                                             int(ObjClass.TOOL),
                                             int(ObjClass.FOOD),
                                             int(ObjClass.GEM)), otyp
    # the gem-sling hook in select_rwep fires at DART in RWERP order
    assert RWERP.index(O.DART.value) > RWERP.index(O.LUCKSTONE.value)
    # the level->bonus tables cover every non-restricted level
    for table in (_WPN_HIT_BY_LEVEL, _TWC_HIT_BY_LEVEL,
                  _WPN_DAM_BY_LEVEL, _TWC_DAM_BY_LEVEL):
        assert set(table) >= {P_UNSKILLED, P_BASIC, P_SKILLED, P_EXPERT}
    # kebabable classes are valid monster classes
    assert all(1 <= mlet < MAXMCLASSES for mlet in _KEBABABLE)
    # the extra-damage tables reference real weapons/venoms
    for otyp in set(_DMG_EXTRA_LARGE) | set(_DMG_EXTRA_SMALL):
        assert 0 <= otyp < NUM_OBJECTS, otyp


_validate()


__all__ = [
    # structural shapes
    "ObjLike", "MonLike",
    # skills.h
    "P_ISRESTRICTED", "P_UNSKILLED", "P_BASIC", "P_SKILLED", "P_EXPERT",
    "P_MASTER", "P_GRAND_MASTER", "P_FIRST_WEAPON", "P_LAST_WEAPON",
    "P_FIRST_SPELL", "P_LAST_SPELL", "P_FIRST_H_TO_H", "P_LAST_H_TO_H",
    "P_SKILL_LIMIT", "practice_needed_to_advance", "DefSkill", "Skills",
    "skill_name", "skill_level_name",
    # obj.h predicates
    "weapon_type", "is_ammo", "is_launcher", "is_weptool", "is_blade",
    "is_sword", "is_axe", "is_pick", "is_spear", "is_pole", "is_missile",
    "is_multigen", "is_blunt_weapon", "bimanual", "is_wet_towel",
    "is_graystone", "is_poisonable", "matching_launcher",
    "ammo_and_launcher", "greatest_erosion",
    # hit/damage
    "CombatCtx", "PM_SHADE", "HIT_BONUS_SOURCES", "hitval",
    "DMG_BONUS_SOURCES", "dmgval",
    "WT_IRON_BALL_INCR", "WT_IRON_BALL_BASE",
    # ability bonuses
    "STR18", "abon", "dbon",
    # towels
    "wet_a_towel", "dry_a_towel",
    # skill system
    "slots_required", "can_advance", "could_advance", "peaked_skill",
    "advance_skill", "use_skill", "add_weapon_skill", "lose_weapon_skill",
    "drain_weapon_skill", "unrestrict_weapon_skill", "skill_init",
    "weapon_hit_bonus", "weapon_dam_bonus", "uwep_skill_type",
    "weapon_descr",
    # monster weapon data + stubs
    "NEED_WEAPON", "NEED_HTH_WEAPON", "NEED_RANGED_WEAPON", "NEED_PICK_AXE",
    "NEED_AXE", "NEED_PICK_OR_AXE", "NO_WEAPON_WANTED",
    "RWERP", "PWERP", "HWEP", "BOLT_LIM", "AKLYS_LIM",
    "ThrowAndReturnWeapon", "ARWEP", "autoreturn_weapon", "monmightthrowwep",
    "select_rwep", "select_hwep", "possibly_unwield", "mon_wield_item",
    "mwepgone", "setmnotwielded", "special_dmgval", "silver_sears",
    "SKILL_RANGES", "add_skills_to_menu", "show_skills",
    "enhance_weapon_skill",
]
