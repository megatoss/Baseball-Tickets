from flask import Flask, render_template, request, redirect, url_for
import csv
import io
import sqlite3

# =========================
# DB Utils
# =========================
def get_db():
    conn = sqlite3.connect("ticket.db")
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# 신청제한 설정
# =========================
def get_apply_restriction_enabled():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT value
        FROM settings
        WHERE key = 'apply_restriction_enabled'
    """)
    row = cur.fetchone()
    conn.close()

    if row is None:
        return True  # 기본값: 신청제한 ON
    return row["value"] == "true"


def set_apply_restriction_enabled(enabled: bool):
    conn = get_db()
    cur = conn.cursor()
    value = "true" if enabled else "false"

    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES ('apply_restriction_enabled', ?)
        ON CONFLICT(key) DO UPDATE SET value = ?
    """, (value, value))

    conn.commit()
    conn.close()


# =========================
# Flask App
# =========================
app = Flask(__name__)


# =========================
# Dashboard (메인 / 신청현황)
# =========================
@app.route("/")
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


# =========================
# Admin (경기 관리)
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        action = request.form.get("action")

        conn = get_db()
        cur = conn.cursor()

        if action == "add":
            match_date = request.form.get("match_date")
            opponent = request.form.get("opponent")

            if match_date and opponent:
                cur.execute(
                    "INSERT INTO matches (date, opponent) VALUES (?, ?)",
                    (match_date, opponent)
                )

        elif action == "delete":
            match_id = int(request.form.get("match_id"))
            cur.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            cur.execute("DELETE FROM applications WHERE match_id = ?", (match_id,))

        conn.commit()
        conn.close()
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches ORDER BY date ASC")
    rows = cur.fetchall()
    conn.close()

    return render_template("admin.html", matches=rows)


# =========================
# Apply (신청)
# =========================
@app.route("/apply", methods=["GET", "POST"])
def apply():
    error_message = None
    restriction_enabled = get_apply_restriction_enabled()

    if request.method == "POST":
        match_id = int(request.form.get("match_id"))
        seat = request.form.get("seat")
        name = request.form.get("name")
        organization = request.form.get("organization")

        if not name or not organization or not seat:
            error_message = "이름, 소속, 좌석을 모두 입력해야 합니다."
        else:
            conn = get_db()
            cur = conn.cursor()

            if restriction_enabled:
                # 같은 날짜에는 하나만 신청 가능
                cur.execute("""
                    SELECT COUNT(*)
                    FROM applications
                    WHERE name = ?
                      AND organization = ?
                      AND match_id = ?
                """, (name, organization, match_id))

                if cur.fetchone()[0] > 0:
                    error_message = "같은 날짜에는 좌석을 하나만 신청할 수 있습니다."

                # 좌석은 날짜와 무관하게 1회
                if error_message is None:
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM applications
                        WHERE name = ?
                          AND organization = ?
                          AND seat = ?
                    """, (name, organization, seat))

                    if cur.fetchone()[0] > 0:
                        error_message = (
                            "이미 해당 좌석을 신청하셨습니다. "
                            "좌석별 신청은 1회만 가능합니다."
                        )

            if error_message is None:
                cur.execute(
                    "SELECT date, opponent FROM matches WHERE id = ?",
                    (match_id,)
                )
                match = cur.fetchone()

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
                return redirect(url_for("apply", success=1))

            conn.close()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM matches ORDER BY date ASC")
    rows = cur.fetchall()
    conn.close()

    return render_template(
        "apply.html",
        matches=rows,
        error_message=error_message,
        restriction_enabled=restriction_enabled
    )


# =========================
# 신청제한 토글
# =========================
@app.route("/admin/toggle-restriction", methods=["POST"])
def toggle_restriction():
    password = request.form.get("password")

    if password != "1233":
        return redirect(url_for("apply", error="pw"))

    current_enabled = get_apply_restriction_enabled()
    set_apply_restriction_enabled(not current_enabled)

    return redirect(url_for("apply"))


# =========================
# 신청 내역 조회
# =========================
@app.route("/applications")
def applications_list():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM applications")
    rows = cur.fetchall()
    conn.close()

    return render_template("applications.html", applications=rows)


# =========================
# 신청 내역 CSV 다운로드
# =========================
@app.route("/applications/download")
def download_applications():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT date, opponent, seat, name, organization FROM applications")
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["경기일자", "상대", "좌석", "이름", "소속"])
    for r in rows:
        writer.writerow([r["date"], r["opponent"], r["seat"], r["name"], r["organization"]])

    csv_content = "\ufeff" + output.getvalue()

    return (
        csv_content,
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=applications.csv",
        }
    )


# =========================
# 신청 취소 (비밀번호 검증)
# =========================
@app.route("/applications/delete", methods=["POST"])
def delete_application():
    app_id = int(request.form.get("application_id"))
    password = request.form.get("cancel_password")

    if password != "1233":
        return redirect(url_for("applications_list", error="pw"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("applications_list", canceled=1))


# =========================
# Run
# =========================
if __name__ == "__main__":
    app.run()