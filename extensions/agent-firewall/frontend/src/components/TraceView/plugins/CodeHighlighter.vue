<template>
  <div class="code-highlighter" :class="{ highlighted: hasHighlights }">
    <pre><code :class="`language-${language}`">{{ formattedContent }}</code></pre>
    <div v-if="hasHighlights" class="highlight-markers">
      <span
        v-for="(highlight, index) in highlights"
        :key="index"
        class="highlight-marker"
        :style="{ backgroundColor: highlight.color }"
        :title="highlight.label || highlight.address"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Highlight {
  address: string
  color: string
  label?: string
}

interface Props {
  content: string
  language?: string
  highlights?: Highlight[]
  address?: string
}

const props = withDefaults(defineProps<Props>(), {
  language: 'text',
  highlights: () => [],
})

const hasHighlights = computed(() => {
  return props.highlights.length > 0
})

const formattedContent = computed(() => {
  // Basic formatting - could be enhanced with syntax highlighting library
  return props.content
})
</script>

<style scoped>
.code-highlighter {
  position: relative;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.code-highlighter pre {
  margin: 0;
  padding: 0;
  overflow-x: auto;
}

.code-highlighter code {
  display: block;
  white-space: pre;
  color: var(--text-primary, #333);
}

.code-highlighter.highlighted {
  background: rgba(255, 235, 59, 0.1);
  border-left: 3px solid #ffc107;
  padding-left: 8px;
}

.highlight-markers {
  position: absolute;
  top: 4px;
  right: 4px;
  display: flex;
  gap: 4px;
}

.highlight-marker {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.1);
  cursor: help;
}

/* Language-specific styling */
.language-json {
  color: #0066cc;
}

.language-python {
  color: #306998;
}

.language-javascript {
  color: #f7df1e;
}
</style>