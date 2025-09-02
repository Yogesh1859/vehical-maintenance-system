from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# ========== DB Setup ==========
def init_db():
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    # Users now include email
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            password TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            model_year TEXT,
            reg_number TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            service_type TEXT,
            last_service_date TEXT,
            next_due_date TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ========== Helper: Email ==========
def send_email_alert(to_email, subject, message):
    try:
        sender_email = "your_email@gmail.com"  # ⚠️ change this
        sender_pass = "your_app_password"      # ⚠️ use Gmail App Password

        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_pass)
            server.sendmail(sender_email, to_email, msg.as_string())
        print("✅ Email sent to", to_email)
    except Exception as e:
        print("❌ Email failed:", e)

# ========== Routes ==========
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username, email, password = data["username"], data["email"], data["password"]
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                    (username, email, password))
        conn.commit()
        return jsonify({"message": "User registered successfully"})
    except:
        return jsonify({"message": "Username already exists"})
    finally:
        conn.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username, password = data["username"], data["password"]
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    if row:
        return jsonify({"user_id": row[0], "email": row[1]})
    return jsonify({"message": "Invalid credentials"})

@app.route("/add_vehicle", methods=["POST"])
def add_vehicle():
    data = request.json
    user_id, name, model_year, reg_number = data["user_id"], data["name"], data["model_year"], data["reg_number"]
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO vehicles (user_id, name, model_year, reg_number) VALUES (?, ?, ?, ?)",
                (user_id, name, model_year, reg_number))
    conn.commit()
    conn.close()
    return jsonify({"message": "Vehicle added"})

@app.route("/get_vehicles/<int:user_id>")
def get_vehicles(user_id):
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM vehicles WHERE user_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "user_id": r[1], "name": r[2], "model_year": r[3], "reg_number": r[4]} for r in rows])

@app.route("/add_service", methods=["POST"])
def add_service():
    data = request.json
    vehicle_id, service_type = data["vehicle_id"], data["service_type"]
    last_service_date = datetime.date.today()
    if service_type == "wash":
        next_due_date = last_service_date + datetime.timedelta(days=30)
    elif service_type == "oil":
        next_due_date = last_service_date + datetime.timedelta(days=90)
    else:
        next_due_date = last_service_date + datetime.timedelta(days=180)

    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO services (vehicle_id, service_type, last_service_date, next_due_date, status) VALUES (?, ?, ?, ?, ?)",
                (vehicle_id, service_type, str(last_service_date), str(next_due_date), "ok"))
    conn.commit()
    conn.close()

    return jsonify({"message": "Service added", "next_due": str(next_due_date)})

@app.route("/get_services/<int:vehicle_id>")
def get_services(vehicle_id):
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM services WHERE vehicle_id=?", (vehicle_id,))
    rows = cur.fetchall()

    # Get the owner's email
    cur.execute("SELECT user_id FROM vehicles WHERE id=?", (vehicle_id,))
    owner = cur.fetchone()
    user_email = None
    if owner:
        cur.execute("SELECT email FROM users WHERE id=?", (owner[0],))
        email_row = cur.fetchone()
        if email_row:
            user_email = email_row[0]
    conn.close()

    today = datetime.date.today()
    result = []
    for r in rows:
        next_due = datetime.date.fromisoformat(r[4])
        status = "ok"
        if today > next_due:
            status = "overdue"
        elif (next_due - today).days <= 7:
            status = "due soon"
        result.append({
            "id": r[0],
            "vehicle_id": r[1],
            "service_type": r[2],
            "last_service_date": r[3],
            "next_due_date": r[4],
            "status": status
        })

        # 🚨 Email alert if overdue
        if status == "overdue" and user_email:
            send_email_alert(
                user_email,
                f"Service Overdue: {r[2]}",
                f"Your vehicle (ID: {vehicle_id}) is overdue for {r[2]}. Due date was {r[4]}."
            )

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
