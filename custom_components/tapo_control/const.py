import logging
import voluptuous as vol

from datetime import timedelta

from homeassistant.helpers import config_validation as cv

DOMAIN = "tapo_control"
BRAND = "TP-Link"
ALARM_MODE = "alarm_mode"
PRESET = "preset"
LIGHT = "light"
SOUND = "sound"
PRIVACY_MODE = "privacy_mode"
DAY_NIGHT_MODE = "day_night_mode"
ALARM = "alarm"
LED_MODE = "led_mode"
NAME = "name"
DISTANCE = "distance"
TILT = "tilt"
PAN = "pan"
MOTION_DETECTION_MODE = "motion_detection_mode"
AUTO_TRACK_MODE = "auto_track_mode"
CLOUD_PASSWORD = "cloud_password"
DEFAULT_SCAN_INTERVAL = 10
SCAN_INTERVAL = timedelta(seconds=5)
CONF_CUSTOM_STREAM = "custom_stream"

ENABLE_MOTION_SENSOR = "enable_motion_sensor"

TOGGLE_STATES = ["on", "off"]

CONF_RTSP_TRANSPORT = "rtsp_transport"
RTSP_TRANS_PROTOCOLS = ["tcp", "udp", "udp_multicast", "http"]

ENABLE_WEBHOOKS = "enable_webhooks"
ENABLE_STREAM = "enable_stream"
ENABLE_SOUND_DETECTION = "enable_sound_detection"
SOUND_DETECTION_PEAK = "sound_detection_peak"
SOUND_DETECTION_DURATION = "sound_detection_duration"
SOUND_DETECTION_RESET = "sound_detection_reset"

ENABLE_TIME_SYNC = "enable_time_sync"

LOGGER = logging.getLogger("custom_components." + DOMAIN)

TIME_SYNC_PERIOD = 3600
MEDIA_CLEANUP_PERIOD = 10 * 60
UPDATE_CHECK_PERIOD = 86400

COLD_DIR_DELETE_TIME = 24 * 60 * 60
HOT_DIR_DELETE_TIME = 60 * 60

SERVICE_SAVE_PRESET = "save_preset"
SCHEMA_SERVICE_SAVE_PRESET = {
    vol.Required(NAME): cv.string,
}

SERVICE_DELETE_PRESET = "delete_preset"
SCHEMA_SERVICE_DELETE_PRESET = {
    vol.Required(PRESET): cv.string,
}
