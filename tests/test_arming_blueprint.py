"""Run blueprints/automation/a1pro/lock_arming_alarm.yaml in a real HA core.

Skipped when homeassistant is not installed.
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

from homeassistant import config_entries, loader  # noqa: E402
from homeassistant.core import Context, HomeAssistant  # noqa: E402
from homeassistant.helpers import (  # noqa: E402
    area_registry,
    category_registry,
    device_registry,
    entity_registry,
    floor_registry,
    frame,
    issue_registry,
    label_registry,
)
from homeassistant.setup import async_setup_component  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = "a1pro/lock_arming_alarm.yaml"
LOCK = "lock.drzwi"
ARMED = "input_boolean.zamek_uzbrojony"


MUTE = "switch.drzwi_wyciszenie"


async def start_hass(config_dir: Path, **inputs) -> tuple[HomeAssistant, list]:
    """Start HA with the blueprint; returns hass and an ordered call log."""
    target = config_dir / "blueprints" / "automation" / BLUEPRINT
    target.parent.mkdir(parents=True)
    shutil.copy(ROOT / "blueprints" / "automation" / BLUEPRINT, target)

    hass = HomeAssistant(str(config_dir))
    frame.async_setup(hass)
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    for registry in (
        area_registry, category_registry, device_registry, entity_registry,
        floor_registry, issue_registry, label_registry,
    ):
        await registry.async_load(hass)
    await hass.async_start()

    calls: list[tuple[str, object]] = []
    for event in ("a1pro_notify", "a1pro_alarm", "a1pro_alarm_stop"):
        hass.bus.async_listen(event, lambda e, name=event: calls.append((name, None)))
    hass.services.async_register(
        "lock", "lock", lambda call: calls.append(("lock.lock", call.data["entity_id"]))
    )
    hass.services.async_register(
        "switch", "turn_off", lambda call: calls.append(("switch.turn_off", call.data["entity_id"]))
    )

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"zamek_uzbrojony": {}}}
    )
    hass.states.async_set(LOCK, "locked")
    blueprint_inputs = {
        "lock_entity": LOCK,
        "arming_entity": ARMED,
        "notify_actions": [{"event": "a1pro_notify"}],
        "alarm_actions": [{"event": "a1pro_alarm"}],
        "stop_actions": [{"event": "a1pro_alarm_stop"}],
        "repeat_interval": 2,
        "max_duration": 1,
        **inputs,
    }
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": {"use_blueprint": {"path": BLUEPRINT, "input": blueprint_inputs}}},
    )
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("automation")
    return hass, calls


async def arm(hass: HomeAssistant, on: bool) -> None:
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": ARMED}, blocking=True
    )


def names(calls: list) -> list[str]:
    return [name for name, _ in calls]


def test_manual_unlock_notifies_once_unmutes_relocks_and_stops_on_disarm(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path, relock=True, lock_mute_switch=MUTE)
        await arm(hass, True)
        # Lock reports a manual unlock: fresh context, no user / parent.
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(2.5)
        log = names(calls)
        assert log[:4] == ["a1pro_notify", "switch.turn_off", "lock.lock", "a1pro_alarm"]
        assert ("switch.turn_off", [MUTE]) in calls or ("switch.turn_off", MUTE) in calls
        assert log.count("a1pro_notify") == 1
        assert log.count("lock.lock") == 1  # relock once, not repeated
        assert log.count("a1pro_alarm") >= 2  # repeated every interval
        await arm(hass, False)
        await asyncio.sleep(0.2)
        count = log.count("a1pro_alarm")
        await asyncio.sleep(2.5)
        assert names(calls).count("a1pro_alarm") == count  # stopped
        assert names(calls).count("a1pro_alarm_stop") == 1
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_repeat_relock_locks_every_interval(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path, repeat_relock=True, lock_mute_switch=MUTE)
        await arm(hass, True)
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(2.5)
        assert names(calls).count("lock.lock") >= 2
        assert names(calls).count("switch.turn_off") == 1
        await arm(hass, False)
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_without_relock_or_mute_switch_only_notifies_and_alarms(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path)
        await arm(hass, True)
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(0.5)
        assert names(calls) == ["a1pro_notify", "a1pro_alarm"]
        await arm(hass, False)
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_unlock_from_home_assistant_does_not_alarm(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path, relock=True)
        await arm(hass, True)
        # Unlock requested by a user (UI / voice) and by an automation.
        hass.states.async_set(LOCK, "unlocked", context=Context(user_id="user1"))
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "locked", context=Context())
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "unlocked", context=Context(parent_id="automation1"))
        await asyncio.sleep(0.5)
        assert calls == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_manual_unlock_while_disarmed_does_not_alarm(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path, relock=True)
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(0.5)
        assert calls == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())
