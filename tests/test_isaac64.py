"""Tests for the ISAAC-64 port (core.isaac64).

The C source has no published golden vectors in the tree, so these tests
check the structural properties the algorithm must have: determinism,
range, seed sensitivity, block structure, and the rejection logic of
next_uint().  If you can compile the C original, add a golden-sequence
test here.
"""
import random

from core.isaac64 import (ISAAC64_SEED_SZ_MAX, ISAAC64_SZ, Isaac64, MASK)


def test_same_seed_same_sequence():
    a, b = Isaac64(), Isaac64()
    a.init(b"\x01\x02\x03")
    b.init(b"\x01\x02\x03")
    assert [a.next_uint64() for _ in range(1000)] == \
           [b.next_uint64() for _ in range(1000)]


def test_different_seeds_diverge():
    a, b = Isaac64(), Isaac64()
    a.init(b"seed-one")
    b.init(b"seed-two")
    seq_a = [a.next_uint64() for _ in range(64)]
    seq_b = [b.next_uint64() for _ in range(64)]
    assert seq_a != seq_b


def test_zero_seed_and_empty_seed_work():
    """An empty seed and an all-zero 8-byte seed are the same seed (the
    zero word is XORed into a zero r[]), so both must be well-defined
    and identical; a non-zero seed must differ."""
    a, a2, b = Isaac64(), Isaac64(), Isaac64()
    a.init(b"")
    a2.init(bytes(8))
    b.init(bytes([1, 2, 3, 4, 5, 6, 7, 8]))
    for _ in range(ISAAC64_SZ * 2):  # force at least two blocks
        assert 0 <= a.next_uint64() <= MASK
        assert 0 <= a2.next_uint64() <= MASK
        assert 0 <= b.next_uint64() <= MASK
    assert a.next_uint64() == a2.next_uint64()
    assert a.next_uint64() != b.next_uint64()  # overwhelmingly likely


def test_first_block_consumed_in_reverse():
    """init() fills r[] and sets n=SZ; the C code returns r[--n], so the
    first output is r[255], the 256th is r[0], then a fresh block."""
    isaac = Isaac64()
    isaac.init(b"test")
    saved_r255 = isaac._r[ISAAC64_SZ - 1]
    saved_r0 = isaac._r[0]
    first = isaac.next_uint64()
    assert first == saved_r255
    assert isaac._n == ISAAC64_SZ - 1
    last = None
    for _ in range(ISAAC64_SZ - 1):  # exhaust the first block
        last = isaac.next_uint64()
    assert last == saved_r0          # the 256th draw was r[0]
    assert isaac._n == 0
    fresh = isaac.next_uint64()      # rolls a new block
    assert isaac._n == ISAAC64_SZ - 1
    assert fresh != saved_r255       # new block differs (overwhelmingly likely)


def test_next_uint_range():
    isaac = Isaac64()
    isaac.init(b"range")
    for n in (1, 2, 3, 7, 20, 100, 1 << 20, 1 << 63):
        for _ in range(200):
            v = isaac.next_uint(n)
            assert 0 <= v < n


def test_next_uint_covers_all_small_values():
    isaac = Isaac64()
    isaac.init(b"cover")
    seen = {isaac.next_uint(3) for _ in range(1000)}
    assert seen == {0, 1, 2}
    seen2 = {isaac.next_uint(2) for _ in range(100)}
    assert seen2 == {0, 1}


def test_next_uint_rejects_bad_n():
    isaac = Isaac64()
    try:
        isaac.next_uint(0)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_seed_longer_than_max_is_truncated():
    """Both seeds share their first SEED_SZ_MAX bytes, so after
    truncation they must produce identical sequences."""
    common = bytes(random.Random(9).randrange(256) for _ in range(ISAAC64_SEED_SZ_MAX))
    a, b = Isaac64(), Isaac64()
    a.init(common + b"EXTRA-STUFF")
    b.init(common + b"OTHER-STUFF")
    assert [a.next_uint64() for _ in range(100)] == \
           [b.next_uint64() for _ in range(100)]


def test_odd_length_seed():
    isaac = Isaac64()
    isaac.init(b"abc")  # 3 bytes: no full word + 3-byte little-endian tail
    for _ in range(ISAAC64_SZ):
        assert 0 <= isaac.next_uint64() <= MASK


def test_reseed_changes_the_sequence():
    isaac = Isaac64()
    isaac.init(b"first")
    before = [isaac.next_uint64() for _ in range(8)]
    isaac.reseed(b"second")
    after = [isaac.next_uint64() for _ in range(8)]
    assert before != after


def test_state_is_masked_to_64_bits():
    """Every internal value must stay a 64-bit word (the C types are
    uint64_t); a missed & MASK would leak unbounded Python ints."""
    isaac = Isaac64()
    isaac.init(b"mask-check")
    for _ in range(ISAAC64_SZ * 3):
        isaac.next_uint64()
    assert all(0 <= v <= MASK for v in isaac._m)
    assert all(0 <= v <= MASK for v in isaac._r)
    for v in (isaac._a, isaac._b, isaac._c):
        assert 0 <= v <= MASK
