<template>
  <div class="rate-limit-page">
    <div class="page-header">
      <h2>Rate Limiting</h2>
      <p class="subtitle">Token-bucket rate limiter to prevent abuse and DoS attacks</p>
    </div>

    <div class="rl-grid">
      <!-- Current Config -->
      <div class="rl-card">
        <div class="card-header">
          <h3>Configuration</h3>
        </div>
        <div class="card-body">
          <div class="form-group">
            <label>Requests per Second</label>
            <div class="range-group">
              <input
                type="range"
                v-model.number="localRps"
                min="1"
                max="1000"
                step="1"
                class="range-input"
              />
              <input v-model.number="localRps" type="number" class="form-input-sm" />
            </div>
          </div>
          <div class="form-group">
            <label>Burst Size</label>
            <div class="range-group">
              <input
                type="range"
                v-model.number="localBurst"
                min="1"
                max="2000"
                step="10"
                class="range-input"
              />
              <input v-model.number="localBurst" type="number" class="form-input-sm" />
            </div>
            <span class="form-hint">Maximum concurrent requests allowed in a burst window</span>
          </div>
          <button class="btn-primary" @click="saveRateLimit" :disabled="!hasChanges">
            Apply Changes
          </button>
        </div>
      </div>

      <!-- Visualization -->
      <div class="rl-card">
        <div class="card-header">
          <h3>Token Bucket Visualization</h3>
        </div>
        <div class="card-body">
          <div class="bucket-viz">
            <div class="bucket">
              <div class="bucket-fill" :style="{ height: bucketFillPercent + '%' }"></div>
              <div class="bucket-label">{{ Math.round(bucketFillPercent) }}%</div>
            </div>
            <div class="bucket-info">
              <div class="info-row">
                <span class="info-label">Capacity</span>
                <span class="info-value">{{ localBurst }} tokens</span>
              </div>
              <div class="info-row">
                <span class="info-label">Refill Rate</span>
                <span class="info-value">{{ localRps }} tokens/sec</span>
              </div>
              <div class="info-row">
                <span class="info-label">Full Refill Time</span>
                <span class="info-value">{{ (localBurst / localRps).toFixed(1) }}s</span>
              </div>
            </div>
          </div>

          <div class="scenarios">
            <h4>Impact Scenarios</h4>
            <div class="scenario" v-for="s in scenarios" :key="s.label">
              <span class="scenario-label">{{ s.label }}</span>
              <span class="scenario-value" :class="s.status">{{ s.result }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RateLimitConfig } from '../types'

const props = defineProps<{
  config: RateLimitConfig
}>()

const emit = defineEmits<{
  save: [config: RateLimitConfig]
}>()

const localRps = ref(props.config.requests_per_sec)
const localBurst = ref(props.config.burst)

const hasChanges = computed(() =>
  localRps.value !== props.config.requests_per_sec ||
  localBurst.value !== props.config.burst
)

const bucketFillPercent = ref(75)

// Simulated refill animation
setInterval(() => {
  bucketFillPercent.value = Math.min(100, bucketFillPercent.value + 2)
}, 500)

const scenarios = computed(() => [
  {
    label: 'Normal agent (10 req/s)',
    result: localRps.value >= 10 ? '✓ Allowed' : '✕ Throttled',
    status: localRps.value >= 10 ? 'ok' : 'error',
  },
  {
    label: 'Rapid bursting (50 req in 1s)',
    result: localBurst.value >= 50 ? '✓ Absorbed' : `✕ ${50 - localBurst.value} dropped`,
    status: localBurst.value >= 50 ? 'ok' : 'warn',
  },
  {
    label: 'DoS attempt (500 req/s)',
    result: `${Math.max(0, 500 - localRps.value)} req/s blocked`,
    status: 'ok',
  },
  {
    label: 'Sustained load (100 req/s)',
    result: localRps.value >= 100 ? '✓ Within limits' : `${100 - localRps.value} excess/s`,
    status: localRps.value >= 100 ? 'ok' : 'warn',
  },
])

function saveRateLimit() {
  emit('save', {
    requests_per_sec: localRps.value,
    burst: localBurst.value,
  })
}
</script>

<style scoped>
.rate-limit-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 24px; font-weight: 600; color: #fff; margin: 0 0 4px; }
.subtitle { color: #666; font-size: 14px; margin: 0; }

.rl-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.rl-card {
  background: #141428;
  border: 1px solid #2a2a3e;
  border-radius: 12px;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.card-header h3 { font-size: 15px; font-weight: 600; color: #ccc; margin: 0; }
.card-body { padding: 20px; }

.form-group { margin-bottom: 20px; }
.form-group label { display: block; font-size: 13px; color: #888; margin-bottom: 8px; }
.form-hint { font-size: 11px; color: #555; margin-top: 6px; display: block; }

.range-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.range-input {
  flex: 1;
  -webkit-appearance: none;
  height: 6px;
  background: #2a2a3e;
  border-radius: 3px;
  outline: none;
}

.range-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e94560;
  cursor: pointer;
  border: 2px solid #fff;
}

.form-input-sm {
  width: 80px;
  background: #0a0a12;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  color: #ccc;
  padding: 6px 10px;
  font-size: 13px;
  text-align: center;
}

.form-input-sm:focus {
  outline: none;
  border-color: #4488ff;
}

.btn-primary {
  padding: 10px 24px;
  background: linear-gradient(135deg, #e94560 0%, #c73450 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Bucket Visualization */
.bucket-viz {
  display: flex;
  gap: 24px;
  align-items: center;
  margin-bottom: 24px;
}

.bucket {
  width: 80px;
  height: 140px;
  border: 2px solid #4488ff;
  border-radius: 0 0 16px 16px;
  border-top: none;
  position: relative;
  overflow: hidden;
}

.bucket::before {
  content: '';
  position: absolute;
  top: -4px;
  left: -6px;
  right: -6px;
  height: 4px;
  background: #4488ff;
  border-radius: 2px;
}

.bucket-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, rgba(68, 136, 255, 0.6) 0%, rgba(68, 136, 255, 0.3) 100%);
  transition: height 0.5s ease;
}

.bucket-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  z-index: 1;
}

.bucket-info { flex: 1; }

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #1a1a2e;
}

.info-label { color: #666; font-size: 13px; }
.info-value { color: #ccc; font-size: 13px; font-weight: 500; }

.scenarios h4 {
  font-size: 13px;
  color: #888;
  margin: 0 0 12px;
}

.scenario {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 6px;
  margin-bottom: 6px;
}

.scenario-label { font-size: 12px; color: #888; }
.scenario-value { font-size: 12px; font-weight: 600; }
.scenario-value.ok { color: #00ff88; }
.scenario-value.warn { color: #ffaa00; }
.scenario-value.error { color: #ff4444; }

@media (max-width: 1200px) {
  .rl-grid { grid-template-columns: 1fr; }
}
</style>
