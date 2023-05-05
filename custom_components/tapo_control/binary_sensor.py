from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.ffmpeg import DATA_FFMPEG

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from homeassistant.const import STATE_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util.enum import try_parse_enum

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    ENABLE_SOUND_DETECTION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_RESET,
)
from .utils import build_device_info, getStreamSource
from .tapo.entities import TapoBinarySensorEntity

import haffmpeg.sensor as ffmpeg_sensor


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    LOGGER.debug("Setting up binary sensor for motion.")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    hass.data[DOMAIN][config_entry.entry_id]["eventsListener"] = EventsListener(
        async_add_entities, hass, config_entry
    )

    binarySensors = []

    if config_entry.data.get(ENABLE_SOUND_DETECTION):
        LOGGER.debug("Adding TapoNoiseBinarySensor...")
        binarySensors.append(TapoNoiseBinarySensor(entry, hass, config_entry))

    if binarySensors:
        async_add_entities(binarySensors)

    return True


class TapoNoiseBinarySensor(TapoBinarySensorEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoNoiseBinarySensor - init - start")
        TapoBinarySensorEntity.__init__(
            self,
            "Noise",
            entry,
            hass,
            config_entry,
            None,
            BinarySensorDeviceClass.SOUND,
        )

        self._hass = hass
        self._config_entry = config_entry
        self._is_noise_sensor = True
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._enable_sound_detection = config_entry.data.get(ENABLE_SOUND_DETECTION)
        self._sound_detection_peak = config_entry.data.get(SOUND_DETECTION_PEAK)
        self._sound_detection_duration = config_entry.data.get(SOUND_DETECTION_DURATION)
        self._sound_detection_reset = config_entry.data.get(SOUND_DETECTION_RESET)

        self._noiseSensor = ffmpeg_sensor.SensorNoise(
            self._ffmpeg.binary, self._noiseCallback
        )
        self._noiseSensor.set_options(
            time_duration=int(self._sound_detection_duration),
            time_reset=int(self._sound_detection_reset),
            peak=int(self._sound_detection_peak),
        )

        self._attr_state = "unavailable"

        LOGGER.debug("TapoNoiseBinarySensor - init - end")

    async def startNoiseDetection(self):
        LOGGER.debug("startNoiseDetection")
        self._hass.data[DOMAIN][self._config_entry.entry_id][
            "noiseSensorStarted"
        ] = True
        await self._noiseSensor.open_sensor(
            input_source=getStreamSource(self._config_entry, False),
            extra_cmd="-nostats",
        )

    @callback
    def _noiseCallback(self, noiseDetected):
        self._attr_state = "on" if noiseDetected else "off"
        self.async_write_ha_state()


class EventsListener:
    def __init__(self, async_add_entities, hass, config_entry):
        LOGGER.debug("EventsListener init")
        self.metaData = hass.data[DOMAIN][config_entry.entry_id]
        self.async_add_entities = async_add_entities

    def createBinarySensor(self):
        LOGGER.debug("Creating binary sensor entity.")

        events = self.metaData["events"]
        name = self.metaData["name"]
        camData = self.metaData["camData"]
        entities = {
            event.uid: TapoMotionSensor(event.uid, events, name, camData)
            for event in events.get_platform("binary_sensor")
        }
        self.async_add_entities(entities.values())
        uids_by_platform = events.get_uids_by_platform("binary_sensor")

        @callback
        def async_check_entities():
            LOGGER.debug("async_check_entities")
            nonlocal uids_by_platform
            if not (missing := uids_by_platform.difference(entities)):
                return
            new_entities: dict[str, TapoMotionSensor] = {
                uid: TapoMotionSensor(uid, events, name, camData) for uid in missing
            }
            LOGGER.debug("async_check_entities2")
            if new_entities:
                LOGGER.debug("async_check_entities3")
                entities.update(new_entities)
                self.async_add_entities(new_entities.values())

        events.async_add_listener(async_check_entities)


class TapoMotionSensor(BinarySensorEntity):
    def __init__(self, uid, events, name, camData):
        LOGGER.debug("TapoMotionSensor - init - start")
        self._attr_unique_id = uid
        self._name = name
        self._attributes = camData["basic_info"]
        self._attr_device_class = BinarySensorDeviceClass.MOTION
        self.uid = uid
        self.events = events
        event = events.get_uid(uid)

        self._attr_device_class = try_parse_enum(
            BinarySensorDeviceClass, event.device_class
        )
        self._attr_entity_category = event.entity_category
        self._attr_entity_registry_enabled_default = event.entity_enabled
        self._attr_name = f"{self._name} {event.name}"
        self._attr_is_on = event.value
        self._attr_device_class = event.device_class
        self._attr_enabled = event.entity_enabled
        BinarySensorEntity.__init__(self)
        LOGGER.debug("TapoMotionSensor - init - end")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.value
        return self._attr_is_on

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def device_class(self) -> Optional[str]:
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.device_class
        return self._attr_device_class

    @property
    def unique_id(self) -> str:
        return self.uid

    @property
    def entity_registry_enabled_default(self) -> bool:
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.entity_enabled
        return self._attr_enabled

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
