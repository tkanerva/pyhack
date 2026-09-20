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
    """Per-turn status upkeep: sleep/stuck/confusion tick down, poison
    deals 1 damage per turn (NetHack simplification: poison does 1d4
    every 4 rounds)."""
    a = world.actors[actor_id]
    if not a.alive:
        return []
    events: List[Event] = []
    if a.sleeping > 0:
        a.sleeping -= 1
        if a.is_hero:
            events.append(MessageEvent("💤 You are asleep."))
    if a.stuck > 0:
        a.stuck -= 1
    if a.confused > 0:
        a.confused -= 1
    if a.poisoned > 0:
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
