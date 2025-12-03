# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-03

### Added
- **Jeedom MQTT Integration** - Subscribe to Jeedom MQTT events
  - Subscribe to `jeedom/cms/event` topic for Ajax sensor states
  - Automatic translation from French to Italian/English
  - Support for all sensor types (door, motion, leak, smoke, tamper, etc.)
  - Dynamic entity creation from MQTT messages
- **French Translation Dictionary** - Comprehensive translation of Ajax states
  - Door/window states (Ouvert/Fermé → Open/Closed)
  - Motion states (Mouvement détecté → Motion Detected)
  - Alarm states (Armé/Désarmé → Armed/Disarmed)
  - Tamper states (Trafiqué → Tampered)
  - Battery, signal, temperature, and more

### Changed
- Added MQTT as a dependency in manifest
- Updated configuration flow with new "Jeedom MQTT" option
- Improved sensor type detection from Jeedom messages

---

## [1.1.0] - 2025-12-02

### Added
- **Jeedom Local/Remote Server Support** - Connect directly to your Jeedom server
  - Configure server IP address or hostname
  - Configure server port (HTTP/HTTPS)
  - SSL/HTTPS support for secure connections
  - API key authentication

### Changed
- Replaced Jeedom Market cloud proxy with direct Jeedom server connection
- Updated configuration flow for Jeedom connection
- Improved error messages for Jeedom connection issues

### Removed
- Jeedom Market credential-based authentication (replaced with API key)

---

## [1.0.0] - 2025-12-02

### Added
- 🎉 **Initial stable release**
- **SIA DC-09 Protocol** - Local communication with Ajax Hub
  - Support for Ajax-specific SIA format (`Nri0/RP0000`, `Nri1/NL501`)
  - Heartbeat and periodic report handling
  - All standard SIA event codes
- **Jeedom Cloud Proxy** - Full control via Jeedom Market
  - Arm/Disarm/Night mode support
  - Device listing and status
  - Panic alarm
  - Mute fire detectors
  - Token refresh handling
- **MQTT State Publishing** - Broadcast state changes
  - Configurable topic prefix
  - Optional attribute publishing
  - MQTT Discovery support
  - Real-time event publishing
- **Entities**
  - Alarm Control Panel (arm, disarm, night mode)
  - Binary Sensors (door, motion, leak, smoke, heat, glass, tamper)
  - Sensors (battery, signal strength, temperature)
- **Multi-language support**
  - English (en)
  - Italian (it)
- **HACS Compatible**
  - Custom repository support
  - Automatic updates

### Changed
- Improved SIA message parsing for Ajax-specific format
- Enhanced error handling and logging

### Deprecated
- Cloud API option (marked as non-functional)

### Fixed
- SIA receiver now correctly parses Ajax heartbeat messages
- Device discovery from SIA events

## [0.1.0] - 2025-11-15

### Added
- Initial development version
- Basic SIA DC-09 support
- Cloud API client (non-functional due to API closure)
- Basic entity structure

---

## Upgrading

### From 0.x to 1.0.0

1. **Backup your configuration** before upgrading
2. Update via HACS or manually replace the `custom_components/ajax_systems` folder
3. Restart Home Assistant
4. Check your configuration - no changes should be required
5. Optionally enable new features (MQTT publishing) in integration options

### New Features in 1.0.0

After upgrading, you can:
- Enable **MQTT publishing** in integration options to broadcast state changes
- Use **Jeedom Cloud Proxy** for full arm/disarm control
- Benefit from improved SIA event parsing

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.2.0 | 2025-12-03 | Jeedom MQTT integration with French translation |
| 1.1.0 | 2025-12-02 | Direct Jeedom server support |
| 1.0.0 | 2025-12-02 | First stable release |
| 0.1.0 | 2025-11-15 | Initial development |
