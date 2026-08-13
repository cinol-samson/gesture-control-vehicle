# Gesture-Controlled Vehicle System

Computer-vision-based remote control system for a Raspberry Pi-driven vehicle. A host machine (laptop/desktop) runs an OpenCV application that captures live webcam video, recognizes hand gestures via MediaPipe, and transmits movement commands to the vehicle over HTTP. The Raspberry Pi runs a Flask web server driving an L298N motor controller board with automatic watchdog auto-stop protection.

---

## Repository Structure

```
gesture-vehicle-control/
├── README.md
├── LICENSE
├── requirements-client.txt
├── requirements-server.txt
├── .env.example
│
├── client/                      # Runs on laptop/PC
│   ├── main.py                  # Entry point: capture loop, orchestration
│   ├── config.py                # Server IP/port, thresholds, camera index
│   ├── gesture/
│   │   ├── __init__.py
│   │   ├── hand_tracker.py      # MediaPipe wrapper
│   │   ├── classifier.py        # Landmark -> gesture label rules
│   │   └── smoothing.py         # Debounce / majority-vote buffer
│   ├── network/
│   │   ├── __init__.py
│   │   └── command_client.py    # HTTP POST wrapper, retry/backoff
│   ├── ui/
│   │   ├── __init__.py
│   │   └── overlay.py           # Draw landmarks, labels, connection status
│   └── tests/
│       ├── test_classifier.py
│       └── test_smoothing.py
│
├── server/                      # Runs on Raspberry Pi
│   ├── app.py                   # Flask app, /command and /status routes
│   ├── config.py                # GPIO pin map, watchdog timeout
│   ├── motor/
│   │   ├── __init__.py
│   │   ├── motor_controller.py  # forward/backward/left/right/stop
│   │   └── dummy_controller.py  # Mock for off-Pi testing
│   ├── watchdog.py              # Background thread, auto-stop on silence
│   └── tests/
│       └── test_app.py
│
├── docs/
│   ├── architecture.md
│   ├── api-spec.md
│   └── wiring-diagram.md
│
└── scripts/
    ├── run_client.sh
    └── run_server.sh
```

---

## Setup & Quickstart

### 1. Client (Laptop / PC)
```bash
cd client
pip install -r ../requirements-client.txt
python main.py --server-ip 192.168.1.42 --port 5000
```

### 2. Server (Raspberry Pi)
```bash
cd server
pip install -r ../requirements-server.txt
python app.py
```

---

## Configuration

Configuration is managed via environment variables and `.env` (using `.env.example` as reference template). Per TRD §6, `config.yaml` is also an acceptable alternative format if preferred for your environment.

### Key Settings
- `PI_SERVER_IP`: IP address of the Raspberry Pi.
- `PI_SERVER_PORT`: HTTP server port (default `5000`).
- `CAMERA_INDEX`: Webcam index (default `0`).
- `FRAME_WIDTH` / `FRAME_HEIGHT`: Camera resolution (default `640x480`).
- `CONFIDENCE_THRESHOLD`: Gesture confidence floor (default `0.6`).
- `WATCHDOG_TIMEOUT`: Silent threshold in seconds before auto-stop triggers (default `1.5`s).

---

## Testing

Run unit tests across client and server modules using `pytest`:

```bash
# Run all tests
pytest client/tests server/tests

# Run client tests only
pytest client/tests

# Run server tests only
pytest server/tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
