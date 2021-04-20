import asyncio
import urllib.parse
import haffmpeg.sensor as ffmpeg_sensor
from homeassistant.helpers.config_validation import boolean
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from typing import Callable
from pytapo import Tapo
from homeassistant.util import slugify
from homeassistant.helpers import entity_platform
from homeassistant.components.camera import (
    SUPPORT_ON_OFF,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from .const import (
    ENABLE_SOUND_DETECTION,
    ENABLE_STREAM,
    SERVICE_SET_LED_MODE,
    SCHEMA_SERVICE_SET_LED_MODE,
    SERVICE_SET_DAY_NIGHT_MODE,
    SCHEMA_SERVICE_SET_DAY_NIGHT_MODE,
    SERVICE_SET_PRIVACY_MODE,
    SCHEMA_SERVICE_SET_PRIVACY_MODE,
    SERVICE_PTZ,
    SCHEMA_SERVICE_PTZ,
    SERVICE_SET_ALARM_MODE,
    SCHEMA_SERVICE_SET_ALARM_MODE,
    SERVICE_SET_MOTION_DETECTION_MODE,
    SCHEMA_SERVICE_SET_MOTION_DETECTION_MODE,
    SERVICE_SET_AUTO_TRACK_MODE,
    SCHEMA_SERVICE_SET_AUTO_TRACK_MODE,
    SERVICE_REBOOT,
    SCHEMA_SERVICE_REBOOT,
    SERVICE_SAVE_PRESET,
    SCHEMA_SERVICE_SAVE_PRESET,
    SERVICE_DELETE_PRESET,
    SCHEMA_SERVICE_DELETE_PRESET,
    SERVICE_FORMAT,
    SCHEMA_SERVICE_FORMAT,
    DOMAIN,
    LOGGER,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    TILT,
    PAN,
    PRESET,
    NAME,
)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SET_LED_MODE, SCHEMA_SERVICE_SET_LED_MODE, "set_led_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_DAY_NIGHT_MODE,
        SCHEMA_SERVICE_SET_DAY_NIGHT_MODE,
        "set_day_night_mode",
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
    platform.async_register_entity_service(
        SERVICE_SET_MOTION_DETECTION_MODE,
        SCHEMA_SERVICE_SET_MOTION_DETECTION_MODE,
        "set_motion_detection_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_AUTO_TRACK_MODE,
        SCHEMA_SERVICE_SET_AUTO_TRACK_MODE,
        "set_auto_track_mode",
    )
    platform.async_register_entity_service(
        SERVICE_REBOOT, SCHEMA_SERVICE_REBOOT, "reboot",
    )
    platform.async_register_entity_service(
        SERVICE_SAVE_PRESET, SCHEMA_SERVICE_SAVE_PRESET, "save_preset",
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_PRESET, SCHEMA_SERVICE_DELETE_PRESET, "delete_preset",
    )
    platform.async_register_entity_service(
        SERVICE_FORMAT, SCHEMA_SERVICE_FORMAT, "format",
    )

    hass.data[DOMAIN][entry.entry_id]["entities"] = [
        TapoCamEntity(hass, entry, hass.data[DOMAIN][entry.entry_id], True),
        TapoCamEntity(hass, entry, hass.data[DOMAIN][entry.entry_id], False),
    ]
    async_add_entities(hass.data[DOMAIN][entry.entry_id]["entities"])


class TapoCamEntity(Camera):
    def __init__(
        self, hass: HomeAssistant, entry: dict, tapoData: Tapo, HDStream: boolean,
    ):
        super().__init__()
        self._controller = tapoData["controller"]
        self._coordinator = tapoData["coordinator"]
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._entry = entry
        self._hass = hass
        self._enabled = False
        self._hdstream = HDStream
        self._host = entry.data.get(CONF_IP_ADDRESS)
        self._username = entry.data.get(CONF_USERNAME)
        self._password = entry.data.get(CONF_PASSWORD)
        self._enable_stream = entry.data.get(ENABLE_STREAM)
        self._enable_sound_detection = entry.data.get(ENABLE_SOUND_DETECTION)
        self._sound_detection_peak = entry.data.get(SOUND_DETECTION_PEAK)
        self._sound_detection_duration = entry.data.get(SOUND_DETECTION_DURATION)
        self._sound_detection_reset = entry.data.get(SOUND_DETECTION_RESET)
        self._attributes = tapoData["camData"]["basic_info"]

        self.updateCam(tapoData["camData"])

        hass.data[DOMAIN][entry.entry_id]["noiseSensorStarted"] = False

        if self._enable_sound_detection:
            self._noiseSensor = ffmpeg_sensor.SensorNoise(
                self._ffmpeg.binary, self._noiseCallback
            )
            self._noiseSensor.set_options(
                time_duration=int(self._sound_detection_duration),
                time_reset=int(self._sound_detection_reset),
                peak=int(self._sound_detection_peak),
            )

    @callback
    def _noiseCallback(self, noiseDetected):
        self._attributes["noise_detected"] = "on" if noiseDetected else "off"
        for entity in self._hass.data[DOMAIN][self._entry.entry_id]["entities"]:
            if entity._enabled:
                entity.async_write_ha_state()

    async def startNoiseDetection(self):
        self._hass.data[DOMAIN][self._entry.entry_id]["noiseSensorStarted"] = True
        await self._noiseSensor.open_sensor(
            input_source=self.getStreamSource(), extra_cmd="-nostats",
        )

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

    @property
    def supported_features(self):
        if self._enable_stream:
            return SUPPORT_STREAM | SUPPORT_ON_OFF
        else:
            return SUPPORT_ON_OFF

    @property
    def icon(self) -> str:
        return "mdi:cctv"

    @property
    def name(self) -> str:
        return self.getName()

    @property
    def unique_id(self) -> str:
        return self.getUniqueID()

    @property
    def device_state_attributes(self):
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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
    def motion_detection_enabled(self):
        return self._motion_detection_enabled

    @property
    def brand(self):
        return "TP-Link"

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def should_poll(self):
        return True

    async def async_camera_image(self):
        ffmpeg = ImageFrame(self._ffmpeg.binary)
        streaming_url = self.getStreamSource()
        image = await asyncio.shield(
            ffmpeg.get_image(streaming_url, output_format=IMAGE_JPEG,)
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        streaming_url = self.getStreamSource()
        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(streaming_url)
        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    def getStreamSource(self):
        if self._hdstream:
            streamType = "stream1"
        else:
            streamType = "stream2"
        streamURL = f"rtsp://{urllib.parse.quote_plus(self._username)}:{urllib.parse.quote_plus(self._password)}@{self._host}:554/{streamType}"
        return streamURL

    async def async_update(self):
        await self._coordinator.async_request_refresh()

    async def stream_source(self):
        return self.getStreamSource()

    def updateCam(self, camData):
        if not camData:
            self._state = "unavailable"
        else:
            self._state = "idle"
            self._motion_detection_enabled = camData["motion_detection_enabled"]

            for attr, value in camData["basic_info"].items():
                self._attributes[attr] = value
            self._attributes["user"] = camData["user"]
            self._attributes["motion_detection_sensitivity"] = camData[
                "motion_detection_sensitivity"
            ]
            self._attributes["privacy_mode"] = camData["privacy_mode"]
            self._attributes["alarm"] = camData["alarm"]
            self._attributes["alarm_mode"] = camData["alarm_mode"]
            self._attributes["led"] = camData["led"]
            self._attributes["day_night_mode"] = camData["day_night_mode"]
            self._attributes["auto_track"] = camData["auto_track"]
            self._attributes["presets"] = camData["presets"]

    def getName(self):
        name = self._attributes["device_alias"]
        if self._hdstream:
            name += " - HD"
        else:
            name += " - SD"
        return name

    def getUniqueID(self):
        if self._hdstream:
            streamType = "hd"
        else:
            streamType = "sd"
        return slugify(f"{self._attributes['mac']}_{streamType}_tapo_control")

    async def ptz(self, tilt=None, pan=None, preset=None, distance=None):
        if preset:
            if preset.isnumeric():
                await self.hass.async_add_executor_job(
                    self._controller.setPreset, preset
                )
            else:
                foundKey = False
                for key, value in self._attributes["presets"].items():
                    if value == preset:
                        foundKey = key
                if foundKey:
                    await self.hass.async_add_executor_job(
                        self._controller.setPreset, foundKey
                    )
                else:
                    LOGGER.error("Preset " + preset + " does not exist.")
        elif tilt:
            if distance:
                distance = float(distance)
                if distance >= 0 and distance <= 1:
                    degrees = 68 * distance
                else:
                    degrees = 5
            else:
                degrees = 5
            if tilt == "UP":
                await self.hass.async_add_executor_job(
                    self._controller.moveMotor, 0, degrees
                )
            else:
                await self.hass.async_add_executor_job(
                    self._controller.moveMotor, 0, -degrees
                )
        elif pan:
            if distance:
                distance = float(distance)
                if distance >= 0 and distance <= 1:
                    degrees = 360 * distance
                else:
                    degrees = 5
            else:
                degrees = 5
            if pan == "RIGHT":
                await self.hass.async_add_executor_job(
                    self._controller.moveMotor, degrees, 0
                )
            else:
                await self.hass.async_add_executor_job(
                    self._controller.moveMotor, -degrees, 0
                )
        else:
            LOGGER.error(
                "Incorrect additional PTZ properties."
                + " You need to specify at least one of"
                + TILT
                + ", "
                + PAN
                + ", "
                + PRESET
                + "."
            )
        await self._coordinator.async_request_refresh()

    async def set_privacy_mode(self, privacy_mode: str):
        if privacy_mode == "on":
            await self.hass.async_add_executor_job(
                self._controller.setPrivacyMode, True
            )
        else:
            await self.hass.async_add_executor_job(
                self._controller.setPrivacyMode, False
            )
        await self._coordinator.async_request_refresh()

    async def set_alarm_mode(self, alarm_mode, sound=None, light=None):
        if not light:
            light = "on"
        if not sound:
            sound = "on"
        if alarm_mode == "on":
            await self.hass.async_add_executor_job(
                self._controller.setAlarm,
                True,
                True if sound == "on" else False,
                True if light == "on" else False,
            )
        else:
            await self.hass.async_add_executor_job(
                self._controller.setAlarm,
                False,
                True if sound == "on" else False,
                True if light == "on" else False,
            )
        await self._coordinator.async_request_refresh()

    async def set_led_mode(self, led_mode: str):
        if led_mode == "on":
            await self.hass.async_add_executor_job(self._controller.setLEDEnabled, True)
        else:
            await self.hass.async_add_executor_job(
                self._controller.setLEDEnabled, False
            )
        await self._coordinator.async_request_refresh()

    async def set_motion_detection_mode(self, motion_detection_mode):
        if motion_detection_mode == "off":
            await self.hass.async_add_executor_job(
                self._controller.setMotionDetection, False
            )
        else:
            await self.hass.async_add_executor_job(
                self._controller.setMotionDetection, True, motion_detection_mode,
            )
        await self._coordinator.async_request_refresh()

    async def async_enable_motion_detection(self):
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection, True
        )
        await self._coordinator.async_request_refresh()

    async def async_disable_motion_detection(self):
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection, False
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self):
        await self.set_privacy_mode("off")

    async def async_turn_off(self):
        await self.set_privacy_mode("on")

    async def set_auto_track_mode(self, auto_track_mode: str):
        if auto_track_mode == "on":
            await self.hass.async_add_executor_job(
                self._controller.setAutoTrackTarget, True
            )
        else:
            await self.hass.async_add_executor_job(
                self._controller.setAutoTrackTarget, False
            )
        await self._coordinator.async_request_refresh()

    async def reboot(self):
        await self.hass.async_add_executor_job(self._controller.reboot)

    async def save_preset(self, name):
        if not name == "" and not name.isnumeric():
            await self.hass.async_add_executor_job(self._controller.savePreset, name)
            await self._coordinator.async_request_refresh()
        else:
            LOGGER.error(
                "Incorrect " + NAME + " value. It cannot be empty or a number."
            )

    async def set_day_night_mode(self, day_night_mode: str):
        await self.hass.async_add_executor_job(
            self._controller.setDayNightMode, day_night_mode
        )
        await self._coordinator.async_request_refresh()

    async def delete_preset(self, preset):
        if preset.isnumeric():
            await self.hass.async_add_executor_job(
                self._controller.deletePreset, preset
            )
            await self._coordinator.async_request_refresh()
        else:
            foundKey = False
            for key, value in self._attributes["presets"].items():
                if value == preset:
                    foundKey = key
            if foundKey:
                await self.hass.async_add_executor_job(
                    self._controller.deletePreset, foundKey
                )
                await self._coordinator.async_request_refresh()
            else:
                LOGGER.error("Preset " + preset + " does not exist.")

    async def format(self):
        await self.hass.async_add_executor_job(self._controller.format)
