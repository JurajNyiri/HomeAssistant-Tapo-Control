from homeassistant.core import HomeAssistant

from homeassistant.components.number import RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoEntity


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up number for movement angle")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    number = TapoMovementAngle(entry, hass)
    if number is not None:
        async_add_entities([number])


class TapoMovementAngle(RestoreNumber, TapoEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        LOGGER.debug("TapoMovementAngle - init - start")
        self._attr_native_min_value = 5
        self._attr_native_max_value = 120
        self._attr_native_step = 5
        self._attr_native_value = entry["movement_angle"] = 15
        self._hass = hass
        self._attr_icon = "mdi:map-marker-distance"

        TapoEntity.__init__(self, entry, "Movement Angle")
        RestoreNumber.__init__(self)
        LOGGER.debug("TapoMovementAngle - init - end")

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = self._entry["movement_angle"] = value

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        data = await self.async_get_last_number_data()

        if data is not None and data.native_value is not None:
            await self.async_set_native_value(data.native_value)
