from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

# ====================================
# 初始化資料庫
# ====================================
def init_db():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # =========================
    # 餐具資料表
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_code TEXT UNIQUE,
        item_type TEXT
    )
    """)

    # =========================
    # 借還紀錄表
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_code TEXT,
        item_type TEXT,
        action TEXT,
        user_name TEXT,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ====================================
# 首頁
# ====================================
@app.route("/")
def index():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # =========================
    # 餐盒借出
    # =========================
    cursor.execute("""
    SELECT COUNT(*)
    FROM records
    WHERE item_type='餐盒'
    AND action='借出'
    """)
    box_borrow = cursor.fetchone()[0]

    # 餐盒歸還
    cursor.execute("""
    SELECT COUNT(*)
    FROM records
    WHERE item_type='餐盒'
    AND action='歸還'
    """)
    box_return = cursor.fetchone()[0]

    # 杯子借出
    cursor.execute("""
    SELECT COUNT(*)
    FROM records
    WHERE item_type='杯子'
    AND action='借出'
    """)
    cup_borrow = cursor.fetchone()[0]

    # 杯子歸還
    cursor.execute("""
    SELECT COUNT(*)
    FROM records
    WHERE item_type='杯子'
    AND action='歸還'
    """)
    cup_return = cursor.fetchone()[0]

    # =========================
    # 已註冊總餐具數
    # =========================
    cursor.execute("""
    SELECT COUNT(*)
    FROM items
    """)
    total_items = cursor.fetchone()[0]

    conn.close()

    # =========================
    # 計算目前借出數
    # =========================
    box_count = box_borrow - box_return
    cup_count = cup_borrow - cup_return

    if box_count < 0:
        box_count = 0

    if cup_count < 0:
        cup_count = 0

    return render_template(
        "index.html",
        box_count=box_count,
        cup_count=cup_count,
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

    data = request.json

    qr_code = data["qr_code"]
    item_type = data["item_type"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:

        cursor.execute("""
        INSERT INTO items
        (qr_code, item_type)
        VALUES (?, ?)
        """, (
            qr_code,
            item_type
        ))

        conn.commit()

        result = {
            "status": "success",
            "message": "新增成功"
        }

    except:

        result = {
            "status": "error",
            "message": "QRCode 已存在"
        }

    conn.close()

    return jsonify(result)

# ====================================
# 新增借還紀錄 API
# ====================================
@app.route("/add_record", methods=["POST"])
def add_record():

    data = request.json

    qr_code = data["qr_code"]
    action = data["action"]
    user_name = data["user_name"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # =========================
    # 查詢餐具種類
    # =========================
    cursor.execute("""
    SELECT item_type
    FROM items
    WHERE qr_code=?
    """, (qr_code,))

    item = cursor.fetchone()

    if item:
        item_type = item[0]

    else:
        conn.close()

        return jsonify({
            "status": "error",
            "message": "此 QRCode 尚未註冊"
        })

    # =========================
    # 新增紀錄
    # =========================
    cursor.execute("""
    INSERT INTO records
    (qr_code, item_type, action, user_name)
    VALUES (?, ?, ?, ?)
    """, (
        qr_code,
        item_type,
        action,
        user_name
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "紀錄成功"
    })

# ====================================
# 歷史紀錄頁
# ====================================
@app.route("/records")
def records():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM records
    ORDER BY id DESC
    """)

    data = cursor.fetchall()

    conn.close()

    return render_template(
        "records.html",
        records=data
    )

# ====================================
# 啟動 Flask
# ====================================
if __name__ == "__main__":
    app.run(debug=True)