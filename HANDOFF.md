# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's second staging: **Wave 5, phase 2
(PLAN-SPECIAL-ROOMS.md) — the zoo family**: `fill_zoo` in C order (the
gold budget), the monster pickers (`courtmon` / `squadmon` /
`morguemon` / `antholemon` / `mk_zoo_thronemon` / `mkundead` +
`ndemon`), the `fill_special_room` dispatcher (C: sp_lev.c — put in
mkroom.py per trap 1) with the VAULT gold branch, `Room.needfill`,
and the two missing `_roll_special_room` conditions.

## 2. Status
**Done (this session, to commit):** core.mkroom.fill_zoo (C order:
the throne / queen-square / gold-budget setup, the per-square
monsters and objects, the royal coffers, the level flags — the gold
budget verbatim: `goldlim = 500 * level_difficulty()`, per square
`i` = the squared dist2 to the first door (`i = goldlim` when
doorless), the flat `5 * level_difficulty()` once `i >= goldlim`,
`mkgold(rn1(i, 10))`, `goldlim -= i`); the zoo pickers (courtmon /
squadmon / morguemon / antholemon / mk_zoo_thronemon / mkundead —
mkclass + makemon fill-ins; **mkundead with the correct C signature**
(coord, revive_corpses, mm_flags), S32's was wrong); core.mkroom.
fill_special_room (C: sp_lev.c 2732 — NOT mkroom.c, said in the
docstring; subroom recursion, the OROOM / THEMEROOM / FILL_NONE
refusal before the flag switch, the _stock_room STUB branch, the
VAULT gold-per-square, the zoo family, the trailing flag switch);
Room.needfill (FILL_NONE / FILL_NORMAL in core.types; reset in
do_room_or_subroom per trap 2) with mkzoo setting FILL_NORMAL;
makelevel's step 8 (the C "Fill all special rooms now" loop, the
traps list rebuilt); _roll_special_room's two missing conditions
(the medusa cap faked as `world.max_lev - 5`, the G_GONE pre-checks
on leprechaun / killer bee / soldier / cockatrice + the draw-free
antholemon pre-check); ndemon (core.makemon, C: minion.c — one draw,
no retry); sobj_at (core.mkobj, C: invent.c); the four ruler rows +
anchors (core.monst_defs / core.monst); World.birth (core.types;
main.py samples getnow() once at game start, the midnight pattern);
tests — 19 in tests/test_zoo.py (one per room type + the pickers +
the dispatcher + the structural walkable test), the mkzoo needfill
assertion in tests/test_mklev.py, the shop / swamp are the two STUBs
left (named in test_mklev.py / test_mkroom.py); docs (the plan's
phase 2 record + status header, the ARCHITECTURE queue, CHANGES).
**Done (earlier, committed):** phase 1 — the temple (core/priest.py:
induced_align / priestini / has_shrine / findpriest / the reduced
intemple / the #pray #offer refusals; core.mkroom.mktemple; the Epri
extra; the entry hook; tests/test_priest.py). 1249 tests green, mypy
+ flake8 clean. The demo path is untouched (it never calls makelevel
with specials=True, and the new step 8 stocks nothing on a level with
no claimed rooms).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 3 — the swamp** (next): `mkswamp` is one STUB from done —
  the pools through set_levltyp (in), the eel / fungus stocking
  (makemon in), the `nexttodoor` guard (in); what's missing is
  `del_engr_at` (the engraving half of phase 0, still out) and the
  eel / piranha / S_FUNGUS pick. Tests per the plan: pools only on
  `(sx+sy)%2` squares, never in a doorway, eels in the water,
  `flags.has_swamp`.
- **Phase 4 — shops** (4a-4d, the `L` in `M→L`): the shk.c billing
  side, per the plan's four sub-phases; the shtypes[] table + name
  lists as data (core/shknam_data.py); `_stock_room` in core.mkroom
  is the dispatcher's shop branch (unreachable while mkshop is a
  STUB).
- Phase 0's engraving half (`make_engr_at` / `del_engr_at`) — it
  blocks both the swamp (del_engr_at) and the shop door sign
  ("Closed for inventory"), so it is the natural first step of the
  swamp phase.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv` would finish the priest's robe
  half of priestini; `splitobj` + merge rules; the mkobj_erosions
  residue), item 4 (wire QuaffCommand), item 5 (scrolls STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 2 as
   rewritten (the record of what landed and why)** + phase 3 (the
   next work) + §5 (the deliberate divergences) + §6 (the traps).
2. `core/mkroom.py` — fill_zoo + fill_special_room + the zoo
   pickers; the module docstring's STUB list (mkshop, _stock_room,
   mkswamp, cmap_to_type) is what's left in the module.
3. `core/mklev.py` — `_roll_special_room` (the odds chain, now
   complete) and `makelevel`'s steps 6-8.
4. `tests/test_zoo.py` — the zoo test shapes (the `_room_map` /
   `_claim_and_fill` / `_gold_budget` helpers are the pattern for
   the swamp and shop tests).
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read
   a C file whole (read the spans: mkroom.c 529-574 for mkswamp,
   shknam.c 209-357 / 628-801 for the shops).

## 4. Key discoveries
- **Room stocking is two-phase in C**: the mk* handler claims
  (rtype + needfill), fill_special_room stocks at the end of
  makelevel — except the temple (C stocks it in mktemple, no
  needfill). A port that stocks inside the handler moves the rng for
  every later room and level (trap 4).
- **fill_special_room is in sp_lev.c, not mkroom.c** (trap 1) — a
  grep of mkroom.c will not find it; it lives in mkroom.py and says
  so in its docstring.
- **`mksobj_at(CHEST, init=TRUE)` may already hold box loot** (C's
  mksobj_init fills containers) — the royal coffers' gold is the
  LAST content (add_to_container appends), not the only one; the
  test that pins it is test_court_gets_the_royal_coffers.
- **The ZOO picker is C's NULL**: a ZOO room gets the makemon anymon
  path per square (a random monster per square); a picker that
  answers None (genocide / out-of-band rung) takes the same path.
- **The gold budget can go negative** — the flat `5 * depth` keeps
  the far squares stocked; the per-square invariant the test pins is
  `quan in [10, i + 9]` of the replayed i (`rn1(i, 10)` = rn2(i) +
  10), replayed in C's square order.
- **C sets no level flag for the anthole / cocknest / leprehall** —
  the fill_special_room flag switch has no case (faithful, not a
  bug); the FILL_NONE refusal comes before the flag switch, so an
  unclaimed room carries no flag either.
- **A doorless room stocks its whole floor** (no door row to skip)
  and takes the flat budget per square; pick_room takes a doorless
  room only 1 in 5, so the no-door test claims the room by hand.
- **A door tile written by hand must keep the stamped roomno / edge
  / lit of the wall it replaces** (C's dosdoor copies them) or
  `Map.room_at` stops resolving the square — the helper in
  tests/test_zoo.py does it; the test that lost this once is
  test_temple_entry_message_fires_on_the_room_crossing_only.
- **`pm_good_location` (sp_lev.c, DRY) accepts furniture and stairs**
  (SPACE_POS is `typ > DOOR`), so the priest can legally stand on the
  fountain next to the shrine. Faithful, not a bug.
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 3: the swamp** (PLAN-SPECIAL-ROOMS.md): first the
   engraving half of phase 0 (`make_engr_at` / `del_engr_at` — the
   shop door sign needs it too), then `mkswamp` (up to 5 rooms ->
   POOL on the `(sx+sy)%2` squares through set_levltyp, the
   `nexttodoor` guard, the `del_engr_at`, the eel / piranha pick +
   the `S_FUNGUS` branch, `flags.has_swamp`) and the plan's tests
   (pools only on `(sx+sy)%2` squares, never in a doorway, eels in
   the water).
2. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv` would finish the priest's robe half: the rn2(2)
   bless/curse of the W_ARMC slot, named in core/priest.py's
   docstring).
3. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
