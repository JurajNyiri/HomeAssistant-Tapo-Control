# HomeAssistant - Tapo: Cameras Control

Custom component - Tapo: Cameras Control - to add Tapo cameras into Home Assistant

## Installation

Copy contents of custom_components/tapo_control/ to custom_components/tapo_control/ in your Home Assistant config folder.

## Installation using HACS

HACS is a community store for Home Assistant. You can install [HACS](https://github.com/custom-components/hacs) and then install Tapo: Camera Control from the HACS store.

## Usage

Add cameras via Integrations (search for Tapo) in Home Assistant UI.

To add multiple cameras, add integration multiple times.

## Services

This custom component creates:
- tapo_control.* services to control a camera
- 2 camera entities, one for HD and one for SD stream
- 1 binary sensor for motion after the motion is detected for the first time

Use these services in following service calls.

<details>
  <summary>tapo_control.ptz</summary>

  Pan and tilt camera. 
  
  You are also able to use presets and set distance the ptz should travel.

  - **entity_id** Required: Entity to adjust
  - **tilt** Optional: Tilt direction. Allowed values: UP, DOWN 
  - **pan** Optional: Pan direction. Allowed values: RIGHT, LEFT
  - **preset** Optional: PTZ preset ID or a Name. See possible presets in entity attributes.
  - **distance** Optional: Distance coefficient. Sets how much PTZ should be executed in one request. Allowed values: floating point numbers, 0 to 1 
</details>

<details>
  <summary>tapo_control.set_privacy_mode</summary>

  Sets privacy mode. 
  
  If privacy mode is turned on, camera does not record anything and does not respond to anything other than turning off privacy mode.

  - **entity_id** Required: Entity to set privacy mode for
  - **privacy_mode** Required: Sets privacy mode for camera. Possible values: on, off
</details>

<details>
  <summary>tapo_control.set_alarm_mode</summary>

  Sets alarm mode. 
  
  If camera detects motion, it will sound an alarm, blink the LED or both.

  - **entity_id** Required: Entity to set alarm mode for
  - **alarm_mode** Required: Sets alarm mode for camera. Possible values: on, off
  - **sound** Optional: Sets whether the alarm should use sound on motion detected. Possible values: on, off
  - **light** Optional: Sets whether the alarm should use light on motion detected. Possible values: on, off
</details>

<details>
  <summary>tapo_control.set_led_mode</summary>

  Sets LED mode. 
  
  When on, LED is turned on when camera is on. 
  
  When off, LED is always off.

  - **entity_id** Required: Entity to set LED mode for
  - **led_mode** Required: Sets LED mode for camera. Possible values: on, off
</details>

<details>
  <summary>tapo_control.format</summary>

  Formats SD card of a camera

  - **entity_id** Required: Entity to format
</details>

<details>
  <summary>tapo_control.set_motion_detection_mode</summary>

  Sets motion detection mode. 
  
  Ability to set "high", "normal" or "low". 
  
  These turn on motion detection and set sensitivity to corresponding values in the app.

  Also ability to set to "off", this turns off motion detection completely. 
  
  Turning motion detection off does not affect settings for recordings so you do not need to re-set those unless you open the settings through the Tapo app.
  
  Notice: If you use motion detection triggered recording and you turn off motion recording, it will no longer record! 

  - **entity_id** Required: Entity to set motion detection mode for
  - **motion_detection_mode** Required: Sets motion detection mode for camera. Possible values: high, normal, low, off
</details>

<details>
  <summary>tapo_control.set_auto_track_mode</summary>

  **Warning: This mode is not available in Tapo app and we do not know why. Use at your own risk and please report any success or failures in [Home Assistant: Community Forum](https://community.home-assistant.io/t/tapo-cameras-control/231795).**

  Sets auto track mode. 
  
  With this mode, camera will be adjusting ptz to track whatever moving object it sees.
  
  Motion detection setting does not affect this mode.

  - **entity_id** Required: Entity to set auto track mode for
  - **auto_track_mode** Required: Sets auto track mode for camera. Possible values: on, off
</details>

<details>
  <summary>tapo_control.reboot</summary>

  Reboots the camera

  - **entity_id** Required: Entity to reboot
</details>

<details>
  <summary>tapo_control.save_preset</summary>

  Saves the current PTZ position to a preset

  - **entity_id** Required: Entity to save the preset for
  - **name** Required: Name of the preset. Cannot be empty or a number
</details>

<details>
  <summary>tapo_control.delete_preset</summary>

  Deletes a preset

  - **entity_id** Required: Entity to delete the preset for
  - **preset** Required: PTZ preset ID or a Name. See possible presets in entity attributes
</details>

## Troubleshooting

<details>
  <summary>Binary sensor for motion doesn't show up or work</summary>

  Motion sensor is added only after a motion is detected for the first time. 

  - Make sure the camera has motion detection turned on
  - Make sure the camera has privacy mode turned off
  - Make sure the camera can see you and your movement
  - Try walking in front of the camera
  - If above didn't work, restart the camera and try again
</details>

## Have a comment or a suggestion?

Please [open a new issue](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/new/choose), or discuss on [Home Assistant: Community Forum](https://community.home-assistant.io/t/tapo-cameras-control/231795).

Join discussion on [Discord](https://discord.gg/pa54QyK).

## Thank you

- [Dale Pavey](https://research.nccgroup.com/2020/07/31/lights-camera-hacked-an-insight-into-the-world-of-popular-ip-cameras/) from NCC Group for the initial research on the Tapo C200
- [likaci](https://github.com/likaci) and [his github repository](https://github.com/likaci/mercury-ipc-control) for the research on the Mercury camera on which tapo is based
- [Tim Zhang](https://github.com/ttimasdf) for additional research for Mercury camera on [his github repository](https://github.com/ttimasdf/mercury-ipc-control)
- [Gábor Szabados](https://github.com/GSzabados) for doing research and gathering all the information above in [Home Assistant Community forum](https://community.home-assistant.io/t/use-pan-tilt-function-for-tp-link-tapo-c200-from-home-assistant/170143/18)