# Cat Feeder - AI Instructions

## Project Overview
Smart cat feeder web app running on a **Raspberry Pi**. Flask backend controls a stepper motor via GPIO to dispense food. Web UI accessible from any device on the local network.

## Tech Stack
- **Backend:** Python 3 + Flask (`app.py`)
- **Motor control:** `motor.py` (StepperMotor class, GPIO via lgpio)
- **Presence sensor:** `presence.py` (MH-SR602 PIR sensor, GPIO via lgpio)
- **Load cell:** `scale.py` (HX711 24-bit ADC, bit-banged directly over lgpio, powered from 3.3V)
- **Frontend:** HTML + CSS + vanilla JS (`templates/`, `static/`)
- **Pi service:** systemd unit at `/etc/systemd/system/cat-feeder.service`

## Project Structure
```
cat-feeder/
├── app.py              # Flask routes & entry point (port 5000)
├── motor.py            # StepperMotor class (lgpio)
├── presence.py         # PresenceSensor class (MH-SR602 PIR, lgpio)
├── system.py           # System stats (CPU, RAM, temp, uptime from /proc)
├── scheduler.py        # Feeding schedule (background thread, JSON storage)
├── camera.py           # OV5647 camera capture (rpicam-still), PhotoTrigger
├── scale.py            # HX711 driver over lgpio (tare, calibration, scale.json)
├── config.py           # Configuration (pins: MOTOR_PINS, MOTOR2_PINS, PIR_PIN, HX711 pins)
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Web UI
├── static/
│   ├── style.css       # Dark glassmorphism theme
│   └── script.js       # API calls + status display
├── helper/
│   ├── deploy.ps1      # Push code to Pi (PowerShell)
│   └── retrieve.ps1    # Pull code from Pi (PowerShell)
├── credentials.txt     # Pi username/password (gitignored)
└── INSTRUCTIONS.md     # This file
```

## API Endpoints
| Method | Route           | Body              | Response                                      |
|--------|-----------------|-------------------|-----------------------------------------------|
| GET    | `/`             | —                 | HTML page (6 tabs: Feeder, Presence, System, Schedule, Photos, Weight) |
| POST   | `/motor/open`   | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/close`  | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/rotate` | `{"rotation": N}` | `{"status":"ok","rotation":N}`                |
| POST   | `/motor2/open`  | —                 | `{"status":"ok"}`                             |
| POST   | `/motor2/close` | —                 | `{"status":"ok"}`                             |
| POST   | `/motor2/rotate`| `{"rotation": N}` | `{"status":"ok","rotation":N}`                |
| GET    | `/presence`     | —                 | `{"current":bool,"samples":[0,1,0,...]}`      |
| GET    | `/status`       | —                 | `{"cpu_percent":N,"ram":{...},"temperature_c":N,"uptime":"...","time":"HH:MM:SS"}` |
| GET    | `/schedule`     | —                 | `[{id,time,rotation},...]`                    |
| POST   | `/schedule`     | `{"time":"08:00","rotation":50}` | `{id,time,rotation}`               |
| DELETE | `/schedule/<id>`| —                 | `{"status":"ok"}`                             |
| GET    | `/photos`       | —                 | `[{name,url},...]`                            |
| GET    | `/photos/<name>`| —                 | Serves JPEG file                              |
| DELETE | `/photos/<name>`| —                 | `{"status":"ok"}`                             |
| GET    | `/weight`       | —                 | `{"available":bool,"calibrated":bool,"grams":N,"stable":bool,"raw":N,"offset":N,"scale":N,"samples":[...]}` |
| POST   | `/weight/tare`  | —                 | `{"status":"ok","offset":N}`                  |
| POST   | `/weight/calibrate` | `{"grams": N}` | scale state, or `{"status":"error","error":"..."}` |
| POST   | `/weight/reset` | —                 | `{"status":"ok"}` (power-cycles the chip)      |

Open = 512 steps, Close = -512 steps.
Motor 1 dispensing pins = BCM [17,18,27,22] (physical 11,12,13,15). Motor 2 = BCM [5,6,13,19] (physical 29,31,33,35, at the far right edge of the header).
Presence samples = rolling last 120 seconds (1 sample/sec). Motion triggers camera (60s cooldown).
Status = live CPU/RAM/temp/uptime/time from /proc (100ms sample for CPU).
Schedule = stored in `schedules.json`, background thread checks every 5s and fires motor at matching HH:MM.
Photos = stored in `Photos/` directory, captured by OV5647 via rpicam-still when PIR detects motion.
Weight = HX711 on BCM 24 (DT) / 25 (SCK), sampled ~10Hz by a background thread. grams = (raw - offset) / scale. Tare offset and calibration factor persist in `scale.json`.
Weight workflow = tare with the bowl empty, then place a known mass and calibrate; `calibrated:false` means no factor yet.

## HX711 troubleshooting
`scale.py` surfaces the problem through `GET /weight`: `error` carries a human-readable reason and `raw` is reported in decimal and hex. The Weight tab shows both. The sensor is opened at startup, so restart the service after changing hardware. Without the web UI:

```bash
curl -s localhost:5000/weight
```

Raw values and what they mean:
- `0x000000` (0), `0xFFFFFF` (-1), `0x7FFFFF` (8388607), `0x800000` (-8388608) = no valid conversion. `scale.py` rejects all four and surfaces an error instead of showing them as a weight.
- **`-1` in particular = all 24 bits read `1`**, which is what you get when the frame aborts mid-shift: the SCK high phase ran past 60µs, the chip powered down, DOUT went high and every remaining bit read 1.
- Probable causes, in order: SCK high phase too long (see `pulse_us`), DT not connected / wrong pin (floating input), DT and SCK swapped, module unpowered, load cell disconnected.
- Two distinct `error` strings, do not conflate them: `clock pulse too slow (N us)` = DOUT *was* ready but the measured SCK high phase hit ≥60µs, so the frame is discarded — a GPIO-speed / CPU-scheduling problem, not wiring. `no data from HX711 (DOUT stayed high)` = DOUT never went low at all — power or wiring.

**Timing note:** PD_SCK high must stay between 0.2µs and 50µs; holding it high >60µs puts the chip into power-down and aborts the frame (that is what produces the all-ones `-1`). `scale.py` measures the slowest pulse of every frame and reports it as `pulse_us` in `/weight`. A healthy frame on this Pi is a few µs. Never add a `time.sleep()` between the two `gpio_write` calls.

**Why not the `hx711` library** (measured on this Pi, Python 3.13): the PyPI `hx711` package needs `RPi.GPIO`, and the pure-Python `rpi-lgpio` shim took **~128µs per clock pair** (`GPIO.output` ≈64µs/call), so every frame aborted with `raw = -1`. `lgpio` is a C extension already used by the motors and is fast enough, so `scale.py` bit-bangs with it directly — no third-party driver, no extra GPIO stack.

## Raspberry Pi Connection
- **Hostname:** `RaspberryThiago`
- **User:** `thiago` (read from `credentials.txt`)
- **Project path:** `/home/thiago/cat-feeder`
- **Python venv:** `/home/thiago/cat-feeder/.venv/bin/python`

## Deploy & Retrieve (from Windows, PowerShell)
```powershell
# Push local code → Pi, restart service, install deps
.\helper\deploy.ps1

# Pull Pi code → local (overwrites)
.\helper\retrieve.ps1

# Custom Pi address
.\helper\deploy.ps1 -PiHost "192.168.1.50"
```

Both scripts exclude `helper/`, `.git`, `.venv`, `__pycache__`, `Photos`, `credentials*`, `*.pyc`, `schedules.json`, `INSTRUCTIONS.md` from sync.

**No extra dependency for the scale.** `requirements.txt` is just `Flask` + `lgpio`; the HX711 is clocked with `lgpio` directly, the same C extension the motors use. If an older deployment still has the `hx711` package or `rpi-lgpio` installed, they are unused and can be removed: `.venv/bin/pip uninstall -y hx711 rpi-lgpio`. Any stale `/home/thiago/cat-feeder/hx711.py` on the Pi is also unused now and safe to delete.

## Pi Service Management
```bash
sudo systemctl status cat-feeder
sudo systemctl restart cat-feeder
sudo systemctl stop cat-feeder
sudo journalctl -u cat-feeder -f   # Follow logs
```

## Conventions
- No comments in code unless essential
- Follow existing patterns when adding routes/features
- `deploy.ps1` handles service restart automatically
- Pi runs Flask on all interfaces (`host="::"`) port 5000
- MH-SR602 PIR sensor wired to GPIO pin 23 (configurable in `config.py` → `PIR_PIN`)
- HX711 is powered from **3.3V**, never 5V: its DT/SCK levels follow VCC and would exceed the Pi's non-5V-tolerant GPIO. Pins in `config.py` → `HX711_DT_PIN`, `HX711_SCK_PIN`
- The HX711 is clocked directly over `lgpio` with **no sleep between the PD_SCK high and low edges** (high phase must stay <60µs). Never add a `time.sleep()` there. Keep two `gpio_write` calls back-to-back.
- `scale.py` is the only place that reads the scale; `grams = (raw - offset) / scale` with `scale.json` as the calibration store. `/weight` reports `pulse_us` (measured SCK high phase) for timing diagnosis.
- Second stepper motor (`MOTOR2_PINS`) controlled via `/motor2/*` endpoints and the Motor 1/2 toggle on the Feeder tab
