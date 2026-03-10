"""
Dynamic gateway tool discovery.

Scans the OpenClaw gateway's TypeScript source tree (src/agents/tools/)
at startup and extracts tool names + descriptions. Provides:
  - A system prompt listing available gateway tools
  - A single `invoke_gateway` OpenAI function-calling tool definition
  - Runtime invocation via the gateway's /tools/invoke HTTP endpoint
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent-firewall.gateway-tools")


@dataclass(frozen=True)
class GatewayToolDef:
    """A gateway tool discovered from the source tree."""

    name: str
    description: str
    source_file: str


class GatewayToolRegistry:
    """
    Auto-discovers gateway tools from the OpenClaw TypeScript source.

    Scans src/agents/tools/*.ts for `name: "xxx"` + `description: "..."`
    patterns to build a registry of available tools.
    """

    def __init__(self, tools_source_dir: str | Path | None = None) -> None:
        if tools_source_dir is None:
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            tools_source_dir = repo_root / "src" / "agents" / "tools"
        self._source_dir = Path(tools_source_dir)
        self._repo_root = Path(__file__).resolve().parent.parent.parent.parent
        self._tools: dict[str, GatewayToolDef] = {}

    def discover(self) -> None:
        """Scan TypeScript tool source files for name + description."""
        self._tools.clear()

        # Scan core tools directory
        if self._source_dir.is_dir():
            self._scan_directory(self._source_dir)
        else:
            logger.warning("Gateway tools source dir not found: %s", self._source_dir)

        # Scan plugin directories (channel/*/src/*.ts)
        channel_dir = self._repo_root / "channel"
        if channel_dir.is_dir():
            for plugin_dir in channel_dir.iterdir():
                if plugin_dir.is_dir():
                    plugin_src = plugin_dir / "src"
                    if plugin_src.is_dir():
                        self._scan_directory(plugin_src)

        logger.info(
            "Gateway tools discovered: %d (%s)",
            len(self._tools),
            ", ".join(sorted(self._tools.keys())),
        )

    def _scan_directory(self, directory: Path) -> None:
        """Scan a single directory for tool definitions."""
        # Utility/helper files that are NOT tool definitions
        skip_names = {
            "common.ts",
            "web-shared.ts",
            "web-fetch-utils.ts",
            "nodes-utils.ts",
            "sessions-helpers.ts",
            "sessions-access.ts",
            "sessions-resolution.ts",
            "sessions-send-helpers.ts",
            "sessions-announce-target.ts",
            "image-tool.helpers.ts",
            "browser-tool.schema.ts",
            "agent-step.ts",
            # Plugin helper files
            "accounts.ts",
            "client.ts",
            "channel.ts",
            "runtime.ts",
            "tool-account.ts",
            "tools-config.ts",
            "config-schema.ts",
            "monitor.ts",
            "bot.ts",
            "send.ts",
            "media.ts",
            "probe.ts",
            "reactions.ts",
            "mention.ts",
            "typing.ts",
            "targets.ts",
            "policy.ts",
            "onboarding.ts",
            "outbound.ts",
            "reply-dispatcher.ts",
            "send-message.ts",
            "send-result.ts",
            "send-target.ts",
            "streaming-card.ts",
            "tool-result.ts",
            "tool-factory-test-harness.ts",
            "dedup.ts",
            "directory.ts",
            "external-keys.ts",
            "feishu-command-handler.ts",
            "secret-input.ts",
            "dynamic-agent.ts",
            "async.ts",
            "post.ts",
        }

        for fpath in sorted(directory.iterdir()):
            if not fpath.name.endswith(".ts"):
                continue
            if fpath.name in skip_names:
                continue
            if ".test." in fpath.name or ".e2e." in fpath.name:
                continue
            if fpath.name.endswith("-schema.ts"):
                continue

            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            # Extract all tool name: "xxx" patterns from file
            name_matches = list(re.finditer(r'name:\s*"([a-z_]+)"', text))
            if not name_matches:
                continue

            for nm in name_matches:
                tool_name = nm.group(1)
                if tool_name in self._tools:
                    continue  # already found in another file

                # Find the nearest description after this name
                desc = self._extract_description(text, nm.start(), nm.end())
                self._tools[tool_name] = GatewayToolDef(
                    name=tool_name,
                    description=desc,
                    source_file=str(fpath),
                )

    def _extract_description(self, text: str, name_start: int, name_end: int) -> str:
        """Extract the description string near a tool's name definition."""
        # Strategy 1: Look for inline description (description: "..." / `...` / '...')
        search_region = text[name_end : name_end + 5000]
        inline_patterns = [
            r'description:\s*"([^"]+)"',
            r"description:\s*`([^`]+)`",
            r"description:\s*'([^']+)'",
        ]
        for pattern in inline_patterns:
            m = re.search(pattern, search_region)
            if m:
                desc = m.group(1).strip()
                # For long multi-line descriptions, keep only the first sentence/line
                first_line = desc.split("\n")[0].strip()
                if first_line:
                    desc = first_line
                desc = re.sub(r"\s+", " ", desc)
                return desc[:300]

        # Strategy 2: description is an array of strings → join first entry
        arr_match = re.search(r'description:\s*\[\s*"([^"]+)"', search_region)
        if arr_match:
            desc = arr_match.group(1).strip()
            desc = re.sub(r"\s+", " ", desc)
            return desc[:300]

        # Strategy 3: description is a variable defined earlier in the file
        before_tool = text[:name_start]
        var_patterns = [
            # Ternary: extract the last (default) branch
            r'const\s+description\s*=\s*.*?:\s*"([^"]+)";\s*$',
            r'const\s+description\s*=\s*"([^"]+)"',
            r"const\s+description\s*=\s*`([^`]+)`",
        ]
        for pattern in var_patterns:
            matches = list(re.finditer(pattern, before_tool, re.MULTILINE | re.DOTALL))
            if matches:
                desc = matches[-1].group(1).strip()
                first_line = desc.split("\n")[0].strip()
                if first_line:
                    desc = first_line
                desc = re.sub(r"\s+", " ", desc)
                return desc[:300]

        # Also check before the name
        before_region = text[max(0, name_start - 1000) : name_start]
        for pattern in inline_patterns:
            m = re.search(pattern, before_region)
            if m:
                desc = m.group(1).strip()
                desc = re.sub(r"\s+", " ", desc)
                return desc[:300]

        # Strategy 4: Look for baseDescription or *Description variables in the whole file
        desc_var_patterns = [
            r'const\s+\w*[Dd]escription\s*=\s*"([^"]+)"',
            r"const\s+\w*[Dd]escription\s*=\s*`([^`]+)`",
        ]
        for pattern in desc_var_patterns:
            m = re.search(pattern, text)
            if m:
                desc = m.group(1).strip()
                first_line = desc.split("\n")[0].strip()
                if first_line:
                    desc = first_line
                desc = re.sub(r"\s+", " ", desc)
                return desc[:300]

        # Strategy 5: Use label field as fallback
        label_match = re.search(r'label:\s*"([^"]+)"', search_region)
        if label_match:
            return label_match.group(1)

        return ""

    @property
    def tools(self) -> dict[str, GatewayToolDef]:
        return dict(self._tools)

    def get_tool(self, name: str) -> GatewayToolDef | None:
        return self._tools.get(name)

    # ── OpenAI tool definition ───────────────────────────────────

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """
        Return a single `invoke_gateway` tool for calling any gateway tool.

        The LLM selects the tool_name and constructs arguments based on
        the system prompt (which lists all tools + descriptions).
        """
        if not self._tools:
            return []

        tool_names = sorted(self._tools.keys())

        return [
            {
                "type": "function",
                "function": {
                    "name": "invoke_gateway",
                    "description": (
                        "Invoke an OpenClaw gateway tool. "
                        f"Available tools: {', '.join(tool_names)}. "
                        "Check the system prompt for tool descriptions and expected arguments."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tool_name": {
                                "type": "string",
                                "description": (
                                    f"Gateway tool to invoke. One of: {', '.join(tool_names)}"
                                ),
                                "enum": tool_names,
                            },
                            "arguments": {
                                "type": "object",
                                "description": (
                                    "Arguments to pass to the tool as a JSON object. "
                                    "Refer to tool descriptions for expected fields."
                                ),
                            },
                        },
                        "required": ["tool_name"],
                    },
                },
            },
        ]

    # ── System prompt ────────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """
        Build a compact system prompt describing available gateway tools.

        The LLM reads this to understand what tools exist and how to call them
        via `invoke_gateway(tool_name, arguments)`.
        """
        if not self._tools:
            return ""

        parts = [
            "# Available Gateway Tools",
            "",
            "Use `invoke_gateway(tool_name, arguments)` to call these OpenClaw gateway tools.",
            "Pass arguments as a JSON object with the expected fields for each tool.",
            "",
            "## Feishu Tools Usage",
            "",
            "Feishu tools use an `action` parameter to specify the operation:",
            "- **feishu_doc**: `{\"action\": \"create\", \"title\": \"...\", \"owner_open_id\": \"ou_xxx\"}` or `{\"action\": \"read\", \"doc_token\": \"...\"}` or `{\"action\": \"write\", \"doc_token\": \"...\", \"content\": \"markdown...\"}`",
            "- **feishu_drive**: `{\"action\": \"list\"}` or `{\"action\": \"create_folder\", \"name\": \"...\"}` or `{\"action\": \"info\", \"file_token\": \"...\", \"type\": \"docx\"}`",
            "- **feishu_wiki**: `{\"action\": \"spaces\"}` or `{\"action\": \"create\", \"space_id\": \"...\", \"title\": \"...\"}`",
            "- **feishu_perm**: `{\"action\": \"list\", \"token\": \"...\", \"type\": \"docx\"}` or `{\"action\": \"add\", \"token\": \"...\", \"type\": \"docx\", \"member_type\": \"email\", \"member_id\": \"...\", \"perm\": \"edit\"}`",
            "- **feishu_chat**: `{\"action\": \"info\", \"chat_id\": \"...\"}` or `{\"action\": \"members\", \"chat_id\": \"...\"}`",
            "- **feishu_bitable_***: Direct parameters like `{\"url\": \"...\"}` or `{\"app_token\": \"...\", \"table_id\": \"...\", \"fields\": {...}}`",
            "",
            "## All Tools",
            "",
        ]

        for name in sorted(self._tools.keys()):
            t = self._tools[name]
            parts.append(f"- **{name}**: {t.description}")

        parts.append("")
        return "\n".join(parts)

    # ── Execution ────────────────────────────────────────────────

    @staticmethod
    async def execute(
        host: str,
        port: int,
        token: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Execute a tool via the OpenClaw gateway's /tools/invoke endpoint."""
        import httpx

        # Separate "action" from args if present (gateway expects top-level action)
        args = dict(arguments) if arguments else {}
        action = args.pop("action", None)

        body: dict[str, Any] = {"tool": tool_name, "args": args}
        if action is not None:
            body["action"] = action

        try:
            headers: dict[str, str] = {"content-type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"http://{host}:{port}/tools/invoke",
                    json=body,
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        result = data.get("result", {})
                        content = result.get("content", [])
                        if content:
                            text_parts = []
                            for c in content:
                                if isinstance(c, dict):
                                    text_parts.append(c.get("text", str(c)))
                                else:
                                    text_parts.append(str(c))
                            return "\n".join(text_parts)
                        return json.dumps(result, ensure_ascii=False)[:2000]
                    else:
                        err = data.get("error", {})
                        return (
                            f"[Gateway error] {err.get('type', 'unknown')}: "
                            f"{err.get('message', str(err))}"
                        )
                elif resp.status_code == 401:
                    return "[Gateway auth error]: Invalid or missing token"
                else:
                    return f"[Gateway HTTP {resp.status_code}]: {resp.text[:500]}"
        except Exception as e:
            return f"[Gateway execution error]: {e}"


# ── Module-level singleton ───────────────────────────────────────

_gateway_registry: GatewayToolRegistry | None = None


def get_gateway_tool_registry(
    tools_source_dir: str | Path | None = None,
) -> GatewayToolRegistry:
    """Get or create the global gateway tool registry."""
    global _gateway_registry
    if _gateway_registry is None:
        _gateway_registry = GatewayToolRegistry(tools_source_dir)
        _gateway_registry.discover()
    return _gateway_registry
