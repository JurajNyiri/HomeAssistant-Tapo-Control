from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import *
from .utils import registerController, getCamData, setupOnvif, setupEvents, update_listener

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tapo: Cameras Control component from YAML."""
    return True

async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:

        new = {**config_entry.data}
        new['enable_motion_sensor'] = True
        
        config_entry.data = {**new}

        config_entry.version = 2

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    if(hass.data[DOMAIN][entry.entry_id]['events']):
        await hass.data[DOMAIN][entry.entry_id]['events'].async_stop()
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)

    try:
        tapoController = await hass.async_add_executor_job(registerController, host, username, password)

        async def async_update_data():
            host = entry.data.get(CONF_IP_ADDRESS)
            username = entry.data.get(CONF_USERNAME)
            password = entry.data.get(CONF_PASSWORD)
            motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)

            # motion detection retries
            if motionSensor:
                if not hass.data[DOMAIN][entry.entry_id]['eventsDevice']:
                    # retry if connection to onvif failed
                    await setupOnvif(hass, entry, host, username, password)
                elif not hass.data[DOMAIN][entry.entry_id]['eventsSetup']:
                    # retry if subscription to events failed
                    hass.data[DOMAIN][entry.entry_id]['eventsSetup'] = await setupEvents(hass, entry)
            
            # cameras state
            someCameraEnabled = False
            for entity in hass.data[DOMAIN][entry.entry_id]['entities']:
                if(entity._enabled):
                    someCameraEnabled = True
                    
            if someCameraEnabled:
                camData = await getCamData(hass, tapoController)
                for entity in hass.data[DOMAIN][entry.entry_id]['entities']:
                    if(entity._enabled):
                        entity.updateCam(camData)
                        entity.async_schedule_update_ha_state(True)

        tapoCoordinator = DataUpdateCoordinator(
                hass,
                LOGGER,
                name="Tapo resource status",
                update_method=async_update_data
            )

        camData = await getCamData(hass, tapoController)

        hass.data[DOMAIN][entry.entry_id] = {
            "controller": tapoController,
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": tapoCoordinator,
            "initialData": camData,
            "motionSensorCreated": False,
            "eventsDevice": False,
            "eventsSetup": False,
            "events": False,
            "name": camData['basic_info']['device_alias']
        }
        if motionSensor:
            await setupOnvif(hass, entry, host, username, password)

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

        async def unsubscribe(event):
            if(hass.data[DOMAIN][entry.entry_id]['events']):
                await hass.data[DOMAIN][entry.entry_id]['events'].async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsubscribe)

    except Exception as e:
        LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

