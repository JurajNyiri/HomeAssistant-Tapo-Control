from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pytapo import Tapo
from .tapo.entities import TapoButtonEntity, ButtonDeviceClass
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
    buttons.append(TapoRebootButton(name, controller, hass, attributes))
    buttons.append(TapoFormatButton(name, controller, hass, attributes))
    buttons.append(TapoStartManualAlarmButton(name, controller, hass, attributes))
    buttons.append(TapoStopManualAlarmButton(name, controller, hass, attributes))
    buttons.append(TapoSyncTimeButton(config_entry, name, controller, hass, attributes))

    async_add_entities(buttons)


class TapoRebootButton(TapoButtonEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoButtonEntity.__init__(self, name, "Reboot", controller, hass, attributes)

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.reboot)

    @property
    def device_class(self) -> str:
        return ButtonDeviceClass.RESTART


class TapoFormatButton(TapoButtonEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoButtonEntity.__init__(
            self, name, "Format", controller, hass, attributes, "mdi:eraser"
        )

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.format)


class TapoSyncTimeButton(TapoButtonEntity):
    def __init__(
        self, entry, name, controller: Tapo, hass: HomeAssistant, attributes: dict
    ):
        self._entry = entry
        TapoButtonEntity.__init__(
            self,
            name,
            "Sync Time",
            controller,
            hass,
            attributes,
            "mdi:timer-sync-outline",
        )

    async def async_press(self) -> None:
        await syncTime(self._hass, self._entry)


class TapoStartManualAlarmButton(TapoButtonEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoButtonEntity.__init__(
            self, name, "Manual Alarm Start", controller, hass, attributes, "mdi:alarm"
        )

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.startManualAlarm)


class TapoStopManualAlarmButton(TapoButtonEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoButtonEntity.__init__(
            self,
            name,
            "Manual Alarm Stop",
            controller,
            hass,
            attributes,
            "mdi:alarm-off",
        )

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.stopManualAlarm)
