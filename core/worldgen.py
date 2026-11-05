"""Deterministic world construction and the level-generator switch.

Two things live here:

1. the **pinned demo cave** (``generator="demo"``): the same layout as
   the old game.py (40x20 map, 15 walls, 10 traps, 9 monsters, hero at
   (20,10) with 25 hp, the midnight flag, the experience init, the
   quaff demo potion) built by a pure function taking its own rng; all
   seeded draws are preserved, so every earlier session's tests keep
   working;

2. the **generator dispatch** (WAVE3.md): ``new_world(rng,
   generator=...)`` and ``generate_level`` route to one of three level
   builders --

   ``"demo"``    the pinned cave above (the default: all the pinned
                 expectations of the earlier waves are about it);
   ``"mklev"``   the ported NetHack rooms + corridors + doors
                 generator (core.mklev);
   ``"cavern"``  the ported cellular-automaton cavern generator
                 (core.mkmap).

   The choice is stored on the World (``World.generator``) because
   levels 2..N are built lazily in generate_level, the first time the
   hero descends.

The three paths share the hero, the starting kit and the demo floor
kit; they differ in how the level -- and the monsters and traps on it
-- is made.  Nothing in the demo path gained or lost an rng draw: the
generated paths use their own draws inside their own builders.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .energy import init_energy
from .experience import init_experience
from .mklev import blank_map, fill_ordinary_room, mklev
from .mkmap import mkmap
from .monst import MONS, PM_BAT, PM_GOBLIN, PM_HILL_ORC
from .objects import ObjClass, ObjType, W_ARM
from .stairs import rebuild_stairs
from .types import (Item, Map, Monster, ObjectType, Pos, PotionType,
                    ScrollType, SpellType, STAIR_DOWN, STAIR_UP, Tile,
                    TerrainType, Trap, TrapType, WandType, World)
from .vision import vision_init, vision_recalc, vision_reset
from .weapon import P_SKILLED, Skill, Skills

# The generator names new_world() / generate_level() accept (WAVE3.md
# decision 1: behind a switch, so nobody's pinned layout moves).
DEMO = "demo"
MKLEV = "mklev"
CAVERN = "cavern"
GENERATORS = (DEMO, MKLEV, CAVERN)

HERO_POS: Pos = (20, 10)
HERO_HP = 25

# The fixed level-1 down stairs (top middle of the map; always ROOM in
# the generator, nothing else lives there -- reserved via keep_floor
# like FLOOR_ARMOR, zero rng draws).  C's newgame puts the hero ON
# these stairs (mklev(); u_on_upstairs()); the seeded demo keeps
# HERO_POS instead (PLAN-STAIRS.md decision 6 / §4).
LEVEL1_DN_STAIRS: Pos = (20, 2)

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
    ((21, 10), "wand of cold", ObjType.WAN_COLD,
     WandType.COLD, 3),
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

# Demo floor foods at FIXED positions (reserved via generate_map): the
# hunger-system demo kit -- apple / orange / food ration / melon --
# zero rng draws (PLAN-HUNGER.md decision 9; no starting food in the
# hero's kit, as in C).
FLOOR_FOODS: List[Tuple[Pos, str, ObjType]] = [
    ((16, 10), "apple", ObjType.APPLE),
    ((24, 10), "orange", ObjType.ORANGE),
    ((19, 9), "food ration", ObjType.FOOD_RATION),
    ((21, 9), "melon", ObjType.MELON),
]

# Demo floor potion at a FIXED position (reserved via generate_map):
# the quaff-port demo kit -- one healing potion (POT_HEALING), zero
# rng draws; charges=1 so quaff() can consume it.  The demo cave's
# floor-only demo item: the generated levels carry the 22-item kit of
# demo_floor_items() without it (the oinit distribution will replace
# all of it, PLAN-MKLEV.md).
FLOOR_POTIONS: List[Tuple[Pos, str, ObjType, PotionType]] = [
    ((25, 9), "healing potion", ObjType.POT_HEALING, PotionType.HEALING),
]

# The demo's three monster kinds: (permonst index, name, hp, damage).
# The generated levels pick from this table too (core.mklev's
# fill_ordinary_room demo subset); the real makemon() distribution is
# not ported (PLAN-MAKEMON.md).
DEMO_MONSTER_KINDS: List[Tuple[int, str, int, int]] = [
    (PM_GOBLIN, "Goblin", 8, 2),
    (PM_HILL_ORC, "Orc", 15, 4),
    (PM_BAT, "Bat", 4, 1),
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


def demo_monster(kind: int, ident: str, pos: Pos, lev: int = 1) -> Monster:
    """One of the three demo monsters, carrying its PerMonst type so
    the committed mhitu/uhitm attack tables apply (the demo's monsters
    run the C-port combat).

    `kind` indexes DEMO_MONSTER_KINDS; the AC comes from the monster
    table, the hp and damage are the demo's hand-tuned values.  m_lev
    is PINNED to mdata.mlevel (the PLAN-EXPERIENCE.md decision 2, as on
    the level-1 spawn): the C adj_lev roll lands with the makemon
    port.  core.mklev._spawn_monster calls this for the generated
    levels' fill (its local import keeps the cycle one-way).
    """
    pm, name, hp, damage = DEMO_MONSTER_KINDS[kind]
    mdata = MONS[pm]
    # all three kinds exist in the implemented monst subset (never None)
    assert mdata is not None
    return Monster(id=ident, name=name, pos=pos, hp=hp, max_hp=hp,
                   ac=mdata.ac, damage=damage, mdata=mdata, lev=lev,
                   m_lev=mdata.mlevel, is_flying=(pm == PM_BAT))


def demo_floor_items() -> List[Item]:
    """The demo floor kit -- armour, scrolls, weapons, wands, books
    and food -- as a fresh list of Items at the FLOOR_* positions.

    One place builds them so the pinned demo cave and the generated
    levels carry the same kit (the generated paths move the positions;
    see _scatter_floor_items).  The healing potion (FLOOR_POTIONS) is
    not in this kit -- it is the demo cave's floor-only demo item;
    the generated levels carry the 22 items (the oinit distribution
    will replace them, PLAN-MKLEV.md).
    """
    items: List[Item] = []
    for i, (pos, name, otyp, cursed) in enumerate(FLOOR_ARMOR):
        items.append(Item(id=f"armor_{i}", otype=ObjectType.ARMOR,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.ARMOR.value, pos=pos,
                          cursed=cursed))
    for i, (pos, name, otyp, stype) in enumerate(FLOOR_SCROLLS):
        items.append(Item(id=f"scroll_{i}", otype=ObjectType.SCROLL,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.SCROLL.value, pos=pos,
                          scroll_type=stype))
    for i, (pos, name, otyp) in enumerate(FLOOR_WEAPONS):
        items.append(Item(id=f"weapon_{i}", otype=ObjectType.WEAPON,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.WEAPON.value, pos=pos))
    for i, (pos, name, otyp, wtype, charges) in enumerate(FLOOR_WANDS):
        items.append(Item(id=f"wand_{i}", otype=ObjectType.WAND,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.WAND.value, pos=pos,
                          wand_type=wtype, charges=charges))
    for i, (pos, name, otyp, btype, charges) in enumerate(FLOOR_BOOKS):
        items.append(Item(id=f"book_{i}", otype=ObjectType.BOOK,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.SPBOOK.value, pos=pos,
                          spell_type=btype, charges=charges))
    for i, (pos, name, otyp) in enumerate(FLOOR_FOODS):
        items.append(Item(id=f"food_{i}", otype=ObjectType.FOOD,
                          name=name, otyp=otyp.value,
                          oclass=ObjClass.FOOD.value, pos=pos))
    return items


def _make_hero(pos: Pos = HERO_POS) -> Monster:
    """The demo hero: Wizard role attributes (INT 15, WIS 12 from
    role.c) feeding the spell and energy formulas, base AC 10 (C:
    mons[PM_HUMAN].ac -- the human row is not in the monst subset)."""
    return Monster(
        id="player", name="Hero", pos=pos,
        hp=HERO_HP, max_hp=HERO_HP, ac=HERO_BASE_AC, damage=2, is_hero=True,
        ulevel=1, ustr=12, udex=12, uwis=12, uint=15,
        skills=_hero_skills())


def _starting_kit(world: World) -> None:
    """The carried starting kit: wielded short sword (fine identity,
    ObjLike-compatible for core.weapon), chain mail WORN (effective AC
    5), leather cloak / gloves and ring of protection (+1) carried.
    No rng draws."""
    hero = world.hero
    sword = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
                 otyp=ObjType.SHORT_SWORD.value,
                 oclass=ObjClass.WEAPON.value, spe=0)
    world.items[sword.id] = sword
    sword.carrier = "player"
    hero.inventory.append(sword)
    hero.wielded = sword.id

    mail = Item(id="mail_0", otype=ObjectType.ARMOR, name="chain mail",
                otyp=ObjType.CHAIN_MAIL.value, oclass=ObjClass.ARMOR.value)
    mail.carrier = "player"
    mail.owornmask = W_ARM
    hero.inventory.append(mail)
    world.items[mail.id] = mail

    cloak = Item(id="cloak_0", otype=ObjectType.ARMOR, name="leather cloak",
                 otyp=ObjType.LEATHER_CLOAK.value,
                 oclass=ObjClass.ARMOR.value)
    cloak.carrier = "player"
    hero.inventory.append(cloak)
    world.items[cloak.id] = cloak

    gloves = Item(id="gloves_0", otype=ObjectType.ARMOR,
                  name="leather gloves",
                  otyp=ObjType.LEATHER_GLOVES.value,
                  oclass=ObjClass.ARMOR.value)
    gloves.carrier = "player"
    hero.inventory.append(gloves)
    world.items[gloves.id] = gloves

    ring = Item(id="ring_0", otype=ObjectType.RING,
                name="ring of protection (+1)",
                otyp=ObjType.RIN_PROTECTION.value,
                oclass=ObjClass.RING.value, spe=1)
    ring.carrier = "player"
    hero.inventory.append(ring)
    world.items[ring.id] = ring


# ============================================================
# The pinned demo cave
# ============================================================

def _new_world_demo(rng, width: int, height: int, levels: int,
                    midnight: bool) -> World:
    """The pinned demo cave (the old new_world body): byte for byte the
    layout every earlier session's tests pin.  All seeded draws are in
    the same order; the midnight flag (the calendar port) and the
    experience init (PLAN-EXPERIENCE.md) add no draws."""
    m = generate_map(rng, width, height,
                     keep_floor=[HERO_POS]
                     + [p for p, _, _, _ in FLOOR_ARMOR]
                     + [p for p, _, _, _ in FLOOR_SCROLLS]
                     + [p for p, _, _ in FLOOR_WEAPONS]
                     + [p for p, _, _, _, _ in FLOOR_WANDS]
                     + [p for p, _, _, _, _ in FLOOR_BOOKS]
                     + [p for p, _, _ in FLOOR_FOODS]
                     + [p for p, _, _, _ in FLOOR_POTIONS]
                     + [LEVEL1_DN_STAIRS])
    # the level-1 down stairs: fixed position, zero rng draws; level 1
    # gets NO up stairs (C: dlevel == 1 -> no upstairs)
    m.tiles[LEVEL1_DN_STAIRS[1]][LEVEL1_DN_STAIRS[0]] = Tile(
        typ=TerrainType.STAIRS, stair_dir=STAIR_DOWN)
    world = World(map=m)
    world.max_lev = levels
    # the midnight state (C: midnight()) for mattacku's undead double
    # damage; the caller (main.py) samples the wall clock once per game
    world.midnight = midnight

    world.actors["player"] = _make_hero()

    # C: u_init.c newpw() adds ONE rng draw (level-0 rnd(3) = 6..8 Pw). Layout draws are untouched.
    init_energy(world, rng)
    # the experience bookkeeping (PLAN-EXPERIENCE.md): the uhpinc[0] init
    # record -- draw-free, no new draw (the m_lev pin keeps spawn
    # draw-free too)
    init_experience(world)

    _starting_kit(world)

    # the demo floor kit at its fixed positions (see FLOOR_* above)
    for it in demo_floor_items():
        world.items[it.id] = it

    # the demo floor potion (fixed position, see FLOOR_POTIONS above):
    # fine identity (ObjLike) + effect tag for quaff dispatch
    for i, (pos, name, otyp, ptype) in enumerate(FLOOR_POTIONS):
        it = Item(id=f"potion_{i}", otype=ObjectType.POTION, name=name,
                  otyp=otyp.value, oclass=ObjClass.POTION.value, pos=pos,
                  potion_type=ptype, charges=1)
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

    # Demo monsters carry PerMonst types for committed mhitu attack
    # tables (AC from table; hp/names from old demo). No rng draws.
    spawns = floor[:]
    rng.shuffle(spawns)
    idx = 0

    def next_pos() -> Pos:
        nonlocal idx
        p = spawns[idx]
        idx += 1
        return p

    # m_lev is pinned to mdata.mlevel inside demo_monster (the
    # PLAN-EXPERIENCE.md decision 2), as on the old inline spawn
    for i in range(4):
        ident = f"goblin_{i}"
        world.actors[ident] = demo_monster(0, ident, next_pos())
    for i in range(2):
        ident = f"orc_{i}"
        world.actors[ident] = demo_monster(1, ident, next_pos())
    for i in range(3):
        ident = f"bat_{i}"
        world.actors[ident] = demo_monster(2, ident, next_pos())

    # Vision system: init/reset/recalc (no rng draws; seeded layout unchanged).
    vision_init(world)
    vision_reset(world)
    vision_recalc(world)

    # the level-1 stairways (the single fixed down stairs)
    rebuild_stairs(world)
    return world


# ============================================================
# The generated levels (mklev / cavern)
# ============================================================

def _scatter_floor_items(world: World, rng) -> None:
    """Lay the demo floor kit out on free room squares.

    The oinit() object distribution is still deferred (PLAN-STAIRS.md
    §5), so a generated level carries the demo kit rather than NetHack's
    per-depth mix -- but at generator-chosen positions, which is what
    makes the layouts playable."""
    from .mkroom import somexyspace  # local import: cycle

    traps = [t for t in world.traps.values() if t.lev == world.lev]
    taken = {it.pos for it in world.items.values() if it.pos is not None}
    taken.add(world.hero.pos)
    for item in demo_floor_items():
        item.pos = None
        for _ in range(50):
            if not world.map.rooms:
                break
            room = world.map.rooms[rng.rn2(len(world.map.rooms))]
            pos = somexyspace(world.map, traps, room, rng)
            if pos is None or pos in taken:
                continue
            item.pos = pos
            taken.add(pos)
            break
        world.items[item.id] = item


def _cavern_stairs(map_: Map, rng, lev: int, max_lev: int) -> None:
    """Staircases for a cavern level.

    C places a generated level's stairways through put_lregion_here()
    on a level definition's regions; a cavern has none, so this is the
    demo shortcut: a random floor tile per staircase, down first (C
    order), then up."""
    floor = map_.floor_tiles()
    if not floor:
        return
    rng.shuffle(floor)
    used: List[Pos] = []
    if lev < max_lev:
        pos = floor[0]
        map_.tiles[pos[1]][pos[0]] = Tile(typ=TerrainType.STAIRS,
                                          stair_dir=STAIR_DOWN)
        used.append(pos)
    if lev > 1:
        for pos in floor:
            if pos in used:
                continue
            map_.tiles[pos[1]][pos[0]] = Tile(typ=TerrainType.STAIRS,
                                              stair_dir=STAIR_UP)
            break


def _cavern_level(world: World, map_: Map, rng, lev: int) -> None:
    """C: the cavern half of a generated level (PLAN-MKLEV.md
    divergence 7): the cellular automaton (core.mkmap), then its
    (irregular) rooms are filled through the same fill_ordinary_room()
    the room generator uses -- C's caverns keep no room contents,
    pyhack keeps the rooms, and the filler needs them.  The stairs are
    the demo shortcut (_cavern_stairs): a cavern has no level-
    definition regions for put_lregion_here()."""
    mkmap(map_, rng, depth=lev)
    for room in list(map_.rooms):
        fill_ordinary_room(world, map_, rng, room, lev, lev)
    _cavern_stairs(map_, rng, lev, world.max_lev)


def _generated_level(world: World, map_: Map, rng, lev: int) -> None:
    """One generated level in place on `map_` (C: the mklev() half of
    goto_level): the rooms + corridors + doors level (core.mklev, the
    C makelevel order) or the cavern (core.mkmap + the room fill + the
    stair shortcut).  Monsters and traps come from fill_ordinary_room's
    demo subset; floor items stay off a lazily generated level (as on
    the demo's lazy levels -- the oinit distribution is deferred,
    PLAN-STAIRS.md §5).  `map_` is a parameter (not world.map): a
    lazy level is built while the hero still stands on the previous
    one."""
    if world.generator == MKLEV:
        mklev(world, map_, rng, lev)
    else:
        _cavern_level(world, map_, rng, lev)


def _new_world_generated(rng, generator: str, levels: int,
                         midnight: bool) -> World:
    """The mklev / cavern world (WAVE3.md): a generated level 1 (rooms
    + corridors + doors, or the cavern -- with its stairs and the demo
    fill), the hero ON the down staircase (the C newgame staircase
    convention: the stairs are excluded from the fill, so no monster
    shares the tile; the pinned demo keeps the (20,10) house rule
    instead), the starting kit, the 22-item demo floor kit scattered
    on room floor, vision and the stairway records.

    The generated path uses its own rng draws (the generator's
    sequence, WAVE3.md decision 6) -- the demo path's pinned draws are
    untouched.
    """
    world = World(map=blank_map(40, 20))
    world.max_lev = levels
    world.midnight = midnight
    world.generator = generator
    _generated_level(world, world.map, rng, 1)
    rebuild_stairs(world)
    down = next((s for s in world.stairs if not s.up), None)
    if down is not None:
        hero_pos = down.pos
    else:
        # levels=1: no down staircase -- a room floor instead
        from .mkroom import somexy  # local import: cycle
        hero_pos = somexy(world.map, world.map.rooms[0], rng) or (20, 10)
    world.actors["player"] = _make_hero(pos=hero_pos)
    init_energy(world, rng)
    init_experience(world)
    _starting_kit(world)
    _scatter_floor_items(world, rng)
    vision_init(world)
    vision_reset(world)
    vision_recalc(world)
    return world


# ============================================================
# The factory and the lazy-level seam
# ============================================================

def new_world(rng, width: int = 40, height: int = 20, levels: int = 3,
              midnight: bool = False, generator: str = DEMO) -> World:
    """The world factory behind the generator switch (WAVE3.md).

    ``"demo"`` (the default) is the pinned cave, byte for byte the old
    new_world; ``"mklev"`` and ``"cavern"`` run the ported generators
    (width / height apply to the demo cave only -- the generated
    levels are the demo's 40x20 grid).  The name is stored on
    ``World.generator`` because levels 2..N generate lazily in
    generate_level, long after this returns.
    """
    if generator not in GENERATORS:
        raise ValueError("unknown generator %r (want one of %s)"
                         % (generator, ", ".join(GENERATORS)))
    if generator == DEMO:
        world = _new_world_demo(rng, width, height, levels, midnight)
    else:
        world = _new_world_generated(rng, generator, levels, midnight)
    world.generator = generator
    return world


def _generate_demo_level(world: World, lev: int, rng) -> Map:
    """The demo's lazy level (the old generate_level body).

    Draw order is sacred (PLAN-STAIRS.md §2.6.2 / §7): the map (15
    wall pairs), the down-stair pick (if not the bottom level), the
    up-stair pick (if not level 1), the trap-tile shuffle + 10 kind
    draws, the spawn shuffle + 9 monster placements -- all on the same
    injected rng stream, at the moment the hero first descends (C: the
    main stream in mklev).  Stair tiles are reserved from traps /
    monsters (the up stairs are the hero's arrival point when
    descending); the two picks are independent draws, the second
    excluding the first's tile.  No floor items (the oinit object
    distribution is deferred, §5).

    C: generate_stairs -- down stairs unless Is_botlevel, up stairs
    unless dlevel == 1, down FIRST, then up.
    """
    m = generate_map(rng)
    stair_positions: List[Pos] = []
    if lev < world.max_lev:
        p = rng.choice(m.floor_tiles())
        m.tiles[p[1]][p[0]] = Tile(typ=TerrainType.STAIRS,
                                   stair_dir=STAIR_DOWN)
        stair_positions.append(p)
    if lev > 1:
        opts = [p for p in m.floor_tiles() if p not in stair_positions]
        p = rng.choice(opts)
        m.tiles[p[1]][p[0]] = Tile(typ=TerrainType.STAIRS,
                                   stair_dir=STAIR_UP)
        stair_positions.append(p)

    floor = [p for p in m.floor_tiles() if p not in stair_positions]

    # 10 traps of the same kinds level 1 uses
    trap_tiles = floor[:]
    rng.shuffle(trap_tiles)
    kinds = [TrapType.PIT, TrapType.SPIKED_PIT, TrapType.FIRE_TRAP,
             TrapType.ARROW_TRAP]
    for i in range(10):
        world.traps[f"trap_{lev}_{i}"] = Trap(
            id=f"trap_{lev}_{i}", trap_type=rng.choice(kinds),
            pos=trap_tiles[i], lev=lev)

    # 9 monsters, the level-1 composition (4 goblins / 2 orcs / 3
    # bats, the committed PerMonst types -- no rng draws for the data)
    spawns = floor[:]
    rng.shuffle(spawns)
    idx = 0

    def next_pos() -> Pos:
        nonlocal idx
        p = spawns[idx]
        idx += 1
        return p

    # m_lev is pinned to mdata.mlevel inside demo_monster (the
    # PLAN-EXPERIENCE.md decision 2), as on level 1
    for i in range(4):
        ident = f"goblin_{lev}_{i}"
        world.actors[ident] = demo_monster(0, ident, next_pos(), lev)
    for i in range(2):
        ident = f"orc_{lev}_{i}"
        world.actors[ident] = demo_monster(1, ident, next_pos(), lev)
    for i in range(3):
        ident = f"bat_{lev}_{i}"
        world.actors[ident] = demo_monster(2, ident, next_pos(), lev)
    return m


def generate_level(world: World, lev: int, rng) -> Map:
    """Generate level `lev` on first visit (C: mklev() in goto_level;
    the result is kept in world.levels afterwards, the getlev()
    equivalent, PLAN-STAIRS.md decision 4).

    Dispatches on ``World.generator`` (WAVE3.md decision 1): "demo" is
    the old draw-order-sacred demo level; "mklev" / "cavern" run the
    ported generators in place on a fresh 40x20 map, the monsters and
    traps parked on `lev` by the generator's own fill.
    """
    if world.generator == DEMO:
        return _generate_demo_level(world, lev, rng)
    m = blank_map(40, 20)
    _generated_level(world, m, rng, lev)
    return m
