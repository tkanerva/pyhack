# Plan: Wave 3 — structure (mklev / mkroom / mkmap)

**Status (2026-10-31):** implemented and tested.  Three new modules
(`core/mklev.py`, `core/mkroom.py`, `core/mkmap.py`) plus the door
interaction module (`core/doors.py`), the value types the generators
needed (`Room`, `RoomType`, `LevelFlags`, `Tile.roomno/edge/lit/
horizontal`, `Map.rooms/subrooms/doors/flags`) and the generator switch
`new_world(generator=…)`.  521 tests green (391 before the wave), mypy
clean.

**Finishing pass (same wave):** the session that landed this stopped
mid-cleanup, which left two things behind, both fixed here:

1. `tests/test_look_tmp.py` -- a scratch "render a level and `assert
   False` to see it" file that pytest collected, so the suite was red.
   Removed (kept outside the repo); the glyphs it was eyeballing are
   pinned by the four console cases in §6.
2. `test_the_generator_stocks_the_level` asserted "this one level has
   monsters" on seed 5, which is a coin flip: C stocks a room with a
   monster 2 times in 3, and the demo's 40x20 grid only holds 2..6
   rooms (see §5).  The test now spans seeds 1..10 and asserts the
   invariants of everything that *was* placed (level tag, walkable
   square, inside a room, asleep; traps on walkable squares).

Both are test-only: no generator or system code changed in this pass.

The blast-radius risk this wave was flagged for did **not** materialise,
because the switch defaults to `"demo"`: every pinned expectation of the
earlier waves (the 42-seed layout, the "no new rng draws" test,
`test_same_seed_same_game`) still runs against exactly the same world.
A generated game is opt-in (`generator="mklev"` / `"cavern"`, or
`python main.py --mklev`).

Goal: the level stops being a 40x20 rectangle with 15 random walls and
becomes a NetHack level — rooms, corridors, doors (open / closed /
locked / secret / trapped), lit rooms, and a map that knows which room
each square belongs to.  Second generator (a cavern) so the level *type*
is a choice, not an accident.

Ground truth is the NetHack 5.0 C source in `../NetHack`
(`src/mklev.c`, `src/mkroom.c`, `src/mkmap.c`, the room half of
`src/sp_lev.c`, `src/rect.c`, the `doopen`/`doclose` half of
`src/lock.c`), read through `nethack_index` (INDEX.md rows, the
`symbols/*.json` spans, `PROGRESS_SESSION_30.md` §4 for mkmap and
`PROGRESS_SESSION_32.md` §8 for mkroom).

---

## 1. What the C code does (reference)

| Mechanic | C location | Port |
|---|---|---|
| free-rectangle manager (`init_rect`, `rnd_rect`, `get_rect`, `split_rects`, `remove_rect`, `add_rect`, `intersect`) | `src/rect.c` | `mklev.RectManager` (+ the module-level `Rect`, `_intersect`) |
| room records `struct mkroom` | `include/mkroom.h` | `types.Room` (identity-compared, doors as a list, subrooms as indices) |
| room numbering (`NO_ROOM` / `SHARED` / `ROOMOFFSET`, the 6-bit `rm.roomno`) | `include/mkroom.h`, `include/rm.h` | `types.NO_ROOM/SHARED/ROOMOFFSET`, `Tile.roomno` |
| `check_room`, `create_room`, `create_subroom` | `src/sp_lev.c` | `mklev.check_room`, `mklev.create_room`, `mklev.create_subroom` |
| `do_room_or_subroom`, `add_room`, `add_subroom`, `sort_rooms` | `src/mklev.c` | same names |
| `makerooms`, `join`, `makecorridors` | `src/mklev.c` | same names (`smeq` is an explicit list) |
| `finddpos`, `finddpos_shift`, `good_rm_wall_doorpos` | `src/mklev.c` | same names |
| `add_door`, `dosdoor`, `dodoor`, `bydoor`, `okdoor`, `maybe_sdoor` | `src/mklev.c` | same names |
| `dig_corridor` | `src/sp_lev.c` | `mklev.dig_corridor` → `(arrived, squares)`. |
| `place_niche`, `makeniche`, `make_niches`, `makevtele` | `src/mklev.c` | same names |
| `topologize`, `level_finalize_topology` | `src/mklev.c` | same names |
| `wallify_map` | `src/sp_lev.c` | `mklev.wallify_map` |
| `clear_level_structures`, `count_level_features` | `src/mklev.c` | same names |
| `mkstairs` (the stair half), `generate_stairs*` | `src/mklev.c` | `mklev.mkstairs`, `_stairs_room_good`, `_stairs_find_room`, `generate_stairs` |
| `fill_ordinary_room` (monster + trap half), `mktrap` | `src/mklev.c` | `mklev.fill_ordinary_room`, `mklev.mktrap` (demo subset) |
| `isbig`, `pick_room`, `somex/somey/somexy/somexyspace`, `inside_room`, `nexttodoor`, `has_dnstairs/has_upstairs`, `search_special`, `do_mkroom`+`mkzoo` | `src/mkroom.c` | `core/mkroom.py` (same names) |
| `shrine_pos`, `invalid_shop_shape`, `nexttodoor` | `src/mkroom.c` | `core/mkroom.py` |
| `mkmap`, `init_map`, `init_fill`, `pass_one..three`, `flood_fill_rm`, `join_map`, `finish_map`, `litstate_rnd` | `src/mkmap.c` | `core/mkmap.py` (same names) |
| `closed_door` macro | `include/rm.h` | `doors.closed_door` |
| `doopen` / `doopen_indir` | `src/lock.c` | `doors.open_door` |
| `doclose` | `src/lock.c` | `doors.close_door` |
| walking into a closed door opens it | `src/hack.c` `domove()` | `step._do_move` (the hero branch) |

---

## 2. Design decisions

1. **The generator is a World setting.**  `new_world(rng,
   generator=…)` takes `"demo"` (default), `"mklev"` or `"cavern"`;
   the name is stored in `World.generator`, because levels 2..N are
   built lazily inside `goto_level`, long after `new_world` returned.
   `generate_level` dispatches on it.  The demo path is byte-identical
   to the previous waves.
2. **Rooms live on the Map, not on the World.**  `Map.rooms` /
   `subrooms` / `doors` / `flags` are parked with the map in
   `World.levels` when the hero leaves, so a revisited level keeps its
   rooms (PLAN-STAIRS.md decision 3, applied to the new state).
3. **No ambient level state.**  C reads `svr.rooms[]`, `gs.smeq[]`,
   `gd.doorindex`, `svd.doors[]`, `gs.stairs` as globals.  Here the map
   is a parameter and the transient per-level arrays (`smeq`, the
   stairways placed so far, the traps placed so far) are explicit
   arguments.  This is what makes it possible to generate a level that
   is *not* the current one — which the lazy levels 2..N need.
4. **`Room` is identity-compared** (`@dataclass(eq=False)`), because
   `Map.room_of()` / `Map.rooms.index()` must find *that* room, not the
   first one with the same geometry.
5. **Doors are terrain + a mask.**  `TerrainType.DOOR` +
   `Tile.door_mask` (the existing `DoorMask`) + `Tile.horizontal` (C's
   `rm.horizontal`, which decides the open/closed glyph); `SDOOR` stays
   part of the wall until found.  Opening/closing is a *system*
   (`core/doors.py`), not a generator detail.
6. **Opening is on the movement key.**  Walking into a closed door
   opens it (C: `domove`), which is why there is no `OpenCommand`.  The
   close command exists (`CloseCommand`, bound to `x` in the console
   because `c` casts) and takes a direction.
7. **Everything the C function does draws in the C order.**  Where a
   branch is a STUB (a mimic in a doorway, the boulder in a dead-end
   corridor, the trick chest) the *rng roll is still taken*, so a later
   port does not have to re-derive the sequence.
8. **`generator="mklev"` needs `core.rnd.Rng`.**  The generators draw
   through `rn2`/`rnd`/`rn1`/`rnl` (`Random` has none of those);
   `Rng` keeps the old demo working too (it also exposes
   `randint`/`choice`/`shuffle`).

---

## 3. Deliberate divergences (documented, not bugs)

1. **`create_room()` numbers its room immediately** (`topologize`),
   where the C classic path leaves `roomno` alone until
   `level_finalize_topology()`.  `good_rm_wall_doorpos()` reads the
   `roomno` of the square *inside* a wall, and `makecorridors()` runs
   *before* `level_finalize_topology()` — without the early numbering
   no door or corridor is ever placed and the level has no corridors at
   all.  C's `sp_lev` path does exactly this explicitly
   (`topologize(aroom); /* set roomno */`).
2. **`mkmap.join_map()` retries a failed corridor with a plain L.**
   C's `dig_corridor()` can run out of steps and give up, which leaves
   a cavern region cut off; a demo level must stay walkable because the
   stairs and the hero are placed on `floor_tiles()`.
3. **`mkmap.join_map_cleanup()` is a no-op.**  C throws the *temporary*
   rooms it used to dig the corridors away (`svn.nroom = 0`), leaving a
   cavern with no room records; pyhack keeps them (they are what
   `somexyspace` / `room_at` / the future special rooms read).  The
   numbers the flood fill stamped are the room indices, so nothing has
   to be recomputed.
4. **`sort_rooms()` sorts stably** (Python) where C uses `qsort`; the
   order of two rooms with the same left edge may differ, which only
   changes which corridor is dug first.
5. **The classic generator fills every `OROOM`.**  C gates
   `fill_ordinary_room()` on the `needfill` flag, a `sp_lev` concept
   for special levels; the field is not carried (see `types.Room`).
6. **`impossible()` becomes a refusal** (`None` / `False`), with the C
   branch named in a comment: a generated level must never abort the
   game over a geometry edge case.
7. **A cavern's rooms are then filled** through the same
   `fill_ordinary_room()` the room generator uses (C: the rooms a
   cavern does not keep).

---

## 4. STUBs (each raises `NotImplementedError` naming its C)

| STUB | waits for |
|---|---|
| `mkroom.mkshop` | the `shknam.c` `shtypes[]` table + `shk.c stock_room()` |
| `mkroom.mktemple` | the altar `altarmask` + `priest.c priestini()` |
| `mkroom.mkswamp` | `set_levltyp` (the sanctioned terrain mutator) + monster generation |
| `mkroom.fill_zoo` | `makemon` / `mksobj` / `mkgold` / `make_grave` |
| `mkroom.courtmon/squadmon/morguemon/antholemon/mkundead/mk_zoo_thronemon` | `mkclass()` + the monster tables + the `mvitals` genocide flags |
| `mkmap.remove_rooms` / `remove_room` | special levels (the only caller) |
| `mklev.makerooms`'s Lua themed-room hook | themed rooms (`dat/*.lua`); the plain rectangle loop is what runs |
| the vault (`create_vault` / `mk_knox_portal`) | special-room stocking + the portal machinery |
| `fill_ordinary_room`'s gold / chests / statues / fountains / sinks / altars / graves / engravings | `mkgold` / `mksobj` (listed in C order in the function) |
| `mktrap`'s type table / dead adventurer / boulder launch | `traptype_rnd` by depth, `mktrap_victim`, `mkobj` |
| `makeniche`'s treasure branch | `mkobj` (the trap and the secret door are real) |
| `doors.open_door`'s `b_trapped` | `trap.c`'s door/chest trap damage |
| the autounlock follow-up, the no-hands polymorph check, the door mimic | `lock.c`'s key/kick offers, `polyself`, `makemon` |
| monsters opening doors | `monmove.c mmove()` |

---

## 5. What a generated level looks like

`mklev` on a 40x20 grid, seed 7: 4 rectangular rooms of 2x2 up to
15x6, lit, walled with `HWALL`/`VWALL` and the four corner types,
connected by `CORR` corridors with a door at each end (plain, open,
locked or secret by C's lottery), one down and (from level 2) one up
staircase standing on free room floor, a handful of secret alcoves in
the outer walls, plus the demo monster kit and the demo trap kit.

Room density is the one number that does *not* look like NetHack, and
it is a size artefact, not a port bug: the free-rectangle margins are
NetHack's (`XLIM` 4 / `YLIM` 3), so on the demo's 40x20 grid a large
room plus its margin eats most of the level.  Measured over seeds
1..15 (depth 2): 2..6 rooms, 2..16 doors, 0..4 monsters, 0..1 traps --
which is exactly C's arithmetic, evaluated on a smaller map.  The same
code on a NetHack-sized 80x21 map (seed 5): 8 rooms, 27 doors, 4
monsters.  Widening the generated levels is a display question (the
console renders the whole 40x20 map at once), see §7.

`cavern` on the same grid: a 40% cellular-automaton blob, smoothed over
three passes, cut into 3..7 *irregular* rooms (blob-shaped, numbered by
`flood_fill_rm`), joined by corridors, walled, lit, and populated by the
same filler.

---

## 6. Tests

| file | what it pins |
|---|---|
| `tests/test_mklev.py` | the room primitives (walls/corners/floor, `topologize`, `SHARED`, `sort_rooms` renumbering, `check_room`, `dig_corridor`, `RectManager`), and the finished level: rooms exist, **every room reachable** (8-way, like the hero), **every room entered through a door**, valid door masks, exactly one stair per direction with the C rules (no up on level 1, no down on the bottom), stairs on free room floor, determinism, the level size coming from the Map, re-generation over an existing level, and the STUBs |
| `tests/test_mkroom.py` | geometry (`somex/somey/somexy/somexyspace`, `inside_room`, `occupied`, `nexttodoor`, `has_*stairs`), room lookup (`pick_room` incl. the stairs and single-door rules, `search_special` with `ANY_TYPE`/`ANY_SHOP`), `shrine_pos`, `invalid_shop_shape` (the dead-end shape), and the `do_mkroom` dispatch |
| `tests/test_mkmap.py` | `litstate_rnd` (including the short-circuit draw count), `init_map`/`init_fill` (exactly the 40% limit), `pass_one`, `flood_fill_rm` (extents, `anyroom` walls, `SHARED`), a finished cavern (size, irregular rooms, cavernous flag), joined blobs, walled/lit variants, determinism, the `remove_rooms` STUB |
| `tests/test_worldgen_generators.py` | the switch itself: the three names, an unknown name refused, `"demo"` unchanged (hero at (20,10), 10 traps, no rooms), each generator's world playable / deterministic / carrying the demo kit, lazy level 2 using the same generator, a real descent-and-return keeping the level, and the door commands through `step()` |
| `tests/test_console.py` | the new glyphs: `+` closed door, `'` open door, secret door still `#`, corridor `#`, lit floor `.`, unlit floor blank |

---

## 7. Next (the natural continuation of this wave)

1. **`set_levltyp`** — the sanctioned terrain mutator (`mkmaze.c`): the
   choke point the swamps, digging, doors and destruction all need.
   It is the single highest-value small port left in level work.
2. **`makemon` / `mksobj` / `mkgold`** (`makemon.c`, `mkobj.c`): they
   turn every STUB above into a few lines — special rooms, room
   contents, the vault, traps with corpses.  It is also the door to the
   object distribution (`o_init`'s `oinit`).
3. **Monster pathing** (`monmove.c mmove`): with this wave's doors, the
   monster AI is now visibly wrong — a monster cannot follow the hero
   through a door.  `find_and_open_door` is the missing piece.
4. **Special rooms**, in this order: temple (`priest.c` is small),
   zoo family (needs 2), shop (needs 2 + `shk.c`).
5. **`wallification`** (`mkmaze.c fix_wall_spines` + `wall_cleanup`):
   the corner fix-up C runs after every generated level; the simpler
   `wallify_map` ported here is enough for rectangular rooms and
   caverns, but corridors meeting walls need it.
6. **Lighting** (`light.c`, `Tile.waslit`, the hero's light radius): the
   `lit` flag is set but nothing reads it except the display.
7. **A NetHack-sized level** (80x21 + a console viewport): every
   generator here is size-driven, and §5 shows the cost of the demo's
   40x20 grid -- 2..6 rooms instead of 8.  This is the change that
   would make the biggest visible difference per line, and it touches
   only `Map` construction plus `ui/console.py` (which today draws the
   whole map and would need a window around the hero, as C's
   `docrt()` + cursor does).

Housekeeping outside this wave: `core/occupation.py` is not in the
repo -- the hunger wave's real implementation went missing and a
placeholder stands in for it.  `step.run_occupation` and
`hunger.py`'s meal generator do run against the placeholder, but until
the real module is restored (or re-ported from `allmain.c`
`do_occupation` / `eat.c` `done_eating`, which the placeholder's own
docstring describes), the occupation mechanism should be treated as a
hole, not as ported work.
