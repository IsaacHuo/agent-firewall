<template>
  <div class="config-page">
    <header class="page-header">
      <h2>Gateway Configuration</h2>
      <p class="subtitle">View and edit the gateway configuration file ({{ configPath || 'agent-shield.json' }})</p>
      <div class="header-actions">
        <div class="mode-toggle">
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'form' }"
            @click="viewMode = 'form'"
          >Form</button>
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'raw' }"
            @click="viewMode = 'raw'"
          >Raw JSON</button>
        </div>
        <button class="btn btn-secondary" @click="refresh">
          <span v-html="refreshIcon"></span>
          Reload
        </button>
        <button class="btn btn-primary" @click="handleSave" :disabled="saving || !hasChanges">
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
        <button class="btn btn-accent" @click="handleApply" :disabled="saving || !hasChanges">
          Save &amp; Apply
        </button>
      </div>
    </header>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading configuration...</p>
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

    <!-- Config editor -->
    <div v-else class="config-content">
      <!-- Issues banner -->
      <div v-if="issues.length > 0" class="issues-banner">
        <div class="issue-title">⚠️ Configuration Issues ({{ issues.length }})</div>
        <div v-for="(issue, i) in issues" :key="i" class="issue-item">
          <span class="issue-path">{{ issue.path }}</span>
          <span class="issue-msg">{{ issue.message }}</span>
        </div>
      </div>

      <!-- Form mode -->
      <div v-if="viewMode === 'form'" class="form-view">
        <div class="config-sections">
          <!-- Sidebar navigation -->
          <div class="section-nav">
            <input
              v-model="sectionSearch"
              type="text"
              class="section-search"
              placeholder="Search sections..."
            />
            <div
              v-for="section in filteredSections"
              :key="section"
              class="section-nav-item"
              :class="{ active: activeSection === section }"
              @click="activeSection = section"
            >
              <span class="section-icon">{{ sectionIcons[section] || '📌' }}</span>
              {{ section }}
            </div>
          </div>

          <!-- Section content -->
          <div class="section-content">
            <h3 class="section-title">{{ activeSection }}</h3>
            <div v-if="activeSectionData" class="config-fields">
              <div
                v-for="(value, key) in activeSectionData"
                :key="String(key)"
                class="config-field"
              >
                <label class="field-label">{{ String(key) }}</label>
                <!-- Boolean -->
                <label v-if="typeof value === 'boolean'" class="toggle">
                  <input
                    type="checkbox"
                    :checked="value"
                    @change="updateField(activeSection, String(key), !value)"
                  />
                  <span class="toggle-slider"></span>
                </label>
                <!-- Number -->
                <input
                  v-else-if="typeof value === 'number'"
                  type="number"
                  :value="value"
                  @change="(e) => updateField(activeSection, String(key), Number((e.target as HTMLInputElement).value))"
                  class="field-input"
                />
                <!-- String -->
                <input
                  v-else-if="typeof value === 'string'"
                  type="text"
                  :value="value"
                  @change="(e) => updateField(activeSection, String(key), (e.target as HTMLInputElement).value)"
                  class="field-input"
                  :class="{ sensitive: isSensitive(String(key)) }"
                />
                <!-- Array / Object (show as JSON) -->
                <textarea
                  v-else
                  :value="JSON.stringify(value, null, 2)"
                  @change="(e) => updateFieldJson(activeSection, String(key), (e.target as HTMLTextAreaElement).value)"
                  class="field-textarea"
                  rows="4"
                ></textarea>
              </div>
            </div>
            <div v-else class="empty-section">
              <p>This section has no configurable fields, or the data format is not a plain object.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Raw JSON mode -->
      <div v-if="viewMode === 'raw'" class="raw-view">
        <div class="raw-header">
          <span class="raw-label">Raw Configuration</span>
          <span class="raw-hash" v-if="configHash">Hash: {{ configHash }}</span>
        </div>
        <textarea
          v-model="rawContent"
          class="raw-editor"
          spellcheck="false"
          @input="markDirty"
        ></textarea>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useGatewayConfig, useGatewayStatus } from '../composables'

const { configSnapshot, loading, saving, error, loadGwConfig, saveGwConfig, applyGwConfig } = useGatewayConfig()
const { connected: gwConnected, connectError } = useGatewayStatus()
const tokenInput = ref('')

function saveToken() {
  if (tokenInput.value) {
    localStorage.setItem('af-gateway-token', tokenInput.value)
    tokenInput.value = ''
    window.location.reload()
  }
}

const viewMode = ref<'form' | 'raw'>('form')
const rawContent = ref('')
const editedConfig = ref<Record<string, unknown>>({})
const dirty = ref(false)
const sectionSearch = ref('')
const activeSection = ref('')

const configPath = computed(() => configSnapshot.value?.path || null)
const configHash = computed(() => configSnapshot.value?.hash || null)
const issues = computed(() => configSnapshot.value?.issues || [])

const configData = computed<Record<string, unknown>>(() => {
  if (!configSnapshot.value?.config) return {}
  return configSnapshot.value.config as Record<string, unknown>
})

const sections = computed(() => Object.keys(editedConfig.value).sort())

const filteredSections = computed(() => {
  const q = sectionSearch.value.toLowerCase()
  if (!q) return sections.value
  return sections.value.filter((s) => s.toLowerCase().includes(q))
})

const sectionIcons: Record<string, string> = {
  environment: '🌍',
  updates: '🔄',
  agents: '🤖',
  authentication: '🔐',
  channels: '📡',
  messages: '💬',
  commands: '⌨️',
  hooks: '🪝',
  skills: '⚡',
  tools: '🔧',
  gateway: '🌐',
  metadata: '📋',
  logging: '📝',
  browser: '🖥️',
  ui: '🎨',
  models: '🧠',
  bindings: '🔗',
  broadcast: '📢',
  audio: '🔊',
  session: '💬',
  cron: '⏰',
  web: '🕸️',
  discovery: '🔍',
  plugins: '🔌',
}

const activeSectionData = computed(() => {
  if (!activeSection.value) return null
  const data = editedConfig.value[activeSection.value]
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    return data as Record<string, unknown>
  }
  return null
})

const hasChanges = computed(() => {
  if (viewMode.value === 'raw') return dirty.value
  return JSON.stringify(editedConfig.value) !== JSON.stringify(configData.value)
})

function updateField(section: string, key: string, value: unknown) {
  const sectionData = editedConfig.value[section]
  if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
    (sectionData as Record<string, unknown>)[key] = value
  }
}

function updateFieldJson(section: string, key: string, jsonStr: string) {
  try {
    const parsed = JSON.parse(jsonStr)
    updateField(section, key, parsed)
  } catch {
    // Invalid JSON, ignore
  }
}

function isSensitive(key: string): boolean {
  const lower = key.toLowerCase()
  return lower.includes('key') || lower.includes('secret') || lower.includes('password') || lower.includes('token')
}

function markDirty() {
  dirty.value = true
}

function handleSave() {
  const content = viewMode.value === 'raw' ? rawContent.value : JSON.stringify(editedConfig.value, null, 2)
  saveGwConfig(content)
  dirty.value = false
}

function handleApply() {
  const content = viewMode.value === 'raw' ? rawContent.value : JSON.stringify(editedConfig.value, null, 2)
  applyGwConfig(content)
  dirty.value = false
}

function refresh() {
  loadGwConfig()
}

watch(configSnapshot, (snapshot) => {
  if (snapshot?.raw) {
    rawContent.value = snapshot.raw
  }
  if (snapshot?.config) {
    editedConfig.value = JSON.parse(JSON.stringify(snapshot.config))
    if (sections.value.length > 0 && !activeSection.value) {
      activeSection.value = sections.value[0]
    }
  }
  dirty.value = false
})

const refreshIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`

onMounted(() => {
  loadGwConfig()
})
</script>

<style scoped>
.config-page {
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
  align-items: center;
}

.mode-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.mode-btn {
  padding: 8px 16px;
  border: none;
  background: var(--bg-elevated);
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: var(--accent-blue);
  color: #fff;
}

.mode-btn:not(.active):hover {
  color: var(--text-secondary);
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

.btn-accent {
  background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading / Error */
.loading-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
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

/* Issues banner */
.issues-banner {
  background: rgba(255, 170, 0, 0.08);
  border: 1px solid rgba(255, 170, 0, 0.25);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
}

.issue-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-yellow);
  margin-bottom: 10px;
}

.issue-item {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  border-top: 1px solid rgba(255, 170, 0, 0.1);
}

.issue-path {
  font-family: monospace;
  color: var(--text-muted);
  min-width: 120px;
}

.issue-msg {
  color: var(--text-secondary);
}

/* Form view */
.config-sections {
  display: flex;
  gap: 24px;
  min-height: 500px;
}

.section-nav {
  width: 220px;
  flex-shrink: 0;
}

.section-search {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 13px;
  margin-bottom: 10px;
  outline: none;
}

.section-search:focus {
  border-color: var(--accent-blue);
}

.section-search::placeholder {
  color: var(--text-dim);
}

.section-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-muted);
  transition: all 0.15s;
  text-transform: capitalize;
}

.section-nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.section-nav-item.active {
  background: rgba(233, 69, 96, 0.1);
  color: var(--accent-red);
}

.section-icon {
  font-size: 16px;
}

.section-content {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  min-width: 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
  text-transform: capitalize;
}

.config-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: monospace;
}

.field-input {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.field-input:focus {
  border-color: var(--accent-blue);
}

.field-input.sensitive {
  font-family: monospace;
  -webkit-text-security: disc;
}

.field-input.sensitive:focus {
  -webkit-text-security: none;
}

.field-textarea {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  resize: vertical;
  outline: none;
  line-height: 1.5;
}

.field-textarea:focus {
  border-color: var(--accent-blue);
}

.empty-section {
  color: var(--text-dim);
  text-align: center;
  padding: 40px;
  font-size: 14px;
}

/* Toggle switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
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

/* Raw JSON view */
.raw-view {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.raw-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
}

.raw-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.raw-hash {
  font-size: 12px;
  font-family: monospace;
  color: var(--text-dim);
}

.raw-editor {
  width: 100%;
  min-height: 600px;
  padding: 16px;
  border: none;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  tab-size: 2;
}
</style>
