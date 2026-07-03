"""
Battle Bot — Robot (Receiver)
==============================
Receives joystick commands from a paired controller over ESP-NOW and
drives two motors using tank-style steering.

How to use:
    1. Flash this file, motors.py, and the glib/ folder to the robot ESP32.
    2. On first power-on, pairing mode starts automatically because there is
       no saved controller address yet.
    3. To re-pair (e.g. swapping to a replacement robot): power on this robot
       and press its BOOT button within 3 seconds, then power on the
       controller and press its BOOT button within 3 seconds.

Pairing:
    - Pair LED blinks while broadcasting and waiting for the controller.
    - Pair LED goes solid once the handshake is complete.
    - Both devices save the pairing to flash and reboot.

LED wiring (external components, both LEDs use a 220Ω series resistor):
    Power LED  — anode → 3.3V pin, cathode → GND (always on, no GPIO needed)
    Pair LED   — anode → GPIO10 (D10), cathode → GND

Safety features:
    - Motors stop within 200 ms if no command is received.
    - Pair LED turns off when the robot loses contact with the controller.
    - Hardware watchdog reboots the board if the main loop hangs for 5 s.

Pin assignments — change these constants to match your wiring:
    Motor A IN1 : GPIO2  (D0)
    Motor A IN2 : GPIO3  (D1)
    Motor B IN1 : GPIO5  (D3)
    Motor B IN2 : GPIO6  (D4)
    Pair LED    : GPIO10 (D10)
    BOOT button : GPIO9  (D9, built-in on XIAO ESP32-C3, active LOW)

Note on GPIO9 (BOOT button): this pin is also a boot-mode strapping pin on
the ESP32-C3.  Holding it LOW *during power-on* drops the chip straight into
the ROM UART bootloader instead of running this script — so pairing can only
be triggered by pressing BOOT shortly *after* boot completes, never by
holding it while powering on.  See run_pairing_mode() below.

Note on GPIO20/21 (D7/D6): these are U0RXD/U0TXD, wired to the onboard
USB-serial bridge used for flashing and the REPL.  Avoid using them as
general-purpose GPIO (e.g. for an LED) — driving GPIO20 will contend with
the bridge chip's TX line whenever USB is connected.
"""

import json
import time
import espnow
import network
import machine
from machine import Pin, WDT

from motors import Motor
from glib import gspnow

# ---------------------------------------------------------------------------
# Pin assignments
# ---------------------------------------------------------------------------
MOTOR_A_IN1     = 2   # D0
MOTOR_A_IN2     = 3   # D1

MOTOR_B_IN1     = 5   # D3
MOTOR_B_IN2     = 6   # D4

PAIR_LED_PIN    = 10  # D10 — blinks while pairing, solid when connected, off on signal loss
BOOT_BUTTON_PIN = 9   # D9 — built-in BOOT button on XIAO ESP32-C3, active LOW

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
# Stop motors if no command arrives within this many milliseconds.
# 200 ms is long enough to survive brief interference but short enough
# to halt the robot quickly if the controller is switched off.
COMMAND_TIMEOUT_MS = 200

# How long after boot to watch BOOT for a re-pair request.  GPIO9 is a boot
# strapping pin, so it can only be sampled as a button *after* the chip has
# already finished booting into this script — not while power is applied.
REPAIR_WINDOW_MS = 3000

# ---------------------------------------------------------------------------
# Config helpers — load/save the paired controller's MAC from flash
# ---------------------------------------------------------------------------
CONFIG_FILE = "config.json"


def load_controller_mac():
    """Return the saved controller MAC string, or None if not yet paired."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f).get("controller_mac")
    except:
        return None


def save_controller_mac(mac):
    """Persist the controller MAC to flash so it survives power cycles."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"controller_mac": mac}, f)


# ---------------------------------------------------------------------------
# Pairing mode
# ---------------------------------------------------------------------------
def run_pairing_mode(pair_led):
    """
    Broadcast this robot's MAC address until a controller pairs with it.

    The robot sends a PAIR broadcast every 500 ms and listens for a PAIR_ACK
    from the controller.  The ACK contains the controller's own MAC so the
    robot can whitelist it for normal operation.

    The pair LED blinks at 2 Hz while advertising.

    Returns the controller's MAC address string once pairing succeeds.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    my_mac = ":".join("{:02x}".format(b) for b in wlan.config("mac")).upper()

    # Use raw espnow here so we can talk to unknown devices during the
    # handshake — gspnow only accepts traffic from whitelisted peers.
    e = espnow.ESPNow()
    e.active(True)
    e.add_peer(b"\xff\xff\xff\xff\xff\xff")

    print("=== ROBOT PAIRING MODE ===")
    print(f"Robot MAC: {my_mac}")
    print("Broadcasting... waiting for a controller.")

    broadcast_msg = json.dumps({"type": "PAIR", "mac": my_mac}).encode()
    led_state = False

    while True:
        # Blink LED and broadcast our MAC
        led_state = not led_state
        pair_led.value(led_state)
        e.send(b"\xff\xff\xff\xff\xff\xff", broadcast_msg)

        # Wait up to 500 ms for a PAIR_ACK from a controller
        sender, data = e.irecv(500)

        if sender and data:
            try:
                reply = json.loads(data.decode())
                if reply.get("type") == "PAIR_ACK":
                    controller_mac = reply["mac"]
                    print(f"Paired with controller: {controller_mac}")
                    pair_led.value(1)  # solid on — pairing complete
                    e.active(False)
                    return controller_mac
            except:
                pass  # malformed packet — keep broadcasting


# ---------------------------------------------------------------------------
# Hardware setup
# ---------------------------------------------------------------------------
motor_a     = Motor(MOTOR_A_IN1, MOTOR_A_IN2)
motor_b     = Motor(MOTOR_B_IN1, MOTOR_B_IN2)
pair_led    = Pin(PAIR_LED_PIN, Pin.OUT, value=0)
boot_button = Pin(BOOT_BUTTON_PIN, Pin.IN, Pin.PULL_UP)


def stop_all_motors():
    """Stop both motors immediately.  Called on timeout and errors."""
    motor_a.stop()
    motor_b.stop()


# ---------------------------------------------------------------------------
# Pairing check — runs once at boot
#
# GPIO9 (BOOT) is a boot-mode strapping pin, so it can't be held during
# power-on to request pairing — that drops the chip into the ROM bootloader
# instead of running this script.  Instead, watch it for a few seconds after
# boot has already completed.
# ---------------------------------------------------------------------------
controller_mac = load_controller_mac()

force_pairing = False
if controller_mac is not None:
    print("Press BOOT within 3s to re-pair...")
    window_start = time.ticks_ms()
    led_state = False
    while time.ticks_diff(time.ticks_ms(), window_start) < REPAIR_WINDOW_MS:
        if boot_button.value() == 0:
            force_pairing = True
            break
        led_state = not led_state
        pair_led.value(led_state)
        time.sleep_ms(100)
    pair_led.value(0)

if force_pairing or controller_mac is None:
    controller_mac = run_pairing_mode(pair_led)
    save_controller_mac(controller_mac)
    print("Pairing saved.  Rebooting into normal mode...")
    machine.reset()

# ---------------------------------------------------------------------------
# Normal operation — set up ESP-NOW with the paired controller
# ---------------------------------------------------------------------------
conn = gspnow.Connection()
ctrl_group = conn.peerGroupAdd("CONTROLLER")
ctrl_group.peerAdd(controller_mac, "CONTROLLER")

# Track when the last command arrived to detect signal loss
last_command_time = time.ticks_ms()


def on_command_received(sender_mac, data):
    """
    Called by the ESP-NOW interrupt every time a command packet arrives.

    data is expected to be a dict: {'x': int, 'y': int}
      x: -100 to 100 — turning  (negative = left,    positive = right)
      y: -100 to 100 — throttle (negative = reverse,  positive = forward)
    """
    global last_command_time
    last_command_time = time.ticks_ms()

    x = data.get("x", 0)
    y = data.get("y", 0)

    # Tank-drive mixing: each side is throttle ± turn
    left_speed  = y + x
    right_speed = y - x

    left_speed  = max(-100, min(100, left_speed))
    right_speed = max(-100, min(100, right_speed))

    motor_a.setSpeed(left_speed)
    motor_b.setSpeed(right_speed)


# Replace the default (print-only) handler with our motor control handler
conn.onDataReceived = on_command_received

# Watchdog: auto-reboot if the main loop stops feeding it for 5 seconds
wdt = WDT(timeout=5000)

print(f"Robot running.  Listening for controller: {controller_mac}")

# ---------------------------------------------------------------------------
# Main loop — watchdog feed, command timeout, and LED status
# ---------------------------------------------------------------------------
while True:
    wdt.feed()

    signal_lost = time.ticks_diff(time.ticks_ms(), last_command_time) > COMMAND_TIMEOUT_MS

    if signal_lost:
        stop_all_motors()
        pair_led.value(0)   # LED off = no signal
    else:
        pair_led.value(1)   # LED solid = connected and receiving

    time.sleep_ms(10)
