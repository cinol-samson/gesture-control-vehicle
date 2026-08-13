"""
Vision Client Entrypoint — Gesture-Controlled Vehicle.
TRD §3.2 & §5.5: Captures webcam video, runs MediaPipe tracking, classifies gestures,
applies majority-vote smoothing, transmits HTTP commands to Pi, renders overlay,
and handles local logging and fail-safe stop.
"""

import sys
import time
import logging
import cv2

from config import parse_args, TARGET_LATENCY_MS
from gesture import HandTracker, GestureClassifier, GestureSmoother
from network import CommandClient
from ui import OverlayDrawer


def setup_logging(log_file: str):
    """Configure standard logging for console and optional file output (TRD §3.2)."""
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers
    )


def main():
    config = parse_args()
    setup_logging(config.log_file)

    logger = logging.getLogger("VisionClient")
    logger.info("Initializing Vision Client...")
    logger.info("Server Target: %s", config.server_url)
    logger.info("Target Latency Budget: %d ms", TARGET_LATENCY_MS)
    logger.info("Resolution: %dx%d", config.frame_width, config.frame_height)

    # Initialize components
    tracker = HandTracker(
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    classifier = GestureClassifier(confidence_threshold=config.confidence_threshold)
    smoother = GestureSmoother(buffer_size=config.buffer_size)
    network_client = CommandClient(
        server_url=config.server_url,
        http_timeout=config.http_timeout,
        heartbeat_interval=config.heartbeat_interval
    )
    overlay = OverlayDrawer()

    cap = cv2.VideoCapture(config.camera_index)
    if not cap.isOpened():
        logger.error("Failed to open webcam at index %d", config.camera_index)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.frame_height)

    logger.info("Camera capture loop started. Press 'q' or Esc to exit.")

    prev_frame_time = time.time()
    fps = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("Failed to capture frame from camera or stream ended.")
                break

            current_time = time.time()
            dt = current_time - prev_frame_time
            if dt > 0:
                fps = 1.0 / dt
            prev_frame_time = current_time

            # 1. Hand landmark detection
            landmarks = tracker.process(frame)

            # 2. Draw landmarks skeleton
            if landmarks:
                tracker.draw_landmarks(frame, landmarks)

            # 3. Classify gesture with confidence floor
            raw_gesture, confidence = classifier.classify(landmarks)

            # 4. Smooth gesture with majority vote buffer
            confirmed_gesture, smoothed_confidence = smoother.add(raw_gesture, confidence)

            # 5. Transmit command to Pi (throttled by state change / heartbeat)
            if confirmed_gesture in {"left", "right", "up", "down", "stop"}:
                success, status_msg, _ = network_client.send_gesture(
                    gesture=confirmed_gesture,
                    confidence=smoothed_confidence
                )
            else:
                status_msg = network_client.connection_status

            # 6. Render visual overlay
            frame = overlay.draw(
                frame=frame,
                landmarks=landmarks,
                gesture=confirmed_gesture,
                confidence=smoothed_confidence,
                connection_status=status_msg,
                fps=fps
            )

            cv2.imshow("Gesture-Controlled Vehicle Client", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):
                logger.info("User requested exit.")
                break

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.exception("Unexpected error in main processing loop: %s", e)
    finally:
        logger.info("Shutting down client...")
        # Fail-safe stop command
        network_client.send_stop()
        cap.release()
        cv2.destroyAllWindows()
        logger.info("Client shutdown complete.")


if __name__ == "__main__":
    main()
