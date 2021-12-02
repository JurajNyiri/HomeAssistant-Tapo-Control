import onvif
import os
import asyncio
import urllib.parse
import socket
import datetime
import time
from onvif import ONVIFCamera
from pytapo import Tapo
from .const import (
    ENABLE_MOTION_SENSOR,
    DOMAIN,
    LOGGER,
    CLOUD_PASSWORD,
    ENABLE_TIME_SYNC,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.onvif.event import EventManager
from homeassistant.components.ffmpeg import DATA_FFMPEG
from haffmpeg.tools import IMAGE_JPEG, ImageFrame


def registerController(host, username, password):
    return Tapo(host, username, password)


def isOpen(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        return True
    except Exception:
        return False


def areCameraPortsOpened(host):
    return isOpen(host, 443) and isOpen(host, 554) and isOpen(host, 2020)


async def isRtspStreamWorking(hass, host, username, password, full_url=""):
    _ffmpeg = hass.data[DATA_FFMPEG]
    ffmpeg = ImageFrame(_ffmpeg.binary)
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)

    streaming_url = full_url
    if full_url == "":
        streaming_url = f"rtsp://{host}:554/stream1"
        if username != "" and password != "":
            streaming_url = f"rtsp://{username}:{password}@{host}:554/stream1"

    image = await asyncio.shield(
        ffmpeg.get_image(streaming_url, output_format=IMAGE_JPEG,)
    )
    return not image == b""


async def initOnvifEvents(hass, host, username, password):
    device = ONVIFCamera(
        host,
        2020,
        username,
        password,
        f"{os.path.dirname(onvif.__file__)}/wsdl/",
        no_cache=True,
    )
    try:
        await device.update_xaddrs()
        device_mgmt = device.create_devicemgmt_service()
        device_info = await device_mgmt.GetDeviceInformation()
        if "Manufacturer" not in device_info:
            raise Exception("Onvif connection has failed.")

        return {"device": device, "device_mgmt": device_mgmt}
    except Exception:
        pass

    return False


async def getCamData(hass, controller):
    camData = {}
    presets = await hass.async_add_executor_job(controller.isSupportingPresets)
    camData["user"] = controller.user
    camData["basic_info"] = await hass.async_add_executor_job(controller.getBasicInfo)
    camData["basic_info"] = camData["basic_info"]["device_info"]["basic_info"]
    try:
        motionDetectionData = await hass.async_add_executor_job(
            controller.getMotionDetection
        )
        motion_detection_enabled = motionDetectionData["enabled"]
        if motionDetectionData["digital_sensitivity"] == "20":
            motion_detection_sensitivity = "low"
        elif motionDetectionData["digital_sensitivity"] == "50":
            motion_detection_sensitivity = "normal"
        elif motionDetectionData["digital_sensitivity"] == "80":
            motion_detection_sensitivity = "high"
        else:
            motion_detection_sensitivity = None
    except Exception:
        motion_detection_enabled = None
        motion_detection_sensitivity = None
    camData["motion_detection_enabled"] = motion_detection_enabled
    camData["motion_detection_sensitivity"] = motion_detection_sensitivity

    try:
        privacy_mode = await hass.async_add_executor_job(controller.getPrivacyMode)
        privacy_mode = privacy_mode["enabled"]
    except Exception:
        privacy_mode = None
    camData["privacy_mode"] = privacy_mode

    try:
        alarmData = await hass.async_add_executor_job(controller.getAlarm)
        alarm = alarmData["enabled"]
        alarm_mode = alarmData["alarm_mode"]
    except Exception:
        alarm = None
        alarm_mode = None
    camData["alarm"] = alarm
    camData["alarm_mode"] = alarm_mode

    try:
        commonImageData = await hass.async_add_executor_job(controller.getCommonImage)
        day_night_mode = commonImageData["image"]["common"]["inf_type"]
    except Exception:
        day_night_mode = None
    camData["day_night_mode"] = day_night_mode

    try:
        led = await hass.async_add_executor_job(controller.getLED)
        led = led["enabled"]
    except Exception:
        led = None
    camData["led"] = led

    try:
        auto_track = await hass.async_add_executor_job(controller.getAutoTrackTarget)
        auto_track = auto_track["enabled"]
    except Exception:
        auto_track = None
    camData["auto_track"] = auto_track

    if presets:
        camData["presets"] = presets
    else:
        camData["presets"] = {}

    return camData


async def update_listener(hass, entry):
    """Handle options update."""
    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)
    cloud_password = entry.data.get(CLOUD_PASSWORD)
    try:
        if cloud_password != "":
            tapoController = await hass.async_add_executor_job(
                registerController, host, "admin", cloud_password
            )
        else:
            tapoController = await hass.async_add_executor_job(
                registerController, host, username, password
            )
        hass.data[DOMAIN][entry.entry_id]["controller"] = tapoController
    except Exception:
        LOGGER.error(
            "Authentication to Tapo camera failed."
            + " Please restart the camera and try again."
        )

    for entity in hass.data[DOMAIN][entry.entry_id]["entities"]:
        entity._host = host
        entity._username = username
        entity._password = password
    if hass.data[DOMAIN][entry.entry_id]["events"]:
        await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()
    if hass.data[DOMAIN][entry.entry_id]["motionSensorCreated"]:
        await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
        hass.data[DOMAIN][entry.entry_id]["motionSensorCreated"] = False
    if motionSensor or enableTimeSync:
        onvifDevice = await initOnvifEvents(hass, host, username, password)
        hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = onvifDevice["device"]
        hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = onvifDevice[
            "device_mgmt"
        ]
        if motionSensor:
            await setupOnvif(hass, entry)


async def syncTime(hass, entry):
    device_mgmt = hass.data[DOMAIN][entry.entry_id]["onvifManagement"]
    if device_mgmt:
        now = datetime.datetime.utcnow()

        time_params = device_mgmt.create_type("SetSystemDateAndTime")
        time_params.DateTimeType = "Manual"
        time_params.DaylightSavings = True
        time_params.UTCDateTime = {
            "Date": {"Year": now.year, "Month": now.month, "Day": now.day},
            "Time": {
                "Hour": now.hour if time.localtime().tm_isdst == 0 else now.hour + 1,
                "Minute": now.minute,
                "Second": now.second,
            },
        }
        await device_mgmt.SetSystemDateAndTime(time_params)
        hass.data[DOMAIN][entry.entry_id][
            "lastTimeSync"
        ] = datetime.datetime.utcnow().timestamp()


async def setupOnvif(hass, entry):
    LOGGER.debug("setupOnvif - entry")
    if hass.data[DOMAIN][entry.entry_id]["eventsDevice"]:
        LOGGER.debug("Setting up onvif...")
        hass.data[DOMAIN][entry.entry_id]["events"] = EventManager(
            hass,
            hass.data[DOMAIN][entry.entry_id]["eventsDevice"],
            f"{entry.entry_id}_tapo_events",
        )

        hass.data[DOMAIN][entry.entry_id]["eventsSetup"] = await setupEvents(
            hass, entry
        )


async def setupEvents(hass, entry):
    LOGGER.debug("setupEvents - entry")
    if not hass.data[DOMAIN][entry.entry_id]["events"].started:
        LOGGER.debug("Setting up events...")
        events = hass.data[DOMAIN][entry.entry_id]["events"]
        if await events.async_start():
            LOGGER.debug("Events started.")
            if not hass.data[DOMAIN][entry.entry_id]["motionSensorCreated"]:
                LOGGER.debug("Creating motion binary sensor...")
                hass.data[DOMAIN][entry.entry_id]["motionSensorCreated"] = True
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(
                        entry, "binary_sensor"
                    )
                )
                LOGGER.debug(
                    "Binary sensor creation for motion has been forwarded to component."
                )
            return True
        else:
            return False
