import voluptuous as vol

from homeassistant.helpers import config_validation as cv

DOMAIN = "tapo_control"
ALARM_MODE = "alarm_mode"
PRESET = "preset"
LIGHT = "light"
SOUND = "sound"
PRIVACY_MODE = "privacy_mode"
LED_MODE = "led_mode"
NAME = "name"
DISTANCE = "distance"
TILT = "tilt"
PAN = "pan"
ENTITY_ID = "entity_id"
MOTION_DETECTION_MODE = "motion_detection_mode"
AUTO_TRACK_MODE = "auto_track_mode"
DEFAULT_SCAN_INTERVAL = 10
ENTITY_CHAR_WHITELIST = set('abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_')
DEVICE_MODEL_C100 = "C100"
DEVICE_MODEL_C200 = "C200"
DEVICES_WITH_NO_PRESETS = [DEVICE_MODEL_C100]

TOGGLE_STATES = ["on", "off"]

SERVICE_PTZ = "ptz"
SCHEMA_SERVICE_PTZ = {
    vol.Required(ENTITY_ID): cv.string,
    vol.Optional(TILT): vol.In(["UP", "DOWN"]),
    vol.Optional(PAN): vol.In(["RIGHT", "LEFT"]),
    vol.Optional(PRESET): cv.string,
    vol.Optional(DISTANCE): cv.string
}

SERVICE_SET_PRIVACY_MODE = "set_privacy_mode"
SCHEMA_SERVICE_SET_PRIVACY_MODE = {
    vol.Required(ENTITY_ID): cv.string,
    vol.Required(PRIVACY_MODE): vol.In(TOGGLE_STATES)
}

SERVICE_SET_LED_MODE = "set_led_mode"
SCHEMA_SERVICE_SET_LED_MODE = {
    vol.Required(ENTITY_ID): cv.string,
    vol.Required(LED_MODE): vol.In(TOGGLE_STATES)
}