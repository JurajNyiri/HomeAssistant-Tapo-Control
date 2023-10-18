from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENABLE_MEDIA_SYNC, LOGGER
from .tapo.entities import TapoSensorEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import PERCENTAGE


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up sensors")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        sensors = []

        if (
            "camData" in entry
            and "basic_info" in entry["camData"]
            and "battery_percent" in entry["camData"]["basic_info"]
        ):
            LOGGER.debug("Adding tapoBatterySensor...")
            sensors.append(TapoBatterySensor(entry, hass, entry))

        if (
            "camData" in entry
            and "sdCardData" in entry["camData"]
            and len(entry["camData"]["sdCardData"]) > 0
        ):
            for hdd in entry["camData"]["sdCardData"]:
                for sensorProperty in hdd:
                    LOGGER.debug(
                        f"Adding TapoHDDSensor for disk {hdd['disk_name']} and property {sensorProperty}..."
                    )
                    sensors.append(
                        TapoHDDSensor(
                            entry, hass, entry, hdd["disk_name"], sensorProperty
                        )
                    )

        sensors.append(TapoSyncSensor(entry, hass, config_entry))

        return sensors

    sensors = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        sensors.extend(await setupEntities(childDevice))

    async_add_entities(sensors)


class TapoBatterySensor(TapoSensorEntity):
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.BATTERY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = ["auto", "on", "off"]
        self._attr_current_option = None
        TapoSensorEntity.__init__(
            self,
            "Battery",
            entry,
            hass,
            config_entry,
            None,
            "battery",
        )

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_state = "unavailable"
        else:
            self._attr_state = camData["basic_info"]["battery_percent"]


class TapoHDDSensor(TapoSensorEntity):
    _attr_device_class: SensorDeviceClass = None
    _attr_state_class: SensorStateClass = None
    _attr_native_unit_of_measurement = None

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry, sensorName, sensorProperty
    ):
        self._attr_options = None
        self._attr_current_option = None
        self._sensor_name = sensorName
        self._sensor_property = sensorProperty
        TapoSensorEntity.__init__(
            self,
            f"Disk {sensorName} {sensorProperty}",
            entry,
            hass,
            config_entry,
            "mdi:sd",
            None,
        )

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        state = STATE_UNAVAILABLE
        if camData and "sdCardData" in camData and len(camData["sdCardData"]) > 0:
            for hdd in camData["sdCardData"]:
                if hdd["disk_name"] == self._sensor_name:
                    state = hdd[self._sensor_property]
        self._attr_state = state


class TapoSyncSensor(TapoSensorEntity):
    _attr_device_class: SensorDeviceClass = None
    _attr_state_class: SensorStateClass = None
    _attr_native_unit_of_measurement = None

    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._attr_options = None
        self._attr_current_option = None
        TapoSensorEntity.__init__(
            self,
            "Recordings Synchronization",
            entry,
            hass,
            config_entry,
            None,
            None,
        )

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        enableMediaSync = self._config_entry.data.get(ENABLE_MEDIA_SYNC)
        if enableMediaSync:
            if not self._hass.data[DOMAIN][self._config_entry.entry_id][
                "initialMediaScanDone"
            ]:
                self._attr_state = "Starting"
            if not self._hass.data[DOMAIN][self._config_entry.entry_id][
                "mediaSyncAvailable"
            ]:
                self._attr_state = "No Recordings Found"
            elif self._hass.data[DOMAIN][self._config_entry.entry_id][
                "downloadProgress"
            ]:
                if (
                    self._hass.data[DOMAIN][self._config_entry.entry_id][
                        "downloadProgress"
                    ]
                    == "Finished download"
                ):
                    self._attr_state = "Idle"
                else:
                    self._attr_state = self._hass.data[DOMAIN][
                        self._config_entry.entry_id
                    ]["downloadProgress"]
            else:
                self._attr_state = "Idle"
        else:
            self._attr_state = "Idle"
