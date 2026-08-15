"""
Threaded webcam capture stream module.
Decouples camera frame capture from MediaPipe processing loop to eliminate video lag.

Windows note: URL-based sources (e.g. DroidCam HTTP stream) are probed first,
bypassing the virtual camera driver entirely and avoiding MSMF green-frame bugs.
For physical cameras, falls back to index-based scanning with MSMF then DSHOW.
"""

import threading
import time
import logging
from typing import Tuple, Optional
import cv2

logger = logging.getLogger(__name__)

# Seconds to allow the camera driver to warm up before reads start.
_WARMUP_SECONDS = 0.5

# How long (seconds) wait_for_frame() will poll before giving up.
_FIRST_FRAME_TIMEOUT = 10.0

# Maximum camera index to scan when auto-detecting.
_MAX_SCAN_INDEX = 2

# URL-based sources probed before index scanning.
# DroidCam (USB or WiFi) serves an HTTP MJPEG stream that OpenCV opens directly,
# bypassing the virtual camera driver and its MSMF pixel-format green-frame bug.
_URL_SOURCES: list[tuple[str, str]] = [
    ("DroidCam-USB",  "http://localhost:4747/mjpegfeed"),
    ("DroidCam-USB2", "http://localhost:4747/video"),
]

# Backends for physical/index-based camera scanning.
# MSMF is the Windows default; DSHOW is kept as a fallback.
_BACKENDS: list[tuple[str, int]] = [
    ("MSMF", cv2.CAP_MSMF),
    ("DSHOW", cv2.CAP_DSHOW),
]


def _open_camera(camera_index: int, width: int, height: int) -> cv2.VideoCapture:
    """
    Open a camera source, preferring URL-based streams then index-based scanning.

    Strategy:
    1. Probe each URL in _URL_SOURCES (e.g. DroidCam HTTP stream).  This bypasses
       the virtual camera driver entirely, avoiding MSMF green-frame artefacts.
    2. If all URLs fail, scan device indices 0-_MAX_SCAN_INDEX with each backend.

    Raises RuntimeError if no usable camera is found.
    """
    def _try_url(source_name: str, url: str) -> Optional[cv2.VideoCapture]:
        """Try to open *url* as a video stream. Returns cap on success, None on failure."""
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            cap.release()
            return None
        time.sleep(0.5)
        grabbed, frame = cap.read()
        if grabbed and frame is not None and frame.size > 0:
            logger.info("Camera opened via HTTP stream (%s): %s", source_name, url)
            return cap
        cap.release()
        return None

    def _try_index(idx: int, backend_name: str, backend_id: int) -> Optional[cv2.VideoCapture]:
        """Try to open camera at numeric *idx* with the given backend."""
        cap = cv2.VideoCapture(idx, backend_id)
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        time.sleep(1.0)
        grabbed, frame = cap.read()
        if grabbed and frame is not None:
            return cap
        cap.release()
        return None

    # --- Step 1: try URL-based sources (virtual cameras, DroidCam, IP webcams) ---
    for source_name, url in _URL_SOURCES:
        cap = _try_url(source_name, url)
        if cap is not None:
            return cap
        logger.debug("URL source unavailable (%s): %s", source_name, url)

    # --- Step 2: fall back to physical device index scanning ---
    indices_to_try = [camera_index] + [
        i for i in range(_MAX_SCAN_INDEX + 1) if i != camera_index
    ]

    for backend_name, backend_id in _BACKENDS:
        for idx in indices_to_try:
            cap = _try_index(idx, backend_name, backend_id)
            if cap is not None:
                logger.info("Camera opened at index %d (%s).", idx, backend_name)
                return cap
        logger.warning(
            "No working camera found with %s backend. Trying next backend...",
            backend_name,
        )

    tried_backends = [name for name, _ in _BACKENDS]
    raise RuntimeError(
        f"Failed to open webcam at index {camera_index} with any available backend "
        f"({tried_backends}). Ensure a camera is connected and not in use by another application."
    )


class WebcamStream:
    """
    Background thread continuously reading frames from OpenCV VideoCapture.
    Flushes internal frame buffers so the main processing loop always receives
    the instantaneous latest frame with zero camera input latency.
    """

    # Number of consecutive failed reads before treating camera as disconnected.
    MAX_CONSECUTIVE_FAILURES = 15

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        self.camera_index = camera_index
        self.width = width
        self.height = height

        # _open_camera probes each backend and returns the first one that delivers
        # a real frame, raising RuntimeError if none work.
        self.cap = _open_camera(camera_index, width, height)

        # Don't read in __init__ — let the camera driver warm up first.
        self.grabbed = False
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._update, daemon=True, name="WebcamCaptureThread")

    def start(self) -> "WebcamStream":
        """Start the background frame capture thread."""
        self.stopped = False
        self.thread.start()
        logger.info("WebcamStream capture thread started (Index: %d, %dx%d, warmup: %.1fs).",
                    self.camera_index, self.width, self.height, _WARMUP_SECONDS)
        logger.debug("Camera warmup set to %.1f seconds for MSMF driver initialisation.", _WARMUP_SECONDS)
        return self

    def wait_for_frame(self, timeout: float = _FIRST_FRAME_TIMEOUT) -> bool:
        """
        Block until the background thread delivers the first real frame, or
        *timeout* seconds elapse. Call this after :meth:`start` so the rest
        of the application does not process empty frames.

        :param timeout: Maximum seconds to wait (default ``_FIRST_FRAME_TIMEOUT``).
        :return: ``True`` if a frame arrived in time, ``False`` on timeout.
        """
        logger.debug("Waiting for first frame (timeout: %.1fs)...", timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                if self.grabbed and self.frame is not None:
                    logger.info("First frame received from camera index %d.", self.camera_index)
                    return True
            if self.stopped:
                logger.warning("Camera stream stopped before first frame was received.")
                return False
            time.sleep(0.05)  # poll every 50 ms
        logger.warning(
            "wait_for_frame() timed out after %.1fs — no frame received from camera index %d.",
            timeout, self.camera_index,
        )
        return False

    def _update(self) -> None:
        """Continuously grab the latest frame in a background loop."""
        # Give the camera driver time to warm up before the first read.
        time.sleep(_WARMUP_SECONDS)

        consecutive_failures = 0

        while not self.stopped:
            grabbed, frame = self.cap.read()

            if not grabbed or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "Camera stream failed %d consecutive reads. Stopping capture thread.",
                        consecutive_failures
                    )
                    self.stopped = True
                    break
                logger.debug("Transient read failure (%d/%d). Retrying...",
                             consecutive_failures, self.MAX_CONSECUTIVE_FAILURES)
                time.sleep(0.02)
                continue

            consecutive_failures = 0  # reset on success
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame

    def read(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """
        Return the most recently grabbed frame.
        :return: Tuple of (success_flag, latest_bgr_frame).
        """
        with self.lock:
            if not self.grabbed or self.frame is None:
                return False, None
            return True, self.frame.copy()

    def stop(self) -> None:
        """Stop background capture thread and release OpenCV camera resources."""
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.cap.isOpened():
            self.cap.release()
        logger.info("WebcamStream camera resources released.")
