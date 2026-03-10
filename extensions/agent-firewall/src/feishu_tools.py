"""
Feishu Tools Integration - Proxy to OpenClaw Gateway.

This module was previously used to manually register Feishu tools.
Now all Feishu tools (doc, drive, perm, wiki, bitable, chat) are
automatically discovered from the TypeScript implementation via
the Gateway tool registry.

The feishu plugin is enabled in ~/.openclaw/openclaw.json and
all 46+ tools are available through the invoke_gateway mechanism.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("agent_firewall.feishu_tools")


class FeishuToolRegistry:
    """
    Legacy registry - now a no-op placeholder.

    All Feishu tools are handled by the Gateway tool discovery system.
    The TypeScript implementation in channel/feishu/src/ provides:
    - feishu_doc (18+ actions: read, write, append, create, list_blocks, etc.)
    - feishu_drive (5 actions: list, info, create_folder, move, delete)
    - feishu_perm (3 actions: list, add, remove)
    - feishu_wiki (6 actions: spaces, nodes, get, create, move, rename)
    - feishu_bitable (9 tools: get_meta, list_fields, list_records, create_record, etc.)
    - feishu_chat (2 actions: members, info)
    """

    def __init__(self, feishu_adapter=None) -> None:
        # No longer needed - tools are discovered from TypeScript source
        logger.info("FeishuToolRegistry initialized (tools handled by Gateway)")

    def get_tool_definitions(self) -> list:
        """Return empty list - tools are provided by Gateway registry."""
        return []

    async def invoke_tool(self, name: str, arguments: dict) -> dict:
        """Not used - tools are invoked via Gateway."""
        msg = f"Feishu tool {name} should be invoked via Gateway, not directly"
        raise NotImplementedError(msg)
