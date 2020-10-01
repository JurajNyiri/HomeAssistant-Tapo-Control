from homeassistant.helpers import entity
from pytapo import Tapo
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD)
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DOMAIN = "tapo_control"
PRESET_ID = "preset_id"
ENTITY_ID = "entity_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

tapo = {}

def setup(hass, config):
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    for camera in config[DOMAIN]:
        host = camera[CONF_HOST]
        username = camera[CONF_USERNAME]
        password = camera[CONF_PASSWORD]

        tapoConnector = Tapo(host, username, password)
        basicInfo = tapoConnector.getBasicInfo()

        entity_id = DOMAIN+"."+basicInfo['device_info']['basic_info']['device_alias'].replace(".","_").replace(" ", "_").lower()
        if(entity_id in tapo):
            # if two entities have the same name, add ip to the next one
            entity_id = entity_id+"_"+host.replace(".","_")

        tapo[entity_id] = tapoConnector
        hass.states.set(entity_id, "monitoring", basicInfo['device_info']['basic_info']) # todo: better state
    
    print(tapo)

    def handle_set_preset(call):
        if ENTITY_ID in call.data and PRESET_ID in call.data:
            entity_id = call.data.get(ENTITY_ID)
            preset_id = call.data.get(PRESET_ID)
            tapo[entity_id].setPreset(preset_id)
        else:
            _LOGGER.warn("entity_id or preset_id not provided")

    hass.services.register(DOMAIN, "set_preset", handle_set_preset)
    
    return True