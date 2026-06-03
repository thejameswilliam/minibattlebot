"""
Two-motor differential drive for a battle bot.

Expects an H-bridge driver (e.g. DRV8833, L298N) wired to the ESP32:

    Motor A: IN1=GPIO17, IN2=GPIO16, PWM=GPIO15
    Motor B: IN1=GPIO19, IN2=GPIO18, PWM=GPIO13

If your wiring differs, change the pin numbers in robot/main.py — the
constants are defined there, not here, so you only edit one place.
"""

from machine import Pin, PWM


class Motor:
    """Controls a single brushed DC motor through an H-bridge driver."""

    # MicroPython PWM duty cycle range
    MAX_DUTY = 1023

    def __init__(self, pin_in1, pin_in2, pin_pwm, freq=1000):
        """
        pin_in1, pin_in2 — direction control pins (connected to H-bridge IN1/IN2)
        pin_pwm          — PWM speed pin (connected to H-bridge EN/PWM)
        freq             — PWM frequency in Hz (1000 Hz is a safe default)
        """
        self._in1 = Pin(pin_in1, Pin.OUT)
        self._in2 = Pin(pin_in2, Pin.OUT)
        self._pwm = PWM(Pin(pin_pwm), freq=freq)
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
            self._in1.value(1)
            self._in2.value(0)
        elif speed < 0:
            self._in1.value(0)
            self._in2.value(1)
        else:
            self._in1.value(0)
            self._in2.value(0)

        self._pwm.duty(duty)

    def stop(self):
        """Stop the motor immediately (coast to zero)."""
        self._in1.value(0)
        self._in2.value(0)
        self._pwm.duty(0)
