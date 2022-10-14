from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pytapo import Tapo
from .tapo.entities import TapoSwitchEntity


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up switches")
    name = hass.data[DOMAIN][config_entry.entry_id]["name"]
    controller: dict = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    attributes = hass.data[DOMAIN][config_entry.entry_id]["camData"]["basic_info"]

    switches = []
    switches.append(await privacy_switch(name, controller, hass, attributes))
    switches.append(await status_led_switch(name, controller, hass, attributes))
    switches.append(await auto_track_switch(name, controller, hass, attributes))

    async_add_entities(switches)


async def privacy_switch(name, controller, hass, attributes):
    try:
        await hass.async_add_executor_job(controller.getPrivacyMode)
    except Exception:
        LOGGER.info("Camera does not support privacy mode")
        return None
    LOGGER.debug("Creating privacy mode switch")
    return TapoPrivacySwitch(name, controller, hass, attributes)


async def status_led_switch(name, controller, hass, attributes):
    try:
        await hass.async_add_executor_job(controller.getLED)
    except Exception:
        LOGGER.info("Camera does not support status led")
        return None
    LOGGER.debug("Creating status led switch")
    return TapoStatusLedSwitch(name, controller, hass, attributes)


async def auto_track_switch(name, controller, hass, attributes):
    try:
        await hass.async_add_executor_job(controller.getAutoTrackTarget)
    except Exception:
        LOGGER.info("Camera does not support auto track mode")
        return None
    LOGGER.debug("Creating auto track mode switch")
    return TapoAutoTrackSwitch(name, controller, hass, attributes)


class TapoPrivacySwitch(TapoSwitchEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoSwitchEntity.__init__(self, name, "Privacy", controller, hass, attributes)

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            False,
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getPrivacyMode)

        self._is_on = "enabled" in data and data["enabled"] == "on"

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:eye"
        else:
            return "mdi:eye-off"


class TapoStatusLedSwitch(TapoSwitchEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoSwitchEntity.__init__(
            self, name, "Status LED", controller, hass, attributes, "mdi:car-light-high"
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled,
            False,
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getLED)

        self._is_on = "enabled" in data and data["enabled"] == "on"


class TapoAutoTrackSwitch(TapoSwitchEntity):
    def __init__(self, name, controller: Tapo, hass: HomeAssistant, attributes: dict):
        TapoSwitchEntity.__init__(
            self,
            name,
            "Auto Track",
            controller,
            hass,
            attributes,
            "mdi:radar",
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget,
            False,
        )

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(
            self._controller.getAutoTrackTarget
        )

        self._is_on = "enabled" in data and data["enabled"] == "on"
