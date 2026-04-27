# MOCA — My Only Capable Assistant

> *"At your service."*

MOCA is a fully autonomous, self-growing AI ecosystem built for one person. It is not an app or a chatbot — it is a personal AI infrastructure that listens, sees, thinks, acts, and grows continuously.

---

## What MOCA Is

Most AI assistants are tools you open and close. MOCA is different — it runs continuously on your own private server, connects to all your devices, learns everything about you over time, and builds new capabilities autonomously when it encounters something it cannot do yet.

The closest reference point is JARVIS from the MCU. That is the design target.

---

## Current Status

| Phase | Name | Status |
|---|---|---|
| 1 | The Brain | ✅ Complete |
| 2 | The Agent Society | ✅ Complete |
| 3 | The Memory Layer | ✅ Complete |
| 4 | The Services Layer | 🔲 Upcoming |
| 5 | The Context Engine | 🔲 Upcoming |
| 6 | The Voice | 🔲 Upcoming |
| 7 | The Desktop Client | 🔲 Upcoming |
| 8 | The Panels | 🔲 Upcoming |
| 9 | The Eyes | 🔲 Upcoming |
| 10 | The Hands | 🔲 Upcoming |
| 11 | The ACE | 🔲 Upcoming |
| 12 | The Connections | 🔲 Upcoming |
| 13 | CRONOS | 🔲 Upcoming |
| 14 | The Body | 🔲 Upcoming |
| 15 | AEGIS | 🔲 Upcoming |
| 16 | The Mobile | 🔲 Upcoming |
| 17 | The Home | 🔲 Upcoming |
| 18 | Oracle Deploy | 🔲 Upcoming |

---

## Architecture

```
Oracle Server (Production) / Mac (Development)
├── Brain — Gemma 4 via Ollama (prod) / Cerebras API (dev)
├── Orchestration — LangGraph + LangChain
├── Agent Society — 10 specialist agents
├── Memory — pgvector + PostgreSQL + Redis + Neo4j
├── Services — Ecosystem-owned core services
└── API — FastAPI + WebSocket

Clients
├── Desktop — Tauri (macOS, Windows, Linux)
├── Mobile — React Native (Android)
└── Tray only — no dock icon, no taskbar presence
```

---

## The Agent Society

| Agent | Domain |
|---|---|
| **MOCA Prime** | Master supervisor — routes all tasks |
| **HERMES** | Communications — email, calls, messages |
| **ATHENA** | Research and analysis |
| **VULCAN** | Code and building |
| **APOLLO** | Vision and health |
| **AEGIS** | Security and privacy |
| **MERCURY** | Automation, timers, scheduling |
| **HESTIA** | Smart home and environment |
| **CRONOS** | Proactive background intelligence |
| **MNEMOSYNE** | Memory and learning |

---

## Key Design Principles

**Brain agnostic** — swap the LLM with one environment variable. No code changes.

**ACE-first** — MOCA builds new capabilities autonomously when it encounters something it cannot do. Nothing is hardcoded beyond the foundation.

**Ecosystem-owned services** — timers, alarms, notifications, and all core services live on MOCA's infrastructure, not on device-native APIs. Devices are terminals.

**Omnipresent** — tray icon on desktop, floating orb on mobile, always listening, always thinking.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Brain (dev) | Cerebras API |
| Brain (prod) | Gemma 4 via Ollama |
| Orchestration | LangGraph |
| Tools | LangChain |
| API | FastAPI |
| Real-time | WebSocket + SSE |
| Vector search | pgvector |
| Cache | Redis |
| Database | PostgreSQL |
| Graph | Neo4j (Phase 3+) |
| Embeddings | sentence-transformers (local) |
| Desktop | Tauri 2.0 |
| Mobile | React Native |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+
- Rust (for Tauri desktop client)

### Setup

```bash
# Clone
git clone https://github.com/deniedhash/mocaai.git
cd mocaai/server

# Environment
cp .env.example .env
# Add your API key to .env

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start databases
docker-compose up -d

# Run migrations
alembic upgrade head

# Start MOCA
PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify

```bash
curl http://localhost:8000/moca/health

curl -X POST http://localhost:8000/moca/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Who are you?", "session_id": "test-001"}'
```

---

## Environment Variables

See `server/.env.example` for the full list. Key variables:

```env
BRAIN_PROVIDER=cerebras        # or ollama
BRAIN_MODEL=llama3.1-8b
BRAIN_API_KEY=your_key_here
BRAIN_BASE_URL=https://api.cerebras.ai/v1
```

Swapping the brain is a one-line change in `.env`. No code changes required.

---

## Project Structure

```
mocaai/
└── server/
    ├── agents/          # 10 specialist agents
    ├── api/             # FastAPI server + WebSocket
    ├── core/            # Brain, orchestrator, memory, context
    ├── memory/          # Vector store, episodic, knowledge graph
    ├── services/        # Ecosystem-owned core services
    ├── tools/           # LangChain tools
    ├── alembic/         # Database migrations
    └── docker-compose.yml
```

---

*MOCA is a personal project. It is not a product.*
