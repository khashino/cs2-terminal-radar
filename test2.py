"""
CS2 Terminal Radar - FINAL VERSION
Loads offsets from JSON files every time it runs
"""

import pymem
import pymem.process
import math
import time
import os
import sys
import json
import ctypes
from ctypes import wintypes
import psutil
import requests
from pathlib import Path

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

class ConfigManager:
    """Manages loading offsets from JSON files"""
    
    def __init__(self):
        self.offsets = {}
        self.client_dll = {}
        self.load_offsets()
    
    def load_offsets(self):
        """Load offsets from JSON files or download from GitHub"""
        print("🔄 Loading offsets...")
        
        # Try to load from local files first
        offsets_file = Path("offsets.json")
        client_dll_file = Path("client_dll.json")
        
        # If local files don't exist or are old, download fresh
        try:
            # Download offsets.json
            print("   Downloading offsets.json...")
            response = requests.get(
                "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json",
                timeout=5
            )
            self.offsets = response.json()
            
            # Download client_dll.json
            print("   Downloading client_dll.json...")
            response = requests.get(
                "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json",
                timeout=5
            )
            self.client_dll = response.json()
            
            # Save locally for next time
            with open("offsets.json", "w") as f:
                json.dump(self.offsets, f, indent=2)
            with open("client_dll.json", "w") as f:
                json.dump(self.client_dll, f, indent=2)
            
            print("✅ Offsets downloaded and saved locally")
            
        except Exception as e:
            print(f"⚠️ Could not download offsets: {e}")
            print("   Trying to load from local files...")
            
            try:
                with open("offsets.json", "r") as f:
                    self.offsets = json.load(f)
                with open("client_dll.json", "r") as f:
                    self.client_dll = json.load(f)
                print("✅ Offsets loaded from local files")
            except Exception as e2:
                print(f"❌ Failed to load offsets: {e2}")
                print("   Using hardcoded fallback offsets")
                self._use_fallback_offsets()
    
    def _use_fallback_offsets(self):
        """Fallback offsets if JSON loading fails"""
        self.offsets = {
            "client.dll": {
                "dwEntityList": 0x254FE70,
                "dwLocalPlayerController": 0x237FB70,
                "dwLocalPlayerPawn": 0x23A5238,
                "dwViewAngles": 0x23BAE18,
                "dwViewMatrix": 0x23AA340
            }
        }
        self.client_dll = {
            "client.dll": {
                "classes": {
                    "CCSPlayerController": {
                        "fields": {"m_hPlayerPawn": 0x914}
                    },
                    "C_BaseEntity": {
                        "fields": {
                            "m_iHealth": 0x34C,
                            "m_iTeamNum": 0x3E7
                        }
                    },
                    "C_BasePlayerPawn": {
                        "fields": {"m_vOldOrigin": 0x13B8}
                    }
                }
            }
        }
    
    def get_base_offset(self, key):
        """Get offset from offsets.json"""
        try:
            return self.offsets["client.dll"][key]
        except:
            return None
    
    def get_class_offset(self, class_name, field_name):
        """Get field offset from client_dll.json"""
        try:
            return self.client_dll["client.dll"]["classes"][class_name]["fields"][field_name]
        except:
            return None

class TerminalRadar:
    def __init__(self):
        self.map_size = 40
        self.update_interval = 0.2
        self.radius = self.map_size // 2
        self.scale = 20
        
        # Load config
        self.config = ConfigManager()
        
        # Get all offsets from config
        self.dwEntityList = self.config.get_base_offset("dwEntityList")
        self.dwLocalPlayerController = self.config.get_base_offset("dwLocalPlayerController")
        self.dwLocalPlayerPawn = self.config.get_base_offset("dwLocalPlayerPawn")
        self.dwViewAngles = self.config.get_base_offset("dwViewAngles")
        self.dwViewMatrix = self.config.get_base_offset("dwViewMatrix")
        
        self.m_hPlayerPawn = self.config.get_class_offset("CCSPlayerController", "m_hPlayerPawn")
        self.m_iHealth = self.config.get_class_offset("C_BaseEntity", "m_iHealth")
        self.m_iTeamNum = self.config.get_class_offset("C_BaseEntity", "m_iTeamNum")
        self.m_vOldOrigin = self.config.get_class_offset("C_BasePlayerPawn", "m_vOldOrigin")
        
        # Validate offsets
        if None in [self.dwEntityList, self.dwLocalPlayerController, self.dwLocalPlayerPawn,
                    self.dwViewAngles, self.m_hPlayerPawn, self.m_iHealth, self.m_iTeamNum, self.m_vOldOrigin]:
            print("❌ Some offsets failed to load!")
            print(f"   dwEntityList: {hex(self.dwEntityList) if self.dwEntityList else 'MISSING'}")
            print(f"   dwLocalPlayerController: {hex(self.dwLocalPlayerController) if self.dwLocalPlayerController else 'MISSING'}")
            print(f"   m_hPlayerPawn: {hex(self.m_hPlayerPawn) if self.m_hPlayerPawn else 'MISSING'}")
            print(f"   m_iHealth: {hex(self.m_iHealth) if self.m_iHealth else 'MISSING'}")
            print(f"   m_iTeamNum: {hex(self.m_iTeamNum) if self.m_iTeamNum else 'MISSING'}")
            print(f"   m_vOldOrigin: {hex(self.m_vOldOrigin) if self.m_vOldOrigin else 'MISSING'}")
            sys.exit(1)
        
        self.pm = None
        self.client_base = None
        self.is_connected = False
        
        self.COLORS = {
            'RESET': '\033[0m',
            'RED': '\033[91m',
            'GREEN': '\033[92m',
            'YELLOW': '\033[93m',
            'BLUE': '\033[94m',
            'BOLD': '\033[1m',
            'DIM': '\033[2m',
            'BG_RED': '\033[41m',
            'BG_GREEN': '\033[42m',
            'BG_YELLOW': '\033[43m',
        }
    
    def connect(self):
        try:
            # Find CS2
            pid = None
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == 'cs2.exe':
                    pid = proc.info['pid']
                    break
            
            if not pid:
                print("❌ CS2 process not found")
                return False
            
            # Open process with read permissions
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, 
                False, 
                pid
            )
            
            if not handle:
                print("❌ Failed to open process. Run as Administrator!")
                return False
            
            self.pm = pymem.Pymem()
            self.pm.process_handle = handle
            self.pm.process_id = pid
            
            # Get client.dll base
            client_module = pymem.process.module_from_name(
                self.pm.process_handle, "client.dll"
            )
            if not client_module:
                print("❌ client.dll not found")
                return False
            
            self.client_base = client_module.lpBaseOfDll
            self.is_connected = True
            
            print(f"✅ Connected to CS2 (PID: {pid})")
            print(f"   Client.dll base: 0x{self.client_base:X}")
            print(f"\n📊 OFFSETS LOADED:")
            print(f"   dwEntityList: 0x{self.dwEntityList:X}")
            print(f"   dwLocalPlayerController: 0x{self.dwLocalPlayerController:X}")
            print(f"   dwLocalPlayerPawn: 0x{self.dwLocalPlayerPawn:X}")
            print(f"   dwViewAngles: 0x{self.dwViewAngles:X}")
            print(f"   m_hPlayerPawn: 0x{self.m_hPlayerPawn:X}")
            print(f"   m_iHealth: 0x{self.m_iHealth:X}")
            print(f"   m_iTeamNum: 0x{self.m_iTeamNum:X}")
            print(f"   m_vOldOrigin: 0x{self.m_vOldOrigin:X}")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def read_int(self, addr):
        try:
            return self.pm.read_int(addr)
        except:
            return 0
    
    def read_longlong(self, addr):
        try:
            return self.pm.read_longlong(addr)
        except:
            return 0
    
    def read_float(self, addr):
        try:
            return self.pm.read_float(addr)
        except:
            return 0.0
    
    def read_vector(self, addr):
        try:
            x = self.read_float(addr)
            y = self.read_float(addr + 4)
            z = self.read_float(addr + 8)
            return (x, y, z)
        except:
            return None
    
    def get_view_angles(self):
        try:
            angles_addr = self.client_base + self.dwViewAngles
            yaw = self.read_float(angles_addr)
            pitch = self.read_float(angles_addr + 4)
            return (yaw, pitch)
        except:
            return None
    
    def resolve_pawn_handle(self, pawn_handle):
        """Resolve pawn handle to pawn address using the entity list"""
        try:
            entity_list = self.client_base + self.dwEntityList
            pawn_entry = self.read_longlong(
                entity_list + 0x10 + 
                8 * ((pawn_handle & 0x7FFF) >> 9) + 
                0x70 * (pawn_handle & 0x1FF)
            )
            if not pawn_entry:
                return None
            pawn = self.read_longlong(
                pawn_entry + 0x78 * (pawn_handle & 0x1FF)
            )
            return pawn
        except:
            return None
    
    def get_local_player(self):
        """Get local player info using controller -> pawn resolution"""
        try:
            # Read local player controller
            local_controller = self.read_longlong(
                self.client_base + self.dwLocalPlayerController
            )
            if not local_controller:
                return None
            
            # Get pawn handle from controller
            pawn_handle = self.read_int(local_controller + self.m_hPlayerPawn)
            if not pawn_handle:
                return None
            
            # Resolve pawn
            local_pawn = self.resolve_pawn_handle(pawn_handle)
            if not local_pawn:
                return None
            
            # Read pawn data
            health = self.read_int(local_pawn + self.m_iHealth)
            if health <= 0 or health > 100:
                return None
            
            team = self.read_int(local_pawn + self.m_iTeamNum)
            pos = self.read_vector(local_pawn + self.m_vOldOrigin)
            
            if not pos:
                return None
            
            return {
                'pawn': local_pawn,
                'controller': local_controller,
                'health': health,
                'team': team,
                'position': pos
            }
        except:
            return None
    
    def get_players(self):
        """Get all players using controller -> pawn resolution"""
        players = []
        local = self.get_local_player()
        
        if not local:
            return players
        
        entity_list = self.client_base + self.dwEntityList
        
        for i in range(1, 65):
            try:
                # Read controller from entity list
                controller = self.read_longlong(entity_list + i * 0x10)
                if not controller:
                    continue
                
                # Skip local player controller
                if controller == local['controller']:
                    continue
                
                # Get pawn handle from controller
                pawn_handle = self.read_int(controller + self.m_hPlayerPawn)
                if not pawn_handle:
                    continue
                
                # Resolve pawn
                pawn = self.resolve_pawn_handle(pawn_handle)
                if not pawn:
                    continue
                
                # Read pawn data
                health = self.read_int(pawn + self.m_iHealth)
                if health <= 0 or health > 100:
                    continue
                
                team = self.read_int(pawn + self.m_iTeamNum)
                pos = self.read_vector(pawn + self.m_vOldOrigin)
                
                if not pos:
                    continue
                
                dx = pos[0] - local['position'][0]
                dy = pos[1] - local['position'][1]
                distance = math.sqrt(dx*dx + dy*dy)
                
                players.append({
                    'health': health,
                    'team': team,
                    'position': pos,
                    'distance': distance,
                    'is_enemy': team != local['team']
                })
                
            except:
                continue
        
        return players
    
    def world_to_radar(self, world_pos, local_pos, local_angles):
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
    
    def draw_health_bar(self, health, width=5):
        filled = int((health / 100) * width)
        empty = width - filled
        
        if health > 70:
            color = self.COLORS['BG_GREEN']
        elif health > 40:
            color = self.COLORS['BG_YELLOW']
        else:
            color = self.COLORS['BG_RED']
        
        return f"{color}{'█' * filled}{self.COLORS['RESET']}{'░' * empty}"
    
    def render(self, players, local):
        local_angles = self.get_view_angles()
        grid = [[' ' for _ in range(self.map_size)] for _ in range(self.map_size)]
        
        for player in players:
            row, col = self.world_to_radar(player['position'], local['position'], local_angles)
            
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
        
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}CS2 Radar{self.COLORS['RESET']} - {time.strftime('%H:%M:%S')}")
        print(f"{self.COLORS['DIM']}Players: {len(players)} | Offsets loaded from JSON{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        
        print(f"{self.COLORS['BOLD']}╔{'═' * self.map_size}╗{self.COLORS['RESET']}")
        
        for row_idx in range(self.map_size):
            print(f"{self.COLORS['BOLD']}║{self.COLORS['RESET']}", end='')
            
            for col_idx in range(self.map_size):
                cell = grid[row_idx][col_idx]
                if cell == '@':
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
        
        enemies = [p for p in players if p['is_enemy']]
        allies = [p for p in players if not p['is_enemy']]
        closest_enemy = min(enemies, key=lambda p: p['distance']) if enemies else None
        
        print(f"\n{self.COLORS['BOLD']}Stats:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['RED']}Enemies:{self.COLORS['RESET']} {len(enemies)}")
        print(f"  {self.COLORS['BLUE']}Allies:{self.COLORS['RESET']} {len(allies)}")
        if closest_enemy:
            print(f"  {self.COLORS['YELLOW']}Closest Enemy:{self.COLORS['RESET']} {closest_enemy['distance']:.1f} units")
        
        if players:
            print(f"\n{self.COLORS['BOLD']}Players:{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'Type':6} {'HP':6} {'Dist':8} {'Health Bar'}{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'-'*35}{self.COLORS['RESET']}")
            
            for player in players[:15]:
                label = f"{self.COLORS['RED']}ENEMY{self.COLORS['RESET']}" if player['is_enemy'] else f"{self.COLORS['BLUE']}ALLY{self.COLORS['RESET']}"
                health_bar = self.draw_health_bar(player['health'])
                print(f"{label:12} {player['health']:3}%  {player['distance']:7.1f}  {health_bar}")
        
        if local_angles:
            yaw = local_angles[0]
            direction = "NORTH" if -45 < yaw <= 45 else \
                       "EAST" if 45 < yaw <= 135 else \
                       "SOUTH" if 135 < yaw <= 225 or yaw < -135 else \
                       "WEST"
            print(f"\n{self.COLORS['BOLD']}Facing:{self.COLORS['RESET']} {direction} ({yaw:.1f}°)")
        
        print(f"\n{self.COLORS['BOLD']}Legend:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['GREEN']}@{self.COLORS['RESET']} = You")
        print(f"  {self.COLORS['RED']}E{self.COLORS['RESET']} = Enemy (HP > 70%)")
        print(f"  {self.COLORS['YELLOW']}e{self.COLORS['RESET']} = Enemy (HP 30-70%)")
        print(f"  {self.COLORS['DIM']}x{self.COLORS['RESET']} = Enemy (HP < 30%)")
        print(f"  {self.COLORS['BLUE']}A{self.COLORS['RESET']} = Ally")
        print(f"  {self.COLORS['DIM']}.{self.COLORS['RESET']} = Empty")
    
    def run(self):
        print("=" * 60)
        print("CS2 Terminal Radar - Auto-Loading Offsets")
        print("=" * 60)
        print("⚠️  Educational purposes only")
        print("⚠️  Run this as Administrator")
        print("=" * 60)
        
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
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
                    print("\r❌ Waiting for player...", end="")
                    time.sleep(1)
                    continue
                
                players = self.get_players()
                self.render(players, local)
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            if self.pm and hasattr(self.pm, 'process_handle'):
                ctypes.windll.kernel32.CloseHandle(self.pm.process_handle)
            print("✅ Clean exit")

if __name__ == "__main__":
    try:
        import pymem
        import psutil
        import requests
    except ImportError as e:
        print(f"❌ Missing library: {e}")
        print("Install with: pip install pymem psutil requests")
        sys.exit(1)
    
    radar = TerminalRadar()
    radar.run()
