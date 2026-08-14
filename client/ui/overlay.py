"""
OpenCV HUD overlay module for visual feedback.
TRD §3.2: Render hand landmarks, bounding box, gesture label, confidence score, and connection status.
"""

from typing import Any, Tuple, Optional
import cv2

class OverlayDrawer:
    """Draws bounding box, hand landmarks, gesture labels, and connection status on video frame."""

    COLOR_GREEN = (0, 255, 0)
    COLOR_YELLOW = (0, 255, 255)
    COLOR_RED = (0, 0, 255)
    COLOR_WHITE = (255, 255, 255)
    COLOR_BLACK = (0, 0, 0)

    def draw(
        self,
        frame: cv2.Mat,
        landmarks: Optional[Any],
        gesture: str,
        confidence: float,
        connection_status: str,
        fps: float = 0.0,
        timings: Optional[dict] = None
    ) -> cv2.Mat:
        """
        Draw visual overlay on frame.

        :param frame: BGR image frame.
        :param landmarks: Hand landmarks object.
        :param gesture: Confirmed gesture label.
        :param confidence: Confidence score.
        :param connection_status: "Connected", "Retrying", or "Offline".
        :param fps: Measured vision loop frames per second.
        :return: Frame with rendered overlay.
        """
        h, w, _ = frame.shape

        # 1. Draw Bounding Box around hand if landmarks available
        if landmarks:
            pts_x = [lm.x * w for lm in (landmarks.landmark if hasattr(landmarks, 'landmark') else landmarks)]
            pts_y = [lm.y * h for lm in (landmarks.landmark if hasattr(landmarks, 'landmark') else landmarks)]

            xmin, xmax = int(min(pts_x)), int(max(pts_x))
            ymin, ymax = int(min(pts_y)), int(max(pts_y))

            # Add padding
            pad = 15
            xmin = max(0, xmin - pad)
            ymin = max(0, ymin - pad)
            xmax = min(w, xmax + pad)
            ymax = min(h, ymax + pad)

            # Draw rectangle
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), self.COLOR_GREEN, 2)

            # Label on bounding box
            label = f"{gesture.upper()} ({confidence*100:.0f}%)"
            cv2.putText(
                frame, label, (xmin, ymin - 10 if ymin - 10 > 10 else ymin + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_GREEN, 2
            )

        # 2. Draw Top Status HUD Bar
        cv2.rectangle(frame, (0, 0), (w, 40), self.COLOR_BLACK, -1)

        # Connection status color indicator
        if connection_status == "Connected":
            status_color = self.COLOR_GREEN
        elif connection_status == "Retrying":
            status_color = self.COLOR_YELLOW
        else:
            status_color = self.COLOR_RED

        cv2.circle(frame, (20, 20), 8, status_color, -1)
        cv2.putText(
            frame, f"Pi Server: {connection_status}", (35, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.COLOR_WHITE, 1
        )

        # Gesture info on top bar
        gesture_text = f"Gesture: {gesture.upper()}"
        cv2.putText(
            frame, gesture_text, (w // 2 - 60, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_YELLOW, 2
        )

        # FPS indicator
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(
            frame, fps_text, (w - 110, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.COLOR_WHITE, 1
        )

        # Optional timing diagnostics (capture, preprocess, mediapipe, gesture, network, display)
        if timings:
            x = 10
            y = h - 80
            line_h = 18
            for key, ms in timings.items():
                text = f"{key}: {ms:.1f} ms"
                cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_WHITE, 1)
                y += line_h

        return frame
