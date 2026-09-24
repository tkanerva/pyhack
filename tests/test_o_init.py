"""Tests for the object table initialization (core.o_init)."""
from core.objects import (ObjClass, ObjType, OBJECTS, MAXOCLASSES,
                          IMMEDIATE, NODIR, NUM_OBJECTS, O)
from core.o_init import (BASES, ObjTables, discover_object, init_oclass_probs,
                         interesting_to_discover, obj_shuffle_range,
                         oinit, observe_object, randomize_gem_colors,
                         setgemprobs, shuffle, typename, undiscover_object)
from core.rnd import Rng


def test_class_probability_totals_are_positive():
    state = ObjTables(Rng(b"probs"))
    for oclass in range(1, MAXOCLASSES):
        assert state.prob_totals[oclass] > 0, oclass
    assert state.prob_totals[ObjClass.ILLOBJ] == 0  # generics are free


def test_gem_probs_at_level_zero():
    state = ObjTables(Rng(b"gem0"))
    first = state.bases[ObjClass.GEM]
    # the 9 most valuable gems (dilithium..citrine) are unavailable on
    # level 0
    for j in range(9):
        assert state.prob[first + j] == 0
    # the rest get (171 + k) / (LAST_REAL_GEM + 1 - first) with the
    # advanced first, i.e. (171+k)/13: mostly 13, tail 14
    rest = state.prob[first + 9:O.JADE.value + 1]
    assert all(p in (13, 14) for p in rest)
    assert rest[0] == 13 and rest[-1] == 14


def test_gem_probs_at_high_level():
    state = ObjTables(Rng(b"gem30"))
    setgemprobs(state, 30)
    first = state.bases[ObjClass.GEM]
    # level 30: 9 - 30//3 = -1 gems suppressed, so the first gem appears;
    # formula (171 + k) / 22 across all 22 gems
    for idx in range(first, O.JADE.value + 1):
        assert state.prob[idx] > 0
    assert state.prob[first] == 7


def test_oinit_uses_current_ledger_level():
    state = ObjTables(Rng(b"oinit"))
    oinit(state, Rng(b"oinit"), ledger_level=30)
    first = state.bases[ObjClass.GEM]
    assert state.prob[first] > 0


def test_init_is_deterministic():
    a = ObjTables(Rng(b"same"))
    b = ObjTables(Rng(b"same"))
    assert a.descr == b.descr
    assert a.color == b.color
    assert a.material == b.material
    assert a.prob == b.prob
    assert a.wand_nothing_dir == b.wand_nothing_dir


def test_wand_nothing_dir():
    state = ObjTables(Rng(b"nothing"))
    assert state.wand_nothing_dir in (NODIR, IMMEDIATE)


class ScriptedRng:
    def __init__(self, *values):
        self.values = list(values)

    def rn2(self, x):
        return self.values.pop(0)


def test_randomize_gem_colors():
    state = ObjTables(Rng(b"gemc"))
    # reset to the unshuffled static descriptions first
    state.descr = [o.descr for o in OBJECTS]
    state.color = [o.color for o in OBJECTS]
    randomize_gem_colors(state, ScriptedRng(1, 1, 1))
    assert state.descr[O.TURQUOISE.value] == "blue"      # sapphire's
    assert state.descr[O.AQUAMARINE.value] == "blue"
    assert state.descr[O.FLUORITE.value] == "blue"
    state.descr = [o.descr for o in OBJECTS]
    randomize_gem_colors(state, ScriptedRng(0, 0, 3))
    assert state.descr[O.FLUORITE.value] == "green"      # emerald's
    assert state.descr[O.TURQUOISE.value] == "green"     # unchanged


def test_shuffle_permutes_unknown_descriptions():
    state = ObjTables(Rng(b"shuf"))
    # rings: all unknown, all described -> descriptions are permuted
    lo = state.bases[ObjClass.RING]
    hi = state.bases[ObjClass.RING + 1] - 1
    static = sorted(d for d in (OBJECTS[i].descr for i in range(lo, hi + 1))
                    if d is not None)
    current = sorted(d for d in state.descr[lo:hi + 1] if d is not None)
    assert static == current


def test_known_objects_do_not_move():
    state = ObjTables(Rng(b"shuf2"))
    # force one potion known, then re-shuffle just the potion range
    otyp = O.POT_HEALING.value
    state.name_known.add(otyp)
    fixed = state.descr[otyp]
    lo, hi = obj_shuffle_range(state, O.POT_HEALING)
    shuffle(state, Rng(b"shuf3"), lo, hi, True)
    assert state.descr[otyp] == fixed
    # water keeps its fixed description (outside the shuffle range)
    assert obj_shuffle_range(state, O.POT_WATER) == (O.POT_WATER,
                                                     O.POT_WATER)
    assert hi == O.POT_WATER.value - 1


def test_obj_shuffle_ranges():
    state = ObjTables(Rng(b"range"))
    assert obj_shuffle_range(state, O.RIN_PROTECTION) == \
        (state.bases[ObjClass.RING], state.bases[ObjClass.RING + 1] - 1)
    assert obj_shuffle_range(state, O.SCR_IDENTIFY) == \
        (state.bases[ObjClass.SCROLL], O.SCR_BLANK_PAPER.value - 1)
    assert obj_shuffle_range(state, O.SPE_HEALING) == \
        (state.bases[ObjClass.SPBOOK], O.SPE_BLANK_PAPER.value - 1)
    assert obj_shuffle_range(state, O.AMULET_OF_GUARDING) == \
        (state.bases[ObjClass.AMULET], O.FAKE_AMULET_OF_YENDOR.value - 1)
    assert obj_shuffle_range(state, O.HELMET) == \
        (O.HELMET.value, O.HELM_OF_TELEPHY.value)
    assert obj_shuffle_range(state, O.PLATE_MAIL) == \
        (O.PLATE_MAIL.value, O.PLATE_MAIL.value)  # suits don't shuffle
    assert obj_shuffle_range(state, O.SPEED_BOOTS) == \
        (O.SPEED_BOOTS.value, O.LEVITATION_BOOTS.value)
    assert obj_shuffle_range(state, O.WAN_LIGHT) == \
        (state.bases[ObjClass.WAND], state.bases[ObjClass.WAND + 1] - 1)


def test_discovery_tracking():
    state = ObjTables(Rng(b"disco"))
    t = O.RIN_PROTECTION.value
    def class_disco(ocls):
        lo = state.bases[ocls]
        hi = state.bases[ocls + 1]
        return [state.disco[i] for i in range(lo, hi)
                if state.disco[i] is not None]

    assert not interesting_to_discover(state, t)
    assert discover_object(state, t, True, True)
    assert not discover_object(state, t, True, True)  # already recorded
    assert t in state.name_known and t in state.encountered
    # flat disco[]: the discovered otyp sits in the first free slot of
    # the class range, in discovery order
    assert class_disco(ObjClass.RING) == [t]
    assert interesting_to_discover(state, t)
    # a second discovery in the same class goes into the next slot
    t2 = O.RIN_WARNING.value
    discover_object(state, t2, True, False)
    assert class_disco(ObjClass.RING) == [t, t2]
    # encounter-only discovery is not "known" and gets no disco slot
    t3 = O.POT_WATER.value
    discover_object(state, t3, False, True)
    assert t3 in state.encountered and t3 not in state.name_known
    assert class_disco(ObjClass.POTION) == []
    # purging a fully forgotten type shifts the rest forward
    state.name_known.discard(t)
    state.encountered.discard(t)
    undiscover_object(state, t)
    assert class_disco(ObjClass.RING) == [t2]


def test_generic_objects_cannot_be_discovered():
    state = ObjTables(Rng(b"gen"))
    assert not discover_object(state, O.GENERIC_WEAPON, True, True)
    assert not observe_object(state, O.STRANGE_OBJECT)


def test_uname_wins_in_typename():
    state = ObjTables(Rng(b"name"))
    t = O.POT_HEALING.value
    assert typename(state, t) == "purple-red"  # unknown: descr
    discover_object(state, t, True, False)
    assert typename(state, t) == "healing"     # known: real name
    state.uname[t] = "slime"
    assert typename(state, t) == "slime"       # called: user name


def test_base_class_order():
    # classes appear in ascending order in the table (C init_objects check)
    prev = -1
    for i in range(1, NUM_OBJECTS):
        cls = int(OBJECTS[i].oclass)
        assert cls >= prev, i
        prev = cls
