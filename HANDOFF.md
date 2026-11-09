# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's first staging: **Wave 5, phase 1
(PLAN-SPECIAL-ROOMS.md) — the temple**: the priest system (core/priest.py
from src/priest.c), the shrine altar in `mktemple`, the `Epri` extra,
the entry message, and the `#pray` / `#offer` refusals.

## 2. Status
**Done (committed):** core/priest.py (`induced_align`, `priestini`,
`has_shrine` / `findpriest` / `_histemple_at`, the reduced `intemple`
with the untended ghost, `do_pray` / `do_offer` refusals);
`core.mkroom.mktemple` (C order: pick_room(TRUE) → rtype → shrine_pos →
ALTAR via set_levltyp → induced_align → priestini → AM_SHRINE →
flags.has_temple); `Epri` + `Monster.epri/ispriest/isshk` in core.types;
MM_EPRI allocates in makemon (MM_ESHK & friends still ignored);
PrayCommand / OfferCommand + the `#pray` / `#offer` console keys; the
TEMPLE half of the room-entry hook (`core.step._room_entry`, C:
spoteffects → check_special_room, once per room crossing); the priest
draws as the human glyph `@` (defsym.h S_HUMAN) with the legend gained
by both the priest and the altar; `PM_ALIGNED_CLERIC` anchor
(monst_defs + monst); tests/test_priest.py (12 tests); docs (plan phase
1 record, ARCHITECTURE queue + bullets, CHANGES). 1231 tests green,
mypy + flake8 clean. The demo path is untouched (it never calls
makelevel with specials=True, and the entry hook is draw-free without
rooms).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 2 — the zoo family** (next): `fill_zoo` in C order per type
  (the gold budget is the fiddly part: `goldlim = 500 *
  level_difficulty()`, per square `i = min(dist², goldlim)`,
  `rn1(i, 10)`, subtracted); `courtmon` / `squadmon` / `morguemon` /
  `antholemon` / `mkundead` (the **correct** C signature is
  `mkundead(coord, revive_corpses, mm_flags)`, not what the STUB says)
  / `mk_zoo_thronemon` as `mkclass` + `makemon` fill-ins;
  `fill_special_room` (sp_lev.c 2732 — **it lives in sp_lev.c, not
  mkroom.c**; put it in mkroom.py and say so in the docstring) as the
  end-of-level dispatcher, including the VAULT gold branch;
  `Room.needfill` (add it, and reset it in do_room_or_subroom — trap #2
  in the plan); the two missing `_roll_special_room` conditions (the
  medusa cap faked as `world.max_lev - 5`, the `G_GONE` pre-checks on
  leprechaun / killer bee / soldier / cockatrice).
- **Phase 3 — the swamp**: `mkswamp` is one STUB from done — only
  `del_engr_at` (the engraving half of phase 0) and the eel / fungus
  stocking are missing (set_levltyp and makemon are in).
- **Phase 4 — shops** (4a-4d, the `L` in `M→L`): the shk.c billing
  side, per the plan's four sub-phases.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv` would finish the priest's robe
  half of priestini; `splitobj` + merge rules; the mkobj_erosions
  residue), item 4 (wire QuaffCommand), item 5 (scrolls STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header (what phase 1 landed) +
   **phase 1 as rewritten (the record of what landed and why)** +
   phase 2 (the next work) + §5 (the deliberate divergences) + §6
   (the traps — read them before touching `fill_special_room` or
   `needfill`).
2. `core/priest.py` — the whole priest system; the module docstring
   lists every named skip (robe tail, pacing timers, nomul(-3),
   intone, Sanctum).
3. `core/mkroom.py` — `mktemple` (the C-ordered temple) and the STUB
   list (what phase 2-4 still raise for).
4. `core/mklev.py` — `_roll_special_room` (the odds chain, now
   carrying world / lev / traps) and `makelevel`'s step 6.
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read
   a C file whole (read the spans: priest.c 220-272 / 410-560,
   mkroom.c 256-453 / 607-630, sp_lev.c 2732-2805, dungeon.c
   2010-2025).

## 4. Key discoveries
- **The human glyph is `@`** (defsym.h `MONSYM(53, '@', HUMAN,
  S_HUMAN)`), the same character as the hero — the plan's "the priest
  as a human glyph" means a second `@` on the map, and the legend has
  to say so ("@ = Hero (or Priest)").
- **C's `mktemple` stocks inline and sets no needfill** — the temple is
  the only special room that doesn't go through `fill_special_room`'s
  stocking (that one only carries its flag). Don't give it a needfill
  in phase 2.
- **C's `priestini` reads the altar mask *before* AM_SHRINE is set**
  (mktemple ORs the bit in after the call); pyhack keeps the order, and
  `amask2align` masks with AM_MASK anyway.
- **C's `makemon` at the hero's square IS the "near the hero" case**
  (the `[u.ux,u.uy]` → enexto branch, only when not in_mklev) — which
  is why the untended-temple ghost "appears next to you" without any
  relocation code.
- **A door tile written by hand must keep the stamped roomno / edge /
  lit of the wall it replaces** (C's dosdoor copies them) or
  `Map.room_at` stops resolving the square — the test that lost this
  is the one that teaches it.
- **`pm_good_location` (sp_lev.c, DRY) accepts furniture and stairs**
  (SPACE_POS is `typ > DOOR`), so the priest can legally stand on the
  fountain next to the shrine. Faithful, not a bug.
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 2: the zoo family** (PLAN-SPECIAL-ROOMS.md): the
   monster pickers first (`courtmon` / `squadmon` / `morguemon` /
   `antholemon` / `mkundead` / `mk_zoo_thronemon` — verify every
   signature against the C span, the plan warns S32's `mkundead` is
   wrong), then `fill_zoo` in C order with the gold budget, then
   `fill_special_room` in core.mkroom (with the VAULT gold branch),
   `Room.needfill`, and the two `_roll_special_room` conditions. The
   zoo rows (queen bee, soldiers, undead, ants, the rulers) are all in
   the 383-row table — `MONS[PM_QUEEN_BEE]` & friends resolve.
2. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv` would finish the priest's robe half: the rn2(2)
   bless/curse of the W_ARMC slot, named in core/priest.py's
   docstring).
3. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
