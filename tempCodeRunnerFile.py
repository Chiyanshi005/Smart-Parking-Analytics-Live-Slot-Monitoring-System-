from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
import pandas as pd
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ================= DATABASE CONNECTION =================
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Chiya005",
        database="smartparking"
    )

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admin WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["admin"] = True
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid Username or Password")

    return render_template("login.html")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # -------- MAIN TABLE DATA --------
    cursor.execute("SELECT * FROM parking_data ORDER BY id DESC")
    data = cursor.fetchall()

    # -------- TOTAL REVENUE --------
    cursor.execute("SELECT SUM(parking_fee) AS total FROM parking_data")
    total_result = cursor.fetchone()
    total = round(total_result["total"] or 0, 3)

    # -------- ACTIVE VEHICLES --------
    cursor.execute("SELECT COUNT(*) AS active FROM parking_data WHERE exit_time IS NULL")
    active_count = cursor.fetchone()["active"]

    # -------- LOT WISE REVENUE --------
    cursor.execute("""
        SELECT parking_lot,
               COALESCE(SUM(parking_fee),0) AS revenue
        FROM parking_data
        GROUP BY parking_lot
        ORDER BY parking_lot
    """)
    lot_data = cursor.fetchall()

    # -------- SLOT MANAGEMENT --------
    cursor.execute("SELECT SUM(total_slots) AS total_slots FROM parking_lots")
    total_slots = cursor.fetchone()["total_slots"] or 0

    cursor.execute("SELECT COUNT(*) AS occupied FROM parking_data WHERE exit_time IS NULL")
    occupied_slots = cursor.fetchone()["occupied"]

    available_slots = total_slots - occupied_slots

    # -------- MONTHLY REVENUE --------
    cursor.execute("""
        SELECT DATE_FORMAT(entry_time, '%Y-%m') AS month,
               SUM(parking_fee) AS revenue
        FROM parking_data
        GROUP BY DATE_FORMAT(entry_time, '%Y-%m')
        ORDER BY month
    """)
    monthly_data = cursor.fetchall()

    # -------- DAILY REVENUE --------
    cursor.execute("""
        SELECT DATE(entry_time) AS day,
               SUM(parking_fee) AS revenue
        FROM parking_data
        GROUP BY DATE(entry_time)
        ORDER BY day
    """)
    daily_data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        data=data,
        total=total,
        lot_data=lot_data,
        monthly_data=monthly_data,
        daily_data=daily_data,
        active_count=active_count,
        total_slots=total_slots,
        occupied_slots=occupied_slots,
        available_slots=available_slots
    )


# ================= ADD ENTRY =================
@app.route("/add", methods=["GET", "POST"])
def add_entry():
    if "admin" not in session:
        return redirect("/")

    if request.method == "POST":
        vehicle_number = request.form["vehicle_number"]
        parking_lot = request.form["parking_lot"]
        entry_time = datetime.now()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO parking_data 
            (vehicle_number, parking_lot, entry_time, parking_fee)
            VALUES (%s, %s, %s, %s)
        """, (vehicle_number, parking_lot, entry_time, 0))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/dashboard")

    return render_template("add.html")


# ================= EDIT ENTRY =================
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_entry(id):
    if "admin" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        vehicle_number = request.form["vehicle_number"]
        parking_lot = request.form["parking_lot"]

        cursor.execute("""
            UPDATE parking_data
            SET vehicle_number=%s,
                parking_lot=%s
            WHERE id=%s
        """, (vehicle_number, parking_lot, id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/dashboard")

    cursor.execute("SELECT * FROM parking_data WHERE id=%s", (id,))
    entry = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("edit.html", entry=entry)


# ================= EXIT VEHICLE =================
@app.route("/exit/<int:id>")
def exit_vehicle(id):
    if "admin" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT entry_time FROM parking_data WHERE id=%s", (id,))
    record = cursor.fetchone()

    if record and record["entry_time"]:
        entry_time = record["entry_time"]
        exit_time = datetime.now()

        diff = exit_time - entry_time
        hours = diff.total_seconds() / 3600

        rate_per_hour = 20
        fee = max(20, round(hours * rate_per_hour, 2))

        cursor.execute("""
            UPDATE parking_data 
            SET exit_time=%s, parking_fee=%s
            WHERE id=%s
        """, (exit_time, fee, id))

        conn.commit()

    cursor.close()
    conn.close()

    return redirect("/dashboard")


# ================= EXCEL EXPORT =================
@app.route("/export_excel")
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM parking_data", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="parking_data.xlsx", as_attachment=True)


# ================= PDF EXPORT =================
@app.route("/export_pdf")
def export_pdf():
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    p.drawString(100, 800, "Smart Parking Report")
    p.drawString(100, 780, f"Generated on: {datetime.now()}")

    p.save()
    buffer.seek(0)

    return send_file(buffer, download_name="parking_report.pdf", as_attachment=True)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)