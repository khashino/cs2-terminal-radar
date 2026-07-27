"""
CS2 Terminal Radar - Educational Tool
Loads configuration and offsets from external JSON files
"""

import pymem
import pymem.process
import math
import time
import os
import sys
import json
import datetime
import requests
from typing import Optional, Tuple, List, Dict

class ConfigManager:
    """Manages configuration and offsets loading"""
    
    def __init__(self, config_file="config.json", offsets_file="offsets.json"):
        self.config_file = config_file
        self.offsets_file = offsets_file
        self.config = {}
        self.offsets = {}
        self.load_config()
        self.load_offsets()
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                print(f"⚠️  Config file {self.config_file} not found. Using defaults.")
                self.config = self.get_default_config()
                self.save_config()
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            "radar": {
                "map_size": 40,
                "update_interval": 0.2,
                "scale": 20,
                "log_enabled": True,
                "colors_enabled": True
            },
            "display": {
                "show_health_bars": True,
                "show_weapons": True,
                "show_distances": True,
                "show_direction": True,
                "show_player_list": True,
                "max_players_in_list": 15
            },
            "safety": {
                "require_insecure": True,
                "read_only_mode": True
            },
            "offsets_source": {
                "url": "https://raw.githubusercontent.com/sezzyaep/CS2-OFFSETS/main/offsets.json",
                "local_file": "offsets.json",
                "auto_update": True,
                "update_check_interval": 86400
            },
            "logging": {
                "enabled": True,
                "log_file_prefix": "radar_log",
                "log_level": "INFO",
                "max_log_files": 10
            }
        }
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save config: {e}")
    
    def load_offsets(self):
        """Load offsets from JSON file or fetch from GitHub"""
        source = self.config.get("offsets_source", {})
        local_file = source.get("local_file", "offsets.json")
        auto_update = source.get("auto_update", True)
        
        # Try to load local offsets file
        if os.path.exists(local_file):
            try:
                with open(local_file, 'r') as f:
                    self.offsets = json.load(f)
                print(f"✅ Loaded offsets from {local_file}")
                print(f"   Build: {self.offsets.get('build', 'Unknown')}")
                print(f"   Timestamp: {self.offsets.get('timestamp', 'Unknown')}")
                return True
            except Exception as e:
                print(f"⚠️  Error loading offsets file: {e}")
        
        # Try to fetch from GitHub if auto_update is enabled
        if auto_update:
            url = source.get("url")
            if url:
                print(f"🔄 Fetching offsets from GitHub...")
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        self.offsets = response.json()
                        # Save to local file
                        with open(local_file, 'w') as f:
                            json.dump(self.offsets, f, indent=2)
                        print(f"✅ Downloaded and saved offsets")
                        print(f"   Build: {self.offsets.get('build', 'Unknown')}")
                        print(f"   Timestamp: {self.offsets.get('timestamp', 'Unknown')}")
                        return True
                    else:
                        print(f"❌ Failed to fetch offsets: HTTP {response.status_code}")
                except Exception as e:
                    print(f"❌ Error fetching offsets: {e}")
        
        print("❌ Could not load offsets. Using hardcoded fallback values.")
        self.offsets = self.get_fallback_offsets()
        return False
    
    def get_fallback_offsets(self):
        """Return hardcoded fallback offsets"""
        return {
            "timestamp": "Unknown",
            "build": 0,
            "client_dll": {
                "dwLocalPlayerPawn": "0x23A5238",
                "dwEntityList": "0x254FE70",
                "dwViewAngles": "0x23BAE18",
                "dwViewMatrix": "0x23AA340"
            },
            "netvars": {
                "m_iHealth": "0x344",
                "m_iTeamNum": "0x3E3",
                "m_vOldOrigin": "0x1324",
                "m_hPlayerPawn": "0x814"
            }
        }
    
    def get(self, key, default=None):
        """Get config value by dot notation (e.g., 'radar.map_size')"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    def get_offset(self, key, default="0x0"):
        """Get offset value by dot notation (e.g., 'client_dll.dwLocalPlayerPawn')"""
        keys = key.split('.')
        value = self.offsets
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return int(default, 16) if isinstance(default, str) and default.startswith('0x') else default
        
        # Convert hex string to int
        if isinstance(value, str) and value.startswith('0x'):
            return int(value, 16)
        return value

class TerminalRadar:
    """Main radar class with external config and offsets"""
    
    def __init__(self, config_manager=None):
        self.config = config_manager or ConfigManager()
        self.map_size = self.config.get('radar.map_size', 40)
        self.update_interval = self.config.get('radar.update_interval', 0.2)
        self.radius = self.map_size // 2
        self.scale = self.config.get('radar.scale', 20)
        self.log_enabled = self.config.get('radar.log_enabled', True)
        self.colors_enabled = self.config.get('radar.colors_enabled', True)
        
        # Display settings
        self.show_health_bars = self.config.get('display.show_health_bars', True)
        self.show_weapons = self.config.get('display.show_weapons', True)
        self.show_distances = self.config.get('display.show_distances', True)
        self.show_direction = self.config.get('display.show_direction', True)
        self.show_player_list = self.config.get('display.show_player_list', True)
        self.max_players_in_list = self.config.get('display.max_players_in_list', 15)
        
        # Logging settings
        self.log_prefix = self.config.get('logging.log_file_prefix', 'radar_log')
        self.log_level = self.config.get('logging.log_level', 'INFO')
        self.max_log_files = self.config.get('logging.max_log_files', 10)
        
        self.rotation_angle = 0
        self.log_file = None
        self.pm = None
        self.client_base = None
        self.engine_base = None
        self.is_connected = False
        
        # Initialize logging
        if self.log_enabled:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = f"{self.log_prefix}_{timestamp}.txt"
            self.cleanup_old_logs()
        
        # Colors
        self.COLORS = {
            'RESET': '\033[0m',
            'RED': '\033[91m',
            'GREEN': '\033[92m',
            'YELLOW': '\033[93m',
            'BLUE': '\033[94m',
            'MAGENTA': '\033[95m',
            'CYAN': '\033[96m',
            'WHITE': '\033[97m',
            'BOLD': '\033[1m',
            'DIM': '\033[2m',
            'BG_RED': '\033[41m',
            'BG_GREEN': '\033[42m',
            'BG_YELLOW': '\033[43m',
        }
    
    def cleanup_old_logs(self):
        """Remove old log files to prevent clutter"""
        try:
            log_files = sorted([f for f in os.listdir('.') if f.startswith(self.log_prefix)])
            if len(log_files) > self.max_log_files:
                for f in log_files[:-self.max_log_files]:
                    os.remove(f)
        except:
            pass
    
    def connect(self) -> bool:
        """Connect to CS2 process"""
        try:
            self.pm = pymem.Pymem("cs2.exe")
            
            client_module = pymem.process.module_from_name(
                self.pm.process_handle, "client.dll"
            )
            if not client_module:
                return False
            self.client_base = client_module.lpBaseOfDll
            
            engine_module = pymem.process.module_from_name(
                self.pm.process_handle, "engine2.dll"
            )
            if engine_module:
                self.engine_base = engine_module.lpBaseOfDll
            
            self.is_connected = True
            self.log("INFO", "Connected to CS2 successfully")
            return True
        except Exception as e:
            self.log("ERROR", f"Connection failed: {e}")
            return False
    
    def log(self, level: str, message: str):
        """Write to log file"""
        if not self.log_enabled or not self.log_file:
            return
        try:
            if level == "INFO" and self.log_level != "INFO":
                return
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, 'a') as f:
                f.write(f"[{timestamp}] [{level}] {message}\n")
        except:
            pass
    
    # [Continue with all the reading methods from the previous code]
    def read_int(self, address: int) -> int:
        try:
            return self.pm.read_int(address)
        except:
            return 0
    
    def read_longlong(self, address: int) -> int:
        try:
            return self.pm.read_longlong(address)
        except:
            return 0
    
    def read_float(self, address: int) -> float:
        try:
            return self.pm.read_float(address)
        except:
            return 0.0
    
    def read_vector(self, address: int) -> Optional[Tuple[float, float, float]]:
        try:
            x = self.read_float(address)
            y = self.read_float(address + 0x4)
            z = self.read_float(address + 0x8)
            return (x, y, z)
        except:
            return None
    
    def get_view_angles(self) -> Optional[Tuple[float, float]]:
        """Get player view angles using loaded offsets"""
        try:
            angles_addr = self.client_base + self.config.get_offset('client_dll.dwViewAngles')
            yaw = self.read_float(angles_addr)
            pitch = self.read_float(angles_addr + 0x4)
            return (yaw, pitch)
        except:
            return None
    
    def get_local_player(self) -> Optional[Tuple[int, Tuple[float, float, float], Tuple[float, float]]]:
        """Get local player info using loaded offsets"""
        try:
            local_pawn = self.read_longlong(
                self.client_base + self.config.get_offset('client_dll.dwLocalPlayerPawn')
            )
            if not local_pawn:
                return None
            
            team = self.read_int(local_pawn + self.config.get_offset('netvars.m_iTeamNum'))
            pos = self.read_vector(local_pawn + self.config.get_offset('netvars.m_vOldOrigin'))
            angles = self.get_view_angles()
            
            if not pos:
                return None
            
            return (team, pos, angles)
        except Exception as e:
            self.log("ERROR", f"get_local_player failed: {e}")
            return None
    
    def get_active_weapon(self, pawn: int) -> str:
        """Placeholder weapon detection"""
        try:
            is_scoped = self.read_int(pawn + self.config.get_offset('netvars.m_bIsScoped'))
            if is_scoped:
                return "SNIPER"
            
            shots = self.read_int(pawn + self.config.get_offset('netvars.m_iShotsFired'))
            if shots > 5:
                return "AUTO"
            
            return "PISTOL"
        except:
            return "?"
    
    def get_players(self) -> List[Dict]:
        """Get all players using loaded offsets"""
        players = []
        local_info = self.get_local_player()
        
        if not local_info:
            return players
        
        local_team, local_pos, local_angles = local_info
        entity_list = self.client_base + self.config.get_offset('client_dll.dwEntityList')
        
        for i in range(1, 65):
            try:
                list_entry = self.read_longlong(
                    entity_list + (8 * (i & 0x7FFF) >> 9) + 16
                )
                if not list_entry:
                    continue
                
                controller = self.read_longlong(
                    list_entry + 120 * (i & 0x1FF)
                )
                if not controller:
                    continue
                
                pawn_handle = self.read_int(
                    controller + self.config.get_offset('netvars.m_hPlayerPawn')
                )
                if not pawn_handle:
                    continue
                
                pawn_entry = self.read_longlong(
                    entity_list + 0x10 + 
                    8 * ((pawn_handle & 0x7FFF) >> 9) + 
                    0x70 * (pawn_handle & 0x1FF)
                )
                if not pawn_entry:
                    continue
                
                pawn = self.read_longlong(
                    pawn_entry + 0x78 * (pawn_handle & 0x1FF)
                )
                if not pawn:
                    continue
                
                health = self.read_int(pawn + self.config.get_offset('netvars.m_iHealth'))
                if health <= 0 or health > 100:
                    continue
                
                team = self.read_int(pawn + self.config.get_offset('netvars.m_iTeamNum'))
                pos = self.read_vector(pawn + self.config.get_offset('netvars.m_vOldOrigin'))
                
                if not pos:
                    continue
                
                weapon = self.get_active_weapon(pawn)
                
                dx = pos[0] - local_pos[0]
                dy = pos[1] - local_pos[1]
                distance = math.sqrt(dx*dx + dy*dy)
                
                players.append({
                    'pawn': pawn,
                    'health': health,
                    'team': team,
                    'position': pos,
                    'weapon': weapon,
                    'distance': distance,
                    'is_enemy': team != local_team,
                    'is_local': pawn == local_info[0] if local_info[0] else False
                })
                
            except:
                continue
        
        players.sort(key=lambda p: p['distance'])
        return players
    
    def world_to_radar(self, world_pos: Tuple[float, float, float], 
                      local_pos: Tuple[float, float, float],
                      local_angles: Tuple[float, float]) -> Tuple[int, int]:
        """Convert world position to radar grid coordinates"""
        dx = world_pos[0] - local_pos[0]
        dy = world_pos[1] - local_pos[1]
        
        if local_angles:
            yaw_rad = math.radians(local_angles[0])
            cos_yaw = math.cos(yaw_rad)
            sin_yaw = math.sin(yaw_rad)
            rotated_dx = dx * cos_yaw - dy * sin_yaw
            rotated_dy = dx * sin_yaw + dy * cos_yaw
            dx, dy = rotated_dx, rotated_dy
        
        grid_x = int(dx / self.scale) + self.radius
        grid_y = int(dy / self.scale) + self.radius
        
        grid_x = max(0, min(self.map_size - 1, grid_x))
        grid_y = max(0, min(self.map_size - 1, grid_y))
        
        return (grid_y, grid_x)
    
    def draw_health_bar(self, health: int, width: int = 5) -> str:
        """Create a visual health bar string"""
        filled = int((health / 100) * width)
        empty = width - filled
        
        if not self.colors_enabled:
            return f"{'█' * filled}{'░' * empty}"
        
        if health > 70:
            color = self.COLORS['BG_GREEN']
        elif health > 40:
            color = self.COLORS['BG_YELLOW']
        else:
            color = self.COLORS['BG_RED']
        
        return f"{color}{'█' * filled}{self.COLORS['RESET']}{'░' * empty}"
    
    def render_radar(self, players: List[Dict], local_info: Tuple[int, Tuple[float, float, float], Tuple[float, float]]):
        """Render the radar map"""
        local_team, local_pos, local_angles = local_info
        
        grid = [[' ' for _ in range(self.map_size)] for _ in range(self.map_size)]
        player_data = {}
        
        for player in players:
            if player['is_local']:
                continue
            
            row, col = self.world_to_radar(player['position'], local_pos, local_angles)
            player_data[(row, col)] = player
            
            if player['is_enemy']:
                if player['health'] > 70:
                    symbol = 'E'
                elif player['health'] > 30:
                    symbol = 'e'
                else:
                    symbol = 'x'
            else:
                symbol = 'A'
            
            grid[row][col] = symbol
        
        grid[self.radius][self.radius] = '@'
        
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print header
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}CS2 Radar{self.COLORS['RESET']} - Updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"{self.COLORS['DIM']}Build: {self.config.offsets.get('build', 'Unknown')} | Press Ctrl+C to exit{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        
        # Print map
        print(f"{self.COLORS['BOLD']}╔{'═' * self.map_size}╗{self.COLORS['RESET']}")
        
        for row_idx in range(self.map_size):
            print(f"{self.COLORS['BOLD']}║{self.COLORS['RESET']}", end='')
            
            for col_idx in range(self.map_size):
                cell = grid[row_idx][col_idx]
                if not self.colors_enabled:
                    print(cell, end='')
                elif cell == '@':
                    print(f"{self.COLORS['GREEN']}{cell}{self.COLORS['RESET']}", end='')
                elif cell == 'E':
                    print(f"{self.COLORS['RED']}{cell}{self.COLORS['RESET']}", end='')
                elif cell == 'e':
                    print(f"{self.COLORS['YELLOW']}{cell}{self.COLORS['RESET']}", end='')
                elif cell == 'x':
                    print(f"{self.COLORS['DIM']}{cell}{self.COLORS['RESET']}", end='')
                elif cell == 'A':
                    print(f"{self.COLORS['BLUE']}{cell}{self.COLORS['RESET']}", end='')
                else:
                    print(f"{self.COLORS['DIM']}.{self.COLORS['RESET']}", end='')
            
            print(f"{self.COLORS['BOLD']}║{self.COLORS['RESET']}")
        
        print(f"{self.COLORS['BOLD']}╚{'═' * self.map_size}╝{self.COLORS['RESET']}")
        
        # Stats
        enemies = [p for p in players if p['is_enemy']]
        allies = [p for p in players if not p['is_enemy'] and not p['is_local']]
        closest_enemy = min(enemies, key=lambda p: p['distance']) if enemies else None
        
        print(f"\n{self.COLORS['BOLD']}Stats:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['RED']}Enemies:{self.COLORS['RESET']} {len(enemies)}")
        print(f"  {self.COLORS['BLUE']}Allies:{self.COLORS['RESET']} {len(allies)}")
        if closest_enemy and self.show_distances:
            print(f"  {self.COLORS['YELLOW']}Closest Enemy:{self.COLORS['RESET']} {closest_enemy['distance']:.1f} units")
        
        # Player list
        if self.show_player_list and players:
            print(f"\n{self.COLORS['BOLD']}Players:{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'Type':6} {'HP':6} {'Dist':8} {'Weapon':8} {'Health Bar'}{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'-'*40}{self.COLORS['RESET']}")
            
            for player in players[:self.max_players_in_list]:
                if player['is_local']:
                    continue
                
                label = f"{self.COLORS['RED']}ENEMY{self.COLORS['RESET']}" if player['is_enemy'] else f"{self.COLORS['BLUE']}ALLY{self.COLORS['RESET']}"
                health_bar = self.draw_health_bar(player['health'])
                dist_display = f"{player['distance']:7.1f}" if self.show_distances else "---"
                weapon_display = player['weapon'] if self.show_weapons else "?"
                print(f"{label:12} {player['health']:3}%  {dist_display}  {weapon_display:8}  {health_bar}")
        
        # Direction
        if self.show_direction and local_angles:
            yaw = local_angles[0]
            direction = "NORTH" if -45 < yaw <= 45 else \
                       "EAST" if 45 < yaw <= 135 else \
                       "SOUTH" if 135 < yaw <= 225 or yaw < -135 else \
                       "WEST"
            print(f"\n{self.COLORS['BOLD']}Facing:{self.COLORS['RESET']} {direction} ({yaw:.1f}°)")
        
        # Legend
        print(f"\n{self.COLORS['BOLD']}Legend:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['GREEN']}@{self.COLORS['RESET']} = You")
        print(f"  {self.COLORS['RED']}E{self.COLORS['RESET']} = Enemy (HP > 70%)")
        print(f"  {self.COLORS['YELLOW']}e{self.COLORS['RESET']} = Enemy (HP 30-70%)")
        print(f"  {self.COLORS['DIM']}x{self.COLORS['RESET']} = Enemy (HP < 30%)")
        print(f"  {self.COLORS['BLUE']}A{self.COLORS['RESET']} = Ally")
        print(f"  {self.COLORS['DIM']}.{self.COLORS['RESET']} = Empty")
        
        if enemies:
            self.log("PLAYERS", f"Found {len(enemies)} enemies")
    
    def run(self):
        """Main radar loop"""
        print("CS2 Terminal Radar - Educational Tool")
        print("=" * 60)
        print("⚠️  This is for EDUCATIONAL purposes ONLY")
        print("⚠️  NEVER use in online matches")
        print("⚠️  Run CS2 with: -insecure -novid -nojoy")
        print("=" * 60)
        print(f"\n📁 Config: {self.config.config_file}")
        print(f"📁 Offsets: {self.config.offsets_file}")
        if self.log_file:
            print(f"📝 Logging to: {self.log_file}")
        
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            return
        
        if not self.connect():
            print("❌ Failed to connect to CS2")
            return
        
        print("✅ Connected to CS2!")
        print("Starting radar (press Ctrl+C to stop)...\n")
        time.sleep(1)
        
        try:
            while True:
                local_info = self.get_local_player()
                if not local_info:
                    print("❌ Lost local player")
                    time.sleep(1)
                    continue
                
                players = self.get_players()
                self.render_radar(players, local_info)
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.log("ERROR", f"Runtime error: {e}")
        finally:
            if self.pm:
                self.pm.close_process()
            self.log("INFO", "Clean exit")
            print("✅ Clean exit")

if __name__ == "__main__":
    # Check for required libraries
    try:
        import pymem
        import requests
    except ImportError as e:
        print(f"❌ Missing required library: {e}")
        print("Install with: pip install pymem requests")
        sys.exit(1)
    
    # Run with config
    config = ConfigManager()
    radar = TerminalRadar(config)
    radar.run()
