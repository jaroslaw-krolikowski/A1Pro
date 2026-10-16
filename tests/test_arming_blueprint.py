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


async def start_hass(config_dir: Path) -> tuple[HomeAssistant, list]:
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

    calls: list[str] = []
    hass.bus.async_listen("a1pro_notify", lambda event: calls.append("notify"))
    # Any lock or switch service call would be a state change on the lock.
    for domain, service in (("lock", "lock"), ("lock", "unlock"), ("switch", "turn_on"), ("switch", "turn_off")):
        hass.services.async_register(
            domain, service, lambda call, name=f"{domain}.{service}": calls.append(name)
        )

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
                        "notify_actions": [{"event": "a1pro_notify"}],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("automation")
    return hass, calls


async def arm(hass: HomeAssistant, on: bool) -> None:
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": ARMED}, blocking=True
    )


def test_manual_unlock_while_armed_only_notifies(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path)
        await arm(hass, True)
        # Lock reports a manual unlock: fresh context, no user / parent.
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await hass.async_block_till_done()
        assert calls == ["notify"]  # no lock / switch service calls
        # A second manual unlock later notifies again.
        hass.states.async_set(LOCK, "locked", context=Context())
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await hass.async_block_till_done()
        assert calls == ["notify", "notify"]
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_unlock_from_home_assistant_does_not_notify(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path)
        await arm(hass, True)
        # Unlock requested by a user (UI / voice) and by an automation.
        hass.states.async_set(LOCK, "unlocked", context=Context(user_id="user1"))
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "locked", context=Context())
        await hass.async_block_till_done()
        hass.states.async_set(LOCK, "unlocked", context=Context(parent_id="automation1"))
        await hass.async_block_till_done()
        assert calls == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())


def test_manual_unlock_while_disarmed_does_not_notify(tmp_path):
    async def scenario():
        hass, calls = await start_hass(tmp_path)
        hass.states.async_set(LOCK, "unlocked", context=Context())
        await hass.async_block_till_done()
        assert calls == []
        await hass.async_stop(force=True)

    asyncio.run(scenario())
