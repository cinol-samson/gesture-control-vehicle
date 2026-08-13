# Raspberry Pi to L298N Motor Driver Wiring Diagram (TRD §5.4)

## Hardware Connections

```
Raspberry Pi (BCM Pinout)           L298N Motor Driver Board
+-----------------------+           +----------------------+
| GPIO 17 (Pin 11)      | --------> | ENA (Enable Motor A) |
| GPIO 27 (Pin 13)      | --------> | IN1 (Motor A Dir 1)  |
| GPIO 22 (Pin 15)      | --------> | IN2 (Motor A Dir 2)  |
|                       |           |                      |
| GPIO 18 (Pin 12)      | --------> | ENB (Enable Motor B) |
| GPIO 23 (Pin 16)      | --------> | IN3 (Motor B Dir 1)  |
| GPIO 24 (Pin 18)      | --------> | IN4 (Motor B Dir 2)  |
|                       |           |                      |
| GND (Pin 6/9/14/20)   | --------> | GND (Common Ground)  |
+-----------------------+           +----------------------+

Power Supply:
- Battery (+7V to +12V) -> L298N +12V & GND
- L298N 5V Out (if jumper enabled) -> Raspberry Pi 5V Pin (or separate Pi USB power)
- Motor A (Left Wheels) -> OUT1 & OUT2
- Motor B (Right Wheels) -> OUT3 & OUT4
```

## Motor Logic Matrix

| Command | IN1 | IN2 | IN3 | IN4 | ENA / ENB PWM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `forward` (`up`) | HIGH | LOW | HIGH | LOW | Speed % |
| `backward` (`down`) | LOW | HIGH | LOW | HIGH | Speed % |
| `turn_left` (`left`) | LOW | HIGH | HIGH | LOW | Speed % |
| `turn_right` (`right`) | HIGH | LOW | LOW | HIGH | Speed % |
| `stop` (`stop`) | LOW | LOW | LOW | LOW | 0% |
