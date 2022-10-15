from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.button import ButtonDeviceClass

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoButtonEntity
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

    buttons = []
    buttons.append(TapoRebootButton(entry, hass))
    buttons.append(TapoFormatButton(entry, hass))
    buttons.append(TapoStartManualAlarmButton(entry, hass))
    buttons.append(TapoStopManualAlarmButton(entry, hass))
    buttons.append(TapoSyncTimeButton(entry, hass, config_entry.entry_id))
    buttons.append(TapoCalibrateButton(entry, hass))

    async_add_entities(buttons)


class TapoRebootButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoButtonEntity.__init__(self, "Reboot", entry, hass)

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.reboot)

    @property
    def device_class(self) -> str:
        return ButtonDeviceClass.RESTART


class TapoFormatButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoButtonEntity.__init__(self, "Format SD Card", entry, hass, "mdi:eraser")

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.format)


class TapoSyncTimeButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, entry_id):
        self._entry_id = entry_id
        TapoButtonEntity.__init__(
            self,
            "Sync Time",
            entry,
            hass,
            "mdi:timer-sync-outline",
        )

    async def async_press(self) -> None:
        await syncTime(self._hass, self._entry_id)


class TapoStartManualAlarmButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoButtonEntity.__init__(self, "Manual Alarm Start", entry, hass, "mdi:alarm")

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.startManualAlarm)


class TapoStopManualAlarmButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoButtonEntity.__init__(
            self,
            "Manual Alarm Stop",
            entry,
            hass,
            "mdi:alarm-off",
        )

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.stopManualAlarm)


class TapoCalibrateButton(TapoButtonEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoButtonEntity.__init__(self, "Calibrate", entry, hass)

    async def async_press(self) -> None:
        await self._hass.async_add_executor_job(self._controller.calibrateMotor)
