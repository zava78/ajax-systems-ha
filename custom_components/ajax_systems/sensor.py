"""Sensor platform for Ajax Systems."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AjaxDataCoordinator
from .models import AjaxDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ajax sensors."""
    coordinator: AjaxDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[SensorEntity] = []
    
    # Add hub sensors
    if coordinator.data.hub:
        hub = coordinator.data.hub
        if hub.battery_level is not None:
            entities.append(AjaxBatterySensor(coordinator, hub))
    
    # Add device sensors
    for device in coordinator.data.devices.values():
        if device.battery_level is not None:
            entities.append(AjaxBatterySensor(coordinator, device))
        if device.signal_strength is not None:
            entities.append(AjaxSignalSensor(coordinator, device))
        if hasattr(device, "temperature") and device.temperature is not None:
            entities.append(AjaxTemperatureSensor(coordinator, device))
    
    async_add_entities(entities)


class AjaxBatterySensor(CoordinatorEntity[AjaxDataCoordinator], SensorEntity):
    """Representation of an Ajax battery sensor."""
    
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_name = "Battery"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDevice,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_battery"
    
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
    def native_value(self) -> int | None:
        """Return the battery level."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            return device.battery_level
        # Check if it's the hub
        if self.coordinator.data.hub and self.coordinator.data.hub.device_id == self._device.device_id:
            return self.coordinator.data.hub.battery_level
        return None
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            self._device = device
        self.async_write_ha_state()


class AjaxSignalSensor(CoordinatorEntity[AjaxDataCoordinator], SensorEntity):
    """Representation of an Ajax signal strength sensor."""
    
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_has_entity_name = True
    _attr_name = "Signal Strength"
    _attr_entity_registry_enabled_default = False
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDevice,
    ) -> None:
        """Initialize the signal sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_signal"
    
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
    def native_value(self) -> int | None:
        """Return the signal strength."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            return device.signal_strength
        return None
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            self._device = device
        self.async_write_ha_state()


class AjaxTemperatureSensor(CoordinatorEntity[AjaxDataCoordinator], SensorEntity):
    """Representation of an Ajax temperature sensor."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"
    _attr_has_entity_name = True
    _attr_name = "Temperature"
    
    def __init__(
        self,
        coordinator: AjaxDataCoordinator,
        device: AjaxDevice,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_temperature"
    
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
    def native_value(self) -> float | None:
        """Return the temperature."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device and hasattr(device, "temperature"):
            return device.temperature
        return None
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.coordinator.data.devices.get(self._device.device_id)
        if device:
            self._device = device
        self.async_write_ha_state()
