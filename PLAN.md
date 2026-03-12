Plan to implement                                                                     │
│                                                                                       │
│ Agent Firewall 增强计划：集成 Invariant Explorer 优点 + Agent-Scan 安全策略           │
│                                                                                       │
│ Context                                                                               │
│                                                                                       │
│ 用户希望以 Agent Firewall 为底座，集成 Invariant Explorer 的所有优点（包括 UI         │
│ 设计），同时保持 Agent Firewall 的轻量化特性。此外，需要将 agent-scan                 │
│ 的安全检测能力融合到 Agent Firewall 的策略系统中。                                    │
│                                                                                       │
│ 关键约束：                                                                            │
│ 1. 数据库使用 SQLite（不使用 PostgreSQL）                                             │
│ 2. 不需要多用户支持（保持单租户设计）                                                 │
│ 3. 集成 agent-scan 的安全检测能力到策略引擎                                           │
│                                                                                       │
│ 核心发现                                                                              │
│                                                                                       │
│ 1. Agent-Scan 安全检测能力                                                            │
│                                                                                       │
│ Agent-Scan 是什么：                                                                   │
│ - Snyk 开发的 AI Agent 供应链安全扫描器                                               │
│ - 专门检测 MCP 服务器、Skills、工具调用中的安全威胁                                   │
│ - 支持静态分析 + 远程 API 验证（Snyk 后端）                                           │
│                                                                                       │
│ 核心检测能力：                                                                        │
│                                                                                       │
│ 1. Issues（严重威胁）                                                                 │
│   - E001: 工具描述中的 Prompt Injection                                               │
│   - E002: 跨服务器工具引用（Tool Shadowing）                                          │
│   - E003: 工具描述劫持 Agent 行为                                                     │
│   - E004: Skill 中的 Prompt Injection                                                 │
│   - E005: Skill 中的可疑下载 URL                                                      │
│   - E006: Skill 中的恶意代码模式                                                      │
│ 2. Warnings（潜在威胁）                                                               │
│   - W001: 工具描述中的可疑词汇                                                        │
│   - W002: 实体数量过多（>100）                                                        │
│   - W007: Skill 中的不安全凭证处理                                                    │
│   - W008: Skill 中的硬编码密钥                                                        │
│   - W009: 直接金融执行能力                                                            │
│   - W011: 暴露于不可信第三方内容                                                      │
│   - W012: 不可验证的外部依赖                                                          │
│   - W013: 系统服务修改                                                                │
│ 3. Toxic Flows（组合威胁）                                                            │
│   - TF001: 数据泄露流（Untrusted Content → Private Data → Public Sink）               │
│   - TF002: 破坏性流（Untrusted Content → Destructive Tool）                           │
│ 4. 工具分类标签（用于 Toxic Flow 检测）                                               │
│   - is_public_sink: 发送数据到外部/公共目的地                                         │
│   - destructive: 执行不可逆操作                                                       │
│   - untrusted_content: 返回外部/用户控制的数据                                        │
│   - private_data: 访问敏感用户数据                                                    │
│                                                                                       │
│ Agent-Scan 架构：                                                                     │
│ CLI (snyk-agent-scan)                                                                 │
│   ↓                                                                                   │
│ 1. Inspect Pipeline (本地扫描)                                                        │
│    - 读取 MCP 配置文件（Claude/Cursor/VSCode/Windsurf）                               │
│    - 连接 MCP 服务器，获取工具描述                                                    │
│    - 扫描 Skills（SKILL.md 文件）                                                     │
│   ↓                                                                                   │
│ 2. Analyze Pipeline (远程验证)                                                        │
│    - 调用 Snyk API 进行深度分析                                                       │
│    - 返回威胁等级、Issue Codes、Toxic Flow 检测                                       │
│   ↓                                                                                   │
│ 3. Output                                                                             │
│    - Rich 格式化输出（终端）                                                          │
│    - JSON 格式输出（可选）                                                            │
│                                                                                       │
│ 关键模型：                                                                            │
│ - ScanPathResult: 扫描结果（包含 servers、issues、labels、toxic flows）               │
│ - ScalarToolLabels: 工具分类标签（4 个维度，0-1 浮点数）                              │
│ - ToxicFlow: 组合威胁检测结果                                                         │
│                                                                                       │
│ 集成价值：                                                                            │
│ - Agent Firewall 当前仅有 L1（静态模式匹配）+ L2（LLM 语义分析）                      │
│ - Agent-Scan 提供了结构化的威胁分类体系（Issue Codes）                                │
│ - Agent-Scan 的 Toxic Flow 检测是 Agent Firewall 缺失的关键能力                       │
│ - Agent-Scan 的工具分类标签可以增强 Agent Firewall 的决策矩阵                         │
│                                                                                       │
│ 2. 设计理念对比                                                                       │
│                                                                                       │
│ 相似之处：                                                                            │
│                                                                                       │
│ 两个项目都是 AI Agent 安全监控系统，但采用了完全不同的架构哲学：                      │
│                                                                                       │
│ - Agent Firewall（你的项目）：                                                        │
│   - 实时拦截型（Real-time Interception） — 作为 MITM 代理直接拦截 MCP JSON-RPC 流量   │
│   - 零信任架构（Zero-Trust） — 默认拒绝，双层分析（L1 静态 + L2 语义）                │
│   - 即时决策（Immediate Verdict） — 在请求到达工具服务器之前做出 ALLOW/BLOCK/ESCALATE │
│  决策                                                                                 │
│   - 轻量级存储 — 使用 JSONL 审计日志，无数据库依赖                                    │
│ - Invariant Explorer：                                                                │
│   - 事后分析型（Post-hoc Analysis） — 通过外部 Gateway 容器记录流量，不直接拦截       │
│   - 可观测性优先（Observability-First） — 重点是可视化、追溯和策略测试                │
│   - 异步策略评估（Async Policy Checking） — 策略检查是批量或流式的，不阻塞实时流量    │
│   - 重量级存储 — PostgreSQL 数据库 + 完整的 ORM 层（SQLAlchemy + Alembic）            │
│                                                                                       │
│ 核心差异：                                                                            │
│ - Agent Firewall 是防火墙（Firewall） — 阻止恶意请求                                  │
│ - Invariant Explorer 是监控平台（Monitoring Platform） — 记录和分析轨迹               │
│                                                                                       │
│ 2. 架构对比                                                                           │
│                                                                                       │
│ Agent Firewall 架构                                                                   │
│                                                                                       │
│ AI Agent → Firewall (9090) → MCP Server                                               │
│               ↓                                                                       │
│          WebSocket Dashboard (9091)                                                   │
│               ↓                                                                       │
│          JSONL Audit Log                                                              │
│                                                                                       │
│ 特点：                                                                                │
│ - 单进程 FastAPI 应用（Uvicorn）                                                      │
│ - 内存会话管理（SessionManager with ring buffer）                                     │
│ - 无数据库依赖                                                                        │
│ - 实时 WebSocket 推送到前端                                                           │
│ - 支持 3 种传输协议：SSE、stdio、OpenAI-compatible                                    │
│                                                                                       │
│ Invariant Explorer 架构                                                               │
│                                                                                       │
│ AI Agent → Gateway Container (8002) → LLM Provider (OpenAI/Anthropic)                 │
│               ↓                                                                       │
│          Explorer API (8000) → PostgreSQL (5432)                                      │
│               ↓                                                                       │
│          React SPA (80) ← Traefik Reverse Proxy                                       │
│                                                                                       │
│ 特点：                                                                                │
│ - 微服务架构（Docker Compose）                                                        │
│ - 外部 Gateway 容器（invariant-gateway）负责拦截                                      │
│ - PostgreSQL 持久化存储                                                               │
│ - Traefik 反向代理                                                                    │
│ - 仅支持 LLM API 代理（OpenAI/Anthropic/Gemini），不支持 MCP                          │
│                                                                                       │
│ 3. 功能对比                                                                           │
│                                                                                       │
│ ┌───────────────────┬─────────────────────────┬────────────────────────────────────┐  │
│ │       功能        │     Agent Firewall      │         Invariant Explorer         │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 实时拦截          │ ✅ 核心功能             │ ❌ 仅记录                          │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ MCP 协议支持      │ ✅ 原生支持             │ ❌ 不支持                          │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ LLM API 代理      │ ✅ OpenAI-compatible    │ ✅ OpenAI/Anthropic/Gemini         │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 双层分析（L1+L2） │ ✅ Aho-Corasick + LLM   │ ❌ 仅策略检查                      │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 策略系统          │ ✅                      │ ✅ Invariant DSL 策略语言          │  │
│ │                   │ 基于威胁等级的决策矩阵  │                                    │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 数据持久化        │ ❌ 仅 JSONL 日志        │ ✅ PostgreSQL + 完整 ORM           │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 轨迹可视化        │ ⚠️  基础（实时流量表）   │ ✅ 高级（TraceView 库 + Monaco     │  │
│ │                   │                         │ 编辑器）                           │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 策略测试环境      │ ❌ 无                   │ ✅ Playground（实时评估）          │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 批量分析          │ ❌ 无                   │ ✅ 数据集级别策略检查              │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 注释系统          │ ❌ 无                   │ ✅ 地址定位注释（address-based）   │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 多用户支持        │ ❌ 单租户               │ ✅ 多用户 + API Key 管理           │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 公开分享          │ ❌ 无                   │ ✅ 共享链接 + 公开数据集           │  │
│ ├───────────────────┼─────────────────────────┼────────────────────────────────────┤  │
│ │ 部署复杂度        │ ✅ 单进程（pip          │ ⚠️  Docker Compose（4+ 容器）       │  │
│ │                   │ install）               │                                    │  │
│ └───────────────────┴─────────────────────────┴────────────────────────────────────┘  │
│                                                                                       │
│ 4. Invariant Explorer 的优点                                                          │
│                                                                                       │
│ 1. 企业级数据管理                                                                     │
│   - PostgreSQL 持久化存储，支持复杂查询                                               │
│   - Alembic 数据库迁移，版本控制                                                      │
│   - 完整的用户管理和权限系统                                                          │
│ 2. 强大的可视化能力                                                                   │
│   - 自定义 TraceView 组件（支持代码高亮、图片查看）                                   │
│   - Monaco 编辑器集成（策略编辑）                                                     │
│   - 地址定位注释系统（精确到字符范围）                                                │
│ 3. 策略开发工作流                                                                     │
│   - Playground 实时测试环境                                                           │
│   - 策略库（Library Policies）                                                        │
│   - 批量策略检查（流式 SSE）                                                          │
│   - 策略合成（从轨迹生成策略）                                                        │
│ 4. 协作功能                                                                           │
│   - 多用户注释                                                                        │
│   - 公开数据集分享                                                                    │
│   - 共享链接（SharedLinks 表）                                                        │
│ 5. 集成生态                                                                           │
│   - 支持 7 种 SDK 集成（OpenAI、Anthropic、Gemini、Swarm、MCP）                       │
│   - 代码片段生成器（SetupSnippets.js）                                                │
│   - API Key 管理                                                                      │
│ 6. 生产就绪                                                                           │
│   - Docker Compose 编排                                                               │
│   - Traefik 反向代理                                                                  │
│   - 异步后台任务（工具调用提取、分析）                                                │
│   - 图片存储优化（base64 → 磁盘）                                                     │
│                                                                                       │
│ 5. Invariant Explorer 的缺点                                                          │
│                                                                                       │
│ 1. 不是真正的防火墙                                                                   │
│   - 无法实时阻止恶意请求                                                              │
│   - 依赖外部 Gateway 容器（黑盒）                                                     │
│   - 策略检查是事后的，不能防止攻击                                                    │
│ 2. 部署复杂度高                                                                       │
│   - 需要 Docker Compose                                                               │
│   - 4+ 容器（API、UI、DB、Gateway、Traefik）                                          │
│   - PostgreSQL 数据库维护                                                             │
│   - 需要配置 Keycloak（JWT 认证）                                                     │
│ 3. 不支持 MCP 协议                                                                    │
│   - 仅支持 LLM API 代理（OpenAI/Anthropic/Gemini）                                    │
│   - 无法监控 MCP 工具调用（你的项目的核心场景）                                       │
│ 4. 资源消耗大                                                                         │
│   - PostgreSQL 数据库                                                                 │
│   - 多容器架构                                                                        │
│   - 图片存储（磁盘空间）                                                              │
│ 5. 策略语言学习曲线                                                                   │
│   - Invariant DSL 需要学习                                                            │
│   - 不如你的威胁等级决策矩阵直观                                                      │
│ 6. 缺少实时分析                                                                       │
│   - 无 L1 静态分析（Aho-Corasick）                                                    │
│   - 无 L2 语义分析（LLM 分类器）                                                      │
│   - 策略检查是批量的，不是实时的                                                      │
│                                                                                       │
│ 6. Agent Firewall 的优势（相对于 Explorer）                                           │
│                                                                                       │
│ 1. 真正的实时防护                                                                     │
│   - 在请求到达工具服务器之前拦截                                                      │
│   - 双层分析（L1 < 1ms，L2 可配置超时）                                               │
│   - 威胁等级决策矩阵（CRITICAL → 立即阻止）                                           │
│ 2. MCP 原生支持                                                                       │
│   - 专为 MCP JSON-RPC 设计                                                            │
│   - 支持 3 种传输协议（SSE、stdio、OpenAI-compatible）                                │
│   - 高风险方法列表（tools/call、completion/complete）                                 │
│ 3. 轻量级部署                                                                         │
│   - 单进程 FastAPI 应用                                                               │
│   - 无数据库依赖                                                                      │
│   - pip install 即可运行                                                              │
│ 4. 高性能                                                                             │
│   - Aho-Corasick 模式匹配（Rust 后端）                                                │
│   - orjson 快速序列化                                                                 │
│   - 内存会话管理（ring buffer + TTL GC）                                              │
│ 5. 零信任架构                                                                         │
│   - 默认拒绝                                                                          │
│   - 安全方法白名单（initialize、ping、tools/list）                                    │
│   - ESCALATE 机制（人工审核）                                                         │
│                                                                                       │
│ 7. Agent Firewall 的劣势（相对于 Explorer）                                           │
│                                                                                       │
│ 1. 数据持久化不足                                                                     │
│   - 仅 JSONL 审计日志                                                                 │
│   - 无法复杂查询                                                                      │
│   - 无历史轨迹管理                                                                    │
│ 2. 可视化能力弱                                                                       │
│   - 基础的实时流量表                                                                  │
│   - 无轨迹详情页                                                                      │
│   - 无策略测试环境                                                                    │
│ 3. 单租户设计                                                                         │
│   - 无用户管理                                                                        │
│   - 无 API Key 系统                                                                   │
│   - 无权限控制                                                                        │
│ 4. 缺少协作功能                                                                       │
│   - 无注释系统                                                                        │
│   - 无公开分享                                                                        │
│   - 无多用户支持                                                                      │
│ 5. 策略系统简单                                                                       │
│   - 基于威胁等级的硬编码决策矩阵                                                      │
│   - 无策略 DSL                                                                        │
│   - 无策略测试环境                                                                    │
│                                                                                       │
│ 建议                                                                                  │
│                                                                                       │
│ 如果你想增强 Agent Firewall，可以借鉴 Explorer 的：                                   │
│                                                                                       │
│ 1. 数据持久化层                                                                       │
│   - 添加 SQLite/PostgreSQL 支持（可选）                                               │
│   - 保留 JSONL 作为轻量级选项                                                         │
│ 2. 轨迹可视化                                                                         │
│   - 增强前端，添加轨迹详情页                                                          │
│   - 支持消息展开/折叠                                                                 │
│   - 工具调用高亮                                                                      │
│ 3. 策略测试环境                                                                       │
│   - 添加 Playground 页面                                                              │
│   - 支持策略实时评估                                                                  │
│   - Monaco 编辑器集成                                                                 │
│ 4. 注释系统                                                                           │
│   - 支持在轨迹上添加注释                                                              │
│   - 地址定位（message index + char range）                                            │
│ 5. 多用户支持（如果需要企业部署）                                                     │
│   - API Key 管理                                                                      │
│   - 用户权限系统                                                                      │
│                                                                                       │
│ 如果你想保持 Agent Firewall 的轻量级特性，应该：                                      │
│                                                                                       │
│ 1. 专注于实时防护                                                                     │
│   - 继续优化 L1 + L2 分析性能                                                         │
│   - 增强威胁等级决策矩阵                                                              │
│   - 添加更多高风险方法                                                                │
│ 2. 保持无数据库设计                                                                   │
│   - JSONL 审计日志足够                                                                │
│   - 可选的 SQLite 支持（不强制）                                                      │
│ 3. 增强 MCP 支持                                                                      │
│   - 这是你的核心优势                                                                  │
│   - Explorer 不支持 MCP                                                               │
│ 4. 简化部署                                                                           │
│   - 单进程设计                                                                        │
│   - pip install 即可运行                                                              │
│   - 无 Docker 依赖                                                                    │
│                                                                                       │
│ 实施计划（修订版）                                                                    │
│                                                                                       │
│ Phase 0: Agent-Scan 集成（新增，P0 优先级）                                           │
│                                                                                       │
│ 目标： 将 agent-scan 的安全检测能力集成到 Agent Firewall 的策略引擎中                 │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. Agent-Scan 库集成 (src/engine/agent_scan_integration.py)                           │
│ # 将 agent-scan 作为 Python 库集成（不是 CLI）                                        │
│ from agent_scan.pipelines import inspect_pipeline, InspectArgs                        │
│ from agent_scan.models import ScanPathResult, ScalarToolLabels, ToxicFlow             │
│                                                                                       │
│ class AgentScanAnalyzer:                                                              │
│     """集成 agent-scan 的安全分析器"""                                                │
│                                                                                       │
│     async def scan_mcp_server(                                                        │
│         self,                                                                         │
│         server_config: dict,                                                          │
│         timeout: int = 10                                                             │
│     ) -> ScanPathResult:                                                              │
│         """扫描单个 MCP 服务器"""                                                     │
│         # 调用 agent-scan 的 inspect_pipeline                                         │
│         # 返回结构化的扫描结果                                                        │
│                                                                                       │
│     async def analyze_tool(                                                           │
│         self,                                                                         │
│         tool_name: str,                                                               │
│         tool_description: str                                                         │
│     ) -> dict:                                                                        │
│         """分析单个工具的安全性"""                                                    │
│         # 返回 Issue Codes + Tool Labels                                              │
│                                                                                       │
│     def detect_toxic_flows(                                                           │
│         self,                                                                         │
│         tools: list[dict]                                                             │
│     ) -> list[ToxicFlow]:                                                             │
│         """检测 Toxic Flows（组合威胁）"""                                            │
│         # TF001: Data Leak (untrusted → private → public)                             │
│         # TF002: Destructive (untrusted → destructive)                                │
│ 2. 增强威胁等级决策矩阵 (src/engine/interceptor.py)                                   │
│ # 现有决策矩阵（基于 L1 + L2）                                                        │
│ # CRITICAL: L1 高风险 + L2 高置信度                                                   │
│ # HIGH: L1 中风险 或 L2 中置信度                                                      │
│ # MEDIUM: L1 低风险                                                                   │
│ # LOW: 无威胁                                                                         │
│                                                                                       │
│ # 新增：Agent-Scan 增强决策矩阵                                                       │
│ def _compute_verdict_with_agent_scan(                                                 │
│     self,                                                                             │
│     l1_result: StaticAnalysisResult,                                                  │
│     l2_result: SemanticAnalysisResult,                                                │
│     agent_scan_result: ScanPathResult,  # 新增                                        │
│ ) -> Verdict:                                                                         │
│     # 1. 检查 Agent-Scan Issues（E001-E006）                                          │
│     if agent_scan_result.has_critical_issues():                                       │
│         return Verdict(                                                               │
│             action="BLOCK",                                                           │
│             threat_level="CRITICAL",                                                  │
│             reason=f"Agent-Scan detected: {agent_scan_result.issues}",                │
│         )                                                                             │
│                                                                                       │
│     # 2. 检查 Toxic Flows（TF001, TF002）                                             │
│     toxic_flows = agent_scan_result.toxic_flows                                       │
│     if toxic_flows:                                                                   │
│         return Verdict(                                                               │
│             action="ESCALATE",                                                        │
│             threat_level="HIGH",                                                      │
│             reason=f"Toxic Flow detected: {toxic_flows}",                             │
│         )                                                                             │
│                                                                                       │
│     # 3. 检查 Tool Labels（用于细粒度控制）                                           │
│     tool_labels = agent_scan_result.tool_labels                                       │
│     if tool_labels.destructive > 0.8:                                                 │
│         return Verdict(                                                               │
│             action="ESCALATE",                                                        │
│             threat_level="HIGH",                                                      │
│             reason="Destructive tool detected",                                       │
│         )                                                                             │
│                                                                                       │
│     # 4. 回退到现有 L1 + L2 决策矩阵                                                  │
│     return self._compute_verdict(l1_result, l2_result)                                │
│ 3. 配置选项 (.env)                                                                    │
│ # Agent-Scan 集成                                                                     │
│ AF_AGENT_SCAN_ENABLED=true  # 启用 agent-scan 集成                                    │
│ AF_AGENT_SCAN_MODE=local    # local | remote（是否调用 Snyk API）                     │
│ AF_AGENT_SCAN_API_KEY=...   # Snyk API Key（remote 模式）                             │
│ AF_AGENT_SCAN_CACHE_TTL=3600  # 扫描结果缓存时间（秒）                                │
│                                                                                       │
│ # 策略配置                                                                            │
│ AF_BLOCK_CRITICAL_ISSUES=true  # 自动阻止 E001-E006                                   │
│ AF_ESCALATE_TOXIC_FLOWS=true   # Toxic Flow 触发人工审核                              │
│ AF_BLOCK_DESTRUCTIVE_TOOLS=false  # 是否阻止破坏性工具                                │
│ 4. 缓存机制 (src/engine/agent_scan_cache.py)                                          │
│ # Agent-Scan 扫描结果缓存（避免重复扫描）                                             │
│ class AgentScanCache:                                                                 │
│     def __init__(self, ttl: int = 3600):                                              │
│         self.cache: dict[str, ScanPathResult] = {}                                    │
│         self.ttl = ttl                                                                │
│                                                                                       │
│     def get(self, tool_signature: str) -> ScanPathResult | None:                      │
│         # 基于工具签名（name + description hash）缓存                                 │
│                                                                                       │
│     def set(self, tool_signature: str, result: ScanPathResult):                       │
│         # 设置缓存，带 TTL                                                            │
│ 5. 前端展示 (frontend/src/components/Traffic.vue)                                     │
│ <!-- 在流量表中显示 Agent-Scan 检测结果 -->                                           │
│ <template>                                                                            │
│   <tr>                                                                                │
│     <td>{{ event.method }}</td>                                                       │
│     <td>                                                                              │
│       <!-- 现有威胁等级 -->                                                           │
│       <span :class="threatLevelClass">{{ event.threat_level }}</span>                 │
│                                                                                       │
│       <!-- 新增：Agent-Scan Issue Codes -->                                           │
│       <div v-if="event.agent_scan_issues">                                            │
│         <span                                                                         │
│           v-for="issue in event.agent_scan_issues"                                    │
│           :key="issue.code"                                                           │
│           class="issue-badge"                                                         │
│           :class="issue.severity"                                                     │
│         >                                                                             │
│           {{ issue.code }}                                                            │
│         </span>                                                                       │
│       </div>                                                                          │
│                                                                                       │
│       <!-- 新增：Toxic Flow 警告 -->                                                  │
│       <div v-if="event.toxic_flows">                                                  │
│         <span class="toxic-flow-badge">                                               │
│           ⚠️  Toxic Flow: {{ event.toxic_flows[0].type }}                              │
│         </span>                                                                       │
│       </div>                                                                          │
│     </td>                                                                             │
│   </tr>                                                                               │
│ </template>                                                                           │
│                                                                                       │
│ 关键文件：                                                                            │
│ - src/engine/agent_scan_integration.py — Agent-Scan 集成层                            │
│ - src/engine/agent_scan_cache.py — 扫描结果缓存                                       │
│ - src/engine/interceptor.py — 增强决策矩阵（集成 Agent-Scan）                         │
│ - src/config.py — 添加 Agent-Scan 配置选项                                            │
│ - src/models.py — 添加 Agent-Scan 相关模型                                            │
│ - frontend/src/components/Traffic.vue — 前端展示 Issue Codes                          │
│                                                                                       │
│ 验证步骤：                                                                            │
│ # 1. 启用 Agent-Scan 集成                                                             │
│ export AF_AGENT_SCAN_ENABLED=true                                                     │
│ export AF_AGENT_SCAN_MODE=local                                                       │
│                                                                                       │
│ # 2. 测试恶意工具检测                                                                 │
│ # 创建一个包含 Prompt Injection 的 MCP 工具                                           │
│ # 验证 Agent Firewall 是否阻止（E001）                                                │
│                                                                                       │
│ # 3. 测试 Toxic Flow 检测                                                             │
│ # 配置多个工具：untrusted_content + private_data + public_sink                        │
│ # 验证是否触发 TF001 警告                                                             │
│                                                                                       │
│ # 4. 查看前端展示                                                                     │
│ # 访问 http://localhost:9091/traffic                                                  │
│ # 验证 Issue Codes 和 Toxic Flow 警告是否显示                                         │
│                                                                                       │
│ Phase 1: 数据持久化层（SQLite）                                                       │
│                                                                                       │
│ 目标： 添加 SQLite 数据库支持，同时保持 JSONL 作为默认选项                            │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. 数据库抽象层 (src/storage/)                                                        │
│ # src/storage/base.py                                                                 │
│ class StorageBackend(ABC):                                                            │
│     @abstractmethod                                                                   │
│     async def save_trace(self, trace: Trace) -> str: ...                              │
│     @abstractmethod                                                                   │
│     async def get_trace(self, trace_id: str) -> Trace: ...                            │
│     @abstractmethod                                                                   │
│     async def list_traces(self, filters: dict) -> list[Trace]: ...                    │
│                                                                                       │
│ # src/storage/jsonl.py (现有实现)                                                     │
│ class JsonlStorage(StorageBackend): ...                                               │
│                                                                                       │
│ # src/storage/sqlite.py (新增)                                                        │
│ class SqliteStorage(StorageBackend):                                                  │
│     # 使用 aiosqlite（异步 SQLite）                                                   │
│     # 表结构：traces, datasets, annotations, policies                                 │
│ 2. 数据模型扩展 (src/models.py)                                                       │
│   - 添加 Trace 模型（包含 messages、metadata、annotations、agent_scan_results）       │
│   - 添加 Dataset 模型（组织 traces，不需要 user_id）                                  │
│   - 添加 Annotation 模型（地址定位注释）                                              │
│   - 添加 Policy 模型（策略定义）                                                      │
│   - 添加 AgentScanResult 模型（agent-scan 检测结果）                                  │
│ 3. 配置选项 (.env)                                                                    │
│ AF_STORAGE_BACKEND=jsonl  # jsonl | sqlite                                            │
│ AF_STORAGE_PATH=./data/traces.db  # SQLite 路径                                       │
│ 4. 迁移工具                                                                           │
│ python -m agent_firewall.tools.migrate --from jsonl --to sqlite                       │
│                                                                                       │
│ 关键文件：                                                                            │
│ - src/storage/base.py — 存储抽象接口                                                  │
│ - src/storage/jsonl.py — 现有 JSONL 实现                                              │
│ - src/storage/sqlite.py — SQLite 实现（使用 aiosqlite）                               │
│ - src/models.py — 扩展数据模型                                                        │
│                                                                                       │
│ Phase 2: 前端增强 - TraceView 组件                                                    │
│                                                                                       │
│ 目标： 将 Explorer 的 TraceView 库移植到 Vue 3，实现高级轨迹可视化                    │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. TraceView Vue 组件 (frontend/src/components/TraceView/)                            │
│ TraceView/                                                                            │
│ ├── TraceView.vue          # 主组件（类似 Explorer 的 traceview.tsx）                 │
│ ├── TraceLine.vue          # 单行消息组件（类似 line.tsx）                            │
│ ├── TraceHighlight.vue     # 高亮注释组件（类似 highlights.ts）                       │
│ ├── TraceEditor.vue        # Monaco 编辑器集成                                        │
│ ├── plugins/                                                                          │
│ │   ├── CodeHighlighter.vue  # 代码高亮插件                                           │
│ │   └── ImageViewer.vue      # 图片查看器                                             │
│ └── TraceView.scss         # 样式（移植 Explorer 的 TraceView.scss）                  │
│ 2. 核心功能：                                                                         │
│   - 消息展开/折叠（collapsible messages）                                             │
│   - 工具调用高亮（tool call highlighting）                                            │
│   - 地址定位注释（address-based annotations）                                         │
│   - 代码块语法高亮（code highlighting）                                               │
│   - 图片内联显示（inline images）                                                     │
│   - 侧边栏编辑器（side-by-side editor）                                               │
│   - 永久链接（permalink navigation）                                                  │
│ 3. UI 设计借鉴：                                                                      │
│   - Explorer 的三栏布局（Trace | Policy | Results）                                   │
│   - 可调整大小的面板（ResizablePanel）                                                │
│   - 图标系统（react-icons → Vue 3 icons）                                             │
│   - 深色/浅色主题切换                                                                 │
│                                                                                       │
│ 关键文件：                                                                            │
│ - frontend/src/components/TraceView/TraceView.vue — 主组件                            │
│ - frontend/src/components/TraceView/TraceLine.vue — 消息行                            │
│ - frontend/src/components/TraceView/plugins/ — 插件系统                               │
│                                                                                       │
│ Phase 3: Playground 策略测试环境                                                      │
│                                                                                       │
│ 目标： 添加策略测试页面，支持实时策略评估                                             │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. Playground 页面 (frontend/src/components/Playground.vue)                           │
│   - 三栏布局：Trace（左） | Policy（中） | Results（右）                              │
│   - Monaco 编辑器集成（策略编辑）                                                     │
│   - 实时策略评估（WebSocket 流式）                                                    │
│   - Base64 URL 编码（分享链接）                                                       │
│ 2. 策略 DSL 设计                                                                      │
│ # 简化版 Invariant DSL（兼容现有 L1+L2 分析）                                         │
│                                                                                       │
│ # 示例 1：基于威胁等级                                                                │
│ raise "High risk detected" if:                                                        │
│     threat_level >= "HIGH"                                                            │
│                                                                                       │
│ # 示例 2：基于工具调用                                                                │
│ raise "Dangerous tool call" if:                                                       │
│     tool_call.name in ["execute_code", "file_write"]                                  │
│                                                                                       │
│ # 示例 3：基于语义分析                                                                │
│ raise "Prompt injection detected" if:                                                 │
│     l2_analysis.is_injection and l2_analysis.confidence >= 0.8                        │
│                                                                                       │
│ # 示例 4：组合条件                                                                    │
│ raise "Critical threat" if:                                                           │
│     threat_level == "CRITICAL" or                                                     │
│     (l1_patterns.count > 3 and l2_analysis.is_injection)                              │
│ 3. 策略评估引擎 (src/engine/policy_dsl.py)                                            │
│ class PolicyEngine:                                                                   │
│     def __init__(self, l1: StaticAnalyzer, l2: SemanticAnalyzer):                     │
│         self.l1 = l1                                                                  │
│         self.l2 = l2                                                                  │
│                                                                                       │
│     async def evaluate(self, policy_code: str, trace: Trace) -> PolicyResult:         │
│         # 解析策略 DSL                                                                │
│         # 执行策略逻辑                                                                │
│         # 返回结果（PASS/FAIL + 详细信息）                                            │
│ 4. API 端点 (src/main.py)                                                             │
│ @app.post("/api/v1/policy/evaluate")                                                  │
│ async def evaluate_policy(                                                            │
│     policy: str,                                                                      │
│     trace: list[dict],                                                                │
│ ) -> PolicyResult:                                                                    │
│     # 流式评估策略                                                                    │
│                                                                                       │
│ 关键文件：                                                                            │
│ - frontend/src/components/Playground.vue — Playground 页面                            │
│ - src/engine/policy_dsl.py — 策略 DSL 解析器                                          │
│ - src/main.py — 添加 /api/v1/policy/evaluate 端点                                     │
│                                                                                       │
│ Phase 4: 数据集管理                                                                   │
│                                                                                       │
│ 目标： 添加数据集功能，组织和管理轨迹                                                 │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. 数据集模型 (src/models.py)                                                         │
│ @dataclass                                                                            │
│ class Dataset:                                                                        │
│     id: str                                                                           │
│     name: str                                                                         │
│     user_id: str | None  # 可选（多用户支持）                                         │
│     is_public: bool                                                                   │
│     traces: list[str]  # trace IDs                                                    │
│     policies: list[Policy]                                                            │
│     metadata: dict                                                                    │
│     created_at: datetime                                                              │
│     updated_at: datetime                                                              │
│ 2. 数据集 API (src/routes/dataset.py)                                                 │
│ @router.post("/api/v1/dataset")                                                       │
│ async def create_dataset(name: str) -> Dataset: ...                                   │
│                                                                                       │
│ @router.get("/api/v1/dataset/{id}")                                                   │
│ async def get_dataset(id: str) -> Dataset: ...                                        │
│                                                                                       │
│ @router.get("/api/v1/dataset/{id}/traces")                                            │
│ async def list_traces(id: str, filters: dict) -> list[Trace]: ...                     │
│                                                                                       │
│ @router.post("/api/v1/dataset/{id}/policy/check")                                     │
│ async def check_policy(id: str, policy_id: str) -> AsyncIterator[PolicyResult]:       │
│     # 流式批量策略检查                                                                │
│ 3. 前端页面 (frontend/src/components/Dataset.vue)                                     │
│   - 数据集列表（类似 Explorer 的 Home 页面）                                          │
│   - 数据集详情（类似 Explorer 的 Dataset 页面）                                       │
│   - 轨迹列表（带过滤和搜索）                                                          │
│   - 批量策略检查                                                                      │
│                                                                                       │
│ 关键文件：                                                                            │
│ - src/routes/dataset.py — 数据集 API                                                  │
│ - frontend/src/components/Dataset.vue — 数据集页面                                    │
│ - frontend/src/components/DatasetList.vue — 数据集列表                                │
│                                                                                       │
│ Phase 5: 注释系统                                                                     │
│                                                                                       │
│ 目标： 支持在轨迹上添加地址定位注释                                                   │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. 注释模型 (src/models.py)                                                           │
│ @dataclass                                                                            │
│ class Annotation:                                                                     │
│     id: str                                                                           │
│     trace_id: str                                                                     │
│     user_id: str | None                                                               │
│     address: str  # "messages.1.content:5-10"                                         │
│     content: str                                                                      │
│     severity: str  # "info" | "warning" | "error"                                     │
│     source: str  # "user" | "l1" | "l2" | "policy"                                    │
│     created_at: datetime                                                              │
│ 2. 注释 API (src/routes/trace.py)                                                     │
│ @router.post("/api/v1/trace/{id}/annotate")                                           │
│ async def add_annotation(                                                             │
│     id: str,                                                                          │
│     address: str,                                                                     │
│     content: str,                                                                     │
│     severity: str,                                                                    │
│ ) -> Annotation: ...                                                                  │
│                                                                                       │
│ @router.get("/api/v1/trace/{id}/annotations")                                         │
│ async def get_annotations(id: str) -> list[Annotation]: ...                           │
│ 3. 前端集成 (frontend/src/components/TraceView/)                                      │
│   - 在 TraceView 组件中显示注释                                                       │
│   - 支持点击添加注释                                                                  │
│   - 注释高亮和悬停显示                                                                │
│                                                                                       │
│ 关键文件：                                                                            │
│ - src/models.py — Annotation 模型                                                     │
│ - src/routes/trace.py — 注释 API                                                      │
│ - frontend/src/components/TraceView/TraceHighlight.vue — 注释显示                     │
│                                                                                       │
│ Phase 6: UI 设计增强                                                                  │
│                                                                                       │
│ 目标： 借鉴 Explorer 的 UI 设计，提升用户体验                                         │
│                                                                                       │
│ 实现方案：                                                                            │
│                                                                                       │
│ 1. 布局系统                                                                           │
│   - 侧边栏导航（类似 Explorer）                                                       │
│   - 顶部导航栏（用户信息、设置）                                                      │
│   - 可调整大小的面板（ResizablePanel）                                                │
│ 2. 组件库                                                                             │
│   - Modal 对话框                                                                      │
│   - Toast 通知                                                                        │
│   - 加载动画（Spinning）                                                              │
│   - 图标系统（统一图标库）                                                            │
│ 3. 主题系统                                                                           │
│   - 深色/浅色主题切换                                                                 │
│   - CSS 变量（颜色、字体、间距）                                                      │
│ 4. 页面重构                                                                           │
│   - Dashboard → 数据集列表 + 最近轨迹                                                 │
│   - Traffic → 实时流量 + 历史轨迹                                                     │
│   - Rules → 策略管理 + Playground                                                     │
│   - Engine → L1/L2 配置 + 统计                                                        │
│   - Audit → 审计日志 + 导出                                                           │
│                                                                                       │
│ 关键文件：                                                                            │
│ - frontend/src/App.vue — 主布局                                                       │
│ - frontend/src/components/Sidebar.vue — 侧边栏                                        │
│ - frontend/src/components/Modal.vue — 对话框                                          │
│ - frontend/src/styles/ — 主题样式                                                     │
│                                                                                       │
│ 实施优先级（修订版）                                                                  │
│                                                                                       │
│ P0（核心功能，必须实现）                                                              │
│                                                                                       │
│ 0. Agent-Scan 集成 — 将 agent-scan 安全检测能力集成到策略引擎                         │
│ 1. 数据持久化层（SQLite） — 轻量级数据库支持                                          │
│ 2. TraceView 组件 — 高级轨迹可视化                                                    │
│ 3. Playground — 策略测试环境                                                          │
│                                                                                       │
│ P1（重要功能，建议实现）                                                              │
│                                                                                       │
│ 4. 数据集管理 — 组织轨迹                                                              │
│ 5. 注释系统 — 地址定位注释                                                            │
│ 6. UI 设计增强 — 借鉴 Explorer 设计                                                   │
│                                                                                       │
│ P2（可选功能，未来扩展）                                                              │
│                                                                                       │
│ 7. ~~多用户支持~~（不需要）                                                           │
│ 8. ~~PostgreSQL 支持~~（不需要）                                                      │
│                                                                                       │
│ 技术栈保持                                                                            │
│                                                                                       │
│ 保持不变：                                                                            │
│ - FastAPI + Uvicorn（单进程）                                                         │
│ - Vue 3 + TypeScript（前端）                                                          │
│ - Pydantic v2（数据验证）                                                             │
│ - ahocorasick-rs（L1 分析）                                                           │
│ - orjson（JSON 序列化）                                                               │
│                                                                                       │
│ 新增依赖：                                                                            │
│ - snyk-agent-scan（Agent-Scan 集成，作为 Python 库）                                  │
│ - aiosqlite（异步 SQLite 支持）                                                       │
│ - monaco-editor-vue3（Monaco 编辑器）                                                 │
│ - @vicons/ionicons5（Vue 3 图标库）                                                   │
│ - vue-virtual-scroller（虚拟滚动）                                                    │
│                                                                                       │
│ 移除依赖：                                                                            │
│ - ~~`sqlalchemy+alembic`~~（不使用 ORM，直接用 aiosqlite）                            │
│                                                                                       │
│ 部署保持轻量级                                                                        │
│                                                                                       │
│ 默认部署（JSONL + Agent-Scan）：                                                      │
│ pip install agent-firewall                                                            │
│ agent-firewall --config .env                                                          │
│                                                                                       │
│ 可选 SQLite 部署：                                                                    │
│ pip install agent-firewall[sqlite]                                                    │
│ agent-firewall --config .env --storage sqlite                                         │
│                                                                                       │
│ 迁移路径                                                                              │
│                                                                                       │
│ 现有用户：                                                                            │
│ 1. 升级到新版本（向后兼容）                                                           │
│ 2. 继续使用 JSONL 审计日志（默认）                                                    │
│ 3. 可选：启用 Agent-Scan 集成（AF_AGENT_SCAN_ENABLED=true）                           │
│ 4. 可选：迁移到 SQLite（python -m agent_firewall.tools.migrate）                      │
│                                                                                       │
│ 新用户：                                                                              │
│ 1. 默认使用 JSONL + Agent-Scan（轻量级）                                              │
│ 2. 可选启用 SQLite（持久化查询）                                                      │
│                                                                                       │
│ 验证步骤                                                                              │
│                                                                                       │
│ Phase 0 验证（Agent-Scan 集成）                                                       │
│                                                                                       │
│ # 1. 测试本地模式                                                                     │
│ export AF_AGENT_SCAN_ENABLED=true                                                     │
│ export AF_AGENT_SCAN_MODE=local                                                       │
│ make test                                                                             │
│                                                                                       │
│ # 2. 测试恶意工具检测（E001）                                                         │
│ # 创建包含 Prompt Injection 的 MCP 工具                                               │
│ # 验证是否被阻止                                                                      │
│                                                                                       │
│ # 3. 测试 Toxic Flow 检测（TF001）                                                    │
│ # 配置 untrusted_content + private_data + public_sink 工具                            │
│ # 验证是否触发 ESCALATE                                                               │
│                                                                                       │
│ # 4. 查看前端展示                                                                     │
│ cd frontend && npm run dev                                                            │
│ # 访问 http://localhost:9091/traffic                                                  │
│ # 验证 Issue Codes 显示                                                               │
│                                                                                       │
│ Phase 1 验证（数据持久化）                                                            │
│                                                                                       │
│ # 测试 JSONL 存储（默认）                                                             │
│ make test                                                                             │
│                                                                                       │
│ # 测试 SQLite 存储                                                                    │
│ AF_STORAGE_BACKEND=sqlite make test                                                   │
│                                                                                       │
│ # 测试迁移工具                                                                        │
│ python -m agent_firewall.tools.migrate --from jsonl --to sqlite                       │
│                                                                                       │
│ Phase 2 验证（TraceView）                                                             │
│                                                                                       │
│ # 启动前端开发服务器                                                                  │
│ cd frontend && npm run dev                                                            │
│                                                                                       │
│ # 访问 http://localhost:9091/traces/{trace_id}                                        │
│ # 验证：                                                                              │
│ # - 消息展开/折叠                                                                     │
│ # - 工具调用高亮                                                                      │
│ # - 代码块语法高亮                                                                    │
│ # - 图片内联显示                                                                      │
│                                                                                       │
│ Phase 3 验证（Playground）                                                            │
│                                                                                       │
│ # 访问 http://localhost:9091/playground                                               │
│ # 验证：                                                                              │
│ # - Monaco 编辑器加载                                                                 │
│ # - 策略实时评估                                                                      │
│ # - 结果高亮显示                                                                      │
│ # - 分享链接生成                                                                      │
│                                                                                       │
│ Phase 4 验证（数据集）                                                                │
│                                                                                       │
│ # 创建数据集                                                                          │
│ curl -X POST http://localhost:9090/api/v1/dataset \                                   │
│   -H "Content-Type: application/json" \                                               │
│   -d '{"name": "test-dataset"}'                                                       │
│                                                                                       │
│ # 批量策略检查                                                                        │
│ curl -X POST http://localhost:9090/api/v1/dataset/{id}/policy/check \                 │
│   -H "Content-Type: application/json" \                                               │
│   -d '{"policy_id": "..."}'                                                           │
│                                                                                       │
│ Phase 5 验证（注释）                                                                  │
│                                                                                       │
│ # 添加注释                                                                            │
│ curl -X POST http://localhost:9090/api/v1/trace/{id}/annotate \                       │
│   -H "Content-Type: application/json" \                                               │
│   -d '{"address": "messages.1.content:5-10", "content": "Suspicious pattern",         │
│ "severity": "warning"}'                                                               │
│                                                                                       │
│ # 获取注释                                                                            │
│ curl http://localhost:9090/api/v1/trace/{id}/annotations                              │
│                                                                                       │
│ 关键文件清单                                                                          │
│                                                                                       │
│ 后端：                                                                                │
│ - src/engine/agent_scan_integration.py — Agent-Scan 集成层（新增）                    │
│ - src/engine/agent_scan_cache.py — 扫描结果缓存（新增）                               │
│ - src/engine/interceptor.py — 增强决策矩阵（修改）                                    │
│ - src/storage/base.py — 存储抽象接口                                                  │
│ - src/storage/jsonl.py — JSONL 实现                                                   │
│ - src/storage/sqlite.py — SQLite 实现（新增）                                         │
│ - src/engine/policy_dsl.py — 策略 DSL 解析器（新增）                                  │
│ - src/routes/dataset.py — 数据集 API（新增）                                          │
│ - src/routes/trace.py — 轨迹 API（扩展）                                              │
│ - src/models.py — 数据模型（扩展）                                                    │
│ - src/config.py — 配置（添加 Agent-Scan 选项）                                        │
│                                                                                       │
│ 前端：                                                                                │
│ - frontend/src/components/TraceView/TraceView.vue — TraceView 主组件（新增）          │
│ - frontend/src/components/TraceView/TraceLine.vue — 消息行组件（新增）                │
│ - frontend/src/components/TraceView/plugins/ — 插件系统（新增）                       │
│ - frontend/src/components/Playground.vue — Playground 页面（新增）                    │
│ - frontend/src/components/Dataset.vue — 数据集页面（新增）                            │
│ - frontend/src/components/DatasetList.vue — 数据集列表（新增）                        │
│ - frontend/src/components/Traffic.vue — 流量页面（修改，显示 Issue Codes）            │
│ - frontend/src/components/Sidebar.vue — 侧边栏（修改）                                │
│ - frontend/src/components/Modal.vue — 对话框（新增）                                  │
│ - frontend/src/App.vue — 主布局（重构）                                               │
│                                                                                       │
│ 工具：                                                                                │
│ - src/tools/migrate.py — 数据迁移工具（新增）                                         │
│ - tests/test_storage.py — 存储层测试（新增）                                          │
│ - tests/test_policy_dsl.py — 策略 DSL 测试（新增）                                    │
│ - tests/test_agent_scan_integration.py — Agent-Scan 集成测试（新增）                  │
│                                                                                       │
│ 总结                                                                                  │
│                                                                                       │
│ 这个增强计划将 Agent Firewall 从一个实时安全网关升级为一个企业级 AI Agent             │
│ 安全平台，同时保持其核心优势：                                                        │
│                                                                                       │
│ 保持的优势：                                                                          │
│ - ✅ 实时拦截能力（MITM 代理）                                                        │
│ - ✅ MCP 原生支持                                                                     │
│ - ✅ 双层分析（L1 + L2）                                                              │
│ - ✅ 零信任架构                                                                       │
│ - ✅ 轻量级部署（无强制数据库）                                                       │
│ - ✅ 单进程设计                                                                       │
│ - ✅ 单租户设计（无多用户复杂度）                                                     │
│                                                                                       │
│ 新增的能力：                                                                          │
│ - ✅ Agent-Scan 集成（结构化威胁检测 + Toxic Flow 分析）                              │
│ - ✅ 高级轨迹可视化（TraceView）                                                      │
│ - ✅ 策略测试环境（Playground）                                                       │
│ - ✅ 数据集管理                                                                       │
│ - ✅ 注释系统                                                                         │
│ - ✅ SQLite 数据库支持（可选）                                                        │
│ - ✅ 现代化 UI 设计                                                                   │
│                                                                                       │
│ 实施策略：                                                                            │
│ - 增量开发（6 个 Phase，Phase 0 为 Agent-Scan 集成）                                  │
│ - 向后兼容（现有用户无影响）                                                          │
│ - 可选功能（按需启用）                                                                │
│ - 渐进式增强（从 P0 到 P1）                                                           │
│                                                                                       │
│ 关键创新：                                                                            │
│ 1. Agent-Scan 集成是最重要的增强，将结构化的威胁分类体系（Issue Codes）和 Toxic Flow  │
│ 检测能力引入 Agent Firewall                                                           │
│ 2. SQLite 替代 PostgreSQL，保持轻量级部署                                             │
│ 3. 移除多用户支持，简化架构，专注于单租户场景                                         │
│ 4. 保留 JSONL 作为默认选项，SQLite 作为可选升级路径
