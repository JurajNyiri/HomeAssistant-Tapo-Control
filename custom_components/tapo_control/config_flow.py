import voluptuous as vol
import os
import re

from homeassistant.core import callback

from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.config_entries import HANDLERS, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EMAIL,
)
from homeassistant.helpers.device_registry import async_get as device_registry_async_get
from homeassistant.helpers.selector import selector

from .utils import (
    getCamData,
    getIP,
    registerController,
    isRtspStreamWorking,
    areCameraPortsOpened,
    isOpen,
    isKLAP,
)
from .const import (
    CLOUD_USERNAME,
    CONF_SKIP_RTSP,
    DOMAIN,
    CONTROL_PORT,
    ENABLE_MOTION_SENSOR,
    ENABLE_STREAM,
    ENABLE_SOUND_DETECTION,
    ENABLE_WEBHOOKS,
    IS_KLAP_DEVICE,
    LOGGER,
    CLOUD_PASSWORD,
    ENABLE_TIME_SYNC,
    MEDIA_SYNC_COLD_STORAGE_PATH,
    MEDIA_SYNC_HOURS,
    MEDIA_VIEW_DAYS_ORDER,
    MEDIA_VIEW_DAYS_ORDER_OPTIONS,
    MEDIA_VIEW_RECORDINGS_ORDER,
    MEDIA_VIEW_RECORDINGS_ORDER_OPTIONS,
    REPORTED_IP_ADDRESS,
    DOORBELL_UDP_DISCOVERED,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_RESET,
    CONF_CUSTOM_STREAM_HD,
    CONF_CUSTOM_STREAM_SD,
    CONF_CUSTOM_STREAM_6,
    CONF_CUSTOM_STREAM_7,
    HAS_STREAM_6,
    HAS_STREAM_7,
    CONF_RTSP_TRANSPORT,
    RTSP_TRANS_PROTOCOLS,
    TAPO_PREFIXES,
    TIME_SYNC_DST,
    TIME_SYNC_DST_DEFAULT,
    TIME_SYNC_NDST,
    TIME_SYNC_NDST_DEFAULT,
    UPDATE_INTERVAL_BATTERY_DEFAULT,
    UPDATE_INTERVAL_MAIN,
    UPDATE_INTERVAL_BATTERY,
    UPDATE_INTERVAL_MAIN_DEFAULT,
)


@HANDLERS.register(DOMAIN)
class FlowHandler(ConfigFlow):
    """Handle a config flow."""

    VERSION = 25

    def __init__(self):
        self.tapoHasStream6 = False
        self.tapoHasStream7 = False

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
        controlPort = self.reauth_entry.data[CONTROL_PORT]
        if not areCameraPortsOpened(host, controlPort=controlPort):
            LOGGER.debug(
                "[REAUTH][%s] Some of the required ports are closed.",
                host,
            )
            self.tapoHost = host
            self.tapoControlPort = controlPort
            self.tapoUsername = ""
            self.tapoPassword = ""
            return await self.async_step_reauth_confirm_cloud()
        else:
            LOGGER.debug(
                "[REAUTH][%s] All camera ports are opened, proceeding to requesting Camera Account.",
                host,
            )
            self.tapoHost = host
            self.tapoControlPort = controlPort
            return await self.async_step_reauth_confirm_stream()

    async def async_step_reauth_confirm_stream(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        errors = {}
        tapoHost = self.reauth_entry.data[CONF_IP_ADDRESS]
        controlPort = self.reauth_entry.data[CONTROL_PORT]
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
                    self.hass, tapoHost, username, password
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
                        data=allConfigData,
                    )
                    try:
                        LOGGER.debug(
                            "[REAUTH][%s] Testing control of camera using Camera Account.",
                            tapoHost,
                        )
                        await self.hass.async_add_executor_job(
                            registerController,
                            tapoHost,
                            controlPort,
                            username,
                            password,
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
                            raise e from e
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
        controlPort = self.reauth_entry.data[CONTROL_PORT]
        cloudPassword = self.reauth_entry.data[CLOUD_PASSWORD]
        if user_input is not None:
            cloudPassword = user_input[CLOUD_PASSWORD]
            try:
                LOGGER.debug(
                    "[REAUTH][%s] Testing control of camera using Cloud Account.",
                    tapoHost,
                )
                await self.hass.async_add_executor_job(
                    registerController, tapoHost, controlPort, "admin", cloudPassword
                )
                LOGGER.debug(
                    "[REAUTH][%s] Cloud Account works for control.",
                    tapoHost,
                )
                allConfigData = {**self.reauth_entry.data}
                allConfigData[CLOUD_PASSWORD] = cloudPassword
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=allConfigData
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
        already_configured = self._async_host_already_configured(
            dhcp_discovery.ip, 443
        ) or self._async_host_already_configured(dhcp_discovery.ip, 80)
        if already_configured:
            LOGGER.debug("[ADD DEVICE][%s] Already discovered.", dhcp_discovery.ip)
            return self.async_abort(reason="already_configured")

        if not any(
            re.match(pattern, dhcp_discovery.hostname, re.IGNORECASE)
            for pattern in TAPO_PREFIXES
        ):
            LOGGER.debug("[ADD DEVICE][%s] Not a tapo device.", dhcp_discovery.ip)
            return self.async_abort(reason="not_tapo_device")

        mac_address = dhcp_discovery.macaddress
        await self.async_set_unique_id(mac_address)
        self.context.update({"title_placeholders": {"name": dhcp_discovery.ip}})
        self.tapoHost = dhcp_discovery.ip
        isKLAPResult = await self.hass.async_add_executor_job(
            isKLAP, self.tapoHost, 80, 5
        )
        if isKLAPResult:
            self.tapoControlPort = 80
            LOGGER.debug(
                "[ADD DEVICE][%s] Initiating config flow by discovery (klap).",
                dhcp_discovery.ip,
            )
            return await self.async_step_auth_klap()
        else:
            self.tapoControlPort = 443
            LOGGER.debug(
                "[ADD DEVICE][%s] Initiating config flow by discovery (camera).",
                dhcp_discovery.ip,
            )
            return await self.async_step_auth()

    @callback
    def _async_host_already_configured(self, host, port):
        """See if we already have an entry matching the host."""
        for entry in self._async_current_entries():
            if (
                entry.data.get(CONF_IP_ADDRESS) == host
                and entry.data.get(CONTROL_PORT) == port
            ):
                return True
            elif (
                entry.data.get(REPORTED_IP_ADDRESS) == host
                and entry.data.get(CONTROL_PORT) == port
            ):
                return True
        return False

    async def _detect_additional_streams(self, host, username, password):
        for stream, attr in (
            ("stream6", "tapoHasStream6"),
            ("stream7", "tapoHasStream7"),
        ):
            try:
                stream_supported = await isRtspStreamWorking(
                    self.hass, host, username, password, stream=stream
                )
                setattr(self, attr, stream_supported)
                LOGGER.debug(
                    "[ADD DEVICE][%s] Probe for %s returned %s.",
                    host,
                    stream,
                    stream_supported,
                )
            except Exception as err:
                setattr(self, attr, False)
                LOGGER.debug(
                    "[ADD DEVICE][%s] Probe for %s failed: %s",
                    host,
                    stream,
                    err,
                )

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
            controlPort = self.tapoControlPort
            cloud_password = self.tapoCloudPassword
            cloud_username = self.tapoCloudUsername
            if cloud_username != "admin":
                isKlapDevice = True
            else:
                isKlapDevice = False
            username = self.tapoUsername
            password = self.tapoPassword
            LOGGER.debug(
                "[ADD DEVICE][%s] Saving entry.",
                self.tapoHost,
            )
            await self.async_set_unique_id(
                DOMAIN
                + (self.reportedIPAddress if self.reportedIPAddress else host)
                + str(self.tapoControlPort)
            )
            if isKlapDevice:
                tapoController = await self.hass.async_add_executor_job(
                    registerController,
                    self.tapoHost,
                    self.tapoControlPort,
                    cloud_username,
                    cloud_password,
                )
                camData = await getCamData(self.hass, tapoController)
                reported_ip_address = getIP(camData)
                return self.async_create_entry(
                    title=host,
                    data={
                        MEDIA_VIEW_DAYS_ORDER: "Ascending",
                        MEDIA_VIEW_RECORDINGS_ORDER: "Ascending",
                        MEDIA_SYNC_HOURS: "",
                        MEDIA_SYNC_COLD_STORAGE_PATH: "",
                        ENABLE_MOTION_SENSOR: False,
                        ENABLE_WEBHOOKS: False,
                        ENABLE_STREAM: False,
                        ENABLE_TIME_SYNC: False,
                        CONF_IP_ADDRESS: host,
                        REPORTED_IP_ADDRESS: reported_ip_address,
                        CONTROL_PORT: controlPort,
                        CONF_USERNAME: cloud_username,
                        CONF_PASSWORD: cloud_password,
                        CLOUD_PASSWORD: "",
                        ENABLE_SOUND_DETECTION: False,
                        SOUND_DETECTION_PEAK: -30,
                        SOUND_DETECTION_DURATION: 1,
                        SOUND_DETECTION_RESET: 10,
                        CONF_EXTRA_ARGUMENTS: "",
                        CONF_CUSTOM_STREAM_HD: "",
                        CONF_CUSTOM_STREAM_SD: "",
                        CONF_CUSTOM_STREAM_6: "",
                        CONF_CUSTOM_STREAM_7: "",
                        CONF_RTSP_TRANSPORT: "tcp",
                        UPDATE_INTERVAL_MAIN: UPDATE_INTERVAL_MAIN_DEFAULT,
                        UPDATE_INTERVAL_BATTERY: UPDATE_INTERVAL_BATTERY_DEFAULT,
                        IS_KLAP_DEVICE: True,
                    },
                )
            else:
                return self.async_create_entry(
                    title=host,
                    data={
                        MEDIA_VIEW_DAYS_ORDER: "Ascending",
                        MEDIA_VIEW_RECORDINGS_ORDER: "Ascending",
                        MEDIA_SYNC_HOURS: "",
                        MEDIA_SYNC_COLD_STORAGE_PATH: "",
                        ENABLE_MOTION_SENSOR: enable_motion_sensor,
                        ENABLE_WEBHOOKS: enable_webhooks,
                        ENABLE_STREAM: enable_stream,
                        ENABLE_TIME_SYNC: enable_time_sync,
                        CONF_IP_ADDRESS: host,
                        CONTROL_PORT: controlPort,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CLOUD_PASSWORD: cloud_password,
                        HAS_STREAM_6: self.tapoHasStream6,
                        HAS_STREAM_7: self.tapoHasStream7,
                        REPORTED_IP_ADDRESS: self.reportedIPAddress,
                        ENABLE_SOUND_DETECTION: enable_sound_detection,
                        SOUND_DETECTION_PEAK: sound_detection_peak,
                        SOUND_DETECTION_DURATION: sound_detection_duration,
                        SOUND_DETECTION_RESET: sound_detection_reset,
                        CONF_EXTRA_ARGUMENTS: extra_arguments,
                        CONF_CUSTOM_STREAM_HD: "",
                        CONF_CUSTOM_STREAM_SD: "",
                        CONF_CUSTOM_STREAM_6: "",
                        CONF_CUSTOM_STREAM_7: "",
                        CONF_RTSP_TRANSPORT: rtsp_transport,
                        UPDATE_INTERVAL_MAIN: UPDATE_INTERVAL_MAIN_DEFAULT,
                        UPDATE_INTERVAL_BATTERY: UPDATE_INTERVAL_BATTERY_DEFAULT,
                        IS_KLAP_DEVICE: False,
                        TIME_SYNC_DST: TIME_SYNC_DST_DEFAULT,
                        TIME_SYNC_NDST: TIME_SYNC_NDST_DEFAULT,
                        DOORBELL_UDP_DISCOVERED: False,
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
        if user_input is None or CONF_USERNAME not in user_input:
            cloud_username = "admin"
        cloud_password = ""
        if user_input is not None:
            try:
                LOGGER.debug(
                    "[ADD DEVICE][%s] Verifying cloud password.",
                    self.tapoHost,
                )
                if CONF_USERNAME in user_input:
                    cloud_username = user_input[CONF_USERNAME]
                cloud_password = user_input[CLOUD_PASSWORD]
                tapoController = await self.hass.async_add_executor_job(
                    registerController,
                    self.tapoHost,
                    self.tapoControlPort,
                    cloud_username,
                    cloud_password,
                )
                camData = await getCamData(self.hass, tapoController)
                self.reportedIPAddress = getIP(camData)
                LOGGER.debug(
                    "[ADD DEVICE][%s] Cloud password works for control.",
                    self.tapoHost,
                )
                self.tapoCloudPassword = cloud_password
                self.tapoCloudUsername = cloud_username
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
        if errors == {}:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CLOUD_PASSWORD, description={"suggested_value": cloud_password}
                    ): str,
                }
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, description={"suggested_value": cloud_username}
                    ): str,
                    vol.Required(
                        CLOUD_PASSWORD, description={"suggested_value": cloud_password}
                    ): str,
                }
            )
        return self.async_show_form(
            step_id="auth_cloud_password",
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_auth_klap(self, user_input=None):
        """Provide authentication data."""
        errors = {}
        email = ""
        password = ""
        host = self.tapoHost
        controlPort = self.tapoControlPort
        if user_input is not None:
            try:
                email = user_input[CONF_EMAIL]
                password = user_input[CONF_PASSWORD]
                self.tapoUsername = email
                self.tapoPassword = password
                reported_ip_address = False

                try:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Testing control of camera using KLAP Account.",
                        host,
                    )
                    tapoController = await self.hass.async_add_executor_job(
                        registerController,
                        host,
                        controlPort,
                        email,
                        password,
                    )
                    camData = await getCamData(self.hass, tapoController)
                    reported_ip_address = getIP(camData)
                    LOGGER.debug(
                        "[ADD DEVICE][%s] KLAP Account works for control.",
                        host,
                    )
                except Exception as e:
                    if str(e) == "Invalid authentication data":
                        raise Exception("Invalid authentication data")
                    elif "Temporary Suspension" in str(e):
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Temporary suspension.",
                            self.tapoHost,
                        )
                        raise Exception("temporary_suspension")
                    else:
                        LOGGER.error(e)
                        raise Exception(e)

                await self.async_set_unique_id(
                    DOMAIN
                    + (reported_ip_address if reported_ip_address else host)
                    + str(self.tapoControlPort)
                )
                return self.async_create_entry(
                    title=host,
                    data={
                        MEDIA_VIEW_DAYS_ORDER: "Ascending",
                        MEDIA_VIEW_RECORDINGS_ORDER: "Ascending",
                        MEDIA_SYNC_HOURS: "",
                        MEDIA_SYNC_COLD_STORAGE_PATH: "",
                        ENABLE_MOTION_SENSOR: False,
                        ENABLE_WEBHOOKS: False,
                        ENABLE_STREAM: False,
                        ENABLE_TIME_SYNC: False,
                        CONF_IP_ADDRESS: host,
                        REPORTED_IP_ADDRESS: reported_ip_address,
                        CONTROL_PORT: controlPort,
                        CONF_USERNAME: email,
                        CONF_PASSWORD: password,
                        CLOUD_PASSWORD: "",
                        ENABLE_SOUND_DETECTION: False,
                        SOUND_DETECTION_PEAK: -30,
                        SOUND_DETECTION_DURATION: 1,
                        SOUND_DETECTION_RESET: 10,
                        CONF_EXTRA_ARGUMENTS: "",
                        CONF_CUSTOM_STREAM_HD: "",
                        CONF_CUSTOM_STREAM_SD: "",
                        CONF_CUSTOM_STREAM_6: "",
                        CONF_CUSTOM_STREAM_7: "",
                        CONF_RTSP_TRANSPORT: "tcp",
                        UPDATE_INTERVAL_MAIN: UPDATE_INTERVAL_MAIN_DEFAULT,
                        UPDATE_INTERVAL_BATTERY: UPDATE_INTERVAL_BATTERY_DEFAULT,
                        IS_KLAP_DEVICE: True,
                    },
                )

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
            "[ADD DEVICE][%s] Showing config flow for KLAP Account.",
            host,
        )
        return self.async_show_form(
            step_id="auth_klap",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, description={"suggested_value": email}
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
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
        controlPort = 443
        if user_input is not None:
            LOGGER.debug("[ADD DEVICE] Verifying IP address")
            try:
                host = user_input[CONF_IP_ADDRESS]
                controlPort = user_input[CONTROL_PORT]

                if self._async_host_already_configured(host, controlPort):
                    LOGGER.debug("[ADD DEVICE][%s] IP:Port already configured.", host)
                    raise Exception("already_configured")

                LOGGER.debug("[ADD DEVICE][%s] Verifying port %s.", host, controlPort)
                if isOpen(host, controlPort):
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Port %s is opened, verifying access to control of camera.",
                        host,
                        controlPort,
                    )
                    try:
                        await self.hass.async_add_executor_job(
                            registerController, host, controlPort, "invalid", ""
                        )
                    except Exception as e:
                        if str(e) == "Invalid authentication data":
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Verifying ports all required camera ports.",
                                host,
                            )
                            if not areCameraPortsOpened(host, controlPort=controlPort):
                                LOGGER.debug(
                                    "[ADD DEVICE][%s] Some of the required ports are closed.",
                                    host,
                                )
                                self.tapoHost = host
                                self.tapoControlPort = controlPort
                                self.tapoUsername = ""
                                self.tapoPassword = ""
                                isKLAPResult = await self.hass.async_add_executor_job(
                                    isKLAP, host, controlPort, 5
                                )

                                if isKLAPResult:
                                    return await self.async_step_auth_klap()
                                else:
                                    return await self.async_step_auth_cloud_password()
                            else:
                                LOGGER.debug(
                                    "[ADD DEVICE][%s] All camera ports are opened, proceeding to requesting Camera Account.",
                                    host,
                                )
                                self.tapoHost = host
                                self.tapoControlPort = controlPort
                                return await self.async_step_auth()
                        elif "Temporary Suspension" in str(e):
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Temporary suspension.",
                                host,
                            )
                            raise e from e
                        else:
                            LOGGER.debug(
                                "[ADD DEVICE][%s] Camera control is not available, IP is not a Tapo device. Error: %s",
                                host,
                                str(e),
                            )
                            raise Exception("not_tapo_device")
                else:
                    LOGGER.debug(
                        "[ADD DEVICE][%s] Port %s is closed.", host, controlPort
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
                elif "Temporary Suspension:" in str(e):
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
                    vol.Required(
                        CONTROL_PORT, description={"suggested_value": controlPort}
                    ): int,
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
                        registerController,
                        self.tapoHost,
                        self.tapoControlPort,
                        "admin",
                        cloud_password,
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
        skip_rtsp = False
        host = self.tapoHost
        controlPort = self.tapoControlPort
        if user_input is not None:
            try:
                username = (
                    user_input[CONF_USERNAME] if CONF_USERNAME in user_input else ""
                )
                password = (
                    user_input[CONF_PASSWORD] if CONF_PASSWORD in user_input else ""
                )
                skip_rtsp = (
                    user_input[CONF_SKIP_RTSP]
                    if CONF_SKIP_RTSP in user_input
                    else False
                )
                if len(username) > 0 and len(password) > 0:
                    if skip_rtsp is True:
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Skipping verifying camera Account.", host
                        )
                    else:
                        LOGGER.debug("[ADD DEVICE][%s] Verifying Camera Account.", host)
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Verifying ports all required camera ports.",
                            host,
                        )
                        if not areCameraPortsOpened(host, controlPort=controlPort):
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
                            await self._detect_additional_streams(
                                host, username, password
                            )

                    self.tapoUsername = username
                    self.tapoPassword = password
                    self.tapoCloudUsername = ""
                    self.tapoCloudPassword = ""

                    try:
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Testing control of camera using Camera Account.",
                            host,
                        )
                        tapoController = await self.hass.async_add_executor_job(
                            registerController,
                            host,
                            controlPort,
                            username,
                            password,
                        )
                        LOGGER.debug(
                            "[ADD DEVICE][%s] Camera Account works for control.",
                            host,
                        )

                        camData = await getCamData(self.hass, tapoController)
                        self.reportedIPAddress = getIP(camData)
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
                            raise e from e
                        else:
                            LOGGER.error(e)
                            raise Exception(e)

                    return await self.async_step_auth_optional_cloud()
                elif skip_rtsp is False:
                    errors["base"] = "skip_rtsp_not_checked"
                else:
                    self.tapoUsername = ""
                    self.tapoPassword = ""
                    return await self.async_step_auth_cloud_password()
            except Exception as e:
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                    LOGGER.error(e)
                elif "ports_closed" in str(e):
                    errors["base"] = "ports_closed"
                elif str(e) == "Invalid authentication data":
                    errors["base"] = "invalid_auth"
                elif "Temporary Suspension:" in str(e):
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
                    vol.Optional(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                    vol.Required(
                        CONF_SKIP_RTSP, description={"suggested_value": skip_rtsp}
                    ): bool,
                }
            ),
            errors=errors,
            last_step=False,
        )


class TapoOptionsFlowHandler(OptionsFlow):
    @property
    def config_entry(self):
        return self.hass.config_entries.async_get_entry(self.handler)

    def __init__(self, config_entry):
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
                elif nextAction == "Configure update interval":
                    return await self.async_step_update_interval()
                elif nextAction == "Configure time synchronization":
                    return await self.async_step_time_sync_options()
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
                            "Configure update interval",
                            "Configure time synchronization",
                            "Configure sound sensor",
                            "Configure media",
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

    async def async_step_update_interval(self, user_input=None):
        """Manage the Tapo options."""
        LOGGER.debug(
            "[%s] Opened Tapo options - update interval",
            self.config_entry.data[CONF_IP_ADDRESS],
        )
        errors = {}
        updateIntervalMain = self.config_entry.data[UPDATE_INTERVAL_MAIN]
        updateIntervalBattery = self.config_entry.data[UPDATE_INTERVAL_BATTERY]

        allConfigData = {**self.config_entry.data}
        if user_input is not None:
            try:
                if UPDATE_INTERVAL_MAIN in user_input:
                    updateIntervalMain = user_input[UPDATE_INTERVAL_MAIN]
                else:
                    updateIntervalMain = UPDATE_INTERVAL_MAIN_DEFAULT

                if UPDATE_INTERVAL_BATTERY in user_input:
                    updateIntervalBattery = user_input[UPDATE_INTERVAL_BATTERY]
                else:
                    updateIntervalBattery = UPDATE_INTERVAL_BATTERY_DEFAULT

                allConfigData[UPDATE_INTERVAL_MAIN] = updateIntervalMain
                allConfigData[UPDATE_INTERVAL_BATTERY] = updateIntervalBattery
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=allConfigData,
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                errors["base"] = "unknown"
                LOGGER.error(e)

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        UPDATE_INTERVAL_MAIN,
                        description={"suggested_value": updateIntervalMain},
                    ): int,
                    vol.Required(
                        UPDATE_INTERVAL_BATTERY,
                        description={"suggested_value": updateIntervalBattery},
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_time_sync_options(self, user_input=None):
        """Manage the Tapo options."""
        LOGGER.debug(
            "[%s] Opened Tapo options - time sync options",
            self.config_entry.data[CONF_IP_ADDRESS],
        )
        errors = {}
        enable_time_sync = self.config_entry.data[ENABLE_TIME_SYNC]
        timeSyncDST = self.config_entry.data[TIME_SYNC_DST]
        timeSyncNDST = self.config_entry.data[TIME_SYNC_NDST]

        allConfigData = {**self.config_entry.data}
        if user_input is not None:
            try:
                if ENABLE_TIME_SYNC in user_input:
                    enable_time_sync = user_input[ENABLE_TIME_SYNC]
                else:
                    enable_time_sync = False

                if TIME_SYNC_DST in user_input:
                    timeSyncDST = user_input[TIME_SYNC_DST]
                else:
                    timeSyncDST = TIME_SYNC_DST_DEFAULT

                if TIME_SYNC_NDST in user_input:
                    timeSyncNDST = user_input[TIME_SYNC_NDST]
                else:
                    timeSyncNDST = TIME_SYNC_NDST_DEFAULT

                allConfigData[ENABLE_TIME_SYNC] = enable_time_sync
                allConfigData[TIME_SYNC_DST] = timeSyncDST
                allConfigData[TIME_SYNC_NDST] = timeSyncNDST
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=allConfigData,
                )
                self.hass.data[DOMAIN][self.config_entry.entry_id][
                    TIME_SYNC_DST
                ] = timeSyncDST
                self.hass.data[DOMAIN][self.config_entry.entry_id][
                    TIME_SYNC_NDST
                ] = timeSyncNDST
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                errors["base"] = "unknown"
                LOGGER.error(e)

        return self.async_show_form(
            step_id="time_sync_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        ENABLE_TIME_SYNC,
                        description={"suggested_value": enable_time_sync},
                    ): bool,
                    vol.Optional(
                        TIME_SYNC_DST,
                        description={"suggested_value": timeSyncDST},
                    ): int,
                    vol.Optional(
                        TIME_SYNC_NDST,
                        description={"suggested_value": timeSyncNDST},
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
        media_view_days_order = self.config_entry.data[MEDIA_VIEW_DAYS_ORDER]
        media_view_recordings_order = self.config_entry.data[
            MEDIA_VIEW_RECORDINGS_ORDER
        ]
        media_sync_hours = self.config_entry.data[MEDIA_SYNC_HOURS]
        media_sync_cold_storage_path = self.config_entry.data[
            MEDIA_SYNC_COLD_STORAGE_PATH
        ]

        allConfigData = {**self.config_entry.data}
        if user_input is not None:
            try:

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

                if media_sync_cold_storage_path != "" and not os.path.exists(
                    media_sync_cold_storage_path
                ):
                    raise Exception("Cold storage path does not exist")

                allConfigData[MEDIA_VIEW_DAYS_ORDER] = media_view_days_order
                allConfigData[MEDIA_VIEW_RECORDINGS_ORDER] = media_view_recordings_order
                allConfigData[MEDIA_SYNC_HOURS] = media_sync_hours
                allConfigData[MEDIA_SYNC_COLD_STORAGE_PATH] = (
                    media_sync_cold_storage_path
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=allConfigData,
                )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                if "Cold storage path does not exist" in str(e):
                    errors["base"] = "cold_storage_path_does_not_exist"
                else:
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
        custom_stream_hd = self.config_entry.data.get(CONF_CUSTOM_STREAM_HD, "")
        custom_stream_sd = self.config_entry.data.get(CONF_CUSTOM_STREAM_SD, "")
        custom_stream6 = self.config_entry.data.get(CONF_CUSTOM_STREAM_6, "")
        custom_stream7 = self.config_entry.data.get(CONF_CUSTOM_STREAM_7, "")
        rtsp_transport = self.config_entry.data[CONF_RTSP_TRANSPORT]
        ip_address = self.config_entry.data[CONF_IP_ADDRESS]
        controlPort = self.config_entry.data[CONTROL_PORT]
        if user_input is not None:
            try:
                if CONF_IP_ADDRESS in user_input:
                    ip_address = user_input[CONF_IP_ADDRESS]

                if CONTROL_PORT in user_input:
                    controlPort = user_input[CONTROL_PORT]

                LOGGER.debug(
                    "[%s] Verifying updated data.",
                    ip_address,
                )
                username = (
                    user_input[CONF_USERNAME] if CONF_USERNAME in user_input else ""
                )
                password = (
                    user_input[CONF_PASSWORD] if CONF_PASSWORD in user_input else ""
                )
                if len(username) == 0 or len(password) == 0:
                    username = ""
                    password = ""
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
                                registerController,
                                ip_address,
                                controlPort,
                                "admin",
                                cloud_password,
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

                if CONF_CUSTOM_STREAM_HD in user_input:
                    custom_stream_hd = user_input[CONF_CUSTOM_STREAM_HD]
                else:
                    custom_stream_hd = ""

                if CONF_CUSTOM_STREAM_SD in user_input:
                    custom_stream_sd = user_input[CONF_CUSTOM_STREAM_SD]
                else:
                    custom_stream_sd = ""

                if CONF_CUSTOM_STREAM_6 in user_input:
                    custom_stream6 = user_input[CONF_CUSTOM_STREAM_6]
                else:
                    custom_stream6 = ""

                if CONF_CUSTOM_STREAM_7 in user_input:
                    custom_stream7 = user_input[CONF_CUSTOM_STREAM_7]
                else:
                    custom_stream7 = ""

                if CONF_EXTRA_ARGUMENTS in user_input:
                    extra_arguments = user_input[CONF_EXTRA_ARGUMENTS]
                else:
                    extra_arguments = ""

                if CONF_RTSP_TRANSPORT in user_input:
                    rtsp_transport = user_input[CONF_RTSP_TRANSPORT]
                else:
                    rtsp_transport = RTSP_TRANS_PROTOCOLS[0]

                if (
                    (
                        self.config_entry.data[CONF_PASSWORD] != password
                        or self.config_entry.data[CONF_USERNAME] != username
                        or self.config_entry.data[CONF_IP_ADDRESS] != ip_address
                    )
                    and len(password) > 0
                    and len(username) > 0
                ):
                    LOGGER.debug(
                        "[%s] Testing RTSP stream.",
                        ip_address,
                    )
                    rtspStreamWorks = await isRtspStreamWorking(
                        self.hass, ip_address, username, password
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
                        or self.config_entry.data[CONTROL_PORT] != controlPort
                        or self.config_entry.data[CLOUD_PASSWORD] != cloud_password
                    ):
                        LOGGER.debug(
                            "[%s] Testing control of camera using Camera Account.",
                            ip_address,
                        )
                        try:
                            tapoController = await self.hass.async_add_executor_job(
                                registerController,
                                ip_address,
                                controlPort,
                                username,
                                password,
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

                reported_ip_address = False

                if ipChanged:
                    if tapoController is None:
                        isKLAPResult = await self.hass.async_add_executor_job(
                            isKLAP, ip_address, 80, 5
                        )
                        if cloud_password != "":
                            LOGGER.debug("Setting up controller using cloud password.")
                            tapoController = await self.hass.async_add_executor_job(
                                registerController,
                                ip_address,
                                controlPort,
                                "admin",
                                cloud_password,
                                cloud_password,
                                "",
                                None,
                                isKLAPResult,
                                self.hass,
                            )
                        else:
                            LOGGER.debug(
                                "Setting up controller using username and password."
                            )
                            tapoController = await self.hass.async_add_executor_job(
                                registerController,
                                ip_address,
                                controlPort,
                                username,
                                password,
                                "",
                                "",
                                None,
                                isKLAPResult,
                                self.hass,
                            )
                    LOGGER.debug("[%s] IP Changed, cleaning up devices...", ip_address)
                    camData = await getCamData(self.hass, tapoController)
                    reported_ip_address = getIP(camData)
                    device_registry = device_registry_async_get(self.hass)
                    devices_to_remove = []
                    for deviceID in device_registry.devices:
                        device = device_registry.devices[deviceID]
                        if (
                            len(device.config_entries)
                            and list(device.config_entries)[0]
                            == self.config_entry.entry_id
                        ):
                            devices_to_remove.append(device.id)
                    for deviceID in devices_to_remove:
                        LOGGER.debug("[%s] Removing device %s.", ip_address, deviceID)
                        device_registry.async_remove_device(deviceID)
                else:
                    LOGGER.debug(
                        "[%s] Skipping removal of devices since IP address did not change.",
                        ip_address,
                    )

                rtspEnablementChanged = (
                    len(self.config_entry.data[CONF_PASSWORD]) == 0
                    and len(self.config_entry.data[CONF_USERNAME]) == 0
                    and len(password) > 0
                    and len(username) > 0
                ) or (
                    len(self.config_entry.data[CONF_PASSWORD]) > 0
                    and len(self.config_entry.data[CONF_USERNAME]) > 0
                    and len(password) == 0
                    and len(username) == 0
                )
                if (len(password) == 0 or len(username) == 0) and (
                    enable_motion_sensor or enable_time_sync
                ):

                    enable_motion_sensor = False
                    enable_time_sync = False
                    LOGGER.warning(
                        "Turning off motion sensor and time sync as RTSP username or password are empty. These functionalities require RTSP/Onvif credentials."
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
                allConfigData[REPORTED_IP_ADDRESS] = reported_ip_address
                allConfigData[CLOUD_PASSWORD] = cloud_password
                allConfigData[ENABLE_TIME_SYNC] = enable_time_sync
                allConfigData[CONF_EXTRA_ARGUMENTS] = extra_arguments
                allConfigData[CONF_CUSTOM_STREAM_HD] = custom_stream_hd
                allConfigData[CONF_CUSTOM_STREAM_SD] = custom_stream_sd
                allConfigData[CONF_CUSTOM_STREAM_6] = custom_stream6
                allConfigData[CONF_CUSTOM_STREAM_7] = custom_stream7
                allConfigData[CONF_RTSP_TRANSPORT] = rtsp_transport
                allConfigData[CONTROL_PORT] = controlPort
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=allConfigData,
                    unique_id=DOMAIN
                    + (reported_ip_address if reported_ip_address else ip_address)
                    + str(controlPort),
                )

                if ipChanged or rtspEnablementChanged:
                    LOGGER.debug(
                        "[%s] IP or RTSP Enablement Changed, reloading entry...",
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
                        CONTROL_PORT, description={"suggested_value": controlPort}
                    ): int,
                    vol.Optional(
                        CONF_USERNAME, description={"suggested_value": username}
                    ): str,
                    vol.Optional(
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
                        ENABLE_STREAM,
                        description={"suggested_value": enable_stream},
                    ): bool,
                    vol.Optional(
                        CONF_EXTRA_ARGUMENTS,
                        description={"suggested_value": extra_arguments},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM_HD,
                        description={"suggested_value": custom_stream_hd},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM_SD,
                        description={"suggested_value": custom_stream_sd},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM_6,
                        description={"suggested_value": custom_stream6},
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_STREAM_7,
                        description={"suggested_value": custom_stream7},
                    ): str,
                    vol.Optional(
                        CONF_RTSP_TRANSPORT,
                        description={"suggested_value": rtsp_transport},
                    ): vol.In(RTSP_TRANS_PROTOCOLS),
                }
            ),
            errors=errors,
        )
