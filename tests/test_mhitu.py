"""Tests for the mhitu.c port (core.mhitu) and its event processor.

mhitu is a *producer*: it emits DamageEvent / StatusEvent /
MessageEvent intents and mutates nothing.  ``rules.process_events`` is
the pure-core half that applies those intents through the choke points.
The tests assert on the produced intents AND on the resulting world
state after processing.
"""
from core import WaitCommand, step
from core.events import DamageEvent, DeathEvent, MessageEvent, StatusEvent
from core.mhitu import (adtyp_to_damage, could_seduce, explmu, getmattk,
                        hitmu, mattacku, missmu)
from core.monst import (AD_ACID, AD_DISE, AD_DRST, AD_FIRE, AD_PHYS, AD_SEDU,
                        AD_SLEE, MONS, PM_CENTIPEDE, PM_GOBLIN, PM_WOOD_NYMPH,
                        PM_YELLOW_LIGHT, PM_ZRUTY, Attack, AT_BITE, AT_CLAW,
                        AT_EXPL, AD_BLND)
from core.rules import process_events
from core.types import DamageType, Monster
from conftest import SeqRng, make_hero, make_world


def _typed(pm: int, pos=(7, 4), hp=8, **kw) -> Monster:
    """A runtime Monster carrying a PerMonst type (the mhitu path)."""
    data = MONS[pm]
    return Monster(id=f"mon_{pm}", name=data.pmnames[2], pos=pos, hp=hp,
                   max_hp=hp, ac=data.ac, mdata=data, **kw)


# ------------------------------------------------------------
# adtyp_to_damage
# ------------------------------------------------------------

def test_adtyp_to_damage_mapping():
    assert adtyp_to_damage(AD_PHYS) == DamageType.MELEE
    assert adtyp_to_damage(AD_FIRE) == DamageType.FIRE
    assert adtyp_to_damage(AD_DRST) == DamageType.POISON
    assert adtyp_to_damage(AD_DISE) == DamageType.POISON
    assert adtyp_to_damage(AD_SLEE) == DamageType.SLEEP
    # the "weird" contact effects fall back to plain melee damage
    assert adtyp_to_damage(AD_ACID) == DamageType.ACID


# ------------------------------------------------------------
# getmattk
# ------------------------------------------------------------

class _Attacker:
    """Stand-in exposing just the ``.mdata.mattk`` shape getmattk reads."""
    def __init__(self, mattk):
        class _PM:
            pass
        pm = _PM()
        pm.mattk = tuple(mattk)
        self.mdata = pm


def test_getmattk_returns_the_indexed_attack():
    a = Attack(AT_CLAW, AD_PHYS, 1, 4)
    b = Attack(AT_BITE, AD_PHYS, 1, 6)
    mon = _Attacker([a, b, Attack(AT_CLAW, AD_PHYS, 1, 4),
                     Attack(0, 0, 0, 0), Attack(0, 0, 0, 0),
                     Attack(0, 0, 0, 0)])
    assert getmattk(mon, 0, [0] * 6) is a
    assert getmattk(mon, 1, [0] * 6) is b


def test_getmattk_substitutes_repeated_disease_with_stun():
    from core.monst import AD_STUN
    d1 = Attack(AT_BITE, AD_DISE, 1, 4)
    d2 = Attack(AT_BITE, AD_DISE, 1, 4)
    mon = _Attacker([d1, d2, Attack(0, 0, 0, 0), Attack(0, 0, 0, 0),
                     Attack(0, 0, 0, 0), Attack(0, 0, 0, 0)])
    # first attack already hit -> the second disease becomes a stun
    sub = getmattk(mon, 1, [1, 0, 0, 0, 0, 0])
    assert sub.adtyp == AD_STUN
    # first attack missed -> no substitution
    assert getmattk(mon, 1, [0, 0, 0, 0, 0, 0]) is d2


# ------------------------------------------------------------
# hitmu (a successful hit) -- produces events, no mutation
# ------------------------------------------------------------

def test_hitmu_produces_damage_event_and_message():
    w = make_world()
    mon = _typed(PM_GOBLIN, pos=(7, 4))
    w.actors[mon.id] = mon
    mattk = Attack(AT_BITE, AD_PHYS, 1, 6)
    events, dmg = hitmu(w, mon, w.hero, mattk, SeqRng(4))
    assert dmg == 4
    assert w.hero.alive and w.hero.hp == 25   # mhitu never mutates the hero
    de = [e for e in events if isinstance(e, DamageEvent)]
    assert len(de) == 1
    assert de[0].target == "player" and de[0].amount == 4
    assert de[0].damage_type == DamageType.MELEE and de[0].source == mon.id
    assert any(isinstance(e, MessageEvent) and e.text == "goblin bites!"
               for e in events)


def test_hitmu_disease_bite_adds_a_poison_status():
    w = make_world()
    mon = _typed(PM_CENTIPEDE, pos=(7, 4))
    w.actors[mon.id] = mon
    mattk = Attack(AT_BITE, AD_DRST, 1, 3)
    # d(1,3) -> 2 ; poison duration rnd(20) -> 7
    events, dmg = hitmu(w, mon, w.hero, mattk, SeqRng(2, 7))
    assert dmg == 2
    de = [e for e in events if isinstance(e, DamageEvent)][0]
    assert de.damage_type == DamageType.POISON
    se = [e for e in events if isinstance(e, StatusEvent)]
    assert len(se) == 1 and se[0].effect == "poison" and se[0].duration == 7


def test_hitmu_negative_ac_reduces_damage():
    w = make_world(hero=make_hero(ac=-3))
    mon = _typed(PM_GOBLIN, pos=(7, 4))
    w.actors[mon.id] = mon
    mattk = Attack(AT_BITE, AD_PHYS, 1, 6)
    # d(1,6)=6 ; negative-AC reduction rnd(3)=3 -> 6-3=3
    events, dmg = hitmu(w, mon, w.hero, mattk, SeqRng(6, 3))
    assert dmg == 3


# ------------------------------------------------------------
# missmu
# ------------------------------------------------------------

def test_missmu_plain_and_near_miss():
    mon = _typed(PM_GOBLIN)
    ev = missmu(mon, Attack(AT_BITE, AD_PHYS, 1, 3))
    assert ev[0].text == "🛡️ goblin misses you!"
    ev = missmu(mon, Attack(AT_BITE, AD_PHYS, 1, 3), nearmiss=True)
    assert ev[0].text == "🛡️ goblin just misses you!"


# ------------------------------------------------------------
# explmu (an exploder detonates)
# ------------------------------------------------------------

def test_explmu_blinds_and_self_damages():
    w = make_world()
    yl = _typed(PM_YELLOW_LIGHT, pos=(7, 4), hp=1)
    w.actors[yl.id] = yl
    mattk = Attack(AT_EXPL, AD_BLND, 10, 20)
    # power = 10 dice of 1 = 10
    events = explmu(w, yl, w.hero, mattk, SeqRng(*([1] * 10)))
    blind = [e for e in events if isinstance(e, StatusEvent)
             and e.effect == "blind"]
    assert len(blind) == 1 and blind[0].duration == 10
    selfdmg = [e for e in events if isinstance(e, DamageEvent)
               and e.target == yl.id]
    assert len(selfdmg) == 1 and selfdmg[0].amount == 10
    # process_events turns the self-damage into the exploder's death
    out = process_events(w, events, SeqRng())
    assert not w.actors[yl.id].alive
    assert any(isinstance(e, DeathEvent) and e.target == yl.id for e in out)


# ------------------------------------------------------------
# could_seduce
# ------------------------------------------------------------

def test_could_seduce():
    nymph = _typed(PM_WOOD_NYMPH)
    goblin = _typed(PM_GOBLIN)
    hero = make_hero()      # the runtime hero has no mdata -> not seducible yet
    sed = Attack(AT_CLAW, AD_SEDU, 0, 0)
    assert could_seduce(nymph, hero, sed) == 0
    assert could_seduce(goblin, hero, sed) == 0
    victim = _typed(PM_GOBLIN)   # a typed victim exercises the positive branch
    assert could_seduce(nymph, victim, sed) == 1
    assert could_seduce(goblin, victim, sed) == 0


# ------------------------------------------------------------
# mattacku (the main loop)
# ------------------------------------------------------------

def test_mattacku_goblin_hit_and_miss():
    w = make_world()
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    # tmp = ac(5) + 10 + mlevel(0) = 15
    hit = mattacku(w, g.id, SeqRng(10, 3))   # roll 10 -> hit; d(1,4)=3
    assert any(isinstance(e, DamageEvent) and e.amount == 3 for e in hit)
    assert any(isinstance(e, MessageEvent) and e.text == "goblin hits!"
               for e in hit)
    miss = mattacku(w, g.id, SeqRng(20))     # roll 20 -> miss, not near
    assert any(isinstance(e, MessageEvent) and "misses you" in e.text
               and "just" not in e.text for e in miss)
    near = mattacku(w, g.id, SeqRng(15))     # roll 15 == tmp -> near miss
    assert any("just misses" in e.text for e in near if isinstance(e, MessageEvent))


def test_mattacku_stops_when_hero_falls():
    w = make_world(hero=make_hero(hp=2))
    z = _typed(PM_ZRUTY)                      # 3 melee attacks, mlevel 9
    w.actors[z.id] = z
    # tmp = 5 + 10 + 9 = 24 -> every hit roll succeeds; the first claw
    # (3 dice) deals >= 3 and kills the 2-hp hero, so only ONE attack's
    # worth of events is produced
    ev = mattacku(w, z.id, SeqRng(5, 1, 1, 1))
    assert sum(1 for e in ev if isinstance(e, DamageEvent)) == 1
    assert sum(1 for e in ev if isinstance(e, MessageEvent)) == 1


def test_mattacku_ignores_monsters_without_mdata():
    w = make_world()
    g = Monster(id="plain", name="goblin", pos=(7, 4), hp=8, max_hp=8,
                ac=10, mdata=None)
    w.actors[g.id] = g
    assert mattacku(w, g.id, SeqRng()) == []


# ------------------------------------------------------------
# process_events (the pure core applies the intents)
# ------------------------------------------------------------

def test_process_events_applies_damage_and_status():
    w = make_world()
    produced = [
        MessageEvent("goblin bites!"),
        DamageEvent(target="player", amount=3, damage_type=DamageType.MELEE,
                    source="mon_70"),
        StatusEvent("player", "poison", 7),
    ]
    out = process_events(w, produced, SeqRng())
    assert w.hero.hp == 22
    assert w.hero.poisoned == 7
    # the produced intents are replaced, not duplicated
    assert sum(1 for e in out if isinstance(e, DamageEvent)) == 1
    assert any(isinstance(e, MessageEvent) and "poison" in e.text for e in out)


def test_process_events_lethal_damage_kills_the_hero():
    w = make_world()
    w.hero.hp = 2
    out = process_events(
        w, [DamageEvent(target="player", amount=5,
                        damage_type=DamageType.MELEE, source="mon_70")],
        SeqRng())
    assert not w.hero.alive
    assert any(isinstance(e, DeathEvent) and e.target == "player" for e in out)


# ------------------------------------------------------------
# step() integration: a typed monster attacks through mhitu
# ------------------------------------------------------------

def test_step_typed_monster_uses_mhitu_path():
    g = _typed(PM_GOBLIN)
    w = make_world(monsters=[g])
    ev = step(w, WaitCommand(), SeqRng(10, 3))   # goblin hits for 3
    assert w.hero.hp == 22
    assert any(isinstance(e, MessageEvent) and e.text == "goblin hits!"
               for e in ev)


def test_step_flat_monster_keeps_simple_path():
    from conftest import make_monster
    g = make_monster(pos=(7, 4))                 # no mdata
    w = make_world(monsters=[g])
    ev = step(w, WaitCommand(), SeqRng(1, 2))    # simple: d20=1 hit, 1d2=2
    assert w.hero.hp == 23
    assert any(isinstance(e, MessageEvent) and "hits you for 2 damage" in e.text
               for e in ev)
