<template>
  <div class="dataset-list">
    <div class="list-header">
      <h2>Datasets</h2>
      <button @click="showCreateModal = true" class="btn-primary">
        + New Dataset
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <p>Loading datasets...</p>
    </div>

    <div v-else-if="datasets.length === 0" class="empty-state">
      <p>No datasets yet</p>
      <button @click="showCreateModal = true" class="btn-primary">
        Create Your First Dataset
      </button>
    </div>

    <div v-else class="dataset-grid">
      <div
        v-for="dataset in datasets"
        :key="dataset.id"
        class="dataset-card"
        @click="$emit('select', dataset.id)"
      >
        <div class="card-header">
          <h3>{{ dataset.name }}</h3>
          <span v-if="dataset.is_public" class="public-badge">Public</span>
        </div>

        <p v-if="dataset.description" class="card-description">
          {{ dataset.description }}
        </p>

        <div class="card-stats">
          <span class="stat">
            <span class="stat-icon">📊</span>
            {{ dataset.traces?.length || 0 }} traces
          </span>
          <span class="stat">
            <span class="stat-icon">📋</span>
            {{ dataset.policies?.length || 0 }} policies
          </span>
        </div>

        <div class="card-footer">
          <span class="timestamp">
            {{ formatDate(dataset.created_at) }}
          </span>
          <div class="card-actions" @click.stop>
            <button @click="editDataset(dataset)" class="btn-icon" title="Edit">
              ✏️
            </button>
            <button @click="deleteDataset(dataset.id)" class="btn-icon" title="Delete">
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <div v-if="showCreateModal || editingDataset" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingDataset ? 'Edit Dataset' : 'Create Dataset' }}</h3>
          <button @click="closeModal" class="btn-close">×</button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>Name *</label>
            <input
              v-model="formData.name"
              type="text"
              placeholder="My Dataset"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label>Description</label>
            <textarea
              v-model="formData.description"
              placeholder="Optional description"
              class="form-textarea"
              rows="3"
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input v-model="formData.is_public" type="checkbox" />
              <span>Make this dataset public</span>
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeModal" class="btn-secondary">Cancel</button>
          <button @click="saveDataset" class="btn-primary" :disabled="!formData.name">
            {{ editingDataset ? 'Save Changes' : 'Create Dataset' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

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

const emit = defineEmits<{
  select: [id: string]
  refresh: []
}>()

// State
const datasets = ref<Dataset[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const editingDataset = ref<Dataset | null>(null)
const formData = ref({
  name: '',
  description: '',
  is_public: false,
})

// Methods
async function loadDatasets() {
  loading.value = true
  try {
    const response = await fetch('/api/v1/dataset')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const data = await response.json()
    datasets.value = data.datasets || []
  } catch (error) {
    console.error('Failed to load datasets:', error)
    alert('Failed to load datasets')
  } finally {
    loading.value = false
  }
}

async function saveDataset() {
  if (!formData.value.name) {
    return
  }

  try {
    const url = editingDataset.value
      ? `/api/v1/dataset/${editingDataset.value.id}`
      : '/api/v1/dataset'
    const method = editingDataset.value ? 'PUT' : 'POST'

    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData.value),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    closeModal()
    await loadDatasets()
    emit('refresh')
  } catch (error) {
    console.error('Failed to save dataset:', error)
    alert('Failed to save dataset')
  }
}

function editDataset(dataset: Dataset) {
  editingDataset.value = dataset
  formData.value = {
    name: dataset.name,
    description: dataset.description,
    is_public: dataset.is_public,
  }
}

async function deleteDataset(id: string) {
  if (!confirm('Are you sure you want to delete this dataset?')) {
    return
  }

  try {
    const response = await fetch(`/api/v1/dataset/${id}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    await loadDatasets()
    emit('refresh')
  } catch (error) {
    console.error('Failed to delete dataset:', error)
    alert('Failed to delete dataset')
  }
}

function closeModal() {
  showCreateModal.value = false
  editingDataset.value = null
  formData.value = {
    name: '',
    description: '',
    is_public: false,
  }
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
  loadDatasets()
})
</script>

<style scoped>
.dataset-list {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.list-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.btn-primary,
.btn-secondary {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--primary-color, #007bff);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover, #0056b3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  color: var(--text-primary, #333);
  border: 1px solid var(--border-color, #e0e0e0);
}

.btn-secondary:hover {
  background: var(--bg-hover, #e8e8e8);
}

.btn-icon {
  padding: 4px 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 16px;
  transition: transform 0.2s;
}

.btn-icon:hover {
  transform: scale(1.1);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-secondary, #666);
  text-align: center;
}

.empty-state button {
  margin-top: 16px;
}

.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.dataset-card {
  padding: 20px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  background: var(--bg-primary, #ffffff);
  cursor: pointer;
  transition: all 0.2s;
}

.dataset-card:hover {
  border-color: var(--primary-color, #007bff);
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.1);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.public-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.card-description {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: var(--text-secondary, #666);
  line-height: 1.5;
}

.card-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-light, #f0f0f0);
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary, #666);
}

.stat-icon {
  font-size: 16px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border-light, #f0f0f0);
}

.timestamp {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.card-actions {
  display: flex;
  gap: 4px;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-primary, #ffffff);
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0;
  width: 32px;
  height: 32px;
  line-height: 1;
}

.btn-close:hover {
  color: var(--text-primary, #333);
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #333);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary-color, #007bff);
}

.form-textarea {
  resize: vertical;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid var(--border-color, #e0e0e0);
}
</style>