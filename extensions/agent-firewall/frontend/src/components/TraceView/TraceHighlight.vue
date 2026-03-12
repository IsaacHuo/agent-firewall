<template>
  <div class="trace-highlight" :class="[`severity-${severity}`]">
    <div class="highlight-header">
      <span class="highlight-source">{{ source }}</span>
      <span class="highlight-severity">{{ severity }}</span>
      <span class="highlight-address" :title="address">{{ shortAddress }}</span>
    </div>
    <div class="highlight-content">
      {{ content }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  address: string
  content: string
  severity: 'info' | 'warning' | 'error'
  source: string
}

const props = defineProps<Props>()

const shortAddress = computed(() => {
  const parts = props.address.split('.')
  if (parts.length > 2) {
    return `...${parts.slice(-2).join('.')}`
  }
  return props.address
})
</script>

<style scoped>
.trace-highlight {
  padding: 8px 12px;
  border-radius: 4px;
  margin: 4px 0;
  font-size: 13px;
  border-left: 3px solid;
}

.severity-info {
  background: rgba(59, 130, 246, 0.08);
  border-left-color: #3b82f6;
}

.severity-warning {
  background: rgba(245, 158, 11, 0.08);
  border-left-color: #f59e0b;
}

.severity-error {
  background: rgba(239, 68, 68, 0.08);
  border-left-color: #ef4444;
}

.highlight-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.highlight-source {
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-secondary, #666);
}

.highlight-severity {
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}

.severity-info .highlight-severity {
  background: #3b82f6;
  color: white;
}

.severity-warning .highlight-severity {
  background: #f59e0b;
  color: white;
}

.severity-error .highlight-severity {
  background: #ef4444;
  color: white;
}

.highlight-address {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-secondary, #666);
  margin-left: auto;
}

.highlight-content {
  color: var(--text-primary, #333);
  line-height: 1.5;
}
</style>