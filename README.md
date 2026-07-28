<div align="center">

# CS2 Radar

### Read-only radar, tactical map, and camera-overlay research tool for Counter-Strike 2

[![Latest release](https://img.shields.io/github/v/release/khashino/cs2-terminal-radar?display_name=tag&sort=semver)](https://github.com/khashino/cs2-terminal-radar/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/khashino/cs2-terminal-radar/total)](https://github.com/khashino/cs2-terminal-radar/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)](https://github.com/khashino/cs2-terminal-radar/releases/latest)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](#license)

[Download the latest Windows release](https://github.com/khashino/cs2-terminal-radar/releases/latest)
|
[Watch the full demo](./DEMO/Video.mp4)
|
[Run from source](#run-from-source)

</div>

> [!IMPORTANT]
> This project is intended for education and controlled research into how
> radar and ESP-style cheats expose game information. It is not an anti-cheat
> and must not be used to retaliate against suspected cheaters in live games.
> Report suspected cheaters through CS2's official reporting tools.

## Preview

[![Animated preview of CS2 Radar](./DEMO/Video.gif)](./DEMO/Video.mp4)

Click the preview to open the full-quality MP4 demonstration.

## What it provides

CS2 Radar presents read-only game information through three focused
workspaces:

| Workspace | Description |
| --- | --- |
| Camera Overlay | A click-through projection aligned with the CS2 client window |
| Tactical Map | A north-up overview for complete spatial context |
| Local Radar | A compact, heading-up radar centered on the local player |

Additional capabilities include:

- Professional desktop observation console
- Optional terminal interface
- Player distance, direction, health, and closest-contact information
- Color-coded health bars and team markers
- Adjustable range, refresh interval, opacity, and always-on-top behavior
- Automatic offsets from [a2x/cs2-dumper](https://github.com/a2x/cs2-dumper)
- Cached and built-in fallback offsets for offline startup
- Animated demo mode that does not require CS2

## Responsible-use notice

This software reads another process's memory. Although it does not write to
game memory, that does **not** make it safe for VAC-secured or official play.
There is no guarantee that an anti-cheat system will not detect it.

Use this project only:

- On a client you own and control
- In a private, controlled testing environment
- With CS2 launched using `-insecure`
- For education, security research, or interface experimentation

Never use it in official matchmaking, VAC-secured servers, tournaments, or to
gain an advantage over other players. If you encounter a cheater, report and
block them instead of responding with another cheat.

## Download

The ready-to-run Windows executable is available from
[GitHub Releases](https://github.com/khashino/cs2-terminal-radar/releases/latest).

1. Download `CS2-Radar.exe` from the latest release.
2. Launch your private CS2 test client with `-insecure -novid -nojoy`.
3. Run `CS2-Radar.exe` as Administrator.
4. Select Camera Overlay, Tactical Map, or Local Radar.

The release executable is standalone; Python is not required.

## Controls

| Input | Action |
| --- | --- |
| `F8` | Close the camera overlay and return to the main menu |
| `Insert` | Close the camera overlay and return to the main menu |
| Navigation bar | Switch between Menu, ESP, Map, and Radar |
| `Ctrl+C` | Exit the terminal interface |

## Run from source

### Requirements

- Windows 10 or Windows 11, 64-bit
- Python 3.8 or newer
- Administrator privileges for live process access
- A private CS2 client started with `-insecure`

Clone the repository and install its dependencies:

```powershell
git clone https://github.com/khashino/cs2-terminal-radar.git
cd cs2-terminal-radar
python -m pip install -r requirements.txt
python main.py
```

### Launch options

```powershell
# Default desktop GUI
python main.py

# Explicit desktop GUI
python main.py --gui

# Animated interface preview; CS2 is not required
python main.py --demo

# Original terminal interface
python main.py --terminal
```

Demo mode uses simulated contacts and does not connect to another process or
download offsets.

## Configuration

Runtime settings are stored in `config.json` and can also be changed from the
GUI:

```json
{
  "mode": "gui",
  "radar": {
    "map_size": 40,
    "update_interval": 0.02,
    "scale": 20.0,
    "colors_enabled": true
  },
  "gui": {
    "window_width": 760,
    "window_height": 720,
    "always_on_top": true,
    "opacity": 0.97,
    "view_mode": "menu",
    "map_bounds": null
  },
  "display": {
    "show_health_bars": true,
    "show_distances": true,
    "show_direction": true,
    "show_player_list": true,
    "max_players_in_list": 15
  },
  "offsets": {
    "auto_update": true,
    "local_file": "offsets.json",
    "offsets_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json",
    "client_dll_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json"
  }
}
```

## Build the executable

The included build script creates a standalone, windowed Windows executable
and bundles the required Tcl/Tk runtime, default configuration, and cached
offsets:

```powershell
python -m pip install pyinstaller
python build_exe.py
```

Build output:

```text
dist/CS2-Radar.exe
```

Saved settings and refreshed offsets are stored beside the executable.

## Troubleshooting

### Connection failed

- Confirm that CS2 is already running.
- Run CS2 Radar as Administrator.
- Confirm that both applications run under the same Windows user.

### Overlay is active and the menu is hidden

Press `F8` or `Insert` to close the overlay and show the main menu.

### Data stopped updating after a CS2 update

Keep `offsets.auto_update` enabled, or refresh the cached offsets manually:

```powershell
python update_offsets.py
```

### Preview the interface without process access

```powershell
python main.py --demo
```

## Project layout

```text
cs2-terminal-radar/
|-- DEMO/
|   |-- Video.gif
|   `-- Video.mp4
|-- main.py
|-- gui_radar.py
|-- config.json
|-- offsets.json
|-- build_exe.py
|-- packaging/
|-- update_offsets.py
`-- requirements.txt
```

## Credits

Offset data is sourced from
[a2x/cs2-dumper](https://github.com/a2x/cs2-dumper).

Counter-Strike 2 and Valve are trademarks of Valve Corporation. This project
is independent and is not affiliated with, endorsed by, or sponsored by
Valve Corporation.

## License

Released under the MIT License.
