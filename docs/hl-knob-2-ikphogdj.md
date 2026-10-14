# HL Knob-2 TuyaOS FD50 lock

## Tested device

- Category: `jtmspro`
- Product ID: `ikphogdj`

## Required `devices.json` fields

Use the same schema as other devices, with the HL Knob-2 product ID:

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

Please note : In some cases, the BLE address of the device shown in Tuya / Smartlife app is the 'reverse' of the actual BLE address. So if the entry for `A1:B2:C3:D4:E5:F6` in `devices.json` doesn't detect your device, try `6F:5E:4D:3C:2B:1A` (both levels)

When the device is newly added, or on every HA restart, all entities show a 'default' state, which is not in sync with actual live states. 
Once the `Lock Control` or `Auto Lock` or `Lock Volume` are set from HA, going ahead it will usually stay in sync.
If required, create an automation using HA startup as trigger, wait for couple mins, and set each of the above entities.
