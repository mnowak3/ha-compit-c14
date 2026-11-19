from homeassistant.components.select import SelectEntity

from . import DOMAIN, REG_BYPASS, REG_FAN_MODE, SIGNAL
from .entity import C14Entity
from homeassistant.helpers.dispatcher import async_dispatcher_send

GEARS = ["Stop", "Bieg 1", "Bieg 2", "Bieg 3", "Harmonogram"]
BYPASS = ["Wyłączony", "Auto", "Włączony"]


async def async_setup_entry(hass, entry, add):
    hub = hass.data[DOMAIN][entry.entry_id]
    add([C14Gear(hub), C14Bypass(hub)])


class C14Gear(C14Entity, SelectEntity):
    _attr_options = GEARS
    _attr_icon = "mdi:fan"

    def __init__(self, hub):
        super().__init__(hub, "tryb_wentylacji", "Tryb wentylacji")

    @property
    def current_option(self):
        x = self.hub.expected(REG_FAN_MODE)
        if x is not None:
            obs = 4 if self.hub.data.get("schedule") else self.hub.data.get("gear")
            if obs == x and REG_FAN_MODE not in self.hub.pending:
                self.hub.expect.pop(REG_FAN_MODE, None)
            return GEARS[x]
        if self.hub.data.get("schedule"):
            return "Harmonogram"
        g = self.hub.data.get("gear")
        return GEARS[g] if g is not None and 0 <= g <= 3 else None

    async def async_select_option(self, option):
        self.hub.write(REG_FAN_MODE, GEARS.index(option))
        async_dispatcher_send(self.hass, SIGNAL)


class C14Bypass(C14Entity, SelectEntity):
    _attr_options = BYPASS
    _attr_icon = "mdi:valve"

    def __init__(self, hub):
        super().__init__(hub, "tryb_bypass", "Tryb bypassu")
        self._val = "Auto"

    @property
    def current_option(self):
        x = self.hub.expected(REG_BYPASS)
        if x is not None:
            return BYPASS[x]
        return self._val

    async def async_select_option(self, option):
        self._val = option
        self.hub.write(REG_BYPASS, BYPASS.index(option))
        async_dispatcher_send(self.hass, SIGNAL)
