from homeassistant.core import HomeAssistant

from homeassistant.components.number import RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import STATE_UNAVAILABLE, UnitOfTime

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoEntity, TapoNumberEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up number for movement angle")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        numbers = []

        tapoMovementAngle = await check_and_create(
            entry, hass, TapoMovementAngle, "getPresets", config_entry
        )
        if tapoMovementAngle:
            LOGGER.debug("Adding TapoMovementAngle...")
            numbers.append(tapoMovementAngle)

        tapoMotionDetectionDigitalSensitivity = await check_and_create(
            entry,
            hass,
            TapoMotionDetectionDigitalSensitivity,
            "getMotionDetection",
            config_entry,
        )
        if tapoMotionDetectionDigitalSensitivity:
            LOGGER.debug("Adding tapoMotionDetectionDigitalSensitivity...")
            numbers.append(tapoMotionDetectionDigitalSensitivity)

        if (
            "microphoneVolume" in entry["camData"]
            and entry["camData"]["microphoneVolume"] is not None
        ):
            tapoMicrophoneVolume = await check_and_create(
                entry,
                hass,
                TapoMicrophoneVolume,
                "getAudioConfig",
                config_entry,
            )
            if tapoMicrophoneVolume:
                LOGGER.debug("Adding tapoMicrophoneVolume...")
                numbers.append(tapoMicrophoneVolume)

        if (
            "speakerVolume" in entry["camData"]
            and entry["camData"]["speakerVolume"] is not None
        ):
            tapoSpeakerVolume = await check_and_create(
                entry,
                hass,
                TapoSpeakerVolume,
                "getAudioConfig",
                config_entry,
            )
            if tapoSpeakerVolume:
                LOGGER.debug("Adding tapoSpeakerVolume...")
                numbers.append(tapoSpeakerVolume)
        if "alarm_config" in entry["camData"] and (
            "siren_volume" in entry["camData"]["alarm_config"]
            or "alarm_volume" in entry["camData"]["alarm_config"]
        ):
            tapoSirenVolume = TapoSirenVolume(entry, hass, config_entry)
            if tapoSirenVolume:
                LOGGER.debug("Adding TapoSirenVolume...")
                numbers.append(tapoSirenVolume)

        if "alarm_config" in entry["camData"] and (
            "siren_duration" in entry["camData"]["alarm_config"]
            or "alarm_duration" in entry["camData"]["alarm_config"]
        ):
            tapoSirenDuration = TapoSirenDuration(entry, hass, config_entry)
            if tapoSirenDuration:
                LOGGER.debug("Adding TapoSirenDuration...")
                numbers.append(tapoSirenDuration)

        if (
            entry["camData"]["whitelampConfigIntensity"] is not None
            and entry["camData"]["smartwtl_digital_level"] is not None
        ):
            tapoSpotlightIntensity = TapoSpotlightIntensity(entry, hass, config_entry)
            if tapoSpotlightIntensity:
                LOGGER.debug("Adding tapoSpotlightIntensity...")
                numbers.append(tapoSpotlightIntensity)

        return numbers

    numbers = await setupEntities(entry)

    for childDevice in entry["childDevices"]:
        numbers.extend(await setupEntities(childDevice))

    async_add_entities(numbers)


class TapoMovementAngle(RestoreNumber, TapoEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
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

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

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


class TapoMotionDetectionDigitalSensitivity(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoMotionDetectionDigitalSensitivity - init - start")
        self._attr_min_value = 1
        self._attr_max_value = 100
        self._attr_native_min_value = 1
        self._attr_native_max_value = 100
        self._attr_step = 1
        self._hass = hass

        TapoNumberEntity.__init__(
            self,
            "Motion Detection - Digital Sensitivity",
            entry,
            hass,
            config_entry,
            "mdi:motion-sensor",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMotionDetection, None, int(value)
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = camData["motion_detection_digital_sensitivity"]


class TapoMicrophoneVolume(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoMicrophoneVolume - init - start")
        self._attr_min_value = 0
        self._attr_max_value = 100
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_step = 1
        self._hass = hass

        TapoNumberEntity.__init__(
            self,
            "Microphone - Volume",
            entry,
            hass,
            config_entry,
            "mdi:microphone",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMicrophone, int(value)
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = camData["microphoneVolume"]


class TapoSpeakerVolume(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoSpeakerVolume - init - start")
        self._attr_min_value = 0
        self._attr_max_value = 100
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_step = 1
        self._hass = hass

        TapoNumberEntity.__init__(
            self,
            "Speaker - Volume",
            entry,
            hass,
            config_entry,
            "mdi:speaker",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setSpeakerVolume, int(value)
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = camData["speakerVolume"]


class TapoSirenVolume(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoSirenVolume - init - start")
        self._attr_min_value = 1
        self._attr_max_value = 10
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10
        self._attr_step = 1
        self._hass = hass
        self.is_hub = entry["camData"]["alarm_is_hubSiren"]
        self.typeOfAlarm = entry["camData"]["alarm_config"]["typeOfAlarm"]
        if "siren_volume" in entry["camData"]["alarm_config"]:
            self.value_key = "siren_volume"
        else:
            self.value_key = "alarm_volume"

        self._attr_native_value = entry["camData"]["alarm_config"][self.value_key]

        TapoNumberEntity.__init__(
            self,
            "Siren volume",
            entry,
            hass,
            config_entry,
            "mdi:volume-high",
        )
        LOGGER.debug("TapoSirenVolume - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        if self.is_hub:
            result = await self._hass.async_add_executor_job(
                self._controller.setHubSirenConfig, None, None, str(int(value))
            )
        else:
            strval = "low"
            if value > 3:
                strval = "normal"
            if value > 7:
                strval = "high"
            if self.typeOfAlarm == "getAlarm":
                result = await self._hass.async_add_executor_job(
                    self._controller.setAlarm,
                    self.alarm_enabled,
                    "sound" in self.alarm_mode,
                    "siren" in self.alarm_mode or "light" in self.alarm_mode,
                    strval,
                )
            elif self.typeOfAlarm == "getAlarmConfig":
                result = await self._hass.async_add_executor_job(
                    self._controller.executeFunction,
                    "setAlarmConfig",
                    {"msg_alarm": {self.value_key: strval}},
                )
            else:
                LOGGER.error("Unexpected type of alarm: " + self.typeOfAlarm)
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            alarmVolume = camData["alarm_config"][self.value_key]
            if str(alarmVolume).isnumeric():
                self._attr_state = camData["alarm_config"][self.value_key]
            elif str(alarmVolume) == "low":
                self._attr_state = 1
            elif str(alarmVolume) == "normal":
                self._attr_state = 5
            elif str(alarmVolume) == "high":
                self._attr_state = 10
            if self.typeOfAlarm == "getAlarm":
                self.alarm_enabled = camData["alarm_config"]["automatic"] == "on"
                self.alarm_mode = camData["alarm_config"]["mode"]


class TapoSpotlightIntensity(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoSpotlightIntensity - init - start")
        self._attr_min_value = 1
        self._attr_native_min_value = 1
        self._attr_max_value = 100
        self._attr_native_max_value = int(entry["camData"]["smartwtl_digital_level"])
        self._attr_step = 1
        self._hass = hass
        self._attr_native_value = entry["camData"]["whitelampConfigIntensity"]
        self._attr_state = entry["camData"]["whitelampConfigIntensity"]

        TapoNumberEntity.__init__(
            self,
            "Spotlight Intensity",
            entry,
            hass,
            config_entry,
            "mdi:lightbulb-on-50",
        )
        LOGGER.debug("TapoSpotlightIntensity - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setWhitelampConfig, False, int(value)
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_native_value = int(camData["whitelampConfigIntensity"])
            self._attr_state = camData["whitelampConfigIntensity"]


class TapoSirenDuration(TapoNumberEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoSirenDuration - init - start")
        self._attr_min_value = 1
        self._attr_native_min_value = 1
        self._attr_max_value = 300
        self._attr_native_max_value = 300
        self.is_hub = entry["camData"]["alarm_is_hubSiren"]
        self.typeOfAlarm = entry["camData"]["alarm_config"]["typeOfAlarm"]
        if self.is_hub:
            self._attr_max_value = 599
            self._attr_native_max_value = 599
        self._attr_step = 1
        self._attr_native_unit_of_measurement: UnitOfTime.SECONDS
        self._hass = hass
        if "siren_duration" in entry["camData"]["alarm_config"]:
            self.value_key = "siren_duration"
        else:
            self.value_key = "alarm_duration"
        self._attr_native_value = entry["camData"]["alarm_config"][self.value_key]

        TapoNumberEntity.__init__(
            self,
            "Siren duration",
            entry,
            hass,
            config_entry,
            "mdi:clock-end",
        )
        LOGGER.debug("TapoSirenDuration - init - end")

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    async def async_set_native_value(self, value: float) -> None:
        if self.is_hub:
            result = await self._hass.async_add_executor_job(
                self._controller.setHubSirenConfig, int(value)
            )
        else:
            if self.typeOfAlarm == "getAlarm":
                result = await self._hass.async_add_executor_job(
                    self._controller.setAlarm,
                    self.alarm_enabled,
                    "sound" in self.alarm_mode,
                    "siren" in self.alarm_mode or "light" in self.alarm_mode,
                    None,
                    int(value),
                )
            elif self.typeOfAlarm == "getAlarmConfig":
                result = await self._hass.async_add_executor_job(
                    self._controller.executeFunction,
                    "setAlarmConfig",
                    {"msg_alarm": {self.value_key: int(value)}},
                )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = value
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = camData["alarm_config"][self.value_key]
            if self.typeOfAlarm == "getAlarm":
                self.alarm_enabled = camData["alarm_config"]["automatic"] == "on"
                self.alarm_mode = camData["alarm_config"]["mode"]
