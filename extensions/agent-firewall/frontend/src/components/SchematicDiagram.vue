<template>
  <div class="schematic-page">
    <div class="page-header">
      <h2>架构示意图</h2>
      <p class="subtitle">可视化拦截流程、策略配置和双层分析引擎</p>
    </div>

    <div class="diagram-container">
      <!-- Main Flow Diagram -->
      <div class="flow-section">
        <h3 class="section-title">拦截流程</h3>
        <div class="flow-diagram">
          <!-- Agent -->
          <div class="flow-node agent-node" @mouseenter="activeNode = 'agent'" @mouseleave="activeNode = null">
            <div class="node-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
            <div class="node-label">AI Agent</div>
            <div class="node-desc">Claude / GPT-4</div>
          </div>

          <!-- Arrow 1 -->
          <div class="flow-arrow" :class="{ active: activeNode === 'agent' }">
            <svg viewBox="0 0 100 24" fill="none">
              <path d="M0 12 L85 12" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/>
              <path d="M85 12 L80 8 M85 12 L80 16" stroke="currentColor" stroke-width="2"/>
            </svg>
            <span class="arrow-label">JSON-RPC Request</span>
          </div>

          <!-- Firewall -->
          <div class="flow-node firewall-node" @mouseenter="activeNode = 'firewall'" @mouseleave="activeNode = null">
            <div class="node-icon accent">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div class="node-label">Agent Firewall</div>
            <div class="node-desc">零信任安全网关</div>
          </div>

          <!-- Arrow 2 -->
          <div class="flow-arrow" :class="{ active: activeNode === 'firewall' }">
            <svg viewBox="0 0 100 24" fill="none">
              <path d="M0 12 L85 12" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/>
              <path d="M85 12 L80 8 M85 12 L80 16" stroke="currentColor" stroke-width="2"/>
            </svg>
            <span class="arrow-label">Filtered Request</span>
          </div>

          <!-- MCP Server -->
          <div class="flow-node server-node" @mouseenter="activeNode = 'server'" @mouseleave="activeNode = null">
            <div class="node-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
                <line x1="6" y1="6" x2="6.01" y2="6"/>
                <line x1="6" y1="18" x2="6.01" y2="18"/>
              </svg>
            </div>
            <div class="node-label">MCP Server</div>
            <div class="node-desc">Tool Server</div>
          </div>
        </div>
      </div>

      <!-- Dual-Layer Analysis -->
      <div class="analysis-section">
        <h3 class="section-title">双层分析引擎</h3>
        <div class="analysis-grid">
          <!-- L1 Static Analysis -->
          <div class="analysis-card l1-card" @click="navigateToEngine">
            <div class="card-header">
              <div class="card-icon green">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </div>
              <div class="card-title">
                <h4>L1 静态分析</h4>
                <span class="card-badge">< 1ms</span>
              </div>
            </div>
            <div class="card-body">
              <p class="card-desc">基于 Aho-Corasick 自动机的高速模式匹配</p>
              <ul class="feature-list">
                <li>• 关键词黑名单检测</li>
                <li>• 正则表达式匹配</li>
                <li>• 命令注入防护</li>
                <li>• 路径遍历检测</li>
              </ul>
            </div>
          </div>

          <!-- L2 Semantic Analysis -->
          <div class="analysis-card l2-card" @click="navigateToEngine">
            <div class="card-header">
              <div class="card-icon purple">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"/>
                </svg>
              </div>
              <div class="card-title">
                <h4>L2 语义分析</h4>
                <span class="card-badge">LLM</span>
              </div>
            </div>
            <div class="card-body">
              <p class="card-desc">基于大语言模型的深度语义理解</p>
              <ul class="feature-list">
                <li>• 意图识别与分类</li>
                <li>• 上下文威胁评估</li>
                <li>• 社会工程学检测</li>
                <li>• 异常行为分析</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Policy Decision Matrix -->
      <div class="policy-section">
        <h3 class="section-title">策略决策矩阵</h3>
        <div class="policy-matrix">
          <div class="matrix-header">
            <div class="matrix-cell header-cell"></div>
            <div class="matrix-cell header-cell">L2: 安全</div>
            <div class="matrix-cell header-cell">L2: 可疑</div>
            <div class="matrix-cell header-cell">L2: 危险</div>
          </div>
          <div class="matrix-row">
            <div class="matrix-cell label-cell">L1: 通过</div>
            <div class="matrix-cell result-cell allow">✓ 允许</div>
            <div class="matrix-cell result-cell escalate">⚠ 人工审核</div>
            <div class="matrix-cell result-cell block">✗ 拦截</div>
          </div>
          <div class="matrix-row">
            <div class="matrix-cell label-cell">L1: 拦截</div>
            <div class="matrix-cell result-cell block">✗ 拦截</div>
            <div class="matrix-cell result-cell block">✗ 拦截</div>
            <div class="matrix-cell result-cell block">✗ 拦截</div>
          </div>
        </div>
        <div class="policy-actions">
          <button class="action-btn primary" @click="navigateToRules">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            配置规则
          </button>
          <button class="action-btn" @click="navigateToEngine">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            引擎设置
          </button>
          <button class="action-btn" @click="navigateToTest">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
            </svg>
            安全测试
          </button>
        </div>
      </div>

      <!-- Custom Policies -->
      <div class="custom-section">
        <h3 class="section-title">自定义策略</h3>
        <div class="custom-grid">
          <div class="custom-card" @click="navigateToRules">
            <div class="custom-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <h4>模式规则</h4>
            <p>配置关键词黑名单、正则表达式和命令过滤规则</p>
          </div>
          <div class="custom-card" @click="navigateToEngine">
            <div class="custom-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </div>
            <h4>引擎配置</h4>
            <p>启用/禁用分析层，配置 LLM 后端和网络参数</p>
          </div>
          <div class="custom-card" @click="navigateToRateLimit">
            <div class="custom-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
            <h4>速率限制</h4>
            <p>配置请求频率限制和突发流量控制</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeNode = ref<string | null>(null)

function navigateToRules() {
  window.location.hash = '#rules'
}

function navigateToEngine() {
  window.location.hash = '#engine'
}

function navigateToTest() {
  window.location.hash = '#test'
}

function navigateToRateLimit() {
  window.location.hash = '#rate-limit'
}
</script>

<style scoped>
.schematic-page {
  padding: 16px;
  overflow-y: auto;
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.subtitle {
  font-size: 12px;
  color: var(--text-muted);
}

.diagram-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Section Titles */
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Flow Diagram */
.flow-section {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.flow-diagram {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px;
  overflow-x: auto;
}

.flow-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--bg-surface);
  border: 2px solid var(--border);
  border-radius: var(--radius-lg);
  min-width: 120px;
  transition: all 0.2s;
  cursor: pointer;
}

.flow-node:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.node-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
}

.node-icon.accent {
  background: var(--accent-muted);
  color: var(--accent);
}

.node-icon svg {
  width: 24px;
  height: 24px;
}

.node-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.node-desc {
  font-size: 10px;
  color: var(--text-muted);
}

.flow-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--text-dim);
  transition: color 0.2s;
}

.flow-arrow.active {
  color: var(--accent);
}

.flow-arrow svg {
  width: 100px;
  height: 24px;
}

.arrow-label {
  font-size: 9px;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Analysis Section */
.analysis-section {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.analysis-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.analysis-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.analysis-card .card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.analysis-card .card-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.analysis-card .card-icon.green {
  background: var(--accent-green-muted);
  color: var(--accent-green);
}

.analysis-card .card-icon.purple {
  background: rgba(168, 85, 247, 0.12);
  color: var(--accent-purple);
}

.analysis-card .card-icon svg {
  width: 18px;
  height: 18px;
}

.analysis-card .card-title {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.analysis-card .card-title h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-badge {
  font-size: 9px;
  padding: 2px 6px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-muted);
  font-weight: 600;
}

.analysis-card .card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feature-list li {
  font-size: 10px;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* Policy Section */
.policy-section {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.policy-matrix {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 12px;
}

.matrix-header,
.matrix-row {
  display: grid;
  grid-template-columns: 100px repeat(3, 1fr);
  gap: 1px;
}

.matrix-cell {
  padding: 10px;
  background: var(--bg-surface);
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.header-cell {
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-hover);
}

.label-cell {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.result-cell {
  font-weight: 600;
  font-size: 12px;
}

.result-cell.allow {
  background: var(--accent-green-muted);
  color: var(--accent-green);
}

.result-cell.block {
  background: var(--accent-red-muted);
  color: var(--accent-red);
}

.result-cell.escalate {
  background: var(--accent-yellow-muted);
  color: var(--accent-yellow);
}

.policy-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-muted);
}

.action-btn.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.action-btn.primary:hover {
  background: var(--accent-hover);
}

.action-btn svg {
  width: 14px;
  height: 14px;
}

/* Custom Section */
.custom-section {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.custom-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.custom-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.custom-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.custom-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-muted);
  color: var(--accent);
  border-radius: var(--radius-md);
}

.custom-icon svg {
  width: 20px;
  height: 20px;
}

.custom-card h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.custom-card p {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.4;
}
</style>
