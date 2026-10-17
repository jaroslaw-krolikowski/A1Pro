"""Raykube A1 Ultra settings datapoints.

DP numbers follow the jtmspro schema of these locks (Tuya cloud DP list of
hc7n0urm, the tuya-local `raykube_a1promax_lock` profile and the hc7n0urm
status snapshot decoded in ShonP40/Tuya-BLE PR #39). Every DP id and the
volume levels can be overridden per device with a `raykube` block in
`tuya_local_ble/devices.json`; see docs/raykube-a1-ultra.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .tuya_ble import TuyaBLEDevice

RAYKUBE_PRODUCT_IDS = ("hc7n0urm", "rlyxv7pe")

# Battery locks that sleep between commands: their setting entities stay
# available and connect on demand.
RAYKUBE_SLEEPY_PRODUCT_IDS = ("hc7n0urm",)

DEFAULT_DPS: dict[str, int | None] = {
    "beep_volume": 31,  # enum, levels per product below
    "automatic_lock": 33,  # bool
    "auto_lock_time": 36,  # value, seconds (1..1800)
    "special_function": 68,  # enum: function1 = recalibrate
}

DEFAULT_BEEP_VOLUME_OPTIONS = ["mute", "low", "normal", "high"]
# Volume levels declared in the Tuya cloud model of each product.
PRODUCT_BEEP_VOLUME_OPTIONS = {
    "hc7n0urm": ["mute", "normal"],
}

# DPs that must never be shown in Home Assistant (unlock check codes, keys,
# credential management payloads).
SENSITIVE_DPS = (1, 2, 3, 54, 61, 70, 71, 72, 73)

# DP codes from the Tuya cloud model, for diagnostics. DPs reported over BLE
# but missing from the cloud model (e.g. 11, 34, 40, 76, 77) have no code.
PRODUCT_DP_CODES: dict[str, dict[int, str]] = {
    "hc7n0urm": {
        1: "unlock_method_create",
        2: "unlock_method_delete",
        3: "unlock_method_modify",
        9: "battery_state",
        16: "unlock_key",
        19: "unlock_ble",
        20: "lock_record",
        21: "alarm_lock",
        31: "beep_volume",
        33: "automatic_lock",
        36: "auto_lock_time",
        44: "rtc_lock",
        46: "manual_lock",
        47: "lock_motor_state",
        54: "synch_method",
        61: "remote_no_dp_key",
        62: "unlock_phone_remote",
        63: "unlock_voice_remote",
        68: "special_function",
        69: "record",
        70: "check_code_set",
        71: "ble_unlock_check",
        72: "unlock_record_check",
        73: "remote_pd_setkey_check",
        78: "special_control",
    },
}

# Enum value names (index order) from the Tuya cloud model.
PRODUCT_DP_ENUMS: dict[str, dict[int, list[str]]] = {
    "hc7n0urm": {
        9: ["high", "medium", "low", "poweroff"],
        21: ["low_battery", "power_off"],
        31: ["mute", "normal"],
        68: ["function1", "function2", "function3", "function4"],
    },
}


@dataclass
class RaykubeConfig:
    dps: dict[str, int | None]
    beep_volume_options: list[str]
    unmute_level: str
    calibrate_value: int
    auto_lock_time_min: int
    auto_lock_time_max: int
    sleepy: bool
    dp_codes: dict[int, str] = field(default_factory=dict)
    dp_enums: dict[int, list[str]] = field(default_factory=dict)

    def dp(self, feature: str) -> int | None:
        return self.dps.get(feature)

    def dp_name(self, dp_id: int) -> str:
        """Attribute-style name of a DP: dp_47_lock_motor_state or dp_11."""
        code = self.dp_codes.get(dp_id)
        return f"dp_{dp_id}_{code}" if code else f"dp_{dp_id}"


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
        options.get("beep_volume_options")
        or PRODUCT_BEEP_VOLUME_OPTIONS.get(device.product_id)
        or DEFAULT_BEEP_VOLUME_OPTIONS
    )
    unmute_level = options.get("unmute_level", "normal")
    if unmute_level not in volume_options or unmute_level == volume_options[0]:
        unmute_level = volume_options[-1]

    # Feature DPs remapped in devices.json name the DP after the feature.
    dp_codes = dict(PRODUCT_DP_CODES.get(device.product_id, {}))
    for feature, dp_id in dps.items():
        if dp_id and dp_id not in dp_codes:
            dp_codes[dp_id] = feature
    for dp_id, code in (options.get("dp_codes") or {}).items():
        dp_codes[int(dp_id)] = str(code)
    dp_enums = dict(PRODUCT_DP_ENUMS.get(device.product_id, {}))
    if dps.get("beep_volume"):
        dp_enums[dps["beep_volume"]] = volume_options

    return RaykubeConfig(
        dps=dps,
        beep_volume_options=volume_options,
        unmute_level=unmute_level,
        calibrate_value=int(options.get("calibrate_value", 0)),
        auto_lock_time_min=int(options.get("auto_lock_time_min", 1)),
        auto_lock_time_max=int(options.get("auto_lock_time_max", 1800)),
        sleepy=device.product_id in RAYKUBE_SLEEPY_PRODUCT_IDS,
        dp_codes=dp_codes,
        dp_enums=dp_enums,
    )
