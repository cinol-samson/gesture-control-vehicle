"""
Unit tests for GestureClassifier.
Tests geometry evaluation, direction classification, and confidence threshold filtering.
"""

import pytest
import sys
import os

# Ensure client directory is on python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gesture.classifier import GestureClassifier, LandmarkPoint

def create_mock_hand(finger_extension: str = "all", direction: str = "up"):
    """
    Helper to construct 21 mock LandmarkPoints.
    :param finger_extension: "all" for extended, "none" for fist/curled.
    :param direction: "up", "down", "left", "right".
    """
    wrist = LandmarkPoint(0.5, 0.5, 0.0)

    # Orientation vector for middle_mcp (index 9) relative to wrist
    if direction == "up":
        middle_mcp = LandmarkPoint(0.5, 0.3, 0.0)
    elif direction == "down":
        middle_mcp = LandmarkPoint(0.5, 0.7, 0.0)
    elif direction == "left":
        middle_mcp = LandmarkPoint(0.3, 0.5, 0.0)
    else:  # right
        middle_mcp = LandmarkPoint(0.7, 0.5, 0.0)

    landmarks = [wrist] + [LandmarkPoint(0.5, 0.5, 0.0)] * 20
    landmarks[9] = middle_mcp

    # Finger PIPs (6, 10, 14, 18) and Tips (8, 12, 16, 20)
    # If extended, tips are further from wrist than PIPs
    if finger_extension == "all":
        # Extend tips outward from wrist
        dx = middle_mcp.x - wrist.x
        dy = middle_mcp.y - wrist.y
        landmarks[6] = LandmarkPoint(wrist.x + dx * 0.5, wrist.y + dy * 0.5)
        landmarks[8] = LandmarkPoint(wrist.x + dx * 1.5, wrist.y + dy * 1.5)
        landmarks[10] = LandmarkPoint(wrist.x + dx * 0.5, wrist.y + dy * 0.5)
        landmarks[12] = LandmarkPoint(wrist.x + dx * 1.5, wrist.y + dy * 1.5)
        landmarks[14] = LandmarkPoint(wrist.x + dx * 0.5, wrist.y + dy * 0.5)
        landmarks[16] = LandmarkPoint(wrist.x + dx * 1.5, wrist.y + dy * 1.5)
        landmarks[18] = LandmarkPoint(wrist.x + dx * 0.5, wrist.y + dy * 0.5)
        landmarks[20] = LandmarkPoint(wrist.x + dx * 1.5, wrist.y + dy * 1.5)
        landmarks[2] = LandmarkPoint(0.5, 0.5)
        landmarks[4] = LandmarkPoint(0.5, 0.5)
    else:
        # Curled fist: tips closer to wrist than PIPs
        landmarks[6] = LandmarkPoint(0.5, 0.4)
        landmarks[8] = LandmarkPoint(0.5, 0.48)
        landmarks[10] = LandmarkPoint(0.5, 0.4)
        landmarks[12] = LandmarkPoint(0.5, 0.48)
        landmarks[14] = LandmarkPoint(0.5, 0.4)
        landmarks[16] = LandmarkPoint(0.5, 0.48)
        landmarks[18] = LandmarkPoint(0.5, 0.4)
        landmarks[20] = LandmarkPoint(0.5, 0.48)
        landmarks[2] = LandmarkPoint(0.5, 0.5)
        landmarks[4] = LandmarkPoint(0.5, 0.5)

    return landmarks

def test_classify_none_input():
    classifier = GestureClassifier()
    gesture, confidence = classifier.classify(None)
    assert gesture == "none"
    assert confidence == 0.0

def test_classify_stop_fist():
    classifier = GestureClassifier()
    landmarks = create_mock_hand(finger_extension="none")
    gesture, confidence = classifier.classify(landmarks)
    assert gesture == "stop"
    assert confidence >= 0.6

def test_classify_up_gesture():
    classifier = GestureClassifier()
    landmarks = create_mock_hand(finger_extension="all", direction="up")
    gesture, confidence = classifier.classify(landmarks)
    assert gesture == "up"
    assert confidence >= 0.6

def test_classify_down_gesture():
    classifier = GestureClassifier()
    landmarks = create_mock_hand(finger_extension="all", direction="down")
    gesture, confidence = classifier.classify(landmarks)
    assert gesture == "down"
    assert confidence >= 0.6

def test_classify_left_gesture():
    classifier = GestureClassifier()
    landmarks = create_mock_hand(finger_extension="all", direction="left")
    gesture, confidence = classifier.classify(landmarks)
    assert gesture == "left"
    assert confidence >= 0.6

def test_classify_right_gesture():
    classifier = GestureClassifier()
    landmarks = create_mock_hand(finger_extension="all", direction="right")
    gesture, confidence = classifier.classify(landmarks)
    assert gesture == "right"
    assert confidence >= 0.6

def test_confidence_threshold_filtering():
    # Strict classifier discarding anything below 0.95
    strict_classifier = GestureClassifier(confidence_threshold=0.98)
    landmarks = create_mock_hand(finger_extension="all", direction="up")
    gesture, confidence = strict_classifier.classify(landmarks)
    # Since confidence is ~0.90, strict_classifier discards it to "none"
    assert gesture == "none"
