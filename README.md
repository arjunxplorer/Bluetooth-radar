# Blue-Discover

A Bluetooth Low Energy (BLE) device scanner and GATT profile explorer for macOS. Automatically discovers nearby BLE devices, connects to them, and dumps their full GATT profiles to a JSON log.

## Features

- **Continuous scanning** — detects BLE devices in real-time
- **Auto-connect** — connects to new devices as they appear
- **Full GATT dump** — reads all readable characteristics, subscribes to notifications, reads descriptors
- **JSON logging** — persists all discovered devices and their profiles to `ble_log.json`
- **Resume support** — loads previous scan results so devices aren't re-connected on restart
- **Color-coded output** — easy to distinguish new devices, errors, and scan progress

## Requirements

- Python 3.9+
- macOS (uses CoreBluetooth via bleak)

## Installation

```bash
pip install bleak
```

## Usage

```bash
python main.py
```

The scanner will continuously search for nearby BLE devices. When a new device is found, it will automatically connect and dump its GATT profile. Press `Ctrl+C` to stop and view a summary.

## Output

### Console

```
BLE Auto-Scanner
Logging to ble_log.json. Ctrl+C to stop.

[2026-06-21T12:00:00Z] Found 3 device(s)

NEW DEVICE: iPhone (AA:BB:CC:DD:EE:FF)
  Connecting and dumping GATT profile...
  Connected!
  Profile: 4 services, 12 characteristics
    Service: 180a
      Char: 2a29 [read]
        Value: Apple Inc.
    Service: 180f
      Char: 2a19 [read, notify]
        Value: 85
        Notifications: 3 received
  Saved to ble_log.json
```

### JSON Log (`ble_log.json`)

```json
{
  "scan_started": "2026-06-21T12:00:00+00:00",
  "devices": [
    {
      "name": "iPhone",
      "address": "AA:BB:CC:DD:EE:FF",
      "first_seen": "2026-06-21T12:00:00+00:00",
      "profile": {
        "services": [
          {
            "uuid": "180a",
            "description": "Device Information",
            "characteristics": [
              {
                "uuid": "2a29",
                "properties": ["read"],
                "value": "QXBwbGUgSW5jLg==",
                "value_decoded": "Apple Inc.",
                "descriptors": [],
                "notifications": []
              }
            ]
          }
        ]
      }
    }
  ]
}
```

## Configuration

Edit the constants at the top of `main.py`:

| Constant | Default | Description |
|---|---|---|
| `LOG_FILE` | `ble_log.json` | Output JSON log file path |
| `SCAN_TIMEOUT` | `5.0` | Seconds per scan pass |
| `NOTIFY_WAIT` | `3.0` | Seconds to listen for notifications per characteristic |

## Limitations

- **macOS only** — relies on CoreBluetooth. For Linux, swap bleak's backend to BlueZ.
- **No programmatic pairing** — macOS handles BLE pairing at the OS level. If a device requires pairing, pair it via System Settings > Bluetooth first.
- **No BLE Mesh** — only supports standard GATT connections.

## Dependencies

- [bleak](https://github.com/hbldh/bleak) — cross-platform BLE library for Python

## License

MIT
