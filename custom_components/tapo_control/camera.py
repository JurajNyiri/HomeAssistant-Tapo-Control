from .const import *
from .utils import *
from homeassistant.core import HomeAssistant
from typing import Callable
from homeassistant.helpers.entity import Entity
from pytapo import Tapo
from homeassistant.util import slugify
from homeassistant.helpers import entity_platform
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: dict, async_add_entities: Callable):
    async_add_entities([TapoCameraControl(entry, hass.data[DOMAIN][entry.entry_id])])

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SET_LED_MODE, SCHEMA_SERVICE_SET_LED_MODE, "set_led_mode",
    )


class TapoCameraControl(Entity):
    def __init__(self, entry: dict, controller: Tapo):
        self._basic_info = controller.getBasicInfo()['device_info']['basic_info']
        self._name = self._basic_info['device_alias']
        self._mac = self._basic_info['mac']
        self._controller = controller
        self._attributes = self._basic_info
        self._entry = entry
        self._state = "Monitoring"
        if(not self._basic_info['device_model'] in DEVICES_WITH_NO_PRESETS):
            self._attributes['presets'] = controller.getPresets()
    
    @property
    def icon(self) -> str:
        return "mdi:cctv"

    @property
    def name(self) -> str:
        return f"{self._name}"

    @property
    def unique_id(self) -> str:
        return slugify(f"{self._mac}_tapo_control")

    @property
    def device_state_attributes(self):
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
    
    def update(self):
        self.manualUpdate()

    def manualUpdate(self):
        self._basic_info = self._controller.getBasicInfo()['device_info']['basic_info']
        self._name = self._basic_info['device_alias']
        self._attributes = self._basic_info
        self._state = "Monitoring"
        if(not self._basic_info['device_model'] in DEVICES_WITH_NO_PRESETS):
            self._attributes['presets'] = self._controller.getPresets()

    def set_led_mode(self, led_mode: str):
        if(led_mode == "on"):
            self._controller.setLEDEnabled(True)
        else:
            self._controller.setLEDEnabled(False)
