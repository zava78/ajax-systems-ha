"""Constants for Ajax Systems integration."""
from enum import StrEnum
from typing import Final

DOMAIN: Final = "ajax_systems"
MANUFACTURER: Final = "Ajax Systems"

# Configuration keys
CONF_ACCOUNT_ID: Final = "account_id"
CONF_HUB_ID: Final = "hub_id"
CONF_USE_CLOUD: Final = "use_cloud"
CONF_USE_SIA: Final = "use_sia"
CONF_SIA_PORT: Final = "sia_port"
CONF_SIA_ACCOUNT: Final = "sia_account"
CONF_USE_MQTT: Final = "use_mqtt"
CONF_MQTT_TOPIC_PREFIX: Final = "mqtt_topic_prefix"
CONF_MQTT_PREFIX: Final = "mqtt_prefix"
CONF_SIA_ENCRYPTION_KEY: Final = "sia_encryption_key"

# Default values
DEFAULT_SIA_PORT: Final = 2410
DEFAULT_MQTT_TOPIC_PREFIX: Final = "jeedom/cmd"
DEFAULT_MQTT_PREFIX: Final = "jeedom/cmd"

# API endpoints (reverse engineered from Jeedom plugin analysis)
AJAX_CLOUD_BASE_URL: Final = "https://app.ajax.systems"
AJAX_API_VERSION: Final = "v1"

# Timeouts
API_TIMEOUT: Final = 30
SIA_TIMEOUT: Final = 60


class AjaxDeviceType(StrEnum):
    """Ajax device types."""
    
    HUB = "Hub"
    HUB_2 = "Hub 2"
    HUB_2_PLUS = "Hub 2 Plus"
    HUB_HYBRID = "Hub Hybrid"
    DOOR_PROTECT = "DoorProtect"
    DOOR_PROTECT_PLUS = "DoorProtect Plus"
    MOTION_PROTECT = "MotionProtect"
    MOTION_PROTECT_PLUS = "MotionProtect Plus"
    MOTION_PROTECT_OUTDOOR = "MotionProtect Outdoor"
    MOTION_CAM = "MotionCam"
    MOTION_CAM_OUTDOOR = "MotionCam Outdoor"
    GLASS_PROTECT = "GlassProtect"
    COMBO_PROTECT = "ComboProtect"
    FIRE_PROTECT = "FireProtect"
    FIRE_PROTECT_PLUS = "FireProtect Plus"
    FIRE_PROTECT_2 = "FireProtect 2"
    LEAKS_PROTECT = "LeaksProtect"
    SPACE_CONTROL = "SpaceControl"
    BUTTON = "Button"
    DOUBLE_BUTTON = "DoubleButton"
    KEYPAD = "KeyPad"
    KEYPAD_PLUS = "KeyPad Plus"
    KEYPAD_TOUCHSCREEN = "KeyPad TouchScreen"
    SIREN_INDOOR = "HomeSiren"
    SIREN_OUTDOOR = "StreetSiren"
    SIREN_OUTDOOR_DOUBLE = "StreetSiren DoubleDeck"
    RELAY = "Relay"
    WALL_SWITCH = "WallSwitch"
    SOCKET = "Socket"
    LIGHT_SWITCH = "LightSwitch"
    RANGE_EXTENDER = "ReX"
    RANGE_EXTENDER_2 = "ReX 2"


class AjaxAlarmState(StrEnum):
    """Ajax alarm states."""
    
    DISARMED = "disarmed"
    ARMED_AWAY = "armed_away"
    ARMED_HOME = "armed_home"  # Night mode
    ARMED_NIGHT = "armed_night"
    ARMING = "arming"
    PENDING = "pending"
    TRIGGERED = "triggered"


class AjaxCommand(StrEnum):
    """Ajax commands."""
    
    ARM = "ARM"
    DISARM = "DISARM"
    NIGHT_MODE = "NIGHT_MODE"
    PARTIAL_ARM = "PARTIAL_ARM"
    MUTE_FIRE = "muteFireDetectors"


# SIA event codes mapping
SIA_EVENT_CODES: Final = {
    # Alarms
    "BA": "Burglar Alarm",
    "BR": "Burglar Alarm Restore",
    "FA": "Fire Alarm",
    "FR": "Fire Alarm Restore",
    "PA": "Panic Alarm",
    "PR": "Panic Alarm Restore",
    "WA": "Water Alarm",
    "WR": "Water Alarm Restore",
    "TA": "Tamper Alarm",
    "TR": "Tamper Alarm Restore",
    # Arm/Disarm
    "CL": "Closing (Armed)",
    "OP": "Opening (Disarmed)",
    "NL": "Night Mode On",
    "NR": "Night Mode Off",
    # Troubles
    "AT": "AC Trouble",
    "AR": "AC Restore",
    "YT": "Battery Trouble",
    "YR": "Battery Restore",
    "YP": "Low Battery",
    "YQ": "Battery Restore",
    # Communication
    "RP": "Automatic Test",
    "RX": "Request for Test",
    # Sensors
    "ZO": "Zone Open",
    "ZC": "Zone Closed",
}

# Device type to platform mapping
DEVICE_PLATFORM_MAP: Final = {
    AjaxDeviceType.HUB: ["alarm_control_panel", "sensor"],
    AjaxDeviceType.HUB_2: ["alarm_control_panel", "sensor"],
    AjaxDeviceType.HUB_2_PLUS: ["alarm_control_panel", "sensor"],
    AjaxDeviceType.DOOR_PROTECT: ["binary_sensor", "sensor"],
    AjaxDeviceType.DOOR_PROTECT_PLUS: ["binary_sensor", "sensor"],
    AjaxDeviceType.MOTION_PROTECT: ["binary_sensor", "sensor"],
    AjaxDeviceType.MOTION_PROTECT_PLUS: ["binary_sensor", "sensor"],
    AjaxDeviceType.MOTION_CAM: ["binary_sensor", "sensor", "camera"],
    AjaxDeviceType.GLASS_PROTECT: ["binary_sensor", "sensor"],
    AjaxDeviceType.FIRE_PROTECT: ["binary_sensor", "sensor"],
    AjaxDeviceType.FIRE_PROTECT_PLUS: ["binary_sensor", "sensor"],
    AjaxDeviceType.FIRE_PROTECT_2: ["binary_sensor", "sensor"],
    AjaxDeviceType.LEAKS_PROTECT: ["binary_sensor", "sensor"],
    AjaxDeviceType.SPACE_CONTROL: ["sensor"],
    AjaxDeviceType.BUTTON: ["sensor"],
    AjaxDeviceType.KEYPAD: ["sensor"],
    AjaxDeviceType.SIREN_INDOOR: ["switch", "sensor"],
    AjaxDeviceType.SIREN_OUTDOOR: ["switch", "sensor"],
    AjaxDeviceType.RELAY: ["switch"],
    AjaxDeviceType.WALL_SWITCH: ["switch"],
    AjaxDeviceType.SOCKET: ["switch", "sensor"],
    AjaxDeviceType.LIGHT_SWITCH: ["light"],
}

# Platforms to load
PLATFORMS: Final = [
    "alarm_control_panel",
    "binary_sensor",
    "sensor",
    "switch",
]
