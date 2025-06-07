from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.storage import Store

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, ENABLE_MEDIA_SYNC, MEDIA_SYNC_HOURS
from .tapo.entities import TapoSwitchEntity
from .utils import check_and_create, getColdDirPathForEntry, getEntryStorageFile


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up switches")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    switches = []

    async def setupEntities(entry):
        entry_storage = Store(hass, version=1, key=getEntryStorageFile(config_entry))
        entry_stored_data = await entry_storage.async_load()
        switches = []
        tapoPrivacySwitch = await check_and_create(
            entry, hass, TapoPrivacySwitch, "getPrivacyMode", config_entry
        )
        if tapoPrivacySwitch:
            LOGGER.debug("Adding tapoPrivacySwitch...")
            switches.append(tapoPrivacySwitch)

        if entry_stored_data is None or ENABLE_MEDIA_SYNC not in entry_stored_data:
            await entry_storage.async_save({ENABLE_MEDIA_SYNC: False})
            entry_stored_data = await entry_storage.async_load()

        if (
            "alert_event_types" in entry["camData"]
            and entry["camData"]["alert_event_types"]
        ):
            for alertEventType in entry["camData"]["alert_event_types"]:
                switches.append(
                    TapoAlarmEventTypeSwitch(
                        entry, hass, config_entry, alertEventType["name"]
                    )
                )

        if entry["controller"].isKLAP is False:
            tapoEnableMediaSyncSwitch = TapoEnableMediaSyncSwitch(
                entry,
                hass,
                config_entry,
                entry_storage,
                entry_stored_data[ENABLE_MEDIA_SYNC],
            )
            if tapoEnableMediaSyncSwitch:
                LOGGER.debug("Adding TapoEnableMediaSyncSwitch...")
                switches.append(tapoEnableMediaSyncSwitch)

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

        if "led" in entry["camData"] and entry["camData"]["led"] is not None:
            tapoIndicatorLedSwitch = TapoIndicatorLedSwitch(entry, hass, config_entry)
            LOGGER.debug("Adding tapoIndicatorLedSwitch...")
            switches.append(tapoIndicatorLedSwitch)

        if (
            "record_audio" in entry["camData"]
            and entry["camData"]["record_audio"] is not None
        ):
            tapoRecordAudioSwitch = TapoRecordAudioSwitch(entry, hass, config_entry)
            LOGGER.debug("Adding tapoRecordAudioSwitch...")
            switches.append(tapoRecordAudioSwitch)

        if (
            "diagnose_mode" in entry["camData"]
            and entry["camData"]["diagnose_mode"] is not None
            and "diagnose_mode" in entry["camData"]["diagnose_mode"]
            and entry["camData"]["diagnose_mode"]["diagnose_mode"] is not None
        ):
            tapoDiagnoseModeSwitch = TapoDiagnoseModeSwitch(entry, hass, config_entry)
            LOGGER.debug("Adding tapoDiagnoseModeSwitch...")
            switches.append(tapoDiagnoseModeSwitch)

        if (
            "smart_track_config" in entry["camData"]
            and entry["camData"]["smart_track_config"] is not None
            and isinstance(entry["camData"]["smart_track_config"], dict)
        ):
            for smartTrackType in entry["camData"]["smart_track_config"]:
                tapoSmartTrackType = TapoSmartTrackSwitch(
                    entry, hass, config_entry, smartTrackType
                )
                LOGGER.debug("Adding tapoCoverSwitch " + smartTrackType + "...")
                switches.append(tapoSmartTrackType)

        if (
            "cover_config" in entry["camData"]
            and entry["camData"]["cover_config"] is not None
            and "enabled" in entry["camData"]["cover_config"]
            and entry["camData"]["cover_config"]["enabled"] is not None
        ):
            tapoCoverSwitch = TapoCoverSwitch(entry, hass, config_entry)
            LOGGER.debug("Adding tapoCoverSwitch...")
            switches.append(tapoCoverSwitch)

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
        if (
            "chimeAlarmConfigurations" in entry["camData"]
            and entry["camData"]["chimeAlarmConfigurations"] is not None
            and len(entry["camData"]["chimeAlarmConfigurations"]) > 0
        ):
            for macAddress in entry["camData"]["chimeAlarmConfigurations"]:
                tapoChimeRingtoneSwitch = TapoChimeRingtoneSwitch(
                    entry, hass, config_entry, macAddress
                )
                switches.append(tapoChimeRingtoneSwitch)
        if (
            "videoCapability" in entry["camData"]
            and entry["camData"]["videoCapability"] is not None
            and entry["camData"]["videoCapability"] is not False
            and "video_capability" in entry["camData"]["videoCapability"]
            and "main" in entry["camData"]["videoCapability"]["video_capability"]
            and "hdrs"
            in entry["camData"]["videoCapability"]["video_capability"]["main"]
            and "videoQualities" in entry["camData"]
            and "video" in entry["camData"]["videoQualities"]
            and "main" in entry["camData"]["videoQualities"]["video"]
            and "hdr" in entry["camData"]["videoQualities"]["video"]["main"]
        ):
            tapoHDRSwitch = await check_and_create(
                entry,
                hass,
                TapoHDRSwitch,
                "getVideoQualities",
                config_entry,
            )
            if tapoHDRSwitch:
                LOGGER.debug("Adding tapoHDRSwitch...")
                switches.append(tapoHDRSwitch)

        return switches

    switches = await setupEntities(entry)

    for childDevice in entry["childDevices"]:
        switches.extend(await setupEntities(childDevice))

    if switches:
        LOGGER.debug("Adding switch entities...")
        async_add_entities(switches)
    else:
        LOGGER.debug("No switch entities available.")


class TapoEnableMediaSyncSwitch(TapoSwitchEntity):
    def __init__(
        self,
        entry: dict,
        hass: HomeAssistant,
        config_entry,
        entry_storage: Store,
        savedValue: bool,
    ):
        self._attr_extra_state_attributes = {}
        TapoSwitchEntity.__init__(
            self,
            "Media Sync",
            entry,
            hass,
            config_entry,
            "mdi:sync",
        )
        self._entry_storage = entry_storage
        self._attr_state = "on" if savedValue else "off"
        hass.data[DOMAIN][config_entry.entry_id][ENABLE_MEDIA_SYNC] = savedValue

    async def async_turn_on(self) -> None:
        await self._entry_storage.async_save({ENABLE_MEDIA_SYNC: True})
        self._hass.data[DOMAIN][self._config_entry.entry_id][ENABLE_MEDIA_SYNC] = True
        self._attr_state = "on"

    async def async_turn_off(self) -> None:
        await self._entry_storage.async_save({ENABLE_MEDIA_SYNC: False})
        self._hass.data[DOMAIN][self._config_entry.entry_id][ENABLE_MEDIA_SYNC] = False
        self._attr_state = "off"

    def updateTapo(self, camData):
        mediaSyncHours = self._config_entry.data.get(MEDIA_SYNC_HOURS)
        self._attr_extra_state_attributes["sync_hours"] = mediaSyncHours
        self._attr_extra_state_attributes["storage_path"] = getColdDirPathForEntry(
            self._hass, self._config_entry.entry_id
        )


class TapoChimeRingtoneSwitch(TapoSwitchEntity):
    def __init__(
        self,
        entry: dict,
        hass: HomeAssistant,
        config_entry,
        macAddress: str,
    ):
        self.macAddress = macAddress
        TapoSwitchEntity.__init__(
            self,
            f"{macAddress} - Chime Ringtone",
            entry,
            hass,
            config_entry,
            "mdi:bell-ring",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setChimeAlarmConfigure, self.macAddress, True
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setChimeAlarmConfigure, self.macAddress, False
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if (
            not camData
            or "chimeAlarmConfigurations" not in camData
            or len(camData["chimeAlarmConfigurations"]) == 0
            or self.macAddress not in camData["chimeAlarmConfigurations"]
        ):
            self._attr_state = STATE_UNAVAILABLE
        else:
            chimeData = camData["chimeAlarmConfigurations"][self.macAddress]
            if "on_off" not in chimeData:
                self._attr_is_on = False
            else:
                self._attr_is_on = chimeData["on_off"] == 1
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoHDRSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "HDR",
            entry,
            hass,
            config_entry,
            "mdi:hdr",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setHDR,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setHDR,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if (
            not camData
            or "videoQualities" not in camData
            or "video" not in camData["videoQualities"]
            or "main" not in camData["videoQualities"]["video"]
            or "hdr" not in camData["videoQualities"]["video"]["main"]
        ):
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = camData["videoQualities"]["video"]["main"]["hdr"] == "1"
            self._attr_state = "on" if self._attr_is_on else "off"


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


class TapoAlarmEventTypeSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry, eventType: str):
        self.eventType = eventType
        TapoSwitchEntity.__init__(
            self,
            f"Trigger alarm on {eventType}",
            entry,
            hass,
            config_entry,
            "mdi:exclamation",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setAlertEventType,
            self.eventType,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setAlertEventType,
            self.eventType,
            False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            if "alert_event_types" in camData and camData["alert_event_types"]:
                for alertEventType in camData["alert_event_types"]:
                    if alertEventType["name"] == self.eventType:
                        self._attr_is_on = alertEventType["enabled"] == "on"
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


class TapoSmartTrackSwitch(TapoSwitchEntity):
    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry, typeOfSmartTrack: str
    ):
        self.typeOfSmartTrack = typeOfSmartTrack

        entityName = typeOfSmartTrack
        if entityName.endswith("_enabled"):
            entityName = entityName[:-8]  # Remove "_enabled"
        entityName = entityName.capitalize()
        TapoSwitchEntity.__init__(
            self,
            "Smart Track - " + entityName,
            entry,
            hass,
            config_entry,
            "mdi:eye-lock",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setSmartTrackConfig,
            self.typeOfSmartTrack,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setSmartTrackConfig,
            self.typeOfSmartTrack,
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
            self._attr_is_on = (
                camData["smart_track_config"][self.typeOfSmartTrack] == "on"
            )
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoCoverSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Privacy Zones", entry, hass, config_entry, "mdi:eye-lock"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setCoverConfig,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setCoverConfig,
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
            self._attr_is_on = camData["cover_config"]["enabled"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoDiagnoseModeSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Diagnose Mode", entry, hass, config_entry, "mdi:tools"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setDiagnoseMode,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setDiagnoseMode,
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
            self._attr_is_on = camData["diagnose_mode"]["diagnose_mode"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoRecordAudioSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Record Audio", entry, hass, config_entry, "mdi:microphone"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setRecordAudio,
            True,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setRecordAudio,
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
            self._attr_is_on = camData["record_audio"]
            self._attr_state = "on" if self._attr_is_on else "off"


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
