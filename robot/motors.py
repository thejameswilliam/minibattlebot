"""
Two-motor differential drive for a battle bot.

Expects a 4-pin IN/IN H-bridge driver (e.g. TC1508S, DRV8833, TB6612) wired
to the ESP32 — no separate PWM/EN pin, speed is controlled by PWMing
whichever IN pin is active:

    Motor A: IN1=GPIO2, IN2=GPIO3
    Motor B: IN1=GPIO5, IN2=GPIO6

If your wiring differs, change the pin numbers in robot/main.py — the
constants are defined there, not here, so you only edit one place.
"""

from machine import Pin, PWM


class Motor:
    """Controls a single brushed DC motor through a 4-pin IN/IN H-bridge driver."""

    # MicroPython PWM duty cycle range
    MAX_DUTY = 1023

    def __init__(self, pin_in1, pin_in2, freq=1000):
        """
        pin_in1, pin_in2 — direction + speed pins (connected to H-bridge IN1/IN2).
                            Each is PWMed directly; there is no separate EN/PWM pin.
        freq              — PWM frequency in Hz (1000 Hz is a safe default)
        """
        self._in1 = PWM(Pin(pin_in1), freq=freq)
        self._in2 = PWM(Pin(pin_in2), freq=freq)
        self.stop()

    def setSpeed(self, speed):
        """
        Set motor direction and speed.

        speed: -100 to 100
            positive = forward
            negative = reverse
            0        = stopped (coasting)
        """
        speed = max(-100, min(100, speed))
        duty = int(abs(speed) / 100 * self.MAX_DUTY)

        if speed > 0:
            self._in1.duty(duty)
            self._in2.duty(0)
        elif speed < 0:
            self._in1.duty(0)
            self._in2.duty(duty)
        else:
            self._in1.duty(0)
            self._in2.duty(0)

    def stop(self):
        """Stop the motor immediately (coast to zero)."""
        self._in1.duty(0)
        self._in2.duty(0)
