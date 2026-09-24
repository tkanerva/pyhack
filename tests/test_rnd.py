"""Tests for the NetHack RNG semantics (core.rnd).

Two test styles, mirroring the repo's existing convention:
- Scripted: preset draw sequences exercise the *math* (rnl/rne/rnz/d)
  table-driven, independent of the underlying generator.
- Real Rng: structural properties (ranges, determinism, the
  randint/choice duck-type the older core relies on).
"""
from core.rnd import Rng


class Scripted:
    """Duck for Rng whose rn2/rne pop preset values (C-style table
    tests, no generator involved)."""

    def __init__(self, *values):
        self.values = list(values)

    def rn2(self, x):
        return self.values.pop(0)

    def rne(self, x, ulevel=1):
        return self.values.pop(0)

    def rnz(self, x):
        # not used by these tests; rnz is tested through Rng below
        raise NotImplementedError


def test_rnl_no_luck_is_plain_rn2():
    assert Rng.rnl(Scripted(5), 10, luck=0) == 5


def test_rnl_good_luck_shifts_down():
    # luck 6, x 10 (<=15): adjustment = (6+1)//3 = 2; draws: 5, then 1
    # (truthy) -> 5-2 = 3
    assert Rng.rnl(Scripted(5, 1), 10, luck=6) == 3


def test_rnl_bad_luck_shifts_up_and_clamps():
    # luck -6, x 10: adjustment = -2; draws: 9, 1 -> 9+2 = 11 -> clamp 9
    assert Rng.rnl(Scripted(9, 1), 10, luck=-6) == 9
    # small luck rounds away from zero: -1 -> 0 (no adjustment)
    assert Rng.rnl(Scripted(4), 10, luck=-1) == 4


def test_rnl_adjustment_gated_by_second_roll():
    # adjustment 2 but the gate roll is 0 (false): no shift
    assert Rng.rnl(Scripted(5, 0), 10, luck=6) == 5


def test_rnl_small_x_scales_luck_by_third():
    # x=5 <= 15, luck=13 -> (13+1)//3 = 4; draws 0, 1 -> 0-4 -> clamp 0
    assert Rng.rnl(Scripted(0, 1), 5, luck=13) == 0


def test_rne_counts_successive_rolls():
    # utmp = max(5, 30//3) = 10; rn2 draws 0,0,1 then rne stops at tmp=3
    s = Scripted(0, 0, 1)
    # rne calls self.rn2 in its loop, so script rn2 draws, not rne draws
    assert Rng.rne(s, 100, ulevel=30) == 3


def test_rne_capped_at_five_for_low_level():
    # ulevel 1: utmp = 5; all-zero draws climb to the cap
    s = Scripted(0, 0, 0, 0, 0, 0, 0)
    assert Rng.rne(s, 100, ulevel=1) == 5


def test_rnz_scales_by_factor_near_one():
    # draws: rn2(1000)=0 -> tmp=1000; rne=1 -> tmp=1000; rn2(2)=1
    # -> x*tmp//1000 = x (exact)
    s = Scripted(0, 1, 1)
    assert Rng.rnz(s, 700) == 700
    # draws: rn2(1000)=999 -> tmp=1999; rne=1; rn2(2)=0
    # -> x*1000//1999 = 350
    s = Scripted(999, 1, 0)
    assert Rng.rnz(s, 700) == 350


def test_real_rng_ranges_and_determinism():
    a, b = Rng(b"t1"), Rng(b"t1")
    draws_a = [a.rn2(20) for _ in range(500)]
    draws_b = [b.rn2(20) for _ in range(500)]
    assert draws_a == draws_b
    assert all(0 <= v < 20 for v in draws_a)

    assert all(1 <= a.rnd(6) <= 6 for _ in range(200))

    # d(n, x) lies in [n, n*x]
    for _ in range(200):
        v = a.d(3, 6)
        assert 3 <= v <= 18


def test_real_rng_rejects_bad_args():
    rng = Rng(b"x")
    for fn in (lambda: rng.rn2(0), lambda: rng.rnd(0),
               lambda: rng.d(1, 0)):
        try:
            fn()
            assert False, "expected ValueError"
        except ValueError:
            pass
    # d(0, 0) is legal in the C code (returns 0), as is d(n, x) with
    # n > 0 and x > 0:
    assert rng.d(0, 0) == 0


def test_real_rng_shuffle_and_choice():
    rng = Rng(b"shuffle")
    items = list(range(30))
    shuffled = items[:]
    rng.shuffle(shuffled)
    assert sorted(shuffled) == items
    assert shuffled != items  # overwhelmingly likely
    for v in (rng.choice(items), rng.choice([7, 8, 9])):
        assert v in items or v in (7, 8, 9)


def test_real_rng_randint_choice_ducktype():
    """The older demo core calls rng.randint(a, b) and rng.choice(seq);
    Rng must satisfy that contract."""
    rng = Rng(b"duck")
    for _ in range(200):
        assert 1 <= rng.randint(1, 20) <= 20
    vals = [rng.randint(3, 3) for _ in range(10)]
    assert all(v == 3 for v in vals)
    for _ in range(100):
        assert rng.choice(["a", "b"]) in ("a", "b")


def test_display_stream_is_separate_and_deterministic():
    # both streams are deterministic under a fixed seed
    c, d = Rng(b"disp"), Rng(b"disp")
    assert [c.rn2(1000) for _ in range(50)] == [d.rn2(1000) for _ in range(50)]
    assert [c.rn2_display(1000) for _ in range(50)] == \
           [d.rn2_display(1000) for _ in range(50)]
    # drawing from the display stream must not advance the main stream
    a, b = Rng(b"disp"), Rng(b"disp")
    a.rn2_display(1000)
    assert a.rn2(1000) == b.rn2(1000)
    # the two streams must not be identical sequences
    e = Rng(b"disp")
    main_seq = [e.rn2(1 << 62) for _ in range(16)]
    e2 = Rng(b"disp")
    disp_seq = [e2.rn2_display(1 << 62) for _ in range(16)]
    assert main_seq != disp_seq
