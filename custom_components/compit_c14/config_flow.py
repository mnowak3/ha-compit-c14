import asyncio

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from . import DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Optional(CONF_PORT, default=502): int})


async def _probe(host, port):
    try:
        _r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 5)
        w.close()
        return True
    except Exception:  # noqa: BLE001
        return False


class C14ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id("aero4a")
            self._abort_if_unique_id_configured()
            if await _probe(user_input[CONF_HOST], user_input[CONF_PORT]):
                return self.async_create_entry(title="Rekuperator AERO 4A", data=user_input)
            errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_import(self, data):
        await self.async_set_unique_id("aero4a")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Rekuperator AERO 4A", data={CONF_HOST: data[CONF_HOST], CONF_PORT: data.get(CONF_PORT, 502)}
        )
