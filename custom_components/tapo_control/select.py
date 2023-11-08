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

        tapoVehicleDetectionSelect = await check_and_create(
            entry, hass, TapoVehicleDetectionSelect, "getVehicleDetection", config_entry
        )
        if tapoVehicleDetectionSelect:
            LOGGER.debug("Adding tapoVehicleDetectionSelect...")
            selects.append(tapoVehicleDetectionSelect)

        tapoBabyCryDetectionSelect = await check_and_create(
            entry, hass, TapoBabyCryDetectionSelect, "getBabyCryDetection", config_entry
        )
        if tapoBabyCryDetectionSelect:
            LOGGER.debug("Adding tapoBabyCryDetectionSelect...")
            selects.append(tapoBabyCryDetectionSelect)

        tapoPetDetectionSelect = await check_and_create(
            entry, hass, TapoPetDetectionSelect, "getPetDetection", config_entry
        )
        if tapoPetDetectionSelect:
            LOGGER.debug("Adding tapoPetDetectionSelect...")
            selects.append(tapoPetDetectionSelect)

        tapoBarkDetectionSelect = await check_and_create(
            entry, hass, TapoBarkDetectionSelect, "getBarkDetection", config_entry
        )
        if tapoBarkDetectionSelect:
            LOGGER.debug("Adding tapoBarkDetectionSelect...")
            selects.append(tapoBarkDetectionSelect)

        tapoMeowDetectionSelect = await check_and_create(
            entry, hass, TapoMeowDetectionSelect, "getMeowDetection", config_entry
        )
        if tapoMeowDetectionSelect:
            LOGGER.debug("Adding tapoMeowDetectionSelect...")
            selects.append(tapoMeowDetectionSelect)

        tapoGlassBreakDetectionSelect = await check_and_create(
            entry,
            hass,
            TapoGlassBreakDetectionSelect,
            "getGlassBreakDetection",
            config_entry,
        )
        if tapoGlassBreakDetectionSelect:
            LOGGER.debug("Adding tapoGlassBreakDetectionSelect...")
            selects.append(tapoGlassBreakDetectionSelect)

        tapoTamperDetectionSelect = await check_and_create(
            entry, hass, TapoTamperDetectionSelect, "getTamperDetection", config_entry
        )
        if tapoTamperDetectionSelect:
            LOGGER.debug("Adding tapoTamperDetectionSelect...")
            selects.append(tapoTamperDetectionSelect)

        tapoMoveToPresetSelect = await check_and_create(
            entry, hass, TapoMoveToPresetSelect, "getPresets", config_entry
        )
        if tapoMoveToPresetSelect:
            LOGGER.debug("Adding TapoMoveToPresetSelect...")
            selects.append(tapoMoveToPresetSelect)

        tapoPatrolModeSelect = await check_and_create(
            entry, hass, TapoPatrolModeSelect, "getPresets", config_entry
        )
        if tapoPatrolModeSelect:
            LOGGER.debug("Adding TapoPatrolModeSelect...")
            selects.append(tapoPatrolModeSelect)

        if entry["camData"]["whitelampConfigForceTime"] is not None:
            tapoWhitelampForceTimeSelect = await check_and_create(
                entry,
                hass,
                TapoWhitelampForceTimeSelect,
                "getWhitelampConfig",
                config_entry,
            )
            if tapoWhitelampForceTimeSelect:
                LOGGER.debug("Adding TapoWhitelampForceTimeSelect...")
                selects.append(tapoWhitelampForceTimeSelect)

        if entry["camData"]["whitelampConfigIntensity"] is not None:
            tapoWhitelampIntensityLevelSelect = await check_and_create(
                entry,
                hass,
                TapoWhitelampIntensityLevelSelect,
                "getWhitelampConfig",
                config_entry,
            )
            if tapoWhitelampIntensityLevelSelect:
                LOGGER.debug("Adding TapoWhitelampIntensityLevelSelect...")
                selects.append(tapoWhitelampIntensityLevelSelect)

        return selects

    selects = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        selects.extend(await setupEntities(childDevice))

    async_add_entities(selects)


class TapoWhitelampForceTimeSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["5 min", "10 min", "15 min", "30 min"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Spotlight on/off for",
            entry,
            hass,
            config_entry,
            "mdi:clock-outline",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            if camData["whitelampConfigForceTime"] == "300":
                self._attr_current_option = self._attr_options[0]
            elif camData["whitelampConfigForceTime"] == "600":
                self._attr_current_option = self._attr_options[1]
            elif camData["whitelampConfigForceTime"] == "900":
                self._attr_current_option = self._attr_options[2]
            elif camData["whitelampConfigForceTime"] == "1800":
                self._attr_current_option = self._attr_options[3]
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        if option == "5 min":
            result = await self._hass.async_add_executor_job(
                self._controller.setWhitelampConfig, 300
            )
        elif option == "10 min":
            result = await self._hass.async_add_executor_job(
                self._controller.setWhitelampConfig, 600
            )
        elif option == "15 min":
            result = await self._hass.async_add_executor_job(
                self._controller.setWhitelampConfig, 900
            )
        elif option == "30 min":
            result = await self._hass.async_add_executor_job(
                self._controller.setWhitelampConfig, 1800
            )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoWhitelampIntensityLevelSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["1", "2", "3", "4", "5"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Spotlight Intensity",
            entry,
            hass,
            config_entry,
            "mdi:lightbulb-on-50",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_current_option = camData["whitelampConfigIntensity"]
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setWhitelampConfig, False, option
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoPatrolModeSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["Horizontal", "Vertical", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Patrol Mode",
            entry,
            hass,
            config_entry,
            "mdi:swap-horizontal",
            "patrol_mode",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_current_option = None
            self._attr_state = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        if option == "off":
            result = await self._hass.async_add_executor_job(
                self._controller.setCruise, False
            )
        else:
            result = await self._hass.async_add_executor_job(
                self._controller.setCruise, True, "x" if option == "Horizontal" else "y"
            )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return None


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


class TapoVehicleDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Vehicle Detection",
            entry,
            hass,
            config_entry,
            "mdi:truck-alert-outline",
            "vehicle_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoVehicleDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoVehicleDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoVehicleDetectionSelect updateTapo 3")
            if camData["vehicle_detection_enabled"] == "off":
                LOGGER.debug("TapoVehicleDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoVehicleDetectionSelect updateTapo 5")
                self._attr_current_option = camData["vehicle_detection_sensitivity"]
            LOGGER.debug("TapoVehicleDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoVehicleDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setVehicleDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoBabyCryDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Baby Cry Detection",
            entry,
            hass,
            config_entry,
            "mdi:emoticon-cry-outline",
            "baby_cry_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 3")
            if camData["babyCry_detection_enabled"] == "off":
                LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 5")
                self._attr_current_option = camData["babyCry_detection_sensitivity"]
            LOGGER.debug("TapoBabyCryDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoBabyCryDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setBabyCryDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoPetDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Pet Detection",
            entry,
            hass,
            config_entry,
            "mdi:paw",
            "pet_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoPetDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoPetDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoPetDetectionSelect updateTapo 3")
            if camData["pet_detection_enabled"] == "off":
                LOGGER.debug("TapoPetDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoPetDetectionSelect updateTapo 5")
                self._attr_current_option = camData["pet_detection_sensitivity"]
            LOGGER.debug("TapoPetDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoPetDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setPetDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoBarkDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Bark Detection",
            entry,
            hass,
            config_entry,
            "mdi:dog",
            "bark_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoBarkDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoBarkDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoBarkDetectionSelect updateTapo 3")
            if camData["bark_detection_enabled"] == "off":
                LOGGER.debug("TapoBarkDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoBarkDetectionSelect updateTapo 5")
                self._attr_current_option = camData["bark_detection_sensitivity"]
            LOGGER.debug("TapoBarkDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoBarkDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setBarkDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoMeowDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Meow Detection",
            entry,
            hass,
            config_entry,
            "mdi:cat",
            "meow_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoMeowDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoMeowDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoMeowDetectionSelect updateTapo 3")
            if camData["meow_detection_enabled"] == "off":
                LOGGER.debug("TapoMeowDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoMeowDetectionSelect updateTapo 5")
                self._attr_current_option = camData["meow_detection_sensitivity"]
            LOGGER.debug("TapoMeowDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoMeowDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setMeowDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoGlassBreakDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Glass Break Detection",
            entry,
            hass,
            config_entry,
            "mdi:image-broken-variant",
            "glass_break_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 3")
            if camData["glass_detection_enabled"] == "off":
                LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 5")
                self._attr_current_option = camData["glass_detection_sensitivity"]
            LOGGER.debug("TapoGlassBreakDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug(
            "Updating TapoGlassBreakDetectionSelect to: " + str(self._attr_state)
        )

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setGlassBreakDetection,
            option != "off",
            option if option != "off" else False,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = option
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoTamperDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Tamper Detection",
            entry,
            hass,
            config_entry,
            "mdi:camera-enhance",
            "tamper_detection",
        )

    def updateTapo(self, camData):
        LOGGER.debug("TapoTamperDetectionSelect updateTapo 1")
        if not camData:
            LOGGER.debug("TapoTamperDetectionSelect updateTapo 2")
            self._attr_state = STATE_UNAVAILABLE
        else:
            LOGGER.debug("TapoTamperDetectionSelect updateTapo 3")
            if camData["tamper_detection_enabled"] == "off":
                LOGGER.debug("TapoTamperDetectionSelect updateTapo 4")
                self._attr_current_option = "off"
            else:
                LOGGER.debug("TapoTamperDetectionSelect updateTapo 5")
                self._attr_current_option = camData["tamper_detection_sensitivity"]
            LOGGER.debug("TapoTamperDetectionSelect updateTapo 6")
            self._attr_state = self._attr_current_option
        LOGGER.debug("Updating TapoTamperDetectionSelect to: " + str(self._attr_state))

    async def async_select_option(self, option: str) -> None:
        result = await self.hass.async_add_executor_job(
            self._controller.setTamperDetection,
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
        if not camData or camData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._presets = camData["presets"]
            presetsConvertedToList = list(camData["presets"].values())
            if presetsConvertedToList:
                self._attr_options = list(camData["presets"].values())
                self._attr_current_option = None
                self._attr_state = self._attr_current_option
            else:
                self._attr_state = STATE_UNAVAILABLE

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
