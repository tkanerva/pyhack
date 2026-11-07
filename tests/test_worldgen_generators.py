"""Tests for the level-generator switch (new_world / generate_level) and
for the door commands (core.doors).

`new_world(generator=...)` is the compatibility seam the wave was landed
behind: "demo" is the pinned cave every earlier session's tests pin
(byte for byte), "mklev"/"cavern" are the ported generators.  The pinned
demo expectations live in the other test modules; here the question is
that the seam exists, that each generator produces a *playable* world,
and that a game never mixes generators.
"""
import random

import pytest

from core import doors
from core.commands import CloseCommand, MoveCommand
from core.doors import close_door, open_door
from core.rnd import Rng
from core.step import step
from core.types import (DoorMask, TerrainType, Tile, World)
from core.worldgen import (CAVERN, DEMO, GENERATORS, HERO_POS, MKLEV,
                           demo_floor_items, new_world)
from conftest import make_hero, make_map, make_world


def _rng(seed: int = 1) -> Rng:
    return Rng(b"worldgen-test:%d" % seed)


# ------------------------------------------------------------
# the switch
# ------------------------------------------------------------

def test_the_generator_names_are_the_three_known_ones():
    assert (DEMO, MKLEV, CAVERN) == GENERATORS == \
        ("demo", "mklev", "cavern")


def test_unknown_generator_is_refused():
    with pytest.raises(ValueError):
        new_world(random.Random(1), generator="maze")


def test_a_generated_level_refuses_the_demo_rng():
    """The rng contract is refused at the seam, with a message that says
    what to pass, not as an AttributeError from inside makelevel.

    The demo cave draws through randint / choice / shuffle, which
    random.Random has; the ported generators draw through rn2 / rnd / d
    (PLAN-MKLEV.md decision 8), which it does not -- `main.py --mklev`
    used to die on `'Random' object has no attribute 'rn2'` inside
    RectManager.rnd_rect().
    """
    with pytest.raises(TypeError, match="core.rnd.Rng"):
        new_world(random.Random(42), generator=MKLEV)


def test_a_lazily_generated_level_refuses_the_demo_rng_too():
    """generate_level() is the other entrance to the generators (the
    lazy levels 2..N)."""
    from core.worldgen import generate_level

    w = new_world(_rng(2), generator=MKLEV, levels=3)
    with pytest.raises(TypeError, match="rn2"):
        generate_level(w, 2, random.Random(1))


def test_the_demo_entry_point_builds_and_steps_every_generator():
    """The entry point's own path: main.make_rng(generator) ->
    new_world -> a few turns of step, on the very rng the game keeps
    using.  This is the regression test for `python main.py --mklev`
    (the shell used to hand `random.Random` to every generator)."""
    from main import make_rng

    for generator in GENERATORS:
        rng = make_rng(generator)
        w = new_world(rng, generator=generator)
        assert w.generator == generator
        if generator == DEMO:
            assert w.hero.pos == HERO_POS, "the pinned cave's hero square"
            assert w.map.rooms == []
        else:
            assert w.map.rooms, "a generated level has rooms"
            assert w.stairs, "a generated level has staircases"
        assert w.map.is_walkable(w.hero.pos)
        for dx, dy in _MOVES:
            if w.over:
                break
            step(w, MoveCommand(dx, dy), rng)
            assert w.map.is_walkable(w.hero.pos)


def test_demo_is_the_default_and_stays_pinned():
    """No generator argument == the demo cave, exactly as before."""
    assert new_world(random.Random(42)).generator == DEMO
    w = new_world(random.Random(42))
    assert w.hero.pos == (20, 10)
    assert len(w.traps) == 10
    assert w.map.rooms == []


@pytest.mark.parametrize("generator", [MKLEV, CAVERN])
def test_generated_world_is_playable(generator):
    """A generated level: the hero stands on walkable floor, there are
    staircases, the level knows where its rooms are, and whatever the
    room filler put on it stands on legal squares.

    C's filler gives a monster to one room in three
    (`if (!rn2(3)) makemon((struct permonst *) 0, ...)` in
    fill_ordinary_room), so a small level legitimately comes out empty
    -- test_generated_worlds_hold_monsters is the population half.
    """
    w = new_world(_rng(7), generator=generator)
    assert w.generator == generator
    assert w.map.rooms, "a generated level has rooms"
    assert w.map.is_walkable(w.hero.pos)
    assert w.stairs, "a generated level has staircases"
    for stair in w.stairs:
        assert w.map.tile_at(stair.pos).typ == TerrainType.STAIRS
    monsters = [a for a in w.actors.values() if not a.is_hero]
    for mon in monsters:
        assert w.map.is_walkable(mon.pos)
        assert mon.pos != w.hero.pos


@pytest.mark.parametrize("generator", [MKLEV, CAVERN])
def test_generated_worlds_hold_monsters(generator):
    """The generated levels are populated by core.makemon, not by the
    old three hand-tuned demo kinds: counted over six seeds, a generated
    level 1 holds monsters.  (One seed is not enough -- with C's
    one-room-in-three roll an empty level is normal.)"""
    placed = 0
    for seed in range(1, 7):
        w = new_world(_rng(seed), generator=generator)
        placed += len([a for a in w.actors.values() if not a.is_hero])
    assert placed >= 3, "a generated level has monsters"


@pytest.mark.parametrize("generator", [MKLEV, CAVERN])
def test_generated_world_carries_the_demo_kit(generator):
    """The demo floor kit is still laid out on the generated level's free
    squares (the wand / scroll / potion demo needs it), and everything on
    the floor stands somewhere legal.

    Since Wave 4a/4b the room filler also places its own objects -- gold,
    a statue, a final random object through core.mkobj -- so the count is
    a floor now, not a pin: the kit's 22 items are all there and the
    genesis may have added more.
    """
    w = new_world(_rng(7), generator=generator)
    floor_items = [it for it in w.items.values()
                   if it.pos is not None and it.carrier is None]
    # 6 armour + 5 scrolls + 2 weapons + 2 wands + 3 books + 4 foods
    kit = {it.id for it, _ in demo_floor_items()}
    assert kit <= {it.id for it in floor_items}
    assert len(floor_items) >= 22
    for item in floor_items:
        assert w.map.is_walkable(item.pos)
        assert item.pos != w.hero.pos


@pytest.mark.parametrize("generator", [MKLEV, CAVERN])
def test_generated_world_is_deterministic(generator):
    a = new_world(_rng(11), generator=generator)
    b = new_world(_rng(11), generator=generator)
    assert [[t.typ for t in row] for row in a.map.tiles] == \
        [[t.typ for t in row] for row in b.map.tiles]
    assert a.hero.pos == b.hero.pos
    assert sorted(a.traps) == sorted(b.traps)
    assert sorted(a.actors) == sorted(b.actors)


def test_deeper_levels_use_the_same_generator():
    """generate_level() is the lazy path (levels 2..N); it must follow
    the World's generator, not a module default."""
    from core.worldgen import generate_level

    w = new_world(_rng(3), generator=MKLEV, levels=3)
    m = generate_level(w, 2, _rng(4))
    assert m.rooms, "a mklev level 2 must have rooms"
    for room in m.rooms:
        assert m.tile_at((room.lx, room.ly)).typ == TerrainType.ROOM

    d = new_world(random.Random(3), generator=DEMO, levels=3)
    m2 = generate_level(d, 2, random.Random(4))
    assert m2.rooms == []
    assert any(t.typ == TerrainType.ROOM for row in m2.tiles for t in row)


def test_a_mklev_game_descends_to_level_two():
    """The whole loop works: a generated level 1, a descent, and a
    generated level 2 that keeps its rooms when the hero comes back."""
    from core.commands import StairsCommand

    w = new_world(_rng(5), generator=MKLEV, levels=3)
    # find the down staircase and stand on it
    down = [s for s in w.stairs if not s.up][0]
    w.hero.pos = down.pos
    step(w, StairsCommand(up=False), _rng(6))
    assert w.lev == 2
    assert w.map.rooms, "level 2 must be a generated rooms level"
    layout = [[t.typ for t in row] for row in w.map.tiles]
    up = [s for s in w.stairs if s.up][0]
    w.hero.pos = up.pos
    step(w, StairsCommand(up=True), _rng(7))
    assert w.lev == 1
    w.hero.pos = [s for s in w.stairs if not s.up][0].pos
    step(w, StairsCommand(up=False), _rng(8))
    assert w.lev == 2
    assert [[t.typ for t in row] for row in w.map.tiles] == layout


def test_lazy_generation_does_not_touch_the_previous_level():
    """A lazily generated level is carved into its own map, not the
    parked previous one (the niche half of mklev took world.map:
    generating level 2 carved level 1's wall, and level 2 got no
    niches)."""
    from core.commands import StairsCommand

    w = new_world(_rng(5), generator=MKLEV, levels=3)
    level1 = [[t.typ for t in row] for row in w.map.tiles]
    down = [s for s in w.stairs if not s.up][0]
    w.hero.pos = down.pos
    step(w, StairsCommand(up=False), _rng(6))
    assert w.lev == 2
    up = [s for s in w.stairs if s.up][0]
    w.hero.pos = up.pos
    step(w, StairsCommand(up=True), _rng(7))
    assert w.lev == 1
    assert [[t.typ for t in row] for row in w.map.tiles] == level1


# ------------------------------------------------------------
# doors
# ------------------------------------------------------------

def _door_world(mask: DoorMask, closed_hero=(5, 5)) -> World:
    """A 10x8 cave whose (6,5) is a door in a north-south wall."""
    m = make_map(width=10, height=8)
    m.tiles[5][6] = Tile(typ=TerrainType.DOOR, door_mask=mask,
                         horizontal=False)
    for y in range(8):
        if (6, y) != (6, 5):
            m.tiles[y][6] = Tile(typ=TerrainType.VWALL, horizontal=False)
    return make_world(map=m, hero=make_hero(pos=closed_hero))


def test_walking_into_a_closed_door_opens_it():
    w = _door_world(DoorMask.CLOSED)
    events = step(w, MoveCommand(1, 0), _rng())
    text = [e.text for e in events if hasattr(e, "text")]
    assert "The door opens." in text
    assert w.map.tile_at((6, 5)).door_mask == DoorMask.ISOPEN
    assert w.hero.pos == (5, 5), "opening a door is not a move"


def test_walking_into_a_locked_door_refuses():
    w = _door_world(DoorMask.LOCKED)
    events = step(w, MoveCommand(1, 0), _rng())
    text = [e.text for e in events if hasattr(e, "text")]
    assert "This door is locked." in text
    assert w.map.tile_at((6, 5)).door_mask == DoorMask.LOCKED
    assert w.hero.pos == (5, 5)


def test_an_open_door_is_walked_through():
    w = _door_world(DoorMask.ISOPEN)
    step(w, MoveCommand(1, 0), _rng())
    assert w.hero.pos == (6, 5)


def test_a_bare_doorway_is_walked_through():
    w = _door_world(DoorMask(0))
    step(w, MoveCommand(1, 0), _rng())
    assert w.hero.pos == (6, 5)


def test_open_door_messages_cover_the_four_refusals():
    """C: doopen_indir's case list -- no door / broken / bare doorway /
    already open / locked."""
    w = _door_world(DoorMask.BROKEN)
    assert open_door(w, (6, 5), _rng())[0].text == "This door is broken."
    w = _door_world(DoorMask(0))
    assert open_door(w, (6, 5), _rng())[0].text == \
        "This doorway has no door."
    w = _door_world(DoorMask.ISOPEN)
    assert open_door(w, (6, 5), _rng())[0].text == \
        "This door is already open."
    w = _door_world(DoorMask.LOCKED)
    assert open_door(w, (6, 5), _rng())[0].text == "This door is locked."
    w = _door_world(DoorMask.CLOSED)
    assert open_door(w, (1, 1), _rng())[0].text == "You see no door there."


def test_opening_a_trapped_door_destroys_it():
    w = _door_world(DoorMask.CLOSED | DoorMask.TRAPPED)
    events = open_door(w, (6, 5), _rng())
    assert [e.text for e in events] == [
        "The door opens.", "A trap on the door goes off!"]
    assert w.map.tile_at((6, 5)).door_mask == DoorMask(0)


def test_door_strength_roll_can_fail():
    """C: rnl(20) < (STR + DEX + CON) / 3, and a resisting door also
    costs the turn."""
    class Weak:
        def rnl(self, x, luck=0):
            return 19

    w = _door_world(DoorMask.CLOSED)
    assert open_door(w, (6, 5), Weak())[0].text == "The door resists!"
    assert w.map.tile_at((6, 5)).door_mask == DoorMask.CLOSED


def test_closing_an_open_door():
    w = _door_world(DoorMask.ISOPEN)
    events = close_door(w, (6, 5), _rng())
    assert [e.text for e in events] == ["The door closes."]
    assert w.map.tile_at((6, 5)).door_mask == DoorMask.CLOSED


def test_close_refuses_for_the_c_reasons():
    w = _door_world(DoorMask.CLOSED)
    assert close_door(w, (6, 5), _rng())[0].text == \
        "This door is already closed."
    w = _door_world(DoorMask.LOCKED)
    assert close_door(w, (6, 5), _rng())[0].text == \
        "This door is already closed."
    w = _door_world(DoorMask.BROKEN)
    assert close_door(w, (6, 5), _rng())[0].text == "This door is broken."
    w = _door_world(DoorMask(0))
    assert close_door(w, (6, 5), _rng())[0].text == \
        "This doorway has no door."


def test_a_monster_in_the_doorway_blocks_closing():
    w = _door_world(DoorMask.ISOPEN)
    from conftest import make_monster
    mon = make_monster("goblin", pos=(6, 5))
    w.actors[mon.id] = mon
    assert close_door(w, (6, 5), _rng())[0].text == \
        "Goblin blocks the way!"


def test_closed_door_blocks_sight_and_walkability():
    """The closed door is opaque (vision) and impassable until opened --
    that is what makes a door worth having."""
    from core.vision import does_block

    w = _door_world(DoorMask.CLOSED)
    assert does_block(w, (6, 5)) != 0
    assert not w.map.is_walkable((6, 5))
    open_door(w, (6, 5), _rng())
    assert does_block(w, (6, 5)) == 0
    assert w.map.is_walkable((6, 5))


def test_close_command_goes_through_step():
    w = _door_world(DoorMask.ISOPEN)
    events = step(w, CloseCommand(1, 0), _rng())
    assert [e.text for e in events if hasattr(e, "text")] == \
        ["The door closes."]
    assert w.map.tile_at((6, 5)).door_mask == DoorMask.CLOSED


def test_closed_door_helper_is_the_c_macro():
    """C: closed_door() is D_CLOSED only -- a locked door is *not*
    "closed" as far as the open command is concerned."""
    w = _door_world(DoorMask.CLOSED)
    assert doors.closed_door(w, (6, 5)) is True
    w = _door_world(DoorMask.LOCKED)
    assert doors.closed_door(w, (6, 5)) is False
    w = _door_world(DoorMask.ISOPEN)
    assert doors.closed_door(w, (6, 5)) is False


# ------------------------------------------------------------
# a whole game on a generated level
# ------------------------------------------------------------

_MOVES = [(1, 0), (-1, 0), (0, 1), (0, -1),
          (1, 1), (1, -1), (-1, 1), (-1, -1)]


@pytest.mark.parametrize("generator", [MKLEV, CAVERN])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_walk_never_breaks_the_world(generator, seed):
    """The smoke test for everything this wave wired together: a few
    hundred random commands (walking, opening doors, falling into traps,
    being hit, taking stairs) on a generated level -- the hero always
    stands somewhere legal and nothing raises."""
    from core.commands import StairsCommand

    rng = Rng(b"walk:%s:%d" % (generator.encode(), seed))
    w = new_world(rng, generator=generator, levels=2)
    for _ in range(400):
        if w.over:
            break
        if not rng.rn2(12):
            cmd: object = StairsCommand(up=bool(rng.rn2(2)))
        else:
            dx, dy = _MOVES[rng.rn2(len(_MOVES))]
            cmd = MoveCommand(dx, dy)
        step(w, cmd, rng)  # type: ignore[arg-type]
        assert w.map.in_bounds(w.hero.pos)
        assert w.map.is_walkable(w.hero.pos)
        assert 1 <= w.lev <= w.max_lev
        for mon in w.actors.values():
            if mon.is_hero or not mon.alive:
                continue
            assert w.map.in_bounds(mon.pos)
