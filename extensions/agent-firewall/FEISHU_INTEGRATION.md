# Feishu/Lark Channel Integration

Agent Firewall现在支持飞书（Feishu/Lark）通道集成，可以通过长连接接收和发送飞书消息。

## 配置步骤

### 1. 获取飞书应用凭证

1. 访问[飞书开放平台](https://open.feishu.cn/)
2. 创建或选择你的应用
3. 获取以下信息：
   - **App ID**: 应用的唯一标识
   - **App Secret**: 应用密钥
   - **Encrypt Key** (可选): 事件加密密钥
   - **Verification Token** (可选): 事件验证令牌

### 2. 配置环境变量

在 `.env` 文件中添加以下配置：

```bash
# 启用飞书通道
AF_FEISHU_ENABLED=1

# 飞书应用凭证
AF_FEISHU_APP_ID=cli_a925cba144f9dbb6
AF_FEISHU_APP_SECRET=cdZ71qTMPZoo9ernzyzatfRHR1PvDOXg

# 可选：事件加密和验证
AF_FEISHU_ENCRYPT_KEY=
AF_FEISHU_VERIFICATION_TOKEN=
```

### 3. 在飞书后台配置事件订阅

⚠️ **重要提醒**：启动Agent Firewall后，你需要到飞书开放平台后台进行以下操作：

1. 进入你的应用管理页面
2. 找到"事件订阅"（Event Subscriptions）配置
3. 启用"长连接模式"（WebSocket Mode）
4. 订阅以下事件：
   - `im.message.receive_v1` - 接收消息事件
   - 其他你需要的事件类型

5. 保存配置并确认启用

### 4. 启动Agent Firewall

```bash
cd extensions/agent-firewall
source .venv/bin/activate
make dev
```

启动后，你应该看到类似以下的日志：

```
🚀 Starting Feishu channel adapter...
✅ Feishu channel connected successfully
🛡️  Agent Firewall started on 127.0.0.1:9090 → upstream 127.0.0.1:3000
```

如果连接失败，请检查：

- App ID 和 App Secret 是否正确
- 网络连接是否正常
- 飞书后台是否已启用事件订阅

## 功能特性

- ✅ 长连接接收飞书消息
- ✅ 消息通过L1+L2双层安全分析
- ✅ 支持发送文本消息回飞书
- ✅ 自动重连机制
- ✅ 完整的审计日志

## 架构说明

```
飞书服务器 (WebSocket)
    ↓
FeishuAdapter (长连接监听)
    ↓
Agent Firewall Engine (L1 + L2 分析)
    ↓
上游MCP服务器 / AI Agent
    ↓
FeishuAdapter (发送响应)
    ↓
飞书用户
```

## 故障排查

### 连接失败

如果看到错误日志：

```
❌ Failed to start Feishu channel: ...
```

请检查：

1. `.env` 文件中的 App ID 和 App Secret 是否正确
2. 网络是否可以访问飞书API（`open.feishu.cn`）
3. 是否在飞书后台启用了长连接模式

### 收不到消息

如果连接成功但收不到消息：

1. 确认在飞书后台已订阅 `im.message.receive_v1` 事件
2. 确认机器人已被添加到对应的群聊或私聊
3. 检查机器人是否有相应的权限（读取消息、发送消息等）

## 开发说明

飞书适配器代码位于：

- `src/channels/feishu_adapter.py` - 核心适配器实现
- `src/config.py` - 配置定义
- `src/main.py` - 集成到主应用

如需扩展功能，可以修改 `FeishuAdapter` 类的 `_handle_message` 方法来处理更多事件类型。
