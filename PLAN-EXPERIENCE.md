# Plan: experience & leveling system (the exper.c port)

**Status (this round):** planned — nothing implemented yet.  The round
lands: the XP fields on the hero, the kill-XP formula, XP gain on
hero-kills (melee, wand and spell alike), leveling up (HP / Pw / level,
the C messages), level *loss* (`losexp`, the drain path), and the
status-line display.  Ground truth is the NetHack 5.0 C source (local
clone at `../NetHack`); the deep reference is `src/exper.c`
(~350 lines, fully read for this plan) plus the verified fragments
cited in section 1.  The 5.0 experience system differs from 3.6 in one
structural way that this plan follows: **`struct permonst` has no
`mexp` field anymore** (verified in `include/permonst.h`) — the XP of a
kill is *computed* from the monster's instance level, effective AC,
speed and attack table by `experience()` in exper.c, not read from a
table column.

Already in pyhack that the port builds on:

- `core/types.py` `Monster` — `ulevel: int = 1` ("fixed in the demo" —
  this round removes that), `hp` / `max_hp`, the spell-power quartet
  `uen` / `uenmax` / `uenpeak` / `ueninc[MAXULEV]` (the same
  per-level bookkeeping array C uses for `ueninc[]`), `mdata`
  (PerMonst), `ac` (base body AC; the effective AC is computed, never
  cached — `core.worn.uac`);
- `core/energy.py` — `newpw(ulevel, rng)` (the Pw-per-level gain; its
  low-level branch is C's exactly, the higher levels are the
  documented interpolation), `init_energy`, `tick_energy` (the regen
  period is computed from the level directly, as in C `regen_pw` —
  `ueninc[]` is the per-level Pw INCREMENT, the newpw / losexp
  bookkeeping the experience system shares with it; init records
  ueninc[0], pluslvl records the old level's slot);
- `core/rules.py` — `apply_damage` (the ONLY place an actor loses HP;
  it already flips `alive` and emits the `DeathEvent(target, by=source)`
  — the kill choke point the XP hook lands in) and `process_events`;
- `core/uhitm.py` / `core/mhitu.py` / `core/zap.py` — the kill sources
  (hero melee `source="player"`, monster melee the monster id, zaps
  `source="zap:xxx"` — see decision 4);
- `core/worldgen.py` — the demo hero (Wizard, fixed abilities,
  `ulevel=1`, 25 HP) and the demo monsters (typed goblins / orcs /
  bats, zero rng draws for the data);
- `core/monst.py` / `core/monst_defs.py` — `PerMonst` with `mlevel`,
  `mmove`, `ac`, `mattk` (the `AT_*` / `AD_*` / `damn` / `damd` the
  XP formula reads); the demo subset includes `PM_MAIL_DAEMON` (the
  C special case below is live);
- `ui/console.py` — the status line (HP / Pw / AC / weapon) the
  level + XP fields join.

## 1. What the C code actually does (reference)

| Mechanic | C location | Notes |
|---|---|---|
| XP threshold | `src/exper.c` `newuexp(lev)`: `lev < 1 → 0`; `lev < 10 → 10·2^lev`; `lev < 20 → 10000·2^(lev−10)`; `else → 10000000·(lev−19)` | the "exp needed to reach level `lev`"; L1→2 = 20, L2→3 = 40, …, L9→10 = 5120, L10→11 = 10000, …, L19→20 = 5 120 000, L20→21 = 10 000 000 |
| Kill XP | `src/exper.c` `experience(mtmp, nk)`: base `1 + m_lev²`; AC bonus if effective AC `find_mac < 3`: `+ (7−i)·(2 if i<0 else 1)`; speed bonus if `mmove > 12`: `+5` if `> 18` else `+3`; per attack `aatyp > AT_BUTT`: `AT_WEAP +5`, `AT_MAGC +10`, other `+3`; per attack damage: `AD_PHYS < adtyp < AD_BLND → +2·m_lev`, `AD_DRLI/AD_STON/AD_SLIM → +50`, other non-`AD_PHYS → +m_lev`, heavy damage `damd·damn > 23 → +m_lev`, eel `AD_WRAP` vs non-amphibious `+1000`; `extra_nasty(ptr) → +7·m_lev` (the mondata.c class list: S_XAN / S_JABBERWOCK / S_WRAITH / S_UMBER / S_VAMPIRE / S_TROLL / S_NYMPH / S_XORN / S_GHOST / S_ELEMENTAL / S_ZRUTY / S_GOLEM / S_QUANTMECH / S_MUMMY / S_GIANT / S_LICH / S_DRAGON — verify the list against `src/mondata.c` at implementation); `m_lev > 8 → +50`; `PM_MAIL_DAEMON → 1` (5.0: `MAIL_STRUCTURES` always defined); revived/cloned kills decay with the per-type kill count `nk` (halving bands 21..40 / 41..80 / …) | `m_lev` is the INSTANCE level: `newmonhp()` in `src/makemon.c` sets `mon->m_lev = adj_lev(ptr)` (C rolls `rnd(mlevel)`; level-0 monsters stay 0 — the goblin / bat are level 0); `find_mac()` is the monster's effective AC (worn.c) |
| Grant on kill | the kill path in `src/mon.c` (C 3.6: `killmon()` → `mkill()`: `xp = experience(mtmp, nk); more_experienced(xp, rexp);` then the level check); **verified: 5.0's `mondead()` (mon.c:3086-3182) does NOT grant XP** — the grant stays in the kill wrapper, only for hero-caused kills | pyhook mirror: the `apply_damage` choke point (decision 3) |
| XP accumulation | `src/exper.c` `more_experienced(exper, rexp)`: `uexp += exper` (cap at `LONG_MAX` on wraparound), `urexp += 4·exper + rexp` (the SCORE XP; kill passes `rexp = 0`); `urexp >= (wizard ? 1000 : 2000)` → `flags.beginner = FALSE`; botl refresh | no pline — XP gain is silent in C |
| Level check | `src/exper.c` `newexplevel()`: `if (u.ulevel < MAXULEV && u.uexp >= newuexp(u.ulevel)) pluslvl(TRUE);` | AD&D-style: at most ONE level per call site (the comment in exper.c says so explicitly) |
| Level up | `src/exper.c` `pluslvl(incr)`: `hpinc = newhp()`; `u.uhp += hpinc; setuhpmax(uhpmax + hpinc)`; `eninc = newpw()`; `uenmax += eninc; uenpeak = max(uenpeak, uenmax); uen += eninc`; the uexp carry: `incr` → `if (uexp >= newuexp(ulevel+1)) uexp = newuexp(ulevel+1) − 1` (the overflow past the NEXT threshold is forfeited), `incr == FALSE` → `uexp = newuexp(ulevel)`; `++ulevel`; `pline("Welcome %sto experience level %d.", (ulevelmax < ulevel) ? "" : "back ", ulevel)`; `ulevelmax = max(ulevelmax, ulevel)`; `ulevelpeak = max(...)`; `adjabil(old, new)` (role/race intrinsic grants at fixed levels); livelog / rank achievements | `newhp()` and `newpw()` are evaluated at the OLD level, and `newhp` records its result in `u.uhpinc[ulevel]` (the per-level HP increment, later subtracted by `losexp`) |
| HP per level | `src/attrib.c` `newhp()`: role/race `hpadv` table — the Wizard row (verified in `src/role.c`): **lower** `lofix 0 + rnd(6)`, **higher** `hifix 1 + rnd(0)` (split at `xlev 12`) — plus the CON table: `≤3 → −2`, `≤6 → −1`, `≤14 → 0`, `≤16 → +1`, `17 → +2`, `18 → +3`, `else +4`; floored at 1; recorded in `uhpinc[ulevel]`; post-MAXULEV throttle (1200 cap) | pyhack has no role/race selection — see decision 5 |
| Pw per level | `src/exper.c` `newpw()` (5.0): role/race `enadv` table — the Wizard row (verified): **lower** `0 + rnd(1)`, **higher** `1 + rnd(1)` — `en = enermod(rn1(enrnd, enfix))` with `enrnd = WIS/2 + lo/hi rnd`, and `enermod` ×2 (cleric/wizard), ×3/2 (healer/knight), ×3/4 (barbarian/valkyrie); post-MAXULEV throttle (600 cap) | pyhack's `core.energy.newpw` is the committed simplified stand-in (decision 6) |
| Level loss | `src/exper.c` `losexp(drainer)`: `resists_drli` bail-out; `pline("%s level %d.", Goodbye(), u.ulevel)` ("Goodbye level N."; level 1 + drainer → `done(DIED)`, level 1 no drainer → `uexp = 0`, no level change); else `ulevel--`, `adjabil(old, new)`, `uhpmax -= uhpinc[ulevel]` floored at `minuhpmax(10)` = `max(CON·2, 10)`, `uhp` adjusted (floor 1, capped at uhpmax), `uenmax -= ueninc[ulevel]` (floor 0), `uen` adjusted, `uexp = max(0, newuexp(ulevel) − 1)` | C callers: the `AD_DRLI` drain attacks (mhitu / mhitm), divine anger (`losexp(NULL)` — adjalign), the min-strength loop in attrib.c, wizard mode |
| Random XP | `src/exper.c` `rndexp(gaining)`: `minexp = newuexp(ulevel−1)` (0 at L1), `maxexp = newuexp(ulevel)`, `result = minexp + factor·rn2(diff)` (with the LARGEST_INT halving) + the MAXULEV gaining addendum | C callers: potion of gain experience, polyself — NO C caller in the demo yet (decision: defer) |
| Hero fields | `include/you.h` `struct you`: `int ulevel, ulevelmax, ulevelpeak` (L378-381); `long uexp, urexp` — "exper pts for gaining levels and for score" (L487); `int uhp, uhpmax, uhppeak`; `xint16 uhpinc[MAXULEV], ueninc[MAXULEV]` (L476-481) | pyhack: on `Monster` (the hero is a monster with `is_hero=True`) |
| Display | `src/botl.c`: the experience field prints `u.uexp` when `flags.showexp` (the BEXP status entry; the level is part of the hero name field) | pyhook mirror: the console status line (decision 8) |
| Instance level | `src/makemon.c` `newmonhp()`: `mon->m_lev = adj_lev(ptr)` (level-0 monsters stay 0 — "level 0 monsters use 1d4"; golems fixed HP; riders 10d8; `mlevel > 49` = encoded fixed HP, `m_lev = mhp/4`) | pyhack mirror: spawn-time `m_lev` (decision 2) |

**Worked demo numbers** (the demo cave's kill economy, from the
committed `MONS` rows: goblin `mlevel 0 / mmove 6 / ac 10 / AT_WEAP
1d4`, hill orc `mlevel 2 / mmove 9 / ac 10 / AT_WEAP 1d6`, bat
`mlevel 0 / mmove 22 / ac 8 / AT_BITE 1d4`):

- goblin: `1 + 0 + 5 (AT_WEAP)` = **6 XP**
- hill orc: `1 + 4 + 5 (AT_WEAP)` = **10 XP**
- bat: `1 + 5 (mmove 22 > 18)` = **6 XP**
- the whole level-1 cave (4 goblins / 2 orcs / 3 bats) = **62 XP** →
  level 2 at the 4th kill (24 ≥ 20), level 3 at the 9th (62 ≥ 60) —
  a full clear lands the hero at level 3, a satisfying demo arc

## 2. Design decisions (decide once, keep consistent)

1. **One new module: `core/experience.py`** (the exper.c port).  Pure
   functions over `World` + injected `rng`; the hero-facing messages
   come out as `MessageEvent`s.  No new `Event` subclasses (C's XP gain
   is silent + botl refresh; the level messages are plain plines) —
   same policy as the hunger port.
2. **Data on `Monster`** (the hero-only fields are unused by the
   monster actors, exactly as C keeps the `u.*` fields on `struct
   you`): `uexp: int = 0`, `urexp: int = 0`, `ulevelmax: int = 1`,
   `ulevelpeak: int = 1`, `uhpinc: List[int] = [0] * MAXULEV` (the
   per-level HP increment; the Pw half already exists as `ueninc`),
   and `m_lev: int = 0` — the monster INSTANCE level (C
   `mtmp->m_lev`), which the XP formula's `1 + m_lev²` reads.
   `m_lev` is set at spawn to `mdata.mlevel` (flat-stat demo monsters
   keep 0) — **zero rng draws**, the seed-42 draw-sequence test and
   `test_new_world_makes_no_new_rng_draws` stay untouched (documented
   simplification of C's `adj_lev` roll `rnd(mlevel)`, section 4).
3. **The XP grant lives in the death choke point.**  C grants XP in
   the kill path for hero-caused kills; pyhack's equivalent choke
   point is `rules.apply_damage` (the only place an actor loses HP —
   it already emits the `DeathEvent(by=source)`).  When the dead actor
   is a non-hero monster and `source == world.hero.id`, `apply_damage`
   calls `experience.grant_kill_xp(world, mon)`: `xp =
   kill_experience(world, mon)` (no draws) → `more_experienced(world,
   xp)` → `newexplevel(world)`.  The hero id `"player"` is the
   convention every hero-caused source already uses (melee
   `source=attacker_id`); non-hero sources (monster ids,
   `"trap:trap_0"`, `"poison"`) grant nothing — matching C.
4. **Normalize the zap damage sources to the caster id.**  The
   `DamageEvent.source` docstring already promises "actor id,
   `trap:trap_0`, …", but the zap effects pass `"zap:striking"` /
   `"zap:death"` / `"zap:undead_turning"`.  The zap effect functions
   already receive the `caster`, so the change is `apply_damage(...,
   source=caster.id)` in `_zap_damage` / `_zap_striking` /
   `_zap_undead_turning` — wand *and* spell kills then flow through
   the same XP gate (C: every hero-caused kill grants XP).  The
   `test_zap.py` assertions on the source strings update with it
   (and `DeathEvent.by` for a zap kill becomes `"player"`, consistent
   with the melee kills `test_demo.py` already asserts).
5. **`newhp()` for the demo: draw-free.**  C's formula is
   role/race-`hpadv`-driven (Wizard: `rnd(6)` below xlev 12) plus the
   verified CON table.  pyhack has no role/race selection, so the demo
   `newhp(hero)` = **fixed base 2 + the C CON table** (the demo hero's
   CON 12 → `+0` → 2) — one documented number, zero draws, and the
   `uhpinc[]` bookkeeping (init records `uhpinc[0]`; `pluslvl` records
   `uhpinc[old_level]`; `losexp` subtracts `uhpinc[new_level]`) works
   exactly as in C.  The hpadv rnd lands with the role-selection port.
6. **Level-up Pw reuses `core.energy.newpw(ulevel, rng)`** (the
   committed, tested module — its low-level branch is C's exactly, the
   rest is the documented interpolation).  Evaluated at the OLD level,
   as in C.  Consequence: the FIRST level-up (L1→2) makes ONE rng draw
   (the `4 + 1 + rnd(3)` branch), later ones none — verified safe for
   the pinned suite: no existing test ever reaches level 2 (the
   biggest kill in the tests is 6 XP, the threshold is 20), and the
   determinism tests compare a seed against itself.  The C role/race
   `enadv` + `enermod` formula (Wizard: `2·(1+rnd(6))` low /
   `2·rn1(7,1)` high) is deferred with role selection.
7. **`losexp` lands this round** (it is small, closes the
   "full experience levels" scope, and the `uhpinc[]` it needs is
   already added).  The demo subset has `PM_VAMPIRE` / `PM_WRAITH` /
   `PM_GHOUL` in the table, but `core.mhitu` currently maps `AD_DRLI`
   to plain melee damage (the drain effect is deferred there —
   "the actual drain … come with their respective ports", mhitu.py
   docstring), so `losexp` gets unit tests with a synthetic drain
   call; its live call site lands with the mhitu `AD_DRLI` port.  C's
   `resists_drli` bail-out: the demo hero has no DRLI resistance
   source (no such Prop) — the check is a documented no-op.  The
   level-1 + drainer death goes through the same death bookkeeping as
   `apply_damage` (alive=False + `DeathEvent(by=drainer)`), which
   `step._finish` turns into the `GameOverEvent`.
8. **Botl: the status line shows level and XP.**  `⭐ Lvl: {ulevel}`
   and `📈 XP: {uexp}` join the HP/Pw/AC line (C prints XP with
   `flags.showexp`; the demo is always-on, like the rest of the
   status line).
9. **`more_experienced` carries the score half too.**  `urexp += 4·exper`
   is one line and the field is cheap; pyhack has no score system yet
   (no topten port) — the value is recorded, tested, and displayed
   nowhere.  C's `LONG_MAX` wraparound cap is a no-op for Python ints
   (documented).
10. **`pluslvl(incr)` keeps the C parameter** (`incr=False` is the
    potion-of-gain-level / wraith-corpse / `#levelchange` path).  No
    demo caller of the `False` branch exists this round (no such
    potion, no wizard mode); the function is implemented and unit
    tested directly.  Same for `rndexp`'s caller-free status — but
    `rndexp` itself is DEFERRED (section 5.1), unlike `pluslvl`.
11. **No intrinsics on level up.**  C's `adjabil(old, new)` grants
    role/race intrinsic abilities at fixed levels (the `role_abil` /
    `race_abil` tables, attrib.c); the demo hero has a fixed ability
    set and the intrinsics system is the property work (PLAN-ARMOR.md
    decision 7).  `pluslvl` notes the skipped grant in a comment.
12. **The "back" in the welcome message is live.**  C prints
    "Welcome **back** to experience level N." when `ulevelmax <
    ulevel` (regaining a lost level); both fields are recorded, so the
    losexp→level-up round trip shows the right text (unit tested).

## 3. What lands this round (planned)

| Area | Port | C provenance |
|---|---|---|
| `core/types.py` | `Monster.uexp` / `urexp` / `ulevelmax` / `ulevelpeak` / `uhpinc` / `m_lev` | you.h `struct you` (L378-381, L476-487) |
| `core/experience.py` (new) | `newuexp(lev)`; `kill_experience(world, mon)` (the full `experience()` formula: base, AC bonus via the computed `core.worn.uac`, speed, the two attack/damage loops, `extra_nasty` class set, `m_lev > 8`, the mail-daemon 1-XP case); `more_experienced(world, exper, rexp=0)`; `newexplevel(world)`; `pluslvl(world, incr, rng)`; `newhp(world)` (base 2 + CON table); `init_experience(world)` (records `uhpinc[0]`, no draws); `grant_kill_xp(world, mon)` (the `apply_damage` hook body); `losexp(world, drainer)` | exper.c, attrib.c `newhp` |
| `core/rules.py` | `apply_damage`: on a non-hero monster death with `source == world.hero.id`, grant the kill XP (the hook) | the kill path in mon.c |
| `core/zap.py` | the zap damage `source` = the caster id (the `"zap:xxx"` strings retired) | decision 4 |
| `core/worldgen.py` | spawn-time `m_lev = mdata.mlevel` for the typed demo monsters (flat 0); `init_experience(world)` after `init_energy` (one line, no draws) | makemon.c `newmonhp`; u_init.c |
| `core/energy.py` | unchanged (the level-up Pw reuses `newpw`) | — |
| `ui/console.py` | `⭐ Lvl` + `📈 XP` on the status line | botl.c |
| `tests/test_experience.py` (new) | table-driven over the C branches with `SeqRng`: the `newuexp` table (L1 20 … L30 110 000 000); `kill_experience` for the three demo monsters (6 / 10 / 6) and a flat-stat monster (1); the AC-bonus branches (i = −1 → ×2, 0..2 → ×1, ≥3 → none); the speed branches (13 → +3, 19 → +5); the attack-type bonuses (WEAP / MAGC / other); the damage-type branches (elemental +2·m_lev, DRLI / STON / SLIM +50, other +m_lev, heavy damage +m_lev); `extra_nasty` (+7·m_lev); `m_lev > 8` (+50); the mail daemon (=1); `more_experienced` (uexp / urexp 4×, no message); the level-up (threshold cross: HP +2, Pw gain incl. the ONE draw at L1→2, "Welcome to experience level 2.", ulevelmax / peak, the uexp carry `199 → 39`); the no-level-up case; the full-cave 62-XP arc (L3 after 9 kills); the XP gate (hero melee / hero zap grant; monster kill / trap / poison grant nothing); `losexp` (L2→L1: HP −2, Pw −`ueninc[1]`, uexp = 19, "Goodbye level 2."; L1 + drainer → death + `DeathEvent(by=drainer)`; the "back" message after regaining) | exper.c, attrib.c |
| `tests/test_zap.py` | the source-string assertions update to the caster id | decision 4 |
| `tests/test_step.py` / `tests/test_demo.py` | no behaviour change expected (no test reaches level 2: the biggest test kill is 6 XP); the victory tests gain nothing visible — verified by the suite run | — |
| `README.md`, `ARCHITECTURE.md`, `CHANGES.md` | the module in the layout / diagram, the decisions (the m_lev pin, the draw-free newhp, the zap source normalization), the status line | house style |

Commit granularity: one commit per task (house style), in the order
types → experience module → rules hook + zap sources → worldgen init →
ui → tests → docs.

## 4. Documented simplifications (not bugs)

- **`m_lev` is pinned to `mdata.mlevel`, not rolled.**  C's `adj_lev`
  rolls `1..mlevel` (level-0 monsters stay 0 — the goblin / bat are
  unaffected, they are level 0; the orc rolls 1..2 in C, pyhack pins 2
  — the orc's 10 XP is C's maximum, not its average).  The pin is the
  zero-draw house rule: spawn is draw-free, so the seed-42 layout /
  trap / placement draw sequence and the draw-audit test pass
  unmodified.  A makemon-style spawn port with a real draw budget can
  switch to the C roll later (one line in worldgen).
- **Kill-count decay (`nk`) is out.**  The halving bands of
  `experience()` apply only to `mrevived` / `mcloned` monsters
  (revived corpses, cloned gremlins) — the demo has no revival /
  cloning, so `nk = 1` always and the branch is omitted (the
  function keeps the `nk` parameter, unused, for the C API shape).
- **`find_mac` → the computed `core.worn.uac`.**  The demo monsters
  wear nothing, so effective AC == base `ac` (the formula reads the
  computed value, so it stays correct the day monsters carry gear).
- **`newhp` is draw-free** (decision 5): the C hpadv `rnd` lands with
  role selection.
- **The level-up Pw gain is the `core.energy.newpw` interpolation**
  (decision 6), not C's `enadv` + `enermod` formula.
- **No `resists_drli`** (decision 7): no DRLI-resistance source in the
  demo.
- **The `LONG_MAX` caps in `more_experienced` / `rndexp`** are no-ops
  (Python ints).
- **`flags.beginner` / `exp_percent_changing` / the status hilites**
  (the botl refresh triggers in C) have no pyhack machinery — the
  status line redraws every turn anyway.
- **No livelog / achievements / rank titles** in `pluslvl` (C
  `livelog_printf(LL_MINORAC, ...)`, `record_achievement`) — the demo
  message is the "Welcome …" pline only.

## 5. Deferred (later round, with their machinery)

1. **`rndexp(gaining)` + the potion of gain experience** — needs the
   GAIN EXPERIENCE potion row (absent from `PotionType` / the object
   table subset); C: exper.c `rndexp`, potion.c `peffect_gainexp`.
2. **The mhitu `AD_DRLI` drain call site** — `losexp(drainer)` is
   ready; the hook lands with the drain-effect port (mhitu.py's
   documented deferral: "the actual drain … come with their respective
   ports").  The drainer name is the C killer string (the monster's
   name, the "killed by X" DeathEvent `by`).
3. **Wizard mode `#levelchange`** — the `pluslvl(incr=False)` /
   `losexp("#levelchange")` (non-fatal override) paths are
   implemented and tested; the command lands with a wizard-mode port.
4. **The role/race `hpadv` / `enadv` formulas + `enermod`** — the real
   `newhp` / `newpw` (Wizard verified: hpadv low `0+rnd(6)`, high
   `1+rnd(0)`, xlev 12; enadv low `0+rnd(1)`, high `1+rnd(1)`),
   `adjabil` intrinsic grants, the post-MAXULEV throttles (1200 / 600
   caps) — all land with the role-selection port.
5. **`adjabil` intrinsic grants on level up** — the `role_abil` /
   `race_abil` tables (attrib.c, S30 §10) + the property system
   (PLAN-ARMOR.md decision 7); until then `pluslvl` skips the grant
   (comment).
6. **Score display** — `urexp` is recorded; the total-score
   computation (`botl.c` `total_score`: `urexp + umoney + depthbonus`)
   lands with the topten / high-score port (S26-P2).
7. **`mrevived` / `mcloned` kill-count decay** — with the corpse /
   revival system (PLAN-HUNGER.md deferral 6 chains into it).
8. **The `m_lev` roll** (`adj_lev`: `rnd(mlevel)`, the golem / rider /
   `mlevel > 49` special cases) — with the makemon-style spawn port
   (section 4).
9. **`minuhpmax` / `setuhpmax` / `adjuhploss`** as a general
   max-HP-maintenance port (attrib.c) — the losexp floor
   (`max(CON·2, 10)`) is inlined in `losexp` for now; the full family
   lands with the STR-loss / fire-trap HP-damage work (S30 §10).
10. **Save/restore of the new fields** — with the savefile port (the
    fields are plain dataclass fields; no work beyond the serializer).

## 6. Files touched

| File | Change |
|---|---|
| `core/types.py` | the six new `Monster` fields |
| `core/experience.py` | **new** — the exper.c port |
| `core/rules.py` | `apply_damage`: the kill-XP hook |
| `core/zap.py` | the zap damage source = caster id |
| `core/worldgen.py` | spawn-time `m_lev`; `init_experience` |
| `ui/console.py` | `⭐ Lvl` + `📈 XP` on the status line |
| `tests/test_experience.py` | **new** |
| `tests/test_zap.py` | the source-string assertions |
| `README.md`, `ARCHITECTURE.md`, `CHANGES.md` | layout, behaviour decisions, the status line |

## 7. Risks / open questions

1. **The pinned draw sequences.**  Decided: the kill-XP path is
   draw-free (pure formula + `more_experienced` + the threshold
   check); the only draw is the `energy.newpw` at the FIRST level-up
   (L1→2).  Verified against the suite: no existing test reaches 20 XP
   (biggest test kill 6 XP), `test_new_world_makes_no_new_rng_draws`
   is spawn-only (m_lev is a pinned field), and the determinism tests
   compare a seed against itself.  The full suite run at the end of
   the round is the check.
2. **The zap source normalization ripples into `test_zap.py`** —
   small and mechanical (string assertions), and it makes
   `DeathEvent.by == "player"` true for zap kills, which
   `test_demo.py` already asserts for melee; a zap-kill test joins
   `test_experience.py`.
3. **`apply_damage` grows a hook** — the choke point stays the single
   mutation site (the XP grant is a call INTO the new module, no new
   mutation path); the hero-dead guard is already there (`source ==
   "player"` cannot be produced by a dead hero, and a monster killed
   while the hero dies the same turn still grants — matching C, where
   the kill is credited before the hero's own death is processed).
4. **`uhpinc` at init** — `init_experience` records `uhpinc[0] = 2`
   (the draw-free `newhp` at level 1).  C records the same slot from
   the level-0 `newhp` call; the value only matters for a future
   level-1 `losexp` (which doesn't subtract HP in C) and the life-
   saving minimum — behaviourally inert today, kept for fidelity.
5. **The demo HP arc** — level-ups give +2 HP each (draw-free
   `newhp`), so a full-cave clear lands the hero at 25 + 4 = 29 HP
   max / level 3; C's roll would give 27..37.  Acceptable for the
   demo; the real formula lands with role selection (section 5.4).
