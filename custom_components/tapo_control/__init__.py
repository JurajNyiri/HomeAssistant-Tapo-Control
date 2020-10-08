import logging
import asyncio
from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.onvif.event import EventManager
from .const import *
from .utils import registerController, getCamData, initOnvifEvents

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tapo: Cameras Control component from YAML."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    print("tapo async_unload_entry")
    """Unload a config entry."""
    platforms = ["camera","binary_sensor"]

    if(hass.data[DOMAIN][entry.entry_id]['events']):
        await hass.data[DOMAIN][entry.entry_id]['events'].async_stop()

    return all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in platforms
            ]
        )
    )

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    try:
        tapoController = await hass.async_add_executor_job(registerController, host, username, password)

        async def setupOnvif():
            hass.data[DOMAIN][entry.entry_id]['eventsDevice'] = await initOnvifEvents(hass, host, username, password)

            if(hass.data[DOMAIN][entry.entry_id]['eventsDevice']):
                hass.data[DOMAIN][entry.entry_id]['events'] = EventManager(
                    hass, hass.data[DOMAIN][entry.entry_id]['eventsDevice'], f"{entry.entry_id}_tapo_events"
                )
            
                hass.data[DOMAIN][entry.entry_id]['eventsSetup'] = await setupEvents()

        async def setupEvents():
            if(not hass.data[DOMAIN][entry.entry_id]['events'].started):
                events = hass.data[DOMAIN][entry.entry_id]['events']
                if(await events.async_start()):
                    print("OK")
                    hass.async_create_task(
                        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
                    )
                    return True
                else:
                    print("FAIL")
                    return False

        async def async_update_data():
            # motion detection retries
            if not hass.data[DOMAIN][entry.entry_id]['eventsDevice']:
                # retry if connection to onvif failed
                await setupOnvif()
            elif not hass.data[DOMAIN][entry.entry_id]['eventsSetup']:
                # retry if subscription to events failed
                hass.data[DOMAIN][entry.entry_id]['eventsSetup'] = await setupEvents()
                    
            # cameras state
            camData = await getCamData(hass, tapoController)
            for entity in hass.data[DOMAIN][entry.entry_id]['entities']:
                entity.updateCam(camData)
                entity.async_schedule_update_ha_state(True)


        tapoCoordinator = DataUpdateCoordinator(
                hass,
                _LOGGER,
                name="Tapo resource status",
                update_method=async_update_data
            )

        camData = await getCamData(hass, tapoController)

        hass.data[DOMAIN][entry.entry_id] = {
            "controller": tapoController,
            "coordinator": tapoCoordinator,
            "initialData": camData,
            "name": camData['basic_info']['device_alias']
        }

        await setupOnvif()

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

        async def unsubscribe(event):
            if(hass.data[DOMAIN][entry.entry_id]['events']):
                await hass.data[DOMAIN][entry.entry_id]['events'].async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsubscribe)

    except Exception as e:
        _LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

