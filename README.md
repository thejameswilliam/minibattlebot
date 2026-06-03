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

Both boards are **Seeed XIAO ESP32-C3**.

### Controller
| Component | XIAO pin | GPIO |
|-----------|----------|------|
| Joystick X axis | D0 / A0 | GPIO2 |
| Joystick Y axis | D1 / A1 | GPIO3 |
| Pair LED (220Ω to GND) | D7 | GPIO20 |
| Power LED (220Ω to GND) | 3V3 pin | — hardwired, no GPIO |
| BOOT button (built-in) | D9 | GPIO9 |

### Robot
| Component | XIAO pin | GPIO |
|-----------|----------|------|
| Motor A IN1 | D0 | GPIO2 |
| Motor A IN2 | D1 | GPIO3 |
| Motor A PWM | D2 | GPIO4 |
| Motor B IN1 | D3 | GPIO5 |
| Motor B IN2 | D4 | GPIO6 |
| Motor B PWM | D5 | GPIO7 |
| Pair LED (220Ω to GND) | D7 | GPIO20 |
| Power LED (220Ω to GND) | 3V3 pin | — hardwired, no GPIO |
| BOOT button (built-in) | D9 | GPIO9 |

Pin assignments are constants at the top of each `main.py` — edit them there if your wiring differs.

### LED wiring

Both boards use the same two-LED setup:

```
Power LED:  3V3 pin ──[220Ω]──[LED anode → cathode]── GND
Pair LED:   GPIO20  ──[220Ω]──[LED anode → cathode]── GND
```

The power LED is always on whenever the board has power — no code involved.
The pair LED is software-controlled (see LED behavior below).

**LED behavior:**

| State | Pair LED |
|-------|----------|
| Pairing mode (searching) | Blinking |
| Paired and connected | Solid on |
| Robot lost signal (>200 ms) | Off |

> **Note on ADC:** GPIO2 and GPIO3 are both ADC1 channels, which remain accurate
> while ESP-NOW / Wi-Fi is active.  Do not use GPIO5 (D3/A3) for ADC — it shares
> ADC2 with the Wi-Fi radio and gives unreliable readings when wireless is on.

---

## Deploying

### Using mpremote

```bash
# Controller
mpremote connect /dev/tty.SLAB_USBtoUART cp controller/main.py :main.py
mpremote connect /dev/tty.SLAB_USBtoUART cp -r glib/ :glib/

# Robot
mpremote connect /dev/tty.SLAB_USBtoUART2 cp robot/main.py :main.py
mpremote connect /dev/tty.SLAB_USBtoUART2 cp robot/motors.py :motors.py
mpremote connect /dev/tty.SLAB_USBtoUART2 cp -r glib/ :glib/
```

### Find your serial port

```bash
ls /dev/tty.*
```

---

## Pairing a controller to a robot

Pairing is required once when you first set up a pair, and again any time
you swap a broken robot for a replacement.  No laptop or reflashing needed.

1. **Robot first:** hold the BOOT button on the robot while powering it on.
   The robot will print its MAC and start advertising.

2. **Controller second:** hold the BOOT button on the controller while
   powering it on.  The controller will scan for any advertising robot.

3. When found, both devices print a confirmation, save the pairing to their
   flash storage, and reboot.  The BOOT button does not need to be held any
   longer after the initial power-on.

4. On all future power-ons, both devices load the saved pairing and connect
   automatically — no BOOT button needed.

**To swap a broken robot:** power off the controller, put the replacement
robot in pairing mode (BOOT at power-on), then put the controller in pairing
mode (BOOT at power-on).  Done in about 10 seconds.

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

**Steering:** The controller sends `{x, y}` values (-100 to 100) at 20 Hz.
The robot uses tank-drive mixing to convert them into per-motor speeds:
```
left_motor  = y + x
right_motor = y - x
```
Pushing the stick straight forward sets both motors to the same speed.
Pushing it left slows the left motor and speeds up the right, turning left.

**Pairing:** Each device stores the other's Wi-Fi MAC address in a `config.json`
file on flash.  During pairing mode, the robot broadcasts its MAC over the
ESP-NOW broadcast address (FF:FF:FF:FF:FF:FF) until the controller responds
with its own MAC.  After the handshake both devices save the config and reboot.
