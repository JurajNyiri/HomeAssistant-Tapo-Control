from homeassistant.core import HomeAssistant

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import STATE_UNAVAILABLE

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoButtonEntity
from .utils import syncTime, check_and_create, result_has_error


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up buttons")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        buttons = []
        if not entry["isChild"]:
            buttons.append(TapoRebootButton(entry, hass, config_entry))
            if entry["controller"].isKLAP is False:
                buttons.append(TapoFormatButton(entry, hass, config_entry))

            tapoStartManualAlarmButton = await check_and_create(
                entry, hass, TapoStartManualAlarmButton, "getAlarm", config_entry
            )
            if tapoStartManualAlarmButton:
                LOGGER.debug("Adding tapoStartManualAlarmButton...")
                buttons.append(tapoStartManualAlarmButton)

            tapoStopManualAlarmButton = await check_and_create(
                entry, hass, TapoStopManualAlarmButton, "getAlarm", config_entry
            )
            if tapoStopManualAlarmButton:
                LOGGER.debug("Adding tapoStopManualAlarmButton...")
                buttons.append(tapoStopManualAlarmButton)

            if not entry["isParent"] and entry["controller"].isKLAP is False:
                buttons.append(TapoSyncTimeButton(entry, hass, config_entry))

        tapoCalibrateButton = await check_and_create(
            entry, hass, TapoCalibrateButton, "getPresets", config_entry
        )
        if tapoCalibrateButton:
            buttons.append(tapoCalibrateButton)
            buttons.append(TapoMoveUpButton(entry, hass, config_entry))
            buttons.append(TapoMoveDownButton(entry, hass, config_entry))
            buttons.append(TapoMoveRightButton(entry, hass, config_entry))
            buttons.append(TapoMoveLeftButton(entry, hass, config_entry))
        else:
            LOGGER.info("Buttons: Camera does not support movement.")

        if (
            "chimeAlarmConfigurations" in entry["camData"]
            and entry["camData"]["chimeAlarmConfigurations"] is not None
            and len(entry["camData"]["chimeAlarmConfigurations"]) > 0
        ):
            buttons.append(TapoChimeRing(entry, hass, config_entry))

        return buttons

    buttons = await setupEntities(entry)

    for childDevice in entry["childDevices"]:
        buttons.extend(await setupEntities(childDevice))

    async_add_entities(buttons)


class TapoChimeRing(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Play Chime", entry, hass, "mdi:home-sound-out")

    async def async_press(self) -> None:
        type = self._entry["chime_play_type"]
        volume = self._entry["chime_play_volume"]
        duration = self._entry["chime_play_duration"]

        await self._hass.async_add_executor_job(
            self._controller.playAlarm, duration, type, volume
        )

    @property
    def entity_category(self):
        return None


class TapoRebootButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Reboot", entry, hass)

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.reboot)

    @property
    def device_class(self) -> str:
        return ButtonDeviceClass.RESTART

    @property
    def entity_category(self):
        return EntityCategory.CONFIG


class TapoFormatButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Format SD Card", entry, hass, "mdi:eraser")

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.format)

    @property
    def entity_category(self):
        return EntityCategory.CONFIG


class TapoSyncTimeButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._entry_id = config_entry.entry_id
        self._attr_extra_state_attributes = {}
        TapoButtonEntity.__init__(
            self,
            "Sync Time",
            entry,
            hass,
            "mdi:timer-sync-outline",
        )

    def updateTapo(self, camData):
        device_mgmt = self._hass.data[DOMAIN][self._entry_id]["onvifManagement"]
        if device_mgmt:
            self._attr_state = None
        else:
            self._attr_state = STATE_UNAVAILABLE

    async def async_press(self) -> None:
        await syncTime(self._hass, self._entry_id)

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    def updateTapo(self, camData):
        if (
            not camData
            or not self._hass.data[DOMAIN][self._entry_id]["onvifManagement"]
        ):
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None
        if camData:
            if "clock_data" in camData and camData["clock_data"]:
                self._attr_extra_state_attributes["clock_data"] = {}
                if "local_time" in camData["clock_data"]:
                    self._attr_extra_state_attributes["clock_data"]["local_time"] = (
                        camData["clock_data"]["local_time"]
                    )
                if "seconds_from_1970" in camData["clock_data"]:
                    self._attr_extra_state_attributes["clock_data"][
                        "seconds_from_1970"
                    ] = camData["clock_data"]["seconds_from_1970"]
            if "dst_data" in camData and camData["dst_data"]:
                self._attr_extra_state_attributes["dst_data"] = {}
                filtered_obj = {
                    key: value
                    for key, value in camData["dst_data"].items()
                    if not key.startswith(".")
                }
                self._attr_extra_state_attributes["dst_data"].update(filtered_obj)


class TapoStartManualAlarmButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(
            self, "Manual Alarm Start", entry, hass, "mdi:alarm-light-outline"
        )

    async def async_press(self) -> None:
        result = False
        result2 = False
        try:
            result = await self._hass.async_add_executor_job(
                self._controller.startManualAlarm,
            )
        except Exception as e:
            LOGGER.debug(e)

        try:
            result2 = await self._hass.async_add_executor_job(
                self._controller.setSirenStatus, True
            )
        except Exception as e:
            LOGGER.debug(e)

        if result_has_error(result) and result_has_error(result2):
            if self.sirenType is not None:
                try:
                    result3 = await self._hass.async_add_executor_job(
                        self._controller.testUsrDefAudio, self.sirenType, True
                    )
                    if result_has_error(result3):
                        raise Exception("Camera does not support triggering the siren.")
                except Exception:
                    raise Exception("Camera does not support triggering the siren.")
            else:
                raise Exception("Camera does not support triggering the siren.")

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self.camData = STATE_UNAVAILABLE
        else:
            if (
                "alarm_config" in camData
                and camData["alarm_config"]
                and "siren_type" in camData["alarm_config"]
                and camData["alarm_config"]["siren_type"]
            ):
                self.sirenType = camData["alarm_config"]["siren_type"]


class TapoStopManualAlarmButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self.sirenType = None
        TapoButtonEntity.__init__(
            self,
            "Manual Alarm Stop",
            entry,
            hass,
            "mdi:alarm-light-off-outline",
        )

    async def async_press(self) -> None:
        result = False
        result2 = False
        try:
            result = await self._hass.async_add_executor_job(
                self._controller.stopManualAlarm,
            )
        except Exception as e:
            LOGGER.debug(e)

        try:
            result2 = await self._hass.async_add_executor_job(
                self._controller.setSirenStatus, False
            )
        except Exception as e:
            LOGGER.debug(e)

        if result_has_error(result) and result_has_error(result2):
            if self.sirenType is not None:
                try:
                    result3 = await self._hass.async_add_executor_job(
                        self._controller.testUsrDefAudio, self.sirenType, False
                    )
                    if result_has_error(result3):
                        self._attr_available = False
                        raise Exception("Camera does not support triggering the siren.")
                except Exception:
                    raise Exception("Camera does not support triggering the siren.")
            else:
                raise Exception("Camera does not support triggering the siren.")

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self.camData = STATE_UNAVAILABLE
        else:
            if (
                "alarm_config" in camData
                and camData["alarm_config"]
                and "siren_type" in camData["alarm_config"]
                and camData["alarm_config"]["siren_type"]
            ):
                self.sirenType = camData["alarm_config"]["siren_type"]


class TapoCalibrateButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Calibrate", entry, hass)

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.calibrateMotor)

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None


class TapoMoveUpButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Move Up", entry, hass, "mdi:arrow-up")

    async def async_press(self) -> None:
        degrees = self._entry["movement_angle"]
        await self._hass.async_add_executor_job(self._controller.moveMotor, 0, degrees)
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None


class TapoMoveDownButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Move Down", entry, hass, "mdi:arrow-down")

    async def async_press(self) -> None:
        degrees = self._entry["movement_angle"]
        await self._hass.async_add_executor_job(self._controller.moveMotor, 0, -degrees)
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None


class TapoMoveRightButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Move Right", entry, hass, "mdi:arrow-right")

    async def async_press(self) -> None:
        degrees = self._entry["movement_angle"]
        await self._hass.async_add_executor_job(self._controller.moveMotor, degrees, 0)
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None


class TapoMoveLeftButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoButtonEntity.__init__(self, "Move Left", entry, hass, "mdi:arrow-left")

    async def async_press(self) -> None:
        degrees = self._entry["movement_angle"]
        await self._hass.async_add_executor_job(self._controller.moveMotor, -degrees, 0)
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = None
