"""
TODO:

- Background scheduled task which automatically downloads and caches videos per selected period (and deletes old stuff and hot/cold storage)
- Handle weird error that sometimes happens causing downloader to get stuck and never recovers until restart
"""


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
from homeassistant.util import dt

from .const import DOMAIN, LOGGER, MEDIA_VIEW_DAYS_ORDER, MEDIA_VIEW_RECORDINGS_ORDER

from .utils import (
    getRecording,
    getFileName,
    getRecordings,
    getWebFile,
)

from pytapo import Tapo


async def async_get_media_source(hass: HomeAssistant) -> TapoMediaSource:
    """Set up Radio Browser media source."""
    LOGGER.debug("async_get_media_source")
    # TODO: handle case where cloud password was not set with nice error

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
        path = item.identifier.split("/")
        if len(path) == 5:
            try:
                entry = path[1]
                date = path[2]
                startDate = int(path[3])
                endDate = int(path[4])
                if (
                    self.hass.data[DOMAIN][entry]["isDownloadingStream"]
                    and getFileName(startDate, endDate, False)
                    not in self.hass.data[DOMAIN][entry]["downloadedStreams"]
                ):
                    raise Unresolvable(
                        "Already downloading a recording, please try again later."
                    )
                tapoController: Tapo = self.hass.data[DOMAIN][entry]["controller"]

                LOGGER.debug(startDate)
                LOGGER.debug(endDate)

                await getRecording(
                    self.hass, tapoController, entry, date, startDate, endDate
                )
                url = getWebFile(self.hass, entry, startDate, endDate, "videos")
                LOGGER.debug(url)
            except Exception as e:
                LOGGER.error(e)
                raise Unresolvable(e)

            return PlayMedia(url, "video/mp4")
        else:
            raise Unresolvable("Incorrect path.")

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
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
                media_view_days_order = self.hass.data[DOMAIN][entry]["entry"].data.get(
                    MEDIA_VIEW_DAYS_ORDER
                )
                if self.hass.data[DOMAIN][entry]["initialMediaScanDone"] is False:
                    raise Unresolvable(
                        "Initial local media scan still running, please try again later."
                    )

                if self.hass.data[DOMAIN][entry]["usingCloudPassword"] is False:
                    raise Unresolvable(
                        "Cloud password is required in order to play recordings.\nSet cloud password inside Settings > Devices & Services > Tapo: Cameras Control > Configure."
                    )
                tapoController: Tapo = self.hass.data[DOMAIN][entry]["controller"]
                recordingsList = await self.hass.async_add_executor_job(
                    tapoController.getRecordingsList
                )
                recordingsDates = []
                for searchResult in recordingsList:
                    for key in searchResult:
                        recordingsDates.append(searchResult[key]["date"])

                recordingsDates.sort(
                    reverse=True if media_view_days_order == "Descending" else False
                )
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

                media_view_recordings_order = self.hass.data[DOMAIN][entry][
                    "entry"
                ].data.get(MEDIA_VIEW_RECORDINGS_ORDER)
                if self.hass.data[DOMAIN][entry]["initialMediaScanDone"] is False:
                    raise Unresolvable(
                        "Initial local media scan still running, please try again later."
                    )
                date = path[2]
                tapoController: Tapo = self.hass.data[DOMAIN][entry]["controller"]
                recordingsForDay = await getRecordings(self.hass, entry, date)
                videoNames = []
                for searchResult in recordingsForDay:
                    for key in searchResult:
                        startTS = (
                            searchResult[key]["startTime"]
                            - self.hass.data[DOMAIN][entry]["timezoneOffset"]
                        )
                        endTS = (
                            searchResult[key]["endTime"]
                            - self.hass.data[DOMAIN][entry]["timezoneOffset"]
                        )
                        startDate = dt.as_local(dt.utc_from_timestamp(startTS))
                        endDate = dt.as_local(dt.utc_from_timestamp(endTS))
                        videoName = f"{startDate.strftime('%H:%M:%S')} - {endDate.strftime('%H:%M:%S')}"
                        videoNames.append(
                            {
                                "name": videoName,
                                "startDate": searchResult[key]["startTime"],
                                "endDate": searchResult[key]["endTime"],
                            }
                        )

                videoNames = sorted(
                    videoNames,
                    key=lambda x: x["startDate"],
                    reverse=True
                    if media_view_recordings_order == "Descending"
                    else False,
                )

                dateChildren = []
                for data in videoNames:
                    fileName = getFileName(data["startDate"], data["endDate"], False)
                    if fileName in self.hass.data[DOMAIN][entry]["downloadedStreams"]:
                        thumbLink = getWebFile(
                            self.hass,
                            entry,
                            data["startDate"],
                            data["endDate"],
                            "thumbs",
                        )

                        dateChildren.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"tapo/{entry}/{date}/{data['startDate']}/{data['endDate']}",
                                media_class=MediaClass.VIDEO,
                                media_content_type=MediaType.VIDEO,
                                thumbnail=thumbLink,
                                title=data["name"],
                                can_play=True,
                                can_expand=False,
                            )
                        )
                    else:
                        dateChildren.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"tapo/{entry}/{date}/{data['startDate']}/{data['endDate']}",
                                media_class=MediaClass.VIDEO,
                                media_content_type=MediaType.VIDEO,
                                title=data["name"],
                                can_play=True,
                                can_expand=False,
                            )
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
                    children=dateChildren,
                )

            else:
                LOGGER.error("Not implemented")
