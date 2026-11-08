# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1: `set_levltyp` + the terrain
writers (mkfount / mksink / mkaltar / mkgrave) and PLAN-MKOBJ phase G's
terrain rolls in `fill_ordinary_room`.

## 2. Status
**Done (committed):** the terrain mutator + furniture generators in
`core/mklev.py`, the C-order furniture rolls in `fill_ordinary_room`,
`Tile.altarmask` + align.h block, `clear_level_structures` now clears
the World half (items / traps / monsters of the level), two test
fixes, plan / arch / changes docs. 1220 tests green, mypy + flake8
clean. Demo path untouched (it never calls `makelevel`).

**Not done:** the phase-G residue (bonus item, chest `!rn2(nroom*5/2)`,
graffiti `make_engr_at` — all STUBs, rolls not taken, named in
`_fill_room_objects`); `mkswamp` (mkroom) still needs engraving removal
+ eel / fungus monsters; everything else on the ARCHITECTURE queue
(queue now starts at item 1 = Wave 5 special rooms).

## 3. Files to read first
1. `ARCHITECTURE.md` — the rule (one World, step(), events out) + the
   "Suggested next steps" queue (this is the work order).
2. `PLAN-MKOBJ.md` §4 phase G + the status header — what the terrain
   rolls are and what remains.
3. `core/mklev.py` — the new `set_levltyp` / `find_okay_roompos` /
   `mkfount` / `mksink` / `mkaltar` / `mkgrave` / `make_grave` block
   (~line 1094) and `_fill_room_objects`.
4. `core/mkroom.py` — the remaining special-room STUBs (`mkswamp` etc.).
5. `../nethack_index/NETHACK-INDEX.md` — the C span index; never read
   a C file whole.

## 4. Key discoveries
- C's `set_levltyp` (mkmaze.c) recounts fountains / sinks, so
  `mkfount`'s `nfountains++` after it is a C double-count — pyhack
  counts once (docstring says why).
- C's `find_okay_roompos` draws the whole room rectangle (`rnd_loc`),
  corners included — a room corner may legally be a fountain.
- C's `clear_level_structures` (mklev.c) frees the level's object /
  monster state in the same call; pyhack's map-only reset broke
  seeded regeneration over a stocked World as soon as the filler
  placed items — hence the World-side clear in that function.
- Carried items keep their carrier's `Item.lev`, so clearing
  `it.lev == lev` removes monster inventories for free.
- The pytest tool's `paths` are relative to the workspace root
  (`pyhack/tests/...`), and they currently resolve to a container
  mount that doesn't see the files — run the full suite with no paths.

## 5. Next steps
1. **Wave 5: special rooms** (PLAN-SPECIAL-ROOMS.md): the temple first
   (needs `src/priest.c` / `src/pray.c` as core systems + the
   `Monster.epri` extra), then the zoo family, shops last. `set_levltyp`
   (temple shrine / swamp pools) and the real `mkmon` distribution are
   both in place now.
2. Interleaveable: the genesis residue (ARCHITECTURE queue item 2:
   `m_initweap` / `m_initinv`, `splitobj` + merge rules, the
   rust / rot / corrode half of `mkobj_erosions`, the
   fire-trap-erodes-armour regression test).
3. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
