"""
Rule-based hand gesture classifier using MediaPipe landmark geometry.
TRD §5.1 & User Requirement: Discards frames below confidence threshold, returning 'none'.
"""

import math
from typing import Tuple, Dict, Any, List

# Allowed Gesture Enums
VALID_GESTURES = {"left", "right", "up", "down", "stop"}

class LandmarkPoint:
    """Simple container for landmark coordinates (x, y, z)."""
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z

class GestureClassifier:
    """Classifies hand landmark configurations into vehicle movement commands."""

    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold

    def classify(self, landmarks: Any) -> Tuple[str, float]:
        """
        Classify hand pose landmarks.

        :param landmarks: MediaPipe NormalizedLandmarkList or list of landmark objects.
        :return: Tuple of (gesture_name, confidence_score)
        """
        if not landmarks:
            return "none", 0.0

        # Extract 21 points
        pts = self._extract_points(landmarks)
        if len(pts) < 21:
            return "none", 0.0

        raw_gesture, confidence = self._evaluate_geometry(pts)

        # Requirement: Discard frames below confidence threshold floor
        if confidence < self.confidence_threshold:
            return "none", round(confidence, 2)

        return raw_gesture, round(confidence, 2)

    def _extract_points(self, landmarks: Any) -> List[LandmarkPoint]:
        pts = []
        if hasattr(landmarks, 'landmark'):
            lm_list = landmarks.landmark
        else:
            lm_list = landmarks

        for lm in lm_list:
            x = getattr(lm, 'x', 0.0)
            y = getattr(lm, 'y', 0.0)
            z = getattr(lm, 'z', 0.0)
            pts.append(LandmarkPoint(x, y, z))
        return pts

    def _evaluate_geometry(self, pts: List[LandmarkPoint]) -> Tuple[str, float]:
        wrist = pts[0]
        middle_mcp = pts[9]

        # Finger tip vs PIP joint extension checks
        # Landmark indices: Tip / PIP
        # Index: 8 / 6
        # Middle: 12 / 10
        # Ring: 16 / 14
        # Pinky: 20 / 18
        # Thumb: 4 / 2

        # Compute distance to wrist for fingertips vs PIPs to be orientation-agnostic for curled detection
        def dist(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
            return math.hypot(p1.x - p2.x, p1.y - p2.y)

        index_ext = dist(pts[8], wrist) > dist(pts[6], wrist)
        middle_ext = dist(pts[12], wrist) > dist(pts[10], wrist)
        ring_ext = dist(pts[16], wrist) > dist(pts[14], wrist)
        pinky_ext = dist(pts[20], wrist) > dist(pts[18], wrist)
        thumb_ext = dist(pts[4], wrist) > dist(pts[2], wrist)

        extended_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])

        # 1. Closed Fist -> Stop Command
        if extended_count == 0:
            # High confidence if all fingers are clearly curled
            conf = 0.95 if not thumb_ext else 0.85
            return "stop", conf

        # 2. Hand vector direction (Wrist -> Middle MCP)
        dx = middle_mcp.x - wrist.x
        dy = middle_mcp.y - wrist.y  # In screen space, y increases downwards!
        angle_rad = math.atan2(-dy, dx)  # Convert to standard Cartesian (up is positive y)
        angle_deg = math.degrees(angle_rad) % 360

        # Calculate gesture direction from palm orientation angle
        # Up: 45 to 135 deg
        # Left: 135 to 225 deg
        # Down: 225 to 315 deg
        # Right: 315 to 45 deg (or >315 or <45)

        if extended_count >= 3:
            if 45 <= angle_deg < 135:
                # Upward pointing
                conf = 0.90 if extended_count == 4 else 0.75
                return "up", conf
            elif 135 <= angle_deg < 225:
                # Left pointing
                conf = 0.90 if extended_count == 4 else 0.75
                return "left", conf
            elif 225 <= angle_deg < 315:
                # Downward pointing
                conf = 0.90 if extended_count == 4 else 0.75
                return "down", conf
            else:
                # Right pointing (>315 or <45)
                conf = 0.90 if extended_count == 4 else 0.75
                return "right", conf

        # Low clarity gesture pose -> return "none" with low confidence
        return "none", 0.40
