from homeassistant.core import HomeAssistant

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
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
    LOGGER.debug("Setting up light for floodlight")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    light = await check_and_create(
        entry, hass, TapoFloodlight, "getForceWhitelampState", config_entry
    )
    if light is not None:
        async_add_entities([light])


class TapoFloodlight(LightEntity, TapoEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoFloodlight - init - start")
        self._attr_is_on = False
        self._hass = hass
        self._attr_icon = "mdi:light-flood-down"

        self.updateTapo(hass.data[DOMAIN][config_entry.entry_id]["camData"])
        TapoEntity.__init__(self, entry, "Floodlight")
        LightEntity.__init__(self)
        LOGGER.debug("TapoFloodlight - init - end")

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_is_on = camData["force_white_lamp_state"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"
