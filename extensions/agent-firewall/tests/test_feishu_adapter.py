"""Tests for Feishu channel adapter."""

from __future__ import annotations

import pytest

from src.channels.feishu_adapter import FeishuAdapter, FeishuConfig


def test_feishu_config_creation() -> None:
    """Test FeishuConfig initialization."""
    config = FeishuConfig(
        app_id="test_app_id",
        app_secret="test_secret",
        encrypt_key="test_key",
        verification_token="test_token",
    )

    assert config.app_id == "test_app_id"
    assert config.app_secret == "test_secret"
    assert config.encrypt_key == "test_key"
    assert config.verification_token == "test_token"


def test_feishu_config_optional_fields() -> None:
    """Test FeishuConfig with optional fields."""
    config = FeishuConfig(
        app_id="test_app_id",
        app_secret="test_secret",
    )

    assert config.app_id == "test_app_id"
    assert config.app_secret == "test_secret"
    assert config.encrypt_key is None
    assert config.verification_token is None


def test_feishu_adapter_initialization() -> None:
    """Test FeishuAdapter initialization."""
    config = FeishuConfig(
        app_id="test_app_id",
        app_secret="test_secret",
    )

    adapter = FeishuAdapter(config, engine=None)  # type: ignore[arg-type]

    assert adapter.config == config
    assert adapter.client is not None
    assert adapter._running is False
