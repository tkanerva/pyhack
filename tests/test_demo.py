"""End-to-end tests for the playable combat demo.

The demo (``new_world`` + ``step``) now runs on the committed C-port
combat in both directions: the demo monsters carry their PerMonst
types, so a monster bumping the hero attacks through ``core.mhitu``
(its real PerMonst attack table), and the hero starts wielding a short
sword, so a hero bumping a monster attacks through the weapon path of
``core.uhitm`` (on top of ``core.weapon``).  All damage flows through
the event model (producers -> rules.process_events -> the choke
points).
"""
import random

from core import MoveCommand, WaitCommand, step
from core.events import DamageEvent, DeathEvent, GameOverEvent, MessageEvent
from core.monst import MONS, PM_BAT, PM_GOBLIN, PM_HILL_ORC
from core.objects import ObjClass, ObjType
from core.types import Item, Monster, ObjectType
from core.weapon import P_SKILLED, Skill, Skills
from core.worldgen import new_world
from conftest import SeqRng, make_hero, make_world


def _typed(pm: int, pos=(7, 4), hp=8, **kw) -> Monster:
    """A runtime Monster carrying a PerMonst type (the mhitu path)."""
    data = MONS[pm]
    return Monster(id=f"mon_{pm}", name=data.pmnames[2], pos=pos, hp=hp,
                   max_hp=hp, ac=data.ac, mdata=data, **kw)


def _hero_with_sword(**kw):
    """The demo hero (worldgen's wiring): wields the short sword, is
    P_SKILLED with it, ulevel 1 / ustr 12 / udex 12 -> to-hit bonus +3
    (skill +2, abon +1, hitval 0)."""
    hero = make_hero(**kw)
    hero.ulevel, hero.ustr, hero.udex = 1, 12, 12
    skills = Skills()
    skills.skill[int(Skill.P_SHORT_SWORD)] = P_SKILLED
    skills.max_skill[int(Skill.P_SHORT_SWORD)] = P_SKILLED
    hero.skills = skills
    sword = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
                 otyp=ObjType.SHORT_SWORD.value,
                 oclass=ObjClass.WEAPON.value)
    hero.inventory.append(sword)
    hero.wielded = sword.id
    return hero, sword


# ------------------------------------------------------------
# hero -> monster (the weapon path) and monster -> hero (mhitu)
# ------------------------------------------------------------

def test_demo_turn_sword_hero_hits_goblin_and_goblin_hits_back():
    """One full demo turn: the hero bumps a typed goblin with its sword,
    and the goblin answers with its mhitu weapon attack."""
    hero, sword = _hero_with_sword()
    g = _typed(PM_GOBLIN)
    w = make_world(hero=hero, monsters=[g])
    w.items[sword.id] = sword
    # hero weapon attack: d20=5 <= 20-10+3=13 -> hit, 1d6=3 (goblin 8->5)
    # goblin counterattack (mhitu): tmp=5+10+0=15 > rnd(20)=1 -> hit,
    #   1d4=2 (hero 25->23)
    ev = step(w, MoveCommand(1, 0), SeqRng(5, 3, 1, 2))
    assert w.hero.pos == (6, 4)            # bumping does not move the hero
    assert g.hp == 5 and w.hero.hp == 23
    texts = [e.text for e in ev if isinstance(e, MessageEvent)]
    assert "⚔️ You hit goblin for 3 damage with your short sword." in texts
    assert "goblin hits!" in texts
    assert any(isinstance(e, DamageEvent) and e.target == g.id
               and e.amount == 3 for e in ev)
    assert any(isinstance(e, DamageEvent) and e.target == "player"
               and e.amount == 2 for e in ev)


def test_demo_monster_hits_the_hero_vice_versa():
    """The other direction on its own: the hero waits, the typed goblin
    attacks through mhitu (the hero's AC feeds the hit differential)."""
    g = _typed(PM_GOBLIN)
    w = make_world(monsters=[g])
    ev = step(w, WaitCommand(), SeqRng(10, 3))   # goblin hits for 3
    assert w.hero.hp == 22
    assert any(isinstance(e, MessageEvent) and e.text == "goblin hits!"
               for e in ev)


def test_demo_weapon_kill_gives_victory():
    hero, sword = _hero_with_sword()
    g = _typed(PM_GOBLIN, hp=1, max_hp=1)
    w = make_world(hero=hero, monsters=[g])
    w.items[sword.id] = sword
    # d20=1 -> hit (threshold 13); 1d6=6 kills the 1-hp goblin; no
    # counterattack (the monster is dead before its turn)
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 6))
    assert not g.alive
    assert w.over
    assert any(isinstance(e, DeathEvent) and e.target == g.id
               and e.by == "player" for e in ev)
    assert any(isinstance(e, GameOverEvent) and e.victory for e in ev)


# ------------------------------------------------------------
# the whole demo world (new_world + step)
# ------------------------------------------------------------

def test_new_world_wires_the_demo_combat():
    w = new_world(random.Random(42))
    for mid, pm in (("goblin_0", PM_GOBLIN), ("orc_0", PM_HILL_ORC),
                    ("bat_0", PM_BAT)):
        assert w.actors[mid].mdata is MONS[pm]
    hero = w.hero
    assert hero.wielded == "sword_0"
    sword = w.items["sword_0"]
    assert sword.otyp == ObjType.SHORT_SWORD.value
    assert sword.oclass == ObjClass.WEAPON.value
    assert hero.skills.skill[int(Skill.P_SHORT_SWORD)] == P_SKILLED
    assert (hero.ulevel, hero.ustr) == (1, 12)


def test_demo_full_game_is_deterministic():
    """Same seed + same commands => same game, now that combat runs on
    the PerMonst / weapon paths (the old demo's determinism property,
    checked on the wired-up world)."""
    def play():
        rng = random.Random(42)
        w = new_world(rng)
        out = []
        for cmd in (MoveCommand(1, 0), MoveCommand(0, 1), WaitCommand(),
                    MoveCommand(-1, 0), MoveCommand(0, -1), WaitCommand()):
            out.extend(step(w, cmd, rng))
        return (w.hero.hp, w.hero.pos, w.turn,
                {m.id: (m.hp, m.pos, m.alive) for m in w.actors.values()},
                [repr(e) for e in out])

    assert play() == play()
