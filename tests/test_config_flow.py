"""Config flow started from "Add integration" (user step) in a real HA core.

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant import config_entries, loader  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import (  # noqa: E402
    area_registry,
    category_registry,
    device_registry,
    entity_registry,
    floor_registry,
    frame,
    issue_registry,
    label_registry,
)

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "tuya_local_ble"
FD50 = "0000fd50-0000-1000-8000-00805f9b34fb"
LOCK_MAC = "DC:23:51:00:00:01"


def service_info(address: str, uuid: str, name: str = "TY") -> SimpleNamespace:
    return SimpleNamespace(
        address=address,
        service_data={uuid: b"\x00"},
        device=SimpleNamespace(name=name),
    )


async def start_hass(config_dir: Path, devices_json: dict | None) -> HomeAssistant:
    shutil.copytree(
        ROOT / "custom_components" / DOMAIN,
        config_dir / "custom_components" / DOMAIN,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if devices_json is not None:
        (config_dir / DOMAIN).mkdir()
        (config_dir / DOMAIN / "devices.json").write_text(json.dumps(devices_json))

    hass = HomeAssistant(str(config_dir))
    hass.config.skip_pip = True
    frame.async_setup(hass)
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    for registry in (
        area_registry, category_registry, device_registry, entity_registry,
        floor_registry, issue_registry, label_registry,
    ):
        await registry.async_load(hass)
    await hass.async_start()
    return hass


CREDENTIALS = {
    LOCK_MAC: {
        "address": LOCK_MAC,
        "uuid": "uuid",
        "local_key": "localkey12345678",
        "device_id": "devid",
        "category": "jtmspro",
        "product_id": "hc7n0urm",
        "device_name": "A1 Ultra",
        "product_model": "A1 Ultra",
        "product_name": "A1 Ultra",
    }
}


async def init_user_flow(hass: HomeAssistant, discovered: list) -> dict:
    with patch(
        "custom_components.tuya_local_ble.config_flow.async_discovered_service_info",
        return_value=discovered,
    ), patch(
        "homeassistant.setup.async_process_deps_reqs", return_value=None
    ), patch(
        # bluetooth_adapters / frontend / http cannot start in this bare core.
        "homeassistant.setup._async_process_dependencies", return_value=[]
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )


def test_user_step_lists_fd50_lock_and_creates_entry(tmp_path):
    async def scenario():
        hass = await start_hass(tmp_path, CREDENTIALS)
        result = await init_user_flow(
            hass,
            [
                service_info(LOCK_MAC, FD50),
                service_info("AA:AA:AA:AA:AA:AA", "0000180f-0000-1000-8000-00805f9b34fb"),
            ],
        )
        assert result["type"] == "form" and result["step_id"] == "device"
        options = result["data_schema"].schema["address"].container
        assert list(options) == [LOCK_MAC]  # FD50 lock listed, unrelated device not
        assert options[LOCK_MAC].startswith("Raykube A1 Ultra")

        with patch(
            "custom_components.tuya_local_ble.async_setup_entry", return_value=True
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"address": LOCK_MAC}
            )
        assert result["type"] == "create_entry"
        assert result["data"] == {"address": LOCK_MAC}
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_user_step_without_bluetooth_devices_aborts_with_hint(tmp_path):
    async def scenario():
        hass = await start_hass(tmp_path, CREDENTIALS)
        result = await init_user_flow(hass, [])
        assert result["type"] == "abort"
        assert result["reason"] == "no_unconfigured_devices"
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_missing_devices_json_shows_error_instead_of_crashing(tmp_path):
    async def scenario():
        hass = await start_hass(tmp_path, None)
        discovered = [service_info(LOCK_MAC, FD50)]
        result = await init_user_flow(hass, discovered)
        assert result["type"] == "form"
        with patch(
            "custom_components.tuya_local_ble.config_flow.async_discovered_service_info",
            return_value=discovered,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"address": LOCK_MAC}
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "device_not_registered"}
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_options_flow_sets_connection_mode_and_migrates_keep_connected(tmp_path):
    async def scenario():
        hass = await start_hass(tmp_path, CREDENTIALS)
        entry = config_entries.ConfigEntry(
            version=1, minor_version=1, domain=DOMAIN, title="Raykube",
            data={"address": LOCK_MAC}, source=config_entries.SOURCE_USER,
            options={"keep_connected": True, "local_key": "kept"},
            unique_id=LOCK_MAC, discovery_keys={}, subentries_data=None,
        )
        with patch(
            "custom_components.tuya_local_ble.async_setup_entry", return_value=True
        ), patch(
            "custom_components.tuya_local_ble.async_unload_entry", return_value=True
        ), patch(
            "homeassistant.setup._async_process_dependencies", return_value=[]
        ):
            await hass.config_entries.async_add(entry)
            result = await hass.config_entries.options.async_init(entry.entry_id)
            assert result["type"] == "form"
            schema = result["data_schema"].schema
            (key,) = schema
            assert key == "connection_mode"
            assert key.default() == "permanent"  # legacy keep_connected
            assert schema[key].config["options"] == ["periodic", "advertisement_change", "permanent"]

            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"connection_mode": "advertisement_change"}
            )
            await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert entry.options == {"local_key": "kept", "connection_mode": "advertisement_change"}
        await hass.async_stop(force=True)

    asyncio.run(scenario())
