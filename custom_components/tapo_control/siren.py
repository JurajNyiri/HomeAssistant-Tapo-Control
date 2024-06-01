import asyncio

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoEntity
from .utils import check_and_create


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up sirens")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    async def setupEntities(entry):
        sirens = []
        tapoSiren = await check_and_create(
            entry, hass, TapoSiren, "getSirenTypeList", config_entry
        )
        if tapoSiren:
            LOGGER.debug("Adding TapoSirenEntity...")
            sirens.append(tapoSiren)

        return sirens

    sirens = await setupEntities(entry)
    for childDevice in entry["childDevices"]:
        sirens.extend(await setupEntities(childDevice))

    async_add_entities(sirens)


class TapoSirenEntity(SirenEntity, TapoEntity):
    def __init__(
        self, name_suffix, entry: dict, hass: HomeAssistant, config_entry: ConfigEntry
    ):

        LOGGER.debug(f"Tapo {name_suffix} - init - start")

        self._hass = hass

        entry["entities"].append({"entity": self, "entry": entry})
        self.updateTapo(entry["camData"])

        self._attr_is_on = False
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON
            | SirenEntityFeature.TURN_OFF
            | SirenEntityFeature.DURATION
        )

        TapoEntity.__init__(self, entry, name_suffix)
        SirenEntity.__init__(self)

        LOGGER.debug(f"Tapo {name_suffix} - init - end")


class TapoSiren(TapoSirenEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        TapoSirenEntity.__init__(self, "Siren", entry, hass, config_entry)
        self._turn_off_task = None
        self.hub = entry["camData"]["alarm_is_hubSiren"]

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    # TODO acording to doc, siren entity could receive sirenType, duration and volume on same service call,would be nice to add it, should be a previous command and not a multiCommand I think, because if execution order of multiCommand is not guaranteed would not be trustable
    # currently the shortest between configured siren duration and this service call duration is the one that will have impact, also ensuring the duration with siren config would allow to aboid the async off with the sleep
    async def async_turn_on(self, duration: int | None = None, **kwargs) -> None:
        for kw in kwargs:
            LOGGER.debug(f"async_turn_on: Parameter '{kw}' not supported")

        async def _turn_off_after(seconds: int, send: bool) -> None:
            await asyncio.sleep(seconds)
            await self.async_turn_off(send)

        if self._turn_off_task:
            self._turn_off_task.cancel()
            self._turn_off_task = None

        if self.hub:
            result = await self._hass.async_add_executor_job(
                self._controller.setHubSirenStatus, True
            )
        else:
            result = await self._hass.async_add_executor_job(
                self._controller.performRequest,
                {
                    "method": "multipleRequest",
                    "params": {
                        "requests": [
                            {
                                "method": "do",
                                "params": {
                                    "msg_alarm": {
                                        "manual_msg_alarm": {"action": "start"}
                                    }
                                },
                            },
                            {
                                "method": "setSirenStatus",
                                "params": {"msg_alarm": {"status": "on"}},
                            },
                        ]
                    },
                },
            )

        if result_has_error(result):
            self._attr_available = False
        else:
            self._is_on = True
            if duration:
                self._turn_off_task = self.hass.async_create_task(
                    _turn_off_after(duration, True)
                )
            # TODO check on multiplerequest time_left
            elif "time_left" in result and result["time_left"]:
                self._turn_off_task = self.hass.async_create_task(
                    _turn_off_after(result["time_left"], False)
                )

        self._attr_is_on = True

        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, send: bool | None = None, **kwargs) -> None:
        if send:
            if self.hub:
                result = await self._hass.async_add_executor_job(
                    self._controller.setHubSirenStatus, False
                )
            else:
                result = await self._hass.async_add_executor_job(
                    self._controller.executeFunction,
                    "multipleRequest",
                    {
                        "requests": [
                            {
                                "method": "do",
                                "params": {
                                    "msg_alarm": {
                                        "manual_msg_alarm": {"action": "stop"}
                                    }
                                },
                            },
                            {
                                "method": "setSirenStatus",
                                "params": {"msg_alarm": {"status": "off"}},
                            },
                        ]
                    },
                )
        # TODO check on multiple request error
        if result_has_error(result):
            self._attr_available = False

        self._attr_is_on = False

        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        if not camData:
            self._attr_available = False
        else:
            self._attr_available = True
            self._is_on = camData["alarm_status"] == "on"


def result_has_error(result):
    # TODO check if is multipleRequest method check for a success inside
    if "error_code" not in result or result["error_code"] == 0:
        return False
    else:
        return True
