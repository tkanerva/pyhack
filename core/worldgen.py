"""Deterministic world construction for the demo cave.
Same layout as the old game.py (40x20 map, 15 walls, 10 traps, 9 monsters, hero at (20,10) with 25 hp) built by a pure function taking its own rng; all seeded draws are preserved."""
from __future__ import annotations

from typing import List, Optional, Tuple

from .energy import init_energy
from .monst import MONS, PM_BAT, PM_GOBLIN, PM_HILL_ORC
from .objects import ObjClass, ObjType, W_ARM
from .types import (Item, Map, Monster, ObjectType, Pos, ScrollType, SpellType,
                    Tile, TerrainType, Trap, TrapType, WandType, World)
from .vision import vision_init, vision_recalc, vision_reset
from .weapon import P_SKILLED, Skill, Skills

HERO_POS: Pos = (20, 10)
HERO_HP = 25

# Hero's base AC 10 (C: mons[PM_HUMAN].ac). Effective AC is 5 (chain mail -5) from core.worn.uac, matching the old demo.
HERO_BASE_AC = 10

# Demo floor armour at FIXED positions (reserved via generate_map): 6 items including one cursed (leather cloak at (20,6)) to enable the "can't doff" path.
FLOOR_ARMOR: List[Tuple[Pos, str, ObjType, bool]] = [
    ((15, 7), "leather armor", ObjType.LEATHER_ARMOR, False),
    ((25, 7), "elven leather helm", ObjType.ELVEN_LEATHER_HELM, False),
    ((15, 13), "low boots", ObjType.LOW_BOOTS, False),
    ((25, 13), "small shield", ObjType.SMALL_SHIELD, False),
    ((20, 15), "leather jacket", ObjType.LEATHER_JACKET, False),
    ((20, 6), "leather cloak", ObjType.LEATHER_CLOAK, True),  # cursed
]

# Demo floor scrolls at FIXED positions: all 5 implemented scroll types, including remove curse (pairs with the cursed FLOOR_ARMOR cloak).
FLOOR_SCROLLS: List[Tuple[Pos, str, ObjType, ScrollType]] = [
    ((17, 7), "enchant weapon", ObjType.SCR_ENCHANT_WEAPON,
     ScrollType.ENCHANT_WEAPON),
    ((23, 7), "enchant armor", ObjType.SCR_ENCHANT_ARMOR,
     ScrollType.ENCHANT_ARMOR),
    ((17, 13), "remove curse", ObjType.SCR_REMOVE_CURSE,
     ScrollType.REMOVE_CURSE),
    ((23, 13), "teleportation", ObjType.SCR_TELEPORTATION,
     ScrollType.TELEPORTATION),
    ((20, 12), "blank paper", ObjType.SCR_BLANK_PAPER,
     ScrollType.BLANK_PAPER),
]

# Demo floor weapons at FIXED positions: dagger and mace. Hero's short sword is carried and wielded.
FLOOR_WEAPONS: List[Tuple[Pos, str, ObjType]] = [
    ((18, 10), "dagger", ObjType.DAGGER),
    ((22, 10), "mace", ObjType.MACE),
]

# Demo floor wands at FIXED positions: wand of striking and wand of cold (both pair with FLOOR_BOOKS via shared ZapEffect).
FLOOR_WANDS: List[Tuple[Pos, str, ObjType, WandType, int]] = [
    ((19, 10), "wand of striking", ObjType.WAN_STRIKING,
     WandType.STRIKING, 3),
    ((21, 10), "wand of cold", ObjType.WAN_COLD, WandType.COLD, 3),
]

# Demo floor spellbooks at FIXED positions: magic missile, cone of cold, healing (5 pages each, mirroring core.objects SPELL rows).
FLOOR_BOOKS: List[Tuple[Pos, str, ObjType, SpellType, int]] = [
    ((18, 11), "book of magic missile", ObjType.SPE_MAGIC_MISSILE,
     SpellType.MAGIC_MISSILE, 5),
    ((20, 11), "book of cone of cold", ObjType.SPE_CONE_OF_COLD,
     SpellType.CONE_OF_COLD, 5),
    ((22, 11), "book of healing", ObjType.SPE_HEALING,
     SpellType.HEALING, 5),
]


def generate_map(rng, width: int = 40, height: int = 20,
                 wall_count: int = 15,
                 keep_floor: Optional[List[Pos]] = None) -> Map:
    tiles = [[
        Tile(typ=TerrainType.STONE)
        if (x == 0 or y == 0 or x == width - 1 or y == height - 1)
        else Tile(typ=TerrainType.ROOM)
        for x in range(width)
    ] for y in range(height)]
    for _ in range(wall_count):
        x = rng.randint(5, width - 6)
        y = rng.randint(5, height - 6)
        tiles[y][x] = Tile(typ=TerrainType.STONE)
    if keep_floor:
        for pos in keep_floor:
            tiles[pos[1]][pos[0]] = Tile(typ=TerrainType.ROOM)
    return Map(tiles)


def _hero_skills() -> Skills:
    """Demo hero starts skilled with short sword. skill_init needs class-skill table which the demo lacks, so the skill is set directly."""
    skills = Skills()
    skill = int(Skill.P_SHORT_SWORD)
    skills.skill[skill] = P_SKILLED
    skills.max_skill[skill] = P_SKILLED
    return skills


def new_world(rng, width: int = 40, height: int = 20) -> World:
    m = generate_map(rng, width, height,
                     keep_floor=[HERO_POS]
                     + [p for p, _, _, _ in FLOOR_ARMOR]
                     + [p for p, _, _, _ in FLOOR_SCROLLS]
                     + [p for p, _, _ in FLOOR_WEAPONS]
                     + [p for p, _, _, _, _ in FLOOR_WANDS]
                     + [p for p, _, _, _, _ in FLOOR_BOOKS])
    world = World(map=m)

    # Wizard role fixed attributes (INT 15, WIS 12 from role.c) feeding spell and energy formulas.
    hero = Monster(
        id="player", name="Hero", pos=HERO_POS,
        hp=HERO_HP, max_hp=HERO_HP, ac=HERO_BASE_AC, damage=2, is_hero=True,
        ulevel=1, ustr=12, udex=12, uwis=12, uint=15,
        skills=_hero_skills())
    world.actors["player"] = hero

    # C: u_init.c newpw() adds ONE rng draw (level-0 rnd(3) = 6..8 Pw). Layout draws are untouched.
    init_energy(world, rng)

    # Hero starts with wielded short sword (fine identity ObjLike-compatible for core.weapon).
    sword = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
                 otyp=ObjType.SHORT_SWORD.value,
                 oclass=ObjClass.WEAPON.value, spe=0)
    world.items[sword.id] = sword
    sword.container = "player"
    hero.inventory.append(sword)
    hero.wielded = sword.id

    # Starting kit: chain mail WORN (effective AC 5), leather cloak/gloves and ring of protection (+1) carried. No rng draws.
    mail = Item(id="mail_0", otype=ObjectType.ARMOR, name="chain mail",
                otyp=ObjType.CHAIN_MAIL.value, oclass=ObjClass.ARMOR.value)
    mail.container = "player"
    mail.owornmask = W_ARM
    hero.inventory.append(mail)
    world.items[mail.id] = mail

    cloak = Item(id="cloak_0", otype=ObjectType.ARMOR, name="leather cloak",
                 otyp=ObjType.LEATHER_CLOAK.value,
                 oclass=ObjClass.ARMOR.value)
    cloak.container = "player"
    hero.inventory.append(cloak)
    world.items[cloak.id] = cloak

    gloves = Item(id="gloves_0", otype=ObjectType.ARMOR,
                  name="leather gloves", otyp=ObjType.LEATHER_GLOVES.value,
                  oclass=ObjClass.ARMOR.value)
    gloves.container = "player"
    hero.inventory.append(gloves)
    world.items[gloves.id] = gloves

    ring = Item(id="ring_0", otype=ObjectType.RING,
                name="ring of protection (+1)",
                otyp=ObjType.RIN_PROTECTION.value,
                oclass=ObjClass.RING.value, spe=1)
    ring.container = "player"
    hero.inventory.append(ring)
    world.items[ring.id] = ring

    # the demo floor armour (fixed positions, see FLOOR_ARMOR above)
    for i, (pos, name, otyp, cursed) in enumerate(FLOOR_ARMOR):
        it = Item(id=f"armor_{i}", otype=ObjectType.ARMOR, name=name,
                  otyp=otyp.value, oclass=ObjClass.ARMOR.value, pos=pos,
                  cursed=cursed)
        world.items[it.id] = it

    # Floor scrolls: fine identity (ObjLike) + effect tag for read dispatch.
    for i, (pos, name, otyp, stype) in enumerate(FLOOR_SCROLLS):
        it = Item(id=f"scroll_{i}", otype=ObjectType.SCROLL, name=name,
                  otyp=otyp.value, oclass=ObjClass.SCROLL.value, pos=pos,
                  scroll_type=stype)
        world.items[it.id] = it

    # the demo floor weapons (fixed positions, see FLOOR_WEAPONS
    # above): fine identity (ObjLike) for the weapon system
    for i, (pos, name, otyp) in enumerate(FLOOR_WEAPONS):
        it = Item(id=f"weapon_{i}", otype=ObjectType.WEAPON, name=name,
                  otyp=otyp.value, oclass=ObjClass.WEAPON.value, pos=pos)
        world.items[it.id] = it

    # Floor wands: fine identity (ObjLike) + effect tag for wand dispatch + fixed charges.
    for i, (pos, name, otyp, wtype, charges) in enumerate(FLOOR_WANDS):
        it = Item(id=f"wand_{i}", otype=ObjectType.WAND, name=name,
                  otyp=otyp.value, oclass=ObjClass.WAND.value, pos=pos,
                  wand_type=wtype, charges=charges)
        world.items[it.id] = it

    # Floor spellbooks: fine identity (ObjLike) + effect tag for cast dispatch + fixed pages.
    for i, (pos, name, otyp, stype, charges) in enumerate(FLOOR_BOOKS):
        it = Item(id=f"book_{i}", otype=ObjectType.BOOK, name=name,
                  otyp=otyp.value, oclass=ObjClass.SPBOOK.value, pos=pos,
                  spell_type=stype, charges=charges)
        world.items[it.id] = it

    floor = [p for p in m.floor_tiles() if p != HERO_POS]

    # 10 traps of the same types the old demo used
    trap_tiles = floor[:]
    rng.shuffle(trap_tiles)
    kinds = [TrapType.PIT, TrapType.SPIKED_PIT, TrapType.FIRE_TRAP,
             TrapType.ARROW_TRAP]
    for i in range(10):
        world.traps[f"trap_{i}"] = Trap(
            id=f"trap_{i}", trap_type=rng.choice(kinds), pos=trap_tiles[i])

    # Demo monsters carry PerMonst types for committed mhitu attack tables (AC from table; hp/names from old demo). No rng draws.
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

    # Vision system: init/reset/recalc (no rng draws; seeded layout unchanged).
    vision_init(world)
    vision_reset(world)
    vision_recalc(world)
    return world
