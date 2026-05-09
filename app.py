from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
from datetime import datetime
import re
import threading

# ── GPIO ──────────────────────────────────────────────────────────────────────
try:
    from gpiozero import OutputDevice, Servo
    from gpiozero.pins.pigpio import PiGPIOFactory
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

app = Flask(__name__)
app.secret_key = "hackathon_secret_2026"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

# =========================
# MongoDB
# =========================
MONGO_URI = "mongodb+srv://hackathon0509_user:1eYLNz7Og9UYlaLl@cluster0.jedeu7j.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["hackathon"]
users_col = db["users"]
containers_col = db["containers"]

# =========================
# GPIO Setup
# =========================
if GPIO_AVAILABLE:
    IN1 = OutputDevice(27)
    IN2 = OutputDevice(22)
    IN3 = OutputDevice(23)
    IN4 = OutputDevice(24)
    stepper_pins = [IN1, IN2, IN3, IN4]

    STEP_SEQUENCE = [
        [1,0,0,0],
        [1,1,0,0],
        [0,1,0,0],
        [0,1,1,0],
        [0,0,1,0],
        [0,0,1,1],
        [0,0,0,1],
        [1,0,0,1],
    ]

    factory = PiGPIOFactory()
    servo = Servo(18, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000,
                  pin_factory=factory)

# =========================
# Hardware Helpers
# =========================
def _degree_to_value(degree):
    return max(-1.0, min(1.0, degree / 90.0))

def _run_stepper(seconds, clockwise=True, delay=0.002):
    from time import sleep, time

    # ── Forward ──────────────────────────────────────────────────────────────
    seq_fwd = STEP_SEQUENCE if clockwise else STEP_SEQUENCE[::-1]
    end = time() + seconds
    while time() < end:
        for step in seq_fwd:
            for pin, val in zip(stepper_pins, step):
                pin.value = val
            sleep(delay)

    # ── Wait 5 seconds ───────────────────────────────────────────────────────
    sleep(5)

    # ── Reverse back ─────────────────────────────────────────────────────────
    seq_rev = STEP_SEQUENCE[::-1] if clockwise else STEP_SEQUENCE
    end = time() + seconds
    while time() < end:
        for step in seq_rev:
            for pin, val in zip(stepper_pins, step):
                pin.value = val
            sleep(delay)

    # ── De-energise coils ────────────────────────────────────────────────────
    for pin in stepper_pins:
        pin.value = 0

def _run_servo(degree):
    from time import sleep
    servo.value = _degree_to_value(degree)
    sleep(1)
    servo.value = 1.0
    sleep(0.5)

def trigger_hardware_sync(item_type):
    """
    同步執行硬體，呼叫方會卡住等到完全復位才繼續。
    PLATE → stepper 2s + servo +25°
    LID   → stepper 4s + servo +25°
    CUP   → stepper 4s + servo -25°
    """
    if not GPIO_AVAILABLE:
        print(f"[GPIO disabled] would trigger for item_type={item_type}")
        return

    if item_type == "PLATE":
        stepper_sec, servo_deg = 2, 25
    elif item_type == "LID":
        stepper_sec, servo_deg = 4, 25
    elif item_type == "CUP":
        stepper_sec, servo_deg = 4, -25
    else:
        return

    # stepper 和 servo 並行跑，但等兩個都完成才 return
    t1 = threading.Thread(target=_run_stepper, args=(stepper_sec,), daemon=True)
    t2 = threading.Thread(target=_run_servo,   args=(servo_deg,),   daemon=True)
    t1.start()
    t2.start()
    t1.join()  # 等 stepper（去程+5秒+回程）完成
    t2.join()  # 等 servo 完成

# =========================
# Helpers
# =========================
def normalize_phone(phone):
    return re.sub(r"\D", "", str(phone))

def parse_item_type(code):
    if not code:
        return None
    match = re.match(r"([A-Z]+)", code)
    return match.group(1) if match else None

# =========================
# Pages
# =========================
@app.route("/")
def index():
    total       = containers_col.count_documents({})
    borrowed    = containers_col.count_documents({"status": {"$regex": "^U"}})
    cup_count   = containers_col.count_documents({"item_type": {"$regex": "^CUP"},   "status": {"$regex": "^U"}})
    plate_count = containers_col.count_documents({"item_type": {"$regex": "^PLATE"}, "status": {"$regex": "^U"}})
    lid_count   = containers_col.count_documents({"item_type": {"$regex": "^LID"},   "status": {"$regex": "^U"}})
    return render_template("index.html",
        total_items=total,
        cup_count=cup_count,
        plate_count=plate_count,
        lid_count=lid_count,
        borrowed_count=borrowed)

@app.route("/scan")
def scan():
    return render_template("scan.html")

@app.route("/register_item")
def register_item():
    return render_template("register_item.html")

# =========================
# Login
# =========================
@app.route("/login_user", methods=["POST"])
def login_user():
    try:
        data       = request.json
        input_val  = data.get("input", "").strip()
        normalized = normalize_phone(input_val)

        user = users_col.find_one({"$or": [
            {"phone":   input_val},
            {"phone":   normalized},
            {"name":    input_val},
            {"account": input_val}
        ]})

        if not user:
            return jsonify({"status": "error", "message": "查無會員"})

        session["user_id"]   = user.get("account") or str(user["_id"])
        session["user_name"] = user["name"]

        return jsonify({"status": "success", "user_name": user["name"]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# =========================
# Add Item
# =========================
@app.route("/add_item", methods=["POST"])
def add_item():
    try:
        code = request.json.get("container_id")
        if not code:
            return jsonify({"status": "error", "message": "缺少 QR"})
        item_type = parse_item_type(code)
        count  = containers_col.count_documents({})
        new_id = f"C{str(count + 1).zfill(2)}"
        containers_col.insert_one({
            "id":         new_id,
            "qr_code":    code,
            "item_type":  item_type,
            "status":     "C01",
            "user_id":    None,
            "updated_at": datetime.now().isoformat()
        })
        return jsonify({"status": "success", "id": new_id, "item_type": item_type})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# =========================
# Scan Core
# =========================
@app.route("/scan_qr", methods=["POST"])
def scan_qr():
    try:
        data   = request.json
        code   = data.get("item_code", "").strip()
        action = data.get("action")

        if not code:
            return jsonify({"status": "error", "message": "no qr"})

        # ── 先嘗試當 user 查詢（account / name / phone）───────────────────────
        user = users_col.find_one({"$or": [
            {"account": code},
            {"name":    code},
            {"phone":   code},
            {"phone":   normalize_phone(code)}
        ]})

        if user:
            session["user_id"]   = user.get("account") or str(user["_id"])
            session["user_name"] = user["name"]
            return jsonify({"status": "success", "type": "user", "name": user["name"]})

        # ── 不是 user，處理 container ─────────────────────────────────────────
        if "user_id" not in session:
            return jsonify({"status": "error", "message": "login first"})

        item = containers_col.find_one({"qr_code": code})
        if not item:
            return jsonify({"status": "error", "message": "not found"})

        user_id   = session["user_id"]
        item_type = item.get("item_type") or parse_item_type(code)

        # ── Borrow ────────────────────────────────────────────────────────────
        if action == "borrow":
            if item["status"].startswith("U"):
                return jsonify({"status": "error", "message": "already borrowed"})

            containers_col.update_one(
                {"qr_code": code},
                {"$set": {
                    "user_id":    user_id,
                    "status":     "U01",
                    "updated_at": datetime.now().isoformat()
                }}
            )

            return jsonify({"status": "success", "message": "borrow ok",
                            "item_type": item_type})

        # ── Return ────────────────────────────────────────────────────────────
        if action == "return":
            containers_col.update_one(
                {"qr_code": code},
                {"$set": {
                    "user_id":    None,
                    "status":     "C01",
                    "updated_at": datetime.now().isoformat()
                }}
            )

            # 同步等硬體完全復位，前端會卡在這裡等，自然鎖住掃描
            trigger_hardware_sync(item_type)

            return jsonify({"status": "success", "message": "return ok",
                            "item_type": item_type})

        return jsonify({"status": "error", "message": "bad action"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# =========================
# Run
# =========================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)