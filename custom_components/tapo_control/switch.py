from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoSwitchEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up switches")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    switches = []

    async def setupEntities(entry):
        switches = []
        tapoPrivacySwitch = await check_and_create(
            entry, hass, TapoPrivacySwitch, "getPrivacyMode", config_entry
        )
        if tapoPrivacySwitch:
            LOGGER.debug("Adding tapoPrivacySwitch...")
            switches.append(tapoPrivacySwitch)

        tapoLensDistortionCorrectionSwitch = await check_and_create(
            entry,
            hass,
            TapoLensDistortionCorrectionSwitch,
            "getLensDistortionCorrection",
            config_entry,
        )
        if tapoLensDistortionCorrectionSwitch:
            LOGGER.debug("Adding tapoLensDistortionCorrectionSwitch...")
            switches.append(tapoLensDistortionCorrectionSwitch)

        tapoIndicatorLedSwitch = await check_and_create(
            entry, hass, TapoIndicatorLedSwitch, "getLED", config_entry
        )
        if tapoIndicatorLedSwitch:
            LOGGER.debug("Adding tapoIndicatorLedSwitch...")
            switches.append(tapoIndicatorLedSwitch)

        tapoFlipSwitch = await check_and_create(
            entry, hass, TapoFlipSwitch, "getImageFlipVertical", config_entry
        )
        if tapoFlipSwitch:
            LOGGER.debug("Adding tapoFlipSwitch...")
            switches.append(tapoFlipSwitch)

        tapoAutoTrackSwitch = await check_and_create(
            entry, hass, TapoAutoTrackSwitch, "getAutoTrackTarget", config_entry
        )
        if tapoAutoTrackSwitch:
            LOGGER.debug("Adding tapoAutoTrackSwitch...")
            switches.append(tapoAutoTrackSwitch)

        tapoNotificationsSwitch = await check_and_create(
            entry,
            hass,
            TapoNotificationsSwitch,
            "getNotificationsEnabled",
            config_entry,
        )
        if tapoNotificationsSwitch:
            LOGGER.debug("Adding tapoNotificationsSwitch...")
            switches.append(tapoNotificationsSwitch)

        tapoRichNotificationsSwitch = await check_and_create(
            entry,
            hass,
            TapoRichNotificationsSwitch,
            "getNotificationsEnabled",
            config_entry,
        )
        if tapoRichNotificationsSwitch:
            LOGGER.debug("Adding tapoRichNotificationsSwitch...")
            switches.append(tapoRichNotificationsSwitch)

        tapoAutoUpgradeSwitch = await check_and_create(
            entry,
            hass,
            TapoAutoUpgradeSwitch,
            "getFirmwareAutoUpgradeConfig",
            config_entry,
        )
        if tapoAutoUpgradeSwitch:
            LOGGER.debug("Adding tapoAutoUpgradeSwitch...")
            switches.append(tapoAutoUpgradeSwitch)

        tapoRecordingPlanSwitch = await check_and_create(
            entry,
            hass,
            TapoRecordingPlanSwitch,
            "getRecordPlan",
            config_entry,
        )
        if tapoRecordingPlanSwitch:
            LOGGER.debug("Adding tapoRecordingPlanSwitch...")
            switches.append(tapoRecordingPlanSwitch)

        if (
            "microphoneMute" in entry["camData"]
            and entry["camData"]["microphoneMute"] is not None
        ):
            tapoMicrophoneMuteSwitch = await check_and_create(
                entry,
                hass,
                TapoMicrophoneMuteSwitch,
                "getAudioConfig",
                config_entry,
            )
            if tapoMicrophoneMuteSwitch:
                LOGGER.debug("Adding tapoMicrophoneMuteSwitch...")
                switches.append(tapoMicrophoneMuteSwitch)

        if (
            "microphoneNoiseCancelling" in entry["camData"]
            and entry["camData"]["microphoneNoiseCancelling"] is not None
        ):
            tapoMicrophoneNoiseCancellationSwitch = await check_and_create(
                entry,
                hass,
                TapoMicrophoneNoiseCancellationSwitch,
                "getAudioConfig",
                config_entry,
            )
            if tapoMicrophoneNoiseCancellationSwitch:
                LOGGER.debug("Adding tapoMicrophoneNoiseCancellationSwitch...")
                switches.append(tapoMicrophoneNoiseCancellationSwitch)

        return switches

    switches = await setupEntities(entry)

    for childDevice in entry["childDevices"]:
        switches.extend(await setupEntities(childDevice))

    if switches:
        LOGGER.debug("Adding switch entities...")
        async_add_entities(switches)
    else:
        LOGGER.debug("No switch entities available.")


class TapoRecordingPlanSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Record to SD Card",
            entry,
            hass,
            config_entry,
            "mdi:record-rec",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setRecordPlan,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setRecordPlan,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or "enabled" not in camData["recordPlan"]:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["recordPlan"]["enabled"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoMicrophoneMuteSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Microphone - Mute",
            entry,
            hass,
            config_entry,
            "mdi:microphone-off",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMicrophone,
            None,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMicrophone,
            None,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or "microphoneMute" not in camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["microphoneMute"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoMicrophoneNoiseCancellationSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Microphone - Noise Cancellation",
            entry,
            hass,
            config_entry,
            "mdi:microphone-settings",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMicrophone, None, None, True
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMicrophone,
            None,
            None,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or "microphoneNoiseCancelling" not in camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["microphoneNoiseCancelling"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoNotificationsSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Notifications",
            entry,
            hass,
            config_entry,
            "mdi:bell",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setNotificationsEnabled,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setNotificationsEnabled,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["notifications"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoAutoUpgradeSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Automatically Upgrade Firmware",
            entry,
            hass,
            config_entry,
            "mdi:cloud-download",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setFirmwareAutoUpgradeConfig,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setFirmwareAutoUpgradeConfig,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["autoUpgradeEnabled"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoRichNotificationsSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Rich Notifications",
            entry,
            hass,
            config_entry,
            "mdi:bell",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setNotificationsEnabled,
            None,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setNotificationsEnabled,
            None,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["rich_notifications"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoLensDistortionCorrectionSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Lens Distortion Correction",
            entry,
            hass,
            config_entry,
            "mdi:google-lens",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["lens_distrotion_correction"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoPrivacySwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(self, "Privacy", entry, hass, config_entry)

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["privacy_mode"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"
        LOGGER.debug("Updating TapoPrivacySwitch to: " + str(self._attr_state))

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:eye-off-outline"
        else:
            return "mdi:eye-outline"

    @property
    def entity_category(self):
        return None


class TapoIndicatorLedSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Indicator LED", entry, hass, config_entry, "mdi:car-light-high"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["led"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoFlipSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Flip", entry, hass, config_entry, "mdi:flip-vertical"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["flip"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoAutoTrackSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Auto Track", entry, hass, config_entry, "mdi:radar"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["auto_track"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"
