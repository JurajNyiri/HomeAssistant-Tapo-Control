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
    LOGGER.debug("Setting up buttons")
    entry = hass.data[DOMAIN][config_entry.entry_id]
    name = entry["name"]
    controller: dict = entry["controller"]
    attributes = entry["camData"]["basic_info"]

    buttons = []
    buttons.append(TapoNightVisionSelect(name, controller, hass, attributes))
    buttons.append(TapoAlarmModeSelect(name, controller, hass, attributes))

    async_add_entities(buttons)


class TapoNightVisionSelect(TapoSelectEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        # on => night, off => day
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
        )

    async def async_update(self) -> None:
        self._attr_current_option = await self._hass.async_add_executor_job(
            self._controller.getDayNightMode
        )

    async def async_select_option(self, option: str) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setDayNightMode, option
        )


class TapoAlarmModeSelect(TapoSelectEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        # on => night, off => day
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
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getAlarm)
        self._attr_current_option = "both"
        LOGGER.debug(f"Tapo {self._name_suffix}: {self._attr_current_option} - {data}")
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
