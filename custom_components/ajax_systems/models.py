"""Data models for Ajax Systems integration."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .const import AjaxAlarmState, AjaxDeviceType


@dataclass
class AjaxDevice:
    """Representation of an Ajax device."""
    
    device_id: str
    device_type: AjaxDeviceType
    name: str
    hub_id: str
    online: bool = True
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None
    temperature: Optional[float] = None
    firmware_version: Optional[str] = None
    tamper: bool = False
    
    # Device-specific attributes
    attributes: dict[str, Any] = field(default_factory=dict)
    
    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        return f"ajax_{self.hub_id}_{self.device_id}"
    
    @property
    def model(self) -> str:
        """Return device model."""
        return self.device_type.value


@dataclass
class AjaxHub(AjaxDevice):
    """Representation of an Ajax Hub."""
    
    state: AjaxAlarmState = AjaxAlarmState.DISARMED
    gsm_signal: Optional[int] = None
    ethernet_connected: bool = False
    wifi_connected: bool = False
    external_power: bool = True
    last_event: Optional[str] = None
    last_event_time: Optional[datetime] = None
    zones: list[dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.HUB


@dataclass
class AjaxDoorSensor(AjaxDevice):
    """Representation of a door/window sensor."""
    
    is_open: bool = False
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.DOOR_PROTECT


@dataclass
class AjaxMotionSensor(AjaxDevice):
    """Representation of a motion sensor."""
    
    motion_detected: bool = False
    pet_immune: bool = False
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.MOTION_PROTECT


@dataclass
class AjaxLeakSensor(AjaxDevice):
    """Representation of a leak sensor."""
    
    leak_detected: bool = False
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.LEAKS_PROTECT


@dataclass
class AjaxFireSensor(AjaxDevice):
    """Representation of a fire/smoke sensor."""
    
    smoke_detected: bool = False
    heat_detected: bool = False
    co_detected: bool = False
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.FIRE_PROTECT


@dataclass
class AjaxGlassSensor(AjaxDevice):
    """Representation of a glass break sensor."""
    
    glass_break_detected: bool = False
    
    def __post_init__(self):
        """Set device type."""
        if not isinstance(self.device_type, AjaxDeviceType):
            self.device_type = AjaxDeviceType.GLASS_PROTECT


@dataclass
class SiaEvent:
    """Representation of a SIA protocol event."""
    
    account: str
    event_code: str
    zone: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[str] = None
    
    @property
    def is_alarm(self) -> bool:
        """Check if this is an alarm event."""
        return self.event_code in ("BA", "FA", "PA", "WA", "TA")
    
    @property
    def is_arm_event(self) -> bool:
        """Check if this is an arm/disarm event."""
        return self.event_code in ("CL", "OP", "NL", "NR")
    
    @property
    def is_restore(self) -> bool:
        """Check if this is a restore event."""
        return self.event_code.endswith("R") or self.event_code in ("OP", "NR")


@dataclass
class AjaxCoordinator:
    """Data coordinator for Ajax integration."""
    
    hub: Optional[AjaxHub] = None
    devices: dict[str, AjaxDevice] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    connected: bool = False
    
    def get_device(self, device_id: str) -> Optional[AjaxDevice]:
        """Get device by ID."""
        return self.devices.get(device_id)
    
    def update_device(self, device: AjaxDevice) -> None:
        """Update or add a device."""
        self.devices[device.device_id] = device
        self.last_update = datetime.now()
