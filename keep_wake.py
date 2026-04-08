#!/usr/bin/env python3
"""
keep_wake.py — Prevent Mac sleep and lock screen using IOKit assertions.
Press Enter to toggle screen dim. Ctrl-C to exit.
"""

from __future__ import annotations

import ctypes
import sys
import time


# ---------------------------------------------------------------------------
# IOKit — replaces caffeinate entirely
# ---------------------------------------------------------------------------
_iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
_iokit.IOPMAssertionCreateWithName.restype = ctypes.c_uint32
_iokit.IOPMAssertionCreateWithName.argtypes = [
    ctypes.c_char_p,
    ctypes.c_uint32,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint32),
]
_iokit.IOPMAssertionRelease.restype = ctypes.c_uint32
_iokit.IOPMAssertionRelease.argtypes = [ctypes.c_uint32]

_kIOPMAssertionLevelOn = 255

# Prevents display sleep + lock screen triggered by user idle
_kPreventUserIdleDisplaySleep = b"PreventUserIdleDisplaySleep"
# Prevents system sleep triggered by user idle
_kPreventUserIdleSystemSleep  = b"PreventUserIdleSystemSleep"


def _create_assertion(assertion_type: bytes, reason: str) -> ctypes.c_uint32:
    aid = ctypes.c_uint32(0)
    ret = _iokit.IOPMAssertionCreateWithName(
        assertion_type,
        _kIOPMAssertionLevelOn,
        reason.encode(),
        ctypes.byref(aid),
    )
    if ret != 0:
        print(f"Warning: IOKit assertion '{assertion_type.decode()}' failed (err={ret})")
    return aid


def _release_assertion(aid: ctypes.c_uint32) -> None:
    if aid.value:
        _iokit.IOPMAssertionRelease(aid)


# ---------------------------------------------------------------------------
# DisplayServices — screen brightness via private framework
# ---------------------------------------------------------------------------
def _init_display():
    CG = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    )
    CG.CGMainDisplayID.restype = ctypes.c_uint32
    display_id = CG.CGMainDisplayID()

    ds = ctypes.cdll.LoadLibrary(
        "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices"
    )
    ds.DisplayServicesGetBrightness.restype = ctypes.c_int
    ds.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
    ds.DisplayServicesSetBrightness.restype = ctypes.c_int
    ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
    return ds, display_id


def _get_brightness(ds, display_id) -> float:
    val = ctypes.c_float(0.0)
    ds.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
    return val.value


def _set_brightness(ds, display_id, level: float) -> None:
    ds.DisplayServicesSetBrightness(display_id, ctypes.c_float(level))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ds, display_id = _init_display()
    original_brightness = _get_brightness(ds, display_id)

    # Acquire IOKit assertions — prevents idle sleep AND lock screen
    display_aid = _create_assertion(_kPreventUserIdleDisplaySleep, "KeepWake: prevent display sleep & lock")
    system_aid  = _create_assertion(_kPreventUserIdleSystemSleep,  "KeepWake: prevent system sleep")

    print("Sleep and lock screen prevented via IOKit.")
    print(f"Brightness: {original_brightness:.2f} → dimming to 0.02")
    print("Press Enter to toggle dim/restore. Ctrl-C to quit.\n")
    time.sleep(1)

    _set_brightness(ds, display_id, 0.02)
    dimmed = True
    print("Screen dimmed.")

    def cleanup() -> None:
        _set_brightness(ds, display_id, original_brightness)
        _release_assertion(display_aid)
        _release_assertion(system_aid)
        print(f"\nBrightness restored. IOKit assertions released.")

    try:
        while True:
            input()
            if dimmed:
                _set_brightness(ds, display_id, original_brightness)
                print(f"Brightness restored to {original_brightness:.2f}")
            else:
                _set_brightness(ds, display_id, 0.02)
                print("Screen dimmed.")
            dimmed = not dimmed
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
