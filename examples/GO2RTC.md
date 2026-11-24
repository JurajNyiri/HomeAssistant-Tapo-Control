# Use an existing go2rtc stream with Native WebRTC

Tapo: Cameras Control 7.3.10 and later can play a saved go2rtc stream through Native WebRTC. Multiple viewers can share the same camera connection.

Reusing the go2rtc stream skips the extra video encode in Tapo: Cameras Control. This reduces CPU load on Home Assistant, especially when several people are watching.

## Save the stream in go2rtc

Always save the stream under `streams:` in `go2rtc.yaml`. Opening a dashboard card with an RTSP camera entity can create a temporary stream in go2rtc. That stream may appear in the web UI and disappear after you change the camera's stream source. If the stream is already saved in `go2rtc.yaml`, use its existing name.

To add a stream, replace the camera address and Tapo Camera Account credentials in this example. [go2rtc configuration](https://go2rtc.org/#configuration)

```yaml
streams:
  front_door: "rtsp://CAMERA_USER:CAMERA_PASSWORD@192.0.2.10:554/stream1"
```

For a compatible camera, go2rtc can also use a `tapo://` source with your Tapo cloud password. [go2rtc TP-Link Tapo setup](https://go2rtc.org/internal/tapo/#configuration)

```yaml
streams:
  front_door: "tapo://CLOUD_PASSWORD@192.0.2.10"
```

Restart go2rtc and check that `front_door` plays in its web UI. The steps below use `192.0.2.20` as the go2rtc server address.

## Configure Home Assistant

1. Open **Tapo: Cameras Control**, select the camera and open **Configure device**.
2. Set **Live view mode** to **Native WebRTC (experimental)**.
3. Set **Custom stream link (HD)** to `rtsp://192.0.2.20:8554/front_door` for either go2rtc source. Use the name you saved in go2rtc. Set the SD link separately if you have an SD stream.
4. Set **go2rtc API URL for Native WebRTC playback** to `http://192.0.2.20:1984` using the same go2rtc server.
5. Save and open the matching HD or SD entity in Home Assistant.

## Dashboards and two-way audio

Use the camera entity in a Home Assistant card such as picture-entity. In Advanced Camera Card, set `live_provider: ha` for the same entity. [Picture-entity example](EXAMPLES_LOVELACE.md#native-live-view), [Advanced Camera Card live providers](https://github.com/dermotduffy/advanced-camera-card/blob/main/docs/configuration/cameras/live-provider.md#ha)

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.front_door_hd_stream
    live_provider: ha
```

Talk still uses the Tapo integration. [Two-way audio setup](../README.md#two-way-audio-preview)
