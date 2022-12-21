from homeassistant.core import HomeAssistant

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoLightEntity
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

    async def setupEntities(entry):
        lights = []

        tapoFloodlight = await check_and_create(
            entry, hass, TapoFloodlight, "getForceWhitelampState", config_entry
        )
        if tapoFloodlight:
            LOGGER.debug("Adding tapoFloodlight...")
            lights.append(tapoFloodlight)
        return lights

    lights = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        lights.extend(await setupEntities(childDevice))

    async_add_entities(lights)


class TapoFloodlight(TapoLightEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoFloodlight - init - start")
        self._attr_is_on = False
        self._hass = hass

        TapoLightEntity.__init__(
            self, "Floodlight", entry, hass, config_entry, "mdi:light-flood-down",
        )
        LOGGER.debug("TapoFloodlight - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        LOGGER.debug("Turning on light")
        result = await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState, True,
        )
        LOGGER.debug(result)
        if "error_code" not in result or result["error_code"] == 0:
            LOGGER.debug("Setting light state to: on")
            self._attr_state = "on"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        LOGGER.debug("Turning off light")
        result = await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState, False,
        )
        LOGGER.debug(result)
        if "error_code" not in result or result["error_code"] == 0:
            LOGGER.debug("Setting light state to: off")
            self._attr_state = "off"
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        LOGGER.debug("Updating light state.")
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_is_on = camData["force_white_lamp_state"] == "on"
            self._attr_state = "on" if self._attr_is_on else "off"
