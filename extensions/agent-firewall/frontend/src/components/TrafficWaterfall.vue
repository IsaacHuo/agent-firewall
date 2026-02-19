<template>
  <div class="traffic-page">
    <div class="page-header">
      <h2>Traffic Waterfall</h2>
      <div class="header-actions">
        <div class="filter-group">
          <select v-model="verdictFilter" class="filter-select">
            <option value="">All Verdicts</option>
            <option value="ALLOW">ALLOW</option>
            <option value="BLOCK">BLOCK</option>
            <option value="ESCALATE">ESCALATE</option>
          </select>
          <select v-model="methodFilter" class="filter-select">
            <option value="">All Methods</option>
            <option v-for="m in uniqueMethods" :key="m" :value="m">{{ m }}</option>
          </select>
          <input
            v-model="searchQuery"
            type="text"
            class="filter-input"
            placeholder="Search payloads..."
          />
        </div>
        <div class="action-group">
          <button class="btn-icon" :class="{ active: autoScroll }" @click="autoScroll = !autoScroll" title="Auto-scroll">
            ↓
          </button>
          <button class="btn-secondary" @click="$emit('clear')">Clear</button>
        </div>
      </div>
    </div>

    <!-- Waterfall + Detail Split Layout -->
    <div class="split-layout">
      <!-- Waterfall List -->
      <div class="waterfall-panel">
        <div class="waterfall-header">
          <span class="col-time">Time</span>
          <span class="col-verdict">Verdict</span>
          <span class="col-method">Method</span>
          <span class="col-agent">Agent</span>
          <span class="col-threat">Threat</span>
          <span class="col-preview">Payload</span>
        </div>
        <div class="waterfall-list" ref="waterfallList">
          <div
            v-for="event in filteredEvents"
            :key="event.timestamp + event.session_id + event.method"
            class="waterfall-row"
            :class="{
              'row-alert': event.is_alert,
              'row-blocked': event.analysis?.verdict === 'BLOCK',
              'row-escalated': event.analysis?.verdict === 'ESCALATE',
              'row-selected': selectedEvent === event,
            }"
            @click="selectedEvent = event"
          >
            <span class="col-time">{{ formatTime(event.timestamp) }}</span>
            <span class="col-verdict" :class="'verdict-' + (event.analysis?.verdict || 'ALLOW').toLowerCase()">
              {{ event.analysis?.verdict || 'ALLOW' }}
            </span>
            <span class="col-method">{{ event.method }}</span>
            <span class="col-agent">{{ event.agent_id || '—' }}</span>
            <span class="col-threat" :class="'threat-' + (event.analysis?.threat_level || 'NONE').toLowerCase()">
              {{ event.analysis?.threat_level || 'NONE' }}
            </span>
            <span class="col-preview">{{ event.payload_preview?.slice(0, 80) }}</span>
          </div>
          <div v-if="filteredEvents.length === 0" class="waterfall-empty">
            <span class="empty-icon">📡</span>
            <span>Waiting for traffic...</span>
          </div>
        </div>
        <div class="waterfall-footer">
          <span class="event-count">{{ filteredEvents.length }} events</span>
          <span v-if="verdictFilter || methodFilter || searchQuery" class="filter-active">
            (filtered from {{ events.length }})
          </span>
        </div>
      </div>

      <!-- Detail Panel -->
      <div class="detail-panel" :class="{ open: selectedEvent }">
        <template v-if="selectedEvent">
          <div class="detail-header">
            <h3>Request Detail</h3>
            <button class="btn-close" @click="selectedEvent = null">✕</button>
          </div>

          <!-- Alert Banner -->
          <div v-if="selectedEvent.is_alert" class="alert-banner">
            <div class="alert-icon">⚠️</div>
            <div class="alert-text">
              <strong>THREAT DETECTED</strong>
              <p>{{ selectedEvent.analysis?.blocked_reason }}</p>
            </div>
          </div>

          <!-- Tabs -->
          <div class="detail-tabs">
            <button
              v-for="tab in detailTabs"
              :key="tab"
              class="detail-tab"
              :class="{ active: activeDetailTab === tab }"
              @click="activeDetailTab = tab"
            >{{ tab }}</button>
          </div>

          <!-- Metadata Tab -->
          <div v-if="activeDetailTab === 'Metadata'" class="detail-content">
            <div class="detail-grid">
              <div class="detail-label">Method</div>
              <div class="detail-value">{{ selectedEvent.method }}</div>
              <div class="detail-label">Session</div>
              <div class="detail-value mono">{{ selectedEvent.session_id }}</div>
              <div class="detail-label">Agent</div>
              <div class="detail-value">{{ selectedEvent.agent_id || '—' }}</div>
              <div class="detail-label">Timestamp</div>
              <div class="detail-value">{{ new Date(selectedEvent.timestamp * 1000).toISOString() }}</div>
              <div class="detail-label">Event Type</div>
              <div class="detail-value">{{ selectedEvent.event_type }}</div>
            </div>
          </div>

          <!-- Analysis Tab -->
          <div v-if="activeDetailTab === 'Analysis'" class="detail-content">
            <template v-if="selectedEvent.analysis">
              <div class="detail-grid">
                <div class="detail-label">Verdict</div>
                <div class="detail-value verdict-badge" :class="'verdict-' + selectedEvent.analysis.verdict.toLowerCase()">
                  {{ selectedEvent.analysis.verdict }}
                </div>
                <div class="detail-label">Threat Level</div>
                <div class="detail-value threat-badge" :class="'threat-' + selectedEvent.analysis.threat_level.toLowerCase()">
                  {{ selectedEvent.analysis.threat_level }}
                </div>
                <div class="detail-label">L1 Patterns</div>
                <div class="detail-value">
                  <span v-if="selectedEvent.analysis.l1_matched_patterns?.length" class="pattern-tags">
                    <span v-for="p in selectedEvent.analysis.l1_matched_patterns" :key="p" class="tag danger">{{ p }}</span>
                  </span>
                  <span v-else class="muted">None</span>
                </div>
                <div class="detail-label">L2 Injection</div>
                <div class="detail-value">
                  {{ selectedEvent.analysis.l2_is_injection
                    ? `Yes (${(selectedEvent.analysis.l2_confidence * 100).toFixed(0)}%)`
                    : 'No' }}
                </div>
                <div class="detail-label">L2 Reasoning</div>
                <div class="detail-value">{{ selectedEvent.analysis.l2_reasoning || '—' }}</div>
              </div>
            </template>
            <div v-else class="empty-state">No analysis data</div>
          </div>

          <!-- Payload Tab -->
          <div v-if="activeDetailTab === 'Payload'" class="detail-content">
            <pre class="payload-block">{{ selectedEvent.payload_preview }}</pre>
          </div>

          <!-- Human-in-the-Loop Actions -->
          <div v-if="selectedEvent.analysis?.verdict === 'ESCALATE'" class="action-bar">
            <button class="btn-allow" @click="$emit('verdict', selectedEvent.analysis!.request_id, 'allow')">
              ✓ Allow Request
            </button>
            <button class="btn-block" @click="$emit('verdict', selectedEvent.analysis!.request_id, 'block')">
              ✕ Block Request
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { FirewallEvent } from '../types'

const props = defineProps<{
  events: FirewallEvent[]
}>()

defineEmits<{
  clear: []
  verdict: [requestId: string, action: 'allow' | 'block']
}>()

const selectedEvent = ref<FirewallEvent | null>(null)
const verdictFilter = ref('')
const methodFilter = ref('')
const searchQuery = ref('')
const autoScroll = ref(true)
const activeDetailTab = ref('Metadata')
const waterfallList = ref<HTMLElement | null>(null)

const detailTabs = ['Metadata', 'Analysis', 'Payload']

const uniqueMethods = computed(() => {
  const methods = new Set(props.events.map((e) => e.method))
  return [...methods].sort()
})

const filteredEvents = computed(() => {
  return props.events.filter((e) => {
    if (verdictFilter.value && (e.analysis?.verdict || 'ALLOW') !== verdictFilter.value) return false
    if (methodFilter.value && e.method !== methodFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return (
        e.method.toLowerCase().includes(q) ||
        e.payload_preview?.toLowerCase().includes(q) ||
        e.agent_id?.toLowerCase().includes(q) ||
        e.session_id?.toLowerCase().includes(q)
      )
    }
    return true
  })
})

// Auto-scroll when new events come in
watch(
  () => props.events.length,
  () => {
    if (autoScroll.value) {
      nextTick(() => {
        if (waterfallList.value) {
          waterfallList.value.scrollTop = waterfallList.value.scrollHeight
        }
      })
    }
  }
)

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-US', {
    hour12: false,
    fractionalSecondDigits: 1,
  })
}
</script>

<style scoped>
.traffic-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  padding: 20px 24px 16px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 12px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.filter-group {
  display: flex;
  gap: 8px;
}

.filter-select,
.filter-input {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  color: #ccc;
  padding: 6px 12px;
  font-size: 12px;
}

.filter-input {
  width: 200px;
}

.filter-select:focus,
.filter-input:focus {
  outline: none;
  border-color: #4488ff;
}

.action-group {
  display: flex;
  gap: 8px;
}

.btn-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid #2a2a3e;
  background: #1a1a2e;
  color: #888;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon.active {
  background: rgba(68, 136, 255, 0.2);
  color: #4488ff;
  border-color: #4488ff;
}

.btn-secondary {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid #2a2a3e;
  background: #1a1a2e;
  color: #888;
  cursor: pointer;
  font-size: 12px;
}

.btn-secondary:hover {
  border-color: #3a3a4e;
  color: #ccc;
}

/* Split Layout */
.split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.waterfall-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.waterfall-header {
  display: grid;
  grid-template-columns: 90px 80px 160px 100px 80px 1fr;
  gap: 8px;
  padding: 8px 24px;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #2a2a3e;
  background: #0f0f1a;
}

.waterfall-list {
  flex: 1;
  overflow-y: auto;
  font-size: 12px;
}

.waterfall-row {
  display: grid;
  grid-template-columns: 90px 80px 160px 100px 80px 1fr;
  gap: 8px;
  padding: 7px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: background 0.15s;
}

.waterfall-row:hover {
  background: #1a1a2e;
}

.waterfall-row.row-selected {
  background: #1a1a3e;
  border-left: 3px solid #4488ff;
  padding-left: 21px;
}

.waterfall-row.row-blocked {
  border-left: 3px solid #ff4444;
  padding-left: 21px;
}

.waterfall-row.row-escalated {
  border-left: 3px solid #ffaa00;
  padding-left: 21px;
}

.waterfall-row.row-alert {
  background: rgba(233, 69, 96, 0.06);
}

.col-time { color: #555; font-family: 'JetBrains Mono', monospace; }
.col-method { color: #4488ff; font-weight: 500; }
.col-agent { color: #888; }
.col-preview { color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.col-verdict { font-weight: 700; font-size: 11px; text-transform: uppercase; }
.verdict-allow { color: #00ff88; }
.verdict-block { color: #ff4444; }
.verdict-escalate { color: #ffaa00; }

.col-threat { font-size: 10px; font-weight: 600; }
.threat-none { color: #444; }
.threat-low { color: #4488ff; }
.threat-medium { color: #ffaa00; }
.threat-high { color: #ff8844; }
.threat-critical { color: #ff4444; }

.waterfall-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 60px;
  color: #444;
  font-style: italic;
}

.empty-icon {
  font-size: 32px;
}

.waterfall-footer {
  padding: 8px 24px;
  border-top: 1px solid #2a2a3e;
  font-size: 11px;
  color: #555;
  background: #0f0f1a;
}

.filter-active {
  color: #4488ff;
}

/* Detail Panel */
.detail-panel {
  width: 0;
  overflow: hidden;
  transition: width 0.3s ease;
  border-left: 1px solid #2a2a3e;
  background: #0f0f1a;
}

.detail-panel.open {
  width: 480px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.detail-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
  margin: 0;
}

.btn-close {
  background: none;
  border: 1px solid #333;
  color: #888;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.btn-close:hover {
  border-color: #666;
  color: #ccc;
}

/* Alert Banner */
.alert-banner {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(255, 0, 0, 0.12) 0%, rgba(255, 68, 68, 0.06) 100%);
  border: 1px solid #ff4444;
  border-radius: 8px;
  margin: 12px 16px;
  animation: alert-flash 1.5s ease-in-out 3;
}

.alert-icon { font-size: 24px; }
.alert-text strong { color: #ff4444; font-size: 13px; display: block; margin-bottom: 4px; }
.alert-text p { color: #ccc; font-size: 12px; margin: 0; line-height: 1.5; }

@keyframes alert-flash {
  0%, 100% { border-color: #ff4444; }
  50% { border-color: #ff0000; box-shadow: 0 0 20px rgba(255, 0, 0, 0.3); }
}

/* Tabs */
.detail-tabs {
  display: flex;
  padding: 0 16px;
  border-bottom: 1px solid #2a2a3e;
}

.detail-tab {
  padding: 10px 16px;
  background: none;
  border: none;
  color: #666;
  font-size: 12px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.detail-tab:hover {
  color: #ccc;
}

.detail-tab.active {
  color: #4488ff;
  border-bottom-color: #4488ff;
}

/* Detail Content */
.detail-content {
  padding: 16px;
  overflow-y: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 6px 12px;
  font-size: 12px;
}

.detail-label {
  color: #666;
}

.detail-value {
  color: #ccc;
  word-break: break-all;
}

.detail-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.verdict-badge {
  font-weight: 700;
  text-transform: uppercase;
}

.threat-badge {
  font-weight: 600;
}

.muted {
  color: #555;
}

.pattern-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.tag.danger {
  background: rgba(255, 68, 68, 0.15);
  color: #ff6666;
}

.payload-block {
  background: #0a0a12;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  padding: 16px;
  font-size: 11px;
  color: #aaa;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  font-family: 'JetBrains Mono', monospace;
}

/* Action Bar */
.action-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #2a2a3e;
  margin-top: auto;
}

.btn-allow, .btn-block {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 8px;
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

.empty-state {
  text-align: center;
  padding: 40px;
  color: #444;
}
</style>
