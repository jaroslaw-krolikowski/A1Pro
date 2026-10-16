"""The integration serves and registers its Lovelace card.

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import HomeAssistant  # noqa: E402

import custom_components.tuya_local_ble as integration  # noqa: E402


def test_async_setup_serves_card_and_adds_it_to_frontend(tmp_path):
    async def scenario():
        hass = HomeAssistant(str(tmp_path))
        hass.http = MagicMock()
        hass.http.async_register_static_paths = AsyncMock()
        with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
            assert await integration.async_setup(hass, {})
        (paths,), _ = hass.http.async_register_static_paths.call_args
        assert paths[0].url_path == "/tuya_local_ble/raykube-lock-card.js"
        assert paths[0].path.endswith("frontend/raykube-lock-card.js")
        url = add_js.call_args.args[1]
        assert url.startswith("/tuya_local_ble/raykube-lock-card.js?v=")
        assert len(url.split("?v=")[1]) == 8
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_async_setup_without_http_is_a_no_op(tmp_path):
    async def scenario():
        hass = HomeAssistant(str(tmp_path))
        hass.http = None
        assert await integration.async_setup(hass, {})
        await hass.async_stop(force=True)

    asyncio.run(scenario())
