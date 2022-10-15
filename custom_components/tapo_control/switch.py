from homeassistant.core import HomeAssistant

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoSwitchEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up switches")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    switches = []
    switches.append(
        await check_and_create(entry, hass, TapoPrivacySwitch, "getPrivacyMode")
    )
    switches.append(
        await check_and_create(
            entry,
            hass,
            TapoLensDistortionCorrectionSwitch,
            "getLensDistortionCorrection",
        )
    )
    switches.append(
        await check_and_create(entry, hass, TapoIndicatorLedSwitch, "getLED")
    )
    switches.append(
        await check_and_create(entry, hass, TapoFlipSwitch, "getImageFlipVertical")
    )
    switches.append(
        await check_and_create(entry, hass, TapoAutoTrackSwitch, "getAutoTrackTarget")
    )

    async_add_entities(switches)


class TapoLensDistortionCorrectionSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoSwitchEntity.__init__(
            self,
            "Lens Distortion Correction",
            entry,
            hass,
            "mdi:google-lens",
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection,
            False,
        )

    async def async_update(self) -> None:
        self._attr_is_on = await self._hass.async_add_executor_job(
            self._controller.getLensDistortionCorrection
        )


class TapoPrivacySwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoSwitchEntity.__init__(self, "Privacy", entry, hass)

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            True,
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode,
            False,
        )
        await self._coordinator.async_request_refresh()

    async def async_update(self) -> None:
        data = await self._hass.async_add_executor_job(self._controller.getPrivacyMode)

        self._attr_is_on = "enabled" in data and data["enabled"] == "on"

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:eye-outline"
        else:
            return "mdi:eye-off-outline"


class TapoIndicatorLedSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoSwitchEntity.__init__(
            self,
            "Indicator LED",
            entry,
            hass,
            "mdi:car-light-high",
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

        self._attr_is_on = "enabled" in data and data["enabled"] == "on"


class TapoFlipSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoSwitchEntity.__init__(self, "Flip", entry, hass, "mdi:flip-vertical")

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical,
            True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical,
            False,
        )

    async def async_update(self) -> None:
        self._attr_is_on = await self._hass.async_add_executor_job(
            self._controller.getImageFlipVertical
        )


class TapoAutoTrackSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant):
        TapoSwitchEntity.__init__(
            self,
            "Auto Track",
            entry,
            hass,
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

        self._attr_is_on = "enabled" in data and data["enabled"] == "on"
