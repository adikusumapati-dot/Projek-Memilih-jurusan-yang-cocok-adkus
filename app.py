import json
import os
from datetime import timedelta

from flask import Flask, abort, jsonify, render_template, request, session

from data import DIM_NAMES, DIM_SHORT, DIMS, GROWTH, JALUR, POTENTIALS, RUMPUN
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-ganti-di-produksi")
app.permanent_session_lifetime = timedelta(days=365)
init_db()


# ---------- Helper: pengguna anonim berbasis session ----------
def current_uid():
    return session.get("uid")


def ensure_uid():
    uid = session.get("uid")
    with get_db() as db:
        if uid and db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
            return uid
        uid = db.execute("INSERT INTO users (nickname) VALUES ('Pelajar')").lastrowid
    session["uid"] = uid
    session.permanent = True
    return uid


def saved_ids(uid):
    if not uid:
        return set()
    with get_db() as db:
        rows = db.execute("SELECT major_id FROM bookmarks WHERE user_id=?", (uid,)).fetchall()
    return {r["major_id"] for r in rows}


def latest_result(uid):
    if not uid:
        return None
    with get_db() as db:
        return db.execute(
            "SELECT id, scores FROM results WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)
        ).fetchone()


# ---------- Algoritma kecocokan ----------
def pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5
    return num / den if den else 0.0


def match_pct(profile, major):
    """Korelasi Pearson antara profil siswa (R,I,A,S,E,C) dan profil jurusan, diubah ke 0-100%."""
    vec = [major[k.lower()] for k in DIMS]
    return round((pearson(profile, vec) + 1) / 2 * 100)


# ---------- Halaman ----------
@app.route("/")
def index():
    last = latest_result(current_uid())
    with get_db() as db:
        n_major = db.execute("SELECT COUNT(*) FROM majors").fetchone()[0]
    return render_template("index.html", last=last, n_major=n_major)


@app.route("/quiz")
def quiz():
    with get_db() as db:
        qs = [dict(q) for q in db.execute("SELECT id, category, text FROM questions ORDER BY id")]
    return render_template("quiz.html", questions=qs)


@app.get("/result/<int:rid>")
def result(rid):
    with get_db() as db:
        r = db.execute(
            "SELECT r.*, u.nickname FROM results r JOIN users u ON u.id = r.user_id WHERE r.id=?", (rid,)
        ).fetchone()
        if not r:
            abort(404)
        matches = json.loads(r["matches"])
        ids = [m[0] for m in matches]
        rows = {
            m["id"]: dict(m)
            for m in db.execute(
                f"SELECT * FROM majors WHERE id IN ({','.join('?' * len(ids))})", ids
            ).fetchall()
        }
    scores = json.loads(r["scores"])
    code = "".join(sorted(DIMS, key=lambda k: -scores[k])[:3])
    return render_template(
        "result.html",
        nickname=r["nickname"],
        scores=scores,
        potentials=json.loads(r["potentials"]),
        code=code,
        top=[(rows[i], pct) for i, pct in matches],
        saved=saved_ids(current_uid()),
        dim_names=DIM_NAMES,
        dim_short=DIM_SHORT,
        dims=DIMS,
    )


@app.get("/explore")
def explore():
    q = request.args.get("q", "").strip()
    rumpun = request.args.get("rumpun", "")
    sql, params = "SELECT * FROM majors WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR careers LIKE ? OR description LIKE ? OR courses LIKE ?)"
        params += [f"%{q}%"] * 4
    if rumpun in RUMPUN:
        sql += " AND rumpun=?"
        params.append(rumpun)
    with get_db() as db:
        majors = [dict(m) for m in db.execute(sql + " ORDER BY name", params)]
    return render_template(
        "explore.html", majors=majors, q=q, rumpun=rumpun, rumpun_list=RUMPUN, saved=saved_ids(current_uid())
    )


@app.get("/major/<slug>")
def major(slug):
    uid = current_uid()
    with get_db() as db:
        m = db.execute("SELECT * FROM majors WHERE slug=?", (slug,)).fetchone()
        if not m:
            abort(404)
        m = dict(m)
        targets = []
        if uid:
            targets = [
                dict(t)
                for t in db.execute(
                    "SELECT * FROM targets WHERE user_id=? AND major_id=? ORDER BY id DESC", (uid, m["id"])
                )
            ]
    sim = {
        "labels": ["Fresh grad"] + [f"{y} tahun" for y, _ in GROWTH[1:]],
        "min": [round(m["salary_min"] * g, 1) for _, g in GROWTH],
        "max": [round(m["salary_max"] * g, 1) for _, g in GROWTH],
    }
    return render_template(
        "major.html", m=m, sim=sim, targets=targets, jalur=JALUR, saved=m["id"] in saved_ids(uid)
    )


@app.get("/compare")
def compare():
    with get_db() as db:
        allm = [dict(m) for m in db.execute("SELECT * FROM majors ORDER BY name")]
    by_id = {m["id"]: m for m in allm}
    a = by_id.get(request.args.get("a", type=int))
    b = by_id.get(request.args.get("b", type=int))
    me = None
    res = latest_result(current_uid())
    if res:
        scores = json.loads(res["scores"])
        me = [scores[k] for k in DIMS]
        for m in (a, b):
            if m:
                m["match"] = match_pct(me, m)
    return render_template(
        "compare.html", allm=allm, a=a, b=b, me=me, labels=[DIM_SHORT[k] for k in DIMS], dims=DIMS
    )


@app.get("/saved")
def saved():
    uid = current_uid()
    majors, targets = [], []
    if uid:
        with get_db() as db:
            majors = [
                dict(m)
                for m in db.execute(
                    "SELECT m.* FROM bookmarks b JOIN majors m ON m.id = b.major_id "
                    "WHERE b.user_id=? ORDER BY b.rowid DESC", (uid,)
                )
            ]
            targets = [
                dict(t)
                for t in db.execute(
                    "SELECT t.*, m.name AS major_name, m.slug FROM targets t JOIN majors m ON m.id = t.major_id "
                    "WHERE t.user_id=? ORDER BY t.id DESC", (uid,)
                )
            ]
    return render_template("saved.html", majors=majors, targets=targets)


# ---------- API ----------
@app.post("/api/quiz/submit")
def submit_quiz():
    d = request.get_json(silent=True) or {}
    answers = d.get("answers") or {}
    nickname = (d.get("nickname") or "").strip()[:30] or "Pelajar"
    with get_db() as db:
        qs = db.execute("SELECT id, dim FROM questions").fetchall()
        majors = db.execute("SELECT * FROM majors").fetchall()

    by_dim = {k: [] for k in DIMS}
    for q in qs:
        try:
            v = int(answers.get(str(q["id"])))
        except (TypeError, ValueError):
            return jsonify(error="Jawaban belum lengkap."), 400
        if not 1 <= v <= 5:
            return jsonify(error="Jawaban tidak valid."), 400
        by_dim[q["dim"]].append(v)

    scores = {k: round((sum(v) / len(v) - 1) / 4 * 100) for k, v in by_dim.items()}
    profile = [scores[k] for k in DIMS]
    potentials = {n: round(sum(scores[k] * w for k, w in ws.items())) for n, ws in POTENTIALS.items()}
    ranked = sorted(((m["id"], match_pct(profile, m)) for m in majors), key=lambda x: -x[1])[:5]

    uid = ensure_uid()
    with get_db() as db:
        db.execute("UPDATE users SET nickname=? WHERE id=?", (nickname, uid))
        rid = db.execute(
            "INSERT INTO results (user_id, scores, potentials, matches) VALUES (?,?,?,?)",
            (uid, json.dumps(scores), json.dumps(potentials), json.dumps(ranked)),
        ).lastrowid
    return jsonify(id=rid)


@app.post("/api/bookmark/<int:mid>")
def toggle_bookmark(mid):
    uid = ensure_uid()
    with get_db() as db:
        if not db.execute("SELECT 1 FROM majors WHERE id=?", (mid,)).fetchone():
            return jsonify(error="Jurusan tidak ditemukan."), 404
        exists = db.execute(
            "SELECT 1 FROM bookmarks WHERE user_id=? AND major_id=?", (uid, mid)
        ).fetchone()
        if exists:
            db.execute("DELETE FROM bookmarks WHERE user_id=? AND major_id=?", (uid, mid))
        else:
            db.execute("INSERT INTO bookmarks (user_id, major_id) VALUES (?,?)", (uid, mid))
    return jsonify(saved=not exists)


@app.post("/api/targets")
def add_target():
    d = request.get_json(silent=True) or {}
    campus = (d.get("campus") or "").strip()[:100]
    note = (d.get("note") or "").strip()[:200]
    try:
        mid = int(d.get("major_id"))
    except (TypeError, ValueError):
        return jsonify(error="Jurusan tidak valid."), 400
    if not campus or d.get("campus_type") not in ("PTN", "PTS") or d.get("path") not in JALUR:
        return jsonify(error="Nama kampus, tipe, dan jalur masuk wajib diisi."), 400
    uid = ensure_uid()
    with get_db() as db:
        if not db.execute("SELECT 1 FROM majors WHERE id=?", (mid,)).fetchone():
            return jsonify(error="Jurusan tidak ditemukan."), 404
        tid = db.execute(
            "INSERT INTO targets (user_id, major_id, campus, campus_type, path, note) VALUES (?,?,?,?,?,?)",
            (uid, mid, campus, d["campus_type"], d["path"], note),
        ).lastrowid
    return jsonify(id=tid), 201


@app.delete("/api/targets/<int:tid>")
def delete_target(tid):
    with get_db() as db:
        db.execute("DELETE FROM targets WHERE id=? AND user_id=?", (tid, current_uid() or 0))
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
