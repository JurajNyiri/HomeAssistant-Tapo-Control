from pytapo import Tapo
from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import logging
from .const import *
from .utils import *

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tapo: Cameras Control component from YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    try:
        tapoController = Tapo(host, username, password)

        hass.data[DOMAIN][entry.entry_id] = tapoController

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

    except Exception as e:
        _LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

"""
tapo = {}
tapoData = {}

def setup(hass, config):
    def update(event_time):
        for entity_id in tapo:
            tapoConnector = tapo[entity_id]
            manualUpdate(entity_id, tapoConnector)

    def manualUpdate(entity_id, tapoConnector):
        basicInfo = tapoConnector.getBasicInfo()
        attributes = basicInfo['device_info']['basic_info']
        if(not basicInfo['device_info']['basic_info']['device_model'] in DEVICES_WITH_NO_PRESETS):
            attributes['presets'] = tapoConnector.getPresets()
        tapoData[entity_id] = {}
        tapoData[entity_id]['state'] = "monitoring" # todo: better state
        tapoData[entity_id]['attributes'] = attributes

        hass.states.set(entity_id, tapoData[entity_id]['state'], tapoData[entity_id]['attributes'])

    def handle_ptz(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if PRESET in call.data:
                    preset = str(call.data.get(PRESET))
                    if(preset.isnumeric()):
                        tapo[entity_id].setPreset(preset)
                    else:
                        foundKey = False
                        presets = tapoData[entity_id]['attributes']['presets']
                        for key, value in presets.items():
                            if value == preset:
                                foundKey = key
                        if(foundKey):
                            tapo[entity_id].setPreset(foundKey)
                        else:
                            _LOGGER.error("Preset "+preset+" does not exist.")
                elif TILT in call.data:
                    tilt = call.data.get(TILT)
                    if DISTANCE in call.data:
                        distance = float(call.data.get(DISTANCE))
                        if(distance >= 0 and distance <= 1):
                            degrees = 68 * distance
                        else:
                            degrees = 5
                    else:
                        degrees = 5
                    if tilt == "UP":
                        tapo[entity_id].moveMotor(0,degrees)
                    elif tilt == "DOWN":
                        tapo[entity_id].moveMotor(0,-degrees)
                    else:
                        _LOGGER.error("Incorrect "+TILT+" value. Possible values: UP, DOWN.")
                elif PAN in call.data:
                    pan = call.data.get(PAN)
                    if DISTANCE in call.data:
                        distance = float(call.data.get(DISTANCE))
                        if(distance >= 0 and distance <= 1):
                            degrees = 360 * distance
                        else:
                            degrees = 5
                    else:
                        degrees = 5
                    if pan == "RIGHT":
                        tapo[entity_id].moveMotor(degrees,0)
                    elif pan == "LEFT":
                        tapo[entity_id].moveMotor(-degrees,0)
                    else:
                        _LOGGER.error("Incorrect "+PAN+" value. Possible values: RIGHT, LEFT.")
                else:
                    _LOGGER.error("Incorrect additional PTZ properties. You need to specify at least one of " + TILT + ", " + PAN + ", " + PRESET + ".")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_set_privacy_mode(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(PRIVACY_MODE in call.data):
                    privacy_mode = call.data.get(PRIVACY_MODE)
                    if(privacy_mode == "on"):
                        tapo[entity_id].setPrivacyMode(True)
                    elif(privacy_mode == "off"):
                        tapo[entity_id].setPrivacyMode(False)
                    else:
                        _LOGGER.error("Incorrect "+PRIVACY_MODE+" value. Possible values: on, off.")
                else:
                    _LOGGER.error("Please specify "+PRIVACY_MODE+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_set_alarm_mode(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(ALARM_MODE in call.data):
                    alarm_mode = call.data.get(ALARM_MODE)
                    sound = "on"
                    light = "on"
                    if(LIGHT in call.data):
                        light = call.data.get(LIGHT)
                    if(SOUND in call.data):
                        sound = call.data.get(SOUND)
                    if(alarm_mode == "on"):
                        tapo[entity_id].setAlarm(True, True if sound == "on" else False, True if light == "on" else False)
                    elif(alarm_mode == "off"):
                        tapo[entity_id].setAlarm(False, True if sound == "on" else False, True if light == "on" else False)
                    else:
                        _LOGGER.error("Incorrect "+ALARM_MODE+" value. Possible values: on, off.")
                else:
                    _LOGGER.error("Please specify "+ALARM_MODE+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_set_led_mode(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(LED_MODE in call.data):
                    led_mode = call.data.get(LED_MODE)
                    if(led_mode == "on"):
                        tapo[entity_id].setLEDEnabled(True)
                    elif(led_mode == "off"):
                        tapo[entity_id].setLEDEnabled(False)
                    else:
                        _LOGGER.error("Incorrect "+LED_MODE+" value. Possible values: on, off.")
                else:
                    _LOGGER.error("Please specify "+LED_MODE+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_set_motion_detection_mode(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(MOTION_DETECTION_MODE in call.data):
                    motion_detection_mode = call.data.get(MOTION_DETECTION_MODE)
                    if(motion_detection_mode == "high" or motion_detection_mode == "normal" or motion_detection_mode == "low"):
                        tapo[entity_id].setMotionDetection(True, motion_detection_mode)
                    elif(motion_detection_mode == "off"):
                        tapo[entity_id].setMotionDetection(False)
                    else:
                        _LOGGER.error("Incorrect "+MOTION_DETECTION_MODE+" value. Possible values: high, normal, low, off.")
                else:
                    _LOGGER.error("Please specify "+MOTION_DETECTION_MODE+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_set_auto_track_mode(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(AUTO_TRACK_MODE in call.data):
                    auto_track_mode = call.data.get(AUTO_TRACK_MODE)
                    if(auto_track_mode == "on"):
                        tapo[entity_id].setAutoTrackTarget(True)
                    elif(auto_track_mode == "off"):
                        tapo[entity_id].setAutoTrackTarget(False)
                    else:
                        _LOGGER.error("Incorrect "+AUTO_TRACK_MODE+" value. Possible values: on, off.")
                else:
                    _LOGGER.error("Please specify "+AUTO_TRACK_MODE+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_reboot(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                tapo[entity_id].reboot()
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_save_preset(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(NAME in call.data):
                    name = call.data.get(NAME)
                    if(not name == "" and not name.isnumeric()):
                        tapo[entity_id].savePreset(name)
                        update(None)
                    else:
                        _LOGGER.error("Incorrect "+NAME+" value. It cannot be empty or a number.")
                else:
                    _LOGGER.error("Please specify "+NAME+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")

    def handle_delete_preset(call):
        if ENTITY_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            if(isinstance(entity_id, list)):
                entity_id = entity_id[0]
            if entity_id in tapo:
                if(PRESET in call.data):
                    preset = str(call.data.get(PRESET))
                    if(preset.isnumeric()):
                        tapo[entity_id].deletePreset(preset)
                    else:
                        foundKey = False
                        presets = tapoData[entity_id]['attributes']['presets']
                        for key, value in presets.items():
                            if value == preset:
                                foundKey = key
                        if(foundKey):
                            tapo[entity_id].deletePreset(foundKey)
                        else:
                            _LOGGER.error("Preset "+preset+" does not exist.")
                else:
                    _LOGGER.error("Please specify "+PRESET+" value.")
            else:
                _LOGGER.error("Entity "+entity_id+" does not exist.")
        else:
            _LOGGER.error("Please specify "+ENTITY_ID+" value.")


    for camera in config[DOMAIN]:
        host = camera[CONF_HOST]
        username = camera[CONF_USERNAME]
        password = camera[CONF_PASSWORD]

        tapoConnector = Tapo(host, username, password)
        basicInfo = tapoConnector.getBasicInfo()

        entity_id = generateEntityIDFromName(basicInfo['device_info']['basic_info']['device_alias'])
        # handles conflicts if entity_id the same
        addTapoEntityID(tapo, entity_id,tapoConnector)


    for entity_id in tapo:
        tapoConnector = tapo[entity_id]
        manualUpdate(entity_id, tapoConnector)

    hass.services.register(DOMAIN, "ptz", handle_ptz)
    hass.services.register(DOMAIN, "set_privacy_mode", handle_set_privacy_mode)
    hass.services.register(DOMAIN, "set_alarm_mode", handle_set_alarm_mode)
    hass.services.register(DOMAIN, "set_led_mode", handle_set_led_mode)
    hass.services.register(DOMAIN, "set_motion_detection_mode", handle_set_motion_detection_mode)
    hass.services.register(DOMAIN, "set_auto_track_mode", handle_set_auto_track_mode)
    hass.services.register(DOMAIN, "reboot", handle_reboot)
    hass.services.register(DOMAIN, "save_preset", handle_save_preset)
    hass.services.register(DOMAIN, "delete_preset", handle_delete_preset)

    track_time_interval(hass, update, timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    
    return True
"""