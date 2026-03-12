<template>
  <div class="log-viewer">
    <div class="log-header">
      <h2>System Logs</h2>
      <div class="actions">
        <span class="status-badge" :class="{ connected }">
          {{ connected ? 'Connected' : 'Disconnected' }}
        </span>
        <button @click="clearLogs" class="btn-secondary">Clear</button>
      </div>
    </div>

    <div ref="logContainer" class="log-container">
      <div v-if="logs.length === 0" class="empty-state">
        Waiting for logs...
      </div>
      <div v-else class="log-lines">
        <div v-for="(log, index) in logs" :key="index" class="log-line">
          {{ log }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:9090'

const logs = ref<string[]>([])
const connected = ref(false)
const logContainer = ref<HTMLElement | null>(null)
let eventSource: EventSource | null = null

function connectLogStream() {
  eventSource = new EventSource(`${API_BASE}/api/logs/stream`)

  eventSource.onopen = () => {
    connected.value = true
  }

  eventSource.onmessage = (event) => {
    logs.value.push(event.data)
    if (logs.value.length > 1000) {
      logs.value.shift()
    }
    scrollToBottom()
  }

  eventSource.onerror = () => {
    connected.value = false
    eventSource?.close()
    // Auto reconnect after 2s
    setTimeout(connectLogStream, 2000)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

function clearLogs() {
  logs.value = []
}

onMounted(() => {
  connectLogStream()
})

onUnmounted(() => {
  eventSource?.close()
})
</script>

<style scoped>
.log-viewer {
  padding: 24px;
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.log-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  background: #eee;
  color: #666;
}

.status-badge.connected {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.btn-secondary {
  padding: 6px 12px;
  border: 1px solid var(--border-color, #e0e0e0);
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-secondary:hover {
  background: var(--bg-hover, #f5f5f5);
}

.log-container {
  flex: 1;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #d4d4d4;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.05);
}
</style>
