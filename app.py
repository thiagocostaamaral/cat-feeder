from flask import Flask, render_template, jsonify
import motor

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/motor/test")
def test_motor():
    motor.test()
    return jsonify({
        "status": "ok"
    })

if __name__ == "__main__":
    app.run(
        host="::",
        port=5000,
        debug=True
    )