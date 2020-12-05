from typing import Optional
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    events = hass.data[DOMAIN][entry.entry_id]["events"]
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    camData = hass.data[DOMAIN][entry.entry_id]["camData"]
    entities = {
        event.uid: TapoBinarySensor(event.uid, events, name, camData)
        for event in events.get_platform("binary_sensor")
    }

    async_add_entities(entities.values())

    @callback
    def async_check_entities():
        new_entities = []
        for event in events.get_platform("binary_sensor"):
            if event.uid not in entities:
                entities[event.uid] = TapoBinarySensor(event.uid, events, name, camData)
                new_entities.append(entities[event.uid])
        async_add_entities(new_entities)

    events.async_add_listener(async_check_entities)

    return True


class TapoBinarySensor(BinarySensorEntity):
    def __init__(self, uid, events, name, camData):
        self._name = name
        self._attributes = camData["basic_info"]
        BinarySensorEntity.__init__(self)

        self.uid = uid
        self.events = events

    @property
    def is_on(self) -> bool:
        return self.events.get_uid(self.uid).value

    @property
    def name(self) -> str:
        return f"{self._name} - Motion"

    @property
    def device_class(self) -> Optional[str]:
        return self.events.get_uid(self.uid).device_class

    @property
    def unique_id(self) -> str:
        return self.uid

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.events.get_uid(self.uid).entity_enabled

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, slugify(f"{self._attributes['mac']}_tapo_control"))
            },
            "name": self._attributes["device_alias"],
            "manufacturer": "TP-Link",
            "model": self._attributes["device_model"],
            "sw_version": self._attributes["sw_version"],
        }

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return "TP-Link"

    async def async_added_to_hass(self):
        self.async_on_remove(self.events.async_add_listener(self.async_write_ha_state))
