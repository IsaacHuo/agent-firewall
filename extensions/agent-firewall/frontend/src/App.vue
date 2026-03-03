<template>
  <div class="app-shell" :data-theme="theme">
    <Sidebar
      :currentSection="currentSection"
      :connected="connected"
      :stats="stats"
      :theme="theme"
      @navigate="navigateTo"
      @toggleTheme="toggleTheme"
    />
    <main class="main-content">
      <ChatLab
        v-if="currentSection === 'chat'"
      />
      <Dashboard
        v-else-if="currentSection === 'dashboard'"
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
      <SkillsManager
        v-else-if="currentSection === 'skills'"
      />
      <AgentsManager
        v-else-if="currentSection === 'agents'"
      />
      <GatewayConfig
        v-else-if="currentSection === 'gateway-config'"
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
  useTheme,
  useGateway,
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
import ChatLab from './components/ChatLab.vue'
import SkillsManager from './components/SkillsManager.vue'
import AgentsManager from './components/AgentsManager.vue'
import GatewayConfig from './components/GatewayConfig.vue'

// ── Composables ──────────────────────────────────────────────────

const { connected, events, clearEvents, sendVerdict } = useWebSocket()
const { stats } = useStats()
useGateway() // Establish Gateway WS connection for Skills/Agents/Config pages
const { config, saving: configSaving, loadConfig, saveConfig } = useConfig()
const { rules: rulesData, loadRules, saveRule, deleteRule, toggleRule } = useRules()
const { results: testResults, running: testRunning, runTest, runBatch, clearResults: clearTestResults } = useSecurityTest()
const { entries: auditEntries, loading: auditLoading, hasMore: auditHasMore, loadEntries: loadAuditEntries, loadMore: loadMoreAudit } = useAuditLog()
const { currentSection, navigateTo } = useNavigation()
const { theme, toggleTheme } = useTheme()

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

:root,
[data-theme="dark"] {
  --bg-primary: #0a0a0f;
  --bg-secondary: #0f0f1a;
  --bg-elevated: #141428;
  --bg-surface: #1a1a2e;
  --bg-hover: rgba(255, 255, 255, 0.05);
  --bg-subtle: rgba(255, 255, 255, 0.02);
  --overlay-bg: rgba(0, 0, 0, 0.7);
  --border: #2a2a3e;
  --border-hover: #3a3a4e;
  --border-subtle: rgba(255, 255, 255, 0.03);
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
  --text-muted: #888888;
  --text-dim: #666666;
  --text-disabled: #444444;
  --accent-red: #e94560;
  --accent-green: #00cc6a;
  --accent-blue: #4488ff;
  --accent-yellow: #ffaa00;
  --accent-orange: #ff8844;
  --accent-purple: #a855f7;
  --accent-cyan: #00c8ff;
  --danger: #ff4444;
  --toggle-bg: #333333;
  --toggle-bg-active: #00cc66;
  --toggle-knob: #ffffff;
  --btn-primary-bg: linear-gradient(135deg, #e94560 0%, #c73450 100%);
  --card-gradient: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  --sidebar-bg-from: #0f0f1a;
  --sidebar-bg-to: #1a1a2e;
  --scrollbar-thumb: #2a2a3e;
  --scrollbar-thumb-hover: #3a3a4e;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

[data-theme="light"] {
  --bg-primary: #f5f5f8;
  --bg-secondary: #eeeef2;
  --bg-elevated: #ffffff;
  --bg-surface: #ffffff;
  --bg-hover: rgba(0, 0, 0, 0.04);
  --bg-subtle: rgba(0, 0, 0, 0.02);
  --overlay-bg: rgba(0, 0, 0, 0.5);
  --border: #d8d8e0;
  --border-hover: #c0c0cc;
  --border-subtle: rgba(0, 0, 0, 0.06);
  --text-primary: #1a1a2e;
  --text-secondary: #3a3a4e;
  --text-muted: #6e6e80;
  --text-dim: #9090a0;
  --text-disabled: #b0b0bb;
  --accent-red: #d63250;
  --accent-green: #00994d;
  --accent-blue: #3366dd;
  --accent-yellow: #cc8800;
  --accent-orange: #dd6622;
  --accent-purple: #8b3fd4;
  --accent-cyan: #0099cc;
  --danger: #dd3333;
  --toggle-bg: #c0c0cc;
  --toggle-bg-active: #00994d;
  --toggle-knob: #ffffff;
  --btn-primary-bg: linear-gradient(135deg, #d63250 0%, #b02840 100%);
  --card-gradient: linear-gradient(135deg, #ffffff 0%, #f8f8fc 100%);
  --sidebar-bg-from: #eaeaf0;
  --sidebar-bg-to: #f0f0f6;
  --scrollbar-thumb: #ccccd4;
  --scrollbar-thumb-hover: #b0b0bc;
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
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
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
