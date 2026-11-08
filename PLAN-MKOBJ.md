# Plan: Wave 4b — the object genesis layer (`mksobj` / `mkobj` / `mkgold`)

**Status: phases A, B, C, D and E landed in substance; F is partly
open, and G's terrain branches (fountain / sink / altar / grave) have
landed with `set_levltyp`.** The second half of table.txt
row 1; the monster half is PLAN-MAKEMON.md. Written after Wave 3
(PLAN-MKLEV.md) landed: 521 tests green, mypy clean.
Landed as `core/mkobj.py` (see CHANGES.md "Wave 4a/4b"): the `Item`
model of phase A (with `container` renamed to `carrier`), `mksobj` /
`mksobj_init` per class, `mkobj` / `rnd_class` against ObjTables.prob,
`mkobj_at` / `mksobj_at` / `place_object`, `mkbox_cnts`,
`add_to_container` / `delete_contents`, `mkgold`, `mkcorpstat`,
`weight` (whole), the BUC lottery, `rndmonnum` and `mkobj_erosions`.
Still open: `splitobj`, the container *merge* rules of phase E,
`mkobj_erosions`' rust / rot / corrode material tests, and the phase-G
residue (the bonus item, the chest `!rn2(nroom*5/2)` and the graffiti,
whose `make_engr_at` needs the engraving system), whose rolls are
deliberately not taken yet.  (The `charges` -> `spe` migration of §4.A
landed with PLAN-INVENT.md phase A: `Item.charges` is deleted and
`spe` is the only counter -- zap / spells / items / the demo kit all
read it.  The terrain branches landed after the last session's crash
point: `set_levltyp` / `find_okay_roompos` / `mkfount` / `mksink` /
`mkaltar` / `mkgrave` are in core.mklev, the `fill_ordinary_room`
rolls are taken in C order, and `Tile.altarmask` + the AM_* /
`align2amask` block sit in core.monst_defs / core.types.)

*Run status:* the wave's tests are written but were landed while the
local pytest was crashing on startup; the first real run (1140 tests)
is green and is recorded in CHANGES.md ("Verified when the test runner
came back"): the object half needed one fix (`mksobj()` registers the
item in `World.items` at creation) and the statue's `spe` is the
caller's `corpstatflags`, as in C.

**Goal:** `mksobj()` — the port of `src/mkobj.c` — so that the level
generator, the special rooms and the special levels can put *real*
objects on the floor: gold, chests with contents, statues, corpses,
royal jelly, the shop stock, the vault hoard. Today every one of those
is a STUB because the only way to make an `Item` is the hand-written
demo kit in `worldgen.py`.

**Ground truth:** `../NetHack` through `nethack_index`
(`INDEX.md` row `src/mkobj.c`: 3,866 lines, 36k tokens, 99 functions;
`symbols/mkobj.json`; `PROGRESS.index.md` §10.4 — prose is a drifted
hypothesis, the spans are not). Never read `mkobj.c` whole.

---

## 1. What the C code does (reference)

| C function (`src/mkobj.c` unless noted) | span | what it does | port target |
|---|---|---|---|
| `mksobj(otyp, init, artif)` | 1179-1259 | the funnel: id, class, `mksobj_init`, then the corpsenm/timer fixups, `weight` | `mkobj.mksobj` |
| `mksobj_init` | 869-1177 | per-class initialisation: quantities, `spe`, blessing, charges, contents | `mkobj.mksobj_init` (split per class, see §5) |
| `mkobj(oclass, artif)` | 270-301 | a random object of a class (or a random class) | `mkobj.mkobj` |
| `mkobj_at` / `mksobj_at` | 227 / 238 | make + `place_object` | `mkobj.mkobj_at`, `mkobj.mksobj_at` |
| `mkbox_cnts` | 304-384 | fill a container (box / chest / sack / ice box) | `mkobj.mkbox_cnts` |
| `mkgold(amount, x, y)` | 2018-2035 | a gold pile (or add to the pile already there) | `mkobj.mkgold` |
| `mkcorpstat` | 2082-2240 | corpse / statue of a monster type (or of the hero) | `mkobj.mkcorpstat` |
| `mk_tt_object` / `mk_named_object` | 2242 / 2268 | corpse/statue at random-or-given spot / a named object | `mkobj.mk_tt_object`, `mkobj.mk_named_object` |
| `set_corpsenm` | 1318-~1380 | corpsenm write with the timer + weight fixups | `mkobj.set_corpsenm` |
| `weight` | 1903-2017 | `owt` from `oc_weight × quan` + contents + corpses | `mkobj.weight` |
| `bless` / `unbless` / `curse` / `uncurse` / `blessorcurse` | 1856-1902 ff. | the BUC lottery | `mkobj.blessorcurse` (+ the four primitives) |
| `next_ident` | 509-~530 | the object id counter | `World.new_ident` (PLAN-MAKEMON.md §3) |
| `splitobj` / `unsplitobj` | 286 / 327 | stack splitting (throwing one dart out of ten) | `mkobj.splitobj` — deferred, see §4.6 |
| `place_object` | 2320-~2380 | put an object on the map (`world.items` + position) | `mkobj.place_object` |
| `rndmonnum` / `rndmonnum_adj` | 241 / 259 | a random monster type (corpse/statue subjects) | `makemon.rndmonst_adj` (PLAN-MAKEMON.md C) |
| `mkobj_erosions` / `may_generate_eroded` | 148 / 135 | "worn-out gear" generation | `mkobj` (phase F) |
| `stone_object_type` / `stone_furniture_type` | 467 / 481 | stone-to-flesh classification | deferred (needs the polymorph system) |

Data that drives it and already exists in pyhack:

- `core/objects.py` / `objects_data.py` — all 480 rows with `prob`,
  `weight`, `cost`, `oc1` (armour AC / hit bonus), `nutrition`,
  `charged`, `magic`, `merge`, `big`, `dir`, `material`, `subtyp`,
  `oclass`; `BASES` (C `svb.bases[]`).
- `core/o_init.py` — `ObjTables` (`prob`, `prob_totals`, `descr`,
  `color`, `material`, `name_known`, `encountered`, `disco`, the
  description shuffle, `oinit()`).
- `core/worn.py` / `core/weapon.py` / `core/hunger.py` /
  `core/scrolls.py` / `core/zap.py` — every consumer of an `Item`'s
  `otyp` / `oclass` / `spe` / `blessed` / `cursed` / `charges`.

Missing data: the three class-frequency tables of `mkobj()` (C:
`mkobjprobs[]`, `hellprobs[]`, `rogueprobs[]`) and `rnd_class()`.

---

## 2. Where pyhack stands: the `Item` model is the real work

`types.Item` today is *demo* data, not `struct obj`:

```python
Item(id, otype, name, charges, blessed, cursed, pos, container, lev,
     wand_type, potion_type, spell_type, scroll_type,
     otyp, oclass, spe, owornmask, greased, dknown, known, oeaten)
```

The gaps that block `mkobj` — every one of them is exercised by a C
function in §1:

| missing | C field | needed by |
|---|---|---|
| `quan: int = 1` | `obj->quan` | gold (a pile is one object), arrows, candles, `splitobj`, `weight` |
| `corpsenm: int = NON_PM` | `obj->corpsenm` | corpses, statues, eggs, figurines, tins |
| `contents: List[str] = []` | `obj->cobj` | every container: chests, ice boxes, sacks, bags of holding, statues with loot, shop stock boxes |
| (rename `container`) | `obj->where` = `OBJ_CONTAINED` + `ocontainer` | **the current `Item.container` means "the id of the monster carrying it"**, which is C's `OBJ_MINVENT`/`OBJ_INVENT`, *not* containment. `mkobj` needs both meanings; they must be two fields: `carrier: Optional[str]` and `contents: List[str]` |
| `owt: int = 0` | `obj->owt` | `weight()`; encumbrance later |
| `oeroded` / `oeroded2` | same | **live defect:** `core/worn.py:erode_obj` reads `item.oeroded` (line 756) and increments it (786/788) unguarded, but `Item` has no such field and PLAN-ARMOR.md §294's "Item gains oeroded/oeroded2" never landed. The tests pass only because `tests/test_worn.py` assigns the attribute by hand (`it.oeroded = 4`); a fire trap on a real worn armour item raises `AttributeError`. Fix this first — it is a one-line change with a test |
| `olocked` / `otrapped` / `broken` | same | chests (`mkbox_cnts`), the trapped-box branch |
| `known`/`dknown` | present | fine |
| `oartifact: int = 0` | same | accepted, always 0 (no artifact system) |
| `age` / `timed` | `obj->age`, `timed` | corpses rotting, eggs hatching, oil burning — **deferred**, but the fields should exist so `mksobj` can accept-and-ignore like C's `start_corpse_timeout` |

Note the *duplication* that used to exist: `Item.charges` (the demo's
charge counter) vs `Item.spe` (C's `spe`).  It is RESOLVED: PLAN-INVENT.md
phase A deleted `charges` and re-pointed the readers (`zap.py` /
`spells.py` / `items.py` / the demo kit) at `spe`, the C field.

---

## 3. Design decisions

1. **`mksobj(world, otyp, init=True, artif=False) -> Item`** — always
   returns an object and *does not* place it. C does the same
   (`mksobj` → `OBJ_FREE`, `place_object` separately), and the callers
   rely on it: `mkbox_cnts` builds items then `add_to_container`s
   them, `fill_zoo` builds the royal coffers gold, then puts it in the
   chest. `mkobj_at` / `mksobj_at` are the "make and place"
   convenience wrappers.
2. **Containment is a list of item ids on the container**, not a
   back-pointer and not an object graph (the pyhack rule: no object
   graphs inside the `World`). `Item.contents: List[str]`; the child
   keeps `pos=None` and `carrier=None`. `add_to_container` /
   `delete_contents` are the only writers, so "a contained item is
   reachable exactly twice" stays an invariant a test can assert.
3. **Carrying stays as it is** (rename `container` → `carrier`), so
   `world.items_at()` / `pickup` / `worn.which_armor` keep working with
   a mechanical rename and no logic change. Do the rename as its own
   commit with a grep-verified zero call-site change.
4. **Ids come from `World.new_ident()`** (PLAN-MAKEMON.md §3). The
   demo's `armor_0`, `scroll_3`, … ids are load-bearing for the pinned
   tests; the allocator therefore takes a prefix, and `worldgen`
   keeps producing the same strings until the demo kit is rebuilt
   (which is *not* part of this wave — see §4.8).
5. **`weight()` is ported whole, not approximated.** It is 90 lines of
   "class → grams", doubles for containers with contents, and it is
   the input to encumbrance and to `costly_alteration`. Formula
   constants (`WT_*`) come from the table.
6. **No `splitobj` in this wave.** Nothing in the target STUBs needs
   to split a stack (throwing and shop stock will, later). `quan`
   alone covers gold piles, arrows and candles. When it lands, it
   must be the only writer of `quan` except `mksobj_init`.
7. **Blessing is one function** (`blessorcurse(item, chance)`), with
   `bless`/`curse`/`unbless`/`uncurse` as primitives — C's split
   exists because the shop code calls the primitives directly; pyhack
   can start with the lottery and add the primitives when the shop
   plan needs them.
8. **The demo floor kit is frozen.** `worldgen.FLOOR_ARMOR/SCROLLS/
   WEAPONS/WANDS/BOOKS/FOODS` keep building `Item`s by hand for the
   `"demo"` generator, byte-identically. Rebuilding them with `mksobj`
   is a *later* cleanup (it would change blessing rolls and therefore
   the pinned tests). The generated (`"mklev"`/`"cavern"`) paths use
   `mkobj`.
9. **`artifact` is accepted and ignored** (`artif: bool`), like
   `MM_EMIN` in PLAN-MAKEMON.md. No `mk_artifact`.
10. **Timers are hooks, not a system.** `mksobj` accepts a corpse and
    sets `corpsenm`; `start_corpse_timeout` / `start_glob_timeout` /
    `item_on_ice` are named in a comment and not called (pyhack has no
    `timeout.c`). This matters: a shop that sells a corpse needs a
    *rotting* corpse eventually, but not for the first delivery.

---

## 4. Phases

### Phase A — the `Item` model (small, do it first, ~1 session)

1. Add `quan`, `corpsenm`, `contents`, `owt`, `oeroded`, `oeroded2`,
   `olocked`, `otrapped`, `broken`, `oartifact`; rename `container` →
   `carrier`.
2. **Fix the erosion defect**: `oeroded`/`oeroded2` as real fields +
   a regression test "a fire trap erodes a worn leather armour" (today
   that path raises `AttributeError`; the test is the proof the fields
   exist).
3. `world.new_ident(prefix)` (shared with PLAN-MAKEMON.md B).
4. Mechanical rename sweep + `charges` → `spe` migration; delete
   `Item.charges`.
5. Tests: `test_objects.py` gains the field/alias checks; the whole
   existing suite must stay green (this phase is refactor-only).

**Exit:** `pytest` green with no logic change; `erode_obj` works on a
plain `Item`.

### Phase B — `mksobj` core (~2 sessions)

In C order, class by class, each with a `Simplifications` note naming
what is skipped:

| sub-phase | class | what it sets | skip (documented) |
|---|---|---|---|
| B1 | WEAPON | `quan` for `is_multigen`, `spe = rne(3)` / `-rne(3)`, blessing, poison | artifacts, `oselect`-style erosion |
| B2 | ARMOR | `spe = rne(3)` (or `-rne(3)` when cursed), `blessorcurse(10)`, the "always cursed" items (fumble boots etc.), `oeroded`/`oerodeproof` from `mkobj_erosions` | artifacts, the Samurai lacquered-splint special case |
| B3 | FOOD | `quan`, corpsenm for eggs/tins/corpses, `oeaten = 0`, oil `age` | timers |
| B4 | POTION / SCROLL / SPBOOK | `blessorcurse(4 / 4 / 17)`, `spestudied = 0` | `SPE_NOVEL` titles |
| B5 | WAND | `spe = rn1(5, 11 if oc_dir == NODIR else 4)` (`WAN_WISHING` = 1, `WAN_STASIS` = `rn1(4,3)`), `blessorcurse(17)`, `recharged = 0` | nothing |
| B6 | RING / AMULET | `blessorcurse(3)`; a charged ring also rolls `spe = rn1(5, 4)`, `recharged = 0` | artifact rings |
| B7 | TOOL / GEM / ROCK | the per-`otyp` switches (candles unlit, lamp `age`, crystal ball, bag of tricks `spe`) | oil `age` behaviour beyond the value |
| B8 | COIN | `quan`, `blessed = cursed = False` | — |

Plus the tail of `mksobj`: the corpsenm/timer switch (corpse → a
random monster type via `rndmonnum`, statue/figure gender `spe`,
`POT_WATER`/`POT_OIL` fields, `LEASH`), and `weight()`.

**Exit:** for every `otyp` in the table, `mksobj(otyp)` returns an
`Item` whose fields are inside the C ranges (a table-driven test over
all 480 rows: no exception, `quan ≥ 1`, `spe` in range, `oclass`
matches `OBJECTS[otyp].oclass`).

### Phase C — `mkobj` + the class-frequency tables (~1 session)

1. `mkobjprobs[]` / `hellprobs[]` / `rogueprobs[]` as data in
   `core/objects_data.py` (or a new `mkobj_data.py`), C order.
2. `mkobj(oclass)`: the `RANDOM_CLASS` roll (`rnd(100)` walk), then
   the within-class roll against `ObjTables.prob` (not
   `OBJECTS[i].prob`: `setgemprobs` adjusts it per level — that is
   why `ObjTables.prob` exists).
3. `rnd_class(low, high)`.
4. Tests: a distribution test per class over 10k draws (±2% against
   the table), and `mkobj` never returns a `None`-named row.

### Phase D — gold and money (~1 session)

1. `mkgold(amount, pos)`: the C amount formula
   (`rnd(30 / max(12 - depth, 2))` × `1 + rnd(level_difficulty() + 2)`),
   the "add to the pile already there" branch, `weight`.
2. `place_object` for coins; `world.items_at` already handles piles.
3. Bare minimum money *reading*: `hero_gold(world)` (sum of the
   hero's `COIN` items) — the shop plan and `stolen_value` need it,
   and `uhitm.steal_it`'s "leprechaun steals your gold" STUB can then
   land.
4. Tests: a gold pile merges on re-`mkgold`; amount within the C
   bounds; picking gold up adds to the carried pile (needs phase E's
   merge).

### Phase E — containers, corpses, statues (~2 sessions)

1. `add_to_container` / `delete_contents` / `weight` recursion.
2. `mkbox_cnts` (ice box / chest / large box / sack / bag of holding
   counts and contents).
3. `mkcorpstat(CORPSE|STATUE, mtmp, ptr, x, y, flags)`,
   `mk_tt_object`, `set_corpsenm`, `corpse_revive_type`.
4. `pickup` merging: same `otyp` + same `spe`/BUC + `oc_merge` →
   `quan` += (C `merged()`); the "You pick up 3 arrows" message shape.
5. Tests: a chest whose contents weigh more than the chest; a statue
   with `spe` gender; corpse `corpsenm` set; merge rules (cursed vs
   blessed do not merge).

### Phase F — the odd corners (~1 session)

`mkobj_erosions` / `may_generate_eroded` (worn gear at depth),
`blessorcurse` refinement, `rnd_treefruit_at` / `is_treefruit`,
`stone_object_type`, `item_on_ice` (no-op with a comment).

### Phase G — integrate (the payoff, ~1 session)

`fill_ordinary_room`'s object list lands **in C's order** (each line
is already commented in `core/mklev.py`): gold `!rn2(3)` → fountain
`!rn2(10)` → sink `!rn2(60)` → altar `!rn2(60)` → grave
`!rn2(80-2*depth)` → statue `!rn2(20)` → bonus item → chest
`!rn2(nroom*5/2)` → graffiti → final object. The fountain/sink/altar/
grave branches need *terrain* writers (`set_levltyp`, table item 2) and
`mkfount`/`mksink`/`mkaltar`/`mkgrave` (mklev.c) — that is the one
place this plan touches another item, and it is the reason table item 1
and item 2 are quoted together.

Then: `makeniche`'s treasure branch, `mktrap_victim`'s corpse, the
vault hoard, and `oinit`'s per-depth object mix in `goto_level`
(pyhack's `generate_level` should call `o_init.oinit` exactly where C's
`makelevel` does — first line, before `clear_level_structures`).

---

## 5. Deliberate divergences

1. **No `struct obj` linked lists.** `world.items` is a dict; floor
   order is insertion order (`items_at` returns the last-placed last,
   which is what `pickup` reads as "topmost").
2. **No `where` field.** `pos is not None` = on the floor,
   `carrier is not None` = carried, `container is not None` (after the
   rename: the parent's id in `contents`) = contained, else "free".
   The three states are mutually exclusive by construction, asserted in
   one test.
3. **No artifact, no `oc_uname`, no discovered-charge bookkeeping** in
   this wave; the hooks (`oartifact`, `known`) exist and stay default.
4. **No timers** (rot, hatch, oil burn, ice melt). The `age` field is
   written where C writes it and read nowhere.
5. **No `no_charge` / `unpaid`** — the shop plan owns billing; the
   fields are added there, not here.
6. **`splitobj` deferred** (§3.6).

---

## 6. Traps

- **`Item.container` already means something else.** The single most
  likely mistake in this wave is to add `contents` and leave
  `container` meaning "carrier"; then `add_to_container` sets
  `container=<id>` and `worn.which_armor` / `pickup` silently start
  treating a contained item as carried. Rename first (phase A), and
  grep for `.container` (13 uses today).
- **The demo's pinned kit.** `test_same_seed_same_game`,
  `test_demo.py` and the console glyph tests pin the demo's items by
  *name and position*. Do not rebuild the kit with `mksobj` in this
  wave (§3.8).
- **`obj_shuffle` / `descr` interaction.** `o_init` shuffles
  descriptions with its *own* rng stream on purpose (so the level draws
  are untouched). `mksobj` must not touch `world.obj_tables` rng —
  if a phase needs a draw there, it goes through `ObjTables`, never
  through the level rng.
- **`mksobj` must not place.** Three callers in the C code rely on
  building first; a "convenience" placement inside `mksobj` would put
  a shop's stock in the wrong square and double-place the vault gold.
- **Weight units.** `oc_weight` is in 1/100 lb (C's `WT_*` macros);
  `weight()` returns the same unit. Do not "fix" it to grams.
- **`spe` vs display.** `worn.uac` reads `oc1 + spe` via `arm_bonus`
  and clamps the *bonus*, not `spe`; `mksobj_init` rolls armour `spe`
  with `rne(3)` (i.e. `1..max(5, ulevel/3)`). A too-eager clamp in
  `mksobj` would silently weaken every generated armour.
- **`rndmonnum` inside `mksobj` (corpse/statue)** is a *monster table*
  draw. It must go through the same weighted sampler as `makemon` so
  the two cannot disagree about what exists (and so genocide is
  honoured) — hence §4.E2 depends on PLAN-MAKEMON.md C.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| `fill_ordinary_room`'s gold / chest / statue / final object | STUB |
| `makeniche`'s treasure | STUB |
| the vault hoard, `fill_zoo`'s coffers/jelly/eggs/food | STUB |
| shop stock (`stock_room`, `mkshobj_at`) | PLAN-SPECIAL-ROOMS.md D |
| `des.object()` / `des.gold()` in special levels | PLAN-SPLEV.md |
| monster inventories (`mongets`, `m_initweap`) | PLAN-MAKEMON.md E |
| leprechaun gold theft, gold detection, `create monster` scroll | STUBs |
| encumbrance, `splitobj`, containers as game mechanics (`#tip`) | future |

| needs | from |
|---|---|
| `World.new_ident` | PLAN-MAKEMON.md B (do the field work there, once) |
| `rndmonnum_adj` | PLAN-MAKEMON.md C |
| ~~`set_levltyp` (fountain / sink / altar / grave terrain)~~ | LANDED: core.mklev (table item 2) |
| `make_engr_at` (the graffiti branch, `make_grave`'s epitaph) | table item 2 / PLAN-SPLEV.md phase 0 |
| the full trap table (`mktrap_victim`) | PLAN-SPLEV.md phase 0 |

---

## 8. Definition of done

- [ ] `Item` carries `quan`/`corpsenm`/`contents`/`owt`/`oeroded`/
      `oeroded2`/`olocked`/`otrapped`; `container` renamed to `carrier`;
      `charges` gone
- [ ] the fire-trap-erodes-armour regression test exists and passes
- [ ] `mksobj` / `mkobj` / `mkgold` / `mkcorpstat` / `weight` /
      `blessorcurse` / `mkbox_cnts` ported with C spans in the
      docstrings
- [ ] the 480-row `mksobj` smoke test
- [x] `fill_ordinary_room` places, in C's order, gold, fountain,
      sink, altar, grave, statue and the final object (the terrain
      branches landed with `set_levltyp`); the bonus item, the chest
      and the graffiti STUBs remain
- [ ] `pickup` merges compatible stacks
- [ ] demo generator byte-identical; `mklev`/`cavern` levels carry real
      objects
- [ ] `CHANGES.md` + `ARCHITECTURE.md` ("no gold / chests / statues /
      fountains" bullet) updated
