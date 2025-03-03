"""Tapo camera sensors."""

import re

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNAVAILABLE,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENABLE_MEDIA_SYNC, LOGGER
from .tapo.entities import TapoSensorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup Tapo camera sensors using config entry."""
    LOGGER.debug("Setting up sensors")
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry: dict) -> list:
        """Setup the entities."""
        sensors = []

        if "camData" in entry:
            camData: dict = entry["camData"]
            if "basic_info" in camData and "battery_percent" in camData["basic_info"]:
                LOGGER.debug("Adding tapoBatterySensor...")
                sensors.append(TapoBatterySensor(entry, hass, config_entry))

            if (
                camData.get("connectionInformation", False) is not False
                and camData["connectionInformation"] is not None
            ):
                if "ssid" in camData["connectionInformation"]:
                    LOGGER.debug("Adding TapoSSIDSensor...")
                    sensors.append(TapoSSIDSensor(entry, hass, config_entry))
                if "link_type" in camData["connectionInformation"]:
                    LOGGER.debug("Adding TapoLinkTypeSensor...")
                    sensors.append(TapoLinkTypeSensor(entry, hass, config_entry))
                if "rssiValue" in camData["connectionInformation"]:
                    LOGGER.debug("Adding TapoRSSISensor...")
                    sensors.append(TapoRSSISensor(entry, hass, config_entry))

            if "sdCardData" in camData and len(camData["sdCardData"]) > 0:
                for hdd in camData["sdCardData"]:
                    for field in hdd:
                        LOGGER.debug(
                            "Adding TapoHDDSensor for disk %s and property %s...",
                            hdd["disk_name"],
                            field,
                        )
                        sensors.append(
                            TapoHDDSensor(
                                entry, hass, config_entry, hdd["disk_name"], field
                            )
                        )
            if (
                "basic_info" in camData
                and camData["basic_info"] is not None
                and "signal_level" in camData["basic_info"]
                and camData["basic_info"]["signal_level"] is not None
            ):
                sensors.append(TapoChimeSignalLevel(entry, hass, config_entry))

        if entry["controller"].isKLAP is False:
            sensors.append(TapoSyncSensor(entry, hass, config_entry))

        return sensors

    sensors = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        sensors.extend(await setupEntities(childDevice))

    async_add_entities(sensors)


class TapoRSSISensor(TapoSensorEntity):
    """Tapo RSSI sensor entity."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "RSSI",
            entry,
            hass,
            config_entry,
            "mdi:signal-variant",
            None,
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        if (
            not camData
            or camData["connectionInformation"] is False
            or "rssiValue" not in camData["connectionInformation"]
        ):
            self._attr_native_value = STATE_UNAVAILABLE
        else:
            self._attr_native_value = camData["connectionInformation"]["rssiValue"]


class TapoLinkTypeSensor(TapoSensorEntity):
    """Tapo link type sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "Link Type",
            entry,
            hass,
            config_entry,
            "mdi:connection",
            None,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        if (
            not camData
            or camData["connectionInformation"] is False
            or "link_type" not in camData["connectionInformation"]
        ):
            self._attr_native_value = STATE_UNAVAILABLE
        else:
            self._attr_native_value = camData["connectionInformation"]["link_type"]


class TapoChimeSignalLevel(TapoSensorEntity):
    """Tapo Chime Signal Level sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "Signal Level",
            entry,
            hass,
            config_entry,
            "mdi:signal",
            None,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        if (
            not camData
            or camData["basic_info"] is False
            or camData["basic_info"] is None
            or "signal_level" not in camData["basic_info"]
        ):
            self._attr_native_value = STATE_UNAVAILABLE
        else:
            self._attr_native_value = camData["basic_info"]["signal_level"]


class TapoSSIDSensor(TapoSensorEntity):
    """Tapo SSID sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "Network SSID",
            entry,
            hass,
            config_entry,
            "mdi:wifi",
            None,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        if (
            not camData
            or camData["connectionInformation"] is False
            or "ssid" not in camData["connectionInformation"]
        ):
            self._attr_native_value = STATE_UNAVAILABLE
        else:
            self._attr_native_value = camData["connectionInformation"]["ssid"]


class TapoBatterySensor(TapoSensorEntity):
    """Tapo battery sensor entity."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "Battery",
            entry,
            hass,
            config_entry,
            "mdi:battery",
            SensorDeviceClass.BATTERY,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        if not camData:
            self._attr_native_value = STATE_UNAVAILABLE
        else:
            self._attr_native_value = camData["basic_info"]["battery_percent"]


class TapoHDDSensor(TapoSensorEntity):
    """Tapo HDD sensor entities."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entry: dict,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        sensorName: str,
        sensorProperty: str,
    ) -> None:
        """Initialize the entity."""
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

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        state = STATE_UNAVAILABLE
        if camData and "sdCardData" in camData and len(camData["sdCardData"]) > 0:
            for hdd in camData["sdCardData"]:
                if hdd["disk_name"] == self._sensor_name:
                    state = hdd[self._sensor_property]
        if "space" in self._sensor_property and (
            match := re.search(r"[-+]?\d*\.?\d+", state)
        ):
            value = match.group()
            if (unit := state.replace(value, "")) in UnitOfInformation:
                self._attr_device_class = SensorDeviceClass.DATA_SIZE
                self._attr_native_unit_of_measurement = UnitOfInformation(unit)
                self._attr_suggested_unit_of_measurement = UnitOfInformation.GIGABYTES
                state = value
        self._attr_native_value = state


class TapoSyncSensor(TapoSensorEntity):
    """Tapo sync sensor entities."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        TapoSensorEntity.__init__(
            self,
            "Recordings Synchronization",
            entry,
            hass,
            config_entry,
            None,
            None,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData: dict | None) -> None:
        """Update the entity."""
        enable_media_sync = self._hass.data[DOMAIN][self._config_entry.entry_id][
            ENABLE_MEDIA_SYNC
        ]
        runningMediaSync = self._hass.data[DOMAIN][self._config_entry.entry_id][
            "runningMediaSync"
        ]
        LOGGER.debug("Enable Media Sync: %s", enable_media_sync)
        if enable_media_sync or runningMediaSync is True:
            data = self._hass.data[DOMAIN][self._config_entry.entry_id]
            LOGGER.debug("Initial Media Scan: %s", data["initialMediaScanDone"])
            LOGGER.debug("Media Sync Available: %s", data["mediaSyncAvailable"])
            LOGGER.debug("Download Progress: %s", data["downloadProgress"])
            LOGGER.debug("Running media sync: %s", data["runningMediaSync"])
            LOGGER.debug("Media Sync Schedueled: %s", data["mediaSyncScheduled"])
            LOGGER.debug("Media Sync Ran Once: %s", data["mediaSyncRanOnce"])

            if not data["initialMediaScanDone"] or (
                data["initialMediaScanDone"] and not data["mediaSyncRanOnce"]
            ):
                self._attr_native_value = "Starting"
            elif not data["mediaSyncAvailable"]:
                self._attr_native_value = "No Recordings Found"
            elif data["downloadProgress"]:
                if data["downloadProgress"] == "Finished download":
                    self._attr_native_value = "Idle"
                else:
                    self._attr_native_value = data["downloadProgress"]
            else:
                self._attr_native_value = "Idle"
        else:
            self._attr_native_value = "Idle"
