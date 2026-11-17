# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's sixth staging: **Wave 5, phase 4c
(PLAN-SPECIAL-ROOMS.md) — the shop's police half: the robbery, the
door block, the anger surcharge, the EF_PAY reprice, and the
death-time inheritance.**  That is the `shk.c` machinery 4b's billing
half needed to bite: `stolen_value` / `rob_shop` (leaving with an
unpaid bill), `setpaid` (the account settlement), `rile_shk` /
`hot_pursuit` / the `surcharge`, `block_door` (the keeper holds the
door), `alter_cost` (the EF_PAY half of the enchant scrolls), and
`paybill` / `inherits` (a dead hero's pack).  Only the shopkeeper's
dialogue (4d) — and, optionally, the vault (phase 5) — are still open.

## 2. Status
**Done (this session, to commit):** `core/shk.py` gained the police
section (the C spans are in the module docstring): `addupbill` (C
495-507), `stolen_value` (C 3775, reduced to the 4b model: the bill
total), `setpaid` (C 399 — the bill / debit / credit / loan cleared,
the `unpaid` marks lifted; the no_charge marks stay with
`track_shop`), `rile_shk` (C 1374 — `mpeaceful` False and, once, the
`surcharge` with every billed entry marked up by (price+2)//3),
`hot_pursuit` (C 1461 — rile_shk + `following = True`), `rob_shop`
(C 687 — the credit cover, the "You escaped the shop without paying!"
/ "You stole N ..." lines, `robbed += total`, hot_pursuit),
`block_door` (C 5812 — the shop's own door, the hero inside, the
keeper alive / at home / on its own square / owed something),
`alter_cost` (C 3258 — the billed item repriced up to get_cost, the
price only goes up), `_move_pack`, `paybill` (C 2506 — the keeper
priority: the resident owed, the resident, a keeper owed, an angry /
following keeper, a local keeper) and `inherits` (C 2598 — die in the
shop with a peaceful keeper and nothing owed -> "gratefully inherits
all your possessions"; a debt / robbery -> the owed amount, or all
when the debt exceeds the gold or the hero is in the shop, the gold
moves, a paid-in-full keeper is pacified; numsk > 1 is a no-op).
`track_shop` now returns events (the robbery fires on a tracked leave
with an unsettled bill and the keeper at home).  `core/step.py`: the
`block_door` check in `_do_move` (hero only, before the walkability
test), the `track_shop` events in `_room_entry`, and
`paybill(world, 1)` in `_finish`'s death path (before the
GameOverEvent).  `core/scrolls.py`: the `alter_cost` call in
`_chwepon` (enchant weapon) and `_seffect_enchant_armor` (enchant
armour) — the C read.c / wield.c EF_PAY call sites; the lazy import
keeps the scrolls -> shk edge one-way.  Tests — 17 new in
tests/test_shop.py's 4c section (the `_inside_shop_pos` / `_bill_item`
helpers).  Docs (the plan's 4c record + status header + the §1 rows +
the DoD 4c line + the §5.3 rewrite, CHANGES, the ARCHITECTURE shop
bullet + queue item 1, the module docstring).  1333 tests green, mypy
clean over 102 files, flake8 clean.  The demo path is untouched (it
never calls makelevel with specials=True, so no shop exists and the
new hooks are no-ops).

**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family; phase 3 — the swamp (+ core.engrave); phase
4a — a stocked shop (core/shknam_data.py + core/shk.py + mkshop);
phase 4b — the billing half (the price chain, the bill model, the Pay
command).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 4d — behaviour** (next): the `shk_talk` subset (C's
  shopkeeper dialogue — `shk_chat` 5542, the `u_entered_shop` 750 /
  `u_left_shop` 578 lines: the greeting, the bill total, the "please
  leave" line), the `shkname` honorific (shknam.c 855 — Mr. / Ms.
  from the name-prefix gender code `nameshk` already carries;
  `_shk_bare_name` is the stopgap until then), `shk_move` (C 4901 —
  the keeper's movement: the `following` chase after a robbery, the
  way home; the greedy gold pickup M2_GREEDY can wait), and the plan's
  `angry_shopkeeper` (the C anger state machine: `angry_shk_exists`
  1343 / `rouse_shk` 1393 / `pacify_shk` 1356 — `rile_shk` itself
  landed in 4c).  kops stay deferred.
- **Phase 5 — the vault** (~1 session, optional here): create_vault +
  the VAULT fill branch; the guard (src/vault.c) is out of scope.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv`, `splitobj` + merge rules, the
  mkobj_erosions residue), item 4 (wire QuaffCommand), item 5 (scrolls
  STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 4c as
   rewritten (the record of what landed and why, including the named
   skips)** + phase 4d (the next work) + §5 (the deliberate
   divergences) + §6 (the traps).
2. `core/shk.py` — the police section (from "The police" to the end:
   addupbill / stolen_value / setpaid / rile_shk / hot_pursuit /
   rob_shop / block_door / alter_cost / paybill / inherits) + the
   module docstring's "what this phase deliberately leaves out" list
   (now the 4d work list).
3. `core/step.py` — the three hooks: `block_door` in `_do_move`, the
   `track_shop` events in `_room_entry`, `paybill` in `_finish`.
4. `core/scrolls.py` — the `alter_cost` wiring in `_chwepon` /
   `_seffect_enchant_armor`.
5. `tests/test_shop.py` — the 4c section (the `_inside_shop_pos` /
   `_bill_item` helpers) and the 4a/4b shapes (`_room_map` /
   `_FixedRng` / `_stocked_shop` / `_billed_shop`).
6. The C spans — via the c_function_index tooling, never a C file
   whole: shk.c 5542+ `shk_chat`, 4901+ `shk_move`, 750+ / 578+ the
   enter/leave dialogue, 1329-1502 the anger machine (`home_shk` /
   `angry_shk_exists` / `pacify_shk` / `rouse_shk` / `make_happy_shk`
   / `make_angry_shk`), shknam.c 855+ `shkname`; the C-side context is
   in `../nethack_index/PROGRESS_SESSION_30.md` §6.

## 4. Key discoveries
- **`stolen_value` collapses to the bill total.**  C's
  `stolen_value` (3775) sums get_pricing_units * get_cost over the
  hero's unpaid objects (the container / gold halves included); in the
  4b model every picked item is billed at get_cost the moment it is
  taken, so what the hero owes is the bill total (debit +
  price*bquan).  The container / gold halves have no pyhack
  counterpart.
- **The surcharge marks up the BILLED prices, not the formula.**
  `get_cost` already adds the anger surcharge to *new* prices while
  `surcharge` is set (the line landed in 4b, a no-op while the flag is
  False); `rile_shk` marks up the prices already on the bill by
  (price+2)//3, so the bill and the pricing agree.  Once only — the
  `surcharge` flag gates the second pass.
- **`track_shop` now returns events.**  The leave hook fires
  `rob_shop` (the credit-cover or the robbery messages) and
  core.step adds them to the turn; it still acts only on an
  enter/leave transition (it compares the new inside_shop to
  hero.in_shop), so moving inside a shop is a no-op.  The entry /
  leave *dialogue* is 4d; a level-change / teleport leave does not
  re-run the hook (a named skip — the robbery fires on a *tracked*
  leave, a hero move).
- **`block_door` is the keeper at the shop's own door while owed.**
  The destination must be a DOOR tile whose room is a shop and
  (x,y) == eshk.shd; the hero must be inside that shop (in_shop ==
  the door tile's roomno); the keeper must be alive, at home
  (inhishop), standing on its own square (shkp.pos == eshk.shk), and
  owed something (debit / billct / robbed).  A closed shop (a dead
  keeper, or a keeper off its square) does not block; the Invis half
  of C's message is a named skip.
- **`alter_cost` only raises the price.**  C: `if (new_price >
  bp->price || amt < 0)` — a reprice goes up only (a de-enchantment
  never refunds the bill); a negative amt forces abs(amt) even below
  the old cost.  The scroll effects call it with amt = 0 ("reprice at
  get_cost").  The lazy `from .shk import alter_cost` inside the
  scroll functions keeps the scrolls -> shk edge one-way (shk imports
  nothing from scrolls).
- **`paybill`'s priority and `inherits`' reduction.**  The resident
  keeper (preferring one who is owed) -> a keeper the hero owes -> an
  angry / following keeper -> a local keeper; the first (numsk 1)
  decides and the rest are no-ops (C: the first already took
  everything).  Die in the shop with a peaceful keeper and nothing
  owed -> the whole pack ("gratefully inherits all your
  possessions"); a debt / robbery -> take the owed amount (or all,
  when the debt exceeds the gold or the hero is in the shop), the
  gold moves (the `_spend_gold` / `_give_gold` halves of money2mon),
  and a paid-in-full keeper is pacified (mpeaceful True, following
  False, robbed 0).  `_move_pack` rewrites the carrier directly (a
  death event, not a pickup / drop) — the conftest item-location
  invariant still holds.
- **No new state fields, no rng.**  4c reuses the 4a/4b account
  (`robbed` / `surcharge` / `following` / `debit` / `credit` / `loan`
  were already carried, zeroed) and the police chain is pure
  arithmetic / state (the robbery, the block, the reprice and the
  inheritance draw nothing).
- **Named skips (4c):** the Keystone Kop system (call_kops /
  makekops — the keeper chases alone), the keeper's movement / chase
  (shk_move / the `following` follow — 4d; `following` is carried and
  read by `paybill` / `block_door` but the keeper does not move yet),
  the cross-level keeper migration (migrate_to_level / home_shk), and
  the level-change / teleport leave (u_left_shop's newlev half — a
  scroll of teleportation out of a shop is a named escape the police
  do not see).
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 4d: behaviour** (PLAN-SPECIAL-ROOMS.md §4d): the
   `shk_talk` subset (the greeting on entering, the bill total, the
   "please leave" line on leaving — C `u_entered_shop` 750 /
   `u_left_shop` 578 / `shk_chat` 5542), the `shkname` honorific
   (shknam.c 855 — replace the `_shk_bare_name` stopgap in do_pay's
   closing line, the robbery and the door-block messages),
   `shk_move` (C 4901 — the `following` chase after a robbery, the
   keeper returning home; the M2_GREEDY gold pickup can wait), and the
   anger state machine (`angry_shk_exists` / `rouse_shk` /
   `pacify_shk`, 1343-1405; `rile_shk` is in).  kops stay deferred.
2. Same commit: the plan's §1 reference rows (the 4d rows -> exists)
   and DoD line, the CHANGES.md entry, and this HANDOFF rewritten for
   phase 5.
3. Optional: phase 5 — the vault (create_vault + the VAULT gold
   branch; the guard is out of scope).
4. Interleaveable: the genesis residue (queue item 2), the
   QuaffCommand wire-up (item 4), the scrolls STUBs (item 5).
5. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
