# Agent Firewall

Zero-Trust Security Gateway for AI Agent Communications — a MITM proxy that intercepts MCP JSON-RPC traffic between AI Agents and Tool Servers using dual-layer analysis (L1 Static + L2 Semantic).

## Tech Stack

**Backend (Python 3.12+)**
- FastAPI + Uvicorn (async HTTP/WebSocket server)
- Pydantic v2 (data validation)
- ahocorasick-rs (Rust-backed pattern matching)
- orjson (fast JSON serialization)
- httpx (async HTTP client for LLM calls)

**Frontend (Vue 3 + TypeScript)**
- Vue 3 Composition API
- Vite 6 (build tool)
- TypeScript 5.7
- Native WebSocket + fetch API

## Project Structure

```
extensions/agent-firewall/
├── src/                          # Python backend
│   ├── main.py                   # FastAPI app entry (routes, lifespan, CORS)
│   ├── config.py                 # FirewallConfig (12-factor env vars)
│   ├── models.py                 # Pydantic domain models
│   ├── engine/                   # Dual analysis engine
│   │   ├── interceptor.py        # Core pipeline: parse → L1 → L2 → policy
│   │   ├── static_analyzer.py    # L1: Aho-Corasick + regex patterns
│   │   └── semantic_analyzer.py  # L2: LLM classifier (Mock + Live)
│   ├── proxy/                    # Transport adapters
│   │   ├── session_manager.py    # Session store (ring buffer, TTL GC)
│   │   ├── sse_adapter.py        # SSE + WebSocket proxy
│   │   ├── stdio_adapter.py      # stdio MITM proxy
│   │   └── openai_adapter.py     # OpenAI-compatible proxy
│   ├── audit/
│   │   └── logger.py             # Async batched JSONL writer
│   └── dashboard/
│       └── ws_handler.py         # WebSocket broadcast + HITL escalation
│
├── frontend/                     # Vue 3 dashboard SPA
│   └── src/
│       ├── main.ts               # Vue app bootstrap
│       ├── types.ts              # TypeScript types (mirrors Python models)
│       ├── composables.ts        # Vue 3 composables (7 total)
│       ├── App.vue               # Shell + hash-based router
│       └── components/           # 7 functional pages + Sidebar
│
├── tests/
│   ├── test_firewall.py          # Unit tests (24 cases, 5 classes)
│   └── red_team/
│       └── attack_simulation.py  # Adversarial scenarios (15 attacks)
│
├── Makefile                      # Build/run/test commands
├── pyproject.toml                # Python project metadata (PEP 621)
├── requirements.txt              # Pinned dependencies
└── .env                          # Environment config (gitignored)
```

## Key Directories

- **src/engine/** — Dual analysis engine (L1 static + L2 semantic), policy enforcement
- **src/proxy/** — Transport adapters (SSE, WebSocket, stdio), session management
- **src/audit/** — Security event logging (async JSONL writer)
- **src/dashboard/** — Real-time monitoring WebSocket hub
- **frontend/src/components/** — 7 Vue SFC pages (Dashboard, Traffic, Rules, Engine, RateLimit, Test, Audit)
- **tests/** — Unit tests + red team attack simulation

## Essential Commands

```bash
# Backend development (hot-reload on port 9090)
cd extensions/agent-firewall
source .venv/bin/activate
make dev

# Frontend development (hot-reload on port 9091)
cd extensions/agent-firewall/frontend
npx vite --port 9091 --host

# Run tests
make test              # Unit tests (pytest)
make attack            # Red team simulation (15 scenarios)

# Code quality
make lint              # ruff check
make fmt               # ruff format

# Production
make run               # 4 workers
cd frontend && npm run build
```

## Configuration

All settings via environment variables (12-factor). See `.env` file or README.md:302-360 for full reference.

Key variables:
- `AF_LISTEN_PORT` (default: 9090) — Firewall proxy port
- `AF_UPSTREAM_HOST/PORT` — Target MCP server
- `AF_L1_ENABLED` / `AF_L2_ENABLED` — Toggle analysis layers
- `AF_L2_MODEL_ENDPOINT` / `AF_L2_API_KEY` — LLM backend for L2
- `AF_AUDIT_LOG` — Audit log path

## Additional Documentation

For specialized topics, see:
- [Architectural Patterns](.claude/docs/architectural_patterns.md) — Design decisions, conventions, patterns used across the codebase

## Key Files Reference

**Core Pipeline:**
- src/engine/interceptor.py:77 — `_compute_verdict()` decision matrix
- src/engine/interceptor.py:54 — High-risk methods list
- src/engine/static_analyzer.py — L1 Aho-Corasick automaton
- src/engine/semantic_analyzer.py — L2 LLM classifier

**API Entry:**
- src/main.py:66 — AppState singleton
- src/main.py — FastAPI routes and lifespan

**Frontend State:**
- frontend/src/composables.ts:36 — `useWebSocket()` composable
- frontend/src/App.vue:2 — Root component with theme support

**Configuration:**
- src/config.py:24 — FirewallConfig dataclass
- src/models.py:29 — JsonRpcRequest model

**IMPORTANT**: When you work on a new feature or bug, create a git branch first. Then work on changes in that branch for the remainder of session.
