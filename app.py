from flask import Flask, render_template, request, redirect, url_for
import csv
import io
import sqlite3

def get_db():
    conn = sqlite3.connect("ticket.db")
    conn.row_factory = sqlite3.Row
    return conn


app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            match_date = request.form.get("match_date")
            opponent = request.form.get("opponent")

            if match_date and opponent:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO matches (date, opponent) VALUES (?, ?)",
                    (match_date, opponent)
                )
                conn.commit()
                conn.close()

        elif action == "delete":
            match_id = int(request.form.get("match_id"))

            conn = get_db()
            cur = conn.cursor()

            # 경기 삭제
            cur.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            # 해당 경기의 신청 기록도 함께 삭제
            cur.execute("DELETE FROM applications WHERE match_id = ?", (match_id,))

            conn.commit()
            conn.close()

        # POST 처리 후에는 반드시 redirect만 하고 끝
        return redirect(url_for("admin"))

    # ✅ 여기부터는 GET 요청 처리
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches ORDER BY date ASC")
    rows = cur.fetchall()
    conn.close()

    return render_template("admin.html", matches=rows)

@app.route("/apply", methods=["GET", "POST"])
def apply():
    error_message = None

    if request.method == "POST":
        match_id = int(request.form.get("match_id"))
        seat = request.form.get("seat")
        name = request.form.get("name")
        organization = request.form.get("organization")

        if not name or not organization:
            error_message = "이름과 소속을 모두 입력해야 합니다."
        else:
            conn = get_db()
            cur = conn.cursor()

            # ✅ 중복 체크 (동일 경기 + 동일 이름 + 동일 소속)
            cur.execute("""
                SELECT COUNT(*)
                FROM applications
                WHERE match_id = ? AND name = ? AND organization = ?
            """, (match_id, name, organization))
            duplicated = cur.fetchone()[0]

            if duplicated:
                error_message = "이미 신청하셨습니다."
            else:
                # ✅ 경기 정보 조회
                cur.execute(
                    "SELECT date, opponent FROM matches WHERE id = ?",
                    (match_id,)
                )
                match = cur.fetchone()

                # ✅ 신청 저장
                cur.execute("""
                    INSERT INTO applications
                    (match_id, date, opponent, seat, name, organization)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    match_id,
                    match["date"],
                    match["opponent"],
                    seat,
                    name,
                    organization
                ))

                conn.commit()
                conn.close()
                return redirect(url_for("applications_list"))

    # ✅ GET 요청: 경기 목록 조회
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches ORDER BY date ASC")
    rows = cur.fetchall()
    conn.close()

    return render_template(
        "apply.html",
        matches=rows,
        error_message=error_message
    )


@app.route("/applications")
def applications_list():
    match_id = request.args.get("match_id", type=int)
    seat = request.args.get("seat")

    conn = get_db()
    cur = conn.cursor()

    if match_id and seat:
        cur.execute("""
            SELECT * FROM applications
            WHERE match_id = ? AND seat = ?
        """, (match_id, seat))
    elif match_id:
        cur.execute("""
            SELECT * FROM applications
            WHERE match_id = ?
        """, (match_id,))
    else:
        cur.execute("SELECT * FROM applications")

    rows = cur.fetchall()
    conn.close()

    return render_template(
        "applications.html",
        applications=rows,
        match_id=match_id
    )

@app.route("/applications/download")
def download_applications():
    headers = ["경기일자", "상대", "좌석", "이름", "소속"]

    rows = [
        [
            a["date"],
            a["opponent"],
            a["seat"],
            a["name"],
            a["organization"],
        ]
        for a in applications
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)

    csv_content = "\ufeff" + output.getvalue()

    return (
        csv_content,
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=applications.csv",
        }
    )

@app.route("/applications/delete", methods=["POST"])
def delete_application():
    app_id = int(request.form.get("application_id"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("applications_list"))

@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            m.id,
            m.date,
            m.opponent,
            SUM(CASE WHEN a.seat = 'Blue' THEN 1 ELSE 0 END) AS Blue,
            SUM(CASE WHEN a.seat = 'Red' THEN 1 ELSE 0 END) AS Red,
            SUM(CASE WHEN a.seat = 'Navy' THEN 1 ELSE 0 END) AS Navy
        FROM matches m
        LEFT JOIN applications a ON m.id = a.match_id
        GROUP BY m.id
        ORDER BY m.date ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", dashboard_data=rows)


if __name__ == "__main__":
    app.run(debug=True)