import datetime
import hashlib
import asyncio
from aiohttp import ClientError

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
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt
from homeassistant.components.media_source.error import Unresolvable
import homeassistant.helpers.entity_registry

from .const import (
    CONF_RTSP_TRANSPORT,
    CONTROL_PORT,
    ENABLE_MEDIA_SYNC,
    ENABLE_SOUND_DETECTION,
    CONF_CUSTOM_STREAM,
    ENABLE_WEBHOOKS,
    IS_KLAP_DEVICE,
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
    REPORTED_IP_ADDRESS,
    RTSP_TRANS_PROTOCOLS,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    TIME_SYNC_DST,
    TIME_SYNC_DST_DEFAULT,
    TIME_SYNC_NDST,
    TIME_SYNC_NDST_DEFAULT,
    TIME_SYNC_PERIOD,
    UPDATE_CHECK_PERIOD,
    PYTAPO_REQUIRED_VERSION,
    UPDATE_INTERVAL_BATTERY,
    UPDATE_INTERVAL_BATTERY_DEFAULT,
    UPDATE_INTERVAL_MAIN,
    UPDATE_INTERVAL_MAIN_DEFAULT,
)
from .utils import (
    convert_to_timestamp,
    deleteDir,
    getColdDirPathForEntry,
    getDataForController,
    getEntryStorageFile,
    getHotDirPathForEntry,
    getIP,
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
    scheduleAll,
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
                    registerController,
                    host,
                    443,
                    "admin",
                    cloud_password,
                    cloud_password,
                )
            else:
                tapoController = await hass.async_add_executor_job(
                    registerController, host, 443, username, password
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

    if config_entry.version == 15:
        new = {**config_entry.data}
        new[UPDATE_INTERVAL_MAIN] = UPDATE_INTERVAL_MAIN_DEFAULT
        new[UPDATE_INTERVAL_BATTERY] = UPDATE_INTERVAL_BATTERY_DEFAULT

        hass.config_entries.async_update_entry(config_entry, data=new, version=16)

    if config_entry.version == 16:
        new = {**config_entry.data}
        entry_storage = Store(hass, version=1, key=getEntryStorageFile(config_entry))

        if ENABLE_MEDIA_SYNC in new:
            await entry_storage.async_save({ENABLE_MEDIA_SYNC: new[ENABLE_MEDIA_SYNC]})
            del new[ENABLE_MEDIA_SYNC]
        else:
            await entry_storage.async_save({ENABLE_MEDIA_SYNC: False})

        hass.config_entries.async_update_entry(config_entry, data=new, version=17)

    if config_entry.version == 17:
        new = {**config_entry.data}
        new[CONTROL_PORT] = 443

        hass.config_entries.async_update_entry(config_entry, data=new, version=18)

    if config_entry.version == 18:
        new = {**config_entry.data}
        new[CONTROL_PORT] = int(new[CONTROL_PORT])

        hass.config_entries.async_update_entry(config_entry, data=new, version=19)

    if config_entry.version == 19:
        new = {**config_entry.data}
        new[IS_KLAP_DEVICE] = False

        hass.config_entries.async_update_entry(config_entry, data=new, version=20)

    if config_entry.version == 20:
        new = {**config_entry.data}
        try:
            host = config_entry.data.get(CONF_IP_ADDRESS)
            controlPort = config_entry.data.get(CONTROL_PORT)
            isKlapDevice = config_entry.data.get(IS_KLAP_DEVICE)
            cloud_password = config_entry.data.get(CLOUD_PASSWORD)
            username = config_entry.data.get(CONF_USERNAME)
            password = config_entry.data.get(CONF_PASSWORD)
            if cloud_password != "":
                LOGGER.debug("Setting up controller using cloud password.")
                tapoController = await hass.async_add_executor_job(
                    registerController,
                    host,
                    controlPort,
                    "admin",
                    cloud_password,
                    cloud_password,
                    "",
                    None,
                    isKlapDevice,
                    hass,
                )
            else:
                LOGGER.debug("Setting up controller using username and password.")
                tapoController = await hass.async_add_executor_job(
                    registerController,
                    host,
                    controlPort,
                    username,
                    password,
                    "",
                    "",
                    None,
                    isKlapDevice,
                    hass,
                )
            camData = await getCamData(hass, tapoController)
            reported_ip_address = getIP(camData)
            LOGGER.debug(f"Detected IP: {reported_ip_address}")
            new[REPORTED_IP_ADDRESS] = reported_ip_address

            hass.config_entries.async_update_entry(
                config_entry,
                data=new,
                version=21,
                unique_id=DOMAIN
                + (reported_ip_address if reported_ip_address else host),
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

    if config_entry.version == 21:
        new = {**config_entry.data}
        new[TIME_SYNC_DST] = TIME_SYNC_DST_DEFAULT
        new[TIME_SYNC_NDST] = TIME_SYNC_NDST_DEFAULT

        hass.config_entries.async_update_entry(config_entry, data=new, version=22)

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    LOGGER.debug("Unloading tapo_control...")
    await hass.config_entries.async_unload_platforms(
        entry,
        [
            "binary_sensor",
            "sensor",
            "button",
            "camera",
            "light",
            "number",
            "select",
            "siren",
            "switch",
            "update",
        ],
    )

    if hass.data[DOMAIN][entry.entry_id]["events"]:
        LOGGER.debug("Stopping events...")
        try:
            async with asyncio.timeout(3):
                await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()
        except (asyncio.TimeoutError, ClientError):
            LOGGER.warning(
                "Timed out waiting for onvif connection to close, proceeding."
            )
        LOGGER.debug("Events stopped.")

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    LOGGER.debug("async_remove_entry")
    entry_id = entry.entry_id
    coldDirPath = getColdDirPathForEntry(hass, entry_id)
    hotDirPath = getHotDirPathForEntry(hass, entry_id)

    entry_storage = Store(hass, version=1, key=getEntryStorageFile(entry))
    await entry_storage.async_remove()

    # Delete all media stored in cold storage for entity
    if coldDirPath:
        LOGGER.debug("Deleting cold storage files for entity " + entry_id + "...")
        await deleteDir(hass, coldDirPath)
    else:
        LOGGER.warning(
            "No cold storage path found for entity"
            + entry_id
            + ". Not deleting anything."
        )

    # Delete all media stored in hot storage for entity
    if hotDirPath:
        LOGGER.debug("Deleting hot storage files for entity " + entry_id + "...")
        await deleteDir(hass, hotDirPath)
    else:
        LOGGER.warning(
            "No hot storage path found for entity"
            + entry_id
            + ". Not deleting anything."
        )

    # Remove the entry data
    hass.data[DOMAIN].pop(entry_id, None)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if PYTAPO_REQUIRED_VERSION != PYTAPO_VERSION:
        raise DependencyError(
            [
                f"Incorrect pytapo version installed: {PYTAPO_VERSION}. Required: {PYTAPO_REQUIRED_VERSION}."
            ]
        )

    LOGGER.debug("Starting setup of Tapo: Cameras Control")

    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    controlPort = entry.data.get(CONTROL_PORT)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    isKlapDevice = entry.data.get(IS_KLAP_DEVICE)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)
    # Disable onvif related capabilities if rtsp data not provided
    if len(username) == 0 or len(password) == 0:
        motionSensor = False
        enableTimeSync = False
    cloud_password = entry.data.get(CLOUD_PASSWORD)
    updateIntervalMain = entry.data.get(UPDATE_INTERVAL_MAIN)
    updateIntervalBattery = entry.data.get(UPDATE_INTERVAL_BATTERY)
    timeSyncDST = entry.data.get(TIME_SYNC_DST)
    timeSyncNDST = entry.data.get(TIME_SYNC_NDST)

    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}
        if "setup_retries" not in hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN][entry.entry_id]["setup_retries"] = 0

    LOGGER.debug("Checking for HTTPS on HA")
    if isUsingHTTPS(hass):
        LOGGER.warning(
            "Home Assistant is running on HTTPS or it was not able to detect base_url schema. Disabling webhooks."
        )
    else:
        LOGGER.debug("HA is not using HTTPS.")

    try:
        LOGGER.debug(isKlapDevice)
        if cloud_password != "":
            LOGGER.debug("Setting up controller using cloud password.")
            tapoController = await hass.async_add_executor_job(
                registerController,
                host,
                controlPort,
                "admin",
                cloud_password,
                cloud_password,
                "",
                None,
                isKlapDevice,
                hass,
            )
        else:
            LOGGER.debug("Setting up controller using username and password.")
            tapoController = await hass.async_add_executor_job(
                registerController,
                host,
                controlPort,
                username,
                password,
                "",
                "",
                None,
                isKlapDevice,
                hass,
            )
        LOGGER.debug("Controller has been set up.")

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
            # Disable onvif related capabilities if rtsp data not provided
            if len(username) == 0 or len(password) == 0:
                motionSensor = False
                enableTimeSync = False
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
                            "Setting up subscription to motion sensor events..."
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
                        try:
                            await syncTime(hass, entry.entry_id)
                        except Exception as e:
                            LOGGER.error(
                                f"Failed to sync time for {host}: {e}",
                                exc_info=True,
                            )
                ts = datetime.datetime.utcnow().timestamp()
            else:
                debugMsg = "Both motion sensor and time sync are disabled."
                if len(username) == 0 or len(password) == 0:
                    debugMsg += " This is because RTSP username or password is empty."
                LOGGER.debug(debugMsg)
            if (
                ts - hass.data[DOMAIN][entry.entry_id]["lastFirmwareCheck"]
                > UPDATE_CHECK_PERIOD
            ):
                LOGGER.debug("Getting latest firmware...")
                hass.data[DOMAIN][entry.entry_id]["latestFirmwareVersion"] = (
                    await getLatestFirmwareVersion(
                        hass,
                        entry,
                        hass.data[DOMAIN][entry.entry_id],
                        tapoController,
                    )
                )
                LOGGER.debug(hass.data[DOMAIN][entry.entry_id]["latestFirmwareVersion"])
                for childDevice in hass.data[DOMAIN][entry.entry_id]["childDevices"]:
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
                    controllerData = getDataForController(hass, entry, controller)
                    LOGGER.debug(
                        f"{controllerData['name']} running on battery: {controllerData['isRunningOnBattery']}"
                    )
                    if (
                        controllerData["isRunningOnBattery"] is False
                        and ts - controllerData["lastUpdate"] > updateIntervalMain
                    ) or (
                        controllerData["isRunningOnBattery"] is True
                        and ts - controllerData["lastUpdate"] > updateIntervalBattery
                    ):
                        timeForAnUpdate = True
                        LOGGER.debug(f"Updating {controllerData['name']}...")
                    else:
                        timeForAnUpdate = False
                        LOGGER.debug(f"Skipping update for {controllerData['name']}...")
                    if timeForAnUpdate:
                        try:
                            updateDataForAllControllers[controller] = await getCamData(
                                hass, controller
                            )
                            controllerData["isRunningOnBattery"] = (
                                True
                                if (
                                    "basic_info"
                                    in updateDataForAllControllers[controller]
                                    and (
                                        (
                                            "power"
                                            in updateDataForAllControllers[controller][
                                                "basic_info"
                                            ]
                                            and (
                                                (
                                                    updateDataForAllControllers[
                                                        controller
                                                    ]["basic_info"]["power"]
                                                    == "BATTERY"
                                                )
                                                or (
                                                    updateDataForAllControllers[
                                                        controller
                                                    ]["basic_info"]["power"]
                                                    == "SOLAR"
                                                )
                                            )
                                        )
                                        or (
                                            "power_mode"
                                            in updateDataForAllControllers[controller][
                                                "basic_info"
                                            ]
                                            and (
                                                (
                                                    updateDataForAllControllers[
                                                        controller
                                                    ]["basic_info"]["power_mode"]
                                                    == "BATTERY"
                                                )
                                                or (
                                                    updateDataForAllControllers[
                                                        controller
                                                    ]["basic_info"]["power_mode"]
                                                    == "SOLAR"
                                                )
                                            )
                                        )
                                    )
                                )
                                else False
                            )
                            controllerData["lastUpdate"] = (
                                datetime.datetime.utcnow().timestamp()
                            )
                            controllerData["reauth_retries"] = 0
                        except Exception as e:
                            updateDataForAllControllers[controller] = False
                            if str(e) == "Invalid authentication data":
                                if controllerData["reauth_retries"] < 3:
                                    controllerData["reauth_retries"] += 1
                                    raise e
                                else:
                                    controllerData["refreshEnabled"] = False
                                    raise ConfigEntryAuthFailed(e)
                            LOGGER.error(e)

                if tapoController in updateDataForAllControllers:
                    hass.data[DOMAIN][entry.entry_id]["camData"] = (
                        updateDataForAllControllers[tapoController]
                    )

                    LOGGER.debug("Updating entities...")

                    # Gather all entities, including of children devices
                    allEntities = getAllEntities(hass.data[DOMAIN][entry.entry_id])

                    for entity in allEntities:
                        if (
                            entity["entity"]._enabled
                            and entity["entry"]["controller"]
                            in updateDataForAllControllers
                        ):
                            LOGGER.debug("Updating entity...")
                            LOGGER.debug(entity["entity"])
                            entity["camData"] = updateDataForAllControllers[
                                entity["entry"]["controller"]
                            ]
                            entity["entity"].updateTapo(
                                updateDataForAllControllers[
                                    entity["entry"]["controller"]
                                ]
                            )
                            entity["entity"].async_schedule_update_ha_state(True)
                            # start noise detection
                            if (
                                not hass.data[DOMAIN][entry.entry_id][
                                    "noiseSensorStarted"
                                ]
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
                LOGGER.debug(
                    "Initiating media cleanup for "
                    + hass.data[DOMAIN][entry.entry_id]["name"]
                    + "..."
                )
                await mediaCleanup(hass, entry, hass.data[DOMAIN][entry.entry_id])
            if hass.data[DOMAIN][entry.entry_id]["isParent"]:
                for child in hass.data[DOMAIN][entry.entry_id]["childDevices"]:
                    if ts - child["lastMediaCleanup"] > MEDIA_CLEANUP_PERIOD:
                        LOGGER.debug(
                            "Initiating media cleanup for " + child["name"] + "..."
                        )
                        await mediaCleanup(hass, entry, child)

            if hass.is_running:
                await scheduleAll(
                    hass, hass.data[DOMAIN][entry.entry_id], entry, mediaSync
                )
                if hass.data[DOMAIN][entry.entry_id]["isParent"]:
                    for child in hass.data[DOMAIN][entry.entry_id]["childDevices"]:
                        await scheduleAll(hass, child, entry, mediaSync)

        LOGGER.debug("Setting up data update coordinator.")

        tapoCoordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="Tapo resource status",
            update_method=async_update_data,
        )

        LOGGER.debug("Retrieving initial device data.")

        camData = await getCamData(hass, tapoController)
        LOGGER.debug("Retrieved initial device data.")
        LOGGER.debug("Retrieving camera time.")
        cameraTime = await hass.async_add_executor_job(tapoController.getTime)
        if not tapoController.isKLAP:
            cameraTS = cameraTime["system"]["clock_status"]["seconds_from_1970"]
        else:
            cameraTS = cameraTime["timestamp"]
        LOGGER.debug("Retrieved camera time.")
        currentTS = dt.as_timestamp(dt.now())
        timezoneOffset = cameraTS - currentTS

        LOGGER.debug(f"Timezone offset is {timezoneOffset}.")

        LOGGER.debug("Setting up entry data.")
        hass.data[DOMAIN][entry.entry_id] = {
            "setup_retries": 0,
            "reauth_retries": 0,
            "runningMediaSync": False,
            TIME_SYNC_DST: timeSyncDST,
            TIME_SYNC_NDST: timeSyncNDST,
            "controller": tapoController,
            "entry": entry,
            "usingCloudPassword": cloud_password != "",
            "allControllers": [tapoController],
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": tapoCoordinator,
            "camData": camData,
            "lastTimeSync": 0,
            "lastMediaCleanup": 0,
            "lastUpdate": 0,
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
            "isRunningOnBattery": (
                True
                if (
                    "basic_info" in camData
                    and "power" in camData["basic_info"]
                    and camData["basic_info"]["power"] == "BATTERY"
                )
                else False
            ),
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
            ENABLE_MEDIA_SYNC: None,
            "mediaSyncScheduled": False,
            "mediaSyncRanOnce": False,
            "mediaSyncAvailable": True,
            "initialMediaScanRunning": False,
            "mediaScanResult": {},  # keeps track of all videos currently on camera
            "timezoneOffset": timezoneOffset,
            "refreshEnabled": True,
        }
        LOGGER.debug("Entry data has been set up.")

        if tapoController.isKLAP is False:
            LOGGER.debug("Controller is not KLAP device.")
            if not (
                camData["childDevices"] is False or camData["childDevices"] is None
            ):
                LOGGER.debug("Device is a parent.")
                hass.data[DOMAIN][entry.entry_id]["isParent"] = True
                for childDevice in camData["childDevices"]["child_device_list"]:
                    LOGGER.debug("Setting up child controller.")
                    tapoChildController = await hass.async_add_executor_job(
                        registerController,
                        host,
                        controlPort,
                        "admin",
                        cloud_password,
                        cloud_password,
                        "",
                        childDevice["device_id"],
                    )
                    LOGGER.debug("Child controller set up.")
                    hass.data[DOMAIN][entry.entry_id]["allControllers"].append(
                        tapoChildController
                    )
                    LOGGER.debug("Getting initial child device data.")
                    childCamData = await getCamData(hass, tapoChildController)
                    LOGGER.debug("Retrieved initial child device data.")
                    hass.data[DOMAIN][entry.entry_id]["childDevices"].append(
                        {
                            "controller": tapoChildController,
                            "coordinator": tapoCoordinator,
                            "entry": entry,
                            "usingCloudPassword": cloud_password != "",
                            "timezoneOffset": hass.data[DOMAIN][entry.entry_id][
                                "timezoneOffset"
                            ],
                            "camData": childCamData,
                            "lastTimeSync": 0,
                            "lastMediaCleanup": 0,
                            "lastUpdate": 0,
                            "lastFirmwareCheck": 0,
                            "latestFirmwareVersion": False,
                            "motionSensorCreated": False,
                            "isDownloadingStream": False,
                            "downloadedStreams": {},  # keeps track of all videos downloaded
                            "downloadProgress": False,
                            "initialMediaScanDone": False,
                            ENABLE_MEDIA_SYNC: None,
                            "mediaSyncScheduled": False,
                            "mediaSyncRanOnce": False,
                            "mediaSyncAvailable": True,
                            "initialMediaScanRunning": False,
                            "runningMediaSync": False,
                            "mediaScanResult": {},  # keeps track of all videos currently on camera
                            "entities": [],
                            "name": childCamData["basic_info"]["device_alias"],
                            "childDevices": [],
                            "isChild": True,
                            "isRunningOnBattery": (
                                True
                                if (
                                    "basic_info" in childCamData
                                    and "power" in childCamData["basic_info"]
                                    and childCamData["basic_info"]["power"] == "BATTERY"
                                )
                                else False
                            ),
                            "isParent": False,
                        }
                    )
            LOGGER.debug("Setting up camera entities.")
            await hass.async_create_task(
                hass.config_entries.async_forward_entry_setups(entry, ["camera"])
            )

        LOGGER.debug("Setting up entities.")
        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(
                entry,
                [
                    "switch",
                    "button",
                    "light",
                    "number",
                    "select",
                    "siren",
                    "update",
                    "binary_sensor",
                    "sensor",
                ],
            )
        )
        LOGGER.debug("Entities set up.")

        # Needs to execute AFTER binary_sensor creation!
        if (
            tapoController.isKLAP is False
            and camData["childDevices"] is None
            and (motionSensor or enableTimeSync)
        ):
            onvifDevice = await initOnvifEvents(hass, host, username, password)
            hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = onvifDevice["device"]
            hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = onvifDevice[
                "device_mgmt"
            ]
            if motionSensor:
                LOGGER.debug("Setting up motion sensor for the first time.")
                await setupOnvif(hass, entry)
            else:
                debugMsg = "Motion sensor is disabled."
                if len(username) == 0 or len(password) == 0:
                    debugMsg += " This is because RTSP username or password is empty."
                LOGGER.debug(debugMsg)
            if enableTimeSync:
                try:
                    await syncTime(hass, entry.entry_id)
                except Exception as e:
                    LOGGER.error(
                        f"Failed to sync time for {host}: {e}",
                        exc_info=True,
                    )

        # Media sync
        timeCorrection = await hass.async_add_executor_job(
            tapoController.getTimeCorrection
        )

        # todo move to utils
        async def mediaSync(now, entry, device):
            LOGGER.debug("mediaSync")
            device["mediaSyncRanOnce"] = True
            enableMediaSync = device[ENABLE_MEDIA_SYNC]
            mediaSyncHours = entry.data.get(MEDIA_SYNC_HOURS)
            LOGGER.debug("mediaSync - 2")

            if mediaSyncHours == "":
                mediaSyncTime = False
            else:
                mediaSyncTime = (int(mediaSyncHours) * 60 * 60) + timeCorrection
            LOGGER.debug("mediaSync - 3")
            if (
                enableMediaSync
                and entry.entry_id in hass.data[DOMAIN]
                and "controller" in device
                and device["runningMediaSync"] is False
                and device["isDownloadingStream"]
                is False  # prevent breaking user manual upload
            ):
                LOGGER.debug("Running media sync for " + device["name"] + "...")
                device["runningMediaSync"] = True
                try:
                    tapoController: Tapo = device["controller"]
                    LOGGER.debug("getRecordingsList -1")
                    recordingsList = await hass.async_add_executor_job(
                        tapoController.getRecordingsList
                    )
                    LOGGER.debug("getRecordingsList -2")

                    ts = datetime.datetime.utcnow().timestamp()
                    for searchResult in recordingsList:
                        for key in searchResult:
                            LOGGER.debug("inside for - 1")
                            enableMediaSync = device[ENABLE_MEDIA_SYNC]
                            LOGGER.debug("inside for - 2")
                            if enableMediaSync and (
                                (mediaSyncTime is False)
                                or (
                                    (
                                        mediaSyncTime is not False
                                        and (
                                            (int(ts) - (int(mediaSyncTime) + 86400))
                                            < convert_to_timestamp(
                                                searchResult[key]["date"]
                                            )
                                        )
                                    )
                                )
                            ):
                                LOGGER.debug("getRecordings -1")
                                recordingsForDay = await getRecordings(
                                    hass,
                                    device,
                                    tapoController,
                                    searchResult[key]["date"],
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
                                                enableMediaSync = device[
                                                    ENABLE_MEDIA_SYNC
                                                ]
                                                if enableMediaSync:
                                                    LOGGER.debug("getRecording -1")
                                                    await getRecording(
                                                        hass,
                                                        tapoController,
                                                        entry.entry_id,
                                                        device,
                                                        searchResult[key]["date"],
                                                        recording[recordingKey][
                                                            "startTime"
                                                        ],
                                                        recording[recordingKey][
                                                            "endTime"
                                                        ],
                                                        recordingCount,
                                                        totalRecordingsToDownload,
                                                    )
                                                    LOGGER.debug("getRecording -2")
                                                else:
                                                    LOGGER.debug(
                                                        f"Media sync disabled (inside getRecording): {enableMediaSync}"
                                                    )
                                            except Unresolvable as err:
                                                if (
                                                    str(err)
                                                    == "Recording is currently in progress."
                                                ):
                                                    LOGGER.info(err)
                                                else:
                                                    LOGGER.warning(err)
                                            except Exception as err:
                                                device["runningMediaSync"] = False
                                                LOGGER.error(err)
                            else:
                                LOGGER.debug(
                                    f"Media sync ignoring {searchResult[key]["date"]}. Media sync: {enableMediaSync}."
                                )
                except Exception as err:
                    LOGGER.error(err)
                LOGGER.debug("runningMediaSync -false")
                device["runningMediaSync"] = False
            else:
                LOGGER.debug(
                    f"Media sync for {device["name"]} disabled (inside mediaSync): {enableMediaSync}"
                )

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
