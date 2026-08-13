"""
Server Configuration & GPIO Pin Specifications.
TRD §5.3 & §5.4: Defines pin assignments, watchdog timeouts, and server host settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class ServerConfig:
    def __init__(self):
        self.host = os.getenv("SERVER_HOST", "0.0.0.0")
        self.port = int(os.getenv("SERVER_PORT", "5000"))
        self.watchdog_timeout = float(os.getenv("WATCHDOG_TIMEOUT", "1.5"))

        # L298N Motor Driver Pins
        self.pin_ena = int(os.getenv("PIN_ENA", "17"))
        self.pin_in1 = int(os.getenv("PIN_IN1", "27"))
        self.pin_in2 = int(os.getenv("PIN_IN2", "22"))

        self.pin_enb = int(os.getenv("PIN_ENB", "18"))
        self.pin_in3 = int(os.getenv("PIN_IN3", "23"))
        self.pin_in4 = int(os.getenv("PIN_IN4", "24"))

        self.pwm_frequency = int(os.getenv("PWM_FREQUENCY", "100"))
        self.default_speed = int(os.getenv("DEFAULT_SPEED", "80"))
        self.use_dummy_motor = os.getenv("USE_DUMMY_MOTOR", "false").lower() == "true"
