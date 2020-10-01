# HomeAssistant: Tapo Control

Custom component - Tapo control - to control Tapo camera features

**This custom component is in very early development right now. A lot of things will be changing.**

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

**set_preset**

Rotates your camera to preset.

Example:
```
{
  "preset_id":1,
  "entity_id":"tapo_control.living_room"
}
```

## Installation using HACS

HACS will be coming soon!

## Thank you

- [Dale Pavey](https://research.nccgroup.com/2020/07/31/lights-camera-hacked-an-insight-into-the-world-of-popular-ip-cameras/) from NCC Group for the initial research on the Tapo C200
- [likaci](https://github.com/likaci) and [his github repository](https://github.com/likaci/mercury-ipc-control) for the research on the Mercury camera on which tapo is based
- [Tim Zhang](https://github.com/ttimasdf) for additional research for Mercury camera on [his github repository](https://github.com/ttimasdf/mercury-ipc-control)
- [Gábor Szabados](https://github.com/GSzabados) for doing research and gathering all the information above in [Home Assistant Community forum](https://community.home-assistant.io/t/use-pan-tilt-function-for-tp-link-tapo-c200-from-home-assistant/170143/18)