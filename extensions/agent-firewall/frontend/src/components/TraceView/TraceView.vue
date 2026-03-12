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
          @toggle="toggleMessage(index)"
          @select="selectMessage(index)"
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
}>()

// State
const messages = computed(() => props.trace)
const expandedMessages = ref<Set<number>>(new Set())
const selectedMessageIndex = ref<number | null>(null)
const allExpanded = ref(false)
const showEditor = ref(props.editor)
const editableTrace = ref(JSON.stringify(props.trace, null, 2))
const messagesContainer = ref<HTMLElement | null>(null)

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
})
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
</style>
