/**
 * Agent Firewall — State Management & API Composables
 */

import { ref, reactive, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  Stats,
  FirewallEvent,
  FirewallConfig,
  RulesConfig,
  PatternRule,
  TestPayload,
  TestResult,
  AuditEntry,
  NavSection,
} from "./types";

// ── API Base ────────────────────────────────────────────────────────

const API_BASE = `${window.location.protocol}//${window.location.hostname}:9090`;
const WS_BASE = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname}:9090`;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── WebSocket Connection ────────────────────────────────────────────

export function useWebSocket() {
  const connected = ref(false);
  const events = ref<FirewallEvent[]>([]);
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) return;

    ws = new WebSocket(`${WS_BASE}/ws/dashboard`);

    ws.onopen = () => {
      connected.value = true;
      console.log("[Firewall] WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const data: FirewallEvent = JSON.parse(event.data);
        events.value.push(data);
        // Keep last 500 events
        if (events.value.length > 500) {
          events.value = events.value.slice(-500);
        }
      } catch (err) {
        console.error("[Firewall] WebSocket parse error:", err);
      }
    };

    ws.onclose = () => {
      connected.value = false;
      console.log("[Firewall] WebSocket disconnected");
      // Auto-reconnect
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error("[Firewall] WebSocket error:", err);
    };
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
  }

  function clearEvents() {
    events.value = [];
  }

  function sendVerdict(requestId: string, action: "allow" | "block") {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, request_id: requestId }));
    }
  }

  onMounted(connect);
  onUnmounted(disconnect);

  return { connected, events, clearEvents, sendVerdict };
}

// ── Stats Polling ───────────────────────────────────────────────────

export function useStats() {
  const stats = ref<Stats>({
    uptime_seconds: 0,
    active_sessions: 0,
    dashboard_clients: 0,
    audit: null,
  });
  const loading = ref(false);
  let interval: ReturnType<typeof setInterval> | null = null;

  async function fetchStats() {
    try {
      loading.value = true;
      stats.value = await apiFetch<Stats>("/api/stats");
    } catch (err) {
      console.error("[Firewall] Failed to fetch stats:", err);
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    fetchStats();
    interval = setInterval(fetchStats, 5000);
  });

  onUnmounted(() => {
    if (interval) clearInterval(interval);
  });

  return { stats, loading, refresh: fetchStats };
}

// ── Configuration API ───────────────────────────────────────────────

export function useConfig() {
  const config = ref<FirewallConfig | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  async function loadConfig() {
    try {
      loading.value = true;
      error.value = null;
      config.value = await apiFetch<FirewallConfig>("/api/config");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load config";
    } finally {
      loading.value = false;
    }
  }

  async function saveConfig(newConfig: Partial<FirewallConfig>) {
    try {
      saving.value = true;
      error.value = null;
      config.value = await apiFetch<FirewallConfig>("/api/config", {
        method: "PATCH",
        body: JSON.stringify(newConfig),
      });
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save config";
    } finally {
      saving.value = false;
    }
  }

  return { config, loading, saving, error, loadConfig, saveConfig };
}

// ── Rules API ───────────────────────────────────────────────────────

export function useRules() {
  const rules = ref<RulesConfig>({
    pattern_rules: [],
    method_rules: [],
    agent_rules: [],
    default_action: "ALLOW",
  });
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  async function loadRules() {
    try {
      loading.value = true;
      error.value = null;
      rules.value = await apiFetch<RulesConfig>("/api/rules");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load rules";
    } finally {
      loading.value = false;
    }
  }

  async function saveRule(rule: PatternRule) {
    try {
      saving.value = true;
      error.value = null;
      await apiFetch<PatternRule>("/api/rules/patterns", {
        method: rule.id ? "PUT" : "POST",
        body: JSON.stringify(rule),
      });
      await loadRules();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save rule";
    } finally {
      saving.value = false;
    }
  }

  async function deleteRule(ruleId: string) {
    try {
      saving.value = true;
      error.value = null;
      await apiFetch(`/api/rules/patterns/${ruleId}`, { method: "DELETE" });
      await loadRules();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to delete rule";
    } finally {
      saving.value = false;
    }
  }

  async function toggleRule(ruleId: string, enabled: boolean) {
    try {
      saving.value = true;
      error.value = null;
      await apiFetch(`/api/rules/patterns/${ruleId}/toggle`, {
        method: "POST",
        body: JSON.stringify({ enabled }),
      });
      await loadRules();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to toggle rule";
    } finally {
      saving.value = false;
    }
  }

  return { rules, loading, saving, error, loadRules, saveRule, deleteRule, toggleRule };
}

// ── Security Test API ───────────────────────────────────────────────

export function useSecurityTest() {
  const results = ref<TestResult[]>([]);
  const running = ref(false);
  const error = ref<string | null>(null);

  async function runTest(payload: TestPayload): Promise<TestResult> {
    const start = performance.now();
    try {
      const result = await apiFetch<{
        verdict: string;
        l1_patterns: string[];
        l2_confidence: number;
      }>("/api/test/analyze", {
        method: "POST",
        body: JSON.stringify({ payload: payload.payload }),
      });

      const testResult: TestResult = {
        payload_id: payload.id,
        actual_verdict: result.verdict as any,
        expected_verdict: payload.expected_verdict,
        passed: result.verdict === payload.expected_verdict,
        l1_patterns: result.l1_patterns,
        l2_confidence: result.l2_confidence,
        latency_ms: performance.now() - start,
        timestamp: Date.now(),
      };

      results.value.push(testResult);
      return testResult;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Test failed";
      throw err;
    }
  }

  async function runBatch(payloads: TestPayload[]) {
    running.value = true;
    error.value = null;
    results.value = [];

    for (const payload of payloads) {
      try {
        await runTest(payload);
      } catch {
        // Continue with other tests
      }
    }

    running.value = false;
  }

  function clearResults() {
    results.value = [];
  }

  const summary = computed(() => {
    const total = results.value.length;
    const passed = results.value.filter((r) => r.passed).length;
    const avgLatency =
      total > 0 ? results.value.reduce((sum, r) => sum + r.latency_ms, 0) / total : 0;
    return { total, passed, failed: total - passed, avgLatency };
  });

  return { results, running, error, runTest, runBatch, clearResults, summary };
}

// ── Audit Log API ───────────────────────────────────────────────────

export function useAuditLog() {
  const entries = ref<AuditEntry[]>([]);
  const loading = ref(false);
  const hasMore = ref(true);
  const error = ref<string | null>(null);

  async function loadEntries(options?: {
    limit?: number;
    offset?: number;
    verdict?: string;
    since?: number;
  }) {
    try {
      loading.value = true;
      error.value = null;
      const params = new URLSearchParams();
      if (options?.limit) params.set("limit", String(options.limit));
      if (options?.offset) params.set("offset", String(options.offset));
      if (options?.verdict) params.set("verdict", options.verdict);
      if (options?.since) params.set("since", String(options.since));

      const result = await apiFetch<{ entries: AuditEntry[]; has_more: boolean }>(
        `/api/audit?${params}`,
      );
      entries.value = result.entries;
      hasMore.value = result.has_more;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load audit log";
    } finally {
      loading.value = false;
    }
  }

  async function loadMore(limit = 50) {
    if (!hasMore.value || loading.value) return;

    try {
      loading.value = true;
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(entries.value.length),
      });

      const result = await apiFetch<{ entries: AuditEntry[]; has_more: boolean }>(
        `/api/audit?${params}`,
      );
      entries.value = [...entries.value, ...result.entries];
      hasMore.value = result.has_more;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load more entries";
    } finally {
      loading.value = false;
    }
  }

  return { entries, loading, hasMore, error, loadEntries, loadMore };
}

// ── Navigation ──────────────────────────────────────────────────────

export function useNavigation() {
  const currentSection = ref<NavSection>("dashboard");

  function navigateTo(section: NavSection) {
    currentSection.value = section;
    history.pushState({ section }, "", `#${section}`);
  }

  // Handle browser back/forward
  function handlePopState(event: PopStateEvent) {
    if (event.state?.section) {
      currentSection.value = event.state.section;
    }
  }

  onMounted(() => {
    // Initialize from URL hash
    const hash = window.location.hash.slice(1) as NavSection;
    if (hash) {
      currentSection.value = hash;
    }
    window.addEventListener("popstate", handlePopState);
  });

  onUnmounted(() => {
    window.removeEventListener("popstate", handlePopState);
  });

  return { currentSection, navigateTo };
}
