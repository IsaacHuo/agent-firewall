# Agent Firewall — Zero-Trust Agent Communication Security Gateway

> Non-invasive MITM proxy for the OpenClaw ecosystem that intercepts, analyzes,
> and enforces security policies on all MCP JSON-RPC traffic between Agents and
> Tool Servers.

## Architecture

```
Agent A ──┐                                    ┌── fs (File System)
Agent B ──┤  JSON-RPC   ┌──────────────────┐   ├── shell (Executor)
Agent N ──┴────────────→│  AGENT FIREWALL  │───┤── fetch (HTTP)
                        │  ┌──────┐ ┌────┐ │   └── db (Database)
              ┌─────────│  │  L1  │→│ L2 │ │
              │         │  │Static│ │Sem.│ │
              │         │  └──────┘ └────┘ │
              │         │     ↓ Policy ↓   │
   Dashboard ←┤         │  ALLOW│BLOCK│ESC │
   (Vue 3)    │         └──────────────────┘
              │              ↓
              └──── Audit Log (JSONL)
```

## Quick Start

```bash
cd extensions/agent-firewall
pip install -e ".[dev]"

# Run the firewall proxy
make dev

# Run red team attack simulation
make attack

# Run tests
make test
```

## Project Structure

```
src/
├── main.py                  # FastAPI application + route wiring
├── config.py                # 12-factor configuration (env vars)
├── models.py                # Pydantic models (JSON-RPC, verdicts, audit)
├── engine/
│   ├── static_analyzer.py   # L1: Aho-Corasick + regex battery
│   ├── semantic_analyzer.py # L2: LLM intent classification
│   └── interceptor.py       # Core intercept_and_analyze pipeline
├── proxy/
│   ├── session_manager.py   # Stateful session reconstruction
│   ├── stdio_adapter.py     # stdio transport (subprocess pipes)
│   └── sse_adapter.py       # SSE + WebSocket transport
├── audit/
│   └── logger.py            # Batched async JSONL audit logging
└── dashboard/
    └── ws_handler.py        # Real-time WebSocket event hub

frontend/                    # Vue 3 God Mode Console
├── src/App.vue              # Dashboard SFC (waterfall + alerts)
└── src/main.ts

tests/
├── test_firewall.py         # Unit tests (L1, L2, interceptor, sessions)
└── red_team/
    └── attack_simulation.py # Automated adversarial testing
```

## Dual Analysis Engine

### L1 — Static Analyzer
- **Aho-Corasick automaton** for O(n) multi-pattern matching.
- **Regex battery** for structural patterns (Base64, shell pipes, SQL injection).
- **Heuristic Base64 decode** to catch obfuscated payloads.
- Latency: < 1ms for payloads up to 64KB.

### L2 — Semantic Analyzer
- LLM-powered intent classification (OpenAI-compatible API).
- Detects prompt injection, confused deputy attacks, role hijacking.
- Mock classifier for testing (zero external dependencies).
- Configurable timeout with fail-open semantics.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AF_LISTEN_HOST` | `127.0.0.1` | Proxy listen address |
| `AF_LISTEN_PORT` | `9090` | Proxy listen port |
| `AF_UPSTREAM_HOST` | `127.0.0.1` | MCP server address |
| `AF_UPSTREAM_PORT` | `3000` | MCP server port |
| `AF_L1_ENABLED` | `1` | Enable static analyzer |
| `AF_L2_ENABLED` | `1` | Enable semantic analyzer |
| `AF_L2_MODEL_ENDPOINT` | `http://localhost:11434/v1/chat/completions` | LLM endpoint |
| `AF_L2_TIMEOUT` | `5.0` | L2 analysis timeout (seconds) |
| `AF_SESSION_BUFFER_SIZE` | `64` | Session ring buffer size |
| `AF_SESSION_TTL` | `3600` | Session expiry (seconds) |
| `AF_AUDIT_LOG` | `./audit/firewall.jsonl` | Audit log path |
