"""Quartz aggregate counters; never request key codes, text, or event payloads."""
import ctypes
from functools import lru_cache

COMBINED_SESSION=0
KEY_DOWN=10
ANY_INPUT=0xffffffff


@lru_cache(maxsize=1)
def quartz():
    lib=ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    lib.CGEventSourceCounterForEventType.argtypes=[ctypes.c_int32,ctypes.c_uint32]
    lib.CGEventSourceCounterForEventType.restype=ctypes.c_uint32
    lib.CGEventSourceSecondsSinceLastEventType.argtypes=[ctypes.c_int32,ctypes.c_uint32]
    lib.CGEventSourceSecondsSinceLastEventType.restype=ctypes.c_double
    return lib


def key_count():
    return quartz().CGEventSourceCounterForEventType(COMBINED_SESSION,KEY_DOWN)


def idle_seconds():
    return quartz().CGEventSourceSecondsSinceLastEventType(COMBINED_SESSION,ANY_INPUT)


def counter_delta(previous,current):
    if current>=previous:return current-previous
    # A counter reset starts a new baseline; only a true uint32 wrap adds events.
    return (current-previous)&ANY_INPUT if previous-current>2**31 else 0
