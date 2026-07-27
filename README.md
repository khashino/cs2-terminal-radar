# CS2 Terminal Radar 🎯

> Terminal-based radar for Counter-Strike 2 - **Educational purposes only**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## ⚠️ Disclaimer

**EDUCATIONAL USE ONLY.** Never use in online matches. Run CS2 with `-insecure` flag when testing. Using this online will result in a VAC ban.

## ✨ Features

- Real-time top-down radar in terminal
- Direction indicator (N/E/S/W)
- Distance to players
- Health bars (Green/Yellow/Red)
- Weapon detection
- Auto-updating offsets from GitHub
- Configurable via JSON

## 📁 Structure
```
cs2-terminal-radar/
├── cs2_radar.py # Main app
├── config.json # Settings (auto-created)
├── offsets.json # Game offsets (auto-downloaded)
└── update_offsets.py # Manual offset updater
```

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/khashino/cs2-terminal-radar.git
cd cs2-terminal-radar
pip install pymem requests

# Run (config/offsets auto-generate)
python cs2_radar.py
```

## ⚙️ Configuration
Edit config.json to customize:

```
{
  "radar": {
    "map_size": 40,           // Grid size
    "update_interval": 0.2,   // Update speed
    "scale": 20,              // Zoom level
    "colors_enabled": true
  },
  "display": {
    "show_health_bars": true,
    "show_weapons": true,
    "show_distances": true,
    "show_direction": true
  },
  "offsets_source": {
    "auto_update": true       // Auto-fetch from GitHub
  }
}
```
## 🎮 Usage
Launch CS2 with: -insecure -novid -nojoy
```
Run: python cs2_radar.py
```
Press Ctrl+C to exit

## Quick Start

```bash
git clone https://github.com/khashino/cs2-terminal-radar.git
cd cs2-terminal-radar
pip install pymem requests
python cs2_radar.py
```

## Config
Edit config.json to customize map size, zoom, colors, etc.

## License
MIT
