# Tuya Local BLE: fork dla Raykube A1 Pro

Fork [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) (MIT), który daje w Home Assistant
lokalne sterowanie zamkiem **Raykube A1 Pro / A1 Pro Max / A1 Ultra** (`jtmspro`, `hc7n0urm`, `rlyxv7pe`)
po Bluetooth, bez chmury i bramki.

Encje zamka:

- otwieranie i zamykanie (`lock`),
- kalibracja (przycisk),
- wyciszenie i odciszenie (przełącznik),
- poziom głośności (select),
- automatyczne zamykanie i jego czas (przełącznik + liczba w sekundach),
- tryb uzbrojenia: powiadomienie z HA przy ręcznym otwarciu zamka (blueprint `blueprints/automation/a1pro/lock_arming_alarm.yaml`),
- karta dashboardu „Raykube Lock” (stuknięcie zamyka, przytrzymanie otwiera panel ze szczegółami),
- odświeżenie stanu i diagnostyka wszystkich DP,
- usługa `tuya_local_ble.set_datapoint` do zapisu dowolnego DP.

Dane z Tuya Cloud (klucze, `ble_unlock_check`, lista DP) pobiera `python3 tools/tuya_export.py`.

Instalacja, konfiguracja `devices.json`, skąd wziąć klucze i jak skonfigurować tryb uzbrojenia:
**[docs/raykube-a1-pro.md](docs/raykube-a1-pro.md)**.

Fork używa domeny `tuya_local_ble`, więc zastępuje oryginalną integrację.
Pozostałe urządzenia z upstreamu działają bez zmian. Ich opis jest w [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md).

## Testy

```bash
pip install bleak bleak-retry-connector pycryptodome pytest
pytest tests   # testy z HA uruchamiają się, gdy zainstalowany jest homeassistant
node tests/card/test_card.mjs   # test karty w przeglądarce (playwright + chromium)
```

## Licencja

MIT, jak upstream (zob. [LICENSE](LICENSE)).
