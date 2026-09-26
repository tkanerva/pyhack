"""Tests for the uhitm.c port (core.uhitm).

uhitm is the hero->monster mirror of mhitu: a *producer* that emits
DamageEvent / MessageEvent intents, applied by
``rules.process_events``.  These tests assert on the produced intents
AND on the resulting world state after processing / stepping.
"""
from core import MoveCommand, step
from core.events import DamageEvent, MessageEvent
from core.monst import MONS, PM_BAT, PM_GOBLIN, PM_OGRE, PM_ZRUTY
from core.rules import process_events
from core.types import DamageType, Monster
from core.uhitm import backstabbable, hmonas, known_hitum, uhitm
from conftest import SeqRng, make_hero, make_world


def _typed(pm: int, pos=(7, 4), hp=8, **kw) -> Monster:
    data = MONS[pm]
    return Monster(id=f"mon_{pm}", name=data.pmnames[2], pos=pos, hp=hp,
                   max_hp=hp, ac=data.ac, mdata=data, **kw)


# ------------------------------------------------------------
# known_hitum
# ------------------------------------------------------------

def test_known_hitum_is_twenty_minus_monster_ac():
    g = _typed(PM_GOBLIN)          # ac 10
    o = _typed(PM_OGRE)            # ac 5
    assert known_hitum(g, make_hero()) == 10
    assert known_hitum(o, make_hero()) == 15


# ------------------------------------------------------------
# backstabbable
# ------------------------------------------------------------

def test_backstabbable():
    assert backstabbable(_typed(PM_GOBLIN)) is True   # small, grounded, orc
    assert backstabbable(_typed(PM_BAT)) is False     # flies
    assert backstabbable(_typed(PM_OGRE)) is False    # large
    plain = Monster(id="p", name="p", pos=(0, 0), hp=1, max_hp=1, ac=0)
    assert backstabbable(plain) is False              # no PerMonst


# ------------------------------------------------------------
# hmonas
# ------------------------------------------------------------

def test_hmonas():
    hero = make_hero()                    # no mdata -> never "as" a monster
    g = _typed(PM_GOBLIN)
    assert hmonas(g, hero) is False
    hero.mdata = MONS[PM_GOBLIN]          # hero "as" goblin now
    assert hmonas(g, hero) is True        # same type -> True
    assert hmonas(_typed(PM_ZRUTY), hero) is False


# ------------------------------------------------------------
# uhitm (a single hero attack) -- producer, no mutation
# ------------------------------------------------------------

def test_uhitm_hit_produces_damage():
    w = make_world()
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    # threshold = 20 - 10 = 10 ; roll 5 -> hit ; 1d2 -> 2
    ev = uhitm(w, g.id, SeqRng(5, 2))
    assert g.hp == 8 and w.hero.hp == 25    # producer mutates nothing
    de = [e for e in ev if isinstance(e, DamageEvent)]
    assert len(de) == 1
    assert de[0].target == g.id and de[0].amount == 2
    assert de[0].damage_type == DamageType.MELEE and de[0].source == "player"
    assert any(isinstance(e, MessageEvent)
               and e.text == "⚔️ You hit goblin for 2 damage." for e in ev)


def test_uhitm_miss():
    w = make_world()
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    ev = uhitm(w, g.id, SeqRng(15))        # roll 15 > 10 -> miss
    assert ev == [MessageEvent("🛡️ You miss.")]


def test_uhitm_ignores_flat_and_dead_targets():
    w = make_world()
    flat = Monster(id="flat", name="goblin", pos=(7, 4), hp=8, max_hp=8, ac=7)
    w.actors[flat.id] = flat
    assert uhitm(w, flat.id, SeqRng()) == []
    dead = _typed(PM_GOBLIN, hp=1)
    dead.alive = False
    w.actors[dead.id] = dead
    assert uhitm(w, dead.id, SeqRng()) == []


def test_process_events_applies_uhitm_damage():
    w = make_world()
    g = _typed(PM_GOBLIN)
    w.actors[g.id] = g
    ev = uhitm(w, g.id, SeqRng(5, 2))
    out = process_events(w, ev, SeqRng())
    assert g.hp == 6
    assert any(isinstance(e, DamageEvent) and e.target == g.id for e in out)


# ------------------------------------------------------------
# step() integration: the hero bumps a typed monster
# ------------------------------------------------------------

def test_step_hero_bumps_typed_monster_uses_uhitm():
    g = _typed(PM_GOBLIN)
    w = make_world(monsters=[g])
    # hero attack: roll 5 (hit, 1d2=2 -> goblin 8->6)
    # goblin counterattack (mhitu): roll 20 -> miss (no hero damage)
    ev = step(w, MoveCommand(1, 0), SeqRng(5, 2, 20))
    assert w.hero.pos == (6, 4)            # bumping does not move the hero
    assert g.hp == 6
    assert w.hero.hp == 25
    assert any(isinstance(e, MessageEvent) and "You hit goblin" in e.text
               for e in ev)


def test_step_hero_bumps_flat_monster_keeps_simple_path():
    from conftest import make_monster
    g = make_monster(pos=(7, 4))           # no mdata
    w = make_world(monsters=[g])
    # simple path: hero d20=1 (hit), 1d2=2 ; goblin counter d20=20 (miss)
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 2, 20))
    assert g.hp == 6
    assert w.hero.hp == 25
    assert any(isinstance(e, MessageEvent) and "You hit Goblin for 2 damage"
               in e.text for e in ev)
