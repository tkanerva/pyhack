"""Long-duration tasks: the occupation system, as generators.

Port of the C occupation mechanism -- ``set_occupation()`` (cmd.c),
the moveloop's ``if (gm.multi >= 0 && go.occupation)`` block
(allmain.c:486), ``stop_occupation()`` (allmain.c:690) and the
``gn.nomovemsg`` print in ``unmul()`` (hack.c:4177) -- onto Python
generators.

In C, a long-duration task is a hand-rolled coroutine:
``set_occupation(fn, "eating the food ration", 0)`` stores a function
pointer (``go.occupation``) plus a context string (``go.occtxt``), and
every round the moveloop calls ``fn()`` which returns 1 (still busy)
or 0 (done).  The task's own state (which item, how far along) is
stashed in per-system global context structs -- ``svc.context.victual``
(eating), ``svc.context.xlock`` (locks), ``svc.context.digging``
(digging), ``svc.context.spbook`` (study), ...

In pyhack the function pointer + global context becomes one generator:
the state lives in the generator frame (its local variables), each
``send(rng)`` runs one round and returns that round's events, and the
generator's RETURN value is the final (completion) events.
Interruption is ``gen.throw(OccupationStopped)``; the generator's
except clause does the system-specific cleanup (keep the half-eaten
food, ...) and RETURNs the cleanup events.

Generator protocol (every occupation generator follows it) -- ONE
yield expression per round, and it does double duty: the value SENT
in is this round's rng, the value YIELDED out is this round's events
(the prime round's yield value is discarded):

    def meal(...) -> Generator[List[Event], None, List[Event]]:
        ev: List[Event] = []
        try:
            while True:
                rng = yield ev       # sent: this round's rng;
                                     # yielded: this round's events
                ...one round of work (the C fn() body)...
                if done:
                    return [MessageEvent("You finish ...")]
                ev = events          # still busy
        except OccupationStopped:
            return cleanup_events    # e.g. [] -- the item stays

Framework invariants (the C rules, PLAN-OCCUPATION.md §3):

- While an occupation is active it CONSUMES the hero's whole turn:
  the command handed to step() is dropped (C queues it for later; the
  demo is one command per turn).
- The occupation advances only while the hero is conscious (C: the
  ``gm.multi >= 0`` half of the guard -- a fainted hero's occupation
  is suspended; the per-turn hunger still ticks, that is how a meal
  deepens a faint).
- After the round's tick, a monster within adjacent range interrupts
  the occupation (C: the ``monster_nearby()`` check AFTER the tick in
  the moveloop).
- The completion message comes from the generator's RETURN value
  (C: the system's own "You finish ..." / "You succeed ..." line).
  C's ``gn.nomovemsg`` / "You can move again." machinery belongs to
  the nomul() countdown actions (prayer); in pyhack those are short
  generators over the same protocol, so no separate print site is
  needed.

The per-round rng flows in through ``send()`` (the C fn() body calls
the global RNG; pyhack injects the round's rng, which in the tests is
a fresh SeqRng per step).  The generator is created on the command
turn, which has already done the work of the first round (the C first
bite in doeat), so the first tick is PRIMED with a next() (which runs
to the first yield and consumes no game round; its yield value is
discarded) and every tick afterwards is a send(rng).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, List

from .events import Event, MessageEvent


class OccupationStopped(Exception):
    """Thrown into the occupation generator on interruption (C: the
    stop_occupation() call sites).  The generator must catch it (or
    a broad except) and RETURN the cleanup events -- it must not
    yield again."""


@dataclass
class Occupation:
    """A running long-duration task (C: go.occupation + go.occtxt).
    The task state is in ``gen``'s frame; ``text`` is the context
    string ("eating the food ration") the "You stop ..." message and
    the UI status line use."""
    gen: Generator[List[Event], None, List[Event]]
    text: str
    started: bool = field(default=False)  # primed (first next() done)


def _monster_nearby(world) -> bool:
    """C: monster_nearby() (src/mon.c) -- any living monster on this
    level within adjacent range of the hero (distmin 1, diagonals
    included).  The C version is a plain proximity test; the line-of-
    sight half of that name is a misnomer in C too."""
    hero = world.hero
    return any(m.alive and not m.is_hero and m.lev == world.lev
               and abs(m.pos[0] - hero.pos[0]) <= 1
               and abs(m.pos[1] - hero.pos[1]) <= 1
               and (m.pos[0] != hero.pos[0] or m.pos[1] != hero.pos[1])
               for m in world.actors.values())


def start_occupation(world, gen, text: str) -> None:
    """C: set_occupation(fn, txt, 0) -- store the task.  ``gen`` must
    follow the generator protocol above (the prime point first)."""
    world.occupation = Occupation(gen=gen, text=text)


def run_occupation(world, rng) -> List[Event]:
    """Advance the current occupation by one round (C: the
    ``(*go.occupation)()`` call in the moveloop) and return the
    round's events.  Clears ``world.occupation`` when the generator
    RETURNs, returning the RETURN value (the completion events).

    The round's rng is fed through send() (see the module docstring).
    After the tick, a monster within adjacent range interrupts the
    still-running occupation (C: the monster_nearby() check)."""
    occ = world.occupation
    if occ is None:
        return []
    if not occ.started:
        # Prime the just-created generator: next() runs it to the
        # prime point (the first `rng = yield`).  Consumes no game
        # round -- the command turn already did the first bite.
        try:
            next(occ.gen)
        except StopIteration as stop:
            # degenerate: a generator that RETURNs before its first
            # round (e.g. the food was already gone) -- completion
            # events, occupation done.
            world.occupation = None
            return stop.value or []
        occ.started = True
    try:
        events = occ.gen.send(rng)
    except StopIteration as stop:
        world.occupation = None
        return stop.value or []
    if world.occupation is not None and _monster_nearby(world):
        # C: the tick happened, THEN the proximity check interrupts
        return events + stop_occupation(world)
    return events


def stop_occupation(world) -> List[Event]:
    """Interrupt the current occupation (C: stop_occupation() in
    allmain.c -- "You stop <occtxt>.").  The exception is thrown into
    the generator at its suspension point; the generator's except
    clause does the cleanup and RETURNs the cleanup events, then the
    framework appends the "You stop ..." line (C prints it after the
    system-specific reset)."""
    occ = world.occupation
    if occ is None:
        return []
    world.occupation = None
    try:
        occ.gen.throw(OccupationStopped)
        # Protocol violation: the generator yielded instead of
        # RETURNing after the cleanup -- close it; the cleanup has
        # already run, only the (stray) yield value is dropped.
        try:
            occ.gen.close()
        except Exception:
            pass
        cleanup: List[Event] = []
    except StopIteration as stop:
        cleanup = stop.value or []
    return list(cleanup) + [MessageEvent(f"You stop {occ.text}.")]
