"""Settings of a sleeping lock are restored after a restart (HA core).

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

import homeassistant.const as ha_const  # noqa: E402
from homeassistant.core import HomeAssistant, State  # noqa: E402
from homeassistant import loader  # noqa: E402
from homeassistant.helpers import frame  # noqa: E402

if not hasattr(ha_const, "UnitOfRatio"):
    # number.py targets a newer HA than the one pinned for the tests.
    ha_const.UnitOfRatio = SimpleNamespace(PARTS_PER_MILLION="ppm")

from custom_components.tuya_local_ble import number, select, switch  # noqa: E402
from custom_components.tuya_local_ble.devices import (  # noqa: E402
    TuyaBLECoordinator,
    get_device_product_info,
)
from custom_components.tuya_local_ble.raykube import get_raykube_config  # noqa: E402
from custom_components.tuya_local_ble.tuya_ble import (  # noqa: E402
    SOURCE_DEVICE,
    SOURCE_HOME_ASSISTANT,
    TuyaBLEDataPointType,
    TuyaBLEDevice,
    TuyaBLEDeviceCredentials,
)

UNLOCK_CHECK = "AAH//zEyMzQ1Njc4Aaq7zN0AAA=="


def make_device() -> TuyaBLEDevice:
    device = TuyaBLEDevice(None, SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="lock"))
    device._device_info = TuyaBLEDeviceCredentials(
        "uuid", "localkey12345678", "devid", "jtmspro", "hc7n0urm",
        "A1 Ultra", "A1 Ultra", "A1 Ultra", UNLOCK_CHECK,
    )
    sent = []

    async def fake_send_packet(code, data, wait_for_response=True):
        sent.append(bytes(data))

    device._send_packet = fake_send_packet
    return device, sent


def settings_entities(hass, device):
    data = SimpleNamespace(
        device=device,
        coordinator=TuyaBLECoordinator(hass, device),
        product=get_device_product_info(device),
    )
    entities = (
        switch.get_raykube_switches(hass, data)
        + number.get_raykube_numbers(hass, data)
        + [
            e for e in select_entities(hass, data)
            if e.entity_description.key == "beep_volume"
        ]
    )
    for entity in entities:
        entity.hass = hass
        entity.async_write_ha_state = lambda: None  # no entity platform here
    return {entity.entity_description.key: entity for entity in entities}


def select_entities(hass, data):
    return [
        select.TuyaBLESelect(hass, data.coordinator, data.device, data.product, mapping)
        for mapping in select.get_mapping_by_device(data.device)
    ]


async def restore(entities, states: dict[str, str]):
    for key, entity in entities.items():
        last = State("x.y", states[key]) if key in states else None
        with patch.object(type(entity), "async_get_last_state", return_value=last):
            await entity.async_added_to_hass()


def test_settings_are_restored_but_never_sent():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        loader.async_setup(hass)
        device, sent = make_device()
        entities = settings_entities(hass, device)
        await restore(entities, {
            "automatic_lock": "on", "auto_lock_time": "30", "mute": "off", "beep_volume": "normal",
        })
        assert entities["automatic_lock"].is_on is True
        assert entities["auto_lock_time"].native_value == 30
        assert entities["beep_volume"].current_option == "normal"
        assert entities["mute"].is_on is False
        for dp_id in (31, 33, 36):
            assert device.datapoints[dp_id].source == SOURCE_HOME_ASSISTANT
        assert sent == []  # restoring writes nothing to the lock
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_muted_lock_restores_level_zero():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        loader.async_setup(hass)
        device, _ = make_device()
        entities = settings_entities(hass, device)
        await restore(entities, {"mute": "on", "beep_volume": "mute"})
        assert entities["mute"].is_on is True
        assert entities["beep_volume"].current_option == "mute"
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_values_from_the_lock_win_and_unknown_is_not_restored():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        loader.async_setup(hass)
        device, _ = make_device()
        device.datapoints._update_from_device(36, 0, 0, TuyaBLEDataPointType.DT_VALUE, 45)
        entities = settings_entities(hass, device)
        await restore(entities, {"auto_lock_time": "30", "automatic_lock": "unknown"})
        assert entities["auto_lock_time"].native_value == 45
        assert device.datapoints[36].source == SOURCE_DEVICE
        assert device.datapoints[33] is None
        assert entities["automatic_lock"].is_on is None
        await hass.async_stop(force=True)

    asyncio.run(scenario())
