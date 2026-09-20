"""Shared test helpers: tiny worlds and a preset-value rng.

Kept at the repo root so that `pytest` puts the root on sys.path
(making `import core` work) and every test module can do
`from conftest import ...`.
"""
from core.types import Map, Monster, Trap, TrapType, World

MONSTER_STATS = {
    "goblin": dict(name="Goblin", hp=8, max_hp=8, ac=7, damage=2),
    "orc": dict(name="Orc", hp=15, max_hp=15, ac=5, damage=4),
    "bat": dict(name="Bat", hp=4, max_hp=4, ac=3, damage=1, is_flying=True),
}


def make_map(width=12, height=8, walls=()):
    tiles = [[0] * width for _ in range(height)]
    for x, y in walls:
        tiles[y][x] = 1
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
        if it.container is not None:
            w.actors[it.container].inventory.append(it)
    return w


def make_trap(trap_type: TrapType, pos=(6, 4), id="trap_0"):
    return Trap(id=id, trap_type=trap_type, pos=pos)


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
