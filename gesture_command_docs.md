# Gesture Control Documentation

This document explains the lifecycle of a gesture control command: how hand movements are detected, classified into text commands, and transmitted over the network to the Raspberry Pi server.

## 1. Gesture Classification
Gestures are evaluated in [`client/gesture/classifier.py`](file:///c:/Users/ezeki/OneDrive/Desktop/new/gesture-control-vehicle/client/gesture/classifier.py) using 21 3D landmarks provided by MediaPipe.

The classification is rule-based and uses geometry:
- **Finger Extension Check:** The system compares the distance from the fingertip to the wrist against the distance from the PIP joint to the wrist. If the tip is further away, the finger is considered "extended".
- **"Stop" Command:** If no fingers are extended (a closed fist), the classifier outputs `stop`.
- **Directional Commands:** If 3 or more fingers are extended, the system calculates the angle from the wrist to the middle finger MCP joint to determine hand orientation:
  - **45° to 135°:** `up`
  - **135° to 225°:** `left`
  - **225° to 315°:** `down`
  - **>315° or <45°:** `right`
- If the hand configuration doesn't match these clear patterns or falls below the confidence threshold, it evaluates to `none`.

> [!NOTE]
> The raw gesture strings are: `left`, `right`, `up`, `down`, `stop`, and `none`.

## 2. Smoothing and Processing
In [`client/main.py`](file:///c:/Users/ezeki/OneDrive/Desktop/new/gesture-control-vehicle/client/main.py), raw gestures pass through a `GestureSmoother`. This applies a majority-vote filter over a rolling buffer of recent frames to prevent jitter and accidental commands.

Once a gesture is confirmed and is one of the valid control commands (`{"left", "right", "up", "down", "stop"}`), it is placed into an asynchronous queue (`send_queue`) to avoid blocking the main video processing loop.

## 3. Network Transmission
A background thread consumes from the queue and uses the `CommandClient` in [`client/network/command_client.py`](file:///c:/Users/ezeki/OneDrive/Desktop/new/gesture-control-vehicle/client/network/command_client.py) to dispatch the command.

### Throttling Logic
To avoid flooding the server, the `CommandClient` only transmits a HTTP POST request when:
1. The gesture has **changed** since the last sent gesture.
2. OR the **heartbeat interval** (default 1.0s) has expired (to let the server know the client is still connected and holding the command).
3. OR the `force` flag is true (used for emergency fail-safe stops).

### HTTP Payload
When triggered, a JSON payload is sent via `POST` to the Raspberry Pi server. The payload conforms to the following contract:

```json
{
    "gesture": "left",
    "confidence": 0.94,
    "timestamp": 1733900000.123
}
```

### Reliability
If the server doesn't respond or returns an error, the `CommandClient` implements an exponential backoff retry mechanism (up to `max_retries`). If all retries fail, the UI connection status updates to "Offline" or "Retrying".
