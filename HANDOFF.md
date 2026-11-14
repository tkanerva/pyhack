# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's fourth staging: **Wave 5, phase 4a
(PLAN-SPECIAL-ROOMS.md) — a stocked shop you can rob**.  That is the
`shknam.c` half of `src/shk.c`: the shop-type table, the room picker,
the shopkeeper and the stock.  The billing half (prices, the police,
the dialogue) is 4b-4d and still open.

## 2. Status
**Done (this session, to commit):** `core.shknam_data.py` (the
`shtypes[]` table — 12 rows with their nine-slot `iprobs` arrays and
`shdist` — plus the twelve shopkeeper name lists, transcribed verbatim
from shknam.c 39-357); `core/shk.py` (the new module: `inside_shop`
(C: shk.c 567), `good_shopdoor` (581), `init` = shkinit (627),
`stock_goodpos` (694), `stock_room` (717), `mkshobj_at` (453),
`get_shop_item` (828), `veggy_item` / `shkveg` / `mkveggy_at`
(379/407/442), `nameshk` (486), plus `shop_keeper` / `room_keeper`);
`core.mkroom.mkshop` (the room pick, the lit rectangle, the shop-type
roll, `rtype = SHOPBASE + i`, FILL_NORMAL — C's forward walk over
`svr.rooms[]`, NOT `pick_room`); `fill_special_room`'s `_stock_room`
shim into `shk.stock_room`; `Eshk` on `Monster` (types.py) with
`makemon`'s MM_ESHK now allocating it (the C neweshk);
`Room.resident` (the keeper's id, cleared in `do_room_or_subroom` with
`needfill`); `cvt_sdoor_to_door` (C: detect.c 1588) in core.mklev;
the `PM_SHOPKEEPER` (271) and `PM_LICHEN` (158) anchors in
core.monst_defs / core.monst; **the engraving constants corrected** to
this NetHack's engrave.h (`E_DUST 1` .. `E_HEADSTONE 6`, `N_ENGRAVE 6`
— the 3.6 `E_PLAIN / E_PEN / E_SABER / E_STYLUS` set was wrong);
tests — 33 in tests/test_shop.py + 1 in tests/test_engrave.py, and
tests/test_mklev.py's shop STUB test became the mkshop claim test;
docs (the plan's phase 4a record + status header + the §1 rows + the
§6 traps + the DoD, CHANGES, ARCHITECTURE's queue item 1 and the
"Added" list).  1294 tests green, mypy + flake8 clean.  The demo path
is untouched (it never calls makelevel with specials=True, and the shop
is only reached through the specials roll).
**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family; phase 3 — the swamp (+ core.engrave).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 4b — prices** (next): `getprice` (shk.c 4341-4380) + all its
  per-class adjustments, `bcsign` (the ×2 / ×½ BUC multipliers, and the
  mirror for selling), the CHA table, the per-move `u.ushops` shop
  square tracking (`inside_shop` is already the room-number lookup),
  `onbill` / `billable` / `add_one_tobill` / `eshk.debit` (the bill as a
  dict keyed by item id — `Eshk` already carries the zeroed account),
  the `Pay` command (`p`) + `paybill`'s messages, the status-line total.
- **Phase 4c — the police** (`stolen_value`, `eshk.robbed`,
  `surcharge`, `alter_cost`, the door block), **4d — behaviour**
  (`shk_talk`, `shkname` with the honorific, `shk_move`); kops stay
  deferred.
- **Phase 5 — the vault** (~1 session, optional here): create_vault +
  the guard is out of scope.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv` would finish the priest's robe
  half of priestini; `splitobj` + merge rules; the mkobj_erosions
  residue), item 4 (wire QuaffCommand), item 5 (scrolls STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 4a as rewritten
   (the record of what landed and why)** + phase 4b (the next work) +
   §5 (the deliberate divergences) + §6 (the traps, three of them new
   this session).
2. `core/shk.py` — the shop system (the module docstring's "what this
   phase deliberately leaves out" list is the 4b-4d work list).
3. `core/shknam_data.py` — the table; `core/mkroom.py`'s mkshop (the
   claim half) and `core/engrave.py` (the constants).
4. `tests/test_shop.py` — the test shapes (`_room_map` / `_FixedRng` /
   `_claim` / `_floor_items`), and `tests/test_zoo.py` for the
   end-of-level dispatch shapes.
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read a
   C file whole (read the spans: shknam.c 39-357 for the tables and
   407-801 for the functions, shk.c 4341+ for `getprice`, shk.c 3331+
   for the bill).

## 4. Key discoveries
- **`mkshop`'s room pick is NOT `pick_room`** — it is C's plain forward
  walk from `svr.rooms[0]`, taking the first OROOM with no staircase,
  exactly one door, and a shape `invalid_shop_shape` accepts.  So a shop
  is deterministic given the level's rooms, and a two-door room can
  never be a shop.  `pick_room` (the zoo family's) has a random start
  and a `!rn2(5)` door preference — do not "unify" them.
- **`shtypes[]` has exactly ONE zero-probability shop** (the lighting
  store).  The plan's §6 said "the four zero-probability special-level
  shops" — that was a 3.6 memory and is corrected in place.  The
  eleven rolled rows sum to 100.
- **The "Closed for inventory" sign goes on the CORRIDOR side.** C
  tests `inside_shop(sx + 1, sy)` and then steps the engraving *away*
  from the shop (`m--`), i.e. out into the street, and coerces that
  square to ROOM / CORR when it is neither.  A port that engraves the
  shop floor looks reasonable and is wrong (this session's first draft
  did exactly that and the test caught it).
- **`good_shopdoor` returns the door *stepped inside*, and `shkinit`
  records both squares**: `eshk.shd` is the door, `eshk.shk` is where
  the keeper stands.  `stock_room`'s door fix-up uses the room's FIRST
  door (C: `svd.doors[sroom->fdoor]`) while the stocking loop uses the
  keeper's (`svd.doors[sh]`); a shop has one door so they agree.
- **The stocking is a separate phase for a reason**: `mkshop` runs
  during the special-room roll (early), `stock_room` at the very end of
  makelevel.  Stocking inside mkshop moves the rng for every later room
  and level (trap 4/5).
- **`veggy_item(None, otyp)` and `veggy_item(obj)` disagree for tins**
  until `set_tin_variety(HEALTHY_TIN)` is ported: the type-only call
  seeds corpsenm with PM_LICHEN (vegetarian), the object call sees an
  empty tin (spe 0).  The health-food tests therefore check the *type*.
- **`_roll_special_room`'s shop gate is `depth > 1 and depth <
  max_lev - 5 and nroom >= 3 and rn2(depth) < 3`** — with the default
  `max_lev == 1` the medusa cap is negative and a shop can never roll.
  A test that wants a generated shop must set `world.max_lev` (see
  tests/test_shop.py's last test).
- **`name_wanted = m_id + ledger_no + (nseed % 13) - (nseed % 5)`** (C: shknam.c nameshk, verified), with
  `nseed = ubirthday / 257`; pyhack reads the monster's numeric id, the
  level number (no ledger) and `World.birth`.  The tools list always
  draws with `rn2` (its names are the jokes) — that is C's, not a bug.
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 4b: prices — fully specified in
   PLAN-SPECIAL-ROOMS.md §4b (build from that section).**  Every C span
   it cites was read and verified 2026-07-11 (`getprice` 4339-4379,
   `get_cost` 2898-3009, the bill functions, `dopay` / `pay_billed_`
   `items` / `dopayobj` / `pay`); the session should not need to
   re-read shk.c beyond spot checks.  Scope: the buy-price chain
   (`getprice` + `get_cost`, table-driven), the bill model (`BillEntry`
   dict on `Eshk` + `onbill` / `billable` / `add_one_tobill` /
   `sub_one_frombill` / `shop_debt`), the pickup hook +
   `costly_spot` / `inhishop`, the `in_shop` move hook with the
   no_charge enter/leave marks, and the `Pay` command (`p` →
   `do_pay`, C's `dopay` simplified to pay-all — no menu).  Two old
   claims are corrected there: this C has **no `bcsign` price
   multiplier** (blessed ×2 / cursed ×½ was a 3.6 memory) and **no
   `oc_prob` math in `getprice`**; the sell side (`sellobj` /
   `set_cost` / `saleable`) is deferred.  Note: in C, buying
   *establishes credit* (`pay()` at 3903-3931 adds to `eshk.credit`) —
   the 4a-era "credit stays 0" note was true of stocking, not of 4b.
2. Same commit: the plan's §1 reference rows and DoD line, the
   CHANGES.md entry, and this HANDOFF rewritten for 4c.
3. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv` would finish the priest's robe half and give the
   shopkeeper its wielded weapon).
4. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
