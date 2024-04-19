import datetime
import hashlib
import logging
import asyncio

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    ConfigEntryAuthFailed,
    DependencyError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt
from homeassistant.components.media_source.error import Unresolvable
import homeassistant.helpers.entity_registry

from .const import (
    CONF_RTSP_TRANSPORT,
    ENABLE_MEDIA_SYNC,
    ENABLE_SOUND_DETECTION,
    CONF_CUSTOM_STREAM,
    ENABLE_WEBHOOKS,
    LOGGER,
    DOMAIN,
    ENABLE_MOTION_SENSOR,
    CLOUD_PASSWORD,
    ENABLE_STREAM,
    ENABLE_TIME_SYNC,
    MEDIA_CLEANUP_PERIOD,
    MEDIA_SYNC_COLD_STORAGE_PATH,
    MEDIA_SYNC_HOURS,
    MEDIA_VIEW_DAYS_ORDER,
    MEDIA_VIEW_RECORDINGS_ORDER,
    RTSP_TRANS_PROTOCOLS,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    TIME_SYNC_PERIOD,
    UPDATE_CHECK_PERIOD,
    PYTAPO_REQUIRED_VERSION,
)
from .utils import (
    convert_to_timestamp,
    deleteDir,
    getColdDirPathForEntry,
    getHotDirPathForEntry,
    isUsingHTTPS,
    mediaCleanup,
    registerController,
    getCamData,
    setupOnvif,
    setupEvents,
    update_listener,
    initOnvifEvents,
    syncTime,
    getLatestFirmwareVersion,
    findMedia,
    getRecordings,
)
from pytapo import Tapo
from pytapo.version import PYTAPO_VERSION

from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .utils import getRecording


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tapo: Cameras Control component from YAML."""
    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        new[ENABLE_MOTION_SENSOR] = True
        new[CLOUD_PASSWORD] = ""

        config_entry.data = {**new}

        config_entry.version = 2

    if config_entry.version == 2:
        new = {**config_entry.data}
        new[CLOUD_PASSWORD] = ""

        config_entry.data = {**new}

        config_entry.version = 3

    if config_entry.version == 3:
        new = {**config_entry.data}
        new[ENABLE_STREAM] = True

        config_entry.data = {**new}

        config_entry.version = 4

    if config_entry.version == 4:
        new = {**config_entry.data}
        new[ENABLE_TIME_SYNC] = False

        config_entry.data = {**new}

        config_entry.version = 5

    if config_entry.version == 5:
        new = {**config_entry.data}
        new[ENABLE_SOUND_DETECTION] = False
        new[SOUND_DETECTION_PEAK] = -30
        new[SOUND_DETECTION_DURATION] = 1
        new[SOUND_DETECTION_RESET] = 10

        config_entry.data = {**new}

        config_entry.version = 6

    if config_entry.version == 6:
        new = {**config_entry.data}
        new[CONF_EXTRA_ARGUMENTS] = ""

        config_entry.data = {**new}

        config_entry.version = 7

    if config_entry.version == 7:
        new = {**config_entry.data}
        new[CONF_CUSTOM_STREAM] = ""

        config_entry.data = {**new}

        config_entry.version = 8

    if config_entry.version == 8:
        new = {**config_entry.data}
        new[CONF_RTSP_TRANSPORT] = RTSP_TRANS_PROTOCOLS[0]

        config_entry.data = {**new}

        config_entry.version = 9

    if config_entry.version == 9:
        new = {**config_entry.data}
        new[ENABLE_WEBHOOKS] = True

        config_entry.data = {**new}

        config_entry.version = 10

    if config_entry.version == 10:
        new = {**config_entry.data}
        new[ENABLE_MEDIA_SYNC] = False

        config_entry.data = {**new}

        config_entry.version = 11

    if config_entry.version == 11:
        new = {**config_entry.data}
        new[MEDIA_SYNC_HOURS] = ""

        config_entry.data = {**new}

        config_entry.version = 12

    if config_entry.version == 12:
        new = {**config_entry.data}
        new[MEDIA_SYNC_COLD_STORAGE_PATH] = ""

        config_entry.data = {**new}

        config_entry.version = 13

    if config_entry.version == 13:
        new = {**config_entry.data}
        new[MEDIA_VIEW_DAYS_ORDER] = "Ascending"
        new[MEDIA_VIEW_RECORDINGS_ORDER] = "Ascending"

        config_entry.data = {**new}

        config_entry.version = 14

    if config_entry.version == 14:
        host = config_entry.data.get(CONF_IP_ADDRESS)
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        cloud_password = config_entry.data.get(CLOUD_PASSWORD)

        try:
            if cloud_password != "":
                tapoController = await hass.async_add_executor_job(
                    registerController, host, "admin", cloud_password, cloud_password
                )
            else:
                tapoController = await hass.async_add_executor_job(
                    registerController, host, username, password
                )
            camData = await getCamData(hass, tapoController)
            macAddress = camData["basic_info"]["mac"].lower()

            @callback
            def update_unique_id(entity_entry):
                if (
                    macAddress not in entity_entry.unique_id
                    and macAddress.replace("-", "_") not in entity_entry.unique_id
                ):
                    return {
                        "new_unique_id": "{}-{}".format(
                            macAddress, entity_entry.unique_id
                        ).lower()
                    }

            await homeassistant.helpers.entity_registry.async_migrate_entries(
                hass, config_entry.entry_id, update_unique_id
            )
        except Exception as e:
            LOGGER.error(
                "Unable to connect to Tapo: Cameras Control controller: %s", str(e)
            )
            if "Invalid authentication data" in str(e):
                raise ConfigEntryAuthFailed(e)
            elif "Temporary Suspension:" in str(
                e
            ):  # keep retrying to authenticate eventually, or throw
                # ConfigEntryAuthFailed on invalid auth eventually
                raise ConfigEntryNotReady
            # Retry for anything else
            raise ConfigEntryNotReady

        config_entry.version = 15

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    LOGGER.debug("Unloading tapo_control...")
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "button")
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    await hass.config_entries.async_forward_entry_unload(entry, "light")
    await hass.config_entries.async_forward_entry_unload(entry, "number")
    await hass.config_entries.async_forward_entry_unload(entry, "select")
    await hass.config_entries.async_forward_entry_unload(entry, "siren")
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    await hass.config_entries.async_forward_entry_unload(entry, "update")

    if hass.data[DOMAIN][entry.entry_id]["events"]:
        LOGGER.debug("Stopping events...")
        try:
            async with asyncio.timeout(3):
                await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()
        except TimeoutError:
            LOGGER.warn("Timed out waiting for onvif connection to close, proceeding.")
        LOGGER.debug("Events stopped.")

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    LOGGER.debug("async_remove_entry")
    entry_id = entry.entry_id
    coldDirPath = getColdDirPathForEntry(hass, entry_id)
    hotDirPath = getHotDirPathForEntry(hass, entry_id)

    # Delete all media stored in cold storage for entity
    LOGGER.debug("Deleting cold storage files for entity " + entry_id + "...")
    deleteDir(coldDirPath)

    # Delete all media stored in hot storage for entity
    LOGGER.debug("Deleting hot storage files for entity " + entry_id + "...")
    deleteDir(hotDirPath)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if PYTAPO_REQUIRED_VERSION != PYTAPO_VERSION:
        raise DependencyError(
            [
                f"Incorrect pytapo version installed: {PYTAPO_VERSION}. Required: {PYTAPO_REQUIRED_VERSION}."
            ]
        )

    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    cloud_password = entry.data.get(CLOUD_PASSWORD)
    enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)

    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
        if "setup_retries" not in hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN][entry.entry_id]["setup_retries"] = 0

    if isUsingHTTPS(hass):
        LOGGER.warn(
            "Home Assistant is running on HTTPS or it was not able to detect base_url schema. Disabling webhooks."
        )

    try:
        if cloud_password != "":
            tapoController = await hass.async_add_executor_job(
                registerController, host, "admin", cloud_password, cloud_password
            )
        else:
            tapoController = await hass.async_add_executor_job(
                registerController, host, username, password
            )

        def getAllEntities(entry):
            # Gather all entities, including of children devices
            allEntities = entry["entities"].copy()
            for childDevice in entry["childDevices"]:
                allEntities.extend(childDevice["entities"])
            return allEntities

        async def async_update_data():
            LOGGER.debug("async_update_data - entry")
            tapoController = hass.data[DOMAIN][entry.entry_id]["controller"]
            host = entry.data.get(CONF_IP_ADDRESS)
            username = entry.data.get(CONF_USERNAME)
            password = entry.data.get(CONF_PASSWORD)
            motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
            enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)
            ts = datetime.datetime.utcnow().timestamp()

            # motion detection retries
            if motionSensor or enableTimeSync:
                LOGGER.debug("Motion sensor or time sync is enabled.")
                if (
                    not hass.data[DOMAIN][entry.entry_id]["isChild"]
                    and not hass.data[DOMAIN][entry.entry_id]["isParent"]
                ):
                    if (
                        not hass.data[DOMAIN][entry.entry_id]["eventsDevice"]
                        or not hass.data[DOMAIN][entry.entry_id]["onvifManagement"]
                    ):
                        # retry if connection to onvif failed
                        LOGGER.debug("Setting up subscription to motion sensor...")
                        onvifDevice = await initOnvifEvents(
                            hass, host, username, password
                        )
                        if onvifDevice:
                            LOGGER.debug(onvifDevice)
                            hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = (
                                onvifDevice["device"]
                            )
                            hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = (
                                onvifDevice["device_mgmt"]
                            )
                            if motionSensor:
                                await setupOnvif(hass, entry)
                    elif (
                        not hass.data[DOMAIN][entry.entry_id]["eventsSetup"]
                        and motionSensor
                    ):
                        LOGGER.debug(
                            "Setting up subcription to motion sensor events..."
                        )
                        # retry if subscription to events failed
                        try:
                            hass.data[DOMAIN][entry.entry_id]["eventsSetup"] = (
                                await setupEvents(hass, entry)
                            )
                        except AssertionError as e:
                            if str(e) != "PullPoint manager already started":
                                raise AssertionError(e)

                    else:
                        LOGGER.debug("Motion sensor: OK")
                else:
                    LOGGER.debug(
                        "Not updating motion sensor because device is child or parent."
                    )

                if (
                    hass.data[DOMAIN][entry.entry_id]["onvifManagement"]
                    and enableTimeSync
                ):
                    if (
                        ts - hass.data[DOMAIN][entry.entry_id]["lastTimeSync"]
                        > TIME_SYNC_PERIOD
                    ):
                        await syncTime(hass, entry.entry_id)
                ts = datetime.datetime.utcnow().timestamp()
                if (
                    ts - hass.data[DOMAIN][entry.entry_id]["lastFirmwareCheck"]
                    > UPDATE_CHECK_PERIOD
                ):
                    hass.data[DOMAIN][entry.entry_id]["latestFirmwareVersion"] = (
                        await getLatestFirmwareVersion(
                            hass,
                            entry,
                            hass.data[DOMAIN][entry.entry_id],
                            tapoController,
                        )
                    )
                    for childDevice in hass.data[DOMAIN][entry.entry_id][
                        "childDevices"
                    ]:
                        childDevice["latestFirmwareVersion"] = (
                            await getLatestFirmwareVersion(
                                hass,
                                entry,
                                hass.data[DOMAIN][entry.entry_id],
                                childDevice["controller"],
                            )
                        )

            # cameras state
            LOGGER.debug("async_update_data - before someEntityEnabled check")
            someEntityEnabled = False
            allEntities = getAllEntities(hass.data[DOMAIN][entry.entry_id])
            for entity in allEntities:
                LOGGER.debug(entity["entity"])
                if entity["entity"]._enabled:
                    LOGGER.debug("async_update_data - enabling someEntityEnabled check")
                    someEntityEnabled = True
                    break

            if (
                someEntityEnabled
                and hass.data[DOMAIN][entry.entry_id]["refreshEnabled"]
            ):
                # Update data for all controllers
                updateDataForAllControllers = {}
                for controller in hass.data[DOMAIN][entry.entry_id]["allControllers"]:
                    try:
                        updateDataForAllControllers[controller] = await getCamData(
                            hass, controller
                        )
                        hass.data[DOMAIN][entry.entry_id]["reauth_retries"] = 0
                    except Exception as e:
                        updateDataForAllControllers[controller] = False
                        if str(e) == "Invalid authentication data":
                            if hass.data[DOMAIN][entry.entry_id]["reauth_retries"] < 3:
                                hass.data[DOMAIN][entry.entry_id]["reauth_retries"] += 1
                                raise e
                            else:
                                hass.data[DOMAIN][entry.entry_id][
                                    "refreshEnabled"
                                ] = False
                                raise ConfigEntryAuthFailed(e)
                        LOGGER.error(e)

                hass.data[DOMAIN][entry.entry_id]["camData"] = (
                    updateDataForAllControllers[tapoController]
                )

                LOGGER.debug("Updating entities...")

                # Gather all entities, including of children devices
                allEntities = getAllEntities(hass.data[DOMAIN][entry.entry_id])

                for entity in allEntities:
                    if entity["entity"]._enabled:
                        LOGGER.debug("Updating entity...")
                        LOGGER.debug(entity["entity"])
                        entity["camData"] = updateDataForAllControllers[
                            entity["entry"]["controller"]
                        ]
                        entity["entity"].updateTapo(
                            updateDataForAllControllers[entity["entry"]["controller"]]
                        )
                        entity["entity"].async_schedule_update_ha_state(True)
                        # start noise detection
                        if (
                            not hass.data[DOMAIN][entry.entry_id]["noiseSensorStarted"]
                            and entity["entity"]._is_noise_sensor
                            and entity["entity"]._enable_sound_detection
                        ):
                            await entity["entity"].startNoiseDetection()

                if ("updateEntity" in hass.data[DOMAIN][entry.entry_id]) and hass.data[
                    DOMAIN
                ][entry.entry_id]["updateEntity"]._enabled:
                    hass.data[DOMAIN][entry.entry_id]["updateEntity"].updateTapo(
                        camData
                    )
                    hass.data[DOMAIN][entry.entry_id][
                        "updateEntity"
                    ].async_schedule_update_ha_state(True)

            if (
                ts - hass.data[DOMAIN][entry.entry_id]["lastMediaCleanup"]
                > MEDIA_CLEANUP_PERIOD
            ):
                await mediaCleanup(hass, entry)

            if (
                hass.is_running
                and hass.data[DOMAIN][entry.entry_id]["mediaSyncAvailable"]
            ):
                if (
                    hass.data[DOMAIN][entry.entry_id]["initialMediaScanDone"] is True
                    and hass.data[DOMAIN][entry.entry_id]["mediaSyncScheduled"] is False
                ):
                    hass.data[DOMAIN][entry.entry_id]["mediaSyncScheduled"] = True
                    async_track_time_interval(
                        hass,
                        mediaSync,
                        timedelta(seconds=60),
                    )
                elif (
                    hass.data[DOMAIN][entry.entry_id]["initialMediaScanRunning"]
                    is False
                ):
                    hass.data[DOMAIN][entry.entry_id]["initialMediaScanRunning"] = True
                    try:
                        await hass.async_add_executor_job(
                            tapoController.getRecordingsList
                        )
                        hass.async_create_background_task(
                            findMedia(hass, entry), "findMedia"
                        )
                    except Exception as err:
                        hass.data[DOMAIN][entry.entry_id]["initialMediaScanDone"] = True
                        hass.data[DOMAIN][entry.entry_id]["mediaSyncAvailable"] = False
                        enableMediaSync = entry.data.get(ENABLE_MEDIA_SYNC)
                        errMsg = "Disabling media sync as there was error returned from getRecordingsList. Do you have SD card inserted?"
                        if enableMediaSync:
                            LOGGER.warn(errMsg)
                            LOGGER.warn(err)
                        else:
                            LOGGER.info(errMsg)
                            LOGGER.info(err)

        tapoCoordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="Tapo resource status",
            update_method=async_update_data,
        )

        camData = await getCamData(hass, tapoController)
        cameraTime = await hass.async_add_executor_job(tapoController.getTime)
        cameraTS = cameraTime["system"]["clock_status"]["seconds_from_1970"]
        currentTS = dt.as_timestamp(dt.now())

        hass.data[DOMAIN][entry.entry_id] = {
            "setup_retries": 0,
            "reauth_retries": 0,
            "runningMediaSync": False,
            "controller": tapoController,
            "entry": entry,
            "usingCloudPassword": cloud_password != "",
            "allControllers": [tapoController],
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": tapoCoordinator,
            "camData": camData,
            "lastTimeSync": 0,
            "lastMediaCleanup": 0,
            "lastFirmwareCheck": 0,
            "latestFirmwareVersion": False,
            "mediaSyncColdDir": False,
            "mediaSyncHotDir": False,
            "motionSensorCreated": False,
            "eventsDevice": False,
            "onvifManagement": False,
            "eventsSetup": False,
            "events": False,
            "eventsListener": False,
            "entities": [],
            "noiseSensorStarted": False,
            "name": camData["basic_info"]["device_alias"],
            "childDevices": [],
            "isChild": False,
            "uuid": hashlib.md5(
                (
                    str(host) + str(username) + str(password) + str(cloud_password)
                ).encode()
            ).hexdigest(),
            "isParent": False,
            "isDownloadingStream": False,
            "downloadedStreams": {},  # keeps track of all videos downloaded
            "downloadProgress": False,
            "initialMediaScanDone": False,
            "mediaSyncScheduled": False,
            "mediaSyncAvailable": True,
            "initialMediaScanRunning": False,
            "mediaScanResult": {},  # keeps track of all videos currently on camera
            "timezoneOffset": cameraTS - currentTS,
            "refreshEnabled": True,
        }

        if camData["childDevices"] is False or camData["childDevices"] is None:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, "camera")
            )
        else:
            hass.data[DOMAIN][entry.entry_id]["isParent"] = True
            for childDevice in camData["childDevices"]["child_device_list"]:
                tapoChildController = await hass.async_add_executor_job(
                    registerController,
                    host,
                    "admin",
                    cloud_password,
                    cloud_password,
                    "",
                    childDevice["device_id"],
                )
                hass.data[DOMAIN][entry.entry_id]["allControllers"].append(
                    tapoChildController
                )
                childCamData = await getCamData(hass, tapoChildController)
                hass.data[DOMAIN][entry.entry_id]["childDevices"].append(
                    {
                        "controller": tapoChildController,
                        "coordinator": tapoCoordinator,
                        "camData": childCamData,
                        "lastTimeSync": 0,
                        "lastMediaCleanup": 0,
                        "lastFirmwareCheck": 0,
                        "latestFirmwareVersion": False,
                        "motionSensorCreated": False,
                        "entities": [],
                        "name": camData["basic_info"]["device_alias"],
                        "childDevices": [],
                        "isChild": True,
                        "isParent": False,
                    }
                )

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "button")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "light")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "number")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "select")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "siren")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "update")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )

        # Needs to execute AFTER binary_sensor creation!
        if camData["childDevices"] is None and (motionSensor or enableTimeSync):
            onvifDevice = await initOnvifEvents(hass, host, username, password)
            hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = onvifDevice["device"]
            hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = onvifDevice[
                "device_mgmt"
            ]
            if motionSensor:
                LOGGER.debug("Seting up motion sensor for the first time.")
                await setupOnvif(hass, entry)
            if enableTimeSync:
                await syncTime(hass, entry.entry_id)

        # Media sync

        timeCorrection = await hass.async_add_executor_job(
            tapoController.getTimeCorrection
        )

        # todo move to utils
        async def mediaSync(time=None):
            LOGGER.debug("mediaSync")
            enableMediaSync = entry.data.get(ENABLE_MEDIA_SYNC)
            mediaSyncHours = entry.data.get(MEDIA_SYNC_HOURS)

            if mediaSyncHours == "":
                mediaSyncTime = False
            else:
                mediaSyncTime = (int(mediaSyncHours) * 60 * 60) + timeCorrection
            if (
                enableMediaSync
                and entry.entry_id in hass.data[DOMAIN]
                and "controller" in hass.data[DOMAIN][entry.entry_id]
                and hass.data[DOMAIN][entry.entry_id]["runningMediaSync"] is False
                and hass.data[DOMAIN][entry.entry_id]["isDownloadingStream"]
                is False  # prevent breaking user manual upload
            ):
                hass.data[DOMAIN][entry.entry_id]["runningMediaSync"] = True
                try:
                    tapoController: Tapo = hass.data[DOMAIN][entry.entry_id][
                        "controller"
                    ]
                    LOGGER.debug("getRecordingsList -1")
                    recordingsList = await hass.async_add_executor_job(
                        tapoController.getRecordingsList
                    )
                    LOGGER.debug("getRecordingsList -2")

                    ts = datetime.datetime.utcnow().timestamp()
                    for searchResult in recordingsList:
                        for key in searchResult:
                            if (mediaSyncTime is False) or (
                                (
                                    mediaSyncTime is not False
                                    and (
                                        (int(ts) - (int(mediaSyncTime) + 86400))
                                        < convert_to_timestamp(
                                            searchResult[key]["date"]
                                        )
                                    )
                                )
                            ):
                                LOGGER.debug("getRecordings -1")
                                recordingsForDay = await getRecordings(
                                    hass, entry.entry_id, searchResult[key]["date"]
                                )
                                LOGGER.debug("getRecordings -2")
                                totalRecordingsToDownload = 0
                                for recording in recordingsForDay:
                                    for recordingKey in recording:
                                        if recording[recordingKey]["endTime"] > int(
                                            ts
                                        ) - (int(mediaSyncTime)):
                                            totalRecordingsToDownload += 1
                                recordingCount = 0
                                for recording in recordingsForDay:
                                    for recordingKey in recording:
                                        if recording[recordingKey]["endTime"] > (
                                            int(ts) - (int(mediaSyncTime))
                                        ):
                                            recordingCount += 1
                                            try:
                                                LOGGER.debug("getRecording -1")
                                                await getRecording(
                                                    hass,
                                                    tapoController,
                                                    entry.entry_id,
                                                    searchResult[key]["date"],
                                                    recording[recordingKey][
                                                        "startTime"
                                                    ],
                                                    recording[recordingKey]["endTime"],
                                                    recordingCount,
                                                    totalRecordingsToDownload,
                                                )
                                                LOGGER.debug("getRecording -2")
                                            except Unresolvable as err:
                                                LOGGER.warn(err)
                                            except Exception as err:
                                                LOGGER.error(err)
                except Exception as err:
                    LOGGER.error(err)
                LOGGER.debug("runningMediaSync -false")
                hass.data[DOMAIN][entry.entry_id]["runningMediaSync"] = False

        async def unsubscribe(event):
            if hass.data[DOMAIN][entry.entry_id]["events"]:
                await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsubscribe)

    except Exception as e:
        if "Invalid authentication data" in str(e):
            if hass.data[DOMAIN][entry.entry_id]["setup_retries"] < 3:
                hass.data[DOMAIN][entry.entry_id]["setup_retries"] += 1
                raise ConfigEntryNotReady(e)
            raise ConfigEntryAuthFailed(e)
        else:
            if "Temporary Suspension:" in str(
                e
            ):  # keep retrying to authenticate eventually, or throw
                # ConfigEntryAuthFailed on invalid auth eventually
                raise ConfigEntryNotReady(e)
            # Retry for anything else
            LOGGER.error(
                "Unable to connect to Tapo: Cameras Control controller: %s", str(e)
            )
            raise ConfigEntryNotReady(e)

    return True
