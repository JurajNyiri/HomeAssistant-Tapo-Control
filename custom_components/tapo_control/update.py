from .utils import build_device_info
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from typing import Callable
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    hass.data[DOMAIN][entry.entry_id]["updateEntity"] = TapoCamUpdate(
        hass, entry, hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities([hass.data[DOMAIN][entry.entry_id]["updateEntity"]])


class TapoCamUpdate(UpdateEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: dict,
        tapoData,
    ):
        super().__init__()
        self._controller = tapoData["controller"]
        self._coordinator = tapoData["coordinator"]
        self._entry = entry
        self._hass = hass
        self._enabled = False
        self._attributes = tapoData["camData"]["basic_info"]
        self._in_progress = False

    def updateCam(self, camData):
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
            self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
            and "release_log"
            in self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
        ):
            return self._hass.data[DOMAIN][self._entry.entry_id][
                "latestFirmwareVersion"
            ]["release_log"].replace("\\n", "\n")
        else:
            return None

    @property
    def name(self) -> str:
        return "Camera - " + self._attributes["device_alias"]

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    @property
    def installed_version(self) -> str:
        return self._attributes["sw_version"]

    @property
    def latest_version(self) -> str:
        if (
            self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
            and "version"
            in self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
        ):
            return self._hass.data[DOMAIN][self._entry.entry_id][
                "latestFirmwareVersion"
            ]["version"]
        else:
            return self._attributes["sw_version"]

    @property
    def release_summary(self) -> str:
        if (
            self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
            and "release_log"
            in self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]
        ):
            maxLength = 255
            releaseLog = self._hass.data[DOMAIN][self._entry.entry_id][
                "latestFirmwareVersion"
            ]["release_log"].replace("\\n", "\n")
            return (
                (releaseLog[: maxLength - 3] + "...")
                if len(releaseLog) > maxLength
                else releaseLog
            )
        else:
            return None

    @property
    def title(self) -> str:
        return "Tapo Camera: {0}".format(self._attributes["device_alias"])

    async def async_install(
        self,
        version,
        backup,
    ):
        try:
            await self.hass.async_add_executor_job(
                self._controller.startFirmwareUpgrade
            )
            self._in_progress = True
            await self._coordinator.async_request_refresh()
        except Exception as e:
            LOGGER.error(e)
