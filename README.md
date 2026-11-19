# Rekuperator Compit AERO 4A + NANO COLOR w Home Assistant (magistrala C14)

## Sprzęt
- Konwerter RS485→WiFi USR-DR164 podpięty do zacisków A2/B2 (+ G) panelu NANO COLOR (magistrala C14).
- Ustawienia DR164: tryb transparent, TCP Server, port 502, 9600 bodów, 8N1, funkcje Modbus wyłączone.

## Instalacja przez HACS
HACS → ⋮ → Custom repositories → `https://github.com/mnowak3/ha-compit-c14`, typ **Integration** → pobierz → restart HA.

## Instalacja ręczna
1. Skopiuj folder `custom_components/compit_c14` do `/config/custom_components/` (np. przez File editor albo Samba).
2. Uruchom ponownie Home Assistant.
3. Ustawienia → Urządzenia i usługi → Dodaj integrację → „Compit C14 (rekuperator Aero 4A)”.
4. Wpisz IP konwertera i port 502.

Pojawi się urządzenie **Rekuperator (Compit AERO 4A + NANO COLOR)** z encjami:
- temperatury: nawiew, wywiew, czerpnia, wyrzutnia, zadana nawiewu, pomieszczenie (NANO), zadana pomieszczenia
- CO2, PM2,5, PM10 (jeśli jest czujnik jakości powietrza na C14)
- wentylator nawiewu/wywiewu (%), wydajność zadana, bieg
- bypass aktywny, wietrzenie aktywne, harmonogram aktywny, połączenie z magistralą
- przełącznik Wietrzenie, wybór Tryb wentylacji (Stop / Bieg 1–3 / Harmonogram), Tryb bypassu
- nastawy (konfiguracja): temperatury zadane, korekta termostatu, osuszanie, limit CO2, obroty biegów nawiewu/wywiewu/AO3, min/max nawiewu, progi GWC, próg bypassu

Usługi: `compit_c14.wietrzenie` (minuty), `compit_c14.zapisz_rejestr`, `compit_c14.odczytaj_rejestry`.

Uwaga: integracja nieoficjalna, protokół C14 odczytany z ruchu na magistrali. Testowane na jednym zestawie (NANO COLOR CTP 2020 + AERO 4A). Używasz na własną odpowiedzialność.

Podziękowania: opis protokołu C14 na podstawie projektu [d-lebed/esphome-awenta-auros](https://github.com/d-lebed/esphome-awenta-auros).

Licencja: MIT.
