"""Raykube A1 Pro / A1 Pro Max / A1 Ultra settings datapoints.

DP numbers follow the jtmspro schema of these locks (Tuya cloud DP list of
hc7n0urm, the tuya-local `raykube_a1promax_lock` profile and the hc7n0urm
status snapshot decoded in ShonP40/Tuya-BLE PR #39). Every DP id and the
volume levels can be overridden per device with a `raykube` block in
`tuya_local_ble/devices.json`; see docs/raykube-a1-pro.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tuya_ble import TuyaBLEDevice

RAYKUBE_PRODUCT_IDS = ("hc7n0urm", "rlyxv7pe")

# Battery locks that sleep between commands: their setting entities stay
# available and connect on demand.
RAYKUBE_SLEEPY_PRODUCT_IDS = ("hc7n0urm",)

DEFAULT_DPS: dict[str, int | None] = {
    "beep_volume": 31,  # enum: mute / low / normal / high
    "automatic_lock": 33,  # bool
    "auto_lock_time": 36,  # value, seconds
    "special_function": 68,  # enum: function1 = recalibrate
    # Unverified: DP11 is the only unexplained bool in the hc7n0urm status
    # snapshot. Override it once the arming DP is confirmed on the device.
    "arming": 11,
}

DEFAULT_BEEP_VOLUME_OPTIONS = ["mute", "low", "normal", "high"]

# DPs that must never be shown in Home Assistant (unlock check codes, keys,
# credential management payloads).
SENSITIVE_DPS = (1, 2, 3, 54, 61, 70, 71, 72, 73)


@dataclass
class RaykubeConfig:
    dps: dict[str, int | None]
    beep_volume_options: list[str]
    unmute_level: str
    calibrate_value: int
    auto_lock_time_min: int
    auto_lock_time_max: int
    sleepy: bool

    def dp(self, feature: str) -> int | None:
        return self.dps.get(feature)


def is_raykube(device: TuyaBLEDevice) -> bool:
    return device.category == "jtmspro" and device.product_id in RAYKUBE_PRODUCT_IDS


def get_raykube_config(device: TuyaBLEDevice) -> RaykubeConfig | None:
    """Return the Raykube settings config for a device, or None."""
    if not is_raykube(device):
        return None
    options = device.raykube_options

    dps = dict(DEFAULT_DPS)
    for feature, dp_id in (options.get("dps") or {}).items():
        # null / 0 disables the entity for that feature.
        dps[feature] = int(dp_id) if dp_id else None

    volume_options = list(
        options.get("beep_volume_options") or DEFAULT_BEEP_VOLUME_OPTIONS
    )
    unmute_level = options.get("unmute_level", "normal")
    if unmute_level not in volume_options or unmute_level == volume_options[0]:
        unmute_level = volume_options[-1]

    return RaykubeConfig(
        dps=dps,
        beep_volume_options=volume_options,
        unmute_level=unmute_level,
        calibrate_value=int(options.get("calibrate_value", 0)),
        auto_lock_time_min=int(options.get("auto_lock_time_min", 1)),
        auto_lock_time_max=int(options.get("auto_lock_time_max", 1800)),
        sleepy=device.product_id in RAYKUBE_SLEEPY_PRODUCT_IDS,
    )
