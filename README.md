# Agent Firewall

Zero-Trust Agent Communication Security Gateway

---

## Table of Contents

1. [Background and Motivation](#background-and-motivation)
2. [System Architecture](#system-architecture)
3. [Dual Analysis Engine](#dual-analysis-engine)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Starting the Service](#starting-the-service)
7. [API Reference](#api-reference)
8. [Testing](#testing)
9. [Project Structure](#project-structure)
10. [Security Decision Matrix](#security-decision-matrix)

---

## Background and Motivation

As AI Agent systems become increasingly powerful, they are granted access to sensitive tools such as file systems, shell execution, databases, and network interfaces. This capability introduces significant security risks:

- **Prompt Injection**: Malicious inputs that hijack agent instructions
- **Confused Deputy Attacks**: Legitimate-looking tool calls serving unauthorized goals
- **Data Exfiltration**: Unauthorized extraction of sensitive information
- **Privilege Escalation**: Attempts to exceed granted permissions

Agent Firewall is designed as a non-invasive Man-in-the-Middle (MITM) proxy that intercepts all MCP (Model Context Protocol) JSON-RPC traffic between AI Agents and Tool Servers. It employs a dual-layer analysis engine to detect and block threats in real-time while maintaining audit trails for security forensics.

---

## System Architecture

```
                                                   Tool Servers
                                                 +------------------+
                                                 | fs (File System) |
Agent A --+                                  +-->| shell (Executor) |
Agent B --+-- JSON-RPC -->+------------------+|  | fetch (HTTP)     |
Agent N --+     :9090     |  AGENT FIREWALL  |+  | db (Database)    |
                          |                  |   +------------------+
                          |  +-----------+   |
                          |  | L1 Static |   |
                          |  | Analyzer  |   |
                          |  +-----+-----+   |
                +---------+        |         |
                |         |        v         |
                |         |  +-----------+   |
                |         |  |L2 Semantic|   |
                |         |  | Analyzer  |   |
   Dashboard <--+         |  +-----+-----+   |
   (Vue 3)      |         |        |         |
   WebSocket    |         |        v         |
                |         |  +-----------+   |
                |         |  |  Policy   |   |
                |         |  | Enforcer  |   |
                |         |  +-----------+   |
                |         |        |         |
                |         | ALLOW BLOCK ESC  |
                |         +------------------+
                |                |
                +---------> Audit Log (JSONL)
```

### Data Flow

1. Agent sends JSON-RPC request to firewall proxy (port 9090)
2. Request is parsed and validated against JSON-RPC 2.0 specification
3. L1 Static Analyzer performs pattern-based threat detection
4. L2 Semantic Analyzer uses LLM for intent classification
5. Policy Enforcer merges L1 + L2 results and renders verdict
6. Verdict: ALLOW (forward), BLOCK (reject), or ESCALATE (human review)
7. All decisions are logged to audit trail and broadcast to dashboard

---

## Dual Analysis Engine

### L1 Static Analyzer

The L1 layer provides high-throughput, low-latency pattern-based threat detection. It operates synchronously and completes in under 1ms for payloads up to 64KB.

#### Aho-Corasick Automaton

The Aho-Corasick algorithm enables O(n) multi-pattern matching regardless of pattern count. The firewall maintains an automaton of known dangerous command fragments:

```
rm -rf, /etc/shadow, /etc/passwd, DROP TABLE, DELETE FROM,
TRUNCATE, shutdown, mkfs, dd if=, FORMAT C:, wget|sh, curl|bash
```

When any of these patterns appear in a payload, the request is flagged immediately.

#### Regex Battery

Compiled regular expressions detect structural attack patterns:

| Pattern Name            | Description                                   | Threat Level |
| ----------------------- | --------------------------------------------- | ------------ |
| shell_pipe_injection    | Shell command chaining via pipes or subshells | HIGH         |
| prompt_injection_marker | "ignore previous instructions" variants       | CRITICAL     |
| base64_obfuscation      | Base64 decode function calls                  | HIGH         |
| hex_obfuscation         | Hex-encoded shell commands                    | MEDIUM       |
| path_traversal          | Directory traversal sequences (../..)         | HIGH         |
| env_exfiltration        | Access to sensitive environment variables     | CRITICAL     |
| sql_injection           | SQL injection patterns (UNION SELECT, etc.)   | HIGH         |
| data_exfiltration_url   | Requests to known exfiltration endpoints      | HIGH         |

#### Heuristic Base64 Decoding

The analyzer attempts to decode suspicious Base64 blobs and re-analyze the decoded content, catching obfuscated payloads that would otherwise evade detection.

### L2 Semantic Analyzer

The L2 layer provides deep intent classification using Large Language Models. It understands the meaning behind requests, catching sophisticated attacks that evade pattern matching.

#### Supported Attacks

- **Prompt Injection**: Attempts to override agent instructions ("Ignore all previous instructions and...")
- **Confused Deputy**: Legitimate-looking calls serving unauthorized goals
- **Role Hijacking**: Identity manipulation ("You are now an admin...")
- **Data Exfiltration**: Disguised attempts to extract sensitive information
- **Privilege Escalation**: Requests exceeding declared scope

#### LLM Backend Configuration

The analyzer supports any OpenAI-compatible chat completions API:

- **OpenRouter** (default): Access to multiple models via single endpoint
- **OpenAI**: Direct GPT-4/GPT-3.5 access
- **Ollama**: Local model deployment
- **vLLM/LiteLLM**: Self-hosted inference servers

The system prompt is carefully crafted to focus the model on security classification only, requesting structured JSON output for reliable parsing.

#### Fail-Open Semantics

If the LLM is unavailable or times out, L2 returns a "no opinion" result. The policy enforcer then relies on L1 results alone. This ensures availability is not compromised by model latency, while all decisions are logged for post-incident analysis.

#### Mock Classifier

For testing and CI environments, a deterministic MockClassifier provides keyword-based classification without external dependencies. This allows the full pipeline to run in isolation.

---

## Installation

### Prerequisites

- Python 3.12 or later
- pip (Python package manager)
- (Optional) Virtual environment tool (venv, conda)

### Setup

```bash
cd extensions/agent-firewall

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Or install as editable package with dev dependencies
pip install -e ".[dev]"
```

### Dependencies

| Package        | Version    | Purpose                         |
| -------------- | ---------- | ------------------------------- |
| fastapi        | >= 0.115.0 | HTTP/WebSocket API framework    |
| uvicorn        | >= 0.34.0  | ASGI server                     |
| pydantic       | >= 2.10.0  | Data validation and models      |
| httpx          | >= 0.28.0  | Async HTTP client for LLM calls |
| ahocorasick-rs | >= 0.22.0  | Aho-Corasick pattern matching   |
| orjson         | >= 3.10.0  | Fast JSON serialization         |
| python-dotenv  | >= 1.0.0   | Environment variable loading    |
| websockets     | >= 14.0    | WebSocket protocol support      |

---

## Configuration

### Environment Variables

Configuration follows the 12-factor methodology. All settings can be overridden via environment variables.

Create a `.env` file in the extension root directory:

```bash
# Network Configuration
AF_LISTEN_HOST=127.0.0.1
AF_LISTEN_PORT=9090

# Upstream MCP Server
AF_UPSTREAM_HOST=127.0.0.1
AF_UPSTREAM_PORT=3000
AF_TRANSPORT_MODE=sse  # Options: stdio, sse, websocket

# L1 Static Analyzer
AF_L1_ENABLED=1
AF_BLOCKED_COMMANDS="rm -rf,/etc/shadow,DROP TABLE"

# L2 Semantic Analyzer
AF_L2_ENABLED=1
AF_L2_MODEL_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
AF_L2_API_KEY=sk-or-v1-your-api-key
AF_L2_MODEL=minimax/minimax-m2.5
AF_L2_TIMEOUT=10.0

# Session Management
AF_SESSION_BUFFER_SIZE=64
AF_SESSION_TTL=3600

# Rate Limiting (token-bucket algorithm)
AF_RATE_LIMIT_RPS=100
AF_RATE_LIMIT_BURST=200

# Audit Logging
AF_AUDIT_LOG=./audit/firewall.jsonl
```

### Variable Reference

| Variable               | Default                | Description                                  |
| ---------------------- | ---------------------- | -------------------------------------------- |
| AF_LISTEN_HOST         | 127.0.0.1              | Firewall proxy listen address                |
| AF_LISTEN_PORT         | 9090                   | Firewall proxy listen port                   |
| AF_UPSTREAM_HOST       | 127.0.0.1              | Target MCP server address                    |
| AF_UPSTREAM_PORT       | 3000                   | Target MCP server port                       |
| AF_TRANSPORT_MODE      | sse                    | MCP transport mode (stdio/sse/websocket)     |
| AF_L1_ENABLED          | 1                      | Enable L1 static analyzer (1=on, 0=off)      |
| AF_L2_ENABLED          | 1                      | Enable L2 semantic analyzer (1=on, 0=off)    |
| AF_L2_MODEL_ENDPOINT   | OpenRouter URL         | LLM API endpoint (OpenAI-compatible)         |
| AF_L2_API_KEY          | (empty)                | API key for LLM authentication               |
| AF_L2_MODEL            | minimax/minimax-m2.5   | Model identifier for L2 classification       |
| AF_L2_TIMEOUT          | 10.0                   | L2 analysis timeout in seconds               |
| AF_SESSION_BUFFER_SIZE | 64                     | Messages to retain per session (ring buffer) |
| AF_SESSION_TTL         | 3600                   | Session expiry in seconds                    |
| AF_RATE_LIMIT_RPS      | 100                    | Maximum requests per second                  |
| AF_RATE_LIMIT_BURST    | 200                    | Token bucket burst capacity                  |
| AF_AUDIT_LOG           | ./audit/firewall.jsonl | Audit log file path                          |

---

## Starting the Service

### Development Mode

Hot-reload enabled for rapid iteration:

```bash
make dev
# Or directly:
uvicorn src.main:app --reload --host 0.0.0.0 --port 9090
```

### Production Mode

Multi-worker deployment with uvicorn:

```bash
make run
# Or directly:
uvicorn src.main:app --host 0.0.0.0 --port 9090 --workers 4
```

### Verification

Once started, verify the service is running:

```bash
# Health check
curl http://127.0.0.1:9090/health

# Expected response
{"status":"healthy","uptime_seconds":123.45}
```

### Dashboard Access

Open a browser and navigate to:

```
http://127.0.0.1:9090/
```

The Vue 3 dashboard provides real-time visibility into:

- Request waterfall (chronological traffic view)
- Threat alerts and block events
- Session statistics
- Audit log viewer

---

## API Reference

### Proxy Endpoints

| Method    | Path     | Description                                   |
| --------- | -------- | --------------------------------------------- |
| POST      | /mcp/\*  | Proxy endpoint for MCP JSON-RPC traffic       |
| GET       | /mcp/sse | Server-Sent Events stream for MCP responses   |
| WebSocket | /ws/mcp  | WebSocket proxy for bidirectional MCP traffic |

### Management Endpoints

| Method    | Path          | Description                                     |
| --------- | ------------- | ----------------------------------------------- |
| GET       | /health       | Service health check                            |
| GET       | /api/stats    | Firewall statistics (requests, blocks, latency) |
| GET       | /api/audit    | Recent audit log entries                        |
| WebSocket | /ws/dashboard | Real-time event stream for dashboard            |

### Error Responses

Blocked requests receive a JSON-RPC error response:

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

---

## Testing

### Unit Tests

Run the full test suite with pytest:

```bash
make test
# Or directly:
pytest tests/ -v --tb=short
```

Test coverage includes:

- JSON-RPC model parsing and serialization
- L1 static analyzer pattern detection
- L2 semantic analyzer (mock classifier)
- Policy enforcer decision matrix
- Session manager lifecycle
- Interceptor pipeline

### Red Team Attack Simulation

Automated adversarial testing with 15 attack scenarios:

```bash
make attack
# Or directly:
python -m tests.red_team.attack_simulation
```

Attack scenarios include:

1. Classic prompt injection ("Ignore previous instructions...")
2. Role hijacking ("You are now in maintenance mode...")
3. Shell command injection via pipes
4. Base64-obfuscated payloads
5. Path traversal attacks
6. SQL injection
7. Environment variable exfiltration
8. Data exfiltration URLs
9. Confused deputy attacks
10. Privilege escalation attempts
11. Recursive prompt injection
12. Multi-stage attacks
13. Unicode obfuscation
14. Context poisoning
15. Instruction extraction

### Expected Results

```
Test Results:
  Total: 24
  Passed: 24
  Failed: 0

Red Team Results:
  Scenarios: 15
  Detection Rate: 100%
```

---

## Project Structure

```
extensions/agent-firewall/
|-- .env                     # Environment configuration (gitignored)
|-- .gitignore
|-- Makefile                 # Build and run commands
|-- pyproject.toml           # Python project metadata
|-- requirements.txt         # Python dependencies
|-- README.md                # This documentation
|
|-- src/
|   |-- __init__.py
|   |-- main.py              # FastAPI application entry point
|   |-- config.py            # Centralized configuration (12-factor)
|   |-- models.py            # Pydantic domain models
|   |
|   |-- engine/              # Dual analysis engine
|   |   |-- static_analyzer.py    # L1: Aho-Corasick + regex
|   |   |-- semantic_analyzer.py  # L2: LLM intent classifier
|   |   +-- interceptor.py        # Core intercept pipeline
|   |
|   |-- proxy/               # Transport adapters
|   |   |-- session_manager.py    # Stateful session tracking
|   |   |-- stdio_adapter.py      # stdio transport (subprocess)
|   |   +-- sse_adapter.py        # SSE + WebSocket transport
|   |
|   |-- audit/               # Security logging
|   |   +-- logger.py             # Async batched JSONL writer
|   |
|   +-- dashboard/           # Real-time monitoring
|       +-- ws_handler.py         # WebSocket event hub
|
|-- frontend/                # Vue 3 dashboard SPA
|   |-- src/
|   |   |-- App.vue               # Main application component
|   |   +-- main.ts               # Application entry point
|   +-- ...
|
+-- tests/
    |-- test_firewall.py          # Unit tests (24 cases)
    +-- red_team/
        +-- attack_simulation.py  # Adversarial test scenarios
```

---

## Security Decision Matrix

The Policy Enforcer merges L1 and L2 analysis results using the following decision matrix:

| L1 Threat Level | L2 Injection | L2 Confidence | Verdict         |
| --------------- | ------------ | ------------- | --------------- |
| CRITICAL        | any          | any           | BLOCK           |
| HIGH            | True         | >= 0.7        | BLOCK           |
| HIGH            | True         | < 0.7         | ESCALATE        |
| HIGH            | False        | any           | ESCALATE        |
| MEDIUM          | True         | >= 0.8        | BLOCK           |
| MEDIUM          | True         | < 0.8         | ESCALATE        |
| MEDIUM          | False        | any           | ALLOW (audited) |
| LOW/NONE        | True         | >= 0.9        | BLOCK           |
| LOW/NONE        | True         | >= 0.7        | ESCALATE        |
| LOW/NONE        | False        | any           | ALLOW           |

### Verdict Definitions

- **ALLOW**: Request is forwarded to upstream MCP server
- **BLOCK**: Request is rejected with JSON-RPC error response
- **ESCALATE**: Request is held pending human review via dashboard

### Safe-by-Default Methods

The following MCP methods are always allowed without analysis:

```
initialize, initialized, ping, tools/list, resources/list,
resources/templates/list, prompts/list, logging/setLevel
```

### High-Risk Methods

The following methods always trigger full L1 + L2 analysis:

```
tools/call, completion/complete, sampling/createMessage
```

---

## Performance Characteristics

| Component          | Latency    | Notes                        |
| ------------------ | ---------- | ---------------------------- |
| L1 Static Analyzer | < 1ms      | Payloads up to 64KB          |
| L1 + L2 (Mock)     | < 2ms      | No network calls             |
| L1 + L2 (Live LLM) | 100ms - 5s | Depends on model and network |
| Session Lookup     | O(1)       | Hash-based session map       |
| Audit Write        | Async      | Batched every 100ms          |

Memory usage is O(1) per request. Payload data is not copied beyond the initial orjson parse.

---

## License

MIT
