from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
from datetime import datetime
import re

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
# helper
# =========================
def normalize_phone(phone):
    return re.sub(r"\D", "", str(phone))


def parse_item_type(code):
    """CUP01 → CUP / LID04 → LID"""
    if not code:
        return None

    match = re.match(r"([A-Z]+)", code)
    return match.group(1) if match else None


# =========================
# pages
# =========================
@app.route("/")
def index():

    total = containers_col.count_documents({})

    borrowed = containers_col.count_documents({
        "status": {"$regex": "^U"}
    })

    cup_count = containers_col.count_documents({
        "item_type": {"$regex": "^CUP"},
        "status": {"$regex": "^U"}
    })

    plate_count = containers_col.count_documents({
        "item_type": {"$regex": "^PLATE"},
        "status": {"$regex": "^U"}
    })

    lid_count = containers_col.count_documents({
        "item_type": {"$regex": "^LID"},
        "status": {"$regex": "^U"}  
    })

    return render_template(
        "index.html",
        total_items=total,
        cup_count=cup_count,
        plate_count=plate_count,
        lid_count=lid_count,
        borrowed_count=borrowed
    )


@app.route("/scan")
def scan():
    return render_template("scan.html")


@app.route("/register_item")
def register_item():
    return render_template("register_item.html")


# =========================
# LOGIN
# =========================
@app.route("/login_user", methods=["POST"])
def login_user():
    try:
        data = request.json

        input_val = data.get("input", "").strip()

        user = users_col.find_one({
            "$or": [
                {"phone": input_val},
                {"name": input_val}
            ]
        })

        if not user:
            return jsonify({"status": "error", "message": "查無會員"})

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        return jsonify({
            "status": "success",
            "user_name": user["name"]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# =========================
# ADD ITEM
# =========================
@app.route("/add_item", methods=["POST"])
def add_item():
    try:
        code = request.json.get("container_id")

        if not code:
            return jsonify({"status": "error", "message": "缺少 QR"})

        item_type = parse_item_type(code)

        count = containers_col.count_documents({})
        new_id = f"C{str(count + 1).zfill(2)}"

        containers_col.insert_one({
            "id": new_id,
            "qr_code": code,
            "item_type": item_type,
            "status": "C01",
            "user_id": None,
            "updated_at": datetime.now().isoformat()
        })

        return jsonify({
            "status": "success",
            "id": new_id,
            "item_type": item_type
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# =========================
# SCAN CORE
# =========================
@app.route("/scan_qr", methods=["POST"])
def scan_qr():
    try:
        data = request.json
        code = data.get("item_code", "").strip()
        action = data.get("action")

        if not code:
            return jsonify({"status": "error", "message": "no qr"})

        # ================= USER =================
        if not code[0].isalpha() or len(code) <= 3:

            user = users_col.find_one({
                "$or": [
                    {"id": code},
                    {"name": code},
                    {"phone": code}
                ]
            })

            if not user:
                return jsonify({"status": "error", "message": "no user"})

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return jsonify({
                "status": "success",
                "type": "user",
                "name": user["name"]
            })

        # ================= CHECK LOGIN =================
        if "user_id" not in session:
            return jsonify({"status": "error", "message": "login first"})

        item = containers_col.find_one({"qr_code": code})

        if not item:
            return jsonify({"status": "error", "message": "not found"})

        user_id = session["user_id"]

        # ================= BORROW =================
        if action == "borrow":

            if item["status"].startswith("U"):
                return jsonify({"status": "error", "message": "already borrowed"})

            containers_col.update_one(
                {"qr_code": code},
                {"$set": {
                    "user_id": user_id,
                    "status": "U01",
                    "updated_at": datetime.now().isoformat()
                }}
            )

            return jsonify({"status": "success", "message": "borrow ok"})

        # ================= RETURN =================
        if action == "return":

            containers_col.update_one(
                {"qr_code": code},
                {"$set": {
                    "user_id": None,
                    "status": "C01",
                    "updated_at": datetime.now().isoformat()
                }}
            )

            return jsonify({"status": "success", "message": "return ok"})

        return jsonify({"status": "error", "message": "bad action"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)