# CHANGES.md — terse change log (newest first)

House log of the implementation sessions: for each change, the why
and the architectural choices.  The full session specs are in the
PLAN-*.md files; the current state is in the module docstrings and
ARCHITECTURE.md.

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
