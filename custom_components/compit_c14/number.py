"""Nastawy rekuperatora (rejestry panelu NANO) — odczyt zapytaniem R, zapis W z opóźnieniem."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_call_later

from . import DOMAIN
from .entity import C14Entity

C = UnitOfTemperature.CELSIUS
# (rejestr, klucz, nazwa, min, max, krok, skala, jednostka)
SETTINGS = [
    (3, "t_komfort", "Temperatura zadana komfortowa", 10, 30, 0.5, 10, C),
    (4, "t_eko_zima", "Temperatura zadana eko zima", 10, 30, 0.5, 10, C),
    (5, "t_eko_chlodzenie", "Temperatura zadana eko chłodzenie", 10, 30, 0.5, 10, C),
    (6, "t_reczna", "Temperatura zadana praca ręczna", 10, 30, 0.5, 10, C),
    (7, "t_poza_domem", "Temperatura zadana poza domem", 10, 30, 0.5, 10, C),
    (8, "korekta_termostatu", "Korekta termostatu", -5, 5, 0.5, 10, C),
    (18, "osuszanie_start", "Start osuszania", 30, 100, 1, 1, PERCENTAGE),
    (19, "osuszanie_stop", "Stop osuszania", 30, 100, 1, 1, PERCENTAGE),
    (20, "co2_limit", "Dopuszczalne stężenie CO2", 400, 2000, 10, 1, "ppm"),
    (141, "nawiew_bieg1", "Nawiew obroty biegu 1", 10, 100, 1, 1, PERCENTAGE),
    (142, "nawiew_bieg2", "Nawiew obroty biegu 2", 10, 100, 1, 1, PERCENTAGE),
    (143, "nawiew_bieg3", "Nawiew obroty biegu 3", 10, 100, 1, 1, PERCENTAGE),
    (144, "nawiew_wietrzenie", "Nawiew obroty wietrzenia", 10, 100, 1, 1, PERCENTAGE),
    (145, "wywiew_bieg1", "Wywiew obroty biegu 1", 10, 100, 1, 1, PERCENTAGE),
    (146, "wywiew_bieg2", "Wywiew obroty biegu 2", 10, 100, 1, 1, PERCENTAGE),
    (147, "wywiew_bieg3", "Wywiew obroty biegu 3", 10, 100, 1, 1, PERCENTAGE),
    (148, "wywiew_wietrzenie", "Wywiew obroty wietrzenia", 10, 100, 1, 1, PERCENTAGE),
    (149, "ao3_bieg1", "AO3 obroty biegu 1", 0, 100, 1, 1, PERCENTAGE),
    (150, "ao3_bieg2", "AO3 obroty biegu 2", 0, 100, 1, 1, PERCENTAGE),
    (151, "ao3_bieg3", "AO3 obroty biegu 3", 0, 100, 1, 1, PERCENTAGE),
    (152, "ao3_wietrzenie", "AO3 obroty wietrzenia", 0, 100, 1, 1, PERCENTAGE),
    (153, "t_nawiew_min", "Temperatura nawiewu minimum", 10, 30, 1, 1, C),
    (154, "t_nawiew_max", "Temperatura nawiewu maksimum", 15, 40, 1, 1, C),
    (172, "gwc_zima", "Praca GWC zima (próg)", -20, 20, 1, 1, C),
    (173, "gwc_lato", "Praca GWC lato (próg)", 10, 40, 1, 1, C),
    (174, "bypass_prog", "T. zewnętrzna zezwolenia bypassu", 10, 40, 1, 1, C),
]
REGS = [s[0] for s in SETTINGS]
WRITE_DELAY = 3


async def async_setup_entry(hass, entry, add):
    hub = hass.data[DOMAIN][entry.entry_id]
    hub.watch_regs = REGS
    hub.queue_read(REGS, delay=20)
    add([C14Setting(hub, *s) for s in SETTINGS])


class C14Setting(C14Entity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, hub, reg, key, name, lo, hi, step, scale, unit):
        super().__init__(hub, key, name)
        self.reg = reg
        self.scale = scale
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._unsub = None
        self._want = None

    def key_available(self):
        return self.reg in self.hub.regs

    @property
    def native_value(self):
        if self._want is not None:
            return self._want
        x = self.hub.expected(self.reg)
        raw = x if x is not None else self.hub.regs.get(self.reg)
        return None if raw is None else raw / self.scale

    async def async_set_native_value(self, value):
        self._want = value
        if self._unsub:
            self._unsub()
        self._unsub = async_call_later(self.hass, WRITE_DELAY, self._commit)
        self.async_write_ha_state()

    async def _commit(self, _now):
        self._unsub = None
        raw = int(round(self._want * self.scale))
        self._want = None
        if self.hub.regs.get(self.reg) != raw:
            self.hub.write(self.reg, raw)
            self.hub.regs[self.reg] = raw
            self.hub.queue_read([self.reg], delay=40)
        self.async_write_ha_state()
