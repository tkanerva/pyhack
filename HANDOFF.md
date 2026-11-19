# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's last staging: **Wave 5, phase 5
(PLAN-SPECIAL-ROOMS.md) — the vault: the sealed 2x2 room, the
double-filled hoard, the vtele entrance.**  That completes the plan:
every room type in the special-room roll is now a real, stocked,
walkable system (temple, zoo family, swamp, shop 4a-4d, vault), and
the next session is a new queue item, not a new phase of Wave 5.

## 2. Status
**Done (this session, to commit):** `core/mklev.py` gained the vault
(the C spans are in the module docstring and the function
docstrings): `create_vault` (C: the mklev.c 53 *macro*
`create_room(-1, -1, 2, 2, -1, -1, VAULT, TRUE)`, running through
create_room's vault path — `dx = dy = 1`, the `xlim++` / `ylim++`
margin, the 100-try loop — reserving the 2x2 spot out of the free
rectangles, split_rects only: no room record, no terrain, the
position is the scratch-slot write), the vault attempt in
`makerooms` (C 403-410: from MAXNROFROOMS / 6 rooms, the
`tried_vault` once-per-level local, the `rn2(2)` test in C's
short-circuit order; the return is the reservation or None),
`check_room`'s `vault` margin parameter (C: `xlim = XLIM + (vault ?
1 : 0)`), the `_add_vault` block of makelevel (C 1319-1345:
check_room at the reserved spot, the one fresh try, `add_room` the
sealed lit 2x2 VAULT as the level's LAST room, `flags.has_vault`,
`needfill = FILL_NORMAL`, the IMMEDIATE fill_special_room gold,
makevtele the 2-in-3 time), `makevtele` (C: makeniche with the
TELEPORTATION trap), and `_roll_special_room`'s `threshold` argument
(C's `++room_threshold`: 4 when a vault is present, 3 otherwise).
C's double fill kept: the inline fill + the end-of-level loop
(needfill never cleared in C), mkgold merging the two
`rn1(depth * 100, 51)` draws per square.  Named skips: the vault.c
guard (`invault` / `gd_move` / `fakecorr` / `paygd`) and
`mk_knox_portal` (no dungeon branch system; its rn2(3) draw not
taken).  Tests — 9 new in tests/test_vault.py (on the C-sized 80x21
grid; the 40x20 demo grid never reaches the six-room threshold) +
the sealed-vault exception in tests/test_mklev.py's three
structural tests.  Docs (the plan's phase-5 record + status header +
§1 rows + DoD, the ARCHITECTURE queue item 1, CHANGES, this
HANDOFF).  1370 tests green, mypy clean over 103 files, flake8
clean.  The demo path is untouched (0 vaults in 60 seeds on 40x20).

**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family; phase 3 — the swamp (+ core.engrave);
phase 4a — a stocked shop (core/shknam_data.py + core/shk.py +
mkshop); phase 4b — the billing half (the price chain, the bill
model, the Pay command); phase 4c — the police (the robbery, the
door block, the surcharge, the EF_PAY reprice, the death-time
inheritance); phase 4d — the behaviour (the dialogue, the honorific,
the keeper's movement, the anger state machine).

**Not done (the rest of Wave 5):** nothing — the plan is complete.
- Out of scope by name, whenever it wants to land: the vault.c
  guard (a separate system: `invault`, `gd_move`, `fakecorr[]`,
  `paygd` — without it the vault is "a secret room full of gold",
  reachable through the vtele niche), and `mvault_tele` /
  `uleftvault` (teleport.c — wait for the guard).
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv`, `splitobj` + merge rules, the
  mkobj_erosions residue), item 4 (wire QuaffCommand), item 5
  (scrolls STUBs), item 6 (the full `mmove()`).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header (the plan is
   complete) + **phase 5 as rewritten (the record of what landed and
   why, including the named skips)** + §5 (the deliberate
   divergences) + §6 (the traps).
2. `core/mklev.py` — `create_vault` + `makerooms` (the vault
   attempt), `check_room` (the `vault` margin), `_add_vault` +
   `makevtele` + `makelevel` (the vault block is step 6 of
   makelevel's documented order), and the module docstring's STUB
   list (the vault's guard + Knox are the named skips).
3. `tests/test_vault.py` — the 9 tests (the reservation shape, the
   refusals, the once-per-level attempt, the sealed vault + hoard,
   the vtele niche, the block directly, the threshold raise).
4. The C spans — via the c_function_index tooling, never a C file
   whole: `create_room` (sp_lev.c 1485, the vault path at
   1502-1579), the mklev.c 53 macro, the makelevel vault block
   (1319-1345); the guard is `src/vault.c` (out of scope).

## 4. Key discoveries
- **`create_vault` is C's macro, not a function** (mklev.c 53:
  `#define create_vault() create_room(-1, -1, 2, 2, -1, -1, VAULT,
  TRUE)`) — the function index never lists it, and the plan's
  "the vault is `create_vault` (src/mkroom.c)" was stale on both
  counts (it is in mklev.c, and it is not a function).  Read the
  span before porting (the plan's trap, again).
- **The vault is the one room C does NOT add to the level in
  makerooms.**  The reservation is split_rects + the scratch-slot
  write (`svr.rooms[svn.nroom].lx = xabs`, the slot's `hx` set to -1
  by the caller) — no room record, no terrain.  makelevel re-adds
  it as the level's LAST room (after the sort and the corridors),
  which is why nothing is ever dug into it: the room's `doorct` is
  0 and its ring is stone.
- **C fills the vault twice, and mkgold makes it one pile per
  square.**  The inline fill + the end-of-level fill_special_room
  loop (needfill is never cleared anywhere in C — verified by
  grep); mkgold merges into the existing pile, so each of the four
  interior squares is the sum of TWO `rn1(depth * 100, 51)` draws
  (102..2*(depth*100+50) at depth 5).  The port reproduces the
  double fill: the rng stands where C leaves it.
- **The grid size decides whether a vault exists.**  The vault
  attempt starts at MAXNROFROOMS / 6 rooms — the 40x20 demo grid
  usually makes 2..6 and never reaches the threshold (0 vaults in
  60 seeds), the C-sized 80x21 makes ~8 and vaults ~40% (24 in
  60).  The tests run on 80x21; the demo is untouched by
  construction.
- **The vault margin is one square wider all round** (C: `xlim++` /
  `ylim++` for the VAULT rtype at 1502-1505, and `xlim = XLIM +
  (vault ? 1 : 0)` in check_room) — the extra room for the wall ring
  and the vtele niche that may be dug into a room next to the
  vault.  Here check_room() takes it as a parameter; create_vault()
  uses the widened constants directly (the documented
  simplification in the module docstring).
- **`++room_threshold` (C 1331) is a shop-roll condition, not a
  flag.**  A level with a vault needs FOUR rooms for the shop roll,
  not three — threaded as `_roll_special_room`'s `threshold`
  argument (3 / 4 from the vault block's answer).  The test pins
  the same 3-room level: it shops at threshold 3 and refuses at 4.
- **The vtele niche reuses phase 2's niche machinery:** makevtele =
  makeniche(TRAP_TELEPORTATION) — the SCORR niche with its
  TELEPORTATION trap behind a secret door, the only way into an
  otherwise sealed vault.  `makeniche` skips non-OROOM rooms, so
  the niche is always dug into an ordinary room next to the vault.
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files
  — run the full suite with no paths (as always).

## 5. Next steps
1. **The queue moves on** (ARCHITECTURE.md, in dependency order):
   item 2 the genesis residue (interleavable — `m_initweap` /
   `m_initinv`, `splitobj` + the merge rules, the
   mkobj_erosions residue), item 4 the QuaffCommand wire-up (`q`
   quits, so the quaff key is to choose), item 5 the scrolls STUBs
   (SCR_DESTROY_ARMOR around the already-real
   `worn.disintegrate_arm`, SCR_LIGHT, SCR_CONFUSE_MONSTER), item 6
   the full `mmove()`.
2. If the vault's guard ever lands (src/vault.c, 1,292 L:
   `invault`, `gd_move`, `fakecorr[]`, `paygd` — the guard that
   watches the gold, digs the fake corridors, and collects
   payment), it brings `mvault_tele` (teleport.c) and `uleftvault`
   with it; without it the vault is "a secret room full of gold".
3. Keep HANDOFF.md updated per the 5 sections above; keep every
   PLAN status header in sync in the same commit.
