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
        # Reduce internal capture buffering to minimize latency buildup
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            # Not all backends support CAP_PROP_BUFFERSIZE; ignore failures
            pass

        # Create a background frame grabber to avoid processing stale buffered frames
        class FrameGrabber(threading.Thread):
            def __init__(self, capture: cv2.VideoCapture):
                super().__init__(daemon=True)
                self.capture = capture
                self.lock = threading.Lock()
                self.latest_frame = None
                self.running = True

            def run(self):
                while self.running:
                    ret, frame = self.capture.read()
                    if not ret:
                        # small sleep to avoid tight looping on error
                        time.sleep(0.01)
                        continue
                    with self.lock:
                        self.latest_frame = frame

            def read(self):
                with self.lock:
                    return self.latest_frame

            def stop(self):
                self.running = False

        grabber = FrameGrabber(cap)
        grabber.start()

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
        network_lock = threading.Lock()
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

        while True:
            # Measure capture time by reading latest frame from grabber
            t0 = time.perf_counter()
            frame = grabber.read()
            capture_ms = (time.perf_counter() - t0) * 1000.0

            if frame is None:
                # No frame available yet from grabber
                time.sleep(0.005)
                continue

            # Enforce configured resolution (some cameras ignore CAP_PROP settings)
            t1 = time.perf_counter()
            if frame.shape[1] != config.frame_width or frame.shape[0] != config.frame_height:
                frame = cv2.resize(frame, (config.frame_width, config.frame_height), interpolation=cv2.INTER_LINEAR)
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

            frame_with_overlay = overlay.draw(
                frame=frame,
                landmarks=landmarks,
                gesture=confirmed_gesture,
                confidence=smoothed_confidence,
                connection_status=status_msg,
                fps=fps,
                timings=timings
            )

            # 7. Mirror display for intuitive webcam preview but keep processing on original orientation
            t6 = time.perf_counter()
            display_frame = cv2.flip(frame_with_overlay, 1)
            cv2.imshow("Gesture-Controlled Vehicle Client", display_frame)
            display_ms = (time.perf_counter() - t6) * 1000.0

            # Update timing shown for draw/display
            timings["Display"] = display_ms

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
        # Fail-safe stop command
        try:
            network_client.send_stop()
        except Exception:
            pass
        # Stop background grabber
        try:
            grabber.stop()
            grabber.join(timeout=1.0)
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()
        logger.info("Client shutdown complete.")


if __name__ == "__main__":
    main()
