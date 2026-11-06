# CHANGES.md — terse change log (newest first)

House log of the implementation sessions: for each change, the why
and the architectural choices.  The full session specs are in the
PLAN-*.md files; the current state is in the module docstrings and
ARCHITECTURE.md.

## The glyph memory: the screen is now what the hero has seen

**Why:** the renderer drew `Tile.typ` -- the *true* terrain -- for
every square of the level, so the hero looked through every wall and
the map was 40x20 of mostly '#' (the wall test included stone, so
unexplored rock was indistinguishable from a corridor he had actually
walked down).  C splits this in three: vision decides what can be seen,
display decides what is *remembered*, and the window port draws it.
pyhack had only the first, so the previous session's `core/vision.py`
port had nothing to draw with -- its own docstring said `Tile` had no
seenv and there was no display to update.

**The choices:**

1. **`Tile.glyph` + `Tile.seenv` + `Tile.waslit` are the memory**
   (C: `rm.h`'s `glyph` / `seenv` / `waslit`).  `glyph` starts at
   `GLYPH_UNEXPLORED`, which draws blank, and only `newsym()` writes
   it -- only where `can_see()` says the hero is looking.  `seenv` (the
   C seen vector, SV0..SV7) records the octants a square was seen
   from, which is what makes an unseen wall draw as stone instead of as
   a wall.
2. **A new display layer, faithful to display.c** (`core/display.py`):
   `back_to_glyph()` (terrain -> glyph, including "a wall you have not
   seen is stone"), `wall_angle()`, `trap_to_glyph()`, the `map_*`
   recorders, `newsym()` (one square, "always correct"), `docrt()` (the
   full redraw: `vision_recalc()` then newsym every square), the
   `seenv`/`set_seenv()` bookkeeping and `mon_visible()`.  C's
   `print_glyph()` is `glyph_to_char()`; the window port is still
   `ui/console.render`.
3. **The glyph space and the defsym.h tables are `core/glyph.py`**
   (C: display.h's `glyph_offsets` + the defsym.h PCHAR table): the 74
   S_* cmap symbols with their characters, the glyph offsets and the
   `glyph_is_*` predicates.  This is also what made the renderer's
   hand-rolled glyph switches unnecessary -- walls are `|` / `-`,
   corridors `#`, a closed door `+`, an open one `|` / `-` (the old
   renderer's `'` is not a defsym.h symbol at all), a lit floor `.`.
4. **`render()` draws the memory, overlaid with the live things.**
   `ui.render` calls `display.docrt()` (as C's window port does before a
   redraw), paints `Tile.glyph` for every square, and overlays the hero
   `'@'`, visible monsters `'M'` and a triggered trap `'X'` -- monsters
   are *never* remembered (C: "monsters float above the map").
   Objects and known traps are remembered by `map_object()` /
   `map_trap()`, so they survive being out of sight, and a picked-up
   object is cleared by the next `newsym()` of its square.
5. **Blindness now reaches the display.**  `vision_recalc()` keeps C's
   `else if (Blind)` branch: the could-see array is still computed (so
   monsters can see the hero) but nothing is marked IN_SIGHT, so a
   blind hero sees only his memory.
6. **The demo cave's room floor is lit.**  With no light sources ported,
   `Tile.lit` is the only thing that tells a visible floor from rock,
   and the demo generator never set it, so the cave rendered blank.
   It is a ROOM (C's rooms are lit); `generate_map` now says so.  No
   rng draw gained or lost, so every pinned layout is unchanged.

Files: core/glyph.py (new), core/display.py (new), core/types.py
(`Tile.glyph` / `seenv` / `waslit`), core/vision.py (the blind branch,
the docstring's seenv note), core/worldgen.py (`lit=True` in the demo
map), ui/console.py (`docrt` + glyph painting + the legend), main.py
(one intro line), tests/test_display.py (new), tests/test_console.py
(re-pinned: visibility-aware item assertions, C's door/wall glyphs, the
unexplored-is-blank and seen-corridor-only regression tests),
tests/test_vision.py (the blind-hero test), README.md,
ARCHITECTURE.md.

Tests: 1166 green (19 new cases), mypy clean over 91 files, flake8
clean on every file touched.

Housekeeping: the stray `pyhack/~/.cache/mypy/` tree a past session
left behind (a mypy run with a bogus HOME) is moved out of the
checkout.

## Fix: `main.py --mklev` / `--cavern` died on the demo's rng

**Why:** the demo entry point was the one path no test ran, and it
still built its rng the way the pre-Wave-3 demo did:
`random.Random(42)` for every generator.  The generated levels draw
through C's `rn2` / `rnd` / `rn1` / `rnl` / `d` / `rne` --
`random.Random` has none of them -- so `python main.py --mklev` stopped
with `AttributeError: 'Random' object has no attribute 'rn2'` inside
`RectManager.rnd_rect()`, in the middle of `makelevel`, before a single
turn was played.  PLAN-MKLEV.md decision 8 said the port needs
`core.rnd.Rng`; nothing made the shell pass it.

**The choices:**

1. **The shell picks the stream, per generator** (`main.make_rng`).
   The pinned demo cave keeps `random.Random(42)` -- every earlier
   wave's expectation was recorded on that stream -- and `--mklev` /
   `--cavern` run on `core.rnd.Rng`, seeded from the same number so a
   generated game is as reproducible as the demo's.  `Rng` also exposes
   `randint` / `choice` / `shuffle`, so the rest of the runtime (`step`,
   the monster AI, the combat dice) runs on it unchanged: one rng for
   world generation and play, as before.
2. **The contract is refused at the seam.**  `worldgen.require_c_rng()`
   runs at the top of `_generated_level()` -- the funnel both
   `new_world()` and `generate_level()` use -- and raises a `TypeError`
   naming the missing draws and pointing at `core.rnd.Rng`.  A
   generating call with the wrong rng now fails in one line at the
   entrance instead of several hundred lines deep in the generator,
   and the lazy path (levels 2..N, generated in the middle of a
descent) is covered by the same check.
3. **The entry point is tested, not just the generators.**  The
   generators were covered by 130 mklev/cavern tests, all of which
   built their rng the right way (`Rng`); the untested part was
   `main.py`'s choice.  `test_the_demo_entry_point_builds_and_steps_
   every_generator` now runs `main.make_rng` -> `new_world` -> a few
   turns of `step` for all three generators, two tests pin the refusal
   (plus the message) on both entrances, and the new `tests/
   test_main.py` runs `main()` itself -- scripted keys, the console the
   only thing faked -- for `python main.py`, `--mklev` and `--cavern`,
   so the shell's loop (worldgen -> step -> events -> render) has a
   test from now on.

Files: main.py (`make_rng`, `SEED`), core/worldgen.py
(`require_c_rng`, `C_RNG_DRAWS`), tests/test_worldgen_generators.py,
tests/test_main.py (new), README.md (the `--mklev` / `--cavern`
invocations).

Tests: 1147 green (seven new cases), mypy clean over 88 files, flake8
clean on every file touched.

## Wave 4a/4b: the monster and object genesis (makemon / mkobj)

**Why:** every remaining level-generation stub was waiting for the same
two functions.  A generated level was populated by three hand-tuned demo
kinds and carried no floor objects at all, so a special room could not
ask for "a queen bee" or "an orc captain" and the vault had no hoard.
This wave lands `src/makemon.c` and `src/mkobj.c` -- table.txt row 1.

**The choices (PLAN-MAKEMON.md and PLAN-MKOBJ.md are the session
specs):**

1. **Two new system modules plus one shared choke point.**
   `core/makemon.py` is the makemon() funnel and its helpers,
   `core/mkobj.py` is the object genesis, and `core/place.py` is
   `goodpos()` / `enexto()` (src/teleport.c) -- placement lives apart
   because teleportation and the level change will need it too.  C's
   `next_ident()` is `World.new_id()`, and the per-type status
   (`svm.mvitals[]`) is `World.mon_state` (`core.mondata.MonState`, the
   ObjTables pattern).
2. **`makemon()` returns `Optional[Monster]`, and None is normal.**  C
   returns NULL for "no monster": no legal square, a genocided species,
   an extinct population.  The callers test the result (`fill_zoo` only
   sleeps a monster it got), so a None return keeps that shape without
   exceptions.
3. **The level is a parameter, not a global.**  `makemon(world, rng,
   ptr, pos, flags, map_=..., lev=..., in_mklev=...)`: a lazy level is
   generated while the hero stands on the previous one, so the map, the
   level number and `gi.in_mklev` are all threaded explicitly
   (PLAN-MAKEMON.md decisions 4 and 8).  `World.monster_at_lev` is the
   level-parameterised occupancy filter goodpos() needs -- one filter
   implementation, two entry points.
4. **The C draw order is kept**, because the level's rng stream is
   shared: position, then type, then hit points, then gender, then
   mood, then inventory.  The weighted reservoir sample of
   `rndmonst_adj()` (C's `rn2(totalweight) < weight` walk) is ported
   draw for draw, and mkobj's corpse / statue subjects go through the
   same sampler, so a corpse and a spawn can never disagree about what
   exists (or about genocide).
5. **The monster table grew a depth band, not a hand-typed 383 rows.**
   36 rows transcribed from include/monsters.h value by value: the ants
   and the bees (ANTHOLE / BEEHIVE), blobs, jellies, gas spore, floating
   eye, hobbit / dwarf / bugbear, the kobold leaders, the orc band
   through orc-captain, piercer / rothe / scorpion, the rodents, pony,
   white unicorn and the S_HUMAN soldiers (BARRACKS).  SUBSET_PM goes
   40 -> 76; the rows are assigned by C index, so the completion pass
   (the monsters.h converter, PLAN-MAKEMON.md §4.5) renumbers nothing.
   `_nams` is the C NAMS() builder, for the three gendered types.
6. **`Item` gains the struct obj fields and `container` becomes
   `carrier`.**  Containment is a list of ids on the parent
   (`Item.contents`), never an object graph, and a contained item keeps
   `pos` and `carrier` None -- so the three where-states (floor /
   carried / contained) are mutually exclusive by construction.  The
   rename is what keeps the old field from meaning two things; it is a
   mechanical sweep of every use in core/, ui/, conftest and the tests.
   The erosion defect PLAN-MKOBJ.md §2 flags disappears with the
   fields: `core.worn.erode_obj` reads `item.oeroded`, which a plain
   Item now has.
7. **The object genesis is a subset, class by class, and every gap is
   named.**  `mksobj_init` covers weapons, armour, food, potions,
   scrolls, spellbooks, wands, rings, amulets, the container tools,
   gems and rocks; the exotic per-otyp switches (tins, candy bars, the
   invocation tools) fall through to C's own `default: break`.  No
   timers (corpse rot, eggs, oil, ice): `Item.age` is written where C
   writes it and read nowhere.  No artifacts, no `splitobj`, no
   container merging, no monster weapon/inventory tables (phase E), no
   monster groups (phase F) -- the generator passes MM_NOGRP so the
   flag is honoured, not faked.
8. **The generator now uses both.**  `fill_ordinary_room()` calls
   `makemon(MM_NOGRP | MM_ASLEEP)` instead of picking one of three demo
   kinds (the old `_spawn_monster` body), and its object half places
   gold, statues and the final random object in C's order -- the
   fountains / sinks / altars / graves still wait for `set_levltyp`
   (table item 2) and their rolls are not taken, which is why they are
   listed as the next thing to land rather than quietly skipped.
   `rules.level_difficulty()` is the one depth helper every caller
   reads, so PLAN-SPLEV.md's dungeon topology is one edit.
9. **No alignment system, so `peace_minded()` is C's shape with
   constant inputs**: `World.hero_align` is A_NEUTRAL, so an aligned
   monster is hostile to the neutral hero and a neutral one gets C's
   co-aligned chance (PLAN-MAKEMON.md divergence 1).

Files: core/{makemon,mkobj,place}.py (new), core/{mondata,monst,
monst_defs,monst_data,types,rules,mklev,worldgen}.py, ui/console.py
and the carrier rename across conftest + the tests; tests/
{test_makemon,test_mkobj,test_place}.py (new) and the table-shape test.

Tests: the 480-row `mksobj` smoke test, the placement invariants (never
a wall / the hero / another monster / water a monster cannot survive),
the MM_ flag behaviour, the genocided / extinct refusal, the difficulty
band of rndmonst_adj, mkclass's class answer, the container
where-states, gold merging, the BUC lottery, and the generated-level
check that every monster carries a table row.

**Verified when the test runner came back (the follow-up fixes).**
The wave was written while pytest was crashing on startup, so its
tests had never executed.  The first real run (1140 tests green, mypy
clean over 87 files, flake8 clean) found three bugs in the new code
and four test expectations that were wrong about C:

1. **The genesis runs before the hero exists.**
   `new_world(generator="mklev"|"cavern")` generates level 1 *and
   then* installs the hero, so `World.hero` raised `KeyError: 'player'`
   in `adj_lev` / `rndmonst_adj` / `mkclass_aligned` / `mksobj_init` --
   every generated world crashed.  C is silently fine here because
   `u.ulevel` is already 1 from `u_init()` and `u_at(x, y)` reads
   `(0, 0)` during the first `mklev()`, which is never a real square.
   `World.hero_or_none` and `World.hero_ulevel` (C's default, 1) are
   now the genesis's two reads; the runtime keeps the strict
   `World.hero`.
2. **`goodpos()` fell through where C returns.**  C's pool and lava
   branches `return (is_swimmer(mdat) || m_in_air(mtmp))` -- before the
   ACCESSIBLE test -- so a flyer over a pool *is* a good position even
   though water is not accessible; the port continued into the
   accessible check and refused it (a bat could not be put over water).
   Same for lava.
3. **`accessible()` was the macro, not the function.**  C's `goodpos()`
   calls monmove.c's `accessible(x, y)`, i.e.
   `ACCESSIBLE(typ) && !closed_door(x, y)`; the port had only the
   ACCESSIBLE half, so a land monster could be placed inside a closed
   door.  Both halves are now in `core.place.goodpos()` (an amorphous
   monster still slides under it -- that test comes first, as in C).
4. **An object is registered when it is built, not when it is put
   somewhere.**  `mksobj()` now adds the object to `World.items` at
   creation (C: newobj(); and every `contents` entry is an id that has
   to resolve), with `place_object()` / `add_to_container()` still the
   only writers of the where-state.

Four *test* expectations were wrong about C and were corrected rather
than coded around: a specific type at a specific square is not
`goodpos()`-checked by `makemon()` (only the random-position and
random-type paths are); a statue's `spe` is the *caller's*
`corpstatflags & CORPSTAT_SPE_VAL`, so `fill_ordinary_room`'s
`CORPSTAT_NONE` overrides mksobj's gender roll; a chest from `mksobj`
arrives with its `mkbox_cnts` contents; and a monster's first attack
slot may be `AT_NONE` with a damage type (the floating eye's gaze, the
jellies' passive cold) -- `NO_ATK` is C's "no attack" row, not
`aatyp == 0`.  Two tests also asserted "a generated level has
monsters" per seed; C's filler gives a monster to one room in three,
so one level in four is legitimately empty -- they now count over six
or eight levels, which is the property they meant.

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
