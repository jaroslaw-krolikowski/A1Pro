"""Datapoint and connection data shared by the diagnostic sensors and the
"Download diagnostics" file.

Values of sensitive DPs (unlock check codes, keys, credential payloads) are
never returned.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .raykube import SENSITIVE_DPS, RaykubeConfig
from .tuya_ble import SOURCE_DEVICE, SOURCE_HOME_ASSISTANT, TuyaBLEDevice

# Synthetic lock-state DP mirrored from DP47; not a real device DP.
SYNTHETIC_DPS = (118,)

REDACTED = "**REDACTED**"

SOURCE_LABELS = {SOURCE_DEVICE: "device", SOURCE_HOME_ASSISTANT: "home_assistant"}


def iso_time(timestamp: float | None) -> str | None:
    """Local ISO time of a time.time() value."""
    if timestamp is None:
        return None
    return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).isoformat(
        timespec="seconds"
    )


def short_time(timestamp: float) -> str:
    return dt_util.as_local(datetime.fromtimestamp(timestamp, dt_util.UTC)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def dp_name(config: RaykubeConfig | None, dp_id: int) -> str:
    return config.dp_name(dp_id) if config else f"dp_{dp_id}"


def format_value(config: RaykubeConfig | None, dp_id: int, value: Any) -> Any:
    """Readable DP value: enum names, hex for raw bytes."""
    if dp_id in SENSITIVE_DPS:
        return REDACTED
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    names = config.dp_enums.get(dp_id) if config else None
    if names and isinstance(value, int) and not isinstance(value, bool):
        if 0 <= value < len(names):
            return names[value]
    return value


def visible(dp_id: int) -> bool:
    return dp_id not in SYNTHETIC_DPS


def datapoint_rows(device: TuyaBLEDevice, config: RaykubeConfig | None) -> list[dict]:
    """Every datapoint with its code, type, value, source and update time."""
    rows = []
    datapoints = device.datapoints
    for dp_id in sorted(datapoints._datapoints):
        if not visible(dp_id):
            continue
        datapoint = datapoints[dp_id]
        rows.append(
            {
                "id": dp_id,
                "name": dp_name(config, dp_id),
                "type": datapoint.type.name,
                "value": format_value(config, dp_id, datapoint.value),
                "source": SOURCE_LABELS.get(datapoint.source, datapoint.source),
                "updated": iso_time(datapoint.timestamp),
            }
        )
    return rows


def change_rows(
    device: TuyaBLEDevice, config: RaykubeConfig | None, limit: int | None = None
) -> list[dict]:
    """Recent value changes, newest first."""
    rows = []
    for change in reversed(device.datapoints.changes):
        if not visible(change.dp_id):
            continue
        rows.append(
            {
                "time": iso_time(change.timestamp),
                "dp": dp_name(config, change.dp_id),
                "old": format_value(config, change.dp_id, change.old),
                "new": format_value(config, change.dp_id, change.new),
                "source": SOURCE_LABELS.get(change.source, change.source),
                "_timestamp": change.timestamp,
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    return rows


def change_lines(
    device: TuyaBLEDevice, config: RaykubeConfig | None, limit: int
) -> list[str]:
    """Recent changes as one-line strings for a state attribute."""
    return [
        f"{short_time(row['_timestamp'])} {row['dp']}: "
        f"{_text(row['old'])} → {_text(row['new'])} ({row['source']})"
        for row in change_rows(device, config, limit)
    ]


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def connection_data(device: TuyaBLEDevice, full: bool = False) -> dict[str, Any]:
    """Connection state; full adds per-advertisement details (download only)."""
    info = device.connection
    data = {
        "state": info.state,
        "connection_mode": info.connection_mode,
        "last_connected": iso_time(info.last_connected),
        "last_disconnected": iso_time(info.last_disconnected),
        "last_error": info.last_error,
        "last_error_at": iso_time(info.last_error_at),
        "connect_attempts": info.connect_attempts,
        "failed_connections": info.failed_connections,
        "last_frame_received": iso_time(info.last_frame_received),
        "last_frame_received_code": info.last_frame_received_code,
        "last_frame_sent": iso_time(info.last_frame_sent),
        "last_frame_sent_code": info.last_frame_sent_code,
        "last_device_report": iso_time(device.datapoints.last_device_report),
        "last_advertisement_change": iso_time(info.last_advertisement_change),
        "advertisement_changes": info.advertisement_changes,
        "rssi": device.rssi,
    }
    if full:
        # Changes with every advertisement: kept out of the sensor.
        data["last_advertisement"] = iso_time(info.last_advertisement)
        data["advertisement_data"] = info.advertisement_data
    return data
