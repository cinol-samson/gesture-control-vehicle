# API Specification — Command Server (TRD §5.2)

The Raspberry Pi Command Server exposes HTTP REST endpoints over port `5000` (configurable).

---

## Endpoint: `POST /command`

Transmits movement commands to the motor controller.

### Headers
- `Content-Type: application/json`

### Request Body (JSON)
```json
{
  "gesture": "left",
  "confidence": 0.94,
  "timestamp": 1733900000.123
}
```

#### Request Parameters
- `gesture` (string, required): Allowed gesture enum `["left", "right", "up", "down", "stop"]`.
- `confidence` (float, required): Gesture classification confidence score (0.0 to 1.0).
- `timestamp` (float, required): Unix timestamp of frame capture.

---

### Success Response (HTTP 200 OK)
Returned when payload is valid and gesture is recognized.
```json
{
  "status": "ok",
  "applied": "left"
}
```

---

### Error Response (HTTP 400 Bad Request)
Returned when `gesture` is missing, invalid, or not in the allowed enum `{left, right, up, down, stop}`.
```json
{
  "status": "error",
  "message": "unknown gesture 'xyz'"
}
```

---

## Endpoint: `GET /status`

Returns current health check and vehicle state.

### Response (HTTP 200 OK)
```json
{
  "status": "ok",
  "motor_state": "forward",
  "watchdog_timeout": 1.5
}
```
