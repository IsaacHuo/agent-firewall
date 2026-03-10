# 飞书模型配置功能

## 更新内容

已添加飞书通道的AI模型自定义配置功能，用户现在可以自由选择使用的AI模型和上游API端点。

## 配置项

### 环境变量 (.env)

```bash
# 飞书AI模型配置
AF_FEISHU_MODEL=anthropic/claude-3.5-sonnet          # 默认使用 Claude 3.5 Sonnet
AF_FEISHU_UPSTREAM_URL=https://openrouter.ai/api/v1  # 上游API端点
```

### 支持的模型

通过 OpenRouter 可以使用任何兼容 OpenAI API 的模型：

**推荐模型：**

- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet (默认)
- `anthropic/claude-3-opus` - Claude 3 Opus
- `openai/gpt-4` - GPT-4
- `openai/gpt-4-turbo` - GPT-4 Turbo
- `google/gemini-pro` - Gemini Pro
- `deepseek/deepseek-chat` - DeepSeek Chat

**其他选项：**

- 任何 OpenRouter 支持的模型
- 自建的 OpenAI 兼容 API 端点

## 前端配置

在飞书通道页面 (http://localhost:9091/#/feishu) 可以：

1. 查看当前配置的模型
2. 修改 Upstream AI URL
3. 修改 Model 名称
4. 保存配置（需要重启服务生效）

## API 端点

### GET /api/feishu/config

获取飞书配置，包括模型信息：

```json
{
  "connected": true,
  "app_id": "cli_xxxxx",
  "app_secret": "***",
  "upstream_url": "https://openrouter.ai/api/v1",
  "model": "anthropic/claude-3.5-sonnet"
}
```

### POST /api/feishu/test-send

测试发送消息到飞书：

```bash
curl -X POST http://localhost:9090/api/feishu/test-send \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "oc_xxxxx",
    "message": "测试消息"
  }'
```

## 代码变更

### 1. config.py

添加了两个新配置字段：

- `feishu_model` - AI模型名称
- `feishu_upstream_url` - 上游API端点

### 2. feishu_adapter.py

- `FeishuConfig` 类添加 `model` 和 `upstream_url` 参数
- `_call_upstream_ai()` 方法使用配置的模型而非硬编码

### 3. main.py

- 初始化 `FeishuConfig` 时传入模型配置
- API 端点返回模型配置信息

### 4. .env

添加默认配置：

```bash
AF_FEISHU_MODEL=anthropic/claude-3.5-sonnet
AF_FEISHU_UPSTREAM_URL=https://openrouter.ai/api/v1
```

## 使用示例

### 切换到 GPT-4

修改 `.env`:

```bash
AF_FEISHU_MODEL=openai/gpt-4
```

重启服务：

```bash
./scripts/stop-all.sh
./scripts/start-all.sh
```

### 使用自建 API

修改 `.env`:

```bash
AF_FEISHU_UPSTREAM_URL=http://localhost:8000/v1
AF_FEISHU_MODEL=your-custom-model
```

## 注意事项

1. **API Key**: 使用 `AF_L2_API_KEY` 环境变量配置 OpenRouter API Key
2. **重启生效**: 修改配置后需要重启服务才能生效
3. **模型兼容性**: 确保选择的模型支持 OpenAI 兼容的 `/chat/completions` 端点
4. **费用**: 不同模型的调用费用不同，请查看 OpenRouter 定价

## 测试

发送消息到飞书应用，系统会：

1. 接收消息
2. 进行 L1 静态分析
3. 进行 L2 语义分析
4. 使用配置的模型调用 AI
5. 返回响应到飞书

查看日志确认使用的模型：

```bash
tail -f /tmp/restart4.log | grep "model"
```
