"""Protocol tests for the Raykube (hc7n0urm) FD50 V4 report decoder and writes.

Run: pip install bleak bleak-retry-connector pycryptodome pytest && pytest tests
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "tuya_local_ble")
)

from tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice, TuyaBLEDeviceCredentials  # noqa: E402
from tuya_ble.const import TuyaBLECode  # noqa: E402

# Placeholder check value with the documented layout:
# 00 01 ff ff <8 ASCII digits> 01 <4 bytes> 00 00
UNLOCK_CHECK = base64.b64encode(
    bytes.fromhex("0001ffff") + b"12345678" + bytes.fromhex("01aabbccdd0000")
).decode()

# hc7n0urm status snapshot published in ShonP40/Tuya-BLE PR #39.
SNAPSHOT = bytes.fromhex(
    "000000003f0100"
    "0904000100"
    "2f01000101"
    "2804000101"
    "1f04000101"
    "4c01000100"
    "4d00000416000600"
    "2101000100"
    "240200040000000a"
    "2204000100"
    "4e01000100"
    "0b01000100"
)


def make_device(product_id: str = "hc7n0urm") -> TuyaBLEDevice:
    device = TuyaBLEDevice(None, SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="lock"))
    device._device_info = TuyaBLEDeviceCredentials(
        "uuid", "localkey12345678", "devid", "jtmspro", product_id,
        "Raykube", "A1 Ultra", "Smart lock", UNLOCK_CHECK,
        None,
    )
    return device


def capture_writes(device: TuyaBLEDevice) -> list[tuple[TuyaBLECode, bytes]]:
    sent: list[tuple[TuyaBLECode, bytes]] = []

    async def fake_send_packet(code, data, wait_for_response=True):
        sent.append((code, bytes(data)))

    device._send_packet = fake_send_packet
    return sent


def test_snapshot_is_decoded_strictly():
    device = make_device()
    updates = []
    device.register_callback(updates.append)
    device._parse_datapoints_v4(SNAPSHOT)

    dps = device.datapoints
    assert dps[47].type == TuyaBLEDataPointType.DT_BOOL and dps[47].value is True
    assert dps[118].value == 1  # unlocked
    assert dps[31].type == TuyaBLEDataPointType.DT_ENUM and dps[31].value == 1
    assert dps[33].value is False
    assert dps[36].type == TuyaBLEDataPointType.DT_VALUE and dps[36].value == 10
    assert dps[11].type == TuyaBLEDataPointType.DT_BOOL and dps[11].value is False
    assert dps[77].value == bytes.fromhex("16000600")
    assert len(updates) == 1 and len(updates[0]) == 12


def test_single_lock_state_report():
    device = make_device()
    device._parse_datapoints_v4(bytes.fromhex("00000000400000" "2f01000100"))
    assert device.datapoints[47].value is False
    assert device.datapoints[118].value == 0  # locked


def test_timestamped_report():
    device = make_device()
    device._parse_datapoints_v4(
        bytes.fromhex("00000000410000" "01" "6543210f" "2101000100")
    )
    assert device.datapoints[33].value is False


def test_raw_typed_volume_is_surfaced_as_enum():
    device = make_device()
    device._parse_datapoints_v4(bytes.fromhex("00000000420000" "1f00000102"))
    assert device.datapoints[31].type == TuyaBLEDataPointType.DT_ENUM
    assert device.datapoints[31].value == 2


def test_malformed_report_falls_back_without_error():
    device = make_device()
    device._parse_datapoints_v4(bytes.fromhex("0000000042000024020004000000"))
    assert device.datapoints[36] is None


def write(device, dp_id, dp_type, value):
    datapoint = device.datapoints.get_or_create(dp_id, dp_type, value)
    asyncio.run(datapoint.set_value(value))


def test_setting_writes_use_typed_v4_frames():
    device = make_device()
    sent = capture_writes(device)

    write(device, 33, TuyaBLEDataPointType.DT_BOOL, True)
    write(device, 36, TuyaBLEDataPointType.DT_VALUE, 30)
    write(device, 31, TuyaBLEDataPointType.DT_ENUM, 0)
    write(device, 68, TuyaBLEDataPointType.DT_ENUM, 0)
    write(device, 11, TuyaBLEDataPointType.DT_BOOL, True)

    assert all(code == TuyaBLECode.FUN_SENDER_DPS_V4 for code, _ in sent)
    assert [data.hex() for _, data in sent] == [
        "00000000" "01" "21" "01" "0001" "01",
        "00000000" "01" "24" "02" "0004" "0000001e",
        "00000000" "01" "1f" "04" "0001" "00",
        "00000000" "01" "44" "04" "0001" "00",
        "00000000" "01" "0b" "01" "0001" "01",
    ]


def test_lock_and_unlock_payloads_unchanged():
    device = make_device()
    sent = capture_writes(device)

    write(device, 46, TuyaBLEDataPointType.DT_BOOL, True)
    write(device, 6, TuyaBLEDataPointType.DT_BOOL, True)

    assert sent[0][1].hex() == "00000000012e00000101"
    assert sent[1][1] == (
        bytes.fromhex("000000000147000013ffff0001")
        + b"12345678"
        + bytes.fromhex("01aabbccdd0001")
    )


def test_keepalive_dp52_is_never_sent():
    device = make_device()
    sent = capture_writes(device)
    write(device, 52, TuyaBLEDataPointType.DT_BOOL, True)
    assert sent == []
