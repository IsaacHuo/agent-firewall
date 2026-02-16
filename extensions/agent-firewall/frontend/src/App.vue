<template>
  <div class="dashboard">
    <!-- Header Bar -->
    <header class="header">
      <div class="header-left">
        <span class="logo">🛡️</span>
        <h1>Agent Firewall <span class="subtitle">God Mode Console</span></h1>
      </div>
      <div class="header-right">
        <div class="stat-pill" :class="{ connected: wsConnected }">
          <span class="dot"></span>
          {{ wsConnected ? 'LIVE' : 'DISCONNECTED' }}
        </div>
        <div class="stat-pill">Sessions: {{ stats.active_sessions }}</div>
        <div class="stat-pill alert">Blocked: {{ stats.audit?.blocked ?? 0 }}</div>
        <div class="stat-pill warn">Escalated: {{ stats.audit?.escalated ?? 0 }}</div>
      </div>
    </header>

    <!-- Main Layout: Waterfall + Detail Panel -->
    <div class="main-layout">
      <!-- Traffic Waterfall (left) -->
      <div class="waterfall-panel">
        <div class="panel-header">
          <span>Traffic Waterfall</span>
          <button class="btn-clear" @click="clearEvents">Clear</button>
        </div>
        <div class="waterfall-list" ref="waterfallList">
          <div
            v-for="event in events"
            :key="event.timestamp + event.session_id"
            class="waterfall-row"
            :class="{
              'row-alert': event.is_alert,
              'row-blocked': event.analysis?.verdict === 'BLOCK',
              'row-escalated': event.analysis?.verdict === 'ESCALATE',
              'row-selected': selectedEvent === event,
            }"
            @click="selectedEvent = event"
          >
            <span class="row-time">{{ formatTime(event.timestamp) }}</span>
            <span class="row-verdict" :class="'verdict-' + (event.analysis?.verdict || 'ALLOW').toLowerCase()">
              {{ event.analysis?.verdict || 'ALLOW' }}
            </span>
            <span class="row-method">{{ event.method }}</span>
            <span class="row-agent">{{ event.agent_id || '—' }}</span>
            <span class="row-preview">{{ event.payload_preview?.slice(0, 80) }}</span>
          </div>
          <div v-if="events.length === 0" class="waterfall-empty">
            Waiting for traffic...
          </div>
        </div>
      </div>

      <!-- Detail / Alert Panel (right) -->
      <div class="detail-panel" v-if="selectedEvent">
        <div class="panel-header">
          <span>Request Detail</span>
          <button class="btn-close" @click="selectedEvent = null">✕</button>
        </div>

        <!-- Red Alert Banner for threats -->
        <div v-if="selectedEvent.is_alert" class="alert-banner">
          <div class="alert-icon">⚠️</div>
          <div class="alert-text">
            <strong>THREAT DETECTED</strong>
            <p>{{ selectedEvent.analysis?.blocked_reason }}</p>
          </div>
        </div>

        <!-- Metadata -->
        <div class="detail-section">
          <h3>Metadata</h3>
          <div class="detail-grid">
            <div class="detail-label">Method</div>
            <div class="detail-value">{{ selectedEvent.method }}</div>
            <div class="detail-label">Session</div>
            <div class="detail-value mono">{{ selectedEvent.session_id }}</div>
            <div class="detail-label">Agent</div>
            <div class="detail-value">{{ selectedEvent.agent_id }}</div>
            <div class="detail-label">Timestamp</div>
            <div class="detail-value">{{ new Date(selectedEvent.timestamp * 1000).toISOString() }}</div>
          </div>
        </div>

        <!-- Analysis Details -->
        <div class="detail-section" v-if="selectedEvent.analysis">
          <h3>Analysis</h3>
          <div class="detail-grid">
            <div class="detail-label">Verdict</div>
            <div class="detail-value" :class="'verdict-' + selectedEvent.analysis.verdict.toLowerCase()">
              {{ selectedEvent.analysis.verdict }}
            </div>
            <div class="detail-label">Threat Level</div>
            <div class="detail-value">{{ selectedEvent.analysis.threat_level }}</div>
            <div class="detail-label">L1 Patterns</div>
            <div class="detail-value mono">{{ selectedEvent.analysis.l1_matched_patterns?.join(', ') || 'None' }}</div>
            <div class="detail-label">L2 Injection</div>
            <div class="detail-value">{{ selectedEvent.analysis.l2_is_injection ? `Yes (${(selectedEvent.analysis.l2_confidence * 100).toFixed(0)}%)` : 'No' }}</div>
            <div class="detail-label">L2 Reasoning</div>
            <div class="detail-value">{{ selectedEvent.analysis.l2_reasoning || '—' }}</div>
          </div>
        </div>

        <!-- Payload -->
        <div class="detail-section">
          <h3>Payload</h3>
          <pre class="payload-block">{{ selectedEvent.payload_preview }}</pre>
        </div>

        <!-- Human-in-the-Loop Actions (for ESCALATED requests) -->
        <div class="action-bar" v-if="selectedEvent.analysis?.verdict === 'ESCALATE'">
          <button class="btn-allow" @click="sendVerdict('allow')">✓ Allow</button>
          <button class="btn-block" @click="sendVerdict('block')">✕ Block</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

// ── Types ────────────────────────────────────────────────────────

interface Analysis {
  request_id: string
  verdict: string
  threat_level: string
  l1_matched_patterns: string[]
  l2_is_injection: boolean
  l2_confidence: number
  l2_reasoning: string
  blocked_reason: string
}

interface FirewallEvent {
  event_type: string
  timestamp: number
  session_id: string
  agent_id: string
  method: string
  payload_preview: string
  analysis: Analysis | null
  is_alert: boolean
}

interface Stats {
  uptime_seconds: number
  active_sessions: number
  dashboard_clients: number
  audit: { total: number; blocked: number; escalated: number; queue_depth: number } | null
}

// ── State ────────────────────────────────────────────────────────

const events = ref<FirewallEvent[]>([])
const selectedEvent = ref<FirewallEvent | null>(null)
const wsConnected = ref(false)
const stats = ref<Stats>({ uptime_seconds: 0, active_sessions: 0, dashboard_clients: 0, audit: null })
const waterfallList = ref<HTMLElement | null>(null)

let ws: WebSocket | null = null
let statsInterval: ReturnType<typeof setInterval> | null = null

// ── WebSocket Connection ─────────────────────────────────────────

function connectWebSocket(): void {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.hostname}:9090/ws/dashboard`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
    console.log('[Firewall] Dashboard WebSocket connected')
  }

  ws.onmessage = (event: MessageEvent) => {
    try {
      const data: FirewallEvent = JSON.parse(
        typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data)
      )
      events.value.push(data)

      // Keep last 500 events to prevent memory bloat
      if (events.value.length > 500) {
        events.value = events.value.slice(-500)
      }

      // Auto-scroll to bottom
      nextTick(() => {
        if (waterfallList.value) {
          waterfallList.value.scrollTop = waterfallList.value.scrollHeight
        }
      })
    } catch (err) {
      console.error('[Firewall] Failed to parse WS message:', err)
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    console.log('[Firewall] Dashboard WebSocket disconnected, reconnecting...')
    setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = (err) => {
    console.error('[Firewall] WebSocket error:', err)
  }
}

// ── Stats Polling ────────────────────────────────────────────────

async function fetchStats(): Promise<void> {
  try {
    const res = await fetch(`${window.location.protocol}//${window.location.hostname}:9090/api/stats`)
    if (res.ok) {
      stats.value = await res.json()
    }
  } catch {
    // Stats fetch failed — non-critical
  }
}

// ── Actions ──────────────────────────────────────────────────────

function sendVerdict(action: 'allow' | 'block'): void {
  if (!ws || !selectedEvent.value?.analysis) return
  ws.send(JSON.stringify({
    action,
    request_id: selectedEvent.value.analysis.request_id,
  }))
  // Optimistically update the UI
  if (selectedEvent.value.analysis) {
    selectedEvent.value.analysis.verdict = action === 'block' ? 'BLOCK' : 'ALLOW'
  }
}

function clearEvents(): void {
  events.value = []
  selectedEvent.value = null
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 1 })
}

// ── Lifecycle ────────────────────────────────────────────────────

onMounted(() => {
  connectWebSocket()
  fetchStats()
  statsInterval = setInterval(fetchStats, 5000)
})

onUnmounted(() => {
  ws?.close()
  if (statsInterval) clearInterval(statsInterval)
})
</script>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────── */
.dashboard {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0a0a0f;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-bottom: 2px solid #e94560;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo { font-size: 24px; }

.header h1 {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.subtitle {
  color: #e94560;
  font-size: 12px;
  font-weight: 400;
  margin-left: 8px;
}

.header-right {
  display: flex;
  gap: 12px;
}

.stat-pill {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  background: #1a1a2e;
  border: 1px solid #333;
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-pill.connected .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00ff88;
  animation: pulse 2s infinite;
}

.stat-pill.alert { color: #ff4444; border-color: #ff4444; }
.stat-pill.warn { color: #ffaa00; border-color: #ffaa00; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── Main Layout ────────────────────────────────────────────────── */
.main-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.waterfall-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #222;
}

.detail-panel {
  width: 480px;
  display: flex;
  flex-direction: column;
  background: #0f0f1a;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #141428;
  border-bottom: 1px solid #222;
  font-size: 13px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ── Waterfall ──────────────────────────────────────────────────── */
.waterfall-list {
  flex: 1;
  overflow-y: auto;
  font-size: 12px;
}

.waterfall-row {
  display: grid;
  grid-template-columns: 90px 80px 160px 100px 1fr;
  gap: 8px;
  padding: 6px 16px;
  border-bottom: 1px solid #111;
  cursor: pointer;
  transition: background 0.15s;
}

.waterfall-row:hover { background: #1a1a2e; }
.waterfall-row.row-selected { background: #1a1a3e; border-left: 3px solid #4488ff; }
.waterfall-row.row-alert { background: rgba(233, 69, 96, 0.08); }
.waterfall-row.row-blocked { border-left: 3px solid #ff4444; }
.waterfall-row.row-escalated { border-left: 3px solid #ffaa00; }

.row-time { color: #666; }
.row-method { color: #4488ff; font-weight: 500; }
.row-agent { color: #888; }
.row-preview { color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.row-verdict { font-weight: 700; font-size: 11px; text-transform: uppercase; }
.verdict-allow { color: #00ff88; }
.verdict-block { color: #ff4444; }
.verdict-escalate { color: #ffaa00; }

.waterfall-empty {
  padding: 40px;
  text-align: center;
  color: #444;
  font-style: italic;
}

/* ── Alert Banner ───────────────────────────────────────────────── */
.alert-banner {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(255, 0, 0, 0.15) 0%, rgba(255, 68, 68, 0.08) 100%);
  border: 1px solid #ff4444;
  border-radius: 8px;
  margin: 12px 16px;
  animation: alert-flash 1.5s ease-in-out 3;
}

.alert-icon { font-size: 28px; }
.alert-text strong { color: #ff4444; font-size: 14px; display: block; margin-bottom: 4px; }
.alert-text p { color: #ccc; font-size: 12px; line-height: 1.5; }

@keyframes alert-flash {
  0%, 100% { border-color: #ff4444; }
  50% { border-color: #ff0000; box-shadow: 0 0 20px rgba(255, 0, 0, 0.3); }
}

/* ── Detail Sections ────────────────────────────────────────────── */
.detail-section {
  padding: 12px 16px;
  border-bottom: 1px solid #1a1a2e;
}

.detail-section h3 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin-bottom: 8px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 4px 12px;
  font-size: 12px;
}

.detail-label { color: #666; }
.detail-value { color: #ccc; word-break: break-all; }
.detail-value.mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }

.payload-block {
  background: #111;
  border: 1px solid #222;
  border-radius: 4px;
  padding: 12px;
  font-size: 11px;
  color: #aaa;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
}

/* ── Action Bar ─────────────────────────────────────────────────── */
.action-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #141428;
  border-top: 1px solid #222;
}

.btn-allow, .btn-block {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.2s;
}

.btn-allow {
  background: #00cc66;
  color: #000;
}

.btn-block {
  background: #ff4444;
  color: #fff;
}

.btn-allow:hover { transform: scale(1.02); box-shadow: 0 0 16px rgba(0, 204, 102, 0.4); }
.btn-block:hover { transform: scale(1.02); box-shadow: 0 0 16px rgba(255, 68, 68, 0.4); }

.btn-clear, .btn-close {
  background: none;
  border: 1px solid #333;
  color: #888;
  padding: 2px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}

.btn-clear:hover, .btn-close:hover { border-color: #666; color: #ccc; }
</style>
