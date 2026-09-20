"""Tests for deterministic world construction."""
import random

from core.worldgen import new_world


def test_layout_counts():
    w = new_world(random.Random(42))
    assert len(w.traps) == 10
    assert w.hero.pos == (20, 10)
    monsters = [m for m in w.actors.values() if not m.is_hero]
    assert len(monsters) == 9
    assert {m.name for m in monsters} == {"Goblin", "Orc", "Bat"}
    for m in w.actors.values():
        assert w.map.is_walkable(m.pos)


def test_hero_spot_is_never_a_wall():
    """The old game.py could place a random wall (or a trap, or a
    monster) on the hero's starting tile."""
    for seed in range(20):
        w = new_world(random.Random(seed))
        assert w.map.is_walkable(w.hero.pos)
        assert not any(t.pos == w.hero.pos for t in w.traps.values())
        assert not any(m.pos == w.hero.pos
                       for m in w.actors.values() if not m.is_hero)
