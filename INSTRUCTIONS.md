# Cat Feeder - AI Instructions

## Project Overview
Smart cat feeder web app running on a **Raspberry Pi**. Flask backend controls a stepper motor via GPIO to dispense food. Web UI accessible from any device on the local network.

## Tech Stack
- **Backend:** Python 3 + Flask (`app.py`)
- **Motor control:** `motor.py` (StepperMotor class, GPIO via lgpio)
- **Presence sensor:** `presence.py` (MH-SR602 PIR sensor, GPIO via lgpio)
- **Load cell:** `scale.py` (HX711 24-bit ADC, bit-banged directly over lgpio, powered from 3.3V)
- **Weight history:** `weightlog.py` (background sampler: every 10 min, every 10 s while presence is detected)
- **Feeding logic:** `auto_feeder.py` (weight-driven refill of motor 1 — replaces the old time scheduler)
- **Frontend:** HTML + CSS + vanilla JS (`templates/`, `static/`)
- **Pi service:** systemd unit at `/etc/systemd/system/cat-feeder.service`

## Project Structure
```
cat-feeder/
├── app.py              # Flask routes & entry point (port 5000)
├── motor.py            # StepperMotor class (lgpio)
├── presence.py         # PresenceSensor class (MH-SR602 PIR, lgpio)
├── system.py           # System stats (CPU, RAM, temp, uptime from /proc)
├── camera.py           # OV5647 camera capture (rpicam-still), PhotoTrigger
├── scale.py            # HX711 driver over lgpio + multi-point calibration (scale.json)
├── weightlog.py        # Periodic weight samples -> weight_log.jsonl (10min / 10s with presence)
├── auto_feeder.py      # Weight-driven motor 1 refill controller (feeding.json, feed_log.jsonl)
├── config.py           # Configuration (pins: MOTOR_PINS, MOTOR2_PINS, PIR_PIN, HX711 pins)
├── requirements.txt    # Python dependencies
├── templates/
│   ├── index.html      # Web UI (6 tabs)
│   └── configure.html  # Scale calibration page (/configure)
├── static/
│   ├── style.css       # Dark glassmorphism theme
│   ├── script.js       # API calls + status display
│   └── configure.js    # Calibration table, capture, raw-vs-weight graph
├── helper/
│   ├── deploy.ps1      # Push code to Pi (PowerShell)
│   └── retrieve.ps1    # Pull code from Pi (PowerShell)
├── credentials.txt     # Pi username/password (gitignored)
└── INSTRUCTIONS.md     # This file
```

## API Endpoints
| Method | Route           | Body              | Response                                      |
|--------|-----------------|-------------------|-----------------------------------------------|
| GET    | `/`             | —                 | HTML page (6 tabs: Feeder, Presence, System, Auto, Photos, Weight) |
| POST   | `/motor/open`   | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/close`  | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/rotate` | `{"rotation": N}` | `{"status":"ok","rotation":N}`                |
| POST   | `/motor2/open`  | —                 | `{"status":"ok"}`                             |
| POST   | `/motor2/close` | —                 | `{"status":"ok"}`                             |
| POST   | `/motor2/rotate`| `{"rotation": N}` | `{"status":"ok","rotation":N}`                |
| GET    | `/presence`     | —                 | `{"current":bool,"samples":[0,1,0,...]}`      |
| GET    | `/status`       | —                 | `{"cpu_percent":N,"ram":{...},"temperature_c":N,"uptime":"...","time":"HH:MM:SS"}` |
| GET    | `/auto`         | —                 | `{"enabled":bool,"state":str,"message":str,"weight":N,"filtered_g":N,"low_g":N,"target_g":N,"grams_per_step":N,"low_for_s":N,"dwell_left_s":N,"cooldown_left_s":N,"last_reset":{t,reason},"last_refill":{...},"events":[...],"config":{...}}` |
| POST   | `/auto`         | `{"enabled":b,"low_g":N,"target_g":N,...}` | updated state, or 400 |
| POST   | `/auto/dose`    | —                 | `{"status":"ok"}` (request one refill now)     |
| POST   | `/auto/stop`    | —                 | `{"status":"ok"}` (abort the refill in flight) |
| GET    | `/photos`       | —                 | `[{name,url},...]`                            |
| GET    | `/photos/<name>`| —                 | Serves JPEG file                              |
| DELETE | `/photos/<name>`| —                 | `{"status":"ok"}`                             |
| GET    | `/weight`       | —                 | `{"available":bool,"calibrated":bool,"grams":N/null,"stable":bool,"raw":N,"raw_hex":"0x..","pulse_us":N,"points":[{"grams":N,"raw":N},...],"warning":str/null,"error":str|null}` |
| POST   | `/weight/tare`  | —                 | `{"status":"ok","raw":N}` (records the 0 g point)  |
| POST   | `/weight/capture` | —               | `{"raw":N,"grams":N/null}` (median of 16 frames)   |
| POST   | `/calibration`  | `{"points":[{"grams":0,"raw":N},...]}` | scale state, or `{"status":"error","error":"..."}` |
| POST   | `/weight/reset` | —                 | `{"status":"ok"}` (power-cycles the chip)      |
| GET    | `/weight/history` | —               | `{"samples":[{"t":epoch,"g":N},...],"count":N,"idle_interval":600,"presence_interval":10,"presence":bool}` |
| DELETE | `/weight/history` | —               | `{"status":"ok"}` (clears the log)             |
| GET    | `/configure`    | —                 | HTML calibration page (separate from the tab UI) |

Open = 512 steps, Close = -512 steps.
Motor 1 dispensing pins = BCM [17,18,27,22] (physical 11,12,13,15). Motor 2 = BCM [5,6,13,19] (physical 29,31,33,35, at the far right edge of the header).
Presence samples = rolling last 120 seconds (1 sample/sec). Motion triggers camera (60s cooldown).
Status = live CPU/RAM/temp/uptime/time from /proc (100ms sample for CPU).
Schedule = **removed** (was `scheduler.py` + `/schedule`). Motor 1 is now driven by `auto_feeder.py`; motor 2 stays manual. Do not re-add a time schedule.
Photos = stored in `Photos/` directory, captured by OV5647 via rpicam-still when PIR detects motion.
Weight = HX711 on BCM 24 (DT) / 25 (SCK), sampled ~10Hz by a background thread. Calibration is a table of `{grams, raw}` points persisted in `scale.json`; weight is piecewise-linear interpolation between points and linear extrapolation beyond the outer two. An inverted load cell (raw falls as weight rises) works fine — the sign comes from the measured points, not from a hardcoded offset.
Weight workflow = the Weight tab shows the value + Tare + Configure. `/configure` is the calibration page: live raw/weight, a Capture button per point (median of 16 frames), a raw-vs-weight graph, and Save. Tare records the 0 g point. `calibrated:false` means fewer than 2 captured points.
Weight history = `weightlog.py` appends one JSON line `{t, g}` to `weight_log.jsonl` every 600s, or every 10s while `presence.current` is true. Append-only on purpose (a full rewrite every 10s would wear the SD card). It only logs when the scale is calibrated and has no error, keeps the newest 5000 samples in memory (and rewrites the file when it passes 6000), and the Weight tab charts the last 1000 (`GET /weight/history`).

## Auto refill (motor 1)
`auto_feeder.py` runs a background control loop. It never uses a fixed steps-per-gram constant; every dose is corrected by what the scale measured.

Trigger (all required): weight **< `low_g`** (10 g) **continuously for `low_dwell_s`** (300 s) — this defeats the cat pausing 20 s mid-meal — and a **stable** reading, and **`cooldown_s` (300 s) since the last attempt**.

The dwell is filtered so a single bad sample cannot wipe it: `_tick` keeps the last 5 in-range readings and "no longer low" requires **all of them to be ≥ `low_g`** (at least 3 samples). A one-tick spike, a transient HX711 error (`clock pulse too slow` / `no data`) or one impossible frame does **not** reset the counter; three consecutive impossible frames do. `/auto` exposes `weight`, `filtered_g`, `low_for_s`, `dwell_left_s` and `last_reset: {t, reason}` so a restarting counter can be explained from the API instead of guessed.

Dose loop: `gap = target_g - weight`; burst = `gap * coarse_factor (0.85) / grams_per_step` when the gap is large, `gap * fine_factor (0.5)` when it is small, clamped to `[min_steps, max_cycle_steps]`. After each burst it sleeps `settle_s` (2 s) and re-measures with `scale.capture()` (median of 16 frames). It stops when `gap <= tolerance_g`. `grams_per_step` is **seeded at 0.08** (the user's "50 steps ≈ 4 g" measurement) and re-learned from every clean dose (`delta / steps`, EMA 0.5, accepted while within 0.2x–5x the current value), persisted to `feeding.json`. No bench calibration is needed: a wrong seed self-corrects within one or two refills. If the seed under-estimates the yield, the first refill deliberately overshoots (that is expected and fine); if it over-estimates, the refill just uses more cycles, which is why `max_total_steps` is 2500.

Safety: aborts on two consecutive no-output cycles ("nothing dispensed (hopper empty?)"), `max_cycles`, `max_total_steps`, scale error, implausible weight (> `plausible_max_g` = a cat on the platform) or a missing bowl (weight < `bowl_min_g`). Every attempt is appended to `feed_log.jsonl` as `{t, before, after, steps, cycles, result}` and shown on the Auto tab.

PIR handling: **not used by the feeder controller at all** — it only drives the camera and the Presence tab. The refill decision is weight-only (low + dwell + stable + cooldown), because the PIR proved unreliable and gating food on it risked starving the cat. If the cat is at the bowl, the reading is unstable and the trigger will not fire; no sensor interlock is involved, so a refill may start while the cat is eating from an already-empty bowl.

Tuning: the Auto tab has the low/target thresholds, an enable toggle, **Dose once** (manual refill for bench tests) and **Stop**. Manual motor commands on the Feeder tab abort an in-flight refill.

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
- `scale.py` is the only place that reads the scale; weight = piecewise-linear interpolation over the `{grams, raw}` points in `scale.json`. `/weight` also reports `pulse_us` (measured SCK high phase), `points` and `warning`
- Second stepper motor (`MOTOR2_PINS`) controlled via `/motor2/*` endpoints and the Motor 1/2 toggle on the Feeder tab
