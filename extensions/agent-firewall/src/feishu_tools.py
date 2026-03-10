"""
Feishu MCP Tools - Expose Feishu capabilities as MCP tools.

This module registers Feishu document/spreadsheet creation tools
that can be invoked by AI agents through the MCP protocol.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .channels.feishu_adapter import FeishuAdapter

logger = logging.getLogger("agent_firewall.feishu_tools")


class FeishuToolRegistry:
    """Registry of Feishu tools exposed via MCP."""

    def __init__(self, feishu_adapter: FeishuAdapter) -> None:
        self.adapter = feishu_adapter
        self._tools = self._register_tools()

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """Register all Feishu tools with their schemas."""
        return {
            "feishu_create_document": {
                "name": "feishu_create_document",
                "description": "Create a new Feishu document with the given title and content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Document title",
                        },
                        "content": {
                            "type": "string",
                            "description": "Document content (markdown or plain text)",
                        },
                        "folder_token": {
                            "type": "string",
                            "description": "Optional folder token to create document in",
                            "default": "",
                        },
                    },
                    "required": ["title", "content"],
                },
            },
            "feishu_create_spreadsheet": {
                "name": "feishu_create_spreadsheet",
                "description": "Create a new Feishu spreadsheet (bitable) with the given title",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Spreadsheet title",
                        },
                        "folder_token": {
                            "type": "string",
                            "description": "Optional folder token to create spreadsheet in",
                            "default": "",
                        },
                    },
                    "required": ["title"],
                },
            },
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions for MCP tools/list."""
        return list(self._tools.values())

    async def invoke_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a Feishu tool by name."""
        if name == "feishu_create_document":
            doc_id = await self.adapter.create_document(
                title=arguments["title"],
                content=arguments["content"],
                folder_token=arguments.get("folder_token", ""),
            )
            return {
                "success": bool(doc_id),
                "document_id": doc_id,
                "message": f"Created document: {doc_id}" if doc_id else "Failed to create document",
            }

        if name == "feishu_create_spreadsheet":
            app_token = await self.adapter.create_spreadsheet(
                title=arguments["title"],
                folder_token=arguments.get("folder_token", ""),
            )
            return {
                "success": bool(app_token),
                "app_token": app_token,
                "message": f"Created spreadsheet: {app_token}" if app_token else "Failed to create spreadsheet",
            }

        msg = f"Unknown Feishu tool: {name}"
        raise ValueError(msg)
