from homeassistant.components.onvif.event import EventManager
from homeassistant.components.onvif.event import PARSERS
from homeassistant.core import HomeAssistant
from onvif import ONVIFCamera
from .const import LOGGER

UNHANDLED_TOPICS: set[str] = set()


class TapoEventManager(EventManager):
    def __init__(self, hass: HomeAssistant, device: ONVIFCamera, unique_id: str):
        LOGGER.error("Initiating")
        LOGGER.debug(TapoEventManager)
        EventManager.__init__(self, hass, device, unique_id)
        LOGGER.error("Initiated")

    # pylint: disable=protected-access
    async def async_parse_messages(self, messages) -> None:
        LOGGER.warn("async_parse_messages")
        """Parse notification message."""
        for msg in messages:
            # Guard against empty message
            if not msg.Topic:
                continue

            topic = msg.Topic._value_1
            if not (parser := PARSERS.get(topic)):
                if topic not in UNHANDLED_TOPICS:
                    LOGGER.info(
                        "No registered handler for event from %s: %s",
                        self.unique_id,
                        msg,
                    )
                    UNHANDLED_TOPICS.add(topic)
                continue

            event = await parser(self.unique_id, msg)

            if not event:
                LOGGER.info("Unable to parse event from %s: %s", self.unique_id, msg)
                return

            self._events[event.uid] = event
