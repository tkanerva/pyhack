# Plan: Wave 7 — throwing and shooting (`dothrow.c` + `mthrowu.c`)

**Status: proposed, nothing implemented.** The hero cannot throw
anything and no monster can throw anything at the hero. `INDEX.md` rows:
`src/dothrow.c` 2,793 lines / 27k tokens / 39 functions / pyhack state
`none` (0%); `src/mthrowu.c` 1,561 lines / 15k tokens / 28 functions /
state `none` (0%). Baseline: 521 tests green, mypy clean.

**Goal:** the two halves of one mechanic. **The hero** throws (`t`) and
shoots a launcher (`f`): a stack splits, a volley leaves the pack, the
projectile walks a line of tiles, stops at a wall / a monster / the edge
of its range, resolves a hit that is *not* melee, breaks sometimes, and
lands on the floor where it can be picked up again. **Monsters** do the
same back (`thrwmu` → `monshoot` → `m_throw` → `thitu`), which is the
first monster behaviour in the port that reaches beyond `distmin == 1`.
Both halves need the same three things pyhack does not have: an item
that can leave a stack and come back to the floor, a flight path, and a
hit resolution that reads range and a mobile target.

**Ground truth:** `../NetHack` through `nethack_index`. Spans from
`symbols/dothrow.json` and `symbols/mthrowu.json`; the hero's flight
walker is `zap.c#bhit` (`symbols/zap.json`, span 3840-4153) — it lives
in `zap.c`, not in `dothrow.c`, and that is the reason
`core/bhit.py` exists in §3.1. Never read either `src/` file whole.

---

## 1. What the C code does (reference)

### 1.1 `src/dothrow.c` — the hero throws (39 functions)

| C function | span | what it does | port target |
|---|---|---|---|
| `dothrow` | 351-376 | `#throw`: `ok_to_throw` → `getobj("throw", throw_ok)` → `throw_obj` | `throw.dothrow` |
| `ok_to_throw` | 296-313 | the two refusals (`notake` / `nohands`) + the encumbrance check + the count prefix (`shotlimit`) | `throw.ok_to_throw` |
| `throw_ok` | 316-348 | the `getobj` filter: weapons / coins / ammo-with-launcher / boulders suggest, the wielded item down-plays | `throw.throw_ok` (a *filter*, the console picks) |
| `throw_obj` | 86-293 | **the entry**: direction, the gold branch, the five refusals (`canletgo`, welded, too heavy, self), the multishot computation, the volley loop `splitobj` → `freeinv` → `throwit` | `throw.throw_obj` |
| `multishot_class_bonus` | 38-83 | the per-role volley bonus (cave dweller / monk / ranger / rogue / ninja / samurai) | `throw.multishot_class_bonus` (data) |
| `throwit` | 1510-1905 | **the flight**: the cursed/greased slip roll, the stamina drop, the `dz` split (`toss_up` up / `hitfloor` down), the range from strength and weight, `bhit`, the return-to-hand branch, breakage, landing | `throw.throwit` |
| `throwit_mon_hit` | 1482-1507 | the "the missile reached a monster" hand-off to `thitmonst` | `throw.throwit_mon_hit` |
| `thitmonst` | 2066-2362 | **the projectile hit**: the to-hit (`-1 + Luck + find_mac + uhitinc + ulevel + dex + distance`), the ammo / launcher / throwing-weapon adjustments, the per-`otyp` damage branches, `hmon`, `should_mulch_missile` | `throw.thitmonst` |
| `tmiss` | 2006-2023 | "the X misses" (+ wake the target) | `throw.tmiss` |
| `omon_adj` | 1968-2003 | the monster's closeness / sleep / `M_AP` adjustments to the thrower's to-hit | `throw.omon_adj` |
| `throwing_weapon` | 1429-1438 | "is this `otyp` a weapon meant to be thrown?" (dart, shuriken, spear, …) — the `+2`/`-2` to-hit choice | `weapon.throwing_weapon` |
| `should_mulch_missile` | 2031-2058 | whether a *hit* missile is used up (ammo / missile, erosion- and `spe`-scaled, blessed survives, hard gems resist) | `throw.should_mulch_missile` |
| `endmultishot` | 589-601 | the "you stop shooting" early-cancel message | `throw.endmultishot` |
| `autoquiver` | 380-442 | `f` with an empty quiver: pick the best ammo / throwable and ready it | `throw.autoquiver` |
| `find_launcher` | 446-465 | find a launcher for a piece of ammo in the pack | `throw.find_launcher` |
| `dofire` | 468-586 | `#fire`: the quiver, auto-quiver, `fireassist` (auto-wield the launcher, auto-swap) and then `throw_obj` | `throw.dofire` |
| `throwit_return` | 1460-1466 | the `gt.thrownobj` cleanup at every `throwit` exit | folded into `throw.throwit`'s return (§3.4) |
| `return_throw_to_inv` | 1910-1965 | a throw-and-return missile arriving in the pack (re-wield, re-quiver) | `throw.return_throw_to_inv` |
| `sho_obj_return_to_u` | 1442-1458 | the display-only return flight | no-op (`ui` has no animation) |
| `toss_up` | 1255-1426 | `dz < 0`: the ceiling, the egg / potion / boomerang specials, `monster_yields` | `throw.toss_up` |
| `hitfloor` | 605-647 | `dz > 0`: throw at your own feet (altar / sink / `hero_breaks` / `dropz`) | `throw.hitfloor` |
| `breakobj` | 2537-2632 | **the break**: first the *crackable* armour (`is_crackable` → `erode_obj(…, ERODE_CRACK)`, i.e. the already-ported `worn.erode_obj`), then mirrors (Luck −2), all potions (oil explodes, otherwise `potionbreathe`), eggs (Luck, pyrolysk explodes), boulders / statues (shop only); everything else is `delobj` | `throw.breakobj` (+ a `BREAK_EFFECTS` registry) |
| `breaktest` | 2639-2667 | will it break at all: glass material, potions, egg, cream pie, melon, both venoms, camera | `throw.breaktest` |
| `breakmsg` | 2669-2711 | the "the potion shatters!" / "the egg splatters" lines | `throw.breakmsg` |
| `hero_breaks` | 2474-2494 | break-on-the-floor with the shop-ownership branch folded in | `throw.hero_breaks` |
| `breaks` | 2501-2512 | the caller-side wrapper over `breakobj` | `throw.breaks` |
| `harmless_missile` | 1219-1248 | "this object cannot hurt anything when it lands" (sling, leaf, scroll, cloth, empty bag) | `throw.harmless_missile` |
| `throw_gold` | 2713-2789 | throwing coins: the whole pile, or one coin from the quiver; the leprechaun bribe | `throw.throw_gold` |
| `walk_path` | 655-735 | "walk from A to B calling a proc at each square" — the *knockback* walker | deferred with `hurtle` (§5.2) |
| `hurtle_jump` / `hurtle_step` / `will_hurtle` / `mhurtle_step` / `hurtle` / `mhurtle` | 741-752 / 772-972 / 976-989 / 991-1068 / 1077-1126 / 1129-1178 | knockback (force bolt, explosions, throne) | deferred — `zap.c`/`explode.c`'s wave (§5.2) |
| `check_shop_obj` | 1180-1214 | billing for a thrown item | deferred — shops (§5.3) |
| `swallowit` | 1468-1476 | the missile vanishes into the swallower | deferred — no swallow (§5.4) |
| `gem_accept` | 2366-2440 | a gem thrown at a co-aligned unicorn | deferred — no unicorns in the subset (§5.5) |
| `release_camera_demon` | 2514-2528 | a broken camera frees a demon | deferred — `apply.c` (§5.6) |

### 1.2 `src/mthrowu.c` — monsters throw (28 functions)

| C function | span | what it does | port target |
|---|---|---|---|
| `thrwmu` | 1173-1264 | **the monster's decision**: wield if needed, `select_rwep`, the polearm thrust, the throw-and-return range, `lined_up`, the "hero is retreating" roll, `monshoot` | `mthrowu.thrwmu` |
| `monshoot` | 261-314 | the "the orc throws a dagger!" line and the **multishot loop** (`m_shot.i = 1..n`) | `mthrowu.monshoot` |
| `monmulti` | 200-258 | the monster's volley count (lord / prince / mplayer, elven gear, launcher `spe`, `rnd`) | `mthrowu.monmulti` |
| `m_throw` | 571-845 | **the flight** for everyone who is not the hero: the `splitobj`, the slip roll, `MT_FLIGHTCHECK` (edge / wall / closed door / bars), the per-tile monster check, the hero branch, `thitu`, `drop_throw` | `mthrowu.m_throw` |
| `thitu` | 74-155 | **the hero is hit**: `u.uac + tlev <= rnd(20)` → miss / "almost hit", else `losehp`; acid venom, silver, potion, egg specials | `mthrowu.thitu` |
| `drop_throw` | 161-196 | the landing: break (pie / venom / hit egg / mulch), `flooreffects`, `place_object`, `passive_obj`, `stackobj` | `mthrowu.drop_throw` |
| `m_useup` | 1161-1170 | `quan--` or `m_useupall` | `mthrowu.m_useup` |
| `m_useupall` | 1153-1158 | remove from `minvent` + free | `mthrowu.m_useupall` |
| `m_carrying` | 1404-1414 | "does this monster carry that `otyp`?" | `mthrowu.m_carrying` |
| `m_has_launcher_and_ammo` | 57-70 | the wielded weapon is a launcher *and* the pack has matching ammo | `mthrowu.m_has_launcher_and_ammo` |
| `linedup` | 1329-1373 | the straight / diagonal line test from the monster to the hero, `BOLT_LIM`, a walk over `blocking_terrain` | `mthrowu.linedup` |
| `linedup_callback` | 1294-1327 | the walker: sets `gt.tbx/tby` (the direction), checks terrain, calls the per-square predicate | `mthrowu.linedup_callback` |
| `m_lined_up` | 1375-1393 | `linedup(mtarg, mtmp, …)` — is this monster lined up with that target | `mthrowu.m_lined_up` |
| `lined_up` | 1397-1401 | `linedup(&youmonst, mtmp, …)` | `mthrowu.lined_up` |
| `blocking_terrain` | 1281-1288 | wall / closed door / bars block a thrown line | `mthrowu.blocking_terrain` |
| `spitmu` | 1267-1271 | `spitmm(mtmp, mattk, &youmonst)` | `mthrowu.spitmu` |
| `spitmm` | 1015-1077 | spit venom: `mksobj(BLINDING_VENOM / ACID_VENOM)` + the `rn2(BOLT_LIM - dist)` gate + `m_throw` — the *hero-target half only* | `mthrowu.spitmm` |
| `ohitmon` | 320-502 | a thrown object hits a **monster** (monster-vs-monster) | deferred — `mhitm.c` wave (§5.7) |
| `thrwmm` | 968-1012 | monster throws at a monster | deferred with `ohitmon` |
| `return_from_mtoss` | 849-965 | the monster's tether/aklys return flight | deferred (§5.8) |
| `ucatchgem` / `u_catch_thrown_obj` | 505-529 / 532-550 | the hero *catches* a thrown gem / object (needs a free hand, a polymorphed hero) | deferred (§5.9) |
| `hit_bars` / `hits_bars` | 1416-1495 / 1498-1559 | iron bars stop / break a missile | deferred — no `IRONBARS` terrain is ever generated (§5.10) |
| `breamm` / `breathwep_name` / `breamu` / `rnd_hallublast` | 1092-1150 / 1082-1089 / 1274-1278 / 51-55 | **breath weapons** — `dobuzz(BZ_M_BREATH(...))`, i.e. the `zap.c` beam engine with a monster breather | **not this plan** (§5.11) |

Seventeen of the 28 are in scope, 28 of 39 in `dothrow.c`. The eleven
deferred functions are named so that nobody re-decides them, and each
has the wave that owns it.

### 1.3 The walker that is in neither file

`throwit` does **not** walk the line itself: it calls `bhit()` in
`zap.c` (span 3840-4153, 313 lines) with `THROWN_WEAPON`, the range and
an object pointer, and `bhit` returns the monster it stopped at (or
`NULL`) with `gb.bhitpos` left on the last legal square. `bhit` is where
"thrown things stop at" lives: the map edge, water walls, iron bars,
webs, sinks, closed doors, the `ZAP_POS` test, and the "it passes a
shade / a monster pretending to be an object" cases.

pyhack has a *degenerate* cousin of it — `rules.find_target_in_line`
(straight line, first monster, wall = stop, no landing position, no
range from weight) used by the beam engine. It is not enough for
throwing (a thrown object must be able to stop in empty air and land
there, and it may pass *over* things `find_target_in_line` stops at),
and it is too little for the day `zap.c` grows `bhit`'s terrain cases.
Hence `core/bhit.py` (§3.1) — one reduced walker, two callers.

### 1.4 Data and machinery that already exist in pyhack

| exists | where | used by |
|---|---|---|
| `is_ammo` / `is_launcher` / `is_missile` / `is_multigen` / `matching_launcher` / `ammo_and_launcher` / `greatest_erosion` / `weapon_type` | `core/weapon.py` | `throw_ok`, `multishot`, `thitmonst`, `monmulti` |
| `dmgval(otmp, pm, rng)` / `hitval` / `weapon_hit_bonus` / `uwep_skill_type` / `abon` | `core/weapon.py` | the projectile damage and to-hit |
| `RWERP` / `PWERP` / `HWEP` / `ARWEP` / `BOLT_LIM` / `AKLYS_LIM` / `autoreturn_weapon` / `monmightthrowwep` | `core/weapon.py` 1202-1279 | `select_rwep`, `thrwmu`, `monmulti` |
| `Skills` / `P_SKILLED` / `Skill.P_BOW` … | `core/weapon.py` | the multishot skill switch |
| the 480-row object table with `wsdam` / `wldam` / `weight` / `material` / `prob` / `skill` | `core/objects*.py` | every damage and range number |
| `AT_WEAP` / `AT_SPIT` / `getmattk` / `distance_atk_type` / `attacktype` / `NATTK` | `core/monst*.py`, `core/mondata.py` | the `mattacku` dispatch |
| `DamageEvent` + `rules.apply_damage` + `process_events` | `core/events.py`, `core/rules.py` | every projectile hit |
| `apply_poison` / `put_to_sleep` / `apply_blind` | `core/rules.py` | poisoned ammo, blinding venom |
| `W_WEP` / `W_QUIVER` / `W_SWAPWEP` + `worn.which_armor(world, mon, mask)` | `core/objects_defs.py` 303-321, `core/worn.py:243` | "which weapon is this monster wielding" (`MON_WEP`) |
| `distmin` / `dist2` / `sgn` / `online2` | `core/hacklib.py` 172-195 | range, `arw->range`, `linedup` |
| `occupation.start_occupation` / `run_occupation` | `core/occupation.py` | `stop_occupation` is **missing** (§2.6) |
| `_ask_direction` | `ui/console.py:40` | the direction prompt |

---

## 2. Where pyhack stands

### 2.1 Nothing throws

`Command` has twelve members and none of them is a throw;
`step` has no branch that could reach one; `core/` has no module that
mentions a trajectory. The demo carries exactly one throwable weapon
(`weapon_0`, a dagger on the floor at (18,10)) and one wielded weapon
(`sword_0`), and neither can leave the pack.

### 2.2 An item cannot leave a stack, because there are no stacks

`types.Item` has `charges`, `spe` and no weight, and **no `quan`** (it
is PLAN-MKOBJ phase A / PLAN-INVENT phase A work, not yet landed). C's
`throw_obj` splits *one* object off the stack (`splitobj(obj, 1L)`) and
throws the copy; a port that throws "the item" without a stack model can
never shoot two arrows, and `should_mulch_missile`'s whole point
("ammo must stay around on average") is about stacks.

### 2.3 Nothing can put an item back on the floor

The only writer of `Item.pos` today is `worldgen` at construction; a
thrown object has no legal way home. `invent.place_object` is
PLAN-INVENT phase A; the throw path is its second caller after drop.

### 2.4 The hero's weapon is a raw id string

`Monster.wielded: Optional[str]` with `items.wielded_of` validating it
by hand. Throwing the wielded weapon must clear that slot **once**
(C `setuwep(0)`); a throw path that leaves `hero.wielded` pointing at a
floor item is the exact bug PLAN-DROP decision 2 exists to make
unrepresentable. PLAN-DROP phase C owns that refactor.

### 2.5 Monsters have no weapons and no ammo

`Monster.inventory` exists and `worn.which_armor` already scans it for
every actor, but nothing ever fills a monster's pack: `demo_monster`
leaves it empty, and there is no `makemon` (PLAN-MAKEMON) with
`m_initweap` / `m_initthrow`. So `thrwmu` can be written today and will
have nothing to throw until PLAN-MAKEMON phase E. That is acceptable —
but it means phase G needs a test that *fills* a pack by hand, and the
demo's own monsters stay unarmed (which is also what keeps the pinned
seed honest, §6.2).

### 2.6 `occupation` has no `stop_occupation`, and `m_throw` needs it

`core/occupation.py` (currently a placeholder reconstruction) has
`start_occupation` and `run_occupation` but **not** `stop_occupation`
(C `allmain.c#stop_occupation` 691-703). Every C path that interrupts a
long task calls it — including `m_throw` (mthrowu.c:786, "your meal is
interrupted by an incoming dart") and `thrwmu` (mthrowu.c:1239/1263,
`nomul(0)`). One more thing the missing `stop_occupation` costs: the
placeholder's `run_occupation` *discards* the events the interrupted
generator returns (`gen.throw(OccupationStopped())` inside
`except StopIteration: pass`), so C's "You stop eating." line and any
reset dialogue are currently lost. Phase 0 lands the ten-line helper;
the throwing wave is its first caller.

### 2.7 The key `t` is take-off, and `f` is unbound

`ui/console.py:96` binds `t<letter>` to `TakeOffCommand`; PLAN-DROP
decision 4 keeps lowercase `t` as a take-off alias. C's `t` is *throw*.
One of the two has to give and it should be the alias (§3.8).

### 2.8 The projectile needs a `PerMonst` for the hero, and there isn't one

`m_throw`'s damage is `dmgval(singleobj, &gy.youmonst)`; pyhack's
`weapon.dmgval` takes a `PerMonst`, and `MONS[PM_HUMAN]` is `None` — the
monster table is a sparse subset (`monst_data.py:218` allocates `None`s,
only some rows are filled) and the hero's row was never one of them
(`worldgen._make_hero` hard-codes `ac` and `damage` instead). §3.9.

---

## 3. Design decisions

1. **Three modules, split where C splits them.**
   `core/throw.py` = `dothrow.c` (the hero), `core/mthrowu.py` =
   `mthrowu.c` (the monsters), `core/bhit.py` = `zap.c#bhit` (the
   walker both the hero's flight and, later, the beams use). The
   `core/mhitu.py` / `core/uhitm.py` precedent (a module per C file,
   named after it) is what makes the provenance table in the docstring
   readable, and the alternative — one `combat_projectiles.py` — would
   merge a 39-function file with a 28-function file that only share a
   data structure.
2. **`core/bhit.py` is a reduced `bhit`, and it is a *walker*, not a
   resolver.** C's signature is `bhit(dx, dy, range, type, fhitm,
   fhito, &obj)` returning the monster it stopped at; the port keeps
   the shape with the two call sites we have
   (`BhitType.THROWN_WEAPON`, `BhitType.THROWN_TETHERED_WEAPON`) and
   drops the `fhitm`/`fhito` callbacks entirely — pyhack has one
   object-in-flight at a time, and the caller knows what it threw. It
   returns a `Flight` value (§3.4), never mutates.
3. **The projectile is one `Item` with `quan == 1`, split off the
   stack.** `mkobj.splitobj` / `unsplitobj` (spans `mkobj.c#splitobj`
   456-503, `#unsplitobj` 555-622) land **here**, because PLAN-MKOBJ
   §3.6 deferred them and named this wave as the owner ("throwing one
   dart out of ten"). Rule inherited from PLAN-MKOBJ: `splitobj` is the
   only writer of `quan` outside `mksobj_init`.
4. **No `gt.thrownobj` global: a `Flight` value.** C carries the
   in-flight object in a global that `drop_throw`, `breakobj`,
   `passive_obj` and `return_throw_to_inv` all read. pyhack has no
   globals, so the object travels as a parameter and the walker returns
   a frozen `Flight(pos, target, blocked, destroyed, returned)` — the
   `ZapSpec` pattern. `throwit_return(TRUE/FALSE)` (C's "which exit am I
   on") disappears: the return *value* is the exit.
5. **Two mutation channels, and the split is C's own.** Item movement
   (`freeinv`, `place_object`, `useup`, `splitobj`) goes through
   `core/invent.py` + `core/mkobj.py` directly — the "single writer"
   rule, exactly as `pickup` and `drop` do it. Hit-points go out as
   `DamageEvent` intents and are applied by `rules.process_events` —
   exactly as `uhitm` / `mhitu` do it. A phase that applies damage
   directly, or that moves an item by assigning `pos`, breaks one of the
   two invariants.
6. **Range is C's formula, verbatim.** `urange = (crossbow ? 18 :
   ACURRSTR) / 2`; `range = urange - owt / 40` (`owt / 100` for the
   heavy iron ball); minimum 1; ammo without its launcher halves it and
   says so ("You aren't wielding a bow, so you throw your arrow by
   hand."); a boulder is 20; a tethered weapon is
   `min(range, isqrt(arw->range))`; and under levitation C's
   `urange -= range; range -= urange` applies the *recoil* rule — the
   throw loses one square and the hero is pushed back the rest of it
   (the push is deferred with `hurtle`, the lost square is not).
7. **`ThrowCommand(item_id, dx, dy, dz)` and `FireCommand(dx, dy, dz)`.**
   Throwing needs the third axis (`u.dz` in C: up at the ceiling, down
   at your feet); `Direction` is 8-way with no up/down and extending it
   would ripple into `ZapCommand`. A raw delta triple matches C's
   `u.dx/u.dy/u.dz`, which every `dothrow.c` function reads.
8. **The console keymap is settled once, in phase B, and `t` becomes
   throw.** C: `t` throw, `f` fire, `Q` quiver, `T` take off, `w`
   wield, `W` wear, `d` drop. PLAN-DROP decision 4 already makes
   `read_command` case-sensitive and moves take-off to `T`; this plan
   takes the lowercase `t` *alias* away (its stated reason was "so the
   existing console tests keep passing" — those tests are updated in the
   same commit). Up/down at the direction prompt: `u` / `d` keys, and
   `>` / `<` stay stairs.
9. **The hero gets a `PerMonst` (`MONS[PM_HUMAN]`) so `dmgval` can be
   called with `&gy.youmonst`.** One `_mon(...)` row copied from
   `monst.c`, `hero.mdata = MONS[PM_HUMAN]` in `worldgen._make_hero`
   (keeping `ac` / `damage` overrides). This does *not* reroute combat:
   `step`'s gates read the **attacker's** `mdata` for monster→hero and
   the **defender's** for hero→monster, and the hero is never a
   defender in the second test. It does light up `uhitm.hmonas` (hero
   vs. same type — no `PM_HUMAN` monster exists in the subset) and
   `bigmonst(&youmonst)` in `thitu`, which is the point. A regression
   test pins `test_same_seed_same_game`.
10. **`select_rwep` and `mon_wield_item` are this plan's, not `mon.c`'s.**
    Both are `NotImplementedError` STUBs in `core/weapon.py:1281-1308`,
    and `thrwmu`'s first two statements call them. They need the
    *monster's* weapon slot, which is `worn.which_armor(mon, W_WEP)`
    after PLAN-DROP C — no new state, plus one small enum
    `Monster.weapon_check` (`NEED_WEAPON` / `NEED_HTH_WEAPON` /
    `NEED_RANGED_WEAPON` / `NEED_NOTHING`, C `monst.h`). `possibly_unwield`,
    `mwepgone` and `setmnotwielded` stay stubs; nothing in the throwing
    path needs them once m_wepgone is a mask clear.
11. **The monster's ranged attack is gated by `range2` before it is
    enabled.** C's `mattacku` computes `range2 = !monnear(mtmp, mux,
    muy)` and every *melee* case starts with `if (!range2)`. pyhack's
    `mattacku` has no such gate because `step._monster_turn` only calls
    it at `distmin == 1`. Phase G adds the gate **first**, with a test
    that a goblin at distance 5 with `AT_WEAP` does not claw the hero
    through the wall — otherwise the first phase that calls `mattacku`
    from range turns every goblin in the dungeon into a sniper.
12. **The remembered hero position is the live one.** C's `range2`,
    `lined_up` and `URETREATING` all read `mtmp->mux/muy` (where the
    monster *thinks* the hero is). pyhack monsters have no memory
    (ARCHITECTURE: "remembered positions" is deferred with `mmove`), so
    `mux/muy` = `hero.pos`. Documented divergence, one line per call
    site.
13. **A volley is one command and one turn, and it re-checks the target
    between shots.** C's loop stops when the thrower dies; the target
    dying mid-volley keeps the remaining shots flying in C (they may hit
    whatever is behind). pyhack tracks *projected* hp (the `mhitu`
    `hero_hp` trick) so the volley stops when the target is provably
    dead, and the abort goes through `endmultishot`.
14. **`fshoot`/`f` keeps `fireassist` but not the command queue.** C's
    `dofire` re-queues `doswapweapon` + `dowield` + `dofire` to
    auto-wield the launcher. pyhack has no command queue (one command
    per turn), so `dofire` *reports* what it would do ("You are not
    wielding a bow.") and the player presses the keys — a documented
    simplification of the ergonomics, not of the rules.
15. **`Item.charges` is not touched by this plan** beyond what
    PLAN-INVENT A already does (`charges` → `spe`); `breakobj`'s
    `spe`-charged branch reads `spe`.

---

## 4. Phases

**Build order.** A (walker) and B (hero throw) are the spine and can be
written in either order; C–F are additive on B; G needs PLAN-DROP C
(`W_WEP`) and its own `range2` gate; H needs G. The one hard *external*
dependency is PLAN-INVENT A — do not start before `core/invent.py`
exists, or phase B will invent a second location writer and the plan
after this one will have to unpick it.

### Phase 0 — the substrate audit and three missing helpers (~0.5 session)

1. Verify (by grep, not by memory) that PLAN-INVENT A/B/C, PLAN-DROP
   C/D and PLAN-MKOBJ A have landed: `Item.quan`/`owt`/`invlet`/
   `carrier`, `invent.{addinv,freeinv,useup,useupall,delobj,place_object}`,
   `objnam.xname/doname/an/the/singular`, `wield.setuwep`/`setuqwep`,
   `W_QUIVER` actually set somewhere. Record the answer at the top of
   `core/throw.py`'s docstring as the "needs" list.
2. Land the three helpers nothing else owns:
   `occupation.stop_occupation(world) -> List[Event]`
   (`allmain.c` 691-703: the `maybe_finished_meal` check, "You stop
   <text>.", clear `world.occupation`, keep the generator's reset
   events); `weapon.throwing_weapon(otmp)` (`dothrow.c` 1429-1438, a
   `_THROWING_WEAPONS` frozenset); `objnam.mshot_xname(obj)` (the
   "3 arrows" / "an arrow" form `thitu` and `drop_throw` build names
   with — a thin wrapper over `xname` + `doname` that PLAN-INVENT C
   should have; if it has it, skip).
3. `MONS[PM_HUMAN]` + `hero.mdata` (§3.9), with the seeded-game
   regression test.
4. `conftest.equip(mon, item)` — the test-only "put this in the pack
   and wield/quiver it" helper, so phase G's tests do not each
   re-implement `world.items[id] = it; mon.inventory.append(it)` (the
   fourth location writer PLAN-INVENT §6 is trying to kill).

**Exit:** the three helpers have tests; `pytest` still 521+ green; the
hero has a `PerMonst` and the demo game is byte-identical.

### Phase A — the walker (`core/bhit.py`, ~1 session)

1. `BhitType` (`THROWN_WEAPON`, `THROWN_TETHERED_WEAPON`; the other
   four C values named in the docstring), `Flight`.
2. `bhit(world, start, (dx, dy), range, kind) -> Flight`:
   the C loop reduced to what a thrown object needs — the map edge
   (restore the last legal square), `blocking_terrain` (wall, closed
   door), the first living monster (`world.monster_at`), the web and
   sink stops (named, empty, §5.10), and the "range exhausted" exit.
   No animation, no `tmp_at`, no `fhitm`/`fhito`.
3. `mthrowu.blocking_terrain` lives in `mthrowu.py` (§1.2) but
   `bhit` needs it: put the predicate in `core/bhit.py` and have
   `mthrowu` import it (one predicate, one home — C has it twice).
4. Tests: the edge stop, the wall stop, the closed-door stop, the
   first-monster stop (with a second monster behind it), and "range 0
   lands on the thrower's own square".

**Exit:** `bhit` returns the right square for a table of hand-built
maps, and `zap.find_target_in_line` still passes its tests untouched
(migrating the beams onto `bhit` is phase I, and optional).

### Phase B — the hero throws, once, straight ahead (~1.5 sessions)

1. `throw.dothrow` / `ok_to_throw` / `throw_ok` / `throw_obj` (the
   single-shot path: `shotlimit` parsed, the multishot count fixed at
   1), `throwit` (`dz == 0`), `throwit_mon_hit`, `thitmonst` (the
   weapon / ammo / `HEAVY_IRON_BALL` / `BOULDER` branches),
   `tmiss`, `omon_adj`, `breaktest`-less landing (`place_object`).
2. The refusals in C order: `notake` / `nohands` (skip — the hero is a
   human), `canletgo`, the welded weapon, "It's too heavy" (boulder
   without `throws_rocks`), "You cannot throw an object at yourself.",
   `welded`/`weldmsg`, `dry_a_towel`.
3. `ThrowCommand` + the console: `t<letter>` then the direction prompt
   (`u`/`d` accepted for `dz`), the case-sensitive keymap change of
   §3.8, `main.py` help text.
4. `step` wiring: one new branch in the hero phase.
5. Tests: throw the demo dagger east → the dagger is on the floor at
   the wall, out of the pack, `world.turn` +1, "You throw the dagger.";
   throw at a goblin 3 tiles away with a `SeqRng`-forced hit → a
   `DamageEvent` of the table's `wsdam` (±`spe`); the same with a miss →
   "The dagger misses the Goblin." and the dagger lands beyond it;
   throwing the wielded sword empties the hands (`W_WEP` clear);
   throwing with a wall adjacent stops at the wall.

**Exit:** `t` is playable end to end, the item leaves the pack and
comes back onto the floor, and no test in the suite holds a stale item
id across a throw (§6.5).

### Phase C — stacks and the volley (~1.5 sessions)

1. `mkobj.splitobj` / `unsplitobj` (spans above), with the
   `quan`/`owt`/`invlet` rules: the parent keeps its letter, the child
   is a new id from `World.new_ident`, `unsplitobj` merges the child
   back into the parent if both still exist (C's `save_osplit`
   restore).
2. `throw_obj`'s multishot block: `multishot_class_bonus` (the role
   table), the skill switch (`P_SKILL(weapon_type(obj))` via
   `weapon.uwep_skill_type` + `Skills`), the ammo/launcher rule, the
   race rule, the crossbow strength rule, `rnd(multishot)`, the
   `shotlimit` clamp, and the "You shoot 3 arrows." line.
3. The volley loop: one `splitobj` per shot, `freeinv`, `throwit`,
   the projected-hp abort, `endmultishot`.
4. `mergable`/`merged` (PLAN-INVENT B) on landing so a second arrow
   stacks with the first.
5. Tests: 5 arrows + a bow → between 1 and 5 leave the pack in one
   turn and the leftovers keep their letter; two arrows land and
   merge into one floor stack of 2; `limit` (`3t`) throws at most 3.

**Exit:** one command, N projectiles, one turn; `quan` arithmetic is
conserved (a `sum(quan)` invariant test over the pack + the floor).

### Phase D — fire, launcher, quiver (~1 session)

*Needs PLAN-DROP D (`W_QUIVER`, `setuqwep`, `Q`).*

1. `find_launcher`, `autoquiver`, `dofire` (without the command queue,
   §3.14), `endmultishot`'s message.
2. `FireCommand` + `f<letter|none>`: with a quiver, `f` fires without
   asking; with none, `autoquiver` fills it or prints C's refusal.
3. The `ammo_and_launcher` to-hit bonus in `thitmonst`
   (`uwep->spe - greatest_erosion(uwep)` + `weapon_hit_bonus`), and
   "You aren't wielding a bow, so you throw your arrow by hand." with
   the halved range.
4. Tests: `f` with a bow wielded and 3 arrows quivered → 3 arrows; `f`
   with no quiver → autoquiver readies the arrows; `f` with arrows but
   no bow → the by-hand line and half range; the quiver emptied → the
   `W_QUIVER` bit gone.

**Exit:** `f` and `t` differ exactly where C says they do (the source
of the item and the launcher bonus), and the quiver has one writer.

### Phase E — up and down (~1 session)

1. `toss_up` (`dz < 0`): the ceiling line, the boomerang / egg /
   potion-on-the-ceiling specials reduced to the ones whose machinery
   exists (an egg that hits the ceiling breaks), `monster_yields`.
2. `hitfloor` (`dz > 0`): `IS_SOFT` / altar / the `surface()` line /
   `hero_breaks` / `dropz`.
3. Range-1 and range-0 interactions (`u.dz` non-zero skips `bhit`).
4. Tests: throw a potion up → it breaks, `breakmsg`, no item left;
   throw a dagger down → it is on the hero's own square ("You hit the
   floor."); a lit potion of oil thrown up is not a special case yet
   (§5.6).

**Exit:** all three `dz` branches are exercised, and `u.dz == 0` is
byte-identical to phase B.

### Phase F — breakage and the object-hit half (~1.5 sessions)

1. `throw.breaktest` / `breakobj` / `breakmsg` / `hero_breaks` /
   `breaks`, `should_mulch_missile`, `harmless_missile`, and a
   `BREAK_EFFECTS: Dict[oclass|otyp, Callable]` registry (the
   `FLOOR_EFFECTS` pattern from PLAN-DROP decision 7) with the
   potion-shatter and egg-splatter entries and *named* empty entries
   for the ones that need `potion.c` / `explode.c`.
2. The `breakobj` branches: the **crackable armour** arm is already
   ported machinery — `is_crackable` calls `erode_obj(ERODE_CRACK)`,
   which is `core/worn.erode_obj` (crystal plate mail and the helm of
   brilliance crack four times before they shatter); mirror Luck −2,
   eggs, boulders / statues. The potion arm is a `BREAK_EFFECTS` entry
   with no body (§5.6); the camera and the pyrolysk stay deferred with
   the waves that own `explode.c` and `apply.c`.
3. `thitmonst`'s `should_mulch_missile` call and the "your arrow is
   gone" path (C: `obfree`, then `return 1` so the caller does not
   place it).
4. Tests: throw a potion at a wall → it shatters (no item, a message,
   no `DamageEvent` — the potion effects are not ported); throw 40
   arrows at a wall → some survive, roughly the C rate (a range test,
   not an exact count); a blessed arrow survives more often than a
   cursed one on the same seed.

**Exit:** breakage is data-driven, every branch names its C, and no
unported branch silently destroys an item (the "no item leak" invariant
of §6.5 covers the destroyed case too).

### Phase G — monsters that throw (`mthrowu.c`, ~2 sessions)

*Needs PLAN-DROP C (`W_WEP` on `Monster`) and, for anything to be
*observable*, PLAN-MAKEMON E (a monster with ammo). The phase is
writable and testable before E lands: the tests fill the pack with
`conftest.equip`.*

1. **`mattacku`'s `range2` gate** (§3.11): compute `range2 = not
   adjacent`, `if range2: continue` on every melee `aatyp`, and route
   `AT_WEAP` to `thrwmu` / `AT_SPIT` to `spitmu` when `range2`;
   `step._monster_turn` gains "a monster that can see the hero and has
   a ranged attack may attack after moving" (C's PHASE FOUR).
2. `m_carrying`, `m_useup`, `m_useupall`, `m_has_launcher_and_ammo`,
   `linedup` / `linedup_callback` / `m_lined_up` / `lined_up`,
   `monmulti`, `monshoot`, `thrwmu`.
3. `select_rwep` + `mon_wield_item` + `Monster.weapon_check` (§3.10).
4. `m_throw` (the hero branch of the per-tile switch, the
   `MT_FLIGHTCHECK` macro as a nested `_flight_blocked` function), and
   `drop_throw`.
5. `thitu`: the `u.uac + tlev <= rnd(20)` differential, "It misses." /
   "You are almost hit by X." / "You are hit by X!", the acid / silver
   / potion specials reduced to what exists, `losehp` → `DamageEvent` +
   `process_events`, `stop_occupation` (§2.6).
6. Tests: a goblin with 3 daggers 4 tiles away throws 1..3, at least
   one lands in the hero's square, the pack count drops and the item
   is in `world.items`; `thitu`'s miss band (`tlev` 8 vs. AC 5) with a
   `SeqRng`; a monster with no ammo neither throws nor moves *and draws
   nothing* (§6.2); a monster's throw interrupts a running meal.

**Exit:** `mthrowu` is 17/28 ported with the eleven deferrals named;
`mattacku` cannot melee at range; the demo's seeded game is unchanged
with unarmed monsters, and changes *only* where a monster is armed.

### Phase H — spit, gold, and the throw-and-return (~1 session)

1. `spitmm` (hero-target half) + `spitmu`: the `mksobj(BLINDING_VENOM)`
   / `ACID_VENOM`, the `rn2(BOLT_LIM - dist)` gate, the blinding and
   acid effects via `apply_blind` / `resists`.
2. `throw_gold` (`dz == 0`): the whole pile, the quiver coin, the
   leprechaun-bribe message; needs PLAN-INVENT E.
3. The throw-and-return weapon (aklys): `ARWEP` is already data;
   `throwit`'s `return_throw_to_inv` / `impaired` branches and
   `sho_obj_return_to_u` as a no-op; C's `rn2(100)` return, the
   "returns to your hand!" and the miss-return hit for `rn2(2)`.
4. The cursed / greased slip (`rn2(7)` → a random direction) and the
   stamina drop (`calc_capacity` + the hp/weight rule) — both are small
   and both are in `throwit`, so they land once.
5. Tests: spit venom at the hero from 3 tiles (blinded, 0 damage);
   throw 50 gold → the pile lands, `hero_gold` drops by 50; a cursed
   dagger sometimes goes sideways; the aklys comes back to the hand.

**Exit:** `dothrow.c` is 28/39 and `mthrowu.c` 17/28, with every
deferred function in §5 and a test naming the wave that owns it.

### Phase I — deferred, listed so nobody re-decides

1. Migrate `zap.py`'s beam onto `core/bhit.bhit` (the two walkers
   should be one; the beams' "always hit the first monster, no landing"
   semantics have to be expressed as a `BhitType.ZAPPED_WAND` mode
   first). **Not in this wave** — it would put the pinned zap tests
   inside a throwing change.
2. `hurtle` / `mhurtle` / `walk_path` (knockback) → the `zap.c` /
   `explode.c` wave.
3. Breath weapons (`breamm`/`breathwep_name`/`rnd_hallublast`) → their
   own plan; they are `dobuzz(BZ_M_BREATH(...))`, i.e. a *beam*, and
   they share nothing with this file but the `m_lined_up` predicate.
4. Monster-vs-monster (`ohitmon`, `thrwmm`) → `mhitm.c`.
5. Iron bars (`hit_bars`/`hits_bars`) → the day `IRONBARS` terrain is
   generated.

---

## 5. Deliberate divergences

1. **No animation.** C flashes the glyph along the path (`tmp_at`,
   `nh_delay_output`). The console redraws per turn; the flight is
   invisible and the events say where it went.
2. **No knockback.** `hurtle`, `mhurtle`, `walk_path` and the
   levitation recoil in `throwit` (1683-1684) are deferred; the *range*
   halving under levitation is kept, the movement is not.
3. **No shops.** `check_shop_obj`, `ship_object`, `unpaid` billing in
   `dothrow.c` / `throwit` / `drop_throw` are PLAN-SPECIAL-ROOMS; a
   thrown item is never billed.
4. **No swallow.** `swallowit`, the `u.uswallow` branches of `throwit`
   and `throw_obj`'s `ball.c` bookkeeping do not exist (`AT_ENGL` is a
   STUB in `mhitu`).
5. **No unicorns, no gems-as-gifts.** `gem_accept`, `ucatchgem`,
   `u_catch_thrown_obj` — the demo's bestiary has no unicorn and the
   hero cannot polymorph.
6. **Reduced breakage effects.** The potion's contents are not applied
   (no `potionhit`), the camera releases no demon, a wand that breaks
   does not explode. The *object* is destroyed, the *effect* is a
   registry entry with its C span and no body.
7. **No monster-vs-monster throw.** `ohitmon` is 183 lines of
   `mhitm`-shaped combat (`mdefend`, `monkilled`); it lands with
   `mhitm.c`, not here. Consequence: a monster's missile passes through
   another monster (C would stop it) — visible only once monsters fight
   each other.
8. **No monster tether return** (`return_from_mtoss`): a monster's
   aklys is thrown and stays thrown.
9. **No hero catching.** A missile aimed at the hero always resolves as
   a hit or a miss; there is no "you catch it".
10. **No iron bars.** `IRONBARS` is never generated, so `hit_bars` /
    `hits_bars` are named and not ported; `blocking_terrain` treats the
    terrain value as blocking, which is what C does for everything else.
11. **Breath weapons are a different plan.** They live in the same C
    file only by history; the machinery is `zap.c#dobuzz` with
    `BZ_M_BREATH`, plus `mspec_used` bookkeeping, and they belong with
    monster spellcasting (`mcastu.c`).
12. **`m_shot` is a local, not a global.** C's `gm.m_shot` (the volley
    counter) exists so `pline` can say "the 2nd arrow misses"; the port
    passes a `Volley` value.
13. **Monsters have no remembered hero position** (§3.12) and no
    `mavenge`/`mux`; `linedup` and `range2` read the live position.

---

## 6. Traps

- **`mattacku` has no distance gate today.** Verified: `mattacku`
  (`core/mhitu.py:447`) loops over `NATTK`, skips
  `distance_atk_type(aatyp)` (SPIT / BREA / MAGC / GAZE) and `AT_EXPL` /
  `AT_ENGL`, and runs *everything else* through the melee hit test.
  `AT_WEAP` is not a distance type, so a distant monster with `AT_WEAP`
  would claw the hero across the room. Only `step._monster_turn`'s
  `distmin(...) == 1` call site keeps that from happening. Add the
  `range2` guard **before** the first ranged call site (§4 G1), and give
  the guard its own test.
- **The pinned seed is the real risk of this wave.** `PM_GOBLIN` has
  `AT_WEAP` (`monst_data.py:298`) and goblins are one of the demo's
  three monster kinds. The moment `_monster_turn` calls `mattacku` from
  range, every distant goblin takes a turn it did not take before. The
  demo's monsters carry no items, so `thrwmu`'s early return must draw
  **nothing** — `mon_wield_item` with an empty pack, then `select_rwep`
  → `None`. Prove it with a `SeqRng` that would raise on exhaustion and
  a `test_same_seed_same_game` that must not move.
- **`owt == 0` means infinite range.** `range = urange - owt / 40`; the
  demo's hand-built items have `owt = 0` (there is no `weight()` yet),
  so every dagger flies its full `ACURRSTR / 2`. Either `owt` is
  initialised in phase 0 (`weight(item)`, PLAN-MKOBJ) or the range
  function special-cases `owt == 0` to the table weight — silently
  giving the hero a 6-tile dagger throw and then changing it later is
  the kind of drift the plan exists to prevent. Assert the range in a
  test with an explicit `owt`.
- **`consume_item` will eat the stack.** `items.consume_item` pops from
  `world.items` unconditionally; a thrown item goes through
  `invent.freeinv` (pack → loose) and `useup` (one at a time), and a
  stack that goes to zero is `useupall`. A phase that calls
  `consume_item` on the split child deletes an item that is still on
  the floor and takes its id out of `world.items` — the suite will not
  notice (§2.3, §6.5).
- **A split child is a new object with a new id; the parent keeps the
  letter.** Every test that wants to assert something after the throw
  must look the item up (`world.items_at(pos)`) rather than hold the
  `Item` or its id across the split — the child is what flies, and it
  may merge into another stack or be destroyed on landing
  (`should_mulch_missile`). The three exits (landed, merged, destroyed)
  must each be a test.
- **`place_object` must set `pos`, `lev` and nothing else.** The floor
  is the `lev`-filtered `world.items`; an item placed with the
  thrower's stale `lev` on a level change is a cross-level ghost
  (PLAN-STAIRS decision 3). The throw path never changes level, so it
  copies `lev` from the thrower — one line, one test.
- **Clear `owornmask` on the flying copy.** C does
  `singleobj->owornmask = 0L` right after the split (mthrowu.c:618,
  "threw one of multiple weapons in hand?"). If the split child keeps
  `W_QUIVER` / `W_WEP`, it lands on the floor still "worn" by the
  thrower: `worn.which_armor` will find it, `uac` will count it, and
  `which_armor(..., W_WEAPON)` will hand `uhitm` a floor item as the
  wielded weapon.
- **Throwing the wielded weapon.** `throw_obj` reads `obj == uwep` for
  the `W_WEP` mask (the throw-and-return path needs it back) and clears
  the slot with `setuwep(0)` before `freeinv`. Without PLAN-DROP C this
  cannot be written correctly — `hero.wielded` would dangle at a floor
  item, and `items.wielded_of`'s "validate the id" fallback would hide
  it. Do not start phase B before phase C of PLAN-DROP.
- **`_item_by_letter` drifts.** The console maps `a` + *index into the
  pack* — throw item 2 and item 3's letter changes under the player's
  fingers. It is invisible in a 6-item demo and fatal in a combat turn
  ("throw the dagger, throw the dagger" throws two different items).
  PLAN-INVENT A's `invlet` is the fix and the throwing wave is the
  first command that cares.
- **`t` collides with take-off** (§2.7). Change the keymap in the same
  commit as the command, update `main.py`, `README.md` and
  `tests/test_console.py`, and keep the case-sensitivity change
  PLAN-DROP decision 4 makes — `w`/`W`, `t`/`T`, `d`/`D`, `f`/`F` all
  depend on it.
- **Direction has no `dz`.** The demo prompt returns a `Direction`; a
  throw needs `u.dx/u.dy/u.dz`. Passing a `Direction` and treating "no
  monster" as "land at the wall" silently turns "throw up" into "throw
  east".
- **The volley outlives the target.** Damage is applied by
  `process_events` *after* the producer returns, so a naive loop throws
  all N missiles at a monster the first one already killed and each hit
  emits a `DamageEvent` against a dead actor (`apply_damage` no-ops,
  but the messages lie). Track projected hp, as `mhitu.mattacku` does.
- **`thitu`'s differential is `u.uac + tlev > rnd(20)`, and
  `u.uac` is not `hero.ac`.** It is C's 10-based AC (lower is *better*
  for the defender, negative is possible) fed straight into the sum —
  the opposite convention from `known_hitum`'s `20 - mdat.ac` on the
  monster side. In pyhack the hero's effective AC is the **computed**
  `worn.uac(world, hero)` (`10` base, `5` in chain mail), exactly as
  `mhitu.mattacku` already reads it; using the raw `hero.ac` skips every
  piece of worn armour. `tlev` then carries the distance and the
  launcher bonus. Pin both sides of the boundary with a `SeqRng` test,
  or the first monster volley is inverted.
- **`select_rwep`/`mon_wield_item` raising from a live path.**
  `thrwmu` calls both on its first line; if a phase wires `AT_WEAP` →
  `thrwmu` while they are still `NotImplementedError`, the demo becomes
  a traceback the first time a goblin has a stick. They are phase G3,
  *before* the wiring in G2.
- **`stop_occupation` discards its events** (§2.6). Write it so the
  generator's `StopIteration` value is returned; `m_throw`'s "your meal
  is interrupted" and the meal's own reset line both ride on it.
- **Spit creates an object from nothing.** `spitmm` does
  `mksobj(BLINDING_VENOM, TRUE, FALSE)`; that object needs an id
  (`World.new_ident`), a `quan`, and a `world.items` entry, and it is
  *not* in the monster's inventory, so `m_useup` cannot free it —
  `m_throw`'s "VENOM is not in minvent" comment (mthrowu.c:600) is the
  rule: a venom object is `OBJ_FREE` and dies in `drop_throw`.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| `t` / `f` — the two missing combat commands | no command at all |
| the hero's first ranged attack | melee only (bump to attack) |
| monsters that can hurt the hero from more than one tile | `distmin == 1` |
| `splitobj` / `unsplitobj` | deferred by PLAN-MKOBJ §3.6 |
| `place_object`'s second caller (after drop) | nothing put an item back |
| `select_rwep` / `mon_wield_item` / `weapon_check` | three STUBs |
| a real second user of the weapon tables (RWERP/ARWEP/BOLT_LIM) | data with no consumer |
| `stop_occupation` | absent; the meal never "stops" |
| a reduced `bhit` for the beams to migrate onto later | `find_target_in_line` |
| quiver / launcher semantics (`f`, `W_QUIVER`) | state with no behaviour |
| `dmgval` against the hero (`&gy.youmonst`) | `MONS[PM_HUMAN] is None` |
| shop theft by throwing, monster-vs-monster throws | listed, owned elsewhere |

| needs | from |
|---|---|
| `Item.quan` / `owt` / `invlet`, `invent.{freeinv,useup,useupall,delobj,place_object}`, `carrier` | PLAN-INVENT A (**hard**) |
| `mergable` / `merged` (landing stacks) | PLAN-INVENT B |
| `xname` / `doname` / `an` / `the` / `singular` (every line) | PLAN-INVENT C |
| `weight_cap` / `calc_capacity` (the stamina drop, encumbrance refusal) | PLAN-INVENT D |
| `hero_gold` (throwing coins) | PLAN-INVENT E |
| `World.new_ident` (split children, venom objects) | PLAN-MAKEMON B |
| `setuwep` / `W_WEP` / `welded` (throwing the wielded weapon) | PLAN-DROP C (**hard**) |
| `setuqwep` / `W_QUIVER` / `doquiver_core` (`f`) | PLAN-DROP D |
| `mksobj` (venom, and ammo for monsters to carry) | PLAN-MKOBJ B |
| `m_initweap` / `m_initthrow` / `mongets` (monsters with ammo) | PLAN-MAKEMON E |
| `potionhit` (a broken potion's contents) | a potion-throwing wave |
| the breath engine (spit is not breath; breath is not here) | `zap.c` / `mcastu.c` wave |

---

## 8. Definition of done

- [ ] `core/throw.py`, `core/mthrowu.py`, `core/bhit.py` exist with the
      C spans in their docstrings and the eleven deferrals named
- [ ] `t<letter>` + direction throws; `f` fires from the quiver; the
      console keymap is case-sensitive and has a table test
- [ ] a stack splits, one object flies, it lands / merges / is
      destroyed — all three exits tested
- [ ] `multishot` is one turn for N missiles, with the role / skill /
      launcher / race rules, and `shotlimit` respected
- [ ] `bhit` returns the landing square for the edge / wall / closed
      door / first-monster / range-exhausted cases
- [ ] `breaktest` / `breakobj` / `breakmsg` / `should_mulch_missile` /
      `harmless_missile` ported, with a `BREAK_EFFECTS` registry whose
      unported entries name their C
- [ ] `mattacku` has the `range2` gate and a test that a distant
      `AT_WEAP` monster cannot melee
- [ ] `thrwmu` / `monshoot` / `monmulti` / `m_throw` / `thitu` /
      `drop_throw` / `m_useup` ported; a monster with ammo throws,
      one without draws nothing
- [ ] `select_rwep` / `mon_wield_item` no longer raise;
      `Monster.weapon_check` exists
- [ ] `occupation.stop_occupation` exists and interrupts a meal
- [ ] `hero.mdata == MONS[PM_HUMAN]`; `test_same_seed_same_game`
      unchanged; the unarmed demo draws exactly what it drew before
- [ ] `mypy` clean, `flake8` clean, the suite green
- [ ] `ARCHITECTURE.md` gains the `dothrow.c` / `mthrowu.c` / `bhit`
      rows, `CHANGES.md` a Wave 7 entry, `README.md` / `main.py` the
      new keys
