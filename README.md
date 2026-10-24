# ⚡ Dev Toolkit

**Ten live calculators for Roblox creators — in one offline window.**
DevEx cash-outs, store packages, marketplace fees, group payout splits, percentages, units, dates, loans, time zones and number bases.

No account linking, no tracking, no pip installs — a single Python file (and prebuilt `.exe`).

## The tools

| Roblox | Daily |
|---|---|
| **DevEx Cash-Out** — Robux ↔ USD at the published rate, with a live "you're N R$ short of the 30,000 minimum" warning | **Percentages** — three inline calculators (% of N / N is what % of / % change) |
| **Buy Robux** — real store tiers (400 → 10,000), per-tier rate, plus a cheapest-way-to-reach-N-R$ planner | **Unit Converter** — length, mass, volume, area, speed, energy, pressure, data sizes, temperature |
| **Marketplace Fees** — 30% cut math; works both ways (gross → net or desired net → required gross) | **Date Calculator** — days between, business days, ± N days, + N business days, age today |
| **Payout Splitter** — equal split with optional upfront cut, cents-safe leftover | **Loan / Growth** — amortized monthly payment, total interest, payoff month |

Plus **Time Zones** (converter + "now" strip across five zones) and **Number Bases** (hex/octal/binary/decimal live conversion).

## Highlights

- **Offline & private**: zero network calls, zero telemetry. Settings live in `%LOCALAPPDATA%\DevexCalculator\config.json`.
- **True rates**: the DevEx conversion constant sits at the top of the source for easy updating; every grouped payout stays cents-accurate (Decimal, half-up).
- **Smooth by default**: 60 fps animation timer, drifting aurora, eased hovers, sliding tool transitions and a theme cross-fade — with a persisted **Reduce motion** switch for accessibility and low-end machines.
- **Themed UI**: dark by default, light toggle, DPI-aware (per-monitor when available), matched Windows title-bar color.
- **Keyboard-first**: `Ctrl+1–0` switch tools · `Ctrl+T` theme · `Ctrl+M` reduce motion · `Enter` copy result · `Esc` clear · `Ctrl+A` select-all in fields. Every tool also has **Copy all**.
- **Never crashes on bad input**: invalid fields get a red border (even while focused), never an error dialog; malformed settings files are ignored safely.

## Download

Grab the ready-to-run `DevToolkit.exe` (≈10 MB, Windows 10/11) from **[Releases](../../releases)**.
No Python needed. The exe is built without UPX (fewer antivirus false positives); it is still unsigned, so SmartScreen may ask once. Verify the SHA-256 in the release notes, or build it yourself from source below.

## Build from source

```powershell
# runtime: plain Python 3.10+ (stdlib only, tk included)
python devex_calculator.py

# optional: rebuild the exe (one-time: pip install pyinstaller)
python make_icon.py            # regenerates the icon
python -m PyInstaller DevToolkit.spec
```

The spec sets `upx=False` deliberately: UPX-packed Python executables are a common antivirus false-positive trigger. Leave it off for a release build.

## Notes for contributors

- The DevEx rate and package list are constants at the top of `devex_calculator.py` — when Roblox changes them, that's a one-line edit.
- Time zones use `zoneinfo` when the IANA database exists (standard on most systems); otherwise it falls back to fixed standard-time offsets and says so in the tool header.
- `devex_calculator.py` is intentionally single-file and dependency-free; please keep new tool code in that file.

## License

MIT — see [LICENSE](LICENSE).

*Not affiliated with or endorsed by Roblox Corporation. DevEx values shown are gross, before taxes or fees.*
