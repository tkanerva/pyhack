# CHANGES.md — terse change log (newest first)

House log of the implementation sessions: for each change, the why
and the architectural choices.  The full session specs are in the
PLAN-*.md files; the current state is in the module docstrings and
ARCHITECTURE.md.

## Wave 3: the level generators (mklev / mkroom / mkmap) + doors

**Why:** the level was a 40x20 rectangle with 15 random walls, 10
traps and 9 monsters; nothing was a *room*, so nothing could be a
room-shaped feature (a shop, a temple, a vault, a niche) and the map
did not look like NetHack.  This wave lands the generator, the
biggest "looks like NetHack" change available.

**The choices (WAVE3.md is the write-up, PLAN-MKLEV.md the session
spec with the full table):**

1. **Behind a switch, so nobody's pinned layout moves.**
   `new_world(rng, generator=…)` takes `"demo"` (the default -- the
   pinned cave every earlier wave's tests assert), `"mklev"` (rooms +
   corridors + doors) or `"cavern"` (the cellular automaton).  The
   name is stored in `World.generator` because levels 2..N are built
   lazily in `goto_level`, and `generate_level` dispatches on it.  The
   demo path is byte-for-byte the old one: `test_same_seed_same_game`
   and the "new_world makes no new rng draws" test still pass
   unchanged.
2. **Rooms are level state, not World state.**  `Map.rooms` /
   `subrooms` / `doors` / `flags` are parked with the map in
   `World.levels`, so coming back up restores the room records
   exactly.  `Room` is identity-compared (`eq=False`): `Map.room_of()`
   must find *that* room.
3. **No ambient level globals.**  C's generators read `svr.rooms[]`,
   `gs.smeq[]`, `gd.doorindex`, `svd.doors[]`; here the Map is a
   parameter and the transient arrays are arguments -- exactly what
   lets a level be generated while the hero still stands on the
   previous one.  (This caught one: the niche half of mklev took
   `world.map` and carved the PARKED level on a lazy descent -- fixed
   by threading `map_` through make_niches / makeniche / makevtele,
   pinned by test_lazy_generation_does_not_touch_the_previous_level.)
4. **`Tile` gains the four `rm.h` fields the work needs** (`roomno`,
   `edge`, `lit`, `horizontal`) with the C `NO_ROOM` / `SHARED` /
   `ROOMOFFSET` values, plus `RoomType` and `LevelFlags`.
5. **Doors are terrain plus a system.**  `TerrainType.DOOR` +
   `Tile.door_mask` or `SDOOR` (part of the wall).  `core/doors.py` is
   the interaction half (`lock.c` `doopen` / `doclose`): walking into
   a closed door opens it (C: `domove`, so there is no `OpenCommand`)
   and `CloseCommand` + a direction closes one (`x<n/s/e/w>` in the
   console, because `c` casts).
6. **Draw order preserved through the STUBs.**  Where a branch is
   unported the roll is still taken, so the later port changes no
   sequence.  Seven documented divergences from C, in PLAN-MKLEV.md
   §3.

Files: core/{mklev,mkroom,mkmap,doors,types,worldgen,step,commands,
__init__}.py, ui/console.py, main.py (`--mklev` / `--cavern`).

Tests: tests/{test_mklev,test_mkroom,test_mkmap,
test_worldgen_generators}.py + four console-glyph cases.  The
structural ones are the point: every room reachable (8-way, like the
hero), every room entered through a door, one stair per direction with
the C rules, determinism, and the demo path unchanged.

## Experience & leveling (core/experience.py, the exper.c port)

**Why:** the hero had no experience system -- kills dealt damage and
that was it.  The 5.0 system is structural in one way: `struct
permonst` has no `mexp` column, so the kill XP is COMPUTED from the
monster's instance level / effective AC / speed / attack table (C
`experience()`, exper.c), not read from a table.

**The choices (PLAN-EXPERIENCE.md decisions 1-12):**

1. One new module `core/experience.py` -- pure functions over World +
   an injected rng; the hero-facing plines come out as MessageEvents.
   The XP gain itself is silent, as in C.
2. The grant sits in the DEATH choke point: `rules.apply_damage`
   grants the kill XP when a non-hero monster dies with
   `source == world.hero.id` (C: the mon.c kill wrapper -- 5.0's
   mondead does NOT grant XP).  The zap damage sources are normalized
   to the caster id (the `"zap:xxx"` strings retired), so wand and
   spell kills flow through the same gate; `DeathEvent.by` for a zap
   kill is `"player"` like for melee.
3. The six hero fields land on `Monster` (`uexp` / `urexp` /
   `ulevelmax` / `ulevelpeak` / `uhpinc` / `m_lev`); the monster
   instance level is PINNED to `mdata.mlevel` at spawn (zero draws --
   the seed-42 layout / draw-sequence tests stay untouched; the C
   `adj_lev` roll lands with the makemon port).
4. `newhp` is the draw-free demo form (base 2 + the C CON table, the
   hpadv rnd lands with role selection); the level-up Pw reuses
   `energy.newpw` -- its ONE draw (at the first, L1 -> L2, level-up)
   is the only draw of the whole XP path.
5. **The `ueninc[]` fix (the subtle C/pyhack discrepancy this round
   turned on):** the array is the per-level Pw INCREMENT (C you.h:
   "increases to uenmax for each level gain") -- C's newpw() records
   it ("remember increment; future level drain could take it away
   again"), losexp() subtracts it.  The committed energy.py had
   repurposed it as the regen-PERIOD table, which collided with the
   port (a level-2 drain would have subtracted the period, ~36, from
   uenmax).  Now: init_energy records the starting Pw in the init
   slot (ueninc[0] -- C's u_init runs newpw at level 0, as uhpinc[0]),
   pluslvl records the old level's slot, and tick_energy computes the
   period from the level directly (C `regen_pw`:
   `(MAXULEV + 8 - u.ulevel) * (wizard ? 3 : 4) / 6`; the demo uses
   the base period) -- the SAME values as before, no behaviour
   change.
6. `losexp` lands this round (the HP / Pw / XP reduction, the
   level-1 + drainer death through the same death bookkeeping as
   apply_damage, the divine-anger reset, the `#levelchange` override,
   the "Goodbye level N." / "Welcome back" messages); its live call
   site lands with the mhitu AD_DRLI port (synthetic-drain unit tests
   for now).

Files: core/{types,experience,rules,zap,worldgen,energy}.py,
ui/console.py, tests/test_experience.py (34 tests).

## ObjType is a literal enum (core/objects_enum.py)

**Why:** the typing baseline left 283 mypy errors, all one systematic
problem: `ObjType` built with the functional `IntEnum` API has no
statically visible members (`"type[ObjType]" has no attribute
"DAGGER"` in 11 files), and no annotation at the ~280 use sites can
fix that — a literal class body is the only form mypy reads the
members from.

**The choice:** `core/objects_enum.py` spells the 480 members out
(one per line, C order, `auto()` values, the C grouping comments)
plus the enum markers (`FIRST_OBJECT`, ..., `NUM_OBJECTS`) and the
`O` alias; `objects.py` re-exports everything (`__all__` unchanged,
no importer touched).  `objects.py` keeps the assembly (`BASES`,
`object_type()`, the sanity checks); `_validate()` asserts the enum
agrees with `objects_data`'s name column (the same C table expanded
twice, as the C preprocessor does).  Typing the enum surfaced two
hidden mismatches: the `_ABILITY_RING` maps (rules.py, rings.py) are
keyed by `ObjType` but looked up with a plain `int` `Item.otyp` —
now `Dict[int, str]` (an IntEnum member is its int at run time, so
the lookups behave exactly as before).  Result: 283 -> 0 mypy errors.

## Typing baseline: the C-table module split (+ the mypy config)

**Why:** mypy reported 1366 errors, 1083 of them the same import
cycle (`objects.py` importing its table back from `objects_data.py`,
which imported the constants from `objects.py`): "Cannot determine
type of `HI_METAL`" for every C constant.  The alternative was an
explicit `int` annotation on every constant.

**The choice:** mirror the C layout — *declare* in the headers,
*define* in the .c table: `*_defs.py` (the enums, the constants, the
row types, the row-macro builders), `*_data.py` (the table rows,
verbatim), the API module (the derived indices, the accessors, the
sanity checks).  The chain is one-way (`*_data` -> `*_defs`; the API
imports both), so every C-style integer constant stays a plain
inferred `int` with no annotation anywhere.  Applied to both tables
(objects, monst); every name reachable as `core.objects.X` /
`core.monst.X` before is still reachable.  The mypy config (it lived
in mypy.ini; it is now `[tool.mypy]` in pyproject.toml) pins the file
set a bare `mypy` checks (`core`, `ui`, `tests`, `main.py`,
`conftest.py`) and suppresses nothing — the count is the point; the
strict flags are switched on one at a time as the count reaches zero.
Result: 1366 -> 283 errors (the rest was the enum problem above).

## Stairs: the multi-level dungeon

**The choices (design decisions):**

1. Stairs are terrain + records, not traps (C has no TT_STAIRS):
   `TerrainType.STAIRS` + the `Tile.stair_dir` ladder mask (rm.h
   LA_UP / LA_DOWN), plus the per-level `Stairway` records in
   `World.stairs`, rebuilt by a map scan on every level entry.  The
   old `TrapType.STAIRS_DOWN/UP` placeholders (the LAST two enum
   members) and their two `TRAP_EFFECTS` entries were removed, no
   value shift.
2. One command, one entry point: `StairsCommand(up)` -> `step()` ->
   `go_stairs()` (the dodown / doup demo subset: the stair lookup,
   the verbatim C refusals, the stuck refusal, the range guard) —
   exactly the QuaffCommand / ReadCommand pattern.
3. `World.map` stays the field holding the CURRENT level (every
   existing system keeps working unmodified); `World.levels` holds
   the NON-current levels, parked / taken on every transition
   (memory is the save file).  Entity level-membership
   (`Monster.lev` / `Trap.lev` / `Item.lev`, default 1 so the
   single-level tests are untouched) is filtered in EXACTLY FOUR
   places: `World.monster_at`, `World.items_at`, `check_traps`,
   `step`'s monster loop (other levels frozen) — a missed filter is
   a cross-level ghost monster.
4. Draw order is sacred: `new_world` gains no rng draw (the fixed
   level-1 down stairs at (20,2) are reserved, zero draws);
   `generate_level` draws strictly inside the lazy call, in the C
   mklev order (map -> down stair -> up stair -> traps -> monsters)
   on the same injected stream.
5. The transition mirrors C `goto_level`'s order (the demo subset):
   guard -> park the old level -> first visit ? generate : take back
   -> rebuild the stairways -> hero placement on the matching
   staircase (C `u_on_dnstairs` / `u_on_upstairs`) -> the
   `u_collide_m` 50/50 -> vision reset / recalc -> the events
   (`LevelChangeEvent` + the C message lines verbatim + the
   first-visit level line + the bottom-level victory).
6. Victory: reaching `World.max_lev` wins (`GameOverEvent`); the old
   all-monsters-cleared check is untouched (with lazy generation,
   unvisited levels contribute no monsters).

Documented simplifications (PLAN-STAIRS.md §4-5): no encumbrance /
fall damage, no holes / trap doors / level teleporters to another
level, no auto-pickup on arrival, no monster level transit, new
levels carry no floor items, a refused stair command consumes a
turn, the hero does not start on the stairs (the seeded (20,10) is
kept, a house rule), a collision neither side can resolve DROPS the
monster (no limbo).

Files: core/{types,events,commands,stairs,step,traps,worldgen,
__init__}.py, ui/console.py, main.py, tests/test_stairs.py (14
tests).
