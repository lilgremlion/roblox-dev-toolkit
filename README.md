# ⚡ Dev Toolkit

**Ten live calculators for Roblox creators — in one offline window.**
DevEx cash-outs, store packages, marketplace fees, group payout splits, percentages, units, dates, loans, time zones and number bases.

No account linking, no tracking, no pip installs — a single Python file (and prebuilt `.exe`).

## The tools

| Roblox | Daily |
|---|---|
| **DevEx Cash-Out** — Robux ↔ USD at the published rate, with a live "you're N R$ short of the 30,000 minimum" warning | **Percentages** — three inline calculators (% of N / N is what % of / % change) |
| **Buy Robux** — real store tiers (400 → 10,000), per-tier rate shown | **Unit Converter** — length, mass, volume, data sizes, temperature |
| **Marketplace Fees** — 30% cut math + net after fees | **Date Calculator** — days between, ± N days with weekdays |
| **Payout Splitter** — equal split with optional upfront cut, cents-safe leftover | **Loan / Growth** — amortized monthly payment, total interest |
| | **Time Zones** — creator-schedule planning across zones |
| | **Number Bases** — hex/octal/binary/decimal live conversion |

## Highlights

- **Offline & private**: zero network calls, zero telemetry. Settings live in `%LOCALAPPDATA%\DevexCalculator\config.json`.
- **True rates**: the DevEx conversion constant sits at the top of the source for easy updating; every grouped payout stays cents-accurate (Decimal, half-up).
- **Themed UI**: dark by default, light toggle with cross-fade, animated aurora background, sliding transitions, DPI-aware, dark Windows 11 title bar.
- **Keyboard-first**: `Ctrl+1–0` switch tools · `Enter` copy result · `Esc` clear · `Ctrl+A` select-all in fields.
- **Never crashes on bad input**: invalid fields get a soft red border, not an error dialog.

## Download

Grab the ready-to-run `DevToolkit.exe` (≈10 MB, Windows 10/11) from **[Releases](../../releases)**.
No Python needed. Paranoid-friendly build: verify the `.exe` on VirusTotal, or build it yourself from source below.

## Build from source

```powershell
# runtime: plain Python 3.10+ (stdlib only, tk included)
python devex_calculator.py

# optional: rebuild the exe (one-time: pip install pyinstaller)
python make_icon.py            # regenerates the icon
python -m PyInstaller DevToolkit.spec
```

## Notes for contributors

- The DevEx rate and package list are constants at the top of `devex_calculator.py` — when Roblox changes them, that's a one-line edit.
- Time zones use `zoneinfo` when the IANA database exists (standard on most systems); otherwise it falls back to fixed standard-time offsets and says so in the tool header.
- `devex_calculator.py` is intentionally single-file and dependency-free; please keep new tool code in that file.

## License

MIT — see [LICENSE](LICENSE).

*Not affiliated with or endorsed by Roblox Corporation. DevEx values shown are gross, before taxes or fees.*
