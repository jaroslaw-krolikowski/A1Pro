"""The Tuya BLE integration."""
from __future__ import annotations

from dataclasses import dataclass, field

import logging
from typing import Callable
from datetime import datetime, timedelta
from threading import Event, Thread
import time

from homeassistant.components.lock import (
    LockEntityDescription,
    LockEntity,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from homeassistant.const import (
    STATE_UNKNOWN,
)

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import SOURCE_HOME_ASSISTANT, TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)

# Raykube FD50 locks: after a lock/unlock command, ask the lock for its real
# state once the motor has finished (it reports DP47 ~7 s after a command).
RAYKUBE_STATE_REFRESH_DELAY = 12
# After a restart a sleeping lock reports nothing until it is contacted, so
# ask it for its state instead of showing "unknown" until the next command.
RAYKUBE_STARTUP_REFRESH_DELAY = 20
RAYKUBE_STARTUP_REFRESH_RETRY = 120
RAYKUBE_STARTUP_REFRESH_ATTEMPTS = 3

TuyaBLELockIsAvailable = Callable[["TuyaBLELock", TuyaBLEProductInfo], bool] | None

from typing import Any

@dataclass
class TuyaBLELockMapping:
    dp_id: int
    dp_id_lock: int
    dp_id_unlock: int
    dp_id_nop: int
    keep_connect_timer: int
    description: LockEntityDescription
    force_add: bool = True
    keep_connect: bool = False
    dp_type: TuyaBLEDataPointType | None = None
    is_available: TuyaBLELockIsAvailable = None
    value_means_locked: bool = False

@dataclass
class TuyaBLELockMapping(TuyaBLELockMapping):
    description: LockEntityDescription = field(
        default_factory=lambda: LockEntityDescription(
            key="push",
            translation_key="push",
        )
    )
    is_available: TuyaBLELockIsAvailable = 0

@dataclass
class TuyaBLECategoryLockMapping:
    products: dict[str, list[TuyaBLELockMapping]] | None = None
    mapping: list[TuyaBLELockMapping] | None = None


mapping: dict[str, TuyaBLECategoryLockMapping] = {
    "jtmspro": TuyaBLECategoryLockMapping(
        products={
            "rlyxv7pe":  # Gimdow Smart Lock
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    dp_id=47,
                    # refer to sdk, dp 52 is for deleting temp password
                    # should be safe as a dummy keep alive message
                    dp_id_nop=52,
                    keep_connect=True,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            "hc7n0urm":  # Raykube A1 Ultra TuyaOS FD50 lock
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    # V4 events are parsed, but the full state model is still unknown.
                    # The entity reflects successful remote unlock after V4 ACK.
                    dp_id=118,
                    dp_id_nop=52,
                    keep_connect=False,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            "y2yaegze":  # CTL20H SmartLock - TuyaOS FD50
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    # Physical DP47 is mirrored to synthetic DP118 by the
                    # Raykube V4 parser. 0=locked, 1=unlocked.
                    dp_id=118,
                    dp_id_nop=52,
                    keep_connect=False,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            "ikphogdj":  # HL Knob-2, TuyaOS FD50 transport
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    # Confirmed via HCI capture: dp 47 (lock_motor_state) is
                    # the reliable state signal, including autonomous
                    # auto-lock events - dp 46 (manual_lock) only fires on
                    # commanded actions. Polarity confirmed twice: dp47=1
                    # after unlock, dp47=0 after lock/auto-lock.
                    dp_id=47,
                    value_means_locked=False,
                    dp_id_nop=52,
                    keep_connect=False,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            "c6hfl8bt":  # MYPIN HS0358 cabinet lock, TuyaOS FD50 transport
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    # Same standardized jtmspro/FD50 DP schema as ikphogdj/
                    # hc7n0urm (dp 47 = lock_motor_state); polarity not yet
                    # confirmed against physical unlock/lock for this device.
                    dp_id=47,
                    value_means_locked=False,
                    dp_id_nop=52,
                    keep_connect=False,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
        }
    ), 
}


def get_mapping_by_device(device: TuyaBLEDevice) -> list[TuyaBLECategoryLockMapping]:
    category = mapping.get(device.category)
    if category is not None and category.products is not None:
        product_mapping = category.products.get(device.product_id)
        if product_mapping is not None:
            return product_mapping
        if category.mapping is not None:
            return category.mapping
        else:
            return []
    else:
        return []


class TuyaBLELock(TuyaBLEEntity, LockEntity):
    """Representation of a Tuya BLE Lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
        mapping: TuyaBLELockMapping,
    ) -> None:
        super().__init__(hass, coordinator, device, product, mapping.description)
        self._mapping = mapping
        self._current_state = STATE_UNKNOWN
        self._target_state = None
        self._commanded = False
        self._commanded_timer = None
        self._datapoint_nop = None
        self._isjammed = False
        self._unsub_state_refresh: CALLBACK_TYPE | None = None
        self._startup_refresh_attempts = 0
        self._keep_connect_stop = Event()
        self._keep_connect_thread: Thread | None = None
        self._update_attrs()
        if mapping.keep_connect:
            self._datapoint_nop = device.datapoints.get_or_create(
                self._mapping.dp_id_nop,
                TuyaBLEDataPointType.DT_BOOL,
                False,
            )
            self._keep_connect_thread = Thread(
                target=self.send_nop_request,
                name=f"tuya-ble-keep-connect-{device.address}",
                daemon=True,
            )
            self._keep_connect_thread.start()

    def send_nop_request(self):
        """Periodically touch a dummy DP to keep the BLE session alive."""
        while not self._keep_connect_stop.wait(self._mapping.keep_connect_timer):
            if self._datapoint_nop:
                self._hass.create_task(self._datapoint_nop.set_value(True))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # The status read during setup runs before this entity exists, so
        # take the state it already delivered instead of waiting for the
        # next report.
        self.update_device_state()
        self._update_attrs()
        if self._device.product_id in ("hc7n0urm", "y2yaegze"):
            self._schedule_startup_refresh(RAYKUBE_STARTUP_REFRESH_DELAY)

    async def async_will_remove_from_hass(self) -> None:
        """Stop keepalive thread when the entity is removed/reloaded."""
        if self._unsub_state_refresh is not None:
            self._unsub_state_refresh()
            self._unsub_state_refresh = None
        self._keep_connect_stop.set()
        thread = self._keep_connect_thread
        if thread is not None and thread.is_alive():
            await self._hass.async_add_executor_job(thread.join, 1.0)

    @property
    def is_locked(self) -> bool | None:
        """Return true if device is locked."""
        if self._current_state == STATE_UNKNOWN:
            return None
        return self._current_state == LockState.LOCKED

    @property
    def is_locking(self) -> bool:
        """Return true if device is locking."""
        return (
            self._current_state == LockState.UNLOCKED
            and self._target_state == LockState.LOCKED
            and self._commanded
        )

    @property
    def is_unlocking(self) -> bool:
        """Return true if device is unlocking."""
        return (
            self._current_state == LockState.LOCKED
            and self._target_state == LockState.UNLOCKED
            and self._commanded
        )

    @property
    def is_jammed(self) -> bool | None:
        """Return true if device is jammed."""
        return self._isjammed

    # Alarm properties
    @property
    def should_poll(self) -> bool: return False

    def _update_attrs(self) -> None:
        self._attr_is_locking = self.is_locking
        self._attr_is_unlocking = self.is_unlocking
        self._attr_is_locked = self.is_locked
        self._attr_is_unlocked = None if self.is_locked is None else not self.is_locked
        self._attr_is_jammed = self.is_jammed
        self._attr_changed_by = super().changed_by

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self._set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def _set_lock_state(self, state: str) -> None:
        self._target_state = state
        self._update_attrs()
        self.async_write_ha_state()

        if self._target_state == LockState.UNLOCKED:
            dp_id = self._mapping.dp_id_unlock
        else:
            dp_id = self._mapping.dp_id_lock

        datapoint = self._device.datapoints.get_or_create(
            dp_id,
            TuyaBLEDataPointType.DT_BOOL,
            False,
        )

        if self._device.product_id in ("hc7n0urm", "y2yaegze"):
            await datapoint.set_value(True)
            self._apply_raykube_commanded_state(self._target_state)
            return

        if self._device.product_id == "ikphogdj" and self._target_state == LockState.UNLOCKED:
            # Similar logic for ikphogdj. Also syncs the real
            # state datapoint locally (not just cosmetic _current_state) and
            # lingers briefly - fixes confirmed necessary for ikphogdj via
            # HCI capture
            await datapoint.set_value(True)
            state_value = False if self._mapping.value_means_locked else True
            self._device.datapoints._update_from_device(
                self._mapping.dp_id, time.time(), 0, TuyaBLEDataPointType.DT_BOOL, state_value,
                source=SOURCE_HOME_ASSISTANT,
            )
            self._current_state = LockState.UNLOCKED
            self._commanded = False
            self._isjammed = False
            self._update_attrs()
            self.async_write_ha_state()
            self._hass.create_task(self._device.linger_connected(30))
            return

        if self._device.product_id == "ikphogdj" and self._target_state == LockState.LOCKED:
            await datapoint.set_value(True)
            state_value = True if self._mapping.value_means_locked else False
            self._device.datapoints._update_from_device(
                self._mapping.dp_id, time.time(), 0, TuyaBLEDataPointType.DT_BOOL, state_value,
                source=SOURCE_HOME_ASSISTANT,
            )
            self._current_state = LockState.LOCKED
            self._commanded = False
            self._isjammed = False
            self._update_attrs()
            self.async_write_ha_state()
            self._hass.create_task(self._device.linger_connected(30))
            return

        #Gimdow need true to activate lock/unlock commands
        self._hass.create_task(datapoint.set_value(True))
        self._commanded = True
        self._commanded_timer = datetime.now()


    def _apply_raykube_commanded_state(self, state: str) -> None:
        """Show the commanded state until the lock reports its real one.

        The synthetic state DP is updated too: otherwise any unrelated
        report arriving before DP47 (e.g. the record DP sent on connect)
        would make update_device_state() restore the pre-command state.
        """
        self._device.datapoints._update_from_device(
            self._mapping.dp_id,
            time.time(),
            0,
            TuyaBLEDataPointType.DT_ENUM,
            1 if state == LockState.UNLOCKED else 0,
            source=SOURCE_HOME_ASSISTANT,
        )
        self._current_state = state
        self._commanded = False
        self._isjammed = False
        self._update_attrs()
        self.async_write_ha_state()
        self._schedule_state_refresh()

    @callback
    def _schedule_state_refresh(self) -> None:
        """Request a status snapshot once the motor has settled."""
        if self._unsub_state_refresh is not None:
            self._unsub_state_refresh()
        self._unsub_state_refresh = async_call_later(
            self._hass, RAYKUBE_STATE_REFRESH_DELAY, self._async_refresh_state
        )

    async def _async_refresh_state(self, _now: datetime) -> None:
        self._unsub_state_refresh = None
        try:
            await self._device.update()
        except Exception:  # noqa: BLE001 - best effort, the next report fixes it
            _LOGGER.debug(
                "%s: state refresh after lock command failed",
                self._device.address,
                exc_info=True,
            )

    @callback
    def _schedule_startup_refresh(self, delay: float) -> None:
        if self._unsub_state_refresh is not None:
            return  # a refresh after a command is already on its way
        self._unsub_state_refresh = async_call_later(
            self._hass, delay, self._async_startup_refresh
        )

    async def _async_startup_refresh(self, now: datetime) -> None:
        self._unsub_state_refresh = None
        if self._current_state != STATE_UNKNOWN:
            return
        self._startup_refresh_attempts += 1
        await self._async_refresh_state(now)
        # The answer arrives as a report; check again later and retry if the
        # lock was out of reach.
        if self._startup_refresh_attempts < RAYKUBE_STARTUP_REFRESH_ATTEMPTS:
            self._schedule_startup_refresh(RAYKUBE_STARTUP_REFRESH_RETRY)

    def update_device_state(self):
        datapoint = self._device.datapoints[self._mapping.dp_id]
        if datapoint:
            is_set = bool(datapoint.value)
            if self._mapping.value_means_locked:
                self._current_state = LockState.LOCKED if is_set else LockState.UNLOCKED
            else:
                self._current_state = LockState.UNLOCKED if is_set else LockState.LOCKED
            if self._commanded:
                if ( self._current_state != self._target_state):
                    if ( datetime.now() > self._commanded_timer + timedelta(seconds = 12) ):
                        self._isjammed = True
                        self._commanded = False
                else:
                    self._commanded = False
                    self._isjammed = False

    @callback
    def _handle_coordinator_update(self) -> None:
        self.update_device_state()
        self._update_attrs()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._device.product_id in ("hc7n0urm", "y2yaegze"):
            # Battery locks sleep and may not keep an active BLE connection between
            # commands. Allow Home Assistant to call unlock; the command path will
            # establish a connection on demand.
            return True
        if self._device.product_id == "ikphogdj":
            # Same reasoning as hc7n0urm above
            return True
        result = super().available
        if result and self._mapping.is_available:
            result = self._mapping.is_available(self, self._product)
        return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    mappings = get_mapping_by_device(data.device)
    entities: list[TuyaBLELock] = []
    # Raykube locks never get the DP52 keepalive (DP52 deletes temporary
    # passwords there); their connection mode is handled in __init__.py.
    # Gimdow keeps its hardcoded keep_connect=True.
    for mapping in mappings:
        runtime_mapping = mapping
        if runtime_mapping.force_add or data.device.datapoints.has_id(
            runtime_mapping.dp_id, runtime_mapping.dp_type
        ):
            entities.append(
                TuyaBLELock(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                    runtime_mapping,
                )
            )
    async_add_entities(entities)
