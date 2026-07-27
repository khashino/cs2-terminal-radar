# CS2 Terminal Radar 🎯

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![CS2 Build](https://img.shields.io/badge/CS2-14172-blueviolet.svg)]()

> A terminal-based radar for Counter-Strike 2 - **Educational purposes only**

## ⚠️ Important Disclaimer

**This tool is created for EDUCATIONAL and LEARNING purposes only.**

- ❌ **DO NOT** use this in online matches
- ❌ **DO NOT** use this to gain an unfair advantage
- ✅ **DO** use this to learn about game memory, offsets, and visualization
- ✅ **DO** run CS2 with `-insecure` flag when testing

**Using this in online matches can result in a permanent VAC ban.**

## 📋 Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Offsets Management](#offsets-management)
- [Screenshots](#screenshots)
- [Safety](#safety)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

- **Real-time Radar** - Top-down 2D map in your terminal
- **Direction Indicator** - Shows which way you're facing (N/E/S/W)
- **Distance Labels** - Displays distance to each player in units
- **Health Bars** - Visual health indicators (Green/Yellow/Red)
- **Weapon Detection** - Shows enemy weapon types (placeholder)
- **Player List** - Detailed list with health, distance, and weapons
- **Map Rotation** - Rotates based on your view angle
- **Automatic Logging** - Saves radar data to timestamped log files
- **Cross-platform** - Works on Windows, Linux, and macOS

## 🧠 How It Works

The radar reads CS2's memory to get player positions and displays them in your terminal. It uses:

1. **Memory Reading** - Reads player data from CS2 process memory
2. **Offset System** - Uses the latest offsets from [CS2-OFFSETS](https://github.com/sezzyaep/CS2-OFFSETS)
3. **Projection Math** - Converts 3D world positions to 2D radar coordinates
4. **Terminal Rendering** - Displays everything using ANSI colors and Unicode characters

Unlike traditional ESP overlays, this runs in your terminal - making it significantly safer and looking like a development tool.

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- CS2 installed and running (with `-insecure` flag)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/cs2-terminal-radar.git
cd cs2-terminal-radar

# Install dependencies
pip install pymem psutil

# Run the radar
python cs2_radar.py
