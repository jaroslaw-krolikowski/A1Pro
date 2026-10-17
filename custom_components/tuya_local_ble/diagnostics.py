"""Diagnostics download ("Download diagnostics") for Raykube A1 Pro (Tuya BLE) devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .commands import get_command_guard
from .const import DOMAIN, get_connection_mode
from .devices import TuyaBLEData
from .diagnostics_data import (
    SOURCE_LABELS,
    change_rows,
    connection_data,
    datapoint_rows,
    iso_time,
)
from .raykube import get_raykube_config

# Credentials and identifiers that could be used to control the device.
TO_REDACT = {
    "local_key",
    "uuid",
    "device_id",
    "ble_unlock_check",
    "login_key",
    "session_key",
    "auth_key",
    "access_id",
    "access_secret",
    "password",
}


def _masked_addresses(data: dict[str, Any]) -> dict[str, Any]:
    if "address" not in data:
        return dict(data)
    return {**data, "address": _masked_address(data["address"] or "")}


def _masked_address(address: str) -> str:
    """Keep the last three bytes of the MAC, enough to tell devices apart."""
    parts = address.split(":")
    if len(parts) != 6:
        return "**REDACTED**"
    return ":".join(["**"] * 3 + parts[3:])


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data: TuyaBLEData | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    result: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(_masked_addresses(entry.data), TO_REDACT),
            "options": async_redact_data(_masked_addresses(entry.options), TO_REDACT),
            "connection_mode": get_connection_mode(entry.options),
        },
    }
    if data is None:
        result["error"] = "integration not loaded"
        return result

    device = data.device
    config = get_raykube_config(device)
    result["device"] = {
        "address": _masked_address(device.address),
        "name": device.name,
        "category": device.category,
        "product_id": device.product_id,
        "product_name": device.product_name,
        "product_model": device.product_model,
        "device_version": device.device_version,
        "hardware_version": device.hardware_version,
        "protocol_version": device.protocol_version,
        "credentials_loaded": bool(device.local_key),
        "ble_unlock_check_loaded": bool(device.ble_unlock_check),
    }
    result["connection"] = connection_data(device, full=True)
    if config is not None:
        result["raykube"] = {
            "dps": config.dps,
            "beep_volume_options": config.beep_volume_options,
            "unmute_level": config.unmute_level,
            "calibrate_value": config.calibrate_value,
            "auto_lock_time_range": [config.auto_lock_time_min, config.auto_lock_time_max],
            "sleepy": config.sleepy,
        }
    # The lock entity's state: DP47 / passive lock events mirrored to DP118.
    state = device.datapoints[118]
    result["lock_state"] = (
        {
            "value": "unlocked" if state.value else "locked",
            "source": SOURCE_LABELS.get(state.source, state.source),
            "updated": iso_time(state.timestamp),
        }
        if state is not None
        else None
    )
    guard = get_command_guard(device)
    result["commands"] = {
        "pending": guard.pending,
        "last_calibration": iso_time(guard.last_calibration),
    }
    result["datapoints"] = datapoint_rows(device, config)
    result["recent_changes"] = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in change_rows(device, config)
    ]
    return result


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    return await async_get_config_entry_diagnostics(hass, entry)
