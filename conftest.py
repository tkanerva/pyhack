"""Shared test helpers: tiny worlds and a preset-value rng.

Kept at the repo root so that `pytest` puts the root on sys.path
(making `import core` work) and every test module can do
`from conftest import ...`.
"""
from core.types import (Map, Monster, Tile, TerrainType, Trap, TrapType,
                        World)

MONSTER_STATS = {
    "goblin": dict(name="Goblin", hp=8, max_hp=8, ac=7, damage=2),
    "orc": dict(name="Orc", hp=15, max_hp=15, ac=5, damage=4),
    "bat": dict(name="Bat", hp=4, max_hp=4, ac=3, damage=1, is_flying=True),
}


def make_map(width=12, height=8, walls=()):
    """An all-floor (ROOM) grid with the given wall (STONE) tiles."""
    tiles = [[Tile(typ=TerrainType.ROOM) for _ in range(width)]
             for _ in range(height)]
    for x, y in walls:
        tiles[y][x] = Tile(typ=TerrainType.STONE)
    return Map(tiles)


def make_hero(pos=(6, 4), hp=25, **kw):
    defaults = dict(id="player", name="Hero", pos=pos, hp=hp, max_hp=hp,
                    ac=5, damage=2, is_hero=True)
    defaults.update(kw)
    return Monster(**defaults)


def make_monster(kind="goblin", pos=(8, 4), **kw):
    stats = dict(MONSTER_STATS[kind])
    stats["id"] = f"{kind}_0"
    stats["pos"] = pos
    stats.update(kw)
    return Monster(**stats)


def make_world(map=None, hero=None, monsters=(), traps=(), items=()):
    w = World(map=map if map is not None else make_map())
    w.actors["player"] = hero if hero is not None else make_hero()
    for m in monsters:
        w.actors[m.id] = m
    for t in traps:
        w.traps[t.id] = t
    for it in items:
        w.items[it.id] = it
        if it.carrier is not None:
            w.actors[it.carrier].inventory.append(it)
    return w


def make_trap(trap_type: TrapType, pos=(6, 4), id="trap_0"):
    return Trap(id=id, trap_type=trap_type, pos=pos)


def assert_item_locations(world: World) -> None:
    """Assert the PLAN-INVENT.md item-location invariant over `world`.

    Every item in ``World.items`` is in exactly ONE place -- on the
    floor (``pos``), carried (``carrier``) or inside a container (a
    parent's ``contents``) -- and every ``carrier`` / ``contents`` id
    resolves to something in the world.  The pack half of the
    where-state is written only by core.invent (addinv / freeinv /
    useup / delobj) and the floor half only by core.mkobj
    (place_object / add_to_container / delete_contents), so this is
    the tripwire for a fifth writer sneaking back in.

    Call it from any suite that mutates items, after the mutation.
    """
    parents: dict = {}
    for parent in world.items.values():
        for child_id in parent.contents:
            assert child_id in world.items, \
                f"{parent.id} lists contents id {child_id} that is not " \
                f"in the world"
            parents.setdefault(child_id, []).append(parent.id)
    for item in world.items.values():
        where = [name for name, on in
                 (("floor", item.pos is not None),
                  ("carrier", item.carrier is not None),
                  ("container", item.id in parents)) if on]
        assert len(where) <= 1, \
            f"{item.id} is in more than one place: {where}"
        if item.carrier is not None:
            assert item.carrier in world.actors, \
                f"{item.id} is carried by unknown {item.carrier}"
        # an item that is nowhere at all is the "ghost" a bad writer
        # leaves behind (the consume_item orphan of PLAN-INVENT.md)
        assert where, (f"{item.id} ({item.name}) is nowhere: no pos, "
                       f"no carrier, no container")


def container_ids(world: World) -> set:
    """The ids of the items that are inside a container (the third
    where-state of `assert_item_locations`)."""
    ids = set()
    for parent in world.items.values():
        ids.update(parent.contents)
    return ids


class SeqRng:
    """Stand-in for random.Random that returns preset values in order.

    Use it where the code under test only calls randint/choice -- full
    determinism without hunting for magic seeds.
    """

    def __init__(self, *values):
        self._values = list(values)

    def randint(self, a, b):
        return self._values.pop(0)

    def choice(self, seq):
        return self._values.pop(0)

    def rn2(self, x):
        return self._values.pop(0) % x
