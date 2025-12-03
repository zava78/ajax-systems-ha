"""Jeedom MQTT Event Handler for Ajax Systems.

This module subscribes to Jeedom MQTT events and translates them to
Home Assistant entities. Jeedom publishes Ajax sensor states via MQTT.

Typical Jeedom message format:
{
  "value": 0,
  "humanName": "[Nessuno][MATRIMONIALE IR][Trafiqué]",
  "unite": "",
  "name": "Trafiqué",
  "type": "info",
  "subtype": "binary"
}
"""
from __future__ import annotations

import asyncio
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


# French to English/Italian translations for Ajax states
FRENCH_TRANSLATIONS: dict[str, dict[str, str]] = {
    # Tamper / Sabotage states
    "Trafiqué": {"en": "Tampered", "it": "Manomesso"},
    "Non trafiqué": {"en": "Not Tampered", "it": "Non manomesso"},
    "Sabotage": {"en": "Tamper", "it": "Manomissione"},
    
    # Door/Window states
    "Ouvert": {"en": "Open", "it": "Aperto"},
    "Fermé": {"en": "Closed", "it": "Chiuso"},
    "Ouverte": {"en": "Open", "it": "Aperta"},
    "Fermée": {"en": "Closed", "it": "Chiusa"},
    
    # Motion states
    "Mouvement": {"en": "Motion", "it": "Movimento"},
    "Pas de mouvement": {"en": "No Motion", "it": "Nessun movimento"},
    "Mouvement détecté": {"en": "Motion Detected", "it": "Movimento rilevato"},
    "Aucun mouvement": {"en": "No Motion", "it": "Nessun movimento"},
    
    # Alarm states
    "Armé": {"en": "Armed", "it": "Armato"},
    "Désarmé": {"en": "Disarmed", "it": "Disarmato"},
    "Armement": {"en": "Arming", "it": "Armando"},
    "Armé total": {"en": "Armed Away", "it": "Armato totale"},
    "Armé partiel": {"en": "Armed Home", "it": "Armato parziale"},
    "Armé nuit": {"en": "Armed Night", "it": "Armato notte"},
    "Mode nuit": {"en": "Night Mode", "it": "Modo notte"},
    "En alarme": {"en": "Triggered", "it": "In allarme"},
    "Alarme": {"en": "Alarm", "it": "Allarme"},
    
    # Fire/Smoke states
    "Fumée": {"en": "Smoke", "it": "Fumo"},
    "Fumée détectée": {"en": "Smoke Detected", "it": "Fumo rilevato"},
    "Pas de fumée": {"en": "No Smoke", "it": "Nessun fumo"},
    "Incendie": {"en": "Fire", "it": "Incendio"},
    "Température élevée": {"en": "High Temperature", "it": "Temperatura elevata"},
    "Chaleur": {"en": "Heat", "it": "Calore"},
    
    # Water/Leak states
    "Fuite": {"en": "Leak", "it": "Perdita"},
    "Fuite d'eau": {"en": "Water Leak", "it": "Perdita d'acqua"},
    "Fuite détectée": {"en": "Leak Detected", "it": "Perdita rilevata"},
    "Pas de fuite": {"en": "No Leak", "it": "Nessuna perdita"},
    "Inondation": {"en": "Flood", "it": "Allagamento"},
    
    # Glass break states
    "Bris de glace": {"en": "Glass Break", "it": "Rottura vetro"},
    "Vitre brisée": {"en": "Glass Broken", "it": "Vetro rotto"},
    
    # Battery states
    "Batterie": {"en": "Battery", "it": "Batteria"},
    "Batterie faible": {"en": "Low Battery", "it": "Batteria scarica"},
    "Batterie OK": {"en": "Battery OK", "it": "Batteria OK"},
    "Batterie critique": {"en": "Critical Battery", "it": "Batteria critica"},
    
    # Connection states
    "Connecté": {"en": "Connected", "it": "Connesso"},
    "Déconnecté": {"en": "Disconnected", "it": "Disconnesso"},
    "En ligne": {"en": "Online", "it": "Online"},
    "Hors ligne": {"en": "Offline", "it": "Offline"},
    "Connexion perdue": {"en": "Connection Lost", "it": "Connessione persa"},
    
    # Signal states
    "Signal": {"en": "Signal", "it": "Segnale"},
    "Signal fort": {"en": "Strong Signal", "it": "Segnale forte"},
    "Signal faible": {"en": "Weak Signal", "it": "Segnale debole"},
    
    # General states
    "Actif": {"en": "Active", "it": "Attivo"},
    "Inactif": {"en": "Inactive", "it": "Inattivo"},
    "OK": {"en": "OK", "it": "OK"},
    "Erreur": {"en": "Error", "it": "Errore"},
    "Problème": {"en": "Problem", "it": "Problema"},
    "Normal": {"en": "Normal", "it": "Normale"},
    "Alerte": {"en": "Alert", "it": "Allerta"},
    
    # Room/Zone names (common)
    "Nessuno": {"en": "None", "it": "Nessuno"},  # Already Italian but often in messages
    "Aucun": {"en": "None", "it": "Nessuno"},
    "Entrée": {"en": "Entrance", "it": "Ingresso"},
    "Salon": {"en": "Living Room", "it": "Soggiorno"},
    "Cuisine": {"en": "Kitchen", "it": "Cucina"},
    "Chambre": {"en": "Bedroom", "it": "Camera"},
    "Salle de bain": {"en": "Bathroom", "it": "Bagno"},
    "Garage": {"en": "Garage", "it": "Garage"},
    "Jardin": {"en": "Garden", "it": "Giardino"},
    "Cave": {"en": "Cellar", "it": "Cantina"},
    "Grenier": {"en": "Attic", "it": "Soffitta"},
    "Bureau": {"en": "Office", "it": "Ufficio"},
    "Couloir": {"en": "Hallway", "it": "Corridoio"},
    
    # Sensor types
    "Détecteur": {"en": "Detector", "it": "Rilevatore"},
    "Détecteur de mouvement": {"en": "Motion Detector", "it": "Rilevatore di movimento"},
    "Détecteur d'ouverture": {"en": "Door Sensor", "it": "Sensore porta"},
    "Détecteur de fumée": {"en": "Smoke Detector", "it": "Rilevatore fumo"},
    "Détecteur de fuite": {"en": "Leak Detector", "it": "Rilevatore perdite"},
    "Télécommande": {"en": "Remote Control", "it": "Telecomando"},
    "Clavier": {"en": "Keypad", "it": "Tastiera"},
    "Sirène": {"en": "Siren", "it": "Sirena"},
    "Hub": {"en": "Hub", "it": "Hub"},
}

# Name patterns for sensor type detection
SENSOR_TYPE_PATTERNS: dict[str, list[str]] = {
    "door": ["door", "porte", "fenêtre", "window", "ouverture", "doorprotect", "porta", "finestra"],
    "motion": ["motion", "mouvement", "ir", "pir", "motionprotect", "movimento"],
    "smoke": ["smoke", "fumée", "fire", "incendie", "fireprotect", "fumo"],
    "leak": ["leak", "fuite", "water", "eau", "leaksprotect", "acqua", "perdita"],
    "glass": ["glass", "vitre", "glassprotect", "vetro"],
    "tamper": ["tamper", "sabotage", "trafiqué", "manomissione"],
    "battery": ["battery", "batterie", "batteria"],
    "signal": ["signal", "rssi", "segnale"],
    "temperature": ["temp", "température", "temperatura", "chaleur", "heat"],
}


@dataclass
class JeedomSensorState:
    """Represents a sensor state from Jeedom MQTT."""
    
    entity_id: str  # Unique ID derived from humanName
    name: str  # Display name (translated)
    original_name: str  # Original French name
    value: Any  # Current value (0/1 for binary, numeric for sensors)
    human_name: str  # Full human readable name from Jeedom
    sensor_type: str  # Detected sensor type (door, motion, etc.)
    subtype: str  # binary, numeric, string, etc.
    unit: str  # Unit of measurement
    device_name: str  # Extracted device name
    zone_name: str  # Extracted zone/room name
    last_update: datetime = field(default_factory=datetime.now)
    attributes: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_binary(self) -> bool:
        """Check if this is a binary sensor."""
        return self.subtype == "binary"
    
    @property
    def state_on(self) -> bool:
        """Get boolean state for binary sensors."""
        if self.is_binary:
            return bool(self.value)
        return False


class JeedomMqttHandler:
    """Handler for Jeedom MQTT messages."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        topic: str = DEFAULT_JEEDOM_MQTT_TOPIC,
        language: str = "it",
    ) -> None:
        """Initialize the Jeedom MQTT handler.
        
        Args:
            hass: Home Assistant instance
            topic: MQTT topic to subscribe to
            language: Target language for translations (en/it)
        """
        self._hass = hass
        self._topic = topic
        self._language = language
        self._unsubscribe: Optional[Callable] = None
        self._sensors: dict[str, JeedomSensorState] = {}
        self._callbacks: list[Callable[[JeedomSensorState], None]] = []
        
    @property
    def sensors(self) -> dict[str, JeedomSensorState]:
        """Get all discovered sensors."""
        return self._sensors
    
    def translate(self, text: str) -> str:
        """Translate French text to target language.
        
        Args:
            text: Text to translate (may contain French words)
            
        Returns:
            Translated text
        """
        if not text:
            return text
            
        result = text
        
        # Try exact match first
        if text in FRENCH_TRANSLATIONS:
            return FRENCH_TRANSLATIONS[text].get(self._language, text)
        
        # Try to translate words within the text
        for french, translations in FRENCH_TRANSLATIONS.items():
            if french.lower() in result.lower():
                translation = translations.get(self._language, french)
                # Case-insensitive replacement
                pattern = re.compile(re.escape(french), re.IGNORECASE)
                result = pattern.sub(translation, result)
        
        return result
    
    def _detect_sensor_type(self, name: str, human_name: str) -> str:
        """Detect sensor type from name and human name.
        
        Args:
            name: Sensor name from Jeedom
            human_name: Human readable name
            
        Returns:
            Detected sensor type
        """
        combined = f"{name} {human_name}".lower()
        
        for sensor_type, patterns in SENSOR_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in combined:
                    return sensor_type
        
        return "unknown"
    
    def _parse_human_name(self, human_name: str) -> tuple[str, str, str]:
        """Parse Jeedom humanName format.
        
        Format: [Zone][Device][State]
        Example: [Nessuno][MATRIMONIALE IR][Trafiqué]
        
        Args:
            human_name: Human name string from Jeedom
            
        Returns:
            Tuple of (zone_name, device_name, state_name)
        """
        # Extract parts between brackets
        parts = re.findall(r'\[([^\]]+)\]', human_name)
        
        zone_name = parts[0] if len(parts) > 0 else ""
        device_name = parts[1] if len(parts) > 1 else human_name
        state_name = parts[2] if len(parts) > 2 else ""
        
        return zone_name, device_name, state_name
    
    def _generate_entity_id(self, human_name: str, name: str) -> str:
        """Generate a unique entity ID.
        
        Args:
            human_name: Human name from Jeedom
            name: State name
            
        Returns:
            Unique entity ID
        """
        zone, device, _ = self._parse_human_name(human_name)
        
        # Clean and combine for entity ID
        parts = []
        if zone and zone.lower() not in ["nessuno", "aucun", "none", ""]:
            parts.append(zone)
        if device:
            parts.append(device)
        if name:
            parts.append(name)
        
        # Create slug
        entity_id = "_".join(parts)
        entity_id = re.sub(r'[^a-zA-Z0-9_]', '_', entity_id)
        entity_id = re.sub(r'_+', '_', entity_id)
        entity_id = entity_id.strip('_').lower()
        
        return f"ajax_{entity_id}" if entity_id else f"ajax_sensor_{id(human_name)}"
    
    def _process_message(self, payload: dict[str, Any]) -> Optional[JeedomSensorState]:
        """Process a Jeedom MQTT message.
        
        Args:
            payload: Parsed JSON payload
            
        Returns:
            JeedomSensorState or None if invalid
        """
        try:
            value = payload.get("value")
            human_name = payload.get("humanName", "")
            name = payload.get("name", "")
            msg_type = payload.get("type", "info")
            subtype = payload.get("subtype", "binary")
            unit = payload.get("unite", "")
            
            if not human_name:
                _LOGGER.debug("Skipping message without humanName: %s", payload)
                return None
            
            # Parse human name
            zone_name, device_name, state_name = self._parse_human_name(human_name)
            
            # Detect sensor type
            sensor_type = self._detect_sensor_type(name, human_name)
            
            # Generate entity ID
            entity_id = self._generate_entity_id(human_name, name)
            
            # Translate names
            translated_name = self.translate(name)
            translated_device = self.translate(device_name)
            translated_zone = self.translate(zone_name)
            translated_state = self.translate(state_name) if state_name else ""
            
            # Build display name
            if translated_zone and translated_zone.lower() not in ["nessuno", "none", ""]:
                display_name = f"{translated_zone} - {translated_device} ({translated_name})"
            else:
                display_name = f"{translated_device} ({translated_name})"
            
            # Create sensor state
            sensor = JeedomSensorState(
                entity_id=entity_id,
                name=display_name,
                original_name=name,
                value=value,
                human_name=human_name,
                sensor_type=sensor_type,
                subtype=subtype,
                unit=unit,
                device_name=translated_device,
                zone_name=translated_zone,
                last_update=datetime.now(),
                attributes={
                    "original_name": name,
                    "original_human_name": human_name,
                    "translated_state": translated_state,
                    "sensor_type": sensor_type,
                    "jeedom_type": msg_type,
                    "zone": translated_zone,
                    "device": translated_device,
                }
            )
            
            return sensor
            
        except Exception as err:
            _LOGGER.error("Error processing Jeedom message: %s - %s", err, payload)
            return None
    
    @callback
    def _handle_message(self, msg) -> None:
        """Handle incoming MQTT message.
        
        Args:
            msg: MQTT message
        """
        try:
            payload = json.loads(msg.payload)
            _LOGGER.debug("Jeedom MQTT message: %s", payload)
            
            sensor = self._process_message(payload)
            if sensor:
                # Update or add sensor
                self._sensors[sensor.entity_id] = sensor
                
                _LOGGER.info(
                    "Jeedom sensor update: %s = %s (%s)",
                    sensor.name,
                    sensor.value,
                    sensor.attributes.get("translated_state", "")
                )
                
                # Notify callbacks
                for callback_fn in self._callbacks:
                    try:
                        callback_fn(sensor)
                    except Exception as err:
                        _LOGGER.error("Error in Jeedom callback: %s", err)
                
                # Send dispatcher signal for entity updates
                async_dispatcher_send(
                    self._hass,
                    f"{SIGNAL_JEEDOM_UPDATE}_{sensor.entity_id}",
                    sensor,
                )
                
        except json.JSONDecodeError as err:
            _LOGGER.error("Invalid JSON in Jeedom MQTT message: %s", err)
        except Exception as err:
            _LOGGER.error("Error handling Jeedom MQTT message: %s", err)
    
    def add_callback(self, callback_fn: Callable[[JeedomSensorState], None]) -> None:
        """Add a callback for sensor updates.
        
        Args:
            callback_fn: Function to call on sensor update
        """
        self._callbacks.append(callback_fn)
    
    def remove_callback(self, callback_fn: Callable[[JeedomSensorState], None]) -> None:
        """Remove a callback.
        
        Args:
            callback_fn: Function to remove
        """
        if callback_fn in self._callbacks:
            self._callbacks.remove(callback_fn)
    
    async def async_start(self) -> bool:
        """Start listening for MQTT messages.
        
        Returns:
            True if subscription successful
        """
        try:
            # Check if MQTT is available
            if not await mqtt.async_wait_for_mqtt_client(self._hass):
                _LOGGER.warning("MQTT not available, cannot subscribe to Jeedom events")
                return False
            
            # Subscribe to topic with wildcard to catch all sub-topics
            # Jeedom publishes to jeedom/cmd/event/1, jeedom/cmd/event/2, etc.
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
                "Subscribed to Jeedom MQTT topic: %s (language: %s)",
                subscribe_topic,
                self._language,
            )
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to subscribe to Jeedom MQTT: %s", err)
            return False
    
    async def async_stop(self) -> None:
        """Stop listening for MQTT messages."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
            _LOGGER.info("Unsubscribed from Jeedom MQTT topic")
    
    def get_sensor(self, entity_id: str) -> Optional[JeedomSensorState]:
        """Get a sensor by entity ID.
        
        Args:
            entity_id: Entity ID to look up
            
        Returns:
            JeedomSensorState or None
        """
        return self._sensors.get(entity_id)
    
    def get_sensors_by_type(self, sensor_type: str) -> list[JeedomSensorState]:
        """Get all sensors of a specific type.
        
        Args:
            sensor_type: Type to filter by (door, motion, etc.)
            
        Returns:
            List of matching sensors
        """
        return [s for s in self._sensors.values() if s.sensor_type == sensor_type]
    
    def get_binary_sensors(self) -> list[JeedomSensorState]:
        """Get all binary sensors.
        
        Returns:
            List of binary sensors
        """
        return [s for s in self._sensors.values() if s.is_binary]
    
    def get_numeric_sensors(self) -> list[JeedomSensorState]:
        """Get all numeric sensors.
        
        Returns:
            List of numeric sensors
        """
        return [s for s in self._sensors.values() if not s.is_binary]
