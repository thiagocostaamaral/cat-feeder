# Cat Feeder - AI Instructions

## Project Overview
Smart cat feeder web app running on a **Raspberry Pi**. Flask backend controls a stepper motor via GPIO to dispense food. Web UI accessible from any device on the local network.

## Tech Stack
- **Backend:** Python 3 + Flask (`app.py`)
- **Motor control:** `motor.py` (StepperMotor class, GPIO via lgpio)
- **Presence sensor:** `presence.py` (MH-SR602 PIR sensor, GPIO via lgpio)
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
├── config.py           # Configuration (pins: MOTOR_PINS, PIR_PIN)
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
| GET    | `/`             | —                 | HTML page (5 tabs: Feeder, Presence, System, Schedule, Photos) |
| POST   | `/motor/open`   | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/close`  | —                 | `{"status":"ok"}`                             |
| POST   | `/motor/rotate` | `{"rotation": N}` | `{"status":"ok","rotation":N}`                |
| GET    | `/presence`     | —                 | `{"current":bool,"samples":[0,1,0,...]}`      |
| GET    | `/status`       | —                 | `{"cpu_percent":N,"ram":{...},"temperature_c":N,"uptime":"...","time":"HH:MM:SS"}` |
| GET    | `/schedule`     | —                 | `[{id,time,rotation},...]`                    |
| POST   | `/schedule`     | `{"time":"08:00","rotation":50}` | `{id,time,rotation}`               |
| DELETE | `/schedule/<id>`| —                 | `{"status":"ok"}`                             |
| GET    | `/photos`       | —                 | `[{name,url},...]`                            |
| GET    | `/photos/<name>`| —                 | Serves JPEG file                              |
| DELETE | `/photos/<name>`| —                 | `{"status":"ok"}`                             |

Open = 512 steps, Close = -512 steps.
Presence samples = rolling last 120 seconds (1 sample/sec). Motion triggers camera (10s cooldown).
Status = live CPU/RAM/temp/uptime/time from /proc (100ms sample for CPU).
Schedule = stored in `schedules.json`, background thread checks every 5s and fires motor at matching HH:MM.
Photos = stored in `Photos/` directory, captured by OV5647 via rpicam-still when PIR detects motion.

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

Both scripts exclude `helper/`, `.git`, `__pycache__`, `credentials*`, `*.pyc` from sync.

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
