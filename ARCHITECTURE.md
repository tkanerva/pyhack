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
        +-- per-turn upkeep        (rules.tick_actor, energy.py,
        |                          rings.tick_rings, hunger.py)
        +-- movement / bump-attack (step.py; the C-port melee via
        |                          uhitm.py / mhitu.py)
        +-- traps                  (traps.py: TRAP_EFFECTS registry)
        +-- zaps                   (zap.py)
        +-- potions                (potions.py)
        +-- scrolls                (scrolls.py: the read.c subset)
        +-- spells                 (spells.py)
        +-- eat                    (hunger.py; a multi-turn meal is the
        |                          C occupation, ticked by occupation.py)
        +-- wear / take off        (worn.py: slots + the computed AC)
        +-- rings                  (rings.py: on/off + discovery)
        +-- pickup                 (pickup.py: the pickobj subset)
        +-- stairs                 (stairs.py: the do.c / dungeon.c subset)
        +-- vision                 (vision.py: the vision.c port)
        +-- rules                  (rules.py: dice, resist, apply_damage,
                                        process_events)
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
| `priest.py`, `pray.py` | the broken sketches were dropped, never ported; the C originals (`src/priest.c`, `src/pray.c`) are still unported (see "Suggested next steps") |

## Behaviour decisions

**Preserved from the old demo:** 30% trap-trigger roll; d20 vs
`20 - AC` hit formula; all damage dice (1d6 pit, 1d12 spiked pit,
1d6 fire, arrow 1d6 / dart 1d4 with `max(5, 20-AC)` hit chance,
boulder 4..20); monster stats (Goblin 8/AC7/dmg2, Orc 15/AC5/dmg4,
Bat 4/AC3/dmg1); hero 25 HP, effective AC 5 (base 10 in the starting
chain mail — the defence is now computed, see below); 40x20 level-1
map with 15 interior walls; 10 traps of the same four types; 9
monsters; `random` seed 42; the emoji log strings.

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

**Added (NetHack-faithful; the architectural choices — the session
details live in the PLAN-*.md files and the module docstrings):**

- Defence / armour (PLAN-ARMOR.md, Phases 1-4): the worn state is the
  C mechanism — `Item.owornmask` (the prop.h bitmask) + an inventory
  scan (`worn.which_armor` / `setworn`), no per-slot fields;
  `Monster.ac` is the BASE body AC and the effective AC is the
  computed `worn.uac()` (C `find_ac`), never cached; `mattacku`'s
  differential reads `AC_VALUE(uac)` (the roll only for negative AC).
  Phase 4 (erosion) is counters (`oeroded` / `oeroded2`) that
  `ARM_BONUS` / `uac` read on every query — no cache invalidation;
  the live call sites are the fire trap and the acid passive attack.
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
- The demo plays the committed C-port combat in both directions: the
  demo monsters carry their PerMonst types (goblin / hill orc / bat;
  the monster->hero hits come from the mhitu attack tables) and the
  hero starts wielding a short sword (the uhitm subset on
  weapon.py's hitval / dmgval; backstab and the weapon special
  effects are deferred).
- Property system, the query half (core/props.py): C's `u.uprops[]`
  split two ways — the intrinsic state is a set on the monster; the
  extrinsic contribution of the worn gear is derived on every query
  from the `owornmask` scan (the computed-never-cached style).  The
  per-type `<Type>_on()` / `<Type>_off()` side effects and the
  UP_BLOCKED / UP_TEMP / UP_ARTIFACT halves stay STUBs (the props.py
  docstring).
- Scroll reading (core/scrolls.py, the read.c port): `ReadCommand`
  (C: 'R'/'r') + `read_scroll()` implement the first five C
  `seffects()` — blank paper, enchant weapon, enchant armor, remove
  curse, teleportation; the remaining seventeen handlers are STUBs
  (each with its C provenance in the module docstring).  The
  teleport collapses C's cursed level-teleport and the blessed
  getpos destination to the random floor-tile set.
- Rings (PLAN-RING.md, core/rings.py): donning / doffing a ring is a
  *producer* — `ring_on` / `ring_off` emit the `DiscoveryEvent` + the
  attribute messages, and the identity mutation (`Item.dknown` /
  `Item.known`, the per-game `oc_name_known` / `oc_encountered`) is
  applied only in the core choke point `rules.apply_discovery` via
  `process_events` (the DamageEvent / StatusEvent pattern).  The
  ability an ability-ring changes is computed, never cached
  (`rules.current_ability`, the `uac` style), so it feeds to-hit for
  free; the per-turn effects are `rings.tick_rings`; the remaining
  ring effects are STUBs (the rings.py docstring).
- The stairs system (PLAN-STAIRS.md, core/stairs.py): stairs are
  TERRAIN (`TerrainType.STAIRS` + `Tile.stair_dir`, C: the `ladder`
  mask) plus per-level STAIRWAY RECORDS (`World.stairs`), not traps.
  `World.map` is the CURRENT level; visited levels are parked in
  `World.levels` (memory is the save file — coming back up restores
  everything).  Entity level-membership (`Monster.lev` / `Trap.lev` /
  `Item.lev`) is filtered in exactly four places (`World.monster_at`,
  `World.items_at`, `check_traps`, `step`'s monster loop) — a missed
  filter is a cross-level ghost.  Levels 2..N generate lazily in the
  C mklev draw order; the transition mirrors C `goto_level`'s order;
  reaching `World.max_lev` wins.  The deferred list is
  PLAN-STAIRS.md §5.
- The hunger system (PLAN-HUNGER.md, core/hunger.py): the C 5.0
  0..2000 gauge + seven-state machine as data on `Monster`
  (`uhunger` / `uhs` / `fainted`); the per-turn ticker runs in the
  hero phase of `step` while the hero is fainted too (that is how a
  faint deepens into starvation); a big food is the C occupation
  (core/occupation.py) — the meal consumes the following turns, a
  nearby monster interrupts it, and eating the same item again
  resumes it.

**Intentional simplifications (documented, not bugs):**
- Monster AI: a monster that can see the hero (the ported vision,
  core/vision.py) chases with a greedy single step; the full
  `mmove()` (doors, fleeing, remembered positions, M2_WANDER, waking
  sleepers by sound) is future work.  A monster that cannot see the
  hero random-walks (C: wander).
- Web/pit "stuck" lasts 10 turns (NetHack: escape checks).
- Spell study/learning mechanics dropped; books have charges only.
- Spell damage is a flat 2d6 (the old `d6 * nd` referenced a stat that
  never existed).
- `src/priest.c` / `src/pray.c` are unported (the old Python sketches
  were dropped, never ported); they land as core systems — functions
  over `World` returning events — from the C originals (see
  "Suggested next steps").

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

1. Wire `QuaffCommand` into the console UI (zap / cast / eat are
   already wired; `q` is the quit key in this demo, so the quaff key
   is to choose).
2. Port `src/priest.c` / `src/pray.c` as systems (start from the
   local clone: `NetHack/src/priest.c` and `NetHack/src/pray.c`).
3. Fill in the scroll STUBs in `core/scrolls.py` as their machinery
   lands (the C provenance of each is in the module docstring).  Next
   candidates on existing machinery: SCR_DESTROY_ARMOR (the wrapper
   around the already-real `worn.disintegrate_arm` / `destroy_arm`),
   SCR_LIGHT (a `lit` flag on Tile), SCR_CONFUSE_MONSTER
   (rules.apply_confusion over nearby monsters).
4. Full monster AI (`mmove()`) on the ported vision: doors, fleeing,
   remembered positions, M2_WANDER (the greedy single-step chase is
   in).
5. If the system/entity matrix grows, evolve into a lightweight ECS —
   the events-out design stays the same.
