"""
Feishu/Lark Channel Adapter for Agent Firewall.

This module provides a long-lived WebSocket connection to Feishu/Lark
to receive and send messages through the Agent Firewall security pipeline.

Architecture:
  1. WebSocket client connects to Feishu event stream
  2. Incoming messages are intercepted and analyzed by L1+L2 engines
  3. Approved messages are forwarded to the agent
  4. Agent responses are sent back to Feishu

Configuration via environment variables:
  - AF_FEISHU_APP_ID: Feishu App ID
  - AF_FEISHU_APP_SECRET: Feishu App Secret
  - AF_FEISHU_ENCRYPT_KEY: Event encryption key (optional)
  - AF_FEISHU_VERIFICATION_TOKEN: Event verification token (optional)
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from ..models import AnalysisResult, AuditEntry, DashboardEvent, Verdict

if TYPE_CHECKING:
    from ..engine.semantic_analyzer import SemanticAnalyzer
    from ..engine.static_analyzer import StaticAnalyzer

logger = logging.getLogger("agent_firewall.channels.feishu")


class FeishuConfig:
    """Feishu channel configuration."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        encrypt_key: str | None = None,
        verification_token: str | None = None,
        model: str = "anthropic/claude-3.5-sonnet",
        upstream_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        self.model = model
        self.upstream_url = upstream_url


class FeishuAdapter:
    """Feishu/Lark channel adapter with WebSocket event stream."""

    def __init__(
        self,
        config: FeishuConfig,
        static_analyzer: StaticAnalyzer,
        semantic_analyzer: SemanticAnalyzer,
        upstream_url: str,
        emit_dashboard_event: Callable[[DashboardEvent], Any],
        emit_audit_entry: Callable[[AuditEntry], Any],
    ) -> None:
        self.config = config
        self.static_analyzer = static_analyzer
        self.semantic_analyzer = semantic_analyzer
        self.upstream_url = upstream_url
        self.emit_dashboard = emit_dashboard_event
        self.emit_audit = emit_audit_entry
        self.client = lark.Client.builder().app_id(config.app_id).app_secret(
            config.app_secret
        ).build()
        self._running = False
        self._ws_client: Any = None
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._event_loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        """Start the Feishu WebSocket event listener in a separate thread."""
        if self._running:
            logger.warning("Feishu adapter already running")
            return

        self._running = True
        logger.info(f"Starting Feishu adapter (App ID: {self.config.app_id})")

        # Store the current event loop for async operations
        self._event_loop = asyncio.get_event_loop()

        # Create event handler with sync wrapper
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.verification_token or "",
            self.config.encrypt_key or "",
        ).register_p2_im_message_receive_v1(self._handle_message_sync).build()

        # Start WebSocket client
        self._ws_client = lark.ws.Client(
            self.config.app_id, self.config.app_secret, event_handler=event_handler
        )

        # Run in separate thread - lark SDK will create its own event loop
        def _run_ws() -> None:
            try:
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._ws_client.start()
            except Exception as e:
                logger.error(f"Feishu WebSocket thread error: {e}")
                # Don't set _running = False here, as SDK has auto-reconnect

        self._ws_thread = threading.Thread(target=_run_ws, daemon=True)
        self._ws_thread.start()
        logger.info("Feishu WebSocket started in background thread")

    async def stop(self) -> None:
        """Stop the Feishu WebSocket connection."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.close()
            except Exception as e:
                logger.error(f"Error closing Feishu WebSocket: {e}")
        if hasattr(self, "_ws_thread") and self._ws_thread.is_alive():
            # Give thread time to finish
            self._ws_thread.join(timeout=2.0)
        logger.info("Feishu adapter stopped")

    def _handle_message_sync(self, data: Any) -> None:  # noqa: ANN401
        """Synchronous wrapper for async message handler (called by lark SDK)."""
        if self._event_loop and self._event_loop.is_running():
            # Schedule the async handler in the main event loop
            asyncio.run_coroutine_threadsafe(
                self._handle_message(data), self._event_loop
            )
        else:
            logger.error("Event loop not available for message handling")

    async def _handle_message(self, data: Any) -> None:  # noqa: ANN401
        """Handle incoming Feishu message event with optimized security analysis."""
        start_time = time.time()
        try:
            event = data.event
            message = event.message
            sender = event.sender

            # Extract message content
            content_raw = message.content
            message_type = message.message_type
            chat_id = message.chat_id
            sender_id = sender.sender_id.open_id

            # Parse text content from JSON
            if message_type == "text":
                content_obj = json.loads(content_raw)
                text_content = content_obj.get("text", "")
            else:
                text_content = content_raw

            logger.info(
                f"📨 Feishu message: chat={chat_id}, sender={sender_id}, "
                f"type={message_type}, content={text_content[:50]}..."
            )

            # ── Step 1: Quick L1 Static Analysis (fast, <1ms) ──
            l1_result = self.static_analyzer.analyze(text_content)
            l1_patterns = l1_result.matched_patterns
            l1_threat = l1_result.threat_level

            # Quick block on L1 HIGH/CRITICAL
            if l1_threat.value in ("HIGH", "CRITICAL"):
                logger.warning(f"🚫 Blocked by L1: {', '.join(l1_patterns)}")
                await self.send_message(
                    chat_id,
                    f"⚠️ 消息被安全防火墙拦截：检测到高风险模式 {', '.join(l1_patterns)}",
                )
                return

            # ── Step 2: Forward to AI immediately (don't wait for L2) ──
            # L2 analysis will run in background for audit/monitoring
            try:
                ai_response = await self._call_upstream_ai(text_content, chat_id, sender_id)
                await self.send_message(chat_id, ai_response)
                logger.info(f"✅ Sent AI response to Feishu chat {chat_id}")
            except Exception as e:
                logger.error(f"Error calling upstream AI: {e}")
                await self.send_message(chat_id, f"❌ AI服务暂时不可用: {e}")

            # ── Step 3: L2 Analysis in background (for audit) ──
            # This runs async and doesn't block the response
            asyncio.create_task(self._background_l2_analysis(
                text_content, chat_id, sender_id, l1_result, start_time
            ))

        except Exception as e:
            logger.error(f"Error handling Feishu message: {e}", exc_info=True)

    async def _background_l2_analysis(
        self, text: str, chat_id: str, sender_id: str, l1_result: Any, start_time: float
    ) -> None:
        """Run L2 analysis in background for audit/monitoring."""
        try:
            l2_result = await self.semantic_analyzer.analyze(
                method="feishu.message",
                params={"text": text, "chat_id": chat_id},
                session_context=[],
            )

            # Build analysis result
            analysis = AnalysisResult(
                l1_matched_patterns=l1_result.matched_patterns,
                l1_threat_level=l1_result.threat_level,
                l2_is_injection=l2_result.is_injection,
                l2_confidence=l2_result.confidence,
                l2_reasoning=l2_result.reasoning,
            )

            # Determine verdict (for audit only, message already sent)
            if l1_result.threat_level.value in ("HIGH", "CRITICAL"):
                analysis.verdict = Verdict.BLOCK
                analysis.blocked_reason = f"L1 detected: {', '.join(l1_result.matched_patterns)}"
            elif l2_result.is_injection and l2_result.confidence > 0.8:
                analysis.verdict = Verdict.ESCALATE  # Flag for review
                analysis.blocked_reason = f"L2 injection detected: {l2_result.reasoning}"
            else:
                analysis.verdict = Verdict.ALLOW

            # Emit dashboard event
            await self.emit_dashboard(
                DashboardEvent(
                    event_type="feishu_message",
                    session_id=chat_id,
                    agent_id=f"feishu:{sender_id}",
                    method="feishu.message.receive",
                    payload_preview=text[:100],
                    analysis=analysis,
                    is_alert=(analysis.verdict != Verdict.ALLOW),
                )
            )

            # Emit audit entry
            response_time = (time.time() - start_time) * 1000
            await self.emit_audit(
                AuditEntry(
                    session_id=chat_id,
                    agent_id=f"feishu:{sender_id}",
                    method="feishu.message.receive",
                    params_summary=text[:200],
                    analysis=analysis,
                    verdict=analysis.verdict,
                    response_time_ms=response_time,
                )
            )

        except Exception as e:
            logger.error(f"Background L2 analysis failed: {e}")

    async def send_message(self, chat_id: str, content: str) -> bool:
        """Send a text message to Feishu chat."""
        try:
            request = CreateMessageRequest.builder().receive_id_type(
                "chat_id"
            ).request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(f'{{"text":"{content}"}}')
                .build()
            ).build()

            response = self.client.im.v1.message.create(request)

            if not response.success():
                logger.error(
                    f"Failed to send Feishu message: {response.code} - {response.msg}"
                )
                return False

            logger.info(f"Sent message to Feishu chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending Feishu message: {e}", exc_info=True)
            return False

    async def _call_upstream_ai(self, text: str, chat_id: str, sender_id: str) -> str:
        """Call upstream AI agent with user message through internal chat API."""
        try:
            # Call internal chat API to get full tool-calling capability
            response = await self._http_client.post(
                "http://127.0.0.1:9090/api/chat/send",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant in Feishu. You have access to various tools including Feishu document operations."},
                        {"role": "user", "content": text},
                    ],
                    "model": self.config.model,
                    "enable_tools": True,
                    "temperature": 0.7,
                },
                timeout=60.0,
            )
            response.raise_for_status()

            # Parse NDJSON stream to extract final response
            content_parts = []
            tool_calls_info = []

            for line in response.text.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "content":
                        content_parts.append(event.get("content", ""))
                    elif event.get("type") == "tool_call":
                        tc = event.get("tool_call", {})
                        tool_name = tc.get("tool_name", "")
                        result_preview = tc.get("result_preview", "")
                        if not tc.get("blocked"):
                            tool_calls_info.append(f"🔧 {tool_name}: {result_preview}")
                except json.JSONDecodeError:
                    continue

            # Combine tool calls and content
            final_response = ""
            if tool_calls_info:
                final_response += "\n".join(tool_calls_info) + "\n\n"
            final_response += "".join(content_parts)

            return final_response if final_response.strip() else "抱歉，我无法生成回复。"

        except Exception as e:
            logger.error(f"Upstream AI call failed: {e}")
            raise

    async def create_document(self, title: str, content: str, folder_token: str = "") -> str:
        """Create a Feishu document."""
        try:
            from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody

            request = CreateDocumentRequest.builder().request_body(
                CreateDocumentRequestBody.builder()
                .title(title)
                .folder_token(folder_token)
                .build()
            ).build()

            response = self.client.docx.v1.document.create(request)

            if not response.success():
                logger.error(f"Failed to create document: {response.code} - {response.msg}")
                return ""

            doc_id = response.data.document.document_id
            logger.info(f"Created Feishu document: {doc_id}")
            return doc_id

        except Exception as e:
            logger.error(f"Error creating Feishu document: {e}", exc_info=True)
            return ""

    async def create_spreadsheet(
        self, title: str, folder_token: str = ""
    ) -> str:
        """Create a Feishu spreadsheet (bitable)."""
        try:
            from lark_oapi.api.bitable.v1 import CreateAppRequest, CreateAppRequestBody

            request = CreateAppRequest.builder().request_body(
                CreateAppRequestBody.builder()
                .name(title)
                .folder_token(folder_token)
                .build()
            ).build()

            response = self.client.bitable.v1.app.create(request)

            if not response.success():
                logger.error(f"Failed to create spreadsheet: {response.code} - {response.msg}")
                return ""

            app_token = response.data.app.app_token
            logger.info(f"Created Feishu spreadsheet: {app_token}")
            return app_token

        except Exception as e:
            logger.error(f"Error creating Feishu spreadsheet: {e}", exc_info=True)
            return ""
