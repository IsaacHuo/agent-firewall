<template>
  <div class="app-shell">
    <Sidebar
      :currentSection="currentSection"
      :connected="connected"
      :stats="stats"
      @navigate="navigateTo"
    />
    <main class="main-content">
      <Dashboard
        v-if="currentSection === 'dashboard'"
        :stats="stats"
        :events="events"
        @navigate="navigateTo"
      />
      <TrafficWaterfall
        v-else-if="currentSection === 'traffic'"
        :events="events"
        @clear="clearEvents"
        @verdict="handleVerdict"
      />
      <RulesConfig
        v-else-if="currentSection === 'rules'"
        :rules="rulesData"
        @save="handleSaveRule"
        @delete="handleDeleteRule"
        @toggle="handleToggleRule"
        @updateMethodAction="handleUpdateMethodAction"
        @updateDefaultAction="handleUpdateDefaultAction"
      />
      <EngineSettings
        v-else-if="currentSection === 'engine'"
        :config="config"
        :saving="configSaving"
        @save="handleSaveConfig"
      />
      <RateLimitSettings
        v-else-if="currentSection === 'rate-limit'"
        :config="config?.rate_limit ?? { requests_per_sec: 10, burst: 20 }"
        @save="handleSaveRateLimit"
      />
      <SecurityTest
        v-else-if="currentSection === 'test'"
        :results="testResults"
        :running="testRunning"
        @run="handleRunTest"
        @runAll="handleRunAllTests"
        @clear="clearTestResults"
      />
      <AuditLog
        v-else-if="currentSection === 'audit'"
        :entries="auditEntries"
        :loading="auditLoading"
        :hasMore="auditHasMore"
        @load="handleLoadAudit"
        @loadMore="handleLoadMoreAudit"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import type { FirewallConfig, PatternRule, TestPayload, RuleAction, RateLimitConfig } from './types'
import {
  useWebSocket,
  useStats,
  useConfig,
  useRules,
  useSecurityTest,
  useAuditLog,
  useNavigation,
} from './composables'

// Components
import Sidebar from './components/Sidebar.vue'
import Dashboard from './components/Dashboard.vue'
import TrafficWaterfall from './components/TrafficWaterfall.vue'
import RulesConfig from './components/RulesConfig.vue'
import EngineSettings from './components/EngineSettings.vue'
import RateLimitSettings from './components/RateLimitSettings.vue'
import SecurityTest from './components/SecurityTest.vue'
import AuditLog from './components/AuditLog.vue'

// ── Composables ──────────────────────────────────────────────────

const { connected, events, clearEvents, sendVerdict } = useWebSocket()
const { stats } = useStats()
const { config, saving: configSaving, loadConfig, saveConfig } = useConfig()
const { rules: rulesData, loadRules, saveRule, deleteRule, toggleRule } = useRules()
const { results: testResults, running: testRunning, runTest, runBatch, clearResults: clearTestResults } = useSecurityTest()
const { entries: auditEntries, loading: auditLoading, hasMore: auditHasMore, loadEntries: loadAuditEntries, loadMore: loadMoreAudit } = useAuditLog()
const { currentSection, navigateTo } = useNavigation()

// ── Event Handlers ───────────────────────────────────────────────

function handleVerdict(requestId: string, action: 'allow' | 'block') {
  sendVerdict(requestId, action)
}

function handleSaveRule(rule: PatternRule) {
  saveRule(rule)
}

function handleDeleteRule(ruleId: string) {
  deleteRule(ruleId)
}

function handleToggleRule(ruleId: string, enabled: boolean) {
  toggleRule(ruleId, enabled)
}

function handleUpdateMethodAction(_method: string, _action: RuleAction) {
  // Method rule updates go through bulk config save
  saveConfig({ blocked_commands: config.value?.blocked_commands })
}

function handleUpdateDefaultAction(action: RuleAction) {
  // Update the default action in rules config
  rulesData.value.default_action = action
}

function handleSaveConfig(newConfig: Partial<FirewallConfig>) {
  saveConfig(newConfig)
}

function handleSaveRateLimit(rateLimit: RateLimitConfig) {
  saveConfig({ rate_limit: rateLimit })
}

function handleRunTest(payload: TestPayload) {
  runTest(payload)
}

function handleRunAllTests(payloads: TestPayload[]) {
  runBatch(payloads)
}

function handleLoadAudit(options: { verdict?: string; since?: number }) {
  loadAuditEntries(options)
}

function handleLoadMoreAudit() {
  loadMoreAudit()
}

// ── Init ─────────────────────────────────────────────────────────

onMounted(() => {
  loadConfig()
  loadRules()
  loadAuditEntries({ limit: 50 })
})
</script>

<style>
/* ── Global Reset & Fonts ─────────────────────────────────────── */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --bg-primary: #0a0a0f;
  --bg-secondary: #0f0f1a;
  --bg-elevated: #141428;
  --bg-surface: #1a1a2e;
  --border: #2a2a3e;
  --border-hover: #3a3a4e;
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
  --text-muted: #888888;
  --text-dim: #666666;
  --accent-red: #e94560;
  --accent-green: #00ff88;
  --accent-blue: #4488ff;
  --accent-yellow: #ffaa00;
  --danger: #ff4444;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-primary);
  color: var(--text-secondary);
  -webkit-font-smoothing: antialiased;
}

/* ── Scrollbar ────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2a2a3e; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3a3a4e; }
</style>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  background: var(--bg-primary);
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
