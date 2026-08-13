"""
Watchdog background thread for vehicle fail-safe auto-stop.
TRD §5.3: Monitors time since last valid command was received.
If time.time() - last_command_time > threshold (e.g. 1.5s), forces motor_controller.stop().
"""

import time
import threading
import logging
from typing import Any

logger = logging.getLogger(__name__)

class WatchdogThread(threading.Thread):
    """Background thread enforcing auto-stop on silent/dropped connection."""

    def __init__(self, motor_controller: Any, timeout_seconds: float = 1.5, check_interval: float = 0.2):
        super().__init__(daemon=True, name="WatchdogThread")
        self.motor_controller = motor_controller
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self.last_command_time = time.time()
        self.running = True
        self._stopped_by_watchdog = False

    def update_last_command_time(self) -> None:
        """Call on every valid incoming HTTP request to refresh watchdog timer."""
        self.last_command_time = time.time()
        self._stopped_by_watchdog = False

    def run(self) -> None:
        logger.info("Watchdog thread started with timeout=%.2fs", self.timeout_seconds)
        while self.running:
            time.sleep(self.check_interval)
            elapsed = time.time() - self.last_command_time

            if elapsed > self.timeout_seconds and not self._stopped_by_watchdog:
                # Watchdog trigger! Force auto-stop
                logger.warning(
                    "WATCHDOG TRIGGERED! Silence threshold exceeded (%.2fs > %.2fs). Auto-stopping motors.",
                    elapsed, self.timeout_seconds
                )
                try:
                    self.motor_controller.stop()
                except Exception as e:
                    logger.error("Error during watchdog auto-stop: %s", e)
                self._stopped_by_watchdog = True

    def stop(self) -> None:
        self.running = False
