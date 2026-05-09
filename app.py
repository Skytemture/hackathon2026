from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

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

    borrowed_count = containers_col.count_documents({
        "user_id": {"$ne": None}
    })

    return render_template(
        "index.html",
        cup_count=cup_count,
        plate_count=plate_count,
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
        item_type = data.get("item_type")

        if not item_type:
            return jsonify({
                "status": "error",
                "message": "資料不完整"
            })

        # =========================
        # 找出所有 container id
        # =========================
        all_items = list(containers_col.find({}, {"_id": 0, "id": 1}))

        max_num = 0

        for item in all_items:
            cid = item.get("id", "")

            # C01 → 1
            if cid.startswith("C"):
                try:
                    num = int(cid[1:])
                    if num > max_num:
                        max_num = num
                except:
                    pass

        # =========================
        # 新 id
        # =========================
        new_id = f"C{str(max_num + 1).zfill(2)}"

        # =========================
        # item type mapping
        # =========================
        if item_type == "杯子":
            item_type = "cup"
        elif item_type == "餐盒":
            item_type = "plate"

        # =========================
        # insert
        # =========================
        containers_col.insert_one({
            "id": new_id,
            "user_id": None,
            "item_type": item_type,
            "status": "C001",
            "updated_at": datetime.now().isoformat()
        })

        return jsonify({
            "status": "success",
            "message": f"{new_id} 新增成功"
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

        container_id = data.get("container_id")
        user_id = data.get("user_id")

        if not container_id:
            return jsonify({
                "status": "error",
                "message": "缺少 container_id"
            })

        container = containers_col.find_one({
            "id": container_id
        })

        if not container:
            return jsonify({
                "status": "error",
                "message": "找不到餐具"
            })

        # ==========================
        # 借出
        # ==========================
        if container["user_id"] is None:

            if not user_id:
                return jsonify({
                    "status": "error",
                    "message": "請提供 user_id"
                })

            user = users_col.find_one({
                "id": user_id
            })

            if not user:
                return jsonify({
                    "status": "error",
                    "message": "使用者不存在"
                })

            containers_col.update_one(
                {"id": container_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "status": "R001",
                        "updated_at": datetime.now().isoformat()
                    }
                }
            )

            return jsonify({
                "status": "success",
                "message": f"{container_id} 借出成功",
                "action": "borrow"
            })

        # ==========================
        # 歸還
        # ==========================
        else:

            containers_col.update_one(
                {"id": container_id},
                {
                    "$set": {
                        "user_id": None,
                        "status": "C001",
                        "updated_at": datetime.now().isoformat()
                    }
                }
            )

            return jsonify({
                "status": "success",
                "message": f"{container_id} 歸還成功",
                "action": "return"
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