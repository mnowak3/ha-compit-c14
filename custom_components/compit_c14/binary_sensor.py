from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from . import DOMAIN
from .entity import C14Entity


async def async_setup_entry(hass, entry, add):
    hub = hass.data[DOMAIN][entry.entry_id]
    add([
        C14Bin(hub, "bypass_active", "Bypass aktywny", None),
        C14Bin(hub, "airing", "Wietrzenie aktywne", BinarySensorDeviceClass.RUNNING),
        C14Bin(hub, "schedule", "Harmonogram aktywny", None),
        C14Conn(hub),
    ])


class C14Bin(C14Entity, BinarySensorEntity):
    def __init__(self, hub, key, name, dc):
        super().__init__(hub, key, name)
        self._attr_device_class = dc

    def key_available(self):
        return self.key in self.hub.data

    @property
    def is_on(self):
        return bool(self.hub.data.get(self.key))


class C14Conn(C14Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hub):
        super().__init__(hub, "polaczenie", "Połączenie z magistralą")

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.hub.link_ok
