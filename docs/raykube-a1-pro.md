# Raykube A1 Pro / A1 Pro Max / A1 Ultra w Home Assistant (lokalnie po BLE)

Ten fork [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) dodaje do zamków Raykube
(`jtmspro`, `hc7n0urm` i `rlyxv7pe`) pełny zestaw ustawień w Home Assistant.

## Encje

| Encja HA (nazwa PL / EN) | Funkcja | DP | Typ | Pewność |
|---|---|---|---|---|
| lock: Zamek / Lock Control | otwieranie / zamykanie | 71 (otwarcie), 46 (zamknięcie) | raw / bool | potwierdzone fizycznie (upstream) |
| select: Głośność zamka / Lock Volume | głośność: `hc7n0urm` mute / normal, `rlyxv7pe` mute / low / normal / high | 31 | enum | model DP z chmury Tuya |
| switch: Wyciszenie / Mute | wycisz / odcisz | 31 | enum | j.w. Odciszenie przywraca ostatni poziom |
| switch: Automatyczne zamykanie / Auto Lock | auto-zamykanie po otwarciu | 33 | bool | DP z chmury Tuya i snapshotu BLE |
| number: Czas automatycznego zamknięcia / Auto lock delay | opóźnienie auto-zamknięcia (s) | 36 | value | DP z chmury Tuya i snapshotu BLE |
| button: Kalibracja / Calibrate | kalibracja zamka | 68 = `function1` | enum | wg profilu tuya-local (`Recalibrate`) |
| switch: Tryb uzbrojenia / Arming mode | tryb uzbrojenia (alarm przy ręcznym przekręceniu) | **do ustalenia** | bool | tworzony dopiero po wpisaniu DP, sprawdź niżej |
| button: Odśwież stan / Refresh status | łączy się z zamkiem i pobiera pełny stan | – | – | – |
| sensor: Datapointy / Datapoints | wszystkie DP odebrane z zamka (atrybuty) | – | – | diagnostyka |

Skąd te numery DP:
- lista DP `hc7n0urm` z chmury Tuya ([make-all/tuya-local#4098](https://github.com/make-all/tuya-local/issues/4098)),
- profil [`raykube_a1promax_lock.yaml`](https://github.com/make-all/tuya-local/blob/main/custom_components/tuya_local/devices/raykube_a1promax_lock.yaml) z tuya-local (DP68: `function1` = Recalibrate, `function2` = Unlock more, `function3` = Keep retracted, `function4` = Add force),
- snapshot stanu po BLE zdekodowany w [ShonP40/Tuya-BLE#39](https://github.com/ShonP40/Tuya-BLE/pull/39) (DP 9, 11, 31, 33, 34, 36, 40, 47, 76, 77, 78).

Kod zapisuje ustawienia tą samą ramką V4, której używa aplikacja Tuya
(`00000000 01 <dp> <typ> <len:2> <wartość>`, przechwyconą dla HL Knob-2 w upstreamie).
Upstream wysyłał głośność z typem `raw`, przez co zamek potwierdzał komendę, ale jej nie odsyłał.
Ten fork wysyła ją jako `enum`.

## Instalacja

1. HACS → Integrations → menu ⋮ → *Custom repositories* → `https://github.com/jaroslaw-krolikowski/A1Pro`, kategoria *Integration*.
   Albo ręcznie: skopiuj `custom_components/tuya_local_ble` do `config/custom_components/`.
2. Fork ma tę samą domenę (`tuya_local_ble`) co ShonP40/Tuya-BLE, więc **zastępuje** oryginał.
   Jeśli oryginał jest zainstalowany, usuń go z HACS (zostaw wpis integracji i `devices.json`) i zainstaluj fork.
3. Uzupełnij `config/tuya_local_ble/devices.json` (niżej) i zrestartuj HA.

## `devices.json`

```json
{
  "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<uuid>",
    "local_key": "<local_key>",
    "device_id": "<device_id>",
    "category": "jtmspro",
    "product_id": "hc7n0urm",
    "device_name": "Raykube A1 Pro",
    "product_model": "A1 Pro",
    "product_name": "Smart lock",
    "ble_unlock_check": "<base64 z Tuya Cloud>",
    "raykube": {
      "dps": {
        "arming": 78
      },
      "beep_volume_options": ["mute", "normal"],
      "unmute_level": "normal"
    }
  }
}
```

Blok `raykube` jest opcjonalny. Wszystkie klucze:

| Klucz | Domyślnie | Znaczenie |
|---|---|---|
| `dps.beep_volume` | 31 | DP głośności (select + wyciszenie) |
| `dps.automatic_lock` | 33 | DP przełącznika auto-zamykania |
| `dps.auto_lock_time` | 36 | DP czasu auto-zamykania |
| `dps.special_function` | 68 | DP kalibracji |
| `dps.arming` | brak | DP trybu uzbrojenia (bez niego przełącznik nie powstaje) |
| `beep_volume_options` | `hc7n0urm`: `["mute","normal"]`, inne: `["mute","low","normal","high"]` | poziomy głośności w kolejności z chmury Tuya |
| `unmute_level` | `normal` | poziom po odciszeniu, gdy nie znamy poprzedniego |
| `calibrate_value` | 0 | indeks wartości DP68 wysyłany przy kalibracji (`function1` = 0) |
| `auto_lock_time_min` / `auto_lock_time_max` | 1 / 1800 | zakres pola czasu (s) |

`null` albo `0` przy DP wyłącza daną encję, np. `"dps": {"arming": null}`.

### Skąd wziąć dane

Najprościej skryptem `tools/tuya_export.py` (Python 3.9+, bez dodatkowych pakietów). Pobiera z Tuya Cloud
wszystkie potrzebne pola, w tym `ble_unlock_check` i pełny model DP, i zapisuje gotowy
`tuya_export/devices.json` razem z blokiem `raykube` dopasowanym do Twojego zamka.

1. Załóż konto na [platform.tuya.com](https://platform.tuya.com). Utwórz *Cloud → Development → Create Cloud Project*,
   z data center *Central Europe* dla kont z Polski.
2. W projekcie: *Service API* → upewnij się, że jest subskrybowane **IoT Core**.
   *Devices → Link App Account* → zeskanuj kod QR aplikacją Smart Life/Tuya (Ja → ikona skanowania).
3. Z zakładki *Overview* skopiuj **Access ID** i **Access Secret**, potem uruchom:

```bash
export TUYA_ACCESS_ID=...  TUYA_ACCESS_SECRET=...  TUYA_REGION=eu
python3 tools/tuya_export.py
```

Skrypt wypisze listę DP zamka (numer, kod, typ, zakres, aktualna wartość). Wskaże też kandydata na tryb
uzbrojenia, jeśli model zawiera taki DP. Plik `tuya_export/devices.json` skopiuj do
`config/tuya_local_ble/devices.json`. Pliki w `tuya_export/` zawierają klucze, dlatego są w `.gitignore`.

Ręcznie, bez skryptu:

- `local_key`, `uuid`, `device_id`, `product_id`, MAC: `python -m tinytuya wizard`
  ([TinyTuya](https://github.com/jasonacox/tinytuya)). W wygenerowanym `devices.json` jest też
  sekcja `mapping` z listą DP. **Sprawdź w niej zakres `beep_volume`.** Jeśli to np. `["mute","normal"]`,
  wpisz go w `beep_volume_options`, bo indeksy enum muszą się zgadzać.
- `ble_unlock_check`: Tuya IoT Platform → Cloud → API Explorer → *Device Management → Get device status*,
  kod `ble_unlock_check`. Bez niego zamykanie działa, ale otwieranie nie.
- MAC bywa zapisany w aplikacji „od tyłu”. Jeśli zamek nie jest wykrywany, odwróć kolejność bajtów.

## Weryfikacja DP trybu uzbrojenia

Model DP `hc7n0urm` w chmurze Tuya nie ma DP o nazwie kojarzącej się z uzbrojeniem (ani DP11).
Kandydaci z modelu to `special_control` (DP78, bool) i opcje `special_function` (DP68, enum).
Najprościej ustalić to przez chmurę:

1. Uruchom `python3 tools/tuya_export.py` i zapisz tabelę DP (kolumna „wartość”).
2. W aplikacji Tuya/Smart Life przełącz **tryb uzbrojenia**. Zmieniaj tylko to jedno ustawienie.
   Poczekaj, aż aplikacja połączy się z zamkiem.
3. Uruchom skrypt ponownie i porównaj wartości. DP, który się zmienił, to tryb uzbrojenia.
4. Jeśli to DP typu bool, wpisz go w `"raykube": {"dps": {"arming": <nr>}}` i zrestartuj HA.

To samo da się zrobić lokalnie przez sensor **Datapointy** i przycisk **Odśwież stan** w HA.
Aplikacja i HA nie mogą być wtedy połączone z zamkiem jednocześnie.

Możesz też przetestować DP bezpośrednio z HA usługą `tuya_local_ble.set_datapoint`:

```yaml
action: tuya_local_ble.set_datapoint
data:
  device_id: <id urządzenia z HA>
  dp_id: 78
  type: bool
  value: "true"
```

Tą samą usługą dostępne są pozostałe funkcje DP68: `type: enum`, `value: 1` (Unlock more),
`2` (Keep retracted), `3` (Add force).

## Przykładowe automatyzacje

```yaml
# Uzbrojenie po wyjściu wszystkich z domu
- alias: Zamek - uzbrój po wyjściu
  triggers:
    - trigger: state
      entity_id: zone.home
      to: "0"
  actions:
    - action: lock.lock
      target: {entity_id: lock.twoj_zamek}
    - action: switch.turn_on
      target: {entity_id: switch.twoj_zamek_tryb_uzbrojenia}

# Cisza nocna
- alias: Zamek - wycisz na noc
  triggers:
    - trigger: time
      at: "22:00:00"
  actions:
    - action: switch.turn_on
      target: {entity_id: switch.twoj_zamek_wyciszenie}
```

Identyfikatory encji (`lock.twoj_zamek` itd.) podmień na swoje z ustawień urządzenia w HA.

## Ograniczenia

- Zamek na baterie śpi między komendami. HA łączy się na żądanie, więc każda zmiana trwa kilka sekund.
  Stan ustawień odświeża się przy każdym połączeniu (snapshot), przyciskiem **Odśwież stan**
  albo na stałe przy opcji *Keep connected (24/7)* w opcjach integracji (wtedy lepiej użyć ESPHome BLE proxy).
- Aplikacja Tuya/Smart Life i HA nie mogą być połączone z zamkiem jednocześnie.
- Na części egzemplarzy z firmware 5.6 `ble_unlock_check` zmienia się po każdym otwarciu z aplikacji
  i otwieranie z HA przestaje działać. Zobacz [ShonP40/Tuya-BLE#17](https://github.com/ShonP40/Tuya-BLE/issues/17).
- Encja *Kierunek zamka* (DP48) pochodzi z upstreamu. W profilu tuya-local kierunek
  dla tych zamków to DP78 (`special_control`). Jeśli potrzebujesz zmiany kierunku, użyj `set_datapoint`
  z `dp_id: 78`, `type: bool`.
