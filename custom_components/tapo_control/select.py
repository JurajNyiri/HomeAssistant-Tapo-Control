from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

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

    selects = []
    selects.append(TapoNightVisionSelect(entry, hass))
    selects.append(TapoAutomaticAlarmModeSelect(entry, hass))
    selects.append(TapoLightFrequencySelect(entry, hass))
    selects.append(
        await check_and_create(
            entry, hass, TapoMotionDetectionSelect, "getAutoTrackTarget"
        )
    )
    selects.append(
        await check_and_create(entry, hass, TapoMoveToPresetSelect, "getPresets")
    )

    async_add_entities(selects)


class TapoNightVisionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        self._attr_options = ["auto", "on", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Night Vision",
            entry,
            hass,
            "mdi:theme-light-dark",
            "night_vision",
        )

    async def async_update(self) -> None:
        self._attr_current_option = await self._hass.async_add_executor_job(
            self._controller.getDayNightMode
        )

    async def async_select_option(self, option: str) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setDayNightMode, option
        )


class TapoLightFrequencySelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        self._attr_options = ["auto", "50", "60"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(self, "Light Frequency", entry, hass, "mdi:sine-wave")

    async def async_update(self) -> None:
        self._attr_current_option = await self._hass.async_add_executor_job(
            self._controller.getLightFrequencyMode
        )

    async def async_select_option(self, option: str) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLightFrequencyMode, option
        )


class TapoAutomaticAlarmModeSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        self._attr_options = ["both", "light", "sound", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Automatic Alarm",
            entry,
            hass,
            "mdi:alarm-check",
            "alarm",
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getAlarm)
        if "enabled" in data and data["enabled"] == "off":
            self._attr_current_option = "off"
        else:
            light = "alarm_mode" in data and "light" in data["alarm_mode"]
            sound = "alarm_mode" in data and "sound" in data["alarm_mode"]
            if light and sound:
                self._attr_current_option = "both"
            elif light and not sound:
                self._attr_current_option = "light"
            else:
                self._attr_current_option = "sound"

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(
            self._controller.setAlarm,
            option != "off",
            option == "off" or option in ["both", "sound"],
            option == "off" or option in ["both", "light"],
        )


class TapoMotionDetectionSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            "Motion Detection",
            entry,
            hass,
            "mdi:motion-sensor",
            "motion_detection",
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(
            self._controller.getMotionDetection
        )
        if "enabled" in data and data["enabled"] == "off":
            self._attr_current_option = "off"
        else:
            digital_sensitivity = data["digital_sensitivity"]
            if digital_sensitivity == "80":
                self._attr_current_option = "high"
            elif digital_sensitivity == "50":
                self._attr_current_option = "normal"
            else:
                self._attr_current_option = "low"

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(
            self._controller.setMotionDetection,
            option != "off",
            option if option != "off" else False,
        )
        await self._coordinator.async_request_refresh()


class TapoMoveToPresetSelect(TapoSelectEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        self._presets = {}
        self._attr_options = []
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self, "Move to Preset", entry, hass, "mdi:arrow-decision"
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getPresets)
        self._presets = data
        self._attr_options = list(data.values())
        self._attr_current_option = None

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
