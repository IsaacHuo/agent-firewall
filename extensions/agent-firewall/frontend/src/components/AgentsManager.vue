<template>
  <div class="agents-page">
    <header class="page-header">
      <h2>Agents &amp; MCP Tools</h2>
      <p class="subtitle">Manage agent configurations, workspace files, and MCP tool permissions</p>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="refresh">
          <span v-html="refreshIcon"></span>
          Refresh
        </button>
      </div>
    </header>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading agents...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <div class="error-card">
        <span class="error-icon">⚠️</span>
        <p>{{ error }}</p>
        <p v-if="connectError" class="error-detail">Gateway rejection: {{ connectError }}</p>
        <p class="error-hint">Make sure the Gateway is running and connected.</p>
        <div v-if="!gwConnected" class="gateway-auth">
          <p class="auth-hint">If the Gateway requires a token, enter it below:</p>
          <div class="token-input-row">
            <input v-model="tokenInput" type="password" placeholder="Gateway token" class="token-input" />
            <button class="btn btn-primary btn-sm" @click="saveToken">Connect</button>
          </div>
        </div>
        <button class="btn btn-primary" @click="refresh">Retry</button>
      </div>
    </div>

    <!-- Agents list -->
    <div v-else class="agents-content">
      <!-- Agent selector -->
      <div class="agent-selector">
        <div
          v-for="agent in agents"
          :key="agent.id"
          class="agent-tab"
          :class="{ active: selectedAgentId === agent.id }"
          @click="selectAgent(agent.id)"
        >
          <span class="agent-emoji">{{ agent.identity?.emoji || '🤖' }}</span>
          <span class="agent-name">{{ agent.identity?.name || agent.name || agent.id }}</span>
          <span v-if="agent.id === defaultAgentId" class="default-badge">Default</span>
        </div>
      </div>

      <!-- Agent detail panels -->
      <div v-if="selectedAgentId" class="agent-detail">
        <!-- Panel tabs -->
        <div class="panel-tabs">
          <button
            v-for="tab in panelTabs"
            :key="tab.id"
            class="panel-tab"
            :class="{ active: activePanel === tab.id }"
            @click="activePanel = tab.id"
          >
            <span v-html="tab.icon"></span>
            {{ tab.label }}
          </button>
        </div>

        <!-- Overview Panel -->
        <div v-if="activePanel === 'overview'" class="panel">
          <h3 class="panel-title">Agent Overview</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Agent ID</span>
              <span class="info-value mono">{{ selectedAgentId }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Display Name</span>
              <span class="info-value">{{ selectedAgent?.identity?.name || selectedAgent?.name || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Theme</span>
              <span class="info-value">{{ selectedAgent?.identity?.theme || 'default' }}</span>
            </div>
            <div v-if="selectedAgent?.identity?.avatarUrl" class="info-item">
              <span class="info-label">Avatar</span>
              <img :src="selectedAgent.identity.avatarUrl" class="agent-avatar" />
            </div>
          </div>
        </div>

        <!-- Files Panel -->
        <div v-if="activePanel === 'files'" class="panel">
          <h3 class="panel-title">
            Workspace Files
            <button class="btn btn-sm btn-secondary" @click="loadFiles">Refresh</button>
          </h3>
          <div v-if="filesLoading" class="loading-state small">
            <div class="spinner"></div>
          </div>
          <div v-else-if="agentFiles.length === 0" class="empty-panel">
            <p>No workspace files found for this agent.</p>
          </div>
          <div v-else class="files-list">
            <div
              v-for="file in agentFiles"
              :key="file.name"
              class="file-item"
              :class="{ missing: file.missing, active: editingFile === file.name }"
              @click="openFile(file)"
            >
              <span class="file-icon">{{ file.missing ? '❌' : '📄' }}</span>
              <div class="file-info">
                <span class="file-name">{{ file.name }}</span>
                <span class="file-meta">
                  {{ file.missing ? 'Missing' : formatFileSize(file.size || 0) }}
                  <template v-if="file.updatedAtMs">
                    · {{ formatDate(file.updatedAtMs) }}
                  </template>
                </span>
              </div>
            </div>
          </div>

          <!-- File editor -->
          <div v-if="editingFile" class="file-editor">
            <div class="editor-header">
              <span class="editor-filename">{{ editingFile }}</span>
              <div class="editor-actions">
                <button class="btn btn-sm btn-primary" @click="saveFile" :disabled="fileSaving">
                  {{ fileSaving ? 'Saving...' : 'Save' }}
                </button>
                <button class="btn btn-sm btn-secondary" @click="editingFile = null">Close</button>
              </div>
            </div>
            <textarea
              v-model="fileContent"
              class="editor-textarea"
              spellcheck="false"
            ></textarea>
          </div>
        </div>

        <!-- Tools Panel -->
        <div v-if="activePanel === 'tools'" class="panel">
          <h3 class="panel-title">MCP Tools Configuration</h3>
          <p class="panel-description">
            Control which MCP tools are available to this agent. Tools are grouped by category.
          </p>

          <div class="tools-section">
            <div v-for="group in toolGroups" :key="group.label" class="tool-group">
              <h4 class="tool-group-label">
                <span class="tool-group-icon">{{ group.icon }}</span>
                {{ group.label }}
              </h4>
              <div class="tool-list">
                <div v-for="tool in group.tools" :key="tool.name" class="tool-item">
                  <label class="toggle">
                    <input
                      type="checkbox"
                      :checked="!isToolBlocked(tool.name)"
                      @change="toggleTool(tool.name)"
                    />
                    <span class="toggle-slider"></span>
                  </label>
                  <div class="tool-info">
                    <span class="tool-name">{{ tool.name }}</span>
                    <span class="tool-desc">{{ tool.description }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Skills Panel -->
        <div v-if="activePanel === 'skills'" class="panel">
          <h3 class="panel-title">Agent Skills</h3>
          <p class="panel-description">
            Skills enabled specifically for this agent. See the global Skills page for all skills.
          </p>
          <div v-if="agentSkillsLoading" class="loading-state small">
            <div class="spinner"></div>
          </div>
          <div v-else-if="agentSkills.length === 0" class="empty-panel">
            <p>No skills configured for this agent.</p>
          </div>
          <div v-else class="skills-list">
            <div v-for="skill in agentSkills" :key="skill.skillKey" class="skill-row">
              <span class="skill-emoji">{{ skill.emoji || '🔧' }}</span>
              <div class="skill-row-info">
                <span class="skill-row-name">{{ skill.name }}</span>
                <span class="skill-row-desc">{{ skill.description }}</span>
              </div>
              <div class="skill-row-status">
                <span v-if="skill.eligible" class="chip chip-green">Active</span>
                <span v-else class="chip chip-red">Inactive</span>
                <span v-if="skill.disabled" class="chip chip-yellow">Disabled</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <p>Select an agent to view its configuration.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { GatewayAgentRow, AgentFileEntry, SkillStatusEntry } from '../types'
import { useGatewayAgents, useGatewaySkills, useGatewayStatus } from '../composables'

const { agents, defaultAgentId, loading, error, loadAgents, loadAgentFiles, saveAgentFile } = useGatewayAgents()
const { skills: agentSkills, loading: agentSkillsLoading, loadSkills: loadAgentSkills } = useGatewaySkills()
const { connected: gwConnected, connectError } = useGatewayStatus()

const selectedAgentId = ref<string | null>(null)
const activePanel = ref<'overview' | 'files' | 'tools' | 'skills'>('overview')
const agentFiles = ref<AgentFileEntry[]>([])
const filesLoading = ref(false)
const editingFile = ref<string | null>(null)
const fileContent = ref('')
const fileSaving = ref(false)
const blockedTools = ref<Set<string>>(new Set())
const tokenInput = ref('')

function saveToken() {
  if (tokenInput.value) {
    localStorage.setItem('af-gateway-token', tokenInput.value)
    tokenInput.value = ''
    window.location.reload()
  }
}

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value) || null,
)

const panelTabs = [
  { id: 'overview' as const, label: 'Overview', icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>` },
  { id: 'files' as const, label: 'Files', icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>` },
  { id: 'tools' as const, label: 'MCP Tools', icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>` },
  { id: 'skills' as const, label: 'Skills', icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>` },
]

const toolGroups = computed(() => [
  {
    label: 'Files',
    icon: '📁',
    tools: [
      { name: 'read_file', description: 'Read file contents' },
      { name: 'write_file', description: 'Write/create files' },
      { name: 'edit_file', description: 'Edit existing files' },
      { name: 'list_directory', description: 'List directory contents' },
      { name: 'apply_patch', description: 'Apply diff patches' },
    ],
  },
  {
    label: 'Runtime',
    icon: '⚡',
    tools: [
      { name: 'execute_command', description: 'Execute shell commands' },
      { name: 'spawn_process', description: 'Spawn background processes' },
    ],
  },
  {
    label: 'Web',
    icon: '🌐',
    tools: [
      { name: 'web_search', description: 'Search the web' },
      { name: 'web_fetch', description: 'Fetch web page content' },
      { name: 'web_screenshot', description: 'Capture web screenshots' },
    ],
  },
  {
    label: 'Memory',
    icon: '🧠',
    tools: [
      { name: 'memory_search', description: 'Search memory store' },
      { name: 'memory_get', description: 'Retrieve memory entries' },
      { name: 'memory_store', description: 'Store new memory entries' },
    ],
  },
  {
    label: 'Sessions',
    icon: '💬',
    tools: [
      { name: 'session_list', description: 'List active sessions' },
      { name: 'session_send', description: 'Send messages to sessions' },
    ],
  },
])

function selectAgent(agentId: string) {
  selectedAgentId.value = agentId
  activePanel.value = 'overview'
}

async function loadFiles() {
  if (!selectedAgentId.value) return
  filesLoading.value = true
  try {
    agentFiles.value = await loadAgentFiles(selectedAgentId.value)
  } finally {
    filesLoading.value = false
  }
}

async function openFile(file: AgentFileEntry) {
  if (file.missing) return
  editingFile.value = file.name
  fileContent.value = file.content || '(loading...)'
  // If content not preloaded, we'd need to fetch it
  if (!file.content) {
    // Content should be available from the file entry
    fileContent.value = ''
  }
}

async function saveFile() {
  if (!selectedAgentId.value || !editingFile.value) return
  fileSaving.value = true
  try {
    await saveAgentFile(selectedAgentId.value, editingFile.value, fileContent.value)
    await loadFiles()
  } finally {
    fileSaving.value = false
  }
}

function isToolBlocked(toolName: string): boolean {
  return blockedTools.value.has(toolName)
}

function toggleTool(toolName: string) {
  if (blockedTools.value.has(toolName)) {
    blockedTools.value.delete(toolName)
  } else {
    blockedTools.value.add(toolName)
  }
}

function refresh() {
  loadAgents()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(ms: number): string {
  return new Date(ms).toLocaleDateString()
}

const refreshIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`

watch(selectedAgentId, (id) => {
  if (id) {
    loadFiles()
    loadAgentSkills(id)
  }
})

onMounted(() => {
  loadAgents()
})

watch(agents, (list) => {
  if (list.length > 0 && !selectedAgentId.value) {
    selectedAgentId.value = defaultAgentId.value || list[0].id
  }
})
</script>

<style scoped>
.agents-page {
  padding: 28px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--btn-primary-bg);
  color: #fff;
}

.btn-secondary {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover {
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading / Error */
.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
}

.loading-state.small {
  padding: 24px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-card {
  text-align: center;
  padding: 32px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.error-icon {
  font-size: 32px;
  display: block;
  margin-bottom: 12px;
}

.error-hint {
  color: var(--text-dim);
  font-size: 13px;
  margin: 8px 0 16px;
}

.error-detail {
  color: var(--danger, #e74c3c);
  font-size: 12px;
  font-family: monospace;
  margin: 4px 0 8px;
}

.gateway-auth {
  margin: 16px 0;
  padding: 16px;
  background: var(--bg-elevated, #1a1a2e);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.auth-hint {
  color: var(--text-dim);
  font-size: 13px;
  margin-bottom: 8px;
}

.token-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.token-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
}

/* Agent selector */
.agent-selector {
  display: flex;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
  overflow-x: auto;
}

.agent-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-surface);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.agent-tab:hover {
  border-color: var(--accent-blue);
}

.agent-tab.active {
  border-color: var(--accent-red);
  background: rgba(233, 69, 96, 0.1);
}

.agent-emoji {
  font-size: 20px;
}

.agent-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.default-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(68, 136, 255, 0.15);
  color: var(--accent-blue);
  font-weight: 600;
}

/* Panel tabs */
.panel-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0;
}

.panel-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: none;
  background: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.panel-tab:hover {
  color: var(--text-secondary);
}

.panel-tab.active {
  color: var(--accent-red);
  border-bottom-color: var(--accent-red);
}

.panel-tab :deep(svg) {
  width: 16px;
  height: 16px;
}

/* Panels */
.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-description {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.5;
}

/* Info grid */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: var(--text-dim);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
}

.info-value.mono {
  font-family: monospace;
}

.agent-avatar {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
}

/* Files list */
.files-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.file-item:hover {
  background: var(--bg-hover);
}

.file-item.active {
  background: rgba(68, 136, 255, 0.1);
}

.file-item.missing {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-icon {
  font-size: 18px;
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: monospace;
}

.file-meta {
  font-size: 11px;
  color: var(--text-dim);
}

/* File editor */
.file-editor {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
}

.editor-filename {
  font-family: monospace;
  font-size: 13px;
  color: var(--text-primary);
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.editor-textarea {
  width: 100%;
  min-height: 300px;
  padding: 14px;
  border: none;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
}

/* Tools section */
.tool-group {
  margin-bottom: 24px;
}

.tool-group-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.tool-group-icon {
  font-size: 18px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  transition: background 0.15s;
}

.tool-item:hover {
  background: var(--bg-hover);
}

.tool-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.tool-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: monospace;
}

.tool-desc {
  font-size: 12px;
  color: var(--text-dim);
}

/* Toggle switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  flex-shrink: 0;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: var(--toggle-bg);
  border-radius: 22px;
  transition: 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 3px;
  bottom: 3px;
  background: var(--toggle-knob, #fff);
  border-radius: 50%;
  transition: 0.3s;
}

.toggle input:checked + .toggle-slider {
  background: var(--toggle-bg-active);
}

.toggle input:checked + .toggle-slider::before {
  transform: translateX(18px);
}

/* Skills list */
.skills-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skill-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 8px;
  transition: background 0.15s;
}

.skill-row:hover {
  background: var(--bg-hover);
}

.skill-emoji {
  font-size: 20px;
}

.skill-row-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.skill-row-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.skill-row-desc {
  font-size: 12px;
  color: var(--text-dim);
}

.skill-row-status {
  display: flex;
  gap: 6px;
}

.chip {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 500;
}

.chip-green {
  background: rgba(0, 204, 106, 0.15);
  color: var(--accent-green);
}

.chip-red {
  background: rgba(233, 69, 96, 0.15);
  color: var(--accent-red);
}

.chip-yellow {
  background: rgba(255, 170, 0, 0.15);
  color: var(--accent-yellow);
}

.empty-state,
.empty-panel {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-dim);
}
</style>
