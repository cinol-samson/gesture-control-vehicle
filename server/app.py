"""
Flask Command Server running on Raspberry Pi.

TRD §5.2 & §5.3:
Endpoints:
  POST /command - Movement commands with strict enum validation & watchdog update.
  GET /status   - Server health check & motor state status.
"""

import os
import sys
import logging
from flask import Flask, request, jsonify
from config import ServerConfig
from motor import get_motor_controller
from watchdog import WatchdogThread

# Configure standard logging (TRD §3.2)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CommandServer")

ALLOWED_GESTURES = {"left", "right", "up", "down", "stop"}

def create_app(config: ServerConfig = None, motor_controller = None) -> Flask:
    app = Flask(__name__)
    if config is None:
        config = ServerConfig()

    app.config["SERVER_CONFIG"] = config

    # Initialize motor controller
    if motor_controller is None:
        motor_controller = get_motor_controller(
            force_dummy=config.use_dummy_motor,
            default_speed=config.default_speed
        )
    app.config["MOTOR_CONTROLLER"] = motor_controller

    # Initialize watchdog thread
    watchdog = WatchdogThread(
        motor_controller=motor_controller,
        timeout_seconds=config.watchdog_timeout
    )
    watchdog.start()
    app.config["WATCHDOG"] = watchdog

    @app.route("/command", methods=["POST"])
    def handle_command():
        """
        Handle movement commands.
        Request JSON: { "gesture": "left", "confidence": 0.94, "timestamp": 1733900000.123 }
        """
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            logger.warning("Invalid or missing JSON payload received.")
            return jsonify({
                "status": "error",
                "message": "invalid JSON body"
            }), 400

        gesture = data.get("gesture")
        if not gesture or not isinstance(gesture, str):
            logger.warning("Missing or non-string 'gesture' field.")
            return jsonify({
                "status": "error",
                "message": "missing or invalid 'gesture' field"
            }), 400

        gesture_lower = gesture.lower()

        # Enforce allowed gesture enum validation (TRD §5.2)
        if gesture_lower not in ALLOWED_GESTURES:
            logger.warning("Rejected unknown gesture '%s'", gesture)
            return jsonify({
                "status": "error",
                "message": f"unknown gesture '{gesture}'"
            }), 400

        # Valid gesture -> refresh watchdog timer & apply motor action
        watchdog.update_last_command_time()
        motor_controller.apply(gesture_lower)

        logger.info("Successfully applied gesture command '%s' (confidence: %s)", gesture_lower, data.get("confidence"))
        return jsonify({
            "status": "ok",
            "applied": gesture_lower
        }), 200

    @app.route("/status", methods=["GET"])
    def handle_status():
        """Health check route returning motor state and watchdog status."""
        current_state = getattr(motor_controller, "current_state", "unknown")
        return jsonify({
            "status": "ok",
            "motor_state": current_state,
            "watchdog_timeout": config.watchdog_timeout
        }), 200

    return app

if __name__ == "__main__":
    cfg = ServerConfig()
    app = create_app(config=cfg)
    logger.info("Starting Command Server on %s:%d ...", cfg.host, cfg.port)
    app.run(host=cfg.host, port=cfg.port, debug=False)
