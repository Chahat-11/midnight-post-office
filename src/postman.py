import os, time, socket
import psycopg2, redis

MAILROOM = os.environ.get("MAILROOM", "/var/mailroom")
DELAY    = int(os.environ.get("DELIVERY_DELAY", "4"))
ME       = socket.gethostname()

def secret(name, default=""):
    path = os.environ.get(f"{name}_FILE")
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name, default)

def db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"], password=secret("POSTGRES_PASSWORD"),
        connect_timeout=3)

r = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, decode_responses=True)

print(f"🚴 postman {ME} clocking in — delay {DELAY}s, mailroom {MAILROOM}", flush=True)

while True:
    job = r.brpop("outbox", timeout=5)      # blocks until a letter arrives
    if not job:
        continue
    letter_id = job[1]
    print(f"📨 {ME} picked up letter #{letter_id}", flush=True)
    time.sleep(DELAY)                        # the long midnight bicycle ride 🌙
    with db() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE letters SET status='delivered', delivered_at=now(),
                       delivered_by=%s WHERE id=%s RETURNING note""", (ME, letter_id))
        row = cur.fetchone()
    if row:
        os.makedirs(MAILROOM, exist_ok=True)
        with open(os.path.join(MAILROOM, f"letter-{letter_id}.txt"), "w") as f:
            f.write(row[0])
        print(f"✅ {ME} delivered #{letter_id}", flush=True)