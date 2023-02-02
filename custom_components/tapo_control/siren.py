from homeassistant.components.siren import (
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
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

    tapoSiren = await check_and_create(entry, hass, TapoSiren, "getAlarm", config_entry)

    if tapoSiren:
        LOGGER.debug("Adding siren entity...")
        async_add_entities(tapoSiren)
    else:
        LOGGER.debug("No siren entity available.")


class TapoSirenEntity(SirenEntity, TapoEntity):
    def __init__(
        self, name_suffix, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ):

        LOGGER.debug(f"Tapo {name_suffix} - init - start")

        LOGGER.debug(f"Tapo {name_suffix} - init - start")
        self._attr_is_on = False
        self._hass = hass
        entry["entities"].append({"entity": self, "entry": entry})
        self.updateTapo(entry["camData"])

        self._attr_is_on = False
        self._attr_supported_features = (
            SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_TONES
        )
        self._attr_available_tones = {
            "LIGHT_AND_SOUND": "Light and sound",
            "LIGHT_ONLY": "Light only",
            "SOUND_ONLY": "Sound only",
        }

        TapoEntity.__init__(self, entry, name_suffix)
        SirenEntity.__init__(self)

        # self._enabled = True

        LOGGER.debug(f"Tapo {name_suffix} - init - end")

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def state(self):
        return self._attr_state


class TapoSiren(TapoSirenEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSirenEntity.__init__(self, "Siren", entry, hass, config_entry)

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = camData["alarm"] == "on"

    @property
    def entity_category(self):
        return None
