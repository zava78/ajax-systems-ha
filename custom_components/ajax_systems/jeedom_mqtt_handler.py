"""Jeedom MQTT Event Handler for Ajax Systems.

This module subscribes to Jeedom MQTT events and translates them to
Home Assistant entities. Jeedom publishes Ajax sensor states via MQTT.

Jeedom message format (one message per command):
Topic: jeedom/cmd/event/{command_id}
Payload: {
  "value": 0|1|"string"|number,
  "humanName": "[Zone][DeviceName][CommandName]",
  "unite": "°C" or "",
  "name": "CommandName",
  "type": "info",
  "subtype": "binary|numeric|string"
}

Each Ajax device has multiple commands:
- Trafiqué (Tamper) - binary 0/1
- En ligne (Online) - binary 0/1  
- Température - numeric with °C
- Ouvert/Fermé (Open/Closed) - binary for door sensors
- Batterie - numeric percentage or string "CHARGED"
- Etat (State) - for sirens, keypads, etc.
- Signal - string "WEAK"/"STRONG"
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Default Jeedom MQTT topic for Ajax events
DEFAULT_JEEDOM_MQTT_TOPIC = "jeedom/cmd/event"

# Signal for entity updates
SIGNAL_JEEDOM_UPDATE = f"{DOMAIN}_jeedom_update"
SIGNAL_JEEDOM_DEVICE_UPDATE = f"{DOMAIN}_jeedom_device_update"

# Command name to attribute mapping
COMMAND_MAPPING = {
    # Tamper commands
    "Trafiqué": {"attr": "tamper", "binary": True, "invert": False},
    "Non trafiqué": {"attr": "tamper", "binary": True, "invert": True},
    "Sabotage": {"attr": "tamper", "binary": True, "invert": False},
    
    # Online/Connection commands
    "En ligne": {"attr": "online", "binary": True, "invert": False},
    "Hors ligne": {"attr": "online", "binary": True, "invert": True},
    "Connecté": {"attr": "online", "binary": True, "invert": False},
    "Déconnecté": {"attr": "online", "binary": True, "invert": True},
    "Ethernet": {"attr": "ethernet", "binary": True, "invert": False},
    "Alimentation secteur": {"attr": "power", "binary": True, "invert": False},
    
    # Door/Window commands
    "Ouvert": {"attr": "is_open", "binary": True, "invert": True},  # 0=open, 1=closed in Ajax
    "Fermé": {"attr": "is_open", "binary": True, "invert": False},
    "Ouverte": {"attr": "is_open", "binary": True, "invert": True},
    "Fermée": {"attr": "is_open", "binary": True, "invert": False},
    "Ouverture": {"attr": "is_open", "binary": True, "invert": True},
    
    # Motion commands
    "Mouvement": {"attr": "motion", "binary": True, "invert": False},
    "Mouvement détecté": {"attr": "motion", "binary": True, "invert": False},
    
    # Leak commands
    "Fuite": {"attr": "leak", "binary": True, "invert": False},
    "Fuite détectée": {"attr": "leak", "binary": True, "invert": False},
    "Fuite d'eau": {"attr": "leak", "binary": True, "invert": False},
    "Inondation": {"attr": "leak", "binary": True, "invert": False},
    
    # Fire/Smoke commands
    "Fumée": {"attr": "smoke", "binary": True, "invert": False},
    "Fumée détectée": {"attr": "smoke", "binary": True, "invert": False},
    "Incendie": {"attr": "fire", "binary": True, "invert": False},
    
    # Temperature command
    "Température": {"attr": "temperature", "binary": False, "unit": "°C"},
    
    # Battery commands
    "Batterie": {"attr": "battery", "binary": False, "unit": "%"},
    "Etat de la batterie": {"attr": "battery_state", "binary": False},
    
    # Signal command
    "Signal": {"attr": "signal", "binary": False},
    
    # State commands (for sirens, keypads, etc.)
    "Etat": {"attr": "state", "binary": False},
    
    # Alarm state commands
    "Armé": {"attr": "alarm_state", "binary": False, "value": "armed"},
    "Désarmé": {"attr": "alarm_state", "binary": False, "value": "disarmed"},
    "Mode nuit": {"attr": "alarm_state", "binary": False, "value": "night"},
}

# French to Italian/English translations
TRANSLATIONS = {
    # States
    "Trafiqué": {"it": "Manomesso", "en": "Tampered"},
    "Non trafiqué": {"it": "Non manomesso", "en": "Not Tampered"},
    "En ligne": {"it": "Online", "en": "Online"},
    "Hors ligne": {"it": "Offline", "en": "Offline"},
    "Ouvert": {"it": "Aperto", "en": "Open"},
    "Fermé": {"it": "Chiuso", "en": "Closed"},
    "Ouverte": {"it": "Aperta", "en": "Open"},
    "Fermée": {"it": "Chiusa", "en": "Closed"},
    "Connecté": {"it": "Connesso", "en": "Connected"},
    "Déconnecté": {"it": "Disconnesso", "en": "Disconnected"},
    "Batterie": {"it": "Batteria", "en": "Battery"},
    "Température": {"it": "Temperatura", "en": "Temperature"},
    "Signal": {"it": "Segnale", "en": "Signal"},
    "Etat": {"it": "Stato", "en": "State"},
    "CHARGED": {"it": "Carica", "en": "Charged"},
    "WEAK": {"it": "Debole", "en": "Weak"},
    "STRONG": {"it": "Forte", "en": "Strong"},
    
    # Device types
    "Sirène": {"it": "Sirena", "en": "Siren"},
    "Clavier": {"it": "Tastiera", "en": "Keypad"},
    "Télécommande": {"it": "Telecomando", "en": "Remote"},
    "Hub": {"it": "Hub", "en": "Hub"},
}

# Device type detection patterns
# Device type detection based on name patterns
DEVICE_TYPE_PATTERNS = {
    "hub": ["hub", "1020", "centrale", "hub 2"],
    "door": ["door", "doorprotect", "fin.", "porta", "finestra", "porte", "fenêtre", "ingresso", "entrata"],
    "motion": ["ir", "pir", "motion", "movimento", "motionprotect"],
    "siren": ["sirena", "sirène", "siren", "homesiren", "streetsiren"],
    "keypad": ["tastiera", "clavier", "keypad"],
    "remote": ["telecomando", "télécommande", "remote", "spacecontrol"],
    "leak": ["leak", "fuite", "acqua", "water", "leaksprotect"],
    "smoke": ["smoke", "fumée", "fire", "incendie", "fireprotect"],
}

# Device type detection based on command names (more reliable)
COMMAND_TO_DEVICE_TYPE = {
    "Ouvert": "door",
    "Fermé": "door", 
    "Ouverte": "door",
    "Fermée": "door",
    "Ouverture": "door",
    "Mouvement": "motion",
    "Mouvement détecté": "motion",
    "Fuite": "leak",
    "Fuite détectée": "leak",
    "Fuite d'eau": "leak",
    "Inondation": "leak",
    "Fumée": "smoke",
    "Fumée détectée": "smoke",
    "Incendie": "smoke",
    "Ethernet": "hub",
    "Alimentation secteur": "hub",
}


@dataclass
class JeedomDevice:
    """Represents an Ajax device discovered from Jeedom MQTT."""
    
    device_id: str  # Unique ID based on device name
    name: str  # Device name (e.g., "MATRIMONIALE IR")
    zone: str  # Zone name (e.g., "Nessuno")
    device_type: str  # Detected type (hub, door, motion, etc.)
    
    # State attributes - updated from MQTT commands
    tamper: Optional[bool] = None
    online: Optional[bool] = None
    is_open: Optional[bool] = None
    motion: Optional[bool] = None
    leak: Optional[bool] = None
    smoke: Optional[bool] = None
    fire: Optional[bool] = None
    
    # Sensor attributes
    temperature: Optional[float] = None
    battery: Optional[int] = None
    battery_state: Optional[str] = None
    signal: Optional[str] = None
    state: Optional[str] = None
    alarm_state: Optional[str] = None
    
    # Connection attributes
    ethernet: Optional[bool] = None
    power: Optional[bool] = None
    
    # Metadata
    last_update: datetime = field(default_factory=datetime.now)
    jeedom_commands: dict[str, str] = field(default_factory=dict)  # command_name -> topic_id
    
    def update_from_command(self, command_name: str, value: Any, topic_id: str) -> bool:
        """Update device state from a Jeedom command.
        
        Returns True if the device state changed.
        """
        mapping = COMMAND_MAPPING.get(command_name)
        if not mapping:
            _LOGGER.debug("Unknown command: %s", command_name)
            return False
        
        attr = mapping["attr"]
        is_binary = mapping.get("binary", False)
        invert = mapping.get("invert", False)
        
        # Store topic ID for this command
        self.jeedom_commands[command_name] = topic_id
        
        # Process value
        if is_binary:
            bool_value = bool(int(value)) if isinstance(value, (int, float, str)) else bool(value)
            if invert:
                bool_value = not bool_value
            old_value = getattr(self, attr, None)
            setattr(self, attr, bool_value)
            changed = old_value != bool_value
        else:
            # Handle special cases
            if attr == "temperature":
                try:
                    new_value = float(value)
                except (ValueError, TypeError):
                    new_value = None
            elif attr == "battery":
                if isinstance(value, str) and value.upper() == "CHARGED":
                    new_value = 100
                else:
                    try:
                        new_value = int(float(value))
                    except (ValueError, TypeError):
                        new_value = None
            elif "value" in mapping:
                new_value = mapping["value"]
            else:
                new_value = str(value) if value is not None else None
            
            old_value = getattr(self, attr, None)
            setattr(self, attr, new_value)
            changed = old_value != new_value
        
        if changed:
            self.last_update = datetime.now()
            _LOGGER.debug(
                "Device %s: %s changed from %s to %s",
                self.name, attr, old_value, getattr(self, attr)
            )
        
        return changed


class JeedomMqttHandler:
    """Handler for Jeedom MQTT messages."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        topic: str = DEFAULT_JEEDOM_MQTT_TOPIC,
        language: str = "it",
    ) -> None:
        """Initialize the Jeedom MQTT handler."""
        self._hass = hass
        self._topic = topic
        self._language = language
        self._unsubscribe: Optional[Callable] = None
        self._devices: dict[str, JeedomDevice] = {}
        self._callbacks: list[Callable[[JeedomDevice, str], None]] = []
        self._message_count = 0
        
    @property
    def devices(self) -> dict[str, JeedomDevice]:
        """Get all discovered devices."""
        return self._devices
    
    def translate(self, text: str) -> str:
        """Translate text to target language."""
        if text in TRANSLATIONS:
            return TRANSLATIONS[text].get(self._language, text)
        return text
    
    def _detect_device_type(self, device_name: str) -> str:
        """Detect device type from name."""
        name_lower = device_name.lower()
        
        for dev_type, patterns in DEVICE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return dev_type
        
        return "unknown"
    
    def _parse_human_name(self, human_name: str) -> tuple[str, str, str]:
        """Parse Jeedom humanName format: [Zone][Device][Command]."""
        parts = re.findall(r'\[([^\]]+)\]', human_name)
        
        zone = parts[0] if len(parts) > 0 else ""
        device = parts[1] if len(parts) > 1 else human_name
        command = parts[2] if len(parts) > 2 else ""
        
        return zone, device, command
    
    def _get_device_id(self, device_name: str, zone: str) -> str:
        """Generate unique device ID."""
        # Clean name for ID
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', device_name)
        clean_name = re.sub(r'_+', '_', clean_name).strip('_').lower()
        
        # Include zone if not empty/default
        if zone and zone.lower() not in ["nessuno", "aucun", "none", ""]:
            clean_zone = re.sub(r'[^a-zA-Z0-9]', '_', zone)
            clean_zone = re.sub(r'_+', '_', clean_zone).strip('_').lower()
            return f"ajax_{clean_zone}_{clean_name}"
        
        return f"ajax_{clean_name}"
    
    def _process_message(self, topic: str, payload: dict[str, Any]) -> Optional[tuple[JeedomDevice, str]]:
        """Process a Jeedom MQTT message.
        
        Returns tuple of (device, changed_attribute) or None.
        """
        try:
            # Extract topic ID (e.g., "91" from "jeedom/cmd/event/91")
            topic_parts = topic.split("/")
            topic_id = topic_parts[-1] if topic_parts else "0"
            
            value = payload.get("value")
            human_name = payload.get("humanName", "")
            command_name = payload.get("name", "")
            subtype = payload.get("subtype", "binary")
            unit = payload.get("unite", "")
            
            if not human_name or not command_name:
                _LOGGER.debug("Skipping message without humanName or name: %s", payload)
                return None
            
            # Parse human name
            zone, device_name, _ = self._parse_human_name(human_name)
            
            if not device_name:
                _LOGGER.debug("Could not extract device name from: %s", human_name)
                return None
            
            # Get or create device
            device_id = self._get_device_id(device_name, zone)
            is_new_device = device_id not in self._devices
            
            if is_new_device:
                device_type = self._detect_device_type(device_name)
                self._devices[device_id] = JeedomDevice(
                    device_id=device_id,
                    name=device_name,
                    zone=zone,
                    device_type=device_type,
                )
                _LOGGER.info(
                    "Discovered new Ajax device: %s (type: %s, zone: %s)",
                    device_name, device_type, zone
                )
            
            device = self._devices[device_id]
            
            # Update device type based on command if still unknown
            if device.device_type == "unknown" and command_name in COMMAND_TO_DEVICE_TYPE:
                device.device_type = COMMAND_TO_DEVICE_TYPE[command_name]
                _LOGGER.info(
                    "Updated device type for %s: %s (from command %s)",
                    device.name, device.device_type, command_name
                )
            
            # Update device from command
            changed = device.update_from_command(command_name, value, topic_id)
            
            # Always notify on first discovery or state change
            if changed or is_new_device:
                # Return the attribute that changed (or "device_type" for new devices)
                mapping = COMMAND_MAPPING.get(command_name, {})
                attr = mapping.get("attr", command_name) if changed else "device_type"
                return (device, attr)
            
            return (device, None)
            
        except Exception as err:
            _LOGGER.error("Error processing message: %s - %s", err, payload)
            return None
    
    @callback
    def _handle_message(self, msg) -> None:
        """Handle incoming MQTT message."""
        self._message_count += 1
        
        try:
            payload = json.loads(msg.payload)
            topic = msg.topic
            
            _LOGGER.debug("MQTT [%s]: %s", topic, payload)
            
            result = self._process_message(topic, payload)
            
            if result:
                device, changed_attr = result
                
                if changed_attr:
                    _LOGGER.info(
                        "Device %s updated: %s = %s",
                        device.name,
                        changed_attr,
                        getattr(device, changed_attr, None)
                    )
                
                # Notify callbacks
                for callback_fn in self._callbacks:
                    try:
                        callback_fn(device, changed_attr)
                    except Exception as err:
                        _LOGGER.error("Callback error: %s", err)
                
                # Send dispatcher signal
                async_dispatcher_send(
                    self._hass,
                    f"{SIGNAL_JEEDOM_DEVICE_UPDATE}_{device.device_id}",
                    device,
                    changed_attr,
                )
                
        except json.JSONDecodeError as err:
            _LOGGER.warning("Invalid JSON: %s", msg.payload)
        except Exception as err:
            _LOGGER.error("Error handling message: %s", err)
    
    def add_callback(self, callback_fn: Callable[[JeedomDevice, str], None]) -> None:
        """Add a callback for device updates."""
        self._callbacks.append(callback_fn)
    
    def remove_callback(self, callback_fn: Callable[[JeedomDevice, str], None]) -> None:
        """Remove a callback."""
        if callback_fn in self._callbacks:
            self._callbacks.remove(callback_fn)
    
    async def async_start(self) -> bool:
        """Start listening for MQTT messages."""
        try:
            if not await mqtt.async_wait_for_mqtt_client(self._hass):
                _LOGGER.warning("MQTT not available")
                return False
            
            # Subscribe with wildcard to catch all sub-topics
            subscribe_topic = self._topic
            if not subscribe_topic.endswith("#") and not subscribe_topic.endswith("+"):
                subscribe_topic = f"{self._topic.rstrip('/')}/#"
            
            self._unsubscribe = await mqtt.async_subscribe(
                self._hass,
                subscribe_topic,
                self._handle_message,
                qos=0,
            )
            
            _LOGGER.info(
                "Subscribed to Jeedom MQTT: %s (language: %s)",
                subscribe_topic,
                self._language,
            )
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to subscribe: %s", err)
            return False
    
    async def async_stop(self) -> None:
        """Stop listening for MQTT messages."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
            _LOGGER.info("Unsubscribed from Jeedom MQTT (processed %d messages)", self._message_count)
    
    def get_device(self, device_id: str) -> Optional[JeedomDevice]:
        """Get a device by ID."""
        return self._devices.get(device_id)
    
    def get_devices_by_type(self, device_type: str) -> list[JeedomDevice]:
        """Get all devices of a specific type."""
        return [d for d in self._devices.values() if d.device_type == device_type]
    
    def get_all_devices(self) -> list[JeedomDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())
