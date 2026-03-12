<template>
  <div class="feishu-page">
    <header class="page-header">
      <div class="header-main">
        <div class="title-row">
          <span class="icon-feishu">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21.5 12a9.5 9.5 0 1 1-19 0 9.5 9.5 0 0 1 19 0Z" stroke="currentColor" stroke-width="2"/>
              <path d="M8 12h8m-4-4v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </span>
          <h2>Feishu Integration</h2>
        </div>
        <p class="subtitle">Configure Feishu/Lark bot and monitor message traffic</p>
      </div>
      <div class="header-status">
        <div class="status-badge" :class="{ connected: feishuConnected }">
          <div class="status-dot"></div>
          <span>{{ feishuConnected ? 'Connected' : 'Disconnected' }}</span>
        </div>
      </div>
    </header>

    <div class="page-content">
      <!-- Left Sidebar: Configuration -->
      <aside class="sidebar">
        <div class="panel config-panel">
          <div class="panel-header">
            <h3>Configuration</h3>
          </div>
          <div class="panel-body">
            <div class="form-group">
              <label>App ID</label>
              <input 
                type="text" 
                v-model="config.app_id" 
                placeholder="cli_..." 
                :disabled="feishuConnected"
                class="input-field"
              />
            </div>
            
            <div class="form-group">
              <label>App Secret</label>
              <input 
                type="password" 
                v-model="config.app_secret" 
                placeholder="••••••••" 
                :disabled="feishuConnected"
                class="input-field"
              />
            </div>

            <div class="form-group">
              <label>Upstream AI URL</label>
              <input 
                type="text" 
                v-model="config.upstream_url" 
                placeholder="https://api.openai.com/v1" 
                class="input-field"
              />
            </div>

            <div class="form-group">
              <label>Model</label>
              <input 
                type="text" 
                v-model="config.model" 
                placeholder="gpt-4" 
                class="input-field"
              />
            </div>

            <div class="actions">
              <button class="btn-primary" @click="saveConfig" :disabled="feishuConnected">
                Save Changes
              </button>
              <button class="btn-secondary" @click="testConnection">
                Test Connection
              </button>
            </div>
          </div>
        </div>

        <div class="panel stats-panel">
          <div class="panel-header">
            <h3>Statistics</h3>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-label">Total</span>
              <span class="stat-value">{{ stats.total_messages }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Blocked</span>
              <span class="stat-value text-danger">{{ stats.blocked_messages }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Active</span>
              <span class="stat-value">{{ stats.active_chats }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Latency</span>
              <span class="stat-value">{{ stats.avg_response_time }}ms</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Content: Traffic Log -->
      <main class="main-view">
        <div class="toolbar">
          <div class="toolbar-left">
            <div class="search-box">
              <span class="search-icon">🔍</span>
              <input v-model="searchQuery" placeholder="Search messages..." />
            </div>
            <select v-model="verdictFilter" class="filter-select">
              <option value="">All Verdicts</option>
              <option value="ALLOW">Allow</option>
              <option value="BLOCK">Block</option>
              <option value="ESCALATE">Escalate</option>
            </select>
          </div>
          <button class="btn-icon" @click="clearEvents" title="Clear Logs">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>

        <div class="traffic-list" ref="waterfallEl">
          <div 
            v-for="(event, idx) in filteredEvents" 
            :key="idx"
            class="traffic-item"
            :class="{ 
              'is-blocked': event.analysis?.verdict === 'BLOCK',
              'is-escalated': event.analysis?.verdict === 'ESCALATE',
              'is-alert': event.is_alert,
              'is-expanded': selectedEvent === event
            }"
            @click="toggleEvent(event)"
          >
            <div class="item-summary">
              <div class="item-meta">
                <span class="time">{{ formatTime(event.timestamp) }}</span>
                <span class="badge verdict" :class="event.analysis?.verdict?.toLowerCase() || 'allow'">
                  {{ event.analysis?.verdict || 'ALLOW' }}
                </span>
                <span class="method">{{ event.method }}</span>
              </div>
              <div class="item-preview">
                {{ event.payload_preview }}
              </div>
              <div class="item-id">
                {{ event.session_id?.slice(0, 8) }}
              </div>
            </div>

            <div v-if="selectedEvent === event" class="item-details" @click.stop>
              <div class="detail-grid">
                <div class="detail-group">
                  <label>Session ID</label>
                  <code>{{ event.session_id }}</code>
                </div>
                <div class="detail-group">
                  <label>Agent</label>
                  <span>{{ event.agent_id }}</span>
                </div>
                <div class="detail-group" v-if="event.analysis?.l2_reasoning">
                  <label>Reasoning</label>
                  <p class="reasoning-text">{{ event.analysis.l2_reasoning }}</p>
                </div>
                <div class="detail-group full-width">
                  <label>Full Payload</label>
                  <pre class="code-block">{{ event.payload_preview }}</pre>
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredEvents.length === 0" class="empty-state">
            <div class="empty-icon">📡</div>
            <h3>No Traffic</h3>
            <p>Send messages to the Feishu bot to see them here.</p>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const props = defineProps<{
  // If needed
}>()

// State
const config = ref({
  app_id: '',
  app_secret: '',
  upstream_url: 'https://api.openai.com/v1',
  model: 'gpt-4'
})

const stats = ref({
  total_messages: 0,
  blocked_messages: 0,
  active_chats: 0,
  avg_response_time: 0
})

const events = ref<any[]>([])
const feishuConnected = ref(false)
const searchQuery = ref('')
const verdictFilter = ref('')
const selectedEvent = ref<any>(null)
const waterfallEl = ref<HTMLElement | null>(null)

// Computed
const filteredEvents = computed(() => {
  return events.value.filter(e => {
    if (verdictFilter.value && e.analysis?.verdict !== verdictFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return (
        e.payload_preview?.toLowerCase().includes(q) ||
        e.session_id?.toLowerCase().includes(q)
      )
    }
    return true
  })
})

// Methods
function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString()
}

function toggleEvent(event: any) {
  selectedEvent.value = selectedEvent.value === event ? null : event
}

function clearEvents() {
  events.value = []
}

async function saveConfig() {
  // Mock save
  console.log('Saving config:', config.value)
  // In real implementation, POST to backend
}

async function testConnection() {
  // Mock test
  feishuConnected.value = true
}

// Mock data stream
onMounted(() => {
  // Simulate incoming traffic
  setInterval(() => {
    if (Math.random() > 0.7) {
      const isBlock = Math.random() > 0.8
      events.value.unshift({
        timestamp: Date.now(),
        method: 'POST /message',
        session_id: crypto.randomUUID(),
        agent_id: 'feishu-bot',
        payload_preview: isBlock ? 'User sent a restricted keyword...' : 'Hello, can you help me with...',
        analysis: {
          verdict: isBlock ? 'BLOCK' : 'ALLOW',
          l2_reasoning: isBlock ? 'Policy violation detected: Sensitive topic' : undefined
        }
      })
      
      // Update stats
      stats.value.total_messages++
      if (isBlock) stats.value.blocked_messages++
      
      // Keep list manageable
      if (events.value.length > 100) events.value.pop()
    }
  }, 3000)
})
</script>

<style scoped>
.feishu-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.page-header {
  height: 60px;
  padding: 0 24px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-main .title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-feishu {
  color: #00d6b9; /* Feishu/Lark brand color */
  width: 24px;
  height: 24px;
  display: flex;
}

.header-main h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 2px 0 0 36px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  background: var(--bg-secondary);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.status-badge.connected {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

/* Layout */
.page-content {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
}

.panel-header h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--text-secondary);
}

.input-field {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  transition: all 0.2s;
}

.input-field:focus {
  border-color: var(--accent);
  outline: none;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 24px;
}

.btn-primary, .btn-secondary {
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--accent);
  color: white;
  border: none;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background: var(--bg-secondary);
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stat-item {
  background: var(--bg-secondary);
  padding: 12px;
  border-radius: 8px;
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.text-danger {
  color: #ff6b6b;
}

/* Main View */
.main-view {
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.toolbar {
  height: 50px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-surface);
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.search-box {
  position: relative;
  width: 240px;
}

.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--text-secondary);
}

.search-box input {
  width: 100%;
  padding: 6px 12px 6px 28px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 13px;
}

.filter-select {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 4px;
  padding: 0 8px;
  font-size: 13px;
}

.btn-icon {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.btn-icon:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* Traffic List */
.traffic-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.traffic-item {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.traffic-item:hover {
  border-color: var(--text-secondary);
}

.traffic-item.is-expanded {
  border-color: var(--accent);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.traffic-item.is-blocked {
  border-left: 4px solid #ff6b6b;
}

.traffic-item.is-escalated {
  border-left: 4px solid #feca57;
}

.item-summary {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.time {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.allow { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.badge.block { background: rgba(255, 107, 107, 0.1); color: #ff6b6b; }
.badge.escalate { background: rgba(254, 202, 87, 0.1); color: #feca57; }

.method {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.item-preview {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  color: var(--text-primary);
}

.item-id {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-secondary);
}

/* Details */
.item-details {
  border-top: 1px solid var(--border);
  padding: 16px;
  background: var(--bg-secondary);
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.detail-group label {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.detail-group code, .detail-group span {
  font-size: 13px;
  color: var(--text-primary);
}

.full-width {
  grid-column: span 2;
}

.reasoning-text {
  font-size: 13px;
  color: #ff6b6b;
  margin: 0;
}

.code-block {
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--border);
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  margin: 0;
  color: var(--text-primary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}
</style>
