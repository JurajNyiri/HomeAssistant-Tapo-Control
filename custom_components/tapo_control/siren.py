import asyncio

from homeassistant.components.siren import (
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_DURATION,
    SirenEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up sirens")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        sirens = []
        tapoSiren = await check_and_create(
            entry, hass, TapoSiren, "getAlarm", config_entry
        )
        if tapoSiren:
            LOGGER.debug("Adding TapoSirenEntity...")
            sirens.append(tapoSiren)

        return sirens

    sirens = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        sirens.extend(await setupEntities(childDevice))

    async_add_entities(sirens)


class TapoSirenEntity(SirenEntity, TapoEntity):
    def __init__(
        self, name_suffix, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ):

        LOGGER.debug(f"Tapo {name_suffix} - init - start")

        self._hass = hass

        entry["entities"].append({"entity": self, "entry": entry})
        self.updateTapo(entry["camData"])

        self._attr_is_on = False
        self._attr_supported_features = (
            SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_DURATION
        )

        # self._attr_supported_features = self._attr_supported_features | SUPPORT_TONES
        # self._attr_available_tones = {
        #     "LIGHT_AND_SOUND": "Light and sound",
        #     "LIGHT_ONLY": "Light only",
        #     "SOUND_ONLY": "Sound only",
        # }

        TapoEntity.__init__(self, entry, name_suffix)
        SirenEntity.__init__(self)

        LOGGER.debug(f"Tapo {name_suffix} - init - end")


class TapoSiren(TapoSirenEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSirenEntity.__init__(self, "Siren", entry, hass, config_entry)
        self._turn_off_task = None

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, duration: int | None = None, **kwargs) -> None:
        for kw in kwargs:
            LOGGER.debug(f"async_turn_on: Parameter '{kw}' not supported")

        async def _turn_off_after(seconds: int) -> None:
            await asyncio.sleep(seconds)
            await self.async_turn_off()

        if self._turn_off_task:
            self._turn_off_task.cancel()
            self._turn_off_task = None

        result = await self._hass.async_add_executor_job(
            self._controller.startManualAlarm,
        )

        if result_has_error(result):
            self._attr_available = False

        else:
            self._is_on = True
            if duration:
                self._turn_off_task = self.hass.async_create_task(
                    _turn_off_after(duration)
                )

        self._attr_is_on = True

        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.stopManualAlarm,
        )

        if result_has_error(result):
            self._attr_available = False
        else:
            self._attr_is_on = False

        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_available = False
        else:
            self._attr_available = True
            self._is_on = camData["alarm"] == "on"


def result_has_error(result):
    if "error_code" not in result or result["error_code"] == 0:
        return False
    else:
        return True
