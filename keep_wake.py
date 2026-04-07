#!/usr/bin/env python3
import ctypes
import subprocess
import time
import datetime
import sys


def _init_brightness():
    CG = ctypes.cdll.LoadLibrary(
        '/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'
    )
    CG.CGMainDisplayID.restype = ctypes.c_uint32
    display_id = CG.CGMainDisplayID()

    ds = ctypes.cdll.LoadLibrary(
        '/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'
    )
    ds.DisplayServicesGetBrightness.restype = ctypes.c_int
    ds.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
    ds.DisplayServicesSetBrightness.restype = ctypes.c_int
    ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]

    return ds, display_id


def get_brightness(ds, display_id):
    val = ctypes.c_float(0.0)
    ds.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
    return val.value


def set_brightness(ds, display_id, level):
    ds.DisplayServicesSetBrightness(display_id, ctypes.c_float(level))


def main():
    ds, display_id = _init_brightness()

    original_brightness = get_brightness(ds, display_id)
    print(f"Current brightness: {original_brightness:.2f}")
    print("Dimming screen... Press Enter to restore brightness.")
    time.sleep(1)  # brief pause so user can read the message

    set_brightness(ds, display_id, 0.02)

    process = subprocess.Popen(["caffeinate", "-dimsu"])
    start_time = time.time()
    print(f"Started caffeinate (PID: {process.pid}) at {datetime.datetime.now()}")

    try:
        dimmed = True
        while True:
            input()  # blocks until Enter is pressed
            if dimmed:
                set_brightness(ds, display_id, original_brightness)
                print(f"Brightness restored to {original_brightness:.2f}")
            else:
                set_brightness(ds, display_id, 0.02)
                print("Screen dimmed.")
            dimmed = not dimmed

    except KeyboardInterrupt:
        print("\nStopping script (Ctrl-C pressed)...")
    finally:
        set_brightness(ds, display_id, original_brightness)
        process.terminate()
        process.wait()
        print(f"Caffeinate stopped at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
