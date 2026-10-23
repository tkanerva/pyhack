# Changes: stairs system (the multi-level dungeon)

Pending git push.  Summary of the working-tree state as of this
change: the hero can descend with `>` and climb back up with `<`, the
NetHack-faithful way -- stairs are TERRAIN plus per-level STAIRWAY
RECORDS, levels generate on first visit, previously visited levels
re-enter intact (kept in memory), and the hero re-appears on the
matching staircase of the other level.  Reaching the bottom level
(3 in the demo) wins.

Ground truth is the NetHack 5.0 C source (local clone at `../NetHack`):
`src/stairs.c` (the whole file -- the `gs.stairs` list), `src/do.c`
(`dodown`, `doup`, `u_collide_m`, `goto_level`), `src/dungeon.c`
(`next_level` / `prev_level` / `u_on_newpos` / `Is_botlevel`),
`src/mklev.c` (`mkstairs`, `generate_stairs`, the `makelevel` order),
`src/allmain.c` (`newgame`'s `mklev(); u_on_upstairs()`),
`include/rm.h` (`LA_UP 1` / `LA_DOWN 2`), `include/defsym.h`
(`S_upstair '<'` / `S_downstair '>'`).  The design, the simplifications
and the deferred list are in `PLAN-STAIRS.md`.

## Files changed

| file | change |
|---|---|
| `core/types.py` | **`STAIR_UP` / `STAIR_DOWN`** constants (C: the `levl[x][y].ladder` mask, rm.h LA_UP/LA_DOWN); **`Tile.stair_dir`** (0 = not a stair; worldgen is the only writer); **`Stairway`** frozen dataclass (C: the sx/sy/up/u_traversed half of struct stairway -- `isladder` dropped, `tolev` derivable as `lev +/- 1`); **`World.levels` / `World.lev` / `World.max_lev` / `World.stairs`**; **`Monster.lev` / `Trap.lev` / `Item.lev`**; `monster_at` / `items_at` gain the lev filter; the last two `TrapType` members (the STAIRS_DOWN/UP placeholders) removed -- no value shift |
| `core/events.py` | **`LevelChangeEvent(lev, first_visit)`** (C: the goto_level transition; `first_visit` is the mklev-vs-getlev branch) |
| `core/commands.py` | **`StairsCommand(up)`** (C: '>' -> dodown, '<' -> doup -- two C functions with one shared skeleton, collapsed) + the `Command` union |
| `core/stairs.py` | **new** -- `rebuild_stairs` (the stairway_free_all + re-add by map scan), `go_stairs` (the dodown/doup demo subset: stair lookup, the verbatim refusals, the stuck refusal, the range guard), `goto_level` (the do.c goto_level demo subset, in C order: guard -> park the old level -> generate/take-back -> set level + rebuild -> hero placement on the matching staircase -> the u_collide_m 50/50 -> vision reset/recalc -> events), `_u_collide_m`, `_free_adjacent` |
| `core/step.py` | wire `StairsCommand` into the player phase (the same `was_asleep` gate as the other commands); the monster loop `continue`s on `mon.lev != world.lev` (other levels frozen) |
| `core/traps.py` | the two STAIRS `TRAP_EFFECTS` entries removed; `check_traps` skips `trap.lev != world.lev` |
| `core/worldgen.py` | **`new_world(rng, levels=3)`** -- the fixed `LEVEL1_DN_STAIRS = (20, 2)` down stairs (reserved via keep_floor, **zero rng draws**), no level-1 up stairs (C: dlevel == 1), `world.max_lev = levels`, ends with `rebuild_stairs`; **`generate_level(world, lev, rng)`** -- the lazy level-2..N generator (C: mklev on first entry), draw order: map -> down stair -> up stair (C: generate_stairs order, down first) -> 10 traps -> 9 monsters, stair tiles reserved from everything, `Trap(lev=)` / `Monster(lev=)`, no floor items (the oinit distribution is deferred) |
| `ui/console.py` | STAIRS tiles draw C's defsym glyphs `'>'` / `'<'` (tile priority: after items/traps, before the wall check); legend gains `> = Stairs down | < = Stairs up`; the header line is `Level {lev} of {max_lev}`; `read_command`: `'>'` -> `StairsCommand(up=False)`, `'<'` -> `StairsCommand(up=True)` |
| `main.py` | banner: the `>` / `<` keys + the 3-level / bottom-level-wins note |
| `core/__init__.py` | export `StairsCommand`, `LevelChangeEvent`, `Stairway`, `STAIR_UP` / `STAIR_DOWN` |
| `tests/test_stairs.py` | **new** -- 14 tests: the worldgen plumbing, the generate_level determinism + stair placement, the bottom level, the descend/climb round trip through `step`, the refusals (no stairs / level 1 / bottom / stuck / asleep), the pinned 50/50 arrival collision (both sides), the cross-level isolation, the trap/item level filtering, and the full-game deterministic replay with the stairs |
| `README.md` | layout list + keys + the multi-level note |
| `ARCHITECTURE.md` | diagram, the behaviour-decision bullet, the deferred list |
| `CHANGES.md` | this file |

No other files changed; the existing suite is untouched and passes
unmodified (no new rng draw at `new_world` time -- the draw-sequence
test and the seed-42 determinism tests are byte-for-byte intact).

## Design decisions (kept consistent with the house rules)

1. **Stairs are terrain + records, not traps.**  C has no TT_STAIRS:
   stairs are `rm.typ == STAIRS` (walkable, `ACCESSIBLE`) with the
   `ladder` up/down mask.  The old `TrapType.STAIRS_DOWN/UP`
   placeholders were the LAST two enum members (removed, no value
   shift) and their two `TRAP_EFFECTS` entries are gone.
2. **One command, one entry point.**  `StairsCommand(up)` ->
   `step()` -> `go_stairs()`, exactly the QuaffCommand / ReadCommand
   pattern: a pure function over `World`, events out, injected rng.
3. **`World.map` stays the field holding the CURRENT level** (every
   existing system keeps working unmodified); `World.levels` holds
   the NON-current levels, parked/taken on every transition.  The
   level membership of entities (`Monster.lev` / `Trap.lev` /
   `Item.lev`, default 1 so the single-level tests are untouched) is
   filtered in EXACTLY FOUR places: `World.monster_at`,
   `World.items_at`, `check_traps`, `step`'s monster loop -- a missed
   filter is a cross-level ghost monster.
4. **Draw order is sacred.**  `new_world` gains no rng draw (the
   fixed stair is zero-draw); `generate_level` draws strictly inside
   the lazy call, in the C mklev order (map -> down stair -> up stair
   -> traps -> monsters) on the same injected stream, so generation
   happens at the moment the hero first descends -- exactly like C's
   main stream.
5. **The transition mirrors C `goto_level`'s order** (the demo
   subset): guard, park the old level (C savelev -> in memory),
   first visit ? generate : take back (C mklev / getlev), rebuild the
   stairways (C stairway_free_all + re-add), hero placement (C
   u_on_dnstairs going up / u_on_upstairs going down, the matching
   stair always exists in the main dungeon), the u_collide_m 50/50
   (C rn2(2) -> rng.randint(1,2)), the vision reset + recalc (C
   vision_reset + docrt), then the events: `LevelChangeEvent` + the
   C message lines VERBATIM ("You descend the stairs." / "You climb
   up the stairs.") + the first-visit level line + the bottom-level
   victory.
6. **Victory: reaching `max_lev` wins** (`GameOverEvent(victory=True,
   reason="You have reached the bottom of the dungeon!")`,
   `world.over` set).  The old all-monsters-cleared check is
   untouched: with lazy generation, unvisited levels contribute no
   monsters, so clearing level 1 before ever descending still wins
   the old way.

## Documented simplifications (not bugs; PLAN-STAIRS.md §4)

- **Levels stay in memory** (no save files at all): a visited level's
  full state lives in `World.levels` until game over, so "coming back
  up" restores everything exactly.
- **No encumbrance / fall damage** (C `goto_level`'s
  "You fall down the stairs." + 1d3 branch); no levitation, rooted,
  steed, pets, swallowed, ceiling-hiders.
- **No holes / trap doors / level teleporters to another level** --
  `TRAPDOOR` / `MAGIC_PORTAL` / `LEVEL_TELEPORTER` stay same-level
  teleports (C's `trap->dst` destinations are deferred).
- **No auto-pickup on arrival** (the demo requires `g`); no
  first-sighting stair message; no conduct / livelog / achievement
  bookkeeping; no regions, temperature, tutorial / quest / knox /
  endgame branches.
- **The hero does not start on the stairs** (C `newgame`:
  `mklev(); u_on_upstairs()` -> standing on the level-1 down stairs):
  the seeded demo keeps `HERO_POS = (20, 10)` and the fixed
  `LEVEL1_DN_STAIRS = (20, 2)`.
- **New levels carry no floor items** (the oinit object distribution
  is deferred).
- **A refused stair command consumes a turn** (C `ECMD_OK` vs
  `ECMD_TIME` collapsed -- the house rule, same as reads / quaffs).
- **`Stairway.traversed`** is kept for C fidelity but unused (it feeds
  C's `stairs_description()` branch text).
- **The 50/50 arrival collision** uses `rng.randint(1, 2)` (C
  rn2(2)); the "move the monster" side picks one random walkable
  unoccupied tile within Chebyshev distance 1 (C `mnexto` searches a
  wider ring); if neither side can move, the monster is DROPPED
  (`alive=False`, no message -- the demo has no limbo, C
  m_into_limbo).
- **Monsters never use stairs** (C-faithful: no monster level
  transit); they may stand on the walkable STAIRS tile.

## Tests

`pytest` from the repo root: 391 passed (377 pre-existing, unmodified
+ 14 new in `tests/test_stairs.py`).  Highlights:

- `new_world(random.Random(42), levels=3)`: the STAIRS/STAIR_DOWN
  tile at (20, 2), the hero at (20, 10), `max_lev == 3`,
  `world.stairs == [Stairway((20,2), up=False)]`, `world.levels == {}`
  -- and the existing draw-sequence / seed-42 tests pass
  unmodified (zero new draws).
- `generate_level` determinism: two same-seed descents, identical
  level-2 tiles / stair positions / trap / monster positions; the
  bottom level has UP stairs only, level 1 DOWN only; no
  trap/monster/item on a stair tile.
- The descend/climb round trip through `step()`: the hero on the
  destination's UP stairs, the C message lines verbatim, the
  `LevelChangeEvent` (first_visit True then False), level 1 parked
  with its monsters intact, the return to (20, 2) with level 2's
  state intact.
- The refusals (no stairs at the tile, `<` on level 1, `>` on the
  bottom, the stuck hero, the asleep hero): the verbatim C lines,
  `world.lev` unchanged, NO level generated, no `LevelChangeEvent`.
- Reaching the bottom level: the `GameOverEvent(victory=True)` in the
  same event list, `world.over` True, further commands return `[]`.
- The pinned arrival collision (SeqRng on a pre-parked level 2):
  even -> the hero offset by one adjacent tile, odd -> the monster
  moved, the hero keeps the stairs.
- Cross-level isolation: a wait on level 2 does not tick / move
  level-1 monsters; a level-1 trap at P does not trigger when the
  hero stands on P on level 2 (and vice versa after returning);
  `items_at` / `monster_at` never cross levels.
- The full deterministic replay with the stairs (walk to (20, 2),
  `>`, moves, `<`, ...) -- byte-for-byte, including the lazy level-2
  generation on the shared rng stream.

## Suggested commit sequence (house style: one commit per task)

1. `types: Stairway + StairsCommand + LevelChangeEvent + level fields
   (World.levels/lev/max_lev/stairs, Monster/Trap/Item.lev,
   Tile.stair_dir)` (core/types.py, core/events.py,
   core/commands.py, core/__init__.py)
2. `stairs: core/stairs.py -- the do.c/dungeon.c port
   (go_stairs, goto_level, rebuild_stairs, u_collide) + step wiring +
   level filtering (monster_at/items_at/check_traps/monster loop) +
   remove the STAIRS trap placeholders` (core/stairs.py new,
   core/step.py, core/traps.py, core/types.py)
3. `worldgen: multi-level new_world(levels=3) + lazy generate_level +
   the fixed level-1 down stairs` (core/worldgen.py)
4. `demo: stair glyphs + level header + the > / < keys + banner`
   (ui/console.py, main.py)
5. `tests: test_stairs.py + docs` (tests/test_stairs.py new,
   README.md, ARCHITECTURE.md, CHANGES.md)
