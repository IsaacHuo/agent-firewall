<template>
  <div class="rules-page">
    <div class="page-header">
      <div>
        <h2>Security Rules</h2>
        <p class="subtitle">Configure pattern matching, method policies, and agent permissions</p>
      </div>
      <button class="btn-primary" @click="showAddRule = true">+ Add Rule</button>
    </div>

    <!-- Rule Category Tabs -->
    <div class="rule-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="rule-tab"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon" v-html="tab.icon"></span>
        {{ tab.label }}
        <span class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Pattern Rules -->
    <div v-if="activeTab === 'patterns'" class="rules-section">
      <div class="rules-toolbar">
        <input v-model="searchQuery" type="text" class="search-input" placeholder="Search rules..." />
        <div class="toolbar-actions">
          <select v-model="actionFilter" class="filter-select">
            <option value="">All Actions</option>
            <option value="BLOCK">BLOCK</option>
            <option value="ESCALATE">ESCALATE</option>
            <option value="ALLOW">ALLOW</option>
            <option value="LOG">LOG</option>
          </select>
        </div>
      </div>

      <div class="rules-list">
        <div
          v-for="rule in filteredPatternRules"
          :key="rule.id"
          class="rule-card"
          :class="{ disabled: !rule.enabled }"
        >
          <div class="rule-header">
            <div class="rule-toggle">
              <label class="switch">
                <input type="checkbox" :checked="rule.enabled" @change="toggleRule(rule)" />
                <span class="slider"></span>
              </label>
            </div>
            <div class="rule-info">
              <div class="rule-name">{{ rule.name }}</div>
              <div class="rule-description">{{ rule.description || 'No description' }}</div>
            </div>
            <div class="rule-badges">
              <span class="badge" :class="'action-' + rule.action.toLowerCase()">{{ rule.action }}</span>
              <span class="badge" :class="'threat-' + rule.threat_level.toLowerCase()">{{ rule.threat_level }}</span>
              <span class="badge type">{{ rule.type }}</span>
            </div>
            <div class="rule-actions">
              <button class="btn-icon-sm" @click="editRule(rule)" title="Edit">✏️</button>
              <button class="btn-icon-sm danger" @click="confirmDeleteRule(rule)" title="Delete">🗑️</button>
            </div>
          </div>
          <div class="rule-pattern">
            <code>{{ rule.pattern }}</code>
          </div>
        </div>

        <div v-if="filteredPatternRules.length === 0" class="empty-state">
          <span class="empty-icon">🛡️</span>
          <p>No pattern rules configured</p>
          <button class="btn-primary" @click="showAddRule = true">Add your first rule</button>
        </div>
      </div>
    </div>

    <!-- Method Rules -->
    <div v-if="activeTab === 'methods'" class="rules-section">
      <div class="method-rules-list">
        <div v-for="rule in rules.method_rules" :key="rule.method" class="method-rule-row">
          <div class="method-name">{{ rule.method }}</div>
          <div class="method-description">{{ rule.description || '—' }}</div>
          <select
            class="action-select"
            :class="'action-' + rule.action.toLowerCase()"
            :value="rule.action"
            @change="updateMethodAction(rule.method, ($event.target as HTMLSelectElement).value)"
          >
            <option value="ALLOW">ALLOW</option>
            <option value="BLOCK">BLOCK</option>
            <option value="ESCALATE">ESCALATE</option>
            <option value="LOG">LOG</option>
          </select>
        </div>

        <!-- Default MCP methods -->
        <div class="section-divider">
          <span>Default MCP Methods</span>
        </div>
        <div v-for="method in defaultMethods" :key="method.name" class="method-rule-row default">
          <div class="method-name">{{ method.name }}</div>
          <div class="method-description">{{ method.description }}</div>
          <span class="badge" :class="'action-' + method.defaultAction.toLowerCase()">
            {{ method.defaultAction }}
          </span>
        </div>
      </div>
    </div>

    <!-- Agent Rules -->
    <div v-if="activeTab === 'agents'" class="rules-section">
      <div class="agent-rules-list">
        <div v-for="rule in rules.agent_rules" :key="rule.agent_id_pattern" class="agent-rule-card">
          <div class="agent-header">
            <div class="agent-pattern">
              <span class="label">Agent Pattern:</span>
              <code>{{ rule.agent_id_pattern }}</code>
            </div>
            <div v-if="rule.rate_limit" class="agent-rate">
              {{ rule.rate_limit }} req/s
            </div>
          </div>
          <div class="agent-methods">
            <span class="label">Allowed Methods:</span>
            <div class="method-chips">
              <span v-for="m in rule.allowed_methods" :key="m" class="method-chip">{{ m }}</span>
            </div>
          </div>
        </div>

        <div v-if="rules.agent_rules.length === 0" class="empty-state">
          <span class="empty-icon">🤖</span>
          <p>No agent-specific rules configured</p>
        </div>
      </div>
    </div>

    <!-- Default Action -->
    <div class="default-action-bar">
      <span class="label">Default Action (when no rule matches):</span>
      <select
        class="action-select large"
        :class="'action-' + rules.default_action.toLowerCase()"
        :value="rules.default_action"
        @change="updateDefaultAction(($event.target as HTMLSelectElement).value)"
      >
        <option value="ALLOW">ALLOW</option>
        <option value="BLOCK">BLOCK</option>
        <option value="ESCALATE">ESCALATE</option>
        <option value="LOG">LOG</option>
      </select>
    </div>

    <!-- Add/Edit Rule Modal -->
    <Teleport to="body">
      <div v-if="showAddRule || editingRule" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <div class="modal-header">
            <h3>{{ editingRule ? 'Edit Rule' : 'Add Pattern Rule' }}</h3>
            <button class="btn-close" @click="closeModal">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Rule Name</label>
              <input v-model="ruleForm.name" type="text" class="form-input" placeholder="e.g., Block shell injection" />
            </div>
            <div class="form-group">
              <label>Pattern</label>
              <input v-model="ruleForm.pattern" type="text" class="form-input mono" placeholder="e.g., rm -rf or .*\\bexec\\b.*" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Type</label>
                <select v-model="ruleForm.type" class="form-input">
                  <option value="literal">Literal</option>
                  <option value="regex">Regex</option>
                </select>
              </div>
              <div class="form-group">
                <label>Action</label>
                <select v-model="ruleForm.action" class="form-input">
                  <option value="BLOCK">BLOCK</option>
                  <option value="ESCALATE">ESCALATE</option>
                  <option value="ALLOW">ALLOW</option>
                  <option value="LOG">LOG</option>
                </select>
              </div>
              <div class="form-group">
                <label>Threat Level</label>
                <select v-model="ruleForm.threat_level" class="form-input">
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="HIGH">HIGH</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="LOW">LOW</option>
                  <option value="NONE">NONE</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label>Description (optional)</label>
              <textarea v-model="ruleForm.description" class="form-input" rows="2" placeholder="What does this rule do?"></textarea>
            </div>
            <!-- Live Test Preview -->
            <div class="form-group" v-if="ruleForm.pattern">
              <label>Test Pattern</label>
              <input v-model="testInput" type="text" class="form-input" placeholder="Enter text to test against pattern..." />
              <div v-if="testInput" class="test-result" :class="{ match: testMatch, 'no-match': !testMatch }">
                {{ testMatch ? '✓ Pattern matches' : '✕ No match' }}
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="closeModal">Cancel</button>
            <button class="btn-primary" @click="saveRule" :disabled="!ruleForm.name || !ruleForm.pattern">
              {{ editingRule ? 'Save Changes' : 'Add Rule' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <div v-if="deletingRule" class="modal-overlay" @click.self="deletingRule = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <h3>Delete Rule</h3>
          </div>
          <div class="modal-body">
            <p>Are you sure you want to delete <strong>{{ deletingRule.name }}</strong>?</p>
            <p class="muted">This action cannot be undone.</p>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="deletingRule = null">Cancel</button>
            <button class="btn-danger" @click="doDeleteRule">Delete</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RulesConfig, PatternRule, RuleAction, ThreatLevel } from '../types'

const props = defineProps<{
  rules: RulesConfig
}>()

const emit = defineEmits<{
  save: [rule: PatternRule]
  delete: [ruleId: string]
  toggle: [ruleId: string, enabled: boolean]
  updateMethodAction: [method: string, action: string]
  updateDefaultAction: [action: string]
}>()

const activeTab = ref<'patterns' | 'methods' | 'agents'>('patterns')
const searchQuery = ref('')
const actionFilter = ref('')
const showAddRule = ref(false)
const editingRule = ref<PatternRule | null>(null)
const deletingRule = ref<PatternRule | null>(null)
const testInput = ref('')

const emptyForm = {
  id: '',
  name: '',
  pattern: '',
  type: 'literal' as const,
  action: 'BLOCK' as RuleAction,
  threat_level: 'HIGH' as ThreatLevel,
  enabled: true,
  description: '',
  created_at: 0,
  updated_at: 0,
}

const ruleForm = ref({ ...emptyForm })

const tabs = computed(() => [
  {
    id: 'patterns' as const,
    label: 'Pattern Rules',
    count: props.rules.pattern_rules.length,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    </svg>`,
  },
  {
    id: 'methods' as const,
    label: 'Method Policies',
    count: props.rules.method_rules.length,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
      <polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>`,
  },
  {
    id: 'agents' as const,
    label: 'Agent Rules',
    count: props.rules.agent_rules.length,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
      <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path>
    </svg>`,
  },
])

const filteredPatternRules = computed(() => {
  return props.rules.pattern_rules.filter((r) => {
    if (actionFilter.value && r.action !== actionFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return (
        r.name.toLowerCase().includes(q) ||
        r.pattern.toLowerCase().includes(q) ||
        (r.description?.toLowerCase().includes(q) ?? false)
      )
    }
    return true
  })
})

const testMatch = computed(() => {
  if (!testInput.value || !ruleForm.value.pattern) return false
  try {
    if (ruleForm.value.type === 'regex') {
      return new RegExp(ruleForm.value.pattern, 'i').test(testInput.value)
    }
    return testInput.value.toLowerCase().includes(ruleForm.value.pattern.toLowerCase())
  } catch {
    return false
  }
})

const defaultMethods = [
  { name: 'initialize', description: 'MCP handshake — always safe', defaultAction: 'ALLOW' },
  { name: 'tools/list', description: 'Tool discovery — read-only', defaultAction: 'ALLOW' },
  { name: 'tools/call', description: 'Tool invocation — HIGH RISK', defaultAction: 'ESCALATE' },
  { name: 'resources/list', description: 'Resource discovery', defaultAction: 'ALLOW' },
  { name: 'sampling/createMessage', description: 'Sampling — HIGH RISK', defaultAction: 'ESCALATE' },
  { name: 'prompts/list', description: 'Prompt discovery', defaultAction: 'ALLOW' },
  { name: 'ping', description: 'Keepalive', defaultAction: 'ALLOW' },
]

function editRule(rule: PatternRule) {
  ruleForm.value = { ...rule }
  editingRule.value = rule
}

function confirmDeleteRule(rule: PatternRule) {
  deletingRule.value = rule
}

function closeModal() {
  showAddRule.value = false
  editingRule.value = null
  ruleForm.value = { ...emptyForm }
  testInput.value = ''
}

function saveRule() {
  const now = Date.now() / 1000
  const rule: PatternRule = {
    ...ruleForm.value,
    id: ruleForm.value.id || `rule-${Date.now()}`,
    created_at: ruleForm.value.created_at || now,
    updated_at: now,
  }
  emit('save', rule)
  closeModal()
}

function doDeleteRule() {
  if (deletingRule.value) {
    emit('delete', deletingRule.value.id)
    deletingRule.value = null
  }
}

function toggleRule(rule: PatternRule) {
  emit('toggle', rule.id, !rule.enabled)
}

function updateMethodAction(method: string, action: string) {
  emit('updateMethodAction', method, action)
}

function updateDefaultAction(action: string) {
  emit('updateDefaultAction', action)
}
</script>

<style scoped>
.rules-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0;
}

.btn-primary {
  padding: 8px 20px;
  background: var(--btn-primary-bg);
  border: none;
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.2s;
}

.btn-primary:hover {
  transform: scale(1.02);
  box-shadow: 0 0 16px rgba(233, 69, 96, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* Tabs */
.rule-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  padding: 4px;
  background: var(--bg-secondary);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.rule-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-dim);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.rule-tab:hover {
  color: var(--text-secondary);
  background: var(--border-subtle);
}

.rule-tab.active {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.tab-icon {
  display: flex;
  align-items: center;
}

.tab-count {
  background: var(--border);
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  color: var(--text-dim);
}

/* Toolbar */
.rules-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  padding: 10px 16px;
  font-size: 13px;
  transition: all 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-muted);
}

.filter-select {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  padding: 8px 12px;
  font-size: 13px;
  outline: none;
  cursor: pointer;
  transition: all 0.2s;
}
.filter-select:focus { border-color: var(--accent); }

/* Rule Cards */
.rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-bottom: 20px;
}

.rule-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: all 0.2s;
  box-shadow: var(--shadow-sm);
}

.rule-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.rule-card.disabled {
  opacity: 0.6;
  background: var(--bg-primary);
}

.rule-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.rule-info {
  flex: 1;
}

.rule-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-description {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.rule-badges {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.badge {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.badge.action-block { background: var(--accent-red-muted); color: var(--accent-red); border-color: rgba(239,68,68,0.2); }
.badge.action-escalate { background: var(--accent-yellow-muted); color: var(--accent-yellow); border-color: rgba(245,158,11,0.2); }
.badge.action-allow { background: var(--accent-green-muted); color: var(--accent-green); border-color: rgba(16,185,129,0.2); }
.badge.action-log { background: var(--accent-muted); color: var(--accent); border-color: rgba(59,130,246,0.2); }

.badge.threat-critical { background: var(--accent-red); color: white; }
.badge.threat-high { background: var(--accent-red-muted); color: var(--accent-red); }
.badge.threat-medium { background: var(--accent-yellow-muted); color: var(--accent-yellow); }
.badge.threat-low { background: var(--accent-muted); color: var(--accent); }
.badge.threat-none { background: var(--bg-hover); color: var(--text-muted); border-color: var(--border); }
.badge.type { background: var(--bg-hover); color: var(--text-dim); border: 1px solid var(--border); }

.rule-actions {
  display: flex;
  gap: 4px;
}

.btn-icon-sm {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  transition: all 0.2s;
}

.btn-icon-sm:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-icon-sm.danger:hover {
  background: var(--accent-red-muted);
  color: var(--accent-red);
}

.rule-pattern {
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  overflow-x: auto;
}

.rule-pattern code {
  font-family: inherit; color: inherit;
}

/* Switch */
.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--toggle-bg);
  transition: .2s;
  border-radius: 20px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: var(--toggle-knob);
  transition: .2s;
  border-radius: 50%;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

input:checked + .slider {
  background-color: var(--toggle-bg-active);
}

input:checked + .slider:before {
  transform: translateX(16px);
}

/* Method Rules */
.method-rules-list {
  overflow-y: auto;
  padding-bottom: 20px;
}

.method-rule-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 8px;
  transition: all 0.2s;
}
.method-rule-row:hover {
  border-color: var(--border-hover);
  background: var(--bg-hover);
}

.method-name {
  width: 180px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}

.method-description {
  flex: 1;
  font-size: 13px;
  color: var(--text-muted);
}

.action-select {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  outline: none;
  transition: all 0.2s;
}
.action-select:focus { border-color: var(--accent); }

.action-select.action-allow { color: var(--accent-green); border-color: var(--accent-green-muted); }
.action-select.action-block { color: var(--accent-red); border-color: var(--accent-red-muted); }
.action-select.action-escalate { color: var(--accent-yellow); border-color: var(--accent-yellow-muted); }
.action-select.action-log { color: var(--accent); border-color: var(--accent-muted); }

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-muted);
}
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }

/* Modal and other styles remain mostly same but use variables */
.modal {
  background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
}
.modal-header { padding: 20px 24px; border-bottom: 1px solid var(--border); }
.modal-header h3 { font-size: 18px; font-weight: 600; color: var(--text-primary); }
.btn-close { color: var(--text-dim); border-color: var(--border); }
.btn-close:hover { color: var(--text-primary); background: var(--bg-hover); }

.form-input {
  background: var(--bg-primary); border: 1px solid var(--border); color: var(--text-primary);
  border-radius: var(--radius-md); padding: 10px 14px;
}
.form-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-muted); }

.btn-secondary {
  border: 1px solid var(--border); color: var(--text-secondary); border-radius: var(--radius-md);
  padding: 8px 16px; font-weight: 500;
}
.btn-secondary:hover { background: var(--bg-hover); color: var(--text-primary); }

.btn-danger {
  background: var(--danger); color: white; border: none; border-radius: var(--radius-md);
  padding: 8px 16px; font-weight: 600;
}
.btn-danger:hover { filter: brightness(1.1); }
</style>
