"""The Tuya BLE integration."""
from __future__ import annotations

from typing_extensions import Final

DOMAIN: Final = "tuya_local_ble"

DEVICE_METADATA_UUIDS: Final = "uuids"

DEVICE_DEF_MANUFACTURER: Final = "Tuya"
SET_DISCONNECTED_DELAY = 10 * 60

CONF_UUID: Final = "uuid"
CONF_LOCAL_KEY: Final = "local_key"
CONF_CATEGORY: Final = "category"
CONF_PRODUCT_ID: Final = "product_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_PRODUCT_MODEL: Final = "product_model"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_BLE_UNLOCK_CHECK: Final = "ble_unlock_check"
# Optional devices.json block with Raykube A1 Ultra overrides (DP ids, volume
# levels, auto-lock range). See docs/raykube-a1-ultra.md.
CONF_RAYKUBE: Final = "raykube"
# Legacy boolean option, read as CONNECTION_MODE_PERMANENT when set.
CONF_KEEP_CONNECTED: Final = "keep_connected"

# How Home Assistant talks to a sleeping battery lock (Raykube hc7n0urm):
# - periodic: connect and read the state after an advertisement, at most
#   every PERIODIC_REFRESH_INTERVAL (default, the original behaviour);
# - advertisement_change: read the state as soon as the advertised data
#   changes (e.g. after a manual turn), with a slow periodic fallback;
# - permanent: keep the BLE session open and reconnect when it drops.
CONF_CONNECTION_MODE: Final = "connection_mode"
CONNECTION_MODE_PERIODIC: Final = "periodic"
CONNECTION_MODE_ADVERTISEMENT: Final = "advertisement_change"
CONNECTION_MODE_PERMANENT: Final = "permanent"
CONNECTION_MODES: Final = [
    CONNECTION_MODE_PERIODIC,
    CONNECTION_MODE_ADVERTISEMENT,
    CONNECTION_MODE_PERMANENT,
]
PERIODIC_REFRESH_INTERVAL: Final = 300  # s
ADVERTISEMENT_REFRESH_MIN_INTERVAL: Final = 10  # s between two reads
ADVERTISEMENT_FALLBACK_INTERVAL: Final = 1800  # s
PERMANENT_CHECK_INTERVAL: Final = 60  # s


def get_connection_mode(options) -> str:
    """Connection mode from the entry options (legacy keep_connected aware)."""
    mode = options.get(CONF_CONNECTION_MODE)
    if mode in CONNECTION_MODES:
        return mode
    if options.get(CONF_KEEP_CONNECTED):
        return CONNECTION_MODE_PERMANENT
    return CONNECTION_MODE_PERIODIC

CONF_CRED_FILE = DOMAIN + "/devices.json"

BATTERY_STATE_LOW: Final = "low"
BATTERY_STATE_NORMAL: Final = "normal"
BATTERY_STATE_HIGH: Final = "high"

BATTERY_NOT_CHARGING: Final = "not_charging"
BATTERY_CHARGING: Final = "charging"
BATTERY_CHARGED: Final = "charged"

CO2_LEVEL_NORMAL: Final = "normal"
CO2_LEVEL_ALARM: Final = "alarm"

FINGERBOT_MODE_PUSH: Final = "push"
FINGERBOT_MODE_SWITCH: Final = "switch"
FINGERBOT_MODE_PROGRAM: Final = "program"
FINGERBOT_BUTTON_EVENT: Final = "fingerbot_button_pressed"
