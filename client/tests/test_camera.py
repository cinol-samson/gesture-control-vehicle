"""
Unit tests for threaded WebcamStream module.
"""

import pytest
import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from camera import WebcamStream

def test_webcam_stream_initialization_failure():
    # Mock OpenCV VideoCapture to simulate failed camera index
    with mock.patch("cv2.VideoCapture") as mock_cap:
        instance = mock_cap.return_value
        instance.isOpened.return_value = False

        with pytest.raises(RuntimeError, match="Failed to open webcam"):
            WebcamStream(camera_index=99)
