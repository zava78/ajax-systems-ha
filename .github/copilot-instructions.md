# Ajax Systems Home Assistant Integration

## Project Overview
Custom Home Assistant integration for Ajax Systems security alarms.

## Features
- **SIA DC-09 Protocol**: Receive alarm events via standard security protocol
- **Ajax Cloud API**: Reverse-engineered API for full device control (experimental)
- **MQTT Bridge**: Support for Jeedom MQTT bridge as fallback
- **Devices Supported**: Hub, DoorProtect, MotionProtect, LeaksProtect, FireProtect, SpaceControl

## Architecture
- `api/` - Ajax Cloud API client
- `sia/` - SIA DC-09 protocol implementation
- `platforms/` - Home Assistant entity platforms

## Development
```bash
# Install in HA custom_components folder
cp -r custom_components/ajax_systems ~/.homeassistant/custom_components/

# Restart Home Assistant
ha core restart
```

## Testing
```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component
pytest tests/
```
