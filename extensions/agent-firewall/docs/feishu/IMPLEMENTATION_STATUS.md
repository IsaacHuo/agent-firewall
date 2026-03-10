# 飞书工具实现状态

## 更新时间

2026-03-10 15:15

## ✅ 已完成

### 1. 核心架构

- ✅ 飞书适配器 (FeishuAdapter) - WebSocket 长连接
- ✅ 工具注册系统 (FeishuToolRegistry)
- ✅ 工具调用流程集成到 main.py
- ✅ 性能优化 (L2 异步分析)
- ✅ 模型配置 (minimax-m2.5)

### 2. 基础工具 (2/46)

- ✅ `feishu_create_document` - 创建文档
- ✅ `feishu_create_spreadsheet` - 创建表格

### 3. Bug 修复

- ✅ 修复 `_state_instance` 未定义错误
- ✅ 修复工具定义格式 (OpenAI function calling)
- ✅ 文档整理到 `docs/feishu/` 目录

## 🚧 待实现工具 (44/46)

根据 `/channel/feishu/skills/` 下的定义，需要实现以下工具：

### feishu_doc (18个操作)

- [ ] read - 读取文档内容
- [ ] write - 替换整个文档
- [ ] append - 追加内容
- [ ] insert - 插入内容
- [ ] list_blocks - 获取块结构
- [ ] get_block - 获取单个块
- [ ] update_block - 更新块
- [ ] delete_block - 删除块
- [ ] create_table - 创建表格
- [ ] write_table_cells - 写入表格单元格
- [ ] create_table_with_values - 创建带数据的表格
- [ ] upload_image - 上传图片
- [ ] upload_file - 上传文件
- [ ] color_text - 文本着色
- [ ] insert_table_row - 插入行
- [ ] insert_table_column - 插入列
- [ ] delete_table_rows - 删除行
- [ ] delete_table_columns - 删除列
- [ ] merge_table_cells - 合并单元格

### feishu_drive (5个操作)

- [ ] list - 列出文件夹内容
- [ ] info - 获取文件信息
- [ ] create_folder - 创建文件夹
- [ ] move - 移动文件
- [ ] delete - 删除文件

### feishu_perm (3个操作)

- [ ] list - 列出协作者
- [ ] add - 添加协作者
- [ ] remove - 移除协作者

### feishu_wiki (6个操作)

- [ ] spaces - 列出知识库
- [ ] nodes - 列出节点
- [ ] get - 获取节点详情
- [ ] create - 创建节点
- [ ] move - 移动节点
- [ ] rename - 重命名节点

### feishu_bitable (9个工具)

- [ ] get_meta - 获取元数据
- [ ] list_fields - 列出字段
- [ ] list_records - 列出记录
- [ ] get_record - 获取记录
- [ ] create_record - 创建记录
- [ ] update_record - 更新记录
- [ ] create_app - 创建应用
- [ ] create_field - 创建字段
- [ ] create_table - 创建表

### feishu_chat (2个操作)

- [ ] info - 获取聊天信息
- [ ] members - 获取成员列表

### 其他

- [ ] feishu_app_scopes - 列出应用权限

## 实现策略

### 方案 1: 直接调用 TypeScript 实现 (推荐)

由于 TypeScript 实现已经完整，可以通过 Gateway 调用：

```python
# 在 feishu_tools.py 中
async def invoke_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # 通过 Gateway 调用 TypeScript 实现的飞书工具
    result = await GatewayToolRegistry.execute(
        host, port, token,
        tool_name=f"feishu_{name}",  # 例如: feishu_doc_read
        arguments=arguments
    )
    return result
```

**优点:**

- 无需重写 Python 实现
- 直接复用已有的 TypeScript 代码
- 快速完成集成

**缺点:**

- 依赖 Gateway 运行
- 需要确保 TypeScript 插件已加载

### 方案 2: Python 原生实现

使用 `lark-oapi` SDK 在 Python 中实现所有工具。

**优点:**

- 独立运行，不依赖 Gateway
- 更好的性能

**缺点:**

- 需要大量开发工作
- 需要维护两套实现

## 推荐实现步骤

### 第一阶段：Gateway 集成 (快速)

1. 确保 Gateway 加载了飞书插件
2. 修改 `feishu_tools.py` 通过 Gateway 调用
3. 测试所有工具可用性

### 第二阶段：高频工具 Python 实现 (可选)

如果需要更好的性能，可以实现高频使用的工具：

- feishu_doc: read, write, append
- feishu_drive: list, info
- feishu_bitable: list_records, create_record

## Gateway 插件配置

需要在 `~/.openclaw/openclaw.json` 中启用飞书插件：

```json
{
  "plugins": {
    "entries": {
      "feishu": {
        "enabled": true,
        "config": {
          "accounts": {
            "default": {
              "appId": "cli_a925cba144f9dbb6",
              "appSecret": "cdZ71qTMPZoo9ernzyzatfRHR1PvDOXg"
            }
          }
        }
      }
    }
  }
}
```

## 测试方法

### 1. 检查 Gateway 工具列表

```bash
curl http://localhost:9090/api/mcp/tools | jq '.[] | select(.function.name | startswith("feishu"))'
```

### 2. 测试工具调用

在飞书或 Chat Lab 中发送：

```
帮我读取飞书文档 doc_xxxxx 的内容
```

### 3. 查看日志

```bash
tail -f /tmp/restart*.log | grep -E "(feishu_tool|tool_call)"
```

## 当前限制

1. **仅支持创建操作**: 目前只实现了 create_document 和 create_spreadsheet
2. **无读取功能**: 无法读取现有文档内容
3. **无编辑功能**: 无法修改现有文档
4. **无权限管理**: 无法管理文档权限
5. **无云空间操作**: 无法浏览/管理云空间文件

## 下一步行动

**立即可做:**

1. 配置 Gateway 加载飞书插件
2. 修改 `feishu_tools.py` 通过 Gateway 调用所有工具
3. 测试完整的工具集

**长期优化:**

1. 实现高频工具的 Python 版本
2. 添加工具使用统计
3. 优化错误处理和重试逻辑

## 参考文档

- TypeScript 实现: `/channel/feishu/src/`
- Skill 定义: `/channel/feishu/skills/`
- 飞书 API 文档: https://open.feishu.cn/document/

## 总结

✅ **核心架构完成** - 飞书通道已集成，工具注册系统就绪
🚧 **工具实现进行中** - 2/46 工具已实现，建议通过 Gateway 快速集成剩余工具
📝 **文档已整理** - 所有飞书相关文档移至 `docs/feishu/` 目录

现在系统可以创建飞书文档和表格，但要实现完整功能（读取、编辑、权限管理等），建议通过 Gateway 调用 TypeScript 实现的工具。
