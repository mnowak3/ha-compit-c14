from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from .entity import C14Entity


async def async_setup_entry(hass, entry, add):
    add([C14Airing(hass.data[DOMAIN][entry.entry_id])])


class C14Airing(C14Entity, SwitchEntity):
    _attr_icon = "mdi:weather-windy"

    def __init__(self, hub):
        super().__init__(hub, "wietrzenie", "Wietrzenie")

    @property
    def is_on(self):
        x = self.hub.expected(81)
        if x is not None:
            obs = bool(self.hub.data.get("airing") or self.hub.data.get("airing_panel"))
            if obs == bool(x) and 81 not in self.hub.pending:
                self.hub.expect.pop(81, None)
            return bool(x)
        return bool(self.hub.airing_until or self.hub.data.get("airing") or self.hub.data.get("airing_panel"))

    @property
    def extra_state_attributes(self):
        return {"koniec": self.hub.airing_until}

    async def async_turn_on(self, **kw):
        self.hub.start_airing(0)

    async def async_turn_off(self, **kw):
        self.hub.stop_airing()
