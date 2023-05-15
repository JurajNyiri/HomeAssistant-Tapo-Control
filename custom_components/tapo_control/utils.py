import asyncio
import datetime
import hashlib
import pathlib
import onvif
import os
import shutil
import socket
import time
import urllib.parse
import uuid
from homeassistant.core import HomeAssistant
from pytapo.media_stream.downloader import Downloader
from homeassistant.components.media_source.error import Unresolvable

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from onvif import ONVIFCamera
from pytapo import Tapo
from yarl import URL
from homeassistant.helpers.network import NoURLAvailableError, get_url

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.components.onvif.event import EventManager
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import slugify

from .const import (
    BRAND,
    COLD_DIR_DELETE_TIME,
    ENABLE_MOTION_SENSOR,
    DOMAIN,
    ENABLE_WEBHOOKS,
    HOT_DIR_DELETE_TIME,
    LOGGER,
    CLOUD_PASSWORD,
    ENABLE_TIME_SYNC,
    CONF_CUSTOM_STREAM,
)

UUID = uuid.uuid4().hex


def isUsingHTTPS(hass):
    try:
        base_url = get_url(hass, prefer_external=False)
    except NoURLAvailableError:
        try:
            base_url = get_url(hass, prefer_external=True)
        except NoURLAvailableError:
            return True
    LOGGER.debug("Detected base_url schema: " + URL(base_url).scheme)
    return URL(base_url).scheme == "https"


def getStreamSource(entry, hdStream):
    custom_stream = entry.data.get(CONF_CUSTOM_STREAM)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    host = entry.data.get(CONF_IP_ADDRESS)
    if custom_stream != "":
        return custom_stream

    if hdStream:
        streamType = "stream1"
    else:
        streamType = "stream2"
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)
    streamURL = f"rtsp://{username}:{password}@{host}:554/{streamType}"
    return streamURL


def registerController(
    host, username, password, password_cloud="", super_secret_key="", device_id=None
):
    return Tapo(host, username, password, password_cloud, super_secret_key, device_id)


def isOpen(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        return True
    except Exception:
        return False


def getDataPath():
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    )


def getColdDirPathForEntry(entry_id):
    return os.path.join(getDataPath(), f".storage/{DOMAIN}/{entry_id}/")


def getHotDirPathForEntry(entry_id):
    return os.path.join(getDataPath(), f"www/{DOMAIN}/{entry_id}/")


def mediaCleanup(hass, entry_id):
    LOGGER.debug("Initiating media cleanup for entity " + entry_id + "...")
    hass.data[DOMAIN][entry_id][
        "lastMediaCleanup"
    ] = datetime.datetime.utcnow().timestamp()
    coldDirPath = getColdDirPathForEntry(entry_id)
    hotDirPath = getHotDirPathForEntry(entry_id)

    # Delete everything other than COLD_DIR_DELETE_TIME seconds from cold storage
    LOGGER.debug(
        "Deleting cold storage files older than "
        + str(COLD_DIR_DELETE_TIME)
        + " seconds for entity "
        + entry_id
        + "..."
    )
    deleteFilesOlderThan(coldDirPath, COLD_DIR_DELETE_TIME)

    # Delete everything other than HOT_DIR_DELETE_TIME seconds from hot storage
    LOGGER.debug(
        "Deleting hot storage files older than "
        + str(HOT_DIR_DELETE_TIME)
        + " seconds for entity "
        + entry_id
        + "..."
    )
    deleteFilesOlderThan(hotDirPath, HOT_DIR_DELETE_TIME)


def deleteDir(dirPath):
    if (
        os.path.exists(dirPath)
        and os.path.isdir(dirPath)
        and dirPath != "/"
        and "tapo_control/" in dirPath
    ):
        LOGGER.debug("Deleting folder " + dirPath + "...")
        shutil.rmtree(dirPath)


def deleteFilesOlderThan(dirPath, deleteOlderThan):
    now = datetime.datetime.utcnow().timestamp()
    if os.path.exists(dirPath):
        for f in os.listdir(dirPath):
            filePath = os.path.join(dirPath, f)
            last_modified = os.stat(filePath).st_mtime
            if now - last_modified > deleteOlderThan:
                os.remove(filePath)


def processDownload(status):
    LOGGER.debug(status)


async def getRecording(
    hass: HomeAssistant,
    tapo: Tapo,
    entry_id: str,
    date: str,
    startDate: int,
    endDate: int,
) -> str:
    # this NEEDS to happen otherwise camera does not send data!
    await hass.async_add_executor_job(tapo.getRecordings, date)

    mediaCleanup(hass, entry_id)

    coldDirPath = getColdDirPathForEntry(entry_id)
    hotDirPath = getHotDirPathForEntry(entry_id)

    pathlib.Path(coldDirPath).mkdir(parents=True, exist_ok=True)
    pathlib.Path(hotDirPath).mkdir(parents=True, exist_ok=True)

    downloadUID = hashlib.md5((str(startDate) + str(endDate)).encode()).hexdigest()
    downloader = Downloader(
        tapo,
        startDate,
        endDate,
        coldDirPath,
        0,
        None,
        None,
        downloadUID + ".mp4",
    )
    # todo: automatic deletion of recordings longer than X in hot storage

    hass.data[DOMAIN][entry_id]["isDownloadingStream"] = True
    downloadedFile = await downloader.downloadFile(processDownload)
    hass.data[DOMAIN][entry_id]["isDownloadingStream"] = False
    if downloadedFile["currentAction"] == "Recording in progress":
        raise Unresolvable("Recording is currently in progress.")

    coldFilePath = downloadedFile["fileName"]
    hotFilePath = (
        coldFilePath.replace("/.storage/", "/www/").replace(".mp4", "") + UUID + ".mp4"
    )
    shutil.copyfile(coldFilePath, hotFilePath)

    fileWebPath = hotFilePath[hotFilePath.index("/www/") + 5 :]  # remove ./www/

    return f"/local/{fileWebPath}"


def areCameraPortsOpened(host):
    return isOpen(host, 443) and isOpen(host, 554) and isOpen(host, 2020)


async def isRtspStreamWorking(hass, host, username, password, full_url=""):
    LOGGER.debug("[isRtspStreamWorking][%s] Testing RTSP stream.", host)
    _ffmpeg = hass.data[DATA_FFMPEG]
    LOGGER.debug("[isRtspStreamWorking][%s] Creating image frame.", host)
    ffmpeg = ImageFrame(_ffmpeg.binary)
    LOGGER.debug("[isRtspStreamWorking][%s] Encoding username and password.", host)
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)

    streaming_url = full_url
    if full_url == "":
        streaming_url = f"rtsp://{host}:554/stream1"
        if username != "" and password != "":
            streaming_url = f"rtsp://{username}:{password}@{host}:554/stream1"

    LOGGER.debug(
        "[isRtspStreamWorking][%s] Getting image from %s.",
        host,
        streaming_url.replace(username, "HIDDEN_USERNAME").replace(
            password, "HIDDEN_PASSWORD"
        ),
    )
    image = await asyncio.shield(
        ffmpeg.get_image(
            streaming_url,
            output_format=IMAGE_JPEG,
        )
    )
    LOGGER.debug(
        "[isRtspStreamWorking][%s] Image data received.",
        host,
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
        LOGGER.debug("[initOnvifEvents] Creating onvif connection...")
        await device.update_xaddrs()
        LOGGER.debug("[initOnvifEvents] Connection estabilished.")
        device_mgmt = await device.create_devicemgmt_service()
        LOGGER.debug("[initOnvifEvents] Getting device information...")
        device_info = await device_mgmt.GetDeviceInformation()
        LOGGER.debug("[initOnvifEvents] Got device information.")
        if "Manufacturer" not in device_info:
            raise Exception("Onvif connection has failed.")

        return {"device": device, "device_mgmt": device_mgmt}
    except Exception as e:
        LOGGER.error("[initOnvifEvents] Initiating onvif connection failed.")
        LOGGER.error(e)

    return False


def tryParseInt(value):
    try:
        return int(value)
    except Exception as e:
        LOGGER.error("Couldnt parse as integer: %s", str(e))
        return None


async def getCamData(hass, controller):
    LOGGER.debug("getCamData")
    data = await hass.async_add_executor_job(controller.getMost)
    LOGGER.debug("Raw update data:")
    LOGGER.debug(data)
    camData = {}

    camData["raw"] = data

    camData["user"] = controller.user
    camData["basic_info"] = data["getDeviceInfo"]["device_info"]["basic_info"]
    try:
        motionDetectionData = data["getDetectionConfig"]["motion_detection"][
            "motion_det"
        ]
        motion_detection_enabled = motionDetectionData["enabled"]
        if motionDetectionData["digital_sensitivity"] == "20" or (
            "sensitivity" in motionDetectionData
            and motionDetectionData["sensitivity"] == "low"
        ):
            motion_detection_sensitivity = "low"
        elif motionDetectionData["digital_sensitivity"] == "50" or (
            "sensitivity" in motionDetectionData
            and motionDetectionData["sensitivity"] == "medium"
        ):
            motion_detection_sensitivity = "normal"
        elif motionDetectionData["digital_sensitivity"] == "80" or (
            "sensitivity" in motionDetectionData
            and motionDetectionData["sensitivity"] == "high"
        ):
            motion_detection_sensitivity = "high"
        else:
            motion_detection_sensitivity = None
    except Exception:
        motion_detection_enabled = None
        motion_detection_sensitivity = None
    camData["motion_detection_enabled"] = motion_detection_enabled
    camData["motion_detection_sensitivity"] = motion_detection_sensitivity

    try:
        personDetectionData = data["getPersonDetectionConfig"]["people_detection"][
            "detection"
        ]
        person_detection_enabled = personDetectionData["enabled"]
        person_detection_sensitivity = None

        sensitivity = tryParseInt(personDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                person_detection_sensitivity = "low"
            elif sensitivity <= 66:
                person_detection_sensitivity = "normal"
            else:
                person_detection_sensitivity = "high"
    except Exception:
        person_detection_enabled = None
        person_detection_sensitivity = None
    camData["person_detection_enabled"] = person_detection_enabled
    camData["person_detection_sensitivity"] = person_detection_sensitivity

    try:
        vehicleDetectionData = data["getVehicleDetectionConfig"]["vehicle_detection"][
            "detection"
        ]
        vehicle_detection_enabled = vehicleDetectionData["enabled"]
        vehicle_detection_sensitivity = None

        sensitivity = tryParseInt(vehicleDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                vehicle_detection_sensitivity = "low"
            elif sensitivity <= 66:
                vehicle_detection_sensitivity = "normal"
            else:
                vehicle_detection_sensitivity = "high"
    except Exception:
        vehicle_detection_enabled = None
        vehicle_detection_sensitivity = None
    camData["vehicle_detection_enabled"] = vehicle_detection_enabled
    camData["vehicle_detection_sensitivity"] = vehicle_detection_sensitivity

    try:
        babyCryDetectionData = data["getBCDConfig"]["sound_detection"]["bcd"]
        babyCry_detection_enabled = babyCryDetectionData["enabled"]
        babyCry_detection_sensitivity = None

        sensitivity = babyCryDetectionData["sensitivity"]
        if sensitivity is not None:
            if sensitivity == "low":
                babyCry_detection_sensitivity = "low"
            elif sensitivity == "medium":
                babyCry_detection_sensitivity = "normal"
            else:
                babyCry_detection_sensitivity = "high"
    except Exception:
        babyCry_detection_enabled = None
        babyCry_detection_sensitivity = None
    camData["babyCry_detection_enabled"] = babyCry_detection_enabled
    camData["babyCry_detection_sensitivity"] = babyCry_detection_sensitivity

    try:
        petDetectionData = data["getPetDetectionConfig"]["pet_detection"]["detection"]
        pet_detection_enabled = petDetectionData["enabled"]
        pet_detection_sensitivity = None

        sensitivity = tryParseInt(petDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                pet_detection_sensitivity = "low"
            elif sensitivity <= 66:
                pet_detection_sensitivity = "normal"
            else:
                pet_detection_sensitivity = "high"
    except Exception:
        pet_detection_enabled = None
        pet_detection_sensitivity = None
    camData["pet_detection_enabled"] = pet_detection_enabled
    camData["pet_detection_sensitivity"] = pet_detection_sensitivity

    try:
        barkDetectionData = data["getBarkDetectionConfig"]["bark_detection"][
            "detection"
        ]
        bark_detection_enabled = barkDetectionData["enabled"]
        bark_detection_sensitivity = None

        sensitivity = tryParseInt(barkDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                bark_detection_sensitivity = "low"
            elif sensitivity <= 66:
                bark_detection_sensitivity = "normal"
            else:
                bark_detection_sensitivity = "high"
    except Exception:
        bark_detection_enabled = None
        bark_detection_sensitivity = None
    camData["bark_detection_enabled"] = bark_detection_enabled
    camData["bark_detection_sensitivity"] = bark_detection_sensitivity

    try:
        meowDetectionData = data["getMeowDetectionConfig"]["meow_detection"][
            "detection"
        ]
        meow_detection_enabled = meowDetectionData["enabled"]
        meow_detection_sensitivity = None

        sensitivity = tryParseInt(meowDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                meow_detection_sensitivity = "low"
            elif sensitivity <= 66:
                meow_detection_sensitivity = "normal"
            else:
                meow_detection_sensitivity = "high"
    except Exception:
        meow_detection_enabled = None
        meow_detection_sensitivity = None
    camData["meow_detection_enabled"] = meow_detection_enabled
    camData["meow_detection_sensitivity"] = meow_detection_sensitivity

    try:
        glassDetectionData = data["getGlassDetectionConfig"]["glass_detection"][
            "detection"
        ]
        glass_detection_enabled = glassDetectionData["enabled"]
        glass_detection_sensitivity = None

        sensitivity = tryParseInt(glassDetectionData["sensitivity"])
        if sensitivity is not None:
            if sensitivity <= 33:
                glass_detection_sensitivity = "low"
            elif sensitivity <= 66:
                glass_detection_sensitivity = "normal"
            else:
                glass_detection_sensitivity = "high"
    except Exception:
        glass_detection_enabled = None
        glass_detection_sensitivity = None
    camData["glass_detection_enabled"] = glass_detection_enabled
    camData["glass_detection_sensitivity"] = glass_detection_sensitivity

    try:
        tamperDetectionData = data["getTamperDetectionConfig"]["tamper_detection"][
            "tamper_det"
        ]
        tamper_detection_enabled = tamperDetectionData["enabled"]
        tamper_detection_sensitivity = None

        if sensitivity is not None:
            if sensitivity == "low":
                tamper_detection_sensitivity = "low"
            elif sensitivity == "medium":
                tamper_detection_sensitivity = "normal"
            else:
                tamper_detection_sensitivity = "high"
    except Exception:
        tamper_detection_enabled = None
        tamper_detection_sensitivity = None
    camData["tamper_detection_enabled"] = tamper_detection_enabled
    camData["tamper_detection_sensitivity"] = tamper_detection_sensitivity

    try:
        presets = {
            id: data["getPresetConfig"]["preset"]["preset"]["name"][key]
            for key, id in enumerate(data["getPresetConfig"]["preset"]["preset"]["id"])
        }
    except Exception:
        presets = False

    try:
        privacy_mode = data["getLensMaskConfig"]["lens_mask"]["lens_mask_info"][
            "enabled"
        ]
    except Exception:
        privacy_mode = None
    camData["privacy_mode"] = privacy_mode

    try:
        lens_distrotion_correction = data["getLdc"]["image"]["switch"]["ldc"]
    except Exception:
        lens_distrotion_correction = None
    camData["lens_distrotion_correction"] = lens_distrotion_correction

    try:
        light_frequency_mode = data["getLdc"]["image"]["common"]["light_freq_mode"]
    except Exception:
        light_frequency_mode = None

    if light_frequency_mode is None:
        try:
            light_frequency_mode = data["getLightFrequencyInfo"]["image"]["common"][
                "light_freq_mode"
            ]
        except Exception:
            light_frequency_mode = None
    camData["light_frequency_mode"] = light_frequency_mode

    try:
        day_night_mode = data["getLdc"]["image"]["common"]["inf_type"]
    except Exception:
        day_night_mode = None

    if day_night_mode is None:
        try:
            if (
                data["getNightVisionModeConfig"]["image"]["switch"]["night_vision_mode"]
                == "inf_night_vision"
            ):
                day_night_mode = "on"
            elif (
                data["getNightVisionModeConfig"]["image"]["switch"]["night_vision_mode"]
                == "wtl_night_vision"
            ):
                day_night_mode = "off"
            elif (
                data["getNightVisionModeConfig"]["image"]["switch"]["night_vision_mode"]
                == "md_night_vision"
            ):
                day_night_mode = "auto"
        except Exception:
            day_night_mode = None
    camData["day_night_mode"] = day_night_mode

    try:
        force_white_lamp_state = data["getLdc"]["image"]["switch"]["force_wtl_state"]
    except Exception:
        force_white_lamp_state = None
    camData["force_white_lamp_state"] = force_white_lamp_state

    try:
        flip = (
            "on"
            if data["getLdc"]["image"]["switch"]["flip_type"] == "center"
            else "off"
        )
    except Exception:
        flip = None

    if flip is None:
        try:
            flip = (
                "on"
                if data["getRotationStatus"]["image"]["switch"]["flip_type"] == "center"
                else "off"
            )
        except Exception:
            flip = None
    camData["flip"] = flip

    try:
        alarmData = data["getLastAlarmInfo"]["msg_alarm"]["chn1_msg_alarm_info"]
        alarm = alarmData["enabled"]
        alarm_mode = alarmData["alarm_mode"]
    except Exception:
        alarm = None
        alarm_mode = None

    if alarm is None or alarm_mode is None:
        try:
            alarmData = data["getAlarmConfig"]
            alarm = alarmData["enabled"]
            alarm_mode = alarmData["alarm_mode"]
        except Exception:
            alarm = None
            alarm_mode = None
    camData["alarm"] = alarm
    camData["alarm_mode"] = alarm_mode

    try:
        led = data["getLedStatus"]["led"]["config"]["enabled"]
    except Exception:
        led = None
    camData["led"] = led

    # todo rest
    try:
        auto_track = data["getTargetTrackConfig"]["target_track"]["target_track_info"][
            "enabled"
        ]
    except Exception:
        auto_track = None
    camData["auto_track"] = auto_track

    if presets:
        camData["presets"] = presets
    else:
        camData["presets"] = {}

    try:
        firmwareUpdateStatus = data["getFirmwareUpdateStatus"]["cloud_config"]
    except Exception:
        firmwareUpdateStatus = None
    camData["firmwareUpdateStatus"] = firmwareUpdateStatus

    try:
        childDevices = data["getChildDeviceList"]
    except Exception:
        childDevices = None
    camData["childDevices"] = childDevices

    LOGGER.debug("getCamData - done")
    LOGGER.debug("Processed update data:")
    LOGGER.debug(camData)
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
        hass.data[DOMAIN][entry.entry_id]["usingCloudPassword"] = cloud_password != ""
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


async def getLatestFirmwareVersion(hass, config_entry, entry, controller):
    entry["lastFirmwareCheck"] = datetime.datetime.utcnow().timestamp()
    try:
        updateInfo = await hass.async_add_executor_job(controller.isUpdateAvailable)
        if (
            "version"
            in updateInfo["result"]["responses"][1]["result"]["cloud_config"][
                "upgrade_info"
            ]
        ):
            updateInfo = updateInfo["result"]["responses"][1]["result"]["cloud_config"][
                "upgrade_info"
            ]
        else:
            updateInfo = False
    except Exception:
        updateInfo = False
    return updateInfo


async def syncTime(hass, entry_id):
    device_mgmt = hass.data[DOMAIN][entry_id]["onvifManagement"]
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
        hass.data[DOMAIN][entry_id][
            "lastTimeSync"
        ] = datetime.datetime.utcnow().timestamp()


async def setupOnvif(hass, entry):
    LOGGER.debug("setupOnvif - entry")
    if hass.data[DOMAIN][entry.entry_id]["eventsDevice"]:
        LOGGER.debug("Setting up onvif...")
        hass.data[DOMAIN][entry.entry_id]["events"] = EventManager(
            hass,
            hass.data[DOMAIN][entry.entry_id]["eventsDevice"],
            entry,
            hass.data[DOMAIN][entry.entry_id]["name"],
        )

        hass.data[DOMAIN][entry.entry_id]["eventsSetup"] = await setupEvents(
            hass, entry
        )


async def setupEvents(hass, config_entry):
    LOGGER.debug("setupEvents - entry")
    shouldUseWebhooks = (
        isUsingHTTPS(hass) is False and config_entry.data.get(ENABLE_WEBHOOKS) is True
    )
    LOGGER.debug("Using HTTPS: " + str(isUsingHTTPS(hass)))
    LOGGER.debug(
        "Webhook enabled: " + str(config_entry.data.get(ENABLE_WEBHOOKS) is True)
    )
    LOGGER.debug("Using Webhooks: " + str(shouldUseWebhooks))
    if not hass.data[DOMAIN][config_entry.entry_id]["events"].started:
        LOGGER.debug("Setting up events...")
        events = hass.data[DOMAIN][config_entry.entry_id]["events"]
        onvif_capabilities = await hass.data[DOMAIN][config_entry.entry_id][
            "eventsDevice"
        ].get_capabilities()
        onvif_capabilities = onvif_capabilities or {}
        pull_point_support = onvif_capabilities.get("Events", {}).get(
            "WSPullPointSupport"
        )
        LOGGER.debug("WSPullPointSupport: %s", pull_point_support)
        if await events.async_start(pull_point_support is not False, shouldUseWebhooks):
            LOGGER.debug("Events started.")
            if not hass.data[DOMAIN][config_entry.entry_id]["motionSensorCreated"]:
                hass.data[DOMAIN][config_entry.entry_id]["motionSensorCreated"] = True
                if hass.data[DOMAIN][config_entry.entry_id]["eventsListener"]:
                    hass.data[DOMAIN][config_entry.entry_id][
                        "eventsListener"
                    ].createBinarySensor()
                else:
                    LOGGER.error(
                        "Trying to create motion sensor but motion listener not set up!"
                    )

                LOGGER.debug(
                    "Binary sensor creation for motion has been forwarded to component."
                )
            return True
        else:
            return False


def build_device_info(attributes: dict) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, slugify(f"{attributes['mac']}_tapo_control"))},
        connections={("mac", attributes["mac"])},
        name=attributes["device_alias"],
        manufacturer=BRAND,
        model=attributes["device_model"],
        sw_version=attributes["sw_version"],
        hw_version=attributes["hw_version"],
    )


def pytapoFunctionMap(pytapoFunctionName):
    if pytapoFunctionName == "getPrivacyMode":
        return ["getLensMaskConfig"]
    elif pytapoFunctionName == "getBasicInfo":
        return ["getDeviceInfo"]
    elif pytapoFunctionName == "getMotionDetection":
        return ["getDetectionConfig"]
    elif pytapoFunctionName == "getPersonDetection":
        return ["getPersonDetectionConfig"]
    elif pytapoFunctionName == "getVehicleDetection":
        return ["getVehicleDetectionConfig"]
    elif pytapoFunctionName == "getBabyCryDetection":
        return ["getBCDConfig"]
    elif pytapoFunctionName == "getPetDetection":
        return ["getPetDetectionConfig"]
    elif pytapoFunctionName == "getBarkDetection":
        return ["getBarkDetectionConfig"]
    elif pytapoFunctionName == "getMeowDetection":
        return ["getMeowDetectionConfig"]
    elif pytapoFunctionName == "getGlassBreakDetection":
        return ["getGlassDetectionConfig"]
    elif pytapoFunctionName == "getTamperDetection":
        return ["getTamperDetectionConfig"]
    elif pytapoFunctionName == "getLdc":
        return ["getLensDistortionCorrection"]
    elif pytapoFunctionName == "getAlarm":
        return ["getLastAlarmInfo", "getAlarmConfig"]
    elif pytapoFunctionName == "getLED":
        return ["getLedStatus"]
    elif pytapoFunctionName == "getAutoTrackTarget":
        return ["getTargetTrackConfig"]
    elif pytapoFunctionName == "getPresets":
        return ["getPresetConfig"]
    elif pytapoFunctionName == "getFirmwareUpdateStatus":
        return ["getFirmwareUpdateStatus"]
    elif pytapoFunctionName == "getMediaEncrypt":
        return ["getMediaEncrypt"]
    elif pytapoFunctionName == "getLightFrequencyMode":
        return ["getLightFrequencyInfo", "getLightFrequencyCapability"]
    elif pytapoFunctionName == "getChildDevices":
        return ["getChildDeviceList"]
    elif pytapoFunctionName == "getRotationStatus":
        return ["getRotationStatus"]
    elif pytapoFunctionName == "getForceWhitelampState":
        return ["getLdc"]
    elif pytapoFunctionName == "getDayNightMode":
        return ["getLightFrequencyInfo", "getNightVisionModeConfig"]
    elif pytapoFunctionName == "getImageFlipVertical":
        return ["getRotationStatus", "getLdc"]
    elif pytapoFunctionName == "getLensDistortionCorrection":
        return ["getLdc"]
    return []


def isCacheSupported(check_function, rawData):
    rawFunctions = pytapoFunctionMap(check_function)
    for function in rawFunctions:
        if function in rawData and rawData[function]:
            if check_function == "getForceWhitelampState":
                return (
                    "image" in rawData["getLdc"]
                    and "switch" in rawData["getLdc"]["image"]
                    and "force_wtl_state" in rawData["getLdc"]["image"]["switch"]
                )
            elif check_function == "getDayNightMode":
                return (
                    "image" in rawData["getLightFrequencyInfo"]
                    and "common" in rawData["getLightFrequencyInfo"]["image"]
                    and "inf_type"
                    in rawData["getLightFrequencyInfo"]["image"]["common"]
                )
            elif check_function == "getImageFlipVertical":
                return (
                    "image" in rawData["getLdc"]
                    and "switch" in rawData["getLdc"]["image"]
                    and "flip_type" in rawData["getLdc"]["image"]["switch"]
                ) or (
                    "image" in rawData["getRotationStatus"]
                    and "switch" in rawData["getRotationStatus"]["image"]
                    and "flip_type" in rawData["getRotationStatus"]["image"]["switch"]
                )
            elif check_function == "getLensDistortionCorrection":
                return (
                    "image" in rawData["getLdc"]
                    and "switch" in rawData["getLdc"]["image"]
                    and "ldc" in rawData["getLdc"]["image"]["switch"]
                )
            return True
    return False


async def check_and_create(entry, hass, cls, check_function, config_entry):
    if isCacheSupported(check_function, entry["camData"]["raw"]):
        LOGGER.debug(
            f"Found cached capability {check_function}, creating {cls.__name__}"
        )
        return cls(entry, hass, config_entry)
    else:
        LOGGER.debug(f"Capability {check_function} not found, querying again...")
        try:
            await hass.async_add_executor_job(
                getattr(entry["controller"], check_function)
            )
        except Exception:
            LOGGER.info(f"Camera does not support {cls.__name__}")
            return None
        LOGGER.debug(f"Creating {cls.__name__}")
        return cls(entry, hass, config_entry)
