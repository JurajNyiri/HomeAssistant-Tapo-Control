import logging
from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD)
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Tapo: Cameras Control component from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    try:
        tapoController = await hass.async_add_executor_job(registerController, host, username, password)

        async def async_update_data():
            if(not hass.data[DOMAIN][entry.entry_id]['events']):
                eventsStarted = await events.async_start()
                if(eventsStarted):
                    print("OK")
                    hass.data[DOMAIN][entry.entry_id]['events'] = events
                    events.async_add_listener(async_events_listener)
                else:
                    hass.data[DOMAIN][entry.entry_id]['events'] = False
                    print("fail")
                    
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
            "initialData": camData
        }

        ### ONVIF - START
        def async_events_listener():
            for event in events.get_platform("binary_sensor"):
                print(f"tapo event: " + str(event))

        device = await initOnvifEvents(hass, host, username, password)

        events = EventManager(
            hass, device, f"{entry.entry_id}_tapo_events"
        )
        
        eventsStarted = await events.async_start()
        if(eventsStarted):
            print("OK")
            hass.data[DOMAIN][entry.entry_id]['events'] = events
            events.async_add_listener(async_events_listener)
        else:
            hass.data[DOMAIN][entry.entry_id]['events'] = False
            print("fail")
        ### ONVIF - END



        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

    except Exception as e:
        _LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

