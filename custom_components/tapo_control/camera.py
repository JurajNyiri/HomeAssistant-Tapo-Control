import asyncio
import urllib.parse
import haffmpeg.sensor as ffmpeg_sensor
from .utils import build_device_info
from homeassistant.helpers.config_validation import boolean
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from typing import Callable
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.helpers import entity_platform
from homeassistant.components.camera import (
    SUPPORT_ON_OFF,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from .const import (
    CONF_RTSP_TRANSPORT,
    CONF_CUSTOM_STREAM,
    ENABLE_SOUND_DETECTION,
    ENABLE_STREAM,
    SERVICE_PTZ,
    SCHEMA_SERVICE_PTZ,
    SERVICE_SAVE_PRESET,
    SCHEMA_SERVICE_SAVE_PRESET,
    SERVICE_DELETE_PRESET,
    SCHEMA_SERVICE_DELETE_PRESET,
    DOMAIN,
    LOGGER,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    TILT,
    PAN,
    PRESET,
    NAME,
    BRAND,
)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_PTZ,
        SCHEMA_SERVICE_PTZ,
        "ptz",
    )
    platform.async_register_entity_service(
        SERVICE_SAVE_PRESET,
        SCHEMA_SERVICE_SAVE_PRESET,
        "save_preset",
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_PRESET,
        SCHEMA_SERVICE_DELETE_PRESET,
        "delete_preset",
    )

    hass.data[DOMAIN][entry.entry_id]["entities"] = [
        TapoCamEntity(hass, entry, hass.data[DOMAIN][entry.entry_id], True),
        TapoCamEntity(hass, entry, hass.data[DOMAIN][entry.entry_id], False),
    ]
    async_add_entities(hass.data[DOMAIN][entry.entry_id]["entities"])


class TapoCamEntity(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: dict,
        tapoData: dict,
        HDStream: boolean,
    ):
        super().__init__()
        self.stream_options[CONF_RTSP_TRANSPORT] = entry.data.get(CONF_RTSP_TRANSPORT)
        self._controller = tapoData["controller"]
        self._coordinator = tapoData["coordinator"]
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._entry = entry
        self._hass = hass
        self._enabled = False
        self._hdstream = HDStream
        self._extra_arguments = entry.data.get(CONF_EXTRA_ARGUMENTS)
        self._host = entry.data.get(CONF_IP_ADDRESS)
        self._username = entry.data.get(CONF_USERNAME)
        self._password = entry.data.get(CONF_PASSWORD)
        self._enable_stream = entry.data.get(ENABLE_STREAM)
        self._enable_sound_detection = entry.data.get(ENABLE_SOUND_DETECTION)
        self._sound_detection_peak = entry.data.get(SOUND_DETECTION_PEAK)
        self._sound_detection_duration = entry.data.get(SOUND_DETECTION_DURATION)
        self._sound_detection_reset = entry.data.get(SOUND_DETECTION_RESET)
        self._custom_stream = entry.data.get(CONF_CUSTOM_STREAM)
        self._attributes = tapoData["camData"]["basic_info"]
        self._attr_is_on = False
        self._attr_motion_detection_enabled = False

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
            input_source=self.getStreamSource(),
            extra_cmd="-nostats",
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
    def extra_state_attributes(self):
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def motion_detection_enabled(self):
        return self._motion_detection_enabled

    @property
    def brand(self):
        return BRAND

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def should_poll(self):
        return True

    async def async_camera_image(self, width=None, height=None):
        ffmpeg = ImageFrame(self._ffmpeg.binary)
        streaming_url = self.getStreamSource()
        image = await asyncio.shield(
            ffmpeg.get_image(
                streaming_url,
                output_format=IMAGE_JPEG,
                extra_cmd=self._extra_arguments,
            )
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        streaming_url = self.getStreamSource()
        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(
            streaming_url,
            extra_cmd=self._extra_arguments,
        )
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
        if self._custom_stream != "":
            return self._custom_stream

        if self._hdstream:
            streamType = "stream1"
        else:
            streamType = "stream2"
        streamURL = f"rtsp://{urllib.parse.quote_plus(self._username)}:{urllib.parse.quote_plus(self._password)}@{self._host}:554/{streamType}"
        return streamURL

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getPrivacyMode)
        self._attr_is_on = "enabled" in data and data["enabled"] == "on"

        data = await self._hass.async_add_executor_job(
            self._controller.getMotionDetection
        )
        self._attr_motion_detection_enabled = (
            "enabled" in data and data["enabled"] == "on"
        )

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

    async def ptz(self, tilt=None, pan=None, distance=None):
        if tilt:
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
                + "."
            )
        await self._coordinator.async_request_refresh()

    async def async_enable_motion_detection(self):
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection, True
        )

    async def async_disable_motion_detection(self):
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection, False
        )

    async def async_turn_on(self):
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            False,
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            True,
        )
        await self._coordinator.async_request_refresh()

    async def save_preset(self, name):
        if not name == "" and not name.isnumeric():
            await self.hass.async_add_executor_job(self._controller.savePreset, name)
            await self._coordinator.async_request_refresh()
        else:
            LOGGER.error(
                "Incorrect " + NAME + " value. It cannot be empty or a number."
            )

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
