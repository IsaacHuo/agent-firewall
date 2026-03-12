<template>
  <div
    class="trace-line"
    :class="{
      expanded,
      selected,
      'has-tool-calls': hasToolCalls,
      [`role-${message.role}`]: true
    }"
    @click="handleClick"
  >
    <!-- Line Header -->
    <div class="trace-line-header">
      <button class="expand-toggle" @click.stop="$emit('toggle')">
        {{ expanded ? '▼' : '▶' }}
      </button>

      <div class="role-icon">
        {{ getRoleIcon(message.role) }}
      </div>

      <div class="role-label">
        {{ message.role }}
      </div>

      <div class="message-index">
        #{{ index }}
      </div>

      <div v-if="hasToolCalls" class="tool-calls-badge">
        {{ message.tool_calls?.length }} tool call(s)
      </div>

      <div v-if="message.tool_call_id" class="tool-call-id-badge">
        ↩ {{ message.tool_call_id }}
      </div>

      <!-- Annotations Badge -->
      <div v-if="messageAnnotations.length > 0" class="annotations-badge">
        📝 {{ messageAnnotations.length }} annotation(s)
      </div>
    </div>

    <!-- Line Content (when expanded) -->
    <div v-if="expanded" class="trace-line-content">
      <!-- Text Content -->
      <div v-if="contentText" class="content-text" @mouseup="handleTextSelection">
        <CodeHighlighter
          :content="contentText"
          :highlights="highlights"
          :address="`messages[${index}].content`"
        />
      </div>

      <!-- Image Content -->
      <div v-if="contentImages.length > 0" class="content-images">
        <ImageViewer
          v-for="(img, imgIndex) in contentImages"
          :key="imgIndex"
          :url="img.image_url.url"
        />
      </div>

      <!-- Tool Calls -->
      <div v-if="hasToolCalls" class="tool-calls">
        <div
          v-for="(toolCall, tcIndex) in message.tool_calls"
          :key="tcIndex"
          class="tool-call"
        >
          <div class="tool-call-header">
            <span class="tool-call-name">🔧 {{ toolCall.function.name }}</span>
            <span class="tool-call-id">ID: {{ toolCall.id }}</span>
          </div>
          <div class="tool-call-args">
            <CodeHighlighter
              :content="JSON.stringify(toolCall.function.arguments, null, 2)"
              language="json"
              :address="`messages[${index}].tool_calls[${tcIndex}].function.arguments`"
            />
          </div>
        </div>
      </div>

      <!-- Annotations Section -->
      <div v-if="messageAnnotations.length > 0" class="annotations-section">
        <div class="annotations-header">
          <span class="annotations-title">📝 Annotations</span>
        </div>
        <div
          v-for="annotation in messageAnnotations"
          :key="annotation.id"
          class="annotation-item"
          :class="`severity-${annotation.severity}`"
        >
          <div class="annotation-header">
            <span class="annotation-icon">{{ getSeverityIcon(annotation.severity) }}</span>
            <span class="annotation-severity">{{ annotation.severity }}</span>
            <span class="annotation-source">{{ annotation.source }}</span>
            <span class="annotation-time">{{ new Date(annotation.created_at).toLocaleString() }}</span>
          </div>
          <div class="annotation-content">
            {{ annotation.content }}
          </div>
          <div class="annotation-address">
            <code>{{ annotation.address }}</code>
          </div>
        </div>
      </div>
    </div>

    <!-- Highlights Indicator -->
    <div v-if="highlights.length > 0 && !expanded" class="highlights-indicator">
      <span
        v-for="(highlight, hIndex) in highlights.slice(0, 3)"
        :key="hIndex"
        class="highlight-dot"
        :style="{ backgroundColor: highlight.color }"
      />
      <span v-if="highlights.length > 3" class="highlight-more">
        +{{ highlights.length - 3 }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CodeHighlighter from './plugins/CodeHighlighter.vue'
import ImageViewer from './plugins/ImageViewer.vue'

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
  message: Message
  index: number
  expanded: boolean
  selected: boolean
  highlights: Highlight[]
  annotations?: Annotation[]
}

const props = withDefaults(defineProps<Props>(), {
  annotations: () => []
})

const emit = defineEmits<{
  toggle: []
  select: []
  annotate: [address: string, selection: string]
}>()

// Computed
const hasToolCalls = computed(() => {
  return props.message.tool_calls && props.message.tool_calls.length > 0
})

const messageAnnotations = computed(() => {
  return props.annotations.filter(ann =>
    ann.address.startsWith(`messages[${props.index}]`)
  )
})

const contentText = computed(() => {
  if (typeof props.message.content === 'string') {
    return props.message.content
  }
  if (Array.isArray(props.message.content)) {
    const textChunks = props.message.content.filter(c => c.type === 'text')
    return textChunks.map(c => c.text).join('\n')
  }
  return null
})

const contentImages = computed(() => {
  if (Array.isArray(props.message.content)) {
    return props.message.content.filter(c => c.type === 'image_url')
  }
  return []
})

// Methods
function getRoleIcon(role: string): string {
  const icons: Record<string, string> = {
    user: '👤',
    assistant: '🤖',
    system: '⚙️',
    tool: '🔧',
    function: '⚡'
  }
  return icons[role] || '💬'
}

function handleClick() {
  emit('select')
}

function handleTextSelection() {
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    const selectedText = selection.toString()
    const address = `messages[${props.index}].content`
    emit('annotate', address, selectedText)
  }
}

function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    info: '#3b82f6',
    warning: '#f59e0b',
    error: '#ef4444'
  }
  return colors[severity] || '#6b7280'
}

function getSeverityIcon(severity: string): string {
  const icons: Record<string, string> = {
    info: 'ℹ️',
    warning: '⚠️',
    error: '❌'
  }
  return icons[severity] || '📝'
}
</script>

<style scoped>
.trace-line {
  margin-bottom: 8px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  background: var(--bg-primary, #ffffff);
  transition: all 0.2s;
  cursor: pointer;
}

.trace-line:hover {
  border-color: var(--border-hover, #999);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.trace-line.selected {
  border-color: var(--primary-color, #007bff);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.1);
}

.trace-line-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  user-select: none;
}

.expand-toggle {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 4px;
  color: var(--text-secondary, #666);
  transition: transform 0.2s;
}

.expanded .expand-toggle {
  transform: rotate(0deg);
}

.role-icon {
  font-size: 18px;
}

.role-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #333);
  text-transform: capitalize;
}

.message-index {
  font-size: 12px;
  color: var(--text-secondary, #666);
  font-family: monospace;
}

.tool-calls-badge,
.tool-call-id-badge,
.annotations-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background: var(--badge-bg, #e8f4f8);
  color: var(--badge-text, #0066cc);
}

.tool-call-id-badge {
  background: var(--badge-bg-alt, #f0f0f0);
  color: var(--text-secondary, #666);
  font-family: monospace;
}

.annotations-badge {
  background: #fef3c7;
  color: #92400e;
}

.trace-line-content {
  padding: 0 12px 12px 40px;
  border-top: 1px solid var(--border-light, #f0f0f0);
}

.content-text {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-code, #f8f8f8);
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.content-images {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.tool-calls {
  margin-top: 12px;
}

.tool-call {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 4px;
  border-left: 3px solid var(--primary-color, #007bff);
}

.tool-call-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.tool-call-name {
  font-weight: 600;
  color: var(--text-primary, #333);
}

.tool-call-id {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-secondary, #666);
}

.tool-call-args {
  font-size: 12px;
}

.highlights-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 12px 8px 40px;
}

.highlight-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.highlight-more {
  font-size: 11px;
  color: var(--text-secondary, #666);
  margin-left: 4px;
}

/* Role-specific styling */
.role-user .trace-line-header {
  background: linear-gradient(to right, rgba(59, 130, 246, 0.05), transparent);
}

.role-assistant .trace-line-header {
  background: linear-gradient(to right, rgba(16, 185, 129, 0.05), transparent);
}

.role-system .trace-line-header {
  background: linear-gradient(to right, rgba(245, 158, 11, 0.05), transparent);
}

.role-tool .trace-line-header {
  background: linear-gradient(to right, rgba(139, 92, 246, 0.05), transparent);
}

/* Annotations Section */
.annotations-section {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 4px;
  border-left: 3px solid #f59e0b;
}

.annotations-header {
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.annotations-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.annotation-item {
  margin-bottom: 12px;
  padding: 10px;
  background: var(--bg-primary, #ffffff);
  border-radius: 4px;
  border-left: 3px solid #6b7280;
}

.annotation-item:last-child {
  margin-bottom: 0;
}

.annotation-item.severity-info {
  border-left-color: #3b82f6;
}

.annotation-item.severity-warning {
  border-left-color: #f59e0b;
}

.annotation-item.severity-error {
  border-left-color: #ef4444;
}

.annotation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}

.annotation-icon {
  font-size: 14px;
}

.annotation-severity {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-secondary, #f5f5f5);
}

.annotation-source {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-secondary, #666);
  padding: 2px 6px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 4px;
}

.annotation-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-secondary, #666);
}

.annotation-content {
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-primary, #333);
  white-space: pre-wrap;
  word-break: break-word;
}

.annotation-address {
  font-size: 11px;
  color: var(--text-secondary, #666);
}

.annotation-address code {
  font-family: monospace;
  background: var(--bg-code, #f8f8f8);
  padding: 2px 6px;
  border-radius: 3px;
}

.content-text {
  cursor: text;
  user-select: text;
}
</style>