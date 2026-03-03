# Architectural Patterns

This document describes the design decisions, conventions, and patterns used throughout the Agent Firewall codebase.

## Core Design Principles

### 1. Dependency Injection Over Singletons

**Pattern:** All major components receive their dependencies explicitly through constructors, not via global state.

**Examples:**

- `interceptor.py` — Pure async function with explicit parameters (no global state)
- `AppState` class in `main.py:66` — Container for all shared state, injected into route handlers
- `SemanticAnalyzer` receives a `classifier` instance (LlmClassifier or MockClassifier)

**Benefits:**

- Fully testable without mocking globals
- Clear dependency graph
- Easy to swap implementations (e.g., Mock vs Live LLM)

### 2. Immutable Configuration (12-Factor)

**Pattern:** Configuration is loaded once at startup from environment variables into an immutable dataclass.

**Implementation:**

- `config.py:24` — `@dataclass(frozen=True, slots=True)` FirewallConfig
- All settings via `AF_*` environment variables
- No runtime config mutation

**Benefits:**

- Predictable behavior (config can't change mid-request)
- Memory efficient (slots=True)
- 12-factor compliant

### 3. Async-First Architecture

**Pattern:** All I/O operations are async; CPU-bound work (L1 analysis) runs synchronously in the event loop.

**Examples:**

- `main.py` — FastAPI with async route handlers
- `audit/logger.py:30` — Async buffered JSONL writer with background flush task
- `dashboard/ws_handler.py:77` — Async broadcast to WebSocket clients
- `session_manager.py:52` — Background GC sweep task

**Benefits:**

- High concurrency without threads
- Minimal latency for I/O-bound operations (L2 LLM calls)
- Efficient resource usage

### 4. Zero-Copy JSON Parsing

**Pattern:** Use `orjson` for fast serialization and parse directly from bytes when possible.

**Implementation:**

- `models.py:44` — `@model_validator` to accept bytes directly
- `models.py:72` — `to_bytes()` method using orjson
- No intermediate string conversions

**Benefits:**

- Reduced memory allocations
- Lower latency (<1ms for L1 analysis)

### 5. Ring Buffer for Session History

**Pattern:** Fixed-size circular buffer per session to cap memory usage.

**Implementation:**

- `session_manager.py:46` — `_buffer_size` from config
- Each session stores at most N messages (default 64)
- Oldest messages are evicted automatically

**Benefits:**

- O(1) memory per session regardless of conversation length
- Predictable memory footprint
- Prevents memory exhaustion from long-running sessions

### 6. Fail-Open Semantics for L2

**Pattern:** If L2 (LLM) times out or fails, return "no opinion" and rely on L1 results alone.

**Implementation:**

- `semantic_analyzer.py` — L2 timeout returns neutral result
- `interceptor.py:77` — `_compute_verdict()` handles missing L2 data
- README.md:146 — "Fail-Open Semantics" section

**Benefits:**

- Availability never compromised by model latency
- Graceful degradation
- L1 still provides baseline protection

### 7. Backpressure Handling for WebSocket Clients

**Pattern:** Bounded queues per client; drop events if client falls behind.

**Implementation:**

- `dashboard/ws_handler.py:45` — `_CLIENT_BUFFER_SIZE = 256`
- `ws_handler.py:68` — `asyncio.Queue(maxsize=_CLIENT_BUFFER_SIZE)`
- Events dropped if queue full (no unbounded buffering)

**Benefits:**

- Prevents memory exhaustion from slow clients
- Fast clients unaffected by slow clients
- Server remains responsive

### 8. Explicit Threat Level Enum

**Pattern:** Use typed enums for verdicts and threat levels, not magic strings.

**Implementation:**

- `models.py` — `Verdict` and `ThreatLevel` enums
- Pattern matching in `interceptor.py:77` — `_compute_verdict()`

**Benefits:**

- Type safety (mypy/pyright catch errors)
- No typos in string comparisons
- Clear domain model

## Frontend Patterns

### 9. Composables for State Management

**Pattern:** Vue 3 Composition API with dedicated composables for each concern.

**Implementation:**

- `composables.ts:36` — `useWebSocket()` for real-time events
- `composables.ts` — 7 composables total (WebSocket, Stats, Config, Rules, SecurityTest, AuditLog, Navigation)
- No Vuex/Pinia — composables provide reactive state

**Benefits:**

- Lightweight (no store boilerplate)
- Composable logic (reusable across components)
- Type-safe with TypeScript

### 10. Hash-Based Routing

**Pattern:** Client-side routing via URL hash without a router library.

**Implementation:**

- `App.vue:2` — `currentSection` reactive ref
- `composables.ts` — `useNavigation()` composable
- Browser back/forward support via `hashchange` event

**Benefits:**

- No router dependency
- Simple implementation
- Works with static file serving

### 11. Theme Persistence

**Pattern:** Store theme preference in localStorage and apply via data attribute.

**Implementation:**

- `App.vue:2` — `:data-theme="theme"` attribute
- localStorage key: `agent-firewall-theme`
- CSS variables scoped by `[data-theme="dark"]`

**Benefits:**

- Persists across sessions
- No flash of unstyled content
- CSS-only theme switching

## Testing Patterns

### 12. Dual Test Strategy

**Pattern:** Unit tests for components + adversarial red team simulation for end-to-end security validation.

**Implementation:**

- `tests/test_firewall.py` — 24 unit tests across 5 classes
- `tests/red_team/attack_simulation.py` — 15 attack scenarios
- Separate test runners: `make test` vs `make attack`

**Benefits:**

- Fast unit tests for development
- Comprehensive security validation
- Clear pass/fail metrics (100% detection rate)

## Code Organization Patterns

### 13. Module-Level Constants

**Pattern:** Define constants at module level with leading underscore for internal use.

**Implementation:**

- `interceptor.py:54` — `_HIGH_RISK_METHODS: frozenset[str]`
- `interceptor.py:63` — `_SAFE_METHODS: frozenset[str]`
- `audit/logger.py:27` — `_FLUSH_INTERVAL = 1.0`

**Benefits:**

- Clear scope (module-private)
- Immutable (frozenset)
- Easy to locate and modify

### 14. Docstring-First Documentation

**Pattern:** Every module and class has a comprehensive docstring explaining purpose, design, and performance characteristics.

**Examples:**

- `interceptor.py:1` — Module docstring with performance characteristics
- `session_manager.py:1` — Memory model explanation
- `audit/logger.py:1` — Design rationale

**Benefits:**

- Self-documenting code
- Onboarding efficiency
- Design decisions preserved

### 15. Type Hints Everywhere

**Pattern:** Full type annotations on all functions, including return types.

**Implementation:**

- `from __future__ import annotations` in every module
- Pydantic models for data validation
- TypeScript types mirror Python models (`types.ts`)

**Benefits:**

- Static analysis (mypy, pyright)
- IDE autocomplete
- Reduced runtime errors

## Performance Patterns

### 16. Fast-Path for Safe Methods

**Pattern:** Skip analysis entirely for known-safe MCP methods.

**Implementation:**

- `interceptor.py:63` — `_SAFE_METHODS` frozenset
- Early return in `intercept_and_analyze()`
- README.md:176 — "Always-safe methods" list

**Benefits:**

- <0.1ms latency for handshake/discovery
- Reduced load on analysis engines
- Better user experience

### 17. Batched Audit Writes

**Pattern:** Buffer audit entries in memory and flush periodically.

**Implementation:**

- `audit/logger.py:39` — `_buffer: list[bytes]`
- `audit/logger.py:27` — `_FLUSH_INTERVAL = 1.0` seconds
- Background task flushes buffer

**Benefits:**

- Reduced I/O syscalls
- Lower latency (async write)
- Graceful shutdown flushes remaining entries

## Security Patterns

### 18. Defense in Depth

**Pattern:** Multiple layers of analysis (L1 + L2) with independent detection mechanisms.

**Implementation:**

- L1: Pattern matching (Aho-Corasick + regex)
- L2: Semantic analysis (LLM)
- Policy enforcer merges results via decision matrix

**Benefits:**

- Catches different attack classes
- Redundancy (L1 works if L2 fails)
- Higher detection rate

### 19. Human-in-the-Loop Escalation

**Pattern:** Ambiguous requests escalate to human operator via dashboard.

**Implementation:**

- `dashboard/ws_handler.py:58` — `_pending_escalations` dict
- 30-second timeout, defaults to BLOCK
- WebSocket protocol for verdicts

**Benefits:**

- Reduces false positives
- Operator learns from edge cases
- Audit trail includes human decisions
