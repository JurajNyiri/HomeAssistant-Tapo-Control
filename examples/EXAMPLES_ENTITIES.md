# HomeAssistant - Tapo: Cameras Control Examples

Below you can find some examples of usage of this custom component in template entities.

- In all the examples, you need to replace camera entity with your entity and adjust the service calls according to your environment.
- See [documentation for template switch](https://www.home-assistant.io/integrations/switch.template/)
- See [documentation for template binary sensor](https://www.home-assistant.io/integrations/binary_sensor.template/)
- See [documentation for template sensor](https://www.home-assistant.io/integrations/template/)

### Control `Privacy Mode`, `Auto Track`, `Alarm Mode` with template switches

Add to your configuration.yaml:

```yaml
# configuration.yaml

switch:
  - platform: template
    switches:
      # This is a switch to turn the privacy mode on/off
      bedroom_privacy_mode:
        friendly_name: Privacy Mode
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
        icon_template: >-
          {% if state_attr('camera.bedroom_hd', 'privacy_mode') == 'on' %}
            mdi:eye-off-outline
          {% else %}
            mdi:eye-outline
          {% endif %}
      # This is a switch to turn the auto track mode on/off
      bedroom_auto_track:
        friendly_name: Auto Track
        value_template: "{{ state_attr('camera.bedroom_hd', 'auto_track') == 'on' }}"
        turn_on:
          - service: tapo_control.set_auto_track_mode
            data:
              entity_id: camera.bedroom_hd
              auto_track_mode: 'on'
        turn_off:
          - service: tapo_control.set_auto_track_mode
            data:
              entity_id: camera.bedroom_hd
              auto_track_mode: 'off'
        icon_template: "mdi:radar"
      # This is a switch to turn the alarm on/off
      bedroom_alarm:
        friendly_name: Alarm
        value_template: "{{ state_attr('camera.bedroom_hd', 'alarm') == 'on' }}"
        turn_on:
          - service: tapo_control.set_alarm_mode
            data:
              entity_id: camera.bedroom_hd
              alarm_mode: 'on'
        turn_off:
          - service: tapo_control.set_alarm_mode
            data:
              entity_id: camera.bedroom_hd
              alarm_mode: 'off'
        icon_template: >-
          {% if state_attr('camera.bedroom_hd', 'alarm') == 'on' %}
            mdi:alarm-note
          {% else %}
            mdi:alarm-note-off
          {% endif %}
```

After refresh, switch will be available as `switch.bedroom_privacy_mode`, `bedroom_auto_track` and `bedroom_alarm`.

### Sensor for motion detection

Add to your configuration.yaml:

```yaml
sensor:
  - platform: template
    sensors:
      bedroom_motion_detection:
        friendly_name: "Bedroom Motion Detection"
        value_template: "{{ state_attr('camera.bedroom_hd', 'motion_detection') }}"
```

Alternative using binary sensor:

```yaml
binary_sensor:
  - platform: template
    sensors:
      bedroom_motion_detection:
        friendly_name: "Bedroom Motion Detection"
        value_template: "{{ state_attr('camera.bedroom_hd', 'motion_detection') == 'on' }}"
```

After refresh, sensor will be available as sensor.bedroom_motion_detection or binary_sensor.bedroom_motion_detection.
