# 📮 The Midnight Post Office

A production-style **letter-delivery system** demonstrating containerized architecture, async job processing, and security best practices using Docker Compose.

## What It Is

**The Midnight Post Office** is a learning project that models a real-world distributed system where:
- Users send letters through a **web API**
- Letters are queued asynchronously
- A **background worker** processes deliveries
- Results are persisted and served back to users

It's designed to showcase modern DevOps and software engineering patterns in a small, understandable package.

---

## Architecture

```
┌─────────────┐
│  Browser 🌐 │
└──────┬──────┘
       │ HTTP :8080
       ↓
┌───────────────────┐
│  Nginx Proxy      │ ← Public interface
│  (nginx:1.25)     │
└──────┬────────────┘
       │ internal network
       ↓
┌──────────────────────────────────────────────┐
│           Internal Services                  │
│                                              │
│  ┌────────────────┐         ┌──────────────┐ │
│  │  Flask API     │◄───────►│  PostgreSQL  │ │
│  │  (gunicorn)    │         │  Database    │ │
│  │  :5000         │         │  :5432       │ │
│  └────────┬───────┘         └──────────────┘ │
│           │ queue job                        │
│           ↓                                  │
│  ┌────────────────┐                          │
│  │  Redis Queue   │                          │
│  │  (redis:7)     │                          │
│  │  :6379         │                          │
│  └────────┬───────┘                          │
│           │ BLPOP outbox                     │
│           ↓                                  │
│  ┌────────────────────────────┐              │
│  │  Postman Worker            │              │
│  │  (same image as API)       │              │
│  │  Long-running delivery loop│              │
│  └────────┬───────────────────┘              │
│           │ write files                      │
│           ↓                                  │
│  ┌────────────────────────────┐              │
│  │  Mailroom (Shared Volume)  │              │
│  │  Delivery records          │              │
│  └────────────────────────────┘              │
└──────────────────────────────────────────────┘
```

---

## Services Explained

### 🌐 **Nginx Proxy** (`nginx:1.25-alpine`)
- **Role**: Public gateway and reverse proxy
- **Exposes**: Port `8080` to the host
- **Isolates**: Internal services from direct access
- **Benefits**: Load balancing, caching, security boundary

### 🐍 **Flask API** (`midnight-post-office:latest`)
- **Role**: HTTP server handling user requests
- **Endpoints**:
  - `GET /` – Display pending/delivered letters
  - `POST /send` – Queue a letter for delivery
  - `GET /mailroom` – View delivered letter files
  - `GET /healthz` – Health check
- **Runs as**: Non-root `postie` user
- **Database**: PostgreSQL (psycopg2)
- **Queue**: Redis (python-redis)

### 🚴 **Postman Worker** (`midnight-post-office:latest`)
- **Role**: Background job processor
- **Task**: Blocks on Redis `BLPOP`, waits for delivery jobs, simulates delivery delay, marks as delivered
- **Writes**: Letter files to shared mailroom volume
- **Delay**: Configurable via `DELIVERY_DELAY` env var

### 🗄️ **PostgreSQL** (`postgres:16-alpine`)
- **Role**: Persistent data store
- **Schema**: Letters table with status tracking (pending → delivered)
- **Security**: Password via Docker secret (not in env var)
- **Isolation**: Only accessible from API/Postman on internal network

### 🔴 **Redis** (`redis:7-alpine`)
- **Role**: Message queue for job processing
- **Queue**: `outbox` list stores letter IDs
- **Pattern**: FIFO blocking queue for reliable job dispatch
- **Isolation**: Only accessible internally

### 📁 **Mailroom** (Docker Volume)
- **Role**: Shared storage between API and Postman
- **Mounted**: Read-only for API (cannot tamper)
- **Contains**: `letter-{id}.txt` files created by Postman
- **Purpose**: Demonstrates inter-container volume sharing

---

## How It Works (Happy Path)

```
1. User writes a letter in the browser
   └─> POST /send with note text

2. API stores letter in database
   └─> INSERT INTO letters (note, status='pending')
   └─> Pushes letter ID to Redis: RPUSH outbox {id}

3. Postman worker picks up job
   └─> BLPOP outbox (blocks until job available)
   └─> Simulates delivery (sleep DELIVERY_DELAY seconds)

4. Postman marks as delivered
   └─> UPDATE letters SET status='delivered', delivered_by='{hostname}'
   └─> Writes letter content: /var/mailroom/letter-{id}.txt

5. Browser auto-refreshes (meta refresh)
   └─> Shows letter as "delivered by {postman-hostname}"
   └─> /mailroom endpoint shows shared files
```

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Bash (for `check.sh`)

### Quick Start

```bash
# Start the entire stack
docker compose up -d --build

# Run the self-check (validates all requirements)
./check.sh

# Open in browser
open http://localhost:8080
```

### Services Status
```bash
# View running services
docker compose ps

# View logs
docker compose logs -f

# Stop everything
docker compose down
```


## Key Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Web Server | Nginx | 1.25-alpine |
| Application | Flask | 3.0.3 |
| App Server | Gunicorn | 22.0.0 |
| Database | PostgreSQL | 16-alpine |
| Queue | Redis | 7-alpine |
| ORM/Driver | psycopg2-binary | 2.9.9 |
| Python | Python | 3.12-slim |

