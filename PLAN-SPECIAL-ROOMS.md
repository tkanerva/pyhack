# Plan: Wave 5 — special rooms (temple → zoo family → shops)

**Status: phase 0 (terrain + engraving) + phase 1 (temple) + phase 2
(the zoo family) + phase 3 (the swamp) + phase 4a (a stocked shop you
can rob) LANDED; phases 4b-4d (prices, the police, the dialogue) and 5
(the vault) proposed.**  Phase 4a landed as core/shknam_data.py
(the shtypes[] table + the twelve name lists, verbatim) + core/shk.py
(inside_shop, good_shopdoor, shkinit, stock_room_goodpos,
get_shop_item / veggy_item / shkveg / mkveggy_at / mkshobj_at,
stock_room, nameshk, shop_keeper) + core.mkroom.mkshop (the room pick,
the lit rectangle, the shop-type roll, rtype, FILL_NORMAL) + the
`Eshk` extra on Monster (MM_ESHK in makemon now allocates it) +
`Room.resident` + `cvt_sdoor_to_door` in core.mklev — tests in
tests/test_shop.py (33).  Phase 3 landed as the engraving half of
phase 0
(core.engrave: the Engraving on the Tile, engr_at / make_engr_at /
del_engr_at, the E_* tool constants) + core.mkroom.mkswamp (up to 5
rooms -> POOL on the (sx+sy) % 2 squares through set_levltyp, the
nexttodoor guard, the del_engr_at, the eel / piranha pick and the
S_FUNGUS branch, flags.has_swamp) + the PM_PIRANHA / PM_ELECTRIC_EEL
anchors — tests in tests/test_swamp.py (6) and tests/test_engrave.py
(5).  Phase 2 landed as
core.mkroom.fill_zoo (C order: the throne / queen-square / gold-budget
setup, the per-square monsters and objects, the royal coffers, the
level flags) + the zoo pickers (courtmon / squadmon / morguemon /
antholemon / mk_zoo_thronemon / mkundead, the mkclass + makemon
fill-ins, mkundead with the **correct** C signature) + core.mkroom.
fill_special_room (the end-of-level dispatcher, C: sp_lev.c 2732 — in
mkroom.py by trap 1, with the VAULT gold branch) + Room.needfill
(FILL_NONE / FILL_NORMAL, reset in do_room_or_subroom per trap 2) +
the two missing _roll_special_room conditions (the medusa cap faked as
world.max_lev - 5, the G_GONE pre-checks) + ndemon in core.makemon +
sobj_at in core.mkobj + the four ruler rows in the table — tests in
tests/test_zoo.py (19).  Phase 1 landed as core/priest.py
(induced_align, priestini, has_shrine / findpriest, the reduced
intemple, the #pray / #offer refusals), core.mkroom.mktemple (the
C-ordered room pick + shrine altar + AM_SHRINE + flags.has_temple),
the `Epri` extra on Monster (MM_EPRI in makemon now allocates it),
and the TEMPLE half of the room-entry hook in core.step (C's
check_special_room).  Phase 0's engraving half (`make_engr_at` /
`del_engr_at`) landed with phase 3 (core.engrave) — the shop door sign
now has it too.  Table.txt row 4, the `L` end of the `M→L` range:
temples and
the zoo family are "room + a few lines" once PLAN-MAKEMON.md and
PLAN-MKOBJ.md exist; **shops are the expensive one**, because a shop
is billing (`src/shk.c`, 6,147 lines, 55.7k tokens — 21 % of a context
window) before it is anything else.

**Goal:** `do_mkroom()` earns its keep. A generated level can contain a
temple with a shrine and a priest, a zoo / barracks / morgue / beehive /
court / anthole / cockatrice nest / leprechaun hall that is actually
stocked, a swamp, and — last — a shop with a shopkeeper, stock and a
bill.

**Ground truth:** `../NetHack` through `nethack_index`:
`INDEX.md` rows for `src/mkroom.c` (1,109 L, 30 fn), `src/priest.c`
(944 L, 23 fn), `src/shknam.c` (928 L, 18 fn), `src/shk.c` (6,147 L,
139 fn), `src/pray.c` (2,721 L — **out of scope**, see §2.6), the
special-room roll in `src/mklev.c` 1347-1378, and
`src/sp_lev.c#fill_special_room` 2732; `symbols/*.json` for spans;
`PROGRESS_SESSION_32.md` §8 (mkroom) and §6 (shk) are *hypotheses* —
S32's `mkundead` signature is wrong (the C is
`mkundead(coord *mm, boolean revive_corpses, int mm_flags)`, not
`(pos, rng)`), so verify every signature against the span.

**Dependencies in one line:** this plan is *gated* on PLAN-MAKEMON.md
and PLAN-MKOBJ.md (a room full of monsters and treasure needs both), on
`set_levltyp` (table item 2 — swamps, fountains, altars), and on
`make_engr_at` (the shop "Closed for inventory" engraving, graves).

---

## 1. What the C code does (reference)

| C function | where | what it does | port target |
|---|---|---|---|
| `do_mkroom(roomtype)` | mkroom.c 51-92 | dispatch: `>= SHOPBASE` → `mkshop`, else the `mkzoo` family / `mktemple` / `mkswamp` | `mkroom.do_mkroom` (exists) |
| `mkshop` | mkroom.c 94-216 | pick an unused one-door room, lit it, roll the shop type from `shtypes[]`, set `rtype = SHOPBASE + i`, `needfill = FILL_NORMAL` | `mkroom.mkshop` (exists, 4a) |
| `mkzoo(type)` | mkroom.c 243-254 | only *claims* the room (`pick_room`, `rtype`) | `mkroom.mkzoo` (exists) |
| `fill_zoo(sroom)` | mkroom.c 275-453 | the stocking: throne + monarch, queen bee, gold, corpses, chests, graves, statues with loot, ants | `mkroom.fill_zoo` (exists) |
| `mk_zoo_thronemon(x, y)` | mkroom.c 256-273 | gnome ruler → dwarf ruler → elven monarch → ogre tyrant by `rnd(level_difficulty())`, asleep, hostile, carrying a MACE | `mkroom.mk_zoo_thronemon` (exists) |
| `courtmon` / `squadmon` / `morguemon` / `antholemon` / `mkundead` | mkroom.c 792 / 826 / 477 / 501 / 455 | the zoo-family monster pickers (`mkclass` + `ndemon`) | same names (exists) |
| `mktemple` | mkroom.c 607-630 | `pick_room(TRUE)`, `rtype = TEMPLE`, `shrine_pos`, `ALTAR` + `induced_align(80)`, `priestini`, `AM_SHRINE`, `flags.has_temple` | `mkroom.mktemple` (exists) |
| `shrine_pos(roomno)` | mkroom.c 578-605 | the room centre, or a free square when the centre is blocked | `mkroom.shrine_pos` (exists) |
| `mkswamp` | mkroom.c 529-574 | up to 5 rooms → `POOL` on the `(sx+sy)%2` squares, eels, fungus; `flags.has_swamp` | `mkroom.mkswamp` (exists) |
| `induced_align(pct)` | dungeon.c 2010-2025 | the level's/dungeon's alignment, else `rn2(3)-1` | `dungeon.induced_align` |
| `priestini(lvl, sroom, sx, sy, sanctum)` | priest.c 220-~300 | the priest: a 1-square ring search, `makemon(PM_ALIGNED_CLERIC, MM_EPRI)`, `epri.shrpos/shralign/shroom`, peaceful, `set_malign`, the goodies | `priest.priestini` |
| `newepri` / `EPRI` | priest.c 16 / mextra.h 95-106 | the priest extra struct (shralign, shroom, shrpos, timers) | `Monster.epri` |
| `intemple(roomno)` | priest.c 410-… | the temple-entry / peace-and-safety messages | `priest.intemple` (thin) |
| `priest_talk` | priest.c 558-… | the service/donation dialogue | **deferred** (§2.6) |
| `shkinit(shp, sroom)` | shknam.c 628-692 | `good_shopdoor`, `makemon(PM_SHOPKEEPER, MM_ESHK)`, `isshk`, `eshk.shoproom/shoptype/shd/shk`, initial capital `mkmonmoney(1000 + 30*rnd(100))`, a touchstone / charging scroll, `nameshk` | `shk.init` (exists, 4a) |
| `stock_room(shp_indx, sroom)` | shknam.c 718-801 | fix the door (no `D_NODOOR`, no trap, no secret), the "Closed for inventory" engraving on a locked door, then one `mkshobj_at` per stockable square | `shk.stock_room` (exists, 4a) |
| `mkshobj_at` / `mkveggy_at` / `get_shop_item` | shknam.c 442 / 407 / 829 | the per-square object (class, or a specific `-otyp`) | `shk.mkshobj_at` (exists, 4a) |
| `stock_room_goodpos` | shknam.c 694-716 | "not the door row, not a wall, not occupied" | `shk.stock_goodpos` (exists, 4a) |
| `shtypes[]` | shknam.c 209-357 | the 12 shop classes: name, `symb`, probability, per-class item probabilities | **data** → `core/shknam_data.py` (exists, 4a) |
| `getprice(obj, shk_buying)` | shk.c 4341-4380 | the base price and its per-class adjustments | `shk.getprice` (4b) |
| `add_one_tobill` / `billable` / `sub_one_frombill` / `alter_cost` / `stolen_value` / `paybill` | shk.c 3331 / 3473 / 3683 / 3259 / 3776 / 2507 | the bill | `shk.bill` (a *model*, §2.3) |
| `inside_shop` / `inhishop` / `costly_spot` / `onbill` | shk.c | "which shop is this square in / is this shopkeeper at home / may this cost money / is this on a bill" | `shk.inside_shop` (exists, 4a); `inhishop` / `costly_spot` / `onbill` = 4b |
| `fill_special_room(croom)` | sp_lev.c 2732-… | the **dispatcher** called for *every* room at the end of `makelevel`: shop → `stock_room`, `VAULT` → gold per square, zoo family → `fill_zoo` | `mkroom.fill_special_room` (exists) |
| the special-room roll | mklev.c 1347-1378 | one special room per level by depth, with the genocide pre-checks (`G_GONE` on leprechaun / killer bee / soldier / cockatrice) and the `depth(medusa_level)` cap | `mklev._roll_special_room` (exists, needs the two missing conditions) |

---

## 2. Design decisions

1. **Extras are optional dataclasses on `Monster`, exactly like C's
   `mextra`.** `Monster.epri: Optional[Epri]`, `Monster.eshk:
   Optional[Eshk]`, later `.edog`/`.egd`/`.emin`. `makemon`'s
   `MM_EPRI`/`MM_ESHK` flags allocate them (PLAN-MAKEMON.md D already
   accepts-and-ignores those flags; here they start doing work). This
   keeps one `Monster` type instead of a priest subclass — the same
   reason the hero is a `Monster`.
2. **The altar is terrain, not an object.** `Tile.typ = ALTAR` plus
   `Tile.altarmask: int` (the `align.h` bits: `AM_LAWFUL/AM_NEUTRAL/
   AM_CHAOTIC` in the low bits, `AM_SHRINE`, `AM_NONE`), with
   `Align2amask`/`Amask2align`. This is the field `types.Tile`'s own
   docstring already lists as a STUB.
3. **A bill is a `dict`, not a linked list.** C's `eshk.bill[]` is a
   fixed array of `struct bill_x` (`bo_id, useup, price, bquan`); here
   it is `Dict[str, BillEntry]` keyed by item id. Everything `shk.c`
   does with the array (subscripts, "billct", compaction) becomes a
   dict operation. **Do not port `shk.c` wholesale**: port the four
   questions the game actually asks —
   (a) *what does this cost?* (`getprice` + the BUC and CHA
   multipliers),
   (b) *is this item unpaid?* (`onbill`),
   (c) *what does the hero owe?* (`eshk.debit`),
   (d) *the hero is leaving / has left with unpaid goods* (`stolen_value`
   → `eshk.robbed`, the shopkeeper turns hostile, kops later).
   That is a few hundred lines, not 6,147.
4. **Money is items.** Gold is a `COIN`-class `Item` with `quan`
   (PLAN-MKOBJ.md D). `hero_gold(world)` is a sum, never a separate
   counter; paying is `splitobj`-free ("reduce `quan`, delete at 0") and
   `mkmonmoney` moves it into the shopkeeper's inventory.
5. **Stocking happens at the end of the level, not in the room
   picker.** C sets `rtype` + `needfill` when it *picks* the room and
   stocks it in the `fill_special_room` loop after every room has been
   filled (`mklev.c` 1417-1421). `Room.needfill` must therefore be
   added (`FILL_NONE = 0`, `FILL_NORMAL = 1`, `FILL_CORRIDOR`,
   `FILL_WALL` — sp_lev.h/mkroom.h; only the first two matter here).
   pyhack's `mkzoo` already follows this shape, which is why it needed
   no change.
6. **Prayer is out of scope, and the plan must say so loudly.**
   `src/pray.c` (2,721 L) owns sacrifice, donation, altar wrath, the
   "you feel a surge of power" path and `priest_talk`'s consequences.
   A temple in this wave is: an altar tile with an alignment, a
   peaceful priest standing next to it who knows the room, the
   `intemple` message, and `#offer`/`#pray` refused with a "not yet"
   line. Anything else is a lie the tests would enforce forever.
7. **Shops before shopkeepers' AI.** Four sub-phases (§4.4) so the
   game stays playable at every commit: a *stocked room you can take
   from for free*, then a *priced* room, then a *policed* room, then
   the shopkeeper's movement/talk.
8. **`shtypes[]` is data with the C probabilities**, in
   `core/shknam_data.py` (the `*_data.py` convention). The shop name
   lists (`shkgeneral`, `shkarmors`, … 12 name arrays, shknam.c
   ~10-190) come with it; `nameshk` picks one with `rl` (a shuffle
   without replacement, so two shops on a level never share a name —
   which needs the per-game `name_list` state, the `ObjTables`
   pattern).
9. **The shop-family sub-template: `Room.resident: Optional[str]`**
   (C `sroom->resident`) so `inside_shop` can find the keeper without
   scanning the monsters, and so a revisited level (parked `Map`)
   keeps it.
10. **The level's special-room roll keeps C's draw order** and gains
    the two conditions pyhack is missing (`depth(medusa_level)` cap,
    the `G_GONE` pre-checks) — with the medusa cap faked as
    `world.max_lev - 5` until the dungeon topology exists.

---

## 3. What a temple/zoo/shop needs that does not exist yet

| need | owner |
|---|---|
| `makemon` / `mksobj` / `mkgold` / `mkcorpstat` / `mongets` | PLAN-MAKEMON.md, PLAN-MKOBJ.md |
| the monster rows for the zoo family and shops (see §3.1) | PLAN-MAKEMON.md A (they are in the 383-row table; the *subset* today has none of them) |
| `Tile.altarmask`; `ALTAR`/`THRONE`/`SINK`/`FOUNTAIN`/`GRAVE` terrain writers (`mkfount`, `mksink`, `mkaltar`, `mkgrave`) | `set_levltyp` (table item 2) |
| `make_engr_at` / `del_engr_at` (shop door sign, gravestones) | `src/engrave.c` subset — table item 2 / PLAN-SPLEV.md phase 0 |
| `Monster.isshk` / `ispriest` (two booleans, C has them on `struct monst`) | this plan |
| a `Pay` command (`p`) + the inventory/price UI line | this plan, phase 4b |
| `ndemon(align)` (a demon picker, mon.c) | PLAN-MAKEMON.md C extension |

### 3.1 The monster rows each room type needs (the checklist)

`QUEEN_BEE`, `KILLER_BEE` (BEEHIVE) · `LEPRECHAUN` (LEPREHALL — already
in the subset) · `COCKATRICE` (COCKNEST — in the subset) ·
`SOLDIER`/`SERGEANT`/`LIEUTENANT`/`CAPTAIN` (BARRACKS) ·
`SOLDIER_ANT`/`FIRE_ANT`/`GIANT_ANT` (ANTHOLE) · `GHOST`/`WRAITH`/
`KOBOLD_ZOMBIE`/`HUMAN_ZOMBIE` (MORGUE — in the subset) plus the
`S_ZOMBIE`/`S_VAMPIRE`/`S_DEMON` class neighbours · `BUGBEAR`,
`GNOME_RULER`, `DWARF_RULER`, `ELVEN_MONARCH`, `OGRE_TYRANT` (COURT) ·
`SHOPKEEPER` (shops) · `ALIGNED_CLERIC`, `HIGH_CLERIC` (temples) ·
`GIANT_EEL`, `ELECTRIC_EEL`, `PIRANHA` + one `S_FUNGUS` (SWAMP).

All of them arrive for free with PLAN-MAKEMON.md phase A (the full
table); *none* are in the 40-row subset today, so this plan cannot
start before that phase lands.

---

## 4. Phases

### Phase 0 — the terrain and engraving prerequisites (shared, S)

Not this plan's work, but this plan cannot test anything without them:

1. `set_levltyp(map, x, y, typ)` (mkmaze.c 77-121) — the sanctioned
   mutator, with `CAN_OVERWRITE_TERRAIN`, the lava `lit`, and the
   fountain/sink recount.
2. `mkfount` / `mksink` / `mkaltar` / `mkgrave` (mklev.c) — each is
   "find a free square in the room, write the terrain".
3. `make_engr_at` / `engr_at` / `del_engr_at` (engrave.c) — the
   minimal `Tile.engr` + text model.
4. `Tile.altarmask`.

### Phase 1 — temple (LANDED) — landed as described, with these notes

1. `Tile.altarmask` + the align.h block landed with the terrain writers
   (queue item 1, core.monst_defs); `induced_align` lives in
   core/priest.py (C: dungeon.c — the temple is its only live caller,
   and pyhack has no dungeon module), always the temperate-dungeon
   roll: `rn2(3) - 1` -> `align2amask`.
2. `Epri` (core.types, the C struct epri with the pacing timers carried
   and never ticked) + `Monster.ispriest`/`isshk`; `MM_EPRI` in makemon
   allocates the extra (the C newepri block); MM_ESHK & friends still
   accepted-and-ignored until their systems.
3. `priest.priestini`: the 1-square ring search in C's xdir/ydir order
   (decl.c), `si = rn2(N_DIRS)`, the `pm_good_location` test reduced to
   in-bounds + `SPACE_POS` (C's DRY half, sp_lev.c — faithfully
   including the furniture next to the shrine), the rloc() insurance
   (enexto), `makemon(PM_ALIGNED_CLERIC, MM_EPRI, in_mklev=True)`, the
   epri fields, `mpeaceful = True`, `set_malign`, the 2-4 spellbooks
   (`rn1(3, 2)`, mkobj's `SPBOOK_no_NOVEL` + the addinv single
   writer).  The robe tail (m_initweap / which_armor W_ARMC + its
   rn2(2)) waits for PLAN-MAKEMON.md phase E — its roll is not taken.
4. `mkroom.mktemple`: `pick_room(TRUE)` → `rtype = TEMPLE` →
   `shrine_pos` → `ALTAR` (through `set_levltyp`; C writes levl[]
   directly, the mutator has no side effect on an ALTAR destination) →
   `altarmask = induced_align(80)` → `priestini` → `altarmask |=
   AM_SHRINE` → `flags.has_temple` — the C order, priestini reading the
   mask before AM_SHRINE is set.  A shrine_pos that gives up (a room
   with no standable square) keeps the rtype, altar and priest unmade —
   C's shrine_pos never answers NULL, so it is the named refusal.
5. `priest.intemple` (the "Pilgrim, you enter a sacred/desecrated
   place!" + the peace / forbidding feeling, the untended eerie lines
   and the 1-in-5 hostile ghost — the nomul(-3) is a named skip) and
   the **refusals** `do_pray` / `do_offer`: "You feel you should not do
   that here." (C's own misaligned-altar line), with `pray.c`'s
   provenance in the docstrings; the commands are PrayCommand /
   OfferCommand (`#pray` / `#offer` in the console, C do_extcmd) and a
   turn is spent.  The room-entry hook is `_room_entry` in core.step
   (C: the spoteffects -> check_special_room half of a hero move, the
   TEMPLE branch only; moving inside the room never re-fires it).
6. Rendering: the altar already drew as `_` (C `S_altar`, the display
   port had the branch); the priest draws as the human glyph `@` (C
   S_HUMAN, defsym.h — the same character as the hero; the console
   legend line says "@ = Hero (or Priest)" and gained the altar).
7. Tests: tests/test_priest.py — all of the plan's list (the one altar
   + AM_SHRINE + legal alignment, the peaceful co-aligned priest on the
   shrine's ring who knows the room, the second-mktemple None, the
   tended / desecrated / untended intemple halves, the refusals, the
   entry hook firing once per crossing) + the ring fallback and the
   induced_align three-way.

### Phase 2 — the zoo family (LANDED) — landed as described, with these notes

1. `fill_zoo` (core.mkroom, C: mkroom.c 275-453) in C's order: the
   per-type setup (the court's throne square by somexyspace — the
   maze-level pre-placed-THRONE scan is a named no-op, pyhack has no
   maze levels; the beehive's queen square = the room centre with the
   irregular fallback; the ZOO / LEPREHALL gold budget), then the
   per-square pass (C's skip conditions — the !SPACE_POS / door-
   adjacent rectangular half and the roomno / edge / distmin
   irregular half; the court's "not on the throne" test; the type's
   picker; makemon(MM_ASLEEP | MM_NOGRP, in_mklev=True); the court's
   mpeaceful -> hostile flip; the type's objects: the ZOO / LEPREHALL
   gold, the MORGUE corpse 1/5 / chest 1/10 / grave 1/5 (the GRAVE
   terrain through make_grave — its engraving half is still out), the
   BEEHIVE royal jelly 1/3, the BARRACKS payroll 1/20, the COCKNEST
   statues (rn2(5) RANDOM_CLASS loot through add_to_container, C's
   mk_tt_object(STATUE) = init FALSE), the ANTHOLE food 1/3), then
   the post-processing (the court's THRONE write + the royal coffers,
   the level flags).  The gold budget, verbatim: goldlim = 500 * 
   level_difficulty(); per square i = the squared dist2 to the first
   door (i = goldlim when the room has no door); when i >= goldlim
   the flat 5 * level_difficulty(); goldlim -= i; mkgold(rn1(i, 10))
   — the budget can go negative and the flat value keeps the far
   squares stocked.  A picker that answers None (C: NULL —
   antholemon after all three ants are genocided, courtmon's
   out-of-band rungs) takes C's makemon anymon path, which pyhack's
   makemon(ptr=None) is — a ZOO room is a random monster per square.
2. The pickers (core.mkroom, C: mkroom.c) as mkclass + makemon
   fill-ins: courtmon (the i = rn2(60) + rn2(3*depth) ladder, the two
   fixed rows bugbear / hobgoblin), squadmon (the squadprob[] table
   kept as data, the cumulative cpro > sel_prob walk, the G_GONE test
   answers None), morguemon (the depth ladder; the Inhell /
   In_endgame mkclass(S_DEMON) half a named no-op — pyhack has no
   hell — so the ndemon(A_NONE) half, and a failed draw drops to the
   ladder, C's comment), antholemon (World.birth % 3 + depth, draw-
   free, the genocide rotation, all-gone answers None), 
   mk_zoo_thronemon (the four rulers by rnd(depth), asleep + hostile
   + the mace), mkundead (the **correct** C signature (coord,
   revive_corpses, mm_flags) — S32's (pos, rng) was wrong; the
   revive() half a named skip: a corpse on the square counts as
   revived).  ndemon (C: minion.c) landed in core.makemon (which
   owns mkclass_aligned): one draw, the lords / princes rejected, no
   retry.
3. `fill_special_room` (core.mkroom; **C: sp_lev.c 2732, NOT
   mkroom.c** — trap 1, said in the docstring; PLAN-SPLEV.md will
   call the same function for des.room({type="zoo"})): the subroom
   recursion, the OROOM / THEMEROOM / FILL_NONE refusal (it comes
   before the flag switch, so an unclaimed room carries no flag
   either), the FILL_NORMAL stocking (the shop branch first — 
   _stock_room STUB, unreachable while mkshop is a STUB; the VAULT
   gold-per-square — the vault room type is useful before vault.c;
   the zoo family through fill_zoo), the trailing flag switch (no
   case for the anthole / cocknest / leprehall, C's).  makelevel
   calls it for every top-level room after the ordinary-room loop
   (C: "Fill all special rooms now"), the traps list rebuilt first so
   the zoo fill sees the ordinary rooms' traps.
4. `Room.needfill` (core.types, C: mkroom.h — FILL_NONE = 0,
   FILL_NORMAL = 1; the plan's FILL_CORRIDOR / FILL_WALL are never
   set) + the trap-2 reset in do_room_or_subroom (a room object is
   re-used on regeneration; a stale FILL_NORMAL would re-stock a
   stale room).  mkzoo sets FILL_NORMAL (C: "the room does not get
   stocked at this time"); the temple sets none (C's mktemple stocks
   inline, so fill_special_room only carries its flag).
5. `_roll_special_room` (core.mklev) gained the two missing
   conditions (§2.10): the shop roll's medusa cap faked as
   world.max_lev - 5 until the dungeon topology exists, and the G_GONE
   pre-checks on the leprechaun / killer bee / soldier / cockatrice
   rolls (plus C's draw-free antholemon() pre-check on the ant roll).
   The draw order otherwise stays C's.
6. The table and the supporting machinery: the four ruler rows
   (PM_GNOME_RULER / PM_DWARF_RULER / PM_ELVEN_MONARCH / 
   PM_OGRE_TYRANT) + anchors in core.monst_defs / core.monst (the
   zoo's other rows were already in the 383-row table); sobj_at
   (core.mkobj, C: invent.c — the mkundead revive half); World.birth
   (core.types, the ubirthday — main.py samples getnow() once at game
   start, the midnight pattern; the tests keep the 0 default so
   seeded worlds keep their draw sequences).
7. Tests: tests/test_zoo.py — one per room type (the monarch on the
   THRONE, asleep + hostile with the mace, the royal coffers' last
   content the rn1(50*depth, 10) gold with spe=2, one monster per
   stocked square, the ZOO / LEPREHALL gold within the replayed per-
   square budget [10, i + 9], the doorless flat budget, the MORGUE
   corpses / chests / graves + the undead ladder, the BEEHIVE's
   single centre queen, the ANTHOLE's single species + no flag, the
   BARRACKS squad + payroll, the COCKNEST statues + loot, every
   monster asleep, the C flags) + the dispatcher's refusals (OROOM
   and FILL_NONE, before the flag switch) + the VAULT gold + flag +
   the pickers (the courtmon depth gating, the squadmon G_GONE, the
   antholemon rotation) + mkundead (the swarm, the graveyard flag,
   the revive skip) + the structural walkable-room test; plus the
   mkzoo needfill assertion in tests/test_mklev.py and the STUB-test
   updates there and in tests/test_mkroom.py (the shop and the swamp
   are the two STUBs left).

### Phase 3 — swamp (LANDED) — landed as described, with these notes

1. **The engraving half of phase 0 landed first** (core.engrave):
   `Engraving` on the Tile (the C `head_engr` list keyed by (x, y)
   becomes `Tile.engr`), `engr_at` / `make_engr_at` / `del_engr_at`
   (C: engrave.c 231 / 408 / 461), and the `E_*` tool constants
   (engrave.h).  Named simplifications: the three text copies collapse
   to one, the time-based wear is not ported, the Elbereth guard and
   the `rnd(N_ENGRAVE - 1)` type roll are not ported (callers pass an
   explicit type), and the player-facing doengrave / read / wipe half
   is out.  This unblocks both the swamp (del_engr_at) and the shop
   door sign (make_engr_at).
2. **`mkswamp` (core.mkroom, C: mkroom.c 529-574)** in C's order:
   up to 5 passes, each a *plain random room* (`map_.rooms[rng.rn2(
   len)]` — NOT pick_room's single-door preference); a room is taken
   only if it is an OROOM with no stairs (the C `hx < 0` empty-slot
   test is a no-op — pyhack's `map_.rooms` holds only real rooms).  A
   taken room is set to SWAMP and stocked *inline* (the swamp, like the
   temple, sets no needfill, so the end-of-level fill_special_room
   refuses it and only its flag would be carried — which mkswamp sets
   itself).  Per square: a floor-type square (C: IS_ROOM = `typ >=
   ROOM`) belonging to the room, free of object / monster / trap and
   not next to a door (nexttodoor); on the (sx+sy)%2 squares the
   engraving is removed and the square becomes a POOL (through
   set_levltyp), with an eel when it is the first (eelct == 0) or by a
   1-in-4 roll — the species by C's conditional draws (rn2(5) giant
   eel, else rn2(2) piranha, else electric eel; mkclass() "won't do,
   as we might get kraken"); the other squares get a S_FUNGUS by a
   1-in-4 roll.  `flags.has_swamp` is set after each swampy room (set
   iff at least one room was swamped).
3. **The table:** `PM_PIRANHA` (317) / `PM_ELECTRIC_EEL` (320) anchors
   in core.monst_defs (the rows were already in the 383-row table; the
   giant eel anchor `PM_GIANT_EEL` 319 was already in).
4. Tests: tests/test_swamp.py (6 — pools only on (sx+sy)%2 squares and
   never in a doorway, the pools run over an engraving, eels in the
   water, fungus on the dry squares, the swamp stocked inline not by
   the dispatcher, the room stays walkable) + tests/test_engrave.py
   (5 — make / read / delete / replace / out-of-bounds).  The STUB
   tests updated: the shop is the one unstocked special room left
   (tests/test_mklev.py, tests/test_mkroom.py).

### Phase 4 — shops (4a LANDED; 4b-4d proposed; the `L` in `M→L`)

**4a — a stocked room you can rob (LANDED)** — landed as described,
with these notes:

1. **The split is C's, not the plan's convenience.** mkshop (the room
   pick, the lit rectangle, the shop-type roll, `rtype = SHOPBASE + i`,
   FILL_NORMAL) stayed in core.mkroom with the other mk* handlers;
   everything that *creates* — shkinit, the door fix-up, the per-square
   objects — is core.shk, called from fill_special_room at the end of
   makelevel (`stock_room(croom->rtype - SHOPBASE, croom)`).  Nothing is
   created while the room is picked, so the rng stands where C leaves
   it (trap 4/5).  `do_mkroom` gained no new arguments: `mkshop(map_,
   stairs, rng)` needs the staircase list for its eligibility test and
   nothing else.
2. **The room pick is a plain forward walk, not pick_room** (C: the
   `for (sroom = &svr.rooms[0];; sroom++)` loop): the first room that is
   an OROOM, holds no staircase, has exactly one door and passes
   `invalid_shop_shape`.  Two consequences pyhack's `pick_room` would
   have hidden: a shop is *deterministic* given the level's rooms, and a
   two-door room can never be a shop.  The wizard-only `SHOPTYPE`
   override at the top of C's mkshop is a named skip (no wizard mode).
3. **The shop type is data** (core/shknam_data.py): the 12 `shtypes[]`
   rows with their nine-slot `iprobs` arrays and the twelve name lists,
   transcribed verbatim; `SHOPTYPES[i]` <-> `SHOPBASE + i`, so the index
   is the room-type offset.  The roll is C's walk (`j = rnd(100); while
   (j -= prob) > 0: i++`) — the overshoot lands on the general store,
   which is a feature — and `isbig(room)` downgrades a wand / book shop
   to index 0 (a big room has nowhere to stand for those).
4. **`shtypes[]` has exactly ONE zero-probability shop** (the lighting
   store), not the four §6 claimed: §6 was written from a 3.6 memory.
   The row is still unreachable from mkshop; it waits for the special
   level loader.  tests/test_shop.py pins the table (12 rows, the 11
   rolled rows sum to 100, every iprobs row sums to 100, no name twice
   within a list).
5. **The billing half is a model, not a port** (§2.3, unchanged):
   `Eshk` carries `shoproom` / `shoptype` / `shd` / `shk` / `shoplevel`
   / `shknam` and a *zeroed* account (`debit` / `credit` / `loan` /
   `robbed` / `surcharge` / `following` / `billct` / `visitct`), and C's
   `struct bill_x bill[]` is not a field at all — 4b adds it as a dict
   keyed by item id.
6. **The door fix-up is C's, including its surprise**: a doorway without
   a door becomes an open one, a secret door becomes a real one
   (`cvt_sdoor_to_door`, ported to core.mklev next to the door writers),
   and a trapped door becomes LOCKED.  A locked door gets "Closed for
   inventory" engraved on the square *opposite the shop's inside* — C
   steps the engraving `m--` / `n--` away from the shop, i.e. into the
   corridor, where a customer can read it, and coerces that square to
   ROOM / CORR when it is neither.  `inside_shop()` (core.shk) is the
   room-number lookup that tells the two sides apart (§5.6).
7. **`nameshk` is C's, on pyhack's clocks:** the seed is `m_id +
   ledger_no - (nseed % 13) + (nseed % 5)` with `nseed = ubirthday /
   257`; here the monster's numeric id stands in for `m_id`, the level
   number for the ledger (one dungeon, no ledger) and `World.birth` for
   `ubirthday`.  The tools list always draws with `rn2` (its names are
   the jokes), a name already in use on the level retries, and the
   fallback chain is the general store's list then Lucrezia / Dirk.
   The `-` / `_` / `+` / `|` / `=` prefix codes are carried and set
   `Monster.female`; the honorific is `shkname()` (4d).
8. **Named skips inside the stocking:** the tribute "special spot"
   (`svc.context.tribute.enabled` + the `rnd(stockcount)` draw — pyhack
   has no tribute system, so `mkshobj_at` is always called with
   `mkspecl=False` and there are no novels), `set_tin_variety(obj,
   HEALTHY_TIN)` (tins have no variety field, so a health-food tin is an
   ordinary one — which is why the tests check `veggy_item(None, otyp)`
   rather than the object), and `mon_learns_traps` (no per-monster trap
   knowledge, the priest's skip).  The mimic roll IS taken, in C's
   short-circuit order (`rn2(100) < depth && !MON_AT && mkclass(S_MIMIC)
   && makemon`), so a shop square can be a mimic instead of an object.
9. **`Room.resident` carries the keeper's id** (§2.9) and
   `do_room_or_subroom` now clears it with `needfill` (a re-generated
   level must not name a shopkeeper it no longer has — trap 2).
   `shk.shop_keeper(world, lev, roomno)` is C's scan; `room_keeper(world,
   room)` reads the field.
10. **The engraving constants were wrong and are fixed**: core.engrave
    carried the 3.6 `E_PLAIN / E_PEN / E_SABER / E_STYLUS` set; this
    NetHack's engrave.h has `DUST 1 / ENGRAVE 2 / BURN 3 / MARK 4 /
    ENGR_BLOOD 5 / HEADSTONE 6` and `N_ENGRAVE 6` (so C's default roll
    `rnd(N_ENGRAVE - 1)` is 1..5 and never a headstone).  The port now
    spells them `E_DUST .. E_HEADSTONE` with those values, and the shop's
    door sign is `E_DUST` (C: DUST).
11. Tests: tests/test_shop.py (33) — the table invariants; the room
    pick, the lighting, the type roll per band and the big-room
    downgrade (a `_FixedRng` pins the roll); the keeper's square, eshk,
    purse, gifts and name (and two shops never sharing one); the four
    door fix-ups and the sign; inside_shop; one object per stockable
    square with the door row empty (or a mimic); the per-class stock;
    the health-food pseudo-class and shkveg; the refusals (no room, no
    door); the walkable room; and a makelevel(specials=True) run that
    really produces a stocked shop.  tests/test_mklev.py's STUB test
    became the mkshop claim test.

**4b — prices (1-2 sessions, proposed).**
  `getprice` (the per-class adjustments, all of them), `bcsign` (blessed ×2 / cursed ×1/2 for buying, the mirror for selling), the CHA
  multiplier table, the `ushk` / `u.ushops` square tracking (`inside_shop`
  on every move), `onbill`, `billable`, `add_one_tobill`, `eshk.debit`,
  the `Pay` command (`p`), `paybill`'s "You bought …" / "You owe …"
  messages, and the total on the status line.
  *Exit:* taking stock creates a bill; paying settles it; the numbers
  match a table-driven test of `getprice` for ~20 representative objects.

**4c — the shopkeeper polices it (1-2 sessions, proposed).**
  `stolen_value` on leaving the shop with unpaid goods, `eshk.robbed`,
  `surcharge`, the "You stole from me!" path, `alter_cost` (so
  `scroll of enchant armour` inside a shop adds `EF_PAY`), the door
  block (a shopkeeper stands in the doorway and `m_move` refuses to let
  him leave it), `inhishop`'s "closed" state.

**4d — behaviour (1-2 sessions, proposed).**
  `shk_talk` subset (the greeting, the bill total, "pay for your
  items", the "please leave" line), `nameshk`-driven `shkname` (the
  honorific and the prefix stripping), `shk_move` (the greedy pickup of
  gold `M2_GREEDY` behaviour can wait), `angry_shopkeeper`, and kops
  **deferred** (no Keystone Kop system yet).

### Phase 5 — the vault (~1 session, optional here)

`create_vault` + the `VAULT` fill branch (phase 2.4) gives the room and
the hoard. The **guard** (`src/vault.c`, 1,292 L: `invault`,
`gd_move`, `fakecorr[]`, `paygd`) is a separate system and stays out of
scope — without it a vault is "a secret room full of gold", which is
most of the fun and none of the cost.

---

## 5. Deliberate divergences

1. **No `pray.c`.** Altars are terrain + alignment; prayer, sacrifice,
   donation and wrath are not implemented. Every one of those entry
   points refuses with a message naming `src/pray.c`.
2. **No `priest_talk` service economy** (`cheapskate_count`,
   `intone_time`, `hostile_time`); the epri timers are carried as
   fields and never ticked.
3. **No shopkeeper credit** (`eshk.credit` stays 0), no repairs
   (`REPAIR_DELAY`), no robbery ledger (`robbed` is used only for the
   "you stole" decision), no kops, no `shkdead` inheritance.
4. **No `saleable`-driven shop inventory subtleties** (the health-food
   shop's `VEGETARIAN_CLASS` pseudo-class is a documented skip in 4a;
   the lighting store's zero-probability "unique" shops are
   special-level-only anyway).
5. **Containers are stocked empty** in 4a (C's `mkshobj_at` can put
   loot in a box); it lands with `mkbox_cnts` in PLAN-MKOBJ.md E.
6. **`inside_shop` is a room-number lookup**, not C's `*u.ushops`
   string of shop rooms the hero is standing in — the hero can only be
   in one square, hence one shop room; the "between two rooms" case
   cannot arise without subrooms.

---

## 6. Traps

- **`fill_special_room` is in `sp_lev.c`, not `mkroom.c`.** A session
  that greps `mkroom.c` for the room-stocking dispatcher will not find
  it and may duplicate it. Put it in `mkroom.py` *and* say so in the
  docstring, because `splev.py` (PLAN-SPLEV.md) will want to call the
  same function for `des.room({type="zoo"})`.
- **The shop needs `needfill`, and `needfill` needs `Room` to grow a
  field.** `mkzoo`/`mkshop` only *set* it; a level that is re-generated
  over an existing `Map` must reset it (`do_room_or_subroom` resets
  `rtype`, `orig_rtype`, `doors`, `sbrooms` — add `needfill` there or
  the second generation re-stocks a stale room).
- **`rtype` is zeroed when the hero enters some rooms** (C keeps
  `orig_rtype`); `pick_room` and `search_special` read `rtype`. pyhack
  already carries both — do not "simplify" `orig_rtype` away.
- **The shop draws in a different order than the room fill.** C sets
  the type during the special-room roll (early) and stocks at the very
  end; a port that stocks inside `mkshop` changes where the rng stands
  for every later room and every later level.
- **`getprice` is a *base* price.** The final price has at least four
  more multipliers in `shk.c` (`shk_buying`, `bcsign`, `surcharge`,
  `CHR` table). A test that pins "a long sword costs 10" will pin the
  wrong number; pin `getprice` and the multipliers separately.
- **Gold `quan` must be signed/`long`-safe in Python anyway**, but the
  *messages* say "1 gold piece" vs "N gold pieces" — `mkgold` merging
  into an existing pile is the only place stacking matters in this
  wave.
- **`shtypes[i].prob` sums to 100** for the eleven *rolled* rows; the
  one zero-probability row is the lighting store (special-level only).
  (§6 of the original plan said "the four zero-probability
  special-level shops" — that was a 3.6 memory; this NetHack's table
  has one, and the sentinel row is not a shop.)  The `for (j =
  rnd(100), i = 0; (j -= prob) > 0; i++)` loop silently lands on index
  0 (general store) when the roll overshoots — that is a feature, keep
  it.
- **The "Closed for inventory" sign goes OUTSIDE the shop.** C steps
  the engraving square *away* from the shop side
  (`if (inside_shop(sx + 1, sy)) m--`), i.e. into the corridor, and
  then coerces that square to ROOM / CORR if it is neither — the sign
  is for the street, not for the shop floor.  A port that engraves the
  shop floor looks reasonable and is wrong.
- **`set_tin_variety(obj, HEALTHY_TIN)` is not ported**, so a tin from
  the health-food store is an ordinary (empty) tin and an *object*-level
  `veggy_item()` check rejects it.  The stocking is right (the type is
  vegetarian); the variety field is the gap.  Same shape for the
  tribute "special spot": no tribute system means `mkspecl` is always
  false and the `rnd(stockcount)` draw is not taken.
- **Session-summary drift.** `PROGRESS_SESSION_32.md` §8 lists
  `cmap_to_type`, `save_rooms`, and a `mkundead(pos, rng)` signature
  that do not match the source. Read the span before porting.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| `_roll_special_room`'s depth ladder | `NotImplementedError` for shop/temple/swamp |
| the vault room type + hoard | STUB |
| `#pray`, `#offer`, `#pay`, `#donate` commands | non-existent |
| special levels' `des.room({type="zoo"})`, `des.altar({type="shrine"})` | PLAN-SPLEV.md |
| the shop as a *system* (`shk.c` behaviours) | this plan's 4b-4d |
| `uhitm.steal_it` (leprechaun gold theft) | needs money (PLAN-MKOBJ.md D) |

| needs | from |
|---|---|
| `makemon`, `mkclass`, `mongets`, `ndemon` | PLAN-MAKEMON.md C-E |
| `mksobj`, `mkgold`, `mkcorpstat`, `mkbox_cnts` | PLAN-MKOBJ.md B-E |
| `set_levltyp`, `mkfount/mksink/mkaltar/mkgrave`, `make_engr_at` | table item 2 + engrave subset |
| the full monster table (the zoo rows, `PM_SHOPKEEPER`, clerics) | PLAN-MAKEMON.md A |
| an 80x21 level (a level with 4 rooms cannot hold a temple *and* a shop: the roll allows one special room and needs `nroom >= 3`) | table item 5 |

**Ordering inside the plan is not negotiable:** phase 0 → 1 → 2 → 3 → 4,
because each phase is the test harness of the next (a temple proves
`makemon` + terrain + alignment; the zoo proves `fill_zoo`'s object and
gold loops; the shop reuses `makemon(MM_ESHK)`, `mksobj`, `mkgold` and
adds only prices).

---

## 8. Definition of done

- [x] `Altarmask` on tiles; `induced_align`; one live `shrine_pos` caller
- [x] a temple: shrine altar with alignment + a peaceful aligned priest
      who knows the room, `flags.has_temple` (+ the intemple message,
      the #pray / #offer refusals, tests/test_priest.py)
- [x] `fill_zoo` for all eight zoo-family types, `fill_special_room`
      dispatching (including the vault's gold), the `_roll_special_room`
      conditions complete
- [x] `mkswamp` on `set_levltyp` (+ the engraving half of phase 0: core.engrave)
- [x] shop 4a: `shtypes[]` + the name lists as data, `mkshop` claiming a
      room, `stock_room` stocking it with a named peaceful keeper (the
      door fix-up + "Closed for inventory"), `nameshk` never repeating a
      name on a level, `flags.has_shop`, `Room.resident`
      (tests/test_shop.py)
- [ ] shops 4b-4c: priced, policed; the `Pay` command; the bill model
      tested table-driven
- [x] every STUB in `core/mkroom.py`'s `__all__` either implemented or
      documented as deferred **with the C span** (only `cmap_to_type`
      is left, and it names the defsym table it waits for)
- [x] `PROGRESS`/`CHANGES.md`: a `## Wave 5: special rooms` section
      (CHANGES.md carries one section per phase)
