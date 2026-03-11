<template>
  <div class="traffic-panel">
    <!-- Panel header -->
    <div class="panel-header">
      <div class="ph-left">
        <span class="ph-title">Traffic</span>
        <span class="ph-count">{{ filteredEvents.length }}</span>
      </div>
      <div class="ph-right">
        <select v-model="verdictFilter" class="ph-filter">
          <option value="">All</option>
          <option value="ALLOW">Allow</option>
          <option value="BLOCK">Block</option>
          <option value="ESCALATE">Escalate</option>
        </select>
        <input v-model="searchQuery" class="ph-search" placeholder="Filter..." />
        <button class="ph-btn" :class="{ active: autoScroll }" @click="autoScroll = !autoScroll" title="Auto-scroll">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <button class="ph-btn" @click="$emit('clear')" title="Clear">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Waterfall list -->
    <div class="waterfall" ref="waterfallEl">
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
          <span class="wf-threat" :class="(event.analysis?.threat_level || 'NONE').toLowerCase()">
            {{ event.analysis?.threat_level || '—' }}
          </span>
        </div>
        <div class="wf-preview">{{ event.payload_preview?.slice(0, 120) }}</div>

        <!-- Expanded detail -->
        <div v-if="selectedEvent === event" class="wf-detail" @click.stop>
          <div class="detail-section">
            <div class="dl"><span class="dk">Session</span><span class="dv mono">{{ event.session_id }}</span></div>
            <div class="dl"><span class="dk">Agent</span><span class="dv">{{ event.agent_id || '—' }}</span></div>
            <div class="dl"><span class="dk">Type</span><span class="dv">{{ event.event_type }}</span></div>
          </div>

          <div v-if="event.analysis" class="detail-section">
            <div class="dl">
              <span class="dk">Verdict</span>
              <span class="verdict-chip" :class="event.analysis.verdict.toLowerCase()">{{ event.analysis.verdict }}</span>
            </div>
            <div class="dl">
              <span class="dk">Threat</span>
              <span class="threat-chip" :class="event.analysis.threat_level.toLowerCase()">{{ event.analysis.threat_level }}</span>
            </div>
            <div v-if="event.analysis.l1_matched_patterns?.length" class="dl">
              <span class="dk">L1</span>
              <div class="pattern-tags">
                <span v-for="p in event.analysis.l1_matched_patterns" :key="p" class="ptag">{{ p }}</span>
              </div>
            </div>
            <div class="dl">
              <span class="dk">L2</span>
              <span class="dv">{{ event.analysis.l2_is_injection ? `Injection (${(event.analysis.l2_confidence * 100).toFixed(0)}%)` : 'Clean' }}</span>
            </div>
            <div v-if="event.analysis.l2_reasoning" class="dl">
              <span class="dk">Reason</span>
              <span class="dv reasoning">{{ event.analysis.l2_reasoning }}</span>
            </div>
          </div>

          <div v-if="event.payload_preview" class="detail-section">
            <div class="dk">Payload</div>
            <pre class="payload-pre">{{ event.payload_preview }}</pre>
          </div>

          <div v-if="event.analysis?.verdict === 'ESCALATE'" class="detail-actions">
            <button class="da-btn allow" @click="$emit('verdict', event.analysis!.request_id, 'allow')">Allow</button>
            <button class="da-btn block" @click="$emit('verdict', event.analysis!.request_id, 'block')">Block</button>
          </div>
        </div>
      </div>

      <div v-if="filteredEvents.length === 0" class="wf-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        <span>Waiting for traffic...</span>
      </div>
    </div>

    <!-- Panel footer -->
    <div class="panel-footer">
      <span>{{ filteredEvents.length }}<span v-if="verdictFilter || searchQuery"> / {{ events.length }}</span> events</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { FirewallEvent } from '../types'

const props = defineProps<{
  events: FirewallEvent[]
  compact?: boolean
}>()

defineEmits<{
  clear: []
  verdict: [requestId: string, action: 'allow' | 'block']
}>()

const selectedEvent = ref<FirewallEvent | null>(null)
const verdictFilter = ref('')
const searchQuery = ref('')
const autoScroll = ref(true)
const waterfallEl = ref<HTMLElement | null>(null)

const filteredEvents = computed(() => {
  return props.events.filter((e) => {
    if (verdictFilter.value && (e.analysis?.verdict || 'ALLOW') !== verdictFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return e.method.toLowerCase().includes(q) || e.payload_preview?.toLowerCase().includes(q) || e.agent_id?.toLowerCase().includes(q)
    }
    return true
  })
})

watch(() => props.events.length, () => {
  if (autoScroll.value) {
    nextTick(() => { if (waterfallEl.value) waterfallEl.value.scrollTop = waterfallEl.value.scrollHeight })
  }
})

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 1 } as any)
}
</script>

<style scoped>
.traffic-panel {
  display: flex; flex-direction: column; height: 100%;
  background: var(--bg-primary); border-left: 1px solid var(--border);
}

/* Header */
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; border-bottom: 1px solid var(--border); background: var(--bg-surface);
  flex-shrink: 0; height: 48px;
}
.ph-left { display: flex; align-items: center; gap: 8px; }
.ph-title { font-size: 14px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.01em; }
.ph-count {
  font-size: 11px; padding: 2px 6px; border-radius: 12px;
  background: var(--bg-elevated); color: var(--text-muted); font-family: var(--font-mono);
}

.ph-right { display: flex; align-items: center; gap: 8px; }
.ph-filter {
  background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary);
  padding: 4px 8px; border-radius: var(--radius-md); font-size: 12px; outline: none; transition: all 0.2s;
}
.ph-filter:focus { border-color: var(--accent); }

.ph-search {
  width: 140px; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
  padding: 4px 8px; border-radius: var(--radius-md); font-size: 12px; outline: none; transition: all 0.2s;
}
.ph-search:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-muted); width: 180px; }

.ph-btn {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-elevated);
  color: var(--text-muted); cursor: pointer; transition: all 0.2s;
}
.ph-btn:hover { border-color: var(--border-hover); color: var(--text-primary); transform: translateY(-1px); }
.ph-btn.active { color: var(--accent); border-color: var(--accent); background: var(--accent-muted); }

/* Waterfall List */
.waterfall { flex: 1; overflow-y: auto; font-size: 13px; scroll-behavior: smooth; }

.wf-row {
  padding: 8px 16px; border-bottom: 1px solid var(--border-subtle);
  cursor: pointer; transition: background 0.15s; display: flex; flex-direction: column; gap: 4px;
}
.wf-row:hover { background: var(--bg-hover); }
.wf-row.selected { background: var(--bg-active); border-left: 3px solid var(--accent); padding-left: 13px; }
.wf-row.blocked { border-left: 3px solid var(--accent-red); padding-left: 13px; background: rgba(239,68,68,0.05); }
.wf-row.escalated { border-left: 3px solid var(--accent-yellow); padding-left: 13px; background: rgba(245,158,11,0.05); }

.wf-main { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.wf-time { font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); }
.wf-method { font-family: var(--font-mono); font-weight: 600; color: var(--text-primary); flex: 1; }

.wf-verdict {
  font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 6px; border-radius: 4px;
  min-width: 24px; text-align: center;
}
.wf-verdict.allow { background: var(--accent-green-muted); color: var(--accent-green); }
.wf-verdict.block { background: var(--accent-red-muted); color: var(--accent-red); }
.wf-verdict.escalate { background: var(--accent-yellow-muted); color: var(--accent-yellow); }

.wf-threat { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
.wf-threat.high { color: var(--accent-red); }
.wf-threat.medium { color: var(--accent-yellow); }

.wf-preview {
  font-size: 12px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-family: var(--font-mono); opacity: 0.8; }

/* Detail View (Expanded) */
.wf-detail {
  margin-top: 8px; padding: 12px; background: var(--bg-elevated); border-radius: var(--radius-md);
  border: 1px solid var(--border); box-shadow: var(--shadow-sm); animation: slideDown 0.2s ease;
}
@keyframes slideDown { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

.detail-section { margin-bottom: 12px; }
.detail-section:last-child { margin-bottom: 0; }

.dl { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 12px; }
.dk { color: var(--text-muted); font-weight: 500; }
.dv { color: var(--text-primary); font-family: var(--font-mono); text-align: right; }
.dv.reasoning { font-family: var(--font-sans); font-style: italic; color: var(--text-secondary); text-align: left; margin-top: 4px; display: block; }

.verdict-chip, .threat-chip {
  font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 6px; border-radius: 4px;
}
.verdict-chip.allow { background: var(--accent-green-muted); color: var(--accent-green); }
.verdict-chip.block { background: var(--accent-red-muted); color: var(--accent-red); }
.threat-chip.high { background: var(--accent-red-muted); color: var(--accent-red); }
.threat-chip.medium { background: var(--accent-yellow-muted); color: var(--accent-yellow); }
.threat-chip.none { background: var(--bg-surface); color: var(--text-muted); }

.pattern-tags { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; max-width: 70%; }
.ptag {
  font-size: 10px; padding: 1px 5px; border-radius: 3px; background: var(--bg-surface);
  border: 1px solid var(--border); color: var(--text-secondary);
}

.payload-pre {
  margin-top: 4px; padding: 8px; background: var(--bg-surface); border-radius: var(--radius-sm);
  border: 1px solid var(--border); color: var(--text-secondary); font-family: var(--font-mono);
  font-size: 11px; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto;
}

.detail-actions { display: flex; gap: 8px; margin-top: 12px; }
.da-btn {
  flex: 1; padding: 6px; border-radius: var(--radius-md); font-size: 12px; font-weight: 600;
  cursor: pointer; border: none; transition: all 0.15s;
}
.da-btn.allow { background: var(--accent-green); color: white; }
.da-btn.allow:hover { background: #059669; }
.da-btn.block { background: var(--accent-red); color: white; }
.da-btn.block:hover { background: #dc2626; }

/* Footer */
.panel-footer {
  padding: 8px 16px; border-top: 1px solid var(--border); background: var(--bg-surface);
  font-size: 11px; color: var(--text-muted); text-align: center;
}
.wf-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 200px; color: var(--text-muted); gap: 12px;
}
</style>
