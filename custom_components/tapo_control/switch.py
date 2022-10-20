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

    tapoPrivacySwitch = await check_and_create(
        entry, hass, TapoPrivacySwitch, "getPrivacyMode", config_entry
    )
    if tapoPrivacySwitch:
        LOGGER.debug("Adding tapoPrivacySwitch...")
        switches.append(tapoPrivacySwitch)

    tapoLensDistortionCorrectionSwitch = await check_and_create(
        entry,
        hass,
        TapoLensDistortionCorrectionSwitch,
        "getLensDistortionCorrection",
        config_entry,
    )
    if tapoLensDistortionCorrectionSwitch:
        LOGGER.debug("Adding tapoLensDistortionCorrectionSwitch...")
        switches.append(tapoLensDistortionCorrectionSwitch)

    tapoIndicatorLedSwitch = await check_and_create(
        entry, hass, TapoIndicatorLedSwitch, "getLED", config_entry
    )
    if tapoIndicatorLedSwitch:
        LOGGER.debug("Adding tapoIndicatorLedSwitch...")
        switches.append(tapoIndicatorLedSwitch)

    tapoFlipSwitch = await check_and_create(
        entry, hass, TapoFlipSwitch, "getImageFlipVertical", config_entry
    )
    if tapoFlipSwitch:
        LOGGER.debug("Adding tapoFlipSwitch...")
        switches.append(tapoFlipSwitch)

    tapoAutoTrackSwitch = await check_and_create(
        entry, hass, TapoAutoTrackSwitch, "getAutoTrackTarget", config_entry
    )
    if tapoAutoTrackSwitch:
        LOGGER.debug("Adding tapoAutoTrackSwitch...")
        switches.append(tapoAutoTrackSwitch)

    tapoMotionDetectionSwitch = await check_and_create(
        entry, hass, TapoMotionDetectionSwitch, "getMotionDetection", config_entry
    )
    if tapoMotionDetectionSwitch:
        LOGGER.debug("Adding tapoMotionDetectionSwitch...")
        switches.append(tapoMotionDetectionSwitch)

    if switches:
        LOGGER.debug("Adding switch entities...")
        async_add_entities(switches)
    else:
        LOGGER.debug("No switch entities available.")


class TapoLensDistortionCorrectionSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self,
            "Lens Distortion Correction",
            entry,
            hass,
            config_entry,
            "mdi:google-lens",
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLensDistortionCorrection, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["lens_distrotion_correction"] == "on"


class TapoPrivacySwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(self, "Privacy", entry, hass, config_entry)

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setPrivacyMode, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["privacy_mode"] == "on"

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:eye-off-outline"
        else:
            return "mdi:eye-outline"
        
    @property
    def entity_category(self):
        return None


class TapoIndicatorLedSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Indicator LED", entry, hass, config_entry, "mdi:car-light-high"
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setLEDEnabled, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["led"] == "on"


class TapoFlipSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Flip", entry, hass, config_entry, "mdi:flip-vertical"
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setImageFlipVertical, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["flip"] == "on"


class TapoAutoTrackSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Auto Track", entry, hass, config_entry, "mdi:radar"
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setAutoTrackTarget, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["auto_track"] == "on"


class TapoMotionDetectionSwitch(TapoSwitchEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSwitchEntity.__init__(
            self, "Motion Detection", entry, hass, config_entry, "mdi:motion-sensor"
        )

    async def async_turn_on(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setMotionDetection, True,
        )

    async def async_turn_off(self) -> None:
        await self._hass.async_add_executor_job(
            self._controller.setMotionDetection, False,
        )

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = "idle"
            self._attr_is_on = camData["motion_detection_enabled"] == "on"
