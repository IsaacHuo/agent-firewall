<template>
  <div class="dataset-detail">
    <div v-if="loading" class="loading-state">
      <p>Loading dataset...</p>
    </div>

    <div v-else-if="!dataset" class="error-state">
      <p>Dataset not found</p>
      <button @click="$emit('back')" class="btn-primary">Back to List</button>
    </div>

    <div v-else class="dataset-content">
      <!-- Header -->
      <div class="detail-header">
        <button @click="$emit('back')" class="btn-back">← Back</button>
        <div class="header-info">
          <h2>{{ dataset.name }}</h2>
          <span v-if="dataset.is_public" class="public-badge">Public</span>
        </div>
        <div class="header-actions">
          <button @click="showPolicyCheck = true" class="btn-secondary">
            Check Policy
          </button>
        </div>
      </div>

      <p v-if="dataset.description" class="dataset-description">
        {{ dataset.description }}
      </p>

      <!-- Stats -->
      <div class="dataset-stats">
        <div class="stat-card">
          <span class="stat-value">{{ traces.length }}</span>
          <span class="stat-label">Traces</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ dataset.policies?.length || 0 }}</span>
          <span class="stat-label">Policies</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ formatDate(dataset.created_at) }}</span>
          <span class="stat-label">Created</span>
        </div>
      </div>

      <!-- Traces List -->
      <div class="traces-section">
        <div class="section-header">
          <h3>Traces</h3>
          <button @click="showAddTrace = true" class="btn-secondary">
            + Add Trace
          </button>
        </div>

        <div v-if="traces.length === 0" class="empty-state">
          <p>No traces in this dataset</p>
          <button @click="showAddTrace = true" class="btn-primary">
            Add Your First Trace
          </button>
        </div>

        <div v-else class="traces-list">
          <div
            v-for="trace in traces"
            :key="trace.id"
            class="trace-item"
            @click="viewTrace(trace.id)"
          >
            <div class="trace-header">
              <span class="trace-id">{{ trace.id.substring(0, 8) }}</span>
              <span
                v-if="trace.analysis"
                class="verdict-badge"
                :class="trace.analysis.verdict.toLowerCase()"
              >
                {{ trace.analysis.verdict }}
              </span>
            </div>

            <div class="trace-info">
              <span class="trace-messages">
                {{ trace.messages?.length || 0 }} messages
              </span>
              <span v-if="trace.analysis" class="trace-threat">
                Threat: {{ trace.analysis.threat_level }}
              </span>
            </div>

            <div class="trace-footer">
              <span class="trace-time">
                {{ formatDate(trace.created_at) }}
              </span>
              <button
                @click.stop="removeTrace(trace.id)"
                class="btn-icon"
                title="Remove from dataset"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Trace Modal -->
    <div v-if="showAddTrace" class="modal-overlay" @click="showAddTrace = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Trace to Dataset</h3>
          <button @click="showAddTrace = false" class="btn-close">×</button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>Trace ID</label>
            <input
              v-model="addTraceId"
              type="text"
              placeholder="Enter trace ID"
              class="form-input"
            />
          </div>
        </div>

        <div class="modal-footer">
          <button @click="showAddTrace = false" class="btn-secondary">Cancel</button>
          <button @click="addTrace" class="btn-primary" :disabled="!addTraceId">
            Add Trace
          </button>
        </div>
      </div>
    </div>

    <!-- Policy Check Modal -->
    <div v-if="showPolicyCheck" class="modal-overlay" @click="showPolicyCheck = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Check Policy on Dataset</h3>
          <button @click="showPolicyCheck = false" class="btn-close">×</button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>Policy Code</label>
            <textarea
              v-model="policyCode"
              class="form-textarea"
              rows="8"
              placeholder='raise "High risk" if: threat_level >= "HIGH"'
            />
          </div>

          <div v-if="policyResults.length > 0" class="policy-results">
            <h4>Results ({{ policyResults.length }} / {{ traces.length }})</h4>
            <div class="results-list">
              <div
                v-for="result in policyResults"
                :key="result.trace_id"
                class="result-item"
                :class="{ failed: !result.passed }"
              >
                <span class="result-icon">{{ result.passed ? '✓' : '✗' }}</span>
                <span class="result-trace">{{ result.trace_id.substring(0, 8) }}</span>
                <span class="result-message">{{ result.message || 'No message' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="showPolicyCheck = false" class="btn-secondary">Close</button>
          <button
            @click="checkPolicy"
            class="btn-primary"
            :disabled="!policyCode || checkingPolicy"
          >
            {{ checkingPolicy ? 'Checking...' : 'Check Policy' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

interface Dataset {
  id: string
  name: string
  description: string
  is_public: boolean
  traces: string[]
  policies: string[]
  created_at: number
  updated_at: number
}

interface Trace {
  id: string
  messages: any[]
  analysis?: {
    verdict: string
    threat_level: string
  }
  created_at: number
}

interface Props {
  datasetId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  back: []
  'view-trace': [id: string]
}>()

// State
const dataset = ref<Dataset | null>(null)
const traces = ref<Trace[]>([])
const loading = ref(false)
const showAddTrace = ref(false)
const showPolicyCheck = ref(false)
const addTraceId = ref('')
const policyCode = ref('')
const policyResults = ref<any[]>([])
const checkingPolicy = ref(false)

// Methods
async function loadDataset() {
  loading.value = true
  try {
    const response = await fetch(`/api/v1/dataset/${props.datasetId}`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    dataset.value = await response.json()
    await loadTraces()
  } catch (error) {
    console.error('Failed to load dataset:', error)
  } finally {
    loading.value = false
  }
}

async function loadTraces() {
  if (!dataset.value) return

  try {
    const response = await fetch(`/api/v1/dataset/${props.datasetId}/traces`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const data = await response.json()
    traces.value = data.traces || []
  } catch (error) {
    console.error('Failed to load traces:', error)
  }
}

async function addTrace() {
  if (!addTraceId.value) return

  try {
    const response = await fetch(
      `/api/v1/dataset/${props.datasetId}/traces/${addTraceId.value}`,
      {
        method: 'POST',
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    showAddTrace.value = false
    addTraceId.value = ''
    await loadDataset()
  } catch (error) {
    console.error('Failed to add trace:', error)
    alert('Failed to add trace. Make sure the trace ID is valid.')
  }
}

async function removeTrace(traceId: string) {
  if (!confirm('Remove this trace from the dataset?')) {
    return
  }

  try {
    const response = await fetch(
      `/api/v1/dataset/${props.datasetId}/traces/${traceId}`,
      {
        method: 'DELETE',
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    await loadDataset()
  } catch (error) {
    console.error('Failed to remove trace:', error)
    alert('Failed to remove trace')
  }
}

async function checkPolicy() {
  if (!policyCode.value) return

  checkingPolicy.value = true
  policyResults.value = []

  try {
    const response = await fetch(`/api/v1/dataset/${props.datasetId}/policy/check`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        policy: policyCode.value,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    // Read streaming response
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n').filter((line) => line.trim())

        for (const line of lines) {
          try {
            const result = JSON.parse(line)
            policyResults.value.push(result)
          } catch (e) {
            console.error('Failed to parse result:', e)
          }
        }
      }
    }
  } catch (error) {
    console.error('Failed to check policy:', error)
    alert('Failed to check policy')
  } finally {
    checkingPolicy.value = false
  }
}

function viewTrace(traceId: string) {
  emit('view-trace', traceId)
}

function formatDate(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Lifecycle
onMounted(() => {
  loadDataset()
})

watch(() => props.datasetId, () => {
  loadDataset()
})
</script>

<style scoped>
.dataset-detail {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-secondary, #666);
  text-align: center;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.btn-back {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-back:hover {
  background: var(--bg-hover, #e8e8e8);
}

.header-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-info h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.public-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.dataset-description {
  margin: 0 0 24px 0;
  font-size: 15px;
  color: var(--text-secondary, #666);
  line-height: 1.6;
}

.dataset-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  padding: 20px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  background: var(--bg-secondary, #f5f5f5);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary, #666);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.traces-section {
  margin-top: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.traces-list {
  display: grid;
  gap: 12px;
}

.trace-item {
  padding: 16px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  background: var(--bg-primary, #ffffff);
  cursor: pointer;
  transition: all 0.2s;
}

.trace-item:hover {
  border-color: var(--primary-color, #007bff);
  box-shadow: 0 2px 8px rgba(0, 123, 255, 0.1);
}

.trace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.trace-id {
  font-family: monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.verdict-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}

.verdict-badge.allow {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.verdict-badge.block {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.verdict-badge.escalate {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.trace-info {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary, #666);
}

.trace-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--border-light, #f0f0f0);
}

.trace-time {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.policy-results {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color, #e0e0e0);
}

.policy-results h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
}

.results-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.05);
  font-size: 13px;
}

.result-item.failed {
  background: rgba(239, 68, 68, 0.05);
}

.result-icon {
  font-size: 16px;
}

.result-trace {
  font-family: monospace;
  font-weight: 600;
}

.result-message {
  flex: 1;
  color: var(--text-secondary, #666);
}

.modal-large {
  max-width: 800px;
}

/* Reuse modal styles from DatasetList */
.btn-primary,
.btn-secondary,
.btn-icon,
.btn-close,
.modal-overlay,
.modal-content,
.modal-header,
.modal-body,
.modal-footer,
.form-group,
.form-input,
.form-textarea,
.empty-state {
  /* Styles inherited from DatasetList */
}
</style>