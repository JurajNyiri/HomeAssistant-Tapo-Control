from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.onvif.event import EventManager
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import onvif
from onvif import ONVIFCamera
import datetime as dt
import logging
import os
from .const import *
from .utils import registerController, getCamData

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

    ### ONVIF - START
    """
    device = ONVIFCamera(host, 2020, username, password, f"{os.path.dirname(onvif.__file__)}/wsdl/",no_cache=True)
    await device.update_xaddrs()
    device_mgmt = device.create_devicemgmt_service()
    device_info = await device_mgmt.GetDeviceInformation()
    if(not 'Manufacturer' in device_info):
        raise Exception("Onvif connection has failed.")

    eventsAvailable = False
    try:
        event_service = device.create_events_service()
        event_capabilities = await event_service.GetServiceCapabilities()
        eventsAvailable = event_capabilities and event_capabilities.WSPullPointSupport
    except:
        raise Exception("Onvif events not available.")

    events = EventManager(
        hass, device, entry.entry_id + "_tapo_events"
    )
    print(f"{host}: {str(await events.async_start())}")

    def async_check_entities():
        for event in events.get_platform("binary_sensor"):
            print(f"tapo event: " + str(event))
    events.async_add_listener(async_check_entities)
    """

    ### ONVIF - END

    """ single update"""

    
    
    try:
        tapoController = await hass.async_add_executor_job(registerController, host, username, password)

        async def async_update_data():
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

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

    except Exception as e:
        _LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

