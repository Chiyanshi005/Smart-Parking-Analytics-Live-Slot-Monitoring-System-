import io
import pandas as pd  # pyright: ignore[reportMissingModuleSource]
from flask import Flask, render_template, request, redirect, session, send_file  # type: ignore
import mysql.connector  # pyright: ignore[reportMissingImports]
from datetime import datetime
from reportlab.lib.pagesizes import letter  # pyright: ignore[reportMissingModuleSource]
from reportlab.pdfgen import canvas  # pyright: ignore[reportMissingModuleSource]
from twilio.rest import Client # pyright: ignore[reportMissingImports]

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

# ================= TWILIO CONFIG =================
account_sid = "YOUR_ACCOUNT_SID"
auth_token = "YOUR_AUTH_TOKEN"
twilio_number = "YOUR_TWILIO_NUMBER"

client = Client(account_sid, auth_token)


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

            # ===== NEW ADMIN PROFILE CODE =====
            session["admin_name"] = user["username"]
            session["login_time"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            session.pop("logout_time", None)
            # ==================================

            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid Username or Password")

    return render_template("login.html")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "admin" not in session:
        return redirect("/")

    search = request.args.get("search")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = request.args.get("page", 1, type=int)

    per_page = 5

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ---------------- FILTER QUERY ----------------
    query = "SELECT * FROM parking_data WHERE 1=1"
    params = []

    if search:
        query += " AND vehicle_number LIKE %s"
        params.append("%" + search + "%")

    if start_date and end_date:
        query += " AND DATE(entry_time) BETWEEN %s AND %s"
        params.append(start_date)
        params.append(end_date)

    # ---------------- COUNT FOR PAGINATION ----------------
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as total")
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()["total"]

    total_pages = (total_records + per_page - 1) // per_page

    # ---------------- PAGINATION ----------------
    offset = (page - 1) * per_page
    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])

    cursor.execute(query, params)
    data = cursor.fetchall()

    # ---------------- SUMMARY DATA ----------------
    cursor.execute("SELECT COALESCE(SUM(parking_fee),0) AS total FROM parking_data")
    total = round(float(cursor.fetchone()["total"]), 2)

    cursor.execute("SELECT COUNT(*) AS active FROM parking_data WHERE exit_time IS NULL")
    active_count = cursor.fetchone()["active"]

    cursor.execute("SELECT COALESCE(SUM(total_slots),0) AS total_slots FROM parking_lots")
    total_slots = cursor.fetchone()["total_slots"]

    cursor.execute("SELECT COUNT(*) AS occupied FROM parking_data WHERE exit_time IS NULL")
    occupied_slots = cursor.fetchone()["occupied"]

    available_slots = total_slots - occupied_slots

    # ---------------- ANALYTICS ----------------
    cursor.execute("""
        SELECT COALESCE(SUM(parking_fee),0)
        FROM parking_data
        WHERE DATE(entry_time) = CURDATE()
    """)
    today_revenue = float(cursor.fetchone()["COALESCE(SUM(parking_fee),0)"])

    cursor.execute("""
        SELECT COALESCE(SUM(parking_fee),0)
        FROM parking_data
        WHERE MONTH(entry_time)=MONTH(CURDATE())
        AND YEAR(entry_time)=YEAR(CURDATE())
    """)
    month_revenue = float(cursor.fetchone()["COALESCE(SUM(parking_fee),0)"])

    cursor.execute("""
        SELECT COALESCE(SUM(parking_fee),0)
        FROM parking_data
        WHERE YEAR(entry_time)=YEAR(CURDATE())
    """)
    year_revenue = float(cursor.fetchone()["COALESCE(SUM(parking_fee),0)"])

    cursor.execute("SELECT COALESCE(AVG(parking_fee),0) FROM parking_data")
    avg_fee = round(float(cursor.fetchone()["COALESCE(AVG(parking_fee),0)"]), 2)

    if total_slots > 0:
        occupancy_percent = round((occupied_slots / total_slots) * 100, 2)
    else:
        occupancy_percent = 0

    # ---------------- LIVE PARKING STATUS PER LOT ----------------
    cursor.execute("SELECT lot_name, total_slots FROM parking_lots")
    lots = cursor.fetchall()

    parking_status = []

    for lot in lots:
        lot_name = lot["lot_name"]
        total_slots_lot = lot["total_slots"]

        cursor.execute("""
            SELECT COUNT(*) AS occupied
            FROM parking_data
            WHERE parking_lot = %s
            AND exit_time IS NULL
        """, (lot_name,))

        occupied = cursor.fetchone()["occupied"]
        available = total_slots_lot - occupied

        parking_status.append({
            "lot_name": lot_name,
            "total": total_slots_lot,
            "occupied": occupied,
            "available": available
        })

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        data=data,
        total=total,
        active_count=active_count,
        total_slots=total_slots,
        occupied_slots=occupied_slots,
        available_slots=available_slots,
        search=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        total_pages=total_pages,
        today_revenue=today_revenue,
        month_revenue=month_revenue,
        year_revenue=year_revenue,
        avg_fee=avg_fee,
        occupancy_percent=occupancy_percent,
        parking_status=parking_status,

        # ===== ADMIN PROFILE DATA =====
        admin_name=session.get("admin_name"),
        login_time=session.get("login_time"),
        logout_time=session.get("logout_time")
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


# ================= EXPORT EXCEL =================
@app.route("/export_excel")
def export_excel():
    if "admin" not in session:
        return redirect("/")

    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM parking_data", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="parking_data.xlsx",
        as_attachment=True
    )


# ================= EXPORT PDF =================
@app.route("/export_pdf")
def export_pdf():
    if "admin" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM parking_data")
    rows = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 40
    p.drawString(30, y, "Smart Parking Report")
    y -= 30

    for row in rows:
        line = " | ".join([str(col) for col in row])
        p.drawString(30, y, line)
        y -= 20

        if y < 40:
            p.showPage()
            y = height - 40

    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        download_name="parking_report.pdf",
        as_attachment=True
    )


# ================= LOGOUT =================
@app.route("/logout")
def logout():

    # ===== STORE LOGOUT TIME =====
    session["logout_time"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    session.pop("admin", None)
    return redirect("/")


# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)

