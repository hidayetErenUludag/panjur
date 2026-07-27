#!/usr/bin/env python3
"""
Calibrate each SG90's rest and press angle, interactively.

    ~/panjur-env/bin/python3 calibrate_servo.py

Mount the bracket and servos first. For each of the four GPIO pins this
walks you through nudging the arm until (a) it sits just off the button
(REST) and (b) it holds the button down firmly but not straining (PRESS).
Results are saved to ~/.panjur.servos.json, which app.py reads on start.

IMPORTANT: stop the main service first so it isn't fighting you for the
pins:  sudo systemctl stop panjur
Restart it when done:  sudo systemctl start panjur

Needs the servo power rail on and grounds commoned to the Pi, same as
normal operation.
"""

import json
import os
import sys
import time

CAL_PATH = os.path.expanduser("~/.panjur.servos.json")

# Must match SHUTTERS in app.py
PINS = [
    (17, "Salon UP"),
    (22, "Salon DOWN"),
    (27, "Yatak Odasi UP"),
    (23, "Yatak Odasi DOWN"),
]


def make_servo(pin):
    from gpiozero import AngularServo
    try:
        from gpiozero.pins.pigpio import PiGPIOFactory
        factory = PiGPIOFactory()
    except Exception:
        factory = None
    return AngularServo(
        pin,
        min_angle=0,
        max_angle=180,
        min_pulse_width=0.5 / 1000,
        max_pulse_width=2.4 / 1000,
        pin_factory=factory,
    )


def calibrate_one(pin, label):
    print(f"\n=== {label}  (GPIO {pin}) ===")
    servo = make_servo(pin)
    angle = 90
    servo.angle = angle
    time.sleep(0.5)

    def prompt(what):
        nonlocal angle
        print(f"\nSet the {what} angle for {label}.")
        print("  +/-  : nudge by 5     (or type a number 0-180)")
        print("  f/b  : fine nudge by 1")
        print("  ok   : accept this angle")
        print("  skip : leave this servo at its saved/default value")
        while True:
            print(f"  [{label}] {what} angle = {angle}", end="  > ")
            cmd = input().strip().lower()
            if cmd == "ok":
                return angle
            if cmd == "skip":
                return None
            if cmd == "+":
                angle = min(180, angle + 5)
            elif cmd == "-":
                angle = max(0, angle - 5)
            elif cmd == "f":
                angle = min(180, angle + 1)
            elif cmd == "b":
                angle = max(0, angle - 1)
            else:
                try:
                    angle = max(0, min(180, int(cmd)))
                except ValueError:
                    print("    ? use +/-/f/b, a number, 'ok' or 'skip'")
                    continue
            servo.angle = angle
            time.sleep(0.25)

    rest = prompt("REST (arm just OFF the button)")
    press = prompt("PRESS (button held down firmly)")

    servo.angle = None  # detach
    if rest is None or press is None:
        print(f"  {label}: skipped")
        return None
    return {"rest": rest, "press": press}


def main():
    print("Panjur servo calibration")
    print("------------------------")
    print("Make sure the main service is stopped:  sudo systemctl stop panjur")
    if input("Ready? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 1

    cal = {}
    if os.path.exists(CAL_PATH):
        with open(CAL_PATH) as f:
            cal = json.load(f)

    for pin, label in PINS:
        result = calibrate_one(pin, label)
        if result:
            cal[str(pin)] = result
            # save after each one, so a mistake later doesn't lose progress
            with open(CAL_PATH, "w") as f:
                json.dump(cal, f, indent=2)
            print(f"  saved: {label} rest={result['rest']} press={result['press']}")

    print(f"\nDone. Wrote {CAL_PATH}:")
    print(json.dumps(cal, indent=2))
    print("\nNow:  sudo systemctl start panjur")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
