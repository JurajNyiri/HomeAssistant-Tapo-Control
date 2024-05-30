# HomeAssistant - Tapo: Cameras Control

Custom component - Tapo: Cameras Control - to add Tapo cameras into Home Assistant

# Integration will / does not work temporarily on firmware build 230921 and higher

TP-Link is currently working on a new API solution that can be used by this integration in order to receive the new cloud issued token for the camera. 

If you wish to continue using this integration, until this issue is resolved, you will need to either:

1. If your camera still works with integration: Block internet access of camera and stop using the official phone app temporarily if you are using firmware build 230921 and higher
2. If your camera no longer works with integration: [Use older firmware](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/551#issuecomment-2061039421) than build 230921 and optionally factory reset camera

Learn more and discuss at https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/551 .

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
- Switch entities for Auto track, Flip setting, LED Indicator, Lens Distortion Correction, (Rich) Notifications, Recording, Microphone Mute, Microphone Noise Cancelling, Automatically Upgrade Firmware and Privacy mode
- Select entities for Automatic Alarm, Light Frequency, Motion Detection, Night Vision and Move to Preset
- Number entity for Movement Angle, Speaker Volume, Microphone Volume and Motion Detection Digital Sensitivity
- Media Source for browsing and playing recordings stored on camera
- Sensor entity that reports monitor media sync status
- Sensor entities for Storage diagnostics
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

Integration is capable of analysing sound from camera microphone and expose noise detected via binary_sensor.

You need to enable this feature in integration options by checking "Enable sound threshold detection". After enabling it, you can also set any other options starting with [Sound Detection]. You will need to restart Home Asssistant after doing any changes.

For more information and troubleshooting see [Home Assistant ffmpeg documentation](https://www.home-assistant.io/integrations/ffmpeg_noise/) on which this feature is based on.

## Media Sync

Integration is capable of synchronizing recordings for fast playback.

Synchronization is turned off by default, you can browse media stored on camera and request it to be played. However, downloading is rather slow, so it is a good idea to enable media synchronization in background. That way, you will be able to play any synchronized media from camera instantly.

You can enable this setting by navigating to Home Assistant Settings -> Devices and clicking on Configure button next to the Tapo device you wish to turn media synchronization on for.

You need to also define the number of hours to synchronize. Unless it is specified, synchronization does not run.

Finally, you are able to set the storage path where the synchronized recordings will be stored (defaults to /config/.storage/tapo_control).

**Notice:**: Recordings are deleted after the number of hours you have chosen to synchronize passes, once both the actual recording time and the file modified time is older than the number of hours set.

## Troubleshooting | FAQ

<details>
  <summary>Binary sensor for motion doesn't show up or work</summary>

Motion sensor is added only after a motion is detected for the first time.

- Make sure the camera has motion detection turned on
- Make sure the camera has privacy mode turned off
- Make sure the camera can see you and your movement
- If you have webhooks enabled, and your Home Assistant internal URL is reachable on HTTP, make sure camera can reach it. 
- Make sure you have correct IP set for Home Assistant. Turn on Advanced Mode under `/profile`. Go to `/config/network` and under `Network Adapter` verify correct IP is shown for the device. If it is not correct, under `Home Assistant URL` uncheck `Automatic` next to `Local Network` and set it to `http://<some IP address>:8123`. **DO NOT USE HTTPS**.
- Certain camera firmwares have pullpoint broken, with only webhooks working. If you are not able to run webhooks because of above (https, or vlan setup), binary sensor will never show up.
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
  <summary>I see error `Invalid authentication data. Make sure you have created your 3rd party account via Tapo app. You can also test if these credentials work via rtsp stream, for example VLC using link rtsp://username:password@IP Address:554/stream1` when I enter correct password</summary>

You might be entering incorrect password or are encountering a camera limitation.

See [official Tapo documentation](https://www.tp-link.com/cz/support/faq/2742/)

> **Q3**: Can multiple accounts/devices view the Tapo camera at the same time?
> 
> **A**: Currently, each camera can be controlled or managed by only one account on the Tapo App. You can share it with 5 different accounts at most, and these two accounts can only access live view and playback features of the camera.
> 
> Each camera also supports up to 2 simultaneous video streams. You could use up to 2 devices to view the live feed of the camera simultaneously using the Tapo App or via RTSP. You may also only view the playback of a camera using one Tapo app at a time.

As well as:

> **Q4**: Why can’t I use Tapo Care, SD card, and NVR at the same time?
>
> **A**: Due to the limited hardware performance of the camera itself, Tapo Care works best with one of the NVR or SD card recordings.
>
> If you are using an SD card and Tapo Care at the same time, the NVR(RTSP/ONVIF) will be disabled.
> 
> To restart the recording on the NVR, please remove the SD card from the camera.

</details>

<details>
  <summary>I see error `Invalid cloud password. Invalid cloud password. Make sure you are entering the password for your cloud account and NOT the password which you created via the camera settings (unless they are the same). You need to enter password which you used with your email when signing into the Tapo app.` when I enter correct password</summary>

  If you are using firmware build 230921 and higher, check issue https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/551.

  Otherwise, try those troubleshooting options:

  1. Make sure that "Two-Step Verification" for login is disabled. Go in the Tapo app > Me > View Account > Login Security > Turn off the "Two-Step Verification".
  2. Reset your password.
  3. Make sure your camera can access the internet.
  4. Reboot your camera a few times.
  5. Reset the camera. Remove it from your account, do a factory reset, add it back with internet access, add it back to the integration.

</details>

<details>
  <summary>Supported models</summary>

Users reported full functionality with following Tapo Cameras:

- TC60
- TC70
- C100
- C110
- C120
- C200
- C210
- C220
- C225
- C310
- C320WS
- C500
- C510W
- C520WS

The integration _should_ work with any other non-battery Tapo Cameras.

Battery cameras controlled via HUB are working only for control:

- C420S2

If you had success with some other model, please report it via a new issue.

</details>

<details>
  <summary>What is webhook when referred to on camera?</summary>

Camera uses ONVIF standard to communicate motion events. This communication can work with 2 ways:
  
  1. Pullpoint: Client opens connection to the camera and waits until the camera responds. Camera responds only when there is some event to communicate. After camera responds, client reopens the connection and waits again.
  2. Webhook: Client tells the camera its URL to receive events at. When an event happens, camera communicates this to the URL client defined.
  
Webhooks are the preffered method of communication as they are faster and lighter. That being said;
  
  - Webhooks require an HTTP only HA setup because Tapo cameras do not support HTTPS webhooks
  - Webhooks require a proper base_url to be defined in HA, so that the URL communicated is correct (you can check URL sent by enabling debug logs for homeassistant.onvif)
  
Points above are automatically determined by this integration and if the HA does not meet the criteria, webhooks are disabled. That being said;

  - There are camera (and/or firmwares) which freeze when both webhooks and pullpoint connection is created, which happens at the start to see if webhooks is supported at all so that communication can fallback back to pullpoint.
  - There are camera firmwares which have pullpoint broken (1.3.6 C200) and only webhooks work
  
For webhooks to work, all the user needs to do is make sure he is using HA on HTTP and that the HA is available on the URL communicated.

</details>

<details>
  <summary>Is this integration free and fully local?</summary>

Yes, the integration is free and does not require any paid subscriptions. It is also fully local requiring no internet access from the camera or this integration.

</details>

<details>
  <summary>I receive Exception: Invalid authentication data when executing an automation / script</summary>

Firmwares of cameras expect messages in sequential order. Sending them in parallel can lead to 401 code from camera which shows us with this exception.

You will need to send the automation actions in sequence instead, possibly with delay as well if needed.

See https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/488 for more information.

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
- [Joe Bebo](https://github.com/bebo-dot-dev) for [documenting](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/243) the communication protocol for cameras which use a hub

<a href="https://www.buymeacoffee.com/jurajnyiri" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee"  width="150px" ></a>

# Disclaimer

This integration is using python module Pytapo which is an unofficial module for achieving interoperability with Tapo cameras.

Author is in no way affiliated with Tp-Link or Tapo.

All the api requests used within the pytapo library are available and published on the internet (examples linked above) and the pytapo module is purely just a wrapper around those https requests.

Author does not guarantee functionality of this integration and is not responsible for any damage.

All product names, trademarks and registered trademarks in this repository, are property of their respective owners.
