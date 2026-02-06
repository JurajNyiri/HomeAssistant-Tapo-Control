import asyncio
import os

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from typing import Callable
from pytapo.media_stream.streamer import Streamer

from homeassistant.const import STATE_UNAVAILABLE, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.components.camera import (
    CameraEntityFeature,
    Camera,
)
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.stream import (
    Stream,
)

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
    HAS_STREAM_6,
    HAS_STREAM_7,
    CONF_CUSTOM_STREAM_6,
    CONF_CUSTOM_STREAM_7,
)
from .utils import build_device_info, getStreamSource


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

    async def setupEntities(entry):
        hasRTSPEntities = False
        chn_id_0 = None
        chn_id_1 = None
        ch_info = entry.get("chInfo") or []
        if isinstance(ch_info, list):
            if len(ch_info) > 0:
                chn_id_0 = ch_info[0].get("chn_id")
            if len(ch_info) > 1:
                chn_id_1 = ch_info[1].get("chn_id")
        if (
            len(config_entry.data[CONF_USERNAME]) > 0
            and len(config_entry.data[CONF_PASSWORD]) > 0
        ):
            hdStream = TapoRTSPCamEntity(
                hass, config_entry, entry, "stream1", chn_id=chn_id_0
            )
            sdStream = TapoRTSPCamEntity(
                hass, config_entry, entry, "stream2", chn_id=chn_id_0
            )

            entry["entities"].append({"entity": hdStream, "entry": entry})
            entry["entities"].append({"entity": sdStream, "entry": entry})
            hasRTSPEntities = True
            async_add_entities([hdStream, sdStream])
            telephotoEntities = []
            has_stream6 = config_entry.data.get(HAS_STREAM_6) or bool(
                config_entry.data.get(CONF_CUSTOM_STREAM_6)
            )
            has_stream7 = config_entry.data.get(HAS_STREAM_7) or bool(
                config_entry.data.get(CONF_CUSTOM_STREAM_7)
            )
            if not entry["isChild"] and has_stream6:
                telephotoEntities.append(
                    TapoRTSPCamEntity(
                        hass,
                        config_entry,
                        entry,
                        stream="stream6",
                        stream_label="Telephoto HD",
                        stream_unique_id="telephoto_hd",
                        chn_id=chn_id_1,
                    )
                )
            if not entry["isChild"] and has_stream7:
                telephotoEntities.append(
                    TapoRTSPCamEntity(
                        hass,
                        config_entry,
                        entry,
                        stream="stream7",
                        stream_label="Telephoto SD",
                        stream_unique_id="telephoto_sd",
                        chn_id=chn_id_1,
                    )
                )
            if len(telephotoEntities) > 0:
                hasRTSPEntities = True
                for telephotoEntity in telephotoEntities:
                    entry["entities"].append(
                        {"entity": telephotoEntity, "entry": entry}
                    )
                async_add_entities(telephotoEntities)

        if not entry["isParent"]:

            allChnInfo = entry.get("camData", {}).get("allChnInfo", {})
            if allChnInfo:
                channel_info = allChnInfo.get("system", {}).get("chn_info", {})
                chn_0_alias = (
                    channel_info[0].get("chn_alias")
                    if isinstance(channel_info, list) and channel_info
                    else None
                )
                chn_1_alias = (
                    channel_info[1].get("chn_alias")
                    if isinstance(channel_info, list) and channel_info
                    else None
                )
            else:
                channel_info = None
                chn_0_alias = None
                chn_1_alias = None

            directStreamHD = TapoDirectCamEntity(
                hass,
                config_entry,
                entry,
                "stream1",
                enabledByDefault=not hasRTSPEntities,
                stream_label=f"{chn_0_alias} HD" if chn_0_alias is not None else None,
                chn_id=chn_id_0,
            )
            directStreamSD = TapoDirectCamEntity(
                hass,
                config_entry,
                entry,
                "stream2",
                enabledByDefault=False,
                stream_label=f"{chn_0_alias} SD" if chn_0_alias is not None else None,
                chn_id=chn_id_0,
            )
            entry["entities"].append({"entity": directStreamHD, "entry": entry})
            entry["entities"].append({"entity": directStreamSD, "entry": entry})
            async_add_entities([directStreamHD, directStreamSD])

            if channel_info:
                directMinorStreamHD = TapoDirectCamEntity(
                    hass,
                    config_entry,
                    entry,
                    "stream6",
                    enabledByDefault=not hasRTSPEntities,
                    videoStream=1,
                    stream_label=(
                        f"{chn_1_alias} HD" if chn_1_alias is not None else None
                    ),
                    chn_id=chn_id_1,
                )
                directMinorStreamSD = TapoDirectCamEntity(
                    hass,
                    config_entry,
                    entry,
                    "stream7",
                    enabledByDefault=False,
                    videoStream=1,
                    stream_label=(
                        f"{chn_1_alias} SD" if chn_1_alias is not None else None
                    ),
                    chn_id=chn_id_1,
                )
                entry["entities"].append(
                    {"entity": directMinorStreamHD, "entry": entry}
                )
                entry["entities"].append(
                    {"entity": directMinorStreamSD, "entry": entry}
                )
                async_add_entities([directMinorStreamHD, directMinorStreamSD])

    await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        await setupEntities(childDevice)


class TapoCamEntity(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: dict,
        entry: dict,
        directStream: bool,
        stream: str = "stream1",
        stream_label: str | None = None,
        stream_unique_id: str | None = None,
        chn_id: int | None = None,
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
        self._directStream = directStream
        self._stream_id = stream
        self.chn_id = chn_id
        self.read_chn_id = str(chn_id) if chn_id else "1"
        default_labels = {
            "stream1": ("HD", "hd"),
            "stream2": ("SD", "sd"),
            "stream6": ("Telephoto HD", "telephoto_hd"),
            "stream7": ("Telephoto SD", "telephoto_sd"),
        }
        fallback_label, fallback_uid = default_labels.get(
            stream, (stream.upper(), stream)
        )
        self._stream_label = stream_label or fallback_label
        self._stream_unique_id = stream_unique_id or fallback_uid
        self._extra_arguments = config_entry.data.get(CONF_EXTRA_ARGUMENTS)
        self._enable_stream = config_entry.data.get(ENABLE_STREAM)
        self._attr_extra_state_attributes = entry["camData"]["basic_info"]
        self._attr_icon = "mdi:cctv"
        self._attr_should_poll = True
        self._is_cam_entity = True
        self._is_noise_sensor = False

        self.updateTapo(entry["camData"])

    async def async_added_to_hass(self) -> None:
        self._enabled = True
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False
        await super().async_will_remove_from_hass()

    @property
    def supported_features(self):
        if self._enable_stream:
            return CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
        else:
            return CameraEntityFeature.ON_OFF

    @property
    def name(self) -> str:
        name = self._attr_extra_state_attributes["device_alias"]
        name += f" {self._stream_label} Stream"
        if self._directStream:
            name += " (Direct)"
        return name

    @property
    def unique_id(self) -> str:
        return slugify(
            f"{self._attr_extra_state_attributes['mac']}_{self._stream_unique_id}{'_direct' if self._directStream else ''}_tapo_control"
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

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_create_stream(self) -> Stream | None:
        return await super().async_create_stream()

    def updateTapo(self, camData):
        LOGGER.debug("updateTapo - camera")
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = "idle"
            motion_enabled = camData["motion_detection_enabled"]
            if isinstance(motion_enabled, dict):
                motion_enabled = motion_enabled.get(self.read_chn_id)
            self._motion_detection_enabled = motion_enabled

            for attr, value in camData["basic_info"].items():
                self._attr_extra_state_attributes[attr] = value
            if "alarm_config" in self._attr_extra_state_attributes:
                self._attr_extra_state_attributes["alarm"] = camData["alarm_config"][
                    "automatic"
                ]
            if "user" in camData:
                self._attr_extra_state_attributes["user"] = camData["user"]
            # Disable incorrect location report by camera
            self._attr_extra_state_attributes["longitude"] = 0
            self._attr_extra_state_attributes["latitude"] = 0
            self._attr_extra_state_attributes["has_set_location_info"] = 0
            # lists below
            self._attr_extra_state_attributes["presets"] = camData["presets"]
            if camData["recordPlan"]:
                self._attr_extra_state_attributes["record_plan"] = {
                    "sunday": (
                        camData["recordPlan"]["sunday"]
                        if "sunday" in camData["recordPlan"]
                        else None
                    ),
                    "monday": (
                        camData["recordPlan"]["monday"]
                        if "monday" in camData["recordPlan"]
                        else None
                    ),
                    "tuesday": (
                        camData["recordPlan"]["tuesday"]
                        if "tuesday" in camData["recordPlan"]
                        else None
                    ),
                    "wednesday": (
                        camData["recordPlan"]["wednesday"]
                        if "wednesday" in camData["recordPlan"]
                        else None
                    ),
                    "thursday": (
                        camData["recordPlan"]["thursday"]
                        if "thursday" in camData["recordPlan"]
                        else None
                    ),
                    "friday": (
                        camData["recordPlan"]["friday"]
                        if "friday" in camData["recordPlan"]
                        else None
                    ),
                    "saturday": (
                        camData["recordPlan"]["saturday"]
                        if "saturday" in camData["recordPlan"]
                        else None
                    ),
                }

    async def async_enable_motion_detection(self):
        LOGGER.debug("async_enable_motion_detection - camera")
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection,
            True,
            None,
            [self.chn_id] if self.chn_id else None,
        )
        await self._coordinator.async_request_refresh()

    async def async_disable_motion_detection(self):
        LOGGER.debug("async_disable_motion_detection - camera")
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection,
            False,
            None,
            [self.chn_id] if self.chn_id else None,
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self):
        LOGGER.debug("async_turn_on - camera")
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            False,
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self):
        LOGGER.debug("async_turn_off - camera")
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            True,
        )
        await self._coordinator.async_request_refresh()

    async def save_preset(self, name):
        LOGGER.debug("save_preset - camera")
        if not name == "" and not name.isnumeric():
            await self.hass.async_add_executor_job(self._controller.savePreset, name)
            await self._coordinator.async_request_refresh()
        else:
            LOGGER.error(
                "Incorrect " + NAME + " value. It cannot be empty or a number."
            )

    async def delete_preset(self, preset):
        LOGGER.debug("delete_preset - camera")
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


class TapoRTSPCamEntity(TapoCamEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: dict,
        entry: dict,
        stream: str,
        stream_label: str | None = None,
        stream_unique_id: str | None = None,
        chn_id: int | None = None,
    ):
        super().__init__(
            hass,
            config_entry,
            entry,
            False,
            stream,
            stream_label,
            stream_unique_id,
            chn_id,
        )

    async def async_camera_image(self, width=None, height=None):
        LOGGER.debug("async_camera_image - camera")
        ffmpeg = ImageFrame(self._ffmpeg.binary)
        streaming_url = getStreamSource(
            self._config_entry,
            self._stream_id,
        )
        image = await asyncio.shield(
            ffmpeg.get_image(
                streaming_url,
                output_format=IMAGE_JPEG,
                extra_cmd=self._extra_arguments,
            )
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        LOGGER.debug("handle_async_mjpeg_stream - camera")
        streaming_url = getStreamSource(
            self._config_entry,
            self._stream_id,
        )
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

    async def stream_source(self):
        return getStreamSource(
            self._config_entry,
            self._stream_id,
        )


class TapoDirectCamEntity(TapoCamEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: dict,
        entry: dict,
        stream: str,
        enabledByDefault: bool,
        videoStream: int = 0,  # 0 for main, 1 for substream
        stream_label: str | None = None,
        chn_id: int | None = None,
    ):
        super().__init__(
            hass, config_entry, entry, True, stream, stream_label, None, chn_id
        )

        if stream in ("stream1"):
            self._directQuality = "HD"
        else:
            self._directQuality = "VGA"

        self._HAstream: Stream | None = None
        self._streamer: Streamer | None = None
        self._stream_fd: int | None = None
        self._stream_task: asyncio.Task | None = None
        self._enabled_by_default = enabledByDefault
        self.videoStream = videoStream

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._enabled_by_default

    async def async_will_remove_from_hass(self) -> None:
        if self._streamer:
            await self._streamer.stop()
        if self._stream_task:
            self._stream_task.cancel()
        await super().async_will_remove_from_hass()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ):
        LOGGER.debug("async_camera_image")
        streamer = Streamer(
            self._controller,
            includeAudio=False,
            quality=self._directQuality,
            logFunction=self.logFunction,
            ff_args={
                "-frames:v": "1",
                "-f": "image2pipe",
                "-c:v": "mjpeg",
                "-vsync": "0",
                "-map-video": f"0:v:{self.videoStream}",
            },
        )
        LOGGER.debug("async_camera_image - Starting streamer")
        info = await streamer.start()

        proc = info["ffmpegProcess"]

        LOGGER.debug("Direct MJPEG: ffmpeg PID %s", proc.pid)

        jpeg = await proc.stdout.read()
        await proc.wait()

        LOGGER.debug("async_camera_image - Stopping streamer")
        await streamer.stop()
        info["streamProcess"].cancel()
        LOGGER.debug("async_camera_image - Returning jpeg")
        return jpeg

    async def handle_async_mjpeg_stream(self, request):
        LOGGER.debug("Direct MJPEG: request")
        streamer = Streamer(
            self._controller,
            includeAudio=False,
            quality=self._directQuality,
            logFunction=self.logFunction,
            ff_args={
                "-c:v": "mjpeg",
                "-f": "mpjpeg",
                "-vsync": "0",
                "-map-video": f"0:v:{self.videoStream}",
            },
        )
        info = await streamer.start()
        proc = info["ffmpegProcess"]

        LOGGER.debug("Direct MJPEG: ffmpeg PID %s", proc.pid)

        try:
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                proc.stdout,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            LOGGER.debug("Direct MJPEG: shutting ffmpeg / streamer")
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            await streamer.stop()
            info["streamProcess"].cancel()

    async def _log_stream(self, stream: asyncio.StreamReader, *, prefix=""):
        async for line in stream:
            LOGGER.debug("%s: %s", prefix, line.decode().rstrip())

    def logFunction(self, data):
        LOGGER.debug(data)

    async def _ensure_av_pipe(self, newStream=False) -> None:
        LOGGER.debug("_ensure_av_pipe() called")

        if self._streamer and self._streamer.running and not newStream:
            LOGGER.debug("_ensure_av_pipe: already running (fd=%s)", self._stream_fd)
            return

        if self._streamer:
            LOGGER.debug("_ensure_av_pipe: stopping previous Streamer")
            try:
                await self._streamer.stop()
                if self._stream_task:
                    self._stream_task.cancel()
            except Exception as err:
                LOGGER.warning(err)
                pass

        LOGGER.debug("_ensure_av_pipe: launching NEW Streamer")
        self._streamer = Streamer(
            self._controller,
            includeAudio=False,
            quality=self._directQuality,
            logFunction=self.logFunction,
        )
        info = await self._streamer.start()

        self._stream_fd: int = info["read_fd"]

        if self._HAstream is not None:
            newSource = await self.stream_source()
            self._HAstream.update_source(newSource)

        os.set_inheritable(self._stream_fd, True)
        self._stream_task = info["streamProcess"]

        LOGGER.debug(
            "_ensure_av_pipe: ready (fd=%s, task=%s)",
            self._stream_fd,
            self._stream_task,
        )

    async def stream_source(self) -> str | None:
        source = f"pipe:{self._stream_fd}"
        LOGGER.debug("stream_source: returning  %s", source)
        return source

    async def async_create_stream(self) -> Stream | None:
        await self._ensure_av_pipe()
        self._HAstream = await super().async_create_stream()
        self._HAstream.set_update_callback(self._on_stream_state)

        return self._HAstream

    def _on_stream_state(self):
        if not self._HAstream.available:
            LOGGER.debug("%s: HA stream unavailable: restarting", self.entity_id)
            asyncio.create_task(self._ensure_av_pipe(newStream=True))
