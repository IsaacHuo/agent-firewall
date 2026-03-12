<template>
  <div class="trace-view" :class="{ 'side-by-side': sideBySide }">
    <!-- Header -->
    <div class="trace-view-header">
      <div class="trace-view-title">
        <slot name="title">
          <h3>{{ title || 'Trace View' }}</h3>
        </slot>
      </div>
      <div class="trace-view-actions">
        <button @click="toggleExpandAll" class="btn-icon" :title="allExpanded ? 'Collapse All' : 'Expand All'">
          {{ allExpanded ? '▼' : '▶' }}
        </button>
        <button @click="copyPermalink" class="btn-icon" title="Copy Permalink">
          🔗
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="trace-view-content">
      <!-- Trace Messages -->
      <div class="trace-view-messages" ref="messagesContainer">
        <TraceLine
          v-for="(message, index) in messages"
          :key="index"
          :message="message"
          :index="index"
          :expanded="expandedMessages.has(index)"
          :selected="selectedMessageIndex === index"
          :highlights="getHighlightsForMessage(index)"
          :annotations="annotations"
          @toggle="toggleMessage(index)"
          @select="selectMessage(index)"
          @annotate="handleAnnotate"
        />
      </div>

      <!-- Side Editor (if sideBySide) -->
      <div v-if="sideBySide && showEditor" class="trace-view-editor">
        <div class="editor-header">
          <span>JSON Editor</span>
          <button @click="showEditor = false" class="btn-close">×</button>
        </div>
        <textarea
          v-model="editableTrace"
          class="editor-textarea"
          @input="handleTraceEdit"
        />
      </div>
    </div>

    <!-- Annotation Modal -->
    <div v-if="showAnnotationModal" class="modal-overlay" @click="showAnnotationModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Annotation</h3>
          <button @click="showAnnotationModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="pendingAnnotation" class="selected-text">
            <strong>Selected text:</strong>
            <pre>{{ pendingAnnotation.selection }}</pre>
          </div>
          <div class="form-group">
            <label>Severity</label>
            <select v-model="annotationSeverity" class="form-select">
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </div>
          <div class="form-group">
            <label>Comment</label>
            <textarea
              v-model="annotationContent"
              class="form-textarea"
              placeholder="Add your comment..."
              rows="4"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showAnnotationModal = false" class="btn-secondary">Cancel</button>
          <button @click="submitAnnotation(annotationSeverity, annotationContent)" class="btn-primary">
            Add Annotation
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import TraceLine from './TraceLine.vue'

interface Message {
  role: string
  content: string | null | Array<{ type: string; text?: string; image_url?: { url: string } }>
  tool_calls?: Array<{
    id: string | number
    type: string
    function: { name: string; arguments: any }
  }>
  tool_call_id?: string | number | null
}

interface Highlight {
  address: string
  color: string
  label?: string
}

interface Annotation {
  id: string
  address: string
  content: string
  severity: 'info' | 'warning' | 'error'
  source: string
  created_at: string
}

interface Props {
  trace: Message[]
  highlights?: Record<string, string>
  traceId?: string
  sideBySide?: boolean
  title?: string
  editor?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  highlights: () => ({}),
  sideBySide: false,
  editor: true,
})

const emit = defineEmits<{
  'update:trace': [trace: Message[]]
  'select-message': [index: number]
  'add-annotation': [address: string, content: string, severity: string]
}>()

// State
const messages = computed(() => props.trace)
const expandedMessages = ref<Set<number>>(new Set())
const selectedMessageIndex = ref<number | null>(null)
const allExpanded = ref(false)
const showEditor = ref(props.editor)
const editableTrace = ref(JSON.stringify(props.trace, null, 2))
const messagesContainer = ref<HTMLElement | null>(null)
const annotations = ref<Annotation[]>([])
const showAnnotationModal = ref(false)
const pendingAnnotation = ref<{ address: string; selection: string } | null>(null)
const annotationSeverity = ref<'info' | 'warning' | 'error'>('info')
const annotationContent = ref('')

// Watch for trace changes
watch(() => props.trace, (newTrace) => {
  editableTrace.value = JSON.stringify(newTrace, null, 2)
}, { deep: true })

// Methods
function toggleMessage(index: number) {
  if (expandedMessages.value.has(index)) {
    expandedMessages.value.delete(index)
  } else {
    expandedMessages.value.add(index)
  }
}

function selectMessage(index: number) {
  selectedMessageIndex.value = index
  emit('select-message', index)
}

function toggleExpandAll() {
  if (allExpanded.value) {
    expandedMessages.value.clear()
  } else {
    messages.value.forEach((_, index) => {
      expandedMessages.value.add(index)
    })
  }
  allExpanded.value = !allExpanded.value
}

function copyPermalink() {
  const url = new URL(window.location.href)
  if (props.traceId) {
    url.searchParams.set('trace', props.traceId)
  }
  if (selectedMessageIndex.value !== null) {
    url.hash = `#message-${selectedMessageIndex.value}`
  }
  navigator.clipboard.writeText(url.toString())
}

function getHighlightsForMessage(index: number): Highlight[] {
  const highlights: Highlight[] = []
  for (const [address, color] of Object.entries(props.highlights)) {
    if (address.startsWith(`messages[${index}]`) || address.startsWith(`/${index}`)) {
      highlights.push({ address, color })
    }
  }
  return highlights
}

function handleTraceEdit() {
  try {
    const parsed = JSON.parse(editableTrace.value)
    emit('update:trace', parsed)
  } catch (e) {
    // Invalid JSON, don't update
  }
}

// Lifecycle
onMounted(() => {
  // Auto-expand first message
  if (messages.value.length > 0) {
    expandedMessages.value.add(0)
  }

  // Fetch annotations if traceId is provided
  if (props.traceId) {
    fetchAnnotations()
  }
})

// Fetch annotations
async function fetchAnnotations() {
  if (!props.traceId) return

  try {
    const response = await fetch(`/api/v1/trace/${props.traceId}/annotations`)
    if (response.ok) {
      annotations.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to fetch annotations:', error)
  }
}

// Handle annotation creation
function handleAnnotate(address: string, selection: string) {
  pendingAnnotation.value = { address, selection }
  showAnnotationModal.value = true
}

async function submitAnnotation(severity: string, content: string) {
  if (!props.traceId || !pendingAnnotation.value) return

  try {
    const response = await fetch(`/api/v1/trace/${props.traceId}/annotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address: pendingAnnotation.value.address,
        content,
        severity
      })
    })

    if (response.ok) {
      const newAnnotation = await response.json()
      annotations.value.push(newAnnotation)
      showAnnotationModal.value = false
      pendingAnnotation.value = null
    }
  } catch (error) {
    console.error('Failed to create annotation:', error)
  }
}
</script>

<style scoped>
.trace-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #ffffff);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  overflow: hidden;
}

.trace-view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f5f5f5);
}

.trace-view-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.trace-view-actions {
  display: flex;
  gap: 8px;
}

.btn-icon {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: var(--bg-hover, #e8e8e8);
}

.trace-view-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.trace-view-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.side-by-side .trace-view-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border-color, #e0e0e0);
}

.trace-view-editor {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary, #ffffff);
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f5f5f5);
  font-weight: 600;
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary, #666);
  padding: 0;
  width: 24px;
  height: 24px;
  line-height: 1;
}

.btn-close:hover {
  color: var(--text-primary, #333);
}

.editor-textarea {
  flex: 1;
  padding: 16px;
  border: none;
  font-family: "Monaco", "Menlo", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  background: var(--bg-code, #f8f8f8);
  color: var(--text-primary, #333);
}

.editor-textarea:focus {
  outline: none;
}

/* Annotation Modal */
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
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.modal-body {
  padding: 20px;
}

.selected-text {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-code, #f8f8f8);
  border-radius: 4px;
  border-left: 3px solid var(--primary-color, #007bff);
}

.selected-text strong {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary, #666);
}

.selected-text pre {
  margin: 0;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary, #333);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #333);
}

.form-select,
.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  background: var(--bg-primary, #ffffff);
  color: var(--text-primary, #333);
}

.form-select:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary-color, #007bff);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.1);
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color, #e0e0e0);
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--primary-color, #007bff);
  color: white;
}

.btn-primary:hover {
  background: #0056b3;
}

.btn-secondary {
  background: var(--bg-secondary, #f5f5f5);
  color: var(--text-primary, #333);
}

.btn-secondary:hover {
  background: #e8e8e8;
}
</style>
