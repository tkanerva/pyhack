"""ISAAC-64 random number generator.

Faithful port of NetHack src/isaac64.c: Timothy B. Terriberry's
implementation (CC0) of Robert J. Jenkins Jr.'s ISAAC-64, with the
NetHack-specific seed constant (0x9E3779B97F4A7C13, not the original
0x9E3779B97F4A7C15 -- port what the C file says, not what other ISAAC64
implementations say).

Python ints are unbounded, so every operation that would wrap in C is
explicitly masked to 64 bits (``& MASK``).  That is the only
interpretive difference from the C source; the sequence of values is
bit-identical.
"""
from __future__ import annotations

MASK = 0xFFFFFFFFFFFFFFFF

ISAAC64_SZ_LOG = 8
ISAAC64_SZ = 1 << ISAAC64_SZ_LOG          # 256
ISAAC64_SEED_SZ_MAX = ISAAC64_SZ << 3     # 2048 bytes

_SEED_CONSTANT = 0x9E3779B97F4A7C13


def _lower_bits(x: int) -> int:
    """Extract ISAAC64_SZ_LOG bits, starting at bit 3 (C: lower_bits)."""
    return (x & ((ISAAC64_SZ - 1) << 3)) >> 3


def _upper_bits(y: int) -> int:
    """Extract the next ISAAC64_SZ_LOG bits, starting at bit SZ_LOG+2."""
    return (y >> (ISAAC64_SZ_LOG + 3)) & (ISAAC64_SZ - 1)


def _mix(x: list) -> None:
    """In-place 8-word mixing function (C: isaac64_mix).

    Note the C loop ``for(i=0;i<8;i++)`` contains a manual ``i++`` in its
    middle: the first group runs for i = 0,2,4,6 and the second (with
    left shifts) for i = 1,3,5,7.
    """
    shift = (9, 9, 23, 15, 14, 20, 17, 14)
    i = 0
    while i < 8:
        x[i] = (x[i] - x[(i + 4) & 7]) & MASK
        x[(i + 5) & 7] = (x[(i + 5) & 7] ^ (x[(i + 7) & 7] >> shift[i])) & MASK
        x[(i + 7) & 7] = (x[(i + 7) & 7] + x[i]) & MASK
        i += 1
        x[i] = (x[i] - x[(i + 4) & 7]) & MASK
        x[(i + 5) & 7] = (x[(i + 5) & 7] ^ (x[(i + 7) & 7] << shift[i])) & MASK
        x[(i + 7) & 7] = (x[(i + 7) & 7] + x[i]) & MASK
        i += 1


class Isaac64:
    """One ISAAC-64 generator instance (C: struct isaac64_ctx).

    Usage mirrors the C API::

        isaac = Isaac64()
        isaac.init(seed_bytes)      # isaac64_init
        isaac.reseed(new_bytes)     # isaac64_reseed (mixes INTO state)
        v = isaac.next_uint64()     # isaac64_next_uint64
        n = isaac.next_uint(x)      # isaac64_next_uint: 0 <= n < x
    """

    def __init__(self) -> None:
        self._m = [0] * ISAAC64_SZ
        self._r = [0] * ISAAC64_SZ
        self._a = 0
        self._b = 0
        self._c = 0
        self._n = 0
        self.init(b"")

    def init(self, seed: bytes = b"") -> None:
        """Reset to a fresh state from `seed` (C: isaac64_init)."""
        self._a = 0
        self._b = 0
        self._c = 0
        self._r = [0] * ISAAC64_SZ
        self._n = 0
        self.reseed(seed)

    def reseed(self, seed: bytes = b"") -> None:
        """Mix new entropy into the current state (C: isaac64_reseed).

        Seed bytes longer than ISAAC64_SEED_SZ_MAX are truncated, as in
        the C code.
        """
        nseed = len(seed)
        if nseed > ISAAC64_SEED_SZ_MAX:
            nseed = ISAAC64_SEED_SZ_MAX

        r = self._r
        m = self._m

        full_words = nseed >> 3
        for i in range(full_words):
            # C packs each 8-byte group big-endian: seed[8i+7] is the MSB
            r[i] ^= int.from_bytes(seed[i << 3:(i << 3) + 8], "big")

        nseed -= full_words << 3
        if nseed > 0:
            # C packs the leftover tail little-endian
            ri = seed[full_words << 3]
            for j in range(1, nseed):
                ri |= seed[(full_words << 3) + j] << (j << 3)
            r[full_words] ^= ri

        x = [_SEED_CONSTANT] * 8
        for _ in range(4):
            _mix(x)
        for i in range(0, ISAAC64_SZ, 8):
            for j in range(8):
                x[j] = (x[j] + r[i + j]) & MASK
            _mix(x)
            m[i:i + 8] = x
        for i in range(0, ISAAC64_SZ, 8):
            for j in range(8):
                x[j] = (x[j] + m[i + j]) & MASK
            _mix(x)
            m[i:i + 8] = x

        self._update()

    def _update(self) -> None:
        """Generate a new random block (C: isaac64_update)."""
        m = self._m
        r = self._r
        half = ISAAC64_SZ // 2
        a = self._a
        c = (self._c + 1) & MASK
        b = (self._b + c) & MASK

        i = 0
        while i < half:
            x = m[i]
            t = (a ^ ((a << 21) & MASK)) & MASK
            a = ((MASK ^ t) + m[i + half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ (a >> 5)) + m[i + half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ ((a << 12) & MASK)) + m[i + half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ (a >> 33)) + m[i + half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1

        while i < ISAAC64_SZ:
            x = m[i]
            t = (a ^ ((a << 21) & MASK)) & MASK
            a = ((MASK ^ t) + m[i - half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ (a >> 5)) + m[i - half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ ((a << 12) & MASK)) + m[i - half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1
            x = m[i]
            a = ((a ^ (a >> 33)) + m[i - half]) & MASK
            m[i] = y = (m[_lower_bits(x)] + a + b) & MASK
            r[i] = b = (m[_upper_bits(y)] + x) & MASK
            i += 1

        self._b = b
        self._a = a
        self._n = ISAAC64_SZ

    def next_uint64(self) -> int:
        """Next 64-bit value (C: isaac64_next_uint64)."""
        if not self._n:
            self._update()
        self._n -= 1
        return self._r[self._n]

    def next_uint(self, n: int) -> int:
        """Uniform int in [0, n) (C: isaac64_next_uint).

        Uses the C code's rejection test: a candidate is discarded when
        ``d + n - 1`` would overflow 64 bits.
        """
        if n <= 0:
            raise ValueError(f"next_uint({n}) attempted")
        while True:
            r = self.next_uint64()
            v = r % n
            d = r - v
            if d + n - 1 < (1 << 64):
                return v
