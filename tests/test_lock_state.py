"""Raykube lock entity state around commands, in a real HA core.

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.lock import LockState  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import frame  # noqa: E402

from custom_components.tuya_local_ble import lock as lock_platform  # noqa: E402
from custom_components.tuya_local_ble.devices import (  # noqa: E402
    TuyaBLECoordinator,
    get_device_product_info,
)
from custom_components.tuya_local_ble.tuya_ble import (  # noqa: E402
    TuyaBLEDevice,
    TuyaBLEDeviceCredentials,
)

UNLOCK_CHECK = base64.b64encode(
    bytes.fromhex("0001ffff") + b"12345678" + bytes.fromhex("01aabbccdd0000")
).decode()


def dp47_report(unlocked: bool) -> bytes:
    return bytes.fromhex("00000000400000" "2f010001" + ("01" if unlocked else "00"))


RECORD_REPORT = bytes.fromhex("00000000410000" "45000003000101")  # DP69 on connect


async def make_lock(hass: HomeAssistant):
    device = TuyaBLEDevice(None, SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="lock"))
    device._device_info = TuyaBLEDeviceCredentials(
        "uuid", "localkey12345678", "devid", "jtmspro", "hc7n0urm",
        "A1 Ultra", "A1 Ultra", "A1 Ultra", UNLOCK_CHECK,
    )
    physical = {"unlocked": False}
    sent: list[str] = []

    async def fake_send_packet(code, data, wait_for_response=True):
        sent.append(bytes(data)[:6].hex())

    async def fake_update():
        sent.append("status")
        device._parse_datapoints_v4(dp47_report(physical["unlocked"]))

    device._send_packet = fake_send_packet
    device.update = fake_update

    coordinator = TuyaBLECoordinator(hass, device)
    entity = lock_platform.TuyaBLELock(
        hass,
        coordinator,
        device,
        get_device_product_info(device),
        lock_platform.get_mapping_by_device(device)[0],
    )
    entity.hass = hass
    entity.entity_id = "lock.test"
    entity.async_write_ha_state = lambda: None
    coordinator.async_add_listener(entity._handle_coordinator_update)
    return device, entity, physical, sent


def state(entity) -> str:
    return LockState.LOCKED if entity.is_locked else LockState.UNLOCKED


def test_unrelated_report_after_command_does_not_restore_stale_state():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with patch.object(lock_platform, "RAYKUBE_STATE_REFRESH_DELAY", 0.2, create=True):
            device, entity, physical, sent = await make_lock(hass)
            device._parse_datapoints_v4(dp47_report(False))
            assert state(entity) == LockState.LOCKED

            physical["unlocked"] = True  # opened by hand, no report reaches HA
            await entity.async_unlock()
            assert state(entity) == LockState.UNLOCKED

            device._parse_datapoints_v4(RECORD_REPORT)  # unrelated report
            assert state(entity) == LockState.UNLOCKED

            await asyncio.sleep(0.5)
            assert "status" in sent  # real state requested after the command
            assert state(entity) == LockState.UNLOCKED
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_refresh_after_command_shows_real_state():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with patch.object(lock_platform, "RAYKUBE_STATE_REFRESH_DELAY", 0.2, create=True):
            device, entity, physical, sent = await make_lock(hass)
            device._parse_datapoints_v4(dp47_report(True))
            assert state(entity) == LockState.UNLOCKED

            # HA sends "lock", but the lock ends up unlocked (e.g. someone
            # turned it back by hand straight away).
            await entity.async_lock()
            assert state(entity) == LockState.LOCKED
            physical["unlocked"] = True

            await asyncio.sleep(0.5)
            assert sent.count("status") == 1
            assert state(entity) == LockState.UNLOCKED  # real state wins
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_quick_commands_refresh_once_after_the_last_one():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with patch.object(lock_platform, "RAYKUBE_STATE_REFRESH_DELAY", 0.3, create=True):
            device, entity, physical, sent = await make_lock(hass)
            device._parse_datapoints_v4(dp47_report(False))
            await entity.async_unlock()
            await asyncio.sleep(0.1)
            await entity.async_lock()
            await asyncio.sleep(0.6)
            assert sent.count("status") == 1
            assert state(entity) == LockState.LOCKED
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def startup_delays(delay: float, retry: float):
    return patch.multiple(
        lock_platform,
        RAYKUBE_STARTUP_REFRESH_DELAY=delay,
        RAYKUBE_STARTUP_REFRESH_RETRY=retry,
    )


def test_state_is_read_from_the_lock_after_restart():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with startup_delays(0.1, 0.1):
            device, entity, physical, sent = await make_lock(hass)
            await entity.async_added_to_hass()
            assert entity.is_locked is None  # unknown until the lock answers
            await asyncio.sleep(0.5)
            assert sent.count("status") == 1  # no retries once the state is known
            assert state(entity) == LockState.LOCKED
            await entity.async_will_remove_from_hass()
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_startup_read_is_retried_while_the_lock_is_out_of_reach():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with startup_delays(0.1, 0.1):
            device, entity, physical, sent = await make_lock(hass)
            answer = device.update
            attempts = []

            async def out_of_reach():
                attempts.append(1)
                if len(attempts) < 3:
                    raise TimeoutError
                await answer()

            device.update = out_of_reach
            physical["unlocked"] = True
            await entity.async_added_to_hass()
            await asyncio.sleep(1.0)
            assert len(attempts) == 3
            assert state(entity) == LockState.UNLOCKED
            await entity.async_will_remove_from_hass()
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_state_reported_before_the_entity_exists_is_shown():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        await hass.async_start()
        with startup_delays(0.1, 0.1):
            device, entity, physical, sent = await make_lock(hass)
            # Integration setup reads the lock before the platforms load.
            device._parse_datapoints_v4(dp47_report(True))
            entity2 = lock_platform.TuyaBLELock(
                hass, entity.coordinator, device,
                get_device_product_info(device),
                lock_platform.get_mapping_by_device(device)[0],
            )
            entity2.hass = hass
            entity2.entity_id = "lock.test2"
            entity2.async_write_ha_state = lambda: None
            assert entity2.is_locked is None
            await entity2.async_added_to_hass()
            assert state(entity2) == LockState.UNLOCKED
            await asyncio.sleep(0.3)
            assert "status" not in sent  # known state: no extra startup read
            await entity2.async_will_remove_from_hass()
        await hass.async_stop(force=True)

    asyncio.run(scenario())
