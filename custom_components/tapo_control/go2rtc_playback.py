"""Signal a WebRTC viewer for an existing named go2rtc stream."""

import asyncio

from aiortc.sdp import SessionDescription
from go2rtc_client.ws import (
    Go2RtcWsClient,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
from homeassistant.components.camera import (
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from webrtc_models import RTCIceCandidateInit


def is_playback_offer(offer_sdp):
    try:
        offer = SessionDescription.parse(offer_sdp)
    except (AssertionError, IndexError, ValueError):
        return False
    media = [
        section
        for section in offer.media
        if section.kind in ("audio", "video")
        and section.port != 0
        and section.direction != "inactive"
    ]
    # An omitted direction defaults to sendrecv. Keep microphone offers in pytapo.
    return any(section.kind == "video" for section in media) and all(
        section.direction == "recvonly" for section in media
    )


class Go2RtcPlaybackSession:
    """Bridge HA signaling to the existing go2rtc stream."""

    def __init__(self, hass, api_url, name, send_message, on_close):
        self._hass = hass
        self._client = Go2RtcWsClient(
            async_get_clientsession(hass), api_url, source=name
        )
        self._client.subscribe(self._on_message)
        self._send_message = send_message
        self._on_close = on_close
        self._lock = asyncio.Lock()
        self._closed = False

    async def start(self, offer_sdp, ice_servers):
        async with self._lock:
            if not self._closed:
                async with asyncio.timeout(10):
                    await self._client.send(WebRTCOffer(offer_sdp, ice_servers))

    def _on_message(self, message):
        if self._closed:
            return
        match message:
            case WebRTCAnswer(sdp=sdp):
                self._send_message(HAWebRTCAnswer(sdp))
            case WebRTCCandidate(candidate=candidate):
                self._send_message(HAWebRTCCandidate(RTCIceCandidateInit(candidate)))
            case WsError():
                self._hass.async_create_task(
                    self.fail(
                        "go2rtc could not play the stream. Check its name and go2rtc logs."
                    )
                )

    async def fail(self, message):
        if not self._closed:
            try:
                self._send_message(WebRTCError("tapo_go2rtc_playback_failed", message))
            finally:
                await self.close()

    async def add_candidate(self, candidate):
        async with self._lock:
            if (
                not self._closed
                and self._client.connected
                and candidate.get("candidate")
            ):
                await self._client.send(WebRTCCandidate(candidate["candidate"]))

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._on_close()
        async with self._lock:
            await self._client.close()
