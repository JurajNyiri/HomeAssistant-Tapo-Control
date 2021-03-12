import datetime
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    ENABLE_SOUND_DETECTION,
    LOGGER,
    DOMAIN,
    ENABLE_MOTION_SENSOR,
    CLOUD_PASSWORD,
    ENABLE_STREAM,
    ENABLE_TIME_SYNC,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    TIME_SYNC_PERIOD,
)
from .utils import (
    registerController,
    getCamData,
    setupOnvif,
    setupEvents,
    update_listener,
    initOnvifEvents,
    syncTime,
)


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
        new[SOUND_DETECTION_PEAK] = -50
        new[SOUND_DETECTION_DURATION] = 1
        new[SOUND_DETECTION_RESET] = 10

        config_entry.data = {**new}

        config_entry.version = 6

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    if hass.data[DOMAIN][entry.entry_id]["events"]:
        await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    cloud_password = entry.data.get(CLOUD_PASSWORD)
    enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)

    try:
        if cloud_password != "":
            tapoController = await hass.async_add_executor_job(
                registerController, host, "admin", cloud_password
            )
        else:
            tapoController = await hass.async_add_executor_job(
                registerController, host, username, password
            )

        async def async_update_data():
            host = entry.data.get(CONF_IP_ADDRESS)
            username = entry.data.get(CONF_USERNAME)
            password = entry.data.get(CONF_PASSWORD)
            motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
            enableTimeSync = entry.data.get(ENABLE_TIME_SYNC)

            # motion detection retries
            if motionSensor or enableTimeSync:
                if (
                    not hass.data[DOMAIN][entry.entry_id]["eventsDevice"]
                    or not hass.data[DOMAIN][entry.entry_id]["onvifManagement"]
                ):
                    # retry if connection to onvif failed
                    onvifDevice = await initOnvifEvents(hass, host, username, password)
                    hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = onvifDevice[
                        "device"
                    ]
                    hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = onvifDevice[
                        "device_mgmt"
                    ]
                    if motionSensor:
                        await setupOnvif(hass, entry)
                elif (
                    not hass.data[DOMAIN][entry.entry_id]["eventsSetup"]
                    and motionSensor
                ):
                    # retry if subscription to events failed
                    hass.data[DOMAIN][entry.entry_id][
                        "eventsSetup"
                    ] = await setupEvents(hass, entry)

                if (
                    hass.data[DOMAIN][entry.entry_id]["onvifManagement"]
                    and enableTimeSync
                ):
                    ts = datetime.datetime.utcnow().timestamp()
                    if (
                        ts - hass.data[DOMAIN][entry.entry_id]["lastTimeSync"]
                        > TIME_SYNC_PERIOD
                    ):
                        await syncTime(hass, entry)

            # cameras state
            someCameraEnabled = False
            for entity in hass.data[DOMAIN][entry.entry_id]["entities"]:
                if entity._enabled:
                    someCameraEnabled = True

            if someCameraEnabled:
                try:
                    camData = await getCamData(hass, tapoController)
                except Exception as e:
                    camData = False
                    LOGGER.error(e)
                hass.data[DOMAIN][entry.entry_id]["camData"] = camData
                for entity in hass.data[DOMAIN][entry.entry_id]["entities"]:
                    if entity._enabled:
                        entity.updateCam(camData)
                        entity.async_schedule_update_ha_state(True)
                        if (
                            not hass.data[DOMAIN][entry.entry_id]["noiseSensorStarted"]
                            and entity._enable_sound_detection
                        ):
                            await entity.startNoiseDetection()

        tapoCoordinator = DataUpdateCoordinator(
            hass, LOGGER, name="Tapo resource status", update_method=async_update_data,
        )

        camData = await getCamData(hass, tapoController)

        hass.data[DOMAIN][entry.entry_id] = {
            "controller": tapoController,
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": tapoCoordinator,
            "camData": camData,
            "lastTimeSync": 0,
            "motionSensorCreated": False,
            "eventsDevice": False,
            "onvifManagement": False,
            "eventsSetup": False,
            "events": False,
            "name": camData["basic_info"]["device_alias"],
        }
        if motionSensor or enableTimeSync:
            onvifDevice = await initOnvifEvents(hass, host, username, password)
            hass.data[DOMAIN][entry.entry_id]["eventsDevice"] = onvifDevice["device"]
            hass.data[DOMAIN][entry.entry_id]["onvifManagement"] = onvifDevice[
                "device_mgmt"
            ]
            if motionSensor:
                await setupOnvif(hass, entry)
            if enableTimeSync:
                await syncTime(hass, entry)

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

        async def unsubscribe(event):
            if hass.data[DOMAIN][entry.entry_id]["events"]:
                await hass.data[DOMAIN][entry.entry_id]["events"].async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsubscribe)

    except Exception as e:
        LOGGER.error(
            "Unable to connect to Tapo: Cameras Control controller: %s", str(e)
        )
        raise ConfigEntryNotReady

    return True
