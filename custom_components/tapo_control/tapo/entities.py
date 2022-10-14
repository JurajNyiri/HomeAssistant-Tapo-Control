from ..utils import build_device_info
from ..const import BRAND, LOGGER
from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from pytapo import Tapo


class TapoSwitchEntity(SwitchEntity):
    def __init__(
        self,
        name,
        name_suffix,
        controller: Tapo,
        hass: HomeAssistant,
        attributes: dict,
        icon=None,
    ):
        LOGGER.debug(f"Tapo {name_suffix} - init - start")
        self._name = name
        self._name_suffix = name_suffix
        self._controller = controller
        self._attributes = attributes
        self._is_on = False
        self._hass = hass
        self._icon = icon
        self._attr_device_class = SwitchDeviceClass.SWITCH
        SwitchEntity.__init__(self)
        LOGGER.debug(f"Tapo {name_suffix} - init - end")

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def name(self) -> str:
        return "{} - {}".format(self._name, self._name_suffix)

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def unique_id(self) -> str:
        id_suffix = "".join(self._name_suffix.split())

        return "{}-{}".format(self._name, id_suffix).lower()

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    @property
    def icon(self) -> str:
        return self._icon


class TapoButtonEntity(ButtonEntity):
    def __init__(
        self,
        name,
        name_suffix,
        controller: Tapo,
        hass: HomeAssistant,
        attributes: dict,
        icon=None,
    ):
        LOGGER.debug(f"Tapo {name_suffix} - init - start")
        self._name = name
        self._name_suffix = name_suffix
        self._controller = controller
        self._attributes = attributes
        self._is_on = False
        self._hass = hass
        self._icon = icon
        ButtonEntity.__init__(self)
        LOGGER.debug(f"Tapo {name_suffix} - init - end")

    @property
    def name(self) -> str:
        return "{} - {}".format(self._name, self._name_suffix)

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def unique_id(self) -> str:
        id_suffix = "".join(self._name_suffix.split())

        return "{}-{}".format(self._name, id_suffix).lower()

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    @property
    def icon(self) -> str:
        return self._icon


class TapoSelectEntity(SelectEntity):
    def __init__(
        self,
        name,
        name_suffix,
        controller: Tapo,
        hass: HomeAssistant,
        attributes: dict,
        icon=None,
    ):
        LOGGER.debug(f"Tapo {name_suffix} - init - start")
        self._name = name
        self._name_suffix = name_suffix
        self._controller = controller
        self._attributes = attributes
        self._is_on = False
        self._hass = hass
        self._icon = icon
        ButtonEntity.__init__(self)
        LOGGER.debug(f"Tapo {name_suffix} - init - end")

    @property
    def name(self) -> str:
        return "{} - {}".format(self._name, self._name_suffix)

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def unique_id(self) -> str:
        id_suffix = "".join(self._name_suffix.split())

        return "{}-{}".format(self._name, id_suffix).lower()

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    @property
    def icon(self) -> str:
        return self._icon
