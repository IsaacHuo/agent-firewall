<template>
  <div class="integrations-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-main">
        <h2>Integrations</h2>
        <p class="subtitle">Manage agents, MCP servers, skills, and tools</p>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshAll" title="Refresh">
          <span v-html="icons.refresh"></span>
        </button>
      </div>
    </header>

    <!-- Tabs -->
    <div class="tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        class="tab-btn" 
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
    </div>

    <!-- Content Area -->
    <div class="tab-content">
      <!-- AGENTS TAB -->
      <div v-if="activeTab === 'agents'" class="agents-view">
        <AgentsManager />
      </div>

      <!-- SKILLS TAB -->
      <div v-if="activeTab === 'skills'" class="skills-view">
        <SkillsManager />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SkillsManager from './SkillsManager.vue'
import AgentsManager from './AgentsManager.vue'

const activeTab = ref<'agents' | 'skills'>('agents')

const tabs = [
  { id: 'agents', label: 'Agents & Tools', icon: '🤖' },
  { id: 'skills', label: 'Skills & Servers', icon: '⚡' }
]

const icons = {
  refresh: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`
}

function refreshAll() {
  // Trigger refresh in children by re-mounting or event bus
  // For simplicity, reload page or use a shared refresh signal
  window.location.reload()
}
</script>

<style scoped>
.integrations-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

.page-header {
  padding: 24px 32px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-surface);
}

.header-main h2 {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
}

.btn-refresh {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-refresh:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.tabs {
  display: flex;
  gap: 2px;
  padding: 0 32px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.agents-view,
.skills-view {
  height: 100%;
  overflow-y: auto;
}

/* Override child component styles to fit container */
:deep(.agents-page),
:deep(.skills-page) {
  padding: 24px 32px;
  height: auto; /* Let parent scroll */
  overflow: visible;
}

:deep(.page-header) {
  display: none; /* Hide headers inside child components */
}
</style>
