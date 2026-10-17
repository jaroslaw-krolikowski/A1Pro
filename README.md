# Raykube A1 Ultra (Tuya BLE)

Autor / Author: **Jarosław Królikowski** ([@jaroslaw-krolikowski](https://github.com/jaroslaw-krolikowski))

[🇵🇱 Polski](#polski) · [🇬🇧 English](#english)

## Polski

Fork [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) (MIT), który daje w Home Assistant
lokalne sterowanie zamkiem **Raykube A1 Ultra** (`jtmspro`, `hc7n0urm`, `rlyxv7pe`)
po Bluetooth, bez chmury i bramki.

Encje zamka:

- otwieranie i zamykanie (`lock`),
- kalibracja (przycisk i karta z potwierdzeniem; najwyżej raz na 2 minuty),
- wyciszenie i odciszenie (przełącznik),
- poziom głośności (select),
- automatyczne zamykanie i jego czas (przełącznik + liczba w sekundach),
- tryb uzbrojenia: powiadomienie z HA przy ręcznym otwarciu zamka (blueprint `blueprints/automation/a1ultra/lock_arming_alarm.yaml`),
- karta dashboardu „Raykube Lock” (przycisk zamyka i otwiera, otwarcie z potwierdzeniem; stuknięcie w kafelek pokazuje szczegóły),
- diagnostyka: stan połączenia BLE z ostatnim błędem, wszystkie DP z nazwami i historią zmian, plik *Pobierz diagnostykę*,
- usługa `tuya_local_ble.set_datapoint` do zapisu dowolnego DP.

Interfejs (encje, opcje, karta, blueprint) jest po polsku i po angielsku.

Dane z Tuya Cloud (klucze, `ble_unlock_check`, lista DP) pobiera `python3 tools/tuya_export.py`.

Instalacja, konfiguracja `devices.json`, skąd wziąć klucze, tryb uzbrojenia i diagnostyka:
**[docs/raykube-a1-ultra.md](docs/raykube-a1-ultra.md)**.

Fork używa domeny `tuya_local_ble`, więc zastępuje oryginalną integrację.
Pozostałe urządzenia z upstreamu działają bez zmian. Ich opis jest w [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md).

## English

A fork of [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) (MIT) that gives Home Assistant local
control of the **Raykube A1 Ultra** lock (`jtmspro`, `hc7n0urm`, `rlyxv7pe`)
over Bluetooth, with no cloud and no gateway.

Lock entities:

- lock and unlock (`lock`),
- calibration (button, and the card with confirmation; at most once every 2 minutes),
- mute and unmute (switch),
- volume level (select),
- auto-lock and its delay (switch + number in seconds),
- arming mode: an HA notification when the lock is unlocked by hand (blueprint `blueprints/automation/a1ultra/lock_arming_alarm.yaml`),
- "Raykube Lock" dashboard card (the button locks and unlocks, unlocking asks for confirmation; a tap on the tile shows details),
- diagnostics: BLE connection state with the last error, every DP with names and change history, a *Download diagnostics* file,
- the `tuya_local_ble.set_datapoint` action to write any DP.

The UI (entities, options, card, blueprint) is available in Polish and English.

`python3 tools/tuya_export.py` fetches the data from the Tuya Cloud (keys, `ble_unlock_check`, DP list).

Installation, `devices.json`, where to get the keys, arming mode and diagnostics:
**[docs/raykube-a1-ultra.en.md](docs/raykube-a1-ultra.en.md)**.

The fork uses the `tuya_local_ble` domain, so it replaces the original integration.
The other upstream devices work unchanged; they are described in [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md).

## Testy / Tests

```bash
pip install bleak bleak-retry-connector pycryptodome pytest
pytest tests   # tests that need HA run when homeassistant is installed
node tests/card/test_card.mjs   # card test in a browser (playwright + chromium)
```

## Autorzy / Credits

- **Jarosław Królikowski**: integracja Raykube A1 Ultra: ustawienia zamka, karta, tryb uzbrojenia,
  diagnostyka, tryby połączenia, eksport z Tuya / the Raykube A1 Ultra integration: lock settings, card,
  arming mode, diagnostics, connection modes, Tuya export.
- Bazuje na / based on [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) (Shon), które rozwija
  [PlusPlus-ua/ha_tuya_ble](https://github.com/PlusPlus-ua/ha_tuya_ble): protokół Tuya BLE i obsługa innych
  urządzeń / the Tuya BLE protocol layer and the other devices.

## Licencja / License

MIT (zob. / see [LICENSE](LICENSE)). Licencja wymaga zachowania informacji o prawach autorskich upstreamu
obok Twoich / the license requires keeping the upstream copyright notice next to yours.
