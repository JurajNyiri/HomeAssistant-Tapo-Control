from .utils import build_device_info
from homeassistant.components.light import LightEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import BRAND, DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pytapo import Tapo


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up light for floodlight")
    name = hass.data[DOMAIN][config_entry.entry_id]["name"]
    controller: dict = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    attributes = hass.data[DOMAIN][config_entry.entry_id]["camData"]["basic_info"]

    try:
        await hass.async_add_executor_job(controller.getForceWhitelampState)
    except Exception:
        LOGGER.info("Camera does not support floodlight")
        return

    LOGGER.debug("Creating light entity")
    light = TapoFloodlight(name, controller, hass, attributes)
    async_add_entities([light])


class TapoFloodlight(LightEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        LOGGER.debug("TapoFloodlight - init - start")
        self._name = name
        self._controller = controller
        self._attributes = attributes
        self._is_on = False
        self._hass = hass
        LightEntity.__init__(self)
        LOGGER.debug("TapoFloodlight - init - end")

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def name(self) -> str:
        return "{} - Floodlight".format(self._name)

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState,
            False,
        )

    async def async_update(self) -> None:
        self._is_on = await self._hass.async_add_executor_job(
            self._controller.getForceWhitelampState
        )

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def unique_id(self) -> str:
        return "{}-floodlight".format(self._name).lower()

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    @property
    def icon(self) -> str:
        return "mdi:light-flood-down"
