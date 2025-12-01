# Ajax Systems Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/zava78/ajax-systems-ha.svg)](https://github.com/zava78/ajax-systems-ha/releases)
[![License](https://img.shields.io/github/license/zava78/ajax-systems-ha.svg)](LICENSE)

Custom Home Assistant integration for **Ajax Systems** security alarms.

## ⚠️ Disclaimer

This is an **unofficial** integration. Ajax Systems does not provide a public API for home users.

### Available Integration Methods:

| Method | Status | Description |
|--------|--------|-------------|
| **SIA DC-09 Protocol** | ✅ **Recommended** | Standard security protocol, local communication |
| **MQTT Bridge** | ✅ Works | Via Jeedom plugin |
| **Cloud API** | ❌ **Not Available** | Was closed in 2018 |
| **Enterprise API** | ❌ Partners Only | Requires commercial partnership |

**Note:** The official [SIA integration](https://www.home-assistant.io/integrations/sia/) in Home Assistant already supports Ajax Systems. This custom integration provides additional features like device-specific entities and enhanced status information.

## Features

- 🔐 **Alarm Control Panel** - Arm, disarm, and night mode
- 🚪 **Door/Window Sensors** (DoorProtect, DoorProtect Plus)
- 🏃 **Motion Sensors** (MotionProtect, MotionProtect Plus, MotionCam)
- 💧 **Water Leak Sensors** (LeaksProtect)
- 🔥 **Fire Sensors** (FireProtect, FireProtect Plus)
- 💔 **Glass Break Sensors** (GlassProtect)
- 🔋 **Battery Monitoring** for all devices
- 📶 **Signal Strength** monitoring
- 🌡️ **Temperature** sensors (where available)

## Supported Devices

| Device Type | SIA Support | Notes |
|-------------|-------------|-------|
| Hub, Hub 2, Hub 2 Plus | ✅ | Full support |
| DoorProtect | ✅ | Open/close states |
| DoorProtect Plus | ✅ | Open/close + tilt |
| MotionProtect | ✅ | Motion detection |
| MotionProtect Plus | ✅ | Motion + pet immunity |
| MotionCam | ✅ | Motion + photo on alarm |
| LeaksProtect | ✅ | Water leak detection |
| FireProtect | ✅ | Smoke detection |
| FireProtect Plus | ✅ | Smoke + CO + heat |
| GlassProtect | ✅ | Glass break detection |
| SpaceControl | ✅ | Remote control events |
| KeyPad | ✅ | Arm/disarm events |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/zava78/ajax-systems-ha`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Ajax Systems" and install

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/ajax_systems` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### SIA Protocol (Recommended)

This method receives alarm events directly from your Ajax Hub via the SIA DC-09 protocol. This is a **local** connection - no cloud required.

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Ajax Systems"
3. Configure:
   - **Hub ID**: A unique identifier for your hub
   - **SIA Port**: Port to listen on (default: 2410)
   - **Account Code**: Must match your hub's configuration
   - **Encryption Key** (optional): 16/24/32 character key

**Ajax Hub Configuration:**

In the Ajax app, go to Hub Settings → Monitoring Stations:
1. Add a new monitoring station
2. Protocol: **SIA (DC-09)**
3. Server: Your Home Assistant IP address
4. Port: 2410 (or your configured port)
5. Account: Your account code (e.g., "AAA")
6. Enable "Connect on demand"
7. Enable "Periodic Reports" (1 minute recommended)
8. Encryption: Optional but recommended

### MQTT Bridge (Jeedom)

Requires Jeedom with the Ajax plugin running and publishing to MQTT.

1. Ensure Jeedom Ajax plugin is configured and publishing to MQTT
2. Add the integration and select "MQTT Bridge (Jeedom)"
3. Configure the MQTT topic prefix

### About Cloud API

⚠️ **The Ajax Cloud API was closed in 2018** and is no longer functional. The Enterprise API exists but is only available to commercial partners serving thousands of systems.

For home users, SIA DC-09 is the only supported method.

## Services

### `ajax_systems.arm`
Arms the alarm system.

```yaml
service: ajax_systems.arm
target:
  entity_id: alarm_control_panel.ajax_hub
```

### `ajax_systems.disarm`
Disarms the alarm system.

```yaml
service: ajax_systems.disarm
target:
  entity_id: alarm_control_panel.ajax_hub
```

### `ajax_systems.arm_night`
Arms the alarm in night mode.

```yaml
service: ajax_systems.arm_night
target:
  entity_id: alarm_control_panel.ajax_hub
```

## Automations

### Example: Turn on lights when motion detected

```yaml
automation:
  - alias: "Motion detected - turn on lights"
    trigger:
      - platform: state
        entity_id: binary_sensor.ajax_motionprotect_living_room_motion
        to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
```

### Example: Send notification on alarm trigger

```yaml
automation:
  - alias: "Alarm triggered notification"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.ajax_hub
        to: "triggered"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 ALARM TRIGGERED"
          message: "Ajax alarm has been triggered!"
```

## Troubleshooting

### SIA events not received

1. Check that your Hub is configured to send to the correct IP and port
2. Ensure no firewall is blocking the SIA port (default: 2410)
3. Check Home Assistant logs for connection attempts

### Cloud API authentication fails

The Ajax Cloud API was closed in 2018 and no longer works. Use the SIA protocol instead.

### Devices not showing

1. After initial setup, devices are discovered automatically
2. With SIA-only mode, devices appear after their first event
3. Try triggering a sensor to force an event

## Development

```bash
# Clone the repository
git clone https://github.com/zava78/ajax-systems-ha.git
cd ajax-systems-ha

# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest tests/
```

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting a PR.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits & Resources

### Inspiration & Code Sources

| Resource | Author | Description |
|----------|--------|-------------|
| [ajax-systems-api](https://github.com/igormukhingmailcom/ajax-systems-api) | Igor Mukhin | PHP library with reverse-engineered Ajax Cloud API endpoints (MIT) |
| [Jeedom-ajax](https://github.com/Flobul/Jeedom-ajax) | Flobul | Jeedom plugin for Ajax Systems |
| [ha-ajax-uart](https://github.com/FScoua/ha-ajax-uart) | FScoua | Home Assistant integration for Ajax via UART Bridge |
| [pysiaalarm](https://github.com/eavanvalkenburg/pysiaalarm) | E. van Valkenburg | Python SIA protocol implementation |

### Ajax Systems Official Resources

- 🏠 [Ajax Systems Website](https://ajax.systems/)
- 🔌 [Ajax Enterprise API](https://ajax.systems/blog/enterprise-api/) - Official API (requires partnership)
- ☁️ [Ajax Cloud Signaling](https://ajax.systems/ajax-cloud-signaling/)
- 📚 [Ajax Support & Manuals](https://support.ajax.systems/)
- 📱 [Ajax Security System App](https://ajax.systems/ajax-security-system/)

### Community Discussions

- [Home Assistant Community - Ajax Integration](https://community.home-assistant.io/t/ajax-systems-alarm/136596)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

## Contributors

- [@zava78](https://github.com/zava78) - Initial development and maintenance

## Acknowledgments

Special thanks to:
- **Igor Mukhin** for the original PHP API reverse engineering work
- **Ajax Systems Community** for sharing integration knowledge
- **Home Assistant Community** for testing and feedback
