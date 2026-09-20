"""Tests for the trap system, including regression tests for bugs that
the old broadcast architecture caused."""
from core.events import DamageEvent, TrapSeenEvent
from core.traps import check_traps, disarm_trap
from core.types import TrapType
from conftest import SeqRng, make_monster, make_trap, make_world


def world_on_trap(trap_type):
    return make_world(traps=[make_trap(trap_type, pos=(6, 4))])


def test_pit_deals_exactly_one_damage():
    """Regression: the old architecture applied trap damage twice
    (TrapActor._apply_trap_effect subtracted HP, then
    check_and_trigger_traps called react_to_damage with the same roll)."""
    w = world_on_trap(TrapType.PIT)
    ev = check_traps(w, "player", SeqRng(5, 4))  # trigger roll 5, pit roll 4
    dmg = [e for e in ev if isinstance(e, DamageEvent)]
    assert len(dmg) == 1 and dmg[0].amount == 4
    assert w.hero.hp == 21
    assert w.traps["trap_0"].triggered
    assert w.hero.stuck == 10


def test_untriggered_trap_is_marked_seen():
    w = world_on_trap(TrapType.PIT)
    ev = check_traps(w, "player", SeqRng(75))
    assert not w.traps["trap_0"].triggered
    assert w.traps["trap_0"].seen
    assert w.hero.hp == 25
    assert any(isinstance(e, TrapSeenEvent) for e in ev)


def test_triggered_trap_is_inert():
    w = world_on_trap(TrapType.PIT)
    check_traps(w, "player", SeqRng(5, 4))
    check_traps(w, "player", SeqRng(5, 4))
    assert w.hero.hp == 21  # no second application


def test_arrow_trap_hit_and_miss():
    w = world_on_trap(TrapType.ARROW_TRAP)  # hero ac 5 -> hit chance 15
    ev = check_traps(w, "player", SeqRng(5, 10, 3))  # trigger, d20=10, 3 dmg
    assert [e.amount for e in ev if isinstance(e, DamageEvent)] == [3]

    w2 = world_on_trap(TrapType.ARROW_TRAP)
    ev2 = check_traps(w2, "player", SeqRng(5, 16))  # d20 = 16 misses
    assert not any(isinstance(e, DamageEvent) for e in ev2)


def test_web_sticks_actor():
    w = world_on_trap(TrapType.WEB)
    check_traps(w, "player", SeqRng(5))
    assert w.hero.stuck == 10


def test_sleeping_gas_puts_to_sleep():
    w = world_on_trap(TrapType.SLEEPING_GAS)
    check_traps(w, "player", SeqRng(5))
    assert w.hero.sleeping == 25


def test_teleport_trap_stays_in_bounds():
    """The old trap.py teleported to a hard-coded 80x22 area while the
    demo map is 40x20 -- teleports could land off the map."""
    w = world_on_trap(TrapType.TELEPORTATION)
    check_traps(w, "player", SeqRng(5, (2, 2)))
    assert w.hero.pos == (2, 2)
    assert w.map.is_walkable((2, 2))


def test_monster_can_trigger_traps_too():
    w = make_world(monsters=[make_monster(pos=(6, 4))],
                   traps=[make_trap(TrapType.SPIKED_PIT, pos=(6, 4))])
    check_traps(w, "goblin_0", SeqRng(5, 7))
    assert w.actors["goblin_0"].hp == 1
    assert w.traps["trap_0"].triggered


def test_disarmed_trap_is_inert():
    w = world_on_trap(TrapType.ARROW_TRAP)
    disarm_trap(w, "trap_0", "player")
    assert w.traps["trap_0"].disarmed
    check_traps(w, "player", SeqRng(5))
    assert not w.traps["trap_0"].triggered
