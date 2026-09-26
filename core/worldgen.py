"""Deterministic world construction for the demo cave.

Same layout as the old game.py (40x20 map, 15 interior walls, 10 traps,
4 goblins / 2 orcs / 3 bats, hero at (20,10) with 25 hp) but built by a
pure function that takes its own rng -- so the game and the tests share
one code path.

The demo combat runs on the committed C-port systems: every monster
carries its PerMonst type (core.monst), so monster->hero attacks come
from the mhitu attack tables, and the hero starts wielding a short sword
(the weapon subset of core.uhitm on top of core.weapon).  Wiring those
in adds NO rng draws, so the seeded layout is unchanged.
"""
from __future__ import annotations

from typing import List, Optional

from .monst import MONS, PM_BAT, PM_GOBLIN, PM_HILL_ORC
from .objects import ObjClass, ObjType
from .types import Item, Map, Monster, ObjectType, Pos, Trap, TrapType, World
from .weapon import P_SKILLED, Skill, Skills

HERO_POS: Pos = (20, 10)
HERO_HP = 25


def generate_map(rng, width: int = 40, height: int = 20,
                 wall_count: int = 15,
                 keep_floor: Optional[List[Pos]] = None) -> Map:
    tiles = [[1 if (x == 0 or y == 0 or x == width - 1 or y == height - 1) else 0
              for x in range(width)] for y in range(height)]
    for _ in range(wall_count):
        x = rng.randint(5, width - 6)
        y = rng.randint(5, height - 6)
        tiles[y][x] = 1
    if keep_floor:
        for pos in keep_floor:
            tiles[pos[1]][pos[0]] = 0
    return Map(tiles)


def _hero_skills() -> Skills:
    """The demo hero's skill state: it starts skilled with its starting
    weapon.  ``skill_init`` needs a role's class-skill table, which the
    demo has no, so the one skill is set directly (no progression in the
    demo)."""
    skills = Skills()
    skill = int(Skill.P_SHORT_SWORD)
    skills.skill[skill] = P_SKILLED
    skills.max_skill[skill] = P_SKILLED
    return skills


def new_world(rng, width: int = 40, height: int = 20) -> World:
    m = generate_map(rng, width, height, keep_floor=[HERO_POS])
    world = World(map=m)

    hero = Monster(
        id="player", name="Hero", pos=HERO_POS,
        hp=HERO_HP, max_hp=HERO_HP, ac=5, damage=2, is_hero=True,
        ulevel=1, ustr=12, udex=12,
        skills=_hero_skills())
    world.actors["player"] = hero

    # the hero starts with one short sword (the demo's weapon subset):
    # the fine identity (ObjLike-compatible for core.weapon) lives on
    # the Item, which is carried and wielded
    sword = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
                 otyp=int(ObjType.SHORT_SWORD),
                 oclass=int(ObjClass.WEAPON), spe=0)
    world.items[sword.id] = sword
    sword.container = "player"
    hero.inventory.append(sword)
    hero.wielded = sword.id

    floor = [p for p in m.floor_tiles() if p != HERO_POS]

    # 10 traps of the same types the old demo used
    trap_tiles = floor[:]
    rng.shuffle(trap_tiles)
    kinds = [TrapType.PIT, TrapType.SPIKED_PIT, TrapType.FIRE_TRAP,
             TrapType.ARROW_TRAP]
    for i in range(10):
        world.traps[f"trap_{i}"] = Trap(
            id=f"trap_{i}", trap_type=rng.choice(kinds), pos=trap_tiles[i])

    # monsters: the demo's three kinds carry their PerMonst types, so
    # monster->hero combat runs on the committed mhitu attack tables
    # (AC comes from the table too; per-instance hp / names stay the
    # old demo's).  No rng draws are added here -- the seeded layout
    # is unchanged.
    goblin = MONS[PM_GOBLIN]
    orc = MONS[PM_HILL_ORC]
    bat = MONS[PM_BAT]

    spawns = floor[:]
    rng.shuffle(spawns)
    idx = 0

    def next_pos() -> Pos:
        nonlocal idx
        p = spawns[idx]
        idx += 1
        return p

    for i in range(4):
        world.actors[f"goblin_{i}"] = Monster(
            id=f"goblin_{i}", name="Goblin", pos=next_pos(),
            hp=8, max_hp=8, ac=goblin.ac, damage=2, mdata=goblin)
    for i in range(2):
        world.actors[f"orc_{i}"] = Monster(
            id=f"orc_{i}", name="Orc", pos=next_pos(),
            hp=15, max_hp=15, ac=orc.ac, damage=4, mdata=orc)
    for i in range(3):
        world.actors[f"bat_{i}"] = Monster(
            id=f"bat_{i}", name="Bat", pos=next_pos(),
            hp=4, max_hp=4, ac=bat.ac, damage=1, is_flying=True,
            mdata=bat)
    return world
