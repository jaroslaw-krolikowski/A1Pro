"""The Tuya BLE integration."""
from __future__ import annotations

import logging
import time

import voluptuous as vol

from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS, get_device

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

from .keyman import HASSTuyaBLEDeviceManager
from .const import DOMAIN
from .devices import TuyaBLECoordinator, TuyaBLEData, get_device_product_info

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.LOCK,
]

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_DATAPOINT = "set_datapoint"

DATAPOINT_TYPES = {
    "bool": TuyaBLEDataPointType.DT_BOOL,
    "value": TuyaBLEDataPointType.DT_VALUE,
    "enum": TuyaBLEDataPointType.DT_ENUM,
    "string": TuyaBLEDataPointType.DT_STRING,
    "raw": TuyaBLEDataPointType.DT_RAW,
}

SET_DATAPOINT_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("dp_id"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        vol.Required("type"): vol.In(list(DATAPOINT_TYPES)),
        vol.Required("value"): cv.string,
    }
)


def _convert_datapoint_value(dp_type: str, value: str) -> bool | int | str | bytes:
    match dp_type:
        case "bool":
            return cv.boolean(value)
        case "value" | "enum":
            return int(value)
        case "raw":
            return bytes.fromhex(value)
        case _:
            return value


async def _async_set_datapoint(hass: HomeAssistant, call: ServiceCall) -> None:
    """Write an arbitrary datapoint (advanced / DP discovery)."""
    device_entry = dr.async_get(hass).async_get(call.data["device_id"])
    addresses = {
        identifier[1]
        for identifier in (device_entry.identifiers if device_entry else ())
        if identifier[0] == DOMAIN
    }
    data: TuyaBLEData | None = next(
        (
            entry_data
            for entry_data in hass.data.get(DOMAIN, {}).values()
            if entry_data.device.address in addresses
        ),
        None,
    )
    if data is None:
        raise HomeAssistantError("Device is not a loaded Tuya Local BLE device")

    dp_id: int = call.data["dp_id"]
    dp_type = DATAPOINT_TYPES[call.data["type"]]
    try:
        value = _convert_datapoint_value(call.data["type"], call.data["value"])
    except (ValueError, vol.Invalid) as exc:
        raise HomeAssistantError(f"Invalid value for type {call.data['type']}") from exc

    datapoints = data.device.datapoints
    datapoint = datapoints[dp_id]
    if datapoint is None or datapoint.type != dp_type:
        datapoints._update_from_device(dp_id, time.time(), 0, dp_type, value)
        datapoint = datapoints[dp_id]
    await datapoint.set_value(value)
    data.coordinator.async_update_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tuya BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Tuya BLE device with address {address}"
        )
    manager = HASSTuyaBLEDeviceManager(hass, entry.options.copy())
    device = TuyaBLEDevice(manager, ble_device)
    await device.initialize()
    product_info = get_device_product_info(device)

    coordinator = TuyaBLECoordinator(hass, device)

    '''
    try:
        await device.update()
    except BLEAK_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(
            f"Could not communicate with Tuya BLE device with address {address}"
        ) from ex
    '''
    #hass.async_create_task(device.update())

    await device.update()
    
    last_raykube_advertisement_update = 0.0

    async def _async_update_raykube_from_advertisement() -> None:
        """Best-effort Raykube state refresh after a BLE advertisement."""
        try:
            await device.update()
        except BLEAK_EXCEPTIONS:
            _LOGGER.debug(
                "%s: Raykube advertisement-triggered update failed",
                address,
                exc_info=True,
            )
        except Exception:
            _LOGGER.debug(
                "%s: Raykube advertisement-triggered update failed unexpectedly",
                address,
                exc_info=True,
            )

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        nonlocal last_raykube_advertisement_update
        device.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )
        if device.product_id in ("hc7n0urm", "y2yaegze"):
            # Raykube locks do not push manual/keypad state changes while the
            # integration is disconnected. A fresh advertisement after a
            # physical action is the safest low-power cue we have to reconnect
            # and request status, without keeping a permanent BLE session open.
            now = time.monotonic()
            if now - last_raykube_advertisement_update >= 300:
                last_raykube_advertisement_update = now
                hass.async_create_task(_async_update_raykube_from_advertisement())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TuyaBLEData(
        entry.title,
        device,
        product_info,
        manager,
        coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_DATAPOINT):
        async def _handle_set_datapoint(call: ServiceCall) -> None:
            await _async_set_datapoint(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_DATAPOINT,
            _handle_set_datapoint,
            schema=SET_DATAPOINT_SCHEMA,
        )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await device.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (e.g. keep_connected) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: TuyaBLEData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.device.stop()

    return unload_ok
