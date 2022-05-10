from typing import Optional
from .utils import build_device_info
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from .const import BRAND, DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    LOGGER.debug("Setting up binary sensor for motion.")
    events = hass.data[DOMAIN][entry.entry_id]["events"]
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    camData = hass.data[DOMAIN][entry.entry_id]["camData"]
    entities = {
        event.uid: TapoBinarySensor(event.uid, events, name, camData)
        for event in events.get_platform("binary_sensor")
    }

    LOGGER.debug("Creating binary sensor entity.")
    async_add_entities(entities.values())

    @callback
    def async_check_entities():
        LOGGER.debug("async_check_entities")
        new_entities = []
        LOGGER.debug("Looping through available events.")
        for event in events.get_platform("binary_sensor"):
            LOGGER.debug(event)
            if event.uid not in entities:
                LOGGER.debug(
                    "Found event which doesn't have entity yet, adding binary sensor!"
                )
                entities[event.uid] = TapoBinarySensor(event.uid, events, name, camData)
                new_entities.append(entities[event.uid])
        async_add_entities(new_entities)
        LOGGER.debug(new_entities)

    events.async_add_listener(async_check_entities)

    return True


class TapoBinarySensor(BinarySensorEntity):
    def __init__(self, uid, events, name, camData):
        LOGGER.debug("TapoBinarySensor - init - start")
        self._name = name
        self._attributes = camData["basic_info"]
        BinarySensorEntity.__init__(self)

        self.uid = uid
        self.events = events
        LOGGER.debug("TapoBinarySensor - init - end")

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
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    async def async_added_to_hass(self):
        self.async_on_remove(self.events.async_add_listener(self.async_write_ha_state))
