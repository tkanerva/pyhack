"""NetHack wall-clock time routines (port of src/calendar.c).

All eleven C functions, the arithmetic verbatim:

    getnow()                        epoch seconds (C: time())
    getyear()                       the full year
    yyyymmdd(now)                   8-digit date number
    hhmmss(now)                     6-digit time-of-day number
    yyyymmddhhmmss(now)             the 14-char "YYYYMMDDHHMMSS"
    time_from_yyyymmddhhmmss(buf)   parse that back to epoch seconds
    phase_of_the_moon(now)          0-7, 0 = new, 4 = full (Metonic)
    friday_13th(now)                the (un)lucky-day predicate
    night(now)                      hour < 6 or hour > 21
    midnight(now)                   hour == 0

C uses these for the rand() seed, the tombstone year, record-file
timestamps, monster reactions to NEW_MOON / FULL_MOON, the undead's
midnight ferocity (the double base damage in mhitu.c's hitmu), and
the "very old files" ageing.  The live game call site in the pyhack
core is ``World.midnight`` (sampled once at world creation, see
core.worldgen.new_world) feeding core.step -> mattacku; the moon
phase awaits the monster-reaction and botl ports.

Adaptations for the pyhack architecture (documented, not bugs):

- C reads the wall clock through getnow() / getlt() (time() +
  localtime()); here every function takes an explicit
  ``now: datetime`` (``None`` = the wall clock, the C behaviour), so
  tests run on exact dates and ``step()`` never touches the clock.
- C's ``tm_year`` is years since 1900; Python's struct_time carries
  the full year, so C's ``1900 +`` addition and the ``year < 70``
  guard (a localtime quirk) are dropped.
- C returns ints for the predicates and a static buffer for
  yyyymmddhhmmss; here bools and a fresh string (no shared state).
- ``time_from_yyyymmddhhmmss`` keeps the C failure contract: 0 for a
  malformed string or a date that does not exist (C's mktime -1 also
  maps to 0).
- This platform's libc reports ``tm_mon`` 1-indexed (January = 1) and
  ``tm_wday`` Monday = 0 (verified: ``time.localtime`` of 2026-10-28
  gives tm_mon = 10, tm_wday = 2), while C's struct tm -- and the
  NetHack arithmetic over it (``tm_mon + 1``, ``tm_wday == 5``) --
  assumes January = 0 and Sunday = 0.  ``_lt`` therefore rebuilds the
  struct from the unambiguous ``datetime.month`` / ``datetime.weekday()``
  fields, so the ported arithmetic behaves as in C on any platform.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional


def _lt(now: Optional[datetime] = None) -> time.struct_time:
    """The local time as a struct_time in C convention
    (C: getlt, calendar.c 40-46).

    ``now`` is the injected wall clock; ``None`` reads the real clock
    (C: getnow).  tm_mon / tm_wday are rebuilt from the datetime's
    own fields because this platform's libc reports them in a
    non-C convention (module docstring).
    """
    if now is None:
        now = datetime.now()
    t = now.timetuple()
    return time.struct_time((
        t.tm_year,
        now.month - 1,            # C: January = 0
        now.day,
        t.tm_hour,
        t.tm_min,
        t.tm_sec,
        (now.weekday() + 1) % 7,  # C: Sunday = 0
        t.tm_yday,
        -1,
    ))


def getnow() -> int:
    """The current wall clock in epoch seconds
    (C: getnow, calendar.c 31-38)."""
    return int(time.time())


def getyear(now: Optional[datetime] = None) -> int:
    """The current year (C: getyear, calendar.c 48-52).

    C computes 1900 + tm_year; Python's struct_time already carries
    the full year (module docstring).
    """
    return _lt(now).tm_year


def yyyymmdd(now: Optional[datetime] = None) -> int:
    """The date as an 8-digit number, e.g. 20261028
    (C: yyyymmdd, calendar.c 55-77)."""
    lt = _lt(now)
    return lt.tm_year * 10000 + (lt.tm_mon + 1) * 100 + lt.tm_mday


def hhmmss(now: Optional[datetime] = None) -> int:
    """The time of day as a 6-digit number, e.g. 150405
    (C: hhmmss, calendar.c 79-92)."""
    lt = _lt(now)
    return lt.tm_hour * 10000 + lt.tm_min * 100 + lt.tm_sec


def yyyymmddhhmmss(now: Optional[datetime] = None) -> str:
    """The full stamp as "YYYYMMDDHHMMSS"
    (C: yyyymmddhhmmss, calendar.c 94-117).

    C writes into a static 15-byte buffer; a fresh string is returned
    instead (no hidden state).
    """
    lt = _lt(now)
    return (f"{lt.tm_year:04d}{lt.tm_mon + 1:02d}{lt.tm_mday:02d}"
            f"{lt.tm_hour:02d}{lt.tm_min:02d}{lt.tm_sec:02d}")


def time_from_yyyymmddhhmmss(buf: Optional[str]) -> int:
    """Parse a 14-char "YYYYMMDDHHMMSS" back to epoch seconds
    (C: time_from_yyyymmddhhmmss, calendar.c 119-175).

    Returns 0 for a malformed string or a nonexistent date (the C
    failure contract; C's mktime -1 also maps to 0 here).
    """
    if not buf or len(buf) != 14:
        return 0
    try:
        dt = datetime(int(buf[0:4]), int(buf[4:6]), int(buf[6:8]),
                      int(buf[8:10]), int(buf[10:12]), int(buf[12:14]))
    except ValueError:
        return 0
    return int(dt.timestamp())


def phase_of_the_moon(now: Optional[datetime] = None) -> int:
    """The moon phase, 0-7 with 0 = new and 4 = full
    (C: phase_of_the_moon, calendar.c 190-203).

    The C Metonic arithmetic verbatim (see the C comment block at
    calendar.c 177-189): golden number + epact, including the two
    epact correction rules, folded into 8 reported phases.
    """
    lt = _lt(now)
    goldn = (lt.tm_year % 19) + 1
    epact = (11 * goldn + 18) % 30
    if (epact == 25 and goldn > 11) or epact == 24:
        epact += 1
    return (((((lt.tm_yday + epact) * 6) + 11) % 177) // 22) & 7


def friday_13th(now: Optional[datetime] = None) -> bool:
    """Whether today is a Friday the 13th
    (C: friday_13th, calendar.c 205-212)."""
    lt = _lt(now)
    return lt.tm_wday == 5 and lt.tm_mday == 13


def night(now: Optional[datetime] = None) -> bool:
    """Whether it is night: before 06:00 or after 21:59
    (C: night, calendar.c 214-220; C returns an int, the truth is
    the same)."""
    hour = _lt(now).tm_hour
    return hour < 6 or hour > 21


def midnight(now: Optional[datetime] = None) -> bool:
    """Whether it is midnight: the 00 hour
    (C: midnight, calendar.c 222-226).

    The live game call site: main.py samples this once into
    ``World.midnight`` (core.worldgen.new_world), which core.step
    forwards to mattacku's undead double-damage.
    """
    return _lt(now).tm_hour == 0
