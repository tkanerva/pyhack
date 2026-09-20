"""Tests for step(): one command in, world + events out."""
import random

from core import MoveCommand, WaitCommand, step
from core.events import GameOverEvent, MessageEvent
from conftest import SeqRng, make_hero, make_map, make_monster, make_world


def test_cannot_move_into_wall():
    w = make_world(map=make_map(walls=((7, 4),)))
    ev = step(w, MoveCommand(1, 0), SeqRng())
    assert w.hero.pos == (6, 4)
    assert any("can't go" in e.text for e in ev if isinstance(e, MessageEvent))


def test_bump_attacks_the_monster():
    w = make_world(monsters=[make_monster(pos=(7, 4))])
    # hero hits for 2 (d20=1, 1d2=2); goblin's counterattack misses (d20=20)
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 2, 20))
    assert w.actors["goblin_0"].hp == 6
    assert w.hero.hp == 25
    assert w.hero.pos == (6, 4)  # bumping does not move the hero


def test_bump_miss():
    w = make_world(monsters=[make_monster(pos=(7, 4))])
    # hero misses (d20=20); goblin hits back for 3 (d20=1, 1d2=3)
    step(w, MoveCommand(1, 0), SeqRng(20, 1, 3))
    assert w.actors["goblin_0"].hp == 8
    assert w.hero.hp == 22


def test_adjacent_monster_attacks_hero():
    w = make_world(monsters=[make_monster(pos=(7, 4))])
    ev = step(w, WaitCommand(), SeqRng(1, 2))  # goblin hits for 2
    assert w.hero.hp == 23
    texts = [e.text for e in ev if isinstance(e, MessageEvent)]
    assert any("hits you for 2 damage" in t for t in texts)


def test_monster_moves_to_free_tile():
    w = make_world(monsters=[make_monster(pos=(8, 4))])
    step(w, WaitCommand(), random.Random(7))
    m = w.actors["goblin_0"]
    assert abs(m.pos[0] - 8) + abs(m.pos[1] - 4) == 1
    assert w.map.is_walkable(m.pos)


def test_monster_does_not_walk_onto_occupied_tile():
    # bat at (7,3): all free neighbours walled off except (7,4),
    # which is occupied by a goblin -> the bat must stay put
    w = make_world(
        map=make_map(walls=((6, 3), (8, 3), (7, 2))),
        monsters=[
            make_monster(kind="bat", pos=(7, 3)),
            make_monster(pos=(7, 4)),
        ],
    )
    step(w, WaitCommand(), random.Random(1))
    assert w.actors["bat_0"].pos == (7, 3)


def test_sleeping_monster_loses_turns():
    w = make_world(monsters=[make_monster(pos=(8, 4), sleeping=2)])
    step(w, WaitCommand(), random.Random(1))
    assert w.actors["goblin_0"].sleeping == 1
    step(w, WaitCommand(), random.Random(2))
    assert w.actors["goblin_0"].sleeping == 0


def test_asleep_hero_ignores_command():
    w = make_world(hero=make_hero(sleeping=1))
    ev = step(w, MoveCommand(1, 0), SeqRng())
    assert w.hero.pos == (6, 4)
    assert any("asleep" in e.text for e in ev if isinstance(e, MessageEvent))


def test_hero_death_ends_game():
    w = make_world(monsters=[make_monster(pos=(7, 4), damage=25)])
    ev = step(w, WaitCommand(), SeqRng(1, 25))  # goblin hits for 25
    assert not w.hero.alive
    assert w.over
    assert any(isinstance(e, GameOverEvent) and not e.victory for e in ev)


def test_victory_when_all_monsters_dead():
    w = make_world(monsters=[make_monster(pos=(7, 4), hp=1, max_hp=1)])
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 1))  # hero hits for 1
    assert w.over
    assert any(isinstance(e, GameOverEvent) and e.victory for e in ev)


def test_no_steps_after_game_over():
    w = make_world(monsters=[make_monster(pos=(7, 4), hp=1, max_hp=1)])
    step(w, MoveCommand(1, 0), SeqRng(1, 1))
    assert step(w, MoveCommand(1, 0), SeqRng()) == []


def test_same_seed_same_game():
    """Full determinism: same seed + same commands => same game."""
    from core.worldgen import new_world

    def play(seed):
        rng = random.Random(seed)
        w = new_world(rng)
        out = []
        for cmd in (MoveCommand(1, 0), MoveCommand(0, 1), WaitCommand(),
                    MoveCommand(-1, 0), MoveCommand(0, -1), WaitCommand()):
            out.extend(step(w, cmd, rng))
        return (w.hero.hp, w.hero.pos, w.turn,
                [(type(e).__name__, getattr(e, "text", "")) for e in out])

    assert play(42) == play(42)
    assert play(42) != play(1337)
