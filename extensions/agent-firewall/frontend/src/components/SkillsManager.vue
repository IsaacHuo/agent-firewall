<template>
  <div class="skills-page">
    <header class="page-header">
      <h2>Skills Management</h2>
      <p class="subtitle">Manage skills, API keys, and availability for your agents</p>
      <div class="header-actions">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Search skills..."
        />
        <button class="btn btn-secondary" @click="refresh">
          <span v-html="refreshIcon"></span>
          Refresh
        </button>
      </div>
    </header>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading skills...</p>
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

    <!-- Skills list -->
    <div v-else class="skills-grid">
      <!-- Skill groups -->
      <div v-for="group in groupedSkills" :key="group.label" class="skill-group">
        <h3 class="group-label">
          {{ group.label }}
          <span class="group-count">{{ group.skills.length }}</span>
        </h3>
        <div class="skill-cards">
          <div
            v-for="skill in group.skills"
            :key="skill.skillKey"
            class="skill-card"
            :class="{
              disabled: skill.disabled,
              'has-missing': skill.missing.bins.length > 0 || skill.missing.env.length > 0,
              always: skill.always,
            }"
          >
            <div class="skill-header">
              <span class="skill-emoji">{{ skill.emoji || '🔧' }}</span>
              <div class="skill-info">
                <span class="skill-name">{{ skill.name }}</span>
                <span class="skill-source">{{ skill.source }}</span>
              </div>
              <div class="skill-toggle" v-if="!skill.always">
                <label class="toggle">
                  <input
                    type="checkbox"
                    :checked="!skill.disabled"
                    @change="toggleSkill(skill)"
                  />
                  <span class="toggle-slider"></span>
                </label>
              </div>
              <span v-else class="always-badge">Always On</span>
            </div>

            <p class="skill-description">{{ skill.description }}</p>

            <!-- Status chips -->
            <div class="skill-chips">
              <span v-if="skill.eligible" class="chip chip-green">Eligible</span>
              <span v-else class="chip chip-red">Not Eligible</span>
              <span v-if="skill.bundled" class="chip chip-blue">Bundled</span>
              <span v-if="skill.blockedByAllowlist" class="chip chip-yellow">Allowlist Blocked</span>
            </div>

            <!-- Missing requirements -->
            <div v-if="skill.missing.bins.length > 0" class="skill-missing">
              <span class="missing-label">Missing binaries:</span>
              <span class="missing-items">{{ skill.missing.bins.join(', ') }}</span>
              <!-- Install options -->
              <div v-if="skill.install.length > 0" class="install-options">
                <button
                  v-for="opt in skill.install"
                  :key="opt.id"
                  class="btn btn-sm btn-install"
                  @click="handleInstall(skill.name, opt.id)"
                  :disabled="installing"
                >
                  Install via {{ opt.kind }}
                </button>
              </div>
            </div>

            <!-- API Key input (if primaryEnv is set) -->
            <div v-if="skill.primaryEnv" class="skill-apikey">
              <label class="apikey-label">
                <span class="key-icon">🔑</span>
                {{ skill.primaryEnv }}
              </label>
              <div class="apikey-input-row">
                <input
                  type="password"
                  :placeholder="`Enter ${skill.primaryEnv}`"
                  :value="apiKeyInputs[skill.skillKey] || ''"
                  @input="(e) => apiKeyInputs[skill.skillKey] = (e.target as HTMLInputElement).value"
                  class="apikey-input"
                />
                <button
                  class="btn btn-sm btn-primary"
                  @click="saveApiKey(skill)"
                  :disabled="!apiKeyInputs[skill.skillKey]"
                >
                  Save
                </button>
              </div>
            </div>

            <!-- Homepage link -->
            <a v-if="skill.homepage" :href="skill.homepage" target="_blank" class="skill-link">
              View Documentation ↗
            </a>
          </div>
        </div>
      </div>

      <div v-if="filteredSkills.length === 0" class="empty-state">
        <p>No skills found matching "{{ searchQuery }}"</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import type { SkillStatusEntry } from '../types'
import { useGatewaySkills, useGatewayStatus } from '../composables'

const { skills, loading, error, loadSkills, toggleSkill: doToggle, setSkillApiKey, installSkill } = useGatewaySkills()
const { connected: gwConnected, connectError } = useGatewayStatus()

const searchQuery = ref('')
const installing = ref(false)
const apiKeyInputs = reactive<Record<string, string>>({})
const tokenInput = ref('')

function saveToken() {
  if (tokenInput.value) {
    localStorage.setItem('af-gateway-token', tokenInput.value)
    tokenInput.value = ''
    // Trigger reconnect — page will auto-retry on next load
    window.location.reload()
  }
}

const filteredSkills = computed(() => {
  const q = searchQuery.value.toLowerCase()
  if (!q) return skills.value
  return skills.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.source.toLowerCase().includes(q),
  )
})

const groupedSkills = computed(() => {
  const groups: Record<string, SkillStatusEntry[]> = {}
  for (const skill of filteredSkills.value) {
    const key = skill.bundled ? 'Bundled Skills' : skill.source === 'workspace' ? 'Workspace Skills' : 'Managed Skills'
    if (!groups[key]) groups[key] = []
    groups[key].push(skill)
  }
  const order = ['Bundled Skills', 'Managed Skills', 'Workspace Skills']
  return order
    .filter((label) => groups[label]?.length)
    .map((label) => ({ label, skills: groups[label] }))
})

function toggleSkill(skill: SkillStatusEntry) {
  doToggle(skill.skillKey, skill.disabled)
}

function saveApiKey(skill: SkillStatusEntry) {
  const key = apiKeyInputs[skill.skillKey]
  if (key) {
    setSkillApiKey(skill.skillKey, key)
    apiKeyInputs[skill.skillKey] = ''
  }
}

async function handleInstall(name: string, installId: string) {
  installing.value = true
  try {
    await installSkill(name, installId)
  } finally {
    installing.value = false
  }
}

function refresh() {
  loadSkills()
}

const refreshIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`

onMounted(() => {
  loadSkills()
})
</script>

<style scoped>
.skills-page {
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

.search-input {
  flex: 1;
  max-width: 400px;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--accent-blue);
}

.search-input::placeholder {
  color: var(--text-dim);
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

.btn-install {
  background: rgba(68, 136, 255, 0.15);
  color: var(--accent-blue);
  border: 1px solid rgba(68, 136, 255, 0.3);
}

.btn-install:hover {
  background: rgba(68, 136, 255, 0.25);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading / Error states */
.loading-state,
.error-state {
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

/* Skills grid */
.skill-group {
  margin-bottom: 28px;
}

.group-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-count {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-elevated);
  color: var(--text-muted);
}

.skill-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 12px;
}

.skill-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  transition: border-color 0.2s;
}

.skill-card:hover {
  border-color: var(--border-hover);
}

.skill-card.disabled {
  opacity: 0.6;
}

.skill-card.always {
  border-left: 3px solid var(--accent-green);
}

.skill-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.skill-emoji {
  font-size: 24px;
}

.skill-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.skill-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.skill-source {
  font-size: 12px;
  color: var(--text-dim);
}

.skill-description {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 10px;
}

.skill-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
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

.chip-blue {
  background: rgba(68, 136, 255, 0.15);
  color: var(--accent-blue);
}

.chip-yellow {
  background: rgba(255, 170, 0, 0.15);
  color: var(--accent-yellow);
}

.skill-missing {
  background: rgba(255, 170, 0, 0.08);
  border: 1px solid rgba(255, 170, 0, 0.2);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
  font-size: 13px;
}

.missing-label {
  color: var(--accent-yellow);
  font-weight: 500;
}

.missing-items {
  color: var(--text-muted);
  font-family: monospace;
  font-size: 12px;
}

.install-options {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.skill-apikey {
  margin-bottom: 10px;
}

.apikey-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
  margin-bottom: 6px;
}

.key-icon {
  font-size: 14px;
}

.apikey-input-row {
  display: flex;
  gap: 8px;
}

.apikey-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 13px;
  font-family: monospace;
  outline: none;
}

.apikey-input:focus {
  border-color: var(--accent-blue);
}

.skill-link {
  display: inline-block;
  font-size: 12px;
  color: var(--accent-blue);
  text-decoration: none;
}

.skill-link:hover {
  text-decoration: underline;
}

.always-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  background: rgba(0, 204, 106, 0.15);
  color: var(--accent-green);
  font-weight: 500;
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

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-dim);
}
</style>
