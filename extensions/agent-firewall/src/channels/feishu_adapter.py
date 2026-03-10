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
import logging
from typing import TYPE_CHECKING, Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

if TYPE_CHECKING:
    from ..engine.interceptor import FirewallEngine

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

    def __init__(self, config: FeishuConfig, engine: FirewallEngine) -> None:
        self.config = config
        self.engine = engine
        self.client = lark.Client.builder().app_id(config.app_id).app_secret(
            config.app_secret
        ).build()
        self._running = False
        self._ws_client: Any = None

    async def start(self) -> None:
        """Start the Feishu WebSocket event listener."""
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

        try:
            await asyncio.to_thread(self._ws_client.start)
        except Exception as e:
            logger.error(f"Feishu WebSocket error: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the Feishu WebSocket connection."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.close()
            except Exception as e:
                logger.error(f"Error closing Feishu WebSocket: {e}")
        logger.info("Feishu adapter stopped")

    async def _handle_message(self, data: Any) -> None:  # noqa: ANN401
        """Handle incoming Feishu message event."""
        try:
            event = data.event
            message = event.message
            sender = event.sender

            # Extract message content
            content = message.content
            message_type = message.message_type
            chat_id = message.chat_id

            logger.info(
                f"Received Feishu message: type={message_type}, "
                f"chat={chat_id}, sender={sender.sender_id.open_id}"
            )

            # TODO: Pass through firewall engine for analysis
            # For now, just log
            logger.debug(f"Message content: {content}")

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
