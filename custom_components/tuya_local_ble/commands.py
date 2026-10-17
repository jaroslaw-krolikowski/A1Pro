"""One lock command at a time for Raykube battery locks.

The lock serves one BLE command at a time, so commands sent in quick
succession used to queue up and run minutes later. Rules:

- lock is always accepted: it drops a pending unlock or calibration that
  has not reached the lock yet, and a second lock joins the first;
- unlock and calibration are refused while another command is pending;
- calibration is refused for CALIBRATION_COOLDOWN seconds after the last one.

Each write also has a deadline in the protocol layer
(TuyaBLEDevice.command_deadline); a command that misses it is dropped and
reported as an error instead of running later.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from weakref import WeakKeyDictionary

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice
from .tuya_ble.exceptions import TuyaBLECommandTimeoutError

COMMAND_LOCK = "lock"
COMMAND_UNLOCK = "unlock"
COMMAND_CALIBRATE = "calibrate"

CALIBRATION_COOLDOWN = 120


class LockCommandGuard:
    """Serialises the commands sent to one lock."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._kind: str | None = None
        self._last_calibration: float | None = None  # time.time()

    @property
    def pending(self) -> str | None:
        """Kind of the command still on its way to the lock."""
        if self._task is not None and not self._task.done():
            return self._kind
        return None

    @property
    def last_calibration(self) -> float | None:
        return self._last_calibration

    def calibration_blocked_for(self) -> float:
        """Seconds until calibration may run again (0 = now)."""
        if self._last_calibration is None:
            return 0.0
        return max(0.0, self._last_calibration + CALIBRATION_COOLDOWN - time.time())

    async def run(self, kind: str, send: Callable[[], Awaitable[None]]) -> None:
        pending = self.pending
        if pending is not None:
            if kind != COMMAND_LOCK:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_pending",
                    translation_placeholders={"command": pending},
                )
            if pending == COMMAND_LOCK:
                await self._wait(asyncio.shield(self._task))
                return
            # Lock wins: the pending unlock / calibration must not go out late.
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        if kind == COMMAND_CALIBRATE:
            blocked = self.calibration_blocked_for()
            if blocked > 0:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="calibration_cooldown",
                    translation_placeholders={"seconds": str(int(blocked) + 1)},
                )
            # Counted from the request: a calibration that timed out may still
            # have reached the lock.
            self._last_calibration = time.time()
        self._kind = kind
        self._task = asyncio.ensure_future(send())
        await self._wait(self._task)

    @staticmethod
    async def _wait(task: Awaitable[None]) -> None:
        try:
            await task
        except TuyaBLECommandTimeoutError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={"seconds": f"{exc.deadline:g}"},
            ) from exc
        except asyncio.CancelledError:
            if asyncio.current_task() is not None and asyncio.current_task().cancelling():
                raise  # our caller was cancelled
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_replaced"
            ) from None


_guards: WeakKeyDictionary[TuyaBLEDevice, LockCommandGuard] = WeakKeyDictionary()


def get_command_guard(device: TuyaBLEDevice) -> LockCommandGuard:
    guard = _guards.get(device)
    if guard is None:
        guard = _guards[device] = LockCommandGuard()
    return guard


async def async_calibrate(device: TuyaBLEDevice, dp_id: int, value: int) -> None:
    """Start the lock's calibration (special_function), once per cooldown."""
    async def send() -> None:
        datapoint = device.datapoints.get_or_create(
            dp_id, TuyaBLEDataPointType.DT_ENUM, value
        )
        await datapoint.set_value(value)

    await get_command_guard(device).run(COMMAND_CALIBRATE, send)
