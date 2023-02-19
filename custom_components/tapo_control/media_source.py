from __future__ import annotations


from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER


async def async_get_media_source(hass: HomeAssistant) -> TapoMediaSource:
    """Set up Radio Browser media source."""
    LOGGER.warn("async_get_media_source")

    # Radio browser support only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return TapoMediaSource(hass, entry)


class TapoMediaSource(MediaSource):
    """Provide Radio stations as media sources."""

    name = "Tapo: Recordings"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        LOGGER.warn("TODO async_resolve_media")

    async def async_browse_media(self, item: MediaSourceItem,) -> BrowseMediaSource:

        for key in self.hass.data[DOMAIN]:
            LOGGER.warn(key)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=self.hass.data[DOMAIN][entry]["name"],
                    can_play=False,
                    can_expand=True,
                )
                for entry in self.hass.data[DOMAIN]
            ],
        )
