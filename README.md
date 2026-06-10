# ORLEN Gas — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Integracja Home Assistant do pobierania danych o zużyciu gazu z konta myORLEN (dawniej eBOK PGNIG).

---

## Wymagania

- Home Assistant 2025.1.0 lub nowszy
- Aktywne konto na [ebok.myorlen.pl](https://ebok.myorlen.pl)

---

## Instalacja przez HACS

1. Otwórz HACS → **Integrations** → menu (⋮) → **Custom repositories**
2. Dodaj URL: `https://github.com/HACS9/home-assistant-orlen-gas`
3. Kategoria: **Integration**
4. Kliknij **Add**, następnie zainstaluj **ORLEN Gas**
5. Zrestartuj Home Assistant

---

## Konfiguracja

1. Przejdź do **Settings → Devices & Services → Add Integration**
2. Wyszukaj **ORLEN Gas**
3. Podaj adres e-mail i hasło do konta myORLEN
4. Kliknij **Submit**

Logowanie następuje raz. Token jest przechowywany w pamięci i odnawiany automatycznie gdy wygaśnie.

---

## Sensory

| Encja | Opis | Jednostka |
|---|---|---|
| `sensor.orlen_gas_saldo` | Aktualne saldo konta | PLN |
| `sensor.orlen_gas_ostatnia_faktura` | Kwota ostatniej faktury | PLN |
| `sensor.orlen_gas_data_ostatniej_faktury` | Data rozliczenia ostatniej faktury | — |
| `sensor.orlen_gas_zuzycie_roczne` | Suma zużycia z ostatnich 12 miesięcy | m³ |
| `sensor.orlen_gas_biezacy_miesiac` | Zużycie w bieżącym miesiącu | m³ |
| `sensor.orlen_gas_poprzedni_miesiac` | Zużycie w poprzednim miesiącu | m³ |
| `sensor.orlen_gas_miesiac_minus_2` … `_minus_11` | Zużycie w starszych miesiącach | m³ |

### Atrybuty sensora salda ostatniej faktury

- `number` — numer faktury
- `start_date` / `end_date` — okres rozliczeniowy
- `wear_m3` — zużycie w m³
- `wear_kwh` — zużycie w kWh
- `is_paid` — czy faktura jest opłacona
- `amount_to_pay` — kwota do zapłaty

### Atrybuty sensorów miesięcznych

- `month` — klucz miesiąca (np. `2025-11`)
- `is_settlement` — `true` jeśli miesiąc wykryto jako wyrównanie po odczycie

---

## Uwagi

**Wyrównania po odczycie rzeczywistym** — myORLEN rozlicza gaz szacunkowo między odczytami. Po odczycie rzeczywistym pojawia się faktura wyrównująca, która może zawierać wielomiesięczne zużycie. Integracja rozkłada je proporcjonalnie na dni i oznacza jako `is_settlement: true` gdy wartość przekracza 3× średnią.

**Częstotliwość odświeżania** — dane są pobierane co 24 godziny.

---

## Licencja

MIT
