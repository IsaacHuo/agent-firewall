<template>
  <div class="audit-page">
    <div class="page-header">
      <div>
        <h2>Audit Log</h2>
        <p class="subtitle">Complete security event history for forensics and compliance</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="exportLog">📥 Export CSV</button>
        <button class="btn-secondary" @click="refresh">🔄 Refresh</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters-bar">
      <div class="filter-group">
        <div class="filter-item">
          <label>Verdict</label>
          <select v-model="verdictFilter" class="filter-select" @change="loadFiltered">
            <option value="">All</option>
            <option value="ALLOW">ALLOW</option>
            <option value="BLOCK">BLOCK</option>
            <option value="ESCALATE">ESCALATE</option>
          </select>
        </div>
        <div class="filter-item">
          <label>Threat Level</label>
          <select v-model="threatFilter" class="filter-select" @change="loadFiltered">
            <option value="">All</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </div>
        <div class="filter-item">
          <label>Time Range</label>
          <select v-model="timeFilter" class="filter-select" @change="loadFiltered">
            <option value="1h">Last 1 hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="">All time</option>
          </select>
        </div>
        <div class="filter-item search">
          <label>Search</label>
          <input v-model="searchQuery" type="text" class="filter-input" placeholder="Session, agent, method..." @input="loadFiltered" />
        </div>
      </div>
    </div>

    <!-- Audit Table  -->
    <div class="audit-table-wrapper">
      <table class="audit-table">
        <thead>
          <tr>
            <th class="col-time" @click="toggleSort('timestamp')">
              Time {{ sortField === 'timestamp' ? (sortDir === 'asc' ? '↑' : '↓') : '' }}
            </th>
            <th class="col-verdict">Verdict</th>
            <th class="col-threat">Threat</th>
            <th class="col-method">Method</th>
            <th class="col-agent">Agent</th>
            <th class="col-session">Session</th>
            <th class="col-patterns">Matched Patterns</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in sortedEntries"
            :key="entry.id"
            class="audit-row"
            :class="{ selected: selectedEntry === entry }"
            @click="selectedEntry = entry"
          >
            <td class="col-time">{{ formatTime(entry.timestamp) }}</td>
            <td class="col-verdict">
              <span class="verdict-tag" :class="'v-' + entry.verdict.toLowerCase()">
                {{ entry.verdict }}
              </span>
            </td>
            <td class="col-threat">
              <span class="threat-tag" :class="'t-' + entry.threat_level.toLowerCase()">
                {{ entry.threat_level }}
              </span>
            </td>
            <td class="col-method mono">{{ entry.method }}</td>
            <td class="col-agent">{{ entry.agent_id || '—' }}</td>
            <td class="col-session mono">{{ entry.session_id.slice(0, 8) }}…</td>
            <td class="col-patterns">
              <span v-for="p in entry.matched_patterns.slice(0, 2)" :key="p" class="pattern-tag">{{ p }}</span>
              <span v-if="entry.matched_patterns.length > 2" class="pattern-more">
                +{{ entry.matched_patterns.length - 2 }}
              </span>
            </td>
            <td class="col-actions">
              <button class="btn-icon-xs" @click.stop="selectedEntry = entry" title="Details">👁️</button>
            </td>
          </tr>
          <tr v-if="entries.length === 0">
            <td colspan="8" class="empty-row">
              <div class="empty-state">
                <span class="empty-icon">📋</span>
                <p>No audit entries found</p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Load More -->
    <div v-if="hasMore" class="load-more">
      <button class="btn-secondary" @click="$emit('loadMore')" :disabled="loading">
        {{ loading ? 'Loading...' : 'Load More' }}
      </button>
    </div>

    <!-- Entry Detail Drawer -->
    <div class="detail-drawer" :class="{ open: selectedEntry }">
      <template v-if="selectedEntry">
        <div class="drawer-header">
          <h3>Audit Entry Detail</h3>
          <button class="btn-close" @click="selectedEntry = null">✕</button>
        </div>
        <div class="drawer-body">
          <div class="detail-grid">
            <div class="detail-label">ID</div>
            <div class="detail-value mono">{{ selectedEntry.id }}</div>
            <div class="detail-label">Timestamp</div>
            <div class="detail-value">{{ new Date(selectedEntry.timestamp * 1000).toISOString() }}</div>
            <div class="detail-label">Verdict</div>
            <div class="detail-value">
              <span class="verdict-tag" :class="'v-' + selectedEntry.verdict.toLowerCase()">
                {{ selectedEntry.verdict }}
              </span>
            </div>
            <div class="detail-label">Threat Level</div>
            <div class="detail-value">
              <span class="threat-tag" :class="'t-' + selectedEntry.threat_level.toLowerCase()">
                {{ selectedEntry.threat_level }}
              </span>
            </div>
            <div class="detail-label">Method</div>
            <div class="detail-value mono">{{ selectedEntry.method }}</div>
            <div class="detail-label">Agent ID</div>
            <div class="detail-value mono">{{ selectedEntry.agent_id || '—' }}</div>
            <div class="detail-label">Session ID</div>
            <div class="detail-value mono">{{ selectedEntry.session_id }}</div>
            <div class="detail-label">Payload Hash</div>
            <div class="detail-value mono">{{ selectedEntry.payload_hash }}</div>
          </div>

          <div v-if="selectedEntry.matched_patterns.length" class="detail-section">
            <h4>Matched Patterns</h4>
            <div class="pattern-list">
              <span v-for="p in selectedEntry.matched_patterns" :key="p" class="pattern-tag-lg">{{ p }}</span>
            </div>
          </div>

          <div v-if="selectedEntry.payload_preview" class="detail-section">
            <h4>Payload Preview</h4>
            <pre class="payload-block">{{ selectedEntry.payload_preview }}</pre>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AuditEntry } from '../types'

const props = defineProps<{
  entries: AuditEntry[]
  loading: boolean
  hasMore: boolean
}>()

const emit = defineEmits<{
  load: [options: { verdict?: string; since?: number }]
  loadMore: []
}>()

const verdictFilter = ref('')
const threatFilter = ref('')
const timeFilter = ref('24h')
const searchQuery = ref('')
const selectedEntry = ref<AuditEntry | null>(null)
const sortField = ref<'timestamp'>('timestamp')
const sortDir = ref<'asc' | 'desc'>('desc')

const filteredEntries = computed(() => {
  return props.entries.filter((e) => {
    if (verdictFilter.value && e.verdict !== verdictFilter.value) return false
    if (threatFilter.value && e.threat_level !== threatFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return (
        e.method.toLowerCase().includes(q) ||
        e.agent_id?.toLowerCase().includes(q) ||
        e.session_id.toLowerCase().includes(q) ||
        e.matched_patterns.some((p) => p.toLowerCase().includes(q))
      )
    }
    return true
  })
})

const sortedEntries = computed(() => {
  return [...filteredEntries.value].sort((a, b) => {
    const dir = sortDir.value === 'asc' ? 1 : -1
    return (a.timestamp - b.timestamp) * dir
  })
})

function toggleSort(field: 'timestamp') {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'desc'
  }
}

function loadFiltered() {
  const since = timeFilter.value ? getTimeSince(timeFilter.value) : undefined
  emit('load', {
    verdict: verdictFilter.value || undefined,
    since,
  })
}

function getTimeSince(range: string): number {
  const now = Date.now() / 1000
  switch (range) {
    case '1h': return now - 3600
    case '24h': return now - 86400
    case '7d': return now - 604800
    case '30d': return now - 2592000
    default: return 0
  }
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString('en-US', {
    hour12: false,
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function refresh() {
  loadFiltered()
}

function exportLog() {
  const headers = ['Timestamp', 'Verdict', 'Threat', 'Method', 'Agent', 'Session', 'Patterns']
  const rows = sortedEntries.value.map((e) => [
    new Date(e.timestamp * 1000).toISOString(),
    e.verdict,
    e.threat_level,
    e.method,
    e.agent_id,
    e.session_id,
    e.matched_patterns.join('; '),
  ])
  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `firewall-audit-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.audit-page {
  display: flex; flex-direction: column; height: 100%; padding: 24px;
}

.page-header {
  display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;
}
.page-header h2 { font-size: 24px; font-weight: 600; color: #fff; margin: 0 0 4px; }
.subtitle { color: #666; font-size: 14px; margin: 0; }
.header-actions { display: flex; gap: 8px; }

.btn-secondary {
  padding: 8px 16px; border: 1px solid #2a2a3e; border-radius: 8px;
  background: transparent; color: #888; font-size: 12px; cursor: pointer;
}
.btn-secondary:hover { border-color: #3a3a4e; color: #ccc; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

/* Filters */
.filters-bar {
  background: #141428; border: 1px solid #2a2a3e; border-radius: 12px;
  padding: 16px; margin-bottom: 16px;
}
.filter-group { display: flex; gap: 16px; align-items: flex-end; }
.filter-item { display: flex; flex-direction: column; gap: 4px; }
.filter-item.search { flex: 1; }
.filter-item label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
.filter-select, .filter-input {
  background: #0a0a12; border: 1px solid #2a2a3e; border-radius: 6px;
  color: #ccc; padding: 7px 12px; font-size: 12px;
}
.filter-select:focus, .filter-input:focus { outline: none; border-color: #4488ff; }

/* Table */
.audit-table-wrapper {
  flex: 1; overflow: auto; border: 1px solid #2a2a3e; border-radius: 12px;
}
.audit-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
.audit-table thead {
  background: #141428; position: sticky; top: 0; z-index: 1;
}
.audit-table th {
  padding: 12px 16px; text-align: left; font-size: 11px; color: #666;
  text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #2a2a3e;
  cursor: pointer; user-select: none;
}
.audit-table th:hover { color: #888; }

.audit-row {
  cursor: pointer; transition: background 0.15s;
}
.audit-row:hover { background: rgba(255, 255, 255, 0.02); }
.audit-row.selected { background: rgba(68, 136, 255, 0.08); }

.audit-row td {
  padding: 10px 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }

.verdict-tag, .threat-tag {
  padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase;
}
.v-allow { background: rgba(0, 255, 136, 0.12); color: #00ff88; }
.v-block { background: rgba(255, 68, 68, 0.12); color: #ff4444; }
.v-escalate { background: rgba(255, 170, 0, 0.12); color: #ffaa00; }
.t-critical { background: rgba(255, 68, 68, 0.12); color: #ff4444; }
.t-high { background: rgba(255, 136, 68, 0.12); color: #ff8844; }
.t-medium { background: rgba(255, 170, 0, 0.12); color: #ffaa00; }
.t-low { background: rgba(68, 136, 255, 0.12); color: #4488ff; }
.t-none { background: rgba(255, 255, 255, 0.04); color: #555; }

.pattern-tag {
  display: inline-block; padding: 1px 6px; background: rgba(255, 68, 68, 0.1);
  border-radius: 3px; font-size: 10px; color: #ff6666;
  font-family: 'JetBrains Mono', monospace; margin-right: 4px;
}
.pattern-more { font-size: 10px; color: #666; }

.btn-icon-xs {
  width: 24px; height: 24px; border: none; border-radius: 4px;
  background: transparent; cursor: pointer; font-size: 12px;
}

.empty-row { text-align: center; }
.empty-state { padding: 60px; color: #444; }
.empty-icon { font-size: 32px; display: block; margin-bottom: 8px; }
.empty-state p { margin: 0; }

/* Load More */
.load-more { text-align: center; padding: 16px; }

/* Detail Drawer */
.detail-drawer {
  position: fixed; top: 0; right: 0; bottom: 0; width: 0; background: #0f0f1a;
  border-left: 1px solid #2a2a3e; overflow: hidden; transition: width 0.3s ease; z-index: 50;
}
.detail-drawer.open { width: 480px; }

.drawer-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px; border-bottom: 1px solid #2a2a3e;
}
.drawer-header h3 { font-size: 16px; font-weight: 600; color: #ccc; margin: 0; }
.btn-close {
  background: none; border: 1px solid #333; color: #888;
  width: 28px; height: 28px; border-radius: 6px; cursor: pointer;
}

.drawer-body { padding: 20px; overflow-y: auto; height: calc(100% - 65px); }

.detail-grid {
  display: grid; grid-template-columns: 100px 1fr; gap: 6px 12px; font-size: 12px;
  margin-bottom: 20px;
}
.detail-label { color: #666; }
.detail-value { color: #ccc; word-break: break-all; }

.detail-section { margin-bottom: 20px; }
.detail-section h4 { font-size: 12px; color: #888; margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.5px; }

.pattern-list { display: flex; flex-wrap: wrap; gap: 6px; }
.pattern-tag-lg {
  padding: 4px 12px; background: rgba(255, 68, 68, 0.1); border-radius: 6px;
  font-size: 12px; color: #ff6666; font-family: 'JetBrains Mono', monospace;
}

.payload-block {
  background: #0a0a12; border: 1px solid #2a2a3e; border-radius: 6px;
  padding: 16px; font-size: 11px; color: #aaa; overflow-x: auto;
  white-space: pre-wrap; word-break: break-all; max-height: 300px;
  font-family: 'JetBrains Mono', monospace;
}
</style>
