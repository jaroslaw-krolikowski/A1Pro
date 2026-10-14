# Raykube A1 Ultra / A1 Pro Max TuyaOS FD50 lock

Adds experimental local BLE support for Raykube A1 Ultra / A1 Pro Max locks using TuyaOS FD50 BLE service.

## Tested device

- Category: `jtmspro`
- Product ID: `hc7n0urm`
- BLE service UUID: `0000fd50-0000-1000-8000-00805f9b34fb`
- GATT write characteristic: `00000001-0000-1001-8001-00805f9b07d0`
- GATT notify characteristic: `00000002-0000-1001-8001-00805f9b07d0`

## What works

- Discovery through the FD50 service UUID.
- Connection on BlueZ/Bleak without `AcquireNotify` conflicts by forcing StartNotify.
- Tuya BLE `DEVICE_INFO` handshake variant used by this lock.
- Local remote unlock through Tuya BLE V4 command framing.
- Basic V4 datapoint/event parsing for future state handling.

## Current limitation

Remote unlock and remote lock have both been physically verified. Remote unlock uses a device-specific `ble_unlock_check` V4 payload. Remote lock uses the `manual_lock` datapoint (`46`) in V4 framing.

Manual lock/keypad/physical-key state changes are best effort only by default. The lock can emit a passive V4 state event (`flags=0x00002f`, boolean value; observed as `true` for open/unlocked and `false` for closed/locked), but Home Assistant only sees that event while a BLE notify session is active. If the battery lock is asleep or the integration is disconnected between commands, no datapoint mapping can update the entity until the integration reconnects and receives a notification.

## Opt-in keep connected

Configure the device → **Keep connected (24/7)** (default: off).

| Mode | Behavior |
|---|---|
| Off (default) | Connect on demand for commands; advertisement-triggered refresh for best-effort reverse sync. Safer for flaky USB BLE adapters. |
| On | Persistent BLE session with periodic keepalive NOP (same idea as Gimdow `rlyxv7pe`). Better live reverse sync; preferred when using ESPHome BLE proxies. |

Reload is automatic after changing the option.

## Required `devices.json` fields

Use the same schema as other devices, with the Raykube product ID:

```json
{
  "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<device UUID>",
    "local_key": "<device local key>",
    "device_id": "<device ID>",
    "category": "jtmspro",
    "product_id": "hc7n0urm",
    "device_name": "Raykube A1 Ultra",
    "product_model": "A1 Ultra",
    "product_name": "Smart lock",
    "ble_unlock_check": "<base64 raw Tuya status value>"
  }
}
```

`ble_unlock_check` is the raw base64 status value reported by Tuya Cloud for the device. It is device-specific and is used to build the V4 remote-unlock command. You can obtain it from the Tuya IoT OpenAPI device details/status response where the status code is `ble_unlock_check`. If this field is missing, remote lock can still work but remote unlock cannot be built and will fail with a configuration error.

## Protocol notes

The official app trace showed that this lock differs from older Gimdow-style Tuya BLE locks:

- `DEVICE_INFO` is sent with payload `00 f3`.
- The first packet uses protocol marker `0x20`.
- The lock expects the encrypted `DEVICE_INFO` frame as one larger ATT write after MTU exchange; splitting it into 20-byte chunks timed out.
- Legacy `FUN_SENDER_DPS` boolean writes can be acknowledged at the BLE/session layer but do not actuate the motor.
- Remote unlock uses `FUN_SENDER_DPS_V4` (`0x0027`) framing.

The V4 state/event schema is not fully reverse-engineered yet. Remote unlock is generated from the device-specific `ble_unlock_check` value; remote lock uses `manual_lock` DP46 in V4 framing.
