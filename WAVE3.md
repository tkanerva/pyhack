## Wave 3: the level generators (mklev / mkroom / mkmap) + doors

**Why:** the level was a 40x20 rectangle with 15 random walls, 10 traps
and 9 monsters; nothing was a *room*, so nothing could be a room-shaped
feature (a shop, a temple, a vault, a niche) and the map did not look
like NetHack.  This wave lands the generator, which is the biggest
"looks like NetHack" change available.

**The choices (design decisions, PLAN-MKLEV.md has the full table):**

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
   `World.levels`, so coming back up restores the room records exactly
   (PLAN-STAIRS decision 3 applied to the new state).  `Room` is
   identity-compared (`eq=False`): `Map.room_of()` must find *that*
   room, not the first one with the same geometry.
3. **No ambient level globals.**  C's generators read `svr.rooms[]`,
   `gs.smeq[]`, `gd.doorindex`, `svd.doors[]`, `gs.stairs`.  Here the
   Map is a parameter and the transient arrays are arguments -- which is
   exactly what lets a level be generated while the hero still stands on
   the previous one.
4. **`Tile` gains the four `rm.h` fields the work needs** (`roomno`,
   `edge`, `lit`, `horizontal`) with the C `NO_ROOM` / `SHARED` /
   `ROOMOFFSET` values, plus `RoomType` (the mkroom.h enum, values
   kept) and `LevelFlags` (`svl.level.flags`, reduced to what is set).
5. **Doors are terrain plus a system.**  `TerrainType.DOOR` +
   `Tile.door_mask` (plain / open / closed / locked / trapped) or
   `SDOOR`, which stays part of the wall.  `core/doors.py` is the
   interaction half (`lock.c` `doopen` / `doclose`), wired two ways:
   walking into a closed door opens it (C: `domove`, so there is no
   `OpenCommand`) and `CloseCommand` + a direction closes one (`x` in
   the console, because `c` casts).
6. **Draw order preserved through the STUBs.**  Where a branch is
   unported (a mimic in a trapped doorway, the boulder in a dead-end
   corridor) the roll is still taken, so the later port changes no
   sequence.
7. **Seven documented divergences** from C, all in PLAN-MKLEV.md §3;
   the two that matter: `create_room()` numbers its room immediately
   (C leaves `roomno` unset until after `makecorridors()`, whose door
   check needs it -- C's `sp_lev` path does the same explicitly), and
   the cavern generator retries a failed corridor with a plain L so a
   level is never split in two.

Files: core/{mklev,mkroom,mkmap,doors,types,worldgen,step,commands,
__init__}.py, ui/console.py, main.py (`--mklev` / `--cavern`),
PLAN-MKLEV.md.

Tests: tests/{test_mklev,test_mkroom,test_mkmap,
test_worldgen_generators}.py (130 new cases, including a 400-command
random-walk smoke test on each generator) + four console-glyph cases.
The structural ones are the point: every room reachable (8-way, like
the hero), every room entered through a door, one stair per direction
with the C rules, determinism, and the demo path unchanged.

