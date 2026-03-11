<template>
  <div class="app-shell" :data-theme="theme">
    <!-- Icon Rail -->
    <nav class="icon-rail">
      <div class="rail-brand">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
      </div>

      <div class="rail-nav">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="rail-btn"
          :class="{ active: currentSection === item.id, separator: item.separator, primary: item.primary }"
          :title="item.label"
          @click="navigateTo(item.id)"
        >
          <span class="rail-icon" v-html="item.icon"></span>
          <span v-if="item.badge" class="rail-badge" :class="item.badgeType">{{ item.badge }}</span>
        </button>
      </div>

      <div class="rail-footer">
        <button class="rail-btn" :title="theme === 'dark' ? 'Light Mode' : 'Dark Mode'" @click="toggleTheme">
          <span class="rail-icon" v-html="theme === 'dark' ? icons.sun : icons.moon"></span>
        </button>
        <div class="rail-status" :class="{ connected }" :title="connected ? 'Firewall connected' : 'Disconnected'"></div>
      </div>
    </nav>

    <!-- Main workspace -->
    <div class="workspace">
      <!-- Top Bar -->
      <header class="top-bar">
        <div class="top-left">
          <h1 class="page-title">{{ activePageTitle }}</h1>
        </div>
        <div class="top-spacer"></div>
        <div class="top-right">
          <div class="top-stats" v-if="stats">
            <span class="stat-pill">
              <span class="stat-dot green"></span>
              {{ stats.active_sessions ?? 0 }} sessions
            </span>
            <span class="stat-pill" v-if="stats.audit?.blocked">
              <span class="stat-dot red"></span>
              {{ stats.audit.blocked }} blocked
            </span>
          </div>
          <button
            class="traffic-toggle"
            :class="{ active: showTraffic }"
            @click="showTraffic = !showTraffic"
            title="Toggle Traffic Panel"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </button>
          <a class="github-link" href="https://github.com/IsaacHuo/agent-firewall" target="_blank" rel="noopener noreferrer" title="GitHub Repository">
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
            </svg>
          </a>
        </div>
      </header>

      <!-- Content split -->
      <div class="content-split">
        <!-- Left: Active page -->
        <div class="content-main" :class="{ 'full-width': !showTraffic }">
          <!-- KeepAlive preserves ChatLab state & streaming across tab switches -->
          <KeepAlive>
            <ChatLab v-if="currentSection === 'chat'" :events="events" />
          </KeepAlive>
          <SchematicDiagram v-if="currentSection === 'schematic'" />
          <RulesConfig v-if="currentSection === 'rules'" :rules="rulesData" @save="handleSaveRule" @delete="handleDeleteRule" @toggle="handleToggleRule" @updateMethodAction="handleUpdateMethodAction" @updateDefaultAction="(a: string) => handleUpdateDefaultAction(a as RuleAction)" />
          <EngineSettings v-if="currentSection === 'engine'" :config="config" :saving="configSaving" @save="handleSaveConfig" />
          <RateLimitSettings v-if="currentSection === 'rate-limit'" :config="config?.rate_limit ?? { requests_per_sec: 10, burst: 20 }" @save="handleSaveRateLimit" />
          <SecurityTest v-if="currentSection === 'test'" :results="testResults" :running="testRunning" @run="handleRunTest" @runAll="handleRunAllTests" @clear="clearTestResults" />
          <AuditLog v-if="currentSection === 'audit'" :entries="auditEntries" :loading="auditLoading" :hasMore="auditHasMore" @load="handleLoadAudit" @loadMore="handleLoadMoreAudit" />
          <SkillsManager v-if="currentSection === 'skills'" />
          <AgentsManager v-if="currentSection === 'agents'" />
          <FeishuConfig v-if="currentSection === 'feishu'" />
          <GatewayConfig v-if="currentSection === 'gateway-config'" />
        </div>

        <!-- Resize handle -->
        <div v-if="showTraffic" class="resize-handle" @mousedown="startResize"></div>

        <!-- Right: Persistent Traffic Waterfall -->
        <div class="content-traffic" :class="{ collapsed: !showTraffic }">
          <TrafficWaterfall :events="events" :compact="true" @clear="clearEvents" @verdict="handleVerdict" />
        </div>
      </div>

      <!-- Status Bar -->
      <footer class="status-bar">
        <div class="status-left">
          <span class="status-item" :class="{ connected }">
            <span class="status-indicator"></span>
            {{ connected ? 'Online' : 'Offline' }}
          </span>
          <span class="status-sep">|</span>
          <span class="status-item" v-if="stats">{{ formatUptime(stats.uptime_seconds) }}</span>
        </div>
        <div class="status-right">
          <span class="status-item">{{ events.length }} events</span>
          <span class="status-sep">|</span>
          <span class="status-item mono">{{ currentSection }}</span>
        </div>
      </footer>
    </div>

    <!-- Command Palette -->
    <Teleport to="body">
      <div v-if="showCommandPalette" class="cmd-overlay" @click.self="showCommandPalette = false">
        <div class="cmd-palette">
          <input ref="cmdInput" v-model="cmdQuery" class="cmd-input" placeholder="Type a command..." @keydown.esc="showCommandPalette = false" @keydown.enter="executeCommand" />
          <div class="cmd-list">
            <button v-for="cmd in filteredCommands" :key="cmd.id" class="cmd-item" @click="executeCommand(cmd)">
              <span class="cmd-icon" v-html="cmd.icon"></span>
              <span class="cmd-label">{{ cmd.label }}</span>
              <kbd v-if="cmd.shortcut" class="cmd-shortcut">{{ cmd.shortcut }}</kbd>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import type { FirewallConfig, PatternRule, TestPayload, RuleAction, RateLimitConfig, NavSection } from './types'
import {
  useWebSocket, useStats, useConfig, useRules, useSecurityTest,
  useAuditLog, useNavigation, useTheme, useGateway,
} from './composables'

import AuditLog from './components/AuditLog.vue'
import ChatLab from './components/ChatLab.vue'
import SkillsManager from './components/SkillsManager.vue'
import AgentsManager from './components/AgentsManager.vue'
import GatewayConfig from './components/GatewayConfig.vue'
import FeishuConfig from './components/FeishuConfig.vue'
import TrafficWaterfall from './components/TrafficWaterfall.vue'
import RulesConfig from './components/RulesConfig.vue'
import EngineSettings from './components/EngineSettings.vue'
import RateLimitSettings from './components/RateLimitSettings.vue'
import SecurityTest from './components/SecurityTest.vue'
import SchematicDiagram from './components/SchematicDiagram.vue'

const icons = {
  chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  schematic: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><line x1="10" y1="6.5" x2="14" y2="6.5"/><line x1="10" y1="17.5" x2="14" y2="17.5"/><line x1="6.5" y1="10" x2="6.5" y2="14"/><line x1="17.5" y1="10" x2="17.5" y2="14"/></svg>`,
  rules: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
  engine: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  rateLimit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  test: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
  audit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  skills: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  agents: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  config: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  feishu: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
}

// Composables
const { connected, events, clearEvents, sendVerdict } = useWebSocket()
const { stats } = useStats()
useGateway()
const { config, saving: configSaving, loadConfig, saveConfig } = useConfig()
const { rules: rulesData, loadRules, saveRule, deleteRule, toggleRule } = useRules()
const { results: testResults, running: testRunning, runTest, runBatch, clearResults: clearTestResults } = useSecurityTest()
const { entries: auditEntries, loading: auditLoading, hasMore: auditHasMore, loadEntries: loadAuditEntries, loadMore: loadMoreAudit } = useAuditLog()
const { currentSection, navigateTo } = useNavigation()
const { theme, toggleTheme } = useTheme()

const showTraffic = ref(true)
const showCommandPalette = ref(false)
const cmdQuery = ref('')
const cmdInput = ref<HTMLInputElement | null>(null)

const navItems = computed(() => [
  { id: 'chat' as const, label: 'Chat Lab', icon: icons.chat, group: 'main', primary: true },
  { id: 'schematic' as const, label: '架构示意图', icon: icons.schematic, group: 'main' },
  { id: 'rules' as const, label: 'Rules', icon: icons.rules, group: 'security', separator: true },
  { id: 'engine' as const, label: 'Engine', icon: icons.engine, group: 'security' },
  { id: 'rate-limit' as const, label: 'Rate Limit', icon: icons.rateLimit, group: 'security' },
  { id: 'test' as const, label: 'Security Test', icon: icons.test, group: 'security' },
  { id: 'audit' as const, label: 'Audit Log', icon: icons.audit, group: 'security', badge: stats.value?.audit?.blocked ?? 0, badgeType: stats.value?.audit?.blocked ? 'danger' : undefined },
  { id: 'agents' as const, label: 'Agents', icon: icons.agents, group: 'agent', separator: true },
  { id: 'skills' as const, label: 'Skills', icon: icons.skills, group: 'agent' },
  { id: 'feishu' as const, label: 'Feishu Channel', icon: icons.feishu, group: 'channels', separator: true },
  { id: 'gateway-config' as const, label: 'Settings', icon: icons.config, group: 'settings', separator: true },
])

const activePageTitle = computed(() => {
  const item = navItems.value.find(i => i.id === currentSection.value)
  return item?.label ?? 'Agent Firewall'
})

const commands = computed(() => [
  { id: 'chat', label: 'Go to Chat Lab', icon: icons.chat, action: () => navigateTo('chat') },
  { id: 'rules', label: 'Go to Rules', icon: icons.rules, action: () => navigateTo('rules') },
  { id: 'traffic-toggle', label: 'Toggle Traffic Panel', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`, action: () => { showTraffic.value = !showTraffic.value } },
  { id: 'test', label: 'Security Test', icon: icons.test, action: () => navigateTo('test') },
  { id: 'audit', label: 'Audit Log', icon: icons.audit, action: () => navigateTo('audit') },
  { id: 'theme', label: 'Toggle Theme', icon: theme.value === 'dark' ? icons.sun : icons.moon, shortcut: '⌘⇧T', action: () => toggleTheme() },
  { id: 'clear', label: 'Clear Traffic', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`, action: () => clearEvents() },
])

const filteredCommands = computed(() => {
  if (!cmdQuery.value) return commands.value
  const q = cmdQuery.value.toLowerCase()
  return commands.value.filter(c => c.label.toLowerCase().includes(q))
})

function executeCommand(cmd?: any) {
  const target = cmd?.action ? cmd : filteredCommands.value[0]
  if (target?.action) {
    target.action()
    showCommandPalette.value = false
    cmdQuery.value = ''
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    showCommandPalette.value = !showCommandPalette.value
  }
}

watch(showCommandPalette, (v) => {
  if (v) nextTick(() => cmdInput.value?.focus())
})

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  loadConfig()
  loadRules()
  loadAuditEntries({ limit: 50 })
})
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))

// Resize handle
function startResize(e: MouseEvent) {
  e.preventDefault()
  const startX = e.clientX
  const trafficEl = document.querySelector('.content-traffic') as HTMLElement
  if (!trafficEl) return
  const startWidth = trafficEl.offsetWidth

  function onMove(ev: MouseEvent) {
    const delta = startX - ev.clientX
    const w = Math.max(280, Math.min(startWidth + delta, window.innerWidth * 0.55))
    trafficEl.style.width = `${w}px`
    trafficEl.style.flex = 'none'
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// Event handlers
function handleVerdict(requestId: string, action: 'allow' | 'block') { sendVerdict(requestId, action) }
function handleSaveRule(rule: PatternRule) { saveRule(rule) }
function handleDeleteRule(ruleId: string) { deleteRule(ruleId) }
function handleToggleRule(ruleId: string, enabled: boolean) { toggleRule(ruleId, enabled) }
function handleUpdateMethodAction() { saveConfig({ blocked_commands: config.value?.blocked_commands }) }
function handleUpdateDefaultAction(action: RuleAction) { rulesData.value.default_action = action }
function handleSaveConfig(newConfig: Partial<FirewallConfig>) { saveConfig(newConfig) }
function handleSaveRateLimit(rateLimit: RateLimitConfig) { saveConfig({ rate_limit: rateLimit }) }
function handleRunTest(payload: TestPayload) { runTest(payload) }
function handleRunAllTests(payloads: TestPayload[]) { runBatch(payloads) }
function handleLoadAudit(options: { verdict?: string; since?: number }) { loadAuditEntries(options) }
function handleLoadMoreAudit() { loadMoreAudit() }

function formatUptime(s: number): string {
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root, [data-theme="dark"] {
  /* Modern Zinc Palette */
  --bg-primary: #09090b;
  --bg-secondary: #121215; /* Slightly lighter than primary */
  --bg-elevated: #1c1c21;
  --bg-surface: #121215;
  --bg-hover: rgba(255,255,255,0.06);
  --bg-active: rgba(255,255,255,0.1);
  
  --overlay-bg: rgba(0,0,0,0.75);
  --backdrop-blur: blur(16px);
  
  --border: #27272a;
  --border-hover: #3f3f46;
  --border-active: #52525b;
  --border-subtle: #27272a;
  
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted: #71717a;
  --text-dim: #52525b;
  --text-disabled: #3f3f46;
  
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --accent-muted: rgba(59,130,246,0.15);
  
  --accent-red: #ef4444;
  --accent-red-muted: rgba(239,68,68,0.15);
  --accent-green: #10b981;
  --accent-green-muted: rgba(16,185,129,0.15);
  --accent-yellow: #f59e0b;
  --accent-yellow-muted: rgba(245,158,11,0.15);
  --accent-orange: #f97316;
  --accent-purple: #8b5cf6;
  --accent-cyan: #06b6d4;
  
  --danger: #ef4444;
  
  --toggle-bg: #3f3f46;
  --toggle-bg-active: #10b981;
  --toggle-knob: #ffffff;
  
  --rail-bg: #09090b;
  --rail-border: #27272a;
  
  --scrollbar-thumb: rgba(255,255,255,0.1);
  --scrollbar-thumb-hover: rgba(255,255,255,0.2);
  
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', monospace;
  
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
}

[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f4f4f5;
  --bg-elevated: #ffffff;
  --bg-surface: #ffffff;
  --bg-hover: rgba(0,0,0,0.04);
  --bg-active: rgba(0,0,0,0.06);
  --overlay-bg: rgba(0,0,0,0.4);
  --border: #e4e4e7;
  --border-hover: #d4d4d8;
  --border-active: #a1a1aa;
  --border-subtle: #f4f4f5;
  --text-primary: #18181b;
  --text-secondary: #52525b;
  --text-muted: #71717a;
  --text-dim: #a1a1aa;
  --text-disabled: #d4d4d8;
  --accent: #2563eb;
  --accent-hover: #3b82f6;
  --accent-muted: rgba(37,99,235,0.1);
  --accent-red: #dc2626;
  --accent-red-muted: rgba(220,38,38,0.1);
  --accent-green: #059669;
  --accent-green-muted: rgba(5,150,105,0.1);
  --accent-yellow: #d97706;
  --accent-yellow-muted: rgba(217,119,6,0.1);
  --accent-orange: #ea580c;
  --accent-purple: #7c3aed;
  --accent-cyan: #0891b2;
  --danger: #dc2626;
  --toggle-bg: #e4e4e7;
  --toggle-bg-active: #059669;
  --toggle-knob: #ffffff;
  --rail-bg: #f4f4f5;
  --rail-border: #e4e4e7;
  --scrollbar-thumb: rgba(0,0,0,0.15);
  --scrollbar-thumb-hover: rgba(0,0,0,0.25);
}

body {
  font-family: var(--font-sans);
  background: var(--bg-primary);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  font-size: 14px;
  line-height: 1.5;
  transition: background 0.3s, color 0.3s;
}

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
::selection { background: var(--accent-muted); color: var(--text-primary); }
input, textarea, select, button { font-family: inherit; font-size: inherit; }

/* ── Global styles for sub-page components ── */
.content-main .page-header h2 { font-size: 18px; font-weight: 600; margin-bottom: 4px; color: var(--text-primary); }
.content-main .subtitle { font-size: 13px; color: var(--text-muted); margin-bottom: 16px; }
.content-main .page-header { margin-bottom: 20px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 16px; }
.content-main h3 { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.content-main h4 { font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 6px; }

/* Page-level padding */
.content-main .rules-page,
.content-main .engine-page,
.content-main .rate-limit-page,
.content-main .test-page,
.content-main .audit-page,
.content-main .skills-page,
.content-main .agents-page,
.content-main .config-page { padding: 24px; max-width: 1200px; margin: 0 auto; width: 100%; }

/* Cards & panels */
.content-main .stat-card,
.content-main .card,
.content-main .settings-card,
.content-main .section-content,
.content-main .panel,
.content-main .payload-card,
.content-main .skill-card {
  padding: 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s, border-color 0.2s;
}
.content-main .card:hover { border-color: var(--border-hover); box-shadow: var(--shadow-md); }

.content-main .card-header { padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; }
.content-main .card-body { padding: 16px; }

/* Buttons */
.content-main .btn,
.content-main .btn-primary,
.content-main .btn-secondary,
.content-main .btn-sm,
.content-main .action-btn {
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* Form controls */
.content-main .form-group { margin-bottom: 16px; }
.content-main .form-group label { font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block; color: var(--text-secondary); }
.content-main .form-input,
.content-main .form-input-sm,
.content-main .form-select,
.content-main .filter-input,
.content-main .filter-select,
.content-main .field-input,
.content-main .search-input {
  font-size: 13px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: border-color 0.2s, box-shadow 0.2s;
  width: 100%;
}
.content-main .form-input:focus,
.content-main .form-select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-muted);
}
.content-main .form-hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

/* Tabs */
.content-main .rule-tab,
.content-main .cat-tab,
.content-main .mode-btn,
.content-main .section-nav-item { font-size: 11px !important; padding: 6px 12px !important; }

/* Tables */
.content-main .audit-table { font-size: 11px !important; }
.content-main .audit-table th { font-size: 10px !important; padding: 8px 10px !important; }
.content-main .audit-table td { padding: 6px 10px !important; }

/* Badges & chips */
.content-main .badge,
.content-main .chip,
.content-main .verdict-tag,
.content-main .threat-tag { font-size: 9px !important; padding: 1px 6px !important; }

/* Info fields (agents/skills) */
.content-main .info-label { font-size: 10px !important; }
.content-main .info-value { font-size: 12px !important; }
.content-main .agent-name,
.content-main .skill-name,
.content-main .rule-name,
.content-main .method-name { font-size: 12px !important; }
.content-main .skill-description,
.content-main .rule-description,
.content-main .card-description { font-size: 11px !important; }
.content-main .payload-name { font-size: 12px !important; }
.content-main .payload-code { font-size: 10px !important; }

/* Misc text */
.content-main .engine-name,
.content-main .alert-method { font-size: 11px !important; }
.content-main .bucket-label { font-size: 12px !important; }
.content-main .tool-name,
.content-main .skill-row-name { font-size: 11px !important; }
.content-main .raw-editor { font-size: 11px !important; }
</style>

<style scoped>
.app-shell { height: 100vh; display: flex; overflow: hidden; background: var(--bg-primary); }

/* Navigation Rail */
.icon-rail {
  width: 64px; display: flex; flex-direction: column; align-items: center;
  background: var(--rail-bg); border-right: 1px solid var(--rail-border); z-index: 20;
  padding-top: 16px; flex-shrink: 0;
}
.rail-brand { margin-bottom: 20px; display: flex; justify-content: center; }
.brand-icon {
  width: 36px; height: 36px; background: var(--accent); border-radius: 10px;
  display: flex; align-items: center; justify-content: center; color: white;
  box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}
.brand-icon svg { width: 22px; height: 22px; }

.rail-nav { flex: 1; width: 100%; padding: 0 8px; display: flex; flex-direction: column; align-items: center; gap: 8px; overflow-y: auto; }
.rail-btn {
  position: relative; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 12px; background: transparent; color: var(--text-muted);
  cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.rail-btn.primary { margin-bottom: 8px; background: var(--accent-muted); color: var(--accent); }
.rail-btn.primary:hover { background: var(--accent); color: #fff; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59,130,246,0.4); }
.rail-btn.primary.active { background: var(--accent); color: #fff; box-shadow: 0 2px 8px rgba(var(--accent-rgb, 99,102,241), 0.3); }

.rail-btn.separator { margin-top: 12px; }
.rail-btn.separator::before { content: ''; position: absolute; top: -8px; left: 8px; right: 8px; height: 1px; background: var(--border-subtle); }

.rail-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.rail-btn.active { background: var(--bg-active); color: var(--text-primary); }
.rail-btn.active::after {
  content: ''; position: absolute; left: -10px; top: 10px; bottom: 10px; width: 4px;
  background: var(--text-primary); border-radius: 0 4px 4px 0;
}

.rail-icon { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; }
.rail-icon :deep(svg) { width: 100%; height: 100%; stroke-width: 1.8px; }

.rail-badge {
  position: absolute; top: 4px; right: 4px; min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: 8px; font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center;
  background: var(--danger); color: white; border: 2px solid var(--rail-bg);
}
.rail-footer { width: 100%; padding: 16px 0; display: flex; flex-direction: column; align-items: center; gap: 12px; border-top: 1px solid var(--border-subtle); }
.rail-status { width: 7px; height: 7px; border-radius: 50%; background: var(--text-disabled); transition: all 0.3s; }
.rail-status.connected { background: var(--accent-green); box-shadow: 0 0 6px rgba(34,197,94,0.4); }

/* Workspace */
.workspace { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

/* Top Bar */
.top-bar { height: 44px; display: flex; align-items: center; padding: 0 14px; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; gap: 12px; }
.top-left { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.page-title { font-size: 12px; font-weight: 600; color: var(--text-primary); white-space: nowrap; letter-spacing: -0.01em; }
.top-spacer { flex: 1; }
.top-right { display: flex; align-items: center; gap: 10px; min-width: 140px; justify-content: flex-end; }
.top-stats { display: flex; gap: 6px; }
.stat-pill { display: flex; align-items: center; gap: 4px; padding: 2px 8px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 12px; font-size: 10px; color: var(--text-muted); white-space: nowrap; }
.stat-dot { width: 5px; height: 5px; border-radius: 50%; }
.stat-dot.green { background: var(--accent-green); }
.stat-dot.red { background: var(--accent-red); }
.traffic-toggle {
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface);
  color: var(--text-dim); cursor: pointer; transition: all 0.15s;
}
.traffic-toggle:hover { border-color: var(--border-hover); color: var(--text-secondary); }
.traffic-toggle.active { background: var(--accent-muted); color: var(--accent); border-color: var(--accent); }
.github-link {
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface);
  color: var(--text-dim); cursor: pointer; transition: all 0.15s; text-decoration: none;
}
.github-link:hover { border-color: var(--border-hover); color: var(--text-secondary); }

/* Content Split */
.content-split { flex: 1; display: flex; position: relative; overflow: hidden; }
.content-main { flex: 1; min-width: 0; overflow-y: auto; overflow-x: hidden; display: flex; flex-direction: column; }
.content-main.full-width { border-right: none; }
.content-traffic { width: 420px; flex-shrink: 0; overflow: hidden; transition: width 0.2s ease; display: flex; flex-direction: column; border-left: 1px solid var(--border); }
.content-traffic.collapsed { width: 0; border-left: none; }
.resize-handle {
  position: absolute; top: 0; bottom: 0; width: 4px; cursor: col-resize; z-index: 5;
  background: transparent; transition: background 0.15s;
  /* positioned dynamically via the traffic panel */
  right: calc(420px - 2px);
}
.resize-handle:hover, .resize-handle:active { background: var(--accent); }

/* Status Bar */
.status-bar {
  height: 22px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 10px; background: var(--bg-secondary); border-top: 1px solid var(--border); flex-shrink: 0;
}
.status-left, .status-right { display: flex; align-items: center; gap: 8px; }
.status-item { display: flex; align-items: center; gap: 3px; color: var(--text-dim); font-size: 10px; }
.status-item.connected .status-indicator { background: var(--accent-green); }
.status-item.connected { color: var(--text-muted); }
.status-indicator { width: 5px; height: 5px; border-radius: 50%; background: var(--text-disabled); }
.status-item.mono { font-family: var(--font-mono); font-size: 9px; }
.status-sep { color: var(--text-disabled); font-size: 10px; }

/* Command Palette */
.cmd-overlay { position: fixed; inset: 0; z-index: 1000; background: var(--overlay-bg); backdrop-filter: var(--backdrop-blur); display: flex; justify-content: center; padding-top: 18vh; }
.cmd-palette { width: 480px; max-height: 360px; background: var(--bg-elevated); border: 1px solid var(--border-hover); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg); overflow: hidden; display: flex; flex-direction: column; }
.cmd-input { width: 100%; padding: 12px 16px; background: transparent; border: none; border-bottom: 1px solid var(--border); color: var(--text-primary); font-size: 14px; outline: none; }
.cmd-input::placeholder { color: var(--text-dim); }
.cmd-list { flex: 1; overflow-y: auto; padding: 4px; }
.cmd-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none; border-radius: var(--radius-md); background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 12px; text-align: left; transition: background 0.1s; }
.cmd-item:hover { background: var(--bg-hover); }
.cmd-icon { width: 14px; height: 14px; display: flex; align-items: center; justify-content: center; color: var(--text-dim); }
.cmd-icon :deep(svg) { width: 100%; height: 100%; }
.cmd-label { flex: 1; }
.cmd-shortcut { padding: 1px 5px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 3px; font-size: 9px; color: var(--text-dim); }
</style>
