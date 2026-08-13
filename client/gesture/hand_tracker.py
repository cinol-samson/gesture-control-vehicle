"""
MediaPipe Tasks HandLandmarker wrapper using hand_landmarker.task.
Replaces legacy mp.solutions.hands and mp.solutions.drawing_utils.
"""

import os
import urllib.request
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    cv2 = None

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    HAS_MEDIAPIPE_TASKS = True
except ImportError:
    HAS_MEDIAPIPE_TASKS = False
    mp = None
    python = None
    vision = None

# Hand landmark connection index pairs for OpenCV custom drawing
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index finger
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle finger
    (9, 10), (10, 11), (11, 12),
    # Ring finger
    (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm connects
    (5, 9), (9, 13), (13, 17)
]

MODEL_FILENAME = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def get_model_path() -> str:
    """Return local path to hand_landmarker.task model, downloading if necessary."""
    dir_path = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(dir_path, MODEL_FILENAME)
    if not os.path.exists(model_path):
        logger.info("Downloading %s to %s ...", MODEL_FILENAME, model_path)
        urllib.request.urlretrieve(MODEL_URL, model_path)
    return model_path


class HandTracker:
    """Hand landmark detector using MediaPipe Tasks HandLandmarker API."""

    def __init__(self, max_num_hands: int = 1, min_detection_confidence: float = 0.5, min_tracking_confidence: float = 0.5):
        self.enabled = HAS_MEDIAPIPE_TASKS
        self.detector = None

        if self.enabled:
            try:
                model_path = get_model_path()
                base_options = python.BaseOptions(model_asset_path=model_path)
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_hands=max_num_hands,
                    min_hand_detection_confidence=min_detection_confidence,
                    min_hand_presence_confidence=min_tracking_confidence
                )
                self.detector = vision.HandLandmarker.create_from_options(options)
                logger.info("Initialized HandLandmarker from %s", model_path)
            except Exception as e:
                logger.error("Failed to initialize MediaPipe HandLandmarker: %s", e)
                self.enabled = False

    def process(self, frame: cv2.Mat) -> Optional[List[Any]]:
        """
        Process a BGR image frame and return normalized hand landmarks.

        :param frame: BGR image frame from OpenCV.
        :return: List of landmark objects for the primary hand, or None.
        """
        if not self.enabled or self.detector is None or frame is None:
            return None

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = self.detector.detect(mp_image)

            if result and result.hand_landmarks and len(result.hand_landmarks) > 0:
                return result.hand_landmarks[0]
        except Exception as e:
            logger.error("Error during landmark detection: %s", e)

        return None

    def draw_landmarks(self, frame: cv2.Mat, landmarks: Any) -> None:
        """
        Draw hand skeleton and joint connections directly using OpenCV.
        Replaces legacy mp.solutions.drawing_utils.
        """
        if not HAS_OPENCV or frame is None or not landmarks:
            return

        h, w, _ = frame.shape
        lm_list = landmarks.landmark if hasattr(landmarks, 'landmark') else landmarks

        points = []
        for lm in lm_list:
            px = int(lm.x * w)
            py = int(lm.y * h)
            points.append((px, py))

        # Draw skeleton lines
        for start_idx, end_idx in HAND_CONNECTIONS:
            if start_idx < len(points) and end_idx < len(points):
                cv2.line(frame, points[start_idx], points[end_idx], (0, 255, 0), 2)

        # Draw joint keypoints
        for px, py in points:
            cv2.circle(frame, (px, py), 4, (0, 0, 255), -1)
