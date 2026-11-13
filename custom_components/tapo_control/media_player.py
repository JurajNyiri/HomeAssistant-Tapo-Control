from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        if entry["camData"].get("music_config") is None:
            return []
        LOGGER.debug("Adding TapoMusicPlayer...")
        return [TapoMusicPlayer(entry, hass)]

    media_players = setupEntities(entry)
    for childDevice in entry["childDevices"]:
        media_players.extend(setupEntities(childDevice))

    async_add_entities(media_players)


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
