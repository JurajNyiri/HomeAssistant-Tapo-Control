from .const import *
from pytapo import Tapo

def registerController(host, username, password):
    return Tapo(host, username, password)

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