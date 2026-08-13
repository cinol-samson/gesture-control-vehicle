"""
Dummy Motor Controller mock implementation for off-Pi testing.
TRD §5.4: Designed to be mockable so the Flask server can be tested on a non-Pi machine.
"""

import logging

logger = logging.getLogger(__name__)

class DummyMotorController:
    """Mock motor controller recording pin states for off-device testing."""

    def __init__(self, speed: int = 80):
        self.speed = speed
        self.current_state = "stop"
        logger.info("Initialized DummyMotorController (mock off-Pi mode) at speed=%d", speed)

    def forward(self) -> None:
        self.current_state = "forward"
        logger.info("[MOCK MOTOR] Moving FORWARD at speed=%d", self.speed)

    def backward(self) -> None:
        self.current_state = "backward"
        logger.info("[MOCK MOTOR] Moving BACKWARD at speed=%d", self.speed)

    def turn_left(self) -> None:
        self.current_state = "left"
        logger.info("[MOCK MOTOR] Turning LEFT at speed=%d", self.speed)

    def turn_right(self) -> None:
        self.current_state = "right"
        logger.info("[MOCK MOTOR] Turning RIGHT at speed=%d", self.speed)

    def stop(self) -> None:
        self.current_state = "stop"
        logger.info("[MOCK MOTOR] STOPPED all motors")

    def apply(self, gesture: str) -> None:
        """Map gesture name to motor direction function."""
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
        logger.info("[MOCK MOTOR] Cleaned up resources")
