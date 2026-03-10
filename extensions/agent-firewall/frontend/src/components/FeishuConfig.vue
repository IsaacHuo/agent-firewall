<template>
  <div class="feishu-config">
    <div class="config-header">
      <h2>飞书通道配置</h2>
      <p class="subtitle">Configure Feishu/Lark channel settings and monitor message traffic</p>
    </div>

    <!-- Connection Status -->
    <div class="status-card" :class="{ connected: feishuConnected }">
      <div class="status-indicator">
        <div class="status-dot" :class="{ active: feishuConnected }"></div>
        <span class="status-text">{{ feishuConnected ? '已连接' : '未连接' }}</span>
      </div>
      <div class="status-info">
        <span v-if="feishuConnected">WebSocket connection active</span>
        <span v-else>Feishu channel is not enabled</span>
      </div>
    </div>

    <!-- Configuration Form -->
    <div class="config-section">
      <h3>基础配置</h3>
      <div class="form-grid">
        <div class="form-field">
          <label>App ID</label>
          <input
            type="text"
            v-model="config.app_id"
            placeholder="cli_xxxxxxxxxxxxx"
            :disabled="feishuConnected"
          />
        </div>

        <div class="form-field">
          <label>App Secret</label>
          <input
            type="password"
            v-model="config.app_secret"
            placeholder="Enter app secret"
            :disabled="feishuConnected"
          />
        </div>

        <div class="form-field">
          <label>Encrypt Key (可选)</label>
          <input
            type="text"
            v-model="config.encrypt_key"
            placeholder="Event encryption key"
            :disabled="feishuConnected"
          />
        </div>

        <div class="form-field">
          <label>Verification Token (可选)</label>
          <input
            type="text"
            v-model="config.verification_token"
            placeholder="Event verification token"
            :disabled="feishuConnected"
          />
        </div>
      </div>
    </div>

    <!-- AI Model Configuration -->
    <div class="config-section">
      <h3>AI模型配置</h3>
      <div class="form-grid">
        <div class="form-field full-width">
          <label>Upstream AI URL</label>
          <input
            type="text"
            v-model="config.upstream_url"
            placeholder="https://api.openai.com/v1"
          />
          <span class="field-hint">AI agent endpoint for processing Feishu messages</span>
        </div>

        <div class="form-field">
          <label>Model</label>
          <input
            type="text"
            v-model="config.model"
            placeholder="gpt-4"
          />
        </div>

        <div class="form-field">
          <label>Timeout (seconds)</label>
          <input
            type="number"
            v-model.number="config.timeout"
            min="5"
            max="120"
          />
        </div>
      </div>
    </div>

    <!-- Statistics -->
    <div class="config-section">
      <h3>消息统计</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_messages }}</div>
          <div class="stat-label">Total Messages</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.blocked_messages }}</div>
          <div class="stat-label">Blocked</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.active_chats }}</div>
          <div class="stat-label">Active Chats</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.avg_response_time }}ms</div>
          <div class="stat-label">Avg Response Time</div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="config-actions">
      <button class="btn-primary" @click="saveConfig" :disabled="feishuConnected">
        保存配置
      </button>
      <button class="btn-secondary" @click="testConnection">
        测试连接
      </button>
      <button class="btn-danger" v-if="feishuConnected" @click="disconnect">
        断开连接
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const feishuConnected = ref(false)

const config = ref({
  app_id: '',
  app_secret: '',
  encrypt_key: '',
  verification_token: '',
  upstream_url: 'https://api.openai.com/v1',
  model: 'gpt-4',
  timeout: 30,
})

const stats = ref({
  total_messages: 0,
  blocked_messages: 0,
  active_chats: 0,
  avg_response_time: 0,
})

onMounted(async () => {
  await loadConfig()
  await loadStats()
})

async function loadConfig() {
  try {
    const response = await fetch('/api/feishu/config')
    if (response.ok) {
      const data = await response.json()
      config.value = { ...config.value, ...data }
      feishuConnected.value = data.connected || false
    }
  } catch (error) {
    console.error('Failed to load Feishu config:', error)
  }
}

async function loadStats() {
  try {
    const response = await fetch('/api/feishu/stats')
    if (response.ok) {
      const data = await response.json()
      stats.value = data
    }
  } catch (error) {
    console.error('Failed to load Feishu stats:', error)
  }
}

async function saveConfig() {
  try {
    const response = await fetch('/api/feishu/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config.value),
    })
    if (response.ok) {
      alert('配置已保存！请重启服务以应用更改。')
    } else {
      alert('保存失败')
    }
  } catch (error) {
    console.error('Failed to save config:', error)
    alert('保存失败')
  }
}

async function testConnection() {
  alert('测试连接功能开发中...')
}

async function disconnect() {
  if (confirm('确定要断开飞书连接吗？')) {
    // TODO: Implement disconnect
    alert('断开连接功能开发中...')
  }
}
</script>

<style scoped>
.feishu-config {
  padding: 2rem;
  max-width: 1200px;
}

.config-header {
  margin-bottom: 2rem;
}

.config-header h2 {
  font-size: 1.75rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.status-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  display: flex;
  align-items: center;
  gap: 2rem;
}

.status-card.connected {
  border-color: var(--success-color);
  background: var(--success-bg);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-dot.active {
  background: var(--success-color);
  box-shadow: 0 0 8px var(--success-color);
}

.status-text {
  font-weight: 600;
  font-size: 1.1rem;
}

.status-info {
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.config-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.config-section h3 {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1.25rem;
  color: var(--text-primary);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-field.full-width {
  grid-column: 1 / -1;
}

.form-field label {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-field input {
  padding: 0.625rem 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

.form-field input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.form-field input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.field-hint {
  font-size: 0.85rem;
  color: var(--text-tertiary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 1.25rem;
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-actions {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
}

.btn-primary,
.btn-secondary,
.btn-danger {
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-weight: 500;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-tertiary);
}

.btn-danger {
  background: var(--danger-color);
  color: white;
}

.btn-danger:hover {
  opacity: 0.9;
}
</style>
