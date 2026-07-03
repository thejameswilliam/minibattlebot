"""
Battle Bot — Controller (Sender)
==================================
Reads a 4-direction switch joystick (COM/Ground + X+/X-/Y+/Y- momentary
switches, no proportional/analog output) and sends motor commands to the
paired robot over ESP-NOW (Espressif's peer-to-peer Wi-Fi protocol, no
router needed).  Since the joystick is on/off per direction, each axis is
sent to the robot at full speed (±100) or 0 — there is no in-between.

How to use:
    1. Flash this file (plus the glib/ folder) to the controller ESP32.
    2. On first power-on, pairing mode starts automatically because there is
       no saved robot address yet.
    3. To re-pair (e.g. swapping a broken robot): power on the replacement
       robot and press its BOOT button within 3 seconds, then power on the
       controller and press its BOOT button within 3 seconds.

Pairing:
    - Pair LED blinks while searching for a robot.
    - Pair LED goes solid once the handshake is complete.
    - Both devices save the pairing to flash and reboot.  Future power-ons
      connect automatically without pressing anything.

LED wiring (external components, both LEDs use a 220Ω series resistor):
    Power LED  — anode → 3.3V pin, cathode → GND (always on, no GPIO needed)
    Pair LED   — anode → GPIO18, cathode → GND

Commands sent to the robot:
    {'x': int, 'y': int}
      x: -100, 0, or 100 — turning  (left = -100, right = 100)
      y: -100, 0, or 100 — throttle (back = -100, forward = 100)

Joystick wiring: this is a 4-direction switch joystick, not a potentiometer.
Ground is common; each of X+/X-/Y+/Y- is a momentary switch that connects to
Ground when the stick is pushed that direction.  Wire each switch pin to its
GPIO with the chip's internal pull-up enabled (done in code below) — no
external resistors needed.  Pushing a direction pulls that pin LOW.

Pin assignments — change these constants to match your wiring:
    Joystick X+ (right) : GPIO32
    Joystick X- (left)  : GPIO33
    Joystick Y+ (fwd)   : GPIO25
    Joystick Y- (back)  : GPIO26
    Pair LED            : GPIO18
    BOOT button         : GPIO0  (built-in BOOT button on ESP32-WROOM-32 dev
                                  boards, no external wiring needed, active LOW)

Note on pin choice: GPIO6-11 are wired to the module's internal SPI flash on
ESP32-WROOM-32 and are not usable.  GPIO1/GPIO3 are UART0 TX/RX, used for
flashing and the REPL — avoid them for GPIO duty.  GPIO34-39 are input-only
and have no internal pull-up, so they're unsuitable for these switches
without an external pull-up resistor — GPIO32/33/25/26 were chosen instead
since they support internal pull-ups.

Note on GPIO0 (BOOT button): this pin is also a boot-mode strapping pin on
the ESP32.  Holding it LOW *during power-on/reset* drops the chip straight
into the ROM UART bootloader instead of running this script — so pairing can
only be triggered by pressing BOOT shortly *after* boot completes, never by
holding it while powering on.  See run_pairing_mode() below.
"""

import json
import time
import espnow
import network
import machine
from machine import Pin, WDT

from glib import gspnow

# ---------------------------------------------------------------------------
# Pin assignments
# ---------------------------------------------------------------------------
JOYSTICK_X_PLUS_PIN  = 32  # right — momentary switch to Ground
JOYSTICK_X_MINUS_PIN = 33  # left  — momentary switch to Ground
JOYSTICK_Y_PLUS_PIN  = 25  # forward — momentary switch to Ground
JOYSTICK_Y_MINUS_PIN = 26  # back    — momentary switch to Ground
PAIR_LED_PIN         = 18  # blinks while pairing, solid once paired
BOOT_BUTTON_PIN      = 0   # built-in BOOT button on ESP32-WROOM-32, active LOW

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
# How long after boot to watch BOOT for a re-pair request.  GPIO0 is a boot
# strapping pin, so it can only be sampled as a button *after* the chip has
# already finished booting into this script — not while power is applied.
REPAIR_WINDOW_MS = 3000

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
pair_led     = Pin(PAIR_LED_PIN, Pin.OUT, value=0)
boot_button  = Pin(BOOT_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
joystick_xp  = Pin(JOYSTICK_X_PLUS_PIN, Pin.IN, Pin.PULL_UP)
joystick_xm  = Pin(JOYSTICK_X_MINUS_PIN, Pin.IN, Pin.PULL_UP)
joystick_yp  = Pin(JOYSTICK_Y_PLUS_PIN, Pin.IN, Pin.PULL_UP)
joystick_ym  = Pin(JOYSTICK_Y_MINUS_PIN, Pin.IN, Pin.PULL_UP)

# ---------------------------------------------------------------------------
# Pairing check — runs once at boot
#
# GPIO0 (BOOT) is a boot-mode strapping pin, so it can't be held during
# power-on to request pairing — that drops the chip into the ROM bootloader
# instead of running this script.  Instead, watch it for a few seconds after
# boot has already completed.
# ---------------------------------------------------------------------------
robot_mac = load_robot_mac()

force_pairing = False
if robot_mac is not None:
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

if force_pairing or robot_mac is None:
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
    Return (x, y) as -100, 0, or 100 based on which direction switches are
    pressed.  Switches are active LOW (pressed pulls the pin to Ground).
    If both switches on an axis are pressed at once, they cancel to 0.
    """
    x = 0
    if joystick_xp.value() == 0:
        x += 100
    if joystick_xm.value() == 0:
        x -= 100

    y = 0
    if joystick_yp.value() == 0:
        y += 100
    if joystick_ym.value() == 0:
        y -= 100

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
