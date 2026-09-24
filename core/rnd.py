"""NetHack random number semantics (port of src/rnd.c).

Wraps Isaac64 (core.isaac64) and provides the game RNG functions the
rest of NetHack draws through:

    rn2(x)   0 <= v < x          (the workhorse; C: RND(x) % via uint64)
    rnd(x)   1 <= v <= x
    rn1(x,y) rn2(x) + y          (hack.h macro)
    rnl(x)   luck-adjusted rn2   (C reads the global Luck)
    d(n,x)   sum of n dice of x  (C: d(n,x); note min is n, not 1)
    rne(x)   1 .. max(5, ulev/3) (C reads u.ulevel)
    rnz(x)   x scaled by ~1.0    (the classic "rnz" fudge factor)

Adaptations for the pyhack architecture (documented, not bugs):

- C reads the globals ``Luck`` and ``u.ulevel``; here the callers pass
  them explicitly (``rnl(x, luck)``, ``rne(x, ulevel)``).  This keeps
  the core free of implicit state.
- The USE_ISAAC64 build of rnd.c uses ``isaac64_next_uint64() % x`` for
  the base draw (modulo bias included -- we keep the exact sequence).
- The second "display" RNG (C: rn2_on_display_rng, used where the
  answer doesn't affect gameplay, e.g. confused-player input) is a
  separate Isaac64 stream seeded from ``b"disp:" + seed`` so that a
  fixed main seed still gives a fixed display stream.
- ``randint(a, b)`` (both ends inclusive) and ``choice(seq)`` match the
  duck-type the older demo core already expects, so existing systems
  keep working.

Callers must pass x > 0 to rn2/rnd/rnl/d/x -- the C release build would
crash (modulo by zero) and the devel build panics; here it raises.
"""
from __future__ import annotations

from typing import List, Sequence

from .isaac64 import Isaac64


class Rng:
    """One NetHack game RNG (C: the CORE entry of rnglist)."""

    def __init__(self, seed: bytes = b""):
        self._core = Isaac64()
        self._core.init(seed)
        self._disp = Isaac64()
        self._disp.init(b"disp:" + seed)

    # --------------------------------------------------------
    # Lifecycle (C: init_random / init_isaac64)
    # --------------------------------------------------------

    def init(self, seed: bytes = b"") -> None:
        """Re-initialize both streams from `seed` (C: init_random)."""
        self._core.init(seed)
        self._disp.init(b"disp:" + seed)

    # --------------------------------------------------------
    # Core draws (C: rnd.c)
    # --------------------------------------------------------

    def rn2(self, x: int) -> int:
        """0 <= rn2(x) < x (C: rn2)."""
        if x <= 0:
            raise ValueError(f"rn2({x}) attempted")
        return self._core.next_uint64() % x

    def rnd(self, x: int) -> int:
        """1 <= rnd(x) <= x (C: rnd)."""
        return self.rn2(x) + 1

    def rn1(self, x: int, y: int) -> int:
        """rn2(x) + y (C: hack.h macro rn1)."""
        return self.rn2(x) + y

    def rnl(self, x: int, luck: int = 0) -> int:
        """Luck-adjusted rn2 (C: rnl; reads the global Luck in C).

        Good luck biases toward 0, bad luck toward x-1.  For x <= 15
        the adjustment is Luck/3 rounded away from 0.
        """
        if x <= 0:
            raise ValueError(f"rnl({x}) attempted")
        adjustment = luck
        if x <= 15:
            # (abs(adjustment) + 1) / 3 * sgn(adjustment), C integer math
            adjustment = ((abs(adjustment) + 1) // 3
                          * (1 if adjustment > 0 else -1 if adjustment < 0 else 0))
        i = self.rn2(x)
        if adjustment and self.rn2(37 + abs(adjustment)):
            i -= adjustment
            if i < 0:
                i = 0
            elif i >= x:
                i = x - 1
        return i

    def d(self, n: int, x: int) -> int:
        """n dice of x sides, summed; result in [n, n*x] (C: d).

        Each die contributes 1 + rn2(x), so d(3, 6) is exactly 3d6
        (minimum 3, not 1).  NetHack damage strings like "1d6" are
        rolled with d(1, 6).
        """
        if x < 0 or n < 0 or (x == 0 and n != 0):
            raise ValueError(f"d({n},{x}) attempted")
        return n + sum(self.rn2(x) for _ in range(n))

    def rne(self, x: int, ulevel: int = 1) -> int:
        """1 <= v <= max(5, ulevel//3) (C: rne; reads u.ulevel in C)."""
        if x <= 0:
            raise ValueError(f"rne({x}) attempted")
        utmp = max(5, ulevel // 3)
        tmp = 1
        while tmp < utmp and not self.rn2(x):
            tmp += 1
        return tmp

    def rnz(self, x: int) -> int:
        """Scale x by a random factor near 1.0 (C: rnz, "everyone's
        favorite")."""
        tmp = 1000 + self.rn2(1000)
        tmp *= self.rne(4)
        if self.rn2(2):
            return (x * tmp) // 1000
        return (x * 1000) // tmp

    # --------------------------------------------------------
    # Sequences (C: shuffle_int_array, ROLL_FROM)
    # --------------------------------------------------------

    def shuffle(self, seq: List) -> None:
        """Randomize in place (C: shuffle_int_array, rn2-based
        Fisher-Yates)."""
        for i in range(len(seq) - 1, 0, -1):
            j = self.rn2(i + 1)
            if j != i:
                seq[i], seq[j] = seq[j], seq[i]

    def choice(self, seq: Sequence) -> object:
        """Uniform random element (C: ROLL_FROM(array))."""
        if not seq:
            raise ValueError("choice(()) attempted")
        return seq[self.rn2(len(seq))]

    # --------------------------------------------------------
    # Display-only stream (C: rn2_on_display_rng)
    # --------------------------------------------------------

    def rn2_display(self, x: int) -> int:
        """Like rn2() but from the display stream: for cosmetic
        randomness that must not let the player steer the main RNG
        (C: rn2_on_display_rng)."""
        if x <= 0:
            raise ValueError(f"rn2_on_display_rng({x}) attempted")
        return self._disp.next_uint64() % x

    def rnd_display(self, x: int) -> int:
        """1 <= v <= x from the display stream (C: rnd_on_display_rng)."""
        return self.rn2_display(x) + 1

    # --------------------------------------------------------
    # Compatibility with the older demo core's rng duck-type
    # --------------------------------------------------------

    def randint(self, a: int, b: int) -> int:
        """Uniform int in [a, b], both ends inclusive."""
        if b < a:
            raise ValueError(f"randint({a}, {b}) attempted")
        return a + self.rn2(b - a + 1)
