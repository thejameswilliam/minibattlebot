"""
Battle Bot — Controller (Sender)
==================================
Reads a two-axis joystick and sends motor commands to the paired robot
over ESP-NOW (Espressif's peer-to-peer Wi-Fi protocol, no router needed).

How to use:
    1. Flash this file (plus the glib/ folder) to the controller ESP32.
    2. On first power-on, pairing mode starts automatically because there is
       no saved robot address yet.
    3. To re-pair (e.g. swapping a broken robot): hold BOOT on the replacement
       robot first, then hold BOOT on the controller while powering it on.

Pairing:
    - Pair LED blinks while searching for a robot.
    - Pair LED goes solid once the handshake is complete.
    - Both devices save the pairing to flash and reboot.  Future power-ons
      connect automatically without pressing anything.

LED wiring (external components, both LEDs use a 220Ω series resistor):
    Power LED  — anode → 3.3V pin, cathode → GND (always on, no GPIO needed)
    Pair LED   — anode → GPIO20 (D7), cathode → GND

Commands sent to the robot:
    {'x': int, 'y': int}
      x: -100 to 100 — turning  (left = negative, right = positive)
      y: -100 to 100 — throttle (back = negative, forward = positive)

Pin assignments — change these constants to match your wiring:
    Joystick X axis : GPIO2  (D0 / A0) — must be ADC1 pin
    Joystick Y axis : GPIO3  (D1 / A1) — must be ADC1 pin
    Pair LED        : GPIO20 (D7)
    BOOT button     : GPIO9  (D9, built-in on XIAO ESP32-C3, active LOW)
"""

import json
import time
import espnow
import network
import machine
from machine import ADC, Pin, WDT

from glib import gspnow

# ---------------------------------------------------------------------------
# Pin assignments
# ---------------------------------------------------------------------------
JOYSTICK_X_PIN  = 2   # D0 / A0 — ADC1 channel, safe to use with Wi-Fi active
JOYSTICK_Y_PIN  = 3   # D1 / A1 — ADC1 channel, safe to use with Wi-Fi active
PAIR_LED_PIN    = 20  # D7 — blinks while pairing, solid once paired
BOOT_BUTTON_PIN = 9   # D9 — built-in BOOT button on XIAO ESP32-C3, active LOW

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
# Joystick center reads ~2048 on a 0-4095 ADC range.
# Any reading within DEADZONE_PCT of center is treated as zero.
# Raise this if the robot drifts when the stick is at rest.
DEADZONE_PCT = 8

# How often to send a command packet to the robot.
# 50 ms = 20 packets per second — snappy response without flooding the radio.
SEND_INTERVAL_MS = 50

# ---------------------------------------------------------------------------
# Config helpers — load/save the paired robot's MAC from flash
# ---------------------------------------------------------------------------
CONFIG_FILE = "config.json"


def load_robot_mac():
    """Return the saved robot MAC string, or None if not yet paired."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f).get("robot_mac")
    except:
        return None


def save_robot_mac(mac):
    """Persist the robot MAC to flash so it survives power cycles."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"robot_mac": mac}, f)


# ---------------------------------------------------------------------------
# Pairing mode
# ---------------------------------------------------------------------------
def run_pairing_mode(pair_led):
    """
    Listen for a robot in pairing mode and complete the handshake.

    The controller listens for PAIR broadcasts from any nearby robot.
    When one is found, it sends back a PAIR_ACK containing the controller's
    own MAC so the robot can whitelist it for normal operation.

    The pair LED blinks at 2 Hz while searching.

    Returns the robot's MAC address string once pairing succeeds.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    my_mac = ":".join("{:02x}".format(b) for b in wlan.config("mac")).upper()

    # Use raw espnow here so we can receive from unknown devices during the
    # handshake — gspnow only accepts traffic from whitelisted peers.
    e = espnow.ESPNow()
    e.active(True)
    e.add_peer(b"\xff\xff\xff\xff\xff\xff")

    print("=== CONTROLLER PAIRING MODE ===")
    print(f"Controller MAC: {my_mac}")
    print("Searching for a robot in pairing mode...")

    led_state = False
    while True:
        # Blink the LED while searching
        led_state = not led_state
        pair_led.value(led_state)

        # Block for 500 ms waiting for a PAIR broadcast from any robot
        sender, data = e.irecv(500)

        if sender and data:
            try:
                msg = json.loads(data.decode())
                if msg.get("type") == "PAIR":
                    robot_mac = msg["mac"]
                    print(f"Found robot: {robot_mac}")

                    # Respond with our MAC so the robot can whitelist us
                    e.add_peer(sender)
                    ack = json.dumps({"type": "PAIR_ACK", "mac": my_mac}).encode()
                    e.send(sender, ack)

                    pair_led.value(1)  # solid on — pairing complete
                    e.active(False)
                    return robot_mac
            except:
                pass  # malformed packet — keep searching

        else:
            print("Still searching...")


# ---------------------------------------------------------------------------
# Hardware setup
# ---------------------------------------------------------------------------
pair_led    = Pin(PAIR_LED_PIN, Pin.OUT, value=0)
boot_button = Pin(BOOT_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
joystick_x  = ADC(Pin(JOYSTICK_X_PIN))
joystick_y  = ADC(Pin(JOYSTICK_Y_PIN))
joystick_x.atten(ADC.ATTN_11DB)  # full 0–3.3 V range → 0–4095 ADC counts
joystick_y.atten(ADC.ATTN_11DB)

# ---------------------------------------------------------------------------
# Pairing check — runs once at boot
# ---------------------------------------------------------------------------
robot_mac = load_robot_mac()

if boot_button.value() == 0 or robot_mac is None:
    robot_mac = run_pairing_mode(pair_led)
    save_robot_mac(robot_mac)
    print("Pairing saved.  Rebooting into normal mode...")
    machine.reset()

# ---------------------------------------------------------------------------
# Normal operation — set up ESP-NOW with the paired robot
# ---------------------------------------------------------------------------
conn = gspnow.Connection()
robot_group = conn.peerGroupAdd("ROBOT")
robot_group.peerAdd(robot_mac, "ROBOT")

# Paired and ready — LED on solid
pair_led.value(1)

# Watchdog: auto-reboot if the main loop stops feeding it for 5 seconds
wdt = WDT(timeout=5000)


def read_joystick():
    """
    Return (x, y) joystick position as percentages (-100 to 100).

    Raw ADC reads 0–4095; resting center is ~2048.  Values within the
    deadzone are clamped to 0 to prevent motor drift at rest.
    """
    raw_x = joystick_x.read()
    raw_y = joystick_y.read()

    # Map 0–4095 → -100 to 100 (center 2048 → 0)
    x = int((raw_x - 2048) / 2048 * 100)
    y = int((raw_y - 2048) / 2048 * 100)

    # Clamp to ±100 in case the ADC reads slightly outside expected range
    x = max(-100, min(100, x))
    y = max(-100, min(100, y))

    # Apply center deadzone
    if abs(x) < DEADZONE_PCT:
        x = 0
    if abs(y) < DEADZONE_PCT:
        y = 0

    return x, y


print(f"Controller running.  Paired with robot: {robot_mac}")

# ---------------------------------------------------------------------------
# Main loop — read joystick and send commands at SEND_INTERVAL_MS
# ---------------------------------------------------------------------------
last_send_time = time.ticks_ms()

while True:
    wdt.feed()

    now = time.ticks_ms()
    if time.ticks_diff(now, last_send_time) >= SEND_INTERVAL_MS:
        x, y = read_joystick()
        robot_group.send({"x": x, "y": y})
        last_send_time = now

    time.sleep_ms(5)
