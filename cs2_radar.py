"""
CS2 Terminal Radar - Educational Tool
Displays a top-down map in the console with advanced features.
SAFER than overlay because it uses the terminal and looks like a dev tool.
"""

import pymem
import pymem.process
import math
import time
import os
import sys
import json
import datetime
from typing import Optional, Tuple, List, Dict

# ===== OFFSETS FROM PROVIDED offsets.py =====
# These are updated as of 2026-07-21 (Build 14172)
# To update: Replace the values below with the latest from:
# https://github.com/sezzyaep/CS2-OFFSETS/blob/main/offsets.py

class ClientDll:
    dwCSGOInput = 0x23BA790
    dwEntityList = 0x254FE70
    dwGameEntitySystem = 0x254FE70
    dwGameEntitySystem_highestEntityIndex = 0x2090
    dwGameRules = 0x1A525C0
    dwGlobalVars = 0x2090D60
    dwGlowManager = 0x23A1708
    dwLocalPlayerController = 0x237FB70
    dwLocalPlayerPawn = 0x23A5238
    dwPlantedC4 = 0x236F658
    dwPrediction = 0x23A5140
    dwSensitivity = 0x23A2228
    dwSensitivity_sensitivity = 0x58
    dwViewAngles = 0x23BAE18
    dwViewMatrix = 0x23AA340
    dwViewRender = 0x23AA398
    dwWeaponC4 = 0x231DB10

class Engine2Dll:
    dwBuildNumber = 0x60F594
    dwNetworkGameClient = 0x90D4B0
    dwNetworkGameClient_clientTickCount = 0x378
    dwNetworkGameClient_deltaTick = 0x24C
    dwNetworkGameClient_isBackgroundMap = 0x2C141F
    dwNetworkGameClient_localPlayer = 0xF8
    dwNetworkGameClient_maxClients = 0x240
    dwNetworkGameClient_serverTickCount = 0x24C
    dwNetworkGameClient_signOnState = 0x230
    dwWindowHeight = 0x9118D4
    dwWindowWidth = 0x9118D0

# Netvars (from client_dll.json - these are common ones you'd need)
# For a complete list, check: https://github.com/sezzyaep/CS2-OFFSETS/blob/main/client_dll.json
class Netvars:
    m_iHealth = 0x344
    m_iTeamNum = 0x3E3
    m_vOldOrigin = 0x1324
    m_hPlayerPawn = 0x814
    m_iShotsFired = 0x3A0
    m_angEyeAngles = 0x1618
    m_flFlashMaxAlpha = 0x14B4
    m_bIsScoped = 0x14E4
    m_iWeapon = 0x12A8
    m_pWeaponServices = 0x1270
    m_hActiveWeapon = 0x1838

# ===== END OF OFFSETS =====

class TerminalRadar:
    def __init__(self, map_size: int = 40, update_interval: float = 0.2):
        """Initialize radar with configurable size and update rate"""
        self.map_size = map_size
        self.update_interval = update_interval
        self.radius = map_size // 2
        self.scale = 20  # Adjust for zoom (lower = zoomed in, higher = zoomed out)
        
        # Store previous state for health bars
        self.previous_players = {}
        
        # Initialize rotation angle (0 = north up)
        self.rotation_angle = 0  # In degrees
        
        # Logging setup
        self.log_file = f"radar_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.log_enabled = True
        
        self.pm = None
        self.client_base = None
        self.engine_base = None
        self.is_connected = False
        
        # Colors for terminal output
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
    
    def connect(self) -> bool:
        """Connect to CS2 process and get module bases"""
        try:
            self.pm = pymem.Pymem("cs2.exe")
            
            # Get client.dll base
            client_module = pymem.process.module_from_name(
                self.pm.process_handle, "client.dll"
            )
            if not client_module:
                return False
            self.client_base = client_module.lpBaseOfDll
            
            # Get engine2.dll base
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
        """Write to log file if enabled"""
        if not self.log_enabled:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, 'a') as f:
                f.write(f"[{timestamp}] [{level}] {message}\n")
        except:
            pass
    
    def read_int(self, address: int) -> int:
        """Safe int reading"""
        try:
            return self.pm.read_int(address)
        except:
            return 0
    
    def read_longlong(self, address: int) -> int:
        """Safe long long reading"""
        try:
            return self.pm.read_longlong(address)
        except:
            return 0
    
    def read_float(self, address: int) -> float:
        """Safe float reading"""
        try:
            return self.pm.read_float(address)
        except:
            return 0.0
    
    def read_vector(self, address: int) -> Optional[Tuple[float, float, float]]:
        """Read 3D position"""
        try:
            x = self.read_float(address)
            y = self.read_float(address + 0x4)
            z = self.read_float(address + 0x8)
            return (x, y, z)
        except:
            return None
    
    def get_view_angles(self) -> Optional[Tuple[float, float]]:
        """Get player view angles (yaw, pitch)"""
        try:
            angles_addr = self.client_base + ClientDll.dwViewAngles
            yaw = self.read_float(angles_addr)
            pitch = self.read_float(angles_addr + 0x4)
            return (yaw, pitch)
        except:
            return None
    
    def get_local_player(self) -> Optional[Tuple[int, Tuple[float, float, float], Tuple[float, float]]]:
        """Get local player info: team, position, view angles"""
        try:
            local_pawn = self.read_longlong(
                self.client_base + ClientDll.dwLocalPlayerPawn
            )
            if not local_pawn:
                return None
            
            team = self.read_int(local_pawn + Netvars.m_iTeamNum)
            pos = self.read_vector(local_pawn + Netvars.m_vOldOrigin)
            angles = self.get_view_angles()
            
            if not pos:
                return None
            
            return (team, pos, angles)
        except Exception as e:
            self.log("ERROR", f"get_local_player failed: {e}")
            return None
    
    def get_active_weapon(self, pawn: int) -> str:
        """Get the name of the player's active weapon"""
        try:
            # Get weapon services
            weapon_services = self.read_longlong(pawn + Netvars.m_pWeaponServices)
            if not weapon_services:
                return "?"
            
            # Get active weapon handle
            active_weapon_handle = self.read_int(weapon_services + Netvars.m_hActiveWeapon)
            if not active_weapon_handle:
                return "?"
            
            # Resolve weapon entity (simplified - this is a placeholder)
            # In a full implementation, you'd resolve the handle to get weapon data
            # For now, return a placeholder based on player state
            return self.get_weapon_from_state(pawn)
        except:
            return "?"
    
    def get_weapon_from_state(self, pawn: int) -> str:
        """Placeholder weapon detection - in practice you'd resolve the weapon entity"""
        # This is a simplified version - real weapon detection requires more work
        try:
            # Check if scoped (likely sniper)
            is_scoped = self.read_int(pawn + Netvars.m_bIsScoped)
            if is_scoped:
                return "SNIPER"
            
            # Check shots fired (if high, likely automatic)
            shots = self.read_int(pawn + Netvars.m_iShotsFired)
            if shots > 5:
                return "AUTO"
            
            return "PISTOL"
        except:
            return "?"
    
    def get_players(self) -> List[Dict]:
        """Get all players with positions and metadata"""
        players = []
        local_info = self.get_local_player()
        
        if not local_info:
            return players
        
        local_team, local_pos, local_angles = local_info
        entity_list = self.client_base + ClientDll.dwEntityList
        
        for i in range(1, 65):
            try:
                # Complex entity resolution (CS2 specific)
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
                    controller + Netvars.m_hPlayerPawn
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
                
                # Read player data
                health = self.read_int(pawn + Netvars.m_iHealth)
                if health <= 0 or health > 100:
                    continue
                
                team = self.read_int(pawn + Netvars.m_iTeamNum)
                pos = self.read_vector(pawn + Netvars.m_vOldOrigin)
                
                if not pos:
                    continue
                
                # Get weapon
                weapon = self.get_active_weapon(pawn)
                
                # Calculate distance
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
                
            except Exception as e:
                continue
        
        # Sort by distance (closest first)
        players.sort(key=lambda p: p['distance'])
        self.log("INFO", f"Found {len(players)} players")
        return players
    
    def world_to_radar(self, world_pos: Tuple[float, float, float], 
                      local_pos: Tuple[float, float, float],
                      local_angles: Tuple[float, float]) -> Tuple[int, int]:
        """
        Convert world position to radar grid coordinates with rotation
        Returns (row, col) in the grid
        """
        # Calculate relative position (ignore Z/height)
        dx = world_pos[0] - local_pos[0]
        dy = world_pos[1] - local_pos[1]
        
        # Apply rotation based on view angles
        if local_angles:
            yaw_rad = math.radians(local_angles[0])
            cos_yaw = math.cos(yaw_rad)
            sin_yaw = math.sin(yaw_rad)
            
            # Rotate coordinates
            rotated_dx = dx * cos_yaw - dy * sin_yaw
            rotated_dy = dx * sin_yaw + dy * cos_yaw
            dx, dy = rotated_dx, rotated_dy
        
        # Scale to radar size
        grid_x = int(dx / self.scale) + self.radius
        grid_y = int(dy / self.scale) + self.radius
        
        # Clamp to grid
        grid_x = max(0, min(self.map_size - 1, grid_x))
        grid_y = max(0, min(self.map_size - 1, grid_y))
        
        return (grid_y, grid_x)  # Return (row, col)
    
    def draw_health_bar(self, health: int, width: int = 5) -> str:
        """Create a visual health bar string"""
        filled = int((health / 100) * width)
        empty = width - filled
        
        if health > 70:
            color = self.COLORS['BG_GREEN']
        elif health > 40:
            color = self.COLORS['BG_YELLOW']
        else:
            color = self.COLORS['BG_RED']
        
        return f"{color}{'█' * filled}{self.COLORS['RESET']}{'░' * empty}"
    
    def render_radar(self, players: List[Dict], local_info: Tuple[int, Tuple[float, float, float], Tuple[float, float]]):
        """Render the radar map to terminal with all features"""
        local_team, local_pos, local_angles = local_info
        
        # Create empty grid
        grid = [[' ' for _ in range(self.map_size)] for _ in range(self.map_size)]
        player_data = {}  # Store player info for labels
        
        # Place players on grid
        for player in players:
            if player['is_local']:
                continue
            
            row, col = self.world_to_radar(player['position'], local_pos, local_angles)
            
            # Store player data for labels
            player_data[(row, col)] = player
            
            # Choose symbol based on team and health
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
        
        # Place local player (center)
        grid[self.radius][self.radius] = '@'
        
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print header
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}CS2 Radar{self.COLORS['RESET']} - Updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"{self.COLORS['DIM']}Build: 14172 | Press Ctrl+C to exit{self.COLORS['RESET']}")
        print(f"{self.COLORS['BOLD']}{'='*60}{self.COLORS['RESET']}")
        
        # Print map with top border
        print(f"{self.COLORS['BOLD']}╔{'═' * self.map_size}╗{self.COLORS['RESET']}")
        
        # Print map rows
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
        
        # Print bottom border
        print(f"{self.COLORS['BOLD']}╚{'═' * self.map_size}╝{self.COLORS['RESET']}")
        
        # Print stats
        enemies = [p for p in players if p['is_enemy']]
        allies = [p for p in players if not p['is_enemy'] and not p['is_local']]
        closest_enemy = min(enemies, key=lambda p: p['distance']) if enemies else None
        
        print(f"\n{self.COLORS['BOLD']}Stats:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['RED']}Enemies:{self.COLORS['RESET']} {len(enemies)}")
        print(f"  {self.COLORS['BLUE']}Allies:{self.COLORS['RESET']} {len(allies)}")
        if closest_enemy:
            print(f"  {self.COLORS['YELLOW']}Closest Enemy:{self.COLORS['RESET']} {closest_enemy['distance']:.1f} units")
        
        # Print player list with details
        if players:
            print(f"\n{self.COLORS['BOLD']}Players:{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'Type':6} {'HP':6} {'Dist':8} {'Weapon':8} {'Health Bar'}{self.COLORS['RESET']}")
            print(f"{self.COLORS['DIM']}{'-'*40}{self.COLORS['RESET']}")
            
            for i, player in enumerate(players[:15]):  # Show top 15
                if player['is_local']:
                    continue
                
                label = f"{self.COLORS['RED']}ENEMY{self.COLORS['RESET']}" if player['is_enemy'] else f"{self.COLORS['BLUE']}ALLY{self.COLORS['RESET']}"
                health_bar = self.draw_health_bar(player['health'])
                print(f"{label:12} {player['health']:3}%  {player['distance']:7.1f}  {player['weapon']:8}  {health_bar}")
        
        # Print direction indicator
        if local_angles:
            yaw = local_angles[0]
            direction = "NORTH" if -45 < yaw <= 45 else \
                       "EAST" if 45 < yaw <= 135 else \
                       "SOUTH" if 135 < yaw <= 225 or yaw < -135 else \
                       "WEST"
            print(f"\n{self.COLORS['BOLD']}Facing:{self.COLORS['RESET']} {direction} ({yaw:.1f}°)")
        
        # Print legend
        print(f"\n{self.COLORS['BOLD']}Legend:{self.COLORS['RESET']}")
        print(f"  {self.COLORS['GREEN']}@{self.COLORS['RESET']} = You")
        print(f"  {self.COLORS['RED']}E{self.COLORS['RESET']} = Enemy (HP > 70%)")
        print(f"  {self.COLORS['YELLOW']}e{self.COLORS['RESET']} = Enemy (HP 30-70%)")
        print(f"  {self.COLORS['DIM']}x{self.COLORS['RESET']} = Enemy (HP < 30%)")
        print(f"  {self.COLORS['BLUE']}A{self.COLORS['RESET']} = Ally")
        print(f"  {self.COLORS['DIM']}.{self.COLORS['RESET']} = Empty")
        
        # Log if enemies detected
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
        print(f"\nLogging to: {self.log_file}")
        
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
                # Get local player
                local_info = self.get_local_player()
                if not local_info:
                    print("❌ Lost local player")
                    time.sleep(1)
                    continue
                
                # Get all players
                players = self.get_players()
                
                # Render radar
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
            print(f"Log saved to: {self.log_file}")

# ===== OFFSET UPDATE CHECK =====
def check_offsets():
    """Check if offsets need updating based on the provided offsets.py"""
    print("Current Offsets (from 2026-07-21, Build 14172):")
    print(f"  dwLocalPlayerPawn: 0x{ClientDll.dwLocalPlayerPawn:X}")
    print(f"  dwEntityList: 0x{ClientDll.dwEntityList:X}")
    print(f"  dwViewAngles: 0x{ClientDll.dwViewAngles:X}")
    print(f"  dwViewMatrix: 0x{ClientDll.dwViewMatrix:X}")
    print()
    print("To update offsets:")
    print("1. Visit: https://github.com/sezzyaep/CS2-OFFSETS/blob/main/offsets.py")
    print("2. Copy the new values")
    print("3. Update the class definitions in this file")
    print("4. Also check client_dll.json for netvars like m_iHealth, m_iTeamNum, etc.")

if __name__ == "__main__":
    # Check for pymem
    try:
        import pymem
    except ImportError:
        print("Installing required library: pymem")
        os.system("pip install pymem")
        import pymem
    
    # Show offset info
    check_offsets()
    print("\n" + "="*60 + "\n")
    
    # Run radar with all features
    radar = TerminalRadar(
        map_size=40,       # Radar size (larger = more detail)
        update_interval=0.2 # Update speed (lower = faster but more CPU)
    )
    
    # You can customize these settings directly:
    # radar.scale = 15     # Zoom in more
    # radar.log_enabled = False  # Disable logging
    
    radar.run()
