import logging
import voluptuous as vol

from datetime import timedelta

from homeassistant.helpers import config_validation as cv

CONTROL_PORT = "control_port"
PYTAPO_REQUIRED_VERSION = "3.3.46"
DOMAIN = "tapo_control"
BRAND = "TP-Link"
ALARM_MODE = "alarm_mode"
PRESET = "preset"
LIGHT = "light"
SOUND = "sound"
PRIVACY_MODE = "privacy_mode"
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
CONF_SKIP_RTSP = "skip_rtsp"

ENABLE_MOTION_SENSOR = "enable_motion_sensor"
ENABLE_MEDIA_SYNC = "enable_media_sync"

IS_KLAP_DEVICE = "is_klap_device"
REPORTED_IP_ADDRESS = "reported_ip_address"
UPDATE_INTERVAL_MAIN = "update_interval_main"
UPDATE_INTERVAL_BATTERY = "update_interval_battery"
UPDATE_INTERVAL_MAIN_DEFAULT = 30
UPDATE_INTERVAL_BATTERY_DEFAULT = 60 * 10

TIME_SYNC_DST = "time_sync_dst"
TIME_SYNC_NDST = "time_sync_ndst"
TIME_SYNC_DST_DEFAULT = 1
TIME_SYNC_NDST_DEFAULT = 0

MEDIA_VIEW_DAYS_ORDER = "media_view_days_order"
MEDIA_VIEW_RECORDINGS_ORDER = "media_view_recordings_order"
MEDIA_SYNC_HOURS = "media_sync_hours"
MEDIA_SYNC_COLD_STORAGE_PATH = "media_sync_cold_storage_path"

TOGGLE_STATES = ["on", "off"]

CONF_RTSP_TRANSPORT = "rtsp_transport"
RTSP_TRANS_PROTOCOLS = ["tcp", "udp", "udp_multicast", "http"]
MEDIA_VIEW_DAYS_ORDER_OPTIONS = ["Ascending", "Descending"]
MEDIA_VIEW_RECORDINGS_ORDER_OPTIONS = ["Ascending", "Descending"]

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

TAPO_PREFIXES = (
    r"^c[0-9]{3}[a-zA-Z]*_.*",  # Security Cameras (C100, C200, C310, C325WB, etc.)
    r"^d[0-9]{3}[a-zA-Z]*_.*",  # Doorbells (D230, D235, D350V, etc.)
    r"^tc[0-9]{2,3}[a-zA-Z]*_.*",  # Pan/Tilt Cameras (TC60, TC70, TC85, etc.)
    r"^d[0-9]{3}[a-zA-Z]*c_.*",  # Doorbell Chimes (D100C, D230C, D325C, etc.)
    r"^h[0-9]{3}[a-zA-Z]*_.*",  # Smart Hubs (H100, H200, H300, etc.)
)
