import time

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import DOMAIN, SIGNAL


class C14Entity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hub, key, name):
        self.hub = hub
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"compit_c14_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "aero4a")}, name="Rekuperator", manufacturer="Compit", model="AERO 4A + NANO COLOR"
        )

    @property
    def available(self):
        return (time.time() - self.hub.last_frame) < 180 and self.key_available()

    def key_available(self):
        return True

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL, self.async_write_ha_state))
