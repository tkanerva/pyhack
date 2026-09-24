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
from enum import Enum, IntEnum

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
# The object type enum (objects.h, OBJECTS_ENUM)
# ------------------------------------------------------------
# C numbering preserved: slot 0 is the real strange object, slots
# 1..17 are the generic class placeholders.  (The old demo core's
# coarse-grained core.types.ObjectType is replaced by this enum as
# each system gets re-ported on the real table.)

_OBJTYPE_NAMES = (
    "STRANGE_OBJECT",
    "GENERIC_ILLOBJ", "GENERIC_WEAPON", "GENERIC_ARMOR", "GENERIC_RING",
    "GENERIC_AMULET", "GENERIC_TOOL", "GENERIC_FOOD", "GENERIC_POTION",
    "GENERIC_SCROLL", "GENERIC_SPBOOK", "GENERIC_WAND", "GENERIC_COIN",
    "GENERIC_GEM", "GENERIC_ROCK", "GENERIC_BALL", "GENERIC_CHAIN",
    "GENERIC_VENOM",
    # weapons
    "ARROW", "ELVEN_ARROW", "ORCISH_ARROW", "SILVER_ARROW", "YA",
    "CROSSBOW_BOLT",
    "DART", "SHURIKEN", "BOOMERANG",
    "SPEAR", "ELVEN_SPEAR", "ORCISH_SPEAR", "DWARVISH_SPEAR",
    "SILVER_SPEAR", "JAVELIN",
    "TRIDENT",
    "DAGGER", "ELVEN_DAGGER", "ORCISH_DAGGER", "SILVER_DAGGER", "ATHAME",
    "SCALPEL", "KNIFE", "STILETTO", "WORM_TOOTH", "CRYSKNIFE",
    "AXE", "BATTLE_AXE",
    "SHORT_SWORD", "ELVEN_SHORT_SWORD", "ORCISH_SHORT_SWORD",
    "DWARVISH_SHORT_SWORD", "SCIMITAR", "SILVER_SABER", "BROADSWORD",
    "ELVEN_BROADSWORD", "LONG_SWORD", "TWO_HANDED_SWORD", "KATANA",
    "TSURUGI", "RUNESWORD",
    "PARTISAN", "RANSEUR", "SPETUM", "GLAIVE", "HALBERD", "BARDICHE",
    "VOULGE", "FAUCHARD", "GUISARME", "BILL_GUISARME", "LUCERN_HAMMER",
    "BEC_DE_CORBIN",
    "DWARVISH_MATTOCK", "LANCE",
    "MACE", "SILVER_MACE", "MORNING_STAR", "WAR_HAMMER", "CLUB",
    "RUBBER_HOSE", "QUARTERSTAFF", "AKLYS", "FLAIL", "BULLWHIP",
    "BOW", "ELVEN_BOW", "ORCISH_BOW", "YUMI", "SLING", "CROSSBOW",
    # armor
    "ELVEN_LEATHER_HELM", "ORCISH_HELM", "DWARVISH_IRON_HELM", "FEDORA",
    "CORNUTHAUM", "DUNCE_CAP", "DENTED_POT", "HELM_OF_BRILLIANCE",
    "HELMET", "HELM_OF_CAUTION", "HELM_OF_OPPOSITE_ALIGNMENT",
    "HELM_OF_TELEPATHY",
    "GRAY_DRAGON_SCALE_MAIL", "GOLD_DRAGON_SCALE_MAIL",
    "SILVER_DRAGON_SCALE_MAIL", "RED_DRAGON_SCALE_MAIL",
    "WHITE_DRAGON_SCALE_MAIL", "ORANGE_DRAGON_SCALE_MAIL",
    "BLACK_DRAGON_SCALE_MAIL", "BLUE_DRAGON_SCALE_MAIL",
    "GREEN_DRAGON_SCALE_MAIL", "YELLOW_DRAGON_SCALE_MAIL",
    "GRAY_DRAGON_SCALES", "GOLD_DRAGON_SCALES", "SILVER_DRAGON_SCALES",
    "RED_DRAGON_SCALES", "WHITE_DRAGON_SCALES", "ORANGE_DRAGON_SCALES",
    "BLACK_DRAGON_SCALES", "BLUE_DRAGON_SCALES", "GREEN_DRAGON_SCALES",
    "YELLOW_DRAGON_SCALES",
    "PLATE_MAIL", "CRYSTAL_PLATE_MAIL", "BRONZE_PLATE_MAIL",
    "SPLINT_MAIL", "BANDED_MAIL", "DWARVISH_MITHRIL_COAT",
    "ELVEN_MITHRIL_COAT", "CHAIN_MAIL", "ORCISH_CHAIN_MAIL", "SCALE_MAIL",
    "STUDED_LEATHER_ARMOR", "RING_MAIL", "ORCISH_RING_MAIL",
    "LEATHER_ARMOR", "LEATHER_JACKET",
    "HAWAIIAN_SHIRT", "T_SHIRT",
    "MUMMY_WRAPPING", "ELVEN_CLOAK", "ORCISH_CLOAK", "DWARVISH_CLOAK",
    "OILSKIN_CLOAK", "ROBE", "ALCHEMY_SMOCK", "LEATHER_CLOAK",
    "CLOAK_OF_PROTECTION", "CLOAK_OF_INVISIBILITY",
    "CLOAK_OF_MAGIC_RESISTANCE", "CLOAK_OF_DISPLACEMENT",
    "SMALL_SHIELD", "SHIELD_OF_DRAIN_RESISTANCE",
    "SHIELD_OF_SHOCK_RESISTANCE", "ELVEN_SHIELD", "URUK_HAI_SHIELD",
    "ORCISH_SHIELD", "LARGE_SHIELD", "DWARVISH_ROUNDSHIELD",
    "SHIELD_OF_REFLECTION",
    "LEATHER_GLOVES", "GAUNTLETS_OF_FUMBLING", "GAUNTLETS_OF_POWER",
    "GAUNTLETS_OF_DEXTERITY",
    "LOW_BOOTS", "IRON_SHOES", "HIGH_BOOTS", "SPEED_BOOTS",
    "WATER_WALKING_BOOTS", "JUMPING_BOOTS", "ELVEN_BOOTS",
    "KICKING_BOOTS", "FUMBLE_BOOTS", "LEVITATION_BOOTS",
    # rings
    "RIN_ADORNMENT", "RIN_GAIN_STRENGTH", "RIN_GAIN_CONSTITUTION",
    "RIN_INCREASE_ACCURACY", "RIN_INCREASE_DAMAGE", "RIN_PROTECTION",
    "RIN_REGENERATION", "RIN_SEARCHING", "RIN_STEALTH",
    "RIN_SUSTAIN_ABILITY", "RIN_LEVITATION", "RIN_HUNGER",
    "RIN_AGGRAVATE_MONSTER", "RIN_CONFLICT", "RIN_WARNING",
    "RIN_POISON_RESISTANCE", "RIN_FIRE_RESISTANCE",
    "RIN_COLD_RESISTANCE", "RIN_SHOCK_RESISTANCE", "RIN_FREE_ACTION",
    "RIN_SLOW_DIGESTION", "RIN_TELEPORTATION", "RIN_TELEPORT_CONTROL",
    "RIN_POLYMORPH", "RIN_POLYMORPH_CONTROL", "RIN_INVISIBILITY",
    "RIN_SEE_INVISIBLE", "RIN_PROTECTION_FROM_SHAPE_CHAN",
    # amulets
    "AMULET_OF_ESP", "AMULET_OF_LIFE_SAVING", "AMULET_OF_STRANGULATION",
    "AMULET_OF_RESTFUL_SLEEP", "AMULET_VERSUS_POISON", "AMULET_OF_CHANGE",
    "AMULET_OF_UNCHANGING", "AMULET_OF_REFLECTION",
    "AMULET_OF_MAGICAL_BREATHING", "AMULET_OF_GUARDING", "AMULET_OF_FLYING",
    "FAKE_AMULET_OF_YENDOR", "AMULET_OF_YENDOR",
    # tools
    "LARGE_BOX", "CHEST", "ICE_BOX", "SACK", "OILSKIN_SACK",
    "BAG_OF_HOLDING", "BAG_OF_TRICKS",
    "SKELETON_KEY", "LOCK_PICK", "CREDIT_CARD",
    "TALLOW_CANDLE", "WAX_CANDLE", "BRASS_LANTERN", "OIL_LAMP",
    "MAGIC_LAMP",
    "EXPENSIVE_CAMERA", "MIRROR", "CRYSTAL_BALL",
    "LENSES", "BLINDFOLD", "TOWEL",
    "SADDLE", "LEASH", "STETHOSCOPE", "TINNING_KIT", "TIN_OPENER",
    "CAN_OF_GREASE", "FIGURINE", "MAGIC_MARKER",
    "LAND_MINE", "BEARTRAP",
    "TIN_WHISTLE", "MAGIC_WHISTLE", "WOODEN_FLUTE", "MAGIC_FLUTE",
    "TOOLED_HORN", "FROST_HORN", "FIRE_HORN", "HORN_OF_PLENTY",
    "WOODEN_HARP", "MAGIC_HARP", "BELL", "BUGLE", "LEATHER_DRUM",
    "DRUM_OF_EARTHQUAKE",
    "PICK_AXE", "GRAPPLING_HOOK", "UNICORN_HORN",
    "CANDELABRUM_OF_INVOCATION", "BELL_OF_OPENING",
    # food
    "TRIPE_RATION", "CORPSE", "EGG", "MEATBALL", "MEAT_STICK",
    "ENORMOUS_MEATBALL", "MEAT_RING",
    "GLOB_OF_GRAY_OOZE", "GLOB_OF_BROWN_PUDDING", "GLOB_OF_GREEN_SLIME",
    "GLOB_OF_BLACK_PUDDING",
    "KELP_FROND", "EUCALYPTUS_LEAF", "APPLE", "ORANGE", "PEAR", "MELON",
    "BANANA", "CARROT", "SPRIG_OF_WOLFSBANE", "CLOVE_OF_GARLIC",
    "SLIME_MOLD",
    "LUMP_OF_ROYAL_JELLY", "CREAM_PIE", "CANDY_BAR", "FORTUNE_COOKIE",
    "PANCAKE", "LEMBAS_WAFER", "CRAM_RATION", "FOOD_RATION", "K_RATION",
    "C_RATION", "TIN",
    # potions
    "POT_GAIN_ABILITY", "POT_RESTORE_ABILITY", "POT_CONFUSION",
    "POT_BLINDNESS", "POT_PARALYSIS", "POT_SPEED", "POT_LEVITATION",
    "POT_HALLUCINATION", "POT_INVISIBILITY", "POT_SEE_INVISIBLE",
    "POT_HEALING", "POT_EXTRA_HEALING", "POT_GAIN_LEVEL",
    "POT_ENLIGHTENMENT", "POT_MONSTER_DETECTION", "POT_OBJECT_DETECTION",
    "POT_GAIN_ENERGY", "POT_SLEEPING", "POT_FULL_HEALING",
    "POT_POLYMORPH", "POT_BOOZE", "POT_SICKNESS", "POT_FRUIT_JUICE",
    "POT_ACID", "POT_OIL", "POT_WATER",
    # scrolls (SCR_MAIL compiled out, as in non-MAIL builds)
    "SCR_ENCHANT_ARMOR", "SCR_DESTROY_ARMOR", "SCR_CONFUSE_MONSTER",
    "SCR_SCARE_MONSTER", "SCR_REMOVE_CURSE", "SCR_ENCHANT_WEAPON",
    "SCR_CREATE_MONSTER", "SCR_TAMING", "SCR_GENOCIDE", "SCR_LIGHT",
    "SCR_TELEPORTATION", "SCR_GOLD_DETECTION", "SCR_FOOD_DETECTION",
    "SCR_IDENTIFY", "SCR_MAGIC_MAPPING", "SCR_AMNESIA", "SCR_FIRE",
    "SCR_EARTH", "SCR_PUNISHMENT", "SCR_CHARGING", "SCR_STINKING_CLOUD",
    "SC01", "SC02", "SC03", "SC04", "SC05", "SC06", "SC07", "SC08",
    "SC09", "SC10", "SC11", "SC12", "SC13", "SC14", "SC15", "SC16",
    "SC17", "SC18", "SC19", "SC20",
    "SCR_BLANK_PAPER",
    # spellbooks
    "SPE_DIG", "SPE_MAGIC_MISSILE", "SPE_FIREBALL", "SPE_CONE_OF_COLD",
    "SPE_SLEEP", "SPE_FINGER_OF_DEATH", "SPE_LIGHT", "SPE_DETECT_MONSTERS",
    "SPE_HEALING", "SPE_KNOCK", "SPE_FORCE_BOLT", "SPE_CONFUSE_MONSTER",
    "SPE_CURE_BLINDNESS", "SPE_DRAIN_LIFE", "SPE_SLOW_MONSTER",
    "SPE_WIZARD_LOCK", "SPE_CREATE_MONSTER", "SPE_DETECT_FOOD",
    "SPE_CAUSE_FEAR", "SPE_CLAIRVOYANCE", "SPE_CURE_SICKNESS",
    "SPE_CHARM_MONSTER", "SPE_HASTE_SELF", "SPE_DETECT_UNSEEN",
    "SPE_LEVITATION", "SPE_EXTRA_HEALING", "SPE_RESTORE_ABILITY",
    "SPE_INVISIBILITY", "SPE_DETECT_TREASURE", "SPE_REMOVE_CURSE",
    "SPE_MAGIC_MAPPING", "SPE_IDENTIFY", "SPE_TURN_UNDEAD",
    "SPE_POLYMORPH", "SPE_TELEPORT_AWAY", "SPE_CREATE_FAMILIAR",
    "SPE_CANCELLATION", "SPE_PROTECTION", "SPE_JUMPING",
    "SPE_STONE_TO_FLESH", "SPE_CHAIN_LIGHTNING",
    "SPE_BLANK_PAPER",
    "SPE_NOVEL", "SPE_BOOK_OF_THE_DEAD",
    # wands
    "WAN_LIGHT", "WAN_SECRET_DOOR_DETECTION", "WAN_ENLIGHTENMENT",
    "WAN_CREATE_MONSTER", "WAN_WISHING", "WAN_STASIS", "WAN_NOTHING",
    "WAN_STRIKING", "WAN_MAKE_INVISIBLE", "WAN_SLOW_MONSTER",
    "WAN_SPEED_MONSTER", "WAN_UNDEAD_TURNING", "WAN_POLYMORPH",
    "WAN_CANCELLATION", "WAN_TELEPORTATION", "WAN_OPENING", "WAN_LOCKING",
    "WAN_PROBING", "WAN_DIGGING", "WAN_MAGIC_MISSILE", "WAN_FIRE",
    "WAN_COLD", "WAN_SLEEP", "WAN_DEATH", "WAN_LIGHTNING",
    "WAN1", "WAN2", "WAN3",
    # coins
    "GOLD_PIECE",
    # gems & rocks
    "DILITHIUM_CRYSTAL", "DIAMOND", "RUBY", "JACINTH", "SAPPHIRE",
    "BLACK_OPAL", "EMERALD", "TURQUOISE", "CITRINE", "AQUAMARINE",
    "AMBER", "TOPAZ", "JET", "OPAL", "CHRYSOBERYL", "GARNET", "AMETHYST",
    "JASPER", "FLUORITE", "OBSIDIAN", "AGATE", "JADE",
    "WORTHLESS_WHITE_GLASS", "WORTHLESS_BLUE_GLASS",
    "WORTHLESS_RED_GLASS", "WORTHLESS_YELLOWBROWN_GLASS",
    "WORTHLESS_ORANGE_GLASS", "WORTHLESS_YELLOW_GLASS",
    "WORTHLESS_BLACK_GLASS", "WORTHLESS_GREEN_GLASS",
    "WORTHLESS_VIOLET_GLASS",
    "LUCKSTONE", "LOADSTONE", "TOUCHSTONE", "FLINT", "ROCK",
    # misc
    "BOULDER", "STATUE",
    "HEAVY_IRON_BALL", "IRON_CHAIN",
    "BLINDING_VENOM", "ACID_VENOM",
)

ObjType = Enum("ObjType", {n: i for i, n in enumerate(_OBJTYPE_NAMES)})

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
    # COIN(): BITS(1, 1, 0, -, 0, 0, ...); wt=1, nutrition=0, HI_GOLD
    return Object(name=name, descr="", oclass=ObjClass.COIN, color=HI_GOLD,
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
# The table itself (C: struct object objects[])
#
# Rows are written in exactly the order of include/objects.h so the
# index of every row equals its ObjType value.
# ------------------------------------------------------------

OBJECTS: "list[Object]" = [
    # [0] the real strange object (NoDes descr, CLR_BLACK)
    Object(name="strange object", descr=None, name_known=True,
           oclass=ObjClass.ILLOBJ, color=CLR_BLACK),
    # [1..17] generic class placeholders
    _generic("strange", ObjClass.ILLOBJ),
    _generic("weapon", ObjClass.WEAPON),
    _generic("armor", ObjClass.ARMOR),
    _generic("ring", ObjClass.RING),
    _generic("amulet", ObjClass.AMULET),
    _generic("tool", ObjClass.TOOL),
    _generic("food", ObjClass.FOOD),
    _generic("potion", ObjClass.POTION),
    _generic("scroll", ObjClass.SCROLL),
    _generic("spellbook", ObjClass.SPBOOK),
    _generic("wand", ObjClass.WAND),
    _generic("coin", ObjClass.COIN),
    _generic("gem", ObjClass.GEM),
    _generic("large rock", ObjClass.ROCK),
    _generic("iron ball", ObjClass.BALL),
    _generic("iron chain", ObjClass.CHAIN),
    _generic("venom", ObjClass.VENOM),
    # missiles (materiel reflects the arrowhead, not the shaft)
    _projectile("arrow", None, 1, 55, 1, 2, 6, 6, 0,
                Material.IRON, -Skill.P_BOW, HI_METAL),
    _projectile("elven arrow", "runed arrow", 0, 20, 1, 2, 7, 6, 0,
                Material.WOOD, -Skill.P_BOW, HI_WOOD),
    _projectile("orcish arrow", "crude arrow", 0, 20, 1, 2, 5, 6, 0,
                Material.IRON, -Skill.P_BOW, CLR_BLACK),
    _projectile("silver arrow", None, 1, 12, 1, 5, 6, 6, 0,
                Material.SILVER, -Skill.P_BOW, HI_SILVER),
    _projectile("ya", "bamboo arrow", 0, 15, 1, 4, 7, 7, 1,
                Material.METAL, -Skill.P_BOW, HI_METAL),
    _projectile("crossbow bolt", None, 1, 55, 1, 2, 4, 6, 0,
                Material.IRON, -Skill.P_CROSSBOW, HI_METAL),
    # missiles that don't use a launcher
    _weapon("dart", None, 1, 1, 0, 60, 1, 2, 3, 2, 0,
            PIERCE, -Skill.P_DART, Material.IRON, HI_METAL),
    _weapon("shuriken", "throwing star", 0, 1, 0, 35, 1, 5, 8, 6, 2,
            PIERCE, -Skill.P_SHURIKEN, Material.IRON, HI_METAL),
    _weapon("boomerang", None, 1, 1, 0, 15, 5, 20, 9, 9, 0,
            0, -Skill.P_BOOMERANG, Material.WOOD, HI_WOOD),
    # spears
    _weapon("spear", None, 1, 1, 0, 50, 30, 3, 6, 8, 0,
            PIERCE, Skill.P_SPEAR, Material.IRON, HI_METAL),
    _weapon("elven spear", "runed spear", 0, 1, 0, 10, 30, 3, 7, 8, 0,
            PIERCE, Skill.P_SPEAR, Material.WOOD, HI_WOOD),
    _weapon("orcish spear", "crude spear", 0, 1, 0, 13, 30, 3, 5, 8, 0,
            PIERCE, Skill.P_SPEAR, Material.IRON, CLR_BLACK),
    _weapon("dwarvish spear", "stout spear", 0, 1, 0, 12, 35, 3, 8, 8, 0,
            PIERCE, Skill.P_SPEAR, Material.IRON, HI_METAL),
    _weapon("silver spear", None, 1, 1, 0, 2, 36, 40, 6, 8, 0,
            PIERCE, Skill.P_SPEAR, Material.SILVER, HI_SILVER),
    _weapon("javelin", "throwing spear", 0, 1, 0, 10, 20, 3, 6, 6, 0,
            PIERCE, Skill.P_SPEAR, Material.IRON, HI_METAL),
    # spearish; doesn't stack, not intended to be thrown
    _weapon("trident", None, 1, 0, 0, 8, 25, 5, 6, 4, 0,
            PIERCE, Skill.P_TRIDENT, Material.IRON, HI_METAL),
    # blades; all stack
    _weapon("dagger", None, 1, 1, 0, 30, 10, 4, 4, 3, 2,
            PIERCE, Skill.P_DAGGER, Material.IRON, HI_METAL),
    _weapon("elven dagger", "runed dagger", 0, 1, 0, 10, 10, 4, 5, 3, 2,
            PIERCE, Skill.P_DAGGER, Material.WOOD, HI_WOOD),
    _weapon("orcish dagger", "crude dagger", 0, 1, 0, 12, 10, 4, 3, 3, 2,
            PIERCE, Skill.P_DAGGER, Material.IRON, CLR_BLACK),
    _weapon("silver dagger", None, 1, 1, 0, 3, 12, 40, 4, 3, 2,
            PIERCE, Skill.P_DAGGER, Material.SILVER, HI_SILVER),
    _weapon("athame", None, 1, 1, 0, 0, 10, 4, 4, 3, 2,
            SLASH, Skill.P_DAGGER, Material.IRON, HI_METAL),
    _weapon("scalpel", None, 1, 1, 0, 0, 5, 6, 3, 3, 2,
            SLASH, Skill.P_KNIFE, Material.METAL, HI_METAL),
    _weapon("knife", None, 1, 1, 0, 20, 5, 4, 3, 2, 0,
            PIERCE | SLASH, Skill.P_KNIFE, Material.IRON, HI_METAL),
    _weapon("stiletto", None, 1, 1, 0, 5, 5, 4, 3, 2, 0,
            PIERCE | SLASH, Skill.P_KNIFE, Material.IRON, HI_METAL),
    _weapon("worm tooth", None, 1, 1, 0, 0, 20, 2, 2, 2, 0,
            0, Skill.P_KNIFE, Material.BONE, CLR_WHITE),
    _weapon("crysknife", None, 1, 1, 0, 0, 20, 100, 10, 10, 3,
            PIERCE, Skill.P_KNIFE, Material.BONE, CLR_WHITE),
    # axes
    _weapon("axe", None, 1, 0, 0, 40, 60, 8, 6, 4, 0,
            SLASH, Skill.P_AXE, Material.IRON, HI_METAL),
    _weapon("battle-axe", "double-headed axe", 0, 0, 1, 10, 120, 40,
            8, 6, 0, SLASH, Skill.P_AXE, Material.IRON, HI_METAL),
    # swords
    _weapon("short sword", None, 1, 0, 0, 8, 30, 10, 6, 8, 0,
            PIERCE, Skill.P_SHORT_SWORD, Material.IRON, HI_METAL),
    _weapon("elven short sword", "runed short sword", 0, 0, 0, 2, 30, 10,
            8, 8, 0, PIERCE, Skill.P_SHORT_SWORD, Material.WOOD, HI_WOOD),
    _weapon("orcish short sword", "crude short sword", 0, 0, 0, 3, 30, 10,
            5, 8, 0, PIERCE, Skill.P_SHORT_SWORD, Material.IRON, CLR_BLACK),
    _weapon("dwarvish short sword", "broad short sword", 0, 0, 0, 2, 30,
            10, 7, 8, 0, PIERCE, Skill.P_SHORT_SWORD, Material.IRON,
            HI_METAL),
    _weapon("scimitar", "curved sword", 0, 0, 0, 15, 40, 15, 8, 8, 0,
            SLASH, Skill.P_SABER, Material.IRON, HI_METAL),
    _weapon("silver saber", None, 1, 0, 0, 6, 40, 75, 8, 8, 0,
            SLASH, Skill.P_SABER, Material.SILVER, HI_SILVER),
    _weapon("broadsword", None, 1, 0, 0, 8, 70, 10, 4, 6, 0,
            SLASH, Skill.P_BROAD_SWORD, Material.IRON, HI_METAL),
    _weapon("elven broadsword", "runed broadsword", 0, 0, 0, 4, 70, 10,
            6, 6, 0, SLASH, Skill.P_BROAD_SWORD, Material.WOOD, HI_WOOD),
    _weapon("long sword", None, 1, 0, 0, 50, 40, 15, 8, 12, 0,
            SLASH, Skill.P_LONG_SWORD, Material.IRON, HI_METAL),
    _weapon("two-handed sword", None, 1, 0, 1, 22, 150, 50, 12, 6, 0,
            SLASH, Skill.P_TWO_HANDED_SWORD, Material.IRON, HI_METAL),
    _weapon("katana", "samurai sword", 0, 0, 0, 4, 40, 80, 10, 12, 1,
            SLASH, Skill.P_LONG_SWORD, Material.IRON, HI_METAL),
    # special swords set up for artifacts
    _weapon("tsurugi", "long samurai sword", 0, 0, 1, 0, 60, 500, 16, 8,
            2, SLASH, Skill.P_TWO_HANDED_SWORD, Material.METAL, HI_METAL),
    _weapon("runesword", "runed broadsword", 0, 0, 0, 0, 40, 300, 4, 6,
            0, SLASH, Skill.P_BROAD_SWORD, Material.IRON, CLR_BLACK),
    # polearms
    _weapon("partisan", "vulgar polearm", 0, 0, 1, 5, 80, 10, 6, 6, 0,
            PIERCE, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("ranseur", "hilted polearm", 0, 0, 1, 5, 50, 6, 4, 4, 0,
            PIERCE, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("spetum", "forked polearm", 0, 0, 1, 5, 50, 5, 6, 6, 0,
            PIERCE, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("glaive", "single-edged polearm", 0, 0, 1, 8, 75, 6, 6, 10,
            0, SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("halberd", "angled poleaxe", 0, 0, 1, 8, 150, 10, 10, 6, 0,
            PIERCE | SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("bardiche", "long poleaxe", 0, 0, 1, 4, 120, 7, 4, 4, 0,
            SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("voulge", "pole cleaver", 0, 0, 1, 4, 125, 5, 4, 4, 0,
            SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("fauchard", "pole sickle", 0, 0, 1, 6, 60, 5, 6, 8, 0,
            PIERCE | SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("guisarme", "pruning hook", 0, 0, 1, 6, 80, 5, 4, 8, 0,
            SLASH, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("bill-guisarme", "hooked polearm", 0, 0, 1, 4, 120, 7, 4,
            10, 0, PIERCE | SLASH, Skill.P_POLEARMS, Material.IRON,
            HI_METAL),
    _weapon("lucern hammer", "pronged polearm", 0, 0, 1, 5, 150, 7, 4,
            6, 0, WHACK | PIERCE, Skill.P_POLEARMS, Material.IRON,
            HI_METAL),
    _weapon("bec de corbin", "beaked polearm", 0, 0, 1, 4, 100, 8, 8, 6,
            0, WHACK | PIERCE, Skill.P_POLEARMS, Material.IRON, HI_METAL),
    _weapon("dwarvish mattock", "broad pick", 0, 0, 1, 13, 120, 50, 12,
            8, -1, WHACK, Skill.P_PICK_AXE, Material.IRON, HI_METAL),
    _weapon("lance", None, 1, 0, 0, 4, 180, 10, 6, 8, 0,
            PIERCE, Skill.P_LANCE, Material.IRON, HI_METAL),
    # bludgeons
    _weapon("mace", None, 1, 0, 0, 40, 30, 5, 6, 6, 0,
            WHACK, Skill.P_MACE, Material.IRON, HI_METAL),
    _weapon("silver mace", None, 1, 0, 0, 2, 36, 60, 6, 6, 0,
            WHACK, Skill.P_MACE, Material.SILVER, HI_SILVER),
    _weapon("morning star", None, 1, 0, 0, 12, 120, 10, 4, 6, 0,
            WHACK, Skill.P_MORNING_STAR, Material.IRON, HI_METAL),
    _weapon("war hammer", None, 1, 0, 0, 15, 50, 5, 4, 4, 0,
            WHACK, Skill.P_HAMMER, Material.IRON, HI_METAL),
    _weapon("club", None, 1, 0, 0, 12, 30, 3, 6, 3, 0,
            WHACK, Skill.P_CLUB, Material.WOOD, HI_WOOD),
    _weapon("rubber hose", None, 1, 0, 0, 0, 20, 3, 4, 3, 0,
            WHACK, Skill.P_WHIP, Material.PLASTIC, CLR_BROWN),
    _weapon("quarterstaff", "staff", 0, 0, 1, 11, 40, 5, 6, 6, 0,
            WHACK, Skill.P_QUARTERSTAFF, Material.WOOD, HI_WOOD),
    # two-piece
    _weapon("aklys", "thonged club", 0, 0, 0, 8, 15, 4, 6, 3, 0,
            WHACK, Skill.P_CLUB, Material.IRON, HI_METAL),
    _weapon("flail", None, 1, 0, 0, 40, 15, 4, 6, 4, 0,
            WHACK, Skill.P_FLAIL, Material.IRON, HI_METAL),
    # misc
    _weapon("bullwhip", None, 1, 0, 0, 2, 20, 4, 2, 1, 0,
            0, Skill.P_WHIP, Material.LEATHER, CLR_BROWN),
    # bows
    _bow("bow", None, 1, 24, 30, 60, 0, Material.WOOD, Skill.P_BOW,
         HI_WOOD),
    _bow("elven bow", "runed bow", 0, 12, 30, 60, 0, Material.WOOD,
         Skill.P_BOW, HI_WOOD),
    _bow("orcish bow", "crude bow", 0, 12, 30, 60, 0, Material.WOOD,
         Skill.P_BOW, CLR_BLACK),
    _bow("yumi", "long bow", 0, 0, 30, 60, 0, Material.WOOD,
         Skill.P_BOW, HI_WOOD),
    _bow("sling", None, 1, 40, 3, 20, 0, Material.LEATHER,
         Skill.P_SLING, HI_LEATHER),
    _bow("crossbow", None, 1, 45, 50, 40, 0, Material.WOOD,
         Skill.P_CROSSBOW, HI_WOOD),
    # helmets
    _helmet("elven leather helm", "leather hat", 0, 0, 0, 6, 1, 3, 8, 9,
            0, Material.LEATHER, HI_LEATHER),
    _helmet("orcish helm", "iron skull cap", 0, 0, 0, 6, 1, 30, 10, 9, 0,
            Material.IRON, CLR_BLACK),
    _helmet("dwarvish iron helm", "hard hat", 0, 0, 0, 6, 1, 40, 20, 8, 0,
            Material.IRON, HI_METAL),
    _helmet("fedora", None, 1, 0, 0, 0, 0, 3, 1, 10, 0, Material.CLOTH,
            CLR_BROWN),
    _helmet("cornuthaum", "conical hat", 0, 1, Prop.CLAIRVOYANT, 5, 1, 4,
            80, 10, 1, Material.CLOTH, CLR_BLUE),
    _helmet("dunce cap", "conical hat", 0, 1, 0, 5, 1, 4, 1, 10, 0,
            Material.CLOTH, CLR_BLUE),
    _helmet("dented pot", None, 1, 0, 0, 2, 0, 10, 8, 9, 0, Material.IRON,
            CLR_BLACK),
    _helmet("helm of brilliance", "crystal helmet", 0, 1, 0, 6, 1, 40, 50,
            9, 0, Material.GLASS, CLR_WHITE),
    # with shuffled appearances...
    _helmet("helmet", "plumed helmet", 0, 0, 0, 10, 1, 30, 10, 9, 0,
            Material.IRON, HI_METAL),
    _helmet("helm of caution", "etched helmet", 0, 1, Prop.WARNING, 6, 1,
            50, 50, 9, 0, Material.IRON, CLR_GREEN),
    _helmet("helm of opposite alignment", "crested helmet", 0, 1, 0, 10, 1,
            50, 50, 9, 0, Material.IRON, HI_METAL),
    _helmet("helm of telepathy", "visored helmet", 0, 1, Prop.TELEPAT, 4,
            1, 50, 50, 9, 0, Material.IRON, HI_METAL),
    # dragon scale mails and scales (order matches the dragons in
    # monst.c -- see the C note)
    _armor("gray dragon scale mail", None, 1, 1, 1, Prop.ANTIMAGIC, 0, 5,
           40, 1200, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_GRAY),
    _armor("gold dragon scale mail", None, 1, 1, 1, 0, 0, 5, 40, 900, 1, 0,
           ARM_SUIT, Material.DRAGON_HIDE, HI_GOLD),
    _armor("silver dragon scale mail", None, 1, 1, 1, Prop.REFLECTING, 0,
           5, 40, 1200, 1, 0, ARM_SUIT, Material.DRAGON_HIDE,
           DRAGON_SILVER),
    _armor("red dragon scale mail", None, 1, 1, 1, Prop.FIRE_RES, 0, 5, 40,
           900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_RED),
    _armor("white dragon scale mail", None, 1, 1, 1, Prop.COLD_RES, 0, 5,
           40, 900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_WHITE),
    _armor("orange dragon scale mail", None, 1, 1, 1, Prop.SLEEP_RES, 0,
           5, 40, 900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_ORANGE),
    _armor("black dragon scale mail", None, 1, 1, 1, Prop.DISINT_RES, 0,
           5, 40, 1200, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_BLACK),
    _armor("blue dragon scale mail", None, 1, 1, 1, Prop.SHOCK_RES, 0, 5,
           40, 900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_BLUE),
    _armor("green dragon scale mail", None, 1, 1, 1, Prop.POISON_RES, 0,
           5, 40, 900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_GREEN),
    _armor("yellow dragon scale mail", None, 1, 1, 1, Prop.ACID_RES, 0, 5,
           40, 900, 1, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_YELLOW),
    _armor("gray dragon scales", None, 1, 0, 1, Prop.ANTIMAGIC, 0, 5, 40,
           700, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_GRAY),
    _armor("gold dragon scales", None, 1, 0, 1, 0, 0, 5, 40, 500, 7, 0,
           ARM_SUIT, Material.DRAGON_HIDE, HI_GOLD),
    _armor("silver dragon scales", None, 1, 0, 1, Prop.REFLECTING, 0, 5,
           40, 700, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, DRAGON_SILVER),
    _armor("red dragon scales", None, 1, 0, 1, Prop.FIRE_RES, 0, 5, 40,
           500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_RED),
    _armor("white dragon scales", None, 1, 0, 1, Prop.COLD_RES, 0, 5, 40,
           500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_WHITE),
    _armor("orange dragon scales", None, 1, 0, 1, Prop.SLEEP_RES, 0, 5,
           40, 500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_ORANGE),
    _armor("black dragon scales", None, 1, 0, 1, Prop.DISINT_RES, 0, 5, 40,
           700, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_BLACK),
    _armor("blue dragon scales", None, 1, 0, 1, Prop.SHOCK_RES, 0, 5, 40,
           500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_BLUE),
    _armor("green dragon scales", None, 1, 0, 1, Prop.POISON_RES, 0, 5,
           40, 500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_GREEN),
    _armor("yellow dragon scales", None, 1, 0, 1, Prop.ACID_RES, 0, 5, 40,
           500, 7, 0, ARM_SUIT, Material.DRAGON_HIDE, CLR_YELLOW),
    # other suits
    _armor("plate mail", None, 1, 0, 1, 0, 40, 5, 450, 600, 3, 2, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("crystal plate mail", None, 1, 0, 1, 0, 10, 5, 415, 820, 3, 2,
           ARM_SUIT, Material.GLASS, CLR_WHITE),
    _armor("bronze plate mail", None, 1, 0, 1, 0, 23, 5, 450, 400, 4, 1,
           ARM_SUIT, Material.COPPER, HI_COPPER),
    _armor("splint mail", None, 1, 0, 1, 0, 57, 5, 400, 80, 4, 1, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("banded mail", None, 1, 0, 1, 0, 66, 5, 350, 90, 4, 1, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("dwarvish mithril-coat", None, 1, 0, 0, 0, 10, 1, 150, 240, 4,
           2, ARM_SUIT, Material.MITHRIL, HI_SILVER),
    _armor("elven mithril-coat", None, 1, 0, 0, 0, 15, 1, 150, 240, 5, 2,
           ARM_SUIT, Material.MITHRIL, HI_SILVER),
    _armor("chain mail", None, 1, 0, 0, 0, 66, 5, 300, 75, 5, 1, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("orcish chain mail", "crude chain mail", 0, 0, 0, 0, 19, 5, 300,
           75, 6, 1, ARM_SUIT, Material.IRON, CLR_BLACK),
    _armor("scale mail", None, 1, 0, 0, 0, 66, 5, 250, 45, 6, 1, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("studded leather armor", None, 1, 0, 0, 0, 66, 3, 200, 15, 7, 1,
           ARM_SUIT, Material.LEATHER, HI_LEATHER),
    _armor("ring mail", None, 1, 0, 0, 0, 66, 5, 250, 100, 7, 1, ARM_SUIT,
           Material.IRON, HI_METAL),
    _armor("orcish ring mail", "crude ring mail", 0, 0, 0, 0, 19, 5, 250,
           80, 8, 1, ARM_SUIT, Material.IRON, CLR_BLACK),
    _armor("leather armor", None, 1, 0, 0, 0, 75, 3, 150, 5, 8, 1, ARM_SUIT,
           Material.LEATHER, HI_LEATHER),
    _armor("leather jacket", None, 1, 0, 0, 0, 11, 0, 30, 10, 9, 0,
           ARM_SUIT, Material.LEATHER, CLR_BLACK),
    # shirts
    _armor("Hawaiian shirt", None, 1, 0, 0, 0, 8, 0, 5, 3, 10, 0,
           ARM_SHIRT, Material.CLOTH, CLR_MAGENTA),
    _armor("T-shirt", None, 1, 0, 0, 0, 2, 0, 5, 2, 10, 0, ARM_SHIRT,
           Material.CLOTH, CLR_WHITE),
    # cloaks
    _cloak("mummy wrapping", None, 1, 0, 0, 0, 0, 3, 2, 10, 1, Material.CLOTH,
           CLR_GRAY),
    _cloak("elven cloak", "faded pall", 0, 1, Prop.STEALTH, 8, 0, 10, 60,
           9, 1, Material.CLOTH, CLR_BLACK),
    _cloak("orcish cloak", "coarse mantelet", 0, 0, 0, 8, 0, 10, 40, 10, 1,
           Material.CLOTH, CLR_BLACK),
    _cloak("dwarvish cloak", "hooded cloak", 0, 0, 0, 8, 0, 10, 50, 10, 1,
           Material.CLOTH, HI_CLOTH),
    _cloak("oilskin cloak", "slippery cloak", 0, 0, 0, 8, 0, 10, 50, 9, 2,
           Material.CLOTH, HI_CLOTH),
    _cloak("robe", None, 1, 1, 0, 6, 0, 15, 50, 8, 2, Material.CLOTH,
           CLR_RED),
    _cloak("alchemy smock", "apron", 0, 1, Prop.POISON_RES, 11, 0, 10, 50,
           9, 1, Material.CLOTH, CLR_WHITE),
    _cloak("leather cloak", None, 1, 0, 0, 8, 0, 15, 40, 9, 1,
           Material.LEATHER, CLR_BROWN),
    # with shuffled appearances...
    _cloak("cloak of protection", "tattered cape", 0, 1, Prop.PROTECTION,
           11, 0, 10, 50, 7, 3, Material.CLOTH, HI_CLOTH),
    _cloak("cloak of invisibility", "opera cloak", 0, 1, Prop.INVIS, 12,
           0, 10, 60, 9, 1, Material.CLOTH, CLR_BRIGHT_MAGENTA),
    _cloak("cloak of magic resistance", "ornamental cope", 0, 1,
           Prop.ANTIMAGIC, 6, 0, 10, 60, 9, 1, Material.CLOTH, CLR_WHITE),
    _cloak("cloak of displacement", "piece of cloth", 0, 1,
           Prop.DISPLACED, 12, 0, 10, 50, 9, 1, Material.CLOTH, HI_CLOTH),
    # shields
    _shield("small shield", "wooden shield", 0, 0, 0, 0, 6, 0, 30, 3, 9, 0,
            Material.WOOD, HI_WOOD),
    _shield("shield of drain resistance", "wooden shield", 0, 1, 0,
            Prop.DRAIN_RES, 12, 0, 30, 50, 9, 0, Material.WOOD, HI_WOOD),
    _shield("shield of shock resistance", "wooden shield", 0, 1, 0,
            Prop.SHOCK_RES, 12, 0, 30, 50, 9, 0, Material.WOOD, HI_WOOD),
    _shield("elven shield", "blue and green shield", 0, 0, 0, 0, 2, 0, 40,
            7, 8, 0, Material.WOOD, CLR_GREEN),
    _shield("Uruk-hai shield", "white-handed shield", 0, 0, 0, 0, 2, 0, 50,
            7, 9, 0, Material.IRON, HI_METAL),
    _shield("orcish shield", "red-eyed shield", 0, 0, 0, 0, 2, 0, 50, 7,
            9, 0, Material.IRON, CLR_RED),
    _shield("large shield", None, 1, 0, 1, 0, 4, 0, 100, 10, 8, 0,
            Material.IRON, HI_METAL),
    _shield("dwarvish roundshield", "large round shield", 0, 0, 0, 0, 3, 0,
            100, 10, 8, 0, Material.IRON, HI_METAL),
    _shield("shield of reflection", "polished silver shield", 0, 1, 0,
            Prop.REFLECTING, 7, 0, 50, 50, 8, 0, Material.SILVER,
            HI_SILVER),
    # gloves (color not material shuffled: IRON stays CLR_BROWN)
    _gloves("leather gloves", "old gloves", 0, 0, 0, 15, 1, 10, 8, 9, 0,
            Material.LEATHER, HI_LEATHER),
    _gloves("gauntlets of fumbling", "padded gloves", 0, 1, Prop.FUMBLING,
            8, 1, 10, 50, 9, 0, Material.LEATHER, HI_LEATHER),
    _gloves("gauntlets of power", "riding gloves", 0, 1, 0, 8, 1, 30, 50,
            9, 0, Material.IRON, CLR_BROWN),
    _gloves("gauntlets of dexterity", "fencing gloves", 0, 1, 0, 8, 1, 10,
            50, 9, 0, Material.LEATHER, HI_LEATHER),
    # boots
    _boots("low boots", "walking shoes", 0, 0, 0, 23, 2, 10, 8, 9, 0,
           Material.LEATHER, HI_LEATHER),
    _boots("iron shoes", "hard shoes", 0, 0, 0, 7, 2, 50, 16, 8, 0,
           Material.IRON, HI_METAL),
    _boots("high boots", "jackboots", 0, 0, 0, 14, 2, 20, 12, 8, 0,
           Material.LEATHER, HI_LEATHER),
    # with shuffled appearances...
    _boots("speed boots", "combat boots", 0, 1, Prop.FAST, 12, 2, 20, 50,
           9, 0, Material.LEATHER, HI_LEATHER),
    _boots("water walking boots", "jungle boots", 0, 1, Prop.WWALKING, 12,
           2, 15, 50, 9, 0, Material.LEATHER, HI_LEATHER),
    _boots("jumping boots", "hiking boots", 0, 1, Prop.JUMPING, 12, 2, 20,
           50, 9, 0, Material.LEATHER, HI_LEATHER),
    _boots("elven boots", "mud boots", 0, 1, Prop.STEALTH, 12, 2, 15, 8,
           9, 0, Material.LEATHER, HI_LEATHER),
    _boots("kicking boots", "buckled boots", 0, 1, 0, 12, 2, 50, 8, 9, 0,
           Material.IRON, CLR_BROWN),
    _boots("fumble boots", "riding boots", 0, 1, Prop.FUMBLING, 12, 2, 20,
           30, 9, 0, Material.LEATHER, HI_LEATHER),
    _boots("levitation boots", "snow boots", 0, 1, Prop.LEVITATION, 12,
           2, 15, 30, 9, 0, Material.LEATHER, HI_LEATHER),
    # rings (RING(name, stone, power, cost, mgc, spec, mohs, metal, color))
    _ring("adornment", "wooden", Prop.ADORNED, 100, 1, 1, 2,
          Material.WOOD, HI_WOOD),
    _ring("gain strength", "granite", 0, 150, 1, 1, 7, Material.MINERAL,
          HI_MINERAL),
    _ring("gain constitution", "opal", 0, 150, 1, 1, 7, Material.MINERAL,
          HI_MINERAL),
    _ring("increase accuracy", "clay", 0, 150, 1, 1, 4, Material.MINERAL,
          CLR_RED),
    _ring("increase damage", "coral", 0, 150, 1, 1, 4, Material.MINERAL,
          CLR_ORANGE),
    _ring("protection", "black onyx", Prop.PROTECTION, 100, 1, 1, 7,
          Material.MINERAL, CLR_BLACK),
    _ring("regeneration", "moonstone", Prop.REGENERATION, 200, 1, 0, 6,
          Material.MINERAL, HI_MINERAL),
    _ring("searching", "tiger eye", Prop.SEARCHING, 200, 1, 0, 6,
          Material.GEMSTONE, CLR_BROWN),
    _ring("stealth", "jade", Prop.STEALTH, 100, 1, 0, 6, Material.GEMSTONE,
          CLR_GREEN),
    _ring("sustain ability", "bronze", Prop.FIXED_ABIL, 100, 1, 0, 4,
          Material.COPPER, HI_COPPER),
    _ring("levitation", "agate", Prop.LEVITATION, 200, 1, 0, 7,
          Material.GEMSTONE, CLR_RED),
    _ring("hunger", "topaz", Prop.HUNGER, 100, 1, 0, 8, Material.GEMSTONE,
          CLR_CYAN),
    _ring("aggravate monster", "sapphire", Prop.AGGRAVATE_MONSTER, 150, 1,
          0, 9, Material.GEMSTONE, CLR_BLUE),
    _ring("conflict", "ruby", Prop.CONFLICT, 300, 1, 0, 9, Material.GEMSTONE,
          CLR_RED),
    _ring("warning", "diamond", Prop.WARNING, 100, 1, 0, 10,
          Material.GEMSTONE, CLR_WHITE),
    _ring("poison resistance", "pearl", Prop.POISON_RES, 150, 1, 0, 4,
          Material.BONE, CLR_WHITE),
    _ring("fire resistance", "iron", Prop.FIRE_RES, 200, 1, 0, 5,
          Material.IRON, HI_METAL),
    _ring("cold resistance", "brass", Prop.COLD_RES, 150, 1, 0, 4,
          Material.COPPER, HI_COPPER),
    _ring("shock resistance", "copper", Prop.SHOCK_RES, 150, 1, 0, 3,
          Material.COPPER, HI_COPPER),
    _ring("free action", "twisted", Prop.FREE_ACTION, 200, 1, 0, 6,
          Material.IRON, HI_METAL),
    _ring("slow digestion", "steel", Prop.SLOW_DIGESTION, 200, 1, 0, 8,
          Material.IRON, HI_METAL),
    _ring("teleportation", "silver", Prop.TELEPORT, 200, 1, 0, 3,
          Material.SILVER, HI_SILVER),
    _ring("teleport control", "gold", Prop.TELEPORT_CONTROL, 300, 1, 0, 3,
          Material.GOLD, HI_GOLD),
    _ring("polymorph", "ivory", Prop.POLYMORPH, 300, 1, 0, 4, Material.BONE,
          CLR_WHITE),
    _ring("polymorph control", "emerald", Prop.POLYMORPH_CONTROL, 300, 1,
          0, 8, Material.GEMSTONE, CLR_BRIGHT_GREEN),
    _ring("invisibility", "wire", Prop.INVIS, 150, 1, 0, 5, Material.IRON,
          HI_METAL),
    _ring("see invisible", "engagement", Prop.SEE_INVIS, 150, 1, 0, 5,
          Material.IRON, HI_METAL),
    _ring("protection from shape changers", "shiny",
          Prop.PROT_FROM_SHAPE_CHANGERS, 100, 1, 0, 5, Material.IRON,
          CLR_BRIGHT_CYAN),
    # amulets - THE Amulet comes last because it is special
    _amulet("amulet of ESP", "circular", Prop.TELEPAT, 120),
    _amulet("amulet of life saving", "spherical", Prop.LIFESAVED, 75),
    _amulet("amulet of strangulation", "oval", Prop.STRANGLED, 115),
    _amulet("amulet of restful sleep", "triangular", Prop.SLEEPY, 115),
    _amulet("amulet versus poison", "pyramidal", Prop.POISON_RES, 115),
    _amulet("amulet of change", "square", 0, 115),
    _amulet("amulet of unchanging", "concave", Prop.UNCHANGING, 60),
    _amulet("amulet of reflection", "hexagonal", Prop.REFLECTING, 75),
    _amulet("amulet of magical breathing", "octagonal",
            Prop.MAGICAL_BREATHING, 75),
    _amulet("amulet of guarding", "perforated", Prop.PROTECTION, 75),
    _amulet("amulet of flying", "cubical", Prop.FLYING, 60),
    # fixed descriptions; the fake must come before the real one
    Object(name="cheap plastic imitation of the Amulet of Yendor",
           descr="Amulet of Yendor", oclass=ObjClass.AMULET,
           color=HI_METAL, weight=20, nutrition=1, uses_known=True,
           material=Material.PLASTIC),
    Object(name="Amulet of Yendor", descr="Amulet of Yendor",
           oclass=ObjClass.AMULET, color=HI_METAL, weight=20, cost=30000,
           nutrition=20, uses_known=True, magic=True, unique=True,
           nowish=True, material=Material.MITHRIL),
    # tools
    # containers
    _container("large box", None, 1, 0, 0, 40, 350, 8, Material.WOOD,
               HI_WOOD),
    _container("chest", None, 1, 0, 0, 35, 600, 16, Material.WOOD, HI_WOOD),
    _container("ice box", None, 1, 0, 0, 5, 900, 42, Material.PLASTIC,
               CLR_WHITE),
    _container("sack", "bag", 0, 0, 0, 35, 15, 2, Material.CLOTH, HI_CLOTH),
    _container("oilskin sack", "bag", 0, 0, 0, 5, 15, 100, Material.CLOTH,
               HI_CLOTH),
    _container("bag of holding", "bag", 0, 1, 0, 20, 15, 100, Material.CLOTH,
               HI_CLOTH),
    _container("bag of tricks", "bag", 0, 1, 1, 20, 15, 100, Material.CLOTH,
               HI_CLOTH),
    # lock opening tools
    _tool("skeleton key", "key", 0, 0, 0, 0, 80, 3, 10, Material.IRON,
          HI_METAL),
    _tool("lock pick", None, 1, 0, 0, 0, 60, 4, 20, Material.IRON, HI_METAL),
    _tool("credit card", None, 1, 0, 0, 0, 15, 1, 10, Material.PLASTIC,
          CLR_WHITE),
    # light sources
    _tool("tallow candle", "candle", 0, 1, 0, 0, 20, 2, 10, Material.WAX,
          CLR_WHITE),
    _tool("wax candle", "candle", 0, 1, 0, 0, 5, 2, 20, Material.WAX,
          CLR_WHITE),
    _tool("brass lantern", None, 1, 0, 0, 0, 30, 30, 12, Material.COPPER,
          CLR_YELLOW),
    _tool("oil lamp", "lamp", 0, 0, 0, 0, 45, 20, 10, Material.COPPER,
          CLR_YELLOW),
    _tool("magic lamp", "lamp", 0, 0, 1, 0, 15, 20, 50, Material.COPPER,
          CLR_YELLOW),
    # other tools
    _tool("expensive camera", None, 1, 0, 0, 1, 15, 12, 200, Material.PLASTIC,
          CLR_BLACK),
    _tool("mirror", "looking glass", 0, 0, 0, 0, 45, 13, 10, Material.GLASS,
          HI_SILVER),
    _tool("crystal ball", "glass orb", 0, 0, 1, 1, 15, 150, 60, Material.GLASS,
          HI_GLASS),
    # eyewear
    _eyewear("lenses", None, 1, 0, 5, 3, 80, Material.GLASS, HI_GLASS),
    _eyewear("blindfold", None, 1, Prop.BLINDED, 50, 2, 20, Material.CLOTH,
             CLR_BLACK),
    _eyewear("towel", None, 1, Prop.BLINDED, 50, 5, 50, Material.CLOTH,
             CLR_MAGENTA),
    # still other tools
    _tool("saddle", None, 1, 0, 0, 0, 5, 200, 150, Material.LEATHER,
          HI_LEATHER),
    _tool("leash", None, 1, 0, 0, 0, 65, 12, 20, Material.LEATHER,
          HI_LEATHER),
    _tool("stethoscope", None, 1, 0, 0, 0, 25, 4, 75, Material.IRON, HI_METAL),
    _tool("tinning kit", None, 1, 0, 0, 1, 15, 100, 30, Material.IRON,
          HI_METAL),
    _tool("tin opener", None, 1, 0, 0, 0, 35, 4, 30, Material.IRON, HI_METAL),
    _tool("can of grease", None, 1, 0, 0, 1, 15, 15, 20, Material.IRON,
          HI_METAL),
    _tool("figurine", None, 1, 0, 1, 0, 25, 50, 80, Material.MINERAL,
          HI_MINERAL),
    _tool("magic marker", None, 1, 0, 1, 1, 15, 2, 50, Material.PLASTIC,
          CLR_RED),
    # traps
    _tool("land mine", None, 1, 0, 0, 0, 0, 200, 180, Material.IRON, CLR_RED),
    _tool("beartrap", None, 1, 0, 0, 0, 0, 200, 60, Material.IRON, HI_METAL),
    # instruments
    _tool("tin whistle", "whistle", 0, 0, 0, 0, 100, 3, 10, Material.METAL,
          HI_METAL),
    _tool("magic whistle", "whistle", 0, 0, 1, 0, 30, 3, 10, Material.METAL,
          HI_METAL),
    _tool("wooden flute", "flute", 0, 0, 0, 0, 4, 5, 12, Material.WOOD,
          HI_WOOD),
    _tool("magic flute", "flute", 0, 0, 1, 1, 2, 5, 36, Material.WOOD,
          HI_WOOD),
    _tool("tooled horn", "horn", 0, 0, 0, 0, 5, 18, 15, Material.BONE,
          CLR_WHITE),
    _tool("frost horn", "horn", 0, 0, 1, 1, 2, 18, 50, Material.BONE,
          CLR_WHITE),
    _tool("fire horn", "horn", 0, 0, 1, 1, 2, 18, 50, Material.BONE,
          CLR_WHITE),
    _tool("horn of plenty", "horn", 0, 0, 1, 1, 2, 18, 50, Material.BONE,
          CLR_WHITE),
    _tool("wooden harp", "harp", 0, 0, 0, 0, 4, 30, 50, Material.WOOD,
          HI_WOOD),
    _tool("magic harp", "harp", 0, 0, 1, 1, 2, 30, 50, Material.WOOD,
          HI_WOOD),
    _tool("bell", None, 1, 0, 0, 0, 2, 30, 50, Material.COPPER, HI_COPPER),
    _tool("bugle", None, 1, 0, 0, 0, 4, 10, 15, Material.COPPER, HI_COPPER),
    _tool("leather drum", "drum", 0, 0, 0, 0, 4, 25, 25, Material.LEATHER,
          HI_LEATHER),
    _tool("drum of earthquake", "drum", 0, 0, 1, 1, 2, 25, 25,
          Material.LEATHER, HI_LEATHER),
    # tools useful as weapons
    _weptool("pick-axe", None, 1, 0, 0, 20, 100, 50, 6, 3, WHACK,
             Skill.P_PICK_AXE, Material.IRON, HI_METAL),
    _weptool("grappling hook", None, 1, 0, 0, 5, 30, 50, 2, 6, WHACK,
             Skill.P_FLAIL, Material.IRON, HI_METAL),
    _weptool("unicorn horn", None, 1, 1, 1, 0, 20, 100, 12, 12, PIERCE,
             Skill.P_UNICORN_HORN, Material.BONE, CLR_WHITE),
    # two unique tools
    Object(name="Candelabrum of Invocation", descr="candelabrum",
           oclass=ObjClass.TOOL, color=HI_GOLD, weight=10, cost=5000,
           nutrition=200, uses_known=True, magic=True, unique=True,
           nowish=True, material=Material.GOLD),
    Object(name="Bell of Opening", descr="silver bell",
           oclass=ObjClass.TOOL, color=HI_SILVER, weight=10, cost=5000,
           nutrition=50, uses_known=True, magic=True, charged=True,
           unique=True, nowish=True, material=Material.SILVER),
    # food (FOOD(name, prob, delay, wt, unk, mat, nutrition, color))
    _food("tripe ration", 140, 2, 10, 0, Material.FLESH, 200, CLR_BROWN),
    _food("corpse", 0, 1, 0, 0, Material.FLESH, 0, CLR_BROWN),
    _food("egg", 85, 1, 1, 1, Material.FLESH, 80, CLR_WHITE),
    _food("meatball", 0, 1, 1, 0, Material.FLESH, 5, CLR_BROWN),
    _food("meat stick", 0, 1, 1, 0, Material.FLESH, 5, CLR_BROWN),
    _food("enormous meatball", 0, 20, 400, 0, Material.FLESH, 2000,
          CLR_BROWN),
    # special case because it's not mergeable
    Object(name="meat ring", descr=None, oclass=ObjClass.FOOD,
           color=CLR_BROWN, delay=1, weight=5, cost=1, nutrition=5,
           name_known=True, material=Material.FLESH),
    # pudding 'corpses'; must be in same order as the pudding monsters
    _food("glob of gray ooze", 0, 2, 20, 0, Material.FLESH, 20, CLR_GRAY),
    _food("glob of brown pudding", 0, 2, 20, 0, Material.FLESH, 20,
          CLR_BROWN),
    _food("glob of green slime", 0, 2, 20, 0, Material.FLESH, 20,
          CLR_GREEN),
    _food("glob of black pudding", 0, 2, 20, 0, Material.FLESH, 20,
          CLR_BLACK),
    # fruits & veggies
    _food("kelp frond", 0, 1, 1, 0, Material.VEGGY, 30, CLR_GREEN),
    _food("eucalyptus leaf", 3, 1, 1, 0, Material.VEGGY, 1, CLR_GREEN),
    _food("apple", 15, 1, 2, 0, Material.VEGGY, 50, CLR_RED),
    _food("orange", 10, 1, 2, 0, Material.VEGGY, 80, CLR_ORANGE),
    _food("pear", 10, 1, 2, 0, Material.VEGGY, 50, CLR_BRIGHT_GREEN),
    _food("melon", 10, 1, 5, 0, Material.VEGGY, 100, CLR_BRIGHT_GREEN),
    _food("banana", 10, 1, 2, 0, Material.VEGGY, 80, CLR_YELLOW),
    _food("carrot", 15, 1, 2, 0, Material.VEGGY, 50, CLR_ORANGE),
    _food("sprig of wolfsbane", 7, 1, 1, 0, Material.VEGGY, 40, CLR_GREEN),
    _food("clove of garlic", 7, 1, 1, 0, Material.VEGGY, 40, CLR_WHITE),
    _food("slime mold", 75, 1, 5, 0, Material.VEGGY, 250, HI_ORGANIC),
    # people food
    _food("lump of royal jelly", 0, 1, 2, 0, Material.VEGGY, 200, CLR_YELLOW),
    _food("cream pie", 25, 1, 10, 0, Material.VEGGY, 100, CLR_WHITE),
    _food("candy bar", 13, 1, 2, 0, Material.VEGGY, 100, CLR_BRIGHT_BLUE),
    _food("fortune cookie", 55, 1, 1, 0, Material.VEGGY, 40, CLR_YELLOW),
    _food("pancake", 25, 2, 2, 0, Material.VEGGY, 200, CLR_YELLOW),
    _food("lembas wafer", 20, 2, 5, 0, Material.VEGGY, 800, CLR_WHITE),
    _food("cram ration", 20, 3, 15, 0, Material.VEGGY, 600, HI_ORGANIC),
    _food("food ration", 380, 5, 20, 0, Material.VEGGY, 800, HI_ORGANIC),
    _food("K-ration", 0, 1, 10, 0, Material.VEGGY, 400, HI_ORGANIC),
    _food("C-ration", 0, 1, 10, 0, Material.VEGGY, 300, HI_ORGANIC),
    # tins
    _food("tin", 75, 0, 10, 1, Material.METAL, 0, HI_METAL),
    # potions (POTION(name, desc, mgc, power, prob, cost, color))
    _potion("gain ability", "ruby", 1, 0, 40, 300, CLR_RED),
    _potion("restore ability", "pink", 1, 0, 40, 100, CLR_BRIGHT_MAGENTA),
    _potion("confusion", "orange", 1, Prop.CONFUSION, 40, 100, CLR_ORANGE),
    _potion("blindness", "yellow", 1, Prop.BLINDED, 30, 150, CLR_YELLOW),
    _potion("paralysis", "emerald", 1, 0, 40, 300, CLR_BRIGHT_GREEN),
    _potion("speed", "dark green", 1, Prop.FAST, 40, 200, CLR_GREEN),
    _potion("levitation", "cyan", 1, Prop.LEVITATION, 40, 200, CLR_CYAN),
    _potion("hallucination", "sky blue", 1, Prop.HALLUC, 30, 100, CLR_CYAN),
    _potion("invisibility", "brilliant blue", 1, Prop.INVIS, 40, 150,
            CLR_BRIGHT_BLUE),
    _potion("see invisible", "magenta", 1, Prop.SEE_INVIS, 40, 50,
            CLR_MAGENTA),
    _potion("healing", "purple-red", 1, 0, 115, 20, CLR_MAGENTA),
    _potion("extra healing", "puce", 1, 0, 45, 100, CLR_RED),
    _potion("gain level", "milky", 1, 0, 20, 300, CLR_WHITE),
    _potion("enlightenment", "swirly", 1, 0, 20, 200, CLR_BROWN),
    _potion("monster detection", "bubbly", 1, 0, 40, 150, CLR_WHITE),
    _potion("object detection", "smoky", 1, 0, 40, 150, CLR_GRAY),
    _potion("gain energy", "cloudy", 1, 0, 40, 150, CLR_WHITE),
    _potion("sleeping", "effervescent", 1, 0, 40, 100, CLR_GRAY),
    _potion("full healing", "black", 1, 0, 10, 200, CLR_BLACK),
    _potion("polymorph", "golden", 1, 0, 10, 200, CLR_YELLOW),
    _potion("booze", "brown", 0, 0, 40, 50, CLR_BROWN),
    _potion("sickness", "fizzy", 0, 0, 40, 50, CLR_CYAN),
    _potion("fruit juice", "dark", 0, 0, 40, 50, CLR_BLACK),
    _potion("acid", "white", 0, 0, 10, 250, CLR_WHITE),
    _potion("oil", "murky", 0, 0, 30, 250, CLR_BROWN),
    # fixed description
    _potion("water", "clear", 0, 0, 80, 100, CLR_CYAN),
    # scrolls (SCROLL(name, text, mgc, prob, cost))
    _scroll("enchant armor", "ZELGO MER", 1, 63, 80),
    _scroll("destroy armor", "JUYED AWK YACC", 1, 45, 100),
    _scroll("confuse monster", "NR 9", 1, 53, 100),
    _scroll("scare monster", "XIXAXA XOXAXA XUXAXA", 1, 35, 100),
    _scroll("remove curse", "PRATYAVAYAH", 1, 65, 80),
    _scroll("enchant weapon", "DAIYEN FOOELS", 1, 80, 60),
    _scroll("create monster", "LEP GEX VEN ZEA", 1, 45, 200),
    _scroll("taming", "PRIRUTSENIE", 1, 15, 200),
    _scroll("genocide", "ELBIB YLOH", 1, 15, 300),
    _scroll("light", "VERR YED HORRE", 1, 90, 50),
    _scroll("teleportation", "VENZAR BORGAVVE", 1, 55, 100),
    _scroll("gold detection", "THARR", 1, 33, 100),
    _scroll("food detection", "YUM YUM", 1, 25, 100),
    _scroll("identify", "KERNOD WEL", 1, 180, 20),
    _scroll("magic mapping", "ELAM EBOW", 1, 45, 100),
    _scroll("amnesia", "DUAM XNAHT", 1, 35, 200),
    _scroll("fire", "ANDOVA BEGARIN", 1, 30, 100),
    _scroll("earth", "KIRJE", 1, 18, 200),
    _scroll("punishment", "VE FORBRYDERNE", 1, 15, 300),
    _scroll("charging", "HACKEM MUCHE", 1, 15, 300),
    _scroll("stinking cloud", "VELOX NEB", 1, 15, 300),
    # extra descriptions, shuffled into use at start of a new game
    _scroll(None, "FOOBIE BLETCH", 1, 0, 100),
    _scroll(None, "TEMOV", 1, 0, 100),
    _scroll(None, "GARVEN DEH", 1, 0, 100),
    _scroll(None, "READ ME", 1, 0, 100),
    _scroll(None, "ETAOIN SHRDLU", 1, 0, 100),
    _scroll(None, "LOREM IPSUM", 1, 0, 100),
    _scroll(None, "FNORD", 1, 0, 100),
    _scroll(None, "KO BATE", 1, 0, 100),
    _scroll(None, "ABRA KA DABRA", 1, 0, 100),
    _scroll(None, "ASHPD SODALG", 1, 0, 100),
    _scroll(None, "ZLORFIK", 1, 0, 100),
    _scroll(None, "GNIK SISI VLE", 1, 0, 100),
    _scroll(None, "HAPAX LEGOMENON", 1, 0, 100),
    _scroll(None, "EIRIS SAZUN IDISI", 1, 0, 100),
    _scroll(None, "PHOL ENDE WODAN", 1, 0, 100),
    _scroll(None, "GHOTI", 1, 0, 100),
    _scroll(None, "MAPIRO MAHAMA DIROMAT", 1, 0, 100),
    _scroll(None, "VAS CORP BET MANI", 1, 0, 100),
    _scroll(None, "XOR OTA", 1, 0, 100),
    _scroll(None, "STRC PRST SKRZ KRK", 1, 0, 100),
    # fixed descriptions (SCR_MAIL compiled out)
    _scroll("blank paper", "unlabeled", 0, 28, 60),
    # spellbooks (SPELL(name, desc, sub, prob, delay, level, mgc, dir,
    #                     color[, material]))
    _spell("dig", "parchment", Skill.P_MATTER_SPELL, 20, 6, 5, 1, RAY,
           HI_LEATHER, mat=Material.LEATHER),
    _spell("magic missile", "vellum", Skill.P_ATTACK_SPELL, 45, 2, 2, 1,
           RAY, HI_LEATHER),
    _spell("fireball", "ragged", Skill.P_ATTACK_SPELL, 20, 4, 4, 1, RAY,
           HI_PAPER),
    _spell("cone of cold", "dog eared", Skill.P_ATTACK_SPELL, 10, 7, 4, 1,
           RAY, HI_PAPER),
    _spell("sleep", "mottled", Skill.P_ENCHANTMENT_SPELL, 30, 1, 3, 1, RAY,
           HI_PAPER),
    _spell("finger of death", "stained", Skill.P_ATTACK_SPELL, 5, 10, 7, 1,
           RAY, HI_PAPER),
    _spell("light", "cloth", Skill.P_DIVINATION_SPELL, 45, 1, 1, 1, NODIR,
           HI_CLOTH),
    _spell("detect monsters", "leathery", Skill.P_DIVINATION_SPELL, 43,
           1, 1, 1, NODIR, HI_LEATHER),
    _spell("healing", "white", Skill.P_HEALING_SPELL, 40, 2, 1, 1,
           IMMEDIATE, CLR_WHITE),
    _spell("knock", "pink", Skill.P_MATTER_SPELL, 25, 1, 1, 1, IMMEDIATE,
           CLR_BRIGHT_MAGENTA),
    _spell("force bolt", "red", Skill.P_ATTACK_SPELL, 30, 2, 1, 1,
           IMMEDIATE, CLR_RED),
    _spell("confuse monster", "orange", Skill.P_ENCHANTMENT_SPELL, 49, 2,
           1, 1, IMMEDIATE, CLR_ORANGE),
    _spell("cure blindness", "yellow", Skill.P_HEALING_SPELL, 25, 2, 2, 1,
           IMMEDIATE, CLR_YELLOW),
    _spell("drain life", "velvet", Skill.P_ATTACK_SPELL, 10, 2, 2, 1,
           IMMEDIATE, CLR_MAGENTA),
    _spell("slow monster", "light green", Skill.P_ENCHANTMENT_SPELL, 30,
           2, 2, 1, IMMEDIATE, CLR_BRIGHT_GREEN),
    _spell("wizard lock", "dark green", Skill.P_MATTER_SPELL, 25, 3, 2, 1,
           IMMEDIATE, CLR_GREEN),
    _spell("create monster", "turquoise", Skill.P_CLERIC_SPELL, 35, 3, 2,
           1, NODIR, CLR_BRIGHT_CYAN),
    _spell("detect food", "cyan", Skill.P_DIVINATION_SPELL, 30, 3, 2, 1,
           NODIR, CLR_CYAN),
    _spell("cause fear", "light blue", Skill.P_ENCHANTMENT_SPELL, 25, 3,
           3, 1, NODIR, CLR_BRIGHT_BLUE),
    _spell("clairvoyance", "dark blue", Skill.P_DIVINATION_SPELL, 15, 3,
           3, 1, NODIR, CLR_BLUE),
    _spell("cure sickness", "indigo", Skill.P_HEALING_SPELL, 32, 3, 3, 1,
           NODIR, CLR_BLUE),
    _spell("charm monster", "magenta", Skill.P_ENCHANTMENT_SPELL, 20, 3,
           5, 1, IMMEDIATE, CLR_MAGENTA),
    _spell("haste self", "purple", Skill.P_ESCAPE_SPELL, 33, 4, 3, 1, NODIR,
           CLR_MAGENTA),
    _spell("detect unseen", "violet", Skill.P_DIVINATION_SPELL, 20, 4, 3,
           1, NODIR, CLR_MAGENTA),
    _spell("levitation", "tan", Skill.P_ESCAPE_SPELL, 20, 4, 4, 1, NODIR,
           CLR_BROWN),
    _spell("extra healing", "plaid", Skill.P_HEALING_SPELL, 27, 5, 3, 1,
           IMMEDIATE, CLR_GREEN),
    _spell("restore ability", "light brown", Skill.P_HEALING_SPELL, 25,
           5, 4, 1, NODIR, CLR_BROWN),
    _spell("invisibility", "dark brown", Skill.P_ESCAPE_SPELL, 20, 5, 4, 1,
           NODIR, CLR_BROWN),
    _spell("detect treasure", "gray", Skill.P_DIVINATION_SPELL, 20, 5, 4,
           1, NODIR, CLR_GRAY),
    _spell("remove curse", "wrinkled", Skill.P_CLERIC_SPELL, 25, 5, 3, 1,
           NODIR, HI_PAPER),
    _spell("magic mapping", "dusty", Skill.P_DIVINATION_SPELL, 18, 7, 5,
           1, NODIR, HI_PAPER),
    _spell("identify", "bronze", Skill.P_DIVINATION_SPELL, 20, 6, 3, 1,
           NODIR, HI_COPPER),
    _spell("turn undead", "copper", Skill.P_CLERIC_SPELL, 16, 8, 6, 1,
           IMMEDIATE, HI_COPPER),
    _spell("polymorph", "silver", Skill.P_MATTER_SPELL, 10, 8, 6, 1,
           IMMEDIATE, HI_SILVER),
    _spell("teleport away", "gold", Skill.P_ESCAPE_SPELL, 15, 6, 6, 1,
           IMMEDIATE, HI_GOLD),
    _spell("create familiar", "glittering", Skill.P_CLERIC_SPELL, 10, 7,
           6, 1, NODIR, CLR_WHITE),
    _spell("cancellation", "shining", Skill.P_MATTER_SPELL, 15, 8, 7, 1,
           IMMEDIATE, CLR_WHITE),
    _spell("protection", "dull", Skill.P_CLERIC_SPELL, 18, 3, 1, 1, NODIR,
           HI_PAPER),
    _spell("jumping", "thin", Skill.P_ESCAPE_SPELL, 20, 3, 1, 1, IMMEDIATE,
           HI_PAPER),
    _spell("stone to flesh", "thick", Skill.P_HEALING_SPELL, 15, 1, 3, 1,
           IMMEDIATE, HI_PAPER),
    _spell("chain lightning", "checkered", Skill.P_ATTACK_SPELL, 25, 4, 2,
           1, NODIR, CLR_GRAY),
    # books with fixed descriptions
    _spell("blank paper", "plain", Skill.P_NONE, 18, 0, 0, 0, 0, HI_PAPER),
    # tribute book
    Object(name="novel", descr="paperback", oclass=ObjClass.SPBOOK,
           color=CLR_BRIGHT_BLUE, prob=1, weight=10, cost=20, oc2=1,
           nutrition=20, uses_known=True, material=Material.PAPER),
    # a special, one of a kind, spellbook
    Object(name="Book of the Dead", descr="papyrus", oclass=ObjClass.SPBOOK,
           color=HI_PAPER, weight=50, cost=10000, oc2=7, nutrition=20,
           uses_known=True, magic=True, unique=True, nowish=True,
           material=Material.PAPER),
    # wands (WAND(name, typ, prob, cost, mgc, dir, metal, color))
    _wand("light", "glass", 95, 100, 1, NODIR, Material.GLASS, HI_GLASS),
    _wand("secret door detection", "balsa", 50, 150, 1, NODIR,
          Material.WOOD, HI_WOOD),
    _wand("enlightenment", "crystal", 15, 150, 1, NODIR, Material.GLASS,
          HI_GLASS),
    _wand("create monster", "maple", 50, 200, 1, NODIR, Material.WOOD,
          HI_WOOD),
    _wand("wishing", "pine", 5, 500, 1, NODIR, Material.WOOD, HI_WOOD),
    _wand("stasis", "redwood", 45, 150, 1, NODIR, Material.WOOD, CLR_RED),
    _wand("nothing", "oak", 25, 100, 0, IMMEDIATE, Material.WOOD, HI_WOOD),
    _wand("striking", "ebony", 30, 150, 1, IMMEDIATE, Material.WOOD,
          HI_WOOD),
    _wand("make invisible", "marble", 45, 150, 1, IMMEDIATE,
          Material.MINERAL, HI_MINERAL),
    _wand("slow monster", "tin", 50, 150, 1, IMMEDIATE, Material.METAL,
          HI_METAL),
    _wand("speed monster", "brass", 50, 150, 1, IMMEDIATE, Material.COPPER,
          HI_COPPER),
    _wand("undead turning", "copper", 50, 150, 1, IMMEDIATE,
          Material.COPPER, HI_COPPER),
    _wand("polymorph", "silver", 45, 200, 1, IMMEDIATE, Material.SILVER,
          HI_SILVER),
    _wand("cancellation", "platinum", 45, 200, 1, IMMEDIATE,
          Material.PLATINUM, CLR_WHITE),
    _wand("teleportation", "iridium", 45, 200, 1, IMMEDIATE,
          Material.METAL, CLR_BRIGHT_CYAN),
    _wand("opening", "zinc", 30, 150, 1, IMMEDIATE, Material.METAL,
          HI_METAL),
    _wand("locking", "aluminum", 30, 150, 1, IMMEDIATE, Material.METAL,
          HI_METAL),
    _wand("probing", "uranium", 30, 150, 1, IMMEDIATE, Material.METAL,
          HI_METAL),
    _wand("digging", "iron", 40, 150, 1, RAY, Material.IRON, HI_METAL),
    _wand("magic missile", "steel", 50, 150, 1, RAY, Material.IRON,
          HI_METAL),
    _wand("fire", "hexagonal", 40, 175, 1, RAY, Material.IRON, HI_METAL),
    _wand("cold", "short", 40, 175, 1, RAY, Material.IRON, HI_METAL),
    _wand("sleep", "runed", 50, 175, 1, RAY, Material.IRON, HI_METAL),
    _wand("death", "long", 5, 500, 1, RAY, Material.IRON, HI_METAL),
    _wand("lightning", "curved", 40, 175, 1, RAY, Material.IRON, HI_METAL),
    # extra descriptions, shuffled into use at start of a new game
    _wand(None, "forked", 0, 150, 1, 0, Material.WOOD, HI_WOOD),
    _wand(None, "spiked", 0, 150, 1, 0, Material.IRON, HI_METAL),
    _wand(None, "jeweled", 0, 150, 1, 0, Material.IRON, HI_MINERAL),
    # coins
    _coin("gold piece", 1000, Material.GOLD, 1),
    # gems & rocks
    _gem("dilithium crystal", "white", 2, 1, 4500, 15, 5, Material.GEMSTONE,
         CLR_WHITE),
    _gem("diamond", "white", 3, 1, 4000, 15, 10, Material.GEMSTONE,
         CLR_WHITE),
    _gem("ruby", "red", 4, 1, 3500, 15, 9, Material.GEMSTONE, CLR_RED),
    _gem("jacinth", "orange", 3, 1, 3250, 15, 9, Material.GEMSTONE,
         CLR_ORANGE),
    _gem("sapphire", "blue", 4, 1, 3000, 15, 9, Material.GEMSTONE,
         CLR_BLUE),
    _gem("black opal", "black", 3, 1, 2500, 15, 8, Material.GEMSTONE,
         CLR_BLACK),
    _gem("emerald", "green", 5, 1, 2500, 15, 8, Material.GEMSTONE,
         CLR_GREEN),
    _gem("turquoise", "green", 6, 1, 2000, 15, 6, Material.GEMSTONE,
         CLR_GREEN),
    _gem("citrine", "yellow", 4, 1, 1500, 15, 6, Material.GEMSTONE,
         CLR_YELLOW),
    _gem("aquamarine", "green", 6, 1, 1500, 15, 8, Material.GEMSTONE,
         CLR_GREEN),
    _gem("amber", "yellowish brown", 8, 1, 1000, 15, 2, Material.GEMSTONE,
         CLR_BROWN),
    _gem("topaz", "yellowish brown", 10, 1, 900, 15, 8, Material.GEMSTONE,
         CLR_BROWN),
    _gem("jet", "black", 6, 1, 850, 15, 7, Material.GEMSTONE, CLR_BLACK),
    _gem("opal", "white", 12, 1, 800, 15, 6, Material.GEMSTONE, CLR_WHITE),
    _gem("chrysoberyl", "yellow", 8, 1, 700, 15, 5, Material.GEMSTONE,
         CLR_YELLOW),
    _gem("garnet", "red", 12, 1, 700, 15, 7, Material.GEMSTONE, CLR_RED),
    _gem("amethyst", "violet", 14, 1, 600, 15, 7, Material.GEMSTONE,
         CLR_MAGENTA),
    _gem("jasper", "red", 15, 1, 500, 15, 7, Material.GEMSTONE, CLR_RED),
    _gem("fluorite", "violet", 15, 1, 400, 15, 4, Material.GEMSTONE,
         CLR_MAGENTA),
    _gem("obsidian", "black", 9, 1, 200, 15, 6, Material.GEMSTONE,
         CLR_BLACK),
    _gem("agate", "orange", 12, 1, 200, 15, 6, Material.GEMSTONE,
         CLR_ORANGE),
    _gem("jade", "green", 10, 1, 300, 15, 6, Material.GEMSTONE, CLR_GREEN),
    # worthless glass
    _gem("worthless piece of white glass", "white", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_WHITE),
    _gem("worthless piece of blue glass", "blue", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_BLUE),
    _gem("worthless piece of red glass", "red", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_RED),
    _gem("worthless piece of yellowish brown glass", "yellowish brown", 77,
         1, 0, 6, 5, Material.GLASS, CLR_BROWN),
    _gem("worthless piece of orange glass", "orange", 76, 1, 0, 6, 5,
         Material.GLASS, CLR_ORANGE),
    _gem("worthless piece of yellow glass", "yellow", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_YELLOW),
    _gem("worthless piece of black glass", "black", 76, 1, 0, 6, 5,
         Material.GLASS, CLR_BLACK),
    _gem("worthless piece of green glass", "green", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_GREEN),
    _gem("worthless piece of violet glass", "violet", 77, 1, 0, 6, 5,
         Material.GLASS, CLR_MAGENTA),
    # stones (wishable "gray stones" range: luckstone..flint)
    _rock("luckstone", "gray", 0, 10, 10, 60, 3, 3, 1, 10, 7, Material.MINERAL,
          CLR_GRAY),
    _rock("loadstone", "gray", 0, 10, 500, 1, 3, 3, 1, 10, 6,
          Material.MINERAL, CLR_GRAY),
    _rock("touchstone", "gray", 0, 8, 10, 45, 3, 3, 1, 10, 6,
          Material.MINERAL, CLR_GRAY),
    _rock("flint", "gray", 0, 10, 10, 1, 6, 6, 0, 10, 7, Material.MINERAL,
          CLR_GRAY),
    _rock("rock", None, 1, 100, 10, 0, 3, 3, 0, 10, 7, Material.MINERAL,
          CLR_GRAY),
    # miscellaneous
    Object(name="boulder", descr=None, oclass=ObjClass.ROCK, color=HI_MINERAL,
           prob=100, weight=6000, wsdam=20, wldam=20, nutrition=2000,
           name_known=True, big=True, material=Material.MINERAL),
    Object(name="statue", descr=None, oclass=ObjClass.ROCK, color=CLR_WHITE,
           prob=900, weight=2500, wsdam=20, wldam=20, nutrition=2500,
           name_known=True, material=Material.MINERAL),
    Object(name="heavy iron ball", descr=None, oclass=ObjClass.BALL,
           color=HI_METAL, prob=1000, weight=480, cost=10, wsdam=25,
           wldam=25, nutrition=200, name_known=True, dir=WHACK,
           material=Material.IRON),
    Object(name="iron chain", descr=None, oclass=ObjClass.CHAIN,
           color=HI_METAL, prob=1000, weight=120, wsdam=4, wldam=4,
           nutrition=200, name_known=True, dir=WHACK,
           material=Material.IRON),
    # venom: normally transitory, but wishable in wizard mode
    Object(name="splash of blinding venom", descr="splash of venom",
           oclass=ObjClass.VENOM, color=HI_ORGANIC, prob=500, weight=1,
           merge=True, nowish=True, material=Material.LIQUID),
    Object(name="splash of acid venom", descr="splash of venom",
           oclass=ObjClass.VENOM, color=HI_ORGANIC, prob=500, weight=1,
           wsdam=6, wldam=6, merge=True, nowish=True,
           material=Material.LIQUID),
]


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


_validate()


def object_type(otyp: "ObjType | int") -> Object:
    """The table row for an object type (C: objects[otyp])."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    return OBJECTS[otyp]


__all__ = [
    "ObjClass", "Material", "Prop", "Skill", "ObjType", "Object",
    "OBJECTS", "object_type", "MAXOCLASSES", "NUM_OBJECTS",
    "LAST_GENERIC", "FIRST_OBJECT", "OBJCLASS_HACK", "FIRST_AMULET",
    "LAST_AMULET", "FIRST_SPELL", "LAST_SPELL", "FIRST_REAL_GEM",
    "LAST_REAL_GEM", "FIRST_GLASS_GEM", "LAST_GLASS_GEM",
    "NODIR", "IMMEDIATE", "RAY", "PIERCE", "SLASH", "WHACK",
    "ARM_SUIT", "ARM_SHIELD", "ARM_HELM", "ARM_GLOVES", "ARM_BOOTS",
    "ARM_CLOAK", "ARM_SHIRT",
    "CLR_BLACK", "CLR_RED", "CLR_GREEN", "CLR_BROWN", "CLR_BLUE",
    "CLR_MAGENTA", "CLR_CYAN", "CLR_GRAY", "NO_COLOR", "CLR_ORANGE",
    "CLR_BRIGHT_GREEN", "CLR_YELLOW", "CLR_BRIGHT_BLUE",
    "CLR_BRIGHT_MAGENTA", "CLR_BRIGHT_CYAN", "CLR_WHITE",
    "HI_METAL", "HI_COPPER", "HI_SILVER", "HI_GOLD", "HI_LEATHER",
    "HI_CLOTH", "HI_ORGANIC", "HI_WOOD", "HI_PAPER", "HI_GLASS",
    "HI_MINERAL", "DRAGON_SILVER",
]
