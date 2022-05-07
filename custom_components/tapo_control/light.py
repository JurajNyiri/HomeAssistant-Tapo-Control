from homeassistant.components.light import LightEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify
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
    controller: Tapo = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    cam_data = hass.data[DOMAIN][config_entry.entry_id]["camData"]

    try:
        await hass.async_add_executor_job(controller.getForceWhitelampState)
    except Exception:
        LOGGER.info("Camera does not support floodlight")
        return

    LOGGER.debug("Creating light entity")
    light = TapoFloodlight(name, controller, hass, cam_data)
    async_add_entities([light])


class TapoFloodlight(LightEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, cam_data):
        LOGGER.debug("TapoFloodlight - init - start")
        self._name = name
        self._controller = controller
        self._attributes = cam_data["basic_info"]
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
        return DeviceInfo(
            identifiers={(DOMAIN, slugify(f"{self._attributes['mac']}_tapo_control"))},
            connections={("mac", self._attributes["mac"])},
            name=self._attributes["device_alias"],
            manufacturer="TP-Link",
            model=self._attributes["device_model"],
            sw_version=self._attributes["sw_version"],
        )

    @property
    def unique_id(self) -> str:
        return "{}-floodlight".format(self._name).lower()

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return "TP-Link"
