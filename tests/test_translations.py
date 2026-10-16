"""Every Polish text has an English counterpart (integration and card)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tuya_local_ble"


def flat_keys(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        keys |= flat_keys(value, path) if isinstance(value, dict) else {path}
    return keys


def load(lang: str) -> dict:
    return json.loads((COMPONENT / "translations" / f"{lang}.json").read_text(encoding="utf-8"))


def test_english_covers_every_polish_text():
    missing = flat_keys(load("pl")) - flat_keys(load("en"))
    assert not missing, sorted(missing)


def test_translations_match_strings_json_when_present():
    strings = COMPONENT / "strings.json"
    if strings.exists():
        assert flat_keys(json.loads(strings.read_text(encoding="utf-8"))) <= flat_keys(load("en"))


def card_strings() -> dict[str, set[str]]:
    source = (COMPONENT / "frontend" / "raykube-lock-card.js").read_text(encoding="utf-8")
    block = source[source.index("const STRINGS = {"):]
    block = block[: block.index("\n};")]
    result = {}
    for lang in ("pl", "en"):
        start = block.index(f"\n  {lang}: {{")
        end = block.index("\n  },", start)
        result[lang] = set(re.findall(r"^\s{4}(\w+):", block[start:end], re.M))
    return result


def test_card_has_the_same_texts_in_both_languages():
    texts = card_strings()
    assert texts["pl"] and texts["pl"] == texts["en"], texts["pl"] ^ texts["en"]
