# Plan: Wave 5 — special rooms (temple → zoo family → shops)

**Status: phase 0's terrain half + phase 1 (temple) LANDED; phases 2-5
proposed.**  Phase 1 landed as core/priest.py (induced_align, priestini,
has_shrine / findpriest, the reduced intemple, the #pray / #offer
refusals), core.mkroom.mktemple (the C-ordered room pick + shrine altar
+ AM_SHRINE + flags.has_temple), the `Epri` extra on Monster (MM_EPRI in
makemon now allocates it), and the TEMPLE half of the room-entry hook in
core.step (C's check_special_room).  Phase 0's engraving half
(`make_engr_at` / `del_engr_at`) is still out — it blocks mkswamp and
the shop door sign.  Table.txt row 4, the `L` end of the `M→L` range:
temples and the zoo family are "room + a few lines" once PLAN-MAKEMON.md
and PLAN-MKOBJ.md exist; **shops are the expensive one**, because a shop
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
| `mkshop` | mkroom.c 94-216 | pick an unused one-door room, lit it, roll the shop type from `shtypes[]`, set `rtype = SHOPBASE + i`, `needfill = FILL_NORMAL` | `mkroom.mkshop` (STUB) |
| `mkzoo(type)` | mkroom.c 243-254 | only *claims* the room (`pick_room`, `rtype`) | `mkroom.mkzoo` (exists) |
| `fill_zoo(sroom)` | mkroom.c 275-453 | the stocking: throne + monarch, queen bee, gold, corpses, chests, graves, statues with loot, ants | `mkroom.fill_zoo` (STUB) |
| `mk_zoo_thronemon(x, y)` | mkroom.c 256-273 | gnome ruler → dwarf ruler → elven monarch → ogre tyrant by `rnd(level_difficulty())`, asleep, hostile, carrying a MACE | `mkroom.mk_zoo_thronemon` (STUB) |
| `courtmon` / `squadmon` / `morguemon` / `antholemon` / `mkundead` | mkroom.c 792 / 826 / 477 / 501 / 455 | the zoo-family monster pickers (`mkclass` + `ndemon`) | same names (STUBs) |
| `mktemple` | mkroom.c 607-630 | `pick_room(TRUE)`, `rtype = TEMPLE`, `shrine_pos`, `ALTAR` + `induced_align(80)`, `priestini`, `AM_SHRINE`, `flags.has_temple` | `mkroom.mktemple` (STUB) |
| `shrine_pos(roomno)` | mkroom.c 578-605 | the room centre, or a free square when the centre is blocked | `mkroom.shrine_pos` (exists) |
| `mkswamp` | mkroom.c 529-574 | up to 5 rooms → `POOL` on the `(sx+sy)%2` squares, eels, fungus; `flags.has_swamp` | `mkroom.mkswamp` (STUB) |
| `induced_align(pct)` | dungeon.c 2010-2025 | the level's/dungeon's alignment, else `rn2(3)-1` | `dungeon.induced_align` |
| `priestini(lvl, sroom, sx, sy, sanctum)` | priest.c 220-~300 | the priest: a 1-square ring search, `makemon(PM_ALIGNED_CLERIC, MM_EPRI)`, `epri.shrpos/shralign/shroom`, peaceful, `set_malign`, the goodies | `priest.priestini` |
| `newepri` / `EPRI` | priest.c 16 / mextra.h 95-106 | the priest extra struct (shralign, shroom, shrpos, timers) | `Monster.epri` |
| `intemple(roomno)` | priest.c 410-… | the temple-entry / peace-and-safety messages | `priest.intemple` (thin) |
| `priest_talk` | priest.c 558-… | the service/donation dialogue | **deferred** (§2.6) |
| `shkinit(shp, sroom)` | shknam.c 628-692 | `good_shopdoor`, `makemon(PM_SHOPKEEPER, MM_ESHK)`, `isshk`, `eshk.shoproom/shoptype/shd/shk`, initial capital `mkmonmoney(1000 + 30*rnd(100))`, a touchstone / charging scroll, `nameshk` | `shk.init` |
| `stock_room(shp_indx, sroom)` | shknam.c 718-801 | fix the door (no `D_NODOOR`, no trap, no secret), the "Closed for inventory" engraving on a locked door, then one `mkshobj_at` per stockable square | `shk.stock_room` |
| `mkshobj_at` / `mkveggy_at` / `get_shop_item` | shknam.c 442 / 407 / 829 | the per-square object (class, or a specific `-otyp`) | `shk.mkshobj_at` |
| `stock_room_goodpos` | shknam.c 694-716 | "not the door row, not a wall, not occupied" | `shk.stock_goodpos` |
| `shtypes[]` | shknam.c 209-357 | the 13 shop classes: name, `symb`, probability, per-class item probabilities | **data** → `core/shknam_data.py` |
| `getprice(obj, shk_buying)` | shk.c 4341-4380 | the base price and its per-class adjustments | `shk.getprice` |
| `add_one_tobill` / `billable` / `sub_one_frombill` / `alter_cost` / `stolen_value` / `paybill` | shk.c 3331 / 3473 / 3683 / 3259 / 3776 / 2507 | the bill | `shk.bill` (a *model*, §2.3) |
| `inside_shop` / `inhishop` / `costly_spot` / `onbill` | shk.c | "which shop is this square in / is this shopkeeper at home / may this cost money / is this on a bill" | `shk.inside_shop` … |
| `fill_special_room(croom)` | sp_lev.c 2732-… | the **dispatcher** called for *every* room at the end of `makelevel`: shop → `stock_room`, `VAULT` → gold per square, zoo family → `fill_zoo` | `splev.fill_special_room` (or `mkroom.fill_special_room` until sp_lev exists) |
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

### Phase 2 — the zoo family (~3 sessions)

1. `fill_zoo` in C order per type — the *gold budget* is the fiddly
   part: `goldlim = 500 * level_difficulty()` for ZOO/LEPREHALL, then
   per square `i = min(dist², goldlim)`, `rn1(i, 10)`, subtracted from
   the budget.
2. `courtmon` / `squadmon` / `morguemon` / `antholemon` / `mkundead`
   (with the **correct** `mkundead(coord, revive_corpses, mm_flags)`),
   plus `ndemon` for the morgue.
3. `mk_zoo_thronemon`; the `THRONE` terrain at the court's centre; the
   royal coffers (a chest containing `rn1(50*depth, 10)` gold, `spe=2`).
4. `fill_special_room` (sp_lev.c 2732) as the dispatcher, called from
   `mklev.makelevel` after the ordinary-room loop — including the
   `VAULT` → gold-per-square branch, which makes the vault room type
   useful before `vault.c` exists.
5. The two missing conditions in `_roll_special_room` (§2.10) and the
   `G_GONE` pre-checks.
6. Tests, one per room type: monster count per square, the throne at
   the centre and hostile monarch asleep with a mace, ZOO/LEPREHALL gold
   budget never exceeded, MORGUE has corpses/chests/graves, BEEHIVE has
   exactly one queen, ANTHOLE is single-species, every monster is
   asleep, `LevelFlags` set, and (the structural one) the room is still
   walkable.

### Phase 3 — swamp (~1 session)

`mkswamp` with `set_levltyp` (POOL), the `nexttodoor` guard, the
`del_engr_at`, the eel/piranha pick and the `mkclass(S_FUNGUS)` branch.
Tests: pools only on `(sx+sy)%2` squares, never in a doorway, eels are
in the water, `flags.has_swamp`.

### Phase 4 — shops (4a-4d, ~4-6 sessions; the `L` in `M→L`)

- **4a — a stocked room you can rob (1-2 sessions).**
  `shknam_data.py` (`shtypes[]` + the name lists + `shop_prob`),
  `mkshop` (the room picker rules: `rtype == OROOM`, no stairs, exactly
  one door, `invalid_shop_shape`), `shk.init` (`good_shopdoor`,
  `makemon(PM_SHOPKEEPER, MM_ESHK)`, `eshk` fields, initial capital,
  `nameshk`), `stock_room` + `mkshobj_at` + `stock_goodpos` (door row
  empty, everything else stocked), the door fix-up (no door → open;
  secret door → door; trapped → locked + the "Closed for inventory"
  engraving), `flags.has_shop`, `Room.resident`.
  *Exit:* a shop you can walk into, take from, and walk out of — free.
- **4b — prices (1-2 sessions).** `getprice` (the per-class
  adjustments, all of them), `bcsign` (blessed ×2 / cursed ×1/2 for
  buying, the mirror for selling), the CHA multiplier table, the
  `ushk`/`u.ushops` square tracking (`inside_shop` on every move),
  `onbill`, `billable`, `add_one_tobill`, `eshk.debit`, the `Pay`
  command (`p`), `paybill`'s "You bought …" / "You owe …" messages, and
  the total on the status line.
  *Exit:* taking stock creates a bill; paying settles it; the numbers
  match a table-driven test of `getprice` for ~20 representative
  objects.
- **4c — the shopkeeper polices it (1-2 sessions).**
  `stolen_value` on leaving the shop with unpaid goods,
  `eshk.robbed`, `surcharge`, the "You stole from me!" path,
  `alter_cost` (so `scroll of enchant armour` inside a shop adds
  `EF_PAY`), the door block (a shopkeeper stands in the doorway and
  `m_move` refuses to let him leave it), `inhishop` "closed" state.
- **4d — behaviour (~1-2 sessions).** `shk_talk` subset (the greeting,
  the bill total, "pay for your items", the "please leave" line),
  `nameshk`-driven `shkname`, `shk_move` (the greedy pickup of gold
  `M2_GREEDY` behaviour can wait), `angry_shopkeeper`, and kops
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
- **`shtypes[i].prob` sums to 100** including the four zero-probability
  special-level shops; the `for (j = rnd(100), i = 0; (j -= prob) > 0;
  i++)` loop silently lands on index 0 (general store) when the roll
  overshoots — that is a feature, keep it.
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
- [ ] `fill_zoo` for all eight zoo-family types, `fill_special_room`
      dispatching (including the vault's gold), the `_roll_special_room`
      conditions complete
- [ ] `mkswamp` on `set_levltyp`
- [ ] shops 4a-4c: stocked, priced, policed; the `Pay` command; the bill
      model tested table-driven
- [ ] `shtypes[]` + shop names as data, `nameshk` never repeating a name
      on a level
- [ ] every STUB in `core/mkroom.py`'s `__all__` either implemented or
      documented as deferred **with the C span**
- [ ] `PROGRESS`/`CHANGES.md`: a `## Wave 5: special rooms` section
