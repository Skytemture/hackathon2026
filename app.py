from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "hackathon_secret"
# ====================================
# MongoDB 連線
# ====================================

MONGO_URI = "mongodb+srv://hackathon0509_user:1eYLNz7Og9UYlaLl@cluster0.jedeu7j.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI)

    # 測試連線
    client.admin.command("ping")
    print("✅ MongoDB 連線成功")

    # Database
    db = client["hackathon"]

    # Collections
    users_col = db["users"]
    containers_col = db["containers"]

except Exception as e:
    print("❌ MongoDB 連線失敗")
    print(e)
    exit()


# ====================================
# 首頁
# ====================================
@app.route("/")
def index():

    total_items = containers_col.count_documents({})

    cup_count = containers_col.count_documents({
        "item_type": "cup",
        "status": "C001"
    })

    plate_count = containers_col.count_documents({
        "item_type": "plate",
        "status": "C001"
    })

    lid_count = containers_col.count_documents({
        "item_type": "lid",
        "status": "C001"
    })

    borrowed_count = containers_col.count_documents({
        "user_id": {"$ne": None}
    })

    return render_template(
        "index.html",
        cup_count=cup_count,
        plate_count=plate_count,
        lid_count=lid_count,
        borrowed_count=borrowed_count,
        total_items=total_items
    )


# ====================================
# 掃描頁
# ====================================
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ====================================
# 新增餐具頁
# ====================================
@app.route("/register_item")
def register_item():
    return render_template("register_item.html")


# ====================================
# 新增餐具 API
# ====================================
@app.route("/add_item", methods=["POST"])
def add_item():

    try:
        data = request.json
        container_id = data.get("container_id")

        if not container_id:
            return jsonify({
                "status": "error",
                "message": "缺少 container_id"
            })

        # =========================
        # 1. 只取前綴當 item_type
        # CUP01 → CUP
        # PLATE02 → PLATE
        # LID01 → LID
        # =========================
        item_type = ""

        if container_id.startswith("CUP"):
            item_type = "cup"
        elif container_id.startswith("PLATE"):
            item_type = "plate"
        elif container_id.startswith("LID"):
            item_type = "lid"
        else:
            return jsonify({
                "status": "error",
                "message": "未知 QR Code 類型"
            })

        # =========================
        # 2. 只做 C + 數字遞增（不拆 QR）
        # =========================
        all_items = list(
            containers_col.find({}, {"_id": 0, "id": 1})
        )

        max_num = 0

        for item in all_items:
            cid = item.get("id", "")

            if cid.startswith("C"):
                try:
                    num = int(cid[1:])
                    max_num = max(max_num, num)
                except:
                    pass

        new_id = f"C{str(max_num + 1).zfill(2)}"

        # =========================
        # 3. insert
        # =========================
        containers_col.insert_one({
            "id": new_id,
            "user_id": None,
            "item_type": item_type,
            "status": "O001",
            "updated_at": datetime.now().isoformat()
        })

        return jsonify({
            "status": "success",
            "message": f"{new_id} 新增成功",
            "item_type": item_type
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })
# ====================================
# 借出 / 歸還 API
# ====================================
@app.route("/scan_qr", methods=["POST"])
def scan_qr():

    try:
        data = request.json

        code = data.get("container_id")
        action = data.get("action")

        if not code:
            return jsonify({
                "status": "error",
                "message": "缺少 QR Code"
            })

        code = code.strip()

        # =====================================
        # 判斷是不是餐具 (C01、C02...)
        # =====================================
        is_container = (
            code.startswith("C")
            and len(code) >= 2
            and code[1:].isdigit()
        )

        # =====================================
        # 掃描使用者
        # =====================================
        if not is_container:

            user = users_col.find_one({
                "$or": [
                    {"id": code},
                    {"name": code}
                ]
            })

            # ==============================
            # 新使用者自動建立
            # ==============================
            if not user:

                all_users = list(
                    users_col.find(
                        {},
                        {"_id": 0, "id": 1}
                    )
                )

                max_num = 0

                for u in all_users:

                    uid = u.get("id", "")

                    if uid.startswith("U"):
                        try:
                            num = int(uid[1:])
                            max_num = max(
                                max_num,
                                num
                            )
                        except:
                            pass

                new_user_id = (
                    f"U{str(max_num + 1).zfill(2)}"
                )

                users_col.insert_one({
                    "id": new_user_id,
                    "name": code,
                    "points": 0,
                    "created_at":
                        datetime.now().isoformat()
                })

                user = users_col.find_one({
                    "id": new_user_id
                })

            # 暫存 user
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return jsonify({
                "status": "success",
                "message":
                    f"目前使用者：{user['name']}",
                "type": "user",
                "user_name":
                    user["name"]
            })

        # =====================================
        # 必須先選模式
        # =====================================
        if not action:

            return jsonify({
                "status": "error",
                "message":
                    "請先選擇借用或歸還"
            })

        # =====================================
        # 必須先掃 user
        # =====================================
        if "user_id" not in session:

            return jsonify({
                "status": "error",
                "message":
                    "請先掃描使用者"
            })

        # =====================================
        # 找餐具
        # =====================================
        container = containers_col.find_one({
            "id": code
        })

        if not container:

            return jsonify({
                "status": "error",
                "message":
                    "找不到餐具"
            })

        # =====================================
        # 借用模式
        # =====================================
        if action == "borrow":

            if container["user_id"] is not None:

                return jsonify({
                    "status": "error",
                    "message":
                        "餐具已被借出"
                })

            user_id = session["user_id"]
            user_name = session["user_name"]

            containers_col.update_one(
                {"id": code},
                {
                    "$set": {
                        "user_id":
                            user_id,
                        "status":
                            "R001",
                        "updated_at":
                            datetime.now()
                            .isoformat()
                    }
                }
            )

            return jsonify({
                "status": "success",
                "message":
                    f"{code} 借出成功（{user_name}）",
                "action":
                    "borrow"
            })

        # =====================================
        # 歸還模式
        # =====================================
        elif action == "return":

            if container["user_id"] is None:

                return jsonify({
                    "status": "error",
                    "message":
                        "此餐具尚未借出"
                })

            borrow_user_id = (
                container["user_id"]
            )

            containers_col.update_one(
                {"id": code},
                {
                    "$set": {
                        "user_id":
                            None,
                        "status":
                            "C001",
                        "updated_at":
                            datetime.now()
                            .isoformat()
                    }
                }
            )

            # ==========================
            # points +1
            # ==========================
            users_col.update_one(
                {
                    "id":
                        borrow_user_id
                },
                {
                    "$inc": {
                        "points": 1
                    }
                }
            )

            return jsonify({
                "status": "success",
                "message":
                    f"{code} 歸還成功 (+1 point)",
                "action":
                    "return"
            })

        # =====================================
        # 模式錯誤
        # =====================================
        else:

            return jsonify({
                "status": "error",
                "message":
                    "模式錯誤"
            })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        })
# ====================================
# 查看所有餐具
# ====================================
@app.route("/containers")
def containers():

    data = list(
        containers_col.find(
            {},
            {"_id": 0}
        )
    )

    return render_template(
        "containers.html",
        containers=data
    )


# ====================================
# 查看所有使用者
# ====================================
@app.route("/users")
def users():

    data = list(
        users_col.find(
            {},
            {"_id": 0}
        )
    )

    return render_template(
        "users.html",
        users=data
    )


# ====================================
# API 查看餐具
# ====================================
@app.route("/api/containers")
def api_containers():

    data = list(
        containers_col.find(
            {},
            {"_id": 0}
        )
    )

    return jsonify(data)


# ====================================
# API 查看使用者
# ====================================
@app.route("/api/users")
def api_users():

    data = list(
        users_col.find(
            {},
            {"_id": 0}
        )
    )

    return jsonify(data)


# ====================================
# 健康檢查
# ====================================
@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "database": "hackathon",
        "collections": [
            "users",
            "containers"
        ]
    })


# ====================================
# 啟動 Flask
# ====================================
if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )