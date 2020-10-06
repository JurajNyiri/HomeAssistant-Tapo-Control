from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import logging
from .const import *
from .utils import registerController

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

        hass.data[DOMAIN][entry.entry_id] = tapoController

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

    except Exception as e:
        _LOGGER.error("Unable to connect to Tapo: Cameras Control controller: %s", str(e))
        raise ConfigEntryNotReady

    return True

