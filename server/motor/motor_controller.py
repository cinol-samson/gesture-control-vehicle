"""
GPIO Motor Controller for L298N / TB6612FNG H-Bridge Motor Driver on Raspberry Pi.
TRD §5.4: Wraps RPi.GPIO calls behind forward(), backward(), turn_left(), turn_right(), stop().
"""

import logging
from typing import Union
from .dummy_controller import DummyMotorController

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_RPI_GPIO = True
except ImportError:
    HAS_RPI_GPIO = False


class MotorController:
    """Raspberry Pi GPIO Hardware Motor Controller for L298N driver board."""

    def __init__(
        self,
        pin_ena: int = 17,
        pin_in1: int = 27,
        pin_in2: int = 22,
        pin_enb: int = 18,
        pin_in3: int = 23,
        pin_in4: int = 24,
        pwm_frequency: int = 100,
        default_speed: int = 80
    ):
        self.pin_ena = pin_ena
        self.pin_in1 = pin_in1
        self.pin_in2 = pin_in2
        self.pin_enb = pin_enb
        self.pin_in3 = pin_in3
        self.pin_in4 = pin_in4
        self.speed = default_speed
        self.current_state = "stop"

        if HAS_RPI_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            pins = [self.pin_ena, self.pin_in1, self.pin_in2, self.pin_enb, self.pin_in3, self.pin_in4]
            for pin in pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

            self.pwm_a = GPIO.PWM(self.pin_ena, pwm_frequency)
            self.pwm_b = GPIO.PWM(self.pin_enb, pwm_frequency)
            self.pwm_a.start(self.speed)
            self.pwm_b.start(self.speed)
            logger.info("Initialized RPi.GPIO MotorController successfully.")
        else:
            logger.warning("RPi.GPIO not available. MotorController instance created without GPIO backend.")

    def forward(self) -> None:
        self.current_state = "forward"
        if HAS_RPI_GPIO:
            self.pwm_a.ChangeDutyCycle(self.speed)
            self.pwm_b.ChangeDutyCycle(self.speed)
            GPIO.output(self.pin_in1, GPIO.HIGH)
            GPIO.output(self.pin_in2, GPIO.LOW)
            GPIO.output(self.pin_in3, GPIO.HIGH)
            GPIO.output(self.pin_in4, GPIO.LOW)
        logger.info("Motor state: FORWARD")

    def backward(self) -> None:
        self.current_state = "backward"
        if HAS_RPI_GPIO:
            self.pwm_a.ChangeDutyCycle(self.speed)
            self.pwm_b.ChangeDutyCycle(self.speed)
            GPIO.output(self.pin_in1, GPIO.LOW)
            GPIO.output(self.pin_in2, GPIO.HIGH)
            GPIO.output(self.pin_in3, GPIO.LOW)
            GPIO.output(self.pin_in4, GPIO.HIGH)
        logger.info("Motor state: BACKWARD")

    def turn_left(self) -> None:
        self.current_state = "left"
        if HAS_RPI_GPIO:
            self.pwm_a.ChangeDutyCycle(self.speed)
            self.pwm_b.ChangeDutyCycle(self.speed)
            # Left motor reverse, right motor forward
            GPIO.output(self.pin_in1, GPIO.LOW)
            GPIO.output(self.pin_in2, GPIO.HIGH)
            GPIO.output(self.pin_in3, GPIO.HIGH)
            GPIO.output(self.pin_in4, GPIO.LOW)
        logger.info("Motor state: TURN LEFT")

    def turn_right(self) -> None:
        self.current_state = "right"
        if HAS_RPI_GPIO:
            self.pwm_a.ChangeDutyCycle(self.speed)
            self.pwm_b.ChangeDutyCycle(self.speed)
            # Left motor forward, right motor reverse
            GPIO.output(self.pin_in1, GPIO.HIGH)
            GPIO.output(self.pin_in2, GPIO.LOW)
            GPIO.output(self.pin_in3, GPIO.LOW)
            GPIO.output(self.pin_in4, GPIO.HIGH)
        logger.info("Motor state: TURN RIGHT")

    def stop(self) -> None:
        self.current_state = "stop"
        if HAS_RPI_GPIO:
            GPIO.output(self.pin_in1, GPIO.LOW)
            GPIO.output(self.pin_in2, GPIO.LOW)
            GPIO.output(self.pin_in3, GPIO.LOW)
            GPIO.output(self.pin_in4, GPIO.LOW)
            self.pwm_a.ChangeDutyCycle(0)
            self.pwm_b.ChangeDutyCycle(0)
        logger.info("Motor state: STOP")

    def apply(self, gesture: str) -> None:
        """Apply motor command mapped from gesture string."""
        mapping = {
            "up": self.forward,
            "down": self.backward,
            "left": self.turn_left,
            "right": self.turn_right,
            "stop": self.stop
        }
        action = mapping.get(gesture.lower(), self.stop)
        action()

    def cleanup(self) -> None:
        self.stop()
        if HAS_RPI_GPIO:
            self.pwm_a.stop()
            self.pwm_b.stop()
            GPIO.cleanup()
        logger.info("Motor controller hardware cleanup finished.")


def get_motor_controller(force_dummy: bool = False, **kwargs) -> Union[MotorController, DummyMotorController]:
    """Factory function: Returns real MotorController on Pi, or DummyMotorController on non-Pi."""
    if force_dummy or not HAS_RPI_GPIO:
        logger.info("Using DummyMotorController fallback.")
        return DummyMotorController(speed=kwargs.get("default_speed", 80))
    return MotorController(**kwargs)
