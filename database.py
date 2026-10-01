import os
import sqlite3
from contextlib import contextmanager

from data import MAJORS, QUESTIONS

# Lokasi file database. Bisa diganti lewat environment variable DATABASE_PATH.
DB_PATH = os.environ.get(
    "DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "jurusanku.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname   TEXT NOT NULL DEFAULT 'Pelajar',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    dim      TEXT NOT NULL,
    text     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS majors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    rumpun      TEXT NOT NULL,
    r INTEGER, i INTEGER, a INTEGER, s INTEGER, e INTEGER, c INTEGER,
    description TEXT, courses TEXT, careers TEXT,
    salary_min  REAL, salary_max REAL,
    pros TEXT, cons TEXT
);
CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    scores     TEXT NOT NULL,      -- JSON skor RIASEC (0-100)
    potentials TEXT NOT NULL,      -- JSON potensi radar (0-100)
    matches    TEXT NOT NULL,      -- JSON [[major_id, persen], ...] top 5
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bookmarks (
    user_id  INTEGER NOT NULL,
    major_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, major_id)
);
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    major_id    INTEGER NOT NULL,
    campus      TEXT NOT NULL,
    campus_type TEXT NOT NULL CHECK (campus_type IN ('PTN', 'PTS')),
    path        TEXT NOT NULL,
    note        TEXT DEFAULT ''
);
"""


@contextmanager
def get_db():
    """Buka koneksi, commit otomatis kalau sukses, selalu ditutup di akhir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)
        if db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
            db.executemany("INSERT INTO questions (category, dim, text) VALUES (?,?,?)", QUESTIONS)
        if db.execute("SELECT COUNT(*) FROM majors").fetchone()[0] == 0:
            for slug, name, rumpun, v, desc, courses, careers, sal, pros, cons in MAJORS:
                db.execute(
                    "INSERT INTO majors (slug,name,rumpun,r,i,a,s,e,c,description,courses,careers,"
                    "salary_min,salary_max,pros,cons) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (slug, name, rumpun, *v, desc, courses, careers, sal[0], sal[1], pros, cons),
                )
