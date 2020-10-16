import onvif
import os
from onvif import ONVIFCamera
from pytapo import Tapo
from .const import *
from homeassistant.const import (CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.onvif.event import EventManager

def registerController(host, username, password):
    return Tapo(host, username, password)

async def initOnvifEvents(hass, host, username, password):
    device = ONVIFCamera(host, 2020, username, password, f"{os.path.dirname(onvif.__file__)}/wsdl/",no_cache=True)
    try:
        await device.update_xaddrs()
        device_mgmt = device.create_devicemgmt_service()
        device_info = await device_mgmt.GetDeviceInformation()
        if(not 'Manufacturer' in device_info):
            raise Exception("Onvif connection has failed.")

        eventsAvailable = False
        try:
            event_service = device.create_events_service()
            event_capabilities = await event_service.GetServiceCapabilities()
            eventsAvailable = event_capabilities and event_capabilities.WSPullPointSupport
        except:
            return False
        return device
    except:
        pass

    return False

async def getCamData(hass, controller):
    camData = {}
    camData['basic_info'] = await hass.async_add_executor_job(controller.getBasicInfo)
    camData['basic_info'] = camData['basic_info']['device_info']['basic_info']
    try:
        motionDetectionData = await hass.async_add_executor_job(controller.getMotionDetection)
        motion_detection_enabled = motionDetectionData['enabled']
        if(motionDetectionData['digital_sensitivity'] == "20"):
            motion_detection_sensitivity = "low"
        elif(motionDetectionData['digital_sensitivity'] == "50"):
            motion_detection_sensitivity = "normal"
        elif(motionDetectionData['digital_sensitivity'] == "80"):
            motion_detection_sensitivity = "high"
        else:
            motion_detection_sensitivity = None
    except:
        motion_detection_enabled = None
        motion_detection_sensitivity = None
    camData['motion_detection_enabled'] = motion_detection_enabled
    camData['motion_detection_sensitivity'] = motion_detection_sensitivity

    try:
        privacy_mode = await hass.async_add_executor_job(controller.getPrivacyMode)
        privacy_mode = privacy_mode['enabled']
    except:
        privacy_mode = None
    camData['privacy_mode'] = privacy_mode

    try:
        alarmData = await hass.async_add_executor_job(controller.getAlarm)
        alarm = alarmData['enabled']
        alarm_mode = alarmData['alarm_mode']
    except:
        alarm = None
        alarm_mode = None
    camData['alarm'] = alarm
    camData['alarm_mode'] = alarm_mode

    try:
        led = await hass.async_add_executor_job(controller.getLED)
        led = led['enabled']
    except:
        led = None
    camData['led'] = led

    try:
        auto_track = await hass.async_add_executor_job(controller.getAutoTrackTarget)
        auto_track = auto_track['enabled']
    except:
        auto_track = None
    camData['auto_track'] = auto_track

    if(camData['basic_info']['device_model'] in DEVICES_WITH_NO_PRESETS):
        camData['presets'] = {}
    else:
        camData['presets'] = await hass.async_add_executor_job(controller.getPresets)

    return camData


async def update_listener(hass, entry):
    """Handle options update."""
    host = entry.data.get(CONF_IP_ADDRESS)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    motionSensor = entry.data.get(ENABLE_MOTION_SENSOR)
    try:
        tapoController = await hass.async_add_executor_job(registerController, host, username, password)
        hass.data[DOMAIN][entry.entry_id]['controller'] = tapoController
    except Exception as e:
        LOGGER.error("Authentication to Tapo camera failed. Please restart the camera and try again.")

    for entity in hass.data[DOMAIN][entry.entry_id]['entities']:
        entity._host = host
        entity._username = username
        entity._password = password
    if(hass.data[DOMAIN][entry.entry_id]['events']):
        await hass.data[DOMAIN][entry.entry_id]['events'].async_stop()
    if(hass.data[DOMAIN][entry.entry_id]['motionSensorCreated']):
        await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
        hass.data[DOMAIN][entry.entry_id]['motionSensorCreated'] = False
    if motionSensor:
        await setupOnvif(hass, entry, host, username, password)

async def setupOnvif(hass, entry, host, username, password):
    hass.data[DOMAIN][entry.entry_id]['eventsDevice'] = await initOnvifEvents(hass, host, username, password)

    if(hass.data[DOMAIN][entry.entry_id]['eventsDevice']):
        hass.data[DOMAIN][entry.entry_id]['events'] = EventManager(
            hass, hass.data[DOMAIN][entry.entry_id]['eventsDevice'], f"{entry.entry_id}_tapo_events"
        )
    
        hass.data[DOMAIN][entry.entry_id]['eventsSetup'] = await setupEvents(hass, entry)

async def setupEvents(hass, entry):
    if(not hass.data[DOMAIN][entry.entry_id]['events'].started):
        events = hass.data[DOMAIN][entry.entry_id]['events']
        if(await events.async_start()):
            if(not hass.data[DOMAIN][entry.entry_id]['motionSensorCreated']):
                hass.data[DOMAIN][entry.entry_id]['motionSensorCreated'] = True
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
                )
            return True
        else:
            return False
