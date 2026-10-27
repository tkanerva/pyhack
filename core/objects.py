"""Object type table (port of src/objects.c + include/objects.h).

In the C source the table is produced from include/objects.h, which a
preprocessor pass expands three different ways (enum / description
array / struct array).  A Python port has to respect the same order --
the rows are built from the declarations -- so it is four modules:

- `objects_defs` -- the declarations: `ObjClass`, `Material`, `Prop`,
                   `Skill`, the glyph/symbol tables, the W_* masks,
                   the `Object` row type (struct objclass) and the
                   objects.h row macros as `_*` builders.  It imports
                   nothing from the rest of the package, so the
                   constants there are plain inferred ints/enums;
- `objects_data` -- the two large tables, kept verbatim and readable:
                   `_OBJTYPE_NAMES` (the OBJECTS_ENUM names, in C
                   order) and `OBJECTS` (the rows);
- `objects_enum` -- the OBJECTS_ENUM itself: the `ObjType` enum with
                   its 480 members and the C enum markers derived
                   from it (FIRST_OBJECT, LAST_SPELL, ...).  It is a
                   literal class body, not a table-driven functional
                   `IntEnum(...)`, so a type checker can see the
                   members (see the objects_enum docstring);
- this module    -- the assembly and the public API: `BASES`
                   (svb.bases[]), `object_type()` and the import-time
                   sanity checks; it re-exports the other three.

`ObjType` is the per-type enum (objects.h, OBJECTS_ENUM): C numbering
preserved exactly, including the generic-class slots [1..17] and the
markers.  `Objects` rows are written in exactly the order of
include/objects.h, so the index of every row equals its ObjType
value.  `BASES` holds the per-class base indices (C: svb.bases[]
from init_objects()); the first row of each class, with a fencepost
at [MAXOCLASSES].

Everything public is re-exported here, so `from .objects import ...`
reaches the whole table; only objects.py, objects_data.py,
objects_defs.py and objects_enum.py know about the split.

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

from .objects_enum import (
    ObjType, O, LAST_GENERIC, FIRST_OBJECT, OBJCLASS_HACK, FIRST_AMULET,
    LAST_AMULET, FIRST_SPELL, LAST_SPELL, FIRST_REAL_GEM, LAST_REAL_GEM,
    FIRST_GLASS_GEM, LAST_GLASS_GEM, NUM_OBJECTS,
)
from .objects_defs import (
    ObjClass, Material, Prop, Skill, Object, MAXOCLASSES, ClassSym,
    DEF_OC_SYMS, class_glyph, ILLOBJ_SYM, WEAPON_SYM, ARMOR_SYM, RING_SYM,
    AMULET_SYM, TOOL_SYM, FOOD_SYM, POTION_SYM, SCROLL_SYM, SPBOOK_SYM,
    WAND_SYM, GOLD_SYM, GEM_SYM, ROCK_SYM, BALL_SYM, CHAIN_SYM, VENOM_SYM,
    NODIR, IMMEDIATE, RAY, PIERCE, SLASH, WHACK, ARM_SUIT, ARM_SHIELD,
    ARM_HELM, ARM_GLOVES, ARM_BOOTS, ARM_CLOAK, ARM_SHIRT, W_ARM, W_ARMC,
    W_ARMH, W_ARMS, W_ARMG, W_ARMF, W_ARMU, W_ARMOR, W_WEP, W_QUIVER,
    W_SWAPWEP, W_WEAPONS, W_AMUL, W_RINGL, W_RINGR, W_RING, W_TOOL,
    W_ACCESSORY, CLR_BLACK, CLR_RED, CLR_GREEN, CLR_BROWN, CLR_BLUE,
    CLR_MAGENTA, CLR_CYAN, CLR_GRAY, NO_COLOR, CLR_ORANGE, CLR_BRIGHT_GREEN,
    CLR_YELLOW, CLR_BRIGHT_BLUE, CLR_BRIGHT_MAGENTA, CLR_BRIGHT_CYAN,
    CLR_WHITE, HI_METAL, HI_COPPER, HI_SILVER, HI_GOLD, HI_LEATHER, HI_CLOTH,
    HI_ORGANIC, HI_WOOD, HI_PAPER, HI_GLASS, HI_MINERAL, DRAGON_SILVER,
)

# C: NUM_SKILLS -- read by core.weapon; outside the documented
# __all__ above, so it is re-exported explicitly.
from .objects_defs import P_NUM_SKILLS  # noqa: F401

from .objects_data import OBJECTS, _OBJTYPE_NAMES


# ------------------------------------------------------------
# The object type enum (objects.h, OBJECTS_ENUM)
# ------------------------------------------------------------
# `ObjType` is the enum of the 480 object types, C numbering preserved:
# slot 0 is the real strange object, slots 1..17 are the generic class
# placeholders, and row i of OBJECTS belongs to the member with value
# i.  It lives in objects_enum.py as a literal class body -- the only
# form a type checker can read the members from -- together with the C
# markers derived from it (FIRST_OBJECT, LAST_SPELL, ...); all of them
# are re-exported here.
#
# (The old demo core's coarse-grained core.types.ObjectType is replaced
# by this enum as each system gets re-ported on the real table.)


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
    # The enum (objects_enum) and the table's name column are the two
    # expansions of the same C table.  Same names, same order, same
    # values -- a row added to one expansion and not the other fails
    # here, at import time.
    assert tuple(ObjType.__members__) == _OBJTYPE_NAMES, (
        "ObjType members and _OBJTYPE_NAMES disagree")
    for i, member in enumerate(ObjType):
        assert member.value == i, (
            f"{member.name} has value {member.value}, expected {i}")
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
    "ClassSym", "DEF_OC_SYMS", "class_glyph",
    "ILLOBJ_SYM", "WEAPON_SYM", "ARMOR_SYM", "RING_SYM", "AMULET_SYM",
    "TOOL_SYM", "FOOD_SYM", "POTION_SYM", "SCROLL_SYM", "SPBOOK_SYM",
    "WAND_SYM", "GOLD_SYM", "GEM_SYM", "ROCK_SYM", "BALL_SYM",
    "CHAIN_SYM", "VENOM_SYM",
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
