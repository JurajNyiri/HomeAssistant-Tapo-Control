from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoSelectEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up selects")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        selects = []

        tapoNightVisionSelect = await check_and_create(
            entry, hass, TapoNightVisionSelect, "getDayNightMode", config_entry
        )
        if tapoNightVisionSelect:
            LOGGER.debug("Adding tapoNightVisionSelect...")
            selects.append(tapoNightVisionSelect)

        tapoLightFrequencySelect = await check_and_create(
            entry, hass, TapoLightFrequencySelect, "getLightFrequencyMode", config_entry
        )
        if tapoLightFrequencySelect:
            LOGGER.debug("Adding tapoLightFrequencySelect...")
            selects.append(tapoLightFrequencySelect)

        tapoAutomaticAlarmModeSelect = await check_and_create(
            entry, hass, TapoAutomaticAlarmModeSelect, "getAlarm", config_entry
        )
        if tapoAutomaticAlarmModeSelect:
            LOGGER.debug("Adding tapoAutomaticAlarmModeSelect...")
            selects.append(tapoAutomaticAlarmModeSelect)

        tapoMotionDetectionSelect = await check_and_create(
            entry, hass, TapoMotionDetectionSelect, "getMotionDetection", config_entry
        )
        if tapoMotionDetectionSelect:
            LOGGER.debug("Adding TapoMotionDetectionSelect...")
            selects.append(tapoMotionDetectionSelect)
 
        tapoPersonDetectionSelect = await check_and_create(
            entry, hass, TapoPersonDetectionSelect, "getPersonDetection", config_entry
        )
        if tapoPersonDetectionSelect:
            LOGGER.debug("Adding tapoPersonDetectionSelect...")
            selects.append(tapoPersonDetectionSelect)

        tapoMoveToPresetSelect = await check_and_create(
            entry, hass, TapoMoveToPresetSelect, "getPresets", config_entry
        )
        if tapoMoveToPresetSelect:
            LOGGER.debug("Adding TapoMoveToPresetSelect...")
            selects.append(tapoMoveToPresetSelect)
        return selects

    selects = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        selects.extend(await setupEntities(childDevice))

    async_add_entities(selects)


class TapoNightVisionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["auto", "on", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Night Vision",
            entry,
            hass,
            config_entry,
            "mdi:theme-light-dark",
            "night_vision",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_current_option = camData["day_night_mode"]
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setDayNightMode, option
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoLightFrequencySelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["auto", "50", "60"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self, "Light Frequency", entry, hass, config_entry, "mdi:sine-wave"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_current_option = camData["light_frequency_mode"]
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setLightFrequencyMode, option
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoAutomaticAlarmModeSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["both", "light", "sound", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Automatic Alarm",
            entry,
            hass,
            config_entry,
            "mdi:alarm-light-outline",
            "alarm",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            if camData["alarm"] == "off":
                self._attr_current_option = "off"
            else:
                light = "light" in camData["alarm_mode"]
                sound = "sound" in camData["alarm_mode"]
                if light and sound:
                    self._attr_current_option = "both"
                elif light and not sound:
                    self._attr_current_option = "light"
                else:
                    self._attr_current_option = "sound"
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        LOGGER.debug(
            "setAlarm("
            + str(option != "off")
            + ", "
            + str(option == "off" or option in ["both", "sound"])
            + ", "
            + str(option == "off" or option in ["both", "light"])
            + ")"
        )
        result = await self.hass.async_add_executor_job(
            self._controller.setAlarm,
            option != "off",
            option == "off" or option in ["both", "sound"],
            option == "off" or option in ["both", "light"],
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoMotionDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Motion Detection",
            entry,
            hass,
            config_entry,
            "mdi:motion-sensor",
            "motion_detection",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        LOGGER.debug("TapoMotionDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoMotionDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoMotionDetectionSelect updateTapo 3")
            if camData["motion_detection_enabled"] == "off":
                LOGGER.debug("TapoMotionDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoMotionDetectionSelect updateTapo 5")
                self._attr_current_option = camData["motion_detection_sensitivity"]
            LOGGER.debug("TapoMotionDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoMotionDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setMotionDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoPersonDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Person Detection",
            entry,
            hass,
            config_entry,
            "mdi:account-alert",
            "person_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoPersonDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoPersonDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoPersonDetectionSelect updateTapo 3")
            if camData["person_detection_enabled"] == "off":
                LOGGER.debug("TapoPersonDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoPersonDetectionSelect updateTapo 5")
                self._attr_current_option = camData["person_detection_sensitivity"]
            LOGGER.debug("TapoPersonDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoPersonDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setPersonDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoMoveToPresetSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._presets = {}
        self._attr_options = []
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self, "Move to Preset", entry, hass, config_entry, "mdi:arrow-decision"
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._presets = camData["presets"]
            self._attr_options = list(camData["presets"].values())
            self._attr_current_option = None
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        foundKey = False
        for key, value in self._presets.items():
            if value == option:
                foundKey = key
                break
        if foundKey:
            await self.hass.async_add_executor_job(self._controller.setPreset, foundKey)
            self._attr_current_option = None
        else:
            LOGGER.error(f"Preset {option} does not exist.")

    @property
    def entity_category(self):
        return None
