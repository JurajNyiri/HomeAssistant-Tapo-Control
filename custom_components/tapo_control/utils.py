import asyncio
import datetime
import hashlib
import pathlib
import onvif
import os
import shutil
import socket
import urllib.parse
import uuid
import requests
import base64

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
from homeassistant.util import slugify, dt as dt_util

from .const import (
    BRAND,
    CONTROL_PORT,
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
    TIME_SYNC_DST,
    TIME_SYNC_NDST,
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


def isKLAP(host, port, timeout=2):
    try:
        url = f"http://{host}:{port}"
        response = requests.get(url, timeout=timeout)
        return "200 OK" in response.text
    except requests.RequestException:
        return False


def registerController(
    host,
    control_port,
    username,
    password,
    password_cloud="",
    super_secret_key="",
    device_id=None,
    is_klap=None,
    hass=None,
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
        controlPort=control_port,
        isKLAP=is_klap,
        hass=hass,
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
    # Fast retrieval of path without file IO
    if (
        entry_id in hass.data[DOMAIN]
        and hass.data[DOMAIN][entry_id]["mediaSyncColdDir"] is not False
    ):
        return hass.data[DOMAIN][entry_id]["mediaSyncColdDir"].rstrip("/")

    coldDirPath = os.path.join(getDataPath(), f".storage/{DOMAIN}/{entry_id}/")
    if entry_id in hass.data[DOMAIN]:
        entry: ConfigEntry = hass.data[DOMAIN][entry_id]["entry"]
    else:  # if device is disabled, get entry from HA storage
        entry: ConfigEntry = hass.config_entries.async_get_entry(entry_id)

    media_sync_cold_storage_path = entry.data.get(MEDIA_SYNC_COLD_STORAGE_PATH)

    if not media_sync_cold_storage_path == "":
        coldDirPath = f"{media_sync_cold_storage_path}/"

    if entry_id in hass.data[DOMAIN]:
        pathlib.Path(coldDirPath + "/videos").mkdir(parents=True, exist_ok=True)
        pathlib.Path(coldDirPath + "/thumbs").mkdir(parents=True, exist_ok=True)
        hass.data[DOMAIN][entry_id]["mediaSyncColdDir"] = coldDirPath

    return coldDirPath.rstrip("/")


def getHotDirPathForEntry(hass: HomeAssistant, entry_id: str):
    if hass.data[DOMAIN][entry_id]["mediaSyncHotDir"] is not False:
        return hass.data[DOMAIN][entry_id]["mediaSyncHotDir"].rstrip("/")

    hotDirPath = os.path.join(getDataPath(), f"www/{DOMAIN}/{entry_id}/")

    if entry_id in hass.data[DOMAIN]:
        if hass.data[DOMAIN][entry_id]["mediaSyncHotDir"] is False:
            pathlib.Path(hotDirPath + "/videos").mkdir(parents=True, exist_ok=True)
            pathlib.Path(hotDirPath + "/thumbs").mkdir(parents=True, exist_ok=True)
            hass.data[DOMAIN][entry_id]["mediaSyncHotDir"] = hotDirPath

        hotDirPath = hass.data[DOMAIN][entry_id]["mediaSyncHotDir"]
    return hotDirPath.rstrip("/")


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


def getEntryStorageFile(config_entry):
    return f"tapo_control_{config_entry.entry_id}"


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
        openHandler = await hass.async_add_executor_job(open, filePathThumb, "wb")
        with openHandler as binary_file:
            binary_file.write(image)
    return filePathThumb


# todo: findMedia needs to run periodically because of this function!!!
async def deleteFilesNoLongerPresentInCamera(hass, entry_id, extension, folder):
    if hass.data[DOMAIN][entry_id]["initialMediaScanDone"] is True:
        coldDirPath = getColdDirPathForEntry(hass, entry_id)
        if os.path.exists(coldDirPath + "/" + folder + "/"):
            listDirFiles = await hass.async_add_executor_job(
                os.listdir, coldDirPath + "/" + folder + "/"
            )
            for f in listDirFiles:
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
            listDirFiles = await hass.async_add_executor_job(
                os.listdir, coldDirPath + "/" + folder + "/"
            )
            for f in listDirFiles:
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
                    LOGGER.warning(
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
    hotDirPath = getHotDirPathForEntry(hass, entry_id)

    # clean cache files from old HA instance
    LOGGER.debug(
        "Removing cache files from old HA instances for entity " + entry_id + "..."
    )
    await deleteFilesNotIncluding(hass, hotDirPath + "/videos/", UUID)
    await deleteFilesNotIncluding(hass, hotDirPath + "/thumbs/", UUID)

    await deleteFilesNoLongerPresentInCamera(hass, entry_id, ".mp4", "videos")
    await deleteFilesNoLongerPresentInCamera(hass, entry_id, ".jpg", "thumbs")

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
    await deleteFilesOlderThan(hass, hotDirPath + "/videos/", HOT_DIR_DELETE_TIME)
    await deleteFilesOlderThan(hass, hotDirPath + "/thumbs/", HOT_DIR_DELETE_TIME)


async def deleteDir(hass, dirPath):
    if (
        os.path.exists(dirPath)
        and os.path.isdir(dirPath)
        and dirPath != "/"
        and "tapo_control/" in dirPath
    ):
        LOGGER.debug("Deleting folder " + dirPath + "...")
        await hass.async_add_executor_job(shutil.rmtree, dirPath)


async def deleteFilesOlderThan(hass: HomeAssistant, dirPath, deleteOlderThan):
    now = datetime.datetime.utcnow().timestamp()
    if os.path.exists(dirPath):

        listDirFiles = await hass.async_add_executor_job(os.listdir, dirPath)
        for f in listDirFiles:
            filePath = os.path.join(dirPath, f)
            last_modified = os.stat(filePath).st_mtime
            if now - last_modified > deleteOlderThan:
                LOGGER.debug("[deleteFilesOlderThan] Removing " + filePath + "...")
                os.remove(filePath)


async def deleteFilesNotIncluding(hass: HomeAssistant, dirPath, includingString):
    if os.path.exists(dirPath):
        listDirFiles = await hass.async_add_executor_job(os.listdir, dirPath)
        for f in listDirFiles:
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


async def getHotFile(
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
        await hass.async_add_executor_job(shutil.copyfile, coldFilePath, hotFilePath)
    return hotFilePath


async def getWebFile(
    hass: HomeAssistant, entry_id: str, startDate: int, endDate: int, folder: str
):
    hotFilePath = await getHotFile(hass, entry_id, startDate, endDate, folder)
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
                (
                    len(allRecordings)
                    if totalRecordingCount is False
                    else totalRecordingCount
                ),
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


def areCameraPortsOpened(host, controlPort=443):
    return isOpen(host, int(controlPort)) and isOpen(host, 554) and isOpen(host, 2020)


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


def result_has_error(result):
    if (
        result is not False
        and "result" in result
        and "responses" in result["result"]
        and any(
            map(
                lambda x: "error_code" not in x or x["error_code"] == 0,
                result["result"]["responses"],
            )
        )
    ):
        return False
    if result is not False and (
        "error_code" not in result or result["error_code"] == 0
    ):
        return False
    else:
        return True


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


def getDataForController(hass, entry, controller):
    for controller in hass.data[DOMAIN][entry.entry_id]["allControllers"]:
        if controller == hass.data[DOMAIN][entry.entry_id]["controller"]:
            return hass.data[DOMAIN][entry.entry_id]
        elif (
            "childDevices" in hass.data[DOMAIN][entry.entry_id]
            and hass.data[DOMAIN][entry.entry_id]["childDevices"] is not False
        ):
            for childDevice in hass.data[DOMAIN][entry.entry_id]["childDevices"]:
                if controller == childDevice["controller"]:
                    return childDevice


def getNightModeMap():
    return {
        "inf_night_vision": "Infrared Mode",
        "wtl_night_vision": "Full Color Mode",
        "md_night_vision": "Smart Mode",
        "dbl_night_vision": "Doorbell Mode",
        "shed_night_vision": "Scheduled Mode",
    }


def getNightModeName(value: str):
    nightModeMap = getNightModeMap()
    if value in nightModeMap:
        return nightModeMap[value]
    return value


def getNightModeValue(value: str):
    night_mode_map = getNightModeMap()
    for key, val in night_mode_map.items():
        if val == value:
            return key
    return value


def convertBasicInfo(basicInfo):
    convertedBasicInfo = basicInfo
    convertedBasicInfo["device_alias"] = base64.b64decode(basicInfo["nickname"]).decode(
        "utf-8"
    )
    convertedBasicInfo["device_model"] = basicInfo["model"]
    convertedBasicInfo["sw_version"] = basicInfo["fw_ver"]
    convertedBasicInfo["hw_version"] = basicInfo["hw_ver"]
    return convertedBasicInfo


def getIP(data):
    # KLAP report IP in this function
    if (
        "basic_info" in data
        and data["basic_info"] is not None
        and "ip" in data["basic_info"]
    ):
        return data["basic_info"]["ip"]
    # cameras report IP in this function
    elif (
        "network_ip_info" in data
        and data["network_ip_info"] is not None
        and "network" in data["network_ip_info"]
        and "wan" in data["network_ip_info"]["network"]
        and "ipaddr" in data["network_ip_info"]["network"]["wan"]
    ):
        return data["network_ip_info"]["network"]["wan"]["ipaddr"]
    return False


async def getCamData(hass, controller):
    LOGGER.debug("getCamData")
    data = await hass.async_add_executor_job(controller.getMost)
    LOGGER.debug("Raw update data:")
    LOGGER.debug(data)
    camData = {}

    camData["raw"] = data

    camData["user"] = controller.user
    if controller.isKLAP:
        camData["basic_info"] = convertBasicInfo(data["get_device_info"][0])
    else:
        camData["basic_info"] = data["getDeviceInfo"][0]["device_info"]["basic_info"]

    try:
        motionDetectionData = data["getDetectionConfig"][0]["motion_detection"][
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
    camData["motion_detection_digital_sensitivity"] = (
        motion_detection_digital_sensitivity
    )

    try:
        dst_data = data["getDstRule"][0]["system"]["dst"]
    except Exception:
        dst_data = None
    camData["dst_data"] = dst_data

    try:
        clock_data = data["getClockStatus"][0]["system"]["clock_status"]
    except Exception:
        clock_data = None
    camData["clock_data"] = clock_data

    try:
        timezone_timezone = data["getTimezone"][0]["system"]["basic"]["timezone"]
    except Exception:
        timezone_timezone = None
    camData["timezone_timezone"] = timezone_timezone

    try:
        alert_event_types = data["getAlertEventType"][0]["msg_alarm"]["msg_alarm_type"]
    except Exception:
        alert_event_types = None
    camData["alert_event_types"] = alert_event_types

    try:
        timezone_zone_id = data["getTimezone"][0]["system"]["basic"]["zone_id"]
    except Exception:
        timezone_zone_id = None
    camData["timezone_zone_id"] = timezone_zone_id

    try:
        timezone_timing_mode = data["getTimezone"][0]["system"]["basic"]["timing_mode"]
    except Exception:
        timezone_timing_mode = None
    camData["timezone_timing_mode"] = timezone_timing_mode

    try:
        personDetectionData = data["getPersonDetectionConfig"][0]["people_detection"][
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
        vehicleDetectionData = data["getVehicleDetectionConfig"][0][
            "vehicle_detection"
        ]["detection"]
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
        babyCryDetectionData = data["getBCDConfig"][0]["sound_detection"]["bcd"]
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
        petDetectionData = data["getPetDetectionConfig"][0]["pet_detection"][
            "detection"
        ]
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
        barkDetectionData = data["getBarkDetectionConfig"][0]["bark_detection"][
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
        meowDetectionData = data["getMeowDetectionConfig"][0]["meow_detection"][
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
        glassDetectionData = data["getGlassDetectionConfig"][0]["glass_detection"][
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
        tamperDetectionData = data["getTamperDetectionConfig"][0]["tamper_detection"][
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
            id: data["getPresetConfig"][0]["preset"]["preset"]["name"][key]
            for key, id in enumerate(
                data["getPresetConfig"][0]["preset"]["preset"]["id"]
            )
        }
    except Exception:
        presets = False

    try:
        privacy_mode = data["getLensMaskConfig"][0]["lens_mask"]["lens_mask_info"][
            "enabled"
        ]
    except Exception:
        privacy_mode = None
    camData["privacy_mode"] = privacy_mode

    try:
        notifications = data["getMsgPushConfig"][0]["msg_push"]["chn1_msg_push_info"][
            "notification_enabled"
        ]
    except Exception:
        notifications = None
    camData["notifications"] = notifications

    try:
        rich_notifications = data["getMsgPushConfig"][0]["msg_push"][
            "chn1_msg_push_info"
        ]["rich_notification_enabled"]
    except Exception:
        rich_notifications = None
    camData["rich_notifications"] = rich_notifications

    try:
        lens_distrotion_correction = data["getLdc"][0]["image"]["switch"]["ldc"]
    except Exception:
        lens_distrotion_correction = None
    camData["lens_distrotion_correction"] = lens_distrotion_correction

    try:
        ldcStyle = data["getLdc"][0]["image"]["common"]["style"]
    except Exception:
        ldcStyle = None
    camData["ldcStyle"] = ldcStyle

    try:
        light_frequency_mode = data["getLdc"][0]["image"]["common"]["light_freq_mode"]
    except Exception:
        light_frequency_mode = None

    if light_frequency_mode is None:
        try:
            light_frequency_mode = data["getLightFrequencyInfo"][0]["image"]["common"][
                "light_freq_mode"
            ]
        except Exception:
            light_frequency_mode = None
    camData["light_frequency_mode"] = light_frequency_mode

    try:
        night_vision_mode = data["getNightVisionModeConfig"][0]["image"]["switch"][
            "night_vision_mode"
        ]
    except Exception:
        night_vision_mode = None
    camData["night_vision_mode"] = night_vision_mode

    try:
        diagnose_mode = data["getDiagnoseMode"][0]["system"]["sys"]
    except Exception:
        diagnose_mode = None
    camData["diagnose_mode"] = diagnose_mode

    try:
        cover_config = data["getCoverConfig"][0]["cover"]["cover"]
    except Exception:
        cover_config = None
    camData["cover_config"] = cover_config

    try:
        smart_track_config = data["getSmartTrackConfig"][0]["smart_track"][
            "smart_track_info"
        ]
    except Exception:
        smart_track_config = None
    camData["smart_track_config"] = smart_track_config

    try:
        network_ip_info = data["getDeviceIpAddress"][0]
    except Exception:
        network_ip_info = None
    camData["network_ip_info"] = network_ip_info

    try:
        night_vision_capability = data["getNightVisionCapability"][0][
            "image_capability"
        ]["supplement_lamp"]["night_vision_mode_range"]
    except Exception:
        night_vision_capability = None
    camData["night_vision_capability"] = night_vision_capability

    try:
        night_vision_mode_switching = data["getLdc"][0]["image"]["common"]["inf_type"]
    except Exception:
        night_vision_mode_switching = None
    camData["night_vision_mode_switching"] = night_vision_mode_switching

    if night_vision_mode_switching is None:
        try:
            night_vision_mode_switching = data["getLightFrequencyInfo"][0]["image"][
                "common"
            ]["inf_type"]
        except Exception:
            night_vision_mode_switching = None
        camData["night_vision_mode_switching"] = night_vision_mode_switching

    try:
        force_white_lamp_state = data["getLdc"][0]["image"]["switch"]["force_wtl_state"]
    except Exception:
        force_white_lamp_state = None
    camData["force_white_lamp_state"] = force_white_lamp_state

    try:
        smartwtl_digital_level = data["getLdc"][0]["image"]["common"][
            "smartwtl_digital_level"
        ]
    except Exception:
        smartwtl_digital_level = None
    camData["smartwtl_digital_level"] = smartwtl_digital_level

    try:
        flood_light_config = data["getFloodlightConfig"][0]["floodlight"]["config"]
    except Exception:
        flood_light_config = None
    camData["flood_light_config"] = flood_light_config

    try:
        flood_light_status = data["getFloodlightStatus"][0]["status"]
    except Exception:
        flood_light_status = None
    camData["flood_light_status"] = flood_light_status

    try:
        flood_light_capability = data["getFloodlightCapability"][0]["floodlight"][
            "capability"
        ]
    except Exception:
        flood_light_capability = None
    camData["flood_light_capability"] = flood_light_capability

    try:
        flip = (
            "on"
            if data["getLdc"][0]["image"]["switch"]["flip_type"] == "center"
            else "off"
        )
    except Exception:
        flip = None

    if flip is None:
        try:
            flip = (
                "on"
                if data["getRotationStatus"][0]["image"]["switch"]["flip_type"]
                == "center"
                else "off"
            )
        except Exception:
            flip = None
    camData["flip"] = flip

    hubSiren = False
    alarmConfig = None
    alarmStatus = False
    alarmSirenTypeList = []
    if controller.isKLAP is False:
        try:
            if data["getSirenConfig"][0] != False:
                hubSiren = True
                sirenData = data["getSirenConfig"][0]
                alarmConfig = {
                    "typeOfAlarm": "getSirenConfig",
                    "siren_type": sirenData["siren_type"],
                    "siren_volume": sirenData["volume"],
                    "siren_duration": sirenData["duration"],
                }
        except Exception as err:
            LOGGER.error(f"getSirenConfig unexpected error {err=}, {type(err)=}")

    if controller.isKLAP is False:
        try:
            if not hubSiren and data["getAlarmConfig"][0] != False:
                alarmData = data["getAlarmConfig"][0]
                alarmConfig = {
                    "typeOfAlarm": "getAlarmConfig",
                    "mode": alarmData["alarm_mode"],
                    "automatic": alarmData["enabled"],
                }
                if "light_type" in alarmData:
                    alarmConfig["light_type"] = alarmData["light_type"]
                if "siren_type" in alarmData:
                    alarmConfig["siren_type"] = alarmData["siren_type"]
                if "siren_duration" in alarmData:
                    alarmConfig["siren_duration"] = alarmData["siren_duration"]
                if "alarm_duration" in alarmData:
                    alarmConfig["alarm_duration"] = alarmData["alarm_duration"]
                if "siren_volume" in alarmData:
                    alarmConfig["siren_volume"] = alarmData["siren_volume"]
                if "alarm_volume" in alarmData:
                    alarmConfig["alarm_volume"] = alarmData["alarm_volume"]

        except Exception as err:
            LOGGER.error(f"getAlarmConfig unexpected error {err=}, {type(err)=}")

    if controller.isKLAP is False:
        try:
            if (
                alarmConfig is None
                and "msg_alarm" in data["getLastAlarmInfo"][0]
                and "chn1_msg_alarm_info" in data["getLastAlarmInfo"][0]["msg_alarm"]
                and data["getLastAlarmInfo"][0]["msg_alarm"]["chn1_msg_alarm_info"]
                is not False
            ):
                alarmData = data["getLastAlarmInfo"][0]["msg_alarm"][
                    "chn1_msg_alarm_info"
                ]
                alarmConfig = {
                    "typeOfAlarm": "getAlarm",
                    "mode": alarmData["alarm_mode"],
                    "automatic": alarmData["enabled"],
                }
                if "light_type" in alarmData:
                    alarmConfig["light_type"] = alarmData["light_type"]
                if "siren_type" in alarmData:
                    alarmConfig["siren_type"] = alarmData["siren_type"]
                if "alarm_type" in alarmData:
                    alarmConfig["siren_type"] = alarmData["alarm_type"]
                if "siren_duration" in alarmData:
                    alarmConfig["siren_duration"] = alarmData["siren_duration"]
                if "alarm_duration" in alarmData:
                    alarmConfig["alarm_duration"] = alarmData["alarm_duration"]
                if "siren_volume" in alarmData:
                    alarmConfig["siren_volume"] = alarmData["siren_volume"]
                if "alarm_volume" in alarmData:
                    alarmConfig["alarm_volume"] = alarmData["alarm_volume"]
        except Exception as err:
            LOGGER.error(f"getLastAlarmInfo unexpected error {err=}, {type(err)=}")

    if controller.isKLAP is False:
        try:
            if (
                data["getSirenStatus"][0] is not False
                and "status" in data["getSirenStatus"][0]
            ):
                alarmStatus = data["getSirenStatus"][0]["status"]
        except Exception as err:
            LOGGER.error(f"getSirenStatus unexpected error {err=}, {type(err)=}")

    if controller.isKLAP is False:
        if alarmConfig is not None:
            try:
                if (
                    data["getSirenTypeList"][0] is not False
                    and "siren_type_list" in data["getSirenTypeList"][0]
                ):
                    alarmSirenTypeList = data["getSirenTypeList"][0]["siren_type_list"]
            except Exception as err:
                LOGGER.error(f"getSirenTypeList unexpected error {err=}, {type(err)=}")

    if controller.isKLAP is False:
        if len(alarmSirenTypeList) == 0:
            try:
                if (
                    data["getAlertTypeList"][0] is not False
                    and "msg_alarm" in data["getAlertTypeList"][0]
                    and "alert_type" in data["getAlertTypeList"][0]["msg_alarm"]
                    and "alert_type_list"
                    in data["getAlertTypeList"][0]["msg_alarm"]["alert_type"]
                ):
                    alarmSirenTypeList = data["getAlertTypeList"][0]["msg_alarm"][
                        "alert_type"
                    ]["alert_type_list"]
            except Exception as err:
                LOGGER.error(f"getSirenTypeList unexpected error {err=}, {type(err)=}")

    if len(alarmSirenTypeList) == 0:
        # Some cameras have hardcoded 0 and 1 values (Siren, Tone)
        alarmSirenTypeList.append("Siren")
        alarmSirenTypeList.append("Tone")

    alarm_user_sounds = None
    try:
        for alertConfig in data["getAlertConfig"]:
            if (
                alertConfig is not False
                and "msg_alarm" in alertConfig
                and "usr_def_audio" in alertConfig["msg_alarm"]
                and (alarm_user_sounds is None or len(alarm_user_sounds) == 0)
            ):
                alarm_user_sounds = []
                for alarm_sound in alertConfig["msg_alarm"]["usr_def_audio"]:
                    first_key = next(iter(alarm_sound))
                    first_value = alarm_sound[first_key]
                    alarm_user_sounds.append(first_value)
    except Exception:
        alarm_user_sounds = None

    alarm_user_start_id = None
    try:
        for alertConfig in data["getAlertConfig"]:
            if (
                alertConfig is not False
                and "msg_alarm" in alertConfig
                and "capability" in alertConfig["msg_alarm"]
                and "usr_def_start_file_id" in alertConfig["msg_alarm"]["capability"]
                and alarm_user_start_id is None
            ):
                alarm_user_start_id = alertConfig["msg_alarm"]["capability"][
                    "usr_def_start_file_id"
                ]
    except Exception:
        alarm_user_start_id = None
    camData["alarm_user_start_id"] = alarm_user_start_id
    camData["alarm_user_sounds"] = alarm_user_sounds
    camData["alarm_config"] = alarmConfig
    camData["alarm_status"] = alarmStatus
    camData["alarm_is_hubSiren"] = hubSiren
    camData["alarm_siren_type_list"] = alarmSirenTypeList

    try:
        if (
            "image_capability" in data["getNightVisionCapability"][0]
            and "supplement_lamp"
            in data["getNightVisionCapability"][0]["image_capability"]
        ):
            nightVisionCapability = data["getNightVisionCapability"][0][
                "image_capability"
            ]["supplement_lamp"]
    except Exception:
        nightVisionCapability = None
    camData["nightVisionCapability"] = nightVisionCapability

    try:
        led = data["getLedStatus"][0]["led"]["config"]["enabled"]
    except Exception:
        led = None

    if led is None:
        led = "on" if data["get_device_info"][0]["led_off"] == 0 else "off"
    camData["led"] = led

    # todo rest
    try:
        auto_track = data["getTargetTrackConfig"][0]["target_track"][
            "target_track_info"
        ]["enabled"]
    except Exception:
        auto_track = None
    camData["auto_track"] = auto_track

    if presets:
        camData["presets"] = presets
    else:
        camData["presets"] = {}

    try:
        firmwareUpdateStatus = data["getFirmwareUpdateStatus"][0]["cloud_config"]
    except Exception:
        firmwareUpdateStatus = None
    camData["firmwareUpdateStatus"] = firmwareUpdateStatus

    try:
        childDevices = data["getChildDeviceList"][0]
    except Exception:
        childDevices = None
    camData["childDevices"] = childDevices

    try:
        whitelampConfigForceTime = data["getWhitelampConfig"][0]["image"]["switch"][
            "wtl_force_time"
        ]
    except Exception:
        whitelampConfigForceTime = None
    camData["whitelampConfigForceTime"] = whitelampConfigForceTime

    try:
        whitelampConfigIntensity = data["getWhitelampConfig"][0]["image"]["switch"][
            "wtl_intensity_level"
        ]
    except Exception:
        whitelampConfigIntensity = None
    camData["whitelampConfigIntensity"] = whitelampConfigIntensity

    try:
        whitelampStatus = data["getWhitelampStatus"][0]["status"]
    except Exception:
        whitelampStatus = None
    camData["whitelampStatus"] = whitelampStatus

    try:
        sdCardData = []
        for hdd in data["getSdCardStatus"][0]["harddisk_manage"]["hd_info"]:
            sdCardData.append(hdd["hd_info_1"])
    except Exception:
        sdCardData = []
    camData["sdCardData"] = sdCardData

    try:
        recordPlan = data["getRecordPlan"][0]["record_plan"]["chn1_channel"]
    except Exception:
        recordPlan = None
    camData["recordPlan"] = recordPlan

    try:
        microphoneVolume = data["getAudioConfig"][0]["audio_config"]["microphone"][
            "volume"
        ]
    except Exception:
        microphoneVolume = None
    camData["microphoneVolume"] = microphoneVolume

    try:
        microphoneMute = data["getAudioConfig"][0]["audio_config"]["microphone"]["mute"]
    except Exception:
        microphoneMute = None
    camData["microphoneMute"] = microphoneMute

    try:
        microphoneNoiseCancelling = data["getAudioConfig"][0]["audio_config"][
            "microphone"
        ]["noise_cancelling"]
    except Exception:
        microphoneNoiseCancelling = None
    camData["microphoneNoiseCancelling"] = microphoneNoiseCancelling

    try:
        speakerVolume = data["getAudioConfig"][0]["audio_config"]["speaker"]["volume"]
    except Exception:
        speakerVolume = None
    camData["speakerVolume"] = speakerVolume

    try:
        record_audio = (
            data["getAudioConfig"][0]["audio_config"]["record_audio"]["enabled"] == "on"
        )
    except Exception:
        record_audio = None
    camData["record_audio"] = record_audio

    try:
        autoUpgradeEnabled = data["getFirmwareAutoUpgradeConfig"][0]["auto_upgrade"][
            "common"
        ]["enabled"]
    except Exception:
        autoUpgradeEnabled = None
    camData["autoUpgradeEnabled"] = autoUpgradeEnabled

    try:
        connectionInformation = data["getConnectionType"][0]
    except Exception:
        connectionInformation = None

    if connectionInformation is None:
        connectionInformation = {}
        try:
            connectionInformation["ssid"] = base64.b64decode(
                data["get_device_info"][0]["ssid"]
            ).decode("utf-8")
        except Exception:
            pass
        try:
            connectionInformation["rssiValue"] = data["get_device_info"][0]["rssi"]

        except Exception:
            pass
    camData["connectionInformation"] = connectionInformation

    try:
        videoCapability = data["getVideoCapability"][0]
    except Exception:
        videoCapability = None
    camData["videoCapability"] = videoCapability

    try:
        videoQualities = data["getVideoQualities"][0]
    except Exception:
        videoQualities = None
    camData["videoQualities"] = videoQualities

    camData["updated"] = datetime.datetime.utcnow().timestamp()

    try:
        chimeAlarmConfigurations = {}
        count = 0
        for chimeAlarmConfiguration in data["get_chime_alarm_configure"]:
            chimeAlarmConfigurations[data["get_pair_list"][0]["mac_list"][count]] = (
                chimeAlarmConfiguration
            )
            count += 1
    except Exception:
        chimeAlarmConfigurations = None
    camData["chimeAlarmConfigurations"] = chimeAlarmConfigurations

    try:
        supportAlarmTypeList = data["get_support_alarm_type_list"][0]
    except Exception:
        supportAlarmTypeList = None
    camData["supportAlarmTypeList"] = supportAlarmTypeList

    try:
        if isinstance(data["getQuickRespList"], list):
            camData["quick_response"] = data["getQuickRespList"][0]["quick_response"][
                "quick_resp_audio"
            ]
        elif isinstance(data["getQuickRespList"], dict):
            camData["quick_response"] = data["getQuickRespList"]["quick_resp_audio"]
        else:
            LOGGER.warning("Quick response data is not in expected format")
    except Exception:
        camData["quick_response"] = None

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
    controlPort = entry.data.get(CONTROL_PORT)
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
                    registerController, host, controlPort, "admin", cloud_password
                )
            else:
                tapoController = await hass.async_add_executor_job(
                    registerController, host, controlPort, username, password
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
        LOGGER.debug(
            "Syncing time for "
            + hass.data[DOMAIN][entry_id]["name"]
            + ", timezone offset is "
            + str(hass.data[DOMAIN][entry_id]["timezoneOffset"])
            + "..."
        )
        isDST = dt_util.now().dst() != datetime.timedelta(0)

        timeSyncDST = int(hass.data[DOMAIN][entry_id][TIME_SYNC_DST])
        timeSyncNDST = int(hass.data[DOMAIN][entry_id][TIME_SYNC_NDST])

        LOGGER.debug("Is DST: " + str(isDST))
        LOGGER.debug("DST offset: " + str(timeSyncDST))
        LOGGER.debug("Non DST offset: " + str(timeSyncNDST))
        now = dt_util.utcnow()

        LOGGER.debug("UTC Home Assistant time: " + str(now))
        LOGGER.debug("Local Home Assistant time: " + str(dt_util.as_local(now)))

        adjustment_hours = timeSyncDST if isDST else timeSyncNDST
        adjusted_time = now + datetime.timedelta(hours=adjustment_hours)

        time_params = device_mgmt.create_type("SetSystemDateAndTime")
        time_params.DateTimeType = "Manual"
        time_params.DaylightSavings = isDST
        time_params.UTCDateTime = {
            "Date": {
                "Year": adjusted_time.year,
                "Month": adjusted_time.month,
                "Day": adjusted_time.day,
            },
            "Time": {
                "Hour": adjusted_time.hour,
                "Minute": adjusted_time.minute,
                "Second": adjusted_time.second,
            },
        }
        LOGGER.debug(
            "Sending time parameters to " + hass.data[DOMAIN][entry_id]["name"] + ":"
        )
        LOGGER.debug(time_params)
        await device_mgmt.SetSystemDateAndTime(time_params)
        LOGGER.debug(
            "Finished synchronizing time successfully. Setting last time sync to: "
            + str(now)
        )
        hass.data[DOMAIN][entry_id]["lastTimeSync"] = now.timestamp()
    else:
        LOGGER.warning(
            "Onvif has not been initialized yet, unable to synchronize time."
        )


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
    if (
        hass.data[DOMAIN][config_entry.entry_id]["events"] is not False
        and not hass.data[DOMAIN][config_entry.entry_id]["events"].started
    ):
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
    elif pytapoFunctionName == "getLightFrequencyMode":
        return ["getLightFrequencyInfo", "getLightFrequencyCapability"]
    elif pytapoFunctionName == "getChildDevices":
        return ["getChildDeviceList"]
    elif pytapoFunctionName == "getForceWhitelampState":
        return ["getLdc"]
    elif pytapoFunctionName == "getDayNightMode":
        return ["getLightFrequencyInfo", "getNightVisionModeConfig"]
    elif pytapoFunctionName == "getImageFlipVertical":
        return ["getRotationStatus", "getLdc"]
    elif pytapoFunctionName == "getLensDistortionCorrection":
        return ["getLdc"]
    return [pytapoFunctionName]


def isCacheSupported(check_function, rawData):
    rawFunctions = pytapoFunctionMap(check_function)
    for function in rawFunctions:
        if function in rawData:
            if rawData[function][0]:
                if check_function == "getForceWhitelampState":
                    return (
                        "image" in rawData["getLdc"][0]
                        and "switch" in rawData["getLdc"][0]["image"]
                        and "force_wtl_state" in rawData["getLdc"][0]["image"]["switch"]
                    )
                elif check_function == "getDayNightMode":
                    return (
                        "image" in rawData["getLightFrequencyInfo"][0]
                        and "common" in rawData["getLightFrequencyInfo"][0]["image"]
                        and "inf_type"
                        in rawData["getLightFrequencyInfo"][0]["image"]["common"]
                    )
                elif check_function == "getImageFlipVertical":
                    return (
                        "image" in rawData["getLdc"][0]
                        and "switch" in rawData["getLdc"][0]["image"]
                        and "flip_type" in rawData["getLdc"][0]["image"]["switch"]
                    ) or (
                        "image" in rawData["getRotationStatus"][0]
                        and "switch" in rawData["getRotationStatus"][0]["image"]
                        and "flip_type"
                        in rawData["getRotationStatus"][0]["image"]["switch"]
                    )
                elif check_function == "getLensDistortionCorrection":
                    return (
                        "image" in rawData["getLdc"][0]
                        and "switch" in rawData["getLdc"][0]["image"]
                        and "ldc" in rawData["getLdc"][0]["image"]["switch"]
                    )
                return True
            else:
                raise Exception(
                    f"Capability {check_function} (mapped to:{function}) cached but not supported."
                )
    return False


async def check_and_create(entry, hass, cls, check_function, config_entry):
    try:
        if isCacheSupported(check_function, entry["camData"]["raw"]):
            LOGGER.debug(
                f"Found cached capability {check_function}, creating {cls.__name__}"
            )
            return cls(entry, hass, config_entry)
        else:
            if (
                entry["controller"].isKLAP is False
            ):  # no uncached entries for klap devices, so no need to check them
                LOGGER.debug(
                    f"Capability {check_function} not found, querying again..."
                )
                result = await hass.async_add_executor_job(
                    getattr(entry["controller"], check_function)
                )
                LOGGER.debug(result)
                LOGGER.debug(f"Creating {cls.__name__}")
                return cls(entry, hass, config_entry)
    except Exception as err:
        LOGGER.info(f"Camera does not support {cls.__name__}: {err}")
        return None
