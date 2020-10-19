from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
import voluptuous as vol
from .utils import registerController
from .const import DOMAIN, ENABLE_MOTION_SENSOR, LOGGER


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TapoOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Confirm the setup."""
        errors = {}
        host = ""
        username = ""
        password = ""
        enable_motion_sensor = True
        if user_input is not None:
            try:
                host = user_input[CONF_IP_ADDRESS]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                enable_motion_sensor = user_input[ENABLE_MOTION_SENSOR]

                await self.hass.async_add_executor_job(
                    registerController, host, username, password
                )

                return self.async_create_entry(
                    title=host,
                    data={
                        ENABLE_MOTION_SENSOR: enable_motion_sensor,
                        CONF_IP_ADDRESS: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                elif str(e) == "Invalid authentication data.":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, description={"suggested_value": host}
                    ): str,
                    vol.Required(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                    vol.Required(
                        ENABLE_MOTION_SENSOR,
                        description={"suggested_value": enable_motion_sensor},
                    ): bool,
                }
            ),
            errors=errors,
        )


class TapoOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Tapo options."""
        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Manage the Tapo options."""
        errors = {}
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]
        enable_motion_sensor = self.config_entry.data[ENABLE_MOTION_SENSOR]
        if user_input is not None:
            try:
                host = self.config_entry.data["ip_address"]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                enable_motion_sensor = user_input[ENABLE_MOTION_SENSOR]

                await self.hass.async_add_executor_job(
                    registerController, host, username, password
                )

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        ENABLE_MOTION_SENSOR: enable_motion_sensor,
                        CONF_IP_ADDRESS: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                elif str(e) == "Invalid authentication data.":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                    vol.Required(
                        ENABLE_MOTION_SENSOR,
                        description={"suggested_value": enable_motion_sensor},
                    ): bool,
                }
            ),
            errors=errors,
        )
