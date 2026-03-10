<template>
  <div class="feishu-channel">
    <!-- Header -->
    <div class="channel-header">
      <div class="header-left">
        <h2>飞书通道 (Feishu/Lark)</h2>
        <div class="status-badge" :class="{ connected: feishuConnected }">
          <div class="status-dot"></div>
          <span>{{ feishuConnected ? '已连接' : '未连接' }}</span>
        </div>
      </div>
      <div class="header-right">
        <button class="btn-secondary" @click="showConfig = !showConfig">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          配置
        </button>
      </div>
    </div>

    <!-- Main Content: Split view -->
    <div class="channel-content">
      <!-- Left: Stats & Config -->
      <div class="content-left" :class="{ collapsed: !showConfig }">
        <!-- Quick Stats -->
        <div class="stats-section">
          <h3>消息统计</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-icon">📨</div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.total_messages }}</div>
                <div class="stat-label">Total Messages</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">🚫</div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.blocked_messages }}</div>
                <div class="stat-label">Blocked</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">💬</div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.active_chats }}</div>
                <div class="stat-label">Active Chats</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">⚡</div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.avg_response_time }}ms</div>
                <div class="stat-label">Avg Response</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Configuration (collapsible) -->
        <div v-if="showConfig" class="config-section">
          <h3>通道配置</h3>

          <div class="config-group">
            <label>App ID</label>
            <input
              type="text"
              v-model="config.app_id"
              placeholder="cli_xxxxxxxxxxxxx"
              :disabled="feishuConnected"
            />
          </div>

          <div class="config-group">
            <label>App Secret</label>
            <input
              type="password"
              v-model="config.app_secret"
              placeholder="Enter app secret"
              :disabled="feishuConnected"
            />
          </div>

          <div class="config-group">
            <label>Upstream AI URL</label>
            <input
              type="text"
              v-model="config.upstream_url"
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div class="config-group">
            <label>Model</label>
            <input
              type="text"
              v-model="config.model"
              placeholder="gpt-4"
            />
          </div>

          <div class="config-actions">
            <button class="btn-primary" @click="saveConfig" :disabled="feishuConnected">
              保存配置
            </button>
            <button class="btn-secondary" @click="testConnection">
              测试连接
            </button>
          </div>
        </div>
      </div>

      <!-- Right: Traffic Waterfall -->
      <div class="content-right">
        <div class="traffic-header">
          <h3>飞书消息流量</h3>
          <div class="traffic-controls">
            <select v-model="verdictFilter" class="filter-select">
              <option value="">All</option>
              <option value="ALLOW">Allow</option>
              <option value="BLOCK">Block</option>
              <option value="ESCALATE">Escalate</option>
            </select>
            <input v-model="searchQuery" class="filter-input" placeholder="搜索..." />
            <button class="btn-icon" @click="clearEvents" title="Clear">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Waterfall List -->
        <div class="waterfall-container" ref="waterfallEl">
          <div
            v-for="(event, idx) in filteredEvents"
            :key="idx"
            class="wf-row"
            :class="{
              alert: event.is_alert,
              blocked: event.analysis?.verdict === 'BLOCK',
              escalated: event.analysis?.verdict === 'ESCALATE',
              selected: selectedEvent === event,
            }"
            @click="selectedEvent = selectedEvent === event ? null : event"
          >
            <div class="wf-main">
              <span class="wf-time">{{ formatTime(event.timestamp) }}</span>
              <span class="wf-verdict" :class="(event.analysis?.verdict || 'ALLOW').toLowerCase()">
                {{ (event.analysis?.verdict || 'ALLOW').charAt(0) }}
              </span>
              <span class="wf-method">{{ event.method }}</span>
              <span class="wf-chat">{{ event.session_id?.slice(0, 8) }}</span>
            </div>
            <div class="wf-preview">{{ event.payload_preview?.slice(0, 100) }}</div>

            <!-- Expanded Detail -->
            <div v-if="selectedEvent === event" class="wf-detail" @click.stop>
              <div class="detail-row">
                <span class="detail-label">Chat ID:</span>
                <span class="detail-value mono">{{ event.session_id }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Sender:</span>
                <span class="detail-value">{{ event.agent_id }}</span>
              </div>
              <div v-if="event.analysis" class="detail-row">
                <span class="detail-label">Verdict:</span>
                <span class="verdict-badge" :class="event.analysis.verdict.toLowerCase()">
                  {{ event.analysis.verdict }}
                </span>
              </div>
              <div v-if="event.analysis?.l2_reasoning" class="detail-row">
                <span class="detail-label">Analysis:</span>
                <span class="detail-value">{{ event.analysis.l2_reasoning }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Content:</span>
                <pre class="detail-payload">{{ event.payload_preview }}</pre>
              </div>
            </div>
          </div>

          <div v-if="filteredEvents.length === 0" class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="48" height="48">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
            </svg>
            <p>暂无飞书消息</p>
            <p class="empty-hint">在飞书中向机器人发送消息，这里会显示流量记录</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const feishuConnected = ref(false)
const showConfig = ref(true)
const selectedEvent = ref<any>(null)
const verdictFilter = ref('')
const searchQuery = ref('')
const waterfallEl = ref<HTMLElement | null>(null)

const config = ref({
  app_id: '',
  app_secret: '',
  upstream_url: 'https://api.openai.com/v1',
  model: 'gpt-4',
})

const stats = ref({
  total_messages: 0,
  blocked_messages: 0,
  active_chats: 0,
  avg_response_time: 0,
})

// Mock events - will be replaced with real WebSocket data
const events = ref<any[]>([])

const filteredEvents = computed(() => {
  let result = events.value.filter((e: any) => e.event_type?.includes('feishu'))

  if (verdictFilter.value) {
    result = result.filter((e: any) => e.analysis?.verdict === verdictFilter.value)
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((e: any) =>
      e.payload_preview?.toLowerCase().includes(q) ||
      e.session_id?.toLowerCase().includes(q)
    )
  }

  return result
})

onMounted(async () => {
  await loadConfig()
  await loadStats()
  connectWebSocket()
})

async function loadConfig() {
  try {
    const response = await fetch('/api/feishu/config')
    if (response.ok) {
      const data = await response.json()
      config.value = { ...config.value, ...data }
      feishuConnected.value = data.connected || false
    }
  } catch (error) {
    console.error('Failed to load Feishu config:', error)
  }
}

async function loadStats() {
  try {
    const response = await fetch('/api/feishu/stats')
    if (response.ok) {
      const data = await response.json()
      stats.value = data
    }
  } catch (error) {
    console.error('Failed to load Feishu stats:', error)
  }
}

function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.hostname}:9090/ws/dashboard`)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      // Only add Feishu events
      if (data.event_type?.includes('feishu') || data.method?.includes('feishu')) {
        events.value.push(data)
        // Keep last 100 events
        if (events.value.length > 100) {
          events.value = events.value.slice(-100)
        }
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error)
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
}

async function saveConfig() {
  try {
    const response = await fetch('/api/feishu/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config.value),
    })
    if (response.ok) {
      alert('配置已保存！请重启服务以应用更改。')
    } else {
      alert('保存失败')
    }
  } catch (error) {
    console.error('Failed to save config:', error)
    alert('保存失败')
  }
}

async function testConnection() {
  alert('测试连接功能开发中...')
}

function clearEvents() {
  events.value = []
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.feishu-channel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

.channel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-left h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  font-size: 0.85rem;
}

.status-badge.connected {
  background: var(--success-bg);
  border-color: var(--success-color);
  color: var(--success-color);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-badge.connected .status-dot {
  background: var(--success-color);
  box-shadow: 0 0 8px var(--success-color);
}

.channel-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-left {
  width: 400px;
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  transition: width 0.3s;
}

.content-left.collapsed {
  width: 0;
  border-right: none;
}

.content-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stats-section,
.config-section {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.stats-section h3,
.config-section h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-secondary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.stat-icon {
  font-size: 1.5rem;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--primary-color);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-group {
  margin-bottom: 1rem;
}

.config-group label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.config-group input {
  width: 100%;
  padding: 0.625rem 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.config-group input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.config-group input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.config-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.btn-primary,
.btn-secondary,
.btn-icon {
  padding: 0.625rem 1rem;
  border-radius: 6px;
  font-weight: 500;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  flex: 1;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-secondary);
}

.btn-icon {
  padding: 0.5rem;
  background: transparent;
  border: 1px solid var(--border-color);
}

.btn-icon:hover {
  background: var(--bg-tertiary);
}

.traffic-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.traffic-header h3 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.traffic-controls {
  display: flex;
  gap: 0.5rem;
}

.filter-select,
.filter-input {
  padding: 0.375rem 0.625rem;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.filter-input {
  width: 150px;
}

.waterfall-container {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.wf-row {
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.wf-row:hover {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
}

.wf-row.blocked {
  border-left: 3px solid var(--danger-color);
}

.wf-row.escalated {
  border-left: 3px solid var(--warning-color);
}

.wf-row.selected {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
}

.wf-main {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
}

.wf-time {
  color: var(--text-tertiary);
  font-family: monospace;
}

.wf-verdict {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 0.75rem;
}

.wf-verdict.allow {
  background: var(--success-bg);
  color: var(--success-color);
}

.wf-verdict.block {
  background: var(--danger-bg);
  color: var(--danger-color);
}

.wf-verdict.escalate {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.wf-method {
  font-weight: 500;
  color: var(--text-primary);
}

.wf-chat {
  font-family: monospace;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.wf-preview {
  color: var(--text-secondary);
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-detail {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.detail-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}

.detail-label {
  min-width: 80px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.detail-value {
  flex: 1;
  color: var(--text-primary);
}

.detail-value.mono {
  font-family: monospace;
}

.detail-payload {
  flex: 1;
  padding: 0.75rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 0.8rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.verdict-badge {
  padding: 0.25rem 0.625rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.verdict-badge.allow {
  background: var(--success-bg);
  color: var(--success-color);
}

.verdict-badge.block {
  background: var(--danger-bg);
  color: var(--danger-color);
}

.verdict-badge.escalate {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  text-align: center;
  padding: 2rem;
}

.empty-state svg {
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state p {
  margin: 0.5rem 0;
}

.empty-hint {
  font-size: 0.85rem;
  color: var(--text-quaternary);
}
</style>
