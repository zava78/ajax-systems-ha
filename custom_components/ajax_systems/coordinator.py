"""Data coordinator for Ajax Systems integration."""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HUB_ID,
    CONF_MQTT_PUBLISH_ENABLED,
    CONF_MQTT_PUBLISH_PREFIX,
    CONF_MQTT_PUBLISH_ATTRIBUTES,
    CONF_MQTT_DISCOVERY_ENABLED,
    CONF_JEEDOM_MQTT_ENABLED,
    CONF_JEEDOM_MQTT_TOPIC,
    CONF_JEEDOM_MQTT_LANGUAGE,
    CONF_SIA_ACCOUNT,
    CONF_SIA_PORT,
    CONF_USE_SIA,
    DEFAULT_MQTT_PUBLISH_PREFIX,
    DEFAULT_SIA_PORT,
    DEFAULT_JEEDOM_MQTT_TOPIC,
    DOMAIN,
)
from .models import AjaxCoordinator, AjaxDevice, AjaxHub, SiaEvent
from .sia import SiaConfig, SiaReceiver, sia_event_to_alarm_state, sia_event_to_sensor_state

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)


class AjaxDataCoordinator(DataUpdateCoordinator[AjaxCoordinator]):
    """Coordinator for Ajax Systems data updates."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        
        self.entry = entry
        self.data = AjaxCoordinator()
        
        # SIA receiver
        self._sia_receiver: Optional[SiaReceiver] = None
        self._use_sia = entry.data.get(CONF_USE_SIA, True)
        
        # Jeedom MQTT handler
        self._jeedom_mqtt_handler = None
        self._use_jeedom_mqtt = entry.data.get(CONF_JEEDOM_MQTT_ENABLED, False)
        
        # MQTT Publisher
        self._mqtt_publisher = None
        self._use_mqtt_publish = entry.data.get(CONF_MQTT_PUBLISH_ENABLED, False)
        
        # List of entity IDs to track for MQTT
        self._tracked_entity_ids: list[str] = []
    
    async def async_setup(self) -> bool:
        """Set up the coordinator."""
        sia_ok = False
        
        # Set up SIA receiver if enabled
        if self._use_sia:
            port = self.entry.data.get(CONF_SIA_PORT, DEFAULT_SIA_PORT)
            account = self.entry.data.get(CONF_SIA_ACCOUNT, "AAA")
            
            config = SiaConfig(port=port, account=account)
            self._sia_receiver = SiaReceiver(config, self._handle_sia_event)
            
            try:
                if await self._sia_receiver.start():
                    _LOGGER.info("SIA receiver started on port %d", port)
                    self.data.connected = True
                    sia_ok = True
                else:
                    _LOGGER.warning("SIA receiver failed to start (port %d may be in use)", port)
            except Exception as err:
                _LOGGER.warning("SIA receiver error: %s", err)
        
        # Set up Jeedom MQTT handler if enabled
        jeedom_mqtt_ok = False
        if self._use_jeedom_mqtt:
            jeedom_mqtt_ok = await self._setup_jeedom_mqtt()
        
        # Create a default hub if we don't have one from cloud
        if self.data.hub is None:
            hub_id = self.entry.data.get(CONF_HUB_ID, "ajax_hub")
            from .const import AjaxDeviceType, AjaxAlarmState
            self.data.hub = AjaxHub(
                device_id=hub_id,
                device_type=AjaxDeviceType.HUB_2,
                name="Ajax Hub",
                hub_id=hub_id,
                state=AjaxAlarmState.DISARMED,
            )
            _LOGGER.info("Created default hub with ID: %s", hub_id)
        
        # Success if at least one method works, or if we just created a default hub
        if sia_ok or jeedom_mqtt_ok:
            _LOGGER.info("Ajax Systems coordinator setup complete (SIA: %s, Jeedom MQTT: %s)", 
                        sia_ok, jeedom_mqtt_ok)
            return True
        
        # Even without SIA/Jeedom, allow setup with default hub for testing
        _LOGGER.warning(
            "Neither SIA receiver nor Jeedom MQTT could be started. "
            "Integration will work with limited functionality."
        )
        return True  # Allow setup anyway with default hub
    
    async def _setup_jeedom_mqtt(self) -> bool:
        """Set up Jeedom MQTT handler."""
        try:
            from .jeedom_mqtt_handler import JeedomMqttHandler
            
            topic = self.entry.data.get(CONF_JEEDOM_MQTT_TOPIC, DEFAULT_JEEDOM_MQTT_TOPIC)
            language = self.entry.data.get(CONF_JEEDOM_MQTT_LANGUAGE, "it")
            
            self._jeedom_mqtt_handler = JeedomMqttHandler(
                hass=self.hass,
                topic=topic,
                language=language,
            )
            
            # Add callback for sensor updates
            self._jeedom_mqtt_handler.add_callback(self._handle_jeedom_sensor_update)
            
            if await self._jeedom_mqtt_handler.async_start():
                _LOGGER.info("Jeedom MQTT handler started (topic: %s, language: %s)", topic, language)
                self.data.connected = True
                return True
            else:
                _LOGGER.warning("Jeedom MQTT handler failed to start")
                return False
                
        except ImportError as err:
            _LOGGER.error("Failed to import Jeedom MQTT handler: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error setting up Jeedom MQTT: %s", err)
            return False
    
    @callback
    def _handle_jeedom_sensor_update(self, device, changed_attr: Optional[str]) -> None:
        """Handle device update from Jeedom MQTT."""
        from .jeedom_mqtt_handler import JeedomDevice
        from .models import AjaxDoorSensor, AjaxMotionSensor, AjaxLeakSensor, AjaxFireSensor, AjaxDevice
        from .const import AjaxDeviceType
        
        if not isinstance(device, JeedomDevice):
            return
        
        _LOGGER.debug(
            "Jeedom device update: %s.%s (type: %s)",
            device.name,
            changed_attr,
            device.device_type,
        )
        
        hub_id = self.data.hub.device_id if self.data.hub else "ajax_hub"
        device_id = device.device_id
        
        # Check if device type was updated from unknown to known
        should_recreate = False
        if device_id in self.data.devices:
            existing = self.data.devices[device_id]
            # If existing device is generic but now we know the specific type, recreate
            if (type(existing) == AjaxDevice and 
                device.device_type != "unknown" and 
                device.device_type != "hub"):
                should_recreate = True
                _LOGGER.info(
                    "Upgrading device %s from generic to %s", 
                    device.name, device.device_type
                )
        
        # Create or update device based on device type
        if device_id not in self.data.devices or should_recreate:
            ajax_device = self._create_device_from_jeedom(device, hub_id)
            if ajax_device:
                self.data.devices[device_id] = ajax_device
                action = "Upgraded" if should_recreate else "Created"
                _LOGGER.info("%s Ajax device: %s (type: %s)", action, device.name, device.device_type)
        else:
            ajax_device = self.data.devices[device_id]
        
        # Update device state
        if ajax_device:
            self._update_device_from_jeedom(ajax_device, device)
        
        # Notify listeners
        self.async_set_updated_data(self.data)
    
    def _create_device_from_jeedom(self, jeedom_device, hub_id: str) -> Optional[AjaxDevice]:
        """Create an Ajax device from Jeedom device data."""
        from .models import AjaxDoorSensor, AjaxMotionSensor, AjaxLeakSensor, AjaxFireSensor
        from .const import AjaxDeviceType
        
        device_type = jeedom_device.device_type
        device_id = jeedom_device.device_id
        name = jeedom_device.name
        
        if device_type == "hub":
            # Update existing hub instead of creating new device
            if self.data.hub:
                self.data.hub.battery_level = jeedom_device.battery
                self.data.hub.online = jeedom_device.online
                return None
            return AjaxDevice(
                device_id=device_id,
                device_type=AjaxDeviceType.HUB_2,
                name=name,
                hub_id=hub_id,
            )
        elif device_type == "door":
            return AjaxDoorSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.DOOR_PROTECT,
                name=name,
                hub_id=hub_id,
                is_open=jeedom_device.is_open or False,
            )
        elif device_type == "motion":
            return AjaxMotionSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.MOTION_PROTECT,
                name=name,
                hub_id=hub_id,
                motion_detected=jeedom_device.motion or False,
            )
        elif device_type == "leak":
            return AjaxLeakSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.LEAKS_PROTECT,
                name=name,
                hub_id=hub_id,
                leak_detected=jeedom_device.leak or False,
            )
        elif device_type == "smoke":
            return AjaxFireSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.FIRE_PROTECT,
                name=name,
                hub_id=hub_id,
                smoke_detected=jeedom_device.smoke or False,
                heat_detected=False,
                co_detected=False,
            )
        elif device_type == "siren":
            return AjaxDevice(
                device_id=device_id,
                device_type=AjaxDeviceType.STREET_SIREN,
                name=name,
                hub_id=hub_id,
            )
        elif device_type == "keypad":
            return AjaxDevice(
                device_id=device_id,
                device_type=AjaxDeviceType.KEYPAD,
                name=name,
                hub_id=hub_id,
            )
        elif device_type == "remote":
            return AjaxDevice(
                device_id=device_id,
                device_type=AjaxDeviceType.SPACE_CONTROL,
                name=name,
                hub_id=hub_id,
            )
        else:
            # For unknown types, try to infer from available attributes
            _LOGGER.warning(
                "Unknown device type '%s' for device '%s'. Available attrs: is_open=%s, motion=%s, leak=%s, smoke=%s",
                device_type, name, 
                jeedom_device.is_open, jeedom_device.motion, 
                jeedom_device.leak, jeedom_device.smoke
            )
            
            # Infer device type from available attributes
            if jeedom_device.is_open is not None:
                return AjaxDoorSensor(
                    device_id=device_id,
                    device_type=AjaxDeviceType.DOOR_PROTECT,
                    name=name,
                    hub_id=hub_id,
                    is_open=jeedom_device.is_open or False,
                )
            elif jeedom_device.motion is not None:
                return AjaxMotionSensor(
                    device_id=device_id,
                    device_type=AjaxDeviceType.MOTION_PROTECT,
                    name=name,
                    hub_id=hub_id,
                    motion_detected=jeedom_device.motion or False,
                )
            elif jeedom_device.leak is not None:
                return AjaxLeakSensor(
                    device_id=device_id,
                    device_type=AjaxDeviceType.LEAKS_PROTECT,
                    name=name,
                    hub_id=hub_id,
                    leak_detected=jeedom_device.leak or False,
                )
            elif jeedom_device.smoke is not None:
                return AjaxFireSensor(
                    device_id=device_id,
                    device_type=AjaxDeviceType.FIRE_PROTECT,
                    name=name,
                    hub_id=hub_id,
                    smoke_detected=jeedom_device.smoke or False,
                    heat_detected=False,
                    co_detected=False,
                )
            else:
                # Generic device for truly unknown types
                return AjaxDevice(
                    device_id=device_id,
                    device_type=AjaxDeviceType.MOTION_PROTECT,
                    name=name,
                    hub_id=hub_id,
                )
    
    def _update_device_from_jeedom(self, ajax_device: AjaxDevice, jeedom_device) -> None:
        """Update Ajax device state from Jeedom device."""
        # Update common attributes
        if jeedom_device.online is not None:
            ajax_device.online = jeedom_device.online
        if jeedom_device.tamper is not None:
            ajax_device.tamper = jeedom_device.tamper
        if jeedom_device.battery is not None:
            ajax_device.battery_level = jeedom_device.battery
        if jeedom_device.temperature is not None:
            ajax_device.temperature = jeedom_device.temperature
        if jeedom_device.signal is not None:
            ajax_device.signal_level = jeedom_device.signal
        
        # Update type-specific attributes
        if hasattr(ajax_device, "is_open") and jeedom_device.is_open is not None:
            ajax_device.is_open = jeedom_device.is_open
        if hasattr(ajax_device, "motion_detected") and jeedom_device.motion is not None:
            ajax_device.motion_detected = jeedom_device.motion
        if hasattr(ajax_device, "leak_detected") and jeedom_device.leak is not None:
            ajax_device.leak_detected = jeedom_device.leak
        if hasattr(ajax_device, "smoke_detected") and jeedom_device.smoke is not None:
            ajax_device.smoke_detected = jeedom_device.smoke
        
        # Store Jeedom-specific attributes
        if not hasattr(ajax_device, "jeedom_data"):
            ajax_device.jeedom_data = {}
        ajax_device.jeedom_data["zone"] = jeedom_device.zone
        ajax_device.jeedom_data["last_update"] = jeedom_device.last_update.isoformat()
    
    @property
    def jeedom_mqtt_handler(self):
        """Get Jeedom MQTT handler."""
        return self._jeedom_mqtt_handler
    
    async def async_setup_mqtt_publisher(self) -> None:
        """Set up MQTT publisher after entities are created."""
        if not self._use_mqtt_publish:
            return
        
        try:
            from .mqtt_publisher import AjaxMqttPublisher, MqttPublisherConfig
            
            # Get config from entry, merging data and options
            config_data = {**self.entry.data, **self.entry.options}
            
            publisher_config = MqttPublisherConfig(
                enabled=True,
                topic_prefix=config_data.get(CONF_MQTT_PUBLISH_PREFIX, DEFAULT_MQTT_PUBLISH_PREFIX),
                publish_attributes=config_data.get(CONF_MQTT_PUBLISH_ATTRIBUTES, True),
                retain=True,
                qos=1,
                discovery_enabled=config_data.get(CONF_MQTT_DISCOVERY_ENABLED, False),
                discovery_prefix="homeassistant",
            )
            
            hub_id = config_data.get(CONF_HUB_ID, "ajax_hub")
            self._mqtt_publisher = AjaxMqttPublisher(self.hass, publisher_config, hub_id)
            
            if await self._mqtt_publisher.async_start():
                _LOGGER.info("MQTT publisher started, tracking %d entities", len(self._tracked_entity_ids))
                # Track entities that were registered
                for entity_id in self._tracked_entity_ids:
                    self._mqtt_publisher.track_entity(entity_id)
            else:
                _LOGGER.warning("MQTT publisher failed to start")
                self._mqtt_publisher = None
                
        except ImportError as err:
            _LOGGER.error("Failed to import MQTT publisher: %s", err)
        except Exception as err:
            _LOGGER.error("Error setting up MQTT publisher: %s", err)
    
    def register_entity_for_mqtt(self, entity_id: str) -> None:
        """Register an entity to be tracked by MQTT publisher."""
        if entity_id not in self._tracked_entity_ids:
            self._tracked_entity_ids.append(entity_id)
            # If publisher is already running, track immediately
            if self._mqtt_publisher:
                self._mqtt_publisher.track_entity(entity_id)
    
    async def async_publish_alarm_event(
        self,
        event_code: str,
        event_description: str,
        zone: str | None = None,
        device_name: str | None = None,
    ) -> None:
        """Publish an alarm event to MQTT."""
        if self._mqtt_publisher:
            await self._mqtt_publisher.async_publish_alarm_event(
                event_code, event_description, zone, device_name
            )
    
    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._sia_receiver:
            await self._sia_receiver.stop()
        
        if self._jeedom_mqtt_handler:
            await self._jeedom_mqtt_handler.async_stop()
        
        if self._mqtt_publisher:
            await self._mqtt_publisher.async_stop()
    
    async def _async_update_data(self) -> AjaxCoordinator:
        """Fetch data from Ajax."""
        # SIA doesn't poll, it receives push events
        return self.data
    
    @callback
    def _handle_sia_event(self, event: SiaEvent) -> None:
        """Handle incoming SIA event."""
        _LOGGER.info("Processing SIA event: code=%s, zone=%s, account=%s", 
                     event.event_code, event.zone, event.account)
        
        # Update alarm state
        new_state = sia_event_to_alarm_state(event)
        if new_state and self.data.hub:
            self.data.hub.state = new_state
            self.data.hub.last_event = event.event_code
            self.data.hub.last_event_time = event.timestamp
            _LOGGER.info("Hub state changed to: %s", new_state)
        
        # Update sensor state
        sensor_update = sia_event_to_sensor_state(event)
        if sensor_update:
            zone = sensor_update.get("zone")
            if zone:
                device_id = f"zone_{zone}"
                sensor_type = sensor_update.get("type", "unknown")
                
                # Create device if it doesn't exist
                if device_id not in self.data.devices:
                    _LOGGER.info("Creating new device for zone %s (type: %s)", zone, sensor_type)
                    device = self._create_device_from_sia(device_id, zone, sensor_type)
                    if device:
                        self.data.devices[device_id] = device
                
                # Update existing device
                if device_id in self.data.devices:
                    device = self.data.devices[device_id]
                    if hasattr(device, "is_open") and "is_open" in sensor_update:
                        device.is_open = sensor_update["is_open"]
                        _LOGGER.debug("Zone %s: is_open = %s", zone, device.is_open)
                    if hasattr(device, "motion_detected") and "motion_detected" in sensor_update:
                        device.motion_detected = sensor_update["motion_detected"]
                        _LOGGER.debug("Zone %s: motion = %s", zone, device.motion_detected)
                    if hasattr(device, "leak_detected") and "leak_detected" in sensor_update:
                        device.leak_detected = sensor_update["leak_detected"]
                    if hasattr(device, "smoke_detected") and "smoke_detected" in sensor_update:
                        device.smoke_detected = sensor_update["smoke_detected"]
                    if "tamper" in sensor_update:
                        device.tamper = sensor_update["tamper"]
        
        # Publish event to MQTT if enabled
        if self._mqtt_publisher:
            from .const import SIA_EVENT_CODES
            event_desc = SIA_EVENT_CODES.get(event.event_code, f"Unknown ({event.event_code})")
            self.hass.async_create_task(
                self._mqtt_publisher.async_publish_alarm_event(
                    event_code=event.event_code,
                    event_description=event_desc,
                    zone=event.zone,
                    device_name=None,
                )
            )
        
        # Notify listeners
        self.async_set_updated_data(self.data)
    
    def _create_device_from_sia(self, device_id: str, zone: str, sensor_type: str) -> Optional[AjaxDevice]:
        """Create a device based on SIA event type."""
        from .const import AjaxDeviceType
        from .models import AjaxDoorSensor, AjaxMotionSensor, AjaxLeakSensor, AjaxFireSensor
        
        hub_id = self.data.hub.device_id if self.data.hub else "unknown"
        name = f"Zone {zone}"
        
        if sensor_type == "door":
            return AjaxDoorSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.DOOR_PROTECT,
                name=name,
                hub_id=hub_id,
                is_open=False,
            )
        elif sensor_type == "motion":
            return AjaxMotionSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.MOTION_PROTECT,
                name=name,
                hub_id=hub_id,
                motion_detected=False,
            )
        elif sensor_type == "leak":
            return AjaxLeakSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.LEAKS_PROTECT,
                name=name,
                hub_id=hub_id,
                leak_detected=False,
            )
        elif sensor_type == "fire":
            return AjaxFireSensor(
                device_id=device_id,
                device_type=AjaxDeviceType.FIRE_PROTECT,
                name=name,
                hub_id=hub_id,
                smoke_detected=False,
                heat_detected=False,
                co_detected=False,
            )
        elif sensor_type == "tamper":
            # For tamper, we create a generic device
            return AjaxDevice(
                device_id=device_id,
                device_type=AjaxDeviceType.MOTION_PROTECT,
                name=name,
                hub_id=hub_id,
                tamper=True,
            )
        
        return None
    
    async def async_arm(self) -> bool:
        """Arm the alarm."""
        # Arm command requires Jeedom proxy
        _LOGGER.warning("Arm command requires Jeedom proxy integration")
        return False
    
    async def async_disarm(self) -> bool:
        """Disarm the alarm."""
        # Disarm command requires Jeedom proxy
        _LOGGER.warning("Disarm command requires Jeedom proxy integration")
        return False
    
    async def async_arm_night(self) -> bool:
        """Set night mode."""
        # Night mode command requires Jeedom proxy
        _LOGGER.warning("Night mode command requires Jeedom proxy integration")
        return False
