# CS2 Terminal Radar 🎯

> Terminal-based, read-only radar for Counter-Strike 2 - **Educational purposes only**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## ⚠️ Disclaimer

**EDUCATIONAL USE ONLY.** This tool only *reads* game memory; it never writes to
the game. Never use it in official or VAC-secured matches — doing so will result
in a VAC ban. Only run it against your own client launched with `-insecure`.

## ✨ Features

- Real-time top-down radar in the terminal
- Direction indicator (N/E/S/W)
- Distance to players and closest-enemy readout
- Health bars (green/yellow/red)
- Offsets auto-downloaded from [a2x/cs2-dumper](https://github.com/a2x/cs2-dumper),
  with an offline fallback
- Configurable via `config.json`

## 📁 Structure

```
cs2-terminal-radar/
├── cs2_radar.py       # Main app
├── config.json        # Settings (loaded on startup; defaults used if missing)
├── offsets.json       # Offline fallback offsets (auto-refreshed when online)
├── update_offsets.py  # Manual offset updater
└── requirements.txt   # Python dependencies
```

## 🚀 Quick Start

Requires **Python 3.8+ on Windows** and a running CS2 client. Reading another
process's memory needs elevated rights, so run your terminal **as Administrator**.

```bash
git clone https://github.com/khashino/cs2-terminal-radar.git
cd cs2-terminal-radar
pip install -r requirements.txt   # pymem, psutil, requests

# Launch CS2 with:  -insecure -novid -nojoy
python cs2_radar.py
```

Press `Ctrl+C` to exit.

## ⚙️ Configuration

Edit `config.json` (all keys are optional — missing keys fall back to defaults):

```jsonc
{
  "radar": {
    "map_size": 40,          // Grid size (cells)
    "update_interval": 0.2,  // Seconds between refreshes
    "scale": 20,             // World units per grid cell (zoom)
    "colors_enabled": true
  },
  "display": {
    "show_health_bars": true,
    "show_distances": true,
    "show_direction": true,
    "show_player_list": true,
    "max_players_in_list": 15
  },
  "offsets": {
    "auto_update": true,     // Download latest offsets on startup
    "local_file": "offsets.json",
    "offsets_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json",
    "client_dll_url": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json"
  }
}
```

## 🔄 Offsets

Offsets change with every CS2 update. With `auto_update` enabled the radar fetches
the latest values from a2x/cs2-dumper on startup and caches them to `offsets.json`.
To refresh manually (or when `auto_update` is off):

```bash
python update_offsets.py
```

If the download fails, the radar uses the cached `offsets.json`, and if that is
missing too, a set of hardcoded fallback offsets baked into `cs2_radar.py`.

## License

MIT
