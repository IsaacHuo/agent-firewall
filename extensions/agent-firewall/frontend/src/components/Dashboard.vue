<template>
  <div class="dashboard">
    <div class="page-header">
      <h2>Security Dashboard</h2>
      <p class="subtitle">Real-time overview of your agent firewall</p>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon blue">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ formatUptime(stats?.uptime_seconds ?? 0) }}</div>
          <div class="stat-label">Uptime</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon green">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.active_sessions ?? 0 }}</div>
          <div class="stat-label">Active Sessions</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon red">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.audit?.blocked ?? 0 }}</div>
          <div class="stat-label">Blocked Requests</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon orange">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.audit?.escalated ?? 0 }}</div>
          <div class="stat-label">Escalated</div>
        </div>
      </div>
    </div>

    <!-- Quick Actions & Recent Activity -->
    <div class="dashboard-grid">
      <!-- Threat Overview -->
      <div class="card threat-overview">
        <div class="card-header">
          <h3>Threat Overview</h3>
        </div>
        <div class="threat-chart">
          <div class="threat-bar">
            <div class="bar-label">CRITICAL</div>
            <div class="bar-track">
              <div class="bar-fill critical" :style="{ width: threatPercentage('CRITICAL') + '%' }"></div>
            </div>
            <div class="bar-count">{{ threatCounts.CRITICAL }}</div>
          </div>
          <div class="threat-bar">
            <div class="bar-label">HIGH</div>
            <div class="bar-track">
              <div class="bar-fill high" :style="{ width: threatPercentage('HIGH') + '%' }"></div>
            </div>
            <div class="bar-count">{{ threatCounts.HIGH }}</div>
          </div>
          <div class="threat-bar">
            <div class="bar-label">MEDIUM</div>
            <div class="bar-track">
              <div class="bar-fill medium" :style="{ width: threatPercentage('MEDIUM') + '%' }"></div>
            </div>
            <div class="bar-count">{{ threatCounts.MEDIUM }}</div>
          </div>
          <div class="threat-bar">
            <div class="bar-label">LOW</div>
            <div class="bar-track">
              <div class="bar-fill low" :style="{ width: threatPercentage('LOW') + '%' }"></div>
            </div>
            <div class="bar-count">{{ threatCounts.LOW }}</div>
          </div>
        </div>
      </div>

      <!-- Recent Alerts -->
      <div class="card recent-alerts">
        <div class="card-header">
          <h3>Recent Alerts</h3>
          <button class="btn-text" @click="$emit('navigate', 'traffic')">View All →</button>
        </div>
        <div class="alerts-list">
          <div
            v-for="alert in recentAlerts"
            :key="alert.timestamp + alert.session_id"
            class="alert-item"
            :class="'alert-' + (alert.analysis?.verdict || 'ALLOW').toLowerCase()"
          >
            <div class="alert-icon">
              <span v-if="alert.analysis?.verdict === 'BLOCK'">🚫</span>
              <span v-else-if="alert.analysis?.verdict === 'ESCALATE'">⚠️</span>
              <span v-else>✓</span>
            </div>
            <div class="alert-content">
              <div class="alert-method">{{ alert.method }}</div>
              <div class="alert-reason">{{ alert.analysis?.blocked_reason || 'Allowed' }}</div>
            </div>
            <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
          </div>
          <div v-if="recentAlerts.length === 0" class="empty-state">
            No recent alerts
          </div>
        </div>
      </div>

      <!-- Engine Status -->
      <div class="card engine-status">
        <div class="card-header">
          <h3>Engine Status</h3>
        </div>
        <div class="engine-list">
          <div class="engine-item">
            <div class="engine-name">L1 Static Analyzer</div>
            <div class="engine-indicator active">
              <span class="dot"></span> Active
            </div>
          </div>
          <div class="engine-item">
            <div class="engine-name">L2 Semantic Analyzer</div>
            <div class="engine-indicator active">
              <span class="dot"></span> Active
            </div>
          </div>
          <div class="engine-item">
            <div class="engine-name">Rate Limiter</div>
            <div class="engine-indicator active">
              <span class="dot"></span> Active
            </div>
          </div>
          <div class="engine-item">
            <div class="engine-name">Audit Logger</div>
            <div class="engine-indicator active">
              <span class="dot"></span> Active
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="card quick-actions">
        <div class="card-header">
          <h3>Quick Actions</h3>
        </div>
        <div class="action-buttons">
          <button class="action-btn" @click="$emit('navigate', 'rules')">
            <span class="action-icon">🛡️</span>
            <span>Configure Rules</span>
          </button>
          <button class="action-btn" @click="$emit('navigate', 'test')">
            <span class="action-icon">🔬</span>
            <span>Run Security Test</span>
          </button>
          <button class="action-btn" @click="$emit('navigate', 'audit')">
            <span class="action-icon">📋</span>
            <span>View Audit Log</span>
          </button>
          <button class="action-btn" @click="$emit('navigate', 'engine')">
            <span class="action-icon">⚙️</span>
            <span>Engine Settings</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Stats, FirewallEvent, ThreatLevel } from '../types'

const props = defineProps<{
  stats: Stats | null
  events: FirewallEvent[]
}>()

defineEmits<{
  navigate: [section: string]
}>()

const recentAlerts = computed(() => {
  return props.events
    .filter((e) => e.is_alert || e.analysis?.verdict !== 'ALLOW')
    .slice(-5)
    .reverse()
})

const threatCounts = computed(() => {
  const counts: Record<ThreatLevel, number> = {
    NONE: 0,
    LOW: 0,
    MEDIUM: 0,
    HIGH: 0,
    CRITICAL: 0,
  }
  for (const event of props.events) {
    const level = event.analysis?.threat_level || 'NONE'
    if (level in counts) {
      counts[level as ThreatLevel]++
    }
  }
  return counts
})

const totalThreats = computed(() =>
  threatCounts.value.LOW +
  threatCounts.value.MEDIUM +
  threatCounts.value.HIGH +
  threatCounts.value.CRITICAL
)

function threatPercentage(level: ThreatLevel): number {
  if (totalThreats.value === 0) return 0
  return (threatCounts.value[level] / totalThreats.value) * 100
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.dashboard {
  padding: 24px;
  max-width: 1400px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 4px;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid #2a2a3e;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon svg {
  width: 24px;
  height: 24px;
}

.stat-icon.blue {
  background: rgba(68, 136, 255, 0.2);
  color: #4488ff;
}

.stat-icon.green {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.stat-icon.red {
  background: rgba(255, 68, 68, 0.2);
  color: #ff4444;
}

.stat-icon.orange {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
}

.stat-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Dashboard Grid */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.card {
  background: #141428;
  border-radius: 12px;
  border: 1px solid #2a2a3e;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
  margin: 0;
}

.btn-text {
  background: none;
  border: none;
  color: #4488ff;
  font-size: 12px;
  cursor: pointer;
}

.btn-text:hover {
  color: #66aaff;
}

/* Threat Overview */
.threat-chart {
  padding: 20px;
}

.threat-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.bar-label {
  width: 70px;
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
}

.bar-track {
  flex: 1;
  height: 8px;
  background: #0a0a0f;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.bar-fill.critical { background: #ff4444; }
.bar-fill.high { background: #ff8844; }
.bar-fill.medium { background: #ffaa00; }
.bar-fill.low { background: #4488ff; }

.bar-count {
  width: 40px;
  font-size: 12px;
  color: #888;
  text-align: right;
}

/* Recent Alerts */
.alerts-list {
  padding: 12px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.alert-item.alert-block {
  border-left: 3px solid #ff4444;
}

.alert-item.alert-escalate {
  border-left: 3px solid #ffaa00;
}

.alert-icon {
  font-size: 16px;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-method {
  font-size: 13px;
  color: #ccc;
  font-weight: 500;
}

.alert-reason {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-time {
  font-size: 11px;
  color: #555;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #444;
  font-style: italic;
}

/* Engine Status */
.engine-list {
  padding: 16px 20px;
}

.engine-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #1a1a2e;
}

.engine-item:last-child {
  border-bottom: none;
}

.engine-name {
  font-size: 13px;
  color: #ccc;
}

.engine-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #666;
}

.engine-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #666;
}

.engine-indicator.active .dot {
  background: #00ff88;
}

.engine-indicator.active {
  color: #00ff88;
}

/* Quick Actions */
.action-buttons {
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  color: #ccc;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: #3a3a4e;
}

.action-icon {
  font-size: 18px;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
