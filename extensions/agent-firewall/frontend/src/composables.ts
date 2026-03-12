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
  SkillStatusReport,
  SkillStatusEntry,
  AgentsListResult,
  GatewayAgentRow,
  AgentFileEntry,
  GatewayConfigSnapshot,
  GatewayConfigSchema,
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

// ── Theme ───────────────────────────────────────────────────────────

export type Theme = "dark" | "light";

export function useTheme() {
  const theme = ref<Theme>((localStorage.getItem("af-theme") as Theme) || "dark");

  function applyTheme(t: Theme) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("af-theme", t);
  }

  function toggleTheme() {
    theme.value = theme.value === "dark" ? "light" : "dark";
    applyTheme(theme.value);
  }

  onMounted(() => {
    applyTheme(theme.value);
  });

  return { theme, toggleTheme };
}

// ── Navigation ──────────────────────────────────────────────────────

export function useNavigation() {
  const currentSection = ref<NavSection>("chat");

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

// ── Gateway WebSocket RPC Client ────────────────────────────────────

let gwWsUrl = localStorage.getItem("af-gateway-url") || `ws://${window.location.hostname}:18789/ws`;

let gwSocket: WebSocket | null = null;
const gwPendingRequests = new Map<
  string,
  { resolve: (val: any) => void; reject: (err: Error) => void }
>();
const gwConnected = ref(false);
const gwConnectError = ref<string | null>(null);
const gwReconnectTimer = ref<ReturnType<typeof setTimeout> | null>(null);
let gwTokenFetched = false;

/** Auto-discover gateway token from the backend, then connect. */
async function gwAutoConnect() {
  if (!gwTokenFetched) {
    gwTokenFetched = true;
    try {
      const resp = await fetch(`${API_BASE}/api/gateway-info`);
      if (resp.ok) {
        const info = await resp.json();
        if (info.configured) {
          // Auto-store token for connect handshake
          if (info.token && !localStorage.getItem("af-gateway-token")) {
            localStorage.setItem("af-gateway-token", info.token);
            console.log("[Gateway] Auto-configured token from backend");
          }
          // Update WS URL if port differs
          if (info.port && !localStorage.getItem("af-gateway-url")) {
            gwWsUrl = `ws://${window.location.hostname}:${info.port}/ws`;
          }
        }
      }
    } catch {
      console.warn("[Gateway] Could not fetch gateway info from backend");
    }
  }
  gwConnect();
}

function gwConnect() {
  if (gwSocket?.readyState === WebSocket.OPEN) return;

  try {
    gwSocket = new WebSocket(gwWsUrl);
  } catch {
    console.warn("[Gateway] Failed to create WebSocket");
    scheduleGwReconnect();
    return;
  }

  gwSocket.onopen = () => {
    gwConnectError.value = null;
    console.log("[Gateway] WebSocket opened, waiting for handshake...");
  };

  gwSocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);

      // Handle challenge — auto-respond with connect using correct protocol
      if (msg.type === "event" && msg.event === "connect.challenge") {
        const connectId = crypto.randomUUID();
        const token = localStorage.getItem("af-gateway-token") || undefined;
        const password = localStorage.getItem("af-gateway-password") || undefined;
        const authObj = token || password ? { token, password } : undefined;
        gwPendingRequests.set(connectId, {
          resolve: (payload: any) => {
            // hello-ok received — connection fully established
            gwConnected.value = true;
            if (payload?.auth?.deviceToken) {
              localStorage.setItem("af-gateway-token", payload.auth.deviceToken);
            }
            console.log("[Gateway] Connected (hello-ok), protocol:", payload?.protocol);
          },
          reject: (err: Error) => {
            console.error("[Gateway] Connect rejected:", err.message);
            gwConnectError.value = err.message;
          },
        });
        gwSocket?.send(
          JSON.stringify({
            type: "req",
            id: connectId,
            method: "connect",
            params: {
              minProtocol: 3,
              maxProtocol: 3,
              client: {
                id: "gateway-client",
                version: "1.0.0",
                platform: "web",
                mode: "backend",
              },
              role: "operator",
              scopes: ["operator.admin"],
              auth: authObj,
            },
          }),
        );
        return;
      }

      // Handle RPC responses (including hello-ok from connect)
      if (msg.type === "res" && msg.id != null) {
        const pending = gwPendingRequests.get(String(msg.id));
        if (pending) {
          gwPendingRequests.delete(String(msg.id));
          if (msg.ok) {
            pending.resolve(msg.payload);
          } else {
            pending.reject(new Error(msg.error?.message || "RPC failed"));
          }
        }
        return;
      }
    } catch (err) {
      console.error("[Gateway] Parse error:", err);
    }
  };

  gwSocket.onclose = () => {
    gwConnected.value = false;
    scheduleGwReconnect();
  };

  gwSocket.onerror = () => {
    console.warn("[Gateway] WebSocket error");
  };
}

function scheduleGwReconnect() {
  if (gwReconnectTimer.value) clearTimeout(gwReconnectTimer.value);
  gwReconnectTimer.value = setTimeout(gwAutoConnect, 5000);
}

function gwDisconnect() {
  if (gwReconnectTimer.value) clearTimeout(gwReconnectTimer.value);
  gwSocket?.close();
  gwSocket = null;
}

function gwRequest<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    if (!gwSocket || gwSocket.readyState !== WebSocket.OPEN || !gwConnected.value) {
      reject(new Error("Gateway not connected"));
      return;
    }
    const id = crypto.randomUUID();
    gwPendingRequests.set(id, { resolve, reject });
    gwSocket.send(JSON.stringify({ type: "req", id, method, params }));

    // Timeout after 30s
    setTimeout(() => {
      if (gwPendingRequests.has(id)) {
        gwPendingRequests.delete(id);
        reject(new Error(`RPC timeout: ${method}`));
      }
    }, 30000);
  });
}

export function useGateway() {
  onMounted(gwAutoConnect);
  onUnmounted(gwDisconnect);

  const gatewayUrl = ref(gwWsUrl);

  function updateGatewayUrl(url: string) {
    localStorage.setItem("af-gateway-url", url);
    gatewayUrl.value = url;
    gwWsUrl = url;
    gwDisconnect();
    gwConnect();
  }

  function setGatewayToken(token: string) {
    if (token) {
      localStorage.setItem("af-gateway-token", token);
    } else {
      localStorage.removeItem("af-gateway-token");
    }
    gwConnectError.value = null;
    gwDisconnect();
    gwConnect();
  }

  function setGatewayPassword(password: string) {
    if (password) {
      localStorage.setItem("af-gateway-password", password);
    } else {
      localStorage.removeItem("af-gateway-password");
    }
    gwConnectError.value = null;
    gwDisconnect();
    gwConnect();
  }

  return {
    connected: gwConnected,
    connectError: gwConnectError,
    gatewayUrl,
    updateGatewayUrl,
    setGatewayToken,
    setGatewayPassword,
    request: gwRequest,
  };
}

/** Read-only gateway connection state — safe to call from any component without lifecycle side effects */
export function useGatewayStatus() {
  return {
    connected: gwConnected,
    connectError: gwConnectError,
  };
}

// ── Skills API (via Gateway RPC) ────────────────────────────────────

export function useGatewaySkills() {
  const skills = ref<SkillStatusEntry[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadSkills(agentId?: string) {
    try {
      loading.value = true;
      error.value = null;
      const report = await gwRequest<SkillStatusReport>(
        "skills.status",
        agentId ? { agentId } : {},
      );
      skills.value = report.skills;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load skills";
    } finally {
      loading.value = false;
    }
  }

  async function toggleSkill(skillKey: string, enabled: boolean) {
    try {
      error.value = null;
      await gwRequest("skills.update", { skillKey, enabled });
      await loadSkills();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to toggle skill";
    }
  }

  async function setSkillApiKey(skillKey: string, apiKey: string) {
    try {
      error.value = null;
      await gwRequest("skills.update", { skillKey, apiKey });
      await loadSkills();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save API key";
    }
  }

  async function installSkill(name: string, installId: string) {
    try {
      error.value = null;
      await gwRequest("skills.install", { name, installId, timeoutMs: 120000 });
      await loadSkills();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to install skill";
    }
  }

  return { skills, loading, error, loadSkills, toggleSkill, setSkillApiKey, installSkill };
}

// ── Agents API (via Gateway RPC) ────────────────────────────────────

export function useGatewayAgents() {
  const agents = ref<GatewayAgentRow[]>([]);
  const defaultAgentId = ref("");
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadAgents() {
    try {
      loading.value = true;
      error.value = null;
      const result = await gwRequest<AgentsListResult>("agents.list", {});
      agents.value = result.agents;
      defaultAgentId.value = result.defaultId;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load agents";
    } finally {
      loading.value = false;
    }
  }

  async function loadAgentFiles(agentId: string): Promise<AgentFileEntry[]> {
    try {
      const result = await gwRequest<{ files: AgentFileEntry[] }>("agents.files.list", { agentId });
      return result.files;
    } catch {
      return [];
    }
  }

  async function loadAgentFile(agentId: string, name: string): Promise<string> {
    try {
      const result = await gwRequest<{ content: string }>("agents.files.get", { agentId, name });
      return result.content ?? "";
    } catch {
      return "";
    }
  }

  async function saveAgentFile(agentId: string, name: string, content: string) {
    try {
      error.value = null;
      await gwRequest("agents.files.set", { agentId, name, content });
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save file";
    }
  }

  return {
    agents,
    defaultAgentId,
    loading,
    error,
    loadAgents,
    loadAgentFiles,
    loadAgentFile,
    saveAgentFile,
  };
}

// ── Gateway Config API (via Gateway RPC) ────────────────────────────

export function useGatewayConfig() {
  const configSnapshot = ref<GatewayConfigSnapshot | null>(null);
  const configSchema = ref<GatewayConfigSchema | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  async function loadGwConfig() {
    try {
      loading.value = true;
      error.value = null;
      const [snapshot, schema] = await Promise.all([
        gwRequest<GatewayConfigSnapshot>("config.get", {}),
        gwRequest<GatewayConfigSchema>("config.schema", {}).catch(() => null),
      ]);
      configSnapshot.value = snapshot;
      if (schema) configSchema.value = schema;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load gateway config";
    } finally {
      loading.value = false;
    }
  }

  async function saveGwConfig(raw: string) {
    try {
      saving.value = true;
      error.value = null;
      await gwRequest("config.set", {
        raw,
        baseHash: configSnapshot.value?.hash,
      });
      await loadGwConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save gateway config";
    } finally {
      saving.value = false;
    }
  }

  async function applyGwConfig(raw: string) {
    try {
      saving.value = true;
      error.value = null;
      await gwRequest("config.apply", {
        raw,
        baseHash: configSnapshot.value?.hash,
        sessionKey: "web-dashboard",
      });
      await loadGwConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to apply gateway config";
    } finally {
      saving.value = false;
    }
  }

  return {
    configSnapshot,
    configSchema,
    loading,
    saving,
    error,
    loadGwConfig,
    saveGwConfig,
    applyGwConfig,
  };
}

// ── Custom MCP/Skill Config ─────────────────────────────────────

export function useCustomConfig() {
  const mcpServers = ref<import("./types").CustomMcpServer[]>([]);
  const customSkills = ref<import("./types").CustomSkillDef[]>([]);
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  async function loadCustomConfig() {
    loading.value = true;
    error.value = null;
    try {
      const data = await apiFetch<import("./types").CustomConfigData>("/api/custom-config");
      mcpServers.value = data.mcp_servers || [];
      customSkills.value = data.skills || [];
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load custom config";
    } finally {
      loading.value = false;
    }
  }

  async function saveMcpServer(server: import("./types").CustomMcpServer) {
    saving.value = true;
    try {
      await apiFetch("/api/custom-config/mcp-servers", {
        method: "POST",
        body: JSON.stringify(server),
      });
      await loadCustomConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save MCP server";
    } finally {
      saving.value = false;
    }
  }

  async function deleteMcpServer(serverId: string) {
    saving.value = true;
    try {
      await apiFetch(`/api/custom-config/mcp-servers/${serverId}`, {
        method: "DELETE",
      });
      await loadCustomConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to delete MCP server";
    } finally {
      saving.value = false;
    }
  }

  async function saveCustomSkill(skill: import("./types").CustomSkillDef) {
    saving.value = true;
    try {
      await apiFetch("/api/custom-config/skills", {
        method: "POST",
        body: JSON.stringify(skill),
      });
      await loadCustomConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save custom skill";
    } finally {
      saving.value = false;
    }
  }

  async function deleteCustomSkill(skillId: string) {
    saving.value = true;
    try {
      await apiFetch(`/api/custom-config/skills/${skillId}`, {
        method: "DELETE",
      });
      await loadCustomConfig();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to delete custom skill";
    } finally {
      saving.value = false;
    }
  }

  return {
    mcpServers,
    customSkills,
    loading,
    saving,
    error,
    loadCustomConfig,
    saveMcpServer,
    deleteMcpServer,
    saveCustomSkill,
    deleteCustomSkill,
  };
}

// ── Toast Notifications ─────────────────────────────────────────────

export { useToast } from "./composables/useToast";
