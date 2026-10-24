#!/usr/bin/env python3
"""
Roblox Dev & Daily Toolkit v2.2 (single-file, offline)
------------------------------------------------------
One window, ten live calculators with a modern dark/light UI:

  Roblox:  DevEx cash-out | Buy Robux | Marketplace fees | Payout splitter
  Daily:   Percentages | Units | Dates | Loans | Time zones | Number bases

- Zero pip installs, zero network / telemetry; settings saved locally as JSON
- Dark theme by default, light toggle with cross-fade; DPI-aware on Windows
- Effects: aurora glow behind cards, gradient heading wash, eased hovers,
  slide-in tool transitions, pulsing DevEx warning
- "Reduce motion" toggle (persisted) turns every effect into an instant swap
- Keyboard: Ctrl+1..0 tools, Ctrl+T theme, Ctrl+M motion, Enter copies,
  Esc clears, Ctrl+A selects all
"""

import ctypes
import json
import math
import os
import time
import tkinter as tk
from tkinter import font as tkfont
from calendar import monthrange
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
VERSION = "2.2"

FRAME_MS = 16            # ~60 fps for the shared animation timer
AURORA_RINGS = 5         # rings per drifting blob (was 10 — half the redraw cost)
THEME_FADE_MS = 240      # theme cross-fade duration
THEME_FADE_STEPS = 10    # deliberate steps (not one repaint per 16 ms frame)

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
    "Area": {  # base unit: square meter
        "cm²": 0.0001, "m²": 1.0, "km²": 1_000_000.0,
        "ft²": 0.09290304, "yd²": 0.83612736,
        "acre": 4046.8564224, "ha": 10_000.0,
    },
    "Speed": {  # base unit: meter / second
        "m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "knot": 0.514444,
    },
    "Energy": {  # base unit: joule
        "J": 1.0, "kJ": 1000.0, "cal": 4.184, "kcal": 4184.0,
        "Wh": 3600.0, "kWh": 3_600_000.0,
    },
    "Pressure": {  # base unit: pascal
        "Pa": 1.0, "kPa": 1000.0, "bar": 100_000.0,
        "psi": 6894.757293168, "atm": 101_325.0,
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
    "Area": {"cm²": "Square centimeters", "m²": "Square meters",
             "km²": "Square kilometers", "ft²": "Square feet",
             "yd²": "Square yards", "acre": "Acres", "ha": "Hectares"},
    "Speed": {"m/s": "Meters/second", "km/h": "Kilometers/hour",
              "mph": "Miles/hour", "knot": "Knots"},
    "Energy": {"J": "Joules", "kJ": "Kilojoules", "cal": "Calories",
               "kcal": "Kilocalories", "Wh": "Watt-hours", "kWh": "Kilowatt-hours"},
    "Pressure": {"Pa": "Pascals", "kPa": "Kilopascals", "bar": "Bar",
                 "psi": "Pounds/square inch", "atm": "Atmospheres"},
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
        "fg": "#e8ebf3", "muted": "#8a92a6", "accent": "#2b63f0",
        "accent_fg": "#ffffff", "warning": "#f0b357", "invalid": "#e0685f",
        "glow1": "#2b4f8f", "glow2": "#46357f",
        "hover_up": True, "status": "#12151b",
    },
    "light": {
        "bg": "#eef1f7", "side": "#e5eaf2", "card": "#ffffff",
        "entry": "#ffffff", "border": "#d2d9e6", "hover": "#e8edf5",
        "fg": "#12161f", "muted": "#4f5868", "accent": "#2563eb",
        "accent_fg": "#ffffff", "warning": "#b45309", "invalid": "#c94b3f",
        "glow1": "#cfddff", "glow2": "#e3dcff",
        "hover_up": False, "status": "#e5eaf2",
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


def add_months(start, months):
    """Calendar-add months, clamping the day to the target month's length."""
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    day = min(start.day, monthrange(y, m)[1])
    return date(y, m, day)


def business_days_between(d1, d2):
    """Mon–Fri days in the half-open interval (start, end]; signed result."""
    sign = 1 if d2 >= d1 else -1
    a, b = (d1, d2) if d2 >= d1 else (d2, d1)
    weeks, rem = divmod((b - a).days, 7)
    count = weeks * 5
    for i in range(rem):
        if (a + timedelta(days=i + 1)).weekday() < 5:
            count += 1
    return sign * count


def add_business_days(start, n):
    """Move forward/back by n weekdays (Mon–Fri, weekends skipped)."""
    step = 1 if n >= 0 else -1
    remaining = abs(int(n))
    current = start
    while remaining:
        current += timedelta(days=step)
        if current.weekday() < 5:
            remaining -= 1
    return current


def years_between(start, end):
    """(years, months, days) between two dates, calendar-accurate."""
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    if days < 0:
        months -= 1
        days += (date(end.year, end.month, 1) - timedelta(days=1)).day
    if months < 0:
        years -= 1
        months += 12
    return years, months, days


def cheapest_package_plan(target_robux):
    """Cheapest combination of store packages covering at least target_robux.

    Returns {'robux': int, 'cents': int, 'parts': [(pack_robux, count), ...]}
    or None when the target is unusable. Exact DP over 100 R$ units; capped so
    a runaway entry cannot freeze the UI.
    """
    try:
        target = float(target_robux)
    except (TypeError, ValueError):
        return None
    if target <= 0 or target > 10_000_000:
        return None
    target_units = int(math.ceil(target / 100.0))
    items = []
    for robux, price in ROBUX_PACKAGES:
        units = int(round(robux / 100.0))
        cents = int(round(price * 100))
        if units > 0 and cents > 0:
            items.append((units, cents, robux))
    if not items:
        return None
    max_units = max(u for u, _c, _r in items)
    limit = target_units + max_units
    inf = float("inf")
    dp = [inf] * (limit + 1)
    prev = [None] * (limit + 1)
    dp[0] = 0
    for u in range(limit + 1):
        base = dp[u]
        if base == inf:
            continue
        for units, cents, _robux in items:
            nu = u + units
            if nu <= limit and base + cents < dp[nu]:
                dp[nu] = base + cents
                prev[nu] = (u, units)
    best = min((u for u in range(target_units, limit + 1) if dp[u] < inf),
               key=lambda u: (dp[u], u))
    counts = {}
    u = best
    while u > 0:
        pu, units = prev[u]
        counts[units] = counts.get(units, 0) + 1
        u = pu
    parts = [(robux, counts[units]) for units, _c, robux in items if counts.get(units)]
    parts.sort(reverse=True)
    return {"robux": best * 100, "cents": int(dp[best]), "parts": parts}


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
    """Read persisted settings, validating every key (a hand-edited or older
    config file must never crash the app)."""
    defaults = {"theme": "dark", "tool": "devex", "inputs": {}, "reduce_motion": False}
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    if data.get("theme") in THEMES:
        defaults["theme"] = data["theme"]
    if isinstance(data.get("tool"), str):
        defaults["tool"] = data["tool"]
    if isinstance(data.get("reduce_motion"), bool):
        defaults["reduce_motion"] = data["reduce_motion"]
    inputs = data.get("inputs")
    if isinstance(inputs, dict):
        clean = {}
        for tool_key, fields in inputs.items():
            if not isinstance(tool_key, str) or not isinstance(fields, dict):
                continue
            clean[tool_key] = {k: v for k, v in fields.items()
                               if isinstance(k, str) and isinstance(v, str)}
        defaults["inputs"] = clean
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
    """~60 fps after-loop: each animation gets eased progress 0..1 (or loops).

    Every step is isolated: a widget that disappears mid-animation (tool
    switch, theme change, window close) drops that animation instead of killing
    the whole tick. Timing comes from perf_counter, so a late frame never
    slows the animation down.
    """

    def __init__(self, root):
        self.root = root
        self.active = []   # [key, t0, dur, step, done, loop]
        self.running = False
        self._job = None

    def start(self, key, dur, step, done=None, loop=False):
        self.cancel(key)
        self.active.append([key, time.perf_counter() * 1000.0, dur, step, done, loop])
        if not self.running:
            self.running = True
            self._schedule()

    def cancel(self, key):
        self.active = [a for a in self.active if a[0] != key]

    def keys(self):
        return [a[0] for a in self.active]

    def stop(self):
        """Stop everything (window closing) and cancel the pending tick."""
        self.active = []
        self.running = False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _schedule(self):
        try:
            self._job = self.root.after(FRAME_MS, self._tick)
        except tk.TclError:
            self._job = None
            self.running = False

    def _tick(self):
        self._job = None
        try:
            now = time.perf_counter() * 1000.0
            snapshot = list(self.active)
            still = []
            for key, t0, dur, step, done, loop in snapshot:
                elapsed = now - t0
                if loop:
                    try:
                        step((elapsed / max(dur, 1)) % 1.0)
                        still.append([key, t0, dur, step, done, loop])
                    except tk.TclError:
                        pass  # one vanished widget must not stop the loop
                    continue
                t = min(1.0, elapsed / max(dur, 1))
                try:
                    step(ease_out(t))
                except tk.TclError:
                    continue  # widget vanished mid-animation — drop this anim
                if t < 1.0:
                    still.append([key, t0, dur, step, done, loop])
                elif done:
                    try:
                        done()
                    except tk.TclError:
                        pass
            # Animations started from a done() callback must survive this tick.
            added = [a for a in self.active if all(a is not b for b in snapshot)]
            self.active = still + added
            if self.active:
                self._schedule()
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
        self._fg = ""
        self._shape = None
        self._label = None
        self._draw_sig = None
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

    def _set_fill(self, color):
        if self._shape is not None:
            try:
                self.itemconfig(self._shape, fill=color)
            except tk.TclError:
                pass

    def _on_enter(self, _e):
        self.configure(cursor="hand2")
        if self.app.reduce_motion:
            self.app.fx.cancel(self._fx_key)
            self._set_fill(self._hover_target())
            return
        self.app.fx.start(self._fx_key, 110, lambda t: self._set_fill(
            mix(self._base, self._hover_target(), t)))

    def _on_leave(self, _e):
        self.configure(cursor="")
        if self.app.reduce_motion:
            self.app.fx.cancel(self._fx_key)
            self._set_fill(self._base)
            return
        self.app.fx.start(self._fx_key, 130, lambda t: self._set_fill(
            mix(self._hover_target(), self._base, t)))

    def _press(self, _e):
        self._set_fill(self._hover_target())
        self.command()

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:  # not mapped yet — use requested size
            try:
                w, h = int(self["width"]), int(self["height"])
            except (ValueError, tk.TclError):
                w, h = 120, 32
        w, h = max(w, 12), max(h, 12)
        sig = (w, h, self._base, self._fg, self.text)
        if sig == self._draw_sig and self._shape is not None:
            return  # spurious <Configure> — nothing changed
        self._draw_sig = sig
        self.delete("all")
        r = min(14, h // 2)
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h,
               w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        self._shape = self.create_polygon(pts, smooth=True, fill=self._base, outline="")
        self._label = self.create_text(w // 2, h // 2, text=self.text, fill=self._fg,
                                       font=self.font)

    def set_text(self, text):
        self.text = text
        if self._label is not None:
            try:
                self.itemconfig(self._label, text=text)
            except tk.TclError:
                pass


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

    # -- change plumbing -----------------------------------------------------
    def _changed(self):
        """One trace path: refresh once, then let the shell re-measure."""
        self.refresh()
        self.app.schedule_fit()

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
        try:
            cv.delete("all")
            w = max(self.frame.winfo_reqwidth(), cv.winfo_width(), 400)
            h = int(cv["height"])
        except tk.TclError:
            return
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
        try:
            h = self.glow.winfo_height()
        except tk.TclError:
            return
        if self.app.reduce_motion:
            try:
                self.glow.coords(self.badge, 6, h - 4, 98, h - 1)
            except tk.TclError:
                pass
            return

        def step(t):
            try:
                self.glow.coords(self.badge, 6, self.glow.winfo_height() - 4,
                                 6 + 92 * t, self.glow.winfo_height() - 1)
            except tk.TclError:
                pass

        def done():
            try:
                self.glow.coords(self.badge, 6, self.glow.winfo_height() - 4,
                                 98, self.glow.winfo_height() - 1)
            except tk.TclError:
                pass
        self.app.fx.start(f"badge{self.key}", 240, step, done=done)

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

    def _register(self, key, var, entry=None, trace=True):
        self.vars[key] = var
        if entry is not None:
            self.entries[key] = entry
        if trace:
            self._pending_traces.append((var, lambda *_: self._changed()))
        if self.primary is None and entry is not None:
            self.primary = entry
        return var

    def field(self, label, key, width=None, trace=True):
        """Labeled entry row returning the StringVar; refresh() runs on edit."""
        lbl = tk.Label(self.frame, text=label, font=("Segoe UI", 10))
        lbl.grid(row=self.row, column=0, sticky="w", pady=(8, 0), padx=(0, 12))
        self.app.tag(lbl, bg="card", fg="muted")
        var = tk.StringVar()
        entry = self._make_entry(self.frame, var)
        if width:
            entry.configure(width=width)
        entry.grid(row=self.row, column=1, sticky="ew", pady=(8, 0), ipady=3)
        self._register(key, var, entry, trace=trace)
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
            self._pending_traces.append((var, lambda *_: self._changed()))
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
        self._pending_traces.append((var, lambda *_: self._changed()))
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

    def extra_line(self, fg="accent"):
        """Third result line for secondary summaries (payoff, cheapest plan…)."""
        row = self.row + 1
        var = tk.StringVar()
        lbl = tk.Label(self.frame, textvariable=var, font=("Segoe UI", 9),
                       anchor="w", justify="left", wraplength=560)
        lbl.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.app.tag(lbl, bg="card", fg=fg)
        self.row = row
        self.extra = var
        return var

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
            if self.app.reduce_motion:
                self.app.fx.cancel(f"warn{self.key}")
                try:
                    self.warn_lbl.config(fg=self.app.colors["warning"])
                except tk.TclError:
                    pass
            else:
                self._start_warn_pulse()
        else:
            self.app.fx.cancel(f"warn{self.key}")
            try:
                self.warn_lbl.config(fg=self.app.colors["warning"])
            except tk.TclError:
                pass

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
        RoundedButton(self.app, row, "Copy all", self.app.copy_all_current,
                      width=84, height=30, role="ghost", font=("Segoe UI", 9))
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
            entry.configure(highlightbackground=c["invalid"],
                            highlightcolor=c["invalid"])
        else:
            self._invalid.discard(key)
            entry.configure(highlightbackground=c["border"],
                            highlightcolor=c["accent"])

    def apply_invalid(self, c):
        for key in self._invalid:
            entry = self.entries.get(key)
            if entry is not None:
                try:
                    entry.configure(highlightbackground=c["invalid"],
                                    highlightcolor=c["invalid"])
                except tk.TclError:
                    pass

    def focus_primary(self):
        if self.primary and self.primary.winfo_ismapped():
            self.primary.focus_set()
            self.primary.select_range(0, "end")

    # -- per-tool interface --------------------------------------------------
    def build(self):
        raise NotImplementedError

    def refresh(self):
        pass

    def retheme(self, c, glow=True):
        if glow:
            self._draw_glow()
        self.apply_invalid(c)

    def copy_text(self):
        return None

    def copy_all_text(self):
        """Everything useful on screen, one item per line."""
        lines = []
        for name in ("big", "sub", "extra", "warn_var"):
            var = getattr(self, name, None)
            if isinstance(var, tk.StringVar):
                text = var.get().strip()
                if text:
                    lines.append(text)
        return "\n".join(lines) or (self.copy_text() or None)

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
    HINT = "Enter Robux earned (or USD) to see the cash-out."

    def build(self):
        self.heading()
        # No generic refresh traces: the two custom handlers below are the one
        # trace path for both fields, so each keystroke refreshes exactly once.
        self.robux = self.field("Robux", "robux", trace=False)
        self.usd = self.field("USD", "usd", trace=False)
        self.big, self.sub = self.results()
        self.warning_line()
        self.actions()
        self._syncing = False
        self.robux.trace_add("write", lambda *_: self._from_robux())
        self.usd.trace_add("write", lambda *_: self._from_usd())

    def _from_robux(self):
        if self._syncing:
            return
        state, robux = read_amount(self.robux.get())
        self._syncing = True
        self.usd.set(format_usd_edit(robux * RUBUX_TO_USD) if state == "ok" else "")
        self._syncing = False
        self._show(robux if state == "ok" else None)

    def _from_usd(self):
        if self._syncing:
            return
        state, usd = read_amount(self.usd.get())
        self._syncing = True
        self.robux.set(format_robux(usd / RUBUX_TO_USD) if state == "ok" else "")
        self._syncing = False
        self._show(usd / RUBUX_TO_USD if state == "ok" else None)

    def refresh(self):
        """Load/clear path: derive from whichever field holds a valid value."""
        r_state, robux = read_amount(self.robux.get())
        u_state, usd = read_amount(self.usd.get())
        if r_state == "ok":
            self._show(robux)
        elif u_state == "ok":
            self._show(usd / RUBUX_TO_USD)
        else:
            self._show(None)

    def _show(self, robux):
        self.mark("robux", read_amount(self.robux.get())[0] == "bad")
        self.mark("usd", read_amount(self.usd.get())[0] == "bad")
        if robux is None:
            self.big.set("")
            self.warn_var.set("")
            self.sub.set("" if (self.robux.get() or self.usd.get()) else self.HINT)
            self.app.schedule_fit()
            return
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
        self.app.schedule_fit()

    def copy_text(self):
        return self.big.get() or None


class BuyTool(Tool):
    key, title = "buy", "Buy Robux"
    note = "Pick the package you'd buy — the rate matches the store tier exactly."
    HINT = "Pick a package, then type USD or Robux — both stay in sync."

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
        self.usd = self.field("USD", "usd", trace=False)
        self.robux = self.field("Robux", "robux", trace=False)
        self.want = self.field("Want at least R$", "want")
        self.big, self.sub = self.results()
        self.extra = self.extra_line()
        self.actions()
        self._syncing = False
        self._fixing = False
        self.usd.trace_add("write", lambda *_: self._from_usd())
        self.robux.trace_add("write", lambda *_: self._from_robux())

    # -- package handling ----------------------------------------------------
    def _package(self):
        """(rate, pack_robux, pack_price) — pure; never mutates the var."""
        parts = (self.package_var.get() or "").split("|")
        if len(parts) == 2:
            try:
                robux_n, price_n = int(parts[0]), float(parts[1])
            except ValueError:
                pass
            else:
                if robux_n > 0 and price_n > 0:
                    return robux_n / price_n, robux_n, price_n
        r0, p0 = ROBUX_PACKAGES[0]  # safe fallback for a hand-edited config
        return r0 / p0, r0, p0

    def _rate(self):
        return self._package()[0]

    def _sanitize_package(self):
        """Reset an unusable remembered package. Guarded against trace recursion."""
        valid = {f"{r}|{p}" for r, p in ROBUX_PACKAGES}
        if self.package_var.get() in valid or self._fixing:
            return
        self._fixing = True
        r0, p0 = ROBUX_PACKAGES[0]
        try:
            self.package_var.set(f"{r0}|{p0}")
        finally:
            self._fixing = False

    def _from_usd(self):
        if self._syncing:
            return
        state, usd = read_amount(self.usd.get())
        self._syncing = True
        self.robux.set(format_robux(usd * self._rate()) if state == "ok" else "")
        self._syncing = False
        self.refresh()

    def _from_robux(self):
        if self._syncing:
            return
        state, robux = read_amount(self.robux.get())
        self._syncing = True
        self.usd.set(format_usd_edit(robux / self._rate()) if state == "ok" else "")
        self._syncing = False
        self.refresh()

    def refresh(self):
        self._sanitize_package()
        u_state, usd = read_amount(self.usd.get())
        r_state, robux = read_amount(self.robux.get())
        self.mark("usd", u_state == "bad")
        self.mark("robux", r_state == "bad")
        self._update_cheapest()
        rate, pack_robux, pack_price = self._package()
        if usd is None and robux is None:
            self.big.set("")
            self.sub.set("" if (self.usd.get() or self.robux.get()) else self.HINT)
            self.app.schedule_fit()
            return
        if usd is None:
            usd = robux / rate
        if robux is None:
            robux = usd * rate
        self.big.set(f"{format_usd(usd)} buys ~{format_num(round(robux))} R$")
        self.sub.set(f"Rate {rate:.1f} R$ per $1.00 "
                     f"({format_num(pack_robux)} R$ pack — ${pack_price:.2f})")
        self.app.schedule_fit()

    def _update_cheapest(self):
        state, want = read_amount(self.want.get())
        self.mark("want", state == "bad")
        if state != "ok" or want is None:
            self.extra.set("")
            return
        plan = cheapest_package_plan(want)
        if plan is None:
            self.extra.set("Enter a target up to 10,000,000 R$ for a suggestion.")
            return
        combo = " + ".join(f"{count}× {format_num(robux)} R$"
                           for robux, count in plan["parts"])
        overshoot = plan["robux"] - want
        extra = f" (+{format_num(overshoot)} R$ extra)" if overshoot >= 1 else ""
        self.extra.set(f"Cheapest for at least {format_num(want)} R$: {combo} = "
                       f"{format_num(plan['robux'])} R$ for "
                       f"${plan['cents'] / 100:,.2f}{extra}")

    def copy_text(self):
        return self.big.get() or None


class FeeTool(Tool):
    key, title = "fees", "Marketplace Fees"
    note = (f"Roblox takes {MARKETPLACE_FEE:.0%} of most sales. Enter the gross "
            "sale — or the net you want — and the other side fills in.")
    HINT = "Enter a gross sale or the net you want to receive."

    def build(self):
        self.heading()
        self.gross = self.field("Gross R$", "gross", trace=False)
        self.net = self.field("Desired net R$", "net", trace=False)
        self.big, self.sub = self.results()
        self.actions()
        self._syncing = False
        self.gross.trace_add("write", lambda *_: self._from_gross())
        self.net.trace_add("write", lambda *_: self._from_net())

    def _from_gross(self):
        if self._syncing:
            return
        state, gross = read_amount(self.gross.get())
        self._syncing = True
        self.net.set(format_robux(gross * (1 - MARKETPLACE_FEE)) if state == "ok" else "")
        self._syncing = False
        self.refresh()

    def _from_net(self):
        if self._syncing:
            return
        state, net = read_amount(self.net.get())
        self._syncing = True
        self.gross.set(format_robux(net / (1 - MARKETPLACE_FEE)) if state == "ok" else "")
        self._syncing = False
        self.refresh()

    def refresh(self):
        g_state, gross = read_amount(self.gross.get())
        n_state, net = read_amount(self.net.get())
        self.mark("gross", g_state == "bad")
        self.mark("net", n_state == "bad")
        if gross is None and net is None:
            self.big.set("")
            self.sub.set("" if (self.gross.get() or self.net.get()) else self.HINT)
            self.app.schedule_fit()
            return
        if gross is not None:
            net = gross * (1 - MARKETPLACE_FEE)
        else:
            gross = net / (1 - MARKETPLACE_FEE)
        self.big.set(f"{format_robux(gross)} R$ → {format_robux(net)} R$ after fees")
        self.sub.set(f"Fee: {format_robux(gross * MARKETPLACE_FEE)} R$ · "
                     f"Net ≈ {format_usd(net * RUBUX_TO_USD)} at DevEx rate")
        self.app.schedule_fit()

    def copy_text(self):
        return self.big.get() or None


class SplitTool(Tool):
    key, title = "split", "Payout Splitter"
    note = "Equal split of group payouts. The optional cut % is removed first."
    HINT = "Enter the payout total and how many people split it."

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
            self.sub.set("" if (self.total.get() or self.people.get()) else self.HINT)
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
    note = ("Length, mass, volume, area, speed, energy, pressure, data sizes "
            "and temperature — all offline.")

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
    note = "Dates as YYYY-MM-DD. Weekdays are Mon–Fri; age is measured from the first date."

    def build(self):
        self.heading()
        self._build_date_row(
            pieces=[("e", "d1", 12), ("t", "to"), ("e", "d2", 12), ("r", "diff")])
        # Second/third rows reuse the 'd1' var; pending trace attached only once.
        self._build_date_row(
            pieces=[("e", "d1b", 12), ("t", "± days"), ("e", "ndays", 7),
                    ("r", "add")],
            shared_key="d1")
        self._build_date_row(
            pieces=[("e", "d1c", 12), ("t", "+ business days"), ("e", "biz", 7),
                    ("r", "bizres")],
            shared_key="d1")
        self.diff_res = self.vars["diff"]
        self.add_res = self.vars["add"]
        self.biz_res = self.vars["bizres"]
        self.age = self.extra_line(fg="muted")
        self.actions()

    def _build_date_row(self, pieces, shared_key=None):
        """One inline row of entries + text labels + bold inline result."""
        row = tk.Frame(self.frame)
        row.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.app.tag(row, bg="card")
        for i, piece in enumerate(pieces):
            if piece[0] == "e":
                key, width = piece[1], piece[2]
                if shared_key and key in ("d1b", "d1c"):
                    _, entry = self.inline_field(row, key, width=width,
                                                 var=self.vars["d1"], with_trace=False)
                else:
                    _, entry = self.inline_field(row, key, width=width)
                entry.grid(row=0, column=i, padx=3, sticky="ew")
                if key in ("d1", "d2", "d1b", "d1c"):
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

    @staticmethod
    def _safe_add(start, days):
        try:
            return start + timedelta(days=days)
        except (OverflowError, ValueError):
            return None

    def refresh(self):
        d1 = self._parse(self.vars["d1"].get())
        d2 = self._parse(self.vars["d2"].get())
        bad_d1 = self.vars["d1"].get().strip() != "" and d1 is None
        # Every widget that shares the d1 var gets the same red border.
        self.mark("d1", bad_d1)
        self.mark("d1b", bad_d1)
        self.mark("d1c", bad_d1)
        self.mark("d2", self.vars["d2"].get().strip() != "" and d2 is None)
        if d1 and d2:
            days = (d2 - d1).days
            biz = business_days_between(d1, d2)
            direction = " (reversed order)" if days < 0 else ""
            self.diff_res.set(f"{abs(days):,} days between{direction} · "
                              f"{d2:%A} · {abs(biz):,} business days")
        else:
            self.diff_res.set("")

        n_state, n = read_signed(self.vars["ndays"].get())
        self.mark("ndays", n_state == "bad")
        if d1 and n is not None:
            result = self._safe_add(d1, n)
            self.add_res.set(f"{result:%Y-%m-%d} · {result:%A}" if result
                             else "Date out of range.")
        else:
            self.add_res.set("")

        b_state, biz_n = read_signed(self.vars["biz"].get())
        self.mark("biz", b_state == "bad")
        if d1 and biz_n is not None:
            if abs(biz_n) > 100000:
                self.biz_res.set("Too many business days (max 100,000).")
            else:
                try:
                    result = add_business_days(d1, int(biz_n))
                except (OverflowError, ValueError):
                    result = None
                self.biz_res.set(f"{result:%Y-%m-%d} · {result:%A}" if result
                                 else "Date out of range.")
        else:
            self.biz_res.set("")

        if d1 and d1 <= date.today():
            y, m, dd = years_between(d1, date.today())
            self.age.set(f"Age today: {y} years, {m} months, {dd} days")
        elif d1:
            self.age.set("Age: first date is in the future.")
        else:
            self.age.set("")

    def copy_all_text(self):
        pieces = [self.diff_res.get(), self.add_res.get(), self.biz_res.get(),
                  self.age.get()]
        return "\n".join(p for p in pieces if p) or None

    def copy_text(self):
        pieces = [t for t in (self.diff_res.get(), self.add_res.get()) if t]
        return " · ".join(pieces) or None


class LoanTool(Tool):
    key, title = "loan", "Loan / Growth"
    note = "Standard amortized payment; rate as APR %."
    HINT = "Enter an amount, APR and term to see the monthly payment."

    def build(self):
        self.heading()
        self.principal = self.field("Amount ($)", "principal")
        self.rate = self.field("APR %", "rate")
        self.years = self.field("Years", "years")
        self.big, self.sub = self.results()
        self.extra = self.extra_line(fg="muted")
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
            self.sub.set("" if (self.principal.get() or self.rate.get()
                                or self.years.get()) else self.HINT)
            self.extra.set("")
            return
        n = int(float(self.years.get()) * 12)
        total = pay * n
        self.big.set(f"{format_usd(pay)} / month")
        self.sub.set(f"Total paid: {format_usd(total)} · "
                     f"Interest: {format_usd(total - principal)}")
        payoff = add_months(date.today(), n)
        share = (total - principal) / principal * 100 if principal else 0
        self.extra.set(f"Paid off ≈ {payoff:%b %Y} · {n} payments · "
                       f"interest {share:.0f}% of principal")

    def copy_text(self):
        joined = " · ".join(x for x in (self.big.get(), self.sub.get()) if x)
        return joined or None


class ZoneTool(Tool):
    key, title = "zones", "Time Zones"
    note = TIMEZONE_FALLBACK_NOTE
    MULTI = (("UTC", "UTC"), ("NY", "US/Eastern"), ("LA", "US/Pacific"),
             ("London", "Europe/London"), ("Tokyo", "Asia/Tokyo"))

    def build(self):
        self.heading()
        zones = [(z, z) for z in TIMEZONES]
        self.zone_a_var, _ = self.dropdown_field("From zone", zones, "zone_a",
                                                 default=TIMEZONES[1])
        self.zone_b_var, _ = self.dropdown_field("To zone", zones, "zone_b",
                                                 default="Asia/Tokyo")
        self.when = self.field("When (YYYY-MM-DD HH:MM, blank = now)", "when")
        self.big, self.sub = self.results()
        self.extra = self.extra_line(fg="muted")
        self.actions()

    def clear(self):
        self.when.set("")
        self.refresh()

    def refresh(self):
        a_name, b_name = self.vars["zone_a"].get(), self.vars["zone_b"].get()
        text = self.when.get().strip()
        try:
            moment, parsed_ok = self._moment(a_name, text)
            converted = self._to_zone(moment, b_name)
            off_a, off_b = moment.utcoffset(), converted.utcoffset()
            if off_a is None or off_b is None:
                raise ValueError("missing utc offset")
            minutes = int((off_b - off_a).total_seconds() // 60)
        except Exception:
            self.big.set("Time zones unavailable for that selection.")
            self.sub.set("")
            self.extra.set("")
            self.mark("when", bool(text))
            return
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
        self.extra.set(self._multi_zone())

    @staticmethod
    def _multi_zone():
        now = datetime.now(timezone.utc)
        bits = []
        for label, name in ZoneTool.MULTI:
            try:
                bits.append(f"{label} {now.astimezone(get_zone(name)):%H:%M}")
            except Exception:
                continue
        return ("Now: " + " · ".join(bits)) if bits else ""

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
        self.base_var, self.base_dd = self.dropdown_field("Input base", pairs, "base",
                                                         default="10")
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
        self.reduce_motion = bool(config.get("reduce_motion", False))
        self.config["reduce_motion"] = self.reduce_motion
        self.tags = []       # [widget, bg_role, fg_role, kind]
        self.buttons = []    # RoundedButtons
        self.dropdowns = []  # themed Dropdown widgets
        self.tools = {}
        self.tab_buttons = {}
        self.current_key = None
        self._status_job = None
        self._fit_job = None
        self._theme_job = None
        self._theme_gen = 0
        self._animating = False
        self._aurora_t = 0.35
        self._aurora_items = []
        self._colors = dict(THEMES[self.theme])
        self.fx = FX(root)
        self._window_size = None

        root.title(APP_TITLE)
        root.minsize(760, 560)
        self._build_shell()
        self._start_aurora()      # canvas first so the tool cards stack above it
        self._build_tools()
        self._paint(self._colors)
        self._apply_windows_chrome()

        # Only restore fields that were actually saved so dropdowns keep defaults.
        inputs = config.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
        for tool_key, tool in self.tools.items():
            saved = inputs.get(tool_key)
            if not isinstance(saved, dict):
                continue
            for field_key, var in tool.vars.items():
                if field_key in saved and isinstance(saved[field_key], str):
                    var.set(saved[field_key] or "")
        for tool in self.tools.values():  # populate default results (e.g. zones = now)
            tool.refresh()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.select_tool(config.get("tool") if config.get("tool") in self.tools else "devex")
        self._size_initial_window()
        self.root.after(0, self._apply_fit)
        self.root.after(80, self._apply_windows_chrome)

    # -- theme registry -----------------------------------------------------
    def tag(self, widget, bg=None, fg=None, kind=None):
        self.tags.append([widget, bg, fg, kind])

    @property
    def colors(self):
        return self._colors

    def apply_theme(self, theme_name):
        """Cross-fade the palette in deliberate steps, then settle exactly."""
        if theme_name not in THEMES:
            return
        target = THEMES[theme_name]
        changed = theme_name != self.theme
        self.theme = theme_name
        self.config["theme"] = theme_name
        start = dict(self._colors)
        self._theme_gen += 1
        gen = self._theme_gen
        if self._theme_job is not None:
            try:
                self.root.after_cancel(self._theme_job)
            except Exception:
                pass
            self._theme_job = None
        if self.reduce_motion or not changed:
            self._colors = dict(target)
            self._paint(self._colors)
            self._apply_windows_chrome()
            save_config(self.collect_config())
            return

        def tick(i):
            if gen != self._theme_gen:
                return
            t = ease_out(i / THEME_FADE_STEPS)
            self._colors = {
                k: (mix(start[k], target[k], t)
                    if isinstance(start[k], str) and isinstance(target[k], str)
                    else target[k])  # hover_up is a flag, not a color
                for k in target}
            # Only the visible tool's glow is repainted mid-fade; the other
            # nine settle once at the end.
            self._paint(self._colors, final=False)
            if i < THEME_FADE_STEPS:
                self._theme_job = self.root.after(
                    max(10, THEME_FADE_MS // THEME_FADE_STEPS), lambda: tick(i + 1))
            else:
                self._theme_job = None
                self._colors = dict(target)
                self._paint(self._colors, final=True)
                self._apply_windows_chrome()
                save_config(self.collect_config())

        self._theme_job = self.root.after(10, lambda: tick(0))

    def toggle_theme(self):
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def toggle_reduce_motion(self):
        self.reduce_motion = not self.reduce_motion
        self.config["reduce_motion"] = self.reduce_motion
        self._sync_motion()
        save_config(self.collect_config())
        self.flash("Reduced motion on" if self.reduce_motion else "Full motion on")

    def _sync_motion(self):
        """Apply a live reduce-motion change: stop/start loops, snap in-flight UI."""
        self.motion_btn.set_text("Motion: reduced" if self.reduce_motion
                                 else "Motion: full")
        self.fx.cancel("aurora")
        for tool in self.tools.values():
            self.fx.cancel(f"warn{tool.key}")
            if hasattr(tool, "warn_lbl"):
                try:
                    tool.warn_lbl.config(fg=self.colors["warning"])
                except tk.TclError:
                    pass
        if self.reduce_motion:
            self._animating = False
            for key in self.tools:
                for prefix in ("in", "out", "badge", "warn"):
                    self.fx.cancel(f"{prefix}{key}")
            for key, tool in self.tools.items():
                if key != self.current_key:
                    try:
                        if tool.frame.winfo_manager() == "place":
                            tool.frame.place_forget()
                    except tk.TclError:
                        pass
            if self.current_key:
                cur = self.current()
                try:
                    cur.frame.place_configure(x=6)
                except tk.TclError:
                    pass
                cur._draw_glow()
            self._draw_aurora(self._aurora_t)
        else:
            self.fx.start("aurora", 14000, self._draw_aurora, loop=True)

    def _paint(self, c, final=True):
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
        if hasattr(self, "aurora"):
            try:
                self.aurora.configure(bg=c["bg"])
            except tk.TclError:
                pass
        if final:
            for tool in self.tools.values():
                tool.retheme(c)
        elif self.current_key:
            self.current().retheme(c)
        self.theme_btn.set_text("☀ Light" if self.theme == "dark" else "☾ Dark")
        self.motion_btn.set_text("Motion: reduced" if self.reduce_motion
                                 else "Motion: full")
        if final and self.reduce_motion and hasattr(self, "aurora"):
            self._draw_aurora(self._aurora_t)

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
        self.aurora.bind("<Configure>", self._on_aurora_configure)
        self._aurora_items = []
        if self.reduce_motion:
            self._draw_aurora(self._aurora_t)
        else:
            self.fx.start("aurora", 14000, self._draw_aurora, loop=True)

    def _on_aurora_configure(self, _event):
        if self.reduce_motion:
            self._draw_aurora(self._aurora_t)

    def _draw_aurora(self, t):
        cv = self.aurora
        self._aurora_t = t
        try:
            # Skip all redraw work while minimized or not yet mapped.
            if self.root.state() == "iconic" or not cv.winfo_ismapped():
                return
        except tk.TclError:
            return
        c = self._colors
        try:
            cv.config(bg=c["bg"])
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 10 or h < 10:
            return
        strength = 0.55
        ovals = []
        for cx, cy, color, phase in ((0.30, 0.30, c["glow1"], 0.0),
                                     (0.78, 0.68, c["glow2"], 2.1)):
            dx = math.sin((t * 2 + phase) * 6.283) * w * 0.06
            dy = math.cos((t * 3 + phase) * 6.283) * h * 0.07
            rx, ry = w * 0.42, h * 0.52
            for i in range(1, AURORA_RINGS + 1):
                frac = i / AURORA_RINGS
                fade = strength * (1 - frac) ** 1.4
                x0 = cx * w + dx - rx * frac
                y0 = cy * h + dy - ry * frac
                ovals.append((x0, y0, cx * w + dx + rx * frac, cy * h + dy + ry * frac,
                              mix(c["bg"], color, fade)))
        try:
            if len(self._aurora_items) != len(ovals):
                cv.delete("all")
                self._aurora_items = [cv.create_oval(0, 0, 0, 0, width=0)
                                      for _ in ovals]
            for item, (x0, y0, x1, y1, fill) in zip(self._aurora_items, ovals):
                cv.coords(item, x0, y0, x1, y1)
                cv.itemconfig(item, fill=fill)
        except tk.TclError:
            self._aurora_items = []

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
        ui9 = tkfont.Font(family="Segoe UI", size=9)
        bold9 = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.theme_btn = RoundedButton(self, header, "☀ Light", self.toggle_theme,
                                       width=max(86, ui9.measure("☀ Light") + 26),
                                       height=28, role="ghost",
                                       font=("Segoe UI", 9), canvas_role="side")
        self.theme_btn.pack(side="right")
        self.motion_btn = RoundedButton(self, header, "Motion: full",
                                        self.toggle_reduce_motion,
                                        width=max(104, ui9.measure("Motion: reduced") + 26),
                                        height=28, role="ghost",
                                        font=("Segoe UI", 9), canvas_role="side")
        self.motion_btn.pack(side="right", padx=(0, 8))
        self.header_frame = header

        self.sidebar = tk.Frame(self.root, padx=10, pady=12)
        self.sidebar.pack(side="left", fill="y")
        self.tag(self.sidebar, bg="side")

        self.content = tk.Frame(self.root)
        self.content.pack(side="right", fill="both", expand=True)
        self.tag(self.content, bg="bg")
        self.content.bind("<Configure>", self._on_content_resize)

        self.status = tk.Label(self.root, text="", font=("Segoe UI", 9), anchor="e")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        self.tag(self.status, bg="status", fg="muted")

    def _build_tools(self):
        for tool_cls in self.TOOLS:
            self.tools[tool_cls.key] = tool_cls(self, self.content)
        bold9 = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        tab_w = max(150, max(bold9.measure(f"{(idx + 1) % 10}  {cls.title}")
                             for idx, cls in enumerate(self.TOOLS)) + 26)
        for idx, tool_cls in enumerate(self.TOOLS):
            label = f"{(idx + 1) % 10}  {tool_cls.title}"
            btn = RoundedButton(self, self.sidebar, label,
                                lambda k=tool_cls.key: self.select_tool(k),
                                width=tab_w, height=30, role="tab",
                                font=("Segoe UI", 9, "bold"), canvas_role="side")
            btn.pack(fill="x", pady=2)
            self.tab_buttons[tool_cls.key] = btn
        hint = tk.Label(self.sidebar,
                        text="Ctrl+1–0 tools · Ctrl+T theme\nCtrl+M motion · Enter copy\n"
                             "Esc clear · Copy all copies every line",
                        font=("Segoe UI", 8), justify="left")
        hint.pack(side="bottom", pady=(8, 0))
        self.tag(hint, bg="side", fg="muted")

    def _size_initial_window(self):
        """One fixed starting size = fits the tallest tool. Switching tools then
        never resizes the window mid-animation, and the user can resize freely."""
        self.root.update_idletasks()
        max_w, max_h = 560, 200
        for tool in self.tools.values():
            max_w = max(max_w, tool.frame.winfo_reqwidth())
            max_h = max(max_h, tool.frame.winfo_reqheight())
        side_w = self.sidebar.winfo_reqwidth()
        width = max(780, side_w + max_w + 60)
        height = (self.header_frame.winfo_reqheight() + max_h +
                  self.status.winfo_reqheight() + 52)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = min(width, max(760, sw - 80))
        height = min(height, max(560, sh - 80))
        self._window_size = (width, height)
        self.root.geometry(f"{width}x{height}")

    def _on_content_resize(self, event):
        """Manual window resizes reflow the active card (height stays natural)."""
        if event.width < 20 or not self.current_key:
            return
        try:
            frame = self.current().frame
            if frame.winfo_manager() == "place":
                frame.place_configure(width=max(300, event.width - 12))
                frame.place_configure(height=max(frame.winfo_reqheight(), 60))
        except tk.TclError:
            pass

    def schedule_fit(self, delay=80):
        """Debounced re-measure after content changes (warnings appearing, etc.)."""
        if not self.current_key:
            return
        if self._fit_job is not None:
            try:
                self.root.after_cancel(self._fit_job)
            except Exception:
                pass
        self._fit_job = self.root.after(delay, self._apply_fit)

    def _apply_fit(self):
        self._fit_job = None
        if not self.current_key:
            return
        if self._animating:
            self._fit_job = self.root.after(140, self._apply_fit)
            return
        try:
            self.root.update_idletasks()
            tool = self.current()
            req_h = max(tool.frame.winfo_reqheight(), 60)
            content_w = self.content.winfo_width()
            if content_w > 20:
                tool.frame.place_configure(width=max(300, content_w - 12))
            tool.frame.place_configure(height=req_h)
            # Only ever GROW the window; shrinking is the user's call.
            if self.root.winfo_viewable():
                avail = self.content.winfo_height()
                shortfall = (req_h + 12) - avail
                if shortfall > 2:
                    self.root.geometry(f"{self.root.winfo_width()}x"
                                       f"{self.root.winfo_height() + shortfall}")
        except tk.TclError:
            pass

    # -- tool switching / actions ----------------------------------------------
    def current(self):
        return self.tools[self.current_key]

    def _place_tool(self, tool, x):
        req_h = tool.frame.winfo_reqheight()
        if req_h < 40:
            req_h = max(200, self.content.winfo_height() - 12)
        opts = {"in_": self.content, "x": x, "y": 6, "height": req_h}
        cw = self.content.winfo_width()
        if cw > 20:
            opts["width"] = max(300, cw - 12)
        tool.frame.place(**opts)
        tool.frame.lift()  # incoming card must sit above the outgoing one

    def select_tool(self, key):
        if key not in self.tools or key == self.current_key:
            return
        old_key = self.current_key
        # Cancel stale transitions and hide any card that is neither the
        # outgoing nor the incoming one (rapid Ctrl+1..0 mashed together).
        for k in self.tools:
            if k not in (key, old_key):
                self.fx.cancel(f"in{k}")
                self.fx.cancel(f"out{k}")
                try:
                    if self.tools[k].frame.winfo_manager() == "place":
                        self.tools[k].frame.place_forget()
                except tk.TclError:
                    pass
        if old_key:
            self.collect_inputs(old_key)
            self.fx.cancel(f"in{old_key}")
            self.tab_buttons[old_key].role = "tab"
            self.tab_buttons[old_key].retheme(self.colors)
        self.fx.cancel(f"out{key}")  # user may be switching back mid-slide
        self.current_key = key
        tool = self.tools[key]

        self.root.update_idletasks()
        animate = bool(old_key) and not self.reduce_motion
        self._animating = animate
        self._place_tool(tool, 36 if animate else 6)

        if old_key:
            old = self.tools[old_key]
            try:
                old_x = int(old.frame.place_info().get("x") or 6)
            except (ValueError, TypeError):
                old_x = 6
            if self.reduce_motion:
                try:
                    old.frame.place_forget()
                except tk.TclError:
                    pass
            else:
                def slide_out(t):
                    try:
                        old.frame.place_configure(x=old_x - int(26 * t))
                    except tk.TclError:
                        pass

                def hide_old():
                    try:
                        old.frame.place_forget()
                    except tk.TclError:
                        pass

                self.fx.start(f"out{old_key}", 150, slide_out, done=hide_old)

        if animate:
            def slide_in(t):
                try:
                    tool.frame.place_configure(x=6 + int(30 * (1 - t)))
                except tk.TclError:
                    pass
            self.fx.start(f"in{key}", 170, slide_in,
                          done=lambda: self._slide_finished(tool))
        else:
            try:
                tool.frame.place_configure(x=6)
            except tk.TclError:
                pass
            self._apply_fit()

        self.tab_buttons[key].role = "tab_active"
        self.tab_buttons[key].retheme(self.colors)
        tool.animate_entry()
        self.config["tool"] = key
        self.root.title(f"{APP_TITLE} — {tool.title}")
        save_config(self.collect_config())
        self.root.after(60, self._focus_current)

    def _slide_finished(self, tool):
        try:
            tool.frame.place_configure(x=6)
        except tk.TclError:
            return
        self._animating = False
        self._apply_fit()

    def _focus_current(self):
        if not self.current_key:
            return
        self.current().focus_primary()
        self._apply_windows_chrome()

    def collect_inputs(self, tool_key):
        inputs = self.config.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
            self.config["inputs"] = inputs
        saved = inputs.get(tool_key)
        if not isinstance(saved, dict):
            saved = {}
            inputs[tool_key] = saved
        for field_key, var in self.tools[tool_key].vars.items():
            try:
                saved[field_key] = var.get()
            except tk.TclError:
                pass

    def collect_config(self):
        for key in self.tools:  # every tool's fields, so switching is not required
            self.collect_inputs(key)
        return self.config

    def copy_current(self):
        self._copy_text(self.current().copy_text())

    def copy_all_current(self):
        self._copy_text(self.current().copy_all_text())

    def _copy_text(self, text):
        if text:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.flash("Copied to clipboard")
            except tk.TclError:
                self.flash("Clipboard unavailable")
        else:
            self.flash("Nothing to copy")

    def clear_current(self):
        self.current().clear()
        self.flash("Cleared")

    def flash(self, message):
        if self._status_job:
            try:
                self.root.after_cancel(self._status_job)
            except Exception:
                pass
        self.status.config(text=message)
        self._status_job = self.root.after(1600, lambda: self.status.config(text=""))

    def _bind_keys(self):
        for idx, tool_cls in enumerate(self.TOOLS):
            self.root.bind(f"<Control-Key-{(idx + 1) % 10}>",
                           lambda _e, k=tool_cls.key: self.select_tool(k))
        self.root.bind("<Escape>", lambda _e: self.clear_current())
        self.root.bind("<Return>", lambda _e: self.copy_current())
        self.root.bind("<Control-t>", lambda _e: self.toggle_theme())
        self.root.bind("<Control-m>", lambda _e: self.toggle_reduce_motion())
        self.root.bind_class("Entry", "<Control-a>",
                             lambda e: (e.widget.select_range(0, "end"),
                                        e.widget.icursor("end"), "break")[2])

    def on_close(self):
        save_config(self.collect_config())
        self.fx.stop()
        self.root.destroy()


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    App(root, load_config())
    root.mainloop()


def enable_dpi_awareness():
    """Crisp text on high-DPI displays. Must run before the Tk root exists.

    Prefer per-monitor awareness (2) so moving between monitors with different
    scale factors stays sharp, then system awareness (1), then the legacy call.
    """
    if os.name != "nt" or not getattr(ctypes, "windll", None):
        return
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(1) == 0:
            return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


if __name__ == "__main__":
    main()





