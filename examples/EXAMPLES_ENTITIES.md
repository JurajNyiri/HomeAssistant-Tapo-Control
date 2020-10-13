# HomeAssistant - Tapo: Cameras Control Examples

Below you can find some examples of usage of this custom component in template entities.

- In all the examples, you need to replace camera entity with your entity and adjust the service calls according to your environment.
- See [documentation for template switch](https://www.home-assistant.io/integrations/switch.template/)
- See [documentation for template binary sensor](https://www.home-assistant.io/integrations/binary_sensor.template/)
- See [documentation for template sensor](https://www.home-assistant.io/integrations/template/)

### Control privacy mode via switch

Add to your configuration.yaml:

```
switch:
  - platform: template
    switches:
      bedroom_privacy_mode:
        value_template: "{{ state_attr('camera.bedroom_hd', 'privacy_mode') == 'on' }}"
        turn_on:
          service: tapo_control.set_privacy_mode
          data:
            entity_id: "camera.bedroom_hd"
            privacy_mode: "on"
        turn_off:
          service: tapo_control.set_privacy_mode
          data:
            entity_id: "camera.bedroom_hd"
            privacy_mode: "off"
```

After refresh, switch will be available as switch.bedroom_privacy_mode.

### Sensor for motion detection

Add to your configuration.yaml:

```
sensor:
  - platform: template
    sensors:
      bedroom_motion_detection:
        friendly_name: "Bedroom Motion Detection"
        value_template: "{{ state_attr('camera.bedroom_hd', 'motion_detection') }}"
```

Alternative using binary sensor:

```
binary_sensor:
  - platform: template
    sensors:
      bedroom_motion_detection:
        friendly_name: "Bedroom Motion Detection"
        value_template: "{{ state_attr('camera.bedroom_hd', 'motion_detection') == 'on' }}"
```

After refresh, sensor will be available as sensor.bedroom_motion_detection or binary_sensor.bedroom_motion_detection.