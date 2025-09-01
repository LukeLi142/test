import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_cors import CORS
from flask import Flask, app, request, jsonify, render_template
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# 從 Render 環境變數讀取 DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(
    dbname="test_hrxm",
    user="test_hrxm_user",
    password="lWnCZdHexyxtghjql1nw2Vy2qAwJ9Oqv",
    host="dpg-d2oh52ogjchc73eok92g-a",   # 例如 abc123.render.com
    port="5432"            # Render PostgreSQL 的 port
)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    return conn, cursor

    

# 初始化資料庫
def init_db():
    conn, cursor = get_db_connection()
    

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id SERIAL PRIMARY KEY,
            username VARCHAR(20),
            phone VARCHAR(20),
            department VARCHAR(100),
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            status VARCHAR(10) CHECK (status IN ('free', 'booked')) DEFAULT 'free',
            CONSTRAINT unique_slot UNIQUE (date, start_time)
        );
    """)
init_db()

# 插入空閒時段
def insert_time_slots(date, start_hour, end_hour):
    conn, cursor = get_db_connection()
    for hour in range(start_hour, end_hour):
        s = f"{hour:02d}:00:00"
        e = f"{hour+1:02d}:00:00"
        try:
            cursor.execute(
                "INSERT INTO reservations(date, start_time, end_time) VALUES (%s, %s, %s)",
                (date, s, e)
            )
        except Exception as ex:
            print(f"插入失敗: {ex}")
    conn.commit()
    conn.close()

# Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})



@app.route("/")
def home():
    return render_template("index.html")


# 查詢 API
@app.route('/api/status', methods=['GET'])
def get_status():
    conn, cursor = get_db_connection()
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': '請提供日期'}), 400

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.today().date()

    if date_obj < today:
        return jsonify({'error': '不能查詢今天以前的日期'}), 400

    cursor.execute("SELECT COUNT(*) FROM reservations WHERE date = %s", (date_str,))
    count = cursor.fetchone()["count"]

    if count == 0:
        insert_time_slots(date_str, 10, 17)

    cursor.execute("SELECT start_time, end_time, status FROM reservations WHERE date = %s", (date_str,))
    slots = cursor.fetchall()
    conn.close()

    result = [
        {'start_time': str(row['start_time']), 'end_time': str(row['end_time']), 'status': row['status']}
        for row in slots
    ]
    return jsonify(result)

# 預約 API
@app.route('/api/book', methods=['POST'])
def book_slot():
    conn, cursor = get_db_connection()
    data = request.json
    name = data.get('name')
    date_str = data.get('date')
    start_time = data.get('start_time')
    phone = data.get('phone')
    department = data.get('department')

    if not all([name, date_str, start_time, phone, department]):
        return jsonify({'error': '缺少資料'}), 400

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.today().date()
    if date_obj < today:
        return jsonify({'error': '不能預約今天以前的日期'}), 400

    cursor.execute("SELECT id, status FROM reservations WHERE date = %s AND start_time = %s", (date_str, start_time))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': '該時段不存在'}), 400
    if row["status"] == 'booked':
        return jsonify({'error': '該時段已被預約'}), 400

    cursor.execute(
        "UPDATE reservations SET username=%s, phone=%s, department=%s, status='booked' WHERE id=%s",
        (name, phone, department, row["id"])
    )
    conn.commit()
    conn.close()
    return jsonify({'message': '預約成功'})

# 取消預約 API
@app.route('/api/cancel', methods=['POST'])
def cancel_slot():
    conn, cursor = get_db_connection()
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    date_str = data.get('date')
    start_time = data.get('start_time')

    if not all([name, phone, date_str, start_time]):
        return jsonify({'error': '缺少資料'}), 400

    cursor.execute(
        "SELECT id, status, username, phone FROM reservations WHERE date = %s AND start_time = %s",
        (date_str, start_time)
    )
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': '該時段不存在'}), 400
    if row["status"] != 'booked' or row["username"] != name or row["phone"] != phone:
        return jsonify({'error': '你沒有預約該時段'}), 400

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.today().date()
    if date_obj < today:
        return jsonify({'error': '過去的預約無法取消'}), 400

    cursor.execute("UPDATE reservations SET username=NULL, phone=NULL, department=NULL, status='free' WHERE id=%s", (row["id"],))
    conn.commit()
    conn.close()
    return jsonify({'message': '取消預約成功'})

# 自動清理舊資料
def clean_old_reservations():
    conn, cursor = get_db_connection()
    seven_days_ago = date.today() - timedelta(days=7)
    cursor.execute("DELETE FROM reservations WHERE date < %s", (seven_days_ago,))
    conn.commit()
    conn.close()
    print("舊預約已清除")

scheduler = BackgroundScheduler()
scheduler.add_job(clean_old_reservations, 'interval', days=1)
scheduler.start()


if __name__ == '__main__':
    init_db()  # 初始化資料表
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)