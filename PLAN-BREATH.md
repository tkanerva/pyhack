# Plan: Wave 8 — breath weapons (`mthrowu.c` + the `zap.c` beam engine)

**Status: proposed, nothing implemented.** No monster can breathe at the
hero. `INDEX.md` rows: `src/mthrowu.c` 1,561 lines / 15k tokens / 28
functions / pyhack state `none` (0%); `src/zap.c` 6,461 lines / 62.5k
tokens / 85 functions / `partial-subset`, 20% by name / 1% exact.
Baseline measured this session: **521 tests green, mypy clean** (76
source files, 0 issues).

**Goal:** a monster that is lined up with the hero and has an `AT_BREA`
attack exhales: `The gray dragon breathes fragments!`, an 8-to-14-square
beam walks the line, is stopped by a wall (and sometimes bounces, hits
the breather itself), passes over the map, hits whatever monster or hero
stands on a square, rolls `zap_hit()` against AC, applies its damage type
through the *same* per-type table the wands use, sets the terrain on fire
/ freezes it / bursts a door, burns a web, interrupts the hero's meal —
and the monster then cannot breathe again for `8 + rn2(18)` turns.

**The whole difficulty is that "breath" is not a mechanic.** In C it is
one of six *flavours* of `dobuzz()` (zap.c 4793-5051), which is the same
function the five ray wands, the five ray spells, monster spellcasting,
the fire/frost horns, a priest's divine lightning and monster wand zaps
all use. `breamm` (1092-1150) only *decides* whether to breathe. So this
plan is: **port `dobuzz` once, properly**, and hang breath off it. The
reduced beam that `pyhack/core/zap.py:zap` implements today — first
monster in a straight line, no hit roll, no terrain, no bounce — is
exactly why breath cannot be written on top of it.

**Ground truth:** `../NetHack` through `nethack_index`. Spans from
`symbols/zap.json` and `symbols/mthrowu.json`. Never read either `src/`
file whole: `zap.c` is 6,461 lines and 62.5k tokens (fourth on
`INDEX.md`'s *Most expensive unported files*, after `options.c`,
`trap.c` and `uhitm.c`); the spans this plan needs are `dobuzz`,
`zap_hit`, `zhitm`, `zhitu`, `zap_over_floor`, `bounce_dir`, `zaptype`,
`flash_str` — about 1,100 lines total, read once, here.

---

## 1. What the C code does (reference)

### 1.1 The four functions and two tables that *are* breath

| C function | span | what it does | port target |
|---|---|---|---|
| `breathwep[]` | 24-28 | the ten breath *names* indexed by `BZ_OFS_AD(adtyp)`: `"fragments", "fire", "frost", "sleep gas", "a disintegration blast", "lightning", "poison gas", "acid", "strange breath #8", "strange breath #9"` — with the header comment "Keep consistent with breath weapons in zap.c, and AD_* in monattk.h" | `zap.BREATH_NAMES` |
| `hallublasts[]` | 31-48 | 96 hallucinatory ray names (`"asteroids"`, `"zorkmids"`, …), used by *both* `flash_str()` and `breathwep_name()` | `zap.HALLU_BLASTS` |
| `rnd_hallublast` | 51-55 | `ROLL_FROM(hallublasts)` = `hallublasts[rn2(96)]` | `zap.rnd_hallublast(rng)` |
| `breathwep_name` | 1082-1089 | `Hallucination ? rnd_hallublast() : breathwep[BZ_OFS_AD(typ)]` | `zap.breath_name(typ, hero)` |
| `breamm` | 1092-1150 | **the decision**: lined up? cancelled (coughs)? target already *seen* to resist / reflect? `mspec_used` free and `rn2(3)`? then `dobuzz(BZ_M_BREATH(BZ_OFS_AD(typ)), mattk->damn, …)` and set `mspec_used`, `nomul(0)` | `mthrowu.breamm` (phase E) |
| `breamu` | 1274-1278 | `breamm(mtmp, mattk, &youmonst)` — the hero-target wrapper | `mthrowu.breamu` |

Four functions and two tables, **77 lines** of body between the
functions (`rnd_hallublast` 5, `breathwep_name` 8, `breamm` 59,
`breamu` 5). Everything else is the engine.

### 1.2 `dobuzz()` — the beam engine (span 4793-5051, 259 lines)

The `type` argument is an **integer encoding**, and it is load-bearing:

```
type ==   0 to   9 : you zapping a wand          BZ_U_WAND
type ==  10 to  19 : you casting a spell         BZ_U_SPELL
type ==  20 to  29 : you breathing as a monster  BZ_U_BREATH
type == -10 to -19 : monster casting a spell     BZ_M_SPELL
type == -20 to -29 : monster breathing at you    BZ_M_BREATH
type == -30 to -39 : monster zapping a wand      BZ_M_WAND
```

with `BZ_OFS_AD(adtyp) = abs(adtyp - AD_MAGM) % 10` (hack.h 1491-1507)
mapping the eight `AD_*` breath types onto offsets 0..7. `zaptype()`
(zap.c 88-96) folds the sign back to `abs()`, `fltyp % 10` recovers the
damage type, and **three parallel string tables are indexed by the
result**: `flash_types[zaptype(type)]` (30 entries, 71-85 — the
`"blast of missiles" / "blast of fire" / …` block at 81-84) and
`breathwep[BZ_OFS_AD(typ)]`.

The loop, reduced:

1. `range = rn1(7, 7)` (= `7 + rnd(7)`, 8..14); `range = 1` if
   `dx == dy == 0`; save `gb.bhitpos`.
2. Per square: `sx += dx; sy += dy`; off-map or `STONE` → `make_bounce`;
   `zap_over_floor()` for every type except fireball and poison gas
   (deferred to the reflection decision), returning a `rangemod`.
3. A monster is there: `zap_hit(find_mac(mon), spell_type)` — on a hit,
   `mon_reflects()` reverses the beam (and `gas_hit = FALSE`), else
   `zhitm()`; the Rider / Death-monster special cases; `range -= 2` on a
   hit, then the loop continues **through** the monster.
4. `u_at()`: the steed intercept (`!rn2(3)`), then
   `zap_hit((int) u.uac, 0)`; on a hit `range -= 2`,
   "`The blast of fire hits you!`", the `Reflecting` reversal, else
   `zhitu()`; the miss line is "`The bolt whizzes by you!`" (`Blind`:
   "Your arm tingles."); then `flashburn(d(nd,50), TRUE)` for lightning
   **even on a miss**, `stop_occupation()`, `nomul(0)`.
5. `!ZAP_POS(typ) || (closed_door && range >= 0)` → `make_bounce`:
   `bchance = 10` (off-map/stone) / `20` (a wall in the mines) / `75`;
   "`The bolt bounces!`"; `bounce_dir()` picks the new direction
   (reverse, or reflect off one axis if the perpendicular square is
   open).
6. Poison gas that was deferred lays a 1×1 cloud *after* the reflection
   decision. A fireball explodes before the obstacle.
7. `pay_for_damage()` if a shop door died (deferred — no shops).

### 1.3 The per-square helpers

| C function | span | what it does | port target |
|---|---|---|---|
| `zaptype` | 88-96 | `-39..-30` shifted by +30, then `abs()` — the one piece of sign arithmetic | `zap.zaptype` |
| `flash_str` | 6442-6459 | `flash_types[zaptype(typ)]`, or `"blast of <hallublast>"` under hallucination (suppressible, for death reasons) | `zap.flash_str` |
| `zap_hit` | 4718-4734 | the to-hit: `chance = rn2(20)`; `!chance` → the 1-in-20 "naked target ducks" `rnd(10) < ac + bonus`; else `3 - chance < AC_VALUE(ac) + bonus` | `zap.zap_hit` |
| `zhitm` | 4251-4412 | a **monster** is hit: an eleven-case switch on `zaptype(type) % 10` — `resists_*()`/`defended()` per type, `d(nd,6)`, the cold-vs-fire and fire-vs-cold bonuses, `destroy_items`/`ignite_items`/`burnarmor`, `sleep_monst(d(nd,25))`, the two death/disintegration branches, lightning's `rnd(50)` blind when `nd > 2`, `acid_damage`/`erode_armor`; returns the damage, then `mon->mhp -= tmp` | `zap.ZAP_EFFECTS` (already the registry) |
| `zhitu` | 4414-4605 | the **hero** is hit: the same eleven cases from the victim's side — `Antimagic`, `Fire_resistance` + `ugolemeffects`, `destroy_items`, `fall_asleep(-d(nd,25))`, disintegration destroys shield→suit→cloak→shirt then `done(DIED)`, `poisoned("blast", A_DEX, …)`, `acid_damage(uwep)`, `erode_armor`; then `losehp(dam, kbuf, KILLED_BY_AN)` with the "breathed by `<mon>`" killer text and `Half_spell_damage` for wands/spells only | `zap.zhitu` (new) |
| `zap_over_floor` | 5154-5511 | the terrain: burning webs, `melt_ice`, water→steam/pit, lava, freezing water, iron bars, the `SDOOR` reveal, the `closed_door` destruction table (`D_NODOOR` for fire/cold/disintegration, `D_BROKEN` for lightning), `burn_floor_objects`, `wakeup(mon)`; returns a range modifier (`-3`, `-1000` = stop) | `zap.zap_over_floor` (new) |
| `bounce_dir` | 4677-4715 | `!dx || !dy || !rn2(bounceback)` → reverse; else reflect off whichever axis has open terrain | `zap.bounce_dir` |

`zhitm`/`zhitu`/`zap_over_floor` are what make this wave large; §4 phases
them so each lands with a test.

### 1.4 The gate that lets a monster breathe at all

`mattacku` (mhitu.c 793-933) walks `NATTK` attacks and dispatches on
`mattk->aatyp`. Every melee case is guarded by `if (!range2)`, and

```c
case AT_BREA:
    if (range2)
        sum[i] = breamu(mtmp, mattk);      /* 873-877 */
```

where `range2 = !monnear(mtmp, mtmp->mux, mtmp->muy)` (450-454). So a
dragon adjacent to the hero will *not* breathe — it claws and bites —
and a dragon at range breathes and does not melee. `range2` is the
whole reason `mattacku` needs a distance gate that pyhack does not have
(PLAN-THROW §6 and its phase G1 own that gate; this plan consumes it).

### 1.5 The bookkeeping that exists only for breath

| C | where | port |
|---|---|---|
| `mtmp->mcan` — "cancelled": a cancelled breather *coughs* instead (1100-1108) | `monst.h` | new `Monster.mcan` (phase 0) |
| `mtmp->mspec_used` — the cooldown: gate at 1117, set to `8 + rn2(18)` at 1132, `+ rnd(20)` for sleep breath at 1133-1134 | set mthrowu.c 1132; **decremented once per turn per monster** in `mon_regen` (monmove.c 305-312), which `mcalcdistress` (mon.c 1179-1193) runs for **every** monster, moving or not | new `Monster.mspec_used` + the decrement in `step`'s monster loop |
| `mon->seen_resistance` / `m_seenres(mon, mask)` — "this monster has watched the hero shrug off fire, don't waste the breath" (1113-1115) | `monst.h:96`, written by `monstseesu()`/`monstunseesu()` (mondata.c 1556-1581) for every monster that can see the hero | new `Monster.seen_resistance` + `mondata.monstseesu` (phase 0) |
| `mtmp->mtame && !mtmp->isminion` → `EDOG(mtmp)->hungrytime -= 10` (1138-1144) | dogs | deferred (no pets) |

### 1.6 `dobuzz`'s nine call sites, and which of them this wave touches

| caller | C | flavour | this plan |
|---|---|---|---|
| `weffects` — the ray wands | zap.c 3477-3479 | `BZ_U_WAND` | **yes** (they are the same engine, and they are also this wave's best regression net) |
| `weffects` — the ray spells | zap.c 3475-3476 | `BZ_U_SPELL` | **yes** (via `spells.cast_spell`, already routed through `zap()`) |
| `breamm` — monster breath | mthrowu.c 1123 | `BZ_M_BREATH` | **yes — the point of the wave** |
| `buzz` from `mcastu` — monster spells | mcastu.c 1006 | `BZ_M_SPELL` | no — the `mcastu.c` wave |
| `buzz` from `priest` — divine lightning | priest.c 870 | `BZ_M_SPELL` | no — temples |
| `buzz` from `timeout` — thunderstorm | timeout.c 1872 | `BZ_M_SPELL` | no — the Plane of Air |
| `ubuzz` from `music` — fire/frost horn | music.c 634 | `BZ_U_WAND` | no — no instruments |
| `dobuzz(..., forcemiss=TRUE)` from `muse` — monster wand zaps | muse.c 1817 | `BZ_M_WAND` | no — the `muse.c` wave |
| `ubuzz` from `zap.c#ubreatheu` — a **polymorphed hero** breathing | zap.c 3030-3036 | `BZ_U_BREATH` | no — no hero polymorph (`polyself.c#dobreathe`) |

Six of these nine call sites are unreachable in pyhack today and stay
that way; the port must still keep their *holes* (the sign, `forcemiss`,
`sayhit`/`saymiss`, the `BZ_U_BREATH` offsets) because the call sites are
named here and nobody should re-decide them.

### 1.7 What already exists in pyhack

| exists | where | used by |
|---|---|---|
| `ZAP_EFFECTS` — 11 registry keys (fire/cold/lightning/magic/striking/sleep/death/polymorph/cancellation/teleport/undead turning) | `core/zap.py` | the ray wands + spells today; the breath dispatch tomorrow |
| `ZapSpec(effect, power, damage_bonus, range, noun, source)` + `WAND_ZAPS` + `SPELL_ZAPS` | `core/zap.py`, `core/spells.py` | the caster side (`nd` and the bonus are computed by the caster, never by the effect) |
| `get_atkdam_type(adtyp, rng)` + `_RND_BREATH_TYP` (the AD_RBRE roll) | `core/mondata.py:1019-1031` | **already the exact C function** — breath needs it and it is done |
| `M_SEEN_*`, `cvt_adtyp_to_mseenres`, `cvt_prop_to_mseenres` | `core/mondata.py:956-990` | the `m_seenres` masks are already tabulated; nothing stores them |
| `can_breathe(ptr)`, `ranged_attk(ptr)`, `attacktype(ptr, AT_BREA)`, `distance_atk_type` | `core/mondata.py`, `core/monst_defs.py` | the dispatch |
| `PerMonst.mresists` / `.mconveys` (`MR` IntFlag: FIRE, COLD, SLEEP, DISINT, ELEC, POISON, ACID, STONE) | `core/monst_defs.py:806` | **nothing reads it today** (§2.4) |
| `Prop.FIRE_RES … Prop.ANTIMAGIC` (`objects_defs.py:223-243`) and `Prop.REFLECTING = 65` | `core/objects_defs.py` | `props.has_property(world, hero, Prop.REFLECTING)` is the hero's `Reflecting` |
| `worn.ac_value(ac, rng)` (C `AC_VALUE`) | `core/worn.py:326` | `zap_hit` |
| `worn.burnarmor` / `erode_armor` / `erode_obj` / `disintegrate_arm` / `_remove_destroyed` | `core/worn.py:695,805,840,872,683` | `zhitu`/`zhitm`'s armour branches |
| `rules.put_to_sleep` / `apply_poison` / `apply_blind` / `apply_damage` | `core/rules.py` | the status cases |
| `vision.clear_path` / `could_see` / `m_can_see_u` | `core/vision.py:425,829,848` | `linedup` (phase E) |
| `hacklib.distmin` / `sgn`, `weapon.BOLT_LIM` (=34) | `core/hacklib.py:172-195`, `core/weapon.py:1247` | `linedup`, `m_lined_up` |
| `TerrainType` with the **exact** `rm.h` values (`POOL` 16 … `DOOR` 23) | `core/types.py:230-275` | `ZAP_POS(typ) = typ >= POOL` is a one-liner |
| `OBJECTS[].oc_dir` = `NODIR` / `IMMEDIATE` / `RAY` | `core/objects_defs.py:377`, `core/objects_data.py:1000-1043` | **C's own split of `weffects`** — the data decides which wands are beams (§3.2) |
| `doors.open_door` / `close_door` / `closed_door` / `is_doorway` | `core/doors.py` | the door branch — but no *destroy* (§2.9) |

---

## 2. Where pyhack stands (verified this session, by reading)

### 2.1 Nothing breathes, and nothing *can*

`core/mhitu.py:490-492`:

```python
if distance_atk_type(aatyp):
    # spit / breath / magic / gaze are not ported yet (STUBs)
    continue
```

`distance_atk_type` is true for `AT_SPIT, AT_BREA, AT_MAGC, AT_GAZE`
(`monst_defs.py:344`), so `AT_BREA` is not merely unimplemented — it is
*filtered out* two lines before the dispatch switch. `mattacku` also has
no `range2` (PLAN-THROW §6), so the day the filter is removed without the
gate, a distant dragon would claw the hero across the room.

### 2.2 The beam engine is a *reduced* `dobuzz`, and its docstring says so

`core/zap.py` lists four simplifications, of which three are exactly the
C machinery breath needs:

- "no AC-based `zap_hit()` miss (C 5.0's dobuzz hit roll): the beam
  always reaches the first monster in the line";
- the walk is `rules.find_target_in_line` — a straight line that stops at
  the **first** monster, has no landing square, no per-square terrain and
  no carry-through after a hit;
- `zap()` draws the range and then the damage, with nothing in between.

Its draw order is pinned by `tests/test_zap.py` (six tests, five of which
pin a draw sequence): `SeqRng(1,1,1,1,1,1,1)` is "range, then six d6".
**A faithful `zap_hit` inserts a `rn2(20)` between the two**, so those
five sequences change. That is a named cost of this wave (§4 phase B,
§6).

### 2.3 The effect registry has no breath damage types

`ZapEffect` has no key for **ACID** or **POISON GAS** — neither is
reachable from a wand (C has no such wand; `ZT_POISON_GAS` is breath and
gas spores, `ZT_ACID` is breath) so nothing has needed them. And C's
`ZT_DEATH` is *overloaded*: it is both the death ray and the black
dragon's **disintegration** blast, distinguished inside `zhitm`/`zhitu`
by `abs(type) != ZT_BREATH(ZT_DEATH)`. The port has no `type` int inside
an effect, so it needs two keys (§3.3).

### 2.4 `rules.resists()` is a four-boolean fiction that reads no monster

```python
def resists(monster, dmg_type):
    if monster.is_undead:  return dmg_type in (COLD, LIGHTNING, MAGIC_MISSILE, POISON, DEATH)
    if monster.is_demon:   return dmg_type in (FIRE, DEATH, SLEEP)
    if monster.is_golem:   return dmg_type in (SLEEP, DEATH, ACID)
    if monster.is_nonliving: return dmg_type == POISON
    return False
```

Grepped: `is_undead` / `is_demon` / `is_golem` / `is_nonliving` are set
**only by tests** (`make_monster(is_undead=True)`); `worldgen.demo_monster`
sets none of them, and no code derives them from `mdata`. So in a real
game **every monster resists nothing** — a fire elemental takes full fire
damage, a black dragon takes full disintegration — and the same will be
true of every monster PLAN-MAKEMON creates. `PerMonst.mresists` (the real
`MR_*` bits, present on all 40 filled rows — some are 0) is never read by
anything.

This matters here because breath is the first attack whose *every* victim
is a monster with a real type, and because `breamm`'s "don't bother"
check needs the *hero's* resistances in the same currency.

### 2.5 The three breath-only fields do not exist

`Monster` has no `mspec_used`, no `mcan`, no `seen_resistance`
(`core/types.py:740-800`). There is no `mon_regen`/`mcalcdistress`
equivalent, so nothing decrements a cooldown; `step`'s monster loop
(`core/step.py:108-133`) is where one would go, once per monster per
turn, *before* the monster acts.

### 2.6 `m_lined_up` is PLAN-THROW's

`breamm`'s first statement is `if (m_lined_up(mtarg, mtmp))`. That is
`linedup()`'s boolean wrapper (`mthrowu.c` 1329-1393 + 1281-1327), which
PLAN-THROW phase G2 ports because `thrwmu`/`spitmm` need it too. This
plan must not write a second one.
**If PLAN-THROW is not yet in the tree, phase E cannot start** — that is
a hard external dependency, stated again in §7.

### 2.7 `stop_occupation` still does not exist

`core/occupation.py` is the placeholder reconstruction (per the session
notes: the real source was lost). It has `start_occupation` and
`run_occupation` but **no `stop_occupation`** (`allmain.c` 691-703), and
`run_occupation`'s interruption path is

```python
try:
    occ.gen.throw(OccupationStopped())
except StopIteration:
    pass          # <-- the generator's return value is DROPPED
```

so an interrupted meal loses "You stop eating." today. `dobuzz` calls
`stop_occupation()` (zap.c 5004) on every square where the hero is hit,
and `breamm` calls `nomul(0)`; breath is therefore a *second* caller.
PLAN-THROW phase 0 lands it first; **if that has not happened, this plan
lands it instead, and fixes the dropped return value in the same
commit** — it is ten lines and it is a live bug either way.

### 2.8 Only two monsters in the subset can breathe, and nothing can place them

Grepped every `MONS[PM_…] = _mon(` row: **40 of NUMMONS (383)** are
filled. Exactly two have `AT_BREA`:

| monster | row | attack |
|---|---|---|
| `PM_GRAY_DRAGON` | `monst_data.py:417-428` | `Attack(AT_BREA, AD_MAGM, 4, 6)` — "breathes **fragments**", 4d6, `mresists 0` |
| `PM_BLACK_DRAGON` | `monst_data.py:430-441` | `Attack(AT_BREA, AD_DISN, 1, 255)` — disintegration, `mresists MR_DISINT` |

And no generator can produce either: `DEMO_MONSTER_KINDS`
(`worldgen.py:127-131`) is goblin / hill orc / bat, and the `mklev`
generator places only those three too — random monster selection is
PLAN-MAKEMON phase C, placement phase D, and the full `mons[]` table
phase A. So breath is **writable and testable now** (a test builds a
dragon from `MONS[PM_GRAY_DRAGON]`), and **playable after MAKEMON
A+C+D**. Same shape as PLAN-THROW's "monsters stay unarmed until
MAKEMON E", and it has the same consequence: the demo's seeded game does
not move.

### 2.9 The terrain `zap_over_floor` cares about, in this port

Generated today: `ROOM`, `CORR`, `DOOR`, `SDOOR`, `STAIRS`, `STONE` and
walls (`mklev.py`), plus traps including `WEB` (`mklev.DEMO_TRAP_KINDS`,
1203-1207, via `mktrap`). **Not** generated: `POOL`, `MOAT`, `WATER`,
`LAVA*`, `ICE`, `TREE`, `FOUNTAIN`, `SINK`, `IRONBARS` — `mklev` only
*counts* fountains and sinks (`mklev.py:1080-1090`) for the level flags.
So of `zap_over_floor`'s 358 lines, two branches can fire today: the
**closed-door destruction table** and the **burning web**, plus
`burn_floor_objects` if fire meets a scroll. Everything else is a named
deferral with an owner.

Two mutators are missing for even that much: `doors.py` has open/close
but no *destroy* (`doors.destroy_door`), and `traps.py` has no `t_at` and
no `delfloortrap` (only `disarm_trap`).

### 2.10 The hero cannot breathe

`ubreatheu`/`dobreathe` need the hero polymorphed into a monster
(`polyself.c`, 34 functions, `none`). Deferred with the polymorph wave.

### 2.11 The tests this wave will have to move, named now

| test | why it moves |
|---|---|
| `test_zap.py::test_fire_wand_deals_flat_six_damage` | one extra draw (`rn2(20)`) before the dice |
| `test_zap.py::test_death_wand_resisted_by_undead` | idem (resistance is checked before the dice, so the *count* stays 2, the *order* changes) |
| `test_zap.py::test_sleep_wand_puts_to_sleep`, `::test_demon_resists_fire_wand`, `::test_no_target_still_consumes_charge` | idem |
| `test_zap.py::test_no_target_still_consumes_charge` | phase D: the bolt now *bounces* instead of stopping at the edge |
| `test_mhitu.py` (nothing) | the demo's three kinds have no `AT_BREA` |
| `test_demo.py::test_demo_full_game_is_deterministic` | only *self*-consistency (same seed ⇒ same game), so it survives — assert it |

---

## 3. Design decisions

1. **One engine, `dobuzz`, in `core/zap.py`; breath is a caller.**
   `zap()` keeps its name and stays the entry point (`ZAP_EFFECTS`'s
   callers and `spells.cast_spell` do not move); its body becomes a thin
   wrapper that builds the beam type and calls `dobuzz()`. A second
   walker for breath, or a "breath-only" variant of `zap()`, is the drift
   this plan exists to prevent — C's own nine call sites, spread over
   seven files, are the proof that these must not fork.
2. **The C integer type encoding is ported literally** (hack.h
   1491-1507, zap.c 45-96): `bz_ofs_ad()`, `zt_breath()`, `bz_m_breath()`,
   `zaptype()`, and the three string tables indexed by it. Not a
   dataclass, not an enum-with-payload: three 30/10/96-entry tables *are*
   the API, `fltyp % 10` is how the damage type is recovered, and the
   `"blast of missiles"` block at `flash_types[20..29]` is literally
   indexed by the encode. Type safety arrives at the registry boundary
   (`ZapEffect`), not before it. `zap_hit`'s `(ac, type)` keeps its
   second argument too (C passes the spell type for the spell bonus).
3. **`ZapEffect` gains three keys: `ACID`, `POISON_GAS`,
   `DISINTEGRATE`.** The first two are unreachable from a wand in C
   either, so nothing else can own them; `DISINTEGRATE` exists because C
   overloads `ZT_DEATH` (`abs(type) != ZT_BREATH(ZT_DEATH)`), and an
   effect function has no `type` to inspect. So `dobuzz` picks
   `DEATH`/`DISINTEGRATE` from the beam type (the exact C test,
   verbatim) and the registry stays a flat key space.
4. **The name tables live in `zap.py`, not in `mthrowu.py`.**
   `breathwep[]`, `hallublasts[]` and `flash_types[]` are three parallel
   tables over **one** encoding, and `rnd_hallublast` is called from both
   files in C (`flash_str` in zap.c, `breathwep_name` in mthrowu.c). C
   even carries the comment "Keep consistent with breath weapons in
   zap.c". One file, one home; `mthrowu.breamm` imports
   `zap.breath_name`.
5. **`dobuzz` is a pure producer: intents only, never `apply_damage`.**
   This is forced, not preferred: a breath is fired from `mattacku`,
   whose caller `step._melee_combat` runs `process_events`
   (`step.py:169`) — a direct mutation inside `dobuzz` would be applied a
   second time by the processor. Consequence: `_zap_damage` and friends
   switch from calling `rules.apply_damage` to **emitting a
   `DamageEvent`**, and the two hero-side entry points (`use_wand`,
   `cast_spell`) end with `process_events(world, events, rng)` — they are
   the only two today that mutate through `apply_damage` and are not
   processed. One convention, one choke point, no double-count.
6. **The walker is `dobuzz`, and it is not `bhit` and not
   `core/bhit.py`.** C has *three* traversals: `bhit()` (the IMMEDIATE
   wands, `apply.c`'s light/invis beams, and thrown objects via
   `THROWN_WEAPON`), `dobuzz()` (rays, spells, breath: it owns the
   bounce), and `m_throw()`'s own loop. PLAN-THROW's `core/bhit.py` is the
   *thrown-object* member of the first family; this plan ports the second
   and leaves `bhit` untouched. **Named deferral:** the remaining
   `ZAPPED_WAND` half of `bhit()` and the four IMMEDIATE wands still on
   the reduced walk belong to the wave that ports the rest of `weffects`.
7. **Which callers move is decided by the object table, not by a new
   list.** C splits in `weffects` on `objects[otyp].oc_dir == IMMEDIATE`
   (bhit) vs the rest (ubuzz). pyhack's table already carries `oc_dir`
   with the C values, so `use_wand` dispatches on
   `OBJECTS[otyp].oc_dir == RAY`. Verified rows: fire / cold / lightning
   / sleep / death are `RAY` (they move to `dobuzz`); striking /
   cancellation / teleportation / polymorph / undead turning are
   `IMMEDIATE` (they stay). `WandType.DIGGING` is `RAY` in the table but
   not in `WAND_ZAPS`; it keeps saying "does nothing".
   `SPELL_ZAPS`'s `POLYMORPH` also stays: its `oc_dir` is `IMMEDIATE`
   (objects.h 1388-1390, and `objects_data.py:972` agrees), so C routes
   it through `bhit()` — the *reduced walk is closer to C for it* than a
   `dobuzz` beam would be. Same for `CANCELLATION` and `TELEPORT`
   (`SELF_ZAPS`, invoked without a beam at all).
8. **`zap_hit` is ported for everyone, not only for breath.** One beam
   that always hits and one that rolls would be two behaviours behind one
   function name. The five `test_zap.py` sequences are migrated in the
   same commit, each with a comment naming the C line
   (`zap.c:4723 chance = rn2(20)`); the "no AC-based zap_hit miss" entry
   is **deleted** from `zap.py`'s Simplifications list, not softened.
9. **`resists()` learns `PerMonst.mresists`; the four booleans become the
   `mdata is None` fallback.** New `mondata` queries in C's own names
   (`resists_fire`, `resists_cold`, `resists_sleep`, `resists_disint`,
   `resists_elec`, `resists_poison`, `resists_acid`, `resists_magm`) over
   `PerMonst.mresists`; `rules.resists(monster, dmg_type)` asks the typed
   half first when `monster.mdata is not None`, else keeps today's four
   booleans. Verified harmless for the demo: all three demo kinds have
   `mresists == 0`, so nothing in `test_demo` moves. The four
   `test_rules.py` boolean tests use `make_monster()` (no `mdata`) and
   stay green unchanged.
10. **The hero's resistances are `props.has_property`, and `Reflecting`
    is `Prop.REFLECTING`.** `zhitu` reads `Antimagic`, `Fire_resistance`,
    … as `has_property(world, hero, Prop.X)` — the same computed-never-
    cached mechanism the armour port established — and the beam's
    reversal reads `Prop.REFLECTING` (already conveyed by the amulet, the
    shield and silver dragon scale mail). `Monster`-side reflection and
    `defended(mon, AD_x)` (`mon_reflects`, monsters' worn rings) are
    deferred: no monster in the subset carries anything (§5.4).
11. **The breath's own draws are the ones `mattacku` already budgets.**
    `breamm`'s `rn2(3)` and the `mspec_used` gate happen *before* any
    beam draw; `dobuzz` then draws the range and one `rn2(20)` per
    monster square. The projected-hp abort in `mattacku` (`mhitu.py:481`)
    applies to the whole attack sequence, and a breath is an attack like
    any other — so a lethal breath stops the dragon's remaining attacks.
12. **`mspec_used` decrements once per monster per turn, before it acts,
    whether or not it acts** (C: `mcalcdistress` → `mon_regen`, which
    runs for every monster including the immobile ones). The decrement
    goes in `step`'s monster loop next to the existing gates, not inside
    `mattacku`: a sleeping dragon's cooldown must still run down.
13. **The beam can hit the breather.** A bounce off the far wall genuinely
    comes back in C, and `m_at()` finds the breather on its own square, so
    a gray dragon in a small room can fry itself (`zhitm` on itself). The
    port keeps that — with a test — because it is the cheapest proof that
    the walk is a real walk and not a line-of-sight shortcut.
14. **No display, no animation.** `tmp_at`/`nh_delay_output`/`newsym` do
    not exist; the flight is invisible and the `MessageEvent`s say where
    it went. `zap_over_floor`'s `newsym` calls drop out; its
    `recalc_block_point` does not (a destroyed secret door changes
    vision).

---

## 4. Phases

**Build order.** 0 → A → B → C → D → E; F is the paperwork. B, C and D
each leave the suite green and the game playable; **E is the only phase
that changes what a monster does**, and it is last. The two external
dependencies are PLAN-THROW phase G2 (`m_lined_up`, hard for E) and
PLAN-THROW phase 0 (`stop_occupation`; land it here if missing).

### Phase 0 — the substrate (~1 session, no behaviour change)

1. Audit by grep, not memory, and paste the answer into `zap.py`'s
   docstring as a "needs" list: `occupation.stop_occupation`,
   `m_lined_up`, `core/bhit.bhit`, `conftest.equip`. Whatever PLAN-THROW
   has not landed gets landed here or blocked on (§7).
2. `Monster` gains `mspec_used: int = 0`, `mcan: bool = False`,
   `seen_resistance: int = 0` (the `M_SEEN_*` mask) — three fields, with
   the C provenance in the docstring, and the `mspec_used` decrement in
   `step`'s monster loop (decision 12).
3. `mondata`: the eight `resists_<type>(ptr)` queries over
   `PerMonst.mresists`, `mon_resists(mon, dmg_type)`, and
   `rules.resists` delegating (decision 9).
4. `mondata`: `m_seenres(mon, mask)`, `monstseesu(world, mask)` (every
   actor with `m_can_see_u`), `monstunseesu(world, mask)` — the tables
   (`M_SEEN_*`, `cvt_*`) already exist, only the writers are missing.
5. The two mutators §2.9 needs: `doors.destroy_door(world, pos, mask)`
   (sets the doormask, `recalc_block_point`, returns the message) and
   `traps.t_at(world, pos)` + `traps.delfloortrap(world, trap)`.
6. `occupation.stop_occupation(world) -> List[Event]` **and** the
   `run_occupation` fix (return the interrupted generator's events), if
   PLAN-THROW phase 0 has not already.

**Exit:** the suite is 521+ green, the demo game is unchanged, and four
new tests exist: a fire elemental resists fire *because it is one*, a
goblin resists nothing, `mspec_used` counts down for a monster that does
not act, and an interrupted meal prints "You stop eating."

### Phase A — the encoding and the names (~0.5 session)

1. `zap.py`: `ZT_MAGIC_MISSILE … ZT_ACID` (zap.c 45-52), `ZT_WAND` /
   `ZT_SPELL` / `ZT_BREATH`, `BZ_U_*` / `BZ_M_*`, `bz_ofs_ad`,
   `bz_valid_adtyp` (`AD_MAGM <= adtyp <= AD_SPC2`), `zaptype`.
2. `FLASH_TYPES` (30 entries, 71-85), `HALLU_BLASTS` (96, 31-48),
   `BREATH_NAMES` (10, 24-28), `rnd_hallublast(rng)`,
   `flash_str(btype, hero, nohallu=False)`, `breath_name(typ, hero)`.
   Hallucination is `hacklib.is_hallucinating(hero)` (the *hero's*
   perception, as in C).
3. `ZapEffect` += `ACID`, `POISON_GAS`, `DISINTEGRATE`; `ZAP_EFFECTS`
   entries for the first two (the DEATH/DISINTEGRATE split is phase B,
   where `dobuzz` can pick it).
4. Tests: `flash_str` for all 30 indices against a literal table; the
   breath names for the eight `AD_*` values (`AD_MAGM` → `"fragments"`,
   `AD_DISN` → `"a disintegration blast"`); a hallucinating hero gets a
   name out of the 96 and a `SeqRng`-pinned one; `zaptype` round-trips
   every family (`bz_m_breath(5)` → `-25` → `zaptype` → `25`).

**Exit:** the three tables and the arithmetic are in and tested, no
engine change, suite green.

### Phase B — `dobuzz` part 1: the walk and the monster victim (~1.5 sessions)

1. `zap_hit(ac, spell_bonus, rng)` (4718-4734) with `worn.ac_value`.
2. `dobuzz(world, btype, nd, start, (dx, dy), rng, caster_id,
   sayhit=True, saymiss=False, forcemiss=False)`: the `rn1(7,7)` range,
   the per-square walk, the off-map/`STONE`/`zap_pos` stop (no bounce
   yet — the beam stops where it stopped before), the first-monster
   `zap_hit`, the dispatch to `ZAP_EFFECTS`, `range -= 2` on a hit and
   the walk **continuing through** the monster, the "Misses." /
   "whizzes by" lines.
3. `zap()` becomes the wrapper; `use_wand` splits on `oc_dir` (decision
   7); `cast_spell` unchanged (it already calls `zap()`).
4. `ZAP_EFFECTS` becomes a producer (decision 5) and `use_wand` /
   `cast_spell` end with `process_events`.
5. Migrate the five `test_zap.py` sequences; delete the "no AC-based
   `zap_hit`" simplification from the docstring.
6. New tests: a beam that **misses** (`SeqRng` `chance = 2` against a
   monster whose `find_mac` is `-1` — the gray dragon's row; note in the
   test that a goblin's `find_mac` of `10` *cannot* be missed by a beam,
   which is C's arithmetic and not a bug), a second monster hit behind
   the first (the range survives by 2), a beam whose range runs out
   before the wall, and `zap_hit`'s 1-in-20 duck (`chance == 0`).

**Exit:** the five ray wands and five ray spells run on `dobuzz`; the
five IMMEDIATE wands are byte-identical to today (test them:
`WAN_STRIKING` still resolves through the old walk); suite green.

### Phase C — `dobuzz` part 2: the hero victim (~1.5 sessions)

1. `zhitu(world, btype, nd, caster_id, rng) -> List[Event]` (4414-4605):
   the eleven cases reduced to what exists — `Antimagic`/`Fire_resistance`
   /… via `has_property`, `d(nd,6)`, `destroy_items`/`ignite_items`
   (deferred, §5.2), `fall_asleep`, the disintegration order (see 2),
   `poisoned` → `apply_poison`, `acid_damage`/`erode_armor`,
   `Half_spell_damage` only for `abstyp < 20`.
2. **The disintegration branch is not `worn.disintegrate_arm`.** That
   function is the (blessed) scroll's (`do_wear.c#disintegrate_arm`) and
   strips the first worn piece in the *scroll's* order — cloak, suit,
   shirt, helmet, gloves, boots, shield. `zhitu`'s order is **shield,
   else suit (+ cloak), else the hero dies (cloak and shirt destroyed
   first, in case of life-saving)**. Two orders, two callers: either a
   parameter or a separate small function, but not a silent reuse — a
   hero in cloak+shield survives the scroll and dies to the dragon.
3. The hero branch of the walk: `zap_hit(uac, 0)`, "`the blast of fire
   hits you!`", the miss lines, `stop_occupation`, `nomul(0)` →
   `stop_occupation` (one call in the port), and `flashburn`'s `d(nd,50)`
   draw kept as a *named* stub that still consumes the draw (the
   draw-order rule: an unported branch keeps its roll, PLAN-MKLEV
   decision 6).
4. Reflection: `Prop.REFLECTING` → "`But the blast of fire reflects from
   your shield!`", the direction reverses, `monstseesu(M_SEEN_REFL)`.
5. Tests: a `BZ_M_WAND` fire beam at the hero from 3 squares hits, takes
   `d(6,6)` and interrupts a running meal; a fire-resistant hero
   (`intrinsics={Prop.FIRE_RES}`) takes 0 and says "You don't feel hot!";
   a reflecting hero sends it back and the *monster* takes the damage; a
   `SeqRng` miss prints "It misses."; and a black dragon's blast takes
   the shield first, the suit second, and the hero only third (the test
   calls `dobuzz(BZ_M_BREATH(BZ_OFS_AD(AD_DISN)), 1, …)` directly — the
   engine takes any flavour from phase A; only the *dispatch* from
   `mattacku` waits for phase E).

**Exit:** the hero can be hit by a beam, and the three defences
(resistance, reflection, AC) each have a test.

### Phase D — `dobuzz` part 3: terrain and the bounce (~1.5 sessions)

1. `bounce_dir` (4677-4715) + `zap_pos(terrain)` + the `make_bounce`
   block with the `10 / 20 / 75` chances; the "`The bolt bounces!`" line.
2. `zap_over_floor(world, pos, btype, rng)` (5154-5511) reduced to a
   `TERRAIN_ZAPS` table (the `FLOOR_EFFECTS`/`BREAK_EFFECTS` pattern):
   **implemented** = the secret-door reveal (5412-5423), the
   closed-door destruction table (5426-5501) via `doors.destroy_door`
   (fire→`D_NODOOR`, cold→`D_NODOOR`, disintegration→`D_NODOOR`,
   lightning→`D_BROKEN`), the burning web (5177-5186) via
   `traps.delfloortrap`, `burn_floor_objects` (5503-5507, deferred with
   the object-destruction wave) and `wakeup` (5508-5509).
   **Named, empty** = ice/water/lava (`melt_ice`, `create_gas_cloud`),
   trees, fountains, sinks, iron bars, `*_wall`, with the C span in each
   entry. The return value is C's `rangemod` and the walk applies it
   (`-1000` = stop) — dropping it means a door silently does not stop a
   beam.
3. Re-pin the zap tests phase B left alone, and add: a bolt fired at a
   wall two squares away bounces back and hits the *hero*; a bolt fired
   at a closed door destroys it and stops there; a bolt fired into a room
   with a burning web removes the web; a bolt with `range` 1 that hits a
   monster bounces and dies.

**Exit:** terrain is data-driven, every branch names its C, no unported
branch silently does nothing (each has a message or an explicit empty
body).

### Phase E — the breath (~1.5 sessions)

*Needs PLAN-THROW G2 (`m_lined_up`) and its `range2` gate in `mattacku`.*

1. `mattacku`: `range2 = not adjacent` (the value PLAN-THROW G1
   introduced), and the `AT_BREA` case — `if range2: breamu(...)` —
   replacing the `distance_atk_type` skip for `AT_BREA` only (`AT_MAGC`
   and `AT_GAZE` stay skipped; `AT_SPIT` is PLAN-THROW H).
2. `core/mthrowu.py`: `breamm` / `breamu` (and `breath_name` re-use),
   with C's order: `m_lined_up` → `mcan` (coughs) → the
   `m_seenres(mtmp, cvt_adtyp_to_mseenres(typ))` / `M_SEEN_REFL`
   short-circuit (returns `M_ATTK_HIT` *without* breathing — a cancelled
   attack still counts as the monster's action) → `!mspec_used and
   rn2(3)` → `dobuzz(BZ_M_BREATH(...), mattk.damn, …, sayhit=utarget,
   saymiss=utarget)` → `nomul(0)` → `mspec_used = 8 + rn2(18)`, `+rnd(20)`
   for sleep breath.
3. `get_atkdam_type` is already there — call it, do not re-roll `AD_RBRE`
   by hand.
4. `step._monster_turn`: the "can see the hero and has a ranged attack
   may attack instead of/after moving" arm (C's PHASE FOUR), so a dragon
   at distance 5 attacks rather than walking into melee every turn.
   **Gate it on `ranged_attk(mdata)`** — three of the four distance types
   are still STUBs.
5. Tests: a gray dragon 3 squares away breathes — the hero takes `d(4,6)`
   (`SeqRng`-pinned), "The gray dragon breathes fragments!" appears, the
   dragon's `mspec_used` is `8 + rn2(18)` and the *next* turn produces no
   breath; a black dragon's disintegration takes the hero's shield (not
   the cloak — phase C's order); `mcan=True` → "The gray dragon coughs."
   and no beam; a dragon
   adjacent does **not** breathe (it melees); a hero with
   `seen_resistance=M_SEEN_MAGR` is not breathed at; a dragon breathes
   through an intervening goblin (the goblin takes it, `range -= 2`, the
   hero is hit too); `test_demo_full_game_is_deterministic` unchanged.

**Exit:** `mthrowu.c` is 6/28 (the four breath functions + `breathwep_name`
and `rnd_hallublast` if they had stayed there — see decision 4) and
`zap.c` gains eight exact names; a dragon in a test room is the most
dangerous thing in the dungeon.

### Phase F — the paperwork (~0.5 session)

1. `zap.py` docstring: the new Simplifications list (each with its owner),
   the "needs" list from phase 0, and the three traversals named
   (`bhit` / `dobuzz` / `m_throw`).
2. `ARCHITECTURE.md`: the `zap.c#dobuzz` row and the breath line in the
   turn-loop diagram; `CHANGES.md` gains the "Wave 8" entry with the five
   decisions that matter (one engine; intents-not-mutations; `oc_dir`
   decides the caller; `mresists` becomes real; the encoding stays ints);
   `INDEX.md`/`ledger` are regenerated by their tools, not by hand.
3. `PLAN-THROW.md` cross-references: its §5.11 "breath weapons are a
   different plan" now points here, and its §7 "the breath engine" row
   is resolved.

---

## 5. Deliberate divergences

1. **No display.** No `tmp_at`, no `nh_delay_output`, no `newsym`. The
   beam is invisible; the messages carry the whole story. The console's
   per-turn redraw means a beam and its bounce are indistinguishable from
   a single flash — acceptable, and it is what the wand port already does.
2. **No `destroy_items` / `ignite_items`.** C's fire/lightning branches
   destroy *items in the hero's pack* (fire also ignites). Those are
   `zap.c` 5978-6111, they need the inventory-destruction machinery, and
   the armour erosion half (`burnarmor`/`erode_armor`) is already ported
   and *is* used. Consequence: a fire breath burns your cloak's
   enchantment but never destroys your scrolls.
3. **No `ugolemeffects`.** A fire-breathing hero-golem does not heal from
   fire; the hero is never a golem (no polymorph).
4. **No monster reflection, no `defended(mon, AD_x)`.** `mon_reflects`
   needs a monster wearing a source of reflection; nothing in the subset
   carries anything (`PLAN-THROW` §2.5 says the same about weapons).
   Consequence: a monster's beam cannot be bounced off a *monster*.
5. **No gas clouds.** `create_gas_cloud` and the `gas_hit` deferral in
   `dobuzz` are dropped; poison gas damages and leaves nothing behind
   (C leaves a 1×1 cloud). This is the one divergence a player could
   notice — poison-gas breath is a one-square effect here.
6. **No shop billing.** `pay_for_damage` / `add_damage` are
   PLAN-SPECIAL-ROOMS; a breath that destroys a shop door bills nobody.
7. **No fireball.** `ZT_SPELL(ZT_FIRE)`'s `explode()` (5040-5041) is the
   `explode.c` wave; the port's `spells._fireball` already has its own
   reduced area burst and keeps it.
8. **No Riders, no `PM_DEATH` absorption.** `is_rider`/`PM_DEATH` do not
   exist in the subset; the two special cases in 4901-4925 are named in
   the docstring.
9. **No steed intercept.** `u.usteed` does not exist (no riding).
10. **No `Half_spell_damage`.** No artifact/property conveys it in the
    subset; the `abstyp < 20` test is written anyway (it costs one line
    and it is where the future prop goes).
11. **`zhitm`'s `resist(mon, WAND_CLASS, 0, NOTELL)` half-damage is not
    ported.** That is the monster's *magic-resistance percentage roll*,
    not a type resistance; the port's defence is the `MR_*` bit test
    (decision 9), which is binary. Already true of the existing zap port;
    recorded here because breath is where a player would notice.
12. **`breamm`'s pet hunger line is dropped** (no pets, no `EDOG`).
13. **`breamm`'s `mux/muy` (remembered hero position) is the live hero
    position** — monsters have no memory (PLAN-THROW decision 12, same
    divergence, same place).
14. **`nomul(0)` and `stop_occupation()` are one call in the port.**
    pyhack's only multi-turn action *is* the occupation; C's `nomul` also
    clears `gm.multi` (the repetition counter and the helplessness
    count), which have no counterpart. Consequence: a beam that hits the
    hero cannot cancel a repeated command, because no command repeats.

---

## 6. Traps

- **The double-apply.** `mattacku`'s events go through
  `process_events` (`step.py:169`); `use_wand`'s do not. A `dobuzz` that
  calls `apply_damage` directly double-counts every breath (the processor
  applies the `DamageEvent` that `apply_damage` returned) and the
  symptom is a dragon that does *exactly* twice its damage — which looks
  like a damage-formula bug, not an architecture bug. Decision 5 exists
  for this; if the implementer "fixes" it by making `mattacku` call
  `apply_damage` directly instead, `test_mhitu`'s producer assertions and
  the `mhitu`-wide convention break.
- **`zap_hit`'s comparison is `3 - chance < AC_VALUE(ac)`, and a *bigger*
  `AC_VALUE` means *easier* to hit.** `find_mac(mon)` is the raw
  `mons[].ac` (goblin `10` = AC 10, easy; gray dragon `-1` = AC -1,
  hard), and `AC_VALUE` only does something for the negative half
  (`-rnd(-ac)`, the anti-invulnerability roll — `worn.ac_value` already
  implements it, and it draws **only** when `ac < 0`: the PLAN-ARMOR
  determinism note). So: a goblin can never be missed by a beam, a
  dragon is missed when `chance <= 4`, and a test that forgets the sign
  silently asserts a hit. Assert both AC sides in the `zap_hit` unit
  test (`ac = 10` → no draw, `ac = -3` → one draw).
- **A dragon in a small room hits twice.** After a hit `range -= 2` and
  the walk continues; with bounce, the beam comes back through the hero
  and hits again. A test that asserts "the hero takes 4d6 once" passes in
  phase C and fails in phase D. Budget `rn2(20)` per monster square in
  the `SeqRng`, and write the phase-D test that *proves* the second hit
  (it is the cheapest bounce test in the plan).
- **`zap_over_floor`'s return value is not optional.** `rangemod` of
  `-1000` is how a closed door stops a beam and `-3` is how water eats
  range. A port that returns messages only lets a bolt pass through a
  closed door — the exact bug `closed_door()` exists to prevent, and one
  no test would catch unless it is written (phase D's door test).
- **The pinned `SeqRng` sequences in `test_zap.py` are *positions*, not
  counts.** `SeqRng.rn2(x)` returns `value % x`, so the value `1` means
  "chance 1" in one slot and "damage die 1" in the next. When migrating,
  write each new sequence with a comment per position
  (`# rn1(7,7)`, `# zap_hit rn2(20)`, `# d(6,6)`), or the next session
  will have no idea what the numbers mean.
- **`zap_hit` vs `u.uac` vs `hero.ac`.** `u.uac` is the *computed* AC
  (`worn.uac(world, hero)`), never `hero.ac` (the body AC). PLAN-THROW's
  trap list makes the same point about `thitu`; here it is the beam's
  to-hit. A raw `hero.ac` silently ignores every piece of worn armour.
- **`M_SEEN_*` is written for monsters that can *see* the hero, and it
  is sticky.** `monstseesu` marks every seeing monster; `breamm` then
  reads its own mask. Getting the direction wrong (writing on the *hero*)
  or forgetting `monstunseesu` (the "no longer resists" path) leaves a
  dungeon full of dragons that never breathe again — a bug that looks
  like "breath does not work" with a perfectly green suite.
- **`mspec_used` decremented inside `mattacku` never runs for a monster
  that does not attack.** C decrements it in `mon_regen`, i.e. from
  `mcalcdistress`, i.e. for every monster every turn. A dragon that is
  asleep, or that the hero cannot see, or that is off-level, must still
  cool down (decision 12).
- **`AT_BREA` and the `distance_atk_type` skip.** The skip at
  `mhitu.py:490` fires *before* the dispatch switch, so adding the
  `AT_BREA` case to the switch below it does nothing at all. Remove the
  skip for that one type (and keep it for `AT_MAGC`/`AT_GAZE`), or the
  phase-E test passes and never runs.
- **A cancelled monster returns `M_ATTK_HIT`, not `M_ATTK_MISS`.** C's
  `breamm` returns `M_ATTK_HIT` both when it breathes and when it
  *knows* the hero resists (1113-1115). The difference matters: `sum[i]`
  feeds the multi-attack loop, and a `MISS` there makes the dragon retry
  its next attack instead of ending the sequence.
- **`AD_DISN` for a monster is not `DamageType.DEATH`.** A black dragon's
  breath destroys armour; the death ray kills. If `DISINTEGRATE` is wired
  to the DEATH effect, a black dragon becomes a wand of death with 255
  dice — and `test_..._resisted_by_undead` still passes, because the
  *ray* is untouched. Two distinct tests, one per key.
- **`flash_str`'s hallucination path is the *hero's* state, on a
  monster's message.** A hallucinating *monster* must not rename the
  beam. Use `is_hallucinating(hero)` everywhere in these three tables.
- **`SeqRng` raises `IndexError` when it runs out — treat it as the
  feature it is.** It is the cheap detector for "this change added a draw
  nobody budgeted for". Do not silence it by appending values: find out
  which draw appeared (`rn1(7,7)`? `rn2(20)`? `rn2(75)`? a bounce? a
  second hit?) and write it into the comment.
- **`HALLU_BLASTS` is 96 entries and `rn2(96)` is one draw.** C's
  `ROLL_FROM` is `rn2(SIZE(array))`; a port that uses `rng.choice()` gets
  the same value but a different draw pattern than a `randint`, which
  matters the moment a test pins it with a `SeqRng`.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| monsters that hurt the hero from more than one tile, with a real attack type | `distance_atk_type` filtered out |
| a **real** `dobuzz`: bounce, `zap_hit`, per-square terrain, carry-through | a first-monster straight line |
| the first consumer of `PerMonst.mresists` | a four-boolean fiction |
| the first consumer of `m_seenres` (monsters that *learn*) | three unused tables in `mondata` |
| three new `ZapEffect` keys (acid, poison gas, disintegration) | 11 keys, no breath types |
| hero-side damage through the intent path (`use_wand`/`cast_spell`) | the hero mutates, the monster emits — one beam engine could not be both |
| `stop_occupation` as a real interrupt (2nd caller) | absent |
| a door that can be destroyed (fire/cold/lightning/disintegration) | open / close only |
| `zap_over_floor`'s `TERRAIN_ZAPS` table for the elements | nothing |
| the `mcastu` / `muse` / horn / priest waves: their engine is now written | `dobuzz` unported |

| needs | from |
|---|---|
| `m_lined_up` / `linedup` / `blocking_terrain` (**hard**, phase E) | PLAN-THROW phase G2 |
| the `range2` gate in `mattacku` (**hard**, phase E) | PLAN-THROW phase G1 |
| `stop_occupation` (+ the `run_occupation` event-drop fix) | PLAN-THROW phase 0, else land it here |
| `conftest.equip`-style helpers for a typed monster in a room | PLAN-THROW phase 0 |
| a breather that can be *placed* (playability, not writability) | PLAN-MAKEMON A (table) + C (selection) + D (placement) |
| `explode.c` for a real fireball, `destroy_items` for item loss | their waves |
| `polyself.c` for a hero that breathes | the polymorph wave |
| `bhit()`'s `ZAPPED_WAND` half for the IMMEDIATE wands | the rest-of-`weffects` wave |

---

## 8. Definition of done

- [ ] `core/zap.py` carries `dobuzz`, `zap_hit`, `zhitm` (the registry),
      `zhitu`, `zap_over_floor`, `bounce_dir`, `zaptype`, `flash_str`,
      `breath_name`, `rnd_hallublast`, each with its C span in the
      docstring
- [ ] the beam type is C's integer encoding, and the three name tables
      are indexed by it; the hallucination path picks from all 96
- [ ] a beam rolls `zap_hit`, carries through a hit with `range -= 2`,
      bounces off a wall (`10/20/75`), and can hit its own caster
- [ ] `ZapEffect` has `ACID`, `POISON_GAS`, `DISINTEGRATE`; the black
      dragon's blast destroys armour and the death ray still kills
- [ ] `zhitu` resolves a hero hit through `has_property` resistance,
      `Prop.REFLECTING`, AC and `apply_*` statuses, and interrupts an
      occupation
- [ ] `dobuzz` is a pure producer; `use_wand` and `cast_spell` process
      their own events; no path applies damage twice
- [ ] `use_wand` dispatches on `OBJECTS[].oc_dir`; the five `RAY` wands
      and the five ray spells run on `dobuzz`, and the five `IMMEDIATE`
      wands are unchanged
- [ ] `mattacku` has the `AT_BREA` case behind `range2`; `AT_MAGC` and
      `AT_GAZE` are still skipped and named
- [ ] `mthrowu.breamm`/`breamu` port C's order: lined up → cancelled →
      seen-resistance → `rn2(3)` → `dobuzz` → `mspec_used` →
      `(8 + rn2(18))`, `+rnd(20)` for sleep
- [ ] `Monster.mspec_used` decrements once per monster per turn, acting
      or not; `Monster.mcan` and `seen_resistance` exist and are written
      by `monstseesu`/`monstunseesu`
- [ ] `rules.resists` reads `PerMonst.mresists`; the four booleans are the
      `mdata is None` fallback; the three demo kinds still resist nothing
- [ ] `zap_over_floor` is a `TERRAIN_ZAPS` table: doors, secret doors and
      burning webs implemented; ice/water/lava/trees/fountains/sinks/iron
      bars/unported walls named with their C span
- [ ] the five `test_zap.py` sequences are migrated with a comment per
      draw position, and the "no `zap_hit`" simplification is deleted
      from the docstring
- [ ] `test_demo_full_game_is_deterministic` unchanged (the demo has no
      breather and no `RAY` wand in play)
- [ ] `mypy` clean, `flake8` clean, the suite green
- [ ] `ARCHITECTURE.md` gains the `dobuzz` row and the breath step;
      `CHANGES.md` a "Wave 8" entry; `PLAN-THROW.md` §5.11 points here
