"""Tests for the mhitu.c port (core.mhitu) and its event processor.

mhitu is a *producer*: it emits DamageEvent / StatusEvent /
MessageEvent intents and mutates nothing.  ``rules.process_events`` is
the pure-core half that applies those intents through the choke points.
The tests assert on the produced intents AND on the resulting world
state after processing.
"""
import itertools

from core import WaitCommand, step
from core.events import DamageEvent, DeathEvent, MessageEvent, StatusEvent
from core.mhitu import (adtyp_to_damage, could_seduce, explmu, getmattk,
                        hitmu, mattacku, magic_negation, missmu, u_slip_free)
from core.monst import (AD_ACID, AD_DISE, AD_DRIN, AD_DRST, AD_FIRE, AD_PHYS,
                        AD_SEDU, AD_SLEE, AD_WRAP, MONS, PM_CENTIPEDE,
                        PM_GOBLIN, PM_WOOD_NYMPH, PM_YELLOW_LIGHT, PM_ZRUTY,
                        Attack, AT_BITE, AT_CLAW, AT_ENGL, AT_EXPL, AT_HUGS,
                        AT_TENT, AD_BLND)
from core.objects import (OBJECTS, ObjClass, ObjType, W_AMUL, W_ARM, W_ARMC,
                          W_ARMF, W_ARMG, W_ARMH, W_ARMS, W_ARMU, W_RINGL)
from core.rules import process_events
from core.types import DamageType, Item, Monster, ObjectType
from core.worn import uac
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


# ------------------------------------------------------------
# defence integration (PLAN-ARMOR.md): the hit differential reads the
# COMPUTED effective AC (core.worn.uac), and AC_VALUE draws only when
# it is negative
# ------------------------------------------------------------

def _add_gear(w, otyp: ObjType, mask: int, name: str, spe: int = 0) -> Item:
    """Carry a fine-identity gear item on the hero, pre-worn with
    `mask`."""
    it = Item(id=f"gear_{otyp.name}", otype=ObjectType.ARMOR,
              name=name, otyp=otyp.value,
              oclass=int(OBJECTS[otyp.value].oclass), spe=spe,
              owornmask=mask, container="player")
    w.hero.inventory.append(it)
    w.items[it.id] = it
    return it


def test_mattacku_geared_hero_uses_effective_ac():
    """Chain-mail hero (base 10, effective 5) vs the goblin (mlevel
    0): threshold 15 -- the same number the old raw-AC formula gave,
    but now through uac (the demo keeps its balance; PLAN-ARMOR.md
    decision 2)."""
    w = make_world(hero=make_hero(ac=10))
    _add_gear(w, ObjType.CHAIN_MAIL, W_ARM, "chain mail")
    assert uac(w, w.hero) == 5
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    hit = mattacku(w, g.id, SeqRng(14, 3))    # roll 14 -> hit; d(1,4)=3
    assert any(isinstance(e, DamageEvent) and e.amount == 3 for e in hit)
    assert any(isinstance(e, MessageEvent) and e.text == "goblin hits!"
               for e in hit)
    near = mattacku(w, g.id, SeqRng(15))      # roll 15 == tmp -> near miss
    assert any(isinstance(e, MessageEvent) and "just misses" in e.text
               for e in near)
    miss = mattacku(w, g.id, SeqRng(16))      # roll 16 -> miss
    assert any(isinstance(e, MessageEvent) and "misses you" in e.text
               and "just" not in e.text for e in miss)


def test_mattacku_negative_ac_rolls_ac_value_first():
    """Full gear + a +2 ring pushes the hero to effective AC -2: the
    AC_VALUE draw precedes the d(20) hit roll, and hitmu's damage
    reduction reads the computed AC (the PLAN-ARMOR.md determinism
    note: the draw appears exactly when the new behaviour is being
    exercised)."""
    w = make_world(hero=make_hero(ac=10))
    for mask, otyp, name in (
        (W_ARM, ObjType.CHAIN_MAIL, "chain mail"),        # 5
        (W_ARMC, ObjType.ELVEN_CLOAK, "elven cloak"),     # 1
        (W_ARMH, ObjType.HELMET, "helmet"),               # 1
        (W_ARMS, ObjType.SMALL_SHIELD, "small shield"),   # 1
        (W_ARMG, ObjType.LEATHER_GLOVES, "leather gloves"),  # 1
        (W_ARMF, ObjType.LOW_BOOTS, "low boots"),         # 1
    ):
        _add_gear(w, otyp, mask, name)
    _add_gear(w, ObjType.RIN_PROTECTION, W_RINGL, "ring of protection",
              spe=2)  # effective AC: 10 - 10 - 2 = -2
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    # draws: ac_value(-2) = -rnd(2) -> 2 (so -2); d20 roll 7 <= tmp 8
    # -> hit; d(1,4) = 4; reduction rnd(2) = 1 -> 3
    ev = mattacku(w, g.id, SeqRng(2, 7, 4, 1))
    assert any(isinstance(e, DamageEvent) and e.amount == 3 for e in ev)
    assert any(isinstance(e, MessageEvent) and e.text == "goblin hits!"
               for e in ev)
    # a miss: only the AC_VALUE + hit draws happen
    rng = SeqRng(2, 16, 99, 99)
    ev = mattacku(w, g.id, rng)
    assert not any(isinstance(e, DamageEvent) for e in ev)
    assert rng._values == [99, 99]


# ------------------------------------------------------------
# Phase 3 of PLAN-ARMOR.md: the mhitu.c defence details
# (magic_negation + u_slip_free) -- implemented, tested, with no
# live call site yet (the call sites land with castmu / the hug port)
# ------------------------------------------------------------

_worn_ids = itertools.count()
# fine oclass -> coarse ObjectType for the Item field
_COARSE = {
    int(ObjClass.ARMOR): ObjectType.ARMOR,
    int(ObjClass.RING): ObjectType.RING,
    int(ObjClass.AMULET): ObjectType.AMULET,
    int(ObjClass.WEAPON): ObjectType.WEAPON,
}


def _wear(w, otyp: ObjType, mask: int, name=None, spe=0, cursed=False,
          greased=False) -> Item:
    """Carry a fine-identity item on the hero, pre-worn with ``mask``
    (0 = carried, not worn)."""
    o = OBJECTS[otyp.value]
    it = Item(id=f"ph3_{next(_worn_ids)}", otype=_COARSE[int(o.oclass)],
              name=name if name is not None else (o.name or o.descr),
              otyp=otyp.value, oclass=int(o.oclass), spe=spe, cursed=cursed,
              greased=greased, owornmask=mask, container="player")
    w.hero.inventory.append(it)
    w.items[it.id] = it
    return it


def _attacker(name="angler") -> Monster:
    """A bare attacker stand-in (only its name matters here)."""
    return Monster(id=f"atk_{name}", name=name, pos=(7, 4), hp=5, max_hp=5,
                   ac=5)


# magic_negation (C: mhitu.c) -------------------------------------------

def test_magic_negation_table():
    # nothing worn -> 0
    w = make_world()
    assert magic_negation(w.hero) == 0

    # the plan's "leather 0": the leather JACKET has a_can 0
    w = make_world()
    _wear(w, ObjType.LEATHER_JACKET, W_ARM)
    assert magic_negation(w.hero) == 0
    # (correction vs the plan's arithmetic, as in its status note: worn
    # LEATHER_ARMOR has a_can 1)
    w = make_world()
    _wear(w, ObjType.LEATHER_ARMOR, W_ARM)
    assert magic_negation(w.hero) == 1

    # plate (a_can 2)
    w = make_world()
    _wear(w, ObjType.PLATE_MAIL, W_ARM)
    assert magic_negation(w.hero) == 2

    # the MAX over the worn slots, not a sum (chain 1 + oilskin 2 -> 2)
    w = make_world()
    _wear(w, ObjType.CHAIN_MAIL, W_ARM)
    _wear(w, ObjType.OILSKIN_CLOAK, W_ARMC)
    assert magic_negation(w.hero) == 2

    # plate + amulet of guarding -> 2 + 2 = 4 -> capped at 3
    w = make_world()
    _wear(w, ObjType.PLATE_MAIL, W_ARM)
    _wear(w, ObjType.AMULET_OF_GUARDING, W_AMUL)
    assert magic_negation(w.hero) == 3

    # amulet of guarding alone -> 2 (the plan's Phase-3 semantics: with no
    # other Protection source in the subset, the worn amulet IS the
    # protection source)
    w = make_world()
    _wear(w, ObjType.AMULET_OF_GUARDING, W_AMUL)
    assert magic_negation(w.hero) == 2

    # an UNWORN amulet gives nothing; a non-guarding amulet neither
    w = make_world()
    _wear(w, ObjType.AMULET_OF_GUARDING, 0)
    assert magic_negation(w.hero) == 0
    w = make_world()
    _wear(w, ObjType.AMULET_OF_ESP, W_AMUL)
    assert magic_negation(w.hero) == 0


# u_slip_free (C: mhitu.c) ----------------------------------------------

def test_u_slip_free_greased_cloak_sheds_a_hug():
    w = make_world()
    cloak = _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    mon = _attacker()
    mattk = Attack(AT_HUGS, AD_PHYS, 0, 0)
    # not cursed: no cursed draw; grease roll preset 2 -> rn2 1 -> keeps
    slipped, events = u_slip_free(w, mon, mattk, SeqRng(2))
    assert slipped is True
    assert cloak.greased is True
    assert [e.text for e in events] == \
        ["angler grabs you, but cannot hold onto your greased "
         "leather cloak!"]


def test_u_slip_free_engulf_never_slips():
    w = make_world()
    _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    # AT_ENGL is excluded before any gear is read: no rng draw
    slipped, events = u_slip_free(w, _attacker(),
                                  Attack(AT_ENGL, AD_WRAP, 1, 6), SeqRng())
    assert slipped is False
    assert events == []


def test_u_slip_free_no_gear_does_not_slip():
    w = make_world()
    slipped, events = u_slip_free(w, _attacker(),
                                  Attack(AT_HUGS, AD_PHYS, 0, 0), SeqRng())
    assert slipped is False
    assert events == []


def test_u_slip_free_cloak_suit_shirt_fallback():
    mon = _attacker()
    hug = Attack(AT_HUGS, AD_PHYS, 0, 0)
    # no cloak: the greased suit protects
    w = make_world()
    _wear(w, ObjType.CHAIN_MAIL, W_ARM, greased=True)
    slipped, _ = u_slip_free(w, mon, hug, SeqRng(2))
    assert slipped is True
    # no cloak / suit: the greased shirt protects
    w = make_world()
    _wear(w, ObjType.HAWAIIAN_SHIRT, W_ARMU, greased=True)
    slipped, _ = u_slip_free(w, mon, hug, SeqRng(2))
    assert slipped is True
    # with both, the cloak wins the message
    w = make_world()
    _wear(w, ObjType.CHAIN_MAIL, W_ARM, greased=True)
    _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    slipped, events = u_slip_free(w, mon, hug, SeqRng(2))
    assert slipped is True
    assert [e.text for e in events] == \
        ["angler grabs you, but cannot hold onto your greased "
         "leather cloak!"]


def test_u_slip_free_brain_drain_is_parried_by_the_helmet():
    mon = _attacker("mind flayer")
    drain = Attack(AT_TENT, AD_DRIN, 0, 0)
    # a worn greased cloak is ignored for AD_DRIN; the greased helmet
    # protects
    w = make_world()
    _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    _wear(w, ObjType.HELMET, W_ARMH, greased=True)
    slipped, events = u_slip_free(w, mon, drain, SeqRng(2))
    assert slipped is True
    assert [e.text for e in events] == \
        ["mind flayer grabs you, but cannot hold onto your greased "
         "helmet!"]
    # a non-greased helmet does NOT protect, even with a greased cloak
    w = make_world()
    _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    _wear(w, ObjType.HELMET, W_ARMH)
    slipped, events = u_slip_free(w, mon, drain, SeqRng())
    assert slipped is False
    assert events == []


def test_u_slip_free_oilskin_cloak():
    w = make_world()
    cloak = _wear(w, ObjType.OILSKIN_CLOAK, W_ARMC)  # slippery, not greased
    mon = _attacker()
    # the AD_WRAP verb is "slips off of"; nothing is drawn (not cursed,
    # not greased)
    slipped, events = u_slip_free(w, mon, Attack(AT_HUGS, AD_WRAP, 0, 0),
                                  SeqRng())
    assert slipped is True
    assert cloak.greased is False
    assert [e.text for e in events] == \
        ["angler slips off of your slippery oilskin cloak!"]


def test_u_slip_free_cursed_gear_fails_one_third():
    w = make_world()
    _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True, cursed=True)
    mon = _attacker()
    hug = Attack(AT_HUGS, AD_PHYS, 0, 0)
    # cursed: the protection fails when rn2(3) == 0 (preset 1 -> 0)
    rng = SeqRng(1)
    slipped, events = u_slip_free(w, mon, hug, rng)
    assert slipped is False
    assert events == []
    assert rng._values == []  # exactly the one cursed draw
    # ...and it holds when the roll is nonzero (preset 2 -> rn2 1);
    # the grease roll (preset 2 -> rn2 1) keeps the grease
    w = make_world()
    cloak = _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True,
                  cursed=True)
    rng = SeqRng(2, 2)
    slipped, events = u_slip_free(w, mon, hug, rng)
    assert slipped is True
    assert cloak.greased is True
    assert rng._values == []  # both draws consumed


def test_u_slip_free_grease_wears_off():
    w = make_world()
    cloak = _wear(w, ObjType.LEATHER_CLOAK, W_ARMC, greased=True)
    mon = _attacker()
    # not cursed (no cursed draw); grease roll preset 1 -> rn2 0 ->
    # "The grease wears off." and the flag is cleared
    slipped, events = u_slip_free(w, mon, Attack(AT_HUGS, AD_PHYS, 0, 0),
                                  SeqRng(1))
    assert slipped is True
    assert cloak.greased is False
    assert [e.text for e in events] == [
        "angler grabs you, but cannot hold onto your greased "
        "leather cloak!",
        "The grease wears off.",
    ]
