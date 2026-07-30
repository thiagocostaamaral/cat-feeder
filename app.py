from flask import Flask, jsonify, render_template, request
from motor import StepperMotor

app = Flask(__name__)
motor = StepperMotor()

@app.post("/motor/open")
def open_motor():
    motor.rotate(512)
    return jsonify({
        "status":"ok"
    })

@app.post("/motor/close")
def close_motor():
    motor.rotate(-512)
    return jsonify({
        "status":"ok"
    })

@app.post("/motor/rotate")
def rotate_motor():
    data = request.get_json()
    rotation = int(data["rotation"])
    motor.rotate(rotation)
    return jsonify({
        "status": "ok",
        "rotation": rotation
    })

@app.get("/")
def index():
    return render_template("index.html")

app.run(
    host="::",
    port=5000,
    debug=False
)