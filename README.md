# HomeAssistant - Tapo: Cameras Control

Custom component - Tapo: Cameras Control - to add Tapo cameras into Home Assistant

## Installation

Copy contents of custom_components/tapo_control/ to custom_components/tapo_control/ in your Home Assistant config folder.

## Installation using HACS

HACS is a community store for Home Assistant. You can install [HACS](https://github.com/custom-components/hacs) and then install Tapo: Camera Control from the HACS store.

## Requirements

### Network

Following target TCP (v)LAN ports **must be open** in firewall for the camera to access your Tapo Camera from Home Assistant:

- 443 - HTTPS for control of the camera ([services](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control#services))
- 554 - RTSP to fetch video stream from the camera
- 2020 - ONVIF to track detected movement via a binary sensor

**These are not WAN ports, _DO NOT_ OPEN WAN PORTS VIA PORT FORWARDING. You might need to open (v)lan ports _only_ if you know what all of this means.**

## Usage

Add cameras via Integrations (search for Tapo) in Home Assistant UI. You can also simply click the button below if you have MyHomeAssistant redirects set up.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tapo_control)

Cameras are also automatically discovered when they are (re)connected to WIFI.

To add multiple cameras, add integration multiple times.

See [examples for lovelace cards](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/blob/main/examples/EXAMPLES_LOVELACE.md).

## Quick Start

This custom component creates:

- Camera entities, one for HD and one for SD stream
- Binary sensor for motion after the motion is detected for the first time
- Light entity, if the camera supports a floodlight switch
- Buttons for Calibrate, Format, Manual Alarm start & stop, Moving the camera, Reboot and syncing time
- Switch entities for auto track, Flip setting, LED Indicator, Lens Distortion Correction and Privacy mode
- Select entities for Automatic Alarm, Light Frequency, Motion Detection, Night Vision and Move to Preset
- Number entity for Movement Angle
- And finally 2 tapo_control.\* services to control a camera

Use these services in following service calls.

<details>
  <summary>tapo_control.save_preset</summary>

Saves the current PTZ position to a preset

- **name** Required: Name of the preset. Cannot be empty or a number
</details>

<details>
  <summary>tapo_control.delete_preset</summary>

Deletes a preset

- **preset** Required: PTZ preset ID or a Name. See possible presets in entity attributes
</details>

## Sound Detection

Integration is capable of analysing sound from camera microphone and expose a new attribute noise_detected on cameras when a voice threshold is reached.

You need to enable this feature in integration options by checking "Enable sound threshold detection". After enabling it, you can also set any other options starting with [Sound Detection]. You will need to restart Home Asssistant after doing any changes.

For more information and troubleshooting see [Home Assistant ffmpeg documentation](https://www.home-assistant.io/integrations/ffmpeg_noise/) on which this feature is based on.

## Troubleshooting | FAQ

<details>
  <summary>Binary sensor for motion doesn't show up or work</summary>

Motion sensor is added only after a motion is detected for the first time.

- Make sure the camera has motion detection turned on
- Make sure the camera has privacy mode turned off
- Make sure the camera can see you and your movement
- Try walking in front of the camera
- If above didn't work, restart the camera and try again

Also make sure that:

- binary sensor is not disabled via entity, check .storage/core.entity_registry for disabled entities, look for "disabled_by": "user" on platform "tapo_control". If it is, remove the whole entity or change to "disabled_by": null, and restart HASS.
- binary sensor is enabled in tapo integration options
- onvif port 2020 on camera is opened
</details>

<details>
  <summary>Big delay in camera stream</summary>

This is a [known issue](https://community.home-assistant.io/t/i-tried-all-the-camera-platforms-so-you-dont-have-to/222999) of Home Assistant.

There is an ability to disable usage of Home Assistant Stream component for the camera, which might lower the delay very significantly at cost of higher CPU usage.

You can choose to disable stream component when adding the camera, or via Options when camera has already been added. This change requires a restart of Home Assistant.

There might be some disadvantages to doing this, like losing option to control playback and a higher CPU usage.
Results depend on your hardware and future Home Assistant updates.

If you disable stream and your hardware is not up to the task, you will get artifacts, bigger delay and freezes.

If you wish, try it out and see what works best for you.

**Another possibility is using [WebRTC Camera by AlexxIT](https://github.com/AlexxIT/WebRTC).**

Example working configuration:

```
type: custom:webrtc-camera
entity: camera.bedroom_hd
```

</details>

<details>
  <summary>No audio in camera stream</summary>

Supported audio codecs in Home Assistant are "aac", "ac3" and "mp3".

Tapo Cameras use PCM ALAW (alaw) which is not supported.

[More details here.](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/58#issuecomment-762787442)

**You can get sound working using [WebRTC Camera by AlexxIT](https://github.com/AlexxIT/WebRTC).**

Example working configuration:

```
type: custom:webrtc-camera
entity: camera.bedroom_hd
```

</details>

<details>
  <summary>Supported models</summary>

Users reported full functionality with following Tapo Cameras:

- TC60
- TC70
- C100
- C110
- C200
- C210
- C310
- C320WS

The integration _should_ work with any other Tapo Cameras.

If you had success with some other model, please report it via a new issue.

</details>

## Have a comment or a suggestion?

Please [open a new issue](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/new/choose), or discuss on [Home Assistant: Community Forum](https://community.home-assistant.io/t/tapo-cameras-control/231795).

Join discussion on [Discord](https://discord.gg/pa54QyK).

## Thank you

- [Dale Pavey](https://research.nccgroup.com/2020/07/31/lights-camera-hacked-an-insight-into-the-world-of-popular-ip-cameras/) from NCC Group for the initial research on the Tapo C200
- [likaci](https://github.com/likaci) and [his github repository](https://github.com/likaci/mercury-ipc-control) for the research on the Mercury camera on which tapo is based
- [Tim Zhang](https://github.com/ttimasdf) for additional research for Mercury camera on [his github repository](https://github.com/ttimasdf/mercury-ipc-control)
- [Gábor Szabados](https://github.com/GSzabados) for doing research and gathering all the information above in [Home Assistant Community forum](https://community.home-assistant.io/t/use-pan-tilt-function-for-tp-link-tapo-c200-from-home-assistant/170143/18)
- [Davide Depau](https://github.com/Depau) for additional [research](https://md.depau.eu/s/r1Ys_oWoP) of the cameras and work on pytapo library

<a href="https://www.buymeacoffee.com/jurajnyiri" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee"  width="150px" ></a>

# Disclaimer

This integration is using python module Pytapo which is an unofficial module for achieving interoperability with Tapo cameras.

Author is in no way affiliated with Tp-Link or Tapo.

All the api requests used within the pytapo library are available and published on the internet (examples linked above) and the pytapo module is purely just a wrapper around those https requests.

Author does not guarantee functionality of this integration and is not responsible for any damage.

All product names, trademarks and registered trademarks in this repository, are property of their respective owners.
