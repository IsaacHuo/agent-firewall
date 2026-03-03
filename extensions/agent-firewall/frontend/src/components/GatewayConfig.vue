<template>
  <div class="settings-page">
    <header class="page-header">
      <h2>Settings</h2>
      <p class="subtitle">Configure API providers, service keys, and gateway settings</p>
    </header>

    <!-- Loading state -->
    <div v-if="fwLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading settings...</p>
    </div>

    <div v-else class="settings-content">
      <!-- Save bar -->
      <div v-if="fwDirty" class="save-bar">
        <span>You have unsaved changes</span>
        <div class="save-actions">
          <button class="btn btn-secondary btn-sm" @click="resetFirewallConfig">Discard</button>
          <button class="btn btn-primary btn-sm" @click="saveFirewallSettings" :disabled="fwSaving">
            {{ fwSaving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <!-- ────────────────────── AI Provider ────────────────────── -->
      <section class="settings-section">
        <div class="section-header">
          <div class="section-icon blue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"/>
            </svg>
          </div>
          <div>
            <h3>AI Model Provider</h3>
            <p class="section-desc">Configure the LLM provider used by the semantic analysis engine and Chat Lab</p>
          </div>
        </div>
        <div class="section-body">
          <div class="form-group">
            <label>Provider Endpoint</label>
            <input v-model="localFw.engine.l2_model_endpoint" type="text" class="form-input mono" placeholder="https://openrouter.ai/api/v1/chat/completions" />
            <span class="form-hint">OpenAI-compatible chat completions endpoint (OpenRouter, OpenAI, Deepseek, etc.)</span>
          </div>
          <div class="form-group">
            <label>API Key</label>
            <div class="input-with-toggle">
              <input
                v-model="localFw.engine.l2_api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="form-input mono"
                placeholder="sk-..."
              />
              <button class="btn-toggle" @click="showApiKey = !showApiKey" type="button">
                {{ showApiKey ? '🙈' : '👁️' }}
              </button>
            </div>
            <span class="form-hint">Your provider API key — stored locally in .env, never sent to third parties</span>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Analysis Model</label>
              <input v-model="localFw.engine.l2_model" type="text" class="form-input" placeholder="deepseek/deepseek-v3.2-speciale" />
              <span class="form-hint">Model used for L2 semantic threat analysis</span>
            </div>
            <div class="form-group">
              <label>Timeout (seconds)</label>
              <input v-model.number="localFw.engine.l2_timeout_seconds" type="number" step="0.5" class="form-input" />
            </div>
          </div>
        </div>
      </section>

      <!-- ────────────────────── Service API Keys ────────────────────── -->
      <section class="settings-section">
        <div class="section-header">
          <div class="section-icon green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <div>
            <h3>Service API Keys</h3>
            <p class="section-desc">External service integrations used by Chat Lab tools</p>
          </div>
        </div>
        <div class="section-body">
          <div class="form-group">
            <label>Tavily Web Search</label>
            <div class="input-with-toggle">
              <input
                v-model="localFw.services.tavily_api_key"
                :type="showTavilyKey ? 'text' : 'password'"
                class="form-input mono"
                placeholder="tvly-..."
              />
              <button class="btn-toggle" @click="showTavilyKey = !showTavilyKey" type="button">
                {{ showTavilyKey ? '🙈' : '👁️' }}
              </button>
            </div>
            <span class="form-hint">Used for web_search tool in Chat Lab — get your key at <a href="https://tavily.com" target="_blank">tavily.com</a></span>
          </div>
        </div>
      </section>

      <!-- ────────────────────── Chat Models ────────────────────── -->
      <section class="settings-section">
        <div class="section-header">
          <div class="section-icon purple">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div>
            <h3>Chat Models</h3>
            <p class="section-desc">Available models in Chat Lab — uses the provider endpoint and API key above</p>
          </div>
        </div>
        <div class="section-body">
          <div class="model-list">
            <div v-for="(model, idx) in chatModels" :key="idx" class="model-item">
              <div class="model-info">
                <span class="model-id">{{ model.id }}</span>
                <span class="model-label">{{ model.label }}</span>
              </div>
            </div>
          </div>
          <p class="form-hint" style="margin-top: 12px;">
            Models are routed through your provider endpoint. If using OpenRouter, all listed models are available with a single API key.
          </p>
        </div>
      </section>

      <!-- ────────────────────── Gateway Config (Advanced) ────────────────────── -->
      <section class="settings-section">
        <div class="section-header clickable" @click="showGateway = !showGateway">
          <div class="section-icon orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
              <line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>
            </svg>
          </div>
          <div style="flex:1">
            <h3>Gateway Configuration</h3>
            <p class="section-desc">Advanced settings for the OpenClaw gateway ({{ configPath || 'openclaw.json' }})</p>
          </div>
          <span class="chevron" :class="{ open: showGateway }">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </span>
        </div>

        <div v-if="showGateway" class="section-body gw-body">
          <!-- Gateway connection state -->
          <div v-if="!gwConnected" class="gw-disconnected">
            <p>⚠️ Gateway not connected</p>
            <p class="form-hint">Make sure the OpenClaw gateway is running.</p>
            <div class="gateway-auth" v-if="true">
              <div class="token-input-row">
                <input v-model="tokenInput" type="password" placeholder="Gateway token (if required)" class="form-input" />
                <button class="btn btn-primary btn-sm" @click="saveToken">Connect</button>
              </div>
            </div>
          </div>

          <div v-else-if="gwLoading" class="loading-state compact">
            <div class="spinner"></div>
            <p>Loading gateway config...</p>
          </div>

          <template v-else>
            <div class="gw-toolbar">
              <div class="mode-toggle">
                <button class="mode-btn" :class="{ active: gwViewMode === 'form' }" @click="gwViewMode = 'form'">Form</button>
                <button class="mode-btn" :class="{ active: gwViewMode === 'raw' }" @click="gwViewMode = 'raw'">Raw JSON</button>
              </div>
              <div class="gw-actions">
                <button class="btn btn-secondary btn-sm" @click="refreshGw">
                  <span v-html="refreshIcon"></span> Reload
                </button>
                <button class="btn btn-primary btn-sm" @click="handleGwSave" :disabled="gwSaving || !gwHasChanges">
                  {{ gwSaving ? 'Saving...' : 'Save' }}
                </button>
                <button class="btn btn-accent btn-sm" @click="handleGwApply" :disabled="gwSaving || !gwHasChanges">
                  Save &amp; Apply
                </button>
              </div>
            </div>

            <!-- Issues banner -->
            <div v-if="issues.length > 0" class="issues-banner">
              <div class="issue-title">⚠️ Configuration Issues ({{ issues.length }})</div>
              <div v-for="(issue, i) in issues" :key="i" class="issue-item">
                <span class="issue-path">{{ issue.path }}</span>
                <span class="issue-msg">{{ issue.message }}</span>
              </div>
            </div>

            <!-- Form mode -->
            <div v-if="gwViewMode === 'form'" class="gw-form-view">
              <div class="gw-sections">
                <div class="gw-nav">
                  <input v-model="sectionSearch" type="text" class="form-input" placeholder="Search sections..." />
                  <div
                    v-for="section in filteredSections"
                    :key="section"
                    class="gw-nav-item"
                    :class="{ active: activeSection === section }"
                    @click="activeSection = section"
                  >
                    <span class="gw-nav-icon">{{ sectionIcons[section] || '📌' }}</span>
                    {{ section }}
                  </div>
                </div>

                <div class="gw-section-content">
                  <h4>{{ activeSection }}</h4>
                  <div v-if="activeSectionData" class="gw-fields">
                    <div v-for="(value, key) in activeSectionData" :key="String(key)" class="form-group">
                      <label>{{ String(key) }}</label>
                      <label v-if="typeof value === 'boolean'" class="switch">
                        <input type="checkbox" :checked="value" @change="updateField(activeSection, String(key), !value)" />
                        <span class="slider"></span>
                      </label>
                      <input
                        v-else-if="typeof value === 'number'"
                        type="number" :value="value"
                        @change="(e) => updateField(activeSection, String(key), Number((e.target as HTMLInputElement).value))"
                        class="form-input"
                      />
                      <input
                        v-else-if="typeof value === 'string'"
                        type="text" :value="value"
                        @change="(e) => updateField(activeSection, String(key), (e.target as HTMLInputElement).value)"
                        class="form-input"
                        :class="{ sensitive: isSensitive(String(key)) }"
                      />
                      <textarea
                        v-else
                        :value="JSON.stringify(value, null, 2)"
                        @change="(e) => updateFieldJson(activeSection, String(key), (e.target as HTMLTextAreaElement).value)"
                        class="form-input mono"
                        rows="4"
                        style="resize:vertical;font-family:monospace"
                      ></textarea>
                    </div>
                  </div>
                  <div v-else class="empty-hint">
                    <p>This section has no configurable fields.</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Raw JSON mode -->
            <div v-if="gwViewMode === 'raw'" class="gw-raw-view">
              <div class="raw-header">
                <span class="raw-label">Raw Configuration</span>
                <span class="raw-hash" v-if="configHash">Hash: {{ configHash }}</span>
              </div>
              <textarea v-model="rawContent" class="raw-editor" spellcheck="false" @input="gwRawDirty = true"></textarea>
            </div>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useConfig, useGatewayConfig, useGatewayStatus } from '../composables'

// ── Firewall config (REST API) ──────────────────────────────────
const { config: fwConfig, loading: fwLoading, saving: fwSaving, loadConfig, saveConfig } = useConfig()

const showApiKey = ref(false)
const showTavilyKey = ref(false)

/** Local editable copy of firewall config */
const localFw = ref({
  engine: {
    l1_enabled: true,
    l2_enabled: true,
    l2_model_endpoint: 'https://openrouter.ai/api/v1/chat/completions',
    l2_api_key: '',
    l2_model: 'deepseek/deepseek-v3.2-speciale',
    l2_timeout_seconds: 10,
  },
  services: {
    tavily_api_key: '',
  },
})

const fwSnapshot = ref('')
const fwDirty = computed(() => JSON.stringify(localFw.value) !== fwSnapshot.value)

function syncFromFwConfig() {
  if (!fwConfig.value) return
  const c = fwConfig.value
  localFw.value.engine = { ...localFw.value.engine, ...c.engine }
  if ((c as any).services) {
    localFw.value.services = { ...localFw.value.services, ...(c as any).services }
  }
  fwSnapshot.value = JSON.stringify(localFw.value)
}

function resetFirewallConfig() {
  if (fwSnapshot.value) {
    const snap = JSON.parse(fwSnapshot.value)
    localFw.value.engine = { ...snap.engine }
    localFw.value.services = { ...snap.services }
  }
}

async function saveFirewallSettings() {
  await saveConfig({
    engine: localFw.value.engine,
    services: localFw.value.services,
  } as any)
  syncFromFwConfig()
}

watch(fwConfig, syncFromFwConfig)

// Available chat models (static list matching ChatLab)
const chatModels = [
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
  { id: 'openai/gpt-4o', label: 'GPT-4o' },
  { id: 'moonshotai/kimi-k2.5', label: 'Kimi K2.5' },
  { id: 'anthropic/claude-sonnet-4', label: 'Claude Sonnet 4' },
  { id: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { id: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
  { id: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { id: 'minimax/minimax-m2.5', label: 'MiniMax M2.5' },
  { id: 'deepseek/deepseek-chat', label: 'Deepseek Chat (no tools)' },
]

// ── Gateway config (WebSocket RPC) ──────────────────────────────
const { configSnapshot, loading: gwLoading, saving: gwSaving, error: gwError, loadGwConfig, saveGwConfig, applyGwConfig } = useGatewayConfig()
const { connected: gwConnected, connectError } = useGatewayStatus()

const showGateway = ref(false)
const gwViewMode = ref<'form' | 'raw'>('form')
const rawContent = ref('')
const editedConfig = ref<Record<string, unknown>>({})
const gwRawDirty = ref(false)
const sectionSearch = ref('')
const activeSection = ref('')
const tokenInput = ref('')

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
  environment: '🌍', updates: '🔄', agents: '🤖', authentication: '🔐', channels: '📡',
  messages: '💬', commands: '⌨️', hooks: '🪝', skills: '⚡', tools: '🔧', gateway: '🌐',
  metadata: '📋', logging: '📝', browser: '🖥️', ui: '🎨', models: '🧠', bindings: '🔗',
  broadcast: '📢', audio: '🔊', session: '💬', cron: '⏰', web: '🕸️', discovery: '🔍', plugins: '🔌',
}

const activeSectionData = computed(() => {
  if (!activeSection.value) return null
  const data = editedConfig.value[activeSection.value]
  if (data && typeof data === 'object' && !Array.isArray(data)) return data as Record<string, unknown>
  return null
})

const gwHasChanges = computed(() => {
  if (gwViewMode.value === 'raw') return gwRawDirty.value
  return JSON.stringify(editedConfig.value) !== JSON.stringify(configData.value)
})

function updateField(section: string, key: string, value: unknown) {
  const d = editedConfig.value[section]
  if (d && typeof d === 'object' && !Array.isArray(d)) {
    (d as Record<string, unknown>)[key] = value
  }
}

function updateFieldJson(section: string, key: string, jsonStr: string) {
  try { updateField(section, key, JSON.parse(jsonStr)) } catch { /* invalid JSON */ }
}

function isSensitive(key: string): boolean {
  const l = key.toLowerCase()
  return l.includes('key') || l.includes('secret') || l.includes('password') || l.includes('token')
}

function handleGwSave() {
  const content = gwViewMode.value === 'raw' ? rawContent.value : JSON.stringify(editedConfig.value, null, 2)
  saveGwConfig(content)
  gwRawDirty.value = false
}

function handleGwApply() {
  const content = gwViewMode.value === 'raw' ? rawContent.value : JSON.stringify(editedConfig.value, null, 2)
  applyGwConfig(content)
  gwRawDirty.value = false
}

function refreshGw() { loadGwConfig() }

function saveToken() {
  if (tokenInput.value) {
    localStorage.setItem('af-gateway-token', tokenInput.value)
    tokenInput.value = ''
    window.location.reload()
  }
}

watch(configSnapshot, (snapshot) => {
  if (snapshot?.raw) rawContent.value = snapshot.raw
  if (snapshot?.config) {
    editedConfig.value = JSON.parse(JSON.stringify(snapshot.config))
    if (sections.value.length > 0 && !activeSection.value) activeSection.value = sections.value[0]
  }
  gwRawDirty.value = false
})

const refreshIcon = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`

onMounted(() => {
  loadConfig()
  loadGwConfig()
})
</script>

<style scoped>
.settings-page {
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
}

/* ── Save bar ── */
.save-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 10px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--text-secondary);
}

.save-actions {
  display: flex;
  gap: 8px;
}

/* ── Settings sections ── */
.settings-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-section {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
}

.section-header.clickable {
  cursor: pointer;
  transition: background 0.15s;
}

.section-header.clickable:hover {
  background: var(--bg-hover);
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 2px 0 0;
}

.section-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-icon.blue { background: rgba(59, 130, 246, 0.12); color: var(--accent-blue); }
.section-icon.green { background: rgba(34, 197, 94, 0.12); color: var(--accent-green, #22c55e); }
.section-icon.purple { background: rgba(168, 85, 247, 0.12); color: var(--accent-purple); }
.section-icon.orange { background: rgba(249, 115, 22, 0.12); color: var(--accent-orange, #f97316); }

.section-body {
  padding: 20px 24px;
}

/* ── Chevron ── */
.chevron {
  transition: transform 0.2s;
  color: var(--text-dim);
}

.chevron.open {
  transform: rotate(180deg);
}

/* ── Form elements ── */
.form-group {
  margin-bottom: 16px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--accent-blue);
}

.form-input.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
}

.form-input.sensitive {
  -webkit-text-security: disc;
}

.form-input.sensitive:focus {
  -webkit-text-security: none;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 4px;
}

.form-hint a {
  color: var(--accent-blue);
  text-decoration: none;
}

.form-hint a:hover {
  text-decoration: underline;
}

.input-with-toggle {
  display: flex;
  gap: 8px;
  align-items: center;
}

.input-with-toggle .form-input {
  flex: 1;
}

.btn-toggle {
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

/* ── Model list ── */
.model-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

.model-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-id {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-muted);
}

.model-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── Buttons ── */
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

.btn-sm {
  padding: 8px 14px;
  font-size: 12px;
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

/* ── Toggle switch ── */
.switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: var(--toggle-bg);
  border-radius: 22px;
  transition: 0.3s;
}

.slider::before {
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

.switch input:checked + .slider {
  background: var(--toggle-bg-active);
}

.switch input:checked + .slider::before {
  transform: translateX(18px);
}

/* ── Loading / Error ── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
}

.loading-state.compact {
  padding: 30px 20px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Gateway body ── */
.gw-body {
  padding: 0;
}

.gw-disconnected {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
}

.gateway-auth {
  margin-top: 12px;
}

.token-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  max-width: 400px;
  margin: 0 auto;
}

.gw-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elevated);
}

.gw-actions {
  display: flex;
  gap: 8px;
}

.mode-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.mode-btn {
  padding: 6px 14px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-muted);
  font-size: 12px;
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

/* ── Gateway form view ── */
.gw-form-view {
  padding: 16px 24px;
}

.gw-sections {
  display: flex;
  gap: 20px;
  min-height: 400px;
}

.gw-nav {
  width: 200px;
  flex-shrink: 0;
}

.gw-nav .form-input {
  margin-bottom: 8px;
}

.gw-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-muted);
  transition: all 0.15s;
  text-transform: capitalize;
}

.gw-nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.gw-nav-item.active {
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent-blue);
}

.gw-nav-icon {
  font-size: 14px;
}

.gw-section-content {
  flex: 1;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  min-width: 0;
}

.gw-section-content h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  text-transform: capitalize;
}

.gw-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-hint {
  color: var(--text-dim);
  text-align: center;
  padding: 30px;
  font-size: 13px;
}

/* ── Issues ── */
.issues-banner {
  background: rgba(255, 170, 0, 0.08);
  border: 1px solid rgba(255, 170, 0, 0.25);
  border-radius: 10px;
  padding: 14px 24px;
  margin: 12px 24px;
}

.issue-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-yellow);
  margin-bottom: 8px;
}

.issue-item {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  font-size: 12px;
  border-top: 1px solid rgba(255, 170, 0, 0.1);
}

.issue-path {
  font-family: monospace;
  color: var(--text-muted);
  min-width: 100px;
}

.issue-msg {
  color: var(--text-secondary);
}

/* ── Raw JSON ── */
.gw-raw-view {
  display: flex;
  flex-direction: column;
}

.raw-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
}

.raw-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.raw-hash {
  font-size: 11px;
  font-family: monospace;
  color: var(--text-dim);
}

.raw-editor {
  width: 100%;
  min-height: 500px;
  padding: 16px 24px;
  border: none;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  tab-size: 2;
  box-sizing: border-box;
}
</style>
