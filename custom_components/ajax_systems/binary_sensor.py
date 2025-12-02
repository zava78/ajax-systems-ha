"""Binary sensor platform for Ajax Systems."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AjaxDeviceType, DOMAIN
from .coordinator import AjaxDataCoordinator
from .models import (
    AjaxDevice,
    AjaxDoorSensor,
    AjaxFireSensor,
    AjaxGlassSensor,
    AjaxLeakSensor,
    AjaxMotionSensor,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ajax binary sensors."""
    coordinator: AjaxDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Track which devices we've already added
    added_devices: set[str] = set()
    
    def add_entities_for_devices() -> None:
        """Add entities for any new devices."""
        entities: list[BinarySensorEntity] = []
        
        for device in coordinator.data.devices.values():
            if device.device_id in added_devices:
                continue
                
            added_devices.add(device.device_id)
            _LOGGER.debug("Adding binary sensor for device: %s (%s)", device.name, device.device_type)
            
            if isinstance(device, AjaxDoorSensor):
                entities.append(AjaxDoorBinarySensor(coordinator, device))
                if device.tamper:
                    entities.append(AjaxTamperSensor(coordinator, device))
            elif isinstance(device, AjaxMotionSensor):
                entities.append(AjaxMotionBinarySensor(coordinator, device))
                if device.tamper:
                    entities.append(AjaxTamperSensor(coordinator, device))
            elif isinstance(device, AjaxLeakSensor):
                entities.append(AjaxLeakBinarySensor(coordinator, device))
            elif isinstance(device, AjaxFireSensor):
                entities.append(AjaxSmokeBinarySensor(coordinator, device))
                entities.append(AjaxHeatBinarySensor(coordinator, device))
            elif isinstance(device, AjaxGlassSensor):
                entities.append(AjaxGlassBreakBinarySensor(coordinator, device))
        
        if entities:
            _LOGGER.info("Adding %d new binary sensor entities", len(entities))
            async_add_entities(entities)
    
    # Add initial devices
    add_entities_for_devices()
    
    # Add hub connection sensor
    if coordinator.data.hub:
        async_add_entities([AjaxHubConnectionSensor(coordinator)])
    
    # Listen for new devices from coordinator updates
    @callback
    def async_check_new_devices() -> None:
        """Check for new devices when coordinator updates."""
        add_entities_for_devices()
    
    entry.async_on_unload(
        coordinator.async_add_listener(async_check_new_devices)
    )
    
    _LOGGER.info("Binary sensor platform setup complete. %d devices tracked.", len(added_devices))


class AjaxBaseBinarySensor(CoordinatorEntity[AjaxDataCoordinator], BinarySensorEntity):
    """Base class for Ajax binary sensors."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDevice,
        sensor_type: str = "",
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_{sensor_type}"
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for MQTT publishing
        self.coordinator.register_entity_for_mqtt(self.entity_id)
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ajax Systems",
            model=self._device.device_type.value,
            via_device=(DOMAIN, self._device.hub_id) if self._device.hub_id else None,
        )
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.online and self.coordinator.data.connected
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "signal_strength": self._device.signal_strength,
        }
        if self._device.battery_level is not None:
            attrs["battery_level"] = self._device.battery_level
        return attrs
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            self._device = device
        self.async_write_ha_state()


class AjaxDoorBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax door/window sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_name = "Door"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDoorSensor,
    ) -> None:
        """Initialize the door sensor."""
        super().__init__(coordinator, device, "door")
        self._door_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if the door is open."""
        return self._door_device.is_open


class AjaxMotionBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax motion sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_name = "Motion"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxMotionSensor,
    ) -> None:
        """Initialize the motion sensor."""
        super().__init__(coordinator, device, "motion")
        self._motion_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self._motion_device.motion_detected


class AjaxLeakBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax leak sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_name = "Leak"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxLeakSensor,
    ) -> None:
        """Initialize the leak sensor."""
        super().__init__(coordinator, device, "leak")
        self._leak_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if leak is detected."""
        return self._leak_device.leak_detected


class AjaxSmokeBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax smoke sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_name = "Smoke"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxFireSensor,
    ) -> None:
        """Initialize the smoke sensor."""
        super().__init__(coordinator, device, "smoke")
        self._fire_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if smoke is detected."""
        return self._fire_device.smoke_detected


class AjaxHeatBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax heat sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_name = "Heat"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxFireSensor,
    ) -> None:
        """Initialize the heat sensor."""
        super().__init__(coordinator, device, "heat")
        self._fire_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if heat is detected."""
        return self._fire_device.heat_detected


class AjaxGlassBreakBinarySensor(AjaxBaseBinarySensor):
    """Representation of an Ajax glass break sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.VIBRATION
    _attr_name = "Glass Break"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxGlassSensor,
    ) -> None:
        """Initialize the glass break sensor."""
        super().__init__(coordinator, device, "glass")
        self._glass_device = device
    
    @property
    def is_on(self) -> bool:
        """Return true if glass break is detected."""
        return self._glass_device.glass_break_detected


class AjaxTamperSensor(AjaxBaseBinarySensor):
    """Representation of a tamper sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_name = "Tamper"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDevice,
    ) -> None:
        """Initialize the tamper sensor."""
        super().__init__(coordinator, device, "tamper")
    
    @property
    def is_on(self) -> bool:
        """Return true if tamper is detected."""
        return self._device.tamper


class AjaxHubConnectionSensor(CoordinatorEntity[AjaxDataCoordinator], BinarySensorEntity):
    """Representation of hub connection status."""
    
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connection"
    
    def __init__(self, coordinator: AjaxDataCoordinator) -> None:
        """Initialize the connection sensor."""
        super().__init__(coordinator)
        
        self._hub = coordinator.data.hub
        self._attr_unique_id = f"{DOMAIN}_{self._hub.device_id}_connection"
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for MQTT publishing
        self.coordinator.register_entity_for_mqtt(self.entity_id)
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.device_id)},
            name=self._hub.name,
            manufacturer="Ajax Systems",
            model=self._hub.device_type.value,
            sw_version=self._hub.firmware_version,
        )
    
    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.data.connected
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._hub = self.coordinator.data.hub
        self.async_write_ha_state()
