import asyncio

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from typing import Callable

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.components.camera import (
    SUPPORT_ON_OFF,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.config_validation import boolean
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import (
    CONF_RTSP_TRANSPORT,
    ENABLE_STREAM,
    SERVICE_SAVE_PRESET,
    SCHEMA_SERVICE_SAVE_PRESET,
    SERVICE_DELETE_PRESET,
    SCHEMA_SERVICE_DELETE_PRESET,
    DOMAIN,
    LOGGER,
    NAME,
    BRAND,
)
from .utils import build_device_info, getStreamSource


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
):
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    platform = entity_platform.current_platform.get()
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

    hdStream = TapoCamEntity(hass, config_entry, entry, True)
    sdStream = TapoCamEntity(hass, config_entry, entry, False)

    entry["entities"].append({"entity": hdStream, "entry": entry})
    entry["entities"].append({"entity": sdStream, "entry": entry})
    async_add_entities([hdStream, sdStream])


class TapoCamEntity(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: dict,
        entry: dict,
        HDStream: boolean,
    ):
        super().__init__()
        self.stream_options[CONF_RTSP_TRANSPORT] = config_entry.data.get(
            CONF_RTSP_TRANSPORT
        )
        self._controller = entry["controller"]
        self._coordinator = entry["coordinator"]
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._config_entry = config_entry
        self._hass = hass
        self._enabled = False
        self._hdstream = HDStream
        self._extra_arguments = config_entry.data.get(CONF_EXTRA_ARGUMENTS)
        self._enable_stream = config_entry.data.get(ENABLE_STREAM)
        self._attr_extra_state_attributes = entry["camData"]["basic_info"]
        self._attr_motion_detection_enabled = False
        self._attr_icon = "mdi:cctv"
        self._attr_should_poll = True
        self._is_cam_entity = True
        self._is_noise_sensor = False

        self.updateTapo(entry["camData"])

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
    def name(self) -> str:
        name = self._attr_extra_state_attributes["device_alias"]
        if self._hdstream:
            name += " HD Stream"
        else:
            name += " SD Stream"
        return name

    @property
    def unique_id(self) -> str:
        if self._hdstream:
            streamType = "hd"
        else:
            streamType = "sd"
        return slugify(
            f"{self._attr_extra_state_attributes['mac']}_{streamType}_tapo_control"
        )

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attr_extra_state_attributes)

    @property
    def motion_detection_enabled(self):
        return self._motion_detection_enabled

    @property
    def brand(self):
        return BRAND

    @property
    def model(self):
        return self._attr_extra_state_attributes["device_model"]

    async def async_camera_image(self, width=None, height=None):
        ffmpeg = ImageFrame(self._ffmpeg.binary)
        streaming_url = getStreamSource(self._config_entry, self._hdstream)
        image = await asyncio.shield(
            ffmpeg.get_image(
                streaming_url,
                output_format=IMAGE_JPEG,
                extra_cmd=self._extra_arguments,
            )
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        streaming_url = getStreamSource(self._config_entry, self._hdstream)
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

    async def async_update(self) -> None:
        try:
            data = await self._hass.async_add_executor_job(
                self._controller.getMotionDetection
            )
            self._attr_motion_detection_enabled = (
                "enabled" in data and data["enabled"] == "on"
            )
        except Exception:
            self._attr_state = STATE_UNAVAILABLE
        await self._coordinator.async_request_refresh()

    async def stream_source(self):
        return getStreamSource(self._config_entry, self._hdstream)

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = "idle"
            self._motion_detection_enabled = camData["motion_detection_enabled"]

            for attr, value in camData["basic_info"].items():
                self._attr_extra_state_attributes[attr] = value
            self._attr_extra_state_attributes["alarm"] = camData["alarm"]
            self._attr_extra_state_attributes["user"] = camData["user"]
            # Disable incorrect location report by camera
            self._attr_extra_state_attributes["longitude"] = 0
            self._attr_extra_state_attributes["latitude"] = 0
            self._attr_extra_state_attributes["has_set_location_info"] = 0
            # lists below
            self._attr_extra_state_attributes["presets"] = camData["presets"]
            if camData["recordPlan"]:
                self._attr_extra_state_attributes["record_plan"] = {
                    "sunday": camData["recordPlan"]["sunday"]
                    if "sunday" in camData["recordPlan"]
                    else None,
                    "monday": camData["recordPlan"]["monday"]
                    if "monday" in camData["recordPlan"]
                    else None,
                    "tuesday": camData["recordPlan"]["tuesday"]
                    if "tuesday" in camData["recordPlan"]
                    else None,
                    "wednesday": camData["recordPlan"]["wednesday"]
                    if "wednesday" in camData["recordPlan"]
                    else None,
                    "thursday": camData["recordPlan"]["thursday"]
                    if "thursday" in camData["recordPlan"]
                    else None,
                    "friday": camData["recordPlan"]["friday"]
                    if "friday" in camData["recordPlan"]
                    else None,
                    "saturday": camData["recordPlan"]["saturday"]
                    if "saturday" in camData["recordPlan"]
                    else None,
                }

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
            for key, value in self._attr_extra_state_attributes["presets"].items():
                if value == preset:
                    foundKey = key
            if foundKey:
                await self.hass.async_add_executor_job(
                    self._controller.deletePreset, foundKey
                )
                await self._coordinator.async_request_refresh()
            else:
                LOGGER.error("Preset " + preset + " does not exist.")
