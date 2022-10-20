from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import BRAND, DOMAIN, LOGGER, CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, ENABLE_SOUND_DETECTION, SOUND_DETECTION_PEAK, SOUND_DETECTION_DURATION, SOUND_DETECTION_RESET
from .utils import build_device_info

import haffmpeg.sensor as ffmpeg_sensor
import urllib.parse

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    LOGGER.debug("Setting up binary sensor for motion.")
    events = hass.data[DOMAIN][entry.entry_id]["events"]
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    camData = hass.data[DOMAIN][entry.entry_id]["camData"]
    entities = {
        event.uid: TapoMotionSensor(event.uid, events, name, camData)
        for event in events.get_platform("binary_sensor")
    }

    LOGGER.debug("Creating binary sensor entity.")
    async_add_entities(entities.values())
    
    binarySensors = []
    LOGGER.debug("Adding TapoSoundBinarySensor...")
    binarySensors.append(TapoSoundBinarySensor(hass.data[DOMAIN][entry.entry_id], hass, entry))
    async_add_entities(binarySensors)

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
                entities[event.uid] = TapoMotionSensor(event.uid, events, name, camData)
                new_entities.append(entities[event.uid])
        async_add_entities(new_entities)
        LOGGER.debug(new_entities)

    events.async_add_listener(async_check_entities)

    return True


class TapoMotionSensor(BinarySensorEntity):
    def __init__(self, uid, events, name, camData):
        LOGGER.debug("TapoMotionSensor - init - start")
        self._name = name
        self._attributes = camData["basic_info"]
        BinarySensorEntity.__init__(self)

        self.uid = uid
        self.events = events
        LOGGER.debug("TapoMotionSensor - init - end")

    @property
    def is_on(self) -> bool:
        return self.events.get_uid(self.uid).value

    @property
    def name(self) -> str:
        return f"{self._name} Motion"

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


class TapoSoundBinarySensor(TapoBinarySensorEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoSoundBinarySensor - init - start")
        self._config_entry = config_entry
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._enable_sound_detection = True #config_entry.data.get(ENABLE_SOUND_DETECTION)
        self._sound_detection_peak = config_entry.data.get(SOUND_DETECTION_PEAK)
        self._sound_detection_duration = config_entry.data.get(SOUND_DETECTION_DURATION)
        self._sound_detection_reset = config_entry.data.get(SOUND_DETECTION_RESET)
        hass.data[DOMAIN][config_entry.entry_id]["noiseSensorStarted"] = False

        if self._enable_sound_detection:
            self._noiseSensor = ffmpeg_sensor.SensorNoise(
                self._ffmpeg.binary, self._noiseCallback
            )
            self._noiseSensor.set_options(
                time_duration=int(self._sound_detection_duration),
                time_reset=int(self._sound_detection_reset),
                peak=int(self._sound_detection_peak),
            )

        TapoBinarySensorEntity.__init__(self, "Sound", entry, hass, config_entry, None, BinarySensorDeviceClass.SOUND)

        self._entry["entities"].append(self)
        self.updateTapo(self._entry["camData"])
        self._is_cam_entity = True
        LOGGER.debug("TapoSoundBinarySensor - init - end")

    @callback
    def _noiseCallback(self, noiseDetected):
        self._attr_is_on = noiseDetected
        for entity in self._entry["entities"]:
            if entity._enabled:
                entity.async_write_ha_state()


    async def startNoiseDetection(self):
        self._entry["noiseSensorStarted"] = True
        await self._noiseSensor.open_sensor(
            input_source=self.getStreamSource(), extra_cmd="-nostats",
        )

    def getStreamSource(self):
        host = self._config_entry.data.get(CONF_IP_ADDRESS)
        username = urllib.parse.quote_plus(self._config_entry.data.get(CONF_USERNAME))
        password = urllib.parse.quote_plus(self._config_entry.data.get(CONF_PASSWORD))
        custom_stream = self._config_entry.data.get(CONF_CUSTOM_STREAM)

        if custom_stream != "":
            return custom_stream

        # if self._hdstream:
        streamType = "stream1"
        # else:
        #     streamType = "stream2"
        return f"rtsp://{username}:{password}@{host}:554/{streamType}"

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
