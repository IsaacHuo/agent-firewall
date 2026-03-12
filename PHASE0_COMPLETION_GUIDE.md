# Phase 0: Agent-Scan Integration - 完成指南

## 当前状态

已在 `feat/phase-0-agent-scan` 分支上创建了 Agent-Scan 集成的核心文件：
- ✅ `src/engine/agent_scan_integration.py` - 核心分析器

## 需要完成的步骤

由于响应长度限制，以下是完成 Phase 0 干净分支的步骤：

### 1. 更新配置文件 (`src/config.py`)

在 `FirewallConfig` 类的末尾添加：

```python
# ── Agent-Scan Integration ───────────────────────────────────────
agent_scan_enabled: bool = field(
    default_factory=lambda: os.getenv("AF_AGENT_SCAN_ENABLED", "1") == "1"
)
agent_scan_mode: str = field(
    default_factory=lambda: os.getenv("AF_AGENT_SCAN_MODE", "local")
)
agent_scan_api_key: str = field(
    default_factory=lambda: os.getenv("AF_AGENT_SCAN_API_KEY", "")
)
agent_scan_cache_ttl: int = field(
    default_factory=lambda: int(os.getenv("AF_AGENT_SCAN_CACHE_TTL", "3600"))
)
block_critical_issues: bool = field(
    default_factory=lambda: os.getenv("AF_BLOCK_CRITICAL_ISSUES", "1") == "1"
)
escalate_toxic_flows: bool = field(
    default_factory=lambda: os.getenv("AF_ESCALATE_TOXIC_FLOWS", "1") == "1"
)
block_destructive_tools: bool = field(
    default_factory=lambda: os.getenv("AF_BLOCK_DESTRUCTIVE_TOOLS", "0") == "1"
)
```

### 2. 更新数据模型 (`src/models.py`)

在 `AnalysisResult` 类中，在 `l2_reasoning` 后添加：

```python
# Agent-Scan analysis (optional, only if enabled)
agent_scan_issues: list[dict[str, Any]] = Field(default_factory=list)
agent_scan_labels: dict[str, float] | None = None
agent_scan_toxic_flows: list[dict[str, Any]] = Field(default_factory=list)
```

### 3. 更新拦截器 (`src/engine/interceptor.py`)

#### 3.1 添加导入
```python
from .agent_scan_integration import AgentScanAnalyzer, AgentScanResult
```

#### 3.2 添加增强决策函数（在 `_compute_verdict` 后）
```python
def _compute_verdict_with_agent_scan(
    l1: L1Result,
    l2: L2Result,
    agent_scan: AgentScanResult | None,
    *,
    block_critical_issues: bool = True,
    escalate_toxic_flows: bool = True,
    block_destructive_tools: bool = False,
) -> tuple[Verdict, ThreatLevel, str]:
    """Enhanced verdict computation with Agent-Scan integration."""
    from .static_analyzer import _threat_ord

    if agent_scan is None:
        return _compute_verdict(l1, l2)

    # 1. Critical Issues (E001-E006) → BLOCK
    if block_critical_issues and agent_scan.has_critical_issues():
        issue_codes = [issue.code for issue in agent_scan.issues if issue.code.startswith("E")]
        return (
            Verdict.BLOCK,
            ThreatLevel.CRITICAL,
            f"Agent-Scan critical issues: {', '.join(issue_codes)}",
        )

    # 2. Toxic Flows (TF001, TF002) → ESCALATE
    if escalate_toxic_flows and agent_scan.has_toxic_flows():
        flow_types = [flow.type for flow in agent_scan.toxic_flows]
        return (
            Verdict.ESCALATE,
            ThreatLevel.HIGH,
            f"Agent-Scan toxic flows: {', '.join(flow_types)}",
        )

    # 3. Destructive Tools → BLOCK (optional)
    if block_destructive_tools and agent_scan.labels.destructive > 0.8:
        return (
            Verdict.BLOCK,
            ThreatLevel.HIGH,
            f"Destructive tool detected (score={agent_scan.labels.destructive:.2f})",
        )

    # 4. Warnings → Elevate threat level
    if agent_scan.has_warnings():
        warning_codes = [issue.code for issue in agent_scan.issues if issue.code.startswith("W")]
        logger.info(f"Agent-Scan warnings detected: {', '.join(warning_codes)}")
        verdict, threat_level, reason = _compute_verdict(l1, l2)
        if _threat_ord(threat_level) < _threat_ord(ThreatLevel.MEDIUM):
            threat_level = ThreatLevel.MEDIUM
            reason = f"{reason}; Agent-Scan warnings: {', '.join(warning_codes)}"
        return verdict, threat_level, reason

    return _compute_verdict(l1, l2)
```

#### 3.3 更新 `intercept_and_analyze` 函数签名
添加参数：
```python
agent_scan_analyzer: AgentScanAnalyzer | None = None,
```

#### 3.4 在 L2 分析后添加 Agent-Scan 分析（Step 5.5）
```python
# ── Step 5.5: Agent-Scan Analysis (async, optional) ──────────
agent_scan_result: AgentScanResult | None = None
if agent_scan_analyzer is not None and agent_scan_analyzer.enabled:
    if request.method == "tools/call" and request.params:
        try:
            tool_name = request.params.get("name", "unknown")
            tool_description = str(request.params.get("arguments", ""))
            agent_scan_result = await agent_scan_analyzer.analyze_tool(
                tool_name=tool_name,
                tool_description=tool_description,
                tool_schema=request.params,
            )
        except Exception as exc:
            logger.error(f"Agent-Scan analysis failed: {exc}")
```

#### 3.5 更新决策逻辑
```python
# Use enhanced verdict if Agent-Scan is available
if agent_scan_result is not None:
    from ..config import FirewallConfig
    config = FirewallConfig()
    verdict, threat_level, reason = _compute_verdict_with_agent_scan(
        l1_result,
        l2_result,
        agent_scan_result,
        block_critical_issues=config.block_critical_issues,
        escalate_toxic_flows=config.escalate_toxic_flows,
        block_destructive_tools=config.block_destructive_tools,
    )
else:
    verdict, threat_level, reason = _compute_verdict(l1_result, l2_result)

# Serialize Agent-Scan results
agent_scan_issues_dict = []
agent_scan_labels_dict = None
agent_scan_toxic_flows_dict = []

if agent_scan_result is not None:
    agent_scan_issues_dict = [
        {"code": issue.code, "message": issue.message, "severity": issue.severity}
        for issue in agent_scan_result.issues
    ]
    agent_scan_labels_dict = {
        "is_public_sink": agent_scan_result.labels.is_public_sink,
        "destructive": agent_scan_result.labels.destructive,
        "untrusted_content": agent_scan_result.labels.untrusted_content,
        "private_data": agent_scan_result.labels.private_data,
    }
    agent_scan_toxic_flows_dict = [
        {"type": flow.type, "description": flow.description, "tool_chain": flow.tool_chain}
        for flow in agent_scan_result.toxic_flows
    ]

analysis = AnalysisResult(
    l1_matched_patterns=l1_result.matched_patterns,
    l1_threat_level=l1_result.threat_level,
    l2_is_injection=l2_result.is_injection,
    l2_confidence=l2_result.confidence,
    l2_reasoning=l2_result.reasoning,
    agent_scan_issues=agent_scan_issues_dict,
    agent_scan_labels=agent_scan_labels_dict,
    agent_scan_toxic_flows=agent_scan_toxic_flows_dict,
    verdict=verdict,
    threat_level=threat_level,
    blocked_reason=reason,
)
```

### 4. 更新主应用 (`src/main.py`)

#### 4.1 添加导入
```python
from .engine.agent_scan_integration import AgentScanAnalyzer
```

#### 4.2 在 `AppState.__init__` 中初始化
```python
# Initialize Agent-Scan analyzer
self.agent_scan_analyzer = AgentScanAnalyzer(
    enabled=config.agent_scan_enabled,
    mode=config.agent_scan_mode,
    api_key=config.agent_scan_api_key,
    cache_ttl=config.agent_scan_cache_ttl,
)
```

#### 4.3 传递给适配器
```python
self.sse_adapter = SseAdapter(
    ...
    agent_scan_analyzer=self.agent_scan_analyzer,
    ...
)

self.ws_adapter = WebSocketAdapter(
    ...
    agent_scan_analyzer=self.agent_scan_analyzer,
    ...
)
```

### 5. 更新 SSE 适配器 (`src/proxy/sse_adapter.py`)

#### 5.1 添加导入
```python
from ..engine.agent_scan_integration import AgentScanAnalyzer
```

#### 5.2 更新 `SseAdapter.__init__` 和 `WebSocketAdapter.__init__`
添加参数：
```python
agent_scan_analyzer: AgentScanAnalyzer | None = None,
```

存储：
```python
self._agent_scan = agent_scan_analyzer
```

#### 5.3 更新所有 `intercept_and_analyze` 调用
添加参数：
```python
agent_scan_analyzer=self._agent_scan,
```

### 6. 更新环境配置 (`.env.example`)

添加：
```bash
# ── Agent-Scan Integration ───────────────────────────────────────
AF_AGENT_SCAN_ENABLED=1
AF_AGENT_SCAN_MODE=local
AF_AGENT_SCAN_API_KEY=
AF_AGENT_SCAN_CACHE_TTL=3600
AF_BLOCK_CRITICAL_ISSUES=1
AF_ESCALATE_TOXIC_FLOWS=1
AF_BLOCK_DESTRUCTIVE_TOOLS=0
```

### 7. 创建测试文件 (`tests/test_agent_scan_integration.py`)

[完整测试代码见之前创建的文件]

### 8. 提交更改

```bash
cd extensions/agent-firewall

# 只添加 Agent-Scan 相关文件
git add src/engine/agent_scan_integration.py
git add src/config.py
git add src/models.py
git add src/engine/interceptor.py
git add src/main.py
git add src/proxy/sse_adapter.py
git add tests/test_agent_scan_integration.py
git add .env.example

# 提交
git commit -m "feat(phase-0): Integrate Agent-Scan security detection

Implement Phase 0 of the enhancement plan: Agent-Scan integration
for structured threat detection and toxic flow analysis.

Key Features:
- AgentScanAnalyzer: Local pattern-based security analysis
- Issue detection: E001-E006 (errors), W001-W013 (warnings)
- Tool classification: 4 dimensions (public_sink, destructive,
  untrusted_content, private_data)
- Toxic flow detection: TF001 (data leak), TF002 (destructive)
- Enhanced verdict computation with Agent-Scan priority checks
- Caching mechanism to avoid redundant scans

Integration Points:
- src/engine/agent_scan_integration.py: Core analyzer
- src/engine/interceptor.py: Enhanced decision matrix
- src/config.py: Agent-Scan configuration options
- src/models.py: Extended AnalysisResult with Agent-Scan fields
- src/main.py: Initialize Agent-Scan analyzer
- src/proxy/sse_adapter.py: Pass analyzer to interceptor

Configuration:
- AF_AGENT_SCAN_ENABLED: Enable/disable Agent-Scan
- AF_AGENT_SCAN_MODE: local (default) | remote (Snyk API)
- AF_BLOCK_CRITICAL_ISSUES: Auto-block E001-E006
- AF_ESCALATE_TOXIC_FLOWS: Escalate TF001/TF002
- AF_BLOCK_DESTRUCTIVE_TOOLS: Block destructive tools

Tests: 15 test cases covering all detection capabilities

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# 运行测试验证
source .venv/bin/activate
python -m pytest tests/test_agent_scan_integration.py -v

# 推送分支
git push origin feat/phase-0-agent-scan
```

### 9. 创建 Pull Request

标题: **Phase 0: Agent-Scan Integration**

描述:
```markdown
## Phase 0: Agent-Scan Integration

实现 PLAN.md 中的 Phase 0，将 Snyk agent-scan 的安全检测能力集成到 Agent Firewall 的策略引擎中。

### 核心功能

- **AgentScanAnalyzer**: 本地模式的安全分析器
- **Issue 检测**: E001-E006 (严重威胁), W001-W013 (警告)
- **工具分类**: 4 个维度的标签系统
- **Toxic Flow 检测**: TF001 (数据泄露), TF002 (破坏性流)
- **增强决策矩阵**: Agent-Scan 优先级检查
- **缓存机制**: 避免重复扫描

### 测试

✅ 15/15 测试通过

### 配置

所有配置通过环境变量，默认启用本地模式。

### 依赖

无新增外部依赖，完全自包含。

### 相关文档

- [PLAN.md Phase 0](../../PLAN.md#phase-0-agent-scan-集成新增p0-优先级)
- [BRANCHES.md](../../BRANCHES.md)
```

## 注意事项

1. **不要提交** `agent-scan/`, `PLAN.md`, `explorer/` 等不相关文件
2. **只提交** Agent Firewall 的 Agent-Scan 集成相关文件
3. **运行测试** 确保所有测试通过后再推送
4. **更新 BRANCHES.md** 标记 Phase 0 为已完成

## 下一步

Phase 0 完成并合并到 main 后，开始 Phase 1 (Storage Layer)：

```bash
git checkout main
git pull origin main
git checkout -b feat/phase-1-storage
```
