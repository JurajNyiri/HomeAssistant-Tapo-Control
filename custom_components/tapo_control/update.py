from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from typing import Callable
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from .const import DOMAIN, LOGGER
from homeassistant.util import slugify
from pytapo import Tapo


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    hass.data[DOMAIN][entry.entry_id]["updateEntity"] = TapoCamUpdate(
        hass, entry, hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities([hass.data[DOMAIN][entry.entry_id]["updateEntity"]])


class TapoCamUpdate(UpdateEntity):
    def __init__(
        self, hass: HomeAssistant, entry: dict, tapoData: Tapo,
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
        return "todo"

    @property
    def name(self) -> str:
        return "Camera - " + self._attributes["device_alias"]

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, slugify(f"{self._attributes['mac']}_tapo_control"))
            },
            "name": self._attributes["device_alias"],
            "manufacturer": "TP-Link",
            "model": self._attributes["device_model"],
            "sw_version": self._attributes["sw_version"],
        }

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    @property
    def installed_version(self) -> str:
        return self._attributes["sw_version"]

    @property
    def latest_version(self) -> str:
        if self._hass.data[DOMAIN][self._entry.entry_id]["latestFirmwareVersion"]:
            return self._hass.data[DOMAIN][self._entry.entry_id][
                "latestFirmwareVersion"
            ]
        else:
            return self._attributes["sw_version"]

    @property
    def release_summary(self) -> str:
        if self.latest_version == self._attributes["sw_version"]:
            return None
        return "todo"

    @property
    def title(self) -> str:
        return "Tapo Camera: {0}".format(self._attributes["device_alias"])

    async def async_install(
        self, version, backup,
    ):
        LOGGER.warn("Install async")
        self._in_progress = True
        await self.hass.async_add_executor_job(self._controller.reboot)  # temp

        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        print("async install")

