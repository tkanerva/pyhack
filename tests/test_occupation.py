"""Tests for the occupation system (core/occupation.py) and the eating
occupation (core/hunger.py: eat_food / _meal, the C eatfood port).

House conventions: table-driven over the C branches, SeqRng presets
the exact dice (the only meal draws are the choke survive rolls in
core/hunger.choke), and every test asserts world state *and* the
event list.

C provenance (NetHack 5.0, local clone at ../NetHack): the
occupation mechanism -- src/cmd.c (set_occupation /
reset_occupations, cmd.c:195-215), src/allmain.c (the moveloop
`if (gm.multi >= 0 && go.occupation)` block, allmain.c:486-512;
stop_occupation, allmain.c:690-703), src/hack.c (unmul's
gn.nomovemsg print, hack.c:4177-4208), src/eat.c (eatfood
eat.c:524-546, bite eat.c:3138-3164, the doeat reqtime / nmod math
eat.c:3054-3082, start_eating's first bite eat.c:2029-2079,
done_eating eat.c:548-578, reset_eat eat.c:307-320); PLAN-
OCCUPATION.md has the full survey of the C candidate tasks.
"""
from core import EatCommand, MoveCommand, WaitCommand, step
from core.events import MessageEvent
from core.hacklib import rounddiv
from core.hunger import eat_food
from core.objects import ObjClass, ObjType, object_type
from core.occupation import (OccupationStopped, run_occupation,
                             start_occupation, stop_occupation)
from core.types import Item, ObjectType
from conftest import SeqRng, make_monster, make_world

OT = ObjType  # (E741-safe alias for the C objects table rows)
SATIATED = 0  # HungerState.SATIATED (C enum value)


def texts(ev):
    return [e.text for e in ev if isinstance(e, MessageEvent)]


def make_food(otyp, id="food_0", **kw):
    it = Item(id=id, otype=ObjectType.FOOD, name=object_type(otyp).name,
              otyp=otyp.value, oclass=ObjClass.FOOD.value, **kw)
    return it


def add_food(w, it):
    it.carrier = "player"
    w.items[it.id] = it
    w.hero.inventory.append(it)
    return it


def set_hunger(w, h, uhs):
    w.hero.uhunger = h
    w.hero.uhs = uhs


# ------------------------------------------------------------
# the C rounddiv helper (src/hack.c)
# ------------------------------------------------------------

def test_rounddiv_is_the_c_formula():
    """C: rounddiv -- half-up rounding, the C sign handling."""
    assert rounddiv(800, 5) == 160
    assert rounddiv(50, 1) == 50
    assert rounddiv(5, 3) == 2          # 1.67 -> 2
    assert rounddiv(1, 2) == 1          # 0.5  -> 1
    assert rounddiv(101, 3) == 34       # 33.67 -> 34
    assert rounddiv(-800, 5) == -160
    assert rounddiv(800, -5) == -160
    try:
        rounddiv(1, 0)
        assert False, "expected ZeroDivisionError"
    except ZeroDivisionError:
        pass


# ------------------------------------------------------------
# the framework: the generator protocol
# ------------------------------------------------------------

def counter(n, cleanup=None):
    """A dummy occupation (the protocol in core/occupation's
    docstring): ticks `n` rounds, the except clause records the tick
    count it was stopped on."""
    ev = []
    k = 0
    try:
        while True:
            rng = yield ev  # noqa: F841  (the protocol's rng slot)
            k += 1
            if k >= n:
                return [MessageEvent(f"done after {k}")]
            ev = [MessageEvent(f"tick {k}")]
    except OccupationStopped:
        if cleanup is not None:
            cleanup.append(k)
        return [MessageEvent("cleanup")]


def test_framework_run_and_complete():
    """The generator RETURN value is the completion events; the
    occupation clears itself."""
    w = make_world()
    start_occupation(w, counter(3), "testing")
    assert texts(run_occupation(w, SeqRng())) == ["tick 1"]
    assert w.occupation is not None
    assert texts(run_occupation(w, SeqRng())) == ["tick 2"]
    assert texts(run_occupation(w, SeqRng())) == ["done after 3"]
    assert w.occupation is None
    assert run_occupation(w, SeqRng()) == []  # nothing running


def test_framework_stop_throws_into_the_generator():
    """The cleanup runs (the except clause), and the framework
    appends the C stop_occupation line "You stop <occtxt>."."""
    w = make_world()
    cleanup = []
    start_occupation(w, counter(10, cleanup), "testing")
    run_occupation(w, SeqRng())
    ev = stop_occupation(w)
    assert texts(ev) == ["cleanup", "You stop testing."]
    assert cleanup == [1]                    # stopped after tick 1
    assert w.occupation is None
    assert stop_occupation(w) == []          # nothing running


def test_framework_prime_is_degenerate_when_the_generator_returns():
    """A generator that RETURNs before its first round (no prime
    yield) completes on the prime next(), no game round consumed."""
    w = make_world()

    def instant():
        return [MessageEvent("instant")]
        yield  # unreachable -- makes this a generator
    start_occupation(w, instant(), "instant")
    assert texts(run_occupation(w, SeqRng())) == ["instant"]
    assert w.occupation is None


# ------------------------------------------------------------
# eating: the one-turn foods are unchanged
# ------------------------------------------------------------

def test_apple_is_one_turn_unchanged():
    """The delay 1 apple: the fprefx was the whole feedback, the piece
    is gone, no occupation (the pre-occupation behaviour)."""
    w = make_world()
    ap = add_food(w, make_food(OT.APPLE))
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["This apple is delicious!"]
    assert w.hero.uhunger == 950
    assert ap not in w.hero.inventory
    assert w.occupation is None


# ------------------------------------------------------------
# eating: the multi-turn meal (the C eatfood occupation)
# ------------------------------------------------------------

def test_ration_meal_timeline():
    """C: the food ration (nutrition 800, oc_delay 5): the first bite
    (160) on the command turn (C: start_eating), then one bite per
    round (C: eatfood + bite), the piece consumed on the last bite
    (C: done_eating's useup + finish line)."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 200, hunger_state(200))
    ev = eat_food(w, "player", r.id, SeqRng())
    assert texts(ev) == ["This food really hits the spot!"]
    assert w.hero.uhunger == 360             # 200 + 160
    assert r.oeaten == 160
    assert w.occupation is not None
    assert w.occupation.text == "eating the food ration"
    for expected in (520, 680, 840):
        ev = run_occupation(w, SeqRng())
        assert texts(ev) == []
        assert w.hero.uhunger == expected
    ev = run_occupation(w, SeqRng())
    assert texts(ev) == ["You finish eating the food ration."]
    assert w.hero.uhunger == 1000            # 200 + 5 * 160
    assert r not in w.hero.inventory
    assert r.oeaten == 800
    assert w.occupation is None


def test_ration_interrupted_by_nearby_monster():
    """C: the moveloop's monster_nearby() check AFTER the tick: the
    round's bite still lands, then stop_occupation ("You stop
    eating ...").  The piece keeps its oeaten bookkeeping (C:
    reset_eat) and the resume (C: the already_partly_eaten path)
    runs for the reduced duration (rounddiv recompute)."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    g = make_monster("goblin", pos=(9, 4))
    w.actors[g.id] = g
    set_hunger(w, 200, hunger_state(200))
    eat_food(w, "player", r.id, SeqRng())
    assert w.hero.uhunger == 360             # first bite
    run_occupation(w, SeqRng())              # no monster nearby
    assert w.hero.uhunger == 520
    assert w.occupation is not None
    g.pos = (7, 4)                           # adjacent
    ev = run_occupation(w, SeqRng())
    assert texts(ev) == ["You stop eating the food ration."]
    assert w.hero.uhunger == 680             # the tick still landed
    assert r.oeaten == 480
    assert w.occupation is None
    assert r in w.hero.inventory
    # the resume: left 320 -> reqtime rounddiv(5*320, 800) = 2
    ev = eat_food(w, "player", r.id, SeqRng())
    assert texts(ev) == ["You begin eating the food ration."]
    assert w.hero.uhunger == 840
    assert r.oeaten == 640
    ev = run_occupation(w, SeqRng())
    assert texts(ev) == ["You finish eating the food ration."]
    assert w.hero.uhunger == 1000            # all 800 nutrition
    assert r not in w.hero.inventory


def test_resume_plan_is_the_c_rounddiv_recompute():
    """C: the doeat reqtime / nmod math (eat.c:3054-3082)."""
    from core.hunger import _meal_plan
    r = make_food(OT.FOOD_RATION)            # nutrition 800, delay 5
    assert _meal_plan(r, False) == (5, 160)
    r.oeaten = 480
    assert _meal_plan(r, True) == (2, 160)   # left 320 over 2 turns
    r.oeaten = 800
    assert _meal_plan(r, True) is None       # fully eaten
    ap = make_food(OT.APPLE)                 # nutrition 50, delay 1
    assert _meal_plan(ap, False) == (1, 50)


def test_busy_refuses_a_second_meal():
    """C: unreachable (the input is queued while an occupation runs);
    the direct-call guard."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION, id="food_r"))
    ap = add_food(w, make_food(OT.APPLE, id="food_a"))
    set_hunger(w, 200, hunger_state(200))
    eat_food(w, "player", r.id, SeqRng())
    assert w.occupation is not None
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["You are already busy."]
    assert ap in w.hero.inventory


def test_fully_eaten_item_is_the_c_used_up_branch():
    """C: the doeat used-up branch (the zero_victual reset)."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION, oeaten=800))
    set_hunger(w, 200, hunger_state(200))
    ev = eat_food(w, "player", r.id, SeqRng())
    assert texts(ev) == []
    assert r not in w.hero.inventory
    assert w.occupation is None


# ------------------------------------------------------------
# eating: the choke end (C: bite() returning 1)
# ------------------------------------------------------------

def test_choke_vomit_ends_the_meal_and_keeps_the_piece():
    """C: the pre-meal SATIATED gauge crossing 2000: the survived
    choke (1/20, the SeqRng 1) vomits and the meal ENDS (C's bite()
    returns 1) -- the piece stays for a later resume."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 1950, hunger_state(1950))  # SATIATED
    ev = eat_food(w, "player", r.id, SeqRng(1))
    assert texts(ev) == ["You stuff yourself and then vomit voluminously."]
    assert w.hero.uhunger == 1110            # 1950 + 160 - 1000
    assert w.occupation is None              # the meal ended
    assert r.oeaten == 160
    assert r in w.hero.inventory             # the piece stays


def test_choke_death_during_a_meal_tick():
    """C: the 19/20 choke death on a meal tick (the SeqRng 13); the
    piece stays."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 200, hunger_state(200))
    eat_food(w, "player", r.id, SeqRng())    # first bite, no choke
    set_hunger(w, 1900, hunger_state(1900))  # SATIATED
    ev = run_occupation(w, SeqRng(13))
    assert "You choke over your food." in texts(ev)
    assert not w.hero.alive
    assert w.occupation is None
    assert r in w.hero.inventory


# ------------------------------------------------------------
# the step() wiring
# ------------------------------------------------------------

def test_step_full_ration_meal():
    """The whole meal through step(): the hunger tick lands before
    each bite (the C per-hero-time order), 200 - 5 + 800 = 995."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 200, hunger_state(200))
    ev = step(w, EatCommand(r.id), SeqRng())
    assert texts(ev) == ["This food really hits the spot!"]
    assert w.hero.uhunger == 359             # 200 - 1 + 160
    assert w.occupation is not None
    for _ in range(3):
        ev = step(w, WaitCommand(), SeqRng())
        assert texts(ev) == []
    ev = step(w, WaitCommand(), SeqRng())
    assert texts(ev) == ["You finish eating the food ration."]
    assert w.hero.uhunger == 995
    assert r not in w.hero.inventory
    assert w.occupation is None
    assert w.turn == 5


def test_step_ignores_commands_during_the_meal():
    """C: the moveloop's occupation block consumes the turn -- the
    command is dropped (the hero neither moves nor acts)."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 200, hunger_state(200))
    step(w, EatCommand(r.id), SeqRng())
    pos = w.hero.pos
    step(w, MoveCommand(1, 0), SeqRng())
    assert w.hero.pos == pos                 # not moved
    assert w.hero.uhunger == 518             # 359 - 1 + 160
    assert w.occupation is not None
    step(w, WaitCommand(), SeqRng())
    assert w.occupation is not None
    # the meal is still running when the monster phase runs; the
    # conftest world has no monsters, so nothing interrupts
    assert w.hero.uhunger == 677


def test_step_fainted_hero_suspends_the_meal():
    """C: the gm.multi >= 0 half of the guard -- an unconscious hero
    does not advance the occupation (the hunger still ticks; the
    metabolism roll is the SeqRng 1)."""
    from core.hunger import hunger_state
    w = make_world()
    r = add_food(w, make_food(OT.FOOD_RATION))
    set_hunger(w, 200, hunger_state(200))
    eat_food(w, "player", r.id, SeqRng())
    assert r.oeaten == 160
    w.hero.fainted = 5
    ev = step(w, MoveCommand(1, 0), SeqRng(1))
    assert texts(ev) == []
    assert w.occupation is not None          # suspended, not stopped
    assert r.oeaten == 160                   # no bite while fainted
    assert w.hero.uhunger == 359             # 360 - the metabolism tick
    assert w.hero.fainted == 4
