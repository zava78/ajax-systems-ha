"""Tests for Ajax Systems models."""
import pytest
from datetime import datetime

from custom_components.ajax_systems.const import AjaxDeviceType, AjaxAlarmState
from custom_components.ajax_systems.models import (
    AjaxDevice,
    AjaxHub,
    AjaxDoorSensor,
    AjaxMotionSensor,
    AjaxLeakSensor,
    AjaxFireSensor,
    SiaEvent,
    AjaxCoordinator,
)


class TestAjaxDevice:
    """Test AjaxDevice model."""
    
    def test_device_creation(self):
        """Test creating a basic device."""
        device = AjaxDevice(
            device_id="test123",
            device_type=AjaxDeviceType.DOOR_PROTECT,
            name="Front Door",
        )
        
        assert device.device_id == "test123"
        assert device.device_type == AjaxDeviceType.DOOR_PROTECT
        assert device.name == "Front Door"
        assert device.online is True
        assert device.battery_level is None
    
    def test_device_with_all_fields(self):
        """Test creating a device with all fields."""
        device = AjaxDevice(
            device_id="test456",
            device_type=AjaxDeviceType.MOTION_PROTECT,
            name="Living Room Motion",
            hub_id="hub123",
            online=True,
            battery_level=85,
            signal_strength=-65,
            firmware_version="1.2.3",
            tamper=False,
        )
        
        assert device.hub_id == "hub123"
        assert device.battery_level == 85
        assert device.signal_strength == -65
        assert device.firmware_version == "1.2.3"
        assert device.tamper is False


class TestAjaxHub:
    """Test AjaxHub model."""
    
    def test_hub_creation(self):
        """Test creating a hub."""
        hub = AjaxHub(
            device_id="hub001",
            device_type=AjaxDeviceType.HUB_2,
            name="My Ajax Hub",
            hub_id="hub001",
            state=AjaxAlarmState.DISARMED,
        )
        
        assert hub.device_id == "hub001"
        assert hub.state == AjaxAlarmState.DISARMED
        assert hub.last_event is None
    
    def test_hub_with_event(self):
        """Test hub with last event."""
        now = datetime.now()
        hub = AjaxHub(
            device_id="hub002",
            device_type=AjaxDeviceType.HUB_2_PLUS,
            name="Main Hub",
            hub_id="hub002",
            state=AjaxAlarmState.ARMED_AWAY,
            last_event="CL",
            last_event_time=now,
        )
        
        assert hub.state == AjaxAlarmState.ARMED_AWAY
        assert hub.last_event == "CL"
        assert hub.last_event_time == now


class TestAjaxSensors:
    """Test sensor models."""
    
    def test_door_sensor(self):
        """Test door sensor model."""
        sensor = AjaxDoorSensor(
            device_id="door001",
            device_type=AjaxDeviceType.DOOR_PROTECT,
            name="Front Door",
            is_open=False,
        )
        
        assert sensor.is_open is False
    
    def test_motion_sensor(self):
        """Test motion sensor model."""
        sensor = AjaxMotionSensor(
            device_id="motion001",
            device_type=AjaxDeviceType.MOTION_PROTECT,
            name="Hallway Motion",
            motion_detected=True,
        )
        
        assert sensor.motion_detected is True
    
    def test_leak_sensor(self):
        """Test leak sensor model."""
        sensor = AjaxLeakSensor(
            device_id="leak001",
            device_type=AjaxDeviceType.LEAKS_PROTECT,
            name="Kitchen Leak",
            leak_detected=False,
        )
        
        assert sensor.leak_detected is False
    
    def test_fire_sensor(self):
        """Test fire sensor model."""
        sensor = AjaxFireSensor(
            device_id="fire001",
            device_type=AjaxDeviceType.FIRE_PROTECT,
            name="Bedroom Smoke",
            smoke_detected=False,
            heat_detected=False,
        )
        
        assert sensor.smoke_detected is False
        assert sensor.heat_detected is False


class TestSiaEvent:
    """Test SIA event model."""
    
    def test_sia_event_creation(self):
        """Test creating a SIA event."""
        event = SiaEvent(
            account="AAA",
            event_code="BA",
            zone="001",
        )
        
        assert event.account == "AAA"
        assert event.event_code == "BA"
        assert event.zone == "001"
        assert event.timestamp is not None
    
    def test_sia_event_with_description(self):
        """Test SIA event with description."""
        event = SiaEvent(
            account="BBB",
            event_code="OP",
            zone="002",
            description="Opening",
        )
        
        assert event.description == "Opening"


class TestAjaxCoordinator:
    """Test coordinator data model."""
    
    def test_coordinator_creation(self):
        """Test creating coordinator data."""
        coordinator = AjaxCoordinator()
        
        assert coordinator.hub is None
        assert coordinator.devices == {}
        assert coordinator.connected is False
    
    def test_update_device(self):
        """Test updating a device."""
        coordinator = AjaxCoordinator()
        
        sensor = AjaxDoorSensor(
            device_id="door001",
            device_type=AjaxDeviceType.DOOR_PROTECT,
            name="Test Door",
            is_open=False,
        )
        
        coordinator.update_device(sensor)
        
        assert "door001" in coordinator.devices
        assert coordinator.devices["door001"].name == "Test Door"
    
    def test_get_device(self):
        """Test getting a device."""
        coordinator = AjaxCoordinator()
        
        sensor = AjaxMotionSensor(
            device_id="motion001",
            device_type=AjaxDeviceType.MOTION_PROTECT,
            name="Test Motion",
            motion_detected=False,
        )
        
        coordinator.devices["motion001"] = sensor
        
        retrieved = coordinator.get_device("motion001")
        assert retrieved is not None
        assert retrieved.device_id == "motion001"
        
        missing = coordinator.get_device("nonexistent")
        assert missing is None
