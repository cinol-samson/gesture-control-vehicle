# Gesture-Controlled Vehicle — Architecture & Technical Design

## 1. Overview & Data Flow

The system implements real-time computer-vision remote control for a Raspberry Pi-driven vehicle via a laptop/PC vision client over HTTP.

```
+------------------+         +-------------------------------+         +---------------------+
|  Webcam Video    | ------> | MediaPipe Hand Tracking       | ------> | Gesture Classifier  |
|  (640x480)       |         | (21 Landmarks)                |         | (Geometric Rules)   |
+------------------+         +-------------------------------+         +---------------------+
                                                                                  |
                                                                                  v
+------------------+         +-------------------------------+         +---------------------+
| Vehicle Motion   | <------ | Motor Controller (RPi.GPIO)   | <------ | Majority-Vote       |
| (L298N H-Bridge) |         | & Watchdog Auto-Stop Thread   |         | Debounce Buffer     |
+------------------+         +-------------------------------+         +---------------------+
                                             ^                                    |
                                             |                                    v
                                     +-----------------------+         +---------------------+
                                     | Flask Command Server  | <------ | HTTP Command Client |
                                     | (Raspberry Pi)        |  POST   | (Throttled/Heartbeat)|
                                     +-----------------------+         +---------------------+
```

## 2. Performance & Latency Constraints (TRD §5.5)

- **Target Latency Budget**: End-to-end latency (from webcam gesture capture to motor response) is targeted under **~150–200ms** to provide crisp manual control.
- **Resolution**: Video frame capture defaults to **640x480** to maintain high MediaPipe inference throughput (>=15 FPS) on standard laptop hardware.
- **Throttling & Heartbeat**: HTTP POST commands are only transmitted when the confirmed gesture changes or when the heartbeat timer (default 1.0s) expires. Vision inference rate is decoupled from network transmission rate.

## 3. Configuration Management (TRD §6)

- Configuration defaults are provided via environment variables loading `.env` (using `.env.example` as reference template).
- **Format Flexibility**: While `.env` is the default approach, `config.yaml` is documented as an acceptable alternative format if preferred for deployment environments.

## 4. Security (TRD §5.6)

> [!WARNING]
> **LAN-Scoped Security Limitation**: By default, no authentication or TLS encryption is implemented for HTTP command endpoints. The system operates under the assumption of a trusted local area network (LAN).

### Security Architecture & Limitations
1. **Scope**: Intended exclusively for isolated or private Wi-Fi LAN operation.
2. **Known Risk**: Any device on the same local network could send arbitrary `POST /command` payloads to the Pi server.
3. **Recommended Upgrade**: If deployed outside a trusted LAN or over public networks:
   - Add a shared-secret HTTP header (e.g. `X-API-Key: <token>`) validated by Flask middleware.
   - Upgrade HTTP transport to HTTPS/TLS or encapsulate traffic within an encrypted VPN (e.g., WireGuard/Tailscale).
