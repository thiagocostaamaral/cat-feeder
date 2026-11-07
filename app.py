from flask import Flask, jsonify, render_template, request, send_from_directory
from motor import StepperMotor
from presence import PresenceSensor
from system import get_stats
from scheduler import Scheduler
from camera import CameraTrigger, list_photos, delete_photo, PHOTOS_DIR
from scale import HX711
from weightlog import WeightLog
import config
import os

app = Flask(__name__)
motor = StepperMotor(pins=config.MOTOR_PINS)
motor2 = StepperMotor(pins=config.MOTOR2_PINS)
camera = CameraTrigger(cooldown=60)
presence = PresenceSensor(pin=config.PIR_PIN, on_detect=camera.on_detect)
scheduler = Scheduler()
scheduler.set_motor(motor)
scheduler.start()
scale = HX711(dt_pin=config.HX711_DT_PIN, sck_pin=config.HX711_SCK_PIN)
weight_history = WeightLog(scale, presence)
weight_history.start()

@app.post("/motor/open")
def open_motor():
    motor.rotate(512)
    return jsonify({"status":"ok"})

@app.post("/motor/close")
def close_motor():
    motor.rotate(-512)
    return jsonify({"status":"ok"})

@app.post("/motor/rotate")
def rotate_motor():
    data = request.get_json()
    rotation = int(data["rotation"])
    motor.rotate(rotation)
    return jsonify({"status":"ok","rotation":rotation})

@app.post("/motor2/open")
def open_motor2():
    motor2.rotate(512)
    return jsonify({"status":"ok"})

@app.post("/motor2/close")
def close_motor2():
    motor2.rotate(-512)
    return jsonify({"status":"ok"})

@app.post("/motor2/rotate")
def rotate_motor2():
    data = request.get_json()
    rotation = int(data["rotation"])
    motor2.rotate(rotation)
    return jsonify({"status":"ok","rotation":rotation})

@app.get("/weight")
def get_weight():
    return jsonify(scale.get_state())

@app.post("/weight/tare")
def tare_weight():
    raw = scale.tare()
    if raw is None:
        return jsonify({"status":"error","error":"no reading, check the load cell"}), 503
    return jsonify({"status":"ok","raw":raw})

@app.post("/weight/capture")
def capture_weight():
    reading = scale.capture()
    if reading is None:
        return jsonify({"status":"error","error":"no reading, check the load cell"}), 503
    return jsonify(reading)

@app.post("/calibration")
def save_calibration():
    data = request.get_json(silent=True) or {}
    points = data.get("points")
    if not isinstance(points, list):
        return jsonify({"status":"error","error":"points must be a list"}), 400
    try:
        scale.set_points(points)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"status":"error","error":str(exc)}), 400
    return jsonify(scale.get_state())

@app.get("/configure")
def configure():
    return render_template("configure.html")

@app.post("/weight/reset")
def reset_weight():
    if not scale.reset():
        return jsonify({"status":"error","error":"scale not available"}), 503
    return jsonify({"status":"ok"})

@app.get("/weight/history")
def get_weight_history():
    return jsonify({
        "samples": weight_history.get_all(),
        "count": weight_history.count(),
        "idle_interval": weight_history.idle_interval(),
        "presence_interval": weight_history.presence_interval,
        "presence": bool(presence.current)
    })

@app.delete("/weight/history")
def clear_weight_history():
    weight_history.clear()
    return jsonify({"status":"ok"})

@app.get("/presence")
def get_presence():
    return jsonify(presence.get_state())

@app.get("/status")
def get_status():
    return jsonify(get_stats())

@app.get("/schedule")
def get_schedule():
    return jsonify(scheduler.get_all())

@app.post("/schedule")
def add_schedule():
    data = request.get_json()
    entry = scheduler.add(data["time"], data["rotation"])
    return jsonify(entry)

@app.delete("/schedule/<schedule_id>")
def remove_schedule(schedule_id):
    scheduler.remove(schedule_id)
    return jsonify({"status":"ok"})

@app.get("/photos")
def get_photos():
    return jsonify(list_photos())

@app.get("/photos/<name>")
def serve_photo(name):
    return send_from_directory(PHOTOS_DIR, name)

@app.delete("/photos/<name>")
def remove_photo(name):
    delete_photo(name)
    return jsonify({"status":"ok"})

@app.get("/")
def index():
    return render_template("index.html")

app.run(host="::",port=5000,debug=False)