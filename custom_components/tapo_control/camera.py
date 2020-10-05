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
    platform.async_register_entity_service(
        SERVICE_SET_PRIVACY_MODE, SCHEMA_SERVICE_SET_PRIVACY_MODE, "set_privacy_mode",
    )
    platform.async_register_entity_service(
        SERVICE_PTZ, SCHEMA_SERVICE_PTZ, "ptz",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ALARM_MODE, SCHEMA_SERVICE_SET_ALARM_MODE, "set_alarm_mode",
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
        if(self._basic_info['device_model'] in DEVICES_WITH_NO_PRESETS):
            self._attributes['presets'] = {}
        else:
            self._attributes['presets'] = self._controller.getPresets()
    
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
        if(self._basic_info['device_model'] in DEVICES_WITH_NO_PRESETS):
            self._attributes['presets'] = {}
        else:
            self._attributes['presets'] = self._controller.getPresets()

    def ptz(self, tilt = None, pan = None, preset = None, distance = None):
        if preset:
            if(preset.isnumeric()):
                self._controller.setPreset(preset)
            else:
                foundKey = False
                for key, value in self._attributes['presets'].items():
                    if value == preset:
                        foundKey = key
                if(foundKey):
                    self._controller.setPreset(foundKey)
                else:
                    _LOGGER.error("Preset "+preset+" does not exist.")
        elif tilt:
            if distance:
                distance = float(distance)
                if(distance >= 0 and distance <= 1):
                    degrees = 68 * distance
                else:
                    degrees = 5
            else:
                degrees = 5
            if tilt == "UP":
                self._controller.moveMotor(0,degrees)
            else:
                self._controller.moveMotor(0,-degrees)
        elif pan:
            if distance:
                distance = float(distance)
                if(distance >= 0 and distance <= 1):
                    degrees = 360 * distance
                else:
                    degrees = 5
            else:
                degrees = 5
            if pan == "RIGHT":
                self._controller.moveMotor(degrees,0)
            else:
                self._controller.moveMotor(-degrees,0)
        else:
            _LOGGER.error("Incorrect additional PTZ properties. You need to specify at least one of " + TILT + ", " + PAN + ", " + PRESET + ".")

    def set_privacy_mode(self, privacy_mode: str):
        if(privacy_mode == "on"):
            self._controller.setPrivacyMode(True)
        else:
            self._controller.setPrivacyMode(False)

    def set_alarm_mode(self, alarm_mode, sound = None, light = None):
        if(not light):
            light = "on"
        if(not sound):
            sound = "on"
        if(alarm_mode == "on"):
            self._controller.setAlarm(True, True if sound == "on" else False, True if light == "on" else False)
        else:
            self._controller.setAlarm(False, True if sound == "on" else False, True if light == "on" else False)

    def set_led_mode(self, led_mode: str):
        if(led_mode == "on"):
            self._controller.setLEDEnabled(True)
        else:
            self._controller.setLEDEnabled(False)
