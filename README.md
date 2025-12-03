# Ajax Systems Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/zava78/ajax-systems-ha.svg)](https://github.com/zava78/ajax-systems-ha/releases)
[![License](https://img.shields.io/github/license/zava78/ajax-systems-ha.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/zava78/ajax-systems-ha)

Custom Home Assistant integration for **Ajax Systems** security alarms.

## ⚠️ Disclaimer

This is an **unofficial** integration. Ajax Systems does not provide a public API for home users.

### Available Integration Methods:

| Method | Status | Description |
|--------|--------|-------------|
| **SIA DC-09 Protocol** | ✅ **Recommended** | Standard security protocol, local communication |
| **Jeedom MQTT** | ✅ **Recommended** | Subscribe to Jeedom MQTT events |
| **Jeedom Server** | ✅ **Full Control** | Connect to local/remote Jeedom with ajaxSystem plugin |
| **MQTT Bridge** | ✅ Works | Via Jeedom plugin |
| **MQTT Publish** | ✅ New | Publish state changes to local MQTT broker |

**Note:** The [SIA integration](https://www.home-assistant.io/integrations/sia/) in Home Assistant already supports Ajax Systems for events. This custom integration adds:
- Full arm/disarm control via Jeedom server
- Device-specific entities
- Enhanced status information
- MQTT state publishing

---

## 📋 Table of Contents

- [Features](#features)
- [Supported Devices](#supported-devices)
- [Installation](#installation)
- [Configuration](#configuration)
  - [SIA Protocol](#sia-protocol-recommended)
  - [Jeedom Cloud Proxy](#jeedom-cloud-proxy-full-control)
  - [MQTT Bridge](#mqtt-bridge-jeedom)
  - [MQTT Publish](#mqtt-publish-option)
- [Services](#services)
- [Automations](#automations)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Credits](#credits--resources)

---

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
- 📡 **MQTT Publishing** - Broadcast state changes to MQTT broker

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

---

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
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/ajax_systems` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

### SIA Protocol (Recommended)

This method receives alarm events directly from your Ajax Hub via the SIA DC-09 protocol. This is a **local** connection - no cloud required.

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Ajax Systems"
3. Select **"SIA Protocol (Recommended - Local)"**
4. Configure:
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

---

### Jeedom Server (Full Control) ⚠️ REQUIRES JEEDOM

This method provides **FULL CONTROL** of your Ajax system including arm/disarm. It connects to a local or remote Jeedom server running the ajaxSystem plugin.

> ⚠️ **IMPORTANT:** This option requires an active **Jeedom installation** with the **ajaxSystem plugin** installed and configured. **Without Jeedom, this option will NOT work.**
>
> **If you don't have Jeedom**, use the **SIA Protocol** option instead for local events (no arm/disarm control).

#### Requirements

1. **Jeedom Server** - A working Jeedom installation (local or remote)
2. **ajaxSystem Plugin** - Installed from Jeedom Market (free plugin)
3. **Jeedom API Key** - From Jeedom Configuration > API
4. **Ajax App Credentials** - Configured in the ajaxSystem plugin

#### 🔑 Setup Steps

##### 1. Install ajaxSystem Plugin on Jeedom

1. In Jeedom, go to **Plugins** → **Plugin Management** → **Market**
2. Search for "ajaxSystem"
3. Install the plugin (free)
4. Configure with your Ajax app credentials
5. Sync your devices

##### 2. Get Jeedom API Key

1. In Jeedom, go to **Settings** → **System** → **Configuration**
2. Click on **API** tab
3. Copy the API key (or generate one if needed)

##### 3. Ajax Systems App Credentials

These are the same credentials you use in the official Ajax app:
- Email address used to register in Ajax app
- Password for your Ajax account

#### Configuration in Home Assistant

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Ajax Systems"
3. Select **"🔌 Jeedom Server (Full Control)"**
4. Enter configuration:
   - **Jeedom Server Address**: IP or hostname (e.g., `192.168.1.100` or `jeedom.local`)
   - **Jeedom Port**: Usually 80 (HTTP) or 443 (HTTPS)
   - **Use HTTPS**: Enable for secure connection
   - **Jeedom API Key**: Key from Jeedom Configuration > API
   - **Ajax App Email**: Your Ajax app email
   - **Ajax App Password**: Your Ajax app password
5. Configure Hub ID and optional SIA settings
6. Click **Submit**

#### Features with Jeedom Server

- ✅ Full arm/disarm control
- ✅ Night mode support
- ✅ Device listing and status
- ✅ Real-time updates (with SIA enabled)
- ✅ Panic alarm
- ✅ Mute fire detectors

---

### MQTT Bridge (Jeedom)

Requires Jeedom with the Ajax plugin running and publishing to MQTT.

1. Ensure Jeedom Ajax plugin is configured and publishing to MQTT
2. Add the integration and select "MQTT Bridge (Jeedom)"
3. Configure the MQTT topic prefix

---

### MQTT Publish Option

This **optional feature** broadcasts state changes from your Ajax entities to a local MQTT broker. This allows other systems to subscribe to Ajax events.

#### Enable MQTT Publishing

During setup (SIA or Jeedom Proxy), or in Options:
- **Publish states to MQTT**: Enable/disable publishing
- **MQTT Topic Prefix**: Prefix for topics (default: `ajax`)
- **Include attributes in MQTT**: Also publish entity attributes
- **Enable MQTT Discovery**: Create auto-discovery configs

#### MQTT Topics

```
ajax/{hub_id}/alarm_control_panel/{entity_name}/state
ajax/{hub_id}/binary_sensor/{entity_name}/state
ajax/{hub_id}/sensor/{entity_name}/state
ajax/{hub_id}/events/alarm    # Real-time SIA events
```

#### Example Payload

```json
{
  "entity_id": "alarm_control_panel.ajax_hub",
  "state": "armed_away",
  "last_changed": "2025-12-02T15:30:00Z",
  "last_updated": "2025-12-02T15:30:00Z",
  "attributes": {
    "last_event": "CL",
    "last_event_time": "2025-12-02T15:30:00Z",
    "friendly_name": "Ajax Hub"
  }
}
```

#### Requirements

- Home Assistant MQTT integration must be installed and configured
- MQTT broker (Mosquitto, etc.) must be running

---

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

### `ajax_systems.diagnose_api`
Run API diagnostics (check logs for results).

```yaml
service: ajax_systems.diagnose_api
```

---

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

### Example: Arm alarm when leaving home

```yaml
automation:
  - alias: "Arm when leaving"
    trigger:
      - platform: state
        entity_id: person.your_name
        from: "home"
    action:
      - service: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.ajax_hub
```

---

## Troubleshooting

### SIA events not received

1. Check that your Hub is configured to send to the correct IP and port
2. Ensure no firewall is blocking the SIA port (default: 2410)
3. Check Home Assistant logs for connection attempts
4. Verify Account Code matches between Hub and integration

### Jeedom Server authentication fails

1. Verify your Jeedom server is reachable from Home Assistant
2. Check that the API key is correct (Jeedom Configuration > API)
3. Ensure the ajaxSystem plugin is installed and configured
4. Check that your Ajax app credentials work in the official app

### Devices not showing

1. After initial setup, devices are discovered automatically
2. With SIA-only mode, devices appear after their first event
3. Try triggering a sensor to force an event

### MQTT not publishing

1. Ensure Home Assistant MQTT integration is configured
2. Check that MQTT publishing is enabled in options
3. Verify MQTT broker is running and accessible

---

## Changelog

### v1.2.0 (2025-12-03)
- 📡 **Jeedom MQTT subscription** - Receive sensor states from Jeedom via MQTT with French translation
- 🗑️ **Removed Cloud API** - Non-functional since 2018
- 🗑️ **Removed Enterprise API references** - Only available to commercial partners
- 🌐 French to Italian/English translation for sensor names and states

### v1.1.0 (2025-12-02)
- 🔧 **Jeedom local/remote server support** - Connect directly to Jeedom server with IP/DNS and port
- 🔧 Replaced Jeedom Market cloud proxy with direct server connection
- 🔧 Added SSL/HTTPS support for Jeedom connection
- 🔧 Added API key authentication for Jeedom

### v1.0.0 (2025-12-02)
- 🎉 **Initial stable release**
- ✅ SIA DC-09 protocol support with Ajax-specific format
- ✅ Jeedom Cloud Proxy for full arm/disarm control
- ✅ MQTT state publishing option
- ✅ Support for all major Ajax sensors
- ✅ HACS compatible
- ✅ Multi-language support (EN, IT)

### v0.1.0 (Initial)
- Basic SIA support
- Cloud API attempt (non-functional)

---

## Development

```bash
# Clone the repository
git clone https://github.com/zava78/ajax-systems-ha.git
cd ajax-systems-ha

# Install dev dependencies
pip install -r requirements_dev.txt

# Run tests
pytest tests/
```

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Credits & Resources

### Inspiration & Code Sources

| Resource | Author | Description |
|----------|--------|-------------|
| [ajax-systems-api](https://github.com/igormukhingmailcom/ajax-systems-api) | Igor Mukhin | PHP library with reverse-engineered Ajax Cloud API endpoints (MIT) |
| [Jeedom-ajax](https://github.com/Flobul/Jeedom-ajax) | Flobul | Jeedom plugin for Ajax Systems (reference for API endpoints) |
| [ha-ajax-uart](https://github.com/FScoua/ha-ajax-uart) | FScoua | Home Assistant integration for Ajax via UART Bridge |
| [pysiaalarm](https://github.com/eavanvalkenburg/pysiaalarm) | E. van Valkenburg | Python SIA protocol implementation |

### Ajax Systems Official Resources

- 🏠 [Ajax Systems Website](https://ajax.systems/)
- 🔌 [Ajax Enterprise API](https://ajax.systems/blog/enterprise-api/) - Official API (requires partnership)
- ☁️ [Ajax Cloud Signaling](https://ajax.systems/ajax-cloud-signaling/)
- 📚 [Ajax Support & Manuals](https://support.ajax.systems/)
- 📱 [Ajax Security System App](https://ajax.systems/ajax-security-system/)

### Jeedom Market

- 🛒 [Jeedom Market](https://market.jeedom.com) - Free account for proxy access
- 📖 [Jeedom Documentation](https://doc.jeedom.com)

### Community Discussions

- [Home Assistant Community - Ajax Integration](https://community.home-assistant.io/t/ajax-systems-alarm/136596)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

---

## Contributors

- [@zava78](https://github.com/zava78) - Initial development and maintenance

## Acknowledgments

Special thanks to:
- **Igor Mukhin** for the original PHP API reverse engineering work
- **Flobul** for the Jeedom Ajax plugin (API reference)
- **Ajax Systems Community** for sharing integration knowledge
- **Home Assistant Community** for testing and feedback
