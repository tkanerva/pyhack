# Plan: Wave 6c — pack ↔ floor and pack ↔ hands (`do.c` drop, `wield.c`)

**Status: proposed, nothing implemented.** Third of the three Wave 6
documents. Needs PLAN-INVENT.md phase A (the `core/invent.py` location
functions, letters, `spe`) and nothing else to *start*; the later
phases need PLAN-INVENT D (weight) and G (`select_many`).

**Goal:** the two directions the pack is missing. **Down:** `d` / `D`
— drop one, drop several, "You cannot drop something you are wearing",
and what happens to an item when it lands. **Sideways:** `w` / `W` /
`Q` / `x` — wield a weapon, quiver one, swap the weapon set out, and
the `'A'` take-everything-off command that `core/worn.py` currently
*raises* on. Plus the one refactor PLAN-ARMOR.md deferred:
`Monster.wielded` moves onto `Item.owornmask`'s `W_WEP` bit.

**Ground truth:** `../NetHack` through `nethack_index` —
`INDEX.md` rows `src/do.c` (2,496 lines, 24k tokens, 44 functions;
pyhack coverage 11%, all of it `core/stairs.py`), `src/wield.c` (1,091
lines, 10k tokens, 26 functions; pyhack coverage 4%, all of it
`scrolls.py`'s `chwepon`). Spans from `symbols/do.json` and
`symbols/wield.json`.

---

## 1. What the C code does (reference)

### 1.1 `src/do.c` — the drop family

| C function | span | what it does | port target |
|---|---|---|---|
| `dodrop` | 28-43 | `#drop`: `getobj("drop", …)` then `drop()` | `drop.dodrop` |
| `canletgo(obj, word)` | 664-711 | the five refusals: worn armor/accessory, a **welded** cursed weapon, a cursed loadstone, a tied leash, a saddle you are sitting on | `drop.canletgo` |
| `drop(obj)` | 713-780 | `canletgo` → the corpse paranoia prompt → the sink special case (`dosinkring`) → `can_reach_floor` (levitating) → `freeinv` + `hitfloor` → `dropx` | `drop.drop` |
| `dropx(obj)` | 785-796 | `freeinv`, `ship_object` (shop), `doaltarobj` (altar: sets `bknown`), `dropy` | `drop.dropx` |
| `dropy` / `dropz(obj, impact)` | 799-803 / 806-843 | `setuwep(0)` / `setuqwep(0)` / `setuswapwep(0)` if the item was one of them, then `flooreffects` then `place_object` | `drop.dropy`, `drop.dropz` |
| `doddrop` | 923-944 | `#droptype` / `D`: `ggetobj("drop", drop, …)` or `menu_drop` — **many items in one turn** | `drop.doddrop` |
| `better_not_try_to_drop_that` | 946-962 | the "Drop the cockatrice corpse without gloves on?" paranoia prompt | `drop.better_not_try_to_drop_that` |
| `menudrop_split` / `menu_drop` | 963-977 / 980-1107 | the multi-select loop | `drop.menu_drop` (via `invent.select_many`) |
| `obj_no_longer_held` | 892-920 | the bookkeeping when the wielded / quivered / swapped weapon leaves the pack | `wield.uwepgone` & co. (§1.2) |
| `flooreffects(obj, x, y, verb)` | 161-359 | **what happens when an item lands**: pool (sink / fill), lava (destroy), altar (`doaltarobj`), sink, grave (`make_grave`), a trapdoor (`obj falls through`), a monster's feet | `drop.flooreffects` — hook only (§5.4) |
| `doaltarobj` | 362-390 | an item on an altar: `priest/profaned` / `bknown` | deferred (no altar terrain) |
| `dosinkring` | 497-661 | a ring dropped on a sink: the 12-effect ring-on-sink table | deferred (needs rings' full effects) |
| `dodown` / `doup` | 1130-1294 / 1297-1344 | **already ported** — `core/stairs.py` | — |

### 1.2 `src/wield.c` — pack ↔ hands

| C function | span | what it does | port target |
|---|---|---|---|
| `chwepon` | 922-1053 | the enchant-weapon scroll body | **already ported**: `scrolls._chwepon` |
| `welded(obj)` / `weldmsg` | 1055-1063 / 1065-1079 | "your weapon is welded to your hand" (a cursed weapon, 1/4 of the time by `chwepon`) | `wield.welded` |
| `setuwep(obj)` | 99-135 | **the single writer** of `uwep`: clear the old `W_WEP`, set the new, drop `u.twoweap` when the new weapon cannot be twoweaponed, "You are now wielding …" / "You are empty handed." | `wield.setuwep` |
| `empty_handed()` | 157-166 | the "your hands are empty" check | `wield.empty_handed` |
| `cant_wield_corpse` | 137-153 | wielding a *corpse* (a cockatrice corpse → stoning) | deferred with the corpse system |
| `wield_ok(obj)` | 335-348 | the per-weapon refusal ("You can't wield that.") | `wield.wield_ok` |
| `ready_weapon(obj)` | 168-278 | the shared unwield→wield path, the two-handed/shield check, the `afternmv` occupation hook | `wield.ready_weapon` |
| `ready_ok(obj)` | 298-332 | the dispatcher the `w`/`x`/`Q` commands use | `wield.ready_ok` |
| `dowield` | 359-462 | `w`: `getobj("wield", …)` → `ready_weapon` → the "wielding" messages | `wield.dowield` |
| `doswapweapon` | 465-506 | `x`: swap the wielded and the swap weapon | `wield.doswapweapon` |
| `dowieldquiver` / `doquiver_core` | 509-513 / 516-684 | `Q`: the quiver menu (ammo preferred, then any throwable) | `wield.doquiver_core` |
| `setuqwep` / `setuswapwep` | 280-287 / 289-294 | the writers of `uquiver` / `uswapwep` | `wield.setuqwep`, `wield.setuswapwep` |
| `wield_tool` | 687-763 | wielding a non-weapon (pick-axe, lamp, mirror): the tool-use checks | deferred (§5.5) |
| `can_twoweapon` / `set_twoweap` / `dotwoweapon` | 765-809 / 838-846 / 849-869 | `#twoweapon`: the skill + both-hands-free checks and the on/off toggle | `wield.can_twoweapon`, `wield.dotwoweapon` |
| `drop_uswapwep` / `untwoweapon` | 813-836 / 910-919 | the cleanup paths | `wield.untwoweapon` |
| `uwepgone` / `uswapwepgone` / `uqwepgone` | 877-890 / 892-899 / 901-908 | "your weapon is gone" bookkeeping (called from `dropz`/`useup`) | `wield.*gone` |

And in `worn.py`, two STUBs that raise `NotImplementedError` today:

| C function (`do_wear.c`) | what it is | today |
|---|---|---|
| `count_worn_stuff(verbose)` | count the worn pieces for `'A'` | `core/worn.py:1092` — **raises** |
| `doddoremarm()` | `'A'`: take everything off, in `takeoff_order` | `core/worn.py:1098` — **raises** |

---

## 2. Where pyhack stands

There is **no drop command at all** — `Command` has twelve members and
none of them moves an item out of the pack. There is no wield command
either: the hero's weapon is set once by `worldgen._starting_kit` and
only changes when a scroll destroys it (`scrolls._destroy_wielded`).
Two `NotImplementedError` STUBs (`count_worn_stuff`, `doddoremarm`) sit
in the module a player would reach with `'A'`, and nothing calls them,
which is the only reason the suite is green.

`Monster.wielded` is **one item id with no invariants**. Concretely:

| today | C |
|---|---|
| `worldgen` sets `hero.wielded = sword.id` | `setuwep(uwep)` sets the mask, fires `Chwepon`-adjacent effects, and drops `twoweap` |
| `scrolls._destroy_wielded` sets `mon.wielded = None` by hand | `uwepgone()` → `setuwep(0)` |
| `items.wielded_of` validates the id against the pack (a dangling id = bare hands) | C cannot have a dangling `uwep`; the invariant is the mask |
| `Item.owornmask & W_WEP` is *defined* (prop.h) and never set | it is the mechanism |
| dropping a wielded weapon (once `d` exists) would leave `wielded` pointing at a floor item | `dropz` calls `setuwep(0)` first |

PLAN-ARMOR.md decision 8 deferred the unification ("cross-cutting
refactor with no defence benefit"); PLAN-ARMOR.md §5/line 321 lists it
as explicitly-not-planned. It is cheap **now** and gets more expensive
after every wave that touches a weapon (each new `mon.wielded = …` is
another site to find), and the drop command *cannot be written
correctly* without it — that is the trigger.

---

## 3. Design decisions

1. **Two new modules, one per C file, because they are different
   subjects.** `core/drop.py` (`do.c`'s drop family) and
   `core/wield.py` (`wield.c`). `core/stairs.py` keeps `do.c`'s level
   transitions; the `do.c` provenance table in `ARCHITECTURE.md` gets
   two rows instead of one.
2. **`Monster.wielded` is deleted; `Item.owornmask & W_WEP` is the
   wielded state.** `wielded_of(world, mon)` becomes
   `worn.which_armor(world, mon, W_WEP)` — the exact call the shield and
   two-handed checks already make (`worn.py:394`), so those two paths
   stop special-casing. `setuwep` is the only writer, and it writes both
   sides of the bit (it is one bit, so there is nothing to keep in sync).
   A dangling weapon becomes unrepresentable: this is the
   "computed, never cached" rule finally applied to the hands.
   ~8 code uses and 4 test uses migrate mechanically.
3. **`DropCommand(items)` drops many items in one turn.** C's `D` is
   `ggetobj("drop", drop, 0, …)`: a loop of `drop()` calls inside one
   command, and `drop()` returns `ECMD_TIME` — the round is spent once.
   So `DropCommand(items: Tuple[Tuple[str, int], ...])` (item id +
   count) with one command = one turn, whether it carries one item or
   ten, is C-faithful *and* it keeps the console loop out of the
   simulation. `d` builds a one-element list; `D` builds several.
4. **The console becomes case-sensitive for command letters.**
   `read_command` lower-cases the whole input line, which makes C's
   `w`/`W` (wield/wear) and `d`/`D` (drop/drop-type) collide. Fix:
   `key[0]` keeps its case, the *selection* letter and the direction
   prompt stay case-insensitive. That is purely additive for every key
   already bound (all lowercase), and it lets the demo adopt C's real
   bindings: `w` wield, `W` wear (the demo's `w` meaning moves — a
   documented behaviour change), `T` take off (lowercase `t` stays as
   an alias so the existing console tests keep passing), `d`/`D` drop,
   `Q` quiver, `x` swap (currently `x` closes a door — the door close
   moves to `c`, which is C's own key, and casting moves to `Z`, since
   `z` already zaps). `main.py`'s help text is rewritten in this phase;
   `tests/test_console.py` gains a keymap test asserting every binding
   in one table.
5. **`canletgo` is the drop gate, ported whole except the leash and
   saddle** — worn armor/accessory, the welded cursed weapon (needs
   `wield.welded`), the cursed loadstone. Leash and saddle do not exist
   in the port.
6. **`drop` reuses the two existing checkers instead of inventing a
   third.** "Can I reach the floor" is `pickup.able_to_loot`'s
   predicate (PLAN-PICKUP phase C); "is it worn" is
   `worn.is_worn`/`canletgo`. A dropped item goes `freeinv` → `dropz` →
   `place_object`, in that order, so the invariants PLAN-INVENT phase A
   asserts hold at every intermediate point.
7. **`flooreffects` lands as a dispatcher with an empty registry.** The
   C function is 200 lines because it knows about pools, lava, altars,
   sinks, graves, trapdoors and a monster's feet — none of which the
   demo can generate. The port is `FLOOR_EFFECTS: Dict[TerrainType,
   Callable]`, with a comment naming each unported branch and its span,
   and **no entries** — the registry *shape* is landed so that
   `set_levltyp` + fountains (PLAN-MKOBJ phase G) can fill it without
   touching `drop.py`. A dropped item on plain floor therefore renders
   "You drop the X." and lands; that is the whole observable behaviour
   today.
8. **Wielding is one turn and instantaneous** (no `oc_delay`
   occupation) — the same house rule as donning (`worn.py` docstring).
   `ready_weapon`'s `afternmv`/`nomul` bookkeeping is not modelled.
9. **Quiver and swap-weapon are state, not behaviour.** `setuqwep` /
   `setuswapwep` set their masks and `doswapweapon` exchanges them;
   the *throwing* system (which reads `uquiver`) is a later wave, and so
   is the off-hand attack (which reads `u.twoweap`). Landing the state
   machine now means the throwing/combat waves have nothing to invent.
10. **Two-weapon is the state toggle only.** `can_twoweapon` checks
    `Skill.P_TWO_WEAPON_COMBAT`, a weapon in each hand, and the
    `W_ARMS`/`bimanual` conflicts; `dotwoweapon` toggles a
    `Monster.twoweap: bool`. `uhitm` keeps swinging one weapon
    (§5.6) — the second attack is a combat-wave change.
11. **`'A'` take-off-all is filled in, in `worn.py`, in `takeoff_order`.**
    The two STUBs raise today; a player who presses the key the help
    text will advertise gets a traceback. `count_worn_stuff` +
    `doddoremarm` are 40 lines of loop over C's order
    (`do_wear.c:17-21`: `W_WEP`, shield, gloves, left ring, right ring,
    cloak, helmet, amulet, suit, shirt, boots, swap weapon, quiver —
    C's leading `WORN_BLINDF` is dropped, the port has no blindfold
    slot), each step a `dotakeoff`. C charges one turn for the command
    and loops; keep that.

---

## 4. Phases

### Phase A — the drop core (~1 session)

*Needs PLAN-INVENT A, and **phase C's `setuwep`** — `dropz` clears the
three weapon masks, which is `setuwep(None)` / `setuqwep(None)` /
`setuswapwep(None)`. In practice phase C is implemented first (it needs
nothing but PLAN-INVENT A) even though it is written here second; the
letters below are the C call order, not the commit order.*

1. `core/drop.py`: `canletgo`, `drop`, `dropx`, `dropy`, `dropz` with
   the C spans in the docstrings.
2. `DropCommand(item_id, count=0)` + `step` wiring + the `d<letter>`
   key. The count prefix splits a stack (`invent.splittable`) and the
   remainder stays in the pack.
3. `drop.better_not_try_to_drop_that`: the corpse paranoia prompt is a
   UI question, so the core takes `force: bool` — a `Command` field the
   console fills in. The refusal path is testable without a prompt.
4. Tests: drop the wielded sword → the hands are empty (the `W_WEP`
   bit is clear) and it is on the floor at the hero's feet; drop the
   worn cloak → refused, "You cannot drop something you are wearing.";
   drop half an arrow stack → 5 on the floor, 5 carried.

**Exit:** `d` works, the location invariant holds after every branch,
and dropping the wielded weapon cannot leave a dangling id.

### Phase B — drop several (~1 session)

*Needs PLAN-INVENT G (`select_many`).*

1. `doddrop` / `menu_drop`: the multi-select loop, one turn for the
   whole batch, one message per item.
2. `D` + the console's confirmation loop; a `,`-style "everything"
   selector for the tests.
3. Tests: drop three items in one command → one turn elapsed
   (`world.turn`), three floor items, three messages; a batch that
   contains a worn item drops the rest and refuses that one.

**Exit:** `D` drops a batch in a single turn, and `world.turn`
advances by exactly one.

### Phase C — wielding (~1.5 sessions)

*Needs PLAN-INVENT A only; this is the `W_WEP` refactor. Implement it
before phase A (see that phase's note).*

1. `core/wield.py`: `setuwep`, `welded`, `weldmsg`, `empty_handed`,
   `wield_ok`, `ready_weapon`, `ready_ok`, `uwepgone` /
   `uswapwepgone` / `uqwepgone`, `setuqwep`, `setuswapwep`.
2. Delete `Monster.wielded`; `items.wielded_of` delegates to
   `worn.which_armor(world, mon, W_WEP)`; migrate `worldgen`,
   `scrolls._destroy_wielded`, `ui/console.py:211`, `worn.py:394`,
   `uhitm.py:281` and the four tests.
3. `WieldCommand(item_id)` + `w<letter>`; `w` with no letter = unwield
   ("You are empty handed.").
4. The two-handed/shield refusal already in `worn.can_wear` moves to
   `wield.wield_ok` where C has it (one place, both callers).
5. Tests: wield the two-handed sword with a shield on → refused; the
   bit is on the item, not the monster; destroy the wielded weapon →
   the hands are empty and the mask is clear.

**Exit:** `grep -n "\.wielded"` finds no assignment outside
`wield.setuwep`; every existing weapon test passes with only the
accessor changed.

### Phase D — quiver and swap (~1 session)

1. `doquiver_core` / `dowieldquiver`: the ammo-first preference, the
   `Q<letter>` key, "You now have 15 arrows in your quiver."
2. `doswapweapon` (`x`): exchange `W_WEP` and `W_SWAPWEP`; the "you
   have no alternate weapon" case.
3. `drop_uswapwep` — dropping the swapped weapon clears the mask (it
   comes free from `dropz`, so this phase is a test, not code).
4. Tests: swap with no alternate weapon; drop the quivered stack;
   quiver something non-throwable (refused).

**Exit:** the three weapon masks (`W_WEP`, `W_SWAPWEP`, `W_QUIVER`) are
mutually consistent and each has one writer.

### Phase E — two-weapon state (~0.5 session)

1. `Monster.twoweap: bool` (C `u.twoweap`), `can_twoweapon`,
   `set_twoweap`, `dotwoweapon`, `untwoweapon`, and
   `#twoweapon` on `X` (no extended commands; a key is needed).
2. `setuwep` clears `twoweap` when the new weapon cannot be
   twoweaponed — that is the one cross-coupling, and it is C's.
3. Tests: the skill gate, the shield/bimanual gate, and "wielding a
   non-twoweaponable weapon turns two-weapon off".

**Exit:** the state machine toggles and nothing in `uhitm` changed
(§5.6 — the off-hand attack is deliberately not here).

### Phase F — `'A'` take-off-all (~1 session)

1. `worn.takeoff_order` (the C constant), `count_worn_stuff`,
   `doddoremarm` — the two `NotImplementedError` STUBs become real.
2. `worn.inaccessible_equipment` (the other raise) either lands with
   its swallow check or is replaced by a `True`-returning named
   predicate with a comment, so `'A'` never raises.
3. `TakeOffAllCommand` + `A`. One turn.
4. Tests: wear four pieces, `A` takes off four, one turn; a cursed
   cloak stops the loop at that item with C's message ("You can't take
   that off."), the rest still come off (C's `doddoremarm` order does
   not abort).

**Exit:** no `NotImplementedError` reachable from a keypress in
`worn.py`; `'A'` documented in `main.py`'s help.

### Phase G — the floor-effect hook (~0.5 session)

1. `drop.flooreffects` with the `FLOOR_EFFECTS` registry (decision 7):
   the dispatcher, the "obj not free" precondition, and the named
   branches with spans.
2. `doaltarobj` as a one-line entry once altar terrain exists
   (PLAN-MKOBJ phase G) — until then the registry is empty and the
   function returns `False` ("nothing special happened").
3. Tests: dropping onto plain floor calls the dispatcher and places the
   item; a fake registry entry (a test-only `TerrainType`) is invoked
   once and only once.

**Exit:** `flooreffects` exists, is called from `dropz`, and a later
wave can fill it without editing `drop.py`.

---

## 5. Deliberate divergences

1. **No `hitfloor`, no levitation.** `drop`'s `can_reach_floor` branch
   ("you drop it, but it does not reach the floor") needs levitation;
   when `able_to_loot`'s predicate says the floor is out of reach the
   drop is refused instead.
2. **No shop interaction.** `dropx`'s `ship_object` and `drop`'s
   `sellobj_state(SELL_DELIBERATE)` are PLAN-SPECIAL-ROOMS phase 4b;
   dropping an `unpaid` item in a shop is a normal drop until then.
3. **No `dosinkring`, no `trycall`, no `boulder_hits_pool`.** Sinks,
   naming and boulders do not exist; a boulder is a `ROCK`-class item
   with no special drop behaviour.
4. **`flooreffects` is a registry with no entries** (§4 G). Pool / lava
   / altar / sink / grave / trapdoor / "lands on a monster's head" are
   named, spanned, and unported.
5. **No `wield_tool`.** Wielding a pick-axe or a lamp has tool
   semantics (`apply.c`) that do not exist; `wield_ok` refuses a
   non-weapon with C's message instead of allowing it.
6. **No off-hand attack.** `can_twoweapon`/`dotwoweapon` change state;
   `uhitm` still makes one attack. C's second swing, the -1/-3 to-hit
   penalties (`twoweapon`'s skill table) and `bimanual`'s damage bonus
   are the combat wave's.
7. **No `afternmv` occupation.** Wielding is instantaneous (decision
   8); the `nomul` bookkeeping in `ready_weapon` is not modelled.
8. **`w` changes meaning.** The demo bound `w<letter>` to *wear*;
   after this wave `w` is C's wield and `W`/`T` are wear/take-off. The
   lowercase `t` alias keeps the old take-off tests intact, but any
   documented `w<letter> wear` in `main.py` and `README.md` must change
   — that is a user-visible break and it is deliberate.

---

## 6. Traps

- **`dropz` ordering.** C empties the weapon slots *before*
  `flooreffects` and `place_object` on purpose: `place_object` can fire
  an altar's `bknown`, a shop's billing, or a `useup`. In pyhack the
  invariant is clearer — `freeinv` (out of the pack) → clear the §3
  masks → `place_object` (onto the floor) — but a phase that calls
  `place_object` first and `freeinv` second leaves a window where the
  item is in `world.items` twice-addressable (the test invariant will
  catch it).
- **`DropCommand` must be a snapshot.** `Tuple[Tuple[str, int], ...]`,
  not a live list of `Item`s: a `useup` inside `drop()` (a stack
  dropping to zero) must not invalidate the loop. Same rule as
  PLAN-PICKUP's `,` loop.
- **Dropping the worn ring.** `canletgo` refuses `W_ARMOR |
  W_ACCESSORY`, both bits; a phase that checks only `W_ARMOR` lets the
  amulet hit the floor while still counting toward `uac`.
- **The `W_WEP` migration touches the pinned tests.**
  `test_worn.py:358/364` and `test_uhitm.py:134` set
  `hero.wielded = …` by hand; they become `setuwep`. A grep for
  `wielded` must reach zero assignments before phase C is done, or a
  later wave will resurrect the field.
- **`setuwep` is called from `dropz`, `uwepgone`, `useup`, the scroll,
  and the command** — five callers, one writer. Any caller that sets
  the mask itself creates the second mechanism the whole decision
  exists to prevent.
- **`'A'` and the cursed cloak.** C's `doddoremarm` does *not* abort on
  a cursed item; it reports and continues. An implementation that
  returns early leaves the boots on with no message, which looks like a
  bug in the boots.
- **`w`/`W` and the console's `.lower()`.** `read_command` currently
  lower-cases *before* comparing to `ARROWS`, whose escape sequences
  are lower (`"\x1b[a"`). Changing the case handling must not break the
  arrow keys — that is a bug the project already fixed once
  (ARCHITECTURE.md, "Arrow keys never worked").
- **`x` is taken twice.** Today `x` + direction closes a door; C uses
  `x` for swap-weapons and `c` for close. Moving close to `c` means
  moving cast off `c` — pick the new key once, in decision 4, and
  update `main.py`, `ui/console.py` and `tests/test_console.py` in the
  same commit.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| `d` / `D` — items can leave the pack | impossible |
| the wielded weapon as a real slot | one unvalidated string |
| `x` / `Q` — swap weapon, quiver | absent |
| `'A'` take-off-all | two `NotImplementedError`s |
| `#twoweapon` state | absent |
| PLAN-PICKUP's `able_to_loot` reaching its own square | only used by looting |
| `flooreffects` for the terrain waves (water, altars, graves) | nothing to hook into |
| the throwing wave (`dothrow.c` reads `uquiver`, `uswapwep`) | those fields did not exist |
| the shop's "drop it on the floor and leave" theft path | needs `dropx`'s hook |

| needs | from |
|---|---|
| `freeinv` / `place_object` / `useup` / `invlet` | PLAN-INVENT A |
| `xname` / `doname` / `the` / `singular` | PLAN-INVENT C (every drop message) |
| `splittable` / `adjust_split` (drop half a stack) | PLAN-INVENT B / G |
| `select_many` | PLAN-INVENT G |
| `near_capacity` (C's "you are not strong enough to wield that") | PLAN-INVENT D |
| `takeoff_order`'s per-type side effects | the property system (PLAN-ARMOR §5) |
| `flooreffects`' entries | terrain: `set_levltyp` + fountains/altars/graves (PLAN-MKOBJ G), water (future) |
| `wield_tool` | `apply.c` (unported) |
| the corpse system (`cant_wield_corpse`, the paranoia prompt's stoning) | PLAN-MAKEMON F |

---

## 8. Definition of done

- [ ] `core/drop.py` and `core/wield.py` exist with C spans in the
      docstrings
- [ ] `Monster.wielded` is gone; `W_WEP` is the wielded state and
      `setuwep` its only writer
- [ ] `d` drops one, `D` drops a batch in one turn; `canletgo`'s
      refusals are ported and tested
- [ ] dropping the wielded / quivered / swapped item clears its mask
- [ ] `w` / `W` / `T` / `Q` / `x` are bound to C's commands; the
      console keymap is case-sensitive and has a table test
- [ ] `wield_ok` / `ready_weapon` / `ready_ok` / `dowield` /
      `doswapweapon` / `doquiver_core` ported
- [ ] `can_twoweapon` / `dotwoweapon` toggle `Monster.twoweap`;
      `uhitm` unchanged
- [ ] `count_worn_stuff` / `doddoremarm` / `'A'` implemented; no
      `NotImplementedError` reachable from `worn.py`
- [ ] `flooreffects` registry in place, empty, with every branch named
      and spanned
- [ ] the location invariant and the "one writer per mask" invariant
      are asserted in the suites that touch them
- [ ] `mypy` clean, `flake8` clean, the suite green
- [ ] `main.py`'s help text, `README.md`'s key list, `ARCHITECTURE.md`'s
      `do.c`/`wield.c` rows and `CHANGES.md` updated in the same wave
