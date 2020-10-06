from pytapo import Tapo
from homeassistant import config_entries
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD
)
import voluptuous as vol
import logging
from .utils import registerController

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                host = user_input[CONF_IP_ADDRESS]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]

                await self.hass.async_add_executor_job(registerController, host, username, password)

                return self.async_create_entry(
                    title=host,
                    data={CONF_IP_ADDRESS: host, CONF_USERNAME: username, CONF_PASSWORD: password,},
                )
            except Exception as e:
                if("Failed to establish a new connection" in str(e)):
                    errors["base"] = "connection_failed"
                elif(str(e) == "Invalid authentication data."):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error(e)

        return self.async_show_form(
            step_id="user", data_schema=DEVICE_SCHEMA, errors=errors
        )