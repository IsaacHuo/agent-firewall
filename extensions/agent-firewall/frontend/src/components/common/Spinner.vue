<template>
  <div class="spinner-container" :class="containerClass">
    <div class="spinner" :class="spinnerClass" :style="spinnerStyle">
      <svg viewBox="0 0 50 50">
        <circle
          class="spinner-track"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          stroke-width="4"
        />
        <circle
          class="spinner-path"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          stroke-width="4"
        />
      </svg>
    </div>
    <div v-if="text" class="spinner-text">{{ text }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  color?: string
  text?: string
  fullscreen?: boolean
  overlay?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md'
})

const containerClass = computed(() => ({
  'spinner-fullscreen': props.fullscreen,
  'spinner-overlay': props.overlay
}))

const spinnerClass = computed(() => `spinner-${props.size}`)

const spinnerStyle = computed(() => {
  if (props.color) {
    return {
      '--spinner-color': props.color
    }
  }
  return {}
})
</script>

<style scoped>
.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.spinner-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9998;
  background: var(--bg-primary);
}

.spinner-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9998;
  background: var(--overlay-bg);
  backdrop-filter: var(--backdrop-blur);
}

.spinner {
  --spinner-color: var(--accent);
  animation: rotate 1.4s linear infinite;
}

.spinner-sm {
  width: 20px;
  height: 20px;
}

.spinner-md {
  width: 32px;
  height: 32px;
}

.spinner-lg {
  width: 48px;
  height: 48px;
}

.spinner-xl {
  width: 64px;
  height: 64px;
}

.spinner svg {
  width: 100%;
  height: 100%;
}

.spinner-track {
  stroke: var(--border);
  opacity: 0.3;
}

.spinner-path {
  stroke: var(--spinner-color);
  stroke-linecap: round;
  stroke-dasharray: 90, 150;
  stroke-dashoffset: 0;
  animation: dash 1.4s ease-in-out infinite;
}

.spinner-text {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

@keyframes rotate {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}
</style>
