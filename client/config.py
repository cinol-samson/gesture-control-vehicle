"""
Client Configuration & Settings.

TRD §5.5 Design Constraints:
- Target end-to-end latency budget: ~150-200ms from gesture pose recognition to motor actuation.
- Camera capture resolution: 640x480 default to optimize MediaPipe landmark inference frame rates.
- HTTP commands are issued on gesture state changes or heartbeat intervals to decouple vision framerate from network call rate.
"""

import os
import argparse
from dotenv import load_dotenv

# Load optional .env file
load_dotenv()

# Performance & Latency Constraints
TARGET_LATENCY_MS = 180  # Target latency budget window (~150-200ms)
DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480

class ClientConfig:
    def __init__(self):
        self.server_ip = os.getenv("PI_SERVER_IP", "127.0.0.1")
        self.server_port = int(os.getenv("PI_SERVER_PORT", "5000"))
        self.camera_index = int(os.getenv("CAMERA_INDEX", "0"))
        self.frame_width = int(os.getenv("FRAME_WIDTH", str(DEFAULT_FRAME_WIDTH)))
        self.frame_height = int(os.getenv("FRAME_HEIGHT", str(DEFAULT_FRAME_HEIGHT)))
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
        self.buffer_size = int(os.getenv("BUFFER_SIZE", "5"))
        self.heartbeat_interval = float(os.getenv("HEARTBEAT_INTERVAL", "1.0"))
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "0.8"))
        self.log_file = os.getenv("LOG_FILE", "client.log")

    @property
    def server_url(self) -> str:
        return f"http://{self.server_ip}:{self.server_port}/command"

    @property
    def status_url(self) -> str:
        return f"http://{self.server_ip}:{self.server_port}/status"

def parse_args() -> ClientConfig:
    """Parse command line arguments and override environment variables."""
    config = ClientConfig()
    parser = argparse.ArgumentParser(description="Gesture Control Vehicle Vision Client")
    parser.add_argument("--server-ip", type=str, default=config.server_ip, help="Raspberry Pi Server IP address")
    parser.add_argument("--port", type=int, default=config.server_port, help="Raspberry Pi Server Port")
    parser.add_argument("--camera-index", type=int, default=config.camera_index, help="Webcam device index")
    parser.add_argument("--width", type=int, default=config.frame_width, help="Camera frame width")
    parser.add_argument("--height", type=int, default=config.frame_height, help="Camera frame height")
    parser.add_argument("--confidence", type=float, default=config.confidence_threshold, help="Gesture confidence threshold floor")
    parser.add_argument("--buffer-size", type=int, default=config.buffer_size, help="Smoothing buffer size")
    parser.add_argument("--heartbeat", type=float, default=config.heartbeat_interval, help="Heartbeat interval in seconds")
    parser.add_argument("--timeout", type=float, default=config.http_timeout, help="HTTP request timeout (0.5-1.0s)")

    args = parser.parse_args()
    config.server_ip = args.server_ip
    config.server_port = args.port
    config.camera_index = args.camera_index
    config.frame_width = args.width
    config.frame_height = args.height
    config.confidence_threshold = args.confidence
    config.buffer_size = args.buffer_size
    config.heartbeat_interval = args.heartbeat
    config.http_timeout = args.timeout

    return config
