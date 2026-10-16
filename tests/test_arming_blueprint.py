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


async def start_hass(config_dir: Path, relock: bool) -> tuple[HomeAssistant, list, list, list]:
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

    alarms, stops, relocks = [], [], []
    hass.bus.async_listen("a1pro_alarm", alarms.append)
    hass.bus.async_listen("a1pro_alarm_stop", stops.append)
    hass.services.async_register("lock", "lock", lambda call: relocks.append(call))

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"zamek_uzbrojony": {}}}
    )
    hass.states.async_set(LOCK, "locked")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": BLUEPRINT,
                    "input": {
                        "lock_entity": LOCK,
                        "arming_entity": ARMED,
                        "alarm_actions": [{"event": "a1pro_alarm"}],
                        "stop_actions": [{"event": "a1pro_alarm_stop"}],
                        "repeat_interval": 2,
                        "max_duration": 1,
                        "relock": relock,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.zamek_tryb_uzbrojenia_alarm_przy_recznym_otwarciu") or \
        hass.states.async_entity_ids("automation")
    return hass, alarms, stops, relocks


async def arm(hass: HomeAssistant, on: bool) -> None:
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": ARMED}, blocking=True
    )


def test_manual_unlock_while_armed_sounds_alarm_until_disarmed(tmp_path):
    async def scenario():
        hass, alarms, stops, relocks = await start_hass(tmp_path, relock=True)
        await arm(hass, True)
        # Lock reports a manual unlock: fresh context, no user / parent.
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(2.5)
        assert len(alarms) >= 2  # immediately and after one interval
        assert len(relocks) == 1
        assert relocks[0].data["entity_id"] in (LOCK, [LOCK])
        await arm(hass, False)
        await asyncio.sleep(0.2)
        count = len(alarms)
        await asyncio.sleep(2.5)
        assert len(alarms) == count  # stopped
        assert len(stops) == 1
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_unlock_from_home_assistant_does_not_alarm(tmp_path):
    async def scenario():
        hass, alarms, stops, relocks = await start_hass(tmp_path, relock=False)
        await arm(hass, True)
        # Unlock requested by a user (UI / voice) and by an automation.
        hass.states.async_set(LOCK, "unlocked", context=Context(user_id="user1"))
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "locked", context=Context())
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "unlocked", context=Context(parent_id="automation1"))
        await asyncio.sleep(0.5)
        assert alarms == [] and relocks == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_manual_unlock_while_disarmed_does_not_alarm(tmp_path):
    async def scenario():
        hass, alarms, stops, relocks = await start_hass(tmp_path, relock=True)
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await asyncio.sleep(0.5)
        assert alarms == [] and relocks == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())
