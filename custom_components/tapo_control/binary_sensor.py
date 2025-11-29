import asyncio
from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import STATE_UNAVAILABLE

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from homeassistant.components.ffmpeg import (
    FFmpegManager,
    get_ffmpeg_manager,
)

from homeassistant.const import STATE_ON, STATE_OFF, CONF_IP_ADDRESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util.enum import try_parse_enum
from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    ENABLE_SOUND_DETECTION,
    DOORBELL_UDP_DISCOVERED,
    DOORBELL_UDP_PORT,
    SOUND_DETECTION_PEAK,
    SOUND_DETECTION_DURATION,
    SOUND_DETECTION_RESET,
)
from .utils import build_device_info, getStreamSource
from .tapo.entities import TapoBinarySensorEntity

import haffmpeg.sensor as ffmpeg_sensor


class TapoUdpBinarySensor(TapoBinarySensorEntity):
    """Binary sensor that pulses on UDP packet receipt."""

    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        super().__init__(
            "Doorbell",
            entry,
            hass,
            config_entry,
            icon="mdi:doorbell",
            device_class=BinarySensorDeviceClass.SOUND,
        )
        self._attr_is_on = False
        self._attr_state = STATE_OFF

    def turn_on(self):
        self._attr_is_on = True
        self._attr_state = STATE_ON
        self.async_write_ha_state()

    def turn_off(self):
        self._attr_is_on = False
        self._attr_state = STATE_OFF
        self.async_write_ha_state()


class TapoUdpMonitor:
    """Background UDP listener for Tapo device broadcasts."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_ip: str | None,
        entry: dict,
        config_entry: ConfigEntry,
        async_add_entities,
        sensor_precreated: bool,
    ):
        self._hass = hass
        self._device_ip = device_ip
        self._entry = entry
        self._config_entry = config_entry
        self._async_add_entities = async_add_entities
        self._transport: asyncio.DatagramTransport | None = None
        self._binary_sensor: TapoUdpBinarySensor | None = None
        self._turn_off_task: asyncio.Task | None = None
        self._sensor_marked_seen = bool(
            self._config_entry.data.get(DOORBELL_UDP_DISCOVERED)
        )
        if sensor_precreated:
            self._hass.async_create_task(
                self.async_ensure_sensor_created(reason="precreate on startup")
            )

    def handle_datagram(self):
        """Schedule handling of an incoming UDP packet."""
        self._hass.async_create_task(self._async_handle_datagram())

    async def _async_handle_datagram(self):
        """Create the sensor on first packet and pulse it on subsequent packets."""
        await self.async_ensure_sensor_created(reason="incoming UDP packet")

        if self._turn_off_task:
            self._turn_off_task.cancel()
            self._turn_off_task = None

        self._binary_sensor.turn_on()
        self._turn_off_task = self._hass.async_create_task(self._async_turn_off())

    async def _async_turn_off(self):
        try:
            await asyncio.sleep(2)
            if self._binary_sensor is not None:
                self._binary_sensor.turn_off()
        except asyncio.CancelledError:
            return
        finally:
            self._turn_off_task = None

    async def async_ensure_sensor_created(self, reason: str | None = None):
        if self._binary_sensor is None:
            LOGGER.debug(
                "Creating doorbell UDP binary sensor (%s)",
                reason or "no reason provided",
            )
            self._binary_sensor = TapoUdpBinarySensor(
                self._entry, self._hass, self._config_entry
            )
            self._async_add_entities([self._binary_sensor])
            await self._async_mark_sensor_seen()

    async def _async_mark_sensor_seen(self):
        if self._sensor_marked_seen:
            return

        self._sensor_marked_seen = True
        new_data = {**self._config_entry.data, DOORBELL_UDP_DISCOVERED: True}
        self._hass.config_entries.async_update_entry(self._config_entry, data=new_data)

    async def async_start(self):
        """Start listening on DOORBELL_UDP_PORT for broadcasts."""
        loop = asyncio.get_running_loop()

        try:
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: _TapoUdpProtocol(self, self._device_ip),
                local_addr=("0.0.0.0", DOORBELL_UDP_PORT),
                allow_broadcast=True,
                reuse_port=True,
            )

            LOGGER.debug(
                "TapoUdpMonitor started on UDP port %s for device IP %s",
                DOORBELL_UDP_PORT,
                self._device_ip,
            )
        except OSError as err:
            LOGGER.warning(
                "TapoUdpMonitor could not bind UDP port %s (already in use?): %s. "
                "UDP doorbell pulses will be disabled.",
                DOORBELL_UDP_PORT,
                err,
            )

    async def async_stop(self):
        """Stop listening."""
        if self._turn_off_task:
            self._turn_off_task.cancel()
            self._turn_off_task = None

        if self._transport is not None:
            self._transport.close()
            self._transport = None
            LOGGER.debug("TapoUdpMonitor stopped")


class _TapoUdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitor: TapoUdpMonitor, device_ip: str | None):
        super().__init__()
        self._monitor = monitor
        self._device_ip = device_ip

    def datagram_received(self, data: bytes, addr):
        ip, _port = addr
        # Only react to packets from the configured device (if known).
        if self._device_ip is None or ip == self._device_ip:
            self._monitor.handle_datagram()


async def async_setup_entry(hass, config_entry, async_add_entities):
    LOGGER.debug("Setting up binary sensor for motion.")
    entry = hass.data[DOMAIN][config_entry.entry_id]
    model = entry.get("camData", {}).get("basic_info", {}).get("device_model")
    is_doorbell_model = isinstance(model, str) and model.upper().startswith("D")
    child_models = [
        child.get("camData", {}).get("basic_info", {}).get("device_model")
        for child in entry.get("childDevices", [])
    ]
    has_doorbell_child = any(
        isinstance(child_model, str) and child_model.upper().startswith("D")
        for child_model in child_models
    )
    is_child_device = bool(entry.get("isChild"))
    device_ip = config_entry.data.get(CONF_IP_ADDRESS)

    hass.data[DOMAIN][config_entry.entry_id]["eventsListener"] = EventsListener(
        async_add_entities, hass, config_entry
    )

    binarySensors = []

    if config_entry.data.get(ENABLE_SOUND_DETECTION):
        LOGGER.debug("Adding TapoNoiseBinarySensor...")
        binarySensors.append(TapoNoiseBinarySensor(entry, hass, config_entry))

    if binarySensors:
        async_add_entities(binarySensors)

    if (is_doorbell_model or has_doorbell_child) and not is_child_device:
        precreate_udp_sensor = bool(config_entry.data.get(DOORBELL_UDP_DISCOVERED))

        udp_monitor = TapoUdpMonitor(
            hass,
            config_entry.data.get(CONF_IP_ADDRESS),
            entry,
            config_entry,
            async_add_entities,
            precreate_udp_sensor,
        )
        await udp_monitor.async_start()
        hass.data[DOMAIN][config_entry.entry_id]["udp_monitor"] = udp_monitor
    else:
        LOGGER.debug(
            "Skipping doorbell UDP binary sensor setup; model=%s, child_models=%s, is_child=%s, Parent IP=%s",
            model,
            child_models,
            is_child_device,
            device_ip,
        )

    return True


class TapoNoiseBinarySensor(TapoBinarySensorEntity):
    def __init__(self, entry: dict, hass: HomeAssistant, config_entry):
        LOGGER.debug("TapoNoiseBinarySensor - init - start")
        TapoBinarySensorEntity.__init__(
            self,
            "Noise",
            entry,
            hass,
            config_entry,
            None,
            BinarySensorDeviceClass.SOUND,
        )

        self._hass = hass
        self._config_entry = config_entry
        self._is_noise_sensor = True
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._enable_sound_detection = config_entry.data.get(ENABLE_SOUND_DETECTION)
        self._sound_detection_peak = config_entry.data.get(SOUND_DETECTION_PEAK)
        self._sound_detection_duration = config_entry.data.get(SOUND_DETECTION_DURATION)
        self._sound_detection_reset = config_entry.data.get(SOUND_DETECTION_RESET)
        self.latestCamData = entry["camData"]

        manager = get_ffmpeg_manager(hass)

        self._noiseSensor = ffmpeg_sensor.SensorNoise(
            manager.binary, self._noiseCallback
        )
        self._noiseSensor.set_options(
            time_duration=int(self._sound_detection_duration),
            time_reset=int(self._sound_detection_reset),
            peak=int(self._sound_detection_peak),
        )

        self._attr_state = STATE_UNAVAILABLE

        LOGGER.debug("TapoNoiseBinarySensor - init - end")

    async def startNoiseDetection(self):
        LOGGER.debug("startNoiseDetection")
        self._hass.data[DOMAIN][self._config_entry.entry_id][
            "noiseSensorStarted"
        ] = True
        LOGGER.debug(getStreamSource(self._config_entry, "stream2"))
        LOGGER.debug(
            str(self._sound_detection_duration)
            + ","
            + str(self._sound_detection_reset)
            + ","
            + str(self._sound_detection_peak),
        )
        await self._noiseSensor.open_sensor(
            input_source=getStreamSource(self._config_entry, "stream2"),
            extra_cmd="-nostats",
        )

    @callback
    def _noiseCallback(self, noiseDetected):
        LOGGER.debug("_noiseCallback")
        LOGGER.debug(noiseDetected)
        if not self.latestCamData or self.latestCamData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE
        else:
            self._attr_state = "on" if noiseDetected else "off"
        self.async_write_ha_state()

    def updateTapo(self, camData):
        self.latestCamData = camData
        if not self.latestCamData or self.latestCamData["privacy_mode"] == "on":
            self._attr_state = STATE_UNAVAILABLE


class EventsListener:
    def __init__(self, async_add_entities, hass, config_entry):
        LOGGER.debug("EventsListener init")
        self.metaData = hass.data[DOMAIN][config_entry.entry_id]
        self.async_add_entities = async_add_entities

    def createBinarySensor(self):
        LOGGER.debug("Creating binary sensor entity.")

        events = self.metaData["events"]
        name = self.metaData["name"]
        camData = self.metaData["camData"]
        entities = {
            event.uid: TapoMotionSensor(event.uid, events, name, camData)
            for event in events.get_platform("binary_sensor")
        }
        self.async_add_entities(entities.values())
        uids_by_platform = events.get_uids_by_platform("binary_sensor")

        @callback
        def async_check_entities():
            LOGGER.debug("async_check_entities")
            nonlocal uids_by_platform
            if not (missing := uids_by_platform.difference(entities)):
                return
            new_entities: dict[str, TapoMotionSensor] = {
                uid: TapoMotionSensor(uid, events, name, camData) for uid in missing
            }
            LOGGER.debug("async_check_entities2")
            if new_entities:
                LOGGER.debug("async_check_entities3")
                entities.update(new_entities)
                self.async_add_entities(new_entities.values())

        events.async_add_listener(async_check_entities)


class TapoMotionSensor(BinarySensorEntity):
    def __init__(self, uid, events, name, camData):
        LOGGER.debug("TapoMotionSensor - init - start")
        self._attr_unique_id = uid
        self._name = name
        self._attributes = camData["basic_info"]
        self._attr_device_class = BinarySensorDeviceClass.MOTION
        self.uid = uid
        self.events = events
        event = events.get_uid(uid)

        self._attr_device_class = try_parse_enum(
            BinarySensorDeviceClass, event.device_class
        )
        self._attr_entity_category = event.entity_category
        self._attr_entity_registry_enabled_default = event.entity_enabled
        self._attr_name = f"{self._name} {event.name}"
        self._attr_is_on = event.value
        self._attr_device_class = event.device_class
        self._attr_enabled = event.entity_enabled
        BinarySensorEntity.__init__(self)
        LOGGER.debug("TapoMotionSensor - init - end")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.value
        return self._attr_is_on

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def device_class(self) -> Optional[str]:
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.device_class
        return self._attr_device_class

    @property
    def unique_id(self) -> str:
        return self.uid

    @property
    def entity_registry_enabled_default(self) -> bool:
        if (event := self.events.get_uid(self._attr_unique_id)) is not None:
            return event.entity_enabled
        return self._attr_enabled

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._attributes)

    @property
    def model(self):
        return self._attributes["device_model"]

    @property
    def brand(self):
        return BRAND

    async def async_added_to_hass(self):
        self.async_on_remove(self.events.async_add_listener(self.async_write_ha_state))
