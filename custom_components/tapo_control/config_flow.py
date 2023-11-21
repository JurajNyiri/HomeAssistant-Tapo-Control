import voluptuous as vol

from homeassistant.core import callback

from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.config_entries import HANDLERS, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.device_registry import async_get as device_registry_async_get
from homeassistant.helpers.selector import selector

from .utils import (
    registerController,
    isRtspStreamWorking,
    areCameraPortsOpened,
    isOpen,
)
from .const import (
    DOMAIN,
    ENABLE_MEDIA_SYNC,
    ENABLE_MOTION_SENSOR,
    ENABLE_STREAM,
    ENABLE_SOUND_DETECTION,
    ENABLE_WEBHOOKS,
    LOGGER,
    CLOUD_PASSWORD,
    ENABLE_TIME_SYNC,
    MEDIA_SYNC_COLD_STORAGE_PATH,
    MEDIA_SYNC_HOURS,
    MEDIA_VIEW_DAYS_ORDER,
    MEDIA_VIEW_DAYS_ORDER_OPTIONS,
    MEDIA_VIEW_RECORDINGS_ORDER,
    MEDIA_VIEW_RECORDINGS_ORDER_OPTIONS,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    CONF_CUSTOM_STREAM,
    CONF_RTSP_TRANSPORT,
    RTSP_TRANS_PROTOCOLS,
)


@HANDLERS.register(DOMAIN)
class FlowHandler(ConfigFlow):
    """Handle a config flow."""

    VERSION = 15

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TapoOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        host = self.reauth_entry.data[CONF_IP_ADDRESS]
        if not areCameraPortsOpened(host):
            LOGGER.debug(
                "[REAUTH][%s] Some of the required ports are closed.",
                host,
            )
            self.tapoHost = host
            self.tapoUsername = ""
            self.tapoPassword = ""
            return await self.async_step_reauth_confirm_cloud()
        else:
            LOGGER.debug(
                "[REAUTH][%s] All camera ports are opened, proceeding to requesting Camera Account.",
                host,
            )
            self.tapoHost = host
            return await self.async_step_reauth_confirm_stream()

    async def async_step_reauth_confirm_stream(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        errors = {}
        tapoHost = self.reauth_entry.data[CONF_IP_ADDRESS]
        custom_stream = self.reauth_entry.data[CONF_CUSTOM_STREAM]
        cloud_password = self.reauth_entry.data[CLOUD_PASSWORD]
        username = self.reauth_entry.data[CONF_USERNAME]
        password = self.reauth_entry.data[CONF_PASSWORD]
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                LOGGER.debug(
                    "[REAUTH][%s] Testing RTSP stream.",
                    tapoHost,
                )
                rtspStreamWorks = await isRtspStreamWorking(
                    self.hass, tapoHost, username, password, custom_stream
                )
                if not rtspStreamWorks:
                    LOGGER.debug(
                        "[REAUTH][%s] RTSP stream returned invalid authentication data error.",
                        tapoHost,
                    )
                    raise Exception("Invalid stream authentication data")
                else:
                    LOGGER.debug(
                        "[REAUTH][%s] RTSP stream works.",
                        tapoHost,
                    )

                    allConfigData = {**self.reauth_entry.data}
                    allConfigData[CONF_USERNAME] = username
                    allConfigData[CONF_PASSWORD] = password
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry,
                        title=tapoHost,
                        data=allConfigData,
                    )
                    try:
                        LOGGER.debug(
                            "[REAUTH][%s] Testing control of camera using Camera Account.",
                            tapoHost,
                        )
                        await self.hass.async_add_executor_job(
                            registerController, tapoHost, username, password
                        )
                        LOGGER.debug(
                            "[REAUTH][%s] Camera Account works for control.",
                            tapoHost,
                        )
                        if cloud_password != "":
                            LOGGER.debug(
                                "[REAUTH][%s] Cloud password is not empty, requesting validation.",
                                tapoHost,
                            )
                            return await self.async_step_reauth_confirm_cloud()
                    except Exception as e:
                        if str(e) == "Invalid authentication data":
                            LOGGER.debug(
                                "[REAUTH][%s] Camera Account does not work for control, requesting cloud password.",
                                tapoHost,
                            )
                            return await self.async_step_reauth_confirm_cloud()
                        elif "Temporary Suspension" in str(e):
                            LOGGER.debug(
                                "[REAUTH][%s] Temporary suspension.",
                                tapoHost,
                            )
                            raise Exception("temporary_suspension")
                        else:
                            LOGGER.error(e)
                            raise Exception(e)

                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    LOGGER.debug(
                        "[REAUTH][%s] Connection failed.",
                        tapoHost,
                    )
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif str(e) == "Invalid authentication data":
                    LOGGER.debug(
                        "[REAUTH][%s] Invalid cloud password provided.",
                        tapoHost,
                    )
                    errors["base"] = "invalid_auth_cloud"
                elif str(e) == "Invalid stream authentication data":
                    LOGGER.debug(
                        "[REAUTH][%s] Invalid 3rd party account password provided.",
                        tapoHost,
                    )
                    errors["base"] = "invalid_stream_auth"
                elif (
                    "Temporary Suspension" in str(e)
                    or str(e) == "temporary_suspension"  # todo: test this
                ):
                    LOGGER.debug(
                        "[REAUTH][%s] Temporary suspension.",
                        tapoHost,
                    )
                    errors["base"] = str(e)
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)
        LOGGER.debug(
            "[REAUTH][%s] Showing config flow for reauth - stream.",
            tapoHost,
        )
        return self.async_show_form(
            step_id="reauth_confirm_stream",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                }
            ),
            errors=errors,
            last_step=True,
        )

    async def async_step_reauth_confirm_cloud(self, user_input=None):
        errors = {}
        tapoHost = self.reauth_entry.data[CONF_IP_ADDRESS]
        cloudPassword = self.reauth_entry.data[CLOUD_PASSWORD]
        if user_input is not None:
            cloudPassword = user_input[CLOUD_PASSWORD]
            try:
                LOGGER.debug(
                    "[REAUTH][%s] Testing control of camera using Cloud Account.",
                    tapoHost,
                )
                await self.hass.async_add_executor_job(
                    registerController, tapoHost, "admin", cloudPassword
                )
                LOGGER.debug(
                    "[REAUTH][%s] Cloud Account works for control.",
                    tapoHost,
                )
                allConfigData = {**self.reauth_entry.data}
                allConfigData[CLOUD_PASSWORD] = cloudPassword
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    title=tapoHost,
                    data=allConfigData,
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    LOGGER.debug(
                        "[REAUTH][%s] Connection failed.",
                        tapoHost,
                    )
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif str(e) == "Invalid authentication data":
                    LOGGER.debug(
                        "[REAUTH][%s] Invalid cloud password provided.",
                        tapoHost,
                    )
                    errors["base"] = "invalid_auth_cloud"
                elif str(e) == "Invalid stream authentication data":
                    LOGGER.debug(
                        "[REAUTH][%s] Invalid 3rd party account password provided.",
                        tapoHost,
                    )
                    errors["base"] = "invalid_stream_auth"
                elif "Temporary Suspension" in str(e):  # tested
                    LOGGER.debug(
                        "[REAUTH][%s] Temporary suspension.",
                        tapoHost,
                    )
                    errors["base"] = str(e)
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)
        LOGGER.debug(
            "[REAUTH][%s] Showing config flow for reauth - cloud.",
            tapoHost,
        )
        return self.async_show_form(
            step_id="reauth_confirm_cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CLOUD_PASSWORD, description={"suggested_value": cloudPassword}
                    ): str,
                }
            ),
            errors=errors,
            last_step=True,
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        LOGGER.debug("[ADD DEVICE] Setup process for tapo initiated by user.")
        return await self.async_step_ip()

    async def async_step_dhcp(self, dhcp_discovery):
        """Handle dhcp discovery."""
        if self._async_host_already_configured(dhcp_discovery.ip):
            LOGGER.debug("[ADD DEVICE][%s] Already discovered.", dhcp_discovery.ip)
            return self.async_abort(reason="already_configured")

        if (
            not dhcp_discovery.hostname.startswith("C100_")
            and not dhcp_discovery.hostname.startswith("C200_")
            and not dhcp_discovery.hostname.startswith("C310_")
            and not dhcp_discovery.hostname.startswith("TC60_")
            and not dhcp_discovery.hostname.startswith("TC70_")
        ):
            LOGGER.debug("[ADD DEVICE][%s] Not a tapo device.", dhcp_discovery.ip)
            return self.async_abort(reason="not_tapo_device")

        mac_address = dhcp_discovery.macaddress
        await self.async_set_unique_id(mac_address)
        self.context.update({"title_placeholders": {"name": dhcp_discovery.ip}})
        self.tapoHost = dhcp_discovery.ip
        LOGGER.debug(
            "[ADD DEVICE][%s] Initiating config flow by discovery.", dhcp_discovery.ip
        )
        return await self.async_step_auth()

    @callback
    def _async_host_already_configured(self, host):
        """See if we already have an entry matching the host."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_IP_ADDRESS) == host:
                return True
        return False

    async def async_step_other_options(self, user_input=None):
        """Enter and process final options"""
        errors = {}
        enable_motion_sensor = True
        enable_webhooks = True
        enable_stream = True
        enable_time_sync = False
        enable_sound_detection = False
        sound_detection_peak = -30
        sound_detection_duration = 1
        sound_detection_reset = 10
        extra_arguments = ""
        custom_stream = ""
        rtsp_transport = RTSP_TRANS_PROTOCOLS[0]
        if user_input is not None:
            LOGGER.debug(
                "[ADD DEVICE][%s] Verifying other options.",
                self.tapoHost,
            )
            if ENABLE_MOTION_SENSOR in user_input:
                enable_motion_sensor = user_input[ENABLE_MOTION_SENSOR]
            else:
                enable_motion_sensor = False
            if ENABLE_WEBHOOKS in user_input:
                enable_webhooks = user_input[ENABLE_WEBHOOKS]
            else:
                enable_webhooks = False
            if ENABLE_STREAM in user_input:
                enable_stream = user_input[ENABLE_STREAM]
            else:
                enable_stream = False
            if ENABLE_TIME_SYNC in user_input:
                enable_time_sync = user_input[ENABLE_TIME_SYNC]
            else:
                enable_time_sync = False
            if ENABLE_SOUND_DETECTION in user_input:
                enable_sound_detection = user_input[ENABLE_SOUND_DETECTION]
            else:
                enable_sound_detection = False
            if SOUND_DETECTION_PEAK in user_input:
                sound_detection_peak = user_input[SOUND_DETECTION_PEAK]
            else:
                sound_detection_peak = -30
            if CONF_CUSTOM_STREAM in user_input:
                custom_stream = user_input[CONF_CUSTOM_STREAM]
            else:
                custom_stream = ""
            if SOUND_DETECTION_DURATION in user_input:
                sound_detection_duration = user_input[SOUND_DETECTION_DURATION]
            else:
                sound_detection_duration = -30
            if SOUND_DETECTION_RESET in user_input:
                sound_detection_reset = user_input[SOUND_DETECTION_RESET]
            else:
                sound_detection_reset = -30
            if CONF_EXTRA_ARGUMENTS in user_input:
                extra_arguments = user_input[CONF_EXTRA_ARGUMENTS]
            else:
                extra_arguments = ""
            if CONF_RTSP_TRANSPORT in user_input:
                rtsp_transport = user_input[CONF_RTSP_TRANSPORT]
            else:
                rtsp_transport = RTSP_TRANS_PROTOCOLS[0]
            host = self.tapoHost
            cloud_password = self.tapoCloudPassword
            username = self.tapoUsername
            password = self.tapoPassword
            LOGGER.debug(
                "[ADD DEVICE][%s] Saving entry.",
                self.tapoHost,
            )
            return self.async_create_entry(
                title=host,
                data={
                    MEDIA_VIEW_DAYS_ORDER: "Ascending",
                    MEDIA_VIEW_RECORDINGS_ORDER: "Ascending",
                    ENABLE_MEDIA_SYNC: False,
                    MEDIA_SYNC_HOURS: "",
                    MEDIA_SYNC_COLD_STORAGE_PATH: "",
                    ENABLE_MOTION_SENSOR: enable_motion_sensor,
                    ENABLE_WEBHOOKS: enable_webhooks,
                    ENABLE_STREAM: enable_stream,
                    ENABLE_TIME_SYNC: enable_time_sync,
                    CONF_IP_ADDRESS: host,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CLOUD_PASSWORD: cloud_password,
                    ENABLE_SOUND_DETECTION: enable_sound_detection,
                    SOUND_DETECTION_PEAK: sound_detection_peak,
                    SOUND_DETECTION_DURATION: sound_detection_duration,
                    SOUND_DETECTION_RESET: sound_detection_reset,
                    CONF_EXTRA_ARGUMENTS: extra_arguments,
                    CONF_CUSTOM_STREAM: custom_stream,
                    CONF_RTSP_TRANSPORT: rtsp_transport,
                },
            )

        LOGGER.debug(
            "[ADD DEVICE][%s] Showing config flow for other options.",
            self.tapoHost,
        )
        return self.async_show_form(
            step_id="other_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        ENABLE_MOTION_SENSOR,
                        description={"suggested_value": enable_motion_sensor},
                    ): bool,
                    vol.Optional(
                        ENABLE_WEBHOOKS,
                        description={"suggested_value": enable_webhooks},
                    ): bool,
                    vol.Optional(
                        ENABLE_TIME_SYNC,
                        description={"suggested_value": enable_time_sync},
                    ): bool,
                    vol.Optional(
                        ENABLE_STREAM,
                        description={"suggested_value": enable_stream},
                    ): bool,
                    vol.Optional(
                        ENABLE_SOUND_DETECTION,
                        description={"suggested_value": enable_sound_detection},
                    ): bool,
                    vol.Optional(
                        SOUND_DETECTION_PEAK,
                        description={"suggested_value": sound_detection_peak},
                    ): int,
                    vol.Optional(
                        SOUND_DETECTION_DURATION,
                        description={"suggested_value": sound_detection_duration},
                    ): int,
                    vol.Optional(
                        SOUND_DETECTION_RESET,
                        description={"suggested_value": sound_detection_reset},
                    ): int,
                    vol.Optional(
                        CONF_EXTRA_ARGUMENTS,
                        description={"suggested_value": extra_arguments},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM,
                        description={"suggested_value": custom_stream},
                    ): str,
                    vol.Optional(
                        CONF_RTSP_TRANSPORT,
                        description={"suggested_value": rtsp_transport},
                    ): str,
                }
            ),
            errors=errors,
            last_step=True,
        )

    async def async_step_auth_cloud_password(self, user_input=None):
        """Enter and process cloud password if needed"""
        errors = {}
        cloud_password = ""
        if user_input is not None:
            try:
                LOGGER.debug(
                    "[ADD DEVICE][%s] Verifying cloud password.",
                    self.tapoHost,
                )
                cloud_password = user_input[CLOUD_PASSWORD]
                await self.hass.async_add_executor_job(
                    registerController, self.tapoHost, "admin", cloud_password
                )
                LOGGER.debug(
                    "[ADD DEVICE][%s] Cloud password works for control.",
                    self.tapoHost,
                )
                self.tapoCloudPassword = cloud_password
                return await self.async_step_other_options()
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Connection failed.",
                        self.tapoHost,
                    )
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif str(e) == "Invalid authentication data":
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Invalid cloud password provided.",
                        self.tapoHost,
                    )
                    errors["base"] = "invalid_auth_cloud"
                elif "Temporary Suspension" in str(e):
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Temporary suspension.",
                        self.tapoHost,
                    )
                    errors["base"] = str(e)
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)
        LOGGER.debug(
            "[ADD DEVICE][%s] Showing config flow for cloud password.",
            self.tapoHost,
        )
        return self.async_show_form(
            step_id="auth_cloud_password",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CLOUD_PASSWORD, description={"suggested_value": cloud_password}
                    ): str,
                }
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_ip(self, user_input=None):
        """Enter IP Address and verify Tapo device"""
        errors = {}
        host = ""
        if user_input is not None:
            LOGGER.debug("[ADD DEVICE] Verifying IP address")
            try:
                host = user_input[CONF_IP_ADDRESS]

                if self._async_host_already_configured(host):
                    LOGGER.debug("[ADD DEVICE][%s] IP already configured.", host)
                    raise Exception("already_configured")

                LOGGER.debug("[ADD DEVICE][%s] Verifying port 443.", host)
                if isOpen(host, 443):
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Port 443 is opened, verifying access to control of camera.",
                        host,
                    )
                    try:
                        await self.hass.async_add_executor_job(
                            registerController, host, "invalid", ""
                        )
                    except Exception as e:
                        if str(e) == "Invalid authentication data":
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Verifying ports all required camera ports.",
                                host,
                            )
                            if not areCameraPortsOpened(host):
                                LOGGER.debug(
                                    "[ADD DEVICE][%s] Some of the required ports are closed.",
                                    host,
                                )
                                self.tapoHost = host
                                self.tapoUsername = ""
                                self.tapoPassword = ""
                                return await self.async_step_auth_cloud_password()
                            else:
                                LOGGER.debug(
                                    "[ADD DEVICE][%s] All camera ports are opened, proceeding to requesting Camera Account.",
                                    host,
                                )
                                self.tapoHost = host
                                return await self.async_step_auth()
                        elif "Temporary Suspension" in str(e):
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Temporary suspension.",
                                self.tapoHost,
                            )
                            raise Exception("temporary_suspension")
                        else:
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Camera control is not available, IP is not a Tapo device. Error: %s",
                                host,
                                str(e),
                            )
                            raise Exception("not_tapo_device")
                else:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Port 443 is closed.",
                        host,
                    )
                    raise Exception("Failed to establish a new connection")
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif "already_configured" in str(e):
                    errors["base"] = "already_configured"
                elif "not_tapo_device" in str(e):
                    errors["base"] = "not_tapo_device"
                elif "ports_closed" in str(e):
                    errors["base"] = "ports_closed"
                elif "temporary_suspension" in str(e):
                    errors["base"] = str(e)
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        LOGGER.debug("[ADD DEVICE] Showing config flow for IP.")
        return self.async_show_form(
            step_id="ip",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, description={"suggested_value": host}
                    ): str,
                }
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_auth_optional_cloud(self, user_input=None):
        """Enter and process cloud password if needed"""
        errors = {}
        if user_input is not None:
            if CLOUD_PASSWORD in user_input:
                try:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Verifying cloud password.",
                        self.tapoHost,
                    )
                    cloud_password = user_input[CLOUD_PASSWORD]
                    await self.hass.async_add_executor_job(
                        registerController, self.tapoHost, "admin", cloud_password
                    )
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Cloud password works for control.",
                        self.tapoHost,
                    )
                    self.tapoCloudPassword = cloud_password
                    return await self.async_step_other_options()
                except Exception as e:
                    if "Failed to establish a new connection" in str(e):
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Connection failed.",
                            self.tapoHost,
                        )
                        errors["base"] = "connection_failed"
                        LOGGER.error(e)
                    elif str(e) == "Invalid authentication data":
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Invalid cloud password provided.",
                            self.tapoHost,
                        )
                        errors["base"] = "invalid_auth_cloud"
                    elif "Temporary Suspension" in str(e):
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Temporary suspension.",
                            self.tapoHost,
                        )
                        errors["base"] = str(e)
                    else:
                        errors["base"] = "unknown"
                        LOGGER.error(e)
            else:
                self.tapoCloudPassword = ""
                return await self.async_step_other_options()
        cloud_password = ""
        LOGGER.debug(
            "[ADD DEVICE][%s] Showing config flow for cloud password.",
            self.tapoHost,
        )
        return self.async_show_form(
            step_id="auth_optional_cloud",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CLOUD_PASSWORD, description={"suggested_value": cloud_password}
                    ): str,
                }
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_auth(self, user_input=None):
        """Provide authentication data."""
        errors = {}
        username = ""
        password = ""
        host = self.tapoHost
        if user_input is not None:
            try:
                LOGGER.debug("[ADD DEVICE][%s] Verifying Camera Account.", host)
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]

                LOGGER.debug(
                    "[ADD DEVICE][%s] Verifying ports all required camera ports.",
                    host,
                )
                if not areCameraPortsOpened(host):
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Some of the required ports are closed.",
                        host,
                    )
                    raise Exception("ports_closed")
                else:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] All camera ports are opened.",
                        host,
                    )

                LOGGER.debug(
                    "[ADD DEVICE][%s] Testing RTSP stream.",
                    host,
                )
                rtspStreamWorks = await isRtspStreamWorking(
                    self.hass, host, username, password
                )
                if not rtspStreamWorks:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] RTSP stream returned invalid authentication data error.",
                        host,
                    )
                    raise Exception("Invalid authentication data")
                else:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] RTSP stream works.",
                        host,
                    )

                self.tapoUsername = username
                self.tapoPassword = password
                self.tapoCloudPassword = ""

                try:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Testing control of camera using Camera Account.",
                        host,
                    )
                    await self.hass.async_add_executor_job(
                        registerController, host, username, password
                    )
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Camera Account works for control.",
                        host,
                    )
                except Exception as e:
                    if str(e) == "Invalid authentication data":
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Camera Account does not work for control, requesting cloud password.",
                            host,
                        )
                        return await self.async_step_auth_cloud_password()
                    elif "Temporary Suspension" in str(e):
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Temporary suspension.",
                            self.tapoHost,
                        )
                        raise Exception("temporary_suspension")
                    else:
                        LOGGER.error(e)
                        raise Exception(e)

                return await self.async_step_auth_optional_cloud()

            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif "ports_closed" in str(e):
                    errors["base"] = "ports_closed"
                elif str(e) == "Invalid authentication data":
                    errors["base"] = "invalid_auth"
                elif str(e) == "temporary_suspension":
                    errors["base"] = str(e)
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        LOGGER.debug(
            "[ADD DEVICE][%s] Showing config flow for Camera Account.",
            host,
        )
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
                }
            ),
            errors=errors,
            last_step=False,
        )


class TapoOptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    # todo rewrite strings into variables
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if "tapo_config_action" in user_input:
                nextAction = user_input["tapo_config_action"]
                if nextAction == "Configure device":
                    return await self.async_step_auth()
                elif nextAction == "Configure media":
                    return await self.async_step_media()
                elif nextAction == "Configure sound sensor":
                    return await self.async_step_sound_sensor()
                elif nextAction == "Help me debug motion sensor":
                    # TODO
                    """
                    On this screen, text field will be shown including the figured base_url and the action it took (enabled or disabled webhooks)
                    Also create a new issue template, for motion sensor, requiring users to go through this screen and screenshot it
                    Screen could also have stuff like firmware, hw, maybe even try configure the sensor and do some kind of debugging?
                    Flow could restart camera, make sure motion sensor is not enabled and require disable and HA restart if it is etc.
                    Finally, add an option to disable webhooks in configuration section
                    """
                else:
                    errors["base"] = "incorrect_options_action"

        data_schema = {
            "tapo_config_action": selector(
                {
                    "select": {
                        "options": [
                            "Configure device",
                            "Configure sound sensor",
                            "Configure media"
                            # "Help me debug motion sensor",
                            # "incorrect",
                        ],
                    }
                }
            )
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_sound_sensor(self, user_input=None):
        """Manage the Tapo options."""
        ip_address = self.config_entry.data[CONF_IP_ADDRESS]
        LOGGER.debug(
            "[%s] Opened Tapo options - sound sensor.",
            ip_address,
        )
        errors = {}

        enable_sound_detection = self.config_entry.data[ENABLE_SOUND_DETECTION]
        sound_detection_peak = self.config_entry.data[SOUND_DETECTION_PEAK]
        sound_detection_duration = self.config_entry.data[SOUND_DETECTION_DURATION]
        sound_detection_reset = self.config_entry.data[SOUND_DETECTION_RESET]

        allConfigData = {**self.config_entry.data}
        if user_input is not None:
            try:
                if ENABLE_SOUND_DETECTION in user_input:
                    enable_sound_detection = user_input[ENABLE_SOUND_DETECTION]
                else:
                    enable_sound_detection = False

                if SOUND_DETECTION_PEAK in user_input:
                    sound_detection_peak = user_input[SOUND_DETECTION_PEAK]
                else:
                    sound_detection_peak = -30

                if SOUND_DETECTION_DURATION in user_input:
                    sound_detection_duration = user_input[SOUND_DETECTION_DURATION]
                else:
                    sound_detection_duration = 1

                if SOUND_DETECTION_RESET in user_input:
                    sound_detection_reset = user_input[SOUND_DETECTION_RESET]
                else:
                    sound_detection_reset = 10

                if not (
                    int(sound_detection_peak) >= -100 and int(sound_detection_peak) <= 0
                ):
                    LOGGER.debug(
                        "[%s] Incorrect range for sound detection peak.",
                        ip_address,
                    )
                    raise Exception("Incorrect sound detection peak value.")

                allConfigData[ENABLE_SOUND_DETECTION] = enable_sound_detection
                allConfigData[SOUND_DETECTION_PEAK] = sound_detection_peak
                allConfigData[SOUND_DETECTION_DURATION] = sound_detection_duration
                allConfigData[SOUND_DETECTION_RESET] = sound_detection_reset

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=ip_address,
                    data=allConfigData,
                )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                if str(e) == "Incorrect sound detection peak value.":
                    errors["base"] = "incorrect_peak_value"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        return self.async_show_form(
            step_id="sound_sensor",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        ENABLE_SOUND_DETECTION,
                        description={"suggested_value": enable_sound_detection},
                    ): bool,
                    vol.Optional(
                        SOUND_DETECTION_PEAK,
                        description={"suggested_value": sound_detection_peak},
                    ): int,
                    vol.Optional(
                        SOUND_DETECTION_DURATION,
                        description={"suggested_value": sound_detection_duration},
                    ): int,
                    vol.Optional(
                        SOUND_DETECTION_RESET,
                        description={"suggested_value": sound_detection_reset},
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_media(self, user_input=None):
        """Manage the Tapo options."""
        LOGGER.debug(
            "[%s] Opened Tapo options - media.", self.config_entry.data[CONF_IP_ADDRESS]
        )
        errors = {}
        enable_media_sync = self.config_entry.data[ENABLE_MEDIA_SYNC]
        media_view_days_order = self.config_entry.data[MEDIA_VIEW_DAYS_ORDER]
        media_view_recordings_order = self.config_entry.data[
            MEDIA_VIEW_RECORDINGS_ORDER
        ]
        media_sync_hours = self.config_entry.data[MEDIA_SYNC_HOURS]
        media_sync_cold_storage_path = self.config_entry.data[
            MEDIA_SYNC_COLD_STORAGE_PATH
        ]
        ip_address = self.config_entry.data[CONF_IP_ADDRESS]

        allConfigData = {**self.config_entry.data}
        if user_input is not None:
            try:
                if ENABLE_MEDIA_SYNC in user_input:
                    enable_media_sync = user_input[ENABLE_MEDIA_SYNC]
                else:
                    enable_media_sync = False

                if MEDIA_VIEW_DAYS_ORDER in user_input:
                    media_view_days_order = user_input[MEDIA_VIEW_DAYS_ORDER]
                else:
                    media_view_days_order = "Ascending"

                if MEDIA_VIEW_RECORDINGS_ORDER in user_input:
                    media_view_recordings_order = user_input[
                        MEDIA_VIEW_RECORDINGS_ORDER
                    ]
                else:
                    media_view_recordings_order = "Ascending"

                if MEDIA_SYNC_HOURS in user_input:
                    media_sync_hours = user_input[MEDIA_SYNC_HOURS]
                else:
                    media_sync_hours = ""

                if MEDIA_SYNC_COLD_STORAGE_PATH in user_input:
                    media_sync_cold_storage_path = user_input[
                        MEDIA_SYNC_COLD_STORAGE_PATH
                    ]
                else:
                    media_sync_cold_storage_path = ""

                allConfigData[ENABLE_MEDIA_SYNC] = enable_media_sync
                allConfigData[MEDIA_VIEW_DAYS_ORDER] = media_view_days_order
                allConfigData[MEDIA_VIEW_RECORDINGS_ORDER] = media_view_recordings_order
                allConfigData[MEDIA_SYNC_HOURS] = media_sync_hours
                allConfigData[
                    MEDIA_SYNC_COLD_STORAGE_PATH
                ] = media_sync_cold_storage_path
                # todo also initial setup to add the default values!
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=ip_address,
                    data=allConfigData,
                )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                errors["base"] = "unknown"
                LOGGER.error(e)

        return self.async_show_form(
            step_id="media",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        MEDIA_VIEW_DAYS_ORDER,
                        description={"suggested_value": media_view_days_order},
                    ): vol.In(MEDIA_VIEW_DAYS_ORDER_OPTIONS),
                    vol.Required(
                        MEDIA_VIEW_RECORDINGS_ORDER,
                        description={"suggested_value": media_view_recordings_order},
                    ): vol.In(MEDIA_VIEW_RECORDINGS_ORDER_OPTIONS),
                    vol.Optional(
                        ENABLE_MEDIA_SYNC,
                        description={"suggested_value": enable_media_sync},
                    ): bool,
                    vol.Optional(
                        MEDIA_SYNC_HOURS,
                        description={"suggested_value": media_sync_hours},
                    ): int,
                    vol.Optional(
                        MEDIA_SYNC_COLD_STORAGE_PATH,
                        description={"suggested_value": media_sync_cold_storage_path},
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_auth(self, user_input=None):
        """Manage the Tapo options."""
        LOGGER.debug(
            "[%s] Opened Tapo options.", self.config_entry.data[CONF_IP_ADDRESS]
        )
        errors = {}
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]
        cloud_password = self.config_entry.data[CLOUD_PASSWORD]
        enable_motion_sensor = self.config_entry.data[ENABLE_MOTION_SENSOR]
        enable_webhooks = self.config_entry.data[ENABLE_WEBHOOKS]
        enable_stream = self.config_entry.data[ENABLE_STREAM]
        enable_time_sync = self.config_entry.data[ENABLE_TIME_SYNC]
        extra_arguments = self.config_entry.data[CONF_EXTRA_ARGUMENTS]
        custom_stream = self.config_entry.data[CONF_CUSTOM_STREAM]
        rtsp_transport = self.config_entry.data[CONF_RTSP_TRANSPORT]
        ip_address = self.config_entry.data[CONF_IP_ADDRESS]
        if user_input is not None:
            try:
                if CONF_IP_ADDRESS in user_input:
                    ip_address = user_input[CONF_IP_ADDRESS]

                LOGGER.debug(
                    "[%s] Verifying updated data.",
                    ip_address,
                )
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                tapoController = None

                if CLOUD_PASSWORD in user_input:
                    cloud_password = user_input[CLOUD_PASSWORD]
                    if self.config_entry.data[CLOUD_PASSWORD] != cloud_password:
                        LOGGER.debug(
                            "[%s] Testing updated cloud password for control.",
                            ip_address,
                        )
                        try:
                            tapoController = await self.hass.async_add_executor_job(
                                registerController, ip_address, "admin", cloud_password
                            )
                            LOGGER.debug(
                                "[%s] Cloud password works for control.",
                                ip_address,
                            )
                        except Exception as e:
                            LOGGER.debug(
                                "[%s] Camera did not accept password.",
                                ip_address,
                            )
                            LOGGER.error(e)
                            if str(e) == "Invalid authentication data":
                                raise Exception("Incorrect cloud password")
                            else:
                                raise e
                    else:
                        LOGGER.debug(
                            "[%s] Skipping test of cloud password for control as it was not updated.",
                            ip_address,
                        )
                else:
                    LOGGER.debug(
                        "[%s] Skipping test of cloud password for control as it was not provided.",
                        ip_address,
                    )
                    cloud_password = ""

                if ENABLE_MOTION_SENSOR in user_input:
                    enable_motion_sensor = user_input[ENABLE_MOTION_SENSOR]
                else:
                    enable_motion_sensor = False

                if ENABLE_WEBHOOKS in user_input:
                    enable_webhooks = user_input[ENABLE_WEBHOOKS]
                else:
                    enable_webhooks = False

                if ENABLE_STREAM in user_input:
                    enable_stream = user_input[ENABLE_STREAM]
                else:
                    enable_stream = False

                if ENABLE_TIME_SYNC in user_input:
                    enable_time_sync = user_input[ENABLE_TIME_SYNC]
                else:
                    enable_time_sync = False

                if CONF_CUSTOM_STREAM in user_input:
                    custom_stream = user_input[CONF_CUSTOM_STREAM]
                else:
                    custom_stream = ""

                if CONF_EXTRA_ARGUMENTS in user_input:
                    extra_arguments = user_input[CONF_EXTRA_ARGUMENTS]
                else:
                    extra_arguments = ""

                if CONF_RTSP_TRANSPORT in user_input:
                    rtsp_transport = user_input[CONF_RTSP_TRANSPORT]
                else:
                    rtsp_transport = RTSP_TRANS_PROTOCOLS[0]

                if (
                    self.config_entry.data[CONF_PASSWORD] != password
                    or self.config_entry.data[CONF_USERNAME] != username
                    or self.config_entry.data[CONF_IP_ADDRESS] != ip_address
                ):
                    LOGGER.debug(
                        "[%s] Testing RTSP stream.",
                        ip_address,
                    )
                    rtspStreamWorks = await isRtspStreamWorking(
                        self.hass, ip_address, username, password, custom_stream
                    )
                    if not rtspStreamWorks:
                        LOGGER.debug(
                            "[%s] RTSP stream returned invalid authentication data error.",
                            ip_address,
                        )
                        raise Exception("Invalid authentication data")
                    else:
                        LOGGER.debug(
                            "[%s] RTSP stream works.",
                            ip_address,
                        )
                else:
                    LOGGER.debug(
                        "[%s] Skipping test of RTSP stream as Camera Account is the same.",
                        ip_address,
                    )
                    rtspStreamWorks = True

                # check if control works with the Camera Account
                if CLOUD_PASSWORD not in user_input and rtspStreamWorks:
                    if (
                        self.config_entry.data[CONF_PASSWORD] != password
                        or self.config_entry.data[CONF_USERNAME] != username
                        or self.config_entry.data[CONF_IP_ADDRESS] != ip_address
                        or self.config_entry.data[CLOUD_PASSWORD] != cloud_password
                    ):
                        LOGGER.debug(
                            "[%s] Testing control of camera using Camera Account.",
                            ip_address,
                        )
                        try:
                            await self.hass.async_add_executor_job(
                                registerController, ip_address, username, password
                            )
                            LOGGER.debug(
                                "[%s] Camera Account works for control.",
                                ip_address,
                            )
                        except Exception as e:
                            LOGGER.error(e)
                            raise Exception("Camera requires cloud password")
                    else:
                        LOGGER.debug(
                            "[%s] Skipping test of control using Camera Account since IP address, cloud password nor Camera Account changed.",
                            ip_address,
                        )
                else:
                    LOGGER.debug(
                        "[%s] Skipping test of control using Camera Account since cloud password is provided.",
                        ip_address,
                    )

                ipChanged = self.config_entry.data[CONF_IP_ADDRESS] != ip_address

                if ipChanged:
                    LOGGER.debug("[%s] IP Changed, cleaning up devices...", ip_address)
                    device_registry = device_registry_async_get(self.hass)
                    for deviceID in device_registry.devices:
                        device = device_registry.devices[deviceID]
                        LOGGER.debug("[%s] Removing device %s.", ip_address, deviceID)
                        if (
                            len(device.config_entries)
                            and list(device.config_entries)[0]
                            == self.config_entry.entry_id
                        ):
                            device_registry.async_remove_device(device.id)
                else:
                    LOGGER.debug(
                        "[%s] Skipping removal of devices since IP address did not change.",
                        ip_address,
                    )

                LOGGER.debug(
                    "[%s] Updating entry.",
                    ip_address,
                )

                allConfigData = {**self.config_entry.data}
                allConfigData[ENABLE_STREAM] = enable_stream
                allConfigData[ENABLE_MOTION_SENSOR] = enable_motion_sensor
                allConfigData[ENABLE_WEBHOOKS] = enable_webhooks
                allConfigData[CONF_IP_ADDRESS] = ip_address
                allConfigData[CONF_USERNAME] = username
                allConfigData[CONF_PASSWORD] = password
                allConfigData[CLOUD_PASSWORD] = cloud_password
                allConfigData[ENABLE_TIME_SYNC] = enable_time_sync
                allConfigData[CONF_EXTRA_ARGUMENTS] = extra_arguments
                allConfigData[CONF_CUSTOM_STREAM] = custom_stream
                allConfigData[CONF_RTSP_TRANSPORT] = rtsp_transport
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=ip_address,
                    data=allConfigData,
                )
                if ipChanged:
                    LOGGER.debug(
                        "[%s] IP Changed, reloading entry...",
                        ip_address,
                    )
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                else:
                    LOGGER.debug(
                        "[%s] Skipping reload of entry.",
                        ip_address,
                    )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif str(e) == "Invalid authentication data":
                    errors["base"] = "invalid_auth"
                elif "Temporary Suspension" in str(e):
                    errors["base"] = "account_suspended"
                elif str(e) == "Incorrect cloud password":
                    errors["base"] = "invalid_auth_cloud"
                elif str(e) == "Camera requires cloud password":
                    errors["base"] = "camera_requires_admin"
                elif str(e) == "Incorrect sound detection peak value.":
                    errors["base"] = "incorrect_peak_value"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, description={"suggested_value": ip_address}
                    ): str,
                    vol.Required(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                    vol.Optional(
                        CLOUD_PASSWORD, description={"suggested_value": cloud_password}
                    ): str,
                    vol.Optional(
                        ENABLE_MOTION_SENSOR,
                        description={"suggested_value": enable_motion_sensor},
                    ): bool,
                    vol.Optional(
                        ENABLE_WEBHOOKS,
                        description={"suggested_value": enable_webhooks},
                    ): bool,
                    vol.Optional(
                        ENABLE_TIME_SYNC,
                        description={"suggested_value": enable_time_sync},
                    ): bool,
                    vol.Optional(
                        ENABLE_STREAM,
                        description={"suggested_value": enable_stream},
                    ): bool,
                    vol.Optional(
                        CONF_EXTRA_ARGUMENTS,
                        description={"suggested_value": extra_arguments},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM,
                        description={"suggested_value": custom_stream},
                    ): str,
                    vol.Optional(
                        CONF_RTSP_TRANSPORT,
                        description={"suggested_value": rtsp_transport},
                    ): vol.In(RTSP_TRANS_PROTOCOLS),
                }
            ),
            errors=errors,
        )
