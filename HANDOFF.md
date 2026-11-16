# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's fifth staging: **Wave 5, phase 4b
(PLAN-SPECIAL-ROOMS.md) — the shop's billing half: prices, the bill,
and the `p` (Pay) command.**  That is the `shk.c` half of the shop that
4a (the `shknam.c` half) left out: `getprice` / `get_cost`, the bill
model, the pickup hook, the `in_shop` tracking, and `do_pay`.  The
police (4c) and the dialogue (4d) are still open.

## 2. Status
**Done (this session, to commit):** `core/shk.py` gained the price
chain (`getprice` shk.c 4339-4379, `get_cost` 2898-3009 — the 0->5
floor, the un-ID'd x4/3, C's round-half-up combine, the <=0->1 floor,
the anger surcharge; the named skips: glass gem, DUNCE_CAP/tourist, the
CHA table, artifacts), the bill model (`BILLSZ = 200`, `onbill`,
`billable`, `add_one_tobill`, `sub_one_frombill`, `shop_debt` — the
`BillEntry` dict on `Eshk` per §2.3, `billct` kept in sync), the two
predicates (`inhishop` 1038, `costly_spot` 5370 — the keeper's own
square is not costly), the `in_shop` hook (`track_shop`, C's
check_special_room u.ushops half: the no_charge enter/leave marks), and
the `Pay` command (`do_pay`, C dopay 1758 simplified to pay-all: the
room keeper, the `money + credit >= total` gate, the per-entry
"You bought ..." + `pay_debt` + the money2mon gold move, the "Thank you
for shopping in ..." line) + `pay_debt` (the debit/loan/credit branches
at 3903-3931, ported for 4c reuse).  `core/types.py`: `Item.unpaid` /
`Item.no_charge`, `Monster.in_shop`, `Eshk.bill` + the new `BillEntry`
dataclass.  `core/commands.py`: `PayCommand` (+ the `Command` union).
`core/step.py`: the `PayCommand` dispatch + `track_shop` in
`_room_entry` (next to the temple branch).  `core/pickup.py`: the
billing hook (a picked item on a costly_spot that is not a coin and not
no_charge goes on the bill, silently).  `ui/console.py`: `p` bound to
`PayCommand` (verified unbound) + the help line.  Tests — 22 new in
tests/test_shop.py's 4b section; docs (the plan's 4b record + status
header + the §1 rows + the DoD 4b/4c split, CHANGES, the module
docstring).  1316 tests green, mypy clean over 102 files, flake8 clean.
The demo path is untouched (it never calls makelevel with
specials=True, so no shop exists and the new hooks are no-ops).

**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family; phase 3 — the swamp (+ core.engrave); phase
4a — a stocked shop (core/shknam_data.py + core/shk.py + mkshop).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 4c — the police** (next): `stolen_value` (shk.c 3776),
  `eshk.robbed` (the "You stole from me!" path, the keeper turns
  hostile), `surcharge` + `alter_cost` (the EF_PAY half, so a
  scroll of enchant armour inside a shop marks the item), the door
  block (the keeper stands in the doorway and refuses to leave it),
  `inhishop`'s "closed" state, and `paybill` (shk.c 2506 — the
  death-time inventory inheritance).  The `unpaid` items that 4b
  leaves behind on leaving are what 4c punishes.  kops stay deferred.
- **Phase 4d — behaviour**: `shk_talk` subset (the greeting, the bill
  total, "please leave"), the `shkname` honorific (do_pay currently
  uses the bare name), `shk_move` (the keeper's movement).
- **Phase 5 — the vault** (~1 session, optional here): create_vault +
  the guard is out of scope.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv` would finish the priest's robe
  half and give the shopkeeper a wielded weapon; `splitobj` + merge
  rules; the mkobj_erosions residue), item 4 (wire QuaffCommand), item
  5 (scrolls STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 4b as
   rewritten (the record of what landed and why, including the credit
   model)** + phase 4c (the next work) + §5 (the deliberate
   divergences) + §6 (the traps).
2. `core/shk.py` — the shop system; the module docstring's "what this
   phase deliberately leaves out" list is now the 4c-4d work list.
3. `core/types.py` — `BillEntry`, `Item.unpaid` / `no_charge`,
   `Monster.in_shop`, `Eshk.bill`.
4. `tests/test_shop.py` — the 4b section (the `_item` / `_price_world`
   / `_stocked_shop` / `_billed_shop` helpers), and the 4a shapes
   (`_room_map` / `_FixedRng` / `_claim` / `_floor_items`).
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read a
   C file whole (read the spans: shk.c 4339+ for `getprice`, 2898+ for
   `get_cost`, 3331+ for the bill, 3776+ for `stolen_value`, 2506+ for
   `paybill`, 577+ / 750+ for the leave/enter dialogue).

## 4. Key discoveries
- **The plan's `pay()` citation is `donate_gold`.**  The 4b spec cites
  the pay arithmetic at "shk.c 3903-3931" and calls it `pay()`; that
  span is C's `donate_gold` (whose zero-debit arm adds the payment to
  `eshk.credit`).  C's actual buy path is `pay()` at 1310
  (check_credit + money2mon), which does *not* establish credit.  The
  plan's 4b model is the deliberate override: buying establishes
  credit (`credit == total` after a clean bill) AND the gold moves to
  the keeper.  `pay_debt` ports the 3903-3931 branches; this is
  documented in the plan, CHANGES, and the `pay_debt` docstring.  If a
  future session wants C-faithful buying, it changes `do_pay` to use a
  1310-style pay (check_credit + money2mon, credit unchanged) — the
  tests pin the plan's model, so they'd need updating too.
- **The un-ID'd surcharge is broader than C's.**  C gates the x4/3 on
  `oid_price_adjustment` (`o_id % 4 == 0`) as well as
  `!dknown || !oc_name_known`; the plan applies it on the `!dknown`
  arm only, so a fresh un-ID'd item is always billed up (a named
  simplification, in the `get_cost` docstring).  The `!oc_name_known`
  half reads the per-game `world.obj_tables.name_known` (the same read
  core.rings uses), so a *discovered* type is not surcharged.
- **`getprice`'s WAND zero is `spe == -1` (a cancelled wand), not
  `spe == 0`.**  A used-up (but not cancelled) wand keeps its base
  price; only a cancelled wand (the cancellation scroll's `spe = -1`)
  is free.  The test pins both (the cancelled wand at 0, the spe-0
  wand at base).
- **`getprice`'s FOOD hunger multiplier hits the BUY side**
  (`uhs >= HUNGRY && !shk_buying`): the hero's `uhs` (2..6) multiplies
  the price of food the hero is *buying*; selling takes no multiplier.
  The test sets `hero.uhs` directly for uhs 2..6.
- **The gold move merges into the keeper's one pile.**  The keeper
  already carries its 4a capital as a single COIN item, so the payment
  is added to it (`_give_gold`), not stacked beside it (a new pile
  would break "one pile").  The hero's pile is reduced by `_spend_gold`
  (deleting a pile that empties, via `invent.delobj`).  Neither draws
  rng (4b is pure arithmetic), so the `_give_gold` fallback builds a
  bare coin without an rng draw.
- **The pickup bill is silent and the BILLSZ cap is per-keeper.**  A
  billable pickup adds an entry with no message (C's pickup line is the
  only one); the 201st pickup on a *full* bill (billct == BILLSZ = 200)
  is "You got that for free!" (no entry).  The cap is checked AFTER
  billable, so a no_charge / coin / already-billed item is free for a
  different reason (no entry, no message).
- **`track_shop` runs on every hero move but only acts on a change.**
  It compares the new `inside_shop` to `hero.in_shop` and returns early
  if unchanged, so moving inside a shop (or staying out) is a no-op;
  only an enter/leave transition sets the no_charge marks.  It is a
  state update with no events (the entry/leave dialogue is 4d).
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 4c: the police** (PLAN-SPECIAL-ROOMS.md §4c — build
   from that section + the C spans in §3.5): `stolen_value` on leaving
   the shop with `unpaid` goods (the 4b `unpaid` flag is the hook),
   `eshk.robbed` + the "You stole from me!" hostility flip, `surcharge`
   + `alter_cost` (the EF_PAY half), the door block (the keeper holds
   the doorway), `inhishop`'s "closed" state, and `paybill` (the
   death-time inheritance).  The `pay_debt` debit / loan branches are
   already ported for this phase's reuse.
2. Same commit: the plan's §1 reference rows (`alter_cost` /
   `stolen_value` / `paybill` -> exists 4c) and DoD line, the
   CHANGES.md entry, and this HANDOFF rewritten for 4d.
3. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv` would finish the priest's robe half and give the
   shopkeeper a wielded weapon), the QuaffCommand wire-up (item 4), the
   scrolls STUBs (item 5).
4. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
