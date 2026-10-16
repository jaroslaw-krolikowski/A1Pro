# Raykube A1 Pro / A1 Pro Max / A1 Ultra w Home Assistant (lokalnie po BLE)

Ten fork [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE) dodaje do zamków Raykube
(`jtmspro`, `hc7n0urm` i `rlyxv7pe`) pełny zestaw ustawień w Home Assistant.

## Encje

| Encja HA (nazwa PL / EN) | Funkcja | DP | Typ | Pewność |
|---|---|---|---|---|
| lock: Zamek / Lock Control | otwieranie / zamykanie; stan z DP47 (`false` = zamknięty) | 71 (otwarcie), 46 (zamknięcie), 47 (stan) | raw / bool | potwierdzone fizycznie (upstream); stan DP47 potwierdzony na `hc7n0urm` |
| select: Głośność zamka / Lock Volume | głośność: `hc7n0urm` mute / normal, `rlyxv7pe` mute / low / normal / high | 31 | enum | model DP z chmury Tuya |
| switch: Wyciszenie / Mute | wycisz / odcisz | 31 | enum | j.w. Odciszenie przywraca ostatni poziom |
| switch: Automatyczne zamykanie / Auto Lock | auto-zamykanie po otwarciu | 33 | bool | DP z chmury Tuya i snapshotu BLE |
| number: Czas automatycznego zamknięcia / Auto lock delay | opóźnienie auto-zamknięcia (s) | 36 | value | DP z chmury Tuya i snapshotu BLE |
| button: Kalibracja / Calibrate | kalibracja zamka | 68 = `function1` | enum | potwierdzone: kalibracja w aplikacji raportuje DP68 = `function1` (`hc7n0urm`) |
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
4. Zamek pojawi się jako wykryty w *Ustawienia → Urządzenia i usługi*. Możesz go też dodać ręcznie:
   *Dodaj integrację → Tuya Local BLE* i wybrać zamek z listy.

Jeśli przy dodawaniu pojawia się komunikat, że HA nie widzi żadnego urządzenia Tuya BLE, to Bluetooth
w HA nie widzi zamka. Najczęstsze przyczyny:
- HA działa w maszynie wirtualnej (np. Proxmox), a adapter Bluetooth nie jest do niej przekazany.
  Przekaż adapter USB do VM (*Hardware → Add → USB Device*) albo użyj ESPHome Bluetooth proxy.
- Zamek jest poza zasięgiem adaptera.
- Aplikacja Tuya/Smart Life jest w tej chwili połączona z zamkiem.

Integracja Bluetooth w HA (*Ustawienia → Urządzenia i usługi → Bluetooth*) pokazuje, czy jest jakiś adapter
lub proxy. Jeśli zamek jest na liście, ale nie ma go w `devices.json`, pojawi się błąd z prośbą o
sprawdzenie adresu MAC w pliku.

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
| `beep_volume_options` | `hc7n0urm`: `["mute","normal"]`, inne: `["mute","low","normal","high"]` | poziomy głośności w kolejności z chmury Tuya |
| `unmute_level` | `normal` | poziom po odciszeniu, gdy nie znamy poprzedniego |
| `calibrate_value` | 0 | indeks wartości DP68 wysyłany przy kalibracji (`function1` = 0) |
| `auto_lock_time_min` / `auto_lock_time_max` | 1 / 1800 | zakres pola czasu (s) |

`null` albo `0` przy DP wyłącza daną encję, np. `"dps": {"special_function": null}`.

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

Skrypt wypisze listę DP zamka (numer, kod, typ, zakres, aktualna wartość). Plik `tuya_export/devices.json` skopiuj do
`config/tuya_local_ble/devices.json`. Pliki w `tuya_export/` zawierają klucze, dlatego są w `.gitignore`.

Ręcznie, bez skryptu:

- `local_key`, `uuid`, `device_id`, `product_id`, MAC: `python -m tinytuya wizard`
  ([TinyTuya](https://github.com/jasonacox/tinytuya)). W wygenerowanym `devices.json` jest też
  sekcja `mapping` z listą DP. **Sprawdź w niej zakres `beep_volume`.** Jeśli to np. `["mute","normal"]`,
  wpisz go w `beep_volume_options`, bo indeksy enum muszą się zgadzać.
- `ble_unlock_check`: Tuya IoT Platform → Cloud → API Explorer → *Device Management → Get device status*,
  kod `ble_unlock_check`. Bez niego zamykanie działa, ale otwieranie nie.
- MAC bywa zapisany w aplikacji „od tyłu”. Jeśli zamek nie jest wykrywany, odwróć kolejność bajtów.

## Karta „Raykube Lock”

Integracja instaluje własną kartę dashboardu. HA ładuje ją sam, bez HACS frontend i bez dodawania zasobów.
Standardowego okna zamka w HA (z dużym przełącznikiem) integracja zmienić nie może, więc ta karta je zastępuje.

- **Stuknięcie** w kafelek **przełącza** zamek: otwiera zamknięty, zamyka otwarty. Przycisk po prawej
  pokazuje, co zrobi stuknięcie. Do czasu potwierdzenia przez zamek kręci się wskaźnik.
- **Przytrzymanie** (albo strzałka po prawej) otwiera panel ze szczegółami:
  - przyciski **Zamknij** i **Otwórz**. Wyróżniony jest ten, który zmienia aktualny stan;
  - stan i czas ostatniej zmiany z informacją, skąd przyszła: *na zamku* (gałka, klucz, aplikacja,
    auto-zamknięcie), *z Home Assistant* albo *automatyzacja*;
  - bateria, auto-zamykanie i jego czas, tryb uzbrojenia, opcjonalnie siła sygnału;
  - ustawienia: tryb uzbrojenia, auto-zamykanie, czas, wyciszenie, odświeżenie stanu, kalibracja
    (z potwierdzeniem);
  - ostatnie zdarzenia z 48 h.

Dodanie: *Edytuj dashboard → Dodaj kartę →* wyszukaj **Raykube Lock**. Albo w YAML:

```yaml
type: custom:raykube-lock-card
entity: lock.raykube_a1_ultra_d9f494_zamek
name: Drzwi wejściowe                        # opcjonalnie
arming_entity: input_boolean.zamek_uzbrojony # opcjonalnie, pomocnik trybu uzbrojenia
confirm_unlock: false                        # opcjonalnie: true = otwarcie wymaga drugiego dotknięcia
```

Wygląd jest wzorowany na shadcn/ui, a ikony to [Lucide](https://lucide.dev) wbudowane w kartę.
Karta dopasowuje się do jasnego i ciemnego motywu HA.

Pozostałe encje zamka (bateria, auto-zamykanie, wyciszenie, przyciski) karta znajduje sama. Każdą można też
wskazać ręcznie: `battery_entity`, `auto_lock_entity`, `auto_lock_time_entity`, `mute_entity`,
`refresh_entity`, `calibrate_entity`, `signal_entity`.

Po aktualizacji integracji odśwież stronę albo aplikację HA, żeby wczytać nową wersję karty.

## Tryb uzbrojenia (powiadomienie w Home Assistant)

Zamek nie ma własnego trybu uzbrojenia (sprawdzone na pełnym modelu DP `hc7n0urm`), więc tryb uzbrojenia
działa w Home Assistant. Zamek jest w nim tylko czujnikiem. Automatyzacja nie zmienia stanu zamka
ani jego ustawień.

Gdy tryb jest włączony, a zamek zmieni stan z *zamknięty* na *otwarty* nie z polecenia HA (ktoś przekręcił
gałkę, użył klucza albo otworzył z aplikacji Tuya), HA wysyła powiadomienie. Otwarcie z HA (panel,
automatyzacja, asystent głosowy) powiadomienia nie wysyła. HA rozpoznaje to po kontekście zmiany stanu:
zmiana zgłoszona przez sam zamek nie ma przypisanego użytkownika ani automatyzacji.

### Konfiguracja

1. Utwórz pomocnika: *Ustawienia → Urządzenia i usługi → Pomocnicy → Utwórz pomocnika → Przełącznik*,
   np. „Zamek uzbrojony” (`input_boolean.zamek_uzbrojony`).
2. Zaimportuj blueprint: *Ustawienia → Automatyzacje i sceny → Blueprinty → Importuj blueprint* i wklej
   `https://github.com/jaroslaw-krolikowski/A1Pro/blob/master/blueprints/automation/a1pro/lock_arming_alarm.yaml`.
   Możesz też skopiować plik do `config/blueprints/automation/a1pro/`.
3. Utwórz z niego automatyzację: wybierz zamek i pomocnika. W polu **Powiadomienie** wklej (w trybie YAML)
   akcję aplikacji mobilnej HA. `mobile_app_twoj_telefon` zamień na nazwę swojego telefonu z listy
   usług `notify`.

   Android (dźwięk alarmu także przy wyciszonym telefonie):
   ```yaml
   - action: notify.mobile_app_twoj_telefon
     data:
       title: "Zamek otwarty ręcznie!"
       message: "Tryb uzbrojenia: ktoś przekręcił zamek."
       data:
         ttl: 0
         priority: high
         channel: alarm_stream
   ```

   iPhone (alert krytyczny, przebija tryb cichy):
   ```yaml
   - action: notify.mobile_app_twoj_telefon
     data:
       title: "Zamek otwarty ręcznie!"
       message: "Tryb uzbrojenia: ktoś przekręcił zamek."
       data:
         push:
           sound:
             name: default
             critical: 1
             volume: 1.0
   ```
4. W opcjach integracji Tuya Local BLE włącz **Keep connected (24/7)**. Bez stałego połączenia HA
   dowiaduje się o ręcznym otwarciu dopiero przy kolejnym odświeżeniu, nawet po ok. 5 minutach.
   Stałe połączenie zużywa więcej baterii zamka. Najlepiej działa przez ESPHome BLE proxy blisko drzwi.

## Historia zmian DP

```bash
python3 tools/tuya_export.py --logs 7
```

Wypisuje historię raportów DP z chmury Tuya (przechowywaną ok. 7 dni), a na końcu ustawienia (`rw`),
które zmieniały wartość. Historia obejmuje tylko DP zadeklarowane w modelu Tuya. Sposób zaczerpnięty
z `Cloud.getdevicelog` w [TinyTuya](https://github.com/jasonacox/tinytuya). Lokalnie to samo widać
w sensorze **Datapointy** po naciśnięciu **Odśwież stan**.

Dowolny DP można zapisać z HA usługą `tuya_local_ble.set_datapoint`:

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
# Zamknięcie i uzbrojenie po wyjściu wszystkich z domu
- alias: Zamek - uzbrój po wyjściu
  triggers:
    - trigger: state
      entity_id: zone.home
      to: "0"
  actions:
    - action: lock.lock
      target: {entity_id: lock.twoj_zamek}
    - action: input_boolean.turn_on
      target: {entity_id: input_boolean.zamek_uzbrojony}

# Rozbrojenie po powrocie
- alias: Zamek - rozbrój po powrocie
  triggers:
    - trigger: numeric_state
      entity_id: zone.home
      above: 0
  actions:
    - action: input_boolean.turn_off
      target: {entity_id: input_boolean.zamek_uzbrojony}

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
