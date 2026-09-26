"""The heart of the architecture: one function advances the game.

    step(world, command, rng) -> list[Event]

This is the ONLY entry point for gameplay.  State may only change
through this function (which delegates to the systems in this package).
There is no broadcast bus, no global state, and no I/O.
"""
from __future__ import annotations

from typing import List

from .commands import (CastCommand, Command, MoveCommand, QuaffCommand,
                       ZapCommand)
from .events import Event, GameOverEvent, MessageEvent
from .hacklib import is_asleep, is_stuck
from .mhitu import mattacku
from .potions import quaff
from .uhitm import uhitm
from .rules import (apply_damage, manhattan, melee_attack, process_events,
                    tick_actor)
from .spells import cast_spell
from .traps import check_traps
from .types import DamageType, World
from .zap import use_wand


def step(world: World, cmd: Command, rng) -> List[Event]:
    if world.over:
        return []

    hero = world.hero
    was_asleep = is_asleep(hero)
    events: List[Event] = []

    # --- player turn ---
    events += tick_actor(world, "player", rng)
    if not world.hero.alive:
        return _finish(world, events)
    if not was_asleep:
        if isinstance(cmd, MoveCommand):
            if is_stuck(world.hero):
                events.append(MessageEvent("🕸️ You are stuck and cannot move."))
            else:
                events += _do_move(world, "player", cmd.dx, cmd.dy, rng)
        elif isinstance(cmd, ZapCommand):
            events += use_wand(world, "player", cmd.wand_type, cmd.direction, rng)
        elif isinstance(cmd, QuaffCommand):
            events += quaff(world, "player", cmd.item_id, rng)
        elif isinstance(cmd, CastCommand):
            events += cast_spell(world, "player", cmd.book_id, cmd.direction, rng)
        # WaitCommand: a deliberate pass (no trap re-roll, unlike the old demo)

    # --- monster turns ---
    for mon_id in list(world.actors.keys()):
        if mon_id == "player":
            continue
        mon = world.actors[mon_id]
        if not mon.alive:
            continue
        events += tick_actor(world, mon_id, rng)
        if not mon.alive:
            continue
        if not world.hero.alive:
            break
        events += _monster_turn(world, mon_id, rng)

    world.turn += 1
    return _finish(world, events)


def _do_move(world: World, actor_id: str, dx: int, dy: int, rng) -> List[Event]:
    actor = world.actors[actor_id]
    dest = (actor.pos[0] + dx, actor.pos[1] + dy)
    if not world.map.is_walkable(dest):
        if actor.is_hero:
            return [MessageEvent("You can't go that way.")]
        return []
    target = world.monster_at(dest)
    if target is not None:
        # bumping a monster attacks it (NetHack behaviour)
        return _melee_combat(world, actor_id, target.id, rng)
    actor.pos = dest
    return check_traps(world, actor_id, rng)


def _melee_combat(world: World, attacker_id: str, defender_id: str, rng) -> List[Event]:
    attacker = world.actors[attacker_id]
    defender = world.actors[defender_id]
    # The rich C-port combat paths, both opt-in via a PerMonst type
    # (mdata): mattacku (mhitu.c) for monster->hero, uhitm (uhitm.c) for
    # hero->monster.  Both are producers -- they emit
    # DamageEvent/StatusEvent/MessageEvent intents without touching state
    # -- and process_events (the pure core) applies them through the
    # state-mutation choke points.  Flat-stat demo monsters (mdata is
    # None) fall through to the simple path below.
    if (not attacker.is_hero and defender.is_hero
            and attacker.mdata is not None):
        # monster hits hero (port of src/mhitu.c): producer + processor
        return process_events(world, mattacku(world, attacker_id, rng), rng)
    if attacker.is_hero and defender.mdata is not None:
        # hero hits monster (port of src/uhitm.c): producer + processor
        return process_events(world, uhitm(world, defender_id, rng), rng)
    dmg = melee_attack(rng, attacker, defender)
    if dmg <= 0:
        if defender.is_hero:
            return [MessageEvent(f"🛡️ {attacker.name} misses you.")]
        if attacker.is_hero:
            return [MessageEvent("🛡️ You miss.")]
        return [MessageEvent(f"🛡️ {attacker.name} misses {defender.name}.")]
    if defender.is_hero:
        flavor = f"⚔️ {attacker.name} hits you for {dmg} damage!"
    elif attacker.is_hero:
        flavor = f"⚔️ You hit {defender.name} for {dmg} damage."
    else:
        flavor = f"⚔️ {attacker.name} hits {defender.name} for {dmg} damage."
    events: List[Event] = [MessageEvent(flavor)]
    events += apply_damage(world, defender_id, dmg, DamageType.MELEE,
                           attacker_id, message=False)
    return events


def _monster_turn(world: World, mon_id: str, rng) -> List[Event]:
    mon = world.actors[mon_id]
    hero = world.hero
    if is_asleep(mon):
        return []
    if hero.alive and manhattan(mon.pos, hero.pos) == 1:
        # a monster next to the hero attacks instead of moving
        return _melee_combat(world, mon_id, "player", rng)
    if is_stuck(mon):
        return []
    # random walk: first free orthogonal tile in random order (old
    # behaviour, now also refusing to step onto occupied tiles)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    rng.shuffle(dirs)
    for dx, dy in dirs:
        dest = (mon.pos[0] + dx, mon.pos[1] + dy)
        if world.map.is_walkable(dest) and world.monster_at(dest) is None:
            mon.pos = dest
            return check_traps(world, mon_id, rng)
    return []


def _finish(world: World, events: List[Event]) -> List[Event]:
    if not world.over:
        if not world.hero.alive:
            world.over = True
            events.append(GameOverEvent(victory=False, reason="You have died!"))
        else:
            monsters = [m for m in world.actors.values() if not m.is_hero]
            if monsters and not any(m.alive for m in monsters):
                world.over = True
                events.append(GameOverEvent(victory=True,
                                            reason="All monsters cleared!"))
    return events
