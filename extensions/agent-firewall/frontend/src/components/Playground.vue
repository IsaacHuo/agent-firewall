<template>
  <div class="playground">
    <header class="playground-header">
      <div class="header-main">
        <h2>Policy Playground</h2>
        <p class="subtitle">Test and debug your security policies against trace data</p>
      </div>
      <div class="header-actions">
        <button class="btn-evaluate" @click="evaluatePolicy" :disabled="evaluating">
          <span v-if="evaluating" class="spinner-sm"></span>
          <span v-else>▶ Evaluate Policy</span>
        </button>
      </div>
    </header>

    <div class="playground-layout">
      <!-- Left: Trace Viewer -->
      <div class="panel trace-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="icon">📜</span>
            Trace Data
          </div>
          <div class="panel-actions">
            <button class="btn-sm" @click="loadSampleTrace">Load Sample</button>
            <button class="btn-sm" @click="clearTrace">Clear</button>
          </div>
        </div>
        <div class="panel-content">
          <TraceView
            v-if="trace.length > 0"
            :trace="trace"
            :highlights="highlights"
            trace-id="playground-trace"
            @update:trace="handleTraceUpdate"
          />
          <div v-else class="empty-state">
            <div class="empty-icon">📜</div>
            <p>No trace loaded</p>
            <button @click="loadSampleTrace" class="btn-primary-sm">Load Sample Trace</button>
          </div>
        </div>
      </div>

      <!-- Middle: Policy Editor -->
      <div class="panel policy-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="icon">🛡️</span>
            Policy Rules
          </div>
          <div class="panel-actions">
            <button class="btn-sm" @click="loadSamplePolicy">Load Template</button>
          </div>
        </div>
        <div class="panel-content no-padding">
          <div class="editor-wrapper">
            <textarea
              v-model="policyCode"
              class="policy-editor"
              placeholder="# Enter your policy rules here...
raise 'High risk detected' if:
    threat_level >= 'HIGH'"
              spellcheck="false"
            />
          </div>
          <div class="policy-help-bar">
            <details>
              <summary>Syntax Reference</summary>
              <div class="help-popup">
                <h4>Variables</h4>
                <ul>
                  <li><code>threat_level</code> (LOW..CRITICAL)</li>
                  <li><code>verdict</code> (ALLOW..BLOCK)</li>
                  <li><code>tool_calls[i].function.name</code></li>
                  <li><code>l2_result.is_injection</code></li>
                </ul>
                <h4>Examples</h4>
                <pre>raise "No shell" if:
  tool_calls[0].function.name == "exec"</pre>
              </div>
            </details>
          </div>
        </div>
      </div>

      <!-- Right: Evaluation Results -->
      <div class="panel results-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="icon">📊</span>
            Evaluation Result
          </div>
          <button v-if="result" @click="clearResult" class="btn-sm">Clear</button>
        </div>
        <div class="panel-content">
          <div v-if="result" class="result-card" :class="result.passed ? 'pass' : 'fail'">
            <div class="result-header">
              <span class="result-icon">{{ result.passed ? '✅' : '🚫' }}</span>
              <span class="result-verdict">{{ result.passed ? 'PASSED' : 'VIOLATION' }}</span>
            </div>
            
            <div v-if="result.message" class="result-message">
              {{ result.message }}
            </div>

            <div v-if="result.error" class="result-error">
              <span class="error-label">Error:</span>
              <code>{{ result.error }}</code>
            </div>

            <div v-if="result.details" class="result-details">
              <span class="details-label">Debug Details:</span>
              <pre>{{ JSON.stringify(result.details, null, 2) }}</pre>
            </div>
          </div>
          
          <div v-else class="empty-state">
            <div class="empty-icon">⚡</div>
            <p>Ready to evaluate</p>
            <span class="hint">Define trace & policy, then click Evaluate</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TraceView from './TraceView/TraceView.vue'
import type { TraceMessage } from './TraceView/types'

// State
const trace = ref<TraceMessage[]>([])
const policyCode = ref('')
const result = ref<any>(null)
const evaluating = ref(false)
const highlights = ref<Record<string, string>>({})

// Sample data
function loadSampleTrace() {
  trace.value = [
    {
      role: 'user',
      content: 'Can you execute this Python code for me?',
    },
    {
      role: 'assistant',
      content: 'I\'ll execute the code for you.',
      tool_calls: [
        {
          id: 'call_001',
          type: 'function',
          function: {
            name: 'execute_code',
            arguments: {
              language: 'python',
              code: 'print("Hello, World!")',
            },
          },
        },
      ],
    },
    {
      role: 'tool',
      content: 'Hello, World!',
      tool_call_id: 'call_001',
    },
  ]
}

function clearTrace() {
  trace.value = []
  highlights.value = {}
}

function loadSamplePolicy() {
  policyCode.value = `# Block dangerous code execution tools
raise "Dangerous tool call detected" if:
    tool_calls[0].function.name in ["execute_code", "file_write", "shell_exec"]

# Prevent high confidence injections
raise "Injection detected" if:
    l2_result.is_injection and l2_result.confidence > 0.8`
}

function handleTraceUpdate(newTrace: TraceMessage[]) {
  trace.value = newTrace
}

async function evaluatePolicy() {
  if (!policyCode.value.trim()) {
    alert('Please enter a policy')
    return
  }

  if (trace.value.length === 0) {
    alert('Please load a trace first')
    return
  }

  evaluating.value = true
  result.value = null

  try {
    // Build trace with mock analysis context for playground
    const traceWithAnalysis = {
      messages: trace.value,
      analysis: {
        verdict: 'ALLOW',
        threat_level: 'MEDIUM',
        l1_result: {
          patterns_found: [],
          risk_score: 0.3,
        },
        l2_result: {
          is_injection: false,
          confidence: 0.2,
          reasoning: 'No injection detected',
        },
      },
    }

    const response = await fetch('/api/v1/policy/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        policy: policyCode.value,
        trace: traceWithAnalysis,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    result.value = await response.json()

    // Highlight violated messages
    if (!result.value.passed && result.value.details) {
      highlights.value = {
        'messages[1]': '#ff6b6b', // Simple heuristic for demo
      }
    } else {
      highlights.value = {}
    }
  } catch (error) {
    console.error('Policy evaluation error:', error)
    result.value = {
      passed: false,
      message: 'Evaluation failed',
      error: error instanceof Error ? error.message : String(error),
    }
  } finally {
    evaluating.value = false
  }
}

function clearResult() {
  result.value = null
  highlights.value = {}
}
</script>

<style scoped>
.playground {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.playground-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-main h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px 0;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
}

.btn-evaluate {
  background: var(--accent);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-evaluate:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-evaluate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.playground-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1px;
  background: var(--border);
  overflow: hidden;
}

.panel {
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elevated);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  position: relative;
}

.panel-content.no-padding {
  padding: 0;
  display: flex;
  flex-direction: column;
}

.btn-sm {
  padding: 4px 10px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-sm:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.btn-primary-sm {
  padding: 6px 12px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

/* Empty State */
.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  text-align: center;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-state p {
  font-weight: 500;
  margin-bottom: 12px;
}

.hint {
  font-size: 12px;
  opacity: 0.7;
}

/* Policy Editor */
.editor-wrapper {
  flex: 1;
  position: relative;
}

.policy-editor {
  width: 100%;
  height: 100%;
  border: none;
  resize: none;
  padding: 16px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
}

.policy-help-bar {
  padding: 8px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
  font-size: 12px;
}

.help-popup {
  margin-top: 8px;
  padding: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.help-popup h4 {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.help-popup ul {
  margin: 0 0 12px 0;
  padding-left: 20px;
}

.help-popup pre {
  background: var(--bg-elevated);
  padding: 8px;
  border-radius: 4px;
  margin: 0;
}

/* Results */
.result-card {
  border: 1px solid transparent;
  border-radius: 8px;
  overflow: hidden;
}

.result-card.pass {
  background: rgba(16, 185, 129, 0.05);
  border-color: rgba(16, 185, 129, 0.2);
}

.result-card.fail {
  background: rgba(239, 68, 68, 0.05);
  border-color: rgba(239, 68, 68, 0.2);
}

.result-header {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(0,0,0,0.05);
}

.result-icon {
  font-size: 24px;
}

.result-verdict {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.5px;
}

.pass .result-verdict { color: #10b981; }
.fail .result-verdict { color: #ef4444; }

.result-message {
  padding: 16px;
  font-weight: 500;
}

.result-error,
.result-details {
  padding: 12px 16px;
  background: rgba(0,0,0,0.03);
  border-top: 1px solid rgba(0,0,0,0.05);
  font-size: 12px;
}

.error-label,
.details-label {
  display: block;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-secondary);
}

.result-error code {
  color: #ef4444;
  font-family: monospace;
}

.result-details pre {
  margin: 0;
  white-space: pre-wrap;
  color: var(--text-dim);
}

/* Spinner */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>