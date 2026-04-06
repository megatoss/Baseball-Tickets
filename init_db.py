import sqlite3

conn = sqlite3.connect("ticket.db")
cur = conn.cursor()

# 경기 테이블
cur.execute("""
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    opponent TEXT NOT NULL
)
""")

# 신청 테이블
cur.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    opponent TEXT NOT NULL,
    seat TEXT NOT NULL,
    name TEXT NOT NULL,
    organization TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("DB 초기화 완료")
