import asyncio
import json
import base64
from datetime import datetime, timezone
from bleak import BleakScanner, BleakClient

LOG_FILE = "ble_log.json"
SCAN_TIMEOUT = 5.0
NOTIFY_WAIT = 3.0  # seconds to listen for notifications per characteristic

# ANSI colors
GREEN = "\033[92m"
DIM = "\033[2m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_log():
    """Load existing log file or create empty structure."""
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"scan_started": None, "devices": []}


def save_log(log_data):
    """Write log data to file."""
    with open(LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)


def encode_value(value):
    """Encode bytes to base64 string for JSON storage."""
    if value is None:
        return None
    return base64.b64encode(value).decode("ascii")


async def dump_profile(client, device):
    """Connect to a device and dump its full GATT profile."""
    profile = {"services": []}

    for service in client.services:
        svc_data = {
            "uuid": service.uuid,
            "description": service.description or "",
            "characteristics": [],
        }

        for char in service.characteristics:
            char_data = {
                "uuid": char.uuid,
                "properties": list(char.properties),
                "value": None,
                "value_decoded": None,
                "descriptors": [],
                "notifications": [],
            }

            # Try reading
            if "read" in char.properties:
                try:
                    value = await client.read_gatt_char(char.uuid)
                    char_data["value"] = encode_value(value)
                    try:
                        char_data["value_decoded"] = value.decode("utf-8")
                    except (UnicodeDecodeError, AttributeError):
                        char_data["value_decoded"] = value.hex()
                except Exception as e:
                    char_data["read_error"] = str(e)

            # Try notifications
            if "notify" in char.properties or "indicate" in char.properties:
                try:
                    received = []

                    def on_notify(sender, data):
                        received.append(encode_value(data))

                    await client.start_notify(char.uuid, on_notify)
                    await asyncio.sleep(NOTIFY_WAIT)
                    await client.stop_notify(char.uuid)
                    char_data["notifications"] = received
                except Exception as e:
                    char_data["notify_error"] = str(e)

            # Read descriptors
            for desc in char.descriptors:
                desc_data = {"uuid": desc.uuid, "value": None}
                try:
                    desc_value = await client.read_gatt_descriptor(desc.uuid)
                    desc_data["value"] = encode_value(desc_value)
                except Exception as e:
                    desc_data["error"] = str(e)
                char_data["descriptors"].append(desc_data)

            svc_data["characteristics"].append(char_data)

        profile["services"].append(svc_data)

    return profile


async def scan_once():
    """Single scan pass, returns list of discovered devices."""
    devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT)
    return [d for d in devices if d.name]


def print_summary(seen):
    """Print summary of all discovered devices."""
    print(f"\n{BOLD}Scan stopped.{RESET}")
    print(f"{CYAN}Summary:{RESET}")
    print(f"  Total devices found: {len(seen)}")
    for addr, info in seen.items():
        if info.get("profile") and "error" not in info["profile"]:
            status = "profile dumped"
        else:
            status = "failed"
        print(f"  - {info['name']} ({addr}) — {status}")
    print(f"\nFull log: {LOG_FILE}")


async def main():
    seen = {}  # address -> {name, first_seen, profile}
    log_data = load_log()

    if not log_data["scan_started"]:
        log_data["scan_started"] = datetime.now(timezone.utc).isoformat()
        save_log(log_data)

    # Load previously seen devices
    for entry in log_data["devices"]:
        seen[entry["address"]] = entry

    print(f"{BOLD}BLE Auto-Scanner{RESET}")
    print(f"{DIM}Logging to {LOG_FILE}. Ctrl+C to stop.{RESET}\n")

    shutdown = False

    try:
        while not shutdown:
            try:
                devices = await scan_once()
            except (KeyboardInterrupt, asyncio.CancelledError):
                break

            now = datetime.now(timezone.utc).isoformat()

            if not devices:
                print(f"{DIM}[{now}] No devices found, scanning again...{RESET}")
                continue

            print(f"{DIM}[{now}] Found {len(devices)} device(s){RESET}")

            for device in devices:
                if shutdown:
                    break

                addr = device.address
                if addr in seen:
                    print(f"  {DIM}{device.name} ({addr}) — already seen{RESET}")
                    continue

                # New device!
                print(f"\n{GREEN}{BOLD}NEW DEVICE: {device.name} ({addr}){RESET}")
                seen[addr] = {
                    "name": device.name,
                    "address": addr,
                    "first_seen": now,
                    "profile": None,
                }

                # Auto-connect and dump profile
                print(f"  {CYAN}Connecting and dumping GATT profile...{RESET}")
                try:
                    async with BleakClient(addr, timeout=15.0) as client:
                        print(f"  {GREEN}Connected!{RESET}")
                        profile = await dump_profile(client, device)
                        seen[addr]["profile"] = profile

                        # Print summary
                        svc_count = len(profile["services"])
                        char_count = sum(
                            len(s["characteristics"]) for s in profile["services"]
                        )
                        print(
                            f"  {GREEN}Profile: {svc_count} services, {char_count} characteristics{RESET}"
                        )

                        for svc in profile["services"]:
                            print(f"    {YELLOW}Service: {svc['uuid']}{RESET}")
                            for ch in svc["characteristics"]:
                                props = ", ".join(ch["properties"])
                                print(f"      Char: {ch['uuid']} [{props}]")
                                if ch["value_decoded"]:
                                    print(f"        Value: {ch['value_decoded']}")
                                if ch["notifications"]:
                                    print(
                                        f"        Notifications: {len(ch['notifications'])} received"
                                    )

                except (KeyboardInterrupt, asyncio.CancelledError):
                    shutdown = True
                    break
                except Exception as e:
                    print(f"  {RED}Connection failed: {e}{RESET}")
                    seen[addr]["profile"] = {"error": str(e)}

                # Save to log
                log_data["devices"] = list(seen.values())
                save_log(log_data)
                print(f"  {DIM}Saved to {LOG_FILE}{RESET}")

            print()  # blank line between scan rounds

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    # Always save and print summary on exit
    log_data["devices"] = list(seen.values())
    save_log(log_data)
    print_summary(seen)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
