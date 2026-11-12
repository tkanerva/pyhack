# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's third staging: **Wave 5, phase 3
(PLAN-SPECIAL-ROOMS.md) — the swamp**, which needed the engraving half
of phase 0 first: `core.engrave` (`make_engr_at` / `engr_at` /
`del_engr_at` — the `Tile.engr` minimal model), then `mkswamp` (up to 5
rooms → POOL on the `(sx+sy)%2` squares through `set_levltyp`, the
`nexttodoor` guard, the `del_engr_at`, the eel / piranha pick and the
`S_FUNGUS` branch, `flags.has_swamp`).

## 2. Status
**Done (this session, to commit):** core.engrave (the engraving half
of phase 0 — `Engraving` on the Tile, the C `head_engr` list keyed by
(x, y) becomes `Tile.engr`; `engr_at` / `make_engr_at` / `del_engr_at`,
C: engrave.c 231 / 408 / 461; the `E_*` tool constants from engrave.h;
named simplifications: one text copy, no time-wear, no Elbereth guard,
no `rnd(N_ENGRAVE-1)` type roll — callers pass an explicit type);
core.mkroom.mkswamp (C: mkroom.c 529-574 — up to 5 passes, each a
plain random room, taken only if an OROOM with no stairs; set to SWAMP
and stocked *inline*, no needfill; per square a floor-type square
(`typ >= ROOM`) of the room, free of object / monster / trap and not
next to a door; on the (sx+sy)%2 squares del_engr_at + POOL through
set_levltyp + an eel (first always, else 1-in-4) by C's conditional
draws (rn2(5) giant eel / rn2(2) piranha / electric eel); the other
squares a S_FUNGUS 1-in-4; `flags.has_swamp` after each swampy room);
the `PM_PIRANHA` (317) / `PM_ELECTRIC_EEL` (320) anchors in
core.monst_defs; tests — 6 in tests/test_swamp.py (pools only on
(sx+sy)%2 squares and never in a doorway, the pools run over an
engraving, eels in the water, fungus on the dry squares, the swamp
stocked inline not by the dispatcher, the room stays walkable) + 5 in
tests/test_engrave.py (make / read / delete / replace / out-of-bounds);
the STUB tests updated (the shop is the one unstocked special room
left — tests/test_mklev.py `test_shop_handler_is_a_stub`,
tests/test_mkroom.py dispatch docstring); docs (the plan's phase 3
record + status header + the reference row + the DoD box, CHANGES).
**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family (core.mkroom.fill_zoo + fill_special_room +
the pickers, Room.needfill, the two missing _roll_special_room
conditions). 1260 tests green, mypy + flake8 clean. The demo path is
untouched (it never calls makelevel with specials=True, and the swamp
is only reached through the specials roll).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 4 — shops (4a-4d, the `L` in `M→L`)** (next): the shk.c
  billing side, per the plan's four sub-phases; the shtypes[] table +
  name lists as data (core/shknam_data.py); `_stock_room` in
  core.mkroom is the dispatcher's shop branch (unreachable while
  mkshop is a STUB).  The engraving half now exists, so the shop door
  sign ("Closed for inventory" on a locked door, C: stock_room) has
  its make_engr_at.
- **Phase 5 — the vault** (~1 session, optional here): create_vault +
  the guard is out of scope.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv` would finish the priest's robe
  half of priestini; `splitobj` + merge rules; the mkobj_erosions
  residue), item 4 (wire QuaffCommand), item 5 (scrolls STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 3 as
   rewritten (the record of what landed and why)** + phase 4 (the next
   work) + §5 (the deliberate divergences) + §6 (the traps).
2. `core/mkroom.py` — mkswamp + fill_zoo + fill_special_room + the zoo
   pickers; the module docstring's STUB list (mkshop, _stock_room,
   cmap_to_type) is what's left in the module.
3. `core/engrave.py` — the minimal engraving model (the new module).
4. `tests/test_swamp.py` — the swamp test shapes (the `_room_map` /
   `_world` / `_pools` / `_mons` helpers); `tests/test_engrave.py` —
   the engraving shapes.
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read
   a C file whole (read the spans: shknam.c 209-357 / 628-801 for the
   shops, shk.c for the billing).

## 4. Key discoveries
- **Room stocking is two-phase in C** — EXCEPT the temple and the
  swamp, which C stocks in their mk* handler (no needfill): the mk*
  handler claims (rtype) and, for the temple / swamp, stocks inline;
  the zoo family and the shop are claimed (rtype + needfill) and
  stocked by the end-of-level fill_special_room loop.  A port that
  stocks the zoo / shop inside the handler, or that gives the temple /
  swamp a needfill, moves the rng or re-stocks (trap 4).
- **`rn2` is 0-indexed in this NetHack (5.0)** (`0 <= rn2(x) < x`,
  C: rnd.c 93): `!rn2(4)` is "1 in 4".  pyhack's `Rng.rn2` matches
  exactly, so the swamp's eel / fungus rolls port directly (`if not
  rng.rn2(4)`).  The eel species is C's *conditional* draws (rn2(5),
  then rn2(2) only if the first was 0) — keep the short-circuit or the
  stream drifts.
- **`IS_ROOM(typ)` is `typ >= ROOM`, not `typ == ROOM`** (C: rm.h
  126) — it means "a floor-type square, not a wall / rock".  pyhack's
  TerrainType has the same ordering (ROOM = 25), so the test is
  `tile.typ < TerrainType.ROOM`.
- **The swamp picks a *plain random room* (`rooms[rn2(nroom)]`), NOT
  pick_room** (which prefers single-door rooms and skips non-OROOM);
  the eligibility is the in-loop `rtype != OROOM || has_upstairs ||
  has_dnstairs` test.  A re-picked room is skipped (its rtype is now
  SWAMP).
- **`flags.has_swamp` is set inline by mkswamp** (C: after each
  swampy room), so the end-of-level fill_special_room never sets it for
  the swamp (the swamp's needfill is FILL_NONE, so the dispatcher
  returns before its flag switch).  The dispatcher's SWAMP flag case is
  C-faithful but dead in the normal flow.
- **The pool square's engraving is removed *before* the pool write**
  (C: del_engr_at then levl[].typ = POOL) — the pools run over it.  The
  shop door sign and the graves are the other make_engr_at callers.
- **fill_ordinary_room skips non-OROOM rooms** (its first line), so the
  swamp room (set before the fill loop, C's order) is not re-filled
  with a monster / objects after its pools are placed.
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 4: shops** (PLAN-SPECIAL-ROOMS.md), starting with
   4a — a stocked room you can rob: `shknam_data.py` (shtypes[] + the
   name lists + shop_prob), `mkshop` (the room picker rules), `shk.init`
   (good_shopdoor, makemon(PM_SHOPKEEPER, MM_ESHK), the eshk fields,
   initial capital, nameshk), `stock_room` + `mkshobj_at` +
   stock_goodpos (door row empty, everything else stocked), the door
   fix-up (the "Closed for inventory" engraving now has its
   make_engr_at), `flags.has_shop`, `Room.resident`.
2. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv` would finish the priest's robe half: the rn2(2)
   bless/curse of the W_ARMC slot, named in core/priest.py's
   docstring).
3. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
