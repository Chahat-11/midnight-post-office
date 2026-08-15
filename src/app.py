import os, socket
from flask import Flask, request, redirect
import psycopg2, redis

app = Flask(__name__)
VERSION  = os.environ.get("APP_VERSION", "unknown")   # ← comes from a build ARG 👀
MAILROOM = os.environ.get("MAILROOM", "/var/mailroom")

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
    with db() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS letters (
            id SERIAL PRIMARY KEY,
            note TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            written_at TIMESTAMPTZ DEFAULT now(),
            delivered_at TIMESTAMPTZ,
            delivered_by TEXT
        )""")

PAGE = """<!DOCTYPE html><html><head><title>Midnight Post Office</title>
<meta http-equiv="refresh" content="4">
<style>
 body{font-family:Georgia,serif;background:#1e1b2e;color:#f0e6f5;max-width:640px;
      margin:40px auto;padding:0 20px}
 h1{color:#ffc4dd;text-align:center;font-weight:400}
 .bar{text-align:center;color:#9c8bab;font-size:.8rem;margin-bottom:20px}
 form{display:flex;gap:10px;margin:22px 0}
 input{flex:1;padding:12px;border:1px solid #4a3f5c;border-radius:10px;
       background:#2a2136;color:#f0e6f5;font-size:1rem}
 button{background:#d05f86;color:#fff;border:0;border-radius:10px;padding:12px 20px;cursor:pointer}
 li{list-style:none;background:#2a2136;border-radius:10px;padding:12px 16px;margin-bottom:9px;
    border-left:3px solid #4a3f5c}
 li.delivered{border-left-color:#4e9c85}
 small{color:#9c8bab}
 .tag{float:right;font-size:.7rem;padding:2px 9px;border-radius:99px}
 .pending{background:#5a4a20;color:#ffd98a}
 .done{background:#1f4a3c;color:#8ce0c0}
</style></head><body>
<h1>📮 The Midnight Post Office</h1>
<div class="bar">v__VER__ · served by __HOST__ · queue: __Q__ · mailroom: __MAIL__ files</div>
<form action="/send" method="post">
  <input name="note" placeholder="write a letter for the midnight post…" maxlength="200" required>
  <button>post it 📮</button>
</form>
<ul>__ITEMS__</ul>
<p class="bar">this page refreshes itself — watch pending letters turn delivered 🌙</p>
</body></html>"""

@app.route("/")
def home():
    try:
        init_db()
        with db() as conn, conn.cursor() as cur:
            cur.execute("""SELECT id, note, status, delivered_by
                           FROM letters ORDER BY id DESC LIMIT 25""")
            rows = cur.fetchall()
    except Exception:
        rows = []

    try:
        qlen = queue().llen("outbox")
    except Exception:
        qlen = "unreachable ❌"
    try:
        mail = len(os.listdir(MAILROOM))
    except Exception:
        mail = "no mailroom ❌"

    items = ""
    for i, note, status, by in rows:
        cls = "delivered" if status == "delivered" else ""
        tag = (f'<span class="tag done">delivered by {by}</span>' if status == "delivered"
               else '<span class="tag pending">in transit</span>')
        items += f'<li class="{cls}">{tag}#{i} — {note}</li>'
    items = items or "<li>the post office is empty… send something 💌</li>"

    return (PAGE.replace("__ITEMS__", items).replace("__VER__", VERSION)
                .replace("__HOST__", socket.gethostname())
                .replace("__Q__", str(qlen)).replace("__MAIL__", str(mail)))

@app.route("/send", methods=["POST"])
def send():
    note = request.form.get("note", "").strip()
    if note:
        init_db()
        with db() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO letters (note) VALUES (%s) RETURNING id", (note,))
            letter_id = cur.fetchone()[0]
        queue().lpush("outbox", letter_id)   # ← hand off to the postman 📬
    return redirect("/")

@app.route("/healthz")
def healthz():
    # You will point a healthcheck at this. It must touch BOTH dependencies.
    db().close(); queue().ping()
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