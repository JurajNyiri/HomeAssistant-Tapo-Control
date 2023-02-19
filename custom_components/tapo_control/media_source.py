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

from pytapo import Tapo
from datetime import datetime, timezone


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
        LOGGER.warn(item)
        raise Unresolvable("Not implemented yet.")
        LOGGER.warn("TODO async_resolve_media")

    async def async_browse_media(self, item: MediaSourceItem,) -> BrowseMediaSource:

        if item.identifier is None:
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="tapo",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=self.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
                children=[
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"tapo/{entry}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaType.VIDEO,
                        title=self.hass.data[DOMAIN][entry]["name"],
                        can_play=False,
                        can_expand=True,
                    )
                    for entry in self.hass.data[DOMAIN]
                ],
            )
        else:
            path = item.identifier.split("/")
            if len(path) == 2:
                entry = path[1]
                tapoController: Tapo = self.hass.data[DOMAIN][entry]["controller"]
                recordingsList = await self.hass.async_add_executor_job(
                    tapoController.getRecordingsList
                )
                recordingsDates = []
                for searchResult in recordingsList:
                    for key in searchResult:
                        recordingsDates.append(searchResult[key]["date"])
                return BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"tapo/{entry}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=self.hass.data[DOMAIN][entry]["name"],
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                    children=[
                        BrowseMediaSource(
                            domain=DOMAIN,
                            identifier=f"tapo/{entry}/{date}",
                            media_class=MediaClass.DIRECTORY,
                            media_content_type=MediaType.VIDEO,
                            title=date,
                            can_play=False,
                            can_expand=True,
                        )
                        for date in recordingsDates
                    ],
                )
            elif len(path) == 3:
                entry = path[1]
                date = path[2]
                tapoController: Tapo = self.hass.data[DOMAIN][entry]["controller"]
                recordingsForDay = await self.hass.async_add_executor_job(
                    tapoController.getRecordings, date
                )
                videoNames = []
                for searchResult in recordingsForDay:
                    for key in searchResult:
                        # todo: check if this works
                        startTS = searchResult[key]["startTime"]
                        endTS = searchResult[key]["endTime"]
                        timezoneDiff = -1 * (
                            int(datetime.now().timestamp())
                            - int(
                                datetime.now().replace(tzinfo=timezone.utc).timestamp()
                            )
                        )

                        startDate = datetime.fromtimestamp(startTS + timezoneDiff)
                        endDate = datetime.fromtimestamp(endTS + timezoneDiff)
                        videoName = f"{startDate.strftime('%H:%M:%S')} - {endDate.strftime('%H:%M:%S')}"
                        videoNames.append(
                            {"name": videoName, "startDate": startTS, "endDate": endTS}
                        )

                return BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"tapo/{entry}/",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=f"{self.hass.data[DOMAIN][entry]['name']} - {date}",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                    children=[
                        BrowseMediaSource(
                            domain=DOMAIN,
                            identifier=f"tapo/{entry}/{date}/{data['startDate']}/{data['endDate']}",
                            media_class=MediaClass.VIDEO,
                            media_content_type=MediaType.VIDEO,
                            title=data["name"],
                            can_play=True,
                            can_expand=False,
                        )
                        for data in videoNames
                    ],
                )

            else:
                LOGGER.error("Not implemented")

