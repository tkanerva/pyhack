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

The hero also runs the defence system (core.worn, PLAN-ARMOR.md):
base AC 10 (HERO_BASE_AC, C mons[PM_HUMAN].ac) wearing chain mail ->
effective AC 5, the old demo's defence; a leather cloak, leather
gloves and a ring of protection (+1) ride carried, and six floor
armours (FLOOR_ARMOR, one of them cursed) wait on fixed tiles.  None
of it adds an rng draw, so the seeded layout is still unchanged.

The hero also runs the spell power system (core.energy): init_energy
(C: u_init.c's `u.uen = newpw()`) adds exactly ONE rng draw (the
level-0 newpw rnd(3)), after the map and before the traps -- the
seeded layout (walls, traps, spawns) is untouched.  The floor carries
the zap-port demo kit (FLOOR_WANDS / FLOOR_BOOKS, fixed positions):
the wand of cold + the cone of cold book run the SAME ZapEffect
(core.zap's shared design), the striking wand the force-bolt effect,
and the magic missile / healing books the spell side.

The grid is now rm-like Tiles (STONE boundary ring, ROOM floor, scattered
STONE obstacles) instead of the old 0/1 ints, so the vision code
(core/vision.py) runs on the same substrate the full mklev.c (rooms +
corridors + doors + furniture) will use when it is ported later.
STUB: that full level generation is still future work -- the demo
layout itself (and its rng draw sequence) is unchanged.
"""
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

# The hero's BASE (body) armor class.  C: mons[PM_HUMAN].ac -- the human
# row is not in core.monst's SUBSET_PM, so a named constant (PLAN-
# ARMOR.md decision 2).  The effective AC is computed from the worn gear
# (core.worn.uac): the hero starts wearing chain mail (a_ac 5), so the
# demo's effective defence is 10 - 5 = 5, exactly the old demo's AC.
HERO_BASE_AC = 10

# The demo floor armour (PLAN-ARMOR.md Phase 2): (position, name, otype,
# cursed) at FIXED positions -- they are reserved via
# generate_map(keep_floor=...) alongside HERO_POS, so no rng draw is
# added and the seed-42 layout, trap / monster placement and every
# seeded test are untouched.  The last piece is cursed (PLAN-ARMOR.md
# risk 3, default yes): it makes the "You can't. It is cursed." doff
# path reachable in play.
FLOOR_ARMOR: List[Tuple[Pos, str, ObjType, bool]] = [
    ((15, 7), "leather armor", ObjType.LEATHER_ARMOR, False),
    ((25, 7), "elven leather helm", ObjType.ELVEN_LEATHER_HELM, False),
    ((15, 13), "low boots", ObjType.LOW_BOOTS, False),
    ((25, 13), "small shield", ObjType.SMALL_SHIELD, False),
    ((20, 15), "leather jacket", ObjType.LEATHER_JACKET, False),
    ((20, 6), "leather cloak", ObjType.LEATHER_CLOAK, True),  # cursed
]

# The demo floor scrolls (the read.c port): (position, name, otype,
# scroll type) at FIXED positions -- reserved via
# generate_map(keep_floor=...) alongside HERO_POS and FLOOR_ARMOR, so
# no rng draw is added and the seed-42 layout, trap / monster
# placement and every seeded test are untouched.  All five
# implemented scroll types are represented; the cursed-gear demo
# piece (the FLOOR_ARMOR cloak) pairs with the remove curse scroll.
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

# The demo floor wands (the zap.c port): (position, name, otype, wand
# type, charges) at FIXED positions -- reserved via
# generate_map(keep_floor=...) alongside the rest, so no rng draw is
# added and the seed-42 layout is untouched.  The striking and cold
# wands pair with the books below: the wand of cold and the cone of
# cold book run the SAME ZapEffect (the shared-effect design), the
# striking wand the force-bolt effect (C bhitm WAN_STRIKING ->
# SPE_FORCE_BOLT).
FLOOR_WANDS: List[Tuple[Pos, str, ObjType, WandType, int]] = [
    ((19, 10), "wand of striking", ObjType.WAN_STRIKING,
     WandType.STRIKING, 3),
    ((21, 10), "wand of cold", ObjType.WAN_COLD, WandType.COLD, 3),
]

# The demo floor spellbooks (the spell.c port): (position, name,
# otype, spell type, charges) at FIXED positions -- the book is the
# power source (C: the spellbook's pages; one page per successful
# cast).  The levels mirror core.objects's SPELL rows (magic missile
# 2, cone of cold 4, healing 1) and core.spells.SPELL_LEVELS.
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
    m = generate_map(rng, width, height,
                     keep_floor=[HERO_POS]
                     + [p for p, _, _, _ in FLOOR_ARMOR]
                     + [p for p, _, _, _ in FLOOR_SCROLLS]
                     + [p for p, _, _, _, _ in FLOOR_WANDS]
                     + [p for p, _, _, _, _ in FLOOR_BOOKS])
    world = World(map=m)

    # C: the Wizard role's fixed attributes (role.c: INT 15, WIS 12) --
    # they feed the spell formulas (core.spells) and the energy
    # formulas (core.energy)
    hero = Monster(
        id="player", name="Hero", pos=HERO_POS,
        hp=HERO_HP, max_hp=HERO_HP, ac=HERO_BASE_AC, damage=2, is_hero=True,
        ulevel=1, ustr=12, udex=12, uwis=12, uint=15,
        skills=_hero_skills())
    world.actors["player"] = hero

    # C: u_init.c -- `u.uen = u.uenmax = u.uenpeak = newpw();` (the
    # level-0 branch: 4 + 1 + rnd(3) = 6..8 Pw).  The ONE rng draw this
    # wiring adds (the layout draws above are untouched -- see
    # test_new_world_makes_no_new_rng_draws).
    init_energy(world, rng)

    # the hero starts with one short sword (the demo's weapon subset):
    # the fine identity (ObjLike-compatible for core.weapon) lives on
    # the Item, which is carried and wielded
    sword = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
                 otyp=ObjType.SHORT_SWORD.value,
                 oclass=ObjClass.WEAPON.value, spe=0)
    world.items[sword.id] = sword
    sword.container = "player"
    hero.inventory.append(sword)
    hero.wielded = sword.id

    # the demo's starting kit (PLAN-ARMOR.md Phase 2): chain mail WORN
    # (effective AC 5 -- the demo's old defence), plus a leather cloak,
    # leather gloves and a ring of protection (+1) carried.  No rng
    # draws; the seeded layout is unchanged.
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

    # the demo floor scrolls (fixed positions, see FLOOR_SCROLLS
    # above): fine identity (ObjLike) + the effect tag the read
    # dispatch switches on
    for i, (pos, name, otyp, stype) in enumerate(FLOOR_SCROLLS):
        it = Item(id=f"scroll_{i}", otype=ObjectType.SCROLL, name=name,
                  otyp=otyp.value, oclass=ObjClass.SCROLL.value, pos=pos,
                  scroll_type=stype)
        world.items[it.id] = it

    # the demo floor wands (the zap.c port): fine identity (ObjLike)
    # + the effect tag the wand dispatch switches on + the fixed
    # charges (no rng draw)
    for i, (pos, name, otyp, wtype, charges) in enumerate(FLOOR_WANDS):
        it = Item(id=f"wand_{i}", otype=ObjectType.WAND, name=name,
                  otyp=otyp.value, oclass=ObjClass.WAND.value, pos=pos,
                  wand_type=wtype, charges=charges)
        world.items[it.id] = it

    # the demo floor spellbooks (the spell.c port): fine identity
    # (ObjLike) + the effect tag the cast dispatch switches on + the
    # fixed pages (no rng draw)
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

    # vision (C: vision_init() before mklev(), vision_reset() after the
    # level + objects are in place, vision_recalc() for the first
    # display).  None of it draws from the rng -- the seeded layout is
    # unchanged.
    vision_init(world)
    vision_reset(world)
    vision_recalc(world)
    return world
