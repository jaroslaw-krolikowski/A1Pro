#!/usr/bin/env python3
"""Export everything tuya_local_ble needs for a Tuya BLE lock from Tuya Cloud.

Fetches, for every lock (category jtmspro) linked to your Tuya IoT project
(or one device given with --device-id):
  - device details: device_id, uuid, local_key, product_id, category, name
  - Bluetooth MAC address (factory info)
  - current status, including ble_unlock_check
  - the full DP model (dp id, code, type, range) and shadow properties

and writes:
  <out>/devices.json         ready to copy to config/tuya_local_ble/devices.json
  <out>/<device_id>.json     every raw API response, for reference

Both files contain secrets (local_key, ble_unlock_check). Do not commit or
share them.

Requirements: Python 3.9+, no extra packages.

Usage:
  export TUYA_ACCESS_ID=...  TUYA_ACCESS_SECRET=...  TUYA_REGION=eu
  python3 tools/tuya_export.py
  python3 tools/tuya_export.py --device-id bf1234567890abcdef
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REGIONS = {
    "eu": "https://openapi.tuyaeu.com",
    "weu": "https://openapi-weaz.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "eus": "https://openapi-ueaz.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}

SUPPORTED_PRODUCT_IDS = ("hc7n0urm", "rlyxv7pe")

# Cloud DP codes -> keys of the "raykube" block in devices.json.
FEATURE_CODES = {
    "beep_volume": "beep_volume",
    "automatic_lock": "automatic_lock",
    "auto_lock_time": "auto_lock_time",
    "special_function": "special_function",
}
ARMING_CODE = re.compile(r"(^|_)(arm|arming|defen[cs]e|guard)(_|$)")

ERROR_HINTS = {
    1004: "Signature invalid: check Access ID / Access Secret.",
    1010: "Token invalid or expired: run the script again.",
    1106: "Permission denied: link your Smart Life / Tuya app account to the "
    "cloud project (Devices -> Link App Account) and check the data center.",
    28841105: "Project not authorized for this API: subscribe the cloud project "
    "to the 'IoT Core' service (Cloud -> Development -> Service API).",
}


class TuyaCloudError(Exception):
    pass


class TuyaCloud:
    """Minimal Tuya OpenAPI client (HMAC-SHA256 request signing)."""

    def __init__(self, endpoint: str, access_id: str, access_secret: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._access_id = access_id
        self._secret = access_secret.encode()
        self._token = ""

    def _sign(self, method: str, url: str, body: bytes, timestamp: str) -> str:
        string_to_sign = "\n".join(
            [method, hashlib.sha256(body).hexdigest(), "", url]
        )
        message = self._access_id + self._token + timestamp + string_to_sign
        return (
            hmac.new(self._secret, message.encode(), hashlib.sha256)
            .hexdigest()
            .upper()
        )

    def request(self, path: str, params: dict | None = None) -> object:
        url = path
        if params:
            url += "?" + urllib.parse.urlencode(sorted(params.items()))
        timestamp = str(int(time.time() * 1000))
        headers = {
            "client_id": self._access_id,
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
            "sign": self._sign("GET", url, b"", timestamp),
        }
        if self._token:
            headers["access_token"] = self._token
        request = urllib.request.Request(self._endpoint + url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.URLError as exc:
            raise TuyaCloudError(f"GET {path}: {exc}") from exc
        if not payload.get("success"):
            code = payload.get("code")
            hint = ERROR_HINTS.get(code, "")
            raise TuyaCloudError(
                f"GET {path}: error {code}: {payload.get('msg')}. {hint}".strip()
            )
        return payload.get("result")

    def connect(self) -> None:
        self._token = ""
        result = self.request("/v1.0/token", {"grant_type": 1})
        self._token = result["access_token"]

    def linked_devices(self) -> list[dict]:
        devices: list[dict] = []
        last_row_key = None
        while True:
            params = {"size": 100}
            if last_row_key:
                params["last_row_key"] = last_row_key
            result = self.request("/v1.0/iot-01/associated-users/devices", params)
            devices += result.get("devices", [])
            last_row_key = result.get("last_row_key")
            if not result.get("has_more") or not last_row_key:
                return devices


def format_mac(mac: str | None) -> str:
    digits = re.sub(r"[^0-9a-fA-F]", "", mac or "").upper()
    if len(digits) != 12:
        return mac or ""
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def mask(value: str | None, show: bool) -> str:
    if not value:
        return "(brak)"
    return value if show else f"{value[:3]}…({len(value)} znaków)"


def fetch_device(cloud: TuyaCloud, device_id: str) -> dict:
    """Fetch every piece of cloud data about one device."""
    raw: dict[str, object] = {}
    calls = {
        "details": (f"/v1.0/devices/{device_id}", None),
        "factory_info": ("/v1.0/devices/factory-infos", {"device_ids": device_id}),
        "status": (f"/v1.0/devices/{device_id}/status", None),
        "specifications": (f"/v1.1/devices/{device_id}/specifications", None),
        "model": (f"/v2.0/cloud/thing/{device_id}/model", None),
        "shadow_properties": (f"/v2.0/cloud/thing/{device_id}/shadow/properties", None),
    }
    for name, (path, params) in calls.items():
        try:
            raw[name] = cloud.request(path, params)
        except TuyaCloudError as exc:
            if name == "details":
                raise
            print(f"  ! {name}: {exc}", file=sys.stderr)
            raw[name] = None
    return raw


def model_properties(raw: dict) -> list[dict]:
    """DP list from the thing model: [{dp_id, code, name, mode, type_spec}]."""
    model = (raw.get("model") or {}).get("model")
    if isinstance(model, str):
        model = json.loads(model)
    properties: list[dict] = []
    for service in (model or {}).get("services", []):
        for prop in service.get("properties", []):
            properties.append(
                {
                    "dp_id": prop.get("abilityId"),
                    "code": prop.get("code"),
                    "name": prop.get("name"),
                    "mode": prop.get("accessMode"),
                    "type_spec": prop.get("typeSpec") or {},
                }
            )
    if properties:
        return sorted(properties, key=lambda p: p["dp_id"] or 0)
    # Fallback: shadow properties carry dp_id, code and type only.
    shadow = (raw.get("shadow_properties") or {}).get("properties") or []
    return sorted(
        (
            {
                "dp_id": prop.get("dp_id"),
                "code": prop.get("code"),
                "name": prop.get("custom_name") or "",
                "mode": "",
                "type_spec": {"type": prop.get("type")},
            }
            for prop in shadow
        ),
        key=lambda p: p["dp_id"] or 0,
    )


def current_values(raw: dict) -> dict[str, object]:
    values: dict[str, object] = {}
    for item in raw.get("status") or []:
        values[item.get("code")] = item.get("value")
    for prop in (raw.get("shadow_properties") or {}).get("properties") or []:
        values.setdefault(prop.get("code"), prop.get("value"))
    return values


def raykube_block(properties: list[dict]) -> tuple[dict, list[dict]]:
    """Build the devices.json "raykube" block from the DP model."""
    block: dict[str, object] = {"dps": {}}
    arming_candidates: list[dict] = []
    for prop in properties:
        code = prop["code"] or ""
        spec = prop["type_spec"]
        if code in FEATURE_CODES:
            block["dps"][FEATURE_CODES[code]] = prop["dp_id"]
        if code == "beep_volume" and spec.get("range"):
            block["beep_volume_options"] = list(spec["range"])
        if code == "auto_lock_time":
            if "min" in spec:
                block["auto_lock_time_min"] = max(int(spec["min"]), 1)
            if "max" in spec:
                block["auto_lock_time_max"] = int(spec["max"])
        if code == "special_function" and "function1" in (spec.get("range") or []):
            block["calibrate_value"] = spec["range"].index("function1")
        if ARMING_CODE.search(code):
            arming_candidates.append(prop)
    if len(arming_candidates) == 1:
        block["dps"]["arming"] = arming_candidates[0]["dp_id"]
    return block, arming_candidates


def describe_spec(spec: dict) -> str:
    kind = spec.get("type", "")
    if spec.get("range"):
        return f"{kind} {spec['range']}"
    if "min" in spec or "max" in spec:
        unit = spec.get("unit", "")
        return f"{kind} {spec.get('min')}..{spec.get('max')} {unit}".strip()
    return kind


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--access-id", default=os.environ.get("TUYA_ACCESS_ID"))
    parser.add_argument("--access-secret", default=os.environ.get("TUYA_ACCESS_SECRET"))
    parser.add_argument(
        "--region",
        default=os.environ.get("TUYA_REGION", "eu"),
        choices=sorted(REGIONS),
        help="data center of the cloud project (default: eu)",
    )
    parser.add_argument("--device-id", action="append", help="export only this device (repeatable)")
    parser.add_argument("--all", action="store_true", help="export all linked devices, not only locks")
    parser.add_argument("--out", default="tuya_export", help="output directory (default: tuya_export)")
    parser.add_argument("--show-secrets", action="store_true", help="print keys unmasked")
    args = parser.parse_args()

    if not args.access_id or not args.access_secret:
        parser.error("set TUYA_ACCESS_ID and TUYA_ACCESS_SECRET (or --access-id/--access-secret)")

    cloud = TuyaCloud(REGIONS[args.region], args.access_id, args.access_secret)
    try:
        cloud.connect()
        if args.device_id:
            device_ids = args.device_id
        else:
            linked = cloud.linked_devices()
            print(f"Urządzenia powiązane z projektem: {len(linked)}")
            for device in linked:
                print(f"  - {device.get('name')} [{device.get('category')}/{device.get('product_id')}] {device.get('id')}")
            device_ids = [
                d["id"] for d in linked if args.all or d.get("category") == "jtmspro"
            ]
            if not device_ids:
                print("Nie znaleziono zamków (category jtmspro). Użyj --all lub --device-id.", file=sys.stderr)
                return 1
    except TuyaCloudError as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    devices_json: dict[str, dict] = {}

    for device_id in device_ids:
        print(f"\n=== {device_id}")
        try:
            raw = fetch_device(cloud, device_id)
        except TuyaCloudError as exc:
            print(f"Błąd: {exc}", file=sys.stderr)
            continue
        details = raw["details"] or {}
        factory = (raw.get("factory_info") or [{}])[0] if raw.get("factory_info") else {}
        values = current_values(raw)
        properties = model_properties(raw)
        mac = format_mac(factory.get("mac"))
        ble_unlock_check = values.get("ble_unlock_check") or ""
        product_id = details.get("product_id", "")

        (out_dir / f"{device_id}.json").write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n"
        )

        entry = {
            "address": mac,
            "uuid": details.get("uuid") or factory.get("uuid", ""),
            "local_key": details.get("local_key", ""),
            "device_id": device_id,
            "category": details.get("category", ""),
            "product_id": product_id,
            "device_name": details.get("name", ""),
            "product_model": details.get("model") or details.get("product_name", ""),
            "product_name": details.get("product_name", ""),
        }
        if ble_unlock_check:
            entry["ble_unlock_check"] = ble_unlock_check
        block, arming_candidates = raykube_block(properties)
        if details.get("category") == "jtmspro":
            entry["raykube"] = block
        devices_json[mac or device_id] = entry

        print(f"Nazwa:            {entry['device_name']} ({entry['product_name']})")
        print(f"Kategoria/produkt: {entry['category']} / {product_id}")
        print(f"MAC (BLE):        {mac or '(brak — odczytaj z aplikacji)'}")
        print(f"UUID:             {mask(entry['uuid'], args.show_secrets)}")
        print(f"local_key:        {mask(entry['local_key'], args.show_secrets)}")
        print(f"ble_unlock_check: {mask(ble_unlock_check, args.show_secrets)}")
        if details.get("category") == "jtmspro" and product_id not in SUPPORTED_PRODUCT_IDS:
            print(f"UWAGA: product_id {product_id} nie jest jeszcze obsługiwany przez fork "
                  f"(obsługiwane: {', '.join(SUPPORTED_PRODUCT_IDS)}).")

        print("\nDP  kod                         tryb  typ / zakres                         wartość")
        for prop in properties:
            value = values.get(prop["code"], "")
            if prop["code"] in ("ble_unlock_check", "check_code_set", "remote_pd_setkey_check",
                                "remote_no_dp_key", "unlock_record_check") and not args.show_secrets:
                value = "<ukryte>" if value else ""
            print(f"{prop['dp_id']!s:>3} {prop['code']!s:<27} {prop['mode']!s:<5} "
                  f"{describe_spec(prop['type_spec'])[:36]:<36} {value}")

        if arming_candidates:
            names = ", ".join(f"DP{p['dp_id']} {p['code']}" for p in arming_candidates)
            print(f"\nTryb uzbrojenia — kandydaci z modelu: {names}")
            if len(arming_candidates) > 1:
                print("Kilka kandydatów: wpisz właściwy w raykube.dps.arming.")
        elif details.get("category") == "jtmspro":
            print("\nModel nie zawiera DP trybu uzbrojenia o znanej nazwie — zostaje domyślny DP11 "
                  "(sprawdź według docs/raykube-a1-pro.md).")

    (out_dir / "devices.json").write_text(
        json.dumps(devices_json, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"\nZapisano {out_dir / 'devices.json'} oraz surowe odpowiedzi w {out_dir}/.")
    print("Skopiuj devices.json do config/tuya_local_ble/devices.json w Home Assistant. "
          "Pliki zawierają klucze — nie wrzucaj ich do repozytorium.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
