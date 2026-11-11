"""Object genesis (port of src/mkobj.c).

`mksobj()` makes one object of a known type; `mkobj()` picks a type
first; `mkgold()` and `mkcorpstat()` are the two special cases the level
generator wants by name.  Everything here *builds* an object and returns
it -- nothing is placed on the map except through `place_object()` /
`mkobj_at()` / `mksobj_at()`, because C's callers rely on that (a shop's
stock is built, then put in the right square; a chest's contents are
built, then added to the chest).

C provenance (all src/mkobj.c unless noted):

  mksobj()                       mksobj()
  mksobj_init()                  mksobj_init() (per class, see below)
  mkobj()                        mkobj()
  mkobj_at() / mksobj_at()       the same names
  rnd_class()                    rnd_class()
  mkbox_cnts()                   mkbox_cnts()
  mkgold()                       mkgold()
  mkcorpstat()                   mkcorpstat()
  set_corpsenm()                 set_corpsenm()
  weight()                       weight()
  bless()/unbless()/curse()/uncurse()/blessorcurse()/bcsign()
                                 the same names
  place_object()                 place_object()
  add_to_container() / delete_contents()
                                 the same names
  rndmonnum() / rndmonnum_adj()  the same names (a corpse / statue's
                                 subject is a makemon.rndmonst_adj draw,
                                 so genocide is honoured)
  mkobj_erosions() / may_generate_eroded()
                                 the same names
  next_ident()                   World.new_id()

Design (PLAN-MKOBJ.md decisions 1-8):

  - Containment is a list of *ids* on the parent (`Item.contents`),
    never an object graph: `add_to_container` / `delete_contents` are
    the only writers, and a contained item keeps `pos` and `carrier`
    None, so the three where-states stay mutually exclusive.
  - `mksobj()` never places: the "make and place" helpers are separate.
  - ids come from `World.new_id()`, so a generated object can never
    collide with the hand-formatted demo kit's ids.
  - an object exists from the moment it is built: `mksobj()` registers
    it in `World.items` (C: newobj() links it into the object free
    list, and every `contents` entry is an id that has to resolve), and
    `place_object()` / `add_to_container()` then set the where-state.
    The three states stay exclusive because *where* is read off
    `pos` / `carrier` / the parent's `contents` list, never off the
    registry.
  - `spe` is the C enchantment / charge field and the only counter the
    genesis writes; the demo's old `Item.charges` alias is GONE (the
    PLAN-INVENT.md phase A migration: `consume_obj_charge` decrements
    `spe`, and the wands / books / demo kit were re-pointed at it).
  - `weight()` takes the World because a container's contents live in
    `World.items` (C walks an obj chain); that keeps the object model
    graph-free without a module-level registry.

STUBs / simplifications (documented, not bugs):

  - **no timers** (corpse rot, egg hatching, oil burning, ice melting):
    `Item.age` is written where C writes it and read nowhere; the C
    start_*_timeout() calls are named in the comments.
  - **no artifacts**: `artif` is accepted and ignored, `oartifact`
    stays 0.
  - **no `splitobj`**: nothing in this wave needs to split a stack.
    `quan` alone covers gold piles, arrows and candles.
  - **`mksobj_init` is a subset per class**: the exotic per-otyp
    switches (tins, candy bars, kelp fronds, the invocation tools) fall
    through to the class default, which is C's own `default: break`.
  - `weight()`'s partially-eaten-food scaling (`eaten_stat`) keeps the
    full weight: `oeaten` is 0 for everything mksobj makes, and the
    meal bookkeeping in core.hunger owns the eaten-down case.
  - `mkobj_erosions` tests only flammability (core.worn.is_flammable):
    the rust / crack / rot / corrode material tests are not ported, so
    `oeroded2` is never generated yet.
  - `mkbox_cnts` does not merge: C's add_to_container merges compatible
    stacks, which is PLAN-MKOBJ.md phase E.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from . import invent, makemon, rules
from .mondata import is_female, is_male, is_neuter, undead_to_corpse
from .monst import (G_HELL, G_NOGEN, G_NOCORPSE, G_UNIQ, LOW_PM, MONS,
                    NON_PM, NUMMONS, PM_HUMAN, SPECIAL_PM)
from .objects import BASES, OBJECTS, ObjClass, ObjType
from .place import goodpos  # noqa: F401  (the random-placement check)
from .types import Item, ObjectType, Pos, World
from .worn import is_flammable

O = ObjType  # noqa: E741 -- the house alias for the object table

# C: objclass RANDOM_CLASS -- the "any class" request of mkobj().
RANDOM_CLASS = int(ObjClass.RANDOM)

#: C: SPBOOK_no_NOVEL -- the spellbook class without the novel (a
#: statue's contents in mksobj_init).
SPBOOK_no_NOVEL = -2

# C: the corpse / statue "who is it" values (obj.h CORPSTAT_*), stored
# in the overloaded `spe` field.
CORPSTAT_NONE = 0
CORPSTAT_FEMALE = 1
CORPSTAT_MALE = 2
CORPSTAT_NEUTER = 3

# C: obj.h MAX_OIL_IN_FLASK.
MAX_OIL_IN_FLASK = 1200


# ------------------------------------------------------------
# The class-frequency tables (C: mkobj.c 36-75, `struct icp`)
# ------------------------------------------------------------
#
# C has four: mkobjprobs (an ordinary level), hellprobs (Gehennom),
# rogueprobs (the rogue level) and boxiprobs (a container's contents).
# pyhack has no Gehennom and no rogue level, so only the first and the
# last have a caller -- the other two are absent rather than unused
# (the class roll is behind mkobj(), which is where they would land).

#: (probability, class) -- C: mkobjprobs[]
MKOBJPROBS: Tuple[Tuple[int, int], ...] = (
    (10, int(ObjClass.WEAPON)),
    (11, int(ObjClass.ARMOR)),
    (20, int(ObjClass.FOOD)),
    (8, int(ObjClass.TOOL)),
    (7, int(ObjClass.GEM)),
    (16, int(ObjClass.POTION)),
    (16, int(ObjClass.SCROLL)),
    (4, int(ObjClass.SPBOOK)),
    (4, int(ObjClass.WAND)),
    (3, int(ObjClass.RING)),
    (1, int(ObjClass.AMULET)),
)

#: (probability, class) -- C: boxiprobs[]
BOXIPROBS: Tuple[Tuple[int, int], ...] = (
    (18, int(ObjClass.GEM)),
    (15, int(ObjClass.FOOD)),
    (18, int(ObjClass.POTION)),
    (18, int(ObjClass.SCROLL)),
    (12, int(ObjClass.SPBOOK)),
    (7, int(ObjClass.COIN)),
    (6, int(ObjClass.WAND)),
    (5, int(ObjClass.RING)),
    (1, int(ObjClass.AMULET)),
)

# The coarse core.types.ObjectType tag a generated Item carries (the
# table-driven systems key off `oclass`; `otype` is the class-level tag
# the console's glyph map and the older systems use).
_COARSE_CLASS: Dict[int, ObjectType] = {
    int(ObjClass.WEAPON): ObjectType.WEAPON,
    int(ObjClass.ARMOR): ObjectType.ARMOR,
    int(ObjClass.RING): ObjectType.RING,
    int(ObjClass.AMULET): ObjectType.AMULET,
    int(ObjClass.TOOL): ObjectType.TOOL,
    int(ObjClass.FOOD): ObjectType.FOOD,
    int(ObjClass.POTION): ObjectType.POTION,
    int(ObjClass.SCROLL): ObjectType.SCROLL,
    int(ObjClass.SPBOOK): ObjectType.BOOK,
    int(ObjClass.WAND): ObjectType.WAND,
    int(ObjClass.COIN): ObjectType.COIN,
    int(ObjClass.GEM): ObjectType.GEM,
    int(ObjClass.ROCK): ObjectType.BOULDER,
    int(ObjClass.BALL): ObjectType.TOOL,
    int(ObjClass.CHAIN): ObjectType.TOOL,
    int(ObjClass.VENOM): ObjectType.TOOL,
    int(ObjClass.ILLOBJ): ObjectType.TOOL,
}


def coarse_otype(otyp: int) -> ObjectType:
    """The ObjectType tag for an otyp: the class tag, except for the
    four object types that have a tag of their own (corpse, egg, statue,
    boulder)."""
    oclass = int(OBJECTS[otyp].oclass)
    if otyp == int(O.CORPSE):
        return ObjectType.CORPSE
    if otyp == int(O.EGG):
        return ObjectType.EGG
    if otyp == int(O.STATUE):
        return ObjectType.STATUE
    if otyp == int(O.BOULDER):
        return ObjectType.BOULDER
    return _COARSE_CLASS.get(oclass, ObjectType.TOOL)


# ------------------------------------------------------------
# Small predicates (C: obj.h macros)
# ------------------------------------------------------------

def is_container(item: Item) -> bool:
    """C: Is_container -- LARGE_BOX .. BAG_OF_TRICKS (C 5.0's macro is
    that otyp range; the core.objects docstring says the same)."""
    return int(O.LARGE_BOX) <= item.otyp <= int(O.BAG_OF_TRICKS)


def is_multigen(item: Item) -> bool:
    """C: is_multigen -- ammunition comes in a bundle.  C tests the
    weapon skill range; the ammo rows are exactly the ones with a
    negative skill (core.objects._validate asserts that), so this is the
    same test without the skill table."""
    return int(OBJECTS[item.otyp].oclass) == int(ObjClass.WEAPON) \
        and OBJECTS[item.otyp].subtyp < 0


def is_ismnum(corpsenm: int) -> bool:
    """C: ismnum -- the object carries a monster type, and this port has
    the table row for it."""
    return LOW_PM <= corpsenm < NUMMONS and MONS[corpsenm] is not None


def bcsign(item: Item) -> int:
    """C: bcsign -- +1 blessed, -1 cursed, 0 otherwise."""
    return int(bool(item.blessed)) - int(bool(item.cursed))


# ------------------------------------------------------------
# The BUC lottery (C: mkobj.c 1856-1902)
# ------------------------------------------------------------

def bless(item: Item) -> None:
    """C: bless."""
    item.blessed = True
    item.cursed = False


def unbless(item: Item) -> None:
    """C: unbless."""
    item.blessed = False


def curse(item: Item) -> None:
    """C: curse."""
    item.cursed = True
    item.blessed = False


def uncurse(item: Item) -> None:
    """C: uncurse."""
    item.cursed = False


def blessorcurse(rng, item: Item, chance: int) -> None:
    """Give a fresh object a 1-in-`chance` chance of being blessed or
    cursed (C: mkobj.c#blessorcurse).

    One function, not four calls: an already-BUC object is left alone
    (so a second call is a no-op) and blessed / cursed stay mutually
    exclusive.
    """
    if item.blessed or item.cursed:
        return
    if not rng.rn2(chance):
        if not rng.rn2(2):
            curse(item)
        else:
            bless(item)


# ------------------------------------------------------------
# weight (C: mkobj.c 1903-1991)
# ------------------------------------------------------------

def weight(world: World, item: Item) -> int:
    """An object's weight in 1/100 lb (C: mkobj.c#weight).

    A stack weighs its unit weight times `quan` (a zero-weight unit
    weighs one unit per two items, C's `(quan + 1) >> 1`); a container
    adds its contents, a bag of holding scales them by its BUC state, a
    corpse weighs what its species weighs, and gold is one unit per 100
    coins with a floor of 1.
    """
    wt = OBJECTS[item.otyp].weight
    if item.quan < 1:
        return 0                      # C: impossible(), and 0

    if is_container(item) or item.otyp == int(O.STATUE):
        if item.otyp == int(O.STATUE) and is_ismnum(item.corpsenm):
            ptr = MONS[item.corpsenm]
            assert ptr is not None    # is_ismnum proved the row exists
            msize = int(ptr.msize)
            minwt = (msize + msize + 1) * 100
            # a statue weighs one and a half corpses
            wt = 3 * ptr.cwt // 2
            if wt < minwt:
                wt = minwt
            wt *= item.quan           # no effect: statues never stack
        cwt = 0
        for child_id in item.contents:
            child = world.items.get(child_id)
            if child is not None:
                cwt += weight(world, child)
        if item.otyp == int(O.BAG_OF_HOLDING):
            # cursed doubles, blessed quarters, otherwise halves
            # (rounded up, the DELTA_CWT equations in pickup.c)
            cwt = cwt * 2 if item.cursed \
                else (cwt + 3) // 4 if item.blessed else (cwt + 1) // 2
        return wt + cwt

    if item.otyp == int(O.CORPSE) and is_ismnum(item.corpsenm):
        ptr = MONS[item.corpsenm]
        assert ptr is not None
        return item.quan * ptr.cwt
    oclass = int(OBJECTS[item.otyp].oclass)
    if oclass == int(ObjClass.FOOD) and item.oeaten:
        # C: eaten_stat(quan * wt, obj) -- the eaten-down scaling.
        # oeaten is 0 for everything mksobj() makes, so the full weight
        # is right here and the meal bookkeeping owns the rest.
        return item.quan * wt
    if oclass == int(ObjClass.COIN):
        return max((item.quan + 50) // 100, 1)
    if item.otyp == int(O.HEAVY_IRON_BALL) and item.owt != 0:
        return item.owt               # kludge for "very" heavy iron ball
    if item.otyp == int(O.CANDELABRUM_OF_INVOCATION) and item.spe:
        return wt + item.spe * OBJECTS[int(O.TALLOW_CANDLE)].weight
    return wt * item.quan if wt else (item.quan + 1) >> 1


# ------------------------------------------------------------
# mksobj / mksobj_init (C: mkobj.c 869-1259)
# ------------------------------------------------------------

def mksobj(world: World, rng, otyp: int, init: bool = True,
           artif: bool = False) -> Item:
    """Create one object of type `otyp` (C: mkobj.c#mksobj).

    Always returns an object and never places it.  The order is C's: the
    id, the class, the per-class initialisation, then the fixups that
    must happen even when `init` is False (a corpse's subject, a
    statue's gender, the oil in a flask), then the weight.

    The object is registered in `World.items` as soon as it is built
    (see the module docstring); it is *not* on the map -- `pos` and
    `carrier` stay None until place_object() / add_to_container().
    """
    row = OBJECTS[otyp]
    item = Item(id=world.new_id("obj"), otype=coarse_otype(otyp),
                name=row.name if row.name is not None else "strange object",
                otyp=otyp, oclass=int(row.oclass), lev=world.lev)
    world.items[item.id] = item
    item.age = max(world.turn, 1)
    item.quan = 1
    item.corpsenm = NON_PM
    unknow_object(item)

    if init:
        mksobj_init(world, rng, item, artif)

    # some things must get done (corpsenm) even if init = 0; C's switch
    # key is "a potion that is not oil is treated as water"
    key = int(O.POT_WATER) if (item.oclass == int(ObjClass.POTION)
                               and otyp != int(O.POT_OIL)) else otyp
    if key in (int(O.CORPSE), int(O.STATUE), int(O.FIGURINE), int(O.EGG)):
        if item.corpsenm == NON_PM:
            item.corpsenm = (_corpse_subject(world, rng)
                             if key == int(O.CORPSE)
                             else rndmonnum(world, rng))
        if key != int(O.EGG) and is_ismnum(item.corpsenm):
            ptr = MONS[item.corpsenm]
            assert ptr is not None
            # C: the gender goes in the overloaded spe field
            item.spe = (CORPSTAT_NEUTER if is_neuter(ptr)
                        else CORPSTAT_FEMALE if is_female(ptr)
                        else CORPSTAT_MALE if is_male(ptr)
                        else CORPSTAT_FEMALE if rng.rn2(2)
                        else CORPSTAT_MALE)
        set_corpsenm(world, item, item.corpsenm)
    elif key == int(O.POT_OIL):
        item.age = MAX_OIL_IN_FLASK
    # C: POT_WATER's fromsink and LEASH's leashmon overload corpsenm,
    # which already reads NON_PM here -- nothing to do

    item.owt = weight(world, item)
    return item


def unknow_object(item: Item) -> None:
    """C: unknow_object -- set up dknown / known for a fresh object.

    An object whose name is always known starts known; everything else
    starts unknown and becomes known through use (core.o_init's
    discover_object, applied by core.rules.apply_discovery).
    """
    row = OBJECTS[item.otyp]
    if row.name_known or row.descr is None:
        item.known = True
        item.dknown = True


def mksobj_init(world: World, rng, item: Item, artif: bool) -> None:
    """Per-class initialisation of a fresh object (C:
    mkobj.c#mksobj_init).

    The classes in C's switch order, with the subset each can honour
    here (the module docstring lists what is skipped): weapons and
    armour roll their enchantment and their BUC state, food its quantity
    and its corpse / egg subject, wands and rings their charges,
    containers their lock / trap state and contents, gems and rocks
    their quantity, tools the per-type switch.
    """
    del artif                          # no artifacts: accepted, ignored
    otyp = item.otyp
    oclass = item.oclass
    ulevel = world.hero_ulevel

    if oclass == int(ObjClass.WEAPON):
        item.quan = rng.rn1(6, 6) if is_multigen(item) else 1
        if not rng.rn2(11):
            item.spe = rng.rne(3, ulevel)
            item.blessed = bool(rng.rn2(2))
        elif not rng.rn2(10):
            curse(item)
            item.spe = -rng.rne(3, ulevel)
        else:
            blessorcurse(rng, item, 10)
        # C: is_poisonable(otmp) && !rn2(100) -> opoisoned; Item has no
        # poisoned field yet and nothing reads one
    elif oclass == int(ObjClass.FOOD):
        item.oeaten = 0
        if otyp == int(O.CORPSE):
            item.corpsenm = _corpse_subject(world, rng)
        elif otyp == int(O.EGG):
            item.corpsenm = NON_PM     # generic egg (typed eggs: later)
        # C also has the TIN / SLIME_MOLD / KELP_FROND / CANDY_BAR
        # cases; those rows are not reachable from the generation
        # tables yet, so they stay at the class default
        if otyp not in (int(O.CORPSE), int(O.MEAT_RING),
                        int(O.KELP_FROND)) and not rng.rn2(6):
            item.quan = 2
    elif oclass == int(ObjClass.GEM):
        item.corpsenm = 0               # C: the LOADSTONE hack
        if otyp == int(O.LOADSTONE):
            curse(item)
        elif otyp == int(O.ROCK):
            item.quan = rng.rn1(6, 6)
        elif otyp != int(O.LUCKSTONE) and not rng.rn2(6):
            item.quan = 2
        else:
            item.quan = 1
    elif oclass == int(ObjClass.TOOL):
        if otyp in (int(O.TALLOW_CANDLE), int(O.WAX_CANDLE)):
            item.spe = 1
            item.age = 20 * OBJECTS[otyp].cost
            item.quan = 1 + (rng.rn2(7) if rng.rn2(2) else 0)
            blessorcurse(rng, item, 5)
        elif otyp in (int(O.BRASS_LANTERN), int(O.OIL_LAMP)):
            item.spe = 1
            item.age = rng.rn1(500, 1000)
            blessorcurse(rng, item, 5)
        elif otyp == int(O.MAGIC_LAMP):
            item.spe = 1
            blessorcurse(rng, item, 2)
        elif otyp in (int(O.CHEST), int(O.LARGE_BOX)):
            item.olocked = bool(rng.rn2(5))
            item.otrapped = not rng.rn2(10)
            mkbox_cnts(world, rng, item)
        elif otyp in (int(O.ICE_BOX), int(O.SACK), int(O.OILSKIN_SACK),
                      int(O.BAG_OF_HOLDING)):
            mkbox_cnts(world, rng, item)
        elif otyp in (int(O.EXPENSIVE_CAMERA), int(O.TINNING_KIT),
                      int(O.MAGIC_MARKER)):
            item.spe = rng.rn1(70, 30)
        elif otyp == int(O.CAN_OF_GREASE):
            item.spe = rng.rn1(21, 5)
            blessorcurse(rng, item, 10)
        elif otyp == int(O.CRYSTAL_BALL):
            item.spe = rng.rn1(5, 3)
            blessorcurse(rng, item, 2)
        elif otyp in (int(O.HORN_OF_PLENTY), int(O.BAG_OF_TRICKS)):
            item.spe = rng.rn1(18, 3)
        elif otyp == int(O.BELL_OF_OPENING):
            item.spe = 3
        elif otyp in (int(O.MAGIC_FLUTE), int(O.MAGIC_HARP),
                      int(O.FROST_HORN), int(O.FIRE_HORN),
                      int(O.DRUM_OF_EARTHQUAKE)):
            item.spe = rng.rn1(5, 4)
        elif otyp == int(O.FIGURINE):
            item.corpsenm = rndmonnum_adj(world, rng, 5, 10)
            blessorcurse(rng, item, 4)
    elif oclass == int(ObjClass.AMULET):
        if rng.rn2(10) and otyp in (int(O.AMULET_OF_STRANGULATION),
                                    int(O.AMULET_OF_CHANGE),
                                    int(O.AMULET_OF_RESTFUL_SLEEP)):
            curse(item)
        else:
            blessorcurse(rng, item, 10)
    elif oclass in (int(ObjClass.POTION), int(ObjClass.SCROLL)):
        blessorcurse(rng, item, 4)
    elif oclass == int(ObjClass.SPBOOK):
        blessorcurse(rng, item, 17)
    elif oclass == int(ObjClass.ARMOR):
        # C: `rn2(10) && (otyp == FUMBLE_BOOTS || ... || !rn2(11))`
        if rng.rn2(10) and (otyp in (int(O.FUMBLE_BOOTS),
                                     int(O.LEVITATION_BOOTS))
                            or not rng.rn2(11)):
            curse(item)
            item.spe = -rng.rne(3, ulevel)
        elif not rng.rn2(10):
            item.blessed = bool(rng.rn2(2))
            item.spe = rng.rne(3, ulevel)
        else:
            blessorcurse(rng, item, 10)
    elif oclass == int(ObjClass.WAND):
        if OBJECTS[otyp].dir == 0:      # C: NODIR wands hold more charges
            item.spe = rng.rn1(5, 11)
        else:
            item.spe = rng.rn1(5, 4)
        blessorcurse(rng, item, 17)
        item.recharged = 0
    elif oclass == int(ObjClass.RING):
        if OBJECTS[otyp].charged:
            blessorcurse(rng, item, 3)
            if rng.rn2(10):
                if rng.rn2(10) and bcsign(item):
                    item.spe = bcsign(item) * rng.rne(3, ulevel)
                else:
                    item.spe = (rng.rne(3, ulevel) if rng.rn2(2)
                                else -rng.rne(3, ulevel))
            # make useless +0 rings much less common
            if item.spe == 0:
                item.spe = rng.rn2(4) - rng.rn2(3)
            # negative rings are usually cursed
            if item.spe < 0 and rng.rn2(5):
                curse(item)
        elif rng.rn2(10) and (otyp in (int(O.RIN_TELEPORTATION),
                                       int(O.RIN_POLYMORPH),
                                       int(O.RIN_AGGRAVATE_MONSTER),
                                       int(O.RIN_HUNGER))
                              or not rng.rn2(9)):
            curse(item)
    elif oclass == int(ObjClass.ROCK):
        if otyp == int(O.STATUE):
            # possibly overridden by mkcorpstat()
            item.corpsenm = rndmonnum(world, rng)
            if not _verysmall(item.corpsenm) \
                    and rng.rn2(rules.level_difficulty(world) // 2 + 10) > 10:
                add_to_container(world, item,
                                 mkobj(world, rng, SPBOOK_no_NOVEL))
        # C: the boulder case is handled in the "regardless of !init"
        # tail -- there is nothing to set until boulders can be thrown
    elif oclass == int(ObjClass.COIN):
        pass                            # do nothing
    # C's default case is a panic("mksobj tried to make type ..."); every
    # class above is handled, so there is nothing to panic about

    mkobj_erosions(world, rng, item)


def _verysmall(corpsenm: int) -> bool:
    """C: verysmall -- a statue of a small monster holds no spellbook."""
    if not is_ismnum(corpsenm):
        return True
    ptr = MONS[corpsenm]
    assert ptr is not None
    return int(ptr.msize) <= 1


def _corpse_subject(world: World, rng) -> int:
    """The monster type of a random corpse (C: the CORPSE case of
    mksobj_init).

    Fifty tries at a species that leaves a corpse; if the level only
    offers the never-leaves-a-corpse ones, an adventurer's corpse
    instead (C: PM_HUMAN).
    """
    tryct = 50
    while tryct > 0:
        mndx = undead_to_corpse(rndmonnum(world, rng))
        if not (world.mon_state.mvitals[mndx].mvflags & G_NOCORPSE):
            return mndx
        tryct -= 1
    return PM_HUMAN


def mkobj_erosions(world: World, rng, item: Item) -> None:
    """A small fraction of gear generates worn-out (C:
    mkobj.c#mkobj_erosions).

    A tiny fraction is erodeproof *instead*; an erodable item may also
    generate greased.  STUB: only the flammability test is ported
    (core.worn.is_flammable), so `oeroded2` (rust / rot / corrode) is
    never generated yet, and `oerodeproof` has no field.
    """
    del world
    if not may_generate_eroded(item):
        return
    if not rng.rn2(100):
        return                          # C: oerodeproof
    if not rng.rn2(80) and is_flammable(item):
        while True:
            item.oeroded += 1
            if item.oeroded >= 3 or rng.rn2(9):
                break
    if not rng.rn2(1000):
        item.greased = True


def may_generate_eroded(item: Item) -> bool:
    """C: may_generate_eroded -- weapons and armour erode; the other
    classes do not (C also excludes artifacts, which do not exist)."""
    return item.oclass in (int(ObjClass.WEAPON), int(ObjClass.ARMOR))


def set_corpsenm(world: World, item: Item, mndx: int) -> None:
    """Record the monster type of a corpse / statue (C:
    mkobj.c#set_corpsenm).

    STUB: the C body also starts (or stops) the revive / rot timers;
    pyhack has no timeout.c, so the field is written and the weight
    updated -- which is all the level generator needs.
    """
    item.corpsenm = mndx
    item.owt = weight(world, item)


# ------------------------------------------------------------
# Containers (C: mkobj.c mkbox_cnts / add_to_container / delete_contents)
# ------------------------------------------------------------

def add_to_container(world: World, container: Item, item: Item) -> None:
    """Put `item` inside `container` (C: mkobj.c#add_to_container).

    A contained item has no position and no carrier -- the parent's id in
    `contents` is the only reference -- and it is registered in
    World.items, so it stays reachable exactly twice (the world's dict
    and the container's list): the invariant the tests assert.  C merges
    compatible stacks first; pyhack's merge rules are PLAN-MKOBJ.md
    phase E, so nothing merges yet.
    """
    item.pos = None
    item.carrier = None
    item.lev = container.lev
    container.contents.append(item.id)
    world.items[item.id] = item
    container.owt = weight(world, container)


def delete_contents(world: World, container: Item) -> None:
    """Empty a container, deleting what was inside (C:
    mkobj.c#delete_contents -- the "the container was destroyed" path,
    so the contents go with it)."""
    for child_id in list(container.contents):
        world.items.pop(child_id, None)
    container.contents = []


def mkbox_cnts(world: World, rng, box: Item) -> None:
    """Fill a container (C: mkobj.c#mkbox_cnts).

    The per-type count is C's: an ice box holds up to 20 corpses, a
    chest 5 (7 when locked), a large box 3 (5 when locked), a sack or a
    bag of holding up to 1.  The contents are then drawn from
    `boxiprobs` and made with mkobj(), with C's two special cases -- a
    coin pile gets a quantity, a rock is swapped for a real gem.

    The ice box's corpses get `age = 0`, which is what "inside an ice
    box" means to the rot timer; there is no timer here, so the field is
    written and read nowhere.
    """
    box.contents = []
    if box.otyp == int(O.ICE_BOX):
        n = 20
    elif box.otyp == int(O.CHEST):
        n = 7 if box.olocked else 5
    elif box.otyp == int(O.LARGE_BOX):
        n = 5 if box.olocked else 3
    elif box.otyp in (int(O.SACK), int(O.OILSKIN_SACK),
                      int(O.BAG_OF_HOLDING)):
        # C: a starting sack is empty; there is no starting inventory
        # path through mksobj yet, so the "up to 1" stands
        n = 1
    else:
        n = 0

    for _ in range(rng.rn2(n + 1)):
        if box.otyp == int(O.ICE_BOX):
            otmp = mksobj(world, rng, int(O.CORPSE))
            otmp.age = 0
        else:
            oclass = _pick_class(rng, BOXIPROBS)
            otmp = mkobj(world, rng, oclass)
            if otmp.oclass == int(ObjClass.COIN):
                # 2.5 times the level's usual amount; weight fixed below
                otmp.quan = rng.rnd(rules.level_difficulty(world) + 2) \
                    * rng.rnd(75)
            else:
                while otmp.otyp == int(O.ROCK):
                    otmp = mksobj(world, rng,
                                  rnd_class(world, rng,
                                            int(O.DILITHIUM_CRYSTAL),
                                            int(O.LOADSTONE)))
                    if otmp.quan > 2:
                        otmp.quan = 1
            if box.otyp == int(O.BAG_OF_HOLDING):
                if otmp.otyp == int(O.BAG_OF_HOLDING):
                    otmp = mksobj(world, rng, int(O.SACK))
                else:
                    while otmp.otyp == int(O.WAN_CANCELLATION):
                        otmp = mksobj(world, rng,
                                      rnd_class(world, rng,
                                                int(O.WAN_LIGHT),
                                                int(O.WAN_LIGHTNING)))
        add_to_container(world, box, otmp)
    box.owt = weight(world, box)


# ------------------------------------------------------------
# mkobj / rnd_class -- picking an object type
# (C: mkobj.c 270-301, 509-530 rnd_class)
# ------------------------------------------------------------

def _pick_class(rng, probs: Tuple[Tuple[int, int], ...]) -> int:
    """Walk a `struct icp` table with one rnd(100) (C: the class loop at
    the top of mkobj()/mkbox_cnts())."""
    tprob = rng.rnd(100)
    for prob, iclass in probs:
        tprob -= prob
        if tprob <= 0:
            return iclass
    return probs[-1][1]


def rnd_class(world: World, rng, o_low: int, o_high: int) -> int:
    """A random object type between o_low and o_high, weighted by the
    current per-type probability (C: mkobj.c#rnd_class).

    The probabilities come from `world.obj_tables.prob`, not from the
    frozen OBJECTS rows, because setgemprobs() adjusts the gems per
    level -- that is the whole reason ObjTables.prob exists
    (PLAN-MKOBJ.md decision C.2).
    """
    prob = world.obj_tables.prob
    total = sum(prob[i] for i in range(o_low, o_high + 1))
    if not total:
        return rng.rnd(o_high - o_low + 1) + o_low - 1
    x = rng.rnd(total)
    i = o_low
    while i <= o_high:
        x -= prob[i]
        if x <= 0:
            return i
        i += 1
    return o_high


def mkobj(world: World, rng, oclass: int = RANDOM_CLASS,
          artif: bool = False) -> Item:
    """Make a random object of class `oclass` (C: mkobj.c#mkobj).

    RANDOM_CLASS rolls the class from mkobjprobs first; SPBOOK_no_NOVEL
    is the spellbook class without the novel.  The within-class roll uses
    ObjTables.prob (see _rnd_class).
    """
    if oclass == RANDOM_CLASS:
        oclass = _pick_class(rng, MKOBJPROBS)

    if oclass == SPBOOK_no_NOVEL:
        i = rnd_class(world, rng, BASES[int(ObjClass.SPBOOK)],
                      int(O.SPE_BLANK_PAPER))
        oclass = int(ObjClass.SPBOOK)
    else:
        prob = rng.rnd(world.obj_tables.prob_totals[oclass])
        i = BASES[oclass]
        while prob > 0:
            prob -= world.obj_tables.prob[i]
            if prob > 0:
                i += 1

    if int(OBJECTS[i].oclass) != oclass or OBJECTS[i].name is None:
        # C: impossible("probtype error"), fall back on the class base
        i = BASES[oclass]

    return mksobj(world, rng, i, True, artif)


def mkobj_at(world: World, rng, oclass: int, pos: Pos, lev: int,
             artif: bool = False) -> Item:
    """A random object of `oclass`, placed on the map (C:
    mkobj.c#mkobj_at)."""
    item = mkobj(world, rng, oclass, artif)
    place_object(world, item, pos, lev)
    return item


def mksobj_at(world: World, rng, otyp: int, pos: Pos, lev: int,
              init: bool = True, artif: bool = False) -> Item:
    """A specific object type, placed on the map (C:
    mkobj.c#mksobj_at)."""
    item = mksobj(world, rng, otyp, init, artif)
    place_object(world, item, pos, lev)
    return item


def place_object(world: World, item: Item, pos: Pos, lev: int) -> None:
    """Put an object on the map (C: mkobj.c#place_object).

    C links the object into the level's `objects[x][y]` chain; here the
    position and the level are set and the object is registered in
    World.items (the "floor item" state of the three).
    """
    item.pos = pos
    item.carrier = None
    item.lev = lev
    world.items[item.id] = item


# ------------------------------------------------------------
# Gold (C: mkobj.c mkgold / mkmonmoney is in core.makemon)
# ------------------------------------------------------------

def gold_at(world: World, lev: int, pos: Pos) -> Optional[Item]:
    """The gold pile on a square, if any (C: g_at)."""
    for item in world.items.values():
        if (item.lev == lev and item.pos == pos
                and item.oclass == int(ObjClass.COIN)):
            return item
    return None


def sobj_at(world: World, otyp: int, lev: int, pos: Pos) -> Optional[Item]:
    """The first floor object of exact type `otyp` at `pos` on level
    `lev`, if any (C: invent.c#sobj_at -- the stack walk with the
    `otmp->otyp == otyp` test)."""
    for item in world.items.values():
        if item.lev == lev and item.pos == pos and item.otyp == otyp:
            return item
    return None


def mkgold(world: World, rng, amount: int, pos: Pos, lev: int) -> Item:
    """A pile of `amount` gold pieces on `pos`, or a random amount when
    amount <= 0 (C: mkobj.c#mkgold).

    Gold already on the square is added to rather than stacked beside
    (C: `if (gold) gold->quan += amount`), which is what keeps a vault's
    hoard one object.
    """
    if amount <= 0:
        mul = rng.rnd(30 // max(12 - rules.level_difficulty(world), 2))
        amount = 1 + rng.rnd(rules.level_difficulty(world) + 2) * mul
    gold = gold_at(world, lev, pos)
    if gold is not None:
        gold.quan += amount
    else:
        gold = mksobj(world, rng, int(O.GOLD_PIECE))
        gold.quan = amount
        place_object(world, gold, pos, lev)
    gold.owt = weight(world, gold)
    return gold


def hero_gold(world: World) -> int:
    """How much gold the hero carries (C: the money count behind
    `u.ugold`).  A gold pile is one object whose `quan` is the amount.

    C's name for the reading is ``invent.money_cnt``, which is where it
    lives now (PLAN-INVENT.md phase E: whichever phase lands the
    function owns it and the other drops its copy); this name stays
    because the shop plan and ``uhitm.steal_it`` speak of it.
    """
    return invent.money_cnt(world.hero)


# ------------------------------------------------------------
# Corpses and statues (C: mkobj.c mkcorpstat / rndmonnum)
# ------------------------------------------------------------

def mkcorpstat(world: World, rng, otyp: int, mon: Optional[object] = None,
               ptr: Optional[object] = None, pos: Pos = (0, 0),
               lev: Optional[int] = None, init: bool = True,
               spe: int = CORPSTAT_NONE) -> Item:
    """Make a corpse or a statue of a monster type (C:
    mkobj.c#mkcorpstat).

    `mon` is a dead Monster and `ptr` its overriding PerMonst; either
    may be None, in which case mksobj()'s random subject stands.  The
    gender / "historic statue" marker goes in the overloaded `spe` field,
    as in C.  A (0, 0) position means "somewhere on the level".
    """
    if otyp not in (int(O.CORPSE), int(O.STATUE)):
        raise ValueError(f"mkcorpstat of type {otyp} is not a corpse/statue")
    lev = world.lev if lev is None else lev
    if pos == (0, 0):
        item = mksobj(world, rng, otyp, init, False)
        _rloco(world, rng, item, lev)
    else:
        item = mksobj_at(world, rng, otyp, pos, lev, init, False)
    item.spe = spe
    if mon is not None:
        # C: save_mtraits() keeps the individual's details for a
        # revive; there is no revive here, so only the type is kept
        if ptr is None:
            ptr = getattr(mon, "mdata", None)
    if ptr is not None:
        item.corpsenm = ptr.pmidx          # type: ignore[attr-defined]
        item.owt = weight(world, item)
    return item


def _rloco(world: World, rng, item: Item, lev: int) -> None:
    """C: rloco -- put an object on a random square of the level (the C
    original is the "random location" case of mkcorpstat; a full map
    leaves the object unplaced)."""
    map_ = world.map
    floor = map_.floor_tiles()
    if floor:
        place_object(world, item, floor[rng.rn2(len(floor))], lev)
        return
    hero = world.hero_or_none
    if hero is None:
        # no square and no hero (a level being generated): the object
        # stays built but unplaced -- C's rloco would have nowhere to
        # put it either
        world.items[item.id] = item
        return
    place_object(world, item, hero.pos, lev)


def rndmonnum(world: World, rng) -> int:
    """A random monster type index (C: mkobj.c#rndmonnum)."""
    return rndmonnum_adj(world, rng, 0, 0)


def rndmonnum_adj(world: World, rng, minadj: int, maxadj: int) -> int:
    """A random monster type index with adjusted difficulty (C:
    mkobj.c#rndmonnum_adj).

    Plan A is the same weighted sample makemon() uses, so a corpse's
    subject and a spawned monster can never disagree about what exists
    (or about what has been genocided).  Plan B -- only when nothing is
    eligible -- takes any never-unique, generatable species, which is
    C's `rn1(SPECIAL_PM - LOW_PM, LOW_PM)` loop.
    """
    ptr = makemon.rndmonst_adj(world, rng, minadj, maxadj)
    if ptr is not None:
        return ptr.pmidx

    excludeflags = G_UNIQ | G_NOGEN | G_HELL
    for _ in range(200):
        i = rng.rn1(SPECIAL_PM - LOW_PM, LOW_PM)
        row = MONS[i]
        if row is not None and not (row.geno & excludeflags):
            return i
    # a level whose whole table is genocided: C would spin forever, so
    # fall back on the first implemented species that qualifies
    for i in range(LOW_PM, SPECIAL_PM):
        row = MONS[i]
        if row is not None and not (row.geno & excludeflags):
            return i
    return PM_HUMAN


__all__ = [
    "BOXIPROBS", "CORPSTAT_FEMALE", "CORPSTAT_MALE", "CORPSTAT_NEUTER",
    "CORPSTAT_NONE", "MAX_OIL_IN_FLASK", "MKOBJPROBS", "RANDOM_CLASS",
    "SPBOOK_no_NOVEL",
    "add_to_container", "bcsign", "bless", "blessorcurse", "coarse_otype",
    "curse", "delete_contents", "gold_at", "hero_gold", "is_container",
    "is_ismnum", "is_multigen", "may_generate_eroded", "mkbox_cnts",
    "mkcorpstat", "mkgold", "mkobj", "mkobj_at", "mkobj_erosions",
    "mksobj", "mksobj_at", "mksobj_init", "place_object", "rnd_class",
    "rndmonnum", "rndmonnum_adj", "set_corpsenm", "sobj_at",
    "unbless", "uncurse",
    "unknow_object", "weight",
]
