<template>
  <div class="playground">
    <!-- Three-column layout -->
    <div class="playground-layout">
      <!-- Left: Trace View -->
      <div class="playground-column trace-column">
        <div class="column-header">
          <h3>Trace</h3>
          <button @click="loadSampleTrace" class="btn-secondary">Load Sample</button>
        </div>
        <div class="column-content">
          <TraceView
            v-if="trace.length > 0"
            :trace="trace"
            :highlights="highlights"
            trace-id="playground-trace"
            @update:trace="handleTraceUpdate"
          />
          <div v-else class="empty-state">
            <p>No trace loaded</p>
            <button @click="loadSampleTrace" class="btn-primary">Load Sample Trace</button>
          </div>
        </div>
      </div>

      <!-- Middle: Policy Editor -->
      <div class="playground-column policy-column">
        <div class="column-header">
          <h3>Policy</h3>
          <div class="header-actions">
            <button @click="loadSamplePolicy" class="btn-secondary">Load Sample</button>
            <button @click="evaluatePolicy" class="btn-primary" :disabled="evaluating">
              {{ evaluating ? 'Evaluating...' : 'Evaluate' }}
            </button>
          </div>
        </div>
        <div class="column-content">
          <textarea
            v-model="policyCode"
            class="policy-editor"
            placeholder='Enter policy code, e.g.:

raise "High risk detected" if:
    threat_level >= "HIGH"'
            spellcheck="false"
          />
          <div class="policy-help">
            <details>
              <summary>Policy Syntax Help</summary>
              <div class="help-content">
                <h4>Basic Syntax</h4>
                <pre>raise "message" if:
    condition</pre>

                <h4>Available Variables</h4>
                <ul>
                  <li><code>threat_level</code> - LOW, MEDIUM, HIGH, CRITICAL</li>
                  <li><code>verdict</code> - ALLOW, BLOCK, ESCALATE</li>
                  <li><code>l1_result.patterns_found</code> - List of matched patterns</li>
                  <li><code>l2_result.is_injection</code> - Boolean</li>
                  <li><code>l2_result.confidence</code> - Float 0-1</li>
                  <li><code>tool_calls[0].function.name</code> - Tool name</li>
                </ul>

                <h4>Operators</h4>
                <ul>
                  <li>Comparison: <code>==</code>, <code>!=</code>, <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code></li>
                  <li>Logical: <code>and</code>, <code>or</code>, <code>not</code></li>
                  <li>Membership: <code>in</code>, <code>not in</code></li>
                </ul>

                <h4>Examples</h4>
                <pre># Block high-risk requests
raise "High risk" if:
    threat_level >= "HIGH"

# Block dangerous tools
raise "Dangerous tool" if:
    tool_calls[0].function.name in ["execute_code", "file_write"]

# Block prompt injection
raise "Injection detected" if:
    l2_result.is_injection and l2_result.confidence >= 0.8</pre>
              </div>
            </details>
          </div>
        </div>
      </div>

      <!-- Right: Results -->
      <div class="playground-column results-column">
        <div class="column-header">
          <h3>Results</h3>
          <button v-if="result" @click="clearResult" class="btn-secondary">Clear</button>
        </div>
        <div class="column-content">
          <div v-if="result" class="result-display">
            <div class="result-status" :class="result.passed ? 'passed' : 'failed'">
              <div class="status-icon">
                {{ result.passed ? '✓' : '✗' }}
              </div>
              <div class="status-text">
                {{ result.passed ? 'Policy Passed' : 'Policy Violated' }}
              </div>
            </div>

            <div v-if="result.message" class="result-message">
              <h4>Message</h4>
              <p>{{ result.message }}</p>
            </div>

            <div v-if="result.error" class="result-error">
              <h4>Error</h4>
              <pre>{{ result.error }}</pre>
            </div>

            <div v-if="result.details" class="result-details">
              <h4>Details</h4>
              <pre>{{ JSON.stringify(result.details, null, 2) }}</pre>
            </div>
          </div>
          <div v-else class="empty-state">
            <p>No results yet</p>
            <p class="hint">Click "Evaluate" to test your policy</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { TraceView } from './TraceView'
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

function loadSamplePolicy() {
  policyCode.value = `raise "Dangerous tool call detected" if:
    tool_calls[0].function.name in ["execute_code", "file_write", "shell_exec"]`
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
    // Build trace with mock analysis
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
        'messages[1]': '#ff6b6b',
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
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary, #ffffff);
}

.playground-layout {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1px;
  flex: 1;
  background: var(--border-color, #e0e0e0);
  overflow: hidden;
}

.playground-column {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary, #ffffff);
  overflow: hidden;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f5f5f5);
}

.column-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.column-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--primary-color, #007bff);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover, #0056b3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  color: var(--text-primary, #333);
  border: 1px solid var(--border-color, #e0e0e0);
}

.btn-secondary:hover {
  background: var(--bg-hover, #e8e8e8);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary, #666);
  text-align: center;
}

.empty-state p {
  margin: 8px 0;
}

.empty-state .hint {
  font-size: 13px;
  font-style: italic;
}

.policy-editor {
  width: 100%;
  height: calc(100% - 120px);
  padding: 16px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: none;
  background: var(--bg-code, #f8f8f8);
  color: var(--text-primary, #333);
}

.policy-editor:focus {
  outline: none;
  border-color: var(--primary-color, #007bff);
}

.policy-help {
  margin-top: 16px;
}

.policy-help details {
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  padding: 12px;
  background: var(--bg-secondary, #f5f5f5);
}

.policy-help summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text-primary, #333);
  user-select: none;
}

.policy-help summary:hover {
  color: var(--primary-color, #007bff);
}

.help-content {
  margin-top: 12px;
  font-size: 13px;
}

.help-content h4 {
  margin: 16px 0 8px 0;
  font-size: 14px;
  color: var(--text-primary, #333);
}

.help-content ul {
  margin: 8px 0;
  padding-left: 24px;
}

.help-content li {
  margin: 4px 0;
}

.help-content code {
  padding: 2px 6px;
  background: var(--bg-code, #f8f8f8);
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 12px;
}

.help-content pre {
  margin: 8px 0;
  padding: 12px;
  background: var(--bg-code, #f8f8f8);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}

.result-display {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
}

.result-status.passed {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
  border: 2px solid #10b981;
}

.result-status.failed {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border: 2px solid #ef4444;
}

.status-icon {
  font-size: 32px;
  line-height: 1;
}

.result-message,
.result-error,
.result-details {
  padding: 16px;
  border-radius: 6px;
  background: var(--bg-secondary, #f5f5f5);
}

.result-message h4,
.result-error h4,
.result-details h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.result-message p {
  margin: 0;
  color: var(--text-primary, #333);
}

.result-error pre,
.result-details pre {
  margin: 0;
  padding: 12px;
  background: var(--bg-code, #f8f8f8);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary, #333);
}

.result-error {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid #ef4444;
}

.result-error h4 {
  color: #dc2626;
}
</style>