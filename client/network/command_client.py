"""
HTTP command client for transmitting gesture movement commands to Raspberry Pi server.

TRD §5.2 Contract:
Request JSON:
{
    "gesture": "left",
    "confidence": 0.94,
    "timestamp": 1733900000.123
}
Response JSON (Success 200):
{
    "status": "ok",
    "applied": "left"
}
Response JSON (Error 400):
{
    "status": "error",
    "message": "unknown gesture 'xyz'"
}
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional
import requests

logger = logging.getLogger(__name__)


class CommandClient:
    """HTTP Client with state-change throttling, heartbeat, timeout, and retry logic."""

    def __init__(
        self,
        server_url: str,
        http_timeout: float = 0.8,
        heartbeat_interval: float = 1.0,
        max_retries: int = 3
    ):
        self.server_url = server_url
        self.http_timeout = max(0.5, min(1.0, http_timeout))  # 0.5-1.0s timeout per TRD §5.2
        self.heartbeat_interval = heartbeat_interval
        self.max_retries = max_retries

        self.session = requests.Session()
        self.last_sent_gesture: Optional[str] = None
        self.last_send_time: float = 0.0
        self.connection_status: str = "Connected"
        self.retry_count: int = 0

    def send_gesture(self, gesture: str, confidence: float, force: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Send gesture to Raspberry Pi server if state changed, heartbeat expired, or forced.

        :param gesture: Confirmed gesture label ("left", "right", "up", "down", "stop").
        :param confidence: Gesture confidence score.
        :param force: Force immediate transmission regardless of throttle state.
        :return: Tuple of (success_flag, status_message, response_json).
        """
        now = time.time()
        time_since_last = now - self.last_send_time

        # Check throttle criteria: state changed or heartbeat interval reached
        should_send = (
            force or
            (gesture != self.last_sent_gesture) or
            (time_since_last >= self.heartbeat_interval)
        )

        if not should_send:
            return True, self.connection_status, None

        payload = {
            "gesture": gesture,
            "confidence": round(float(confidence), 2),
            "timestamp": round(now, 3)
        }

        success, response_data, err_msg = self._post_with_retry(payload)

        if success:
            self.last_sent_gesture = gesture
            self.last_send_time = now
            self.connection_status = "Connected"
            self.retry_count = 0
            logger.info("Sent gesture '%s' successfully (applied: '%s')", gesture, response_data.get("applied"))
            return True, "Connected", response_data
        else:
            self.retry_count += 1
            if self.retry_count >= self.max_retries:
                self.connection_status = "Offline"
            else:
                self.connection_status = "Retrying"

            logger.warning("Failed to send gesture '%s': %s (status: %s)", gesture, err_msg, self.connection_status)
            return False, self.connection_status, response_data

    def send_stop(self) -> bool:
        """Fail-safe: Send immediate stop command to Pi."""
        logger.info("Executing fail-safe stop command...")
        success, _, _ = self.send_gesture(gesture="stop", confidence=1.0, force=True)
        return success

    def _post_with_retry(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Execute HTTP POST with exponential backoff retry for network resilience."""
        backoff = 0.1
        last_error = ""

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.server_url,
                    json=payload,
                    timeout=self.http_timeout
                )

                try:
                    data = response.json()
                except Exception:
                    data = {}

                if response.status_code == 200 and data.get("status") == "ok":
                    return True, data, ""

                # HTTP 400 error (e.g. unknown gesture) or server error
                msg = data.get("message", f"HTTP {response.status_code}")
                return False, data, f"Server rejected payload: {msg}"

            except (requests.Timeout, requests.ConnectionError, requests.RequestException) as e:
                last_error = str(e)
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff

        return False, None, last_error
