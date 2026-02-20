"""
OpenAI API Proxy Adapter — Intercepts and secures LLM traffic.

This module provides a `handle_openai_chat_completion` function that:
  1. Intercepts `POST /v1/chat/completions`.
  2. Extracts prompt content from the request body.
  3. Uses L1/L2 engines to analyze the prompt for malice/injection.
  4. Blocks dangerous requests or forwards safe ones to the upstream provider.
  5. Supports SSE streaming responses.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models import AuditEntry, Verdict, ThreatLevel
from ..engine.semantic_analyzer import SemanticAnalyzer
from ..engine.static_analyzer import StaticAnalyzer

logger = logging.getLogger("agent_firewall.openai")


class OpenAIAdapter:
    """
    Proxy adapter for OpenAI-compatible chat completion endpoints.
    """

    def __init__(
        self,
        upstream_base_url: str,
        static_analyzer: StaticAnalyzer,
        semantic_analyzer: SemanticAnalyzer,
    ) -> None:
        # Ensure upstream base URL doesn't have trailing slash
        self.upstream_url = upstream_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.static_analyzer = static_analyzer
        self.semantic_analyzer = semantic_analyzer

    async def close(self) -> None:
        await self.client.aclose()

    async def handle_chat_completion(self, request: Request) -> StreamingResponse:
        """
        Handle a POST /v1/chat/completions request.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        messages = body.get("messages", [])
        if not messages:
            # Pass through empty requests or just forward them
            pass

        # 1. Extract content for analysis
        # We analyze the last user message usually, or all new content.
        # For simplicity, let's concat all user messages.
        user_content = "\n".join(
            [m.get("content", "") for m in messages if m.get("role") == "user"]
        )

        # 2. L1 Analysis (Static)
        l1_result = self.static_analyzer.analyze(user_content)

        # Map L1 threat level to a verdict
        is_l1_blocked = l1_result.threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)

        if is_l1_blocked:
            reason = f"Static Analysis: {', '.join(l1_result.matched_patterns)}"
            logger.warning(f"BLOCKED (L1) request: {reason}")
            raise HTTPException(status_code=403, detail=f"Firewall Blocked: {reason}")

        # 3. L2 Analysis (Semantic)
        # Only run L2 if L1 didn't block (and if configured to do so)
        # The SemanticAnalyzer handles the "should I run?" logic internally or via config checks usually.
        l2_result = await self.semantic_analyzer.analyze(
            method="chat/completions", params=user_content, session_context=[]
        )

        # Map L2 threat level to a verdict
        is_l2_blocked = l2_result.threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)

        if is_l2_blocked:
            reason = f"Semantic Analysis: {l2_result.reasoning}"
            logger.warning(f"BLOCKED (L2) request: {reason}")
            raise HTTPException(status_code=403, detail=f"Firewall Blocked: {reason}")
        # but keep authorization if provided by the client (Gateway).
        upstream_headers = dict(request.headers)
        upstream_headers.pop("host", None)
        upstream_headers.pop("content-length", None)

        # We need to forward to the EXACT upstream endpoint.
        # Assuming upstream_base_url is "https://openrouter.ai/api/v1"
        target_url = f"{self.upstream_url}/chat/completions"

        req = self.client.build_request(
            "POST",
            target_url,
            headers=upstream_headers,
            json=body,
        )

        r = await self.client.send(req, stream=True)

        return StreamingResponse(
            r.aiter_raw(),
            status_code=r.status_code,
            headers=dict(r.headers),
            background=None,
        )
