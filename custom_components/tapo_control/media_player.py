import asyncio
from urllib.parse import urlsplit

from pytapo.media_stream.talk import Talk

from homeassistant.components import media_source
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .tapo.entities import TapoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.debug("Setting up media players")
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]

    def setupEntities(entry):
        players = []
        if entry["camData"].get("music_config") is not None:
            players.append(TapoMusicPlayer(entry, hass))
        if (
            entry["camData"].get("speakerVolume") is not None
            and entry["controller"].cloudPassword
        ):
            players.append(TapoSpeaker(entry, hass))
        return players

    media_players = setupEntities(entry)
    for childDevice in entry["childDevices"]:
        media_players.extend(setupEntities(childDevice))

    async_add_entities(media_players)


class TapoSpeaker(MediaPlayerEntity, TapoEntity):
    """Play audio through the camera's existing speaker backchannel."""

    _attr_has_entity_name = True
    _attr_translation_key = "speaker"
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_should_poll = False
    _attr_state = MediaPlayerState.IDLE
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    name = MediaPlayerEntity.name

    def __init__(self, entry: dict, hass: HomeAssistant):
        self._hass = hass
        self._ffmpeg = hass.data[DATA_FFMPEG].binary
        self._play_task = None
        self._talk = None
        self._play_lock = asyncio.Lock()
        entry["entities"].append({"entity": self, "entry": entry})
        TapoEntity.__init__(self, entry, "Speaker")
        MediaPlayerEntity.__init__(self)
        self.updateTapo(entry["camData"])

    def updateTapo(self, camData):
        volume = camData.get("speakerVolume") if camData else None
        self._attr_available = volume is not None
        if volume is not None:
            self._attr_volume_level = int(volume) / 100

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        return await media_source.async_browse_media(
            self._hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_play_media(self, media_type, media_id, **kwargs):
        if kwargs.get("enqueue") not in (None, "replace"):
            raise HomeAssistantError("The camera speaker does not support a queue")
        if media_source.is_media_source_id(media_id):
            media = await media_source.async_resolve_media(
                self._hass, media_id, self.entity_id
            )
            media_id = media.url
        media_id = async_process_play_media_url(self._hass, media_id)
        if urlsplit(media_id).scheme not in ("http", "https"):
            raise HomeAssistantError("Use an HTTP(S) audio URL or a media source")

        async with self._play_lock:
            await self._stop_playback()
            talk = Talk(self._controller, on_interrupt=self.async_media_stop)
            try:
                await talk.__aenter__()
            except Exception as err:
                raise HomeAssistantError(str(err)) from err
            try:
                self._talk = talk
                self._attr_state = MediaPlayerState.PLAYING
                self.async_write_ha_state()
                self._play_task = self._hass.async_create_background_task(
                    self._play(talk, media_id),
                    "Tapo speaker playback",
                    eager_start=False,
                )
            except BaseException:
                await talk.close()
                self._talk = None
                self._attr_state = MediaPlayerState.IDLE
                raise

    async def _play(self, talk, media_id):
        try:
            await talk.play(media_id, ffmpeg=self._ffmpeg)
        except Exception as err:
            LOGGER.error("Camera speaker playback failed: %s", err)
        finally:
            try:
                await talk.close()
            finally:
                self._talk = None
                self._attr_state = MediaPlayerState.IDLE
                self.async_write_ha_state()

    async def _stop_playback(self):
        if self._play_task is not None:
            self._play_task.cancel()
            await asyncio.gather(self._play_task, return_exceptions=True)
            self._play_task = None
        # A task cancelled before its first step never runs its finally block.
        if self._talk is not None:
            await self._talk.close()
            self._talk = None
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()

    async def async_media_stop(self):
        async with self._play_lock:
            await self._stop_playback()

    async def async_will_remove_from_hass(self):
        await self.async_media_stop()
        await super().async_will_remove_from_hass()

    async def async_set_volume_level(self, volume):
        result = await self._hass.async_add_executor_job(
            self._controller.setSpeakerVolume, round(volume * 100)
        )
        if result.get("error_code", 0) != 0:
            raise HomeAssistantError("The camera rejected the speaker volume")
        self._attr_volume_level = volume
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()


class TapoMusicPlayer(MediaPlayerEntity, TapoEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "music_player"
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    # State is pushed by the coordinator via updateTapo. Polling would refresh
    # the coordinator every 10 seconds, the media_player platform default.
    _attr_should_poll = False

    # Use HA's translated name instead of TapoEntity's legacy name property.
    name = MediaPlayerEntity.name

    def __init__(self, entry: dict, hass: HomeAssistant):
        self._hass = hass
        self._song_names = []
        self._song_count = 0
        self._song_index = None
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )
        entry["entities"].append({"entity": self, "entry": entry})
        self.updateTapo(entry["camData"])

        TapoEntity.__init__(self, entry, "Music Player")
        MediaPlayerEntity.__init__(self)

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    def updateTapo(self, camData):
        music_config = camData.get("music_config") if camData else None
        self._attr_available = music_config is not None
        if music_config is None:
            return
        # The list is refreshed with every update, so songs uploaded in the
        # Tapo app show up without restarting Home Assistant.
        self._song_names = camData.get("music_list") or []
        self._attr_source_list = self._song_names or None
        self._attr_state = (
            MediaPlayerState.PLAYING
            if music_config["play_state"] == "Playing"
            else MediaPlayerState.PAUSED
        )
        self._attr_volume_level = music_config["volume"] / 100
        if music_config.get("playmode") is not None:
            self._attr_repeat = (
                RepeatMode.ONE
                if int(music_config["playmode"]) == 0
                else RepeatMode.ALL
            )
        self._song_count = int(music_config.get("songnum", len(self._song_names)))
        self._setSongIndex(music_config["songindex"])

    def _setSongIndex(self, index: int) -> None:
        self._song_index = index
        if 0 <= index < len(self._song_names):
            self._attr_source = self._song_names[index]
            self._attr_media_title = self._song_names[index]
        else:
            self._attr_source = None
            self._attr_media_title = None

    async def _setMusicState(self, play: bool, songIndex: int = None) -> None:
        result = await self._hass.async_add_executor_job(
            self._controller.setMusicState, play, songIndex
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_state = (
                MediaPlayerState.PLAYING if play else MediaPlayerState.PAUSED
            )
            if songIndex is not None:
                self._setSongIndex(songIndex)
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        await self._setMusicState(True)

    async def async_media_pause(self) -> None:
        await self._setMusicState(False)

    async def async_media_next_track(self) -> None:
        if self._song_count and self._song_index is not None:
            await self._setMusicState(True, (self._song_index + 1) % self._song_count)

    async def async_media_previous_track(self) -> None:
        if self._song_count and self._song_index is not None:
            await self._setMusicState(True, (self._song_index - 1) % self._song_count)

    async def async_select_source(self, source: str) -> None:
        # Selecting a track starts playback, matching the Tapo app.
        await self._setMusicState(True, self._song_names.index(source))

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        # The camera only supports repeating one song (0) or the playlist (1).
        # There is no "off", so OFF falls back to repeating the playlist.
        repeat = RepeatMode.ONE if repeat == RepeatMode.ONE else RepeatMode.ALL
        result = await self._hass.async_add_executor_job(
            self._controller.setMusicConfig,
            None,
            0 if repeat == RepeatMode.ONE else 1,
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_repeat = repeat
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        volume = round(volume * 100)
        result = await self._hass.async_add_executor_job(
            self._controller.setMusicConfig, volume
        )
        if "error_code" not in result or result["error_code"] == 0:
            self._attr_volume_level = volume / 100
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()
