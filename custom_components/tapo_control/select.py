from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pytapo import Tapo
from .tapo.entities import TapoSelectEntity
from .utils import syncTime


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up selects")
    entry = hass.data[DOMAIN][config_entry.entry_id]
    name = entry["name"]
    controller: dict = entry["controller"]
    attributes = entry["camData"]["basic_info"]

    selects = []
    selects.append(TapoNightVisionSelect(name, controller, hass, attributes))
    selects.append(TapoAutomaticAlarmModeSelect(name, controller, hass, attributes))
    selects.append(await motion_detection_select(name, controller, hass, attributes))

    async_add_entities(selects)


async def motion_detection_select(name, controller, hass, attributes):
    try:
        await hass.async_add_executor_job(controller.getAutoTrackTarget)
    except Exception:
        LOGGER.info("Camera does not support motion detection")
        return None
    LOGGER.debug("Creating motion detection select")
    return TapoMotionDetectionSelect(name, controller, hass, attributes)


class TapoNightVisionSelect(TapoSelectEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        self._attr_options = ["auto", "on", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            name,
            "Night Vision",
            controller,
            hass,
            attributes,
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


class TapoAutomaticAlarmModeSelect(TapoSelectEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        self._attr_options = ["both", "light", "sound", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            name,
            "Automatic Alarm",
            controller,
            hass,
            attributes,
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
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        self._attr_options = ["high", "normal", "low", "off"]
        self._attr_current_option = None
        TapoSelectEntity.__init__(
            self,
            name,
            "Motion Detection",
            controller,
            hass,
            attributes,
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
