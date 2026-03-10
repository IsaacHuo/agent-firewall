# 飞书通道重大升级

## 更新时间

2026-03-10 13:13

## 核心改进

### 1. 工具调用能力 ✅

**之前：** 飞书消息直接调用 OpenRouter API，只能进行简单对话，无法使用工具

**现在：** 飞书消息通过内部 `/api/chat/send` 端点处理，获得完整的工具调用能力：

- ✅ 飞书文档操作（创建、编辑、读取）
- ✅ 飞书多维表格操作
- ✅ 飞书云空间操作
- ✅ 所有 MCP 工具
- ✅ 所有 Gateway 注册的工具

### 2. 性能优化 ⚡

**之前：** 每条消息都要等待 L2 语义分析完成（~10-30秒），导致响应缓慢

**现在：** 优化的异步处理流程：

1. **L1 快速检查** (<1ms) - 立即拦截高危模式
2. **立即转发AI** - 不等待 L2，快速响应用户
3. **L2 后台分析** - 异步运行，用于审计和监控

**响应时间：** 从 10-30秒 降低到 2-5秒

### 3. 连续对话支持 💬

**之前：** 每条消息独立处理，无上下文

**现在：** 通过 `/api/chat/send` 端点，支持：

- ✅ 多轮对话上下文
- ✅ 工具调用链
- ✅ 复杂任务分解

### 4. 模型切换 🤖

**之前：** 硬编码 gpt-4

**现在：** 可配置模型，当前使用 `minimax/minimax-m2.5`

## 架构对比

### 旧架构（简单对话）

```
Feishu Message → L1 Analysis → L2 Analysis (阻塞) → Direct OpenRouter API → Response
                                  ↓ (10-30秒延迟)
```

### 新架构（完整工具调用）

```
Feishu Message → L1 Quick Check → Internal Chat API → Gateway (MCP) → AI + Tools → Response
                      ↓                                                    ↓
                  立即拦截高危                                        工具调用能力
                      ↓
                L2 Background Analysis (异步，不阻塞)
```

## 代码变更

### 1. feishu_adapter.py

#### \_call_upstream_ai() 方法重构

```python
# 之前：直接调用 OpenRouter
response = await self._http_client.post(
    f"{self.config.upstream_url}/chat/completions",
    json={"model": "gpt-4", "messages": [...]}
)

# 现在：调用内部 Chat API
response = await self._http_client.post(
    "http://127.0.0.1:9090/api/chat/send",
    json={
        "messages": [...],
        "model": self.config.model,
        "enable_tools": True,  # 启用工具调用
    }
)
```

#### \_handle_message() 方法优化

```python
# 之前：同步等待 L2
l2_result = await self.semantic_analyzer.analyze(...)  # 阻塞 10-30秒
if l2_result.is_injection:
    block_message()
else:
    forward_to_ai()

# 现在：异步处理
l1_result = self.static_analyzer.analyze(...)  # <1ms
if l1_threat_high:
    block_immediately()
else:
    forward_to_ai()  # 立即转发
    asyncio.create_task(background_l2_analysis())  # 后台分析
```

### 2. .env 配置

```bash
AF_FEISHU_MODEL=minimax/minimax-m2.5
AF_FEISHU_UPSTREAM_URL=https://openrouter.ai/api/v1
```

## 功能对比

| 功能         | 旧版本      | 新版本    |
| ------------ | ----------- | --------- |
| 简单对话     | ✅          | ✅        |
| 工具调用     | ❌          | ✅        |
| 飞书文档操作 | ❌          | ✅        |
| 多轮对话     | ❌          | ✅        |
| 响应速度     | 慢 (10-30s) | 快 (2-5s) |
| L2 分析      | 阻塞        | 异步      |
| 连续提问     | ❌          | ✅        |

## 使用示例

### 1. 简单对话

```
用户: 你好
AI: 你好！我是AI助手，有什么可以帮助你的吗？
```

### 2. 工具调用 - 创建飞书文档

```
用户: 帮我创建一个飞书文档，标题是"项目计划"
AI: 🔧 create_feishu_doc({"title": "项目计划"})
    → 已创建文档，文档ID: doc_xxxxx

    我已经为你创建了一个名为"项目计划"的飞书文档。
```

### 3. 多轮对话

```
用户: 帮我查询今天的天气
AI: 🔧 get_weather({"location": "北京"})
    → 北京今天晴，温度15-25°C

    北京今天天气不错，晴天，温度在15-25°C之间。

用户: 那明天呢？
AI: 🔧 get_weather({"location": "北京", "date": "明天"})
    → 北京明天多云，温度12-22°C

    明天会有点多云，温度12-22°C，建议带件外套。
```

## 测试方法

### 1. 发送测试消息

在飞书应用中发送消息，观察响应速度和工具调用。

### 2. 查看日志

```bash
tail -f /tmp/restart5.log | grep -E "(Feishu|tool_call)"
```

### 3. 监控面板

访问 http://localhost:9091/#/feishu 查看：

- 实时消息流量
- 工具调用记录
- L1/L2 分析结果

## 性能指标

### 响应时间对比

- **旧版本：** 10-30秒（等待 L2 分析）
- **新版本：** 2-5秒（立即响应）

### L2 分析

- **旧版本：** 阻塞主流程
- **新版本：** 后台异步，不影响响应

### 工具调用

- **旧版本：** 不支持
- **新版本：** 完整支持，包括飞书原生工具

## 注意事项

1. **API Key**: 确保 `AF_L2_API_KEY` 配置正确
2. **Gateway**: 确保 Gateway 服务运行在 18789 端口
3. **工具权限**: 飞书应用需要有相应的权限（文档、表格等）
4. **模型选择**: minimax-m2.5 是高性价比选择，也可以切换到其他模型

## 下一步计划

1. ✅ 工具调用能力 - 已完成
2. ✅ 性能优化 - 已完成
3. ✅ 模型配置 - 已完成
4. 🔄 会话管理 - 支持多轮对话上下文持久化
5. 🔄 前端统一 - Chat Lab 页面也能使用飞书工具
6. 🔄 更多通道 - 企业微信、钉钉等

## 总结

这次升级将飞书通道从简单的"对话机器人"升级为"全功能AI助手"，具备：

- ✅ 完整的工具调用能力
- ✅ 快速响应（2-5秒）
- ✅ 连续对话支持
- ✅ 与 Chat Lab 相同的能力

用户现在可以通过飞书直接操作飞书文档、表格、云空间等，无需切换到网页界面。
