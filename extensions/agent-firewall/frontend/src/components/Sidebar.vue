<template>
  <nav class="sidebar">
    <div class="sidebar-header">
      <span class="logo">🛡️</span>
      <h1>Agent Firewall</h1>
    </div>

    <div class="sidebar-nav">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-item"
        :class="{ active: currentSection === item.id }"
        @click="$emit('navigate', item.id)"
      >
        <span class="nav-icon" v-html="item.icon"></span>
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="item.badge" class="nav-badge" :class="item.badgeType">
          {{ item.badge }}
        </span>
      </button>
    </div>

    <div class="sidebar-footer">
      <button class="theme-toggle" @click="$emit('toggleTheme')" :title="props.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'">
        <span class="theme-icon" v-html="props.theme === 'dark' ? icons.sun : icons.moon"></span>
        <span>{{ props.theme === 'dark' ? 'Light Mode' : 'Dark Mode' }}</span>
      </button>
      <div class="connection-status" :class="{ connected }">
        <span class="status-dot"></span>
        {{ connected ? 'Connected' : 'Disconnected' }}
      </div>
      <div class="version">v1.0.0</div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NavSection, Stats } from '../types'
import type { Theme } from '../composables'

const props = defineProps<{
  currentSection: NavSection
  connected: boolean
  stats: Stats | null
  theme: Theme
}>()

defineEmits<{
  navigate: [section: NavSection]
  toggleTheme: []
}>()

// SVG icons as strings for v-html
const icons = {
  dashboard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="3" y="3" width="7" height="7"></rect>
    <rect x="14" y="3" width="7" height="7"></rect>
    <rect x="14" y="14" width="7" height="7"></rect>
    <rect x="3" y="14" width="7" height="7"></rect>
  </svg>`,
  traffic: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
  </svg>`,
  rules: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
  </svg>`,
  engine: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="3"></circle>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
  </svg>`,
  rateLimit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10"></circle>
    <polyline points="12 6 12 12 16 14"></polyline>
  </svg>`,
  test: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
  </svg>`,
  chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
  </svg>`,
  audit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
    <polyline points="10 9 9 9 8 9"></polyline>
  </svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="5"></circle>
    <line x1="12" y1="1" x2="12" y2="3"></line>
    <line x1="12" y1="21" x2="12" y2="23"></line>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
    <line x1="1" y1="12" x2="3" y2="12"></line>
    <line x1="21" y1="12" x2="23" y2="12"></line>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
  </svg>`,
  moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>`,
}

const navItems = computed(() => [
  { id: 'dashboard' as const, label: 'Dashboard', icon: icons.dashboard },
  {
    id: 'traffic' as const,
    label: 'Traffic',
    icon: icons.traffic,
    badge: props.stats?.active_sessions ?? 0,
    badgeType: 'info',
  },
  { id: 'rules' as const, label: 'Rules', icon: icons.rules },
  { id: 'engine' as const, label: 'Engine', icon: icons.engine },
  { id: 'rate-limit' as const, label: 'Rate Limit', icon: icons.rateLimit },
  { id: 'test' as const, label: 'Security Test', icon: icons.test },
  { id: 'chat' as const, label: 'Chat Lab', icon: icons.chat },
  {
    id: 'audit' as const,
    label: 'Audit Log',
    icon: icons.audit,
    badge: props.stats?.audit?.blocked ?? 0,
    badgeType: props.stats?.audit?.blocked ? 'danger' : undefined,
  },
])
</script>

<style scoped>
.sidebar {
  width: 240px;
  height: 100vh;
  background: linear-gradient(180deg, var(--sidebar-bg-from) 0%, var(--sidebar-bg-to) 100%);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--border);
}

.logo {
  font-size: 28px;
}

.sidebar-header h1 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.sidebar-nav {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
  text-align: left;
  font-size: 14px;
}

.nav-item:hover {
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-secondary);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.2) 0%, rgba(233, 69, 96, 0.1) 100%);
  color: var(--accent-red);
  border-left: 3px solid var(--accent-red);
}

.nav-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-elevated);
  color: var(--text-muted);
}

.nav-badge.info {
  background: rgba(68, 136, 255, 0.2);
  color: var(--accent-blue);
}

.nav-badge.danger {
  background: rgba(255, 68, 68, 0.2);
  color: var(--danger);
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.theme-toggle:hover {
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}

.theme-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-dim);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-dim);
}

.connection-status.connected .status-dot {
  background: var(--accent-green);
  animation: pulse 2s infinite;
}

.connection-status.connected {
  color: var(--accent-green);
}

.version {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 8px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
