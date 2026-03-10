# Feishu Tools Integration via OpenClaw Gateway

## Architecture Overview

All Feishu tools (46+ tools across 6 categories) are now integrated through the **OpenClaw Gateway** TypeScript implementation, eliminating the need for duplicate Python implementations.

## Integration Flow

```
User Message (Feishu/Web)
    ↓
Agent Firewall (Python)
    ↓
L1 Static Analysis (fast)
    ↓
Forward to AI (immediate)
    ↓
L2 Semantic Analysis (background)
    ↓
AI calls invoke_gateway(tool_name="feishu_doc", arguments={...})
    ↓
Gateway Tool Registry → HTTP POST to OpenClaw Gateway
    ↓
OpenClaw Gateway (TypeScript) → Feishu API
    ↓
Result returned to AI → Response to user
```

## Available Feishu Tools

### 1. Document Tools (feishu_doc)

- **18+ actions**: read, write, append, create, list_blocks, get_block, update_block, delete_block, create_table, write_table_cells, create_table_with_values, upload_image, upload_file
- Supports markdown conversion, table operations, image/file uploads

### 2. Drive Tools (feishu_drive)

- **5 actions**: list, info, create_folder, move, delete
- Cloud storage file management

### 3. Permission Tools (feishu_perm)

- **3 actions**: list, add, remove
- Manage document/file collaborators and permissions

### 4. Wiki Tools (feishu_wiki)

- **6 actions**: spaces, nodes, get, create, move, rename
- Knowledge base navigation and management

### 5. Bitable Tools (feishu*bitable*\*)

- **9 tools**: get_meta, list_fields, list_records, get_record, create_record, update_record, create_app, create_field
- Multi-dimensional table operations

### 6. Chat Tools (feishu_chat)

- **2 actions**: members, info
- Chat group information and member management

## Configuration

### 1. Enable Feishu Plugin in OpenClaw

Edit `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "entries": {
      "feishu": {
        "enabled": true
      }
    }
  },
  "feishu": {
    "accounts": {
      "default": {
        "appId": "cli_xxx",
        "appSecret": "xxx",
        "enabled": true
      }
    }
  }
}
```

### 2. Enable Feishu Channel in Agent Firewall

Edit `extensions/agent-firewall/.env`:

```bash
AF_FEISHU_ENABLED=1
AF_FEISHU_APP_ID=cli_xxx
AF_FEISHU_APP_SECRET=xxx
AF_FEISHU_MODEL=minimax/minimax-m2.5
```

## Tool Discovery Mechanism

The `GatewayToolRegistry` class automatically discovers all tools from the TypeScript source:

1. **Scan**: `channel/feishu/src/*.ts` files
2. **Extract**: Tool names and descriptions using regex patterns
3. **Register**: Single `invoke_gateway` meta-tool with all tool names as enum
4. **Execute**: HTTP POST to `http://127.0.0.1:18789/tools/invoke` with Bearer token auth

## Benefits of Gateway Integration

1. **No Duplicate Code**: Single source of truth in TypeScript
2. **Auto-Discovery**: New tools automatically available without Python changes
3. **Consistent Behavior**: Same tool implementation for all channels (Telegram, Feishu, Web)
4. **Reduced Maintenance**: Update tools in one place
5. **Type Safety**: TypeScript provides compile-time validation

## Code Changes

### Simplified `feishu_tools.py`

- Removed manual tool definitions (feishu_create_document, feishu_create_spreadsheet)
- Now a no-op placeholder with documentation
- All tools handled by Gateway discovery

### Updated `main.py`

- Removed `FeishuToolRegistry` initialization
- Removed special handling for `feishu_create_document` and `feishu_create_spreadsheet`
- All Feishu tools now route through `invoke_gateway` → Gateway execution

### Gateway Configuration

- Added feishu plugin entry to `~/.openclaw/openclaw.json`
- Configured Feishu account credentials

## Testing

1. Start OpenClaw Gateway:

   ```bash
   # Gateway should be running on port 18789
   ```

2. Start Agent Firewall:

   ```bash
   cd extensions/agent-firewall
   make dev
   ```

3. Test via Feishu chat or Web Chat Lab:
   ```
   User: "帮我创建一个飞书文档，标题是测试文档"
   AI: [calls invoke_gateway with tool_name="feishu_doc", action="create"]
   ```

## Troubleshooting

### Tools not discovered

- Check Gateway is running: `curl http://127.0.0.1:18789/health`
- Verify feishu plugin enabled in `~/.openclaw/openclaw.json`
- Check logs: `Gateway tools discovered: X (feishu_doc, feishu_drive, ...)`

### Authentication errors

- Verify Gateway token in `~/.openclaw/openclaw.json` matches
- Check Bearer token in HTTP requests

### Tool execution fails

- Check Feishu App ID/Secret are correct
- Verify app has required permissions (docx:document, drive:drive, etc.)
- Check Gateway logs for detailed error messages

## References

- TypeScript Implementation: `/channel/feishu/src/`
- Skill Definitions: `/channel/feishu/skills/*/SKILL.md`
- Gateway Tool Registry: `/extensions/agent-firewall/src/gateway_tools.py`
- Main Integration: `/extensions/agent-firewall/src/main.py`
