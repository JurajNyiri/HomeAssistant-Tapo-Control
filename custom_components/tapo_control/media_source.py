"""
TODO:

- Background scheduled task which automatically downloads and caches videos per selected period (and deletes old stuff and hot/cold storage)
- Handle weird error that sometimes happens causing downloader to get stuck and never recovers until restart
"""

from __future__ import annotations


import asyncio
from typing import Optional
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

from .const import (
    DOMAIN,
    LOGGER,
    MEDIA_VIEW_DAYS_ORDER,
    MEDIA_VIEW_RECORDINGS_ORDER,
    RECORDINGS_UNAVAILABLE_MESSAGE,
)

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

    def _map_recordings_exception(self, err: Exception) -> str:
        err_msg = str(err)
        if "-71105" in err_msg:
            return RECORDINGS_UNAVAILABLE_MESSAGE
        return "Unable to retrieve recordings, please try again later."

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    def _format_clip_label(self, start_ts: int, end_ts: int) -> str:
        start_dt = dt.as_local(dt.utc_from_timestamp(int(start_ts)))
        end_dt = dt.as_local(dt.utc_from_timestamp(int(end_ts)))
        return (
            f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')} - {end_dt.strftime('%H:%M:%S')}"
        )

    def _build_notification_id(self, entry_id: str, child_id: str) -> str:
        suffix = child_id if child_id else "root"
        return f"{DOMAIN}_recording_download_{entry_id}_{suffix}"

    def _schedule_notification(self, coro):
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop == self.hass.loop:
            self.hass.async_create_task(coro)
        else:
            asyncio.run_coroutine_threadsafe(coro, self.hass.loop)

    async def _async_create_download_notification(
        self, notification_id: str, title: str, message: str
    ) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
            blocking=False,
        )

    async def _async_dismiss_download_notification(self, notification_id: str) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=False,
        )

    def _build_progress_notifier(
        self, notification_id: str, main_title: str, sub_title: str
    ):
        def notifier(
            message: str,
            progress: Optional[float] = None,
            total: Optional[float] = None,
        ):
            friendly_message = message
            if progress is not None and total is not None and total > 0:
                percent = round((float(progress) / float(total)) * 100)
                friendly_message = (
                    f"Downloading... {percent}% ({round(progress)} / {round(total)})"
                )

            full_message = (
                f"{sub_title}\n{friendly_message}\n\n"
                "Download runs in the background; check this notification for progress.\n\n"
                "When browsing during downloading, only downloaded recordings are visible."
            )
            self._schedule_notification(
                self._async_create_download_notification(
                    notification_id, main_title, full_message
                )
            )

        return notifier

    def _get_entry_data(self, entry_id: str) -> dict:
        """Return entry data or raise a user facing error if setup is incomplete."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
        if not entry_data or "name" not in entry_data or "isParent" not in entry_data:
            raise Unresolvable(
                "Camera setup has not finished yet. Recordings will be available once the device is connected."
            )
        return entry_data

    def _manual_download_active(self, device: dict) -> bool:
        """Return True when a user-triggered download is running (not media sync)."""
        return bool(
            device.get("isDownloadingStream") and not device.get("runningMediaSync")
        )

    def _any_download_active(self, device: dict) -> bool:
        """Return True when a download is running."""
        return bool(device.get("isDownloadingStream"))

    def _local_date_key(self, ts_utc: int, tz_offset: int) -> str:
        """Return YYYY-MM-DD string for a timestamp adjusted by timezone offset."""
        local_dt = dt.as_local(dt.utc_from_timestamp(ts_utc - tz_offset))
        return local_dt.strftime("%Y-%m-%d")

    def _parse_download_meta(
        self, meta: dict, file_key: str
    ) -> tuple[int | None, int | None]:
        """Extract start/end timestamps from stored download metadata."""
        if not isinstance(meta, dict):
            LOGGER.debug(
                "[media_source] Skipping downloaded entry %s: metadata not a dict (%s)",
                file_key,
                meta,
            )
            return None, None

        if "startDate" in meta and "endDate" in meta:
            try:
                return int(meta["startDate"]), int(meta["endDate"])
            except Exception:
                LOGGER.debug(
                    "[media_source] Skipping downloaded entry %s: invalid start/end in metadata %s",
                    file_key,
                    meta,
                )
                return None, None

        # Legacy form: keys are timestamps (and values mirror keys).
        numeric_vals = []
        for key, val in meta.items():
            for candidate in (key, val):
                try:
                    numeric_vals.append(int(candidate))
                except Exception:
                    continue

        if len(numeric_vals) >= 2:
            numeric_vals = sorted(set(numeric_vals))
            return numeric_vals[0], numeric_vals[-1]

        LOGGER.debug(
            "[media_source] Skipping downloaded entry %s due to unrecognized metadata: %s",
            file_key,
            meta,
        )
        return None, None

    def _get_downloaded_recordings_for_device(
        self, device: dict, date_key: str | None = None
    ):
        """Return downloaded recordings metadata filtered by optional date key."""
        results = []
        tz_offset = device.get("timezoneOffset", 0)
        normalized_filter = date_key.replace("-", "") if date_key else None
        for file_key, meta in device.get("downloadedStreams", {}).items():
            start_ts, end_ts = self._parse_download_meta(meta, file_key)
            if start_ts is None or end_ts is None:
                continue

            computed_key = self._local_date_key(start_ts, tz_offset)
            if normalized_filter:
                computed_normalized = computed_key.replace("-", "")
                if computed_normalized != normalized_filter:
                    continue

            results.append(
                {
                    "startDate": start_ts,
                    "endDate": end_ts,
                    "date_key": self._local_date_key(start_ts, tz_offset),
                }
            )
        return results

    def _normalize_camera_date(self, date: str) -> str:
        """Camera API expects dates without dashes."""
        return date.replace("-", "")

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

                fileName = getFileName(startDate, endDate, False, childID=childID)

                # If we need to fetch the clip, do it in the background and guide the user.
                if fileName not in device["downloadedStreams"]:
                    notification_id = self._build_notification_id(entry, childID)
                    clip_label = self._format_clip_label(int(startDate), int(endDate))
                    main_title = f"{device['name']}: Downloading..."
                    sub_title = f"{device['name']} - {clip_label}"
                    progress_notifier = self._build_progress_notifier(
                        notification_id, main_title, sub_title
                    )
                    progress_notifier(
                        "Starting download. This runs in the background; the player will open when ready."
                    )

                    async def _download_and_prepare():
                        try:
                            await getRecording(
                                self.hass,
                                tapoController,
                                entry,
                                device,
                                self._normalize_camera_date(date),
                                startDate,
                                endDate,
                                progress_callback=progress_notifier,
                            )
                            # Prepare hot path so the next click can play instantly.
                            await getWebFile(
                                self.hass,
                                entry,
                                startDate,
                                endDate,
                                "videos",
                                childID=childID,
                            )
                        except Exception as err:
                            progress_notifier(f"Download failed: {err}")
                            LOGGER.error(err)
                        else:
                            await self._async_dismiss_download_notification(
                                notification_id
                            )

                    self.hass.async_create_task(_download_and_prepare())
                    raise Unresolvable(
                        "Recording download started in the background. Track progress in notifications, then try again once it finishes."
                    )

                # Already downloaded: return the playable URL.
                try:
                    url = await getWebFile(
                        self.hass,
                        entry,
                        startDate,
                        endDate,
                        "videos",
                        childID=childID,
                    )
                    LOGGER.debug(url)
                except Exception as e:
                    LOGGER.error(e)
                    raise Unresolvable(e)
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
        cached_only = self._any_download_active(device)
        downloaded = self._get_downloaded_recordings_for_device(device, date_key=date)

        def _add_clip(target: dict, start_ts: int, end_ts: int):
            start_local = dt.as_local(
                dt.utc_from_timestamp(start_ts - device["timezoneOffset"])
            )
            end_local = dt.as_local(
                dt.utc_from_timestamp(end_ts - device["timezoneOffset"])
            )
            target[(start_ts, end_ts)] = {
                "name": f"{start_local.strftime('%H:%M:%S')} - {end_local.strftime('%H:%M:%S')}",
                "startDate": start_ts,
                "endDate": end_ts,
            }

        # Collect clips keyed by (start, end) to merge camera data with cached items.
        clips: dict[tuple[int, int], dict] = {}

        if cached_only:
            LOGGER.debug(
                "[media_source] Using cached clips only for date %s; manual_download=%s; downloadedStreams keys: %s",
                date,
                cached_only,
                list(device.get("downloadedStreams", {}).keys()),
            )
        else:
            recordingsForDay = []
            camera_date = self._normalize_camera_date(date)
            try:
                recordingsForDay = await getRecordings(
                    self.hass, device, tapoController, camera_date
                )
            except Exception as err:
                LOGGER.error(
                    "Unable to fetch recordings for %s on %s: %s",
                    device["name"],
                    date,
                    err,
                )
                recordingsForDay = []
                if not downloaded:
                    raise Unresolvable(self._map_recordings_exception(err)) from err
            for searchResult in recordingsForDay:
                for key in searchResult:
                    _add_clip(
                        clips,
                        searchResult[key]["startTime"],
                        searchResult[key]["endTime"],
                    )

        # Merge in cached clips
        for item in downloaded:
            _add_clip(clips, item["startDate"], item["endDate"])

        videoNames = sorted(
            clips.values(),
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
        cached_only = self._any_download_active(device)

        if cached_only:
            downloaded = self._get_downloaded_recordings_for_device(device)
            recordingsDates = list(
                {item["date_key"] for item in downloaded if "date_key" in item}
            )
            if not recordingsDates:
                LOGGER.debug(
                    "[media_source] No cached dates available while in cached-only mode."
                )
                # Show an empty list
                return self.generateView(
                    build_identifier(query),
                    title,
                    False,
                    True,
                    children=[],
                )
        else:
            if device["usingCloudPassword"] is False:
                raise Unresolvable(
                    "Cloud password is required in order to play recordings.\nSet cloud password inside Settings > Devices & Services > Tapo: Cameras Control > Configure."
                )
            try:
                recordingsList = await self.hass.async_add_executor_job(
                    tapoController.getRecordingsList
                )
            except Exception as err:
                LOGGER.error(
                    "Unable to fetch recordings list for %s: %s", device["name"], err
                )
                raise Unresolvable(self._map_recordings_exception(err)) from err
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
            children = []
            for entry_id, entry_data in self.hass.data.get(DOMAIN, {}).items():
                name = entry_data.get("name")
                if not name:
                    LOGGER.debug(
                        "Skipping media browse for %s because setup is incomplete",
                        entry_id,
                    )
                    continue
                children.append(
                    self.generateView(
                        build_identifier({"entry": entry_id, "title": name}),
                        name,
                        False,
                        True,
                    )
                )
            return self.generateView(
                build_identifier(),
                self.name,
                False,
                True,
                children=children,
            )
        else:
            path = item.identifier.split("/")
            if len(path) != 2:
                raise Exception("Incorrect path, try navigating from Media again.")

            query = parse_identifier(path[1])
            entry = query["entry"]
            entry_data = self._get_entry_data(entry)
            isParent = entry_data["isParent"]
            title = query["title"]
            device = entry_data
            if isParent is True:
                if "childID" in query:
                    childID = query["childID"]
                    for child in entry_data["childDevices"]:
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
                    entry_data["name"],
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
                        for childDevice in entry_data["childDevices"]
                    ],
                )
            else:
                raise Exception("Unexpected path.")
