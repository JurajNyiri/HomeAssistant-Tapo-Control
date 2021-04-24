"""ONVIF event abstraction."""
from __future__ import annotations

"""
Copy of homeassistant/components/onvif/event.py with a lot more debug messages
Shall not be used on official releases
"""

import asyncio
from contextlib import suppress
import datetime as dt
from typing import Callable

from httpx import RemoteProtocolError, TransportError
from onvif import ONVIFCamera, ONVIFService
from zeep.exceptions import Fault

from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from homeassistant.components.onvif.const import LOGGER
from homeassistant.components.onvif.models import Event
from homeassistant.components.onvif.parsers import PARSERS

UNHANDLED_TOPICS = set()
SUBSCRIPTION_ERRORS = (
    Fault,
    asyncio.TimeoutError,
    TransportError,
)


class EventManager:
    """ONVIF Event Manager."""

    def __init__(self, hass: HomeAssistant, device: ONVIFCamera, unique_id: str):
        LOGGER.debug("event manager init")
        """Initialize event manager."""
        self.hass: HomeAssistant = hass
        self.device: ONVIFCamera = device
        self.unique_id: str = unique_id
        self.started: bool = False

        self._subscription: ONVIFService = None
        self._events: dict[str, Event] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_refresh: CALLBACK_TYPE | None = None

        super().__init__()

    @property
    def platforms(self) -> set[str]:
        """Return platforms to setup."""
        return {event.platform for event in self._events.values()}

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""
        LOGGER.debug("async_add_listener")
        # This is the first listener, set up polling.
        if not self._listeners:
            LOGGER.debug("async_add_listener 1")
            self.async_schedule_pull()

        LOGGER.debug("async_add_listener 2")
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            LOGGER.debug("async_add_listener 3")
            """Remove update listener."""
            self.async_remove_listener(update_callback)

        LOGGER.debug("async_add_listener 4")
        return remove_listener

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        LOGGER.debug("async_remove_listener")
        """Remove data update."""
        if update_callback in self._listeners:
            LOGGER.debug("async_remove_listener 1")
            self._listeners.remove(update_callback)

        if not self._listeners and self._unsub_refresh:
            LOGGER.debug("async_remove_listener 2")
            self._unsub_refresh()
            self._unsub_refresh = None
            LOGGER.debug("async_remove_listener 3")

    async def async_start(self) -> bool:
        LOGGER.debug("async_start")
        """Start polling events."""
        if await self.device.create_pullpoint_subscription():
            # Create subscription manager
            LOGGER.debug("async_start 1")
            self._subscription = self.device.create_subscription_service(
                "PullPointSubscription"
            )
            LOGGER.debug("async_start 2")

            # Renew immediately
            await self.async_renew()
            LOGGER.debug("async_start 3")

            # Initialize events
            pullpoint = self.device.create_pullpoint_service()
            with suppress(*SUBSCRIPTION_ERRORS):
                await pullpoint.SetSynchronizationPoint()
            response = await pullpoint.PullMessages(
                {"MessageLimit": 100, "Timeout": dt.timedelta(seconds=5)}
            )
            LOGGER.debug("async_start 4")

            # Parse event initialization
            await self.async_parse_messages(response.NotificationMessage)
            LOGGER.debug("async_start 5")

            self.started = True
            return True

        LOGGER.debug("async_start 6")
        return False

    async def async_stop(self) -> None:
        LOGGER.debug("async_stop")
        """Unsubscribe from events."""
        self._listeners = []
        self.started = False

        if not self._subscription:
            LOGGER.debug("async_stop 1")
            return

        LOGGER.debug("async_stop 2")
        await self._subscription.Unsubscribe()
        self._subscription = None
        LOGGER.debug("async_stop 3")

    async def async_restart(self, _now: dt = None) -> None:
        LOGGER.debug("async_restart")
        """Restart the subscription assuming the camera rebooted."""
        if not self.started:
            LOGGER.debug("async_restart 1")
            return

        if self._subscription:
            LOGGER.debug("async_restart 2")
            # Suppressed. The subscription may no longer exist.
            with suppress(*SUBSCRIPTION_ERRORS):
                await self._subscription.Unsubscribe()
            self._subscription = None
            LOGGER.debug("async_restart 3")

        try:
            LOGGER.debug("async_restart 4")
            restarted = await self.async_start()
            LOGGER.debug("async_restart 5")
        except SUBSCRIPTION_ERRORS:
            LOGGER.debug("async_restart 6")
            restarted = False

        if not restarted:
            LOGGER.warning(
                "Failed to restart ONVIF PullPoint subscription for '%s'. Retrying",
                self.unique_id,
            )
            # Try again in a minute
            self._unsub_refresh = async_call_later(self.hass, 60, self.async_restart)
            LOGGER.debug("async_restart 7")
        elif self._listeners:
            LOGGER.debug("async_restart 8")
            LOGGER.debug(
                "Restarted ONVIF PullPoint subscription for '%s'", self.unique_id
            )
            self.async_schedule_pull()
            LOGGER.debug("async_restart 9")

    async def async_renew(self) -> None:
        LOGGER.debug("async_renew")
        """Renew subscription."""
        if not self._subscription:
            LOGGER.debug("async_renew 1")
            return

        termination_time = (
            (dt_util.utcnow() + dt.timedelta(days=1))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        LOGGER.debug("async_renew 2")
        await self._subscription.Renew(termination_time)
        LOGGER.debug("async_renew 3")

    def async_schedule_pull(self) -> None:
        LOGGER.debug("async_schedule_pull")
        """Schedule async_pull_messages to run."""
        self._unsub_refresh = async_call_later(self.hass, 1, self.async_pull_messages)
        LOGGER.debug("async_schedule_pull 1")

    async def async_pull_messages(self, _now: dt = None) -> None:
        LOGGER.debug("async_pull_messages")
        """Pull messages from device."""
        if self.hass.state == CoreState.running:
            try:
                LOGGER.debug("async_pull_messages 1")
                pullpoint = self.device.create_pullpoint_service()
                response = await pullpoint.PullMessages(
                    {"MessageLimit": 100, "Timeout": dt.timedelta(seconds=60)}
                )

                # Renew subscription if less than two hours is left
                if (
                    dt_util.as_utc(response.TerminationTime) - dt_util.utcnow()
                ).total_seconds() < 7200:
                    LOGGER.debug("async_pull_messages 2")
                    await self.async_renew()
                    LOGGER.debug("async_pull_messages 3")
            except RemoteProtocolError:
                LOGGER.debug("async_pull_messages 4")
                # Likley a shutdown event, nothing to see here
                return
            except SUBSCRIPTION_ERRORS as err:
                LOGGER.warning(
                    "Failed to fetch ONVIF PullPoint subscription messages for '%s': %s",
                    self.unique_id,
                    err,
                )
                # Treat errors as if the camera restarted. Assume that the pullpoint
                # subscription is no longer valid.
                self._unsub_refresh = None
                LOGGER.debug("async_pull_messages 5")
                await self.async_restart()
                LOGGER.debug("async_pull_messages 6")
                return
            LOGGER.debug("async_pull_messages 7")

            # Parse response
            await self.async_parse_messages(response.NotificationMessage)
            LOGGER.debug("async_pull_messages 8")

            # Update entities
            for update_callback in self._listeners:
                LOGGER.debug("async_pull_messages 9")
                update_callback()

        # Reschedule another pull
        if self._listeners:
            LOGGER.debug("async_pull_messages 10")
            self.async_schedule_pull()
            LOGGER.debug("async_pull_messages 11")

    # pylint: disable=protected-access
    async def async_parse_messages(self, messages) -> None:
        """Parse notification message."""
        for msg in messages:
            # Guard against empty message
            if not msg.Topic:
                continue

            topic = msg.Topic._value_1
            parser = PARSERS.get(topic)
            if not parser:
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
                LOGGER.warning("Unable to parse event from %s: %s", self.unique_id, msg)
                return

            self._events[event.uid] = event

    def get_uid(self, uid) -> Event:
        """Retrieve event for given id."""
        return self._events[uid]

    def get_platform(self, platform) -> list[Event]:
        """Retrieve events for given platform."""
        return [event for event in self._events.values() if event.platform == platform]
