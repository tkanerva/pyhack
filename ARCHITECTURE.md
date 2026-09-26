# PyHack architecture

## The rule

All game state lives in **one `World` object**. One function —
`step(world, command, rng) -> list[Event]` — advances the game by one
turn. The core has **no I/O, no global state, and no broadcast bus**:

```
 ui/console.py (keys, screen)           main.py (loop)
        | Command                              |
        v                                      v
   step(world, cmd, rng)  ---------------->  [Event, Event, ...]
        |
        +-- movement / bump-attack     (step.py)
        +-- traps                      (traps.py: TRAP_EFFECTS registry)
        +-- zaps                       (zap.py)
        +-- potions                    (potions.py)
        +-- spells                     (spells.py)
        +-- rules                      (rules.py: dice, resist,
                                        apply_damage, tick_actor)
```

Events are frozen dataclasses. The UI renders `MessageEvent`s; tests
assert on the whole event list *and* the resulting world state.

## Why not the old broadcast/actor model

In single-threaded Python, a "message to an actor" is a function call
with extra indirection. The old code had **both** a message layer
(`MessageRouter`, `world.broadcast`, TypedDict messages) **and** direct
calls with direct attribute mutation (`entity.hp -= dmg` in
`TrapActor._apply_trap_effect`, `mon.attack(hero)` in `game.py`,
`react_to_damage` everywhere). That combination caused a concrete bug:
trap damage was applied **twice** (once in `TrapActor`, once in
`check_and_trigger_traps`). With one transition function and one
mutation choke point (`rules.apply_damage`), that bug class cannot
happen, and every state change is visible in a debugger.

Events-as-data keep the decoupling the broadcast was aiming for (UI,
sound, replay, tests all just consume the list) without the invisible
bus — and a recorded `(Command, [Event])` sequence *is* a replay.

## Old file -> new home

| old file      | new home                                   |
|---------------|--------------------------------------------|
| `contracts.py`| enums split into `core/types.py`; the TypedDict message schemas, `BaseActor`, `MessageRouter` and `Protocol`s are **deleted** (they were dead weight: nothing sent those messages, `world.query` always returned `None`) |
| `game.py`     | `core/step.py` + `core/worldgen.py` + `main.py` + `ui/console.py` |
| `player.py`, `monster.py` | `core/types.py` — one `Monster` dataclass; the hero is a monster with `is_hero=True` |
| `trap.py`     | `core/traps.py` — data + `TRAP_EFFECTS` registry, no actor |
| `zap.py`      | `core/zap.py` |
| `potion.py`   | `core/potions.py` |
| `spell.py`    | `core/spells.py` |
| `priest.py`, `pray.py` | **not ported yet** (see below) |

## Behaviour decisions

**Preserved from the old demo:** 30% trap-trigger roll; d20 vs
`20 - AC` hit formula; all damage dice (1d6 pit, 1d12 spiked pit,
1d6 fire, arrow 1d6 / dart 1d4 with `max(5, 20-AC)` hit chance,
boulder 4..20); monster stats (Goblin 8/AC7/dmg2, Orc 15/AC5/dmg4,
Bat 4/AC3/dmg1); hero 25 HP / AC5; 40x20 map with 15 interior walls;
10 traps of the same four types; 9 monsters; `random` seed 42; the
emoji log strings.

**Fixed (latent bugs in the old code):**
- Trap damage applied twice (see above) — regression test:
  `tests/test_traps.py::test_pit_deals_exactly_one_damage`.
- Teleport traps used a hard-coded 80x22 area while the map is 40x20 —
  teleports now always land on an in-bounds floor tile.
- A random wall / trap / monster could spawn on the hero's starting
  tile — `worldgen` keeps `(20,10)` free.
- Arrow keys never worked: the old code lower-cased the key and then
  compared against `"\x1b[A"`.
- Monsters could walk onto the hero or onto each other.
- Pressing enter ("wait") re-rolled the trap under the hero's feet;
  `WaitCommand` is now a true pass.
- The broken blessed/cursed potion inversion (flipped on every quaff)
  is dropped.

**Added (NetHack-faithful, small):**
- Bump-to-attack: walking into a monster attacks it (the old demo had
  no hero attack at all, so the game was a death-watching exercise).
  Hero melee uses the same hit formula with 1d2 damage.
- A monster adjacent to the hero attacks instead of moving.
- Sleep / stuck / confusion / poison now tick down each turn
  (`rules.tick_actor`); poison deals 1 damage per turn
  (NetHack: 1d4 every 4 rounds — simplification).
- Wands discharge (consume a charge) even when they hit a wall; beams
  stop at the first monster (NetHack behaviour; the old spell.py beam
  hit everything in range).
- The demo now plays the committed C-port combat in both directions:
  the demo monsters carry their PerMonst types (goblin / hill orc /
  bat; monster->hero hits come from the mhitu attack tables) and the
  hero starts wielding a short sword (the uhitm melee-weapon subset on
  weapon.py's hitval / dmgval; backstab and the weapon special effects
  are deferred).

**Intentional simplifications (documented, not bugs):**
- Monster AI is still a random walk — no awareness/line-of-sight yet.
- Web/pit "stuck" lasts 10 turns (NetHack: escape checks).
- Spell study/learning mechanics dropped; books have charges only.
- Spell damage is a flat 2d6 (the old `d6 * nd` referenced a stat that
  never existed).
- `priest.py` / `pray.py` are currently broken sketches (undefined
  attributes like `player.blindfolded`, a module-global `player`);
  they should be ported *from the C originals* as core systems —
  functions over `World` returning events — rather than refactored.

## Testing

- **Rules** are pure functions: table-driven unit tests, no mocks
  (`tests/test_rules.py`).
- **step()** is a function: build a tiny world with `conftest.make_world`,
  feed a command, assert on world state *and* the event list.
  `SeqRng` (in `conftest.py`) presets exact dice rolls.
- **Whole games** are deterministic: `new_world(random.Random(42))` +
  a command list reproduces byte-for-byte
  (`tests/test_step.py::test_same_seed_same_game`).

## Suggested next steps

1. Wire `ZapCommand` / `QuaffCommand` / `CastCommand` into the console
   UI (the systems exist and are tested; the hero just needs starting
   inventory in `worldgen` and a few keys in `read_command`).
2. Port `priest.py` / `pray.py` as systems (start from
   `NetHack/NetHack/src/priest.c` and `pray.c`).
3. Monster awareness/LOS for chases.
4. If the system/entity matrix grows, evolve into a lightweight ECS —
   the events-out design stays the same.
