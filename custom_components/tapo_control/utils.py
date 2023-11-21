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
import pathlib
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
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
    MEDIA_SYNC_COLD_STORAGE_PATH,
    MEDIA_SYNC_HOURS,
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


def pytapoLog(msg):
    LOGGER.debug(f"[pytapo] {msg}")


def registerController(
    host, username, password, password_cloud="", super_secret_key="", device_id=None
):
    return Tapo(
        host,
        username,
        password,
        password_cloud,
        super_secret_key,
        device_id,
        reuseSession=False,
        printDebugInformation=pytapoLog,
        retryStok=False,
    )


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


def getColdDirPathForEntry(hass: HomeAssistant, entry_id: str):
    if hass.data[DOMAIN][entry_id]["mediaSyncColdDir"] is False:
        entry: ConfigEntry = hass.data[DOMAIN][entry_id]["entry"]
        media_sync_cold_storage_path = entry.data.get(MEDIA_SYNC_COLD_STORAGE_PATH)
        if media_sync_cold_storage_path == "":
            coldDirPath = os.path.join(getDataPath(), f".storage/{DOMAIN}/{entry_id}/")
        else:
            coldDirPath = f"{media_sync_cold_storage_path}/"

        pathlib.Path(coldDirPath + "/videos").mkdir(parents=True, exist_ok=True)
        pathlib.Path(coldDirPath + "/thumbs").mkdir(parents=True, exist_ok=True)
        hass.data[DOMAIN][entry_id]["mediaSyncColdDir"] = coldDirPath

    coldDirPath = hass.data[DOMAIN][entry_id]["mediaSyncColdDir"]
    return coldDirPath


def getHotDirPathForEntry(hass: HomeAssistant, entry_id: str):
    if hass.data[DOMAIN][entry_id]["mediaSyncHotDir"] is False:
        hotDirPath = os.path.join(getDataPath(), f"www/{DOMAIN}/{entry_id}/")
        pathlib.Path(hotDirPath + "/videos").mkdir(parents=True, exist_ok=True)
        pathlib.Path(hotDirPath + "/thumbs").mkdir(parents=True, exist_ok=True)
        hass.data[DOMAIN][entry_id]["mediaSyncHotDir"] = hotDirPath

    hotDirPath = hass.data[DOMAIN][entry_id]["mediaSyncHotDir"]
    return hotDirPath


async def getRecordings(hass, entry_id, date):
    tapoController: Tapo = hass.data[DOMAIN][entry_id]["controller"]
    LOGGER.debug("Getting recordings for date " + date + "...")
    recordingsForDay = await hass.async_add_executor_job(
        tapoController.getRecordings, date
    )
    if recordingsForDay is not None:
        for recording in recordingsForDay:
            for recordingKey in recording:
                hass.data[DOMAIN][entry_id]["mediaScanResult"][
                    str(recording[recordingKey]["startTime"])
                    + "-"
                    + str(recording[recordingKey]["endTime"])
                ] = True
    else:
        recordingsForDay = []
    return recordingsForDay


# todo: findMedia needs to run periodically
async def findMedia(hass, entry):
    entry_id = entry.entry_id
    LOGGER.debug("Finding media...")
    hass.data[DOMAIN][entry_id]["initialMediaScanDone"] = False
    tapoController: Tapo = hass.data[DOMAIN][entry_id]["controller"]

    recordingsList = await hass.async_add_executor_job(tapoController.getRecordingsList)
    mediaScanResult = {}
    for searchResult in recordingsList:
        for key in searchResult:
            LOGGER.debug(f"Getting media for day {searchResult[key]['date']}...")
            recordingsForDay = await getRecordings(
                hass, entry_id, searchResult[key]["date"]
            )
            LOGGER.debug(
                f"Looping through recordings for day {searchResult[key]['date']}..."
            )
            for recording in recordingsForDay:
                for recordingKey in recording:
                    filePathVideo = getColdFile(
                        hass,
                        entry_id,
                        recording[recordingKey]["startTime"],
                        recording[recordingKey]["endTime"],
                        "videos",
                    )
                    mediaScanResult[
                        str(recording[recordingKey]["startTime"])
                        + "-"
                        + str(recording[recordingKey]["endTime"])
                    ] = True
                    if os.path.exists(filePathVideo):
                        await processDownload(
                            hass,
                            entry_id,
                            recording[recordingKey]["startTime"],
                            recording[recordingKey]["endTime"],
                        )
    hass.data[DOMAIN][entry_id]["mediaScanResult"] = mediaScanResult
    hass.data[DOMAIN][entry_id]["initialMediaScanDone"] = True
    await mediaCleanup(hass, entry)


async def processDownload(hass, entry_id: int, startDate: int, endDate: int):
    filePath = getFileName(
        startDate,
        endDate,
        False,
    )

    coldFilePath = getColdFile(
        hass,
        entry_id,
        startDate,
        endDate,
        "videos",
    )

    if not os.path.exists(coldFilePath):
        raise Unresolvable("Failed to get file from cold storage: " + coldFilePath)

    if filePath not in hass.data[DOMAIN][entry_id]["downloadedStreams"]:
        hass.data[DOMAIN][entry_id]["downloadedStreams"][filePath] = {
            startDate: startDate,
            endDate: endDate,
        }
    mediaScanName = str(startDate) + "-" + str(endDate)
    if mediaScanName not in hass.data[DOMAIN][entry_id]["mediaScanResult"]:
        hass.data[DOMAIN][entry_id]["mediaScanResult"][mediaScanName] = True

    await generateThumb(
        hass,
        entry_id,
        startDate,
        endDate,
    )


async def generateThumb(hass, entry_id, startDate: int, endDate: int):
    filePathThumb = getColdFile(
        hass,
        entry_id,
        startDate,
        endDate,
        "thumbs",
    )
    if not os.path.exists(filePathThumb):
        filePathVideo = getColdFile(
            hass,
            entry_id,
            startDate,
            endDate,
            "videos",
        )
        _ffmpeg = hass.data[DATA_FFMPEG]
        ffmpeg = ImageFrame(_ffmpeg.binary)
        image = await asyncio.shield(
            ffmpeg.get_image(
                filePathVideo,
                output_format=IMAGE_JPEG,
            )
        )
        with open(filePathThumb, "wb") as binary_file:
            binary_file.write(image)
    return filePathThumb


# todo: findMedia needs to run periodically because of this function!!!
def deleteFilesNoLongerPresentInCamera(hass, entry_id, extension, folder):
    if hass.data[DOMAIN][entry_id]["initialMediaScanDone"] is True:
        coldDirPath = getColdDirPathForEntry(hass, entry_id)
        if os.path.exists(coldDirPath + "/" + folder + "/"):
            for f in os.listdir(coldDirPath + "/" + folder + "/"):
                fileName = f.replace(extension, "")
                filePath = os.path.join(coldDirPath + "/" + folder + "/", f)
                if fileName not in hass.data[DOMAIN][entry_id]["mediaScanResult"]:
                    LOGGER.debug(
                        "[deleteFilesNoLongerPresentInCamera] Removing "
                        + filePath
                        + " ("
                        + fileName
                        + ")..."
                    )
                    hass.data[DOMAIN][entry_id]["downloadedStreams"].pop(
                        fileName,
                        None,
                    )
                    os.remove(filePath)


async def deleteColdFilesOlderThanMaxSyncTime(hass, entry, extension, folder):
    entry_id = entry.entry_id
    mediaSyncHours = entry.data.get(MEDIA_SYNC_HOURS)

    if mediaSyncHours != "":
        coldDirPath = getColdDirPathForEntry(hass, entry_id)
        tapoController: Tapo = hass.data[DOMAIN][entry_id]["controller"]
        timeCorrection = await hass.async_add_executor_job(
            tapoController.getTimeCorrection
        )
        mediaSyncTime = int(mediaSyncHours) * 60 * 60
        entry_id = entry.entry_id
        ts = datetime.datetime.utcnow().timestamp()
        if os.path.exists(coldDirPath + "/" + folder + "/"):
            for f in os.listdir(coldDirPath + "/" + folder + "/"):
                fileName = f.replace(extension, "")
                filePath = os.path.join(coldDirPath + "/" + folder + "/", f)
                splitFileName = fileName.split("-")
                if len(splitFileName) == 2:
                    endTS = int(fileName.split("-")[1])
                    last_modified = os.stat(filePath).st_mtime
                    if (endTS < (int(ts) - (int(mediaSyncTime) + timeCorrection))) and (
                        ts - last_modified > int(mediaSyncTime)
                    ):
                        LOGGER.debug(
                            "[deleteColdFilesOlderThanMaxSyncTime] Removing "
                            + filePath
                            + " ("
                            + fileName
                            + ")..."
                        )
                        hass.data[DOMAIN][entry_id]["downloadedStreams"].pop(
                            fileName,
                            None,
                        )
                        os.remove(filePath)
                else:
                    LOGGER.warn(
                        "[deleteColdFilesOlderThanMaxSyncTime] Ignoring "
                        + filePath
                        + " ("
                        + fileName
                        + ") because of incorrect file name format..."
                    )


async def mediaCleanup(hass, entry):
    entry_id = entry.entry_id
    LOGGER.debug("Initiating media cleanup for entity " + entry_id + "...")

    ts = datetime.datetime.utcnow().timestamp()
    hass.data[DOMAIN][entry_id]["lastMediaCleanup"] = ts
    coldDirPath = getColdDirPathForEntry(hass, entry_id)
    hotDirPath = getHotDirPathForEntry(hass, entry_id)

    # clean cache files from old HA instance
    LOGGER.debug(
        "Removing cache files from old HA instances for entity " + entry_id + "..."
    )
    deleteFilesNotIncluding(hotDirPath + "/videos/", UUID)
    deleteFilesNotIncluding(hotDirPath + "/thumbs/", UUID)

    deleteFilesNoLongerPresentInCamera(hass, entry_id, ".mp4", "videos")
    deleteFilesNoLongerPresentInCamera(hass, entry_id, ".jpg", "thumbs")

    await deleteColdFilesOlderThanMaxSyncTime(hass, entry, ".mp4", "videos")
    await deleteColdFilesOlderThanMaxSyncTime(hass, entry, ".jpg", "thumbs")

    # Delete everything other than HOT_DIR_DELETE_TIME seconds from hot storage
    LOGGER.debug(
        "Deleting hot storage files older than "
        + str(HOT_DIR_DELETE_TIME)
        + " seconds for entity "
        + entry_id
        + "..."
    )
    deleteFilesOlderThan(hotDirPath + "/videos/", HOT_DIR_DELETE_TIME)
    deleteFilesOlderThan(hotDirPath + "/thumbs/", HOT_DIR_DELETE_TIME)


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
                LOGGER.debug("[deleteFilesOlderThan] Removing " + filePath + "...")
                os.remove(filePath)


def deleteFilesNotIncluding(dirPath, includingString):
    if os.path.exists(dirPath):
        for f in os.listdir(dirPath):
            filePath = os.path.join(dirPath, f)
            if includingString not in filePath:
                LOGGER.debug("[deleteFilesOlderThan] Removing " + filePath + "...")
                os.remove(filePath)


def processDownloadStatus(
    hass, entry_id, date: str, allRecordingsCount: int, recordingCount: int = False
):
    def processUpdate(status):
        if isinstance(status, str):
            hass.data[DOMAIN][entry_id]["downloadProgress"] = status
        else:
            hass.data[DOMAIN][entry_id]["downloadProgress"] = (
                status["currentAction"]
                + " "
                + date
                + (
                    f" ({recordingCount} / {allRecordingsCount})"
                    if recordingCount is not False
                    else ""
                )
                + (
                    ": " + str(round(status["progress"])) + " / " + str(status["total"])
                    if status["total"] > 0
                    else ""
                )
            )

    return processUpdate


def getFileName(startDate: int, endDate: int, encrypted=False):
    if encrypted:
        return hashlib.md5((str(startDate) + str(endDate)).encode()).hexdigest()
    else:
        return str(startDate) + "-" + str(endDate)


def getColdFile(
    hass: HomeAssistant, entry_id: str, startDate: int, endDate: int, folder: str
):
    coldDirPath = getColdDirPathForEntry(hass, entry_id)
    fileName = getFileName(startDate, endDate, False)

    if folder == "videos":
        extension = ".mp4"
    elif folder == "thumbs":
        extension = ".jpg"
    else:
        raise Unresolvable("Incorrect folder specified: " + folder)
    return coldDirPath + "/" + folder + "/" + fileName + extension


def getHotFile(
    hass: HomeAssistant, entry_id: str, startDate: int, endDate: int, folder: str
):
    coldFilePath = getColdFile(hass, entry_id, startDate, endDate, folder)
    hotDirPath = getHotDirPathForEntry(hass, entry_id)
    extension = pathlib.Path(coldFilePath).suffix
    fileNameEncrypted = getFileName(
        startDate,
        endDate,
        True,
    )
    hotFilePath = f"{hotDirPath}/{folder}/{fileNameEncrypted}{UUID}{extension}"

    if not os.path.exists(hotFilePath):
        if not os.path.exists(coldFilePath):
            raise Unresolvable("Failed to get file from cold storage: " + coldFilePath)
        shutil.copyfile(coldFilePath, hotFilePath)
    return hotFilePath


def getWebFile(
    hass: HomeAssistant, entry_id: str, startDate: int, endDate: int, folder: str
):
    hotFilePath = getHotFile(hass, entry_id, startDate, endDate, folder)
    fileWebPath = hotFilePath[hotFilePath.index("/www/") + 5 :]  # remove ./www/

    return f"/local/{fileWebPath}"


async def getRecording(
    hass: HomeAssistant,
    tapo: Tapo,
    entry_id: str,
    date: str,
    startDate: int,
    endDate: int,
    recordingCount: int = False,
    totalRecordingCount: int = False,
) -> str:
    timeCorrection = await hass.async_add_executor_job(tapo.getTimeCorrection)

    coldDirPath = getColdDirPathForEntry(hass, entry_id)
    downloadUID = getFileName(startDate, endDate, False)

    coldFilePath = getColdFile(hass, entry_id, startDate, endDate, "videos")
    if not os.path.exists(coldFilePath):
        # this NEEDS to happen otherwise camera does not send data!
        allRecordings = await hass.async_add_executor_job(tapo.getRecordings, date)
        downloader = Downloader(
            tapo,
            startDate,
            endDate,
            timeCorrection,
            coldDirPath + "/videos/",
            0,
            None,
            None,
            downloadUID + ".mp4",
        )

        hass.data[DOMAIN][entry_id]["isDownloadingStream"] = True
        downloadedFile = await downloader.downloadFile(
            processDownloadStatus(
                hass,
                entry_id,
                date,
                len(allRecordings)
                if totalRecordingCount is False
                else totalRecordingCount,
                recordingCount if recordingCount is not False else False,
            )
        )
        hass.data[DOMAIN][entry_id]["isDownloadingStream"] = False
        if downloadedFile["currentAction"] == "Recording in progress":
            raise Unresolvable("Recording is currently in progress.")

        hass.bus.fire(
            "tapo_control_media_downloaded",
            {
                "entry_id": entry_id,
                "startDate": startDate,
                "endDate": endDate,
                "filePath": coldFilePath,
            },
        )

    await processDownload(
        hass,
        entry_id,
        startDate,
        endDate,
    )

    return coldFilePath


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
        motion_detection_digital_sensitivity = motionDetectionData[
            "digital_sensitivity"
        ]
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
        motion_detection_digital_sensitivity = None
    camData["motion_detection_enabled"] = motion_detection_enabled
    camData["motion_detection_sensitivity"] = motion_detection_sensitivity
    camData[
        "motion_detection_digital_sensitivity"
    ] = motion_detection_digital_sensitivity

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
        notifications = data["getMsgPushConfig"]["msg_push"]["chn1_msg_push_info"][
            "notification_enabled"
        ]
    except Exception:
        notifications = None
    camData["notifications"] = notifications

    try:
        rich_notifications = data["getMsgPushConfig"]["msg_push"]["chn1_msg_push_info"][
            "rich_notification_enabled"
        ]
    except Exception:
        rich_notifications = None
    camData["rich_notifications"] = rich_notifications

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

    try:
        whitelampConfigForceTime = data["getWhitelampConfig"]["image"]["switch"][
            "wtl_force_time"
        ]
    except Exception:
        whitelampConfigForceTime = None
    camData["whitelampConfigForceTime"] = whitelampConfigForceTime

    try:
        whitelampConfigIntensity = data["getWhitelampConfig"]["image"]["switch"][
            "wtl_intensity_level"
        ]
    except Exception:
        whitelampConfigIntensity = None
    camData["whitelampConfigIntensity"] = whitelampConfigIntensity

    try:
        whitelampStatus = data["getWhitelampStatus"]["status"]
    except Exception:
        whitelampStatus = None
    camData["whitelampStatus"] = whitelampStatus

    try:
        sdCardData = []
        for hdd in data["getSdCardStatus"]["harddisk_manage"]["hd_info"]:
            sdCardData.append(hdd["hd_info_1"])
    except Exception:
        sdCardData = []
    camData["sdCardData"] = sdCardData

    try:
        recordPlan = data["getRecordPlan"]["record_plan"]["chn1_channel"]
    except Exception:
        recordPlan = None
    camData["recordPlan"] = recordPlan

    try:
        microphoneVolume = data["getAudioConfig"]["audio_config"]["microphone"][
            "volume"
        ]
    except Exception:
        microphoneVolume = None
    camData["microphoneVolume"] = microphoneVolume

    try:
        microphoneMute = data["getAudioConfig"]["audio_config"]["microphone"]["mute"]
    except Exception:
        microphoneMute = None
    camData["microphoneMute"] = microphoneMute

    try:
        microphoneNoiseCancelling = data["getAudioConfig"]["audio_config"][
            "microphone"
        ]["noise_cancelling"]
    except Exception:
        microphoneNoiseCancelling = None
    camData["microphoneNoiseCancelling"] = microphoneNoiseCancelling

    try:
        speakerVolume = data["getAudioConfig"]["audio_config"]["speaker"]["volume"]
    except Exception:
        speakerVolume = None
    camData["speakerVolume"] = speakerVolume

    try:
        autoUpgradeEnabled = data["getFirmwareAutoUpgradeConfig"]["auto_upgrade"][
            "common"
        ]["enabled"]
    except Exception:
        autoUpgradeEnabled = None
    camData["autoUpgradeEnabled"] = autoUpgradeEnabled

    LOGGER.debug("getCamData - done")
    LOGGER.debug("Processed update data:")
    LOGGER.debug(camData)
    return camData


def convert_to_timestamp(date_string):
    date_format = "%Y%m%d"
    try:
        date = datetime.datetime.strptime(date_string, date_format)
        timestamp = datetime.datetime.timestamp(date)
        return int(timestamp)
    except ValueError:
        raise Exception(
            "Invalid date format. Please provide a date in the format 'YYYYMMDD'."
        )


async def update_listener(hass, entry):
    """Handle options update."""
    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)
    cloud_password = entry.data.get(CLOUD_PASSWORD)
    try:
        newUUID = hashlib.md5(
            (str(host) + str(username) + str(password) + str(cloud_password)).encode()
        ).hexdigest()
        # only update controller if auth data changed
        if newUUID != hass.data[DOMAIN][entry.entry_id]["uuid"]:
            hass.data[DOMAIN][entry.entry_id]["uuid"] = newUUID
            if (
                hass.data[DOMAIN][entry.entry_id]["controller"]
                in hass.data[DOMAIN][entry.entry_id]["allControllers"]
            ):
                hass.data[DOMAIN][entry.entry_id]["allControllers"].remove(
                    hass.data[DOMAIN][entry.entry_id]["controller"]
                )
            if cloud_password != "":
                tapoController = await hass.async_add_executor_job(
                    registerController, host, "admin", cloud_password
                )
            else:
                tapoController = await hass.async_add_executor_job(
                    registerController, host, username, password
                )
            hass.data[DOMAIN][entry.entry_id]["usingCloudPassword"] = (
                cloud_password != ""
            )
            hass.data[DOMAIN][entry.entry_id]["controller"] = tapoController
            hass.data[DOMAIN][entry.entry_id]["allControllers"].append(tapoController)
    except Exception:
        LOGGER.error(
            "Authentication to Tapo camera failed."
            + " Please restart the camera and try again."
        )

    for entity in hass.data[DOMAIN][entry.entry_id]["entities"]:
        if "_host" in entity:
            entity._host = host
        if "_username" in entity:
            entity._username = username
        if "_password" in entity:
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
    elif pytapoFunctionName == "getNotificationsEnabled":
        return ["getMsgPushConfig"]
    elif pytapoFunctionName == "getWhitelampStatus":
        return ["getWhitelampStatus"]
    elif pytapoFunctionName == "getRecordPlan":
        return ["getRecordPlan"]
    elif pytapoFunctionName == "getWhitelampConfig":
        return ["getWhitelampConfig"]
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
    elif pytapoFunctionName == "getAudioConfig":
        return ["getAudioConfig"]
    elif pytapoFunctionName == "getFirmwareAutoUpgradeConfig":
        return ["getFirmwareAutoUpgradeConfig"]
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
