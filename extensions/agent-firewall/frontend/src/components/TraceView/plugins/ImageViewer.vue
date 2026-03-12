<template>
  <div class="image-viewer">
    <img
      :src="url"
      :alt="alt"
      @click="toggleFullscreen"
      @error="handleError"
      :class="{ fullscreen: isFullscreen, error: hasError }"
    />
    <div v-if="hasError" class="error-message">
      Failed to load image
    </div>
    <div v-if="isFullscreen" class="fullscreen-overlay" @click="toggleFullscreen">
      <img :src="url" :alt="alt" class="fullscreen-image" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  url: string
  alt?: string
}

const props = withDefaults(defineProps<Props>(), {
  alt: 'Image',
})

const isFullscreen = ref(false)
const hasError = ref(false)

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

function handleError() {
  hasError.value = true
}
</script>

<style scoped>
.image-viewer {
  position: relative;
  display: inline-block;
  max-width: 100%;
}

.image-viewer img {
  max-width: 300px;
  max-height: 300px;
  border-radius: 4px;
  border: 1px solid var(--border-color, #e0e0e0);
  cursor: pointer;
  transition: all 0.2s;
  object-fit: contain;
}

.image-viewer img:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  transform: scale(1.02);
}

.image-viewer img.error {
  opacity: 0.3;
  cursor: not-allowed;
}

.error-message {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--error-color, #dc3545);
  font-size: 12px;
  font-weight: 500;
  text-align: center;
  pointer-events: none;
}

.fullscreen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: pointer;
}

.fullscreen-image {
  max-width: 90vw;
  max-height: 90vh;
  border: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}
</style>