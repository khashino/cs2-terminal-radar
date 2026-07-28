"""
Manually refresh offsets.json from a2x/cs2-dumper.

The radar auto-updates offsets on startup when config.radar/offsets.auto_update
is enabled, so running this is optional. Use it to pre-populate the offline
fallback file or when auto_update is turned off.

Only `requests` is required for this script.
"""

import json
import argparse

import requests

OFFSETS_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json"
CLIENT_DLL_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json"


def extract(offsets_json, client_dll_json):
    """Pull the offsets the radar needs out of the a2x nested schema."""
    client = offsets_json["client.dll"]
    classes = client_dll_json["client.dll"]["classes"]
    return {
        "dwEntityList": client["dwEntityList"],
        "dwLocalPlayerController": client["dwLocalPlayerController"],
        "dwViewAngles": client["dwViewAngles"],
        "m_hPlayerPawn": classes["CCSPlayerController"]["fields"]["m_hPlayerPawn"],
        "m_iHealth": classes["C_BaseEntity"]["fields"]["m_iHealth"],
        "m_iTeamNum": classes["C_BaseEntity"]["fields"]["m_iTeamNum"],
        "m_vOldOrigin": classes["C_BasePlayerPawn"]["fields"]["m_vOldOrigin"],
    }


def update_offsets(offsets_url=OFFSETS_URL, client_dll_url=CLIENT_DLL_URL,
                   output="offsets.json"):
    print("🔄 Updating offsets from a2x/cs2-dumper...")
    try:
        offsets_json = requests.get(offsets_url, timeout=10).json()
        client_dll_json = requests.get(client_dll_url, timeout=10).json()
        offsets = extract(offsets_json, client_dll_json)

        payload = {
            "_comment": "Offline fallback offsets for cs2_radar.py (flat schema, hex strings).",
            "_source": "https://github.com/a2x/cs2-dumper",
        }
        payload.update({key: hex(value) for key, value in offsets.items()})

        with open(output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(f"✅ Offsets written to {output}")
        for key, value in offsets.items():
            print(f"   {key}: {hex(value)}")
        return True
    except (requests.RequestException, ValueError, KeyError, OSError) as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update offsets.json from a2x/cs2-dumper")
    parser.add_argument("--offsets-url", default=OFFSETS_URL, help="URL for offsets.json")
    parser.add_argument("--client-dll-url", default=CLIENT_DLL_URL, help="URL for client_dll.json")
    parser.add_argument("--output", default="offsets.json", help="Output file name")
    args = parser.parse_args()

    update_offsets(args.offsets_url, args.client_dll_url, args.output)
