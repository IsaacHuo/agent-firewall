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
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token


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

    async def start(self) -> None:
        """Start the Feishu WebSocket event listener in a separate thread."""
        if self._running:
            logger.warning("Feishu adapter already running")
            return

        self._running = True
        logger.info(f"Starting Feishu adapter (App ID: {self.config.app_id})")

        # Create event handler
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.verification_token or "",
            self.config.encrypt_key or "",
        ).register_p2_im_message_receive_v1(self._handle_message).build()

        # Start WebSocket client
        self._ws_client = lark.ws.Client(
            self.config.app_id, self.config.app_secret, event_handler=event_handler
        )

        # Run in separate thread with its own event loop
        def _run_ws() -> None:
            try:
                self._ws_client.start()
            except Exception as e:
                logger.error(f"Feishu WebSocket error: {e}")
                self._running = False

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

    async def _handle_message(self, data: Any) -> None:  # noqa: ANN401
        """Handle incoming Feishu message event with full security analysis."""
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

            # ── Step 1: L1 Static Analysis ──
            l1_patterns = self.static_analyzer.scan(text_content)
            l1_threat = self.static_analyzer.assess_threat_level(l1_patterns)

            # ── Step 2: L2 Semantic Analysis ──
            l2_result = await self.semantic_analyzer.analyze(
                method="feishu.message",
                params={"text": text_content, "chat_id": chat_id},
                session_context=[],
            )

            # ── Step 3: Policy Decision ──
            analysis = AnalysisResult(
                l1_matched_patterns=l1_patterns,
                l1_threat_level=l1_threat,
                l2_is_injection=l2_result.is_injection,
                l2_confidence=l2_result.confidence,
                l2_reasoning=l2_result.reasoning,
            )

            # Compute verdict
            if l1_threat.value in ("HIGH", "CRITICAL"):
                analysis.verdict = Verdict.BLOCK
                analysis.blocked_reason = f"L1 detected: {', '.join(l1_patterns)}"
            elif l2_result.is_injection and l2_result.confidence > 0.8:
                analysis.verdict = Verdict.BLOCK
                analysis.blocked_reason = f"L2 injection detected: {l2_result.reasoning}"
            else:
                analysis.verdict = Verdict.ALLOW

            # ── Step 4: Emit Dashboard Event ──
            await self.emit_dashboard(
                DashboardEvent(
                    event_type="feishu_message",
                    session_id=chat_id,
                    agent_id=f"feishu:{sender_id}",
                    method="feishu.message.receive",
                    payload_preview=text_content[:100],
                    analysis=analysis,
                    is_alert=(analysis.verdict != Verdict.ALLOW),
                )
            )

            # ── Step 5: Handle Verdict ──
            if analysis.verdict == Verdict.BLOCK:
                logger.warning(f"🚫 Blocked Feishu message: {analysis.blocked_reason}")
                await self.send_message(
                    chat_id,
                    f"⚠️ 消息被安全防火墙拦截：{analysis.blocked_reason}",
                )
                return

            # ── Step 6: Forward to AI Agent (upstream) ──
            try:
                ai_response = await self._call_upstream_ai(text_content, chat_id, sender_id)
                await self.send_message(chat_id, ai_response)
                logger.info(f"✅ Sent AI response to Feishu chat {chat_id}")
            except Exception as e:
                logger.error(f"Error calling upstream AI: {e}")
                await self.send_message(chat_id, f"❌ AI服务暂时不可用: {e}")

            # ── Step 7: Audit Log ──
            response_time = (time.time() - start_time) * 1000
            await self.emit_audit(
                AuditEntry(
                    session_id=chat_id,
                    agent_id=f"feishu:{sender_id}",
                    method="feishu.message.receive",
                    params_summary=text_content[:200],
                    analysis=analysis,
                    verdict=analysis.verdict,
                    response_time_ms=response_time,
                )
            )

        except Exception as e:
            logger.error(f"Error handling Feishu message: {e}", exc_info=True)

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
        """Call upstream AI agent with user message."""
        try:
            # Call upstream AI endpoint (assuming OpenAI-compatible API)
            response = await self._http_client.post(
                f"{self.upstream_url}/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant in Feishu."},
                        {"role": "user", "content": text},
                    ],
                    "metadata": {
                        "channel": "feishu",
                        "chat_id": chat_id,
                        "sender_id": sender_id,
                    },
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
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
