"""
Gesture debouncing and majority-vote rolling buffer.
TRD §3.2: Majority agreement over last N frames prevents jitter-triggered duplicate commands.
"""

from collections import Counter, deque
from typing import Tuple

class GestureSmoother:
    """Rolling window majority vote buffer for gesture stabilization."""

    def __init__(self, buffer_size: int = 5):
        self.buffer_size = max(1, buffer_size)
        self.buffer = deque(maxlen=self.buffer_size)
        self.last_confirmed = "stop"

    def add(self, gesture: str, confidence: float) -> Tuple[str, float]:
        """
        Add a frame's gesture prediction to the buffer and compute smoothed output.

        :param gesture: Raw gesture classification ("up", "down", "left", "right", "stop", "none").
        :param confidence: Confidence score.
        :return: Tuple of (smoothed_gesture, average_confidence).
        """
        self.buffer.append((gesture, confidence))

        if not self.buffer:
            return self.last_confirmed, 0.0

        # Tally gesture occurrences in buffer
        counts = Counter(item[0] for item in self.buffer)
        most_common_gesture, count = counts.most_common(1)[0]

        # Require majority vote (> 50% of buffer)
        majority_needed = (len(self.buffer) // 2) + 1
        if count >= majority_needed and most_common_gesture != "none":
            self.last_confirmed = most_common_gesture

        # Compute average confidence for the confirmed gesture
        relevant_confidences = [conf for gest, conf in self.buffer if gest == self.last_confirmed]
        avg_confidence = (
            sum(relevant_confidences) / len(relevant_confidences)
            if relevant_confidences
            else 0.0
        )

        return self.last_confirmed, round(avg_confidence, 2)

    def reset(self) -> None:
        """Clear buffer state."""
        self.buffer.clear()
        self.last_confirmed = "stop"
