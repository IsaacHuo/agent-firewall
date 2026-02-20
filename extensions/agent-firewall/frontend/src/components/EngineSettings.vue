<template>
  <div class="engine-page">
    <div class="page-header">
      <h2>Engine & Network Settings</h2>
      <p class="subtitle">Configure analysis engines, network, and session parameters</p>
    </div>

    <div class="settings-grid">
      <!-- Network Settings -->
      <div class="settings-card">
        <div class="card-header">
          <div class="card-icon blue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
              <line x1="6" y1="6" x2="6.01" y2="6"></line>
              <line x1="6" y1="18" x2="6.01" y2="18"></line>
            </svg>
          </div>
          <h3>Network</h3>
        </div>
        <div class="card-body">
          <div class="form-group">
            <label>Listen Host</label>
            <input v-model="localConfig.network.listen_host" type="text" class="form-input" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Listen Port</label>
              <input v-model.number="localConfig.network.listen_port" type="number" class="form-input" />
            </div>
            <div class="form-group">
              <label>Transport Mode</label>
              <select v-model="localConfig.network.transport_mode" class="form-input">
                <option value="sse">SSE (Server-Sent Events)</option>
                <option value="websocket">WebSocket</option>
                <option value="stdio">STDIO</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Upstream Host</label>
            <input v-model="localConfig.network.upstream_host" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label>Upstream Port</label>
            <input v-model.number="localConfig.network.upstream_port" type="number" class="form-input" />
          </div>
        </div>
      </div>

      <!-- L1 Static Analyzer -->
      <div class="settings-card">
        <div class="card-header">
          <div class="card-icon green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
          </div>
          <h3>L1 Static Analyzer</h3>
          <label class="switch">
            <input type="checkbox" v-model="localConfig.engine.l1_enabled" />
            <span class="slider"></span>
          </label>
        </div>
        <div class="card-body">
          <p class="card-description">
            High-throughput pattern-based threat detection using Aho-Corasick automaton and regex battery.
            Executes in &lt;1ms per payload.
          </p>
          <div class="form-group">
            <label>Blocked Commands <span class="count">({{ localConfig.blocked_commands?.length || 0 }})</span></label>
            <textarea
              :value="localConfig.blocked_commands?.join('\n') ?? ''"
              @input="updateBlockedCommands(($event.target as HTMLTextAreaElement).value)"
              class="form-input mono"
              rows="6"
              placeholder="One blocked command per line..."
            ></textarea>
            <span class="form-hint">Aho-Corasick patterns — one per line. Case-insensitive matching.</span>
          </div>
        </div>
      </div>

      <!-- L2 Semantic Analyzer -->
      <div class="settings-card">
        <div class="card-header">
          <div class="card-icon purple">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path>
            </svg>
          </div>
          <h3>L2 Semantic Analyzer</h3>
          <label class="switch">
            <input type="checkbox" v-model="localConfig.engine.l2_enabled" />
            <span class="slider"></span>
          </label>
        </div>
        <div class="card-body">
          <p class="card-description">
            LLM-powered intent classification for deep semantic analysis. Detects prompt injection, social engineering, and obfuscated threats.
          </p>
          <div class="form-group">
            <label>Model Endpoint</label>
            <input v-model="localConfig.engine.l2_model_endpoint" type="text" class="form-input mono" />
          </div>
          <div class="form-group">
            <label>API Key</label>
            <div class="input-with-toggle">
              <input
                v-model="localConfig.engine.l2_api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="form-input mono"
                placeholder="sk-..."
              />
              <button class="btn-toggle" @click="showApiKey = !showApiKey">
                {{ showApiKey ? '🙈' : '👁️' }}
              </button>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Model</label>
              <input v-model="localConfig.engine.l2_model" type="text" class="form-input" />
            </div>
            <div class="form-group">
              <label>Timeout (seconds)</label>
              <input v-model.number="localConfig.engine.l2_timeout_seconds" type="number" step="0.5" class="form-input" />
            </div>
          </div>
        </div>
      </div>

      <!-- Session Settings -->
      <div class="settings-card">
        <div class="card-header">
          <div class="card-icon orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
            </svg>
          </div>
          <h3>Session Management</h3>
        </div>
        <div class="card-body">
          <div class="form-row">
            <div class="form-group">
              <label>Ring Buffer Size</label>
              <input v-model.number="localConfig.session.ring_buffer_size" type="number" class="form-input" />
              <span class="form-hint">Requests kept per session for context analysis</span>
            </div>
            <div class="form-group">
              <label>Session TTL (seconds)</label>
              <input v-model.number="localConfig.session.ttl_seconds" type="number" class="form-input" />
              <span class="form-hint">Idle session expiration time</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Audit Settings -->
      <div class="settings-card">
        <div class="card-header">
          <div class="card-icon cyan">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
          </div>
          <h3>Audit Logging</h3>
        </div>
        <div class="card-body">
          <div class="form-group">
            <label>Audit Log Path</label>
            <input v-model="localConfig.audit_log_path" type="text" class="form-input mono" />
            <span class="form-hint">JSONL format — one entry per line</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Save Bar -->
    <div class="save-bar" :class="{ visible: hasChanges }">
      <span class="save-text">You have unsaved changes</span>
      <div class="save-actions">
        <button class="btn-secondary" @click="resetConfig">Discard</button>
        <button class="btn-primary" @click="saveConfig" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FirewallConfig } from '../types'

const props = defineProps<{
  config: FirewallConfig | null
  saving: boolean
}>()

const emit = defineEmits<{
  save: [config: Partial<FirewallConfig>]
}>()

const showApiKey = ref(false)

const defaultConfig: FirewallConfig = {
  network: { listen_host: '127.0.0.1', listen_port: 9090, upstream_host: '127.0.0.1', upstream_port: 3000, transport_mode: 'sse' },
  engine: { l1_enabled: true, l2_enabled: true, l2_model_endpoint: 'https://openrouter.ai/api/v1/chat/completions', l2_api_key: '', l2_model: 'minimax/minimax-m2.5', l2_timeout_seconds: 10 },
  session: { ring_buffer_size: 64, ttl_seconds: 3600 },
  rate_limit: { requests_per_sec: 100, burst: 200 },
  audit_log_path: './audit/firewall.jsonl',
  blocked_commands: ['rm -rf', '/etc/shadow', '/etc/passwd', 'DROP TABLE', 'DELETE FROM', 'TRUNCATE', 'shutdown', 'mkfs', 'dd if=', 'FORMAT C:', 'wget|sh', 'curl|bash'],
}

const localConfig = reactive<FirewallConfig>(JSON.parse(JSON.stringify(props.config || defaultConfig)))

watch(() => props.config, (newConfig) => {
  if (newConfig) {
    Object.assign(localConfig, JSON.parse(JSON.stringify(newConfig)))
  }
}, { deep: true })

const hasChanges = computed(() => {
  return JSON.stringify(localConfig) !== JSON.stringify(props.config || defaultConfig)
})

function updateBlockedCommands(text: string) {
  localConfig.blocked_commands = text.split('\n').map((s) => s.trim()).filter(Boolean)
}

function resetConfig() {
  Object.assign(localConfig, JSON.parse(JSON.stringify(props.config || defaultConfig)))
}

function saveConfig() {
  emit('save', JSON.parse(JSON.stringify(localConfig)))
}
</script>

<style scoped>
.engine-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  padding-bottom: 100px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 { font-size: 24px; font-weight: 600; color: #fff; margin: 0 0 4px; }
.subtitle { color: #666; font-size: 14px; margin: 0; }

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.settings-card {
  background: #141428;
  border: 1px solid #2a2a3e;
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.card-header h3 { font-size: 15px; font-weight: 600; color: #ccc; margin: 0; flex: 1; }

.card-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
}

.card-icon svg { width: 20px; height: 20px; }
.card-icon.blue { background: rgba(68, 136, 255, 0.15); color: #4488ff; }
.card-icon.green { background: rgba(0, 255, 136, 0.15); color: #00ff88; }
.card-icon.purple { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.card-icon.orange { background: rgba(255, 170, 0, 0.15); color: #ffaa00; }
.card-icon.cyan { background: rgba(0, 200, 255, 0.15); color: #00c8ff; }

.card-body { padding: 20px; }
.card-description { font-size: 12px; color: #666; margin: 0 0 16px; line-height: 1.5; }

.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: #888; margin-bottom: 6px; }
.form-group .count { color: #555; }

.form-input {
  width: 100%; background: #0a0a12; border: 1px solid #2a2a3e; border-radius: 8px;
  color: #ccc; padding: 8px 14px; font-size: 13px;
}
.form-input:focus { outline: none; border-color: #4488ff; }
.form-input.mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
textarea.form-input { resize: vertical; }
.form-hint { font-size: 11px; color: #555; margin-top: 4px; display: block; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }

.input-with-toggle { position: relative; }
.btn-toggle {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px 8px;
}

/* Switch */
.switch { position: relative; display: inline-block; width: 36px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute; cursor: pointer; inset: 0;
  background-color: #333; border-radius: 20px; transition: 0.3s;
}
.slider::before {
  content: ''; position: absolute; width: 16px; height: 16px; left: 2px; bottom: 2px;
  background: #888; border-radius: 50%; transition: 0.3s;
}
input:checked + .slider { background-color: #00cc66; }
input:checked + .slider::before { transform: translateX(16px); background: #fff; }

/* Save Bar */
.save-bar {
  position: fixed; bottom: 0; right: 0; left: 240px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 24px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-top: 2px solid #e94560;
  transform: translateY(100%);
  transition: transform 0.3s ease;
  z-index: 50;
}

.save-bar.visible { transform: translateY(0); }
.save-text { color: #e94560; font-size: 13px; font-weight: 500; }
.save-actions { display: flex; gap: 12px; }

.btn-primary {
  padding: 8px 20px; background: linear-gradient(135deg, #e94560 0%, #c73450 100%);
  border: none; border-radius: 8px; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  padding: 8px 20px; border: 1px solid #2a2a3e; border-radius: 8px;
  background: transparent; color: #888; font-size: 13px; cursor: pointer;
}
.btn-secondary:hover { border-color: #3a3a4e; color: #ccc; }

@media (max-width: 1200px) {
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
