"""Pure rules: dice, hit chances, resistances, and the single
state-mutation choke points (apply_damage, heal, status setters).

Everything here takes an explicit `rng` (a random.Random instance, or
anything with randint/choice) so tests can be fully deterministic.
There is no `import random` anywhere in the core -- the world never
depends on the global RNG.
"""
from __future__ import annotations

from typing import List

from .events import DamageEvent, DeathEvent, Event, MessageEvent, StatusEvent
from .hacklib import (is_asleep, is_blind, is_confused, is_hallucinating,
                      is_poisoned, is_stuck)
from .types import DamageType, Direction, Monster, Pos, World

ORTHOGONAL: List[Pos] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ------------------------------------------------------------
# Dice
# ------------------------------------------------------------

def roll(rng, die: int, times: int = 1) -> int:
    """Roll `times` dice of `die` sides (1..die) and sum them."""
    return sum(rng.randint(1, die) for _ in range(times))


def hit_chance(attacker: Monster, defender: Monster) -> int:
    """d20 hit chance: 20 - defender AC (same formula as the old demo).
    Can be <= 0 (always miss) or > 20 (always hit) -- kept as-is."""
    return 20 - defender.ac


def melee_attack(rng, attacker: Monster, defender: Monster) -> int:
    """Returns damage dealt, or 0 on a miss."""
    if rng.randint(1, 20) <= hit_chance(attacker, defender):
        return roll(rng, attacker.damage)
    return 0


# ------------------------------------------------------------
# Resistances (data-driven by monster flags; the old code scattered
# these across per-class resists() methods in three files)
# ------------------------------------------------------------

def resists(monster: Monster, dmg_type: DamageType) -> bool:
    if monster.is_undead:
        return dmg_type in (DamageType.COLD, DamageType.LIGHTNING,
                            DamageType.MAGIC_MISSILE, DamageType.POISON,
                            DamageType.DEATH)
    if monster.is_demon:
        return dmg_type in (DamageType.FIRE, DamageType.DEATH, DamageType.SLEEP)
    if monster.is_golem:
        return dmg_type in (DamageType.SLEEP, DamageType.DEATH, DamageType.ACID)
    if monster.is_nonliving:
        return dmg_type == DamageType.POISON
    return False


def can_polymorph(monster: Monster) -> bool:
    return not (monster.is_demon or monster.is_golem)


# ------------------------------------------------------------
# State mutation choke points
# ------------------------------------------------------------

def apply_damage(world: World, target_id: str, amount: int,
                 dmg_type: DamageType, source: str,
                 message: bool = True) -> List[Event]:
    """The ONLY way an actor loses hit points.

    Returns events.  Callers may pass message=False and emit their own
    flavour text (e.g. "A pit hits you for 3 damage!") -- the mutation
    still happens here and only here.
    """
    target = world.actors[target_id]
    if not target.alive or amount <= 0:
        return []
    if resists(target, dmg_type):
        if message:
            text = ("You resist the damage!" if target.is_hero
                    else f"{target.name} resists {dmg_type.name.lower()}!")
            return [MessageEvent(text)]
        return []
    target.hp = max(0, target.hp - amount)
    events: List[Event] = [DamageEvent(target=target_id, amount=amount,
                                       damage_type=dmg_type, source=source)]
    if message:
        if target.is_hero:
            events.append(MessageEvent(f"⚠️ You take {amount} damage!"))
        else:
            events.append(MessageEvent(f"{target.name} takes {amount} damage!"))
    if target.hp <= 0:
        target.alive = False
        events.append(DeathEvent(target=target_id, by=source))
        events.append(MessageEvent("💀 You are dead!" if target.is_hero
                                   else f"☠️ {target.name} dies!"))
    return events


def heal(world: World, target_id: str, amount: int) -> List[Event]:
    target = world.actors[target_id]
    healed = min(amount, target.max_hp - target.hp)
    if healed <= 0:
        text = "You feel healthy." if target.is_hero \
            else f"{target.name} is already healthy."
        return [MessageEvent(text)]
    target.hp += healed
    text = "You feel better." if target.is_hero \
        else f"{target.name} recovers {healed} HP."
    return [MessageEvent(text)]


# ------------------------------------------------------------
# Statuses
# ------------------------------------------------------------

def put_to_sleep(world: World, target_id: str, duration: int,
                 message: bool = True) -> List[Event]:
    t = world.actors[target_id]
    t.sleeping = max(t.sleeping, duration)
    events: List[Event] = [StatusEvent(target_id, "sleep", duration)]
    if message:
        events.append(MessageEvent("🛌 You feel very sleepy!" if t.is_hero
                                   else f"😴 {t.name} falls asleep!"))
    return events


def apply_stuck(world: World, target_id: str, duration: int,
                message: bool = True) -> List[Event]:
    t = world.actors[target_id]
    t.stuck = max(t.stuck, duration)
    events: List[Event] = [StatusEvent(target_id, "stuck", duration)]
    if message:
        events.append(MessageEvent("🕸️ You are stuck in a web!" if t.is_hero
                                   else f"🕸️ {t.name} is stuck in a web!"))
    return events


def apply_poison(world: World, target_id: str, duration: int) -> List[Event]:
    t = world.actors[target_id]
    t.poisoned = max(t.poisoned, duration)
    events: List[Event] = [StatusEvent(target_id, "poison", duration)]
    events.append(MessageEvent("☣️ You have been poisoned!" if t.is_hero
                               else f"☣️ {t.name} has been poisoned!"))
    return events


def apply_confusion(world: World, target_id: str, duration: int) -> List[Event]:
    t = world.actors[target_id]
    t.confused = max(t.confused, duration)
    events: List[Event] = [StatusEvent(target_id, "confusion", duration)]
    events.append(MessageEvent("You feel very confused." if t.is_hero
                               else f"{t.name} feels very confused."))
    return events


def apply_blind(world: World, target_id: str, duration: int) -> List[Event]:
    t = world.actors[target_id]
    t.blind = max(t.blind, duration)
    events: List[Event] = [StatusEvent(target_id, "blind", duration)]
    events.append(MessageEvent("👁️ You are blinded!" if t.is_hero
                               else f"👁️ {t.name} is blinded!"))
    return events


def apply_hallucination(world: World, target_id: str, duration: int) -> List[Event]:
    t = world.actors[target_id]
    t.hallucinating = max(t.hallucinating, duration)
    events: List[Event] = [StatusEvent(target_id, "hallucination", duration)]
    events.append(MessageEvent("🌀 You feel hallucinations!" if t.is_hero
                               else f"🌀 {t.name} is hallucinating!"))
    return events


def teleport_to_floor(world: World, target_id: str, rng) -> List[Event]:
    """Teleport to a random floor tile.  Always in bounds and on floor
    (the old trap.py teleported to a hard-coded 80x22 area regardless of
    the actual map size)."""
    t = world.actors[target_id]
    options = [p for p in world.map.floor_tiles() if p != t.pos]
    if not options:
        text = "Nothing happens." if t.is_hero else f"Nothing happens to {t.name}."
        return [MessageEvent(text)]
    t.pos = rng.choice(options)
    events: List[Event] = [StatusEvent(target_id, "teleport", 0)]
    events.append(MessageEvent("✨ You are teleported." if t.is_hero
                               else f"✨ {t.name} is teleported."))
    return events


def tick_actor(world: World, actor_id: str, rng) -> List[Event]:
    """Per-turn status upkeep: every active status ticks down by one
    turn, and poison deals 1 damage per turn (NetHack simplification:
    poison does 1d4 every 4 rounds).

    Status reads go through the core.hacklib query functions (no raw
    `m.confused > 0` style checks); the decrements below are the only
    place a status counter is reduced.
    """
    a = world.actors[actor_id]
    if not a.alive:
        return []
    events: List[Event] = []
    if is_asleep(a):
        a.sleeping -= 1
        if a.is_hero:
            events.append(MessageEvent("💤 You are asleep."))
    if is_stuck(a):
        a.stuck -= 1
    if is_confused(a):
        a.confused -= 1
    if is_blind(a):
        a.blind -= 1
    if is_hallucinating(a):
        a.hallucinating -= 1
    if is_poisoned(a):
        a.poisoned -= 1
        events += apply_damage(world, actor_id, 1, DamageType.POISON,
                               "poison", message=False)
        events.append(MessageEvent("☣️ You feel poisoned." if a.is_hero
                                   else f"☣️ {a.name} is poisoned."))
    return events


def find_target_in_line(world: World, start: Pos, direction: Direction,
                        max_range: int = 7):
    """Walk a straight line from `start`.  Returns
    (first monster encountered, whether a wall was hit first)."""
    x, y = start
    dx, dy = direction.delta
    for _ in range(max_range):
        x += dx
        y += dy
        pos = (x, y)
        if not world.map.in_bounds(pos) or world.map.is_wall(pos):
            return None, True
        m = world.monster_at(pos)
        if m is not None:
            return m, False
    return None, False


# ------------------------------------------------------------
# Event processing (the pure-core side of the event-producing systems)
# ------------------------------------------------------------

def _apply_status_event(world: World, e: StatusEvent, rng) -> List[Event]:
    """Route one produced StatusEvent to its status setter (the single
    place a status changes).  Returns the concrete events the setter
    emits (its own StatusEvent + message), which replace the intent."""
    if e.effect == "sleep":
        return put_to_sleep(world, e.target, e.duration)
    if e.effect == "stuck":
        return apply_stuck(world, e.target, e.duration)
    if e.effect == "poison":
        return apply_poison(world, e.target, e.duration)
    if e.effect == "confusion":
        return apply_confusion(world, e.target, e.duration)
    if e.effect == "blind":
        return apply_blind(world, e.target, e.duration)
    if e.effect == "hallucination":
        return apply_hallucination(world, e.target, e.duration)
    if e.effect == "teleport":
        return teleport_to_floor(world, e.target, rng)
    return [e]  # unknown effect: pass through untouched


def process_events(world: World, events: List[Event], rng) -> List[Event]:
    """Run produced events through the state-mutation choke points.

    This is the "pure functional core" half of the event-producing
    systems (``mhitu`` and friends): they emit ``DamageEvent`` /
    ``StatusEvent`` *intents* without touching state, and this function
    applies them.  A ``DamageEvent`` goes through ``apply_damage`` (the
    only way an actor loses HP -- called with ``message=False`` because
    the producer already emitted the specific flavour line); a
    ``StatusEvent`` goes through the status setters; everything else
    (messages, deaths, game-over) passes through.  Returns the final
    event list -- each intent is replaced by the concrete events the
    choke point emits, so nothing is double-counted.
    """
    out: List[Event] = []
    for e in events:
        if isinstance(e, DamageEvent):
            out += apply_damage(world, e.target, e.amount, e.damage_type,
                                e.source, message=False)
        elif isinstance(e, StatusEvent):
            out += _apply_status_event(world, e, rng)
        else:
            out.append(e)
    return out
