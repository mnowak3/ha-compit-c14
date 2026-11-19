"""Compit C14 bus listener/writer over a transparent RS485-TCP converter (USR-DR164)."""
import asyncio
import logging
import time

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
DOMAIN = "compit_c14"
SIGNAL = "compit_c14_update"
PLATFORMS = ["sensor", "binary_sensor", "switch", "select", "number"]
LINK_TIMEOUT = 60  # s bez ramek, po których połączenie uznajemy za zerwane

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_PORT, default=502): cv.port})},
    extra=vol.ALLOW_EXTRA,
)

REG_AIRING = 81
REG_FAN_MODE = 80
REG_BYPASS = 79


def _pair(h, l):
    return ((h & 0x7F) << 7) | (l & 0x7F)


def _chk(f):
    return sum(b for i, b in enumerate(f) if i != 2) & 0x7F


class Hub:
    def __init__(self, hass, host, port):
        self.hass = hass
        self.host = host
        self.port = port
        self.data = {}
        self.pending = {}          # reg -> value
        self.expect = {}           # reg -> (value, until)
        self.attempts = 0
        self.writer = None
        self.connected = False
        self.last_frame = 0
        self.airing_until = None
        self._unsub_air = None
        self._unsub_tick = None
        self._task = None
        self._stop = False
        self.raw = {}              # "dst cmd src" -> (time, hex) — podgląd ramek do analizy
        self.read_regs = []        # rejestry do odczytu zapytaniem R
        self.read_log = []         # ramki po wysłaniu zapytania R
        self.read_until = 0
        self.regs = {}             # rejestr -> wartość z odpowiedzi R
        self.watch_regs = []       # nastawy odświeżane co 10 min
        self._unsub_refresh = None

    @property
    def link_ok(self):
        return (time.time() - self.last_frame) < LINK_TIMEOUT

    # ---------- frames ----------
    def _decode(self, f):
        d = self.data
        dst, cmd, src = f[0], f[1], f[3]
        self.raw[f"{dst:02X} {cmd:02X} {src:02X}"] = (round(time.time()), f.hex(" "))
        if time.time() < self.read_until and len(self.read_log) < 40:
            self.read_log.append(f.hex(" "))
        if dst == 0xE4 and cmd == 0x21 and src == 0x29:      # panel status
            d["room_temp"] = (_pair(f[12], f[13]) - 2000) / 10
            d["room_target"] = (_pair(f[14], f[15]) - 2000) / 10
            d["schedule"] = bool(f[5] & 0x10)
            d["away"] = bool(f[5] & 0x04)
            d["airing_panel"] = bool(f[27] & 0x20)
            g = {1: 0, 3: 1, 5: 2, 7: 3}.get(f[28] & 0x0F)
            if g is not None:
                d["panel_gear"] = g
                d["gear"] = g          # bieg zawsze z ramki panelu NANO
        elif dst == 0xE4 and cmd == 0x21 and src == 0x63:    # aero telemetry
            d["t_czerpnia"] = (_pair(f[10], f[11]) - 2000) / 10  # T1, dwa bajty
            d["t_nawiew"] = (_pair(f[12], f[13]) - 2000) / 10
            d["t_wyrzut"] = f[16] - 40
            d["t_wywiew"] = f[17] - 40
            d["t_nawiew_zadana"] = (_pair(f[18], f[19]) - 2000) / 10
            d["wydajnosc"] = f[22]
            d["fan_supply"] = f[25]
            d["fan_exhaust"] = f[26]
            d["aero_gear_raw"] = f[8]  # tylko diagnostyka, nie używane jako bieg
            d["airing"] = bool(f[9] & 0x20)
            d["bypass_active"] = bool(f[28] & 0x20)
        elif dst == 0xA9 and cmd == 0x21 and src == 0x50:    # air quality sensor
            d["pm25"] = _pair(f[14], f[15]) - 2000
            d["pm10"] = _pair(f[16], f[17]) - 2000
            d["co2"] = _pair(f[18], f[19]) - 2000
        elif dst == 0xF0 and cmd == 0x44:                    # iNext poll -> our window
            self.hass.async_create_task(self._send_pending())
            return False
        elif dst == 0xF0 and cmd == 0x72:                    # 'r' odpowiedź na odczyt
            for k in range(6):
                reg = _pair(f[5 + 4 * k], f[6 + 4 * k])
                if reg:
                    self.regs[reg] = _pair(f[7 + 4 * k], f[8 + 4 * k]) - 2000
            return True
        elif dst == 0xF0 and cmd == 0x77:                    # 'w' confirmation
            for k in range(6):
                reg = _pair(f[5 + 4 * k], f[6 + 4 * k])
                if reg in self.pending:
                    self.pending.pop(reg, None)
            self.attempts = 0
        else:
            return False
        return True

    def _build_w(self, items):
        f = [0xA9, 0x57, 0, 0x70, 0x00]
        for k in range(6):
            if k < len(items):
                reg, val = items[k]
                v = int(val) + 2000
                f += [(reg >> 7) & 0x7F, reg & 0x7F, (v >> 7) & 0x7F, v & 0x7F]
            else:
                f += [0x00, 0x00, 0x0F, 0x50]
        f.append(0x23)
        f[2] = _chk(f)
        return bytes(f)

    @callback
    def _notify(self, _now=None):
        async_dispatcher_send(self.hass, SIGNAL)

    @callback
    def _refresh(self, _now=None):
        self.queue_read(self.watch_regs)

    def queue_read(self, regs, delay=0):
        @callback
        def _add(_n=None):
            for r in regs:
                if r not in self.read_regs:
                    self.read_regs.append(r)
        if delay:
            async_call_later(self.hass, delay, _add)
        else:
            _add()

    def _build_r(self, regs):
        f = [0xA9, 0x52, 0, 0x70, 0x00]
        for k in range(6):
            if k < len(regs):
                reg = regs[k]
                f += [(reg >> 7) & 0x7F, reg & 0x7F, 0x0F, 0x50]
            else:
                f += [0x00, 0x00, 0x0F, 0x50]
        f.append(0x23)
        f[2] = _chk(f)
        return bytes(f)

    async def _send_pending(self):
        if not self.pending and self.read_regs and self.writer:
            regs, self.read_regs = self.read_regs[:6], self.read_regs[6:]
            await asyncio.sleep(0.04)
            frame = self._build_r(regs)
            self.read_log = ["TX " + frame.hex(" ")]
            self.read_until = time.time() + 6
            self.writer.write(frame)
            await self.writer.drain()
            async_call_later(self.hass, 7, self._notify)
            return
        if not self.pending or not self.writer:
            return
        if self.attempts >= 8:
            _LOGGER.warning("C14: brak potwierdzenia zapisu %s, rezygnuję", self.pending)
            self.pending.clear()
            self.attempts = 0
            return
        await asyncio.sleep(0.04)
        frame = self._build_w(list(self.pending.items())[:6])
        try:
            self.writer.write(frame)
            await self.writer.drain()
            self.attempts += 1
            _LOGGER.debug("C14 TX %s (próba %s)", frame.hex(" "), self.attempts)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("C14 write error: %s", err)

    def write(self, reg, value):
        self.pending[reg] = int(value)
        self.expect[reg] = (int(value), time.time() + 30)
        self.attempts = 0
        async_call_later(self.hass, 31, self._notify)

    def expected(self, reg):
        e = self.expect.get(reg)
        if e and time.time() < e[1]:
            return e[0]
        self.expect.pop(reg, None)
        return None

    # ---------- airing timer ----------
    def start_airing(self, minutes):
        self.write(REG_AIRING, 1)
        if self._unsub_air:
            self._unsub_air()
            self._unsub_air = None
        if minutes and minutes > 0:
            self.airing_until = time.time() + minutes * 60
            self._unsub_air = async_call_later(self.hass, minutes * 60, self._airing_timeout)
        else:
            self.airing_until = None
        async_dispatcher_send(self.hass, SIGNAL)

    def stop_airing(self):
        self.write(REG_AIRING, 0)
        self.airing_until = None
        if self._unsub_air:
            self._unsub_air()
            self._unsub_air = None
        async_dispatcher_send(self.hass, SIGNAL)

    async def _airing_timeout(self, _now):
        self._unsub_air = None
        self.stop_airing()

    # ---------- loop ----------
    async def run(self):
        buf = bytearray()
        while not self._stop:
            try:
                reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 10)
                self.connected = True
                buf.clear()
                while not self._stop:
                    chunk = await asyncio.wait_for(reader.read(1024), 60)
                    if not chunk:
                        raise ConnectionError("closed")
                    buf += chunk
                    changed = False
                    while len(buf) >= 30:
                        start = next((i for i in range(len(buf) - 29) if buf[i] & 0x80 and buf[i + 29] == 0x23), -1)
                        if start < 0:
                            del buf[: len(buf) - 29]
                            break
                        f = bytes(buf[start:start + 30])
                        del buf[: start + 30]
                        if _chk(f) != f[2]:
                            continue
                        self.last_frame = time.time()
                        if self._decode(f):
                            changed = True
                    if changed:
                        async_dispatcher_send(self.hass, SIGNAL)
            except asyncio.CancelledError:
                break
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("C14 connection problem: %s", err)
            self.connected = False
            if self.writer:
                try:
                    self.writer.close()
                except Exception:  # noqa: BLE001
                    pass
            self.writer = None
            if not self._stop:
                await asyncio.sleep(2)

    def start(self):
        self._task = self.hass.loop.create_task(self.run())
        # odświeżanie co 15 s, żeby wskaźnik połączenia zmieniał się także bez nowych ramek
        self._unsub_tick = async_track_time_interval(
            self.hass, self._notify, timedelta(seconds=15)
        )
        self._unsub_refresh = async_track_time_interval(
            self.hass, self._refresh, timedelta(minutes=10)
        )

    async def stop(self, *_):
        self._stop = True
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None
        if self._task:
            self._task.cancel()


def _parse_regs(s):
    out = []
    for part in s.replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


async def async_setup(hass, config):
    """Konfiguracja z YAML jest jednorazowo przenoszona do wpisu w interfejsie."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config[DOMAIN]))
        )

    hub_of = lambda: next(iter(hass.data.get(DOMAIN, {}).values()), None)

    async def svc_airing(call):
        hub = hub_of()
        if not hub:
            return
        minutes = int(call.data.get("minuty", 15))
        if minutes <= 0:
            hub.stop_airing()
        else:
            hub.start_airing(minutes)

    async def svc_write(call):
        hub = hub_of()
        if hub:
            hub.write(int(call.data["rejestr"]), int(call.data["wartosc"]))

    hass.services.async_register(DOMAIN, "wietrzenie", svc_airing)
    async def svc_read(call):
        hub = hub_of()
        if hub:
            hub.read_regs = _parse_regs(str(call.data["rejestry"]))

    hass.services.async_register(DOMAIN, "zapisz_rejestr", svc_write)
    hass.services.async_register(DOMAIN, "odczytaj_rejestry", svc_read)
    return True


async def async_setup_entry(hass, entry: ConfigEntry):
    hub = Hub(hass, entry.data[CONF_HOST], entry.data.get(CONF_PORT, 502))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    hub.start()
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.stop))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry: ConfigEntry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub = hass.data[DOMAIN].pop(entry.entry_id, None)
    if hub:
        await hub.stop()
    return ok
