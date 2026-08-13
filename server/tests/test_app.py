"""
Unit tests for Flask Command Server endpoints, gesture validation, and watchdog fail-safe.
"""

import time
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import ServerConfig
from motor import DummyMotorController
from app import create_app

@pytest.fixture
def client():
    config = ServerConfig()
    config.watchdog_timeout = 0.5  # Short timeout for testing
    dummy_motor = DummyMotorController()
    app = create_app(config=config, motor_controller=dummy_motor)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client, dummy_motor, app.config["WATCHDOG"]
    app.config["WATCHDOG"].stop()

def test_status_endpoint(client):
    test_client, dummy_motor, watchdog = client
    response = test_client.get("/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "motor_state" in data

def test_valid_gesture_commands(client):
    test_client, dummy_motor, watchdog = client
    valid_gestures = ["left", "right", "up", "down", "stop"]

    for gesture in valid_gestures:
        payload = {
            "gesture": gesture,
            "confidence": 0.95,
            "timestamp": time.time()
        }
        response = test_client.post("/command", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["applied"] == gesture

def test_invalid_gesture_returns_http_400(client):
    test_client, dummy_motor, watchdog = client
    payload = {
        "gesture": "xyz",
        "confidence": 0.90,
        "timestamp": time.time()
    }
    response = test_client.post("/command", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert data["message"] == "unknown gesture 'xyz'"

def test_watchdog_auto_stop(client):
    test_client, dummy_motor, watchdog = client

    # Apply forward movement
    response = test_client.post("/command", json={"gesture": "up", "confidence": 0.9, "timestamp": time.time()})
    assert response.status_code == 200
    assert dummy_motor.current_state == "forward"

    # Wait longer than watchdog_timeout (0.5s)
    time.sleep(0.7)

    # Watchdog should have auto-stopped the motor
    assert dummy_motor.current_state == "stop"
