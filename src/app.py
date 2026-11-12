import os
import socket
from flask import Flask, request, redirect, render_template, jsonify
import psycopg2
import redis

app = Flask(__name__)
VERSION = os.environ.get("APP_VERSION", "unknown")   # ← comes from a build ARG 👀
MAILROOM = os.environ.get("MAILROOM", "/var/mailroom")
MAX_NOTE = 200
_schema_ready = False


def secret(name, default=""):
    # Reads NAME_FILE (a Docker secret) if present, else falls back to NAME.
    # This is the standard pattern — you'll use both halves of it in Part 3.
    path = os.environ.get(f"{name}_FILE")
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name, default)


def db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=secret("POSTGRES_PASSWORD"),
        connect_timeout=3,
    )


def queue():
    return redis.Redis(host=os.environ["REDIS_HOST"], port=6379, decode_responses=True)


def init_db():
    # Only needs to succeed once per process — skip the round-trip after that.
    global _schema_ready
    if _schema_ready:
        return
    with db() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS letters (
            id SERIAL PRIMARY KEY,
            note TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            written_at TIMESTAMPTZ DEFAULT now(),
            delivered_at TIMESTAMPTZ,
            delivered_by TEXT
        )""")
    _schema_ready = True


def snapshot():
    # Everything the page shows, gathered defensively so one dead service
    # degrades the page instead of crashing it.
    letters, db_ok = [], True
    try:
        init_db()
        conn = db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""SELECT id, note, status, delivered_by, written_at, delivered_at
                               FROM letters ORDER BY id DESC LIMIT 25""")
                rows = cur.fetchall()
        finally:
            conn.close()
        letters = [{
            "id": i,
            "note": note,
            "delivered": status == "delivered",
            "delivered_by": by,
            "written_at": w.isoformat() if w else None,
            "delivered_at": d.isoformat() if d else None,
        } for i, note, status, by, w, d in rows]
    except Exception:
        db_ok = False

    try:
        qlen = queue().llen("outbox")
    except Exception:
        qlen = None
    try:
        mail = len(os.listdir(MAILROOM))
    except Exception:
        mail = None

    return {
        "version": VERSION,
        "host": socket.gethostname(),
        "db_ok": db_ok,
        "queue": qlen,
        "mailroom": mail,
        "letters": letters,
    }


def wants_json():
    return request.headers.get("Accept", "").startswith("application/json")


@app.route("/")
def home():
    return render_template("index.html", s=snapshot(), max_note=MAX_NOTE)


@app.route("/api/letters")
def api_letters():
    return jsonify(snapshot())


@app.route("/send", methods=["POST"])
def send():
    note = request.form.get("note", "").strip()[:MAX_NOTE]
    if not note:
        if wants_json():
            return jsonify(error="your letter is empty"), 400
        return redirect("/", code=303)
    try:
        init_db()
        with db() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO letters (note) VALUES (%s) RETURNING id", (note,))
            letter_id = cur.fetchone()[0]
        queue().lpush("outbox", letter_id)   # ← hand off to the postman 📬
    except Exception:
        if wants_json():
            return jsonify(error="the post office is closed right now — try again soon"), 503
        return redirect("/", code=303)
    if wants_json():
        return jsonify(id=letter_id), 201
    return redirect("/", code=303)


@app.route("/healthz")
def healthz():
    # You will point a healthcheck at this. It must touch BOTH dependencies.
    db().close()
    queue().ping()
    return "ok\n", 200


@app.route("/whoami")
def whoami():
    return f"api container: {socket.gethostname()} (v{VERSION})\n"


@app.route("/mailroom")
def mailroom():
    # Proves the shared volume works — these files were written by a DIFFERENT container.
    try:
        return "\n".join(sorted(os.listdir(MAILROOM))) + "\n"
    except Exception as e:
        return f"mailroom unreadable: {e}\n", 500


@app.route("/tamper")
def tamper():
    # Part 3 checks this fails! The api must NOT be able to write to the mailroom.
    try:
        with open(os.path.join(MAILROOM, "api-was-here.txt"), "w") as f:
            f.write("oops")
        return "WROTE — mailroom is not read-only ❌\n", 200
    except Exception as e:
        return f"blocked ✅ ({type(e).__name__})\n", 403
