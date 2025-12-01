"""SIA DC-09 Protocol handler for Ajax Systems.

This module implements the SIA DC-09 (Security Industry Association)
protocol for receiving alarm events from Ajax hubs.

The SIA protocol is the standard way Ajax communicates with
Alarm Receiving Centers (ARCs).
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from ..const import SIA_EVENT_CODES, AjaxAlarmState
from ..models import SiaEvent

_LOGGER = logging.getLogger(__name__)

# SIA message format regex
# Format: [#ACCOUNT|CODE/ZONE]
SIA_MESSAGE_PATTERN = re.compile(
    r'\[#(?P<account>\w+)\|'
    r'(?P<code>[A-Z]{2})'
    r'(?:/(?P<zone>\d+))?\]'
)

# Extended SIA DC-09 format
SIA_DC09_PATTERN = re.compile(
    r'"(?P<seq>\d+)"'
    r'(?P<receiver>\d+)?'
    r'L(?P<line>\d+)'
    r'#(?P<account>\w+)'
    r'\[(?P<data>.*?)\]'
)


@dataclass
class SiaConfig:
    """SIA receiver configuration."""
    
    port: int = 2410
    account: str = "AAA"
    zones: int = 2
    encryption_key: Optional[str] = None


class SiaProtocol(asyncio.Protocol):
    """SIA DC-09 Protocol implementation."""
    
    def __init__(
        self,
        config: SiaConfig,
        event_callback: Callable[[SiaEvent], None],
    ) -> None:
        """Initialize the protocol."""
        self.config = config
        self.event_callback = event_callback
        self.transport: Optional[asyncio.Transport] = None
        self._buffer = b""
    
    def connection_made(self, transport: asyncio.Transport) -> None:
        """Handle new connection."""
        self.transport = transport
        peer = transport.get_extra_info("peername")
        _LOGGER.debug("SIA connection from %s", peer)
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection lost."""
        if exc:
            _LOGGER.warning("SIA connection lost: %s", exc)
        else:
            _LOGGER.debug("SIA connection closed")
        self.transport = None
    
    def data_received(self, data: bytes) -> None:
        """Handle received data."""
        self._buffer += data
        
        # Try to parse complete messages
        while self._buffer:
            # Look for message boundaries
            # SIA messages typically end with CR or LF
            end_idx = -1
            for i, byte in enumerate(self._buffer):
                if byte in (0x0D, 0x0A):  # CR or LF
                    end_idx = i
                    break
            
            if end_idx == -1:
                # No complete message yet
                break
            
            # Extract message
            message = self._buffer[:end_idx]
            self._buffer = self._buffer[end_idx + 1:]
            
            # Skip empty messages
            if not message.strip():
                continue
            
            # Parse and handle message
            try:
                self._handle_message(message.decode("ascii", errors="ignore"))
            except Exception as err:
                _LOGGER.error("Error handling SIA message: %s", err)
    
    def _handle_message(self, message: str) -> None:
        """Handle a complete SIA message."""
        _LOGGER.debug("Received SIA message: %s", message)
        
        # Try DC-09 format first
        match = SIA_DC09_PATTERN.search(message)
        if match:
            account = match.group("account")
            data = match.group("data")
            
            # Parse the data portion
            data_match = SIA_MESSAGE_PATTERN.search(f"[#{account}|{data}]")
            if data_match:
                event = self._parse_event(data_match)
                if event:
                    self._send_ack(match.group("seq"))
                    self.event_callback(event)
                    return
        
        # Try simple format
        match = SIA_MESSAGE_PATTERN.search(message)
        if match:
            event = self._parse_event(match)
            if event:
                self._send_ack()
                self.event_callback(event)
                return
        
        _LOGGER.warning("Could not parse SIA message: %s", message)
    
    def _parse_event(self, match: re.Match) -> Optional[SiaEvent]:
        """Parse a SIA event from regex match."""
        account = match.group("account")
        code = match.group("code")
        zone_str = match.group("zone")
        zone = int(zone_str) if zone_str else None
        
        # Validate account if configured
        if self.config.account and account != self.config.account:
            _LOGGER.debug(
                "Ignoring event for account %s (expected %s)",
                account,
                self.config.account,
            )
            return None
        
        return SiaEvent(
            account=account,
            event_code=code,
            zone=zone,
            timestamp=datetime.now(),
            raw_data=match.string,
        )
    
    def _send_ack(self, sequence: Optional[str] = None) -> None:
        """Send acknowledgment to hub."""
        if self.transport:
            # Standard SIA ACK
            if sequence:
                ack = f'"ACK"{sequence}L0#[]\r\n'
            else:
                ack = "ACK\r\n"
            self.transport.write(ack.encode("ascii"))


class SiaReceiver:
    """SIA DC-09 event receiver server."""
    
    def __init__(
        self,
        config: SiaConfig,
        event_callback: Callable[[SiaEvent], None],
    ) -> None:
        """Initialize the receiver."""
        self.config = config
        self.event_callback = event_callback
        self._server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self) -> bool:
        """Start the SIA receiver server."""
        if self._running:
            return True
        
        try:
            loop = asyncio.get_event_loop()
            self._server = await loop.create_server(
                lambda: SiaProtocol(self.config, self._handle_event),
                "0.0.0.0",
                self.config.port,
            )
            self._running = True
            _LOGGER.info("SIA receiver started on port %d", self.config.port)
            return True
            
        except OSError as err:
            _LOGGER.error("Failed to start SIA receiver: %s", err)
            return False
    
    async def stop(self) -> None:
        """Stop the SIA receiver server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._running = False
        _LOGGER.info("SIA receiver stopped")
    
    def _handle_event(self, event: SiaEvent) -> None:
        """Handle incoming SIA event."""
        event_desc = SIA_EVENT_CODES.get(event.event_code, "Unknown")
        _LOGGER.info(
            "SIA event: %s (%s) - Zone %s - Account %s",
            event.event_code,
            event_desc,
            event.zone,
            event.account,
        )
        self.event_callback(event)
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running


def sia_event_to_alarm_state(event: SiaEvent) -> Optional[AjaxAlarmState]:
    """Convert SIA event to alarm state."""
    code = event.event_code
    
    # Arm/Disarm events
    if code == "CL":  # Closing (Armed)
        return AjaxAlarmState.ARMED_AWAY
    elif code == "OP":  # Opening (Disarmed)
        return AjaxAlarmState.DISARMED
    elif code == "NL":  # Night mode on
        return AjaxAlarmState.ARMED_HOME
    elif code == "NR":  # Night mode off
        return AjaxAlarmState.DISARMED
    
    # Alarm events
    elif code in ("BA", "FA", "PA", "WA", "TA"):
        return AjaxAlarmState.TRIGGERED
    
    # Restore events (alarm cleared)
    elif code in ("BR", "FR", "PR", "WR", "TR"):
        # Keep current armed state, just clear triggered
        return None
    
    return None


def sia_event_to_sensor_state(event: SiaEvent) -> Optional[dict]:
    """Convert SIA event to sensor state update."""
    code = event.event_code
    zone = event.zone
    
    result = {"zone": zone}
    
    # Door/window sensors
    if code == "ZO":  # Zone open
        result["type"] = "door"
        result["is_open"] = True
    elif code == "ZC":  # Zone closed
        result["type"] = "door"
        result["is_open"] = False
    
    # Alarm events
    elif code == "BA":  # Burglar alarm
        result["type"] = "motion"
        result["motion_detected"] = True
    elif code == "BR":  # Burglar restore
        result["type"] = "motion"
        result["motion_detected"] = False
    
    elif code == "FA":  # Fire alarm
        result["type"] = "fire"
        result["smoke_detected"] = True
    elif code == "FR":  # Fire restore
        result["type"] = "fire"
        result["smoke_detected"] = False
    
    elif code == "WA":  # Water alarm
        result["type"] = "leak"
        result["leak_detected"] = True
    elif code == "WR":  # Water restore
        result["type"] = "leak"
        result["leak_detected"] = False
    
    elif code == "TA":  # Tamper alarm
        result["type"] = "tamper"
        result["tamper"] = True
    elif code == "TR":  # Tamper restore
        result["type"] = "tamper"
        result["tamper"] = False
    
    else:
        return None
    
    return result
