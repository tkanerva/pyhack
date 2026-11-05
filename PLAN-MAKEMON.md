# Plan: Wave 4a — the monster genesis layer (`makemon`)

**Status: phases A (as a depth band), B, C and D landed; E is the
mechanism only; F and G are partly open.** Written after Wave 3 landed
(PLAN-MKLEV.md: rooms + corridors + doors, 521 tests green, mypy clean).
Landed as `core/makemon.py` + `core/place.py` (see CHANGES.md "Wave
4a/4b"): the funnel, the selection half (uncommon / rndmonst_adj /
MongenOrder / gen_ok / mkclass), the strength half (adj_lev / newmonhp /
mbirth_limit / MonState.propagate), the mood half (peace_minded /
set_malign), `mongets` / `mkmonmoney`, and `fill_ordinary_room()` now
spawns through it.  What is still open, in this plan's terms: **A** is a
76-row depth band, not the full 383 (the rows are assigned by C index,
so the converter pass in §4.5 renumbers nothing); **E** has the
inventory *mechanism* but not the `m_initweap` / `m_initinv` species
tables; **F** (groups, grow_up, clone_mon) is untouched and the
generator passes MM_NOGRP so the flag is honoured rather than faked;
**G** retired the demo spawn and added the object half of
fill_ordinary_room (gold / statue / final object), while the trap-type
table, `mktrap_victim` and the special-room fillers are still STUBs.
This is table.txt row 1, the `makemon` half; the object half is
PLAN-MKOBJ.md. Row 1 is the highest-leverage port left: it is what
turns the remaining level-generation STUBs from "raise
`NotImplementedError`" into a few lines each.

*Run status:* the wave's tests were landed while the local pytest was
crashing on startup; the first real run (1140 tests) is green and is
recorded in CHANGES.md ("Verified when the test runner came back").
It found two `makemon`-side bugs: the genesis runs *before* the hero
exists (fixed with `World.hero_or_none` / `World.hero_ulevel`), and
`goodpos()` has to return -- as C does -- on the water and lava
branches, and to apply the closed-door half of C's `accessible()`.

**Goal:** `makemon()` — the port of `src/makemon.c` — so that a
generated level is populated by NetHack's own monster distribution
instead of the three hand-tuned demo kinds, and so that the special
rooms of PLAN-SPECIAL-ROOMS.md can ask for "an orc captain", "a queen
bee" or "whatever is appropriate at depth 12" and get one.

**Ground truth:** the NetHack 5.0 C source in `../NetHack`, read through
`nethack_index` (`INDEX.md` row for `src/makemon.c`: 2,614 lines,
25k tokens, 42 functions; `symbols/makemon.json` for the spans;
`PROGRESS.index.md` §10.2 for the prose — a *hypothesis*, its numbers are
drifted, the spans are not). Never read `makemon.c` whole.

---

## 1. What the C code does (reference)

`makemon()` is one function, but it is a funnel: a dozen helpers decide
*which* monster, *where*, *with what*, *how strong*, and *in what mood*.
The port target for each is a function of the same name in
`core/makemon.py` (new module) unless stated otherwise.

| C function (`src/makemon.c` unless noted) | span | what it decides | port target |
|---|---|---|---|
| `makemon(ptr, x, y, mmflags)` | 1146-1510 | the whole funnel | `makemon.makemon` |
| `makemon_rnd_goodpos` | 1075-1137 | a random legal square (50 tries, then a full map scan) | `makemon.rnd_goodpos` |
| `goodpos` (`src/teleport.c`) | 86 | "may a monster of this type stand here?" | `core/place.goodpos` |
| `enexto` / `enexto_gpflags` / `enexto_core` (`src/teleport.c`) | 196 / 206 / 219 | the nearest legal square to a point | `core/place.enexto` |
| `rndmonst` → `rndmonst_adj` | 1651 / 1658-1732 | weighted reservoir sample over `mons[]` by level band | `makemon.rndmonst_adj` |
| `uncommon` | 1592-1603 | the "rare monster" frequency test | `makemon.uncommon` |
| `mk_gen_ok` | 1735-1752 | genocide / geno-mask / placeholder filter | `makemon.gen_ok` |
| `init_mongen_order`, `cmp_init_mongen_order`, `check_mongen_order` | 1806-1828, 1759-1777, 1782-1802 | the per-class, per-difficulty ordering `mkclass` walks | `makemon.MongenOrder` |
| `mkclass` / `mkclass_aligned` | 1872 / 1879-1974 | "a monster of class S_x", optionally aligned, weighted by difficulty | `makemon.mkclass` |
| `adj_lev` | 2015-2046 | a monster's *actual* level on this dungeon level | `makemon.adj_lev` |
| `newmonhp` / `monhp_per_lvl` / `golemhp` | 1011-1054 / 985-1007 / 2232-2261 | hit points and `m_lev` | `makemon.newmonhp` |
| `propagate` + `svm.mvitals[]` | 957-982 | born / died counters, extinction | `mondata.MonState.propagate` |
| `mbirth_limit` / `create_critters` | 1541-1551 / 1555-1590 | the population cap and "n of them" | `makemon.mbirth_limit`, `makemon.create_critters` |
| `peace_minded` / `set_malign` | 2267-2308 / 2320-2366 | peaceful? and the alignment score | `makemon.peace_minded`, `makemon.set_malign` |
| `mongets` / `mkmonmoney` | 2180-2230 / 575-586 | give a monster one object / money | `makemon.mongets`, `makemon.mkmonmoney` |
| `m_initweap` | 160-572 | weapons + armour for armed monsters (the 413-line beast) | `makemon.initweap` (subset) |
| `m_initinv` | 588-833 | class-specific extras (jelly, treasure, wands) | `makemon.initinv` (subset) |
| `m_initthrow` / `m_initgrp` | 147-158 / 78-145 | thrown ammo / group members | `makemon.initthrow`, `makemon.initgrp` |
| `grow_up` | 2050-2178 | a monster that levels up | `makemon.grow_up` |
| `clone_mon` | 836-944 | a duplicate (splitting jellies) | `makemon.clone_mon` |
| `set_mimic_sym` | 2392-2550 | a mimic disguised as something | deferred (needs the display glyphs) |
| `unmakemon` | 1513-1539 | undo a creation (genesis failures) | `makemon.unmakemon` |

Two tables drive all of it and they are *data*, not code:

- `mons[]` — `include/monsters.h`, 383 rows of `MON(...)`
  (`LVL(level, move, ac, mr, align)`, `G_*` geno mask with the
  frequency in the low 3 bits, six `A(ATTK(...))`, `SIZ(weight,
  nutrition, sound, size)`, resistances, `M1/M2/M3`, difficulty,
  colour, name). `dat/data.base` is *not* this table; `makedefs -m`
  compiles `monsters.h`.
- `mclass_maxf[]` + `mongen_order[]` (`init_mongen_order`, built at
  boot from `mons[]`; the per-class max frequency is what
  `mkclass` uses to know a class exists at all).

---

## 2. Where pyhack stands (measured, not asserted)

| piece | state |
|---|---|
| `core/monst.py` + `monst_defs.py` + `monst_data.py` | the three-module C split is in place; `PM_NAMES` holds the **complete** 383-name ordering, `SUBSET_PM` **40 of 383** rows, `MONS[pm] is None` everywhere else |
| `core/mondata.py` | the per-type predicates (60+), `set_mon_data`, and `MonState`/`MonVitals` (C: `svm.mvitals[]`) — but **`MonState` is not on the `World`** |
| `core/worldgen.py` | `demo_monster(kind, …)` — three hand-tuned kinds (goblin / hill orc / bat); `DEMO_MONSTER_KINDS` |
| `core/mklev.py` | `_spawn_monster()` — C `makemon()` in three lines: `rng.rn2(3)` → one of the demo kinds |
| `Monster` (types.py) | `id, name, pos, hp, max_hp, ac, damage, alive, is_hero, lev, mdata, sleeping, stuck, …, inventory` — **no** `mnum`, `m_lev`, `female`, `mpeaceful`, `maligntyp`, `mavenge`, `mcan`, `mstrategy` |
| `World` | **no** monster-vitals state, no id allocator (`ids` are formatted strings like `"monster_2_3"`) |

So the port is **two halves**: (a) the data, (b) the machinery. The data
half is bigger in tokens than the machinery, and it is mechanical.

Cheap fact that shapes the plan: `monst_data.PM_NAMES` already fixes the
numbering, and `MONS` is a sparse list, so **rows can be filled in
incrementally without renumbering anything** — a depth band at a time is
safe. That is what makes "unlock a specific special room early"
possible (see §4.7).

---

## 3. Model changes (all in `core/types.py` / `core/mondata.py`)

| field | C | why |
|---|---|---|
| `Monster.mnum: int` | `mtmp->mnum` | the `mons[]` index — vitals, corpses, statues, genocide all key off it |
| `Monster.m_lev: int` | `mtmp->m_lev` | `adj_lev()` result; drives hp, attack strength, `grow_up` |
| `Monster.female: bool` | `mtmp->female` | genders decide name and corpse stacking |
| `Monster.mpeaceful: bool` | `mtmp->mpeaceful` | temples (priest), shops (keeper), zoo/court monsters, `MM_ANGRY` |
| `Monster.maligntyp: int` | `mtmp->data->maligntyp` adjusted by `set_malign` | peace decisions, `mkclass_aligned`, altar/priest alignment |
| `Monster.mavenge: bool` | `mtmp->mavenge` | a peaceful monster that was attacked |
| `Monster.mcan: bool` | `mtmp->mcan` | cancelled (blocks most special attacks) |
| `Monster.mstrategy: int` | `mtmp->mstrategy` | `STRAT_WAITFORU` / `STRAT_CLOSE` / `STRAT_APPEARMSG` (the `M3_*` flags) |
| `World.mon_state: MonState` | `svm` | the vitals array + born/died counters; the `ObjTables` pattern |
| `World.next_ident: int` + `World.new_id(prefix)` | `next_ident()` | one allocator for monsters/objects/traps (mkobj.c#next_ident 509-527; today ids are hand-formatted and can collide across generators) |

`MonState` needs one more thing than it has: `propagate()` is a method
nowhere yet, and `mvitals[].mvflags` must be readable by `mkclass`
(`G_GONE` filter) and writable by genocide/extinction later.

`Monster.damage` (the demo's `1d<damage>`) stays for the flat-stat demo
monsters, but a monster made by `makemon` uses `mdata`'s attack table —
which is what `core/mhitu.py` already consumes. The two paths must not
both apply; `_spawn_monster` is deleted, not extended.

---

## 4. Design decisions

1. **`makemon()` is a function over `(world, map_, rng)`, returning
   `Optional[Monster]`.** C returns `struct monst *` (or NULL for
   "no monster"), and the callers test it: `fill_zoo` only sets
   `msleeping` when it got one, `mktrap` only places a spider on a web
   it made, `priestini` only fills `EPRI` when the priest exists. A
   `None` return keeps that shape without exceptions. `C None` (i.e.
   no monster) is a *normal* result — a level full of water refuses
   land monsters — so it must not raise.
2. **The flags are an `IntFlag` with the C names and values**
   (`NoMinvent=0x1 … MamMsg=0x20000`, 19 bits, `src/hack.h` 1160-1180).
   `NO_MM_FLAGS = MmFlags(0)`.
3. **Placement lives in a new `core/place.py`, not in `makemon.py`.**
   `goodpos` / `enexto` are `src/teleport.c` and they will be needed by
   teleportation, level change (`mnexto`), level generation and the
   shopkeeper's door guard. `place.goodpos` is the choke point that
   later learns about pools, lava, boulders and scare monsters — one
   place to grow, like `rules.apply_damage` for damage.
4. **`makemon` never draws for the map.** C's draw order is: position
   first (when `x == 0 && y == 0`), then the type, then hp, then
   gender, then inventory. Keep that order exactly; the level's rng
   stream is shared, so a reordering silently reshuffles every later
   draw of the level (the PLAN-MKLEV.md §2.7 rule, one level up).
5. **`mons[]` is completed by a script, checked by `_validate()`.**
   The rows are 8 lines each and utterly regular. The plan is a
   one-off converter (kept in `tools/`, not shipped) that walks
   `include/monsters.h`, expands `MON/LVL/A/ATTK/SIZ/MON_WITH_...` and
   emits `monst_data.py` rows in the existing style; `monst._validate()`
   grows the cross-checks (name ↔ `PM_NAMES`, class contiguity per
   `mongen_order`, `G_FREQ` range 0..7, `SPECIAL_PM` boundary). Do not
   hand-type 383 rows.
6. **The full table lands in one go, not per band.** The "banded"
   alternative is legal (§2) and is the right choice only if a special
   room blocks a release; the default is one complete pass, because a
   half-filled table changes `rndmonst`'s distribution silently and
   makes bugs look like tuning.
7. **Depth comes from `world.lev` behind `rules.level_difficulty()`.**
   C reads `level_difficulty()` (`src/dungeon.c` 2038), which is
   `depth(&u.uz)` with branches, builds-up adjustments and the Amulet
   case. pyhack has a linear dungeon (`World.lev` / `World.max_lev`), so
   the helper is `world.lev` today and becomes the real thing with
   PLAN-SPLEV.md's dungeon topology. Every caller uses the helper, so
   that switch is one edit.
8. **`in_mklev` is explicit.** C's `gi.in_mklev` changes behaviour in
   six places inside `makemon` (no appear message, hide-under for
   spiders/eels, sleep rolls for demons, `mkobj_at` under a spider).
   pyhack passes `in_mklev: bool` down from the generator rather than
   storing a global; the level-change and zap call sites pass False.
9. **Inventory is a two-phase subset.** `m_initweap` is 413 lines of
   "which weapon would this species prefer given skill and depth";
   it is not needed for the first delivery (a monster that fights with
   its natural attacks is already NetHack-shaped for depth 1..10). The
   subset is: (i) `mongets` (give one specific otyp), (ii) a
   depth-appropriate weapon/armour roll for `M2_MERC`/humanoids, (iii)
   `mkmonmoney` for greedy monsters. Everything else names its C in a
   comment and takes no roll (the PLAN-MKLEV draw-order rule).
10. **Groups are behind the flag, not deleted.** `m_initgrp` (soldier
    squads, orc bands, ant swarms) is what makes BARRACKS and ANTHOLE
    look right, but it multiplies the monster count on every level. It
    lands in phase F; until then the generator passes `MM_NOGRP`.

---

## 5. Phases

Each phase is a session, ends green (tests + mypy), and commits its own
`CHANGES.md` paragraph.

### Phase A — the `mons[]` table (data; ~1 session + review)

1. `tools/convert_monsters.py`: `include/monsters.h` → `monst_data.py`
   rows (`_mon(...)`, C order, `#if 0` and `CHARON` excluded exactly as
   `PM_NAMES` did).
2. Extend `monst._validate()`: 383 rows present, name column equals
   `PM_NAMES`, `SUBSET_PM` becomes "all", `mlet` matches the class
   comments, `G_FREQ` in 0..7, every class in `mongen_order` non-empty.
3. `tests/test_monst.py`: a table-driven check of ~20 spot rows against
   `monsters.h` (giant ant, killer bee, soldier ant, goblin, hill orc,
   ogre, troll, vampire, ghost, shopkeeper, aligned cleric, high cleric,
   queen bee, leprechaun, cockatrice, soldier, sergeant, lieutenant,
   captain, gray dragon) — value by value, so a converter bug cannot
   hide behind "383 rows exist".

**Exit:** `len(SUBSET_PM) == 383`, validate clean, spot rows exact.

### Phase B — state, ids, flags (~1 session)

1. `Monster` fields of §3; `World.mon_state`, `World.new_ident`.
2. `MmFlags` IntFlag + `NO_MM_FLAGS` in `core/makemon.py`.
3. `rules.level_difficulty(world)`; sweep `mklev`/`mkroom`/`worldgen`
   call sites that use `depth`/`lev` for the same purpose.
4. Id sweep: every `f"monster_{lev}_{i}"` / `f"trap_{lev}_{i}"` /
   `item_{i}` becomes `world.new_id("mon")` etc. **Test impact:** the
   existing tests that assert on ids must be rewritten to assert on
   positions/contents; this is the one place the wave touches pinned
   tests. Keep the demo's ids *stable* by seeding the counter so
   `test_same_seed_same_game` still passes (`ident` is not part of any
   rendered output; verify before changing).

**Exit:** demo path byte-identical (`test_same_seed_same_game`), new
fields unset-but-defaulted for the demo monsters.

### Phase C — selection: which monster (~1-2 sessions)

1. `uncommon`, `gen_ok`, `mongen_order` + `mclass_maxf`,
   `rndmonst_adj` (weighted reservoir; C's `rn2(total+weight)` draw
   order preserved), `mkclass(class, spc)` / `mkclass_aligned`.
2. `adj_lev`, `monhp_per_lvl`, `golemhp`, `newmonhp`.
3. Tests: distribution invariants (no monster above/below the depth
   band; `G_GENOD` never appears; a class request returns that class or
   `None`), plus a seeded snapshot of "seed N at depth D yields these
   12 monsters" so a future edit that reorders the table is caught.

**Exit:** `rndmonst_adj` and `mkclass` usable from tests alone.

### Phase D — creation: where and with what (~2 sessions)

1. `core/place.py`: `goodpos` (subset: in bounds, `SPACE_POS`, not
   water/lava unless swimmer/flyer/amphibious/breathless, no monster
   if `GP_AVOID_MONPOS`, not the hero), `enexto` (ring search),
   `rnd_goodpos` (50 random tries, then the full scan in C's rotated
   order).
2. `makemon` proper: the mmflags funnel in C's order (position → type
   → genocide → `propagate` → `newmonhp` → gender → sleep → peaceful
   → `set_malign`), including `MM_ADJACENTOK`, `MM_ANGRY`,
   `MM_ASLEEP`, `NO_MINVENT`, `MM_NOCOUNTBIRTH`.
3. `peace_minded`, `set_malign` (needs `maligntyp` and the hero's
   alignment — a `Monster.ualign` field or a `World` constant; C reads
   `u.ualign.type`, pyhack has no alignment yet → add
   `World.hero_align` with `A_NONE` as the demo default).
4. Integration: `mklev.fill_ordinary_room`'s monster branch becomes
   `makemon(None, pos, MM_NOGRP | MM_ASLEEP)`; `_spawn_monster` is
   deleted; the web+giant-spider branch lands (`mktrap`/`maketrap`);
   `mktrap`'s own `PM_GIANT_SPIDER` on a web.
5. Tests: a monster never lands on a wall/closed door/the hero/another
   monster; sleepers are asleep; a water-only level returns `None`
   rather than crashing; `MM_ANGRY` is not peaceful; a genocided type
   is refused; the level stays walkable (the 400-command random-walk
   smoke test of `test_worldgen_generators.py` already asserts this).

**Exit:** `generator="mklev"` levels are populated from the real table,
placed legally, and the demo generator is untouched.

### Phase E — inventory (~1-2 sessions, depends on PLAN-MKOBJ.md C–E)

1. `mongets`, `mkmonmoney`; `Monster.inventory` fed through `mksobj`.
2. `m_initweap` subset: for `M2_MERC`/`AT_WEAP` monsters, a weapon by
   depth + armour by class (the C table is 400 lines of `switch`
   chains; port `oselect`-equivalent as data: `(oclass, otyp,
   probability)` per species-group, with the exotic cases STUBbed and
   commented).
3. `m_initthrow` (ammo with a launcher), `m_initinv` subset (jelly
   treasure, leprechaun gold, nymph items).
4. Rendering: the console must show a monster's weapon/armour nowhere
   yet — assert via inventory contents only.

**Exit:** a BARRACKS squad can carry swords and armour; a leprechaun
carries gold.

### Phase F — growth, groups, vitals (~1 session)

1. `grow_up` (level-up, type promotion by `mnext` adjacent table — the
   `G_NOCORPSE`/class chains), `clone_mon`, `create_critters`,
   `mbirth_limit`.
2. `m_initsgrp` / `m_initlgrp` (`m_initgrp` at 78-145), switched on per
   room type, not globally.
3. `propagate` + extinction: the `mvitals` counters, `G_EXTINCT` when
   the born/died ledger empties a type (C: `mondead`).
4. Tests: a genocided species never respawns; `grow_up` preserves
   `m_id` and location; group sizes match the `G_SGROUP`/`G_LGROUP`
   ranges.

### Phase G — retire the STUBs (the payoff, ~1 session)

Fill in, from PLAN-MKLEV.md §4 and core/mkroom.py's STUB list:

| STUB | becomes |
|---|---|
| `mklev.fill_ordinary_room` monster branch | `makemon(None, …)` (done in D) |
| `mklev.mktrap` type table | `traptype_rnd(depth)` — needs the full `TRAPNUM` table (PLAN-SPLEV.md phase 0) |
| `mklev.mktrap`'s dead adventurer (`mktrap_victim` 1819-…) | `makemon` corpse + cursed gear subset |
| `mkroom.fill_zoo` | PLAN-SPECIAL-ROOMS.md phase 2 |
| `mkroom.courtmon/squadmon/morguemon/antholemon/mkundead/mk_zoo_thronemon` | `mkclass` + `makemon` (same phase) |
| `mkroom.mkswamp` | needs `set_levltyp` (table item 2) + `makemon` |
| the vault (`create_vault`) | PLAN-SPECIAL-ROOMS.md phase 5 |
| `worldgen._spawn_monster` | deleted |

---

## 6. Deliberate divergences (documented, not bugs)

1. **No alignment system yet.** `peace_minded` needs the hero's
   alignment and the monster's; pyhack has neither. `World.hero_align`
   defaults to `A_NONE` (neutral), so `peace_minded` degenerates to
   "peaceful when `M2_PEACEFUL`, hostile when `M2_HOSTILE`". The
   quest/priest/shop alignment consequences wait for their systems.
2. **No `Inhell` / `In_sokoban` / quest / endgame level predicates.**
   The branches that read them keep the temperate-dungeon default and
   say so. (PLAN-SPLEV.md phase 8 owns the real predicates.)
3. **No worm segments** (`MM_NOTAIL` is accepted and ignored; a long
   worm is a single monster), **no mimics** (`set_mimic_sym` needs the
   display glyph), **no `mextra` for pets/steeds/vault guards**
   (`MM_EDOG`/`MM_EGD` accepted and ignored; the priest and
   shopkeeper extras land in PLAN-SPECIAL-ROOMS.md as
   `Monster.epri` / `Monster.eshk`).
4. **`MM_EMIN` (minions)** — accepted and ignored; minion AI is its own
   system (`src/minion.c`).
5. **`m_initweap` is a data-driven subset**, not the 413-line `switch`
   chain: fewer exotic starting kits, same statistics for the common
   species. Named in the docstring.
6. **No appear messages** ("A kobold appears!") until the monster
   message layer exists; `MM_NOMSG` is therefore always effectively on.

---

## 7. Traps (what went wrong elsewhere, and what to check)

- **The sparse table.** `MONS[pm]` is `None` for 343 entries. Every
  loop over `LOW_PM..SPECIAL_PM` must skip `None` (`rndmonst_adj`,
  `init_mongen_order`, `mkclass`) *and* the `assert mdata is not None`
  in `worldgen.demo_monster` must not survive into the general path.
- **`m_lev` vs `mlevel`.** C has `ptr->mlevel` (the table value) and
  `mtmp->m_lev` (the adjusted, per-instance level). Confusing them
  produces monsters that are 5 levels too strong on depth 12. Name the
  Monster field `m_lev` and read `mdata.mlevel` only inside `adj_lev`.
- **The `G_FREQ` bits live inside `geno`.** `ptr->geno & G_FREQ` is the
  frequency (0..7); `0` means "never gen". A converter that copies
  `geno` as an opaque int is fine; code that compares `geno` for
  equality is not.
- **Difficulty is a column, not a formula** (5.0 moved it into the
  table). It is *not* used by `rndmonst_adj` (which uses `mlevel`
  bands) but it *is* used by `monmin/monmax_difficulty` and by
  `mstrength`. Copy it; do not derive it.
- **`40x20` is a small level.** C's `makemon_rnd_goodpos` scans
  `COLNO/ROWNO`; on the demo grid a level with a pool can legitimately
  fail all 50 tries and fall into the scan. Make sure the scan
  terminates and returns `None` — C's "mass drowning on the medusa
  level" comment (makemon.c 1213-1217) is exactly this failure mode.
- **Draw-order regressions look like tuning.** Every phase lands with
  one seeded snapshot test (depth 5, depth 12) so a changed draw count
  is a red test rather than a slightly different level.
- **`SUBSET_PM` is referenced by tests** (`test_monst.py`,
  `test_demo.py`); growing it to 383 will break any test that asserts
  "only the subset exists". Grep before Phase A lands.

---

## 8. What this unblocks / what blocks it

| unblocked by this plan | was |
|---|---|
| `fill_ordinary_room` monsters | demo kit |
| `fill_zoo` / court / barracks / morgue / beehive / anthole | `NotImplementedError` |
| `mktrap`'s spider, `mkeniche`'s corpse, `mktrap_victim` | STUB |
| temple priest, shop keeper (as monsters) | PLAN-SPECIAL-ROOMS.md |
| `des.monster()` in special levels | PLAN-SPLEV.md |
| genocide scroll, `create monster` scroll, extinction | STUBs in `core/scrolls.py` |
| "A monster appears" messages, monster inventories, pets | future |

| this plan needs | from |
|---|---|
| `mksobj` / `mkgold` (Phase E: monster inventory, money) | PLAN-MKOBJ.md C-E |
| the full trap-type table (`mktrap`'s `traptype_rnd`) | PLAN-SPLEV.md phase 0 |
| `set_levltyp` (swamps) | table item 2 (S) |
| `Monster.epri` / `.eshk` extras | PLAN-SPECIAL-ROOMS.md |
| an 80x21 level and the console viewport (only for real NetHack monster counts: 80x21 holds ~27 monsters, 40x20 holds ~4) | table item 5 (S-M) |

**Ordering:** A → B → C → D is strictly linear. E can start in parallel
with PLAN-MKOBJ.md's C. F and G are independent of each other after D.

---

## 9. Definition of done

- [ ] `SUBSET_PM` = all 383 rows; `_validate()` clean; spot rows exact
- [ ] `makemon` / `mkclass` / `rndmonst_adj` / `adj_lev` / `newmonhp`
      ported with their C spans in the docstrings
- [ ] `core/place.py` with `goodpos` + `enexto`, tested for pools,
      lava, walls, doors, monster-on-monster
- [ ] `world.mon_state` (vitals) and `world.new_id` in place
- [ ] `generator="mklev"` levels populated from `mons[]`; the 400-command
      random-walk smoke test green on `mklev` and `cavern`
- [ ] demo generator byte-identical (`test_same_seed_same_game`)
- [ ] the STUB table of §5-G has no `NotImplementedError` left that
      `makemon` alone can retire
- [ ] `CHANGES.md` paragraph + `ARCHITECTURE.md` "Intentional
      simplifications" entry updated (the "same three monster kinds"
      bullet goes away)
