"""Desktop GUI renderer for CS2 Terminal Radar."""

import math
import random
import time
import json
import ctypes
import tkinter as tk
from tkinter import messagebox
from ctypes import wintypes

from main import TerminalRadar, writable_path


class GuiRadar(TerminalRadar):
    """A polished Tkinter view backed by the existing read-only radar."""

    BG = "#080c14"
    PANEL = "#0e1522"
    PANEL_ALT = "#141e2e"
    PANEL_HOVER = "#19263a"
    BORDER = "#243249"
    BORDER_SOFT = "#192538"
    TEXT = "#f2f6fc"
    MUTED = "#8997ad"
    GREEN = "#48d7a0"
    RED = "#ff647c"
    YELLOW = "#f4bd58"
    BLUE = "#5aa7ff"
    GRID = "#253650"
    ACCENT = "#6d8cff"
    ACCENT_HOVER = "#7d99ff"
    MAP_FLOOR = "#0a1320"

    def __init__(self, config, demo=False):
        super().__init__(config, load_offsets=not demo)
        self.config = config
        self.gui_config = config.get("gui", {})
        self.demo = demo
        self.demo_started = time.monotonic()
        self.demo_contacts = self._make_demo_contacts() if demo else []
        self.root = None
        self.canvas = None
        self.contact_canvas = None
        self.esp_window = None
        self.esp_canvas = None
        self.cs2_window = None
        self.hotkey_state = {0x77: False, 0x2D: False}
        self.running = False
        # Always start at the chooser; selected modes are session-only.
        self.view_mode = "menu"
        self.mode_buttons = {}
        self.menu_hitboxes = []
        self.view_title_var = None
        self.auto_map_bounds = None
        self.hovered_menu_mode = None

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
            return "EAST"
        if normalized < 135:
            return "NORTH"
        if normalized < 225:
            return "WEST"
        return "SOUTH"

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

    def _button(self, parent, text, command, width=None):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            activebackground=self.BORDER,
            activeforeground=self.TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=14,
            pady=8,
            takefocus=True,
        )
        button.bind(
            "<Enter>",
            lambda _event: button.configure(
                bg=getattr(button, "_hover_bg", self.PANEL_HOVER)
            ),
        )
        button.bind(
            "<Leave>",
            lambda _event: button.configure(
                bg=getattr(button, "_normal_bg", self.PANEL_ALT)
            ),
        )
        button._normal_bg = self.PANEL_ALT
        button._hover_bg = self.PANEL_HOVER
        return button

    def _set_view_mode(self, mode):
        if mode == "esp" and not self.demo:
            self._enter_esp_overlay()
        elif self.esp_window is not None:
            self._exit_esp_overlay()
        self.view_mode = mode
        for name, button in self.mode_buttons.items():
            active = name == mode
            button._normal_bg = self.ACCENT if active else self.PANEL_ALT
            button._hover_bg = self.ACCENT_HOVER if active else self.PANEL_HOVER
            button.configure(
                bg=button._normal_bg,
                fg="#ffffff" if active else self.MUTED,
            )
        if self.view_title_var is not None:
            titles = {
                "menu": "SELECT A VIEW",
                "esp": "ESP  /  CAMERA VIEW",
                "map": "FULL MAP  /  NORTH UP",
                "radar": "LOCAL RADAR  /  HEADING UP",
            }
            self.view_title_var.set(titles[mode])

    def _find_cs2_window(self):
        """Find the visible top-level window owned by the connected CS2 process."""
        if not self.pm or not getattr(self.pm, "process_id", None):
            return None
        user32 = ctypes.windll.user32
        target_pid = int(self.pm.process_id)
        matches = []
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid and user32.IsWindowVisible(hwnd):
                rect = wintypes.RECT()
                if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                    area = max(0, rect.right - rect.left) * max(
                        0, rect.bottom - rect.top
                    )
                    if area:
                        matches.append((area, hwnd))
            return True

        user32.EnumWindows(callback_type(visit), 0)
        return max(matches, default=(0, None))[1]

    @staticmethod
    def _client_rect_on_screen(hwnd):
        if not hwnd:
            return None
        user32 = ctypes.windll.user32
        rect = wintypes.RECT()
        origin = wintypes.POINT(0, 0)
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 1 or height <= 1:
            return None
        return origin.x, origin.y, width, height

    def _position_esp_overlay(self):
        bounds = self._client_rect_on_screen(self.cs2_window)
        if not bounds or self.esp_window is None:
            return
        x, y, width, height = bounds
        self.esp_window.geometry(f"{width}x{height}+{x}+{y}")

    def _enter_esp_overlay(self):
        """Create a transparent, click-through overlay over the CS2 client."""
        if self.root is None or self.esp_window is not None:
            return
        self.cs2_window = self._find_cs2_window()
        if self.cs2_window is None:
            messagebox.showerror(
                "CS2 window not found",
                "The CS2 game window could not be found.",
                parent=self.root,
            )
            return

        transparent = "#010203"
        overlay = tk.Toplevel(self.root)
        overlay.title("CS2 ESP Overlay")
        overlay.overrideredirect(True)
        overlay.configure(bg=transparent)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        self.esp_canvas = tk.Canvas(
            overlay, bg=transparent, highlightthickness=0, bd=0
        )
        self.esp_canvas.pack(fill="both", expand=True)
        self.esp_window = overlay
        self._position_esp_overlay()
        overlay.update_idletasks()

        user32 = ctypes.windll.user32
        hwnd = overlay.winfo_id()
        wrapper = user32.GetParent(hwnd)
        if wrapper:
            hwnd = wrapper
        gwl_exstyle = -20
        ws_ex_layered = 0x00080000
        ws_ex_transparent = 0x00000020
        ws_ex_toolwindow = 0x00000080
        ws_ex_noactivate = 0x08000000
        style = user32.GetWindowLongW(hwnd, gwl_exstyle)
        user32.SetWindowLongW(
            hwnd,
            gwl_exstyle,
            style
            | ws_ex_layered
            | ws_ex_transparent
            | ws_ex_toolwindow
            | ws_ex_noactivate,
        )
        # Apply the extended style without moving or activating the overlay.
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x37)
        self.root.withdraw()

    def _exit_esp_overlay(self):
        if self.esp_window is not None:
            self.esp_window.destroy()
        self.esp_window = None
        self.esp_canvas = None
        self.cs2_window = None
        if self.root is not None:
            self.root.deiconify()
            self.root.lift()

    def _check_esp_hotkey(self):
        """F8 or Insert returns from the overlay to the mode menu."""
        if self.esp_window is None:
            self.hotkey_state = {key: False for key in self.hotkey_state}
            return
        user32 = ctypes.windll.user32
        for virtual_key in self.hotkey_state:
            is_down = bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)
            was_down = self.hotkey_state[virtual_key]
            self.hotkey_state[virtual_key] = is_down
            if is_down and not was_down:
                self._set_view_mode("menu")
                return

    def _build_window(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("CS2 Radar — Observation Console")
        width = int(self.gui_config.get("window_width", 760))
        height = int(self.gui_config.get("window_height", 720))
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(560, 560)
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

        header = tk.Frame(self.root, bg=self.BG, padx=18, pady=14)
        header.pack(fill="x")
        brand_mark = tk.Canvas(
            header,
            width=34,
            height=34,
            bg=self.BG,
            bd=0,
            highlightthickness=0,
        )
        brand_mark.pack(side="left", padx=(0, 11))
        brand_mark.create_oval(3, 3, 31, 31, outline=self.ACCENT, width=2)
        brand_mark.create_oval(10, 10, 24, 24, outline=self.GRID)
        brand_mark.create_line(17, 5, 17, 29, fill=self.GRID)
        brand_mark.create_line(5, 17, 29, 17, fill=self.GRID)
        brand_mark.create_oval(14, 14, 20, 20, fill=self.GREEN, outline="")

        title_group = tk.Frame(header, bg=self.BG)
        title_group.pack(side="left")
        tk.Label(
            title_group,
            text="CS2 RADAR",
            bg=self.BG,
            fg=self.TEXT,
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w")
        status_row = tk.Frame(title_group, bg=self.BG)
        status_row.pack(anchor="w", pady=(2, 0))
        tk.Label(
            status_row,
            text="●",
            bg=self.BG,
            fg=self.GREEN,
            font=("Segoe UI", 7),
        ).pack(side="left", padx=(0, 5))
        self.status_var = tk.StringVar(value="CONNECTING")
        tk.Label(
            status_row,
            textvariable=self.status_var,
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")

        header_actions = tk.Frame(header, bg=self.BG)
        header_actions.pack(side="right")
        self._button(
            header_actions, "SETTINGS", self._open_settings
        ).pack(side="right", padx=(12, 0))
        self.clock_var = tk.StringVar()
        tk.Label(
            header_actions,
            textvariable=self.clock_var,
            bg=self.BG,
            fg=self.MUTED,
            font=("Consolas", 11),
        ).pack(side="right")
        tk.Label(
            header_actions,
            text="LOCAL TIME",
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI Semibold", 7),
        ).pack(side="right", padx=(0, 8))

        body = tk.Frame(self.root, bg=self.BG, padx=18)
        body.pack(fill="both", expand=True, pady=(0, 10))

        radar_panel = tk.Frame(
            body,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        radar_panel.pack(side="left", fill="both", expand=True)
        view_header = tk.Frame(radar_panel, bg=self.PANEL, padx=16, pady=12)
        view_header.pack(fill="x")
        self.view_title_var = tk.StringVar()
        tk.Label(
            view_header,
            textvariable=self.view_title_var,
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")
        switcher = tk.Frame(view_header, bg=self.PANEL_ALT)
        switcher.pack(side="right")
        for mode, label in (
            ("menu", "MENU"),
            ("esp", "ESP"),
            ("map", "MAP"),
            ("radar", "RADAR"),
        ):
            button = self._button(
                switcher,
                label,
                lambda selected=mode: self._set_view_mode(selected),
            )
            button.configure(padx=13, pady=6, font=("Segoe UI Semibold", 8))
            button.pack(side="left")
            self.mode_buttons[mode] = button
        self.canvas = tk.Canvas(
            radar_panel, bg=self.PANEL, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)

        # Compact mode keeps the data available for the canvas HUD without
        # spending permanent window space on a separate sidebar.
        self.enemy_var = tk.StringVar(value="0")
        self.ally_var = tk.StringVar(value="0")
        self.closest_var = tk.StringVar(value="--")
        self.heading_var = tk.StringVar(value="--")
        self._set_view_mode(self.view_mode)

        footer = tk.Frame(self.root, bg=self.BG, padx=18)
        footer.pack(fill="x", pady=(0, 12))
        tk.Label(
            footer,
            text="READ-ONLY TELEMETRY",
            bg=self.BG,
            fg=self.GREEN,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")
        tk.Label(
            footer,
            text="  •  EDUCATIONAL USE  •  -INSECURE MODE ONLY",
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left")
        tk.Label(
            footer,
            text="F8 / INSERT  EXIT OVERLAY",
            bg=self.BG,
            fg=self.MUTED,
            font=("Consolas", 8),
        ).pack(side="right")
        self.root.deiconify()
        self.root.lift()

    def _sync_display_options(self):
        """Retained for settings compatibility; compact mode has no sidebar."""

    def _on_canvas_click(self, event):
        if self.view_mode != "menu":
            return
        for left, top, right, bottom, mode in self.menu_hitboxes:
            if left <= event.x <= right and top <= event.y <= bottom:
                self._set_view_mode(mode)
                return

    def _on_canvas_motion(self, event):
        if self.view_mode != "menu":
            return
        hovered = next(
            (
                mode
                for left, top, right, bottom, mode in self.menu_hitboxes
                if left <= event.x <= right and top <= event.y <= bottom
            ),
            None,
        )
        self.canvas.configure(cursor="hand2" if hovered else "")
        if hovered != self.hovered_menu_mode:
            self.hovered_menu_mode = hovered
            self._draw_mode_menu()

    def _on_canvas_leave(self, _event):
        self.canvas.configure(cursor="")
        if self.hovered_menu_mode is not None:
            self.hovered_menu_mode = None
            if self.view_mode == "menu":
                self._draw_mode_menu()

    def _open_settings(self):
        """Open a compact modal settings panel and persist accepted changes."""
        window = tk.Toplevel(self.root)
        window.title("Radar settings")
        window.geometry("430x480")
        window.resizable(False, False)
        window.configure(bg=self.BG)
        window.transient(self.root)
        window.grab_set()

        tk.Label(
            window,
            text="SETTINGS",
            bg=self.BG,
            fg=self.TEXT,
            font=("Segoe UI Semibold", 18),
        ).pack(anchor="w", padx=24, pady=(22, 2))
        tk.Label(
            window,
            text="Save to apply changes and keep them for next launch.",
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=24, pady=(0, 18))

        form = tk.Frame(
            window,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            padx=18,
            pady=12,
        )
        form.pack(fill="both", expand=True, padx=24)

        always_on_top = tk.BooleanVar(
            value=bool(self.gui_config.get("always_on_top", False))
        )
        show_health = tk.BooleanVar(
            value=bool(self.display.get("show_health_bars", True))
        )
        opacity = tk.DoubleVar(
            value=float(self.gui_config.get("opacity", 0.97))
        )
        scale = tk.DoubleVar(value=float(self.scale))
        refresh = tk.DoubleVar(value=float(self.update_interval))

        def checkbox(label, variable):
            tk.Checkbutton(
                form,
                text=label,
                variable=variable,
                bg=self.PANEL,
                fg=self.TEXT,
                activebackground=self.PANEL,
                activeforeground=self.TEXT,
                selectcolor=self.PANEL_ALT,
                font=("Segoe UI", 10),
                bd=0,
                highlightthickness=0,
            ).pack(anchor="w", pady=5)

        def slider(label, variable, start, end, resolution, suffix):
            row = tk.Frame(form, bg=self.PANEL)
            row.pack(fill="x", pady=(10, 0))
            value_label = tk.Label(
                row, bg=self.PANEL, fg=self.GREEN, font=("Consolas", 9, "bold")
            )
            value_label.pack(side="right")
            tk.Label(
                row,
                text=label,
                bg=self.PANEL,
                fg=self.MUTED,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")

            def update_label(value):
                numeric = float(value)
                value_label.configure(
                    text=f"{numeric:.2f}{suffix}"
                    if resolution < 1 else f"{numeric:.0f}{suffix}"
                )

            control = tk.Scale(
                form,
                from_=start,
                to=end,
                resolution=resolution,
                orient="horizontal",
                variable=variable,
                command=update_label,
                bg=self.PANEL,
                fg=self.TEXT,
                troughcolor=self.PANEL_ALT,
                activebackground=self.ACCENT,
                highlightthickness=0,
                bd=0,
                showvalue=False,
            )
            control.pack(fill="x")
            update_label(variable.get())

        checkbox("Keep window always on top", always_on_top)
        checkbox("Show health bars", show_health)
        slider("Window opacity", opacity, 0.55, 1.0, 0.01, "")
        slider("Radar range", scale, 5, 80, 1, " u")
        slider("Refresh interval", refresh, 0.01, 0.25, 0.01, " s")

        actions = tk.Frame(window, bg=self.BG)
        actions.pack(fill="x", padx=24, pady=18)
        self._button(actions, "CANCEL", window.destroy).pack(side="right")

        def save():
            self.gui_config["always_on_top"] = always_on_top.get()
            self.gui_config["opacity"] = round(opacity.get(), 2)
            self.display["show_health_bars"] = show_health.get()
            self.scale = scale.get()
            self.update_interval = refresh.get()
            self.config["radar"]["scale"] = self.scale
            self.config["radar"]["update_interval"] = self.update_interval
            self.root.attributes("-topmost", always_on_top.get())
            self.root.attributes("-alpha", opacity.get())
            self._sync_display_options()
            try:
                writable_path("config.json").write_text(
                    json.dumps(self.config, indent=2) + "\n", encoding="utf-8"
                )
            except OSError as error:
                messagebox.showerror(
                    "Could not save settings", str(error), parent=window
                )
                return
            window.destroy()

        save_button = self._button(actions, "SAVE CHANGES", save)
        save_button.configure(bg=self.ACCENT)
        save_button._normal_bg = self.ACCENT
        save_button._hover_bg = self.ACCENT_HOVER
        save_button.pack(side="right", padx=(0, 8))

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

    def _map_bounds(self, players, local):
        """Return configured map bounds or stable bounds containing every player."""
        configured = self.gui_config.get("map_bounds")
        if (
            isinstance(configured, (list, tuple))
            and len(configured) == 4
        ):
            try:
                min_x, min_y, max_x, max_y = map(float, configured)
                if max_x > min_x and max_y > min_y:
                    return min_x, min_y, max_x, max_y
            except (TypeError, ValueError):
                pass

        points = [local["position"]] + [item["position"] for item in players]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        minimum_span = max(1000.0, self.scale * self.radius * 2.0)
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        span_x = max(max(xs) - min(xs), minimum_span) * 1.18
        span_y = max(max(ys) - min(ys), minimum_span) * 1.18
        frame_bounds = (
            center_x - span_x / 2,
            center_y - span_y / 2,
            center_x + span_x / 2,
            center_y + span_y / 2,
        )
        if self.auto_map_bounds is None:
            self.auto_map_bounds = frame_bounds
        else:
            old = self.auto_map_bounds
            self.auto_map_bounds = (
                min(old[0], frame_bounds[0]),
                min(old[1], frame_bounds[1]),
                max(old[2], frame_bounds[2]),
                max(old[3], frame_bounds[3]),
            )
        return self.auto_map_bounds

    @staticmethod
    def _map_heading_points(x, y, yaw):
        """Convert CS2 yaw (0° = +X, 90° = +Y) into canvas coordinates."""
        radians = math.radians(yaw)

        def point(angle, distance):
            return (
                x + math.cos(angle) * distance,
                y - math.sin(angle) * distance,
            )

        return (
            point(radians, 13),
            point(radians + 2.45, 9),
            point(radians - 2.45, 9),
        )

    def _draw_map_marker(self, x, y, color, label, health, local=False, yaw=0):
        if local:
            tip, left, right = self._map_heading_points(x, y, yaw)
            self.canvas.create_polygon(
                tip, left, right, fill=self.GREEN, outline="#d9fff1", width=2
            )
            self.canvas.create_text(
                x, y + 21, text="YOU", fill=self.GREEN,
                font=("Consolas", 8, "bold")
            )
            return

        self.canvas.create_oval(
            x - 9, y - 9, x + 9, y + 9,
            fill=color, outline="#ffffff", width=1
        )
        self.canvas.create_text(
            x, y, text=label, fill="#ffffff", font=("Consolas", 7, "bold")
        )
        self.canvas.create_text(
            x, y - 18, text=str(health), fill=self.TEXT,
            font=("Consolas", 8, "bold")
        )
        if self.display.get("show_health_bars", True):
            self.canvas.create_rectangle(
                x - 12, y + 13, x + 12, y + 16,
                fill=self.BORDER, outline=""
            )
            self.canvas.create_rectangle(
                x - 12, y + 13, x - 12 + 24 * health / 100, y + 16,
                fill=self.GREEN if health > 60 else self.YELLOW if health > 30 else self.RED,
                outline="",
            )

    def _draw_map(self, players, local, angles):
        """Draw a north-up world overview with every player in one frame."""
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        margin = 34
        min_x, min_y, max_x, max_y = self._map_bounds(players, local)
        span_x = max_x - min_x
        span_y = max_y - min_y
        scale = min(
            (width - margin * 2) / span_x,
            (height - margin * 2) / span_y,
        )
        map_width, map_height = span_x * scale, span_y * scale
        left = (width - map_width) / 2
        top = (height - map_height) / 2

        self.canvas.create_rectangle(
            left, top, left + map_width, top + map_height,
            fill=self.MAP_FLOOR, outline=self.BORDER, width=2
        )
        for fraction in (0.25, 0.5, 0.75):
            x = left + map_width * fraction
            y = top + map_height * fraction
            self.canvas.create_line(
                x, top, x, top + map_height, fill=self.GRID, dash=(2, 5)
            )
            self.canvas.create_line(
                left, y, left + map_width, y, fill=self.GRID, dash=(2, 5)
            )
        self.canvas.create_text(
            left + 12, top + 12, anchor="nw", text="N ↑",
            fill=self.MUTED, font=("Consolas", 10, "bold")
        )
        self.canvas.create_text(
            left + map_width - 12, top + map_height - 10,
            anchor="se",
            text=f"{span_x:.0f} × {span_y:.0f} WORLD UNITS",
            fill=self.MUTED,
            font=("Consolas", 8),
        )

        def project(position):
            return (
                left + (position[0] - min_x) * scale,
                top + (max_y - position[1]) * scale,
            )

        enemy_index = ally_index = 0
        for player in players:
            if player["is_enemy"]:
                enemy_index += 1
                label, color = f"E{enemy_index}", self.RED
            else:
                ally_index += 1
                label, color = f"A{ally_index}", self.BLUE
            x, y = project(player["position"])
            self._draw_map_marker(
                x, y, color, label, player["health"]
            )
        local_x, local_y = project(local["position"])
        self._draw_map_marker(
            local_x, local_y, self.GREEN, "YOU", 100,
            local=True, yaw=angles[0] if angles else 0.0
        )

    def _draw_mode_menu(self):
        """Draw the first-open selector for the three visual modes."""
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self.menu_hitboxes = []
        self.canvas.create_text(
            width / 2,
            38,
            text="OBSERVATION CONSOLE",
            fill=self.ACCENT,
            font=("Segoe UI Semibold", 8),
        )
        self.canvas.create_text(
            width / 2,
            68,
            text="Choose a workspace",
            fill=self.TEXT,
            font=("Segoe UI Semibold", 20),
        )
        self.canvas.create_text(
            width / 2,
            96,
            text="You can switch views at any time from the navigation above.",
            fill=self.MUTED,
            font=("Segoe UI", 9),
        )
        options = (
            (
                "esp",
                "CAMERA OVERLAY",
                "Live projection aligned to the game viewport",
                self.YELLOW,
                "01",
            ),
            (
                "map",
                "TACTICAL MAP",
                "North-up overview with complete spatial context",
                self.BLUE,
                "02",
            ),
            (
                "radar",
                "LOCAL RADAR",
                "Heading-up view centered on the local player",
                self.GREEN,
                "03",
            ),
        )
        card_width = min(520, width - 44)
        card_height = min(108, max(78, (height - 190) / 3 - 12))
        left = (width - card_width) / 2
        top = 126
        for mode, title, subtitle, color, number in options:
            bottom = top + card_height
            is_hovered = mode == self.hovered_menu_mode
            self.canvas.create_rectangle(
                left,
                top,
                left + card_width,
                bottom,
                fill=self.PANEL_HOVER if is_hovered else self.PANEL_ALT,
                outline=color if is_hovered else self.BORDER,
                width=2,
            )
            self.canvas.create_rectangle(
                left,
                top,
                left + 5,
                bottom,
                fill=color,
                outline="",
            )
            self.canvas.create_text(
                left + 25,
                top + 22,
                anchor="w",
                text=number,
                fill=color,
                font=("Consolas", 8, "bold"),
            )
            self.canvas.create_text(
                left + 24,
                top + card_height / 2 - 7,
                anchor="w",
                text=title,
                fill=self.TEXT,
                font=("Segoe UI Semibold", 13),
            )
            self.canvas.create_text(
                left + 24,
                top + card_height / 2 + 18,
                anchor="w",
                text=subtitle,
                fill=self.MUTED,
                font=("Segoe UI", 9),
            )
            self.canvas.create_text(
                left + card_width - 24,
                top + card_height / 2,
                anchor="e",
                text="OPEN  →",
                fill=color,
                font=("Consolas", 9, "bold"),
            )
            self.menu_hitboxes.append(
                (left, top, left + card_width, bottom, mode)
            )
            top = bottom + 12
        self.canvas.create_text(
            width / 2,
            min(height - 18, top + 16),
            text="Read-only local visualization  •  No game memory is modified",
            fill=self.MUTED,
            font=("Segoe UI", 8),
        )

    @staticmethod
    def _world_to_screen(position, matrix, width, height):
        """Project a world point with CS2's row-major 4x4 view matrix."""
        x, y, z = position
        clip_x = x * matrix[0] + y * matrix[1] + z * matrix[2] + matrix[3]
        clip_y = x * matrix[4] + y * matrix[5] + z * matrix[6] + matrix[7]
        clip_w = x * matrix[12] + y * matrix[13] + z * matrix[14] + matrix[15]
        if clip_w <= 0.01:
            return None
        return (
            width * 0.5 * (1.0 + clip_x / clip_w),
            height * 0.5 * (1.0 - clip_y / clip_w),
        )

    @staticmethod
    def _demo_world_to_screen(position, local, angles, width, height):
        """Perspective fallback used only by demo mode."""
        dx = position[0] - local["position"][0]
        dy = position[1] - local["position"][1]
        dz = position[2] - (local["position"][2] + 64.0)
        yaw = math.radians(angles[0])
        forward = dx * math.cos(yaw) + dy * math.sin(yaw)
        right = dx * math.sin(yaw) - dy * math.cos(yaw)
        if forward <= 5:
            return None
        focal = width * 0.72
        return (
            width / 2 + right / forward * focal,
            height / 2 - dz / forward * focal,
        )

    def _draw_esp(self, players, local, angles, matrix=None):
        """Draw read-only player boxes projected into the camera view."""
        canvas = self.esp_canvas if self.esp_canvas is not None else self.canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        if canvas is self.canvas:
            canvas.create_rectangle(
                0, 0, width, height, fill="#080d16", outline=""
            )
        canvas.create_text(
            16,
            14,
            anchor="nw",
            text=(
                "ESP ACTIVE  /  F8 OR INSERT: RETURN TO MENU"
                if canvas is self.esp_canvas
                else "ESP  /  READ-ONLY CAMERA PROJECTION"
            ),
            fill=self.MUTED,
            font=("Consolas", 8, "bold"),
        )
        if canvas is self.canvas:
            cx, cy = width / 2, height / 2
            canvas.create_line(cx - 7, cy, cx + 7, cy, fill=self.MUTED)
            canvas.create_line(cx, cy - 7, cx, cy + 7, fill=self.MUTED)

        use_matrix = matrix and len(matrix) == 16 and any(matrix)

        def project(position):
            if use_matrix:
                return self._world_to_screen(position, matrix, width, height)
            return self._demo_world_to_screen(
                position, local, angles, width, height
            )

        for player in sorted(
            players, key=lambda item: item["distance"], reverse=True
        ):
            feet = project(player["position"])
            head_position = (
                player["position"][0],
                player["position"][1],
                player["position"][2] + 72.0,
            )
            head = project(head_position)
            if not feet or not head:
                continue
            box_height = abs(feet[1] - head[1])
            if box_height < 4:
                continue
            box_width = box_height * 0.46
            center_x = (feet[0] + head[0]) / 2
            top = min(feet[1], head[1])
            bottom = max(feet[1], head[1])
            left, right = center_x - box_width / 2, center_x + box_width / 2
            if right < 0 or left > width or bottom < 0 or top > height:
                continue
            color = self.RED if player["is_enemy"] else self.BLUE
            label = "ENEMY" if player["is_enemy"] else "ALLY"
            canvas.create_rectangle(
                left, top, right, bottom, outline=color, width=2
            )
            canvas.create_text(
                left,
                top - 7,
                anchor="sw",
                text=f"{label}  {player['distance']:.0f}u",
                fill=color,
                font=("Consolas", 8, "bold"),
            )
            if self.display.get("show_health_bars", True):
                canvas.create_rectangle(
                    left - 7, top, left - 3, bottom,
                    fill=self.BORDER, outline=""
                )
                health_top = bottom - box_height * player["health"] / 100
                canvas.create_rectangle(
                    left - 7, health_top, left - 3, bottom,
                    fill=self.GREEN if player["health"] > 50 else self.YELLOW
                    if player["health"] > 25 else self.RED,
                    outline="",
                )

    def _draw_contacts(self, players):
        if self.contact_canvas is None:
            return
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

    def _draw_compact_hud(self):
        """Place essential stats over the view instead of using a sidebar."""
        height = max(1, self.canvas.winfo_height())
        y = height - 28
        text = (
            f"E {self.enemy_var.get()}   A {self.ally_var.get()}"
            f"   |   {self.closest_var.get()}"
            f"   |   {self.heading_var.get()}"
        )
        text_id = self.canvas.create_text(
            22,
            y,
            anchor="w",
            text=text,
            fill=self.TEXT,
            font=("Consolas", 8, "bold"),
        )
        bounds = self.canvas.bbox(text_id)
        if bounds:
            background = self.canvas.create_rectangle(
                bounds[0] - 8,
                bounds[1] - 5,
                bounds[2] + 8,
                bounds[3] + 5,
                fill=self.PANEL_ALT,
                outline=self.BORDER,
            )
            self.canvas.tag_lower(background, text_id)

    def _show_snapshot(self, local, angles, players, status, matrix=None):
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
        if self.view_mode == "menu":
            self._draw_mode_menu()
            return
        if self.view_mode == "esp":
            self._draw_esp(players, local, angles, matrix)
        elif self.view_mode == "map":
            self._draw_map(players, local, angles)
        else:
            self._draw_radar(players, local, angles)
        if self.esp_window is None:
            self._draw_compact_hud()

    def _update_frame(self):
        if not self.running:
            return
        try:
            self._check_esp_hotkey()
            if self.esp_window is not None:
                self._position_esp_overlay()
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
                    matrix = (
                        self.get_view_matrix()
                        if self.view_mode == "esp" else None
                    )
                    self._show_snapshot(
                        local, angles, players, "LIVE  /  CONNECTED", matrix
                    )
        except Exception as error:
            label = "DEMO ERROR" if self.demo else "READ ERROR"
            self.status_var.set(f"{label}  /  {error}")

        delay = max(8, int(self.update_interval * 1000))
        self.root.after(delay, self._update_frame)

    def _on_close(self):
        self.running = False
        if self.esp_window is not None:
            self.esp_window.destroy()
            self.esp_window = None
            self.esp_canvas = None
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
