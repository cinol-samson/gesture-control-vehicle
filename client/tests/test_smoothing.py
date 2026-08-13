"""
Unit tests for GestureSmoother (rolling buffer majority vote).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gesture.smoothing import GestureSmoother

def test_smoother_majority_vote():
    smoother = GestureSmoother(buffer_size=5)

    # Add 3 'left' and 2 'up' -> majority is 'left'
    smoother.add("left", 0.9)
    smoother.add("left", 0.9)
    smoother.add("up", 0.8)
    smoother.add("left", 0.95)
    gesture, avg_conf = smoother.add("up", 0.85)

    assert gesture == "left"
    assert avg_conf > 0.0

def test_smoother_prevents_single_frame_jitter():
    smoother = GestureSmoother(buffer_size=5)

    # Establish stable 'up' state
    for _ in range(5):
        smoother.add("up", 0.9)

    # Single jitter frame of 'right'
    gesture, _ = smoother.add("right", 0.95)

    # Output remains 'up' because 'up' retains majority (4/5 frames)
    assert gesture == "up"

def test_smoother_reset():
    smoother = GestureSmoother(buffer_size=5)
    smoother.add("right", 0.9)
    smoother.reset()
    assert len(smoother.buffer) == 0
    assert smoother.last_confirmed == "stop"
