"""Restore the last known settings of a sleeping lock after a restart.

A battery lock (Raykube hc7n0urm) only reports its settings when HA
connects to it, so right after a restart they would show as unknown. The
last value HA knew is put back into the datapoint, marked as set by Home
Assistant (not reported by the lock), and is never sent to the lock. The
lock's own report replaces it as soon as it arrives.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.restore_state import RestoreEntity

from .tuya_ble import SOURCE_HOME_ASSISTANT, TuyaBLEDataPointType, TuyaBLEDevice


async def async_restore_datapoint(
    entity: RestoreEntity,
    device: TuyaBLEDevice,
    dp_id: int,
    dp_type: TuyaBLEDataPointType,
    value_from_state: Callable[[str], Any],
) -> bool:
    """Seed a datapoint from the entity's last state; True if restored."""
    if device.datapoints[dp_id] is not None:
        return False  # the lock already reported it
    last_state = await entity.async_get_last_state()
    if last_state is None or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False
    try:
        value = value_from_state(last_state.state)
    except (TypeError, ValueError):
        return False
    if value is None:
        return False
    device.datapoints._update_from_device(
        dp_id, time.time(), 0, dp_type, value, source=SOURCE_HOME_ASSISTANT
    )
    return True
