"""
Dynamic skill discovery and execution.

Scans the skills/ directory at startup, parses SKILL.md frontmatter,
and provides:
  - Tool definitions for LLM function-calling (OpenAI format)
  - A generic shell executor so the LLM can invoke any skill's CLI
  - Skill context injection for the system prompt
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("agent-firewall.skills")


@dataclass(frozen=True)
class SkillDef:
    """Parsed skill definition from SKILL.md frontmatter."""

    name: str
    description: str
    homepage: str
    emoji: str
    os_list: list[str]
    required_bins: list[str]
    skill_md_path: str  # absolute path to SKILL.md
    skill_md_content: str  # full markdown body (the usage instructions)


def _parse_skill_md(path: Path) -> SkillDef | None:
    """Parse a SKILL.md file and extract frontmatter + body."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Cannot read %s: %s", path, e)
        return None

    # Strip leading ```skill / ``` fences that wrap the whole file
    text = raw.strip()
    if text.startswith("```skill"):
        text = text[len("```skill") :].strip()
    if text.startswith("````skill"):
        text = text[len("````skill") :].strip()
    # Remove trailing fence
    if text.endswith("```"):
        text = text[: -len("```")].strip()
    if text.endswith("````"):
        text = text[: -len("````")].strip()

    # Extract YAML frontmatter between --- ... ---
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not fm_match:
        logger.debug("No frontmatter in %s", path)
        return None

    fm_raw, body = fm_match.group(1), fm_match.group(2)

    try:
        fm = yaml.safe_load(fm_raw)
    except Exception as e:
        logger.warning("Bad YAML in %s: %s", path, e)
        return None

    if not isinstance(fm, dict) or "name" not in fm:
        return None

    meta = fm.get("metadata", {})
    oc = meta.get("openclaw", {}) if isinstance(meta, dict) else {}

    return SkillDef(
        name=fm["name"],
        description=fm.get("description", ""),
        homepage=fm.get("homepage", ""),
        emoji=oc.get("emoji", "🔧"),
        os_list=oc.get("os", []),
        required_bins=oc.get("requires", {}).get("bins", []),
        skill_md_path=str(path),
        skill_md_content=body.strip(),
    )


class SkillRegistry:
    """
    Discovers skills from the skills/ directory and provides:
      - OpenAI function-calling tool definitions
      - Skill context for system prompts
      - Shell command execution for skill CLI tools
    """

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        if skills_dir is None:
            # Default: <repo_root>/skills/
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            skills_dir = repo_root / "skills"
        self._skills_dir = Path(skills_dir)
        self._skills: dict[str, SkillDef] = {}
        self._ready_skills: dict[str, SkillDef] = {}  # only skills whose bins are available

    def discover(self) -> None:
        """Scan skills directory and load all SKILL.md definitions."""
        self._skills.clear()
        self._ready_skills.clear()

        if not self._skills_dir.is_dir():
            logger.warning("Skills directory not found: %s", self._skills_dir)
            return

        current_os = platform.system().lower()  # 'darwin', 'linux', 'windows'

        count = 0
        for child in sorted(self._skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue

            skill = _parse_skill_md(skill_md)
            if skill is None:
                continue

            self._skills[skill.name] = skill

            # Check OS compatibility
            if skill.os_list and current_os not in skill.os_list:
                logger.debug(
                    "Skipping %s (os=%s, current=%s)", skill.name, skill.os_list, current_os
                )
                continue

            # Check required binaries
            bins_ok = all(shutil.which(b) for b in skill.required_bins)
            if not bins_ok:
                missing = [b for b in skill.required_bins if not shutil.which(b)]
                logger.debug("Skipping %s (missing bins: %s)", skill.name, missing)
                continue

            self._ready_skills[skill.name] = skill
            count += 1

        logger.info(
            "Skills discovered: %d total, %d ready (%s)",
            len(self._skills),
            len(self._ready_skills),
            ", ".join(sorted(self._ready_skills.keys())),
        )

    @property
    def ready_skills(self) -> dict[str, SkillDef]:
        return dict(self._ready_skills)

    @property
    def all_skills(self) -> dict[str, SkillDef]:
        return dict(self._skills)

    def get_skill(self, name: str) -> SkillDef | None:
        return self._ready_skills.get(name) or self._skills.get(name)

    # ── OpenAI tool definitions ──────────────────────────────────

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """
        Generate OpenAI function-calling tool definitions.

        Provides two tools:
          1. `get_skill_docs` — retrieve full SKILL.md docs for a skill (call before run_skill)
          2. `run_skill` — execute a shell command for a skill

        The LLM calls get_skill_docs first to learn the CLI, then run_skill to execute.
        """
        if not self._ready_skills:
            return []

        skill_names = sorted(self._ready_skills.keys())
        # Use simple list format for description to save tokens and reduce confusion
        skill_list_desc = ", ".join(skill_names)

        return [
            {
                "type": "function",
                "function": {
                    "name": "get_skill_docs",
                    "description": (
                        "Get the usage documentation for a specific skill. "
                        f"Available skills: {skill_list_desc}. "
                        "Call this FIRST to learn how to use a skill. "
                        "Supports fuzzy matching if exact name is not known."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "The name of the skill to inspect. Can be a keyword.",
                            },
                        },
                        "required": ["skill_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_skill",
                    "description": (
                        "Execute a skill's CLI command. "
                        "You MUST read the docs via `get_skill_docs` first to know the correct command syntax. "
                        "Do not guess flags or arguments."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "The skill to use.",
                                "enum": skill_names,
                            },
                            "command": {
                                "type": "string",
                                "description": "The full shell command string to run (e.g. 'feishu-doc create ...').",
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Why you are running this command.",
                            },
                        },
                        "required": ["skill_name", "command"],
                    },
                },
            },
        ]

    # ── Helpers ──────────────────────────────────────────────────

    def get_skill_docs(self, skill_name: str) -> str:
        """Get the full SKILL.md content for a skill (supports fuzzy match)."""
        # 1. Exact match
        skill = self._ready_skills.get(skill_name)
        if skill:
            header = f"# {skill.emoji} {skill.name}\n{skill.description}\n"
            if skill.required_bins:
                header += f"CLI binaries: {', '.join(skill.required_bins)}\n"
            header += "\n"
            return header + skill.skill_md_content

        # 2. Fuzzy match
        matches = []
        name_lower = skill_name.lower()
        for s in self._ready_skills.values():
            if name_lower in s.name.lower() or name_lower in s.description.lower():
                matches.append(s)
        
        if matches:
            # If only one match, return it directly? Maybe risky if ambiguous.
            # Better to return a list of suggestions.
            if len(matches) == 1:
                s = matches[0]
                return (
                    f"Skill '{skill_name}' not found, but found match: {s.name}.\n\n"
                    f"# {s.emoji} {s.name}\n{s.description}\n\n"
                    f"CLI binaries: {', '.join(s.required_bins)}\n\n"
                    f"{s.skill_md_content}"
                )
            
            # Multiple matches
            parts = [f"Skill '{skill_name}' not found. Did you mean one of these?"]
            for s in matches:
                parts.append(f"- **{s.name}**: {s.description}")
            return "\n".join(parts)

        # 3. No match
        available = ", ".join(sorted(self._ready_skills.keys()))
        return f"[Error] Skill '{skill_name}' not available. Ready skills: {available}"

    def get_skills_system_prompt(self) -> str:
        """
        Build a compact system prompt listing available skills.
        The LLM should call get_skill_docs to learn the full CLI before using run_skill.
        """
        if not self._ready_skills:
            return ""

        parts = [
            "# Available Skills",
            "",
            "You have access to `get_skill_docs` and `run_skill` tools for the following skills.",
            "Workflow: call `get_skill_docs(skill_name)` first to learn the CLI, "
            "then `run_skill(skill_name, command)` to execute.",
            "",
        ]

        for name in sorted(self._ready_skills.keys()):
            skill = self._ready_skills[name]
            bins = f" (CLI: {', '.join(skill.required_bins)})" if skill.required_bins else ""
            parts.append(f"- **{skill.emoji} {skill.name}**: {skill.description}{bins}")

        parts.append("")
        return "\n".join(parts)

    # ── Execution ────────────────────────────────────────────────

    async def execute_skill(
        self,
        skill_name: str,
        command: str,
        timeout: float = 60.0,
    ) -> str:
        """
        Execute a shell command for a skill.
        Returns stdout+stderr output, truncated to 4000 chars.
        """
        skill = self._ready_skills.get(skill_name)
        if not skill:
            available = ", ".join(sorted(self._ready_skills.keys()))
            return f"[Error] Skill '{skill_name}' not available. Ready skills: {available}"

        # Security: reject obviously dangerous patterns
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]
        cmd_lower = command.lower()
        for d in dangerous:
            if d in cmd_lower:
                return f"[BLOCKED] Dangerous command pattern detected: {d}"

        logger.info("Executing skill %s: %s", skill_name, command[:200])

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output_parts = []
            stdout_text = stdout.decode(errors="replace").strip()
            stderr_text = stderr.decode(errors="replace").strip()

            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text and proc.returncode != 0:
                output_parts.append(f"[stderr] {stderr_text}")

            output = "\n".join(output_parts) if output_parts else "(no output)"

            if proc.returncode != 0:
                output = f"[exit code {proc.returncode}] {output}"

            return output[:4000]

        except asyncio.TimeoutError:
            return f"[Timeout] Command did not complete within {timeout}s"
        except Exception as e:
            return f"[Execution error] {e}"


# ── Module-level singleton ───────────────────────────────────────

_registry: SkillRegistry | None = None


def get_skill_registry(skills_dir: str | Path | None = None) -> SkillRegistry:
    """Get or create the global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry(skills_dir)
        _registry.discover()
    return _registry
