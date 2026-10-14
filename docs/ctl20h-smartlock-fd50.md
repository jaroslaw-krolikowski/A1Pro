# CTL20H SmartLock — TuyaOS FD50

Adds local BLE support for the CTL20H cabinet/drawer smart lock using Home Assistant and Tuya Local BLE.

## Tested device

- Category: `jtmspro`
- Product ID: `y2yaegze`
- Product name: `CTL20H SmartLock`
- Model: `CTL20H`
- Transport family: TuyaOS FD50 BLE

## What works

- Direct Bluetooth connection from Home Assistant
- Remote unlock from Home Assistant
- Remote/manual lock command path
- Physical locked/unlocked state reporting
- Correct state initialization after Home Assistant restart
- Automatic relock reflected in Home Assistant
- Battery percentage
- RSSI / signal strength

No Tuya Bluetooth gateway was required for the tested setup.

## Confirmed datapoints

### DP8 — battery percentage

DP8 is a Tuya `VALUE` and carries the battery percentage in the CTL20H startup bulk status snapshot.

Example:

```text
08 02 0004 0000002a
```

Decoded value: `42` percent.

A later live Home Assistant value of `40` percent confirmed that this is a live battery-percentage datapoint.

### DP47 — physical lock state

DP47 is a Tuya `BOOL` in the CTL20H startup status snapshot.

Encoding:

```text
2f 01 0001 00   -> locked
2f 01 0001 01   -> unlocked
```

Confirmed with physical testing:

- Home Assistant unlock command opened the lock and state became unlocked.
- The lock's normal automatic relock produced the locked state again.
- After Home Assistant restart while physically locked, DP47 initialized the entity correctly as locked.

The current Raykube-style lock entity uses synthetic DP118 as the state datapoint, so CTL20H DP47 is mirrored into DP118:

- DP47 `0` -> DP118 `0`
- DP47 `1` -> DP118 `1`

### DP6 — unlock

The existing Raykube-compatible V4 unlock path is used for CTL20H.

### DP46 — lock

The existing Raykube-compatible V4 manual-lock path is used for CTL20H.

## Example `devices.json`

Do not publish a real file. The values below are placeholders only.

```json
{
  "AA:BB:CC:DD:EE:FF": {
    "address": "AA:BB:CC:DD:EE:FF",
    "uuid": "<device-uuid>",
    "local_key": "<local-key>",
    "device_id": "<device-id>",
    "category": "jtmspro",
    "product_id": "y2yaegze",
    "device_name": "CTL20H SmartLock",
    "product_model": "CTL20H",
    "product_name": "CTL20H SmartLock"
  }
}
```

Remote unlock uses the inherited Raykube V4 unlock mechanism and requires the device-specific `ble_unlock_check` value in `devices.json`. Never publish a real `ble_unlock_check` value.

## Battery hardware used during testing

The tested lock used four rechargeable AAA cells, 700 mAh each. This is installation information only; it is not required by the integration protocol.
