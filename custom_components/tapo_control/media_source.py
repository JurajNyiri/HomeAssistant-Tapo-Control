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

import json
from urllib.parse import urlencode, urlparse, parse_qsl


async def async_get_media_source(hass: HomeAssistant) -> TapoMediaSource:
    """Set up Radio Browser media source."""
    LOGGER.debug("async_get_media_source")
    # TODO: handle case where cloud password was not set with nice error

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return TapoMediaSource(hass, entry)


def build_identifier(
    params: dict[str, str | list[str]] = None, base: str = DOMAIN
) -> str:
    if params is None:
        return f"{base}"
    query = urlencode(params, doseq=True)
    return f"{base}/?{query}"


def parse_identifier(identifier: str) -> dict[str, str]:
    query = urlparse(identifier).query
    return dict(parse_qsl(query, keep_blank_values=True))


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
        if len(path) == 2:
            try:
                query = parse_identifier(path[1])
                LOGGER.debug(query)
                entry = query["entry"]
                date = query["date"]
                startDate = query["startDate"]
                endDate = query["endDate"]
                childID = ""
                isParent = self.hass.data[DOMAIN][entry]["isParent"]
                device = self.hass.data[DOMAIN][entry]

                if isParent is True:
                    childID = query["childID"]
                    for child in self.hass.data[DOMAIN][entry]["childDevices"]:
                        if child["camData"]["basic_info"]["dev_id"] == childID:
                            device = child
                            break

                tapoController: Tapo = device["controller"]

                if (
                    device["isDownloadingStream"]
                    and getFileName(startDate, endDate, False, childID=childID)
                    not in device["downloadedStreams"]
                ):
                    raise Unresolvable(
                        "Already downloading a recording, please try again later."
                    )

                LOGGER.debug(startDate)
                LOGGER.debug(endDate)

                await getRecording(
                    self.hass, tapoController, entry, device, date, startDate, endDate
                )
                url = await getWebFile(
                    self.hass, entry, startDate, endDate, "videos", childID=childID
                )
                LOGGER.debug(url)
            except Exception as e:
                LOGGER.error(e)
                raise Unresolvable(e)

            return PlayMedia(url, "video/mp4")
        else:
            raise Unresolvable("Unexpected path.")

    async def generateVideosForDate(self, query, title, entry, date, device):
        tapoController = device["controller"]
        childID = ""
        if "childID" in query:
            childID = query["childID"]
        media_view_recordings_order = self.hass.data[DOMAIN][entry]["entry"].data.get(
            MEDIA_VIEW_RECORDINGS_ORDER
        )
        if device["initialMediaScanDone"] is False:
            raise Unresolvable(
                "Initial local media scan still running, please try again later."
            )
        recordingsForDay = await getRecordings(self.hass, device, tapoController, date)
        videoNames = []
        for searchResult in recordingsForDay:
            for key in searchResult:
                startTS = searchResult[key]["startTime"] - device["timezoneOffset"]
                endTS = searchResult[key]["endTime"] - device["timezoneOffset"]
                startDate = dt.as_local(dt.utc_from_timestamp(startTS))
                endDate = dt.as_local(dt.utc_from_timestamp(endTS))
                videoName = (
                    f"{startDate.strftime('%H:%M:%S')} - {endDate.strftime('%H:%M:%S')}"
                )
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
            reverse=(True if media_view_recordings_order == "Descending" else False),
        )

        dateChildren = []
        for data in videoNames:
            fileName = getFileName(
                data["startDate"], data["endDate"], False, childID=childID
            )
            thumbLink = None
            if fileName in device["downloadedStreams"]:
                thumbLink = await getWebFile(
                    self.hass,
                    entry,
                    data["startDate"],
                    data["endDate"],
                    "thumbs",
                    childID=childID,
                )

            dateChildren.append(
                self.generateView(
                    build_identifier(
                        {
                            **query,
                            "title": data["name"],
                            "startDate": data["startDate"],
                            "endDate": data["endDate"],
                        }
                    ),
                    data["name"],
                    True,
                    False,
                    thumbnail=thumbLink,
                )
            )

        return self.generateView(
            build_identifier(query), title, False, True, children=dateChildren
        )

    async def generateDates(self, query, title, entry, device):
        tapoController = device["controller"]
        media_view_days_order = self.hass.data[DOMAIN][entry]["entry"].data.get(
            MEDIA_VIEW_DAYS_ORDER
        )
        if device["initialMediaScanDone"] is False:
            raise Unresolvable(
                "Initial local media scan still running, please try again later."
            )

        if device["usingCloudPassword"] is False:
            raise Unresolvable(
                "Cloud password is required in order to play recordings.\nSet cloud password inside Settings > Devices & Services > Tapo: Cameras Control > Configure."
            )
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

        return self.generateView(
            build_identifier(query),
            title,
            False,
            True,
            children=[
                self.generateView(
                    build_identifier({**query, "title": date, "date": date}),
                    date,
                    False,
                    True,
                )
                for date in recordingsDates
            ],
        )

    def generateView(
        self, identifier, title, can_play, can_expand, thumbnail=None, children=None
    ):
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=title,
            can_play=can_play,
            can_expand=can_expand,
            thumbnail=thumbnail,
            children_media_class=MediaClass.DIRECTORY,
            children=children,
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        if item.identifier is None:
            return self.generateView(
                build_identifier(),
                self.name,
                False,
                True,
                children=[
                    self.generateView(
                        build_identifier(
                            {
                                "entry": entry,
                                "title": self.hass.data[DOMAIN][entry]["name"],
                            }
                        ),
                        self.hass.data[DOMAIN][entry]["name"],
                        False,
                        True,
                    )
                    for entry in self.hass.data[DOMAIN]
                ],
            )
        else:
            path = item.identifier.split("/")
            if len(path) != 2:
                raise Exception("Incorrect path, try navigating from Media again.")

            query = parse_identifier(path[1])
            entry = query["entry"]
            isParent = self.hass.data[DOMAIN][entry]["isParent"]
            title = query["title"]
            device = self.hass.data[DOMAIN][entry]
            if isParent is True:
                if "childID" in query:
                    childID = query["childID"]
                    for child in self.hass.data[DOMAIN][entry]["childDevices"]:
                        if child["camData"]["basic_info"]["dev_id"] == childID:
                            device = child
                            break

            if "date" in query:
                return await self.generateVideosForDate(
                    query, title, entry, query["date"], device
                )
            elif isParent is False or (isParent is True and "childID" in query):
                return await self.generateDates(query, title, entry, device)
            elif isParent is True:
                return self.generateView(
                    build_identifier(query),
                    self.hass.data[DOMAIN][entry]["name"],
                    False,
                    True,
                    children=[
                        self.generateView(
                            build_identifier(
                                {
                                    **query,
                                    "title": childDevice["name"],
                                    "childID": childDevice["camData"]["basic_info"][
                                        "dev_id"
                                    ],
                                }
                            ),
                            childDevice["name"],
                            False,
                            True,
                        )
                        for childDevice in self.hass.data[DOMAIN][entry]["childDevices"]
                    ],
                )
            else:
                raise Exception("Unexpected path.")
