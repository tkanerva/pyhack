"""Tests for the calendar.c port (core.calendar).

Fixed-date table tests: every function takes an explicit ``now``
(datetime), so nothing here touches the wall clock except two small
smoke tests of the default (``now=None``) path.
"""
import time
from datetime import datetime, timedelta

from core.calendar import (friday_13th, getnow, getyear, hhmmss,
                           midnight, night, phase_of_the_moon,
                           time_from_yyyymmddhhmmss, yyyymmdd,
                           yyyymmddhhmmss)

T = datetime(2026, 10, 28, 15, 4, 5)


def test_getyear():
    assert getyear(T) == 2026
    assert getyear(datetime(1999, 12, 31)) == 1999


def test_yyyymmdd():
    assert yyyymmdd(T) == 20261028
    assert yyyymmdd(datetime(2000, 1, 1)) == 20000101


def test_hhmmss():
    assert hhmmss(T) == 150405
    assert hhmmss(datetime(2026, 1, 1, 0, 0, 0)) == 0


def test_yyyymmddhhmmss():
    assert yyyymmddhhmmss(T) == "20261028150405"
    assert yyyymmddhhmmss(datetime(2000, 1, 2, 3, 4, 5)) == \
        "20000102030405"


def test_time_from_yyyymmddhhmmss_roundtrip():
    epoch = time_from_yyyymmddhhmmss("20261028150405")
    back = datetime.fromtimestamp(epoch)
    assert (back.year, back.month, back.day,
            back.hour, back.minute, back.second) == \
        (2026, 10, 28, 15, 4, 5)


def test_time_from_yyyymmddhhmmss_malformed_is_zero():
    for bad in ("", "2026102", "202610281504051", "abcdefghijklmn",
                "20261301000000", "20260229120000"):
        assert time_from_yyyymmddhhmmss(bad) == 0


def test_phase_of_the_moon_table():
    # (date, phase) hand-computed from the C formula (the calendar.c
    # 177-189 comment block), covering both epact correction rules:
    # 2000-01-10: goldn 6, epact 24 -> 25; 2011-01-17: goldn 17 > 11,
    # epact 25 -> 26.
    cases = [
        (datetime(2026, 1, 1), 3),
        (datetime(2000, 1, 10), 2),
        (datetime(2011, 1, 17), 4),
        (datetime(2026, 10, 28), 5),
    ]
    for d, want in cases:
        assert phase_of_the_moon(d) == want, d


def test_phase_of_the_moon_range_over_a_year():
    day = datetime(2026, 1, 1)
    seen = set()
    for _ in range(366):
        p = phase_of_the_moon(day)
        assert 0 <= p <= 7
        seen.add(p)
        day += timedelta(days=1)
    assert len(seen) >= 4


def test_friday_13th():
    assert datetime(2026, 2, 13).weekday() == 4  # guard: a Friday
    assert datetime(2026, 3, 13).weekday() == 4  # guard: a Friday
    assert friday_13th(datetime(2026, 2, 13, 12)) is True
    assert friday_13th(datetime(2026, 3, 13, 12)) is True
    assert friday_13th(datetime(2026, 3, 12, 12)) is False
    assert friday_13th(datetime(2026, 3, 14, 12)) is False
    assert friday_13th(datetime(2026, 12, 13, 12)) is False  # Sunday


def test_night_boundaries():
    # C: hour < 6 || hour > 21
    assert night(datetime(2026, 1, 1, 5, 59)) is True
    assert night(datetime(2026, 1, 1, 6, 0)) is False
    assert night(datetime(2026, 1, 1, 12, 0)) is False
    assert night(datetime(2026, 1, 1, 21, 30)) is False
    assert night(datetime(2026, 1, 1, 22, 0)) is True
    assert night(datetime(2026, 1, 1, 23, 59)) is True


def test_midnight():
    assert midnight(datetime(2026, 1, 1, 0, 30)) is True
    assert midnight(datetime(2026, 1, 1, 1, 0)) is False
    assert midnight(datetime(2026, 1, 1, 23, 59)) is False


def test_getnow_smoke():
    assert abs(getnow() - time.time()) < 5


def test_defaults_read_the_wall_clock():
    # now=None == the wall clock (the C getlt() behaviour); values
    # are wall-clock dependent, so only the ranges are asserted.
    assert 19500101 <= yyyymmdd(None) <= 20501231
    assert 0 <= hhmmss(None) <= 235959
    assert 0 <= phase_of_the_moon(None) <= 7
    assert isinstance(friday_13th(None), bool)
