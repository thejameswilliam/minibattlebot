# Mini Battle Bot

Two-player ESP32 battle bots using MicroPython and ESP-NOW for wireless control.
Designed for a makerspace fundraising event.

---

## Project layout

```
minibattlebot/
├── controller/         ← Flash to the controller ESP32
│   └── main.py
├── robot/              ← Flash to the robot ESP32
│   ├── main.py
│   └── motors.py
└── glib/               ← Shared ESP-NOW library — deploy to BOTH devices
    ├── gspnow.py
    ├── glog.py
    └── pickle.py
```

The `glib/` folder must be present on both devices.  When deploying, copy
the device folder AND the `glib/` folder to the device.

---

## Hardware

Robot is a **Seeed XIAO ESP32-C3**. Controller is an **ESP32-WROOM-32** dev board.

Controller's joystick is a 4-direction switch type (COM/Ground + X+/X-/Y+/Y-
momentary switches), not a potentiometer — each axis is full speed (±100) or
0, no in-between. Internal pull-ups are used, so no external resistors are
needed on the switch wiring.

### Controller
| Component | GPIO | WIRE COLOR |
|-----------|------| ----------- |
| Joystick X+ (right) | GPIO32 | Green X+
| Joystick X- (left) | GPIO33 | Blue X-
| Joystick Y+ (forward) | GPIO25 | Grey Y+
| Joystick Y- (back) | GPIO26 | Purple Y-
| Pair LED (220Ω to GND) | GPIO18 |
| Power LED (220Ω to GND) | 3V3 pin — hardwired, no GPIO |
| BOOT button (built-in) | GPIO0 |






Robot uses a 4-pin IN/IN H-bridge driver (e.g. TC1508S) — no separate PWM/EN
pin, speed is controlled by PWMing whichever IN pin is active.

### Robot
| Component | XIAO pin | GPIO |
|-----------|----------|------|
| Motor A IN1 | D0 | GPIO2 |
| Motor A IN2 | D1 | GPIO3 |
| Motor B IN1 | D3 | GPIO5 |
| Motor B IN2 | D4 | GPIO6 |
| Pair LED (220Ω to GND) | D10 | GPIO10 |
| Power LED (220Ω to GND) | 3V3 pin | — hardwired, no GPIO |
| BOOT button (built-in) | D9 | GPIO9 |

Pin assignments are constants at the top of each `main.py` — edit them there if your wiring differs.

### LED wiring

Both boards use the same two-LED setup, just on different pair-LED pins (see
the tables above):

```
Power LED:  3V3 pin      ──[220Ω]──[LED anode → cathode]── GND
Pair LED:   GPIO10 or 18 ──[220Ω]──[LED anode → cathode]── GND
```

The power LED is always on whenever the board has power — no code involved.
The pair LED is software-controlled (see LED behavior below).

**LED behavior:**

| State | Pair LED |
|-------|----------|
| Pairing mode (searching) | Blinking |
| Paired and connected | Solid on |
| Robot lost signal (>200 ms) | Off |

> **Robot (XIAO ESP32-C3) notes:**
>
> **ADC:** GPIO2 and GPIO3 are both ADC1 channels, which remain accurate
> while ESP-NOW / Wi-Fi is active.  Do not use GPIO5 (D3/A3) for ADC — it shares
> ADC2 with the Wi-Fi radio and gives unreliable readings when wireless is on.
>
> **GPIO9 (BOOT):** this is a boot-mode strapping pin on the ESP32-C3
> — holding it LOW during power-on drops the chip into the ROM bootloader
> instead of running MicroPython, so it can only be read as a button *after*
> boot completes (see Pairing below), never held while powering on.
>
> **GPIO20/21 (D7/D6):** these are the onboard USB-serial UART pins
> (U0RXD/U0TXD) used for flashing and the REPL. Avoid wiring anything to them.

> **Controller (ESP32-WROOM-32) notes:**
>
> **Joystick switch pins:** GPIO32/33/25/26 all support the chip's internal
> pull-up resistor, which is enabled in code — no external pull-up wiring
> needed for the direction switches.
>
> **GPIO34-39:** input-only and have no internal pull-up, so they're not
> usable for the joystick switches without adding an external pull-up
> resistor.
>
> **GPIO6-11:** wired to the module's internal SPI flash — not usable/broken
> out on most WROOM-32 dev boards.
>
> **GPIO0 (BOOT):** a boot-mode strapping pin, same caveat as the robot's
> GPIO9 — it can only be read as a button *after* boot completes, never held
> during power-on. It's wired to the physical BOOT button already on the dev
> board, so no external wiring is needed.
>
> **GPIO1/GPIO3:** UART0 TX/RX, used for flashing and the REPL. Avoid wiring
> anything to them.

---

## Deploying

### Find your serial port

```bash
ls /dev/tty.*
```

The robot (XIAO ESP32-C3) typically shows up as `/dev/tty.usbmodem*`. The
controller (ESP32-WROOM-32) typically shows up as `/dev/tty.usbserial-*` or
`/dev/tty.SLAB_USBtoUART*`, depending on its USB-serial chip.

### Flashing MicroPython (only needed once per board, or on a blank board)

Download the matching firmware `.bin` from micropython.org and flash it.
**Use the right variant for each chip** — `ESP32_GENERIC_C3` for the robot,
plain `ESP32_GENERIC` for the controller — mixing them up gets rejected by
esptool with an "not an ESP32 image" error.

```bash
# Robot (XIAO ESP32-C3) — download from
# https://micropython.org/download/ESP32_GENERIC_C3/
esptool.py --chip esp32c3 --port /dev/tty.usbmodem1101 erase_flash
esptool.py --chip esp32c3 --port /dev/tty.usbmodem1101 write_flash -z 0x0 ESP32_GENERIC_C3-XXXXXXXX-v1.XX.X.bin

# Controller (ESP32-WROOM-32) — download from
# https://micropython.org/download/ESP32_GENERIC/
esptool.py --chip esp32 --port /dev/tty.usbserial-0001 erase_flash
esptool.py --chip esp32 --port /dev/tty.usbserial-0001 write_flash -z 0x1000 ESP32_GENERIC-XXXXXXXX-v1.XX.X.bin
```

### Copying the code (using mpremote)

```bash
cd "/Users/thejameswilliam/Documents/Mini Battlebots/minibattlebot"

# Robot
mpremote connect /dev/tty.usbmodem1101 cp robot/main.py :main.py
mpremote connect /dev/tty.usbmodem1101 cp robot/motors.py :motors.py
mpremote connect /dev/tty.usbmodem1101 cp -r glib/ :

# Controller — note the `sleep 2`: opening the serial port resets the board
# (DTR is wired to EN), and on this board's USB-serial adapter, mpremote's
# raw-REPL handshake can race the boot process and hang indefinitely without
# a short pause first to let the board finish rebooting.
mpremote connect /dev/tty.usbserial-0001 sleep 2 cp controller/main.py :main.py
mpremote connect /dev/tty.usbserial-0001 sleep 2 cp -r glib/ :
```

### Reset and watch it run

```bash
mpremote connect /dev/tty.usbmodem1101 reset
mpremote connect /dev/tty.usbmodem1101      # opens a REPL to see print() output; Ctrl-] to exit

mpremote connect /dev/tty.usbserial-0001 reset
mpremote connect /dev/tty.usbserial-0001    # opens a REPL to see print() output; Ctrl-] to exit
```

---

## Pairing a controller to a robot

Pairing is required once when you first set up a pair, and again any time
you swap a broken robot for a replacement.  No laptop or reflashing needed.

1. **Robot first:** power on the robot and press its BOOT button within
   3 seconds of boot.  The robot will print its MAC and start advertising.

2. **Controller second:** power on the controller and press its BOOT button
   within 3 seconds of boot.  The controller will scan for any advertising
   robot.

3. When found, both devices print a confirmation, save the pairing to their
   flash storage, and reboot.

4. On all future power-ons, both devices load the saved pairing and connect
   automatically — no BOOT button needed.

> GPIO9 (BOOT) is a boot-mode strapping pin on the ESP32-C3: holding it down
> *while power is applied* drops the chip into the ROM bootloader instead of
> running MicroPython at all. That's why pairing is triggered by a press
> shortly *after* boot, not by holding the button during power-on.

**To swap a broken robot:** power off the controller, power on the
replacement robot and press BOOT within 3 seconds, then power on the
controller and press BOOT within 3 seconds.  Done in about 10 seconds.

---

## Safety features

| Feature | What it does |
|---------|--------------|
| **Command timeout** | Robot stops motors within 200 ms of losing contact with the controller (out of range, turned off, crashed). |
| **Hardware watchdog** | Both devices automatically reboot if their main loop hangs for more than 5 seconds. |

---

## How it works

**Communication:** ESP-NOW is a connectionless Wi-Fi protocol by Espressif that
works without a router.  Range is 50–200 m line-of-sight.  Packets are small
(< 250 bytes) and low-latency (~1 ms).

**Steering:** The controller sends `{x, y}` values at 20 Hz. Since the
joystick is a 4-direction switch type, each of `x`/`y` is always -100, 0, or
100 — never in between. The robot uses tank-drive mixing to convert them
into per-motor speeds:
```
left_motor  = y + x
right_motor = y - x
```
Pushing the stick straight forward sets both motors to the same speed.
Pushing it left slows the left motor and speeds up the right, turning left.
Pushing a diagonal (e.g. forward + left) drives one motor at full speed and
the other at half, since the mixing still sums `x` and `y` even though each
is now only ever a full-scale value.

**Pairing:** Each device stores the other's Wi-Fi MAC address in a `config.json`
file on flash.  During pairing mode, the robot broadcasts its MAC over the
ESP-NOW broadcast address (FF:FF:FF:FF:FF:FF) until the controller responds
with its own MAC.  After the handshake both devices save the config and reboot.
