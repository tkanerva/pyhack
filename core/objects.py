"""Object type table (port of src/objects.c + include/objects.h).

In the C source the table lives in include/objects.h and is expanded
three different ways (enum / description array / struct array) by
preprocessor macros.  This module is the single Python home for all of
that:

- `ObjClass`    -- object classes (defsym.h, OBJCLASS_CLASS_ENUM)
- `Material`    -- object materials (objclass.h)
- `Prop`        -- intrinsic properties conveyed (prop.h)
- `Skill`       -- weapon/spell skills (skills.h)
- `ObjType`     -- the per-type enum (objects.h, OBJECTS_ENUM); C
                   numbering is preserved exactly, including the
                   generic-class slots [1..17] and the markers
                   (FIRST_OBJECT, FIRST_AMULET, LAST_SPELL, ...)
- `Object`      -- one row of the `objects[]` table
                   (struct objclass in objclass.h)
- `OBJECTS`     -- the table itself, in C order
- `BASES`       -- per-class base indices (C: svb.bases[] from
                   init_objects()); the first row of each class, with
                   a fencepost at [MAXOCLASSES]

The two large tables -- the `_OBJTYPE_NAMES` name tuple and the
`OBJECTS` row list -- live in objects_data.py so this module stays
readable; they are imported back below, once the `Object` row type
and the builder functions the rows use are defined.

Adaptations (documented, not bugs):

- The `ctnr` (container) bit of the C BITS() macro maps to a dead
  struct slot in 5.0 (container-ness is the LARGE_BOX..BAG_OF_TRICKS
  otyp range, see is_container()); it is dropped here.
- The C fencepost `objects[NUM_OBJECTS]` (NULL name terminator) is
  omitted; Python lists need no sentinel.
- `oc_dir` is overloaded in C: zap style (NODIR/IMMEDIATE/RAY) for
  wands/spells and strike mode (PIERCE/SLASH/WHACK bitmask) for
  weapons.  Both constant sets are defined; interpret per class.
- Runtime-only fields of struct objclass (oc_uname, discovery counters)
  are not part of the table; instances keep their own copies.
- SCR_MAIL is compiled out here, as in non-MAIL builds of NetHack.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# ------------------------------------------------------------
# Colors (color.h)
# ------------------------------------------------------------

CLR_BLACK = 0
CLR_RED = 1
CLR_GREEN = 2
CLR_BROWN = 3
CLR_BLUE = 4
CLR_MAGENTA = 5
CLR_CYAN = 6
CLR_GRAY = 7
NO_COLOR = 8
CLR_ORANGE = 9
CLR_BRIGHT_GREEN = 10
CLR_YELLOW = 11
CLR_BRIGHT_BLUE = 12
CLR_BRIGHT_MAGENTA = 13
CLR_BRIGHT_CYAN = 14
CLR_WHITE = 15

# the "high" aliases are configuration defaults in C; we keep the
# standard values
HI_METAL = CLR_CYAN
HI_COPPER = CLR_YELLOW
HI_SILVER = CLR_GRAY
HI_GOLD = CLR_YELLOW
HI_LEATHER = CLR_BROWN
HI_CLOTH = CLR_BROWN
HI_ORGANIC = CLR_BROWN
HI_WOOD = CLR_BROWN
HI_PAPER = CLR_WHITE
HI_GLASS = CLR_BRIGHT_CYAN
HI_MINERAL = CLR_GRAY
DRAGON_SILVER = CLR_BRIGHT_CYAN


# ------------------------------------------------------------
# Object classes (defsym.h)
# ------------------------------------------------------------

class ObjClass(IntEnum):
    RANDOM = 0        # used for generating random objects
    ILLOBJ = 1
    WEAPON = 2
    ARMOR = 3
    RING = 4
    AMULET = 5
    TOOL = 6
    FOOD = 7
    POTION = 8
    SCROLL = 9
    SPBOOK = 10
    WAND = 11
    COIN = 12
    GEM = 13
    ROCK = 14
    BALL = 15
    CHAIN = 16
    VENOM = 17

MAXOCLASSES = 18


# ------------------------------------------------------------
# Materials (objclass.h)
# ------------------------------------------------------------

class Material(IntEnum):
    NO_MATERIAL = 0
    LIQUID = 1
    WAX = 2
    VEGGY = 3
    FLESH = 4
    PAPER = 5
    CLOTH = 6
    LEATHER = 7
    WOOD = 8
    BONE = 9
    DRAGON_HIDE = 10
    IRON = 11
    METAL = 12
    COPPER = 13
    SILVER = 14
    GOLD = 15
    PLATINUM = 16
    MITHRIL = 17
    PLASTIC = 18
    GLASS = 19
    GEMSTONE = 20
    MINERAL = 21


# ------------------------------------------------------------
# Intrinsic properties conveyed (prop.h)
# ------------------------------------------------------------

class Prop(IntEnum):
    FIRE_RES = 1
    COLD_RES = 2
    SLEEP_RES = 3
    DISINT_RES = 4
    SHOCK_RES = 5
    POISON_RES = 6
    ACID_RES = 7
    STONE_RES = 8
    DRAIN_RES = 9
    SICK_RES = 10
    INVULNERABLE = 11
    ANTIMAGIC = 12
    STUNNED = 13
    CONFUSION = 14
    BLINDED = 15
    DEAF = 16
    SICK = 17
    STONED = 18
    STRANGLED = 19
    VOMITING = 20
    GLIB = 21
    SLIMED = 22
    HALLUC = 23
    HALLUC_RES = 24
    FUMBLING = 25
    WOUNDED_LEGS = 26
    SLEEPY = 27
    HUNGER = 28
    SEE_INVIS = 29
    TELEPAT = 30
    WARNING = 31
    WARN_OF_MON = 32
    WARN_UNDEAD = 33
    SEARCHING = 34
    CLAIRVOYANT = 35
    INFRAVISION = 36
    DETECT_MONSTERS = 37
    BLND_RES = 38
    ADORNED = 39
    INVIS = 40
    DISPLACED = 41
    STEALTH = 42
    AGGRAVATE_MONSTER = 43
    CONFLICT = 44
    JUMPING = 45
    TELEPORT = 46
    TELEPORT_CONTROL = 47
    LEVITATION = 48
    FLYING = 49
    WWALKING = 50
    SWIMMING = 51
    MAGICAL_BREATHING = 52
    PASSES_WALLS = 53
    SLOW_DIGESTION = 54
    HALF_SPDAM = 55
    HALF_PHDAM = 56
    REGENERATION = 57
    ENERGY_REGENERATION = 58
    PROTECTION = 59
    PROT_FROM_SHAPE_CHANGERS = 60
    POLYMORPH = 61
    POLYMORPH_CONTROL = 62
    UNCHANGING = 63
    FAST = 64
    REFLECTING = 65
    FREE_ACTION = 66
    FIXED_ABIL = 67
    LIFESAVED = 68


# ------------------------------------------------------------
# Worn-slot masks (prop.h)
# ------------------------------------------------------------
# The worn state lives on the item itself (Item.owornmask): a bitmask
# over these W_* bits.  core.worn scans the carrier's inventory for the
# bits (which_armor / setworn) -- the exact C mechanism (prop.h +
# src/worn.c), used for the hero and future monsters alike.  C values
# preserved exactly.

W_ARM = 0x00000001      # Body armor
W_ARMC = 0x00000002     # Cloak
W_ARMH = 0x00000004     # Helmet/hat
W_ARMS = 0x00000008     # Shield
W_ARMG = 0x00000010     # Gloves/gauntlets
W_ARMF = 0x00000020     # Footwear
W_ARMU = 0x00000040     # Undershirt
W_ARMOR = W_ARM | W_ARMC | W_ARMH | W_ARMS | W_ARMG | W_ARMF | W_ARMU

W_WEP = 0x00000100      # Wielded weapon
W_QUIVER = 0x00000200   # Quiver for (f)iring ammo
W_SWAPWEP = 0x00000400  # Secondary weapon
W_WEAPONS = W_WEP | W_SWAPWEP | W_QUIVER

W_AMUL = 0x00010000     # Amulet
W_RINGL = 0x00020000    # Left ring
W_RINGR = 0x00040000    # Right ring
W_RING = W_RINGL | W_RINGR
W_TOOL = 0x00080000     # Eyewear
W_ACCESSORY = W_RING | W_AMUL | W_TOOL


# ------------------------------------------------------------
# Skills (skills.h) -- used as oc_subtyp (oc_skill / oc_armcat)
# ------------------------------------------------------------

class Skill(IntEnum):
    P_NONE = 0
    P_DAGGER = 1
    P_KNIFE = 2
    P_AXE = 3
    P_PICK_AXE = 4
    P_SHORT_SWORD = 5
    P_BROAD_SWORD = 6
    P_LONG_SWORD = 7
    P_TWO_HANDED_SWORD = 8
    P_SABER = 9
    P_CLUB = 10
    P_MACE = 11
    P_MORNING_STAR = 12
    P_FLAIL = 13
    P_HAMMER = 14
    P_QUARTERSTAFF = 15
    P_POLEARMS = 16
    P_SPEAR = 17
    P_TRIDENT = 18
    P_LANCE = 19
    P_BOW = 20
    P_SLING = 21
    P_CROSSBOW = 22
    P_DART = 23
    P_SHURIKEN = 24
    P_BOOMERANG = 25
    P_WHIP = 26
    P_UNICORN_HORN = 27
    P_ATTACK_SPELL = 28
    P_HEALING_SPELL = 29
    P_DIVINATION_SPELL = 30
    P_ENCHANTMENT_SPELL = 31
    P_CLERIC_SPELL = 32
    P_ESCAPE_SPELL = 33
    P_MATTER_SPELL = 34
    P_BARE_HANDED_COMBAT = 35
    P_TWO_WEAPON_COMBAT = 36
    P_RIDING = 37

P_NUM_SKILLS = 38

# armor categories (objclass.h enum obj_armor_types)
ARM_SUIT, ARM_SHIELD, ARM_HELM, ARM_GLOVES = 0, 1, 2, 3
ARM_BOOTS, ARM_CLOAK, ARM_SHIRT = 4, 5, 6

# oc_dir values: zap style for wands/spells, strike mode for weapons
NODIR, IMMEDIATE, RAY = 1, 2, 3
PIERCE, SLASH, WHACK = 1, 2, 4


# ------------------------------------------------------------
# The table row (struct objclass)
# ------------------------------------------------------------

@dataclass(frozen=True)
class Object:
    name: str                    # actual name (None = no description)
    descr: str                   # description when name unknown
    oprop: int = 0               # intrinsic property conveyed
    oclass: int = ObjClass.ILLOBJ
    delay: int = 0               # delay when using such an object
    color: int = CLR_GRAY
    prob: int = 0                # probability, used in mkobj()
    weight: int = 0              # encumbrance (1 cn = 0.1 lb.)
    cost: int = 0                # base cost in shops
    wsdam: int = 0               # max small monster damage (weapons)
    wldam: int = 0               # max large monster damage
    oc1: int = 0                 # hit bonus / armor AC
    oc2: int = 0                 # armor "can" / spell level
    nutrition: int = 0           # food value
    # the BITS() bitfields
    name_known: bool = False     # oc_name_known
    merge: bool = False          # oc_merge
    uses_known: bool = False     # oc_uses_known
    magic: bool = False          # oc_magic
    charged: bool = False        # oc_charged
    unique: bool = False         # oc_unique
    nowish: bool = False         # oc_nowish
    big: bool = False            # oc_big (bimanual/bulky)
    tough: bool = False          # oc_tough (hard gems/rings)
    dir: int = 0                 # zap style or strike mode (overloaded)
    material: int = Material.NO_MATERIAL
    subtyp: int = 0              # oc_skill / oc_armcat

    # C macro convenience overloads
    @property
    def hitbon(self) -> int:
        return self.oc1

    @property
    def armor_ac(self) -> int:
        return self.oc1

    @property
    def spell_level(self) -> int:
        return self.oc2

    @property
    def bimanual(self) -> bool:
        return self.big


# ------------------------------------------------------------
# Builders mirroring the C macros in objects.h
# ------------------------------------------------------------

def _hardgem(mohs: int) -> bool:
    return mohs >= 8


def _generic(descr: str, cls: int) -> Object:
    # GENERIC(): unique, no prob/weight/cost/damage, gray
    return Object(name=f"generic {descr}", descr=descr,
                  unique=True, oclass=cls, color=CLR_GRAY)


def _weapon(name, descr, kn, mg, bi, prob, wt, cost, sdam, ldam, hitbon,
            typ, sub, metal, color) -> Object:
    # WEAPON(): BITS(kn, mg, 1, -, 0, 1, 0, 0, bi, 0, typ, sub, metal)
    return Object(name=name, descr=descr,
                  name_known=kn, merge=mg, uses_known=True, charged=True,
                  big=bi, dir=typ, material=metal, subtyp=sub,
                  oclass=ObjClass.WEAPON, prob=prob, weight=wt, cost=cost,
                  wsdam=sdam, wldam=ldam, oc1=hitbon, nutrition=wt,
                  color=color)


def _projectile(name, descr, kn, prob, wt, cost, sdam, ldam, hitbon,
                metal, sub, color) -> Object:
    # PROJECTILE(): BITS(kn, 1, 1, -, 0, 1, 0, 0, 0, 0, PIERCE, sub, metal)
    return _weapon(name, descr, kn, True, False, prob, wt, cost, sdam,
                   ldam, hitbon, PIERCE, sub, metal, color)


def _bow(name, descr, kn, prob, wt, cost, hitbon, metal, sub,
         color) -> Object:
    # BOW(): BITS(kn, 0, 1, -, 0, 1, 0, 0, 0, 0, 0, sub, metal);
    # sdam=ldam=2
    return _weapon(name, descr, kn, False, False, prob, wt, cost, 2, 2,
                   hitbon, 0, sub, metal, color)


def _armor(name, descr, kn, mgc, blk, power, prob, delay, wt, cost, ac,
           can, sub, metal, color) -> Object:
    # ARMOR(): BITS(kn, 0, 1, -, mgc, 1, 0, 0, blk, 0, 0, sub, metal);
    # oc1 = 10 - ac  (a_ac), oc2 = can (a_can), nutrition = weight
    return Object(name=name, descr=descr, oprop=power, oclass=ObjClass.ARMOR,
                  delay=delay, color=color, prob=prob, weight=wt, cost=cost,
                  oc1=10 - ac, oc2=can, nutrition=wt,
                  name_known=kn, uses_known=True, magic=mgc, charged=True,
                  big=blk, material=metal, subtyp=sub)


def _helmet(name, descr, kn, mgc, power, prob, delay, wt, cost, ac, can,
            metal, color) -> Object:
    return _armor(name, descr, kn, mgc, False, power, prob, delay, wt, cost,
                  ac, can, ARM_HELM, metal, color)


def _cloak(name, descr, kn, mgc, power, prob, delay, wt, cost, ac, can,
           metal, color) -> Object:
    return _armor(name, descr, kn, mgc, False, power, prob, delay, wt, cost,
                  ac, can, ARM_CLOAK, metal, color)


def _shield(name, descr, kn, mgc, blk, power, prob, delay, wt, cost, ac, can,
            metal, color) -> Object:
    return _armor(name, descr, kn, mgc, blk, power, prob, delay, wt, cost,
                  ac, can, ARM_SHIELD, metal, color)


def _gloves(name, descr, kn, mgc, power, prob, delay, wt, cost, ac, can,
            metal, color) -> Object:
    return _armor(name, descr, kn, mgc, False, power, prob, delay, wt, cost,
                  ac, can, ARM_GLOVES, metal, color)


def _boots(name, descr, kn, mgc, power, prob, delay, wt, cost, ac, can,
           metal, color) -> Object:
    return _armor(name, descr, kn, mgc, False, power, prob, delay, wt, cost,
                  ac, can, ARM_BOOTS, metal, color)


def _ring(name, stone, power, cost, mgc, spec, mohs, metal, color) -> Object:
    # RING(): BITS(0, 0, spec, -, mgc, spec, 0, 0, 0, HARDGEM(mohs), 0,
    #              P_NONE, metal); prob=1, wt=3, nutrition=15
    return Object(name=name, descr=stone, oprop=power, oclass=ObjClass.RING,
                  color=color, prob=1, weight=3, cost=cost, nutrition=15,
                  uses_known=spec, magic=mgc, charged=spec,
                  tough=_hardgem(mohs), material=metal)


def _amulet(name, descr, power, prob) -> Object:
    # AMULET(): BITS(0, 0, 0, -, 1, 0, 0, 0, 0, 0, 0, P_NONE, IRON);
    # wt=20, cost=150, nutrition=20, HI_METAL
    return Object(name=name, descr=descr, oprop=power,
                  oclass=ObjClass.AMULET, color=HI_METAL, prob=prob,
                  weight=20, cost=150, nutrition=20, magic=True,
                  material=Material.IRON)


def _tool(name, descr, kn, mrg, mgc, chg, prob, wt, cost, mat, color) -> Object:
    # TOOL(): BITS(kn, mrg, chg, -, mgc, chg, 0, 0, 0, 0, 0, P_NONE, mat);
    # nutrition = weight
    return Object(name=name, descr=descr, oclass=ObjClass.TOOL, color=color,
                  prob=prob, weight=wt, cost=cost, nutrition=wt,
                  name_known=kn, merge=mrg, uses_known=chg, magic=mgc,
                  charged=chg, material=mat)


def _container(name, descr, kn, mgc, chg, prob, wt, cost, mat, color) -> Object:
    # CONTAINER(): BITS(kn, 0, chg, 1, mgc, chg, ...) -- the container bit
    # is dead in 5.0 (see module docstring)
    return _tool(name, descr, kn, False, mgc, chg, prob, wt, cost, mat, color)


def _eyewear(name, descr, kn, prop, prob, wt, cost, mat, color) -> Object:
    # EYEWEAR(): BITS(kn, 0, 0, -, 0, 0, ...); oprop = prop
    o = _tool(name, descr, kn, False, False, False, prob, wt, cost, mat, color)
    return Object(**{**o.__dict__, "oprop": prop})


def _weptool(name, descr, kn, mgc, bi, prob, wt, cost, sdam, ldam, strike,
             sub, mat, color) -> Object:
    # WEPTOOL(): BITS(kn, 0, 1, -, mgc, 1, 0, 0, bi, 0, strike, sub, mat);
    # note: the C "hitbon" slot gets the strike mode (oc1 is only read
    # for weapons), dir gets it too
    return Object(name=name, descr=descr, oclass=ObjClass.TOOL, color=color,
                  prob=prob, weight=wt, cost=cost, wsdam=sdam, wldam=ldam,
                  oc1=strike, nutrition=wt,
                  name_known=kn, uses_known=True, magic=mgc, charged=True,
                  big=bi, dir=strike, material=mat, subtyp=sub)


def _food(name, prob, delay, wt, unk, mat, nutrition, color) -> Object:
    # FOOD(): BITS(1, 1, unk, -, 0, 0, ...); descr = NoDes (None);
    # cost = nutrition/20 + 5
    return Object(name=name, descr=None, oclass=ObjClass.FOOD, color=color,
                  prob=prob, delay=delay, weight=wt,
                  cost=nutrition // 20 + 5, nutrition=nutrition,
                  name_known=True, merge=True, uses_known=unk, material=mat)


def _potion(name, descr, mgc, power, prob, cost, color) -> Object:
    # POTION(): BITS(0, 1, 0, -, mgc, 0, ...); wt=20, nutrition=10
    return Object(name=name, descr=descr, oprop=power,
                  oclass=ObjClass.POTION, color=color, prob=prob,
                  weight=20, cost=cost, nutrition=10, merge=True,
                  magic=mgc, material=Material.GLASS)


def _scroll(name, text, mgc, prob, cost) -> Object:
    # SCROLL(): BITS(0, 1, 0, -, mgc, 0, ...); wt=5, nutrition=6, HI_PAPER
    return Object(name=name, descr=text, oclass=ObjClass.SCROLL,
                  color=HI_PAPER, prob=prob, weight=5, cost=cost,
                  nutrition=6, merge=True, magic=mgc,
                  material=Material.PAPER)


def _spell(name, descr, sub, prob, delay, level, mgc, dir, color,
           mat=None) -> Object:
    # SPELL(): BITS(0, 0, 0, -, mgc, 0, 0, 0, 0, 0, dir, sub, PAPER);
    # wt=50, cost = level*100, oc2 = level, nutrition=20.
    # "dig" uses LEATHER pages (see the C note); pass mat=Material.LEATHER.
    if mat is None:
        mat = Material.PAPER
    return Object(name=name, descr=descr, oclass=ObjClass.SPBOOK,
                  color=color, prob=prob, delay=delay, weight=50,
                  cost=level * 100, oc2=level, nutrition=20,
                  magic=mgc, dir=dir, material=mat, subtyp=sub)


def _wand(name, typ, prob, cost, mgc, dir, metal, color) -> Object:
    # WAND(): BITS(0, 0, 1, -, mgc, 1, ...); wt=7, nutrition=30
    return Object(name=name, descr=typ, oclass=ObjClass.WAND, color=color,
                  prob=prob, weight=7, cost=cost, nutrition=30,
                  uses_known=True, magic=mgc, charged=True, dir=dir,
                  material=metal)


def _coin(name, prob, metal, worth) -> Object:
    # COIN(): BITS(1, 1, 0, -, 0, 0, ...); descr is NoDes (None);
    # wt=1, nutrition=0, HI_GOLD
    return Object(name=name, descr=None, oclass=ObjClass.COIN, color=HI_GOLD,
                  prob=prob, weight=1, cost=worth,
                  name_known=True, merge=True, material=metal)


def _gem(name, desc, prob, wt, gval, nutr, mohs, mat, color) -> Object:
    # GEM(): BITS(0, 1, 0, -, 0, 0, 0, 0, 0, HARDGEM(mohs), 0, -P_SLING,
    #            mat); sdam=ldam=3
    return Object(name=name, descr=desc, oclass=ObjClass.GEM, color=color,
                  prob=prob, weight=wt, cost=gval, wsdam=3, wldam=3,
                  nutrition=nutr, merge=True, tough=_hardgem(mohs),
                  material=mat, subtyp=-Skill.P_SLING)


def _rock(name, desc, kn, prob, wt, gval, sdam, ldam, mgc, nutr, mohs,
          mat, color) -> Object:
    # ROCK(): BITS(kn, 1, 0, -, mgc, 0, 0, 0, 0, HARDGEM(mohs), 0, -P_SLING,
    #             mat)
    return Object(name=name, descr=desc, oclass=ObjClass.GEM, color=color,
                  prob=prob, weight=wt, cost=gval, wsdam=sdam, wldam=ldam,
                  nutrition=nutr, name_known=kn, merge=True, magic=mgc,
                  tough=_hardgem(mohs), material=mat,
                  subtyp=-Skill.P_SLING)


# ------------------------------------------------------------
# The object tables (C: objects.h)
#
# The two large tables -- the _OBJTYPE_NAMES name tuple and the
# OBJECTS row list -- live in objects_data.py.  They are imported
# here, late, because the rows are built with the `Object` dataclass
# and the builder functions defined above.  The rows are written in
# exactly the order of include/objects.h so the index of every row
# equals its ObjType value.
from .objects_data import OBJECTS, _OBJTYPE_NAMES  # noqa: E402


# ------------------------------------------------------------
# The object type enum (objects.h, OBJECTS_ENUM)
# ------------------------------------------------------------
# C numbering preserved: slot 0 is the real strange object, slots
# 1..17 are the generic class placeholders.  (The old demo core's
# coarse-grained core.types.ObjectType is replaced by this enum as
# each system gets re-ported on the real table.)

ObjType = IntEnum("ObjType", {n: i for i, n in enumerate(_OBJTYPE_NAMES)})
O = ObjType  # short alias for table lookups

# C enum markers
LAST_GENERIC = ObjType.GENERIC_VENOM.value
FIRST_OBJECT = LAST_GENERIC + 1
OBJCLASS_HACK = FIRST_OBJECT - 1
FIRST_AMULET = ObjType.AMULET_OF_ESP.value
LAST_AMULET = ObjType.AMULET_OF_YENDOR.value
FIRST_SPELL = ObjType.SPE_DIG.value
LAST_SPELL = ObjType.SPE_BLANK_PAPER.value
FIRST_REAL_GEM = ObjType.DILITHIUM_CRYSTAL.value
LAST_REAL_GEM = ObjType.JADE.value
FIRST_GLASS_GEM = ObjType.WORTHLESS_WHITE_GLASS.value
LAST_GLASS_GEM = ObjType.WORTHLESS_VIOLET_GLASS.value
NUM_OBJECTS = len(_OBJTYPE_NAMES)


# ------------------------------------------------------------
# Class base indices (C: svb.bases[] from init_objects())
#
# bases[oclass] is the index of the first object of that class in
# OBJECTS, so a class's rows run bases[oclass] .. bases[oclass+1]-1;
# bases[MAXOCLASSES] is the fencepost NUM_OBJECTS.
#
# Documented deviation from C: the gap-fill (C applies it to every
# class without rows) is skipped for ILLOBJ, whose base stays at the
# strange object (0).  C's fill-forward would overwrite it with
# bases[WEAPON] (18) because the generic placeholders [1..17] are
# excluded from the scan; the strange object IS the only real
# ILLOBJ-class object, so 0 is the truthful base (bases[RANDOM]
# follows it).
# ------------------------------------------------------------

def _compute_bases() -> "list[int]":
    bases = [0] * (MAXOCLASSES + 1)
    first = FIRST_OBJECT
    prevoclass = -1
    while first < NUM_OBJECTS:
        oclass = int(OBJECTS[first].oclass)
        if oclass < prevoclass:
            raise ValueError(
                f"objects[{first}] class #{oclass} not in order!")
        last = first + 1
        while last < NUM_OBJECTS and int(OBJECTS[last].oclass) == oclass:
            last += 1
        bases[oclass] = first
        first = last
        prevoclass = oclass
    bases[MAXOCLASSES] = NUM_OBJECTS
    # guarantee no gaps (C: fill forward from the end); the ILLOBJ
    # gap is the documented deviation above
    for last in range(MAXOCLASSES - 1, -1, -1):
        if not bases[last] and last != int(ObjClass.ILLOBJ):
            bases[last] = bases[last + 1]
    return bases


BASES: "list[int]" = _compute_bases()


# ------------------------------------------------------------
# Import-time sanity checks (C: o_init.c init_objects())
# ------------------------------------------------------------

def _validate() -> None:
    assert len(OBJECTS) == NUM_OBJECTS, (
        f"objects table has {len(OBJECTS)} rows, expected {NUM_OBJECTS}")
    for i, o in enumerate(OBJECTS):
        assert o.name is None or o.name, f"row {i} has no name"
        assert int(o.oclass) < MAXOCLASSES, f"row {i} bad class {o.oclass}"
        assert int(o.material) <= int(Material.MINERAL), \
            f"row {i} bad material {o.material}"
    # slots [1..17] must be the generic placeholders
    for i in range(1, MAXOCLASSES):
        assert OBJECTS[i].oclass == i, f"generic slot {i} wrong class"
        assert OBJECTS[i].unique, f"generic slot {i} not unique"
    # ammo/launcher pairing: negative skill of ammo = positive of launcher
    for name in ("ARROW", "CROSSBOW_BOLT", "DART", "SHURIKEN",
                 "BOOMERANG"):
        t = ObjType[name]
        assert OBJECTS[t.value].subtyp < 0
    # the Amulet must be last among amulets, and the fake before the real
    assert OBJECTS[LAST_AMULET].name == "Amulet of Yendor"
    assert OBJECTS[LAST_AMULET - 1].name == \
        "cheap plastic imitation of the Amulet of Yendor"
    # BASES: first row of every real class, fencepost at the end
    assert BASES[MAXOCLASSES] == NUM_OBJECTS
    for cls in range(1, MAXOCLASSES):
        assert int(OBJECTS[BASES[cls]].oclass) == cls, \
            f"BASES[{cls}] points at the wrong class"


_validate()


def object_type(otyp: "ObjType | int") -> Object:
    """The table row for an object type (C: objects[otyp])."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    return OBJECTS[otyp]


__all__ = [
    "ObjClass", "Material", "Prop", "Skill", "ObjType", "O", "Object",
    "OBJECTS", "BASES", "object_type", "MAXOCLASSES", "NUM_OBJECTS",
    "LAST_GENERIC", "FIRST_OBJECT", "OBJCLASS_HACK", "FIRST_AMULET",
    "LAST_AMULET", "FIRST_SPELL", "LAST_SPELL", "FIRST_REAL_GEM",
    "LAST_REAL_GEM", "FIRST_GLASS_GEM", "LAST_GLASS_GEM",
    "NODIR", "IMMEDIATE", "RAY", "PIERCE", "SLASH", "WHACK",
    "ARM_SUIT", "ARM_SHIELD", "ARM_HELM", "ARM_GLOVES", "ARM_BOOTS",
    "ARM_CLOAK", "ARM_SHIRT",
    "W_ARM", "W_ARMC", "W_ARMH", "W_ARMS", "W_ARMG", "W_ARMF", "W_ARMU",
    "W_ARMOR", "W_WEP", "W_QUIVER", "W_SWAPWEP", "W_WEAPONS", "W_AMUL",
    "W_RINGL", "W_RINGR", "W_RING", "W_TOOL", "W_ACCESSORY",
    "CLR_BLACK", "CLR_RED", "CLR_GREEN", "CLR_BROWN", "CLR_BLUE",
    "CLR_MAGENTA", "CLR_CYAN", "CLR_GRAY", "NO_COLOR", "CLR_ORANGE",
    "CLR_BRIGHT_GREEN", "CLR_YELLOW", "CLR_BRIGHT_BLUE",
    "CLR_BRIGHT_MAGENTA", "CLR_BRIGHT_CYAN", "CLR_WHITE",
    "HI_METAL", "HI_COPPER", "HI_SILVER", "HI_GOLD", "HI_LEATHER",
    "HI_CLOTH", "HI_ORGANIC", "HI_WOOD", "HI_PAPER", "HI_GLASS",
    "HI_MINERAL", "DRAGON_SILVER",
]
