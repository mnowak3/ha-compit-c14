from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, PERCENTAGE, UnitOfTemperature

from . import DOMAIN
from .entity import C14Entity

T = (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)
SENSORS = [
    ("t_nawiew", "Temperatura nawiewu", *T),
    ("t_wywiew", "Temperatura wywiewu", *T),
    ("t_czerpnia", "Temperatura czerpni", *T),
    ("t_wyrzut", "Temperatura wyrzutni", *T),
    ("t_nawiew_zadana", "Zadana temperatura nawiewu", *T),
    ("room_temp", "Temperatura pomieszczenia (NANO)", *T),
    ("room_target", "Zadana temperatura pomieszczenia", *T),
    ("co2", "CO2", SensorDeviceClass.CO2, CONCENTRATION_PARTS_PER_MILLION),
    ("pm25", "PM2,5 (% normy)", None, PERCENTAGE),
    ("pm10", "PM10 (% normy)", None, PERCENTAGE),
    ("fan_supply", "Wentylator nawiewu", None, PERCENTAGE),
    ("fan_exhaust", "Wentylator wywiewu", None, PERCENTAGE),
    ("wydajnosc", "Wydajność zadana", None, PERCENTAGE),
    ("gear", "Bieg", None, None),
]


async def async_setup_entry(hass, entry, add):
    hub = hass.data[DOMAIN][entry.entry_id]
    add([C14Sensor(hub, *s) for s in SENSORS] + [C14Frames(hub)])


class C14Sensor(C14Entity, SensorEntity):
    def __init__(self, hub, key, name, dc, unit):
        super().__init__(hub, key, name)
        self._attr_device_class = dc
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT

    def key_available(self):
        return self.key in self.hub.data

    @property
    def native_value(self):
        return self.hub.data.get(self.key)


class C14Frames(C14Entity, SensorEntity):
    """Diagnostyka: ostatnia ramka każdego typu z magistrali (do analizy nastaw)."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-brackets"
    _unrecorded_attributes = frozenset({"ramki", "odczyt", "rejestry"})

    def __init__(self, hub):
        super().__init__(hub, "ramki", "Ramki C14")

    @property
    def native_value(self):
        return len(self.hub.raw)

    @property
    def extra_state_attributes(self):
        return {"ramki": {k: v[1] for k, v in sorted(self.hub.raw.items())}, "bajt8_aero": self.hub.data.get("aero_gear_raw"), "odczyt": self.hub.read_log, "rejestry": dict(sorted(self.hub.regs.items())), "w_kolejce": len(self.hub.read_regs)}
