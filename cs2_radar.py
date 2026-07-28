"""
CS2 Terminal Radar - EDUCATIONAL USE ONLY.

Read-only, top-down terminal radar for Counter-Strike 2. Reads game memory
via a limited (PROCESS_VM_READ) handle and never writes to the game.

Never use online: run CS2 with `-insecure`. Using this in official/VAC-secured
matches will result in a ban.
"""

import math
import time
import os
import json
import ctypes
import argparse
from ctypes import wintypes
from pathlib import Path

import pymem
import pymem.process
import psutil
import requests

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
STD_OUTPUT_HANDLE = -11

# Offsets the radar actually uses. Anything not listed here is intentionally
# not loaded.
REQUIRED_OFFSETS = (
    "dwEntityList",
    "dwLocalPlayerController",
    "dwViewAngles",
    "m_hPlayerPawn",
    "m_iHealth",
    "m_iTeamNum",
    "m_vOldOrigin",
)

# Last-resort offsets baked into the binary, used only when both the network
# fetch and the local file are unavailable. Confirmed against a2x/cs2-dumper.
FALLBACK_OFFSETS = {
    "dwEntityList": 0x254FE70,
    "dwLocalPlayerController": 0x237FB70,
    "dwViewAngles": 0x23BAE18,
    "m_hPlayerPawn": 0x914,
    "m_iHealth": 0x34C,
    "m_iTeamNum": 0x3E7,
    "m_vOldOrigin": 0x13B8,
}

DEFAULT_CONFIG = {
    "mode": "terminal",
    "radar": {
        "map_size": 40,
        "update_interval": 0.2,
        "scale": 20,
        "colors_enabled": True,
    },
    "gui": {
        "window_width": 1040,
        "window_height": 720,
        "always_on_top": False,
        "opacity": 0.97,
    },
    "display": {
        "show_health_bars": True,
        "show_distances": True,
        "show_direction": True,
        "show_player_list": True,
        "max_players_in_list": 15,
    },
    "offsets": {
        "auto_update": True,
        "local_file": "offsets.json",
        "offsets_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json",
        "client_dll_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json",
    },
}


def _deep_merge(base, override):
    """Return base updated with override, recursing into nested dicts."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path="config.json"):
    """Load config.json, merged onto defaults. Missing/invalid -> defaults."""
    config_path = Path(path)
    if not config_path.exists():
        print(f"ℹ️  {path} not found, using default configuration.")
        return DEFAULT_CONFIG
    try:
        with config_path.open("r", encoding="utf-8") as f:
            user_config = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, user_config)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Could not read {path} ({e}); using defaults.")
        return DEFAULT_CONFIG


def _coerce_offset(value):
    """Accept an int or a hex string like '0x1234' and return an int."""
    if isinstance(value, str):
        return int(value, 16)
    return int(value)


class OffsetManager:
    """Loads the handful of offsets the radar needs.

    Resolution order:
      1. Download the latest dump from a2x/cs2-dumper (if auto_update).
      2. Fall back to the local flat offsets file.
      3. Fall back to the hardcoded FALLBACK_OFFSETS.
    """

    def __init__(self, offsets_config):
        self.config = offsets_config
        self.offsets = {}

    def load(self):
        print("🔄 Loading offsets...")

        if self.config.get("auto_update", True):
            fetched = self._download()
            if fetched:
                self._save_local(fetched)
                self.offsets = fetched
                self._report("network (a2x/cs2-dumper)")
                return self.offsets

        local = self._load_local()
        if local:
            self.offsets = local
            self._report(f"local file ({self.config.get('local_file', 'offsets.json')})")
            return self.offsets

        print("⚠️  Falling back to hardcoded offsets (may be outdated).")
        self.offsets = dict(FALLBACK_OFFSETS)
        self._report("hardcoded fallback")
        return self.offsets

    def _download(self):
        try:
            offsets_url = self.config["offsets_url"]
            client_dll_url = self.config["client_dll_url"]
            print("   Downloading offsets from a2x/cs2-dumper...")
            offsets_json = requests.get(offsets_url, timeout=5).json()
            client_dll_json = requests.get(client_dll_url, timeout=5).json()
            return self._extract(offsets_json, client_dll_json)
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"⚠️  Could not download offsets: {e}")
            return None

    @staticmethod
    def _extract(offsets_json, client_dll_json):
        """Pull the required offsets out of the a2x nested schema."""
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

    def _save_local(self, offsets):
        local_file = self.config.get("local_file", "offsets.json")
        payload = {
            "_comment": "Auto-generated cache of a2x/cs2-dumper offsets used by the radar.",
            "_source": "https://github.com/a2x/cs2-dumper",
        }
        payload.update({key: hex(value) for key, value in offsets.items()})
        try:
            with open(local_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as e:
            print(f"⚠️  Could not cache offsets to {local_file}: {e}")

    def _load_local(self):
        local_file = Path(self.config.get("local_file", "offsets.json"))
        if not local_file.exists():
            return None
        try:
            with local_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {key: _coerce_offset(data[key]) for key in REQUIRED_OFFSETS}
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
            print(f"⚠️  Could not use local offsets file: {e}")
            return None

    def _report(self, source):
        print(f"✅ Offsets loaded from {source}:")
        for key in REQUIRED_OFFSETS:
            print(f"   {key}: 0x{self.offsets[key]:X}")


class TerminalRadar:
    def __init__(self, config):
        radar_cfg = config["radar"]
        self.map_size = int(radar_cfg["map_size"])
        self.update_interval = float(radar_cfg["update_interval"])
        self.scale = float(radar_cfg["scale"])
        self.radius = self.map_size // 2
        self.display = config["display"]

        # Load offsets.
        offsets = OffsetManager(config["offsets"]).load()
        self.dwEntityList = offsets["dwEntityList"]
        self.dwLocalPlayerController = offsets["dwLocalPlayerController"]
        self.dwViewAngles = offsets["dwViewAngles"]
        self.m_hPlayerPawn = offsets["m_hPlayerPawn"]
        self.m_iHealth = offsets["m_iHealth"]
        self.m_iTeamNum = offsets["m_iTeamNum"]
        self.m_vOldOrigin = offsets["m_vOldOrigin"]

        self.pm = None
        self.process_handle = None
        self.client_base = None
        self.is_connected = False

        colors = {
            "RESET": "\033[0m",
            "RED": "\033[91m",
            "GREEN": "\033[92m",
            "YELLOW": "\033[93m",
            "BLUE": "\033[94m",
            "BOLD": "\033[1m",
            "DIM": "\033[2m",
            "BG_RED": "\033[41m",
            "BG_GREEN": "\033[42m",
            "BG_YELLOW": "\033[43m",
        }
        if not radar_cfg.get("colors_enabled", True):
            colors = {key: "" for key in colors}
        self.COLORS = colors

    # -- platform helpers ---------------------------------------------------

    @staticmethod
    def _enable_windows_ansi():
        """Enable ANSI/VT processing so colors render in classic cmd.exe."""
        if os.name != "nt":
            return
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.GetStdHandle.restype = wintypes.HANDLE
            handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            mode = wintypes.DWORD()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(
                    handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                )
        except OSError:
            pass

    @staticmethod
    def _clear_screen():
        # ANSI clear + cursor home (VT is enabled on Windows in run()).
        print("\033[2J\033[H", end="")

    # -- connection ---------------------------------------------------------

    def connect(self):
        try:
            pid = None
            for proc in psutil.process_iter(["pid", "name"]):
                if proc.info["name"] == "cs2.exe":
                    pid = proc.info["pid"]
                    break

            if not pid:
                print("❌ CS2 process not found")
                return False

            # OpenProcess returns a HANDLE (pointer-sized). Declare the return
            # type so the 64-bit handle is not truncated to a C int.
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            handle = kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
            )

            if not handle:
                print("❌ Failed to open process. Run as Administrator!")
                return False

            self.process_handle = handle
            self.pm = pymem.Pymem()
            self.pm.process_handle = handle
            self.pm.process_id = pid

            client_module = pymem.process.module_from_name(
                self.pm.process_handle, "client.dll"
            )
            if not client_module:
                print("❌ client.dll not found")
                return False

            self.client_base = client_module.lpBaseOfDll
            self.is_connected = True

            print(f"✅ Connected to CS2 (PID: {pid})")
            print(f"   client.dll base: 0x{self.client_base:X}")
            return True

        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def close(self):
        if self.process_handle:
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel32.CloseHandle(self.process_handle)
            except OSError:
                pass
            self.process_handle = None

    # -- memory reads -------------------------------------------------------

    def read_int(self, addr):
        try:
            return self.pm.read_int(addr)
        except Exception:
            return 0

    def read_longlong(self, addr):
        try:
            return self.pm.read_longlong(addr)
        except Exception:
            return 0

    def read_float(self, addr):
        try:
            return self.pm.read_float(addr)
        except Exception:
            return 0.0

    def read_vector(self, addr):
        x = self.read_float(addr)
        y = self.read_float(addr + 4)
        z = self.read_float(addr + 8)
        return (x, y, z)

    def get_view_angles(self):
        angles_addr = self.client_base + self.dwViewAngles
        yaw = self.read_float(angles_addr)
        pitch = self.read_float(angles_addr + 4)
        return (yaw, pitch)

    def resolve_pawn_handle(self, pawn_handle):
        """Resolve a pawn handle to a pawn address via the entity list."""
        entity_list = self.client_base + self.dwEntityList
        pawn_entry = self.read_longlong(
            entity_list
            + 0x10
            + 8 * ((pawn_handle & 0x7FFF) >> 9)
            + 0x70 * (pawn_handle & 0x1FF)
        )
        if not pawn_entry:
            return None
        pawn = self.read_longlong(pawn_entry + 0x78 * (pawn_handle & 0x1FF))
        return pawn or None

    def _read_player(self, controller):
        """Read one player's state from a controller address, or None."""
        pawn_handle = self.read_int(controller + self.m_hPlayerPawn)
        if not pawn_handle:
            return None

        pawn = self.resolve_pawn_handle(pawn_handle)
        if not pawn:
            return None

        health = self.read_int(pawn + self.m_iHealth)
        if health <= 0 or health > 100:
            return None

        team = self.read_int(pawn + self.m_iTeamNum)
        pos = self.read_vector(pawn + self.m_vOldOrigin)

        return {
            "pawn": pawn,
            "controller": controller,
            "health": health,
            "team": team,
            "position": pos,
        }

    def get_local_player(self):
        local_controller = self.read_longlong(
            self.client_base + self.dwLocalPlayerController
        )
        if not local_controller:
            return None
        return self._read_player(local_controller)

    def get_players(self, local):
        """Enumerate other players relative to the given local player."""
        players = []
        entity_list = self.client_base + self.dwEntityList

        for i in range(1, 65):
            controller = self.read_longlong(entity_list + i * 0x10)
            if not controller or controller == local["controller"]:
                continue

            player = self._read_player(controller)
            if not player:
                continue

            dx = player["position"][0] - local["position"][0]
            dy = player["position"][1] - local["position"][1]
            player["distance"] = math.sqrt(dx * dx + dy * dy)
            player["is_enemy"] = player["team"] != local["team"]
            players.append(player)

        return players

    # -- rendering ----------------------------------------------------------

    def world_to_radar(self, world_pos, local_pos, local_angles):
        dx = world_pos[0] - local_pos[0]
        dy = world_pos[1] - local_pos[1]

        if local_angles:
            yaw_rad = math.radians(local_angles[0])
            cos_yaw = math.cos(yaw_rad)
            sin_yaw = math.sin(yaw_rad)
            dx, dy = dx * cos_yaw - dy * sin_yaw, dx * sin_yaw + dy * cos_yaw

        grid_x = int(dx / self.scale) + self.radius
        grid_y = int(dy / self.scale) + self.radius

        grid_x = max(0, min(self.map_size - 1, grid_x))
        grid_y = max(0, min(self.map_size - 1, grid_y))

        return (grid_y, grid_x)

    def draw_health_bar(self, health, width=5):
        filled = int((health / 100) * width)
        empty = width - filled

        if health > 70:
            color = self.COLORS["BG_GREEN"]
        elif health > 40:
            color = self.COLORS["BG_YELLOW"]
        else:
            color = self.COLORS["BG_RED"]

        return f"{color}{'█' * filled}{self.COLORS['RESET']}{'░' * empty}"

    def render(self, players, local, local_angles):
        c = self.COLORS
        grid = [[" " for _ in range(self.map_size)] for _ in range(self.map_size)]

        for player in players:
            row, col = self.world_to_radar(
                player["position"], local["position"], local_angles
            )
            if player["is_enemy"]:
                if player["health"] > 70:
                    symbol = "E"
                elif player["health"] > 30:
                    symbol = "e"
                else:
                    symbol = "x"
            else:
                symbol = "A"
            grid[row][col] = symbol

        grid[self.radius][self.radius] = "@"

        self._clear_screen()

        print(f"{c['BOLD']}{'=' * 60}{c['RESET']}")
        print(f"{c['BOLD']}CS2 Radar{c['RESET']} - {time.strftime('%H:%M:%S')}")
        print(f"{c['DIM']}Players: {len(players)}{c['RESET']}")
        print(f"{c['BOLD']}{'=' * 60}{c['RESET']}")

        print(f"{c['BOLD']}╔{'═' * self.map_size}╗{c['RESET']}")
        cell_colors = {
            "@": c["GREEN"], "E": c["RED"], "e": c["YELLOW"],
            "x": c["DIM"], "A": c["BLUE"],
        }
        for row_idx in range(self.map_size):
            print(f"{c['BOLD']}║{c['RESET']}", end="")
            for col_idx in range(self.map_size):
                cell = grid[row_idx][col_idx]
                if cell in cell_colors:
                    print(f"{cell_colors[cell]}{cell}{c['RESET']}", end="")
                else:
                    print(f"{c['DIM']}.{c['RESET']}", end="")
            print(f"{c['BOLD']}║{c['RESET']}")
        print(f"{c['BOLD']}╚{'═' * self.map_size}╝{c['RESET']}")

        enemies = [p for p in players if p["is_enemy"]]
        allies = [p for p in players if not p["is_enemy"]]

        print(f"\n{c['BOLD']}Stats:{c['RESET']}")
        print(f"  {c['RED']}Enemies:{c['RESET']} {len(enemies)}")
        print(f"  {c['BLUE']}Allies:{c['RESET']} {len(allies)}")
        if self.display.get("show_distances", True) and enemies:
            closest = min(enemies, key=lambda p: p["distance"])
            print(f"  {c['YELLOW']}Closest Enemy:{c['RESET']} {closest['distance']:.1f} units")

        if self.display.get("show_player_list", True) and players:
            max_players = int(self.display.get("max_players_in_list", 15))
            show_hp_bar = self.display.get("show_health_bars", True)
            show_dist = self.display.get("show_distances", True)
            print(f"\n{c['BOLD']}Players:{c['RESET']}")
            for player in players[:max_players]:
                label = (
                    f"{c['RED']}ENEMY{c['RESET']}" if player["is_enemy"]
                    else f"{c['BLUE']}ALLY{c['RESET']}"
                )
                line = f"{label:12} {player['health']:3}%"
                if show_dist:
                    line += f"  {player['distance']:7.1f}"
                if show_hp_bar:
                    line += f"  {self.draw_health_bar(player['health'])}"
                print(line)

        if self.display.get("show_direction", True) and local_angles:
            yaw = local_angles[0]
            direction = (
                "NORTH" if -45 < yaw <= 45 else
                "EAST" if 45 < yaw <= 135 else
                "SOUTH" if 135 < yaw <= 225 or yaw < -135 else
                "WEST"
            )
            print(f"\n{c['BOLD']}Facing:{c['RESET']} {direction} ({yaw:.1f}°)")

        print(f"\n{c['BOLD']}Legend:{c['RESET']}")
        print(f"  {c['GREEN']}@{c['RESET']} = You")
        print(f"  {c['RED']}E{c['RESET']} = Enemy (HP > 70%)")
        print(f"  {c['YELLOW']}e{c['RESET']} = Enemy (HP 30-70%)")
        print(f"  {c['DIM']}x{c['RESET']} = Enemy (HP < 30%)")
        print(f"  {c['BLUE']}A{c['RESET']} = Ally")
        print(f"  {c['DIM']}.{c['RESET']} = Empty")

    # -- main loop ----------------------------------------------------------

    def run(self):
        self._enable_windows_ansi()
        print("=" * 60)
        print("CS2 Terminal Radar")
        print("=" * 60)
        print("⚠️  Educational purposes only - run CS2 with -insecure")
        print("⚠️  Run this as Administrator")
        print("=" * 60)

        if input("\nContinue? (yes/no): ").strip().lower() != "yes":
            return

        if not self.connect():
            print("❌ Failed to connect")
            return

        print("\n✅ Starting radar... Press Ctrl+C to stop\n")
        time.sleep(1)

        try:
            while True:
                local = self.get_local_player()
                if not local:
                    print("\r❌ Waiting for player...", end="", flush=True)
                    time.sleep(1)
                    continue

                local_angles = self.get_view_angles()
                players = self.get_players(local)
                self.render(players, local, local_angles)
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            self.close()
            print("✅ Clean exit")


def main():
    parser = argparse.ArgumentParser(description="Read-only CS2 radar")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="open the desktop radar")
    mode.add_argument("--terminal", action="store_true", help="use the terminal radar")
    args = parser.parse_args()

    config = load_config()
    selected_mode = (
        "gui" if args.gui else
        "terminal" if args.terminal else
        str(config.get("mode", "terminal")).lower()
    )
    if selected_mode == "gui":
        from gui_radar import GuiRadar
        radar = GuiRadar(config)
    else:
        radar = TerminalRadar(config)
    radar.run()


if __name__ == "__main__":
    main()
