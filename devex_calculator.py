#!/usr/bin/env python3
"""
Roblox Dev & Daily Toolkit v2.1 (single-file, offline)
------------------------------------------------------
One window, ten live calculators with a modern dark/light UI:

  Roblox:  DevEx cash-out | Buy Robux | Marketplace fees | Payout splitter
  Daily:   Percentages | Units | Dates | Loans | Time zones | Number bases

- Zero pip installs, zero network / telemetry; settings saved locally as JSON
- Dark theme by default, light toggle with cross-fade; DPI-aware on Windows
- Effects: aurora glow behind cards, gradient heading wash, eased hovers,
  slide-in tool transitions, pulsing DevEx warning
- Keyboard: Ctrl+1..0 switch tools, Enter copies, Esc clears, Ctrl+A selects
"""

import ctypes
import json
import math
import os
import time
import tkinter as tk
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ZoneInfo("UTC")  # probe: Windows Python is often installed without IANA tz data
    HAVE_TZDATA = True
except Exception:
    HAVE_TZDATA = False

# ---------------------------------------------------------------------------
# Configuration constants (edit these to keep the app current)
# ---------------------------------------------------------------------------
RUBUX_TO_USD = 0.0035         # 100,000 R$ = $350.00 — long-standing published DevEx rate
DEX_MINIMUM_ROBUX = 30_000    # cash-out eligibility threshold
MARKETPLACE_FEE = 0.30        # Roblox marketplace cut on most sales (30%)
# Real purchase packages: (robux, price in USD), smallest first.
ROBUX_PACKAGES = [
    (400, 4.99), (800, 9.99), (1_700, 19.99),
    (4_500, 49.99), (10_000, 99.99),
]

APP_TITLE = "Dev Toolkit"
VERSION = "2.1"

TIMEZONES = [
    "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Moscow",
    "Asia/Dubai", "Asia/Kolkata", "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul",
    "Australia/Sydney", "America/Sao_Paulo", "America/Mexico_City",
]
LOCAL_ZONE = "System (my time)"
TIMEZONES = [LOCAL_ZONE] + TIMEZONES
# Fixed standard-time offsets (hours from UTC) used ONLY when the IANA database
# is missing on this system — no DST handling in that case.
FALLBACK_OFFSETS = {
    "UTC": 0, "US/Eastern": -5, "US/Central": -6, "US/Mountain": -7,
    "US/Pacific": -8, "Europe/London": 0, "Europe/Berlin": 1,
    "Europe/Paris": 1, "Europe/Moscow": 3, "Asia/Dubai": 4,
    "Asia/Kolkata": 5.5, "Asia/Shanghai": 8, "Asia/Tokyo": 9, "Asia/Seoul": 9,
    "Australia/Sydney": 10, "America/Sao_Paulo": -3, "America/Mexico_City": -6,
}

TIMEZONE_FALLBACK_NOTE = ("DST-aware via the system IANA database." if HAVE_TZDATA
                          else "IANA database not found — fixed offsets, no DST.")

UNIT_FACTORS = {
    "Length": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "mi": 1609.344,
    },
    "Mass": {
        "mg": 0.000001, "g": 0.001, "kg": 1.0,
        "oz": 0.028349523, "lb": 0.45359237,
    },
    "Volume": {  # base unit: milliliter; exact US customary factors
        "mL": 1.0, "L": 1000.0, "fl oz": 29.5735295625,
        "cup": 236.5882365, "qt": 946.352946, "gal": 3785.411784,
    },
    "Data": {
        "B": 1.0, "KB": 1024.0, "MB": 1024.0 ** 2, "GB": 1024.0 ** 3, "TB": 1024.0 ** 4,
    },
    "Temperature": ["°C", "°F", "K"],  # converted through Celsius internally
}

UNIT_NAMES = {
    "Length": {"mm": "Millimeters", "cm": "Centimeters", "m": "Meters",
               "km": "Kilometers", "in": "Inches", "ft": "Feet", "mi": "Miles"},
    "Mass": {"mg": "Milligrams", "g": "Grams", "kg": "Kilograms",
             "oz": "Ounces", "lb": "Pounds"},
    "Volume": {"mL": "Milliliters", "L": "Liters", "fl oz": "Fluid ounces (US)",
               "cup": "Cups", "qt": "Quarts", "gal": "Gallons"},
    "Data": {"B": "Bytes", "KB": "Kilobytes", "MB": "Megabytes",
             "GB": "Gigabytes", "TB": "Terabytes"},
    "Temperature": {"°C": "Celsius", "°F": "Fahrenheit", "K": "Kelvin"},
}

# ---------------------------------------------------------------------------
# Theming
# ---------------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg": "#0e1014", "side": "#12151b", "card": "#171a22",
        "entry": "#1e222c", "border": "#2a2f3c", "hover": "#222735",
        "fg": "#e8ebf3", "muted": "#8a92a6", "accent": "#4d8dff",
        "accent_fg": "#ffffff", "warning": "#f0b357", "invalid": "#e0685f",
        "glow1": "#2b4f8f", "glow2": "#46357f",
        "hover_up": True, "status": "#12151b",
    },
    "light": {
        "bg": "#f4f6fa", "side": "#e9edf4", "card": "#ffffff",
        "entry": "#ffffff", "border": "#dde2ec", "hover": "#eef1f7",
        "fg": "#12161f", "muted": "#5c6575", "accent": "#2f6bff",
        "accent_fg": "#ffffff", "warning": "#b45309", "invalid": "#c94b3f",
        "glow1": "#dbe6ff", "glow2": "#eae4ff",
        "hover_up": False, "status": "#e9edf4",
    },
}

HOVER_STRENGTH = 0.14  # hover shift toward white (dark) / black (light)


# ---------------------------------------------------------------------------
# Parsing / formatting (shared by every tool)
# ---------------------------------------------------------------------------

def format_num(value):
    """Thousands separators; whole numbers plain, fractions trimmed to <=4 dp."""
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def _parse_number(kept):
    try:
        return float(kept)
    except ValueError:
        return None


def read_amount(text):
    """('empty', None) | ('bad', None) | ('ok', float) for currency-style input."""
    if not text:
        return "empty", None
    kept = "".join(ch for ch in text if ch.isdigit() or ch in "-.")
    if not kept or kept in ("-", ".", "-.", ".-"):
        return "bad", None
    value = _parse_number(kept)
    if value is None or value < 0:
        return "bad", None
    return "ok", value


def read_signed(text):
    """Same protocol as read_amount, but negative values are allowed."""
    if not text:
        return "empty", None
    kept = text.strip().replace(",", "").replace("$", "").replace("R$", "").replace(" ", "")
    if not kept:
        return "bad", None
    value = _parse_number(kept)
    return ("bad", None) if value is None else ("ok", value)


def parse_amount(text):
    """Back-compat helper: non-negative float or None."""
    state, value = read_amount(text)
    return value if state == "ok" else None


def format_robux(value):
    """Robux-style formatting: whole numbers preferred, else up to 2 dp."""
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _money(value):
    """Round to cents half-up via Decimal so float noise cannot flip a cent."""
    return Decimal(str(round(value, 6))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_usd(value):
    """USD for result lines: 2 dp, '< $0.01' for tiny positives."""
    if value is None:
        return ""
    tiny = 0 < round(value, 6) < 0.01
    cents = _money(value)
    if tiny:
        return "< $0.01"
    return f"${cents:,.2f}"


def format_usd_edit(value):
    """USD for input fields: 2 dp normally, more precision for tiny amounts."""
    if value is None:
        return ""
    if value >= 0.01:
        return f"{round(value, 2):,.2f}"
    return f"{round(value, 6):,.4f}".rstrip("0").rstrip(".")


def monthly_payment(principal, annual_rate_pct, years):
    """Standard amortized monthly payment. Returns None on invalid input."""
    try:
        p = float(principal)
        r = float(annual_rate_pct) / 100.0 / 12.0
        n = int(float(years) * 12)
    except (TypeError, ValueError):
        return None
    if p <= 0 or n <= 0 or annual_rate_pct is None:
        return None
    if r == 0:
        return p / n
    return p * r / (1 - (1 + r) ** -n)


def unit_convert(category, amount, unit_from, unit_to):
    """Convert via base-unit factors; Temperature goes through Celsius."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None
    units = UNIT_FACTORS.get(category)
    try:
        if isinstance(units, list):  # Temperature
            celsius = {"°C": amount, "°F": (amount - 32) * 5 / 9, "K": amount - 273.15}[unit_from]
            return {"°C": celsius, "°F": celsius * 9 / 5 + 32, "K": celsius + 273.15}[unit_to]
        return amount * units[unit_from] / units[unit_to]
    except (KeyError, ZeroDivisionError):
        return None


def unit_options(category):
    """[(display, value)] pairs for the converter menus, or [] if unknown."""
    data = UNIT_FACTORS.get(category)
    if data is None:
        return []
    if isinstance(data, list):
        return [(f"{UNIT_NAMES[category][c]} ({c})", c) for c in data]
    return [(f"{UNIT_NAMES[category][code]} ({code})", code) for code in data]


def get_zone(name):
    """Tzinfo for a zone name, or None for the local-system sentinel."""
    if name == LOCAL_ZONE:
        return None
    if HAVE_TZDATA and name in FALLBACK_OFFSETS:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return timezone(timedelta(hours=FALLBACK_OFFSETS.get(name, 0)))


# ---------------------------------------------------------------------------
# Settings persistence (local JSON; no network, no telemetry)
# ---------------------------------------------------------------------------

def config_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "DevexCalculator" / "config.json"


def load_config():
    defaults = {"theme": "dark", "tool": "devex", "inputs": {}}
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in defaults:
                if key in data:
                    defaults[key] = data[key]
    except (OSError, ValueError):
        pass
    return defaults


def save_config(cfg):
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass  # unwritable location — app still works, just won't remember


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def mix(c1, c2, t):
    """Linear interpolation between two hex colors, t in 0..1."""
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def ease_out(t):
    """Cubic ease-out for natural-feeling animation."""
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------------------
# Animation manager ("shader-ish" effects ride on this)
# ---------------------------------------------------------------------------

class FX:
    """~30 fps after-loop: each animation gets eased progress 0..1 (or loops)."""

    def __init__(self, root):
        self.root = root
        self.active = []   # [key, t0, dur, step, done, loop]
        self.running = False

    def start(self, key, dur, step, done=None, loop=False):
        self.cancel(key)
        self.active.append([key, time.perf_counter() * 1000.0, dur, step, done, loop])
        if not self.running:
            self.running = True
            self.root.after(30, self._tick)

    def cancel(self, key):
        self.active = [a for a in self.active if a[0] != key]

    def _tick(self):
        try:
            now = time.perf_counter() * 1000.0
            still = []
            for key, t0, dur, step, done, loop in self.active:
                elapsed = now - t0
                if loop:
                    step((elapsed / max(dur, 1)) % 1.0)
                    still.append([key, t0, dur, step, done, loop])
                    continue
                t = min(1.0, elapsed / max(dur, 1))
                try:
                    step(ease_out(t))
                except tk.TclError:  # widget vanished mid-animation
                    continue
                if t < 1.0:
                    still.append([key, t0, dur, step, done, loop])
                elif done:
                    done()
            self.active = still
            if self.active:
                self.root.after(30, self._tick)
            else:
                self.running = False
        except tk.TclError:  # root destroyed mid-flight — stop quietly
            self.active = []
            self.running = False


# ---------------------------------------------------------------------------
# Modern widgets
# ---------------------------------------------------------------------------

class RoundedButton(tk.Canvas):
    """Flat pill button: rounded corners, eased hover, themable."""

    ROLES = {  # role -> (background color key, foreground color key)
        "accent": ("accent", "accent_fg"),
        "ghost": ("entry", "fg"),
        "tab": ("entry", "muted"),
        "tab_active": ("accent", "accent_fg"),
    }

    def __init__(self, app, master, text, command, width=120, height=32,
                 role="accent", font=None, canvas_role="card"):
        super().__init__(master, width=width, height=height, highlightthickness=0, bd=0)
        self.app = app
        self.command = command
        self.text = text
        self.role = role
        self.canvas_role = canvas_role
        self.font = font or ("Segoe UI", 10, "bold")
        self._base = ""
        self._shape = None
        self._label = None
        self._fx_key = f"hover{id(self)}"
        app.buttons.append(self)
        self.retheme(app.colors)
        self.bind("<Button-1>", self._press)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda _e: self._draw())

    def retheme(self, c):
        bg_key, fg_key = self.ROLES[self.role]
        self._base = c[bg_key]
        self._fg = c[fg_key]
        self.configure(bg=c[self.canvas_role])
        self._draw()

    def _hover_target(self):
        c = self.app.colors
        return mix(self._base, "#ffffff" if c["hover_up"] else "#000000", HOVER_STRENGTH)

    def _on_enter(self, _e):
        self.configure(cursor="hand2")
        self.app.fx.start(self._fx_key, 110, lambda t: self.itemconfig(
            self._shape, fill=mix(self._base, self._hover_target(), t)))

    def _on_leave(self, _e):
        self.configure(cursor="")
        self.app.fx.start(self._fx_key, 130, lambda t: self.itemconfig(
            self._shape, fill=mix(self._hover_target(), self._base, t)))

    def _press(self, _e):
        self.itemconfig(self._shape, fill=self._hover_target())
        self.command()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:  # not mapped yet — use requested size
            w, h = int(self["width"]), int(self["height"])
        r = min(14, h // 2)
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h,
               w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        self._shape = self.create_polygon(pts, smooth=True, fill=self._base, outline="")
        self._label = self.create_text(w // 2, h // 2, text=self.text, fill=self._fg,
                                       font=self.font)

    def set_text(self, text):
        self.text = text
        self.itemconfig(self._label, text=text)


class Dropdown(tk.Frame):
    """Themed replacement for OptionMenu: flat pill field + borderless popup list."""

    def __init__(self, app, master):
        super().__init__(master, highlightthickness=1, cursor="hand2")
        self.app = app
        self.onpick = None           # called with the value when user picks
        self._pairs = []             # [(display, value)] — NOT "_options": that
        self._display_of = {}        # name shadows tkinter's Misc._options()
        self._value = None
        self._popup = None
        self.config(bg=app.colors["entry"], highlightbackground=app.colors["border"],
                    highlightcolor=app.colors["accent"])
        self.label = tk.Label(self, text="", anchor="w", bg=app.colors["entry"],
                              fg=app.colors["fg"], font=("Segoe UI", 10), padx=8, pady=2)
        self.label.pack(side="left", fill="both", expand=True)
        self.arrow = tk.Label(self, text="▾", bg=app.colors["entry"],
                              fg=app.colors["muted"], font=("Segoe UI", 10), padx=6)
        self.arrow.pack(side="right", fill="y")
        for w in (self, self.label, self.arrow):
            w.bind("<Button-1>", lambda _e: self.open_popup())
        app.dropdowns.append(self)

    # -- data ---------------------------------------------------------------
    def set_options(self, options):
        """options: list of strings, or (display, value) pairs."""
        self._pairs = [(o, o) if isinstance(o, str) else (o[0], o[1]) for o in options]
        self._display_of = {v: d for d, v in self._pairs}

    def get(self):
        return self._value

    def show(self, value):
        """Update display for a value set externally (no onpick callback)."""
        self._value = value
        self.label.config(text=self._display_of.get(value, value if value else ""))

    def pick(self, value):
        self.show(value)
        if self.onpick:
            self.onpick(value)

    # -- popup list ----------------------------------------------------------
    def open_popup(self):
        if self._popup:
            self.close_popup()
            return
        c = self.app.colors
        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        holder = tk.Frame(top, bg=c["border"], padx=1, pady=1)
        holder.pack()
        for display, value in self._pairs:
            item = tk.Label(holder, text=display, anchor="w", bg=c["card"], fg=c["fg"],
                            font=("Segoe UI", 10), padx=10, pady=4)
            item.pack(fill="x")
            item.bind("<Enter>", lambda _e, w=item: w.config(bg=c["hover"]))
            item.bind("<Leave>", lambda _e, w=item: w.config(bg=c["card"]))
            item.bind("<Button-1>", lambda _e, v=value: self.pick(v) or "break")
        top.update_idletasks()
        width = max(self.winfo_width(), holder.winfo_reqwidth())
        height = holder.winfo_reqheight() + 2
        x = max(0, self.winfo_rootx())
        y = self.winfo_rooty() + self.winfo_height()
        if y + height > self.winfo_screenheight():  # flip above if near the bottom
            y = max(0, self.winfo_rooty() - height - 4)
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.grab_set()
        top.bind("<Escape>", lambda _e: self.close_popup())
        top.bind("<Button-1>", lambda e: self.close_popup() if e.widget is top else None)
        top.bind("<FocusOut>", lambda _e: self.close_popup())
        self._popup = top

    def close_popup(self):
        if self._popup:
            try:
                self._popup.grab_release()
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None

    def retheme(self, c):
        self.config(bg=c["entry"], highlightbackground=c["border"],
                    highlightcolor=c["accent"])
        self.label.config(bg=c["entry"], fg=c["fg"])
        self.arrow.config(bg=c["entry"], fg=c["muted"])
        self.close_popup()  # an open popup would show stale colors


# ---------------------------------------------------------------------------
# Tool base class (shared builders + validation feedback)
# ---------------------------------------------------------------------------

class Tool:
    key = ""
    title = ""
    note = ""     # small muted line under the heading

    def __init__(self, app, content):
        self.app = app
        self.frame = tk.Frame(content, bg=app.colors["card"], padx=22, pady=16)
        app.tag(self.frame, bg="card")
        self.vars = {}        # field key -> StringVar (remembered between runs)
        self.entries = {}     # field key -> Entry widgets (validation borders)
        self.dropdown_keys = set()
        self._invalid = set()
        self._pending_traces = []  # wired after build() so refresh() can't run
        self.row = 0                 # on a half-constructed tool
        self.primary = None
        self.badge = None
        self.frame.columnconfigure(1, weight=1)
        self.build()
        for var, callback in self._pending_traces:
            var.trace_add("write", callback)

    # -- heading -------------------------------------------------------------
    def heading(self):
        self.glow = tk.Canvas(self.frame, height=52, bd=0, highlightthickness=0)
        self.glow.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.row += 1
        self.glow.bind("<Configure>", lambda _e: self._draw_glow())
        if self.note:
            self.muted_line(self.note)

    def _draw_glow(self):
        """Horizontal color wash (the 'gradient hero' under each tool title)."""
        c = self.app.colors
        cv = self.glow
        cv.delete("all")
        w = max(self.frame.winfo_reqwidth(), cv.winfo_width(), 400)
        h = int(cv["height"])
        steps = 64
        for i in range(steps):
            t = i / steps
            fade = (1 - t) ** 1.7
            # two hues sweep the strip: accent-blue on the left, violet on the right
            base = c["glow1"] if t < 0.55 else c["glow2"]
            color = mix(c["card"], base, 0.55 * fade)
            x0 = i * w / steps
            cv.create_rectangle(x0, 0, x0 + w / steps + 1, h, fill=color, width=0)
        cv.create_text(6, h // 2, text=self.title, anchor="w", fill=c["fg"],
                       font=("Segoe UI", 14, "bold"))
        active = 98 if self.app.current_key == self.key else 6
        self.badge = cv.create_rectangle(6, h - 4, active, h - 1,
                                         fill=c["accent"], width=0)

    def animate_entry(self):
        """Grow the accent underline when this tool becomes active."""
        def step(t):
            try:
                self.glow.coords(self.badge, 6, self.glow.winfo_height() - 4,
                                 6 + 92 * t, self.glow.winfo_height() - 1)
            except tk.TclError:
                pass
        self.app.fx.start(f"badge{self.key}", 240, step,
                          done=lambda: self.glow.coords(self.badge, 6,
                                                        self.glow.winfo_height() - 4,
                                                        98, self.glow.winfo_height() - 1))

    def muted_line(self, text, pady=(0, 6)):
        lbl = tk.Label(self.frame, text=text, font=("Segoe UI", 9), anchor="w",
                       wraplength=560, justify="left")
        lbl.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=pady)
        self.app.tag(lbl, bg="card", fg="muted")
        self.row += 1
        return lbl

    # -- field builders ------------------------------------------------------
    def _make_entry(self, master, var):
        entry = tk.Entry(master, textvariable=var, font=("Segoe UI", 11),
                         relief="flat", highlightthickness=1)
        self.app.tag(entry, kind="entry")
        return entry

    def _register(self, key, var, entry=None):
        self.vars[key] = var
        if entry is not None:
            self.entries[key] = entry
        self._pending_traces.append((var, lambda *_: self.refresh()))
        if self.primary is None and entry is not None:
            self.primary = entry
        return var

    def field(self, label, key, width=None):
        """Labeled entry row returning the StringVar; refresh() runs on edit."""
        lbl = tk.Label(self.frame, text=label, font=("Segoe UI", 10))
        lbl.grid(row=self.row, column=0, sticky="w", pady=(8, 0), padx=(0, 12))
        self.app.tag(lbl, bg="card", fg="muted")
        var = tk.StringVar()
        entry = self._make_entry(self.frame, var)
        if width:
            entry.configure(width=width)
        entry.grid(row=self.row, column=1, sticky="ew", pady=(8, 0), ipady=3)
        self._register(key, var, entry)
        self.row += 1
        return var

    def inline_field(self, master, key, width=8, var=None, with_trace=True):
        """Entry for inline (one-line) layouts."""
        var = var if var is not None else tk.StringVar()
        entry = self._make_entry(master, var)
        entry.configure(width=width)
        if self.primary is None:
            self.primary = entry
        self.entries[key] = entry
        self.vars[key] = var
        if with_trace:
            self._pending_traces.append((var, lambda *_: self.refresh()))
        return var, entry

    def dropdown_field(self, label, options, key, default=None):
        """Labeled themed dropdown row returning (var, Dropdown)."""
        lbl = tk.Label(self.frame, text=label, font=("Segoe UI", 10))
        lbl.grid(row=self.row, column=0, sticky="w", pady=(8, 0), padx=(0, 12))
        self.app.tag(lbl, bg="card", fg="muted")
        var = tk.StringVar()
        dd = Dropdown(self.app, self.frame)
        dd.set_options(options)
        dd.grid(row=self.row, column=1, sticky="ew", pady=(8, 0))
        dd.onpick = var.set
        # Display follows the var even when it is set programmatically.
        var.trace_add("write", lambda *_: dd.show(var.get()))
        self.vars[key] = var
        self.dropdown_keys.add(key)
        var.set(default if default is not None else (options[0][1] if options else ""))
        self.row += 1
        self._pending_traces.append((var, lambda *_: self.refresh()))
        return var, dd

    def _result_big(self):
        """[Label big bold] + [Label muted] pair; returns (big, sub) vars."""
        row = self.row + 1
        big, sub = tk.StringVar(), tk.StringVar()
        big_lbl = tk.Label(self.frame, textvariable=big, font=("Segoe UI", 15, "bold"),
                           anchor="w")
        big_lbl.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 2))
        self.app.tag(big_lbl, bg="card", fg="fg")
        sub_lbl = tk.Label(self.frame, textvariable=sub, font=("Segoe UI", 9),
                           anchor="w", justify="left", wraplength=560)
        sub_lbl.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.app.tag(sub_lbl, bg="card", fg="muted")
        self.row = row + 1
        return big, sub

    def results(self):
        self.row += 1  # spacer
        return self._result_big()

    def _result_inline(self, master, var):
        lbl = tk.Label(master, textvariable=var, font=("Segoe UI", 11, "bold"), anchor="e")
        self.app.tag(lbl, bg="card", fg="fg")
        return lbl

    def warning_line(self):
        self.row += 1
        var = tk.StringVar()
        lbl = tk.Label(self.frame, textvariable=var, font=("Segoe UI", 9, "italic"),
                       anchor="w", justify="left", wraplength=560)
        lbl.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        self.app.tag(lbl, bg="card", fg="warning")
        self.warn_lbl = lbl
        self.warn_var = var
        var.trace_add("write", self._on_warn_change)
        self.row += 1
        return var

    def _on_warn_change(self, *_):
        """Non-empty warning text starts a gentle breathing pulse on the label."""
        if self.warn_var.get():
            self._start_warn_pulse()
        else:
            self.app.fx.cancel(f"warn{self.key}")
            self.warn_lbl.config(fg=self.app.colors["warning"])

    def _start_warn_pulse(self):
        def pulse(t):
            base = self.app.colors["warning"]
            self.warn_lbl.config(fg=mix(base, self.app.colors["fg"],
                                        0.35 * abs(0.5 - t) * 2))
        self.app.fx.start(f"warn{self.key}", 1800, pulse, loop=True)

    def actions(self, pady=(12, 0)):
        self.row += 1
        row = tk.Frame(self.frame)
        row.grid(row=self.row, column=0, columnspan=2, sticky="w", pady=pady)
        self.app.tag(row, bg="card")
        RoundedButton(self.app, row, "Copy result", self.app.copy_current,
                      width=110, height=30, role="accent")
        RoundedButton(self.app, row, "Clear", self.app.clear_current,
                      width=70, height=30, role="ghost", font=("Segoe UI", 10))
        self.row += 1

    # -- validation feedback -------------------------------------------------
    def mark(self, key, bad):
        entry = self.entries.get(key)
        if entry is None:
            return
        c = self.app.colors
        if bad:
            self._invalid.add(key)
            entry.configure(highlightbackground=c["invalid"])
        else:
            self._invalid.discard(key)
            entry.configure(highlightbackground=c["border"])

    def apply_invalid(self, c):
        for key in self._invalid:
            self.entries[key].configure(highlightbackground=c["invalid"])

    def focus_primary(self):
        if self.primary and self.primary.winfo_ismapped():
            self.primary.focus_set()
            self.primary.select_range(0, "end")

    # -- per-tool interface --------------------------------------------------
    def build(self):
        raise NotImplementedError

    def refresh(self):
        pass

    def retheme(self, c):
        self._draw_glow()
        self.apply_invalid(c)

    def copy_text(self):
        return None

    def clear(self):
        for key, var in self.vars.items():
            if key not in self.dropdown_keys:
                var.set("")
        self.refresh()


# ---------------------------------------------------------------------------
# Roblox tools
# ---------------------------------------------------------------------------

class DevExTool(Tool):
    key, title = "devex", "DevEx Cash-Out"
    note = "Cash out earned Robux at the published DevEx rate."

    def build(self):
        self.heading()
        self.robux = self.field("Robux", "robux")
        self.usd = self.field("USD", "usd")
        self.big, self.sub = self.results()
        self.warning_line()
        self.actions()
        self._syncing = False
        self.robux.trace_add("write", lambda *_: self._from_robux())
        self.usd.trace_add("write", lambda *_: self._from_usd())

    def _from_robux(self):
        if self._syncing:
            return
        robux = parse_amount(self.robux.get())
        self._syncing = True
        self.usd.set("" if robux is None else format_usd_edit(robux * RUBUX_TO_USD))
        self._syncing = False
        self.refresh(robux=robux)

    def _from_usd(self):
        if self._syncing:
            return
        usd = parse_amount(self.usd.get())
        self._syncing = True
        self.robux.set("" if usd is None else format_robux(usd / RUBUX_TO_USD))
        self._syncing = False
        self.refresh(usd=usd)

    def refresh(self, robux=None, usd=None):
        self.mark("robux", read_amount(self.robux.get())[0] == "bad")
        self.mark("usd", read_amount(self.usd.get())[0] == "bad")
        if robux is None and usd is None:
            if not self.robux.get() and not self.usd.get():
                self.big.set("")
                self.sub.set("")
                self.warn_var.set("")
            return
        if robux is None:
            robux = usd / RUBUX_TO_USD
        if usd is None:
            usd = robux * RUBUX_TO_USD
        self.big.set(f"{format_robux(robux)} R$ = {format_usd(usd)}")
        self.sub.set("Gross amounts, before taxes or fees.")
        if 0 < robux < DEX_MINIMUM_ROBUX:
            short = DEX_MINIMUM_ROBUX - robux
            self.warn_var.set(
                "Below the 30,000 R$ DevEx minimum — not eligible to cash out. "
                f"{format_robux(short)} R$ more reaches {format_usd(DEX_MINIMUM_ROBUX * RUBUX_TO_USD)}."
            )
        else:
            self.warn_var.set("")

    def copy_text(self):
        return self.big.get() or None


class BuyTool(Tool):
    key, title = "buy", "Buy Robux"
    note = "Pick the package you'd buy — the rate matches the store tier exactly."

    def build(self):
        self.heading()
        self.top_robux = ROBUX_PACKAGES[-1][0]
        pairs = []
        for robux, price in ROBUX_PACKAGES:
            display = f"{robux:,} R$ — ${price:.2f}"
            if robux == self.top_robux:
                display += "  (best value)"
            pairs.append((display, f"{robux}|{price}"))
        self.package_var, _ = self.dropdown_field("Package", pairs, "package",
                                                  default=pairs[-1][1])
        self.usd = self.field("USD", "usd")
        self.robux = self.field("Robux", "robux")
        self.big, self.sub = self.results()
        self.actions()
        self._syncing = False
        self.usd.trace_add("write", lambda *_: self._from_usd())
        self.robux.trace_add("write", lambda *_: self._from_robux())

    def _rate(self):
        """(rate, pack_robux, pack_price) for the selected package.

        Falls back to the smallest package if a remembered value is unusable —
        a hand-edited config must never crash the tool.
        """
        def parse(text):
            parts = text.split("|")
            if len(parts) == 2:
                try:
                    robux_n, price_n = int(parts[0]), float(parts[1])
                except ValueError:
                    return None
                if robux_n > 0 and price_n > 0:
                    return robux_n / price_n, robux_n, price_n
            return None

        result = parse(self.package_var.get())
        if result is None:
            r0, p0 = ROBUX_PACKAGES[0]
            self.package_var.set(f"{r0}|{p0}")
            result = parse(self.package_var.get())
        if result is None:  # cannot happen; extra guard for clarity
            r0, p0 = ROBUX_PACKAGES[0]
            result = r0 / p0, r0, p0
        return result

    def _from_usd(self):
        if self._syncing:
            return
        state, usd = read_amount(self.usd.get())
        robux = usd * self._rate()[0] if state == "ok" else None
        self._syncing = True
        self.robux.set("" if robux is None else format_robux(robux))
        self._syncing = False
        self.refresh(usd=usd)

    def _from_robux(self):
        if self._syncing:
            return
        state, robux = read_amount(self.robux.get())
        usd = robux / self._rate()[0] if state == "ok" else None
        self._syncing = True
        self.usd.set("" if usd is None else format_usd_edit(usd))
        self._syncing = False
        self.refresh(robux=robux)

    def refresh(self, usd=None, robux=None):
        self.mark("usd", read_amount(self.usd.get())[0] == "bad")
        self.mark("robux", read_amount(self.robux.get())[0] == "bad")
        if usd is None and robux is None:
            if not self.usd.get() and not self.robux.get():
                self.big.set("")
                self.sub.set("")
            return
        if usd is None:
            usd = robux / self._rate()[0]
        if robux is None:
            robux = usd * self._rate()[0]
        rate, pack_robux, pack_price = self._rate()
        self.big.set(f"{format_usd(usd)} buys ~{format_num(round(robux))} R$")
        self.sub.set(f"Rate {rate:.1f} R$ per $1.00 "
                     f"({format_num(pack_robux)} R$ pack — ${pack_price:.2f})")

    def copy_text(self):
        return self.big.get() or None


class FeeTool(Tool):
    key, title = "fees", "Marketplace Fees"
    note = f"Roblox takes {MARKETPLACE_FEE:.0%} of most sales. Enter the gross sale to see your cut."

    def build(self):
        self.heading()
        self.gross = self.field("Gross R$", "gross")
        self.big, self.sub = self.results()
        self.actions()

    def refresh(self):
        state, gross = read_amount(self.gross.get())
        self.mark("gross", state == "bad")
        if state != "ok":
            self.big.set("")
            self.sub.set("")
            return
        net = gross * (1 - MARKETPLACE_FEE)
        self.big.set(f"{format_robux(gross)} R$ → {format_robux(net)} R$ after fees")
        self.sub.set(f"Fee: {format_robux(gross * MARKETPLACE_FEE)} R$ · "
                     f"Net ≈ {format_usd(net * RUBUX_TO_USD)} at DevEx rate")

    def copy_text(self):
        return self.big.get() or None


class SplitTool(Tool):
    key, title = "split", "Payout Splitter"
    note = "Equal split of group payouts. The optional cut % is removed first."

    def build(self):
        self.heading()
        self.total = self.field("Total R$", "total")
        self.people = self.field("People", "people")
        self.cut = self.field("Upfront cut %", "cut")
        self.big, self.sub = self.results()
        self.actions()

    def refresh(self):
        state, total = read_amount(self.total.get())
        people_state, people = read_amount(self.people.get())
        self.mark("total", state == "bad")
        self.mark("people", people_state == "bad" or (people is not None and people < 1))
        self.mark("cut", read_amount(self.cut.get())[0] == "bad")
        cut = parse_amount(self.cut.get()) or 0.0
        if total is None or people is None or people < 1:
            self.big.set("")
            self.sub.set("")
            return
        remaining = total * (1 - min(cut, 100.0) / 100.0)
        each = int(remaining // people)
        remainder = remaining - each * people
        self.big.set(f"{format_num(each)} R$ each (×{format_num(people)})")
        extra = f" · {format_num(remainder)} R$ left over" if remainder >= 1 else ""
        self.sub.set(f"{format_robux(remaining)} R$ paid out{extra}")

    def copy_text(self):
        return self.big.get() or None


# ---------------------------------------------------------------------------
# Daily tools
# ---------------------------------------------------------------------------

class PercentTool(Tool):
    key, title = "percent", "Percentages"
    note = ""

    def build(self):
        self.heading()
        self.res1 = self._inline_row(
            [("e", "a_a"), ("t", "% of"), ("e", "a_b"), ("t", "=")])
        self.res2 = self._inline_row(
            [("e", "b_a"), ("t", "is what % of"), ("e", "b_b"), ("t", "→")])
        self.res3 = self._inline_row(
            [("t", "change"), ("e", "c_a"), ("t", "to"), ("e", "c_b"), ("t", "→")])
        self.actions()

    def _inline_row(self, pieces):
        """entries / text labels / bold inline result on one line."""
        row = tk.Frame(self.frame)
        row.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.app.tag(row, bg="card")
        result_var = tk.StringVar()
        for i, piece in enumerate(pieces):
            if piece[0] == "e":
                _, key = piece
                _, entry = self.inline_field(row, key)
                entry.grid(row=0, column=i, padx=3, sticky="ew")
                row.columnconfigure(i, weight=1)
            elif piece[0] == "t":
                lbl = tk.Label(row, text=piece[1], font=("Segoe UI", 10))
                lbl.grid(row=0, column=i, padx=4)
                self.app.tag(lbl, bg="card", fg="muted")
            else:  # inline result
                res = self._result_inline(row, result_var)
                res.grid(row=0, column=i, padx=(10, 0), sticky="e")
        self.row += 1
        return result_var

    def refresh(self):
        for key, reader in (("a_a", read_amount), ("a_b", read_amount),
                            ("b_a", read_amount), ("b_b", read_amount),
                            ("c_a", read_signed), ("c_b", read_signed)):
            self.mark(key, reader(self.vars[key].get())[0] == "bad")
        _, a_pct = read_amount(self.vars["a_a"].get())
        _, a_of = read_amount(self.vars["a_b"].get())
        _, b_part = read_amount(self.vars["b_a"].get())
        _, b_whole = read_amount(self.vars["b_b"].get())
        _, c_from = read_signed(self.vars["c_a"].get())
        _, c_to = read_signed(self.vars["c_b"].get())
        self.res1.set(f"{format_num(a_pct / 100 * a_of)}" if a_pct is not None and a_of is not None else "")
        self.res2.set(f"{format_num(b_part / b_whole * 100)}%" if b_part is not None and b_whole not in (None, 0) else "")
        if c_from is not None and c_to is not None and c_from != 0:
            pct = (c_to - c_from) / abs(c_from) * 100
            self.res3.set(f"{pct:+.2f}% ({'up' if pct >= 0 else 'down'})")
        else:
            self.res3.set("")

    def copy_text(self):
        lines = [self.res1.get(), self.res2.get(), self.res3.get()]
        return " | ".join(x for x in lines if x) or None


class UnitsTool(Tool):
    key, title = "units", "Unit Converter"
    note = "Length, mass, volume, data sizes and temperature — all offline."

    def build(self):
        self.heading()
        categories = list(UNIT_FACTORS)
        self.category_var, self.category_dd = self.dropdown_field(
            "Category", [(cat, cat) for cat in categories], "category",
            default=categories[0])
        self.category_var.trace_add("write", lambda *_: self._on_category())
        self.frm_var, self.frm_dd = self.dropdown_field(
            "From", unit_options(self.category_var.get()), "from")
        self.to_var, self.to_dd = self.dropdown_field(
            "To", unit_options(self.category_var.get()), "to")
        self._on_category()
        self.value = self.field("Value", "value")
        self.big, self.sub = self.results()
        self.actions()

    def _on_category(self):
        opts = unit_options(self.category_var.get())
        values = [v for _, v in opts]
        self.frm_dd.set_options(opts)
        self.to_dd.set_options(opts)
        if self.frm_var.get() not in values:
            self.frm_var.set(values[len(values) // 2] if values else "")
        if self.to_var.get() not in values:
            self.to_var.set(values[-1] if values else "")

    def refresh(self):
        state, value = read_amount(self.value.get())
        self.mark("value", state == "bad")
        result = unit_convert(self.category_var.get(), value,
                              self.frm_var.get(), self.to_var.get())
        if state != "ok" or result is None:
            self.big.set("")
            self.sub.set("")
            return
        self.big.set(f"{format_num(value)} {self.frm_var.get()} = "
                     f"{format_num(result)} {self.to_var.get()}")
        self.sub.set("")

    def clear(self):
        self.value.set("")
        self.refresh()

    def copy_text(self):
        return self.big.get() or None


class DatesTool(Tool):
    key, title = "dates", "Date Calculator"
    note = "Dates as YYYY-MM-DD."

    def build(self):
        self.heading()
        self._build_date_row(
            pieces=[("e", "d1", 12), ("t", "to"), ("e", "d2", 12), ("r", "diff")])
        # Second row reuses the 'd1' var; the pending trace is attached only once.
        self._build_date_row(
            pieces=[("e", "d1b", 12), ("t", "±"), ("e", "ndays", 7), ("r", "add")],
            shared_key="d1")
        self.diff_res = self.vars["diff"]
        self.add_res = self.vars["add"]
        self.actions()

    def _build_date_row(self, pieces, shared_key=None):
        """One inline row of entries + text labels + bold inline result."""
        row = tk.Frame(self.frame)
        row.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.app.tag(row, bg="card")
        for i, piece in enumerate(pieces):
            if piece[0] == "e":
                key, width = piece[1], piece[2]
                if shared_key and key == "d1b":
                    _, entry = self.inline_field(row, key, width=width,
                                                 var=self.vars["d1"], with_trace=False)
                else:
                    _, entry = self.inline_field(row, key, width=width)
                entry.grid(row=0, column=i, padx=3, sticky="ew")
                if key in ("d1", "d2", "d1b"):
                    row.columnconfigure(i, weight=1)
            elif piece[0] == "t":
                lbl = tk.Label(row, text=piece[1], font=("Segoe UI", 10))
                lbl.grid(row=0, column=i, padx=4)
                self.app.tag(lbl, bg="card", fg="muted")
            else:  # inline result
                result_key = piece[1]
                result_var = tk.StringVar()
                self.vars[result_key] = result_var
                res = self._result_inline(row, result_var)
                res.config(anchor="w")
                res.grid(row=0, column=i, padx=(14, 0), sticky="w")
        self.row += 1
        return row

    @staticmethod
    def _parse(text):
        try:
            return date.fromisoformat(text.strip())
        except (ValueError, AttributeError):
            return None

    def refresh(self):
        d1 = self._parse(self.vars["d1"].get())
        d2 = self._parse(self.vars["d2"].get())
        self.mark("d1", self.vars["d1"].get().strip() != "" and d1 is None)
        self.mark("d2", self.vars["d2"].get().strip() != "" and d2 is None)
        if d1 and d2:
            days = (d2 - d1).days
            direction = " (reversed order)" if days < 0 else ""
            self.diff_res.set(f"{abs(days):,} days between{direction} · {d2:%A}")
        else:
            self.diff_res.set("")
        n_state, n = read_signed(self.vars["ndays"].get())
        self.mark("ndays", n_state == "bad")
        if d1 and n is not None:
            result = d1 + timedelta(days=n)
            self.add_res.set(f"{result:%Y-%m-%d} · {result:%A}")
        else:
            self.add_res.set("")

    def copy_text(self):
        pieces = [t for t in (self.diff_res.get(), self.add_res.get()) if t]
        return " · ".join(pieces) or None


class LoanTool(Tool):
    key, title = "loan", "Loan / Growth"
    note = "Standard amortized payment; rate as APR %."

    def build(self):
        self.heading()
        self.principal = self.field("Amount ($)", "principal")
        self.rate = self.field("APR %", "rate")
        self.years = self.field("Years", "years")
        self.big, self.sub = self.results()
        self.actions()

    def refresh(self):
        for key, reader in (("principal", read_amount), ("rate", read_amount),
                            ("years", read_amount)):
            self.mark(key, reader(getattr(self, key).get())[0] == "bad")
        principal = parse_amount(self.principal.get())
        pay = monthly_payment(principal, parse_amount(self.rate.get()),
                              parse_amount(self.years.get()))
        if pay is None:
            self.big.set("")
            self.sub.set("")
            return
        total = pay * int(float(self.years.get()) * 12)
        self.big.set(f"{format_usd(pay)} / month")
        self.sub.set(f"Total paid: {format_usd(total)} · "
                     f"Interest: {format_usd(total - principal)}")

    def copy_text(self):
        joined = " · ".join(x for x in (self.big.get(), self.sub.get()) if x)
        return joined or None


class ZoneTool(Tool):
    key, title = "zones", "Time Zones"
    note = TIMEZONE_FALLBACK_NOTE

    def build(self):
        self.heading()
        zones = [(z, z) for z in TIMEZONES]
        self.zone_a_var, _ = self.dropdown_field("From zone", zones, "zone_a",
                                                 default=TIMEZONES[1])
        self.zone_b_var, _ = self.dropdown_field("To zone", zones, "zone_b",
                                                 default="Asia/Tokyo")
        self.when = self.field("When (YYYY-MM-DD HH:MM, blank = now)", "when")
        self.big, self.sub = self.results()
        self.actions()

    def clear(self):
        self.when.set("")
        self.refresh()

    def refresh(self):
        a_name, b_name = self.vars["zone_a"].get(), self.vars["zone_b"].get()
        text = self.when.get().strip()
        moment, parsed_ok = self._moment(a_name, text)
        converted = self._to_zone(moment, b_name)
        minutes = int((converted.utcoffset() - moment.utcoffset()).total_seconds() // 60)
        if minutes == 0:
            diff_text = "same time"
        else:
            hours, mins = divmod(abs(minutes), 60)
            diff_text = (f"+{hours}h{mins:02d} ahead" if minutes > 0
                         else f"−{hours}h{mins:02d} behind")
        a_short = a_name.split("/")[-1].replace("_", " ")
        b_short = b_name.split("/")[-1].replace("_", " ")
        self.big.set(f"{converted:%H:%M} in {b_short} · {diff_text}")
        extra = f" · {converted:%Y-%m-%d}"
        hint = " · couldn't read that time — showing now" if text and not parsed_ok else ""
        self.sub.set(f"{moment:%Y-%m-%d %H:%M} in {a_short}{extra}{hint}")
        self.mark("when", bool(text) and not parsed_ok)

    @staticmethod
    def _moment(zone_name, text):
        moment, parsed_ok = None, True
        if text:
            naive = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%H:%M"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    naive = parsed if fmt != "%H:%M" else datetime.combine(date.today(), parsed.time())
                    break
                except ValueError:
                    continue
            if naive is None:
                parsed_ok = False
            else:
                if zone_name == LOCAL_ZONE:
                    naive = naive.replace(tzinfo=datetime.now().astimezone().tzinfo)
                else:
                    naive = naive.replace(tzinfo=get_zone(zone_name))
                moment = naive
        if moment is None:
            if zone_name == LOCAL_ZONE:
                moment = datetime.now().astimezone()
            else:
                moment = datetime.now(get_zone(zone_name) or timezone.utc)
        return moment, parsed_ok

    @staticmethod
    def _to_zone(moment, zone_name):
        if zone_name == LOCAL_ZONE:
            return moment.astimezone(datetime.now().astimezone().tzinfo)
        return moment.astimezone(get_zone(zone_name) or timezone.utc)

    def copy_text(self):
        joined = " · ".join(x for x in (self.big.get(), self.sub.get()) if x)
        return joined or None


class BaseTool(Tool):
    key, title = "base", "Number Bases"
    note = "Enter a value in one base; see it in all four."

    BASES = [("2 (binary)", 2), ("8 (octal)", 8), ("10 (decimal)", 10), ("16 (hex)", 16)]

    def build(self):
        self.heading()
        pairs = [(label, str(base)) for label, base in self.BASES]
        self.base_var, _ = self.dropdown_field("Input base", pairs, "base", default="10")
        self.value = self.field("Value", "value")
        self.big, self.sub = self.results()
        self.actions()

    def refresh(self):
        text = self.value.get().strip()
        # Old configs remembered the menu LABEL ("2 (binary)"); new ones store
        # the bare base ("2"). Accept both so a stale config never crashes.
        raw = self.base_var.get() or "10"
        digits = "".join(ch for ch in raw if ch.isdigit())
        base = int(digits) if digits and int(digits) in (2, 8, 10, 16) else 10
        if self.base_var.get() != str(base):
            self.base_var.set(str(base))
        try:
            value = int(text, base)
        except ValueError:
            value = None
        self.mark("value", bool(text) and value is None)
        if not text or value is None:
            self.big.set("")
            self.sub.set("")
            return
        self.big.set(f"Decimal: {value:,}")
        self.sub.set(f"Hex {value:X} · Oct {value:o} · Bin {value:b}")

    def clear(self):
        self.value.set("")
        self.refresh()

    def copy_text(self):
        joined = " · ".join(x for x in (self.big.get(), self.sub.get()) if x)
        return joined or None


# ---------------------------------------------------------------------------
# Application shell
# ---------------------------------------------------------------------------

class App:
    TOOLS = [DevExTool, BuyTool, FeeTool, SplitTool, PercentTool,
             UnitsTool, DatesTool, LoanTool, ZoneTool, BaseTool]

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.theme = config.get("theme") if config.get("theme") in THEMES else "dark"
        self.tags = []       # [widget, bg_role, fg_role, kind]
        self.buttons = []    # RoundedButtons
        self.dropdowns = []  # themed Dropdown widgets
        self.tools = {}
        self.tab_buttons = {}
        self.current_key = None
        self._status_job = None
        self._colors = dict(THEMES[self.theme])
        self.fx = FX(root)
        self._window_size = None

        root.title(APP_TITLE)
        root.minsize(700, 460)
        self._build_shell()
        self._start_aurora()      # canvas first so the tool cards stack above it
        self._build_tools()
        self._paint(self._colors)
        self._apply_windows_chrome()

        # Only restore fields that were actually saved so dropdowns keep defaults.
        inputs = config.get("inputs", {})
        for tool_key, tool in self.tools.items():
            saved = inputs.get(tool_key, {})
            for field_key, var in tool.vars.items():
                if field_key in saved:
                    var.set(saved[field_key] or "")
        for tool in self.tools.values():  # populate default results (e.g. zones = now)
            tool.refresh()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.select_tool(config.get("tool") if config.get("tool") in self.tools else "devex")

    # -- theme registry -----------------------------------------------------
    def tag(self, widget, bg=None, fg=None, kind=None):
        self.tags.append([widget, bg, fg, kind])

    @property
    def colors(self):
        return self._colors

    def apply_theme(self, theme_name):
        """Cross-fade the palette over ~260ms, then settle exactly on target."""
        target = THEMES[theme_name]
        self.theme = theme_name
        start = dict(self._colors)
        if start == target:
            self._colors = dict(target)
            self._paint(self._colors)
        else:
            def step(t):
                self._colors = {
                    k: (mix(start[k], target[k], t)
                        if isinstance(start[k], str) and isinstance(target[k], str)
                        else target[k])  # hover_up is a flag, not a color
                    for k in target}
                self._paint(self._colors)
            def done():
                self._colors = dict(target)
                self._paint(target)
            self.fx.start("themefade", 260, step, done=done)
        self.config["theme"] = theme_name
        save_config(self.collect_config())

    def toggle_theme(self):
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def _paint(self, c):
        """Apply a full color dictionary to every registered widget."""
        self.root.configure(bg=c["bg"])
        for widget, bg, fg, kind in self.tags:
            try:
                if kind == "entry":
                    widget.configure(bg=c["entry"], fg=c["fg"], insertbackground=c["fg"],
                                     disabledforeground=c["muted"],
                                     highlightbackground=c["border"],
                                     highlightcolor=c["accent"])
                else:
                    if bg:
                        widget.configure(bg=c[bg])
                    if fg and isinstance(widget, tk.Label):
                        widget.configure(fg=c[fg])
            except tk.TclError:
                pass
        for button in self.buttons:
            button.retheme(c)
        for dd in self.dropdowns:
            dd.retheme(c)
        for tool in self.tools.values():
            tool.retheme(c)
        self.theme_btn.set_text("☀ Light" if self.theme == "dark" else "☾ Dark")

    # -- Windows chrome -------------------------------------------------------
    def _apply_windows_chrome(self):
        """Match the OS title bar caption color to the app theme (Win11)."""
        if os.name != "nt" or not getattr(ctypes, "windll", None):
            return
        try:
            r, g, b = hex_to_rgb(self._colors.get("side", "#12151b"))
            caption = ctypes.c_int((b << 16) | (g << 8) | r)
            tr, tg, tb = hex_to_rgb(self._colors.get("fg", "#e8ebf3"))
            caption_text = ctypes.c_int((tb << 16) | (tg << 8) | tr)
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            dark = 1 if self.theme == "dark" else 0
            for attr, value in ((20, ctypes.c_int(dark)),   # dark titlebar text
                                (19, ctypes.c_int(dark)),   # pre-1903 fallback
                                (35, caption),              # caption color
                                (36, caption_text)):        # caption text color
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr,
                                                           ctypes.byref(value), 4)
        except Exception:
            pass  # older Windows — default chrome is fine

    # -- aurora background ----------------------------------------------------
    def _start_aurora(self):
        """Slow drifting glow behind the tool cards (canvas-drawn, no shaders)."""
        self.aurora = tk.Canvas(self.content, bd=0, highlightthickness=0)
        self.aurora.pack(fill="both", expand=True)

        def drift(t):
            self._draw_aurora(t)
        self.fx.start("aurora", 12000, drift, loop=True)

    def _draw_aurora(self, t):
        cv = self.aurora
        cv.delete("all")
        c = self._colors
        cv.config(bg=c["bg"])
        w = max(cv.winfo_width(), 10)
        h = max(cv.winfo_height(), 10)
        strength = 0.55
        for cx, cy, color, phase in ((0.30, 0.30, c["glow1"], 0.0),
                                     (0.78, 0.68, c["glow2"], 2.1)):
            dx = math.sin((t * 2 + phase) * 6.283) * w * 0.06
            dy = math.cos((t * 3 + phase) * 6.283) * h * 0.07
            rx, ry = w * 0.42, h * 0.52
            for i in range(1, 11):
                fade = strength * (1 - i / 10) ** 1.4
                cv.create_oval(cx * w + dx - rx * i / 10, cy * h + dy - ry * i / 10,
                               cx * w + dx + rx * i / 10, cy * h + dy + ry * i / 10,
                               fill=mix(c["bg"], color, fade), width=0)

    # -- layout ---------------------------------------------------------------
    def _build_shell(self):
        header = tk.Frame(self.root, padx=16, pady=12)
        header.pack(fill="x")
        self.tag(header, bg="side")
        title_lbl = tk.Label(header, text="⚡ Dev Toolkit", font=("Segoe UI", 13, "bold"))
        title_lbl.pack(side="left")
        self.tag(title_lbl, bg="side", fg="fg")
        ver_lbl = tk.Label(header, text=f"v{VERSION} · offline & private",
                           font=("Segoe UI", 9))
        ver_lbl.pack(side="left", padx=(10, 0))
        self.tag(ver_lbl, bg="side", fg="muted")
        self.theme_btn = RoundedButton(self, header, "☀ Light", self.toggle_theme,
                                       width=86, height=28, role="ghost",
                                       font=("Segoe UI", 9), canvas_role="side")
        self.theme_btn.pack(side="right")
        self.header_frame = header

        self.sidebar = tk.Frame(self.root, padx=10, pady=12)
        self.sidebar.pack(side="left", fill="y")
        self.tag(self.sidebar, bg="side")

        self.content = tk.Frame(self.root)
        self.content.pack(side="right", fill="both", expand=True)
        self.tag(self.content, bg="bg")

        self.status = tk.Label(self.root, text="", font=("Segoe UI", 9), anchor="e")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        self.tag(self.status, bg="status", fg="muted")

    def _build_tools(self):
        for tool_cls in self.TOOLS:
            self.tools[tool_cls.key] = tool_cls(self, self.content)
        for idx, tool_cls in enumerate(self.TOOLS):
            label = f"{(idx + 1) % 10}  {tool_cls.title}"
            btn = RoundedButton(self, self.sidebar, label,
                                lambda k=tool_cls.key: self.select_tool(k),
                                width=150, height=30, role="tab", font=("Segoe UI", 9, "bold"),
                                canvas_role="side")
            btn.pack(fill="x", pady=2)
            self.tab_buttons[tool_cls.key] = btn
        hint = tk.Label(self.sidebar, text="Ctrl+1–0 switch\nEnter copy · Esc clear",
                        font=("Segoe UI", 8), justify="left")
        hint.pack(side="bottom", pady=(8, 0))
        self.tag(hint, bg="side", fg="muted")

    def _fit_window(self):
        """Size the window to the active card so nothing clips at 150% DPI too."""
        tool = self.current()
        self.root.update_idletasks()
        card_w = max(tool.frame.winfo_reqwidth(), 560)
        card_h = tool.frame.winfo_reqheight()
        if card_h < 40 or not card_w:
            self.root.after(40, self._fit_window)
            return
        width = max(700, self.sidebar.winfo_reqwidth() + card_w + 60)
        height = (self.header_frame.winfo_reqheight() + card_h +
                  self.status.winfo_reqheight() + 52)
        self._window_size = (width, height)
        self.root.geometry(f"{width}x{height}")
        tool.frame.place_configure(width=max(300, self.content.winfo_width() - 12),
                                   height=card_h)

    # -- tool switching / actions ----------------------------------------------
    def current(self):
        return self.tools[self.current_key]

    def select_tool(self, key):
        if key == self.current_key or key not in self.tools:
            return
        old_key, self.current_key = self.current_key, key
        tool = self.tools[key]
        # Sliding transition: exit-left for the old card, enter-from-right for the new.
        if old_key:
            self.collect_inputs(old_key)
            old = self.tools[old_key]
            old_x = int(old.frame.place_info()["x"] or 6)
            def slide_out(t):
                old.frame.place_configure(x=old_x - int(30 * t))
            self.fx.start(f"out{old_key}", 140, slide_out,
                          done=lambda: old.frame.place_forget())
            self.tab_buttons[old_key].role = "tab"
            self.tab_buttons[old_key].retheme(self.colors)
        tool.frame.place(in_=self.content, x=36, y=6, bordermode="outside")

        def slide_in(t):
            try:
                tool.frame.place_configure(x=6 + int(30 * (1 - t)))
            except tk.TclError:
                pass
        self.fx.start(f"in{key}", 170, slide_in)
        self.tab_buttons[key].role = "tab_active"
        self.tab_buttons[key].retheme(self.colors)
        tool.animate_entry()
        self.config["tool"] = key
        save_config(self.collect_config())
        self._fit_window()
        self.root.after(80, self._fit_window)  # second pass once fully mapped
        self.root.after(80, lambda: (tool.focus_primary(), self._apply_windows_chrome()))

    def collect_inputs(self, tool_key):
        saved = self.config.setdefault("inputs", {}).setdefault(tool_key, {})
        for field_key, var in self.tools[tool_key].vars.items():
            saved[field_key] = var.get()

    def collect_config(self):
        for key in self.tools:  # every tool's fields, so switching is not required
            self.collect_inputs(key)
        return self.config

    def copy_current(self):
        text = self.current().copy_text()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.flash("Copied to clipboard")
        else:
            self.flash("Nothing to copy")

    def clear_current(self):
        self.current().clear()
        self.flash("Cleared")

    def flash(self, message):
        if self._status_job:
            self.root.after_cancel(self._status_job)
        self.status.config(text=message)
        self._status_job = self.root.after(1600, lambda: self.status.config(text=""))

    def _bind_keys(self):
        for idx, tool_cls in enumerate(self.TOOLS):
            self.root.bind(f"<Control-Key-{(idx + 1) % 10}>",
                           lambda _e, k=tool_cls.key: self.select_tool(k))
        self.root.bind("<Escape>", lambda _e: self.clear_current())
        self.root.bind("<Return>", lambda _e: self.copy_current())
        self.root.bind_class("Entry", "<Control-a>",
                             lambda e: (e.widget.select_range(0, "end"),
                                        e.widget.icursor("end"), "break")[2])

    def on_close(self):
        save_config(self.collect_config())
        self.root.destroy()


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    App(root, load_config())
    root.mainloop()


def enable_dpi_awareness():
    """Crisp text on high-DPI displays. Must run before the Tk root exists."""
    if os.name != "nt" or not getattr(ctypes, "windll", None):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


if __name__ == "__main__":
    main()
