"""
Vision Client Entrypoint — Gesture-Controlled Vehicle.
TRD §3.2 & §5.5: Captures webcam video via threaded WebcamStream, runs MediaPipe tracking,
classifies gestures, applies majority-vote smoothing, transmits HTTP commands to Pi,
renders overlay, and handles local logging and fail-safe stop.
"""

import sys
import time
import logging
import cv2

from config import parse_args, TARGET_LATENCY_MS
from camera import WebcamStream
from gesture import HandTracker, GestureClassifier, GestureSmoother
from network import CommandClient
from ui import OverlayDrawer

import threading
from queue import Queue, Empty


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

    # Initialize vision & network components
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

    # Initialize threaded camera stream to eliminate buffer latency
    try:
        stream = WebcamStream(
            camera_index=config.camera_index,
            width=config.frame_width,
            height=config.frame_height
        ).start()
    except Exception as e:
        logger.error("Failed to initialize camera stream: %s", e)
        sys.exit(1)

    logger.info("Threaded camera stream active. Press 'q' or Esc to exit.")

    prev_frame_time = time.time()
    fps = 0.0

    try:
        PROCESS_EVERY_N = 2  # Only run expensive detector every Nth frame
        frame_counter = 0

        # Hold last results for display on skipped frames
        last_landmarks = None
        last_confirmed_gesture = "stop"
        last_smoothed_confidence = 0.0
        # Initial connection state: assume disconnected until a send updates status
        last_status_msg = "Disconnected"

        # Background network sender to decouple blocking HTTP calls
        send_queue: Queue = Queue()
        last_network_ms = 0.0

        def network_worker():
            nonlocal last_network_ms
            while True:
                try:
                    gesture, confidence = send_queue.get(timeout=0.5)
                except Empty:
                    continue
                t_net = time.perf_counter()
                try:
                    network_client.send_gesture(gesture=gesture, confidence=confidence)
                except Exception as e:
                    logging.getLogger("NetworkWorker").exception("Network send failed: %s", e)
                last_network_ms = (time.perf_counter() - t_net) * 1000.0
                send_queue.task_done()

        net_thread = threading.Thread(target=network_worker, daemon=True)
        net_thread.start()

        while not stream.stopped:
            # Read latest frame from threaded WebcamStream
            t0 = time.perf_counter()
            ret, frame = stream.read()
            capture_ms = (time.perf_counter() - t0) * 1000.0

            if not ret or frame is None:
                time.sleep(0.005)
                continue

            # Enforce configured resolution
            t1 = time.perf_counter()

            if frame.shape[1] != config.frame_width or frame.shape[0] != config.frame_height:
                frame = cv2.resize(
                    frame,
                    (config.frame_width, config.frame_height),
                    interpolation=cv2.INTER_LINEAR
                )

            # Mirror the frame BEFORE any vision processing
            frame = cv2.flip(frame, 1)

            preprocess_ms = (time.perf_counter() - t1) * 1000.0

            current_time = time.time()
            dt = current_time - prev_frame_time
            if dt > 0:
                fps = 1.0 / dt
            prev_frame_time = current_time

            # Only run the full detection + classification pipeline every N frames
            do_process = (frame_counter % PROCESS_EVERY_N) == 0

            mediapipe_ms = 0.0
            gesture_ms = 0.0
            network_ms = 0.0

            if do_process:
                # 1. Hand landmark detection (on the raw captured frame)
                t2 = time.perf_counter()
                timestamp_ms = int(time.monotonic() * 1000)
                landmarks = tracker.process(frame, timestamp_ms)
                mediapipe_ms = (time.perf_counter() - t2) * 1000.0
                last_landmarks = landmarks

                # 2. Classify gesture with confidence floor
                t3 = time.perf_counter()
                raw_gesture, confidence = classifier.classify(landmarks)
                gesture_time = time.perf_counter()

                # 3. Smooth gesture with majority vote buffer
                confirmed_gesture, smoothed_confidence = smoother.add(raw_gesture, confidence)
                gesture_ms = (time.perf_counter() - t3) * 1000.0

                # 4. Transmit command to Pi (throttled by state change / heartbeat)
                t4 = time.perf_counter()
                if confirmed_gesture in {"left", "right", "up", "down", "stop"}:
                    # Enqueue the command for sending by the background worker to avoid blocking
                    try:
                        send_queue.put_nowait((confirmed_gesture, smoothed_confidence))
                    except Exception:
                        # If queue is full or fails, fall back to synchronous send (rare)
                        try:
                            network_client.send_gesture(gesture=confirmed_gesture, confidence=smoothed_confidence)
                        except Exception:
                            pass
                    # Network status will be reflected by the CommandClient internally; read it for HUD
                    last_status_msg = network_client.connection_status
                else:
                    # No new confirmed gesture; keep previous connection status
                    last_status_msg = network_client.connection_status
                # Report last async network time measured by worker (may be from previous send)
                network_ms = last_network_ms

                last_confirmed_gesture = confirmed_gesture
                last_smoothed_confidence = smoothed_confidence

            else:
                # Skip heavy processing; reuse last known results for UI and throttled network
                landmarks = last_landmarks
                confirmed_gesture = last_confirmed_gesture
                smoothed_confidence = last_smoothed_confidence
                status_msg = last_status_msg

            # 5. Draw landmarks skeleton (use last_landmarks when skipped)
            t5 = time.perf_counter()
            if landmarks:
                tracker.draw_landmarks(frame, landmarks)
            draw_ms = (time.perf_counter() - t5) * 1000.0

            # 6. Render visual overlay (include timings for diagnostics)
            timings = {
                "Capture": capture_ms,
                "Preprocess": preprocess_ms,
                "MediaPipe": mediapipe_ms,
                "Gesture": gesture_ms,
                "Network": network_ms,
                "Draw": draw_ms
            }

            # Ensure status_msg is set for all execution paths
            status_msg = last_status_msg

            # 7. Display the already-mirrored frame
            t6 = time.perf_counter()
            frame_with_overlay = overlay.draw(
                frame=frame,
                landmarks=landmarks,
                gesture=confirmed_gesture,
                confidence=smoothed_confidence,
                connection_status=status_msg,
                fps=fps,
                timings=timings
            )

            cv2.imshow(
                "Gesture-Controlled Vehicle Client",
                frame_with_overlay
            )

            display_ms = (time.perf_counter() - t6) * 1000.0


  

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):
                logger.info("User requested exit.")
                break

            frame_counter += 1

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.exception("Unexpected error in main processing loop: %s", e)
    finally:
        logger.info("Shutting down client...")
        # Fail-safe stop command & resource cleanup
        try:
            network_client.send_stop()
        except Exception:
            pass
        stream.stop()
        cv2.destroyAllWindows()
        logger.info("Client shutdown complete.")


if __name__ == "__main__":
    main()
