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
        api_key: str | None = None,
    ) -> None:
        # Ensure upstream base URL doesn't have trailing slash
        self.upstream_url = upstream_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.static_analyzer = static_analyzer
        self.semantic_analyzer = semantic_analyzer
        self.api_key = api_key

    async def close(self) -> None:
        await self.client.aclose()

    def _normalize_to_chat_completions(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        Convert OpenAI Responses API format to Chat Completions format.

        Responses API uses ``input`` (list of messages or a string),
        while Chat Completions uses ``messages``.  This normalizer
        ensures the upstream (OpenRouter / any OpenAI-compatible
        provider) always receives a well-formed Chat Completions body.
        """
        if "messages" in body:
            return body  # already in Chat Completions format

        if "input" not in body:
            return body  # nothing to convert

        raw_input = body["input"]

        # input can be a plain string or a list of message objects
        if isinstance(raw_input, str):
            messages = [{"role": "user", "content": raw_input}]
        elif isinstance(raw_input, list):
            messages = []
            for item in raw_input:
                if isinstance(item, str):
                    messages.append({"role": "user", "content": item})
                elif isinstance(item, dict):
                    messages.append(item)
        else:
            messages = [{"role": "user", "content": str(raw_input)}]

        # Build a new body with ``messages`` instead of ``input``
        converted = {k: v for k, v in body.items() if k != "input"}
        converted["messages"] = messages

        # Responses API uses ``instructions`` for the system prompt
        if "instructions" in converted:
            messages.insert(0, {"role": "system", "content": converted.pop("instructions")})

        return converted

    async def handle_chat_completion(self, request: Request) -> StreamingResponse:
        """
        Handle POST /v1/chat/completions **and** POST /v1/responses.

        If the incoming body uses the Responses API schema (``input``
        field), it is transparently converted to Chat Completions
        format before analysis and upstream forwarding.
        """
        try:
            body = await request.json()
            logger.info(f"Incoming payload: {json.dumps(body)}")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # Normalize: convert Responses API format → Chat Completions format
        body = self._normalize_to_chat_completions(body)

        messages = body.get("messages", [])
        if not messages:
            # Pass through empty requests or just forward them
            pass

        # 1. Extract content for analysis
        # We analyze the last user message usually, or all new content.
        # For simplicity, let's concat all user messages.
        # content can be a string OR a list of content parts (multi-modal format).
        def _extract_text(content: Any) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content) if content else ""

        user_content = "\n".join(
            [_extract_text(m.get("content", "")) for m in messages if m.get("role") == "user"]
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
        # Build clean upstream headers — only forward safe headers to avoid
        # 400 errors from hop-by-hop or internal headers leaking through.
        # Build minimal upstream headers — do NOT forward client headers to
        # avoid Cloudflare / upstream rejecting unexpected or malformed headers.
        upstream_headers: dict[str, str] = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        }
        if self.api_key:
            upstream_headers["Authorization"] = f"Bearer {self.api_key}"

        # Forward HTTP-Referer and X-Title if present (OpenRouter ranking)
        for h in ("http-referer", "x-title"):
            v = request.headers.get(h)
            if v:
                upstream_headers[h] = v

        # We need to forward to the EXACT upstream endpoint.
        target_url = f"{self.upstream_url}/chat/completions"

        logger.info(f"Forwarding to upstream: {target_url} model={body.get('model')}")

        req = self.client.build_request(
            "POST",
            target_url,
            headers=upstream_headers,
            json=body,
        )

        r = await self.client.send(req, stream=True)

        # Log non-2xx responses for debugging
        if r.status_code >= 400:
            error_body = await r.aread()
            logger.error(
                f"Upstream returned {r.status_code}: {error_body[:500].decode(errors='replace')}"
            )
            return StreamingResponse(
                iter([error_body]),
                status_code=r.status_code,
                headers={"content-type": r.headers.get("content-type", "application/json")},
            )

        # Only forward safe response headers — do NOT forward transport-level
        # headers like transfer-encoding, content-encoding, content-length as
        # they conflict with ASGI/uvicorn's own framing and cause broken streams.
        safe_response_headers: dict[str, str] = {}
        _SKIP_RESPONSE_HEADERS = frozenset(
            {
                "transfer-encoding",
                "content-encoding",
                "content-length",
                "connection",
                "keep-alive",
            }
        )
        for key, value in r.headers.items():
            if key.lower() not in _SKIP_RESPONSE_HEADERS:
                safe_response_headers[key] = value

        # Use aiter_bytes() to get decoded (decompressed) content, since we
        # stripped content-encoding above.
        return StreamingResponse(
            r.aiter_bytes(),
            status_code=r.status_code,
            headers=safe_response_headers,
        )
