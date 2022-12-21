from typing import Callable

from homeassistant.core import HomeAssistant

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, LOGGER
from .utils import build_device_info
from .tapo.entities import TapoUpdateEntity


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
):
    entry = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        updates = []
        entry["updateEntity"] = TapoCamUpdate(entry, hass, entry)
        updates.append(entry["updateEntity"])

        return updates

    updates = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        updates.extend(await setupEntities(childDevice))

    async_add_entities(updates)


class TapoCamUpdate(UpdateEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        self._in_progress = False
        self._hass = hass
        TapoUpdateEntity.__init__(self, "Update", entry, hass, config_entry)

    @property
    def name(self) -> str:
        return "{} {}".format(self._name, self._name_suffix)

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def unique_id(self) -> str:
        id_suffix = "".join(self._name_suffix.split())

        return "{}-{}".format(self._name, id_suffix).lower()

    def updateTapo(self, camData):
        if not camData:
            self._state = "unavailable"
        else:
            self._attributes = camData["basic_info"]
            if (
                self._in_progress
                and "firmwareUpdateStatus" in camData
                and "upgrade_status" in camData["firmwareUpdateStatus"]
                and "state" in camData["firmwareUpdateStatus"]["upgrade_status"]
                and camData["firmwareUpdateStatus"]["upgrade_status"]["state"]
                == "normal"
            ):
                self._in_progress = False

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

    @property
    def supported_features(self):
        return UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES

    async def async_release_notes(self) -> str:
        """Return the release notes."""
        if (
            self._entry["latestFirmwareVersion"]
            and "release_log" in self._entry["latestFirmwareVersion"]
        ):
            return self._entry["latestFirmwareVersion"]["release_log"].replace(
                "\\n", "\n"
            )
        else:
            return None

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    @property
    def installed_version(self) -> str:
        return self._attributes["sw_version"]

    @property
    def latest_version(self) -> str:
        if (
            self._entry["latestFirmwareVersion"]
            and "version" in self._entry["latestFirmwareVersion"]
        ):
            return self._entry["latestFirmwareVersion"]["version"]
        else:
            return self._attributes["sw_version"]

    @property
    def release_summary(self) -> str:
        if (
            self._entry["latestFirmwareVersion"]
            and "release_log" in self._entry["latestFirmwareVersion"]
        ):
            maxLength = 255
            releaseLog = self._entry["latestFirmwareVersion"]["release_log"].replace(
                "\\n", "\n"
            )
            return (
                (releaseLog[: maxLength - 3] + "...")
                if len(releaseLog) > maxLength
                else releaseLog
            )
        else:
            return None

    async def async_install(
        self, version, backup,
    ):
        try:
            await self.hass.async_add_executor_job(
                self._controller.startFirmwareUpgrade
            )
            self._in_progress = True
            await self._coordinator.async_request_refresh()
        except Exception as e:
            LOGGER.error(e)
