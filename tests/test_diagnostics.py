"""Diagnostics: datapoint sources and changes, connection info, the
diagnostic sensors and the "Download diagnostics" file.

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

import homeassistant.const as ha_const  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import frame  # noqa: E402

if not hasattr(ha_const, "UnitOfRatio"):
    # sensor.py targets a newer HA than the one pinned for the tests.
    ha_const.UnitOfRatio = SimpleNamespace(PARTS_PER_MILLION="ppm")

from custom_components.tuya_local_ble import diagnostics, sensor  # noqa: E402
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
from custom_components.tuya_local_ble.tuya_ble import tuya_ble as protocol  # noqa: E402
from custom_components.tuya_local_ble.tuya_ble.const import TuyaBLECode  # noqa: E402

# Same placeholder check value and hc7n0urm snapshot as test_raykube_fd50.
UNLOCK_CHECK = "AAH//zEyMzQ1Njc4Aaq7zN0AAA=="
SNAPSHOT = bytes.fromhex(
    "000000003f0100" "0904000100" "2f01000101" "2804000101" "1f04000101"
    "4c01000100" "4d00000416000600" "2101000100" "240200040000000a"
    "2204000100" "4e01000100" "0b01000100"
)

LOCAL_KEY = "localkey12345678"
UUID = "uuid-secret-0001"
DEVICE_ID = "devid-secret-01"


def make_device() -> TuyaBLEDevice:
    device = TuyaBLEDevice(None, SimpleNamespace(address="DC:23:51:D9:F4:94", name="lock"))
    device._device_info = TuyaBLEDeviceCredentials(
        UUID, LOCAL_KEY, DEVICE_ID, "jtmspro", "hc7n0urm",
        "A1 Ultra", "A1 Ultra", "A1 Ultra", UNLOCK_CHECK,
    )

    async def fake_send_packet(code, data, wait_for_response=True):
        pass

    device._send_packet = fake_send_packet
    return device


def test_sources_and_changes_are_recorded():
    device = make_device()
    device._parse_datapoints_v4(SNAPSHOT)
    dp36 = device.datapoints[36]
    assert dp36.source == SOURCE_DEVICE and dp36.value == 10
    assert device.datapoints.last_device_report is not None

    # Set from Home Assistant: HA is the source until the lock reports again.
    asyncio.run(dp36.set_value(45))
    assert dp36.source == SOURCE_HOME_ASSISTANT
    change = device.datapoints.changes[-1]
    assert (change.dp_id, change.old, change.new, change.source) == (36, 10, 45, SOURCE_HOME_ASSISTANT)

    device._parse_datapoints_v4(bytes.fromhex("00000000400000" "240200040000002d"))
    assert dp36.source == SOURCE_DEVICE  # confirmed by the lock, same value: no new change
    assert device.datapoints.changes[-1] is change

    # A command creates its DP locally: not a value reported by the lock.
    assert device.datapoints.get_or_create(46, TuyaBLEDataPointType.DT_BOOL, False).source == SOURCE_HOME_ASSISTANT


def test_connection_info_tracks_failures_and_frames():
    device = make_device()
    device._ble_device = SimpleNamespace(address=device.address, name="lock")

    async def not_found(*args, **kwargs):
        raise protocol.BleakNotFoundError()

    events = []
    device.register_connection_callback(lambda: events.append(device.connection.state))
    with patch.object(protocol, "establish_connection", not_found):
        with pytest.raises(protocol.BleakNotFoundError):
            asyncio.run(device._ensure_connected())
    info = device.connection
    assert info.state == "error"
    assert info.last_error == "all connection attempts failed"
    assert info.connect_attempts == 99 and info.failed_connections == 1
    assert events[0] == "connecting" and events[-1] == "error"

    device._handle_command_or_response(1, 0, TuyaBLECode.FUN_SENDER_DEVICE_STATUS, b"\x00")
    assert info.last_frame_received_code == "FUN_SENDER_DEVICE_STATUS"
    assert info.last_frame_received is not None
    device._disconnected(None)
    assert info.state == "disconnected" and info.last_disconnected is not None


async def setup_entities(hass: HomeAssistant, device: TuyaBLEDevice):
    coordinator = TuyaBLECoordinator(hass, device)
    config = get_raykube_config(device)
    product = get_device_product_info(device)
    entities = []
    for cls in (sensor.TuyaBLERaykubeDatapointsSensor, sensor.TuyaBLERaykubeConnectionSensor):
        entity = cls(hass, coordinator, device, product, config)
        entity.hass = hass
        entities.append(entity)
    return coordinator, entities


def test_diagnostic_sensors():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        device = make_device()
        _, (datapoints, connection) = await setup_entities(hass, device)
        device._parse_datapoints_v4(SNAPSHOT)
        device.datapoints._update_from_device(
            71, 0, 0, TuyaBLEDataPointType.DT_RAW, b"\x01secret"
        )
        await device.datapoints.get_or_create(46, TuyaBLEDataPointType.DT_BOOL, False).set_value(True)

        attrs = datapoints.extra_state_attributes
        assert datapoints.native_value == 12  # 11 snapshot DPs + DP71; not DP46 / DP118
        assert attrs["dp_47_lock_motor_state"] is True
        assert attrs["dp_31_beep_volume"] == "normal"
        assert attrs["dp_9_battery_state"] == "high"
        assert attrs["dp_36_auto_lock_time"] == 10
        assert attrs["dp_11"] is False  # not in the cloud model: no code
        assert not any(key.startswith("dp_71") for key in attrs)
        assert "dp_118" not in json.dumps(attrs)
        assert attrs["not_from_lock"] == ["dp_46_manual_lock"]
        assert attrs["last_report"] is not None
        assert attrs["recent_changes"][0].endswith("dp_46_manual_lock: false → true (home_assistant)")
        assert any("dp_47_lock_motor_state: — → true (device)" in line for line in attrs["recent_changes"])

        assert connection.native_value == "disconnected"
        device._connection_error("pairing request failed")
        assert connection.extra_state_attributes["last_error"] == "pairing request failed"
        assert connection.available
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_download_diagnostics_is_redacted():
    async def scenario():
        hass = HomeAssistant("/tmp")
        frame.async_setup(hass)
        device = make_device()
        coordinator, _ = await setup_entities(hass, device)
        device._parse_datapoints_v4(SNAPSHOT)
        device.datapoints._update_from_device(
            71, 0, 0, TuyaBLEDataPointType.DT_RAW, b"\x01secret"
        )
        entry = SimpleNamespace(
            entry_id="e1", title="Raykube", data={"address": device.address},
            options={"keep_connected": True, "local_key": LOCAL_KEY},  # legacy option
        )
        hass.data["tuya_local_ble"] = {
            "e1": SimpleNamespace(device=device, coordinator=coordinator)
        }
        result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
        dumped = json.dumps(result)
        for secret in (LOCAL_KEY, UUID, DEVICE_ID, UNLOCK_CHECK, "DC:23:51", b"\x01secret".hex()):
            assert secret not in dumped
        assert result["device"]["address"] == "**:**:**:D9:F4:94"
        assert result["entry"]["connection_mode"] == "permanent"
        assert result["device"]["ble_unlock_check_loaded"] is True
        rows = {row["id"]: row for row in result["datapoints"]}
        assert rows[47]["name"] == "dp_47_lock_motor_state" and rows[47]["source"] == "device"
        assert rows[71]["value"] == "**REDACTED**"
        assert 118 not in rows
        assert result["connection"]["state"] == "disconnected"
        assert result["recent_changes"][0]["dp"] == "dp_71_ble_unlock_check"
        assert result["recent_changes"][0]["new"] == "**REDACTED**"
        assert result["entry"]["options"].get("address") is None
        assert result["lock_state"] == {
            "value": "unlocked", "source": "device",
            "updated": result["lock_state"]["updated"],
        }
        assert result["commands"] == {"pending": None, "last_calibration": None}

        # The full MAC in the options (17.10 file) is masked as well.
        entry.options = {"address": device.address, "connection_mode": "periodic"}
        result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
        assert result["entry"]["options"]["address"] == "**:**:**:D9:F4:94"
        assert "DC:23:51" not in json.dumps(result)
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def advert(service: bytes, manufacturer: bytes, rssi: int):
    return SimpleNamespace(
        service_data={"0000fd50-0000-1000-8000-00805f9b34fb": service},
        manufacturer_data={0x07D0: manufacturer},
        rssi=rssi,
    )


def test_advertisement_changes_are_tracked_without_rssi():
    device = make_device()
    ble = SimpleNamespace(address=device.address, name="lock")
    events = []
    device.register_connection_callback(lambda: events.append(device.connection.advertisement_changes))

    assert device.set_ble_device_and_advertisement_data(ble, advert(b"\x01", b"\xaa", -70)) is False
    info = device.connection
    assert info.advertisement_changes == 0 and info.last_advertisement_change is None  # baseline only
    assert device.set_ble_device_and_advertisement_data(ble, advert(b"\x01", b"\xaa", -55)) is False  # RSSI only
    assert device.set_ble_device_and_advertisement_data(ble, advert(b"\x01", b"\xab", -55)) is True
    assert info.advertisement_changes == 1 and info.last_advertisement_change is not None
    assert "07d0=ab" in info.advertisement_data
    assert events == [0, 1]  # sensor updates only when the content changes


def test_status_read_decision_per_connection_mode():
    from custom_components.tuya_local_ble import status_read_due
    from custom_components.tuya_local_ble.const import get_connection_mode

    assert status_read_due("periodic", False, 301) and not status_read_due("periodic", True, 100)
    assert status_read_due("advertisement_change", True, 11)
    assert not status_read_due("advertisement_change", True, 5)  # debounced
    assert not status_read_due("advertisement_change", False, 600)
    assert status_read_due("advertisement_change", False, 1801)  # slow fallback
    assert not status_read_due("permanent", True, 10_000)

    assert get_connection_mode({}) == "periodic"
    assert get_connection_mode({"keep_connected": True}) == "permanent"
    assert get_connection_mode({"keep_connected": True, "connection_mode": "advertisement_change"}) == "advertisement_change"
    assert get_connection_mode({"connection_mode": "bogus"}) == "periodic"
