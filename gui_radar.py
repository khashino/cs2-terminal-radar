"""Desktop GUI renderer for CS2 Terminal Radar."""

import math
import random
import time
import tkinter as tk
from tkinter import messagebox

from cs2_radar import TerminalRadar


class GuiRadar(TerminalRadar):
    """A polished Tkinter view backed by the existing read-only radar."""

    BG = "#070b14"
    PANEL = "#0d1422"
    PANEL_ALT = "#111b2d"
    BORDER = "#1d2a40"
    TEXT = "#e7eefc"
    MUTED = "#7f8da8"
    GREEN = "#48e0a4"
    RED = "#ff5c73"
    YELLOW = "#ffc857"
    BLUE = "#55a7ff"
    GRID = "#20304a"

    def __init__(self, config, demo=False):
        super().__init__(config, load_offsets=not demo)
        self.gui_config = config.get("gui", {})
        self.demo = demo
        self.demo_started = time.monotonic()
        self.demo_contacts = self._make_demo_contacts() if demo else []
        self.root = None
        self.canvas = None
        self.contact_canvas = None
        self.running = False

    def _make_demo_contacts(self):
        """Create stable random contacts that can be animated each frame."""
        generator = random.Random()
        contacts = []
        for index in range(generator.randint(8, 13)):
            contacts.append(
                {
                    "angle": generator.uniform(0, math.tau),
                    "radius": generator.uniform(0.12, 0.92),
                    "speed": generator.uniform(-0.28, 0.28),
                    "pulse": generator.uniform(0, math.tau),
                    "health": generator.randint(18, 100),
                    "is_enemy": index < 7 or generator.random() < 0.55,
                }
            )
        return contacts

    def _demo_snapshot(self):
        """Return animated data shaped like a live memory snapshot."""
        elapsed = time.monotonic() - self.demo_started
        world_radius = max(1.0, self.scale * self.radius)
        players = []
        for index, contact in enumerate(self.demo_contacts):
            angle = contact["angle"] + elapsed * contact["speed"]
            distance = world_radius * contact["radius"]
            distance *= 1.0 + 0.035 * math.sin(elapsed + contact["pulse"])
            players.append(
                {
                    "pawn": index + 1,
                    "controller": index + 1,
                    "health": contact["health"],
                    "team": 2 if contact["is_enemy"] else 3,
                    "position": (
                        math.cos(angle) * distance,
                        math.sin(angle) * distance,
                        0.0,
                    ),
                    "distance": distance,
                    "is_enemy": contact["is_enemy"],
                }
            )
        local = {
            "controller": 0,
            "health": 100,
            "team": 3,
            "position": (0.0, 0.0, 0.0),
        }
        yaw = 24.0 * math.sin(elapsed * 0.18)
        return local, (yaw, 0.0), players

    @staticmethod
    def _direction(yaw):
        normalized = yaw % 360
        if normalized < 45 or normalized >= 315:
            return "NORTH"
        if normalized < 135:
            return "EAST"
        if normalized < 225:
            return "SOUTH"
        return "WEST"

    def _stat_card(self, parent, label, color):
        card = tk.Frame(
            parent,
            bg=self.PANEL_ALT,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        value = tk.StringVar(value="--")
        tk.Label(
            card,
            text=label.upper(),
            bg=self.PANEL_ALT,
            fg=self.MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            textvariable=value,
            bg=self.PANEL_ALT,
            fg=color,
            font=("Segoe UI Semibold", 18),
        ).pack(anchor="w")
        return value

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("CS2 Radar")
        width = int(self.gui_config.get("window_width", 1040))
        height = int(self.gui_config.get("window_height", 720))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(820, 580)
        self.root.configure(bg=self.BG)
        self.root.attributes(
            "-topmost", bool(self.gui_config.get("always_on_top", False))
        )
        try:
            opacity = max(
                0.4, min(1.0, float(self.gui_config.get("opacity", 0.97)))
            )
            self.root.attributes("-alpha", opacity)
        except (tk.TclError, ValueError):
            pass
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        header = tk.Frame(self.root, bg=self.BG, padx=24, pady=18)
        header.pack(fill="x")
        title_group = tk.Frame(header, bg=self.BG)
        title_group.pack(side="left")
        tk.Label(
            title_group,
            text="CS2  /  RADAR",
            bg=self.BG,
            fg=self.TEXT,
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        self.status_var = tk.StringVar(value="CONNECTING")
        tk.Label(
            title_group,
            textvariable=self.status_var,
            bg=self.BG,
            fg=self.GREEN,
            font=("Consolas", 9, "bold"),
        ).pack(anchor="w", pady=(3, 0))

        self.clock_var = tk.StringVar()
        tk.Label(
            header,
            textvariable=self.clock_var,
            bg=self.BG,
            fg=self.MUTED,
            font=("Consolas", 11),
        ).pack(side="right")

        body = tk.Frame(self.root, bg=self.BG, padx=24)
        body.pack(fill="both", expand=True, pady=(0, 22))

        radar_panel = tk.Frame(
            body,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        radar_panel.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(
            radar_panel, bg=self.PANEL, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)

        sidebar = tk.Frame(body, bg=self.BG, width=330)
        sidebar.pack(side="right", fill="y", padx=(18, 0))
        sidebar.pack_propagate(False)

        stats = tk.Frame(sidebar, bg=self.BG)
        stats.pack(fill="x")
        self.enemy_var = self._stat_card(stats, "Enemies", self.RED)
        self.ally_var = self._stat_card(stats, "Allies", self.BLUE)

        info = tk.Frame(
            sidebar,
            bg=self.PANEL_ALT,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            padx=16,
            pady=14,
        )
        info.pack(fill="x", pady=(12, 12))
        self.closest_var = tk.StringVar(value="--")
        self.heading_var = tk.StringVar(value="--")
        for label, variable in (
            ("CLOSEST CONTACT", self.closest_var),
            ("HEADING", self.heading_var),
        ):
            tk.Label(
                info,
                text=label,
                bg=self.PANEL_ALT,
                fg=self.MUTED,
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w")
            tk.Label(
                info,
                textvariable=variable,
                bg=self.PANEL_ALT,
                fg=self.TEXT,
                font=("Consolas", 12, "bold"),
            ).pack(anchor="w", pady=(2, 12))

        contacts = tk.Frame(
            sidebar,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        contacts.pack(fill="both", expand=True)
        tk.Label(
            contacts,
            text="LIVE CONTACTS",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=12,
        ).pack(anchor="w")
        self.contact_canvas = tk.Canvas(
            contacts, bg=self.PANEL, highlightthickness=0, bd=0
        )
        self.contact_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tk.Label(
            self.root,
            text="READ-ONLY  /  EDUCATIONAL USE  /  RUN CS2 WITH -INSECURE",
            bg="#09111d",
            fg=self.MUTED,
            font=("Consolas", 8),
            pady=7,
        ).pack(fill="x", side="bottom")

    def _draw_grid(self, cx, cy, radius):
        self.canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            fill="#091321",
            outline=self.BORDER,
            width=2,
        )
        for fraction in (0.25, 0.5, 0.75, 1.0):
            ring = radius * fraction
            self.canvas.create_oval(
                cx - ring,
                cy - ring,
                cx + ring,
                cy + ring,
                outline=self.GRID,
            )
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            self.canvas.create_line(
                cx,
                cy,
                cx + math.sin(radians) * radius,
                cy - math.cos(radians) * radius,
                fill=self.GRID,
            )
        for label, angle in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            radians = math.radians(angle)
            self.canvas.create_text(
                cx + math.sin(radians) * (radius + 15),
                cy - math.cos(radians) * (radius + 15),
                text=label,
                fill=self.MUTED,
                font=("Consolas", 9, "bold"),
            )

    def _draw_radar(self, players, local, angles):
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        cx, cy = width / 2, height / 2
        radius = max(40, min(width, height) / 2 - 30)
        self._draw_grid(cx, cy, radius)

        world_radius = max(1.0, self.scale * self.radius)
        yaw_radians = math.radians(angles[0] if angles else 0.0)
        cos_yaw, sin_yaw = math.cos(yaw_radians), math.sin(yaw_radians)

        for player in sorted(
            players, key=lambda item: item["distance"], reverse=True
        ):
            dx = player["position"][0] - local["position"][0]
            dy = player["position"][1] - local["position"][1]
            forward = dx * cos_yaw + dy * sin_yaw
            right = dx * sin_yaw - dy * cos_yaw
            px = cx + max(-1.0, min(1.0, right / world_radius)) * radius
            py = cy - max(-1.0, min(1.0, forward / world_radius)) * radius
            color = self.RED if player["is_enemy"] else self.BLUE
            marker = 7 if player["is_enemy"] else 6
            self.canvas.create_oval(
                px - marker - 4,
                py - marker - 4,
                px + marker + 4,
                py + marker + 4,
                fill=color,
                outline="",
                stipple="gray50",
            )
            self.canvas.create_oval(
                px - marker,
                py - marker,
                px + marker,
                py + marker,
                fill=color,
                outline="#ffffff",
            )
            self.canvas.create_text(
                px,
                py - 16,
                text=str(player["health"]),
                fill=self.TEXT,
                font=("Consolas", 8, "bold"),
            )

        self.canvas.create_oval(
            cx - 11,
            cy - 11,
            cx + 11,
            cy + 11,
            fill=self.GREEN,
            outline="#d9fff1",
            width=2,
        )
        self.canvas.create_polygon(
            cx,
            cy - 19,
            cx - 5,
            cy - 8,
            cx + 5,
            cy - 8,
            fill=self.GREEN,
            outline="",
        )

    def _draw_contacts(self, players):
        self.contact_canvas.delete("all")
        width = max(1, self.contact_canvas.winfo_width())
        limit = int(self.display.get("max_players_in_list", 15))
        ordered = sorted(
            players, key=lambda item: (not item["is_enemy"], item["distance"])
        )
        for index, player in enumerate(ordered[:limit]):
            y = 8 + index * 38
            color = self.RED if player["is_enemy"] else self.BLUE
            label = "ENEMY" if player["is_enemy"] else "ALLY"
            self.contact_canvas.create_oval(
                5, y + 7, 13, y + 15, fill=color, outline=""
            )
            self.contact_canvas.create_text(
                21,
                y + 11,
                anchor="w",
                text=label,
                fill=self.TEXT,
                font=("Segoe UI", 9, "bold"),
            )
            self.contact_canvas.create_text(
                width - 5,
                y + 11,
                anchor="e",
                text=f"{player['distance']:.0f} u",
                fill=self.MUTED,
                font=("Consolas", 9),
            )
            bar_width = max(40, width - 26)
            self.contact_canvas.create_rectangle(
                21, y + 25, 21 + bar_width, y + 29, fill=self.BORDER, outline=""
            )
            hp_color = (
                self.GREEN
                if player["health"] > 70
                else self.YELLOW
                if player["health"] > 40
                else self.RED
            )
            self.contact_canvas.create_rectangle(
                21,
                y + 25,
                21 + bar_width * player["health"] / 100,
                y + 29,
                fill=hp_color,
                outline="",
            )

    def _show_snapshot(self, local, angles, players, status):
        enemies = [player for player in players if player["is_enemy"]]
        allies = [player for player in players if not player["is_enemy"]]
        closest = (
            min(enemies, key=lambda item: item["distance"]) if enemies else None
        )
        self.status_var.set(status)
        self.enemy_var.set(str(len(enemies)))
        self.ally_var.set(str(len(allies)))
        self.closest_var.set(
            f"{closest['distance']:.1f} units" if closest else "NO CONTACT"
        )
        yaw = angles[0]
        self.heading_var.set(f"{self._direction(yaw)}  /  {yaw:.1f} deg")
        self._draw_radar(players, local, angles)
        self._draw_contacts(players)

    def _update_frame(self):
        if not self.running:
            return
        try:
            self.clock_var.set(time.strftime("%H:%M:%S"))
            if self.demo:
                local, angles, players = self._demo_snapshot()
                self._show_snapshot(
                    local, angles, players, "DEMO  /  SIMULATED DATA"
                )
            else:
                local = self.get_local_player()
                if not local:
                    self.status_var.set("WAITING FOR PLAYER")
                    self.canvas.delete("all")
                    self.canvas.create_text(
                        self.canvas.winfo_width() / 2,
                        self.canvas.winfo_height() / 2,
                        text="WAITING FOR PLAYER",
                        fill=self.MUTED,
                        font=("Segoe UI Semibold", 14),
                    )
                else:
                    angles = self.get_view_angles()
                    players = self.get_players(local)
                    self._show_snapshot(
                        local, angles, players, "LIVE  /  CONNECTED"
                    )
        except Exception as error:
            label = "DEMO ERROR" if self.demo else "READ ERROR"
            self.status_var.set(f"{label}  /  {error}")

        delay = max(25, int(self.update_interval * 1000))
        self.root.after(delay, self._update_frame)

    def _on_close(self):
        self.running = False
        self.close()
        if self.root is not None:
            self.root.destroy()
            self.root = None

    def run(self):
        self._build_window()
        if self.demo:
            self.running = True
            self.root.after(50, self._update_frame)
            self.root.mainloop()
            return

        proceed = messagebox.askyesno(
            "Educational use only",
            "Use only with your own CS2 client launched with -insecure.\n\n"
            "Never use this in official or VAC-secured matches.\n\nContinue?",
            parent=self.root,
        )
        if not proceed:
            self._on_close()
            return
        if not self.connect():
            messagebox.showerror(
                "Connection failed",
                "Could not connect to CS2.\n\n"
                "Start CS2 and run this app as Administrator.",
                parent=self.root,
            )
            self._on_close()
            return

        self.running = True
        self.root.after(50, self._update_frame)
        self.root.mainloop()
