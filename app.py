from flask import Flask, jsonify, render_template, request
from motor import StepperMotor
from presence import PresenceSensor
from system import get_stats
from scheduler import Scheduler
import config

app = Flask(__name__)
motor = StepperMotor(pins=config.MOTOR_PINS)
presence = PresenceSensor(pin=config.PIR_PIN)
scheduler = Scheduler()
scheduler.set_motor(motor)
scheduler.start()

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

@app.get("/")
def index():
    return render_template("index.html")

app.run(host="::",port=5000,debug=False)