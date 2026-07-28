# CS2 Radar

> A read-only terminal and desktop visualization for Counter-Strike 2.
> Educational use only.

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Demo

<video src="./DEMO/Video.mp4" controls width="100%">
  Your browser does not support embedded video.
</video>

[Watch or download the full software demo](./DEMO/Video.mp4)

## Disclaimer

**Educational use only.** This tool reads game memory but never writes to it.
Use it only with your own client launched using `-insecure`. Never use it in
official or VAC-secured matches.

## Features

- Professional desktop observation console
- Startup selector for Camera Overlay, Tactical Map, and Local Radar
- Real-time top-down terminal radar
- Read-only camera projection with player boxes, distance, and health
- Click-through overlay aligned to the CS2 window
- Full-map and heading-up local-radar views
- Health bars, direction, distance, and closest-enemy information
- Settings for range, refresh rate, opacity, always-on-top, and contact display
- Automatic offsets from [a2x/cs2-dumper](https://github.com/a2x/cs2-dumper)
- Offline cached and built-in fallback offsets

## Controls

| Key | Action |
| --- | --- |
| `F8` | Close the camera overlay and show the main menu |
| `Insert` | Close the camera overlay and show the main menu |
| `Ctrl+C` | Exit terminal mode |

You can also switch between Menu, ESP, Map, and Radar from the navigation bar.

## Download and run the executable

The packaged Windows application is generated at:

```text
dist/CS2-Radar.exe
```

1. Launch CS2 with `-insecure -novid -nojoy`.
2. Run `CS2-Radar.exe` as Administrator.
3. Choose a view from the main menu.
4. While the camera overlay is active, press `F8` to show the menu again.

No Python installation is required for the packaged executable.

## Run from source

Requires Python 3.8 or newer on Windows:

```powershell
git clone https://github.com/khashino/cs2-terminal-radar.git
cd cs2-terminal-radar
python -m pip install -r requirements.txt
python main.py
```

Open the GUI explicitly:

```powershell
python main.py --gui
```

Preview the complete interface with simulated data and without CS2:

```powershell
python main.py --demo
```

Use the original terminal interface:

```powershell
python main.py --terminal
```

## Build the Windows executable

Install PyInstaller and run the included reproducible build script:

```powershell
python -m pip install pyinstaller
python build_exe.py
```

The output will be available at `dist/CS2-Radar.exe`. Bundled defaults work on
first launch. Saved settings and downloaded offsets are stored beside the
executable.

## Configuration

Settings are stored in `config.json`:

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

## Project structure

```text
cs2-terminal-radar/
├── DEMO/
│   └── Video.mp4
├── main.py
├── gui_radar.py
├── config.json
├── offsets.json
├── build_exe.py
├── packaging/
├── update_offsets.py
└── requirements.txt
```

## License

MIT
