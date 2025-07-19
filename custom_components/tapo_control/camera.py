import asyncio
import os

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from typing import Callable
from .pytapo.media_stream.streamer import Streamer

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

    if (
        len(config_entry.data[CONF_USERNAME]) > 0
        and len(config_entry.data[CONF_PASSWORD]) > 0
    ):
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
        self._attr_icon = "mdi:cctv"
        self._attr_should_poll = True
        self._is_cam_entity = True
        self._is_noise_sensor = False

        self._streamer: Streamer | None = None
        self._stream_fd: int | None = None
        self._stream_task: asyncio.Task | None = None

        self.updateTapo(entry["camData"])

    def debugLog(self, msg):
        LOGGER.debug(msg)

    async def _ensure_pipe(self):
        LOGGER.warning("_ensure_pipe")
        if self._streamer and self._streamer.running:
            LOGGER.warning("running")
            return

        self._streamer = Streamer(
            self._controller,
            callbackFunction=self.debugLog,
            mode="pipe",  # ← switch to pipe
            outputDirectory="/config/videos/",
            includeAudio=True,  # or follow user option
        )
        info = await self._streamer.start()
        self._stream_fd = info["read_fd"]
        LOGGER.warning("Creating " + str(self._stream_fd))
        os.set_inheritable(self._stream_fd, True)  # good practice
        self._stream_task = info["streamProcess"]

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        if self._streamer:
            await self._streamer.stop_hls()
        if self._stream_task:
            self._stream_task.cancel()
        self._enabled = False

    @property
    def supported_features(self):
        if self._enable_stream:
            return CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
        else:
            return CameraEntityFeature.ON_OFF

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

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ):
        """Return one JPEG from the live in‑memory stream."""
        if True:
            await self._ensure_pipe()
            LOGGER.warning("async_camera_image")
            fd = self._stream_fd
            os.set_inheritable(fd, True)

            ff_cmd = [
                self._ffmpeg.binary,
                "-loglevel",
                "quiet",
                "-probesize",
                "32",
                "-analyzeduration",
                "0",
                "-i",
                f"pipe:{fd}",
                "-frames:v",
                "1",  # grab a single frame
                "-f",
                "image2",
                "-q:v",
                "2",  # high quality
                "pipe:1",
            ]

            proc = await asyncio.create_subprocess_exec(
                *ff_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                pass_fds=(fd,),
            )
            jpeg, _ = await proc.communicate()
            return jpeg  # bytes, HA will serve it
        else:
            # legacy path (RTSP / HLS)
            ff = ImageFrame(self._ffmpeg.binary)
            url = getStreamSource(self._config_entry, self._hdstream)
            return await asyncio.shield(
                ff.get_image(
                    url, output_format=IMAGE_JPEG, extra_cmd=self._extra_arguments
                )
            )

    # --------------------------------------------------------------------------- #
    # 2.  Continuous MJPEG stream via the pipe
    # --------------------------------------------------------------------------- #
    async def handle_async_mjpeg_stream(self, request):
        """Serve MJPEG generated from the live in‑memory pipe."""
        LOGGER.warning("MJPEG ⟶ request")

        # 1 ── make sure the Streamer (pipe backend) is running
        await self._ensure_pipe()
        fd = self._stream_fd
        os.set_inheritable(fd, True)
        LOGGER.warning("MJPEG ⟶ using pipe fd %s", fd)

        # 2 ── FFmpeg command
        ff_cmd = [
            self._ffmpeg.binary,
            "-loglevel",
            "warning",  # drop per‑packet spam
            "-hide_banner",
            # robust TS input settings
            "-fflags",
            "+discardcorrupt+igndts",
            "-err_detect",
            "ignore_err",
            "-probesize",
            "5M",  # look at up to 5 MB
            "-analyzeduration",
            "5000000",  # …or 5 s before deciding
            "-use_wallclock_as_timestamps",
            "1",
            "-i",
            f"pipe:{fd}",  # INPUT (live TS)
            # select the video stream only
            "-map",
            "0:v:0",
            "-an",  # ignore audio completely
            # transcode to MJPEG
            "-c:v",
            "mjpeg",
            "-q:v",
            "5",  # quality 2…31 (lower=better)
            "-f",
            "mjpeg",
            "pipe:1",  # OUTPUT (multipart‑JPEG)
        ]
        LOGGER.warning("MJPEG ⟶ ffmpeg cmd: %s", " ".join(ff_cmd))

        # 3 ── spawn FFmpeg with our FD kept open
        proc = await asyncio.create_subprocess_exec(
            *ff_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            pass_fds=(fd,),
        )
        LOGGER.warning("MJPEG ⟶ ffmpeg PID %s", proc.pid)

        # async task that logs only the first few stderr lines
        async def _brief_stderr(stream):
            for _ in range(40):  # ~ first two seconds
                line = await stream.readline()
                if not line:
                    break
                LOGGER.warning("MJPEG ffmpeg: %s", line.decode().rstrip())

        asyncio.create_task(_brief_stderr(proc.stderr))

        # 4 ── proxy MJPEG to the frontend
        try:
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                proc.stdout,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            LOGGER.warning("MJPEG ⟶ closing ffmpeg")
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def stream_source(self):
        await self._ensure_pipe()
        # FFmpeg & PyAV understand "pipe:<fd>"
        # return f"pipe:{self._stream_fd}"
        return getStreamSource(self._config_entry, self._hdstream)

    def updateTapo(self, camData):
        LOGGER.debug("updateTapo - camera")
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = "idle"
            self._motion_detection_enabled = camData["motion_detection_enabled"]

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
            self._controller.setMotionDetection, True
        )
        await self._coordinator.async_request_refresh()

    async def async_disable_motion_detection(self):
        LOGGER.debug("async_disable_motion_detection - camera")
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection, False
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
