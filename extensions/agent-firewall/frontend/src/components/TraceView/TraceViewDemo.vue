<template>
  <div class="trace-demo">
    <h1>TraceView Demo</h1>

    <div class="demo-controls">
      <button @click="loadSampleTrace">Load Sample Trace</button>
      <button @click="toggleSideBySide">Toggle Side-by-Side</button>
      <button @click="addHighlight">Add Random Highlight</button>
      <button @click="clearHighlights">Clear Highlights</button>
    </div>

    <div class="demo-content">
      <TraceView
        v-if="trace.length > 0"
        :trace="trace"
        :highlights="highlights"
        :trace-id="traceId"
        :side-by-side="sideBySide"
        title="Sample Agent Trace"
        @update:trace="handleTraceUpdate"
        @select-message="handleMessageSelect"
      />
      <div v-else class="empty-state">
        <p>No trace loaded. Click "Load Sample Trace" to get started.</p>
      </div>
    </div>

    <div class="demo-info">
      <h3>Selected Message</h3>
      <pre v-if="selectedMessage">{{ JSON.stringify(selectedMessage, null, 2) }}</pre>
      <p v-else>No message selected</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { TraceView } from './index'
import type { TraceMessage } from './types'

const trace = ref<TraceMessage[]>([])
const highlights = ref<Record<string, string>>({})
const traceId = ref('demo-trace-001')
const sideBySide = ref(false)
const selectedMessageIndex = ref<number | null>(null)

const selectedMessage = computed(() => {
  if (selectedMessageIndex.value !== null) {
    return trace.value[selectedMessageIndex.value]
  }
  return null
})

function loadSampleTrace() {
  trace.value = [
    {
      role: 'system',
      content: 'You are a helpful AI assistant with access to various tools.',
    },
    {
      role: 'user',
      content: 'Can you help me analyze this data and create a visualization?',
    },
    {
      role: 'assistant',
      content: 'I\'ll help you analyze the data and create a visualization. Let me start by reading the data file.',
      tool_calls: [
        {
          id: 'call_001',
          type: 'function',
          function: {
            name: 'read_file',
            arguments: {
              path: '/data/sample.csv',
              encoding: 'utf-8',
            },
          },
        },
      ],
    },
    {
      role: 'tool',
      content: 'name,value,category\nAlice,100,A\nBob,200,B\nCharlie,150,A',
      tool_call_id: 'call_001',
    },
    {
      role: 'assistant',
      content: 'I\'ve read the data. Now let me create a visualization using the plotting tool.',
      tool_calls: [
        {
          id: 'call_002',
          type: 'function',
          function: {
            name: 'create_plot',
            arguments: {
              data: [
                { name: 'Alice', value: 100, category: 'A' },
                { name: 'Bob', value: 200, category: 'B' },
                { name: 'Charlie', value: 150, category: 'A' },
              ],
              chart_type: 'bar',
              title: 'Sample Data Visualization',
            },
          },
        },
      ],
    },
    {
      role: 'tool',
      content: null,
      tool_call_id: 'call_002',
    },
    {
      role: 'assistant',
      content: 'I\'ve created a bar chart visualization of your data. The chart shows the values for Alice (100), Bob (200), and Charlie (150), grouped by their categories.',
    },
  ]
}

function toggleSideBySide() {
  sideBySide.value = !sideBySide.value
}

function addHighlight() {
  const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#6c5ce7']
  const randomColor = colors[Math.floor(Math.random() * colors.length)]
  const randomIndex = Math.floor(Math.random() * trace.value.length)
  const address = `messages[${randomIndex}].content`
  highlights.value[address] = randomColor
}

function clearHighlights() {
  highlights.value = {}
}

function handleTraceUpdate(newTrace: TraceMessage[]) {
  trace.value = newTrace
  console.log('Trace updated:', newTrace)
}

function handleMessageSelect(index: number) {
  selectedMessageIndex.value = index
  console.log('Message selected:', index)
}
</script>

<style scoped>
.trace-demo {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 20px;
  color: var(--text-primary, #333);
}

.demo-controls {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.demo-controls button {
  padding: 10px 16px;
  background: var(--primary-color, #007bff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.demo-controls button:hover {
  background: var(--primary-hover, #0056b3);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 123, 255, 0.3);
}

.demo-content {
  margin-bottom: 20px;
  min-height: 400px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
  border: 2px dashed var(--border-color, #e0e0e0);
  border-radius: 8px;
  color: var(--text-secondary, #666);
}

.demo-info {
  padding: 16px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
}

.demo-info h3 {
  margin-top: 0;
  margin-bottom: 12px;
  color: var(--text-primary, #333);
}

.demo-info pre {
  background: var(--bg-code, #f8f8f8);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.demo-info p {
  color: var(--text-secondary, #666);
  font-style: italic;
}
</style>