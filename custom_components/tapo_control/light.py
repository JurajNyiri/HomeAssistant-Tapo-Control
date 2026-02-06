from homeassistant.core import HomeAssistant

from homeassistant.components.light import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    STATE_UNAVAILABLE,
)
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.util.color import value_to_brightness
from .const import DOMAIN, LOGGER
from .tapo.entities import TapoLightEntity
from .utils import check_and_create, check_functionality


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up light for floodlight")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        lights = []

        tapoFloodlightAvailable = await check_functionality(
            entry, hass, TapoFloodlight, "getForceWhitelampState"
        )
        if tapoFloodlightAvailable:
            if entry["chInfo"]:
                for lens in entry["chInfo"]:
                    chn_alias = lens.get("chn_alias", "")
                    chn_id = lens.get("chn_id")
                    force_state = entry["camData"].get("force_white_lamp_state")
                    if isinstance(force_state, dict) and (
                        str(chn_id) not in force_state
                        or force_state.get(str(chn_id)) is None
                    ):
                        continue
                    tapoFloodlight = TapoFloodlight(
                        entry, hass, config_entry, chn_alias, chn_id
                    )
                    if tapoFloodlight:
                        LOGGER.debug(
                            f"Adding tapoFloodlight for {chn_alias}, id: {chn_id}..."
                        )
                        lights.append(tapoFloodlight)
            else:
                tapoFloodlight = TapoFloodlight(entry, hass, config_entry)
                if tapoFloodlight:
                    LOGGER.debug("Adding tapoFloodlight...")
                    lights.append(tapoFloodlight)
        else:
            if (
                entry["camData"]["flood_light_capability"] is not None
                and entry["camData"]["flood_light_config"] is not None
                and entry["camData"]["flood_light_status"] is not None
                and "min_intensity" in entry["camData"]["flood_light_capability"]
                and "intensity_level_max" in entry["camData"]["flood_light_capability"]
                and "intensity_level" in entry["camData"]["flood_light_config"]
            ):
                tapoFloodlightModern = TapoFloodlightModern(
                    entry,
                    hass,
                    config_entry,
                    entry["camData"]["flood_light_capability"]["min_intensity"],
                    entry["camData"]["flood_light_capability"]["intensity_level_max"],
                )
                if tapoFloodlightModern:
                    LOGGER.debug("Adding tapoFloodlightModern...")
                    lights.append(tapoFloodlightModern)

        tapoWhitelight = await check_and_create(
            entry,
            hass,
            TapoWhitelight,
            "getWhitelampStatus",
            config_entry,
        )
        if tapoWhitelight:
            LOGGER.debug("Adding tapoWhitelightSwitch...")
            lights.append(tapoWhitelight)

        return lights

    lights = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        lights.extend(await setupEntities(childDevice))

    async_add_entities(lights)


class TapoWhitelight(TapoLightEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoWhitelight - init - start")
        self._attr_is_on = False
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = set([ColorMode.ONOFF])
        self._hass = hass

        TapoLightEntity.__init__(
            self,
            "Floodlight (Timed)",
            entry,
            hass,
            config_entry,
            "mdi:light-flood-down",
        )
        LOGGER.debug("TapoWhitelight - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        LOGGER.debug("Turning on light")
        camData = self._entry["camData"]
        if (
            camData is not False
            and "whitelampStatus" in camData
            and str(camData["whitelampStatus"]) == "0"
        ):
            result = await self._hass.async_add_executor_job(
                self._controller.reverseWhitelampStatus
            )
            LOGGER.debug(result)
            if "error_code" not in result or result["error_code"] == 0:
                LOGGER.debug("Setting light state to: on")
                self._attr_is_on = True
                self._attr_state = "on"
            camData["whitelampStatus"] = 1
            self.async_write_ha_state()
            await self._coordinator.async_request_refresh()
            camData["whitelampStatus"] = 1

    async def async_turn_off(self) -> None:
        LOGGER.debug("Turning off light")
        camData = self._entry["camData"]
        if (
            camData is not False
            and "whitelampStatus" in camData
            and str(camData["whitelampStatus"]) == "1"
        ):
            result = await self._hass.async_add_executor_job(
                self._controller.reverseWhitelampStatus
            )
            LOGGER.debug(result)
            if "error_code" not in result or result["error_code"] == 0:
                LOGGER.debug("Setting light state to: off")
                self._attr_is_on = False
                self._attr_state = "off"
            camData["whitelampStatus"] = 0
            self.async_write_ha_state()
            await self._coordinator.async_request_refresh()
            camData["whitelampStatus"] = 0

    def updateTapo(self, camData):
        LOGGER.debug("Updating light state.")
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_is_on = str(camData["whitelampStatus"]) == "1"
            self._attr_state = "on" if self._attr_is_on else "off"


class TapoFloodlightModern(TapoLightEntity):
    def __init__(
        self,
        entry: dict,
        hass: HomeAssistant,
        config_entry,
        minValue: int,
        maxValue: int,
    ):
        LOGGER.debug("TapoFloodlightModern - init - start")
        self._attr_is_on = str(entry["camData"]["flood_light_status"]) == "1"
        self.is_on = self._attr_is_on
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = set([ColorMode.BRIGHTNESS])
        self._minValue = int(minValue)
        self._maxValue = int(maxValue)
        self._hass = hass
        self._brightness = int(
            entry["camData"]["flood_light_config"]["intensity_level"]
        )

        TapoLightEntity.__init__(
            self,
            "Floodlight",
            entry,
            hass,
            config_entry,
            "mdi:light-flood-down",
        )
        LOGGER.debug("TapoFloodlight - init - end")

    def scaleBrightnessValue(self, value):
        if not (1 <= value <= 255):
            raise ValueError("Value must be between 1 and 255")
        return self._minValue + (value - 1) * (self._maxValue - self._minValue) // (
            255 - 1
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        LOGGER.debug("Turning on light")
        if ATTR_BRIGHTNESS in kwargs:
            brightnessValue = self.scaleBrightnessValue(kwargs[ATTR_BRIGHTNESS])
            if brightnessValue != self._brightness:
                LOGGER.debug(f"Changing brightness to {brightnessValue}...")
                result = await self._hass.async_add_executor_job(
                    self._controller.setFloodlightConfig,
                    None,
                    None,
                    None,
                    None,
                    int(brightnessValue),
                )
                if "error_code" not in result or result["error_code"] == 0:
                    self._brightness = brightnessValue
        if self._attr_state != "on":
            result = await self._hass.async_add_executor_job(
                self._controller.manualFloodlightOp,
                True,
            )
            LOGGER.debug(result)
            if "error_code" not in result or result["error_code"] == 0:
                LOGGER.debug("Setting light state to: on")
                self._attr_state = "on"
                self.is_on = True
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        LOGGER.debug("Turning off light")
        if self._attr_state != "off":
            result = await self._hass.async_add_executor_job(
                self._controller.manualFloodlightOp,
                False,
            )
            LOGGER.debug(result)
            if "error_code" not in result or result["error_code"] == 0:
                LOGGER.debug("Setting light state to: off")
                self._attr_state = "off"
                self.is_on = False
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        LOGGER.debug("Updating modern light state.")
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._brightness = int(camData["flood_light_config"]["intensity_level"])
            self._attr_is_on = str(camData["flood_light_status"]) == "1"
            self._attr_state = "on" if self._attr_is_on else "off"

    @property
    def brightness(self) -> int:
        """Return the current brightness."""
        return value_to_brightness(
            (self._minValue, self._maxValue),
            self._brightness,
        )


class TapoFloodlight(TapoLightEntity):
    def __init__(
        self,
        entry: dict,
        hass: HomeAssistant,
        config_entry,
        specific_name=None,
        chn_id=None,
    ):
        LOGGER.debug("TapoFloodlight - init - start")
        self._attr_is_on = False
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = set([ColorMode.ONOFF])
        self._hass = hass
        self.chn_id = chn_id
        self.read_chn_id = str(chn_id) if chn_id else "1"

        TapoLightEntity.__init__(
            self,
            f"Floodlight{" - " + specific_name if specific_name else ""}",
            entry,
            hass,
            config_entry,
            "mdi:light-flood-down",
        )
        LOGGER.debug("TapoFloodlight - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        LOGGER.debug("Turning on light")
        result = await self._hass.async_add_executor_job(
            self._controller.setForceWhitelampState,
            True,
            [self.chn_id] if self.chn_id else None,
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
            self._controller.setForceWhitelampState,
            False,
            [self.chn_id] if self.chn_id else None,
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
            self._attr_state = STATE_UNAVAILABLE
        else:
            force_state = camData["force_white_lamp_state"]
            if isinstance(force_state, dict):
                force_state = force_state.get(self.read_chn_id)
            self._attr_is_on = force_state == "on"
            self._attr_state = "on" if self._attr_is_on else "off"
