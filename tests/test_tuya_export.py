"""tools/tuya_export.py against a local mock of the Tuya OpenAPI."""
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import tuya_export  # noqa: E402

ACCESS_ID = "testaccessid"
SECRET = "testsecret"
TOKEN = "tok123"
DEVICE_ID = "bfdevice0001"

MODEL = {
    "services": [
        {
            "properties": [
                {"abilityId": 9, "code": "battery_state", "accessMode": "ro",
                 "typeSpec": {"type": "enum", "range": ["high", "medium", "low", "poweroff"]}},
                {"abilityId": 11, "code": "arming_switch", "accessMode": "rw",
                 "typeSpec": {"type": "bool"}},
                {"abilityId": 21, "code": "alarm_lock", "accessMode": "ro",
                 "typeSpec": {"type": "enum", "range": ["low_battery", "defense"]}},
                {"abilityId": 31, "code": "beep_volume", "accessMode": "rw",
                 "typeSpec": {"type": "enum", "range": ["mute", "normal"]}},
                {"abilityId": 33, "code": "automatic_lock", "accessMode": "rw",
                 "typeSpec": {"type": "bool"}},
                {"abilityId": 36, "code": "auto_lock_time", "accessMode": "rw",
                 "typeSpec": {"type": "value", "min": 0, "max": 600, "unit": "s"}},
                {"abilityId": 68, "code": "special_function", "accessMode": "rw",
                 "typeSpec": {"type": "enum", "range": ["function1", "function2"]}},
                {"abilityId": 71, "code": "ble_unlock_check", "accessMode": "rw",
                 "typeSpec": {"type": "raw"}},
            ]
        }
    ]
}

RESPONSES = {
    "/v1.0/token": {"access_token": TOKEN, "expire_time": 7200},
    "/v1.0/iot-01/associated-users/devices": {
        "devices": [
            {"id": DEVICE_ID, "name": "Drzwi", "category": "jtmspro", "product_id": "hc7n0urm"},
            {"id": "bfplug", "name": "Gniazdko", "category": "cz", "product_id": "x"},
        ],
        "has_more": False,
    },
    f"/v1.0/devices/{DEVICE_ID}": {
        "id": DEVICE_ID, "name": "Drzwi", "uuid": "uuid0001", "local_key": "lk0123456789",
        "category": "jtmspro", "product_id": "hc7n0urm", "product_name": "A1 Ultra-JM",
    },
    "/v1.0/devices/factory-infos": [{"id": DEVICE_ID, "mac": "dc23aabbccdd", "uuid": "uuid0001"}],
    f"/v1.0/devices/{DEVICE_ID}/status": [
        {"code": "beep_volume", "value": "normal"},
        {"code": "ble_unlock_check", "value": "AAH//zEyMzQ1Njc4AaqrzN0AAA=="},
    ],
    f"/v1.1/devices/{DEVICE_ID}/specifications": {"functions": [], "status": []},
    f"/v2.0/cloud/thing/{DEVICE_ID}/model": {"model": json.dumps(MODEL)},
    f"/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties": {"properties": []},
}


def expected_sign(path_and_query: str, timestamp: str, token: str) -> str:
    # Independent implementation of Tuya's post-2021 signing (as in tinytuya).
    payload = ACCESS_ID + token + timestamp
    payload += "GET\n" + hashlib.sha256(b"").hexdigest() + "\n" + "\n" + path_and_query
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest().upper()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlsplit(self.path).path
        token = self.headers.get("access_token", "")
        ok_sign = self.headers.get("sign") == expected_sign(self.path, self.headers["t"], token)
        if not ok_sign:
            body = {"success": False, "code": 1004, "msg": "sign invalid"}
        elif path != "/v1.0/token" and token != TOKEN:
            body = {"success": False, "code": 1010, "msg": "token invalid"}
        elif path in RESPONSES:
            body = {"success": True, "result": RESPONSES[path]}
        else:
            body = {"success": False, "code": 404, "msg": "unknown"}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_export_builds_devices_json(tmp_path, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setitem(tuya_export.REGIONS, "eu", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("TUYA_ACCESS_ID", ACCESS_ID)
    monkeypatch.setenv("TUYA_ACCESS_SECRET", SECRET)
    monkeypatch.setattr(sys, "argv", ["tuya_export.py", "--out", str(tmp_path)])
    try:
        assert tuya_export.main() == 0
    finally:
        server.shutdown()

    devices = json.loads((tmp_path / "devices.json").read_text())
    assert list(devices) == ["DC:23:AA:BB:CC:DD"]
    entry = devices["DC:23:AA:BB:CC:DD"]
    assert entry["uuid"] == "uuid0001"
    assert entry["local_key"] == "lk0123456789"
    assert entry["product_id"] == "hc7n0urm"
    assert entry["ble_unlock_check"] == "AAH//zEyMzQ1Njc4AaqrzN0AAA=="
    assert entry["raykube"] == {
        "dps": {
            "arming": 11,
            "beep_volume": 31,
            "automatic_lock": 33,
            "auto_lock_time": 36,
            "special_function": 68,
        },
        "beep_volume_options": ["mute", "normal"],
        "auto_lock_time_min": 1,
        "auto_lock_time_max": 600,
        "calibrate_value": 0,
    }
    assert (tmp_path / f"{DEVICE_ID}.json").exists()


def test_alarm_is_not_an_arming_candidate():
    assert not tuya_export.ARMING_CODE.search("alarm_lock")
    assert tuya_export.ARMING_CODE.search("arming_switch")


def test_script_runs_standalone():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "tuya_export.py"), "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "--device-id" in result.stdout
