# Plan: Wave 6 — special levels (`sp_lev.c` + the `dat/*.lua` level programs)

**Status: proposed, nothing implemented.** Table.txt row 8, the one `XL`.
This is the end-game of level work: the Big Room, the Gnomish Mines and
their town, Sokoban, Medusa, the Castle, Gehennom, the Quest. It is a
*wave*, not a slice — but it is also the most *parallelisable* piece in
the queue, because the level programs are independent of each other and
most of the machinery is a handful of well-separated systems.

**Goal, staged.** A first delivery is *not* "all special levels". It is:

1. the `des` API (the 34 functions of `sp_lev.c`'s `lspo_*` table) as
   `core/des.py`, front-end agnostic;
2. the selection algebra (`nhlsel.c` + `selvar.c`) as
   `core/selection.py`;
3. the map-fragment reader + the map-character legend as
   `core/mapfrag.py`;
4. the loader's post passes (wallification, flips, solidify, link
   doors→rooms, boundary symbols, way-out) as `core/splev.py`;
5. **one real level program ported by hand and playable: `bigrm-1`**
   (13 variants are the same shape, so the 13 are one session after
   that);
6. then the level programs in value order (§6), each a session of its
   own.

**Ground truth:** `../NetHack` through `nethack_index`:
`INDEX.md` rows for `src/sp_lev.c` (6,514 L, 53k tokens, 144 fn — 20 %
of a context window, never read whole), `src/nhlsel.c` (1,051 L, 34 fn),
`src/selvar.c` (812 L, 26 fn), `src/nhlua.c` (3,094 L, 98 fn — the
`nh`/`u`/`obj` tables and the sandbox), `src/nhlobj.c` (685 L),
`src/mkmaze.c` (2,110 L: `wallification` + the maze walker),
`src/mkmap.c` (488 L: the mines filler, `remove_rooms`), `src/dungeon.c`
(3,745 L, 112 fn: the topology the loader asks "which file for this
level?"), plus `include/sp_lev.h` (the `sp_coder` state and the
parameter structs) and the `dat/*.lua` corpus.

---

## 1. The four layers (and why each is a different kind of work)

The C file is 6,514 lines because four unrelated things live in it.

| layer | C | size | kind of work |
|---|---|---|---|
| **L1 the coder + post passes** | `sp_level_coder_init`, `splev_initlev`, `load_special` (6445-…), `create_des_coder`, `map_cleanup` (328), `solidify_map` (315), `flip_level`/`flip_level_rnd` (253/967), `remove_boundary_syms` (1016), `link_doors_rooms` (1122), `ensure_way_out`/`generate_way_out_method` (1705/1693), `fixup_special` (**mkmaze.c 570**), `premap_detect` (detect.c 2134), `count_level_features` (mklev) | ~1,200 L | **port it once**, straight, testable without any Lua |
| **L2 the `des` API** | the 34 `lspo_*` functions + their table readers (`get_table_monclass`, `find_montype`, `get_table_objtype`, `get_table_roomtype_opt`, `get_table_traptype_opt`, `get_table_region`, `get_coord`, …) | ~2,500 L | mechanical: each is "parse a table, call a builder". The *builders* (`create_room`, `create_monster`, `create_object`, `create_altar`, `create_corridor`, `create_door`, `create_trap`, `light_region`, `wallify_map`) are the real content |
| **L3 the selection algebra** | `selvar.c` (26 fn) + `nhlsel.c` (34 fn: the Lua wrappers) | ~1,900 L | pure data structure over a point set; **the single best-value sub-port** — no map mutation, no Lua, unit-testable |
| **L4 the map grammar** | `mapfrag_fromstr`/`mapfrag_match`/`get_location`/`set_ok_location_func`, `splev_chr2typ` (**nhlua.c 375-392**), `char2typ[]` (nhlua.c 337-373) | ~400 L | 34-row legend table + a centred fragment match; small |

Plus the data: **131 `.lua` files in `dat/`**, of which 5 are not level
programs (`dungeon.lua` topology, `quest.lua` text, `nhlib.lua`,
`nhcore.lua`, `themerms.lua`), i.e. ~126 level programs.

The full `des` surface (the reference list — this is the API contract
the port must meet):

`des.message`, `monster`, `object`, `level_flags`, `level_init`,
`engraving`, `mineralize`, `door`, `stair`, `ladder`, `grave`, `altar`,
`map`, `feature`, `terrain`, `replace_terrain`, `room`, `corridor`,
`random_corridors`, `gold`, `trap`, `mazewalk`, `drawbridge`, `region`,
`levregion`, `exclusion`, `wallify`, `wall_property`, `non_diggable`,
`non_passwall`, `teleport_region`, `reset_level`, `finalize_level`,
`gas_cloud` (**34**; `branch`/`portal` are `/* TODO */` in C too).

The parameter sets are enumerated in `include/sp_lev.h` — use it as the
spec rather than reverse-engineering each call site:

| call | fields (sp_lev.h) |
|---|---|
| `des.monster` | `name, appear_as, sp_amask, coord, class, appear, peaceful, asleep, female, invis, cancelled, revived, avenge, fleeing, blinded, paralyzed, stunned, confused, waiting, m_lev_adj, seentraps, has_invent, mm_flags` |
| `des.object` | `name, corpsenm, spe, coord, class, containment, curse_state, quan, buried, lit, eroded, locked, trapped, tknown, recharged, invis, greased, broken, achievement` |
| `des.altar` | `coord, sp_amask, shrine` |
| `des.room` | `name, parent, x, y, w, h, xalign, yalign, rtype, chance, rlit, needfill, joined` |
| `des.region` | `x1,y1,x2,y2, rtype, rlit, rirreg` (+ `filled`, `joined`) |
| `des.corridor` | `src{room,wall,door}, dest{room,wall,door}` |
| `des.level_init` | `init_style` ∈ {solidfill, mazegrid, maze, mines, rogue, swamp}, `fg, bg, filling, smoothed, joined, lit, walled, icedpools, corrwid, wallthick, rm_deadends` |
| `des.level_flags` | `noteleport, hardfloor, nommap, shortsighted, arboreal, mazelevel, shroud, graveyard, icedpools, corrmaze, premapped, solidify, sokoban, inaccessibles, noflipx, noflipy, noflip, temperate/hot/cold, nomongen, nodeathdrops, noautosearch, fumaroles` |

---

## 2. The hard decision: what executes a `.lua` file?

This is the one architectural fork in the plan, and it must be decided
*before* the des API is written, because the API's Python signature
depends on it. The corpus is not declarative: it has closures
(`hellfill.lua`, `themerms.lua`, `knox.lua`, `bigrm-11.lua`), `for`
loops bounded by `math.random`, `if percent(...)`, table literals,
method calls on selections (`place:rndcoord(1)`), `&`/`|` operators on
selections, `local` variables, string concatenation, and the
`and/or` ternary idiom.

| option | what it costs | fidelity | dependency | verdict |
|---|---|---|---|---|
| **A. Runtime Lua** (`lupa`), with `des`/`selection`/`nh` implemented in Python and handed to the interpreter | ~2-3 sessions for the front end; zero per-file work | **exact** — the real files run | a C extension (LuaJIT/Lua via CFFI); contradicts `INDEX.md`'s standing convention "Lua is replaced by Python" | the best *short-term* unblock |
| **B. A Lua→Python transpiler** (lexer + Pratt parser + emitter) | 6-10 sessions + a `LuaTable` shim (`1`-based arrays, `#`, `..`, `and/or` returning values, multiple returns) | high, with review | none — the output is Python in the repo | the honest long-term answer |
| **C. Pre-bake to a recorded trace** (run the real Lua once, replay the `des.*` calls) | 1 session | **loses the variety** — a `for i = 1, math.random(5,15)` loop is frozen at its recorded count | none at runtime, `lupa` at conversion time | not recommended |
| **D. Hand-port each level program to Python** against the des API | ~0.5-1 file per session | exact by construction (the port *is* the source, diffable) | none | **recommended as the policy** |

**Recommendation: D as the policy, A as an optional accelerator.**
The reasoning:

1. The expensive part (L1-L4, ~6,000 C lines) is *identical* in all four
   options. It must be ported either way. So the front end is not where
   the XL comes from — the *files* are the long tail, and they are
   independent.
2. D keeps the project's conventions intact (pure Python, provenance in
   the docstring, one reviewed module per level) and each file is a
   closed, testable session. A hand-ported `bigrm-1.py` is 40 readable
   lines.
3. B is worth doing only when the long tail becomes the bottleneck
   (i.e. after the ~30 interesting levels are in). It can then be added
   *behind the same interface* and used to convert the remaining ~90.
4. A is the pragmatic escape hatch if a reviewer wants "all 126 levels
   working this month"; it is one module swap, because of §3.1.

### 3.1 The front end is an interface, not a dependency

```
core/levels/__init__.py     # LEVELS: Dict[str, LevelProgram]
core/levels/bigrm1.py       # def build(des: "Des") -> None: ...     (option D)
core/levels/lua.py          # def run(path, des): ...               (option A, later)
```

`Des` is the only thing a level program may touch. Every `des` method
takes plain Python values (ints, strings, lists, dicts) — *never* a Lua
table — so the L2 layer is written once and a future `lua.py` only
converts `lua.Table` → `dict` at the boundary. The prototype of that
boundary already exists in C: `get_table_*` is exactly this conversion,
so the Python signature of `des.monster(**kwargs)` mirrors
`struct monster` in `sp_lev.h` and the conversion layer is 100 lines.

---

## 4. Model prerequisites (what `types.py` must grow)

| addition | C | why |
|---|---|---|
| `TerrainType.MATCH_WALL` (38) and the `x*` feedback types (`xFLOOR`…`xSEA`, 39-46), `MAX_TYPE` (37) | rm.h / sp_lev.h | `des.map`'s `w` char means "any wall"; `x` means "transparent"; the boundary char `B` is a hack the loader removes again |
| `Tile.wall_info` (the 5-bit flags nibble: `W_NONDIGGABLE`, `W_NONPASSWALL`, `W_NOSPLATMON`) | rm.h | `des.non_diggable`, `des.non_passwall`, `des.wall_property`, and `solidify_map` |
| `Tile.altarmask` | rm.h | `des.altar`, temples (PLAN-SPECIAL-ROOMS.md) |
| `Tile.engr` (or a level-wide `Map.engravings` list) | engrave.c | `des.engraving`, gravestones, the shop sign |
| `Tile.flags.ladder` already exists as `stair_dir`; add `LADDER` as its own terrain use | rm.h | `des.ladder` |
| `LevelFlags` completion: `temperature`, `rndmongen`, `deathdrops`, `sokoban_rules`, `hardfloor`, `nommap`, `shortsighted`, `hero_memory`, `fumaroles`, `noautosearch`, `icedpools` | decl.h | `des.level_flags` |
| `Room.needfill`, `Room.resident`, `Room.nsubrooms` (exists) + `Room.parent` | mkroom.h | `des.room({parent=…})`, `filled=`, the shop's resident |
| `Map.exclusions: List[Tuple[int,int,int,int]]` | sp_lev.c `create_exclusion` | `des.exclusion` — consulted by `makemon`'s position search |
| `Map.lregions: List[LevRegion]` | sp_lev.c | `des.levregion` / `des.teleport_region`; consumed by `fixup_special` |
| `Map.coder` (the `sp_coder` state) or a `LevelCoder` value threaded through generation | sp_lev.h | `croom`, `room_stack`, `failed_room[]`, `n_subroom`, `lvl_is_joined`, `premapped`, `solidify`, `check_inaccessibles`, `allow_flips`, plus `xstart/ystart/xsize/ysize` for relative coordinates |
| **an 80×21 `Map`** (COLNO/ROWNO) and the console viewport | table item 5 | **hard prerequisite**: `MAP_X_LIM` 76 / `MAP_Y_LIM` 21, and every non-trivial level program is a 60-76 column map |

---

## 5. Phases

Ordered so that each phase is independently mergeable and the first
playable level comes as early as possible.

### Phase 0 — the prerequisites that are other items (S/M; do them first)

| prerequisite | table item | why sp_lev needs it |
|---|---|---|
| an 80×21 level + a hero-centred console window | 5 (S-M) | the maps are 76×21 |
| `set_levltyp` + `set_levltyp_lit` (mkmaze.c 77/125) | 2 (S) | `des.terrain`, `des.feature`, `des.replace_terrain` all funnel through it |
| `wallification` / `wall_cleanup` / `fix_wall_spines` (mkmaze.c 198/229/290) | 6 (S) | the loader's last mandatory pass |
| lighting (`light.c`, `Tile.waslit`, light sources) | 7 (M) | `des.region(..., "lit")` and `premapped` are otherwise invisible |
| `make_engr_at` / `del_engr_at` | — | `des.engraving`, `make_grave` |
| the full trap table (22 `TRAPNUM` types + `traptype_rnd`/`traptype_roguelvl`) | — | `des.trap` by trap *name* ("hole", "rolling boulder", …) |
| `makemon` / `mksobj` / `mkgold` / `mkcorpstat` | 1 (L) | `des.monster`/`des.object`/`des.gold` |
| special rooms (`fill_special_room`, `fill_zoo`, shops) | 4 (M→L) | `des.room({type="zoo"})`, `{type="shop"}` |
| `mkmap.remove_rooms`/`remove_room` (mkmap.c 166/180) | — | `des.map` + `remove_boundary_syms` (the last `mkmap` STUB) |

This is the "L/XL items depend on the small ones" fact in its clearest
form: **five of the ten prerequisites are the S/M items further down
table.txt**, and they are cheap. Land them first; they are the reason
the L plan can start at all.

### Phase 1 — `core/selection.py` (1-2 sessions, no dependencies at all)

`selvar.c` in full + the `nhlsel.c` wrappers folded into the same
functions (the Python API is the Lua one).

- `Selection`: bounds + a row-bitmask (C: `UCHAR_PTR` bitmap, one bit
  per square), `setpoint`, `getpoint`, `not`, `and`, `or`, `xor`,
  `sub`, `intersect` (the `&` operator), `union` (`|`), `clone`,
  `numpoints`, `getbounds`, `recalc_bounds`, `is_irregular`.
- the shape constructors: `area`, `line`, `rect`, `fillrect`, `randline`
  (the drunkard's walk), `ellipse`/`circle`, `gradient` (radial/square),
  `grow` (the dilation), `filter_percent`, `filter_mapchar`, `match`
  (map fragment), `floodfill` (with the pluggable
  `set_floodfillchk_match_under` / `_accessible` predicates),
  `rndcoord`, `iterate`, `from_mkroom`, `force_newsyms`.
- **All coordinates are relative to the coder's `xstart/ystart` when a
  region is being described** (C: `cvt_to_abscoord`/`cvt_to_relcoord`);
  make that an explicit `frame` argument, not a global.
- Tests: set algebra against hand-built bitmaps; `line`/`rect` extents;
  `floodfill` on a small map; `rndcoord` determinism under `SeqRng`;
  `grow` idempotence at the plateau.

**Exit:** the 26 `selvar.c` functions exist, tested, with no map
mutation and no `des` dependency.

### Phase 2 — `core/mapfrag.py` (1 session)

- `char2typ[]` as a 34-row table (nhlua.c 337-373) and its inverse
  `typ2chr`; `splev_chr2typ` / `check_mapchr`.
- `MapFragment` (wid/hei/rows), `mapfrag_fromstr` (lines, trailing
  newline, the "right ragged edge is stone" rule), `mapfrag_canmatch`
  (odd width *and* height), `mapfrag_get`, `mapfrag_match` against a
  `Map` at an anchor, `mapfrag_error` (the exact C error strings).
- `get_location` / `set_ok_location_func` / `is_ok_location` /
  `pm_good_location` (the `DRY`/`WET`/`HOT`/`SOLID`/`ANY_LOC`/`SPACELOC`
  flags), `get_room_loc`, `get_free_room_loc`, `get_unpacked_coord`
  (`SP_COORD_PACK`/`SP_COORD_IS_RANDOM`).
- Tests: every character round-trips through the legend; a fragment
  with an even dimension is rejected with C's message; matching `w`
  against each of the twelve wall types.

### Phase 3 — `core/des.py` skeleton + the "no rooms" API (2-3 sessions)

`Des` (aliased `LevelCoder`) with the coder state of §4 and these
methods: `level_init` (`splev_initlev` → `lvlfill_solid`/`_maze_grid`/
`_swamp`, `create_maze`, `makeroguerooms`, `mkmap(linit)`),
`level_flags`, `message` (→ a `MessageEvent` note for the level log),
`reset_level`, `finalize_level`, `terrain`, `replace_terrain`,
`feature`, `door` (`rnddoor`), `stair`, `ladder`, `grave`, `altar`,
`trap` (`rndtrap`), `gold`, `engraving`, `mineralize`,
`non_diggable`, `non_passwall`, `wall_property`, `wallify`,
`teleport_region`/`levregion`, `exclusion`, `map`.

`mkmap` must grow the `linit` parameter set (corrwid, wallthick,
rm_deadends, icedpools, smoothed/joined/lit/walled) — today pyhack's
`mkmap()` has three of them.

**Exit:** `bigrm-1`'s *substance* works without rooms:
`level_init({style="solidfill", fg=" "})` + `des.map(...)` +
`des.region(area, "lit")` + `des.stair` + `des.non_diggable` +
`des.terrain(selection.line(...))`.

### Phase 4 — rooms, corridors, regions with type (2 sessions)

`room` (`build_room`, `update_croom`, `spo_endroom`, the
`MAX_NESTED_ROOMS` stack + `failed_room[]`), `random_corridors`
(`create_corridor`, `dig_corridor` — the ported `mklev.dig_corridor`),
`region` with `type`/`filled`/`irregular`/`joined` (→ `mkroom`'s
`do_mkroom` + `Room.needfill`), `add_doors_to_room`, and
`selection.room()` (`selection_from_mkroom`).

**Exit:** `minetn-1`'s room skeleton (a walled town with shop doors)
builds, albeit empty.

### Phase 5 — monsters and objects (2 sessions; needs PLAN-MAKEMON/MKOBJ)

`des.monster` / `des.object` as the **single writer of the
`struct monster` / `struct object` parameter tables** (§1), including
`appear_as` (`set_mimic_sym`'s cousin — a *deferred* field, stored and
ignored), `containment` (recursive `des.object` inside `des.object`,
`MAX_CONTAINMENT = 10`), `has_invent = CUSTOM_INVENT`,
`m_lev_adj` (`makemon` + `grow_up`), `achievement` (ignored).

**Exit:** the Big Room is fully populated; a two-deep container works.

### Phase 6 — the post passes (2 sessions)

`core/splev.py`: `load_special(name)` in C's exact order —

```
create_des_coder → run the program → link_doors_rooms →
remove_boundary_syms → ensure_way_out (if check_inaccessibles) →
map_cleanup → wallification(1,0,COLNO-1,ROWNO-1) (unless corrmaze) →
flip_level_rnd(allow_flips, FALSE) → count_level_features →
solidify_map (if solidify) → fixup_special → premap_detect (if premapped)
```

with `generate_way_out_method`/`ensure_way_out` (the "a sealed region
gets a hole/teleporter/secret door" search) and `flip_level`'s
"flip the terrain, the doors, the drawbridges, the levregions, the
vault guard" bookkeeping.

**Exit:** a loaded level satisfies the invariants of §7 (reachable,
stairs placed, no orphan levregion).

### Phase 7 — the level programs, in value order (the long tail, ~1 per session)

See §6.

### Phase 8 — the dungeon topology (5-8 sessions; can start in parallel)

`dat/dungeon.lua` → `core/dungeon_data.py` (`dungeons[]` with
`base`/`range`/`branches`/`levels`/`flags`/`lvlfill`), and the
`dungeon.c` subset: `init_dungeons`, `depth()`, `level_difficulty()`,
`find_level`, `Is_special`, `Is_branchlev`, `In_sokoban`, `In_hell`,
`In_quest`, `In_endgame`, `builds_up`, `place_branch`, `next_level`/
`prev_level`, plus the branch-stair placement in the `mklev` flow.
This is what turns `World.lev` (a scalar) into `u.uz` (dungeon +
dlevel), and it is the prerequisite for "the third Sokoban level runs
`soko3-1.lua`" and for branch stairs/portals to mean anything.

**Until phase 8 lands, phase 7 uses a stopgap**: a
`level_plan: Dict[int, str]` on the `World` mapping a dlevel to a level
program name, so the Big Room and the Mines can be *reached* without
the full topology. Say so in the docstring; it is a scaffold, not a
design.

### Phase 9 — the fillers and mazes (2-3 sessions)

`minefill.lua` / `hellfill.lua` (the per-dungeon fillers),
`LVLINIT_MAZE` → `create_maze`/`walkfrom`/`mazexy` (mkmaze.c 1316),
`corrmaze`, the `mazewalk` API, and `setup_waterlevel` (only if the
Plane of Water is ever attempted — it is not, in this plan).

### Phase 10 — Sokoban, Gehennom, the Quest, the Planes (**not in this wave**)

Named here so nobody starts them by accident. They need boulder
pushing (`hack.c`), `Sokoban` rules and the "you moved a boulder" hook;
demon princes and lairs; the quest artefacts and leaders; the endgame
planes with their own level flags and Amulet mechanics.

---

## 6. The level-program queue (value order)

| # | file(s) | why now | needs |
|---|---|---|---|
| 1 | `bigrm-1` | the smallest complete level program, no rooms, no monsters with inventories; teaches `des.map`, `level_init`, `region`, `terrain`, `stair`, `non_diggable` | phases 1-3 |
| 2 | `bigrm-2 … bigrm-13` | same shape, 12 free variations: `selection.match`, `fillrect`, `randline`, `replace_terrain`, currency of the selection algebra | 1 |
| 3 | `tut-1`, `tut-2` | tiny, and they exercise `des.message`/`des.engraving` | 1 |
| 4 | `oracle` | `des.levregion`, `des.teleport_region`, special rooms (DELPHI), `des.door` | phase 4 |
| 5 | `minetn-1 … minetn-7` | the town: `des.room` + shops + `fire traps`/`iron bars` + `selection.floodfill`; the real test of `fill_special_room` | 4, 7 (topology or the stopgap), shops |
| 6 | `minend-1 … minend-3` | the mines' end, `des.map` + lava + traps | 5 |
| 7 | `medusa-1 … medusa-4` | water/moat terrain, statues, `des.map` with `}` | 5 |
| 8 | `castle` | the drawbridge + portcullis (`des.drawbridge`), the wand of wishing, `des.levregion` | 6 |
| 9 | `knox` | the vault portal, `des.region({type="vault"})` | 6, 8 |
| 10 | `soko1-1 … soko4-2` | boulders, holes, `des.exclusion`, `premapped`; **generation ≠ play** until boulder pushing exists | 5, 6, `hack.c` |
| 11 | `valley`, `sanctum`, `juiblex`, `orcus`, `asmodeus`, `baalz`, `wizard1-3`, `fakewiz1-2`, `tower1-3` | Gehennom: mazes, demon lairs, the invocation | 9, 10 |
| 12 | `*-strt/-loca/-fila/-filb/-goal` (13 roles × 5) | the Quest; role data + quest text (`quest.lua`, already converted to `dat/quest_data.py` upstream) | everything above |
| 13 | `air`, `earth`, `fire`, `water`, `astral` | the Planes — **out of scope** (they need `setup_waterlevel`, regions, the endgame) | — |

---

## 7. Testing strategy (this is where an XL plan earns its keep)

1. **Layer tests, no levels involved.** Selection algebra, map-fragment
   legend, `des.terrain`/`replace_terrain` on a 20×10 hand-built map,
   `rnddoor`/`rndtrap` tables, the parameter-table parsers (one test per
   field of `sp_lev.h`'s structs).
2. **Per-level invariants** (the pattern `test_mklev.py` already uses):
   every `des.stair("up"/"down")` present, every room reachable 8-way,
   every door between two rooms, no monster on a wall/closed door, no
   object buried in stone, the level's `LevelFlags` as the program
   asked, the `lit` regions match the program's `des.region` calls.
3. **Golden maps.** A loaded special level is deterministic under a
   seeded rng; store its rendered rows in `tests/golden/levels/*.txt`
   and diff. This is the cheapest defence against "a refactor changed
   the draw order" and it doubles as documentation of what the level
   looks like. Generate them once per level program, review by eye, then
   pin.
4. **The API-coverage test.** A test that greps every `dat/*.lua` for
   `des\.(\w+)` and `selection\.(\w+)` and asserts each name exists on
   the Python `Des`/`Selection`, and that no `des`/`selection` name is
   *missing a caller-only* feature. It runs against the corpus, so it
   cannot rot — and it fails the day someone ports a level that uses
   `des.gas_cloud` before `region.c` exists.
5. **Determinism.** `flip_level_rnd` draws from the level rng; a level
   with `allow_flips` on produces four different maps from four seeds.
   Pin the *invariants* per seed, not one map. And keep the demo
   generator's `new_world` draw count at zero (the standing rule).

---

## 8. Deliberate divergences (planned, not accidental)

1. **No Lua at first** (§2): level programs are Python modules under
   `core/levels/`, one per file, citing `dat/<name>.lua` and the span of
   the `des` calls they use.
2. **`des.gas_cloud` deferred** until `src/region.c` exists (regions are
   a whole system: TTL, enter/leave callbacks, display). The method
   exists and raises `NotImplementedError` naming the C.
3. **`premapped` becomes "remember the map"**; the C `premap_detect`
   also pre-maps traps/objects for Sokoban. pyhack's memory model is
   `Tile.lit` + the vision arrays today; the full `seenv` glyph memory
   is table item 7's work.
4. **No `bones`** (`src/bones.c`), no `themerooms` (`themerms.lua`,
   33 KB of themed-room closures — a separate wave), no `tut-1`'s
   tutorial callbacks (`nhcore.lua`), no Lua sandbox.
5. **Flip bookkeeping is limited to terrain + doors + levregions** in
   the first pass; the room rectangles are re-derived from the flipped
   tiles (or `allow_flips` is left off for levels with rooms, with a
   note).
6. **`ensure_way_out` gets a simpler algorithm** than C's
   `generate_way_out_method` (which tries dig/teleport/secret-door in a
   fixed order): a single "find the nearest unreachable region, punch a
   corridor or a secret door to it" pass that logs the C provenance.
   This is the one place the port may legitimately differ in *output*;
   pin the invariant (everything reachable), not the method.

---

## 9. Traps

- **`fixup_special` is in `mkmaze.c`, not `sp_lev.c`** (line 570). So is
  `wallification`. Two sessions will look in the wrong file otherwise.
- **`splev_chr2typ`/`char2typ[]` are in `nhlua.c`** (337-392), not
  `sp_lev.c`, and `check_mapchr` is `nhlua.c` 387. The legend is the
  most-referenced table in the whole loader; put it in `mapfrag.py` with
  the C line range in the docstring.
- **`PROGRESS_SESSION_32.md` §5's "Map Grammar" table is wrong**: it
  labels `S` as `SDOOR` (right) but `H` as `SCORR` (right) and omits
  `B` (boundary) / `w` (match-wall) / `x` (transparent) — and it claims
  `des.map(char, x, y)`, which is not the API (the API is a
  multi-line string). Use `nhlua.c` 337-373.
- **Coordinates are room-relative inside a `des.room(...)` block.**
  `cvt_to_abscoord` (sp_lev.c 4782) adds the *current room's* `lx/ly`
  while a room is open, and `xstart/ystart` (which are 0 outside the
  loader, per the C comment) at the top level. So
  `des.stair("down", 1, 1)` in `soko1-1.lua` is absolute (no room open)
  while the same call inside `des.room({x=10,y=5,…})` lands at
  (11, 6). Getting this wrong shifts a whole level and looks like
  "rooms are in the wrong place". Model it as an explicit `frame` on
  the coder (the open room), never as an ambient variable.
- **`mapfrag_canmatch` requires odd width AND height.** A hand-typed
  map that violates it fails at run time with C's message; the Python
  reader must reject it at *load* time (a test per corpus file).
- **The Big Room is `mazelevel` but not a maze**; `is_maze_lev` changes
  `topologize`, the stair search and `room_at`. Do not "fix" it.
- **`fill_special_room` is called for every room at the end of the
  level**, including on special levels; a level program that stocks its
  own zoo *and* sets `needfill` gets it stocked twice.
- **`load_special` leaves `gc.coder` set** in C (a global). In pyhack
  the coder must be a value on the `Map`/`World` or passed through, or
  two levels in a row (a lazy level 2 generated while the hero stands
  on level 1) will mix coders — exactly the class of bug
  PLAN-MKLEV.md §2.3 was written to prevent.
- **80×21 or nothing.** Do not start phase 3 before table item 5 lands;
  `des.map` on a 40×20 grid silently truncates 76-column maps.

---

## 10. What this unblocks / what blocks it

| blocked by (must land first) | item |
|---|---|
| 80×21 map + console viewport | 5 |
| `set_levltyp` | 2 |
| `wallification` | 6 |
| lighting | 7 |
| `makemon` + `mksobj`/`mkgold` | 1 (PLAN-MAKEMON.md / PLAN-MKOBJ.md) |
| special rooms + shops | 4 (PLAN-SPECIAL-ROOMS.md) |
| `remove_rooms` (currently a `mkmap` STUB) | — |
| the full trap table, `make_engr_at` | — |

| unblocked when it lands | becomes |
|---|---|
| the Big Room, the Mines, Medusa, the Castle, Sokoban *generation* | a level generator with level types |
| `Is_special`/branch stairs/portals (phase 8) | a real dungeon, not a ladder of N levels |
| `des.room({type="zoo"})`, `des.altar` | the special-room systems get a second caller |
| `themerms.lua` | themed rooms (its own wave) |
| the Quest, Gehennom, the Planes | out of scope here |

---

## 11. Definition of done (first delivery, not the whole row)

- [ ] `core/selection.py`: the 26 `selvar` operations + the `nhlsel`
      constructors, fully tested, no map or Lua dependency
- [ ] `core/mapfrag.py`: the 34-character legend + fragment matching +
      `get_location`, tested against the corpus
- [ ] `core/des.py`: the 34 `des` methods, each citing its
      `lspo_*` span; the parameter tables of `sp_lev.h` implemented
      field-complete (or field-stored-and-ignored with a note)
- [ ] `core/splev.py`: `load_special` in C's post-pass order, with
      `wallification`, `flip_level_rnd`, `solidify_map`,
      `link_doors_rooms`, `remove_boundary_syms`, `ensure_way_out`
- [ ] `core/levels/bigrm1.py` … `bigrm13.py`, playable, with golden maps
- [ ] the API-coverage test green over all 131 `dat/*.lua`
- [ ] an 80×21 generated level renders in the console with a viewport
- [ ] `CHANGES.md`: a `## Wave 6: special levels` section naming what is
      *not* done (Sokoban play, Gehennom, the Quest, the Planes)
