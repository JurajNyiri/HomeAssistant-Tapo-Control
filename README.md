# HomeAssistant - Tapo: Cameras Control

Custom component - Tapo: Cameras Control - to control Tapo camera features

**This custom component is in very early development right now.**

**A lot of things will be changing and a lot of new features will be added.**

Because of that, HACS, versioning etc will come after a first stable release soon.

Use at your own risk.

## Installation:

Copy contents of custom_components/tapo_control/ to custom_components/tapo_control/ in your Home Assistant config folder.

## Usage:

Add to configuration.yaml:

```
tapo_control:
  - host: [IP ADDRESS TO TAPO CAMERA]
    username: [USERNAME SET IN ADVANCED OPTIONS IN CAMERA APP]
    password: [PASSWORD SET IN ADVANCED OPTIONS IN CAMERA APP]
```

You are able to add multiple cameras.

## Services

This custom component creates tapo_control.* entities in your Home Assistant. Use these entity_id(s) in following service calls.

**ptz**

Pan and tilt camera.

Data:
- **entity_id** Required: Name of the entity to rotate
- **tilt** Optional: Tilt direction. Allowed values: UP, DOWN 
- **pan** Optional: Pan direction. Allowed values: RIGHT, LEFT
- **preset** Optional: PTZ preset ID, starts at 1
- **distance** Optional: Distance coefficient. Sets how much PTZ should be executed in one request. Allowed values: floating point numbers, 0 to 1 


**set_privacy_mode**

Sets privacy mode.

Data:
- **entity_id** Required: Name of the entity to set privacy mode for
- **privacy_mode** Required: Sets privacy mode for camera. Possible values: on, off

**set_alarm_mode**

Sets alarm mode.

Data:
- **entity_id** Required: Name of the entity to set alarm mode for
- **alarm_mode** Required: Sets alarm mode for camera. Possible values: on, off
- **sound** Optional: Sets whether the alarm should use sound on motion detected. Possible values: on, off
- **light** Optional: Sets whether the alarm should use light on motion detected. Possible values: on, off

## Have a comment or a suggestion?

Please [open a new issue](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/new), or discuss on [Home Assistant: Community Forum](https://community.home-assistant.io/t/tapo-cameras-control/231795).

## Installation using HACS

HACS will be coming soon!

## Thank you

- [Dale Pavey](https://research.nccgroup.com/2020/07/31/lights-camera-hacked-an-insight-into-the-world-of-popular-ip-cameras/) from NCC Group for the initial research on the Tapo C200
- [likaci](https://github.com/likaci) and [his github repository](https://github.com/likaci/mercury-ipc-control) for the research on the Mercury camera on which tapo is based
- [Tim Zhang](https://github.com/ttimasdf) for additional research for Mercury camera on [his github repository](https://github.com/ttimasdf/mercury-ipc-control)
- [Gábor Szabados](https://github.com/GSzabados) for doing research and gathering all the information above in [Home Assistant Community forum](https://community.home-assistant.io/t/use-pan-tilt-function-for-tp-link-tapo-c200-from-home-assistant/170143/18)