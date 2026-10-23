# -*- coding: utf-8 -*-
"""Build devtoolkit.ico with zero dependencies (stdlib zlib PNG-in-ICO).

Design: dark rounded square with a blue->violet diagonal gradient and three
white rounded stat bars (calculator/analytics glyph). Anti-aliased via signed
distance fields so edges stay crisp at 16 px.
"""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "devtoolkit.ico"
SIZE = 256
BAR_W, BAR_R = 30.0, 14.0
BARS = [  # (center_x, height); baseline y=188
    (82, 104), (128, 142), (174, 78),
]
BASE = 188.0


def sd_round_rect(px, py, cx, cy, hw, hh, r):
    qx = abs(px - cx) - hw + r
    qy = abs(py - cy) - hh + r
    dx, dy = max(qx, 0.0), max(qy, 0.0)
    return min(max(qx, qy), 0.0) + math.hypot(dx, dy) - r


def coverage(sd):
    return max(0.0, min(1.0, 0.5 - sd))


def render(size):
    scale = size / 256.0
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            # background rounded square with diagonal gradient
            bg_sd = sd_round_rect(x + 0.5, y + 0.5, size / 2, size / 2,
                                  118 * scale, 118 * scale, 56 * scale)
            a = coverage(bg_sd)
            t = (x + y) / (2 * size)
            r = 77 + (122 - 77) * t
            g = 141 + (92 - 141) * t
            b = 255 + (255 - 255) * t
            # subtle top-left highlight
            hl = max(0.0, 1.0 - math.hypot(x - 56 * scale, y - 56 * scale) / (170 * scale))
            r += 30 * hl; g += 34 * hl; b += 20 * hl
            # white stat bars
            cover_bars = 0.0
            for cx, h in BARS:
                s = sd_round_rect(x + 0.5, y + 0.5, cx * scale, (BASE - h / 2) * scale,
                                  BAR_W / 2 * scale, h / 2 * scale, BAR_R * scale)
                cover_bars = max(cover_bars, coverage(s))
            alpha = a * 255
            if cover_bars > 0 and a > 0.02:
                r = r * (1 - cover_bars) + 255 * cover_bars
                g = g * (1 - cover_bars) + 255 * cover_bars
                b = b * (1 - cover_bars) + 255 * cover_bars
            row += bytes((int(min(255, r)), int(min(255, g)), int(min(255, b)),
                          int(alpha)))
        rows.append(bytes(row))
    return rows, 4 * size


def box_downscale(rows, w, factor):
    """Average-factor downscale of an RGBA byte-grid (w = source width)."""
    out_w = w // factor
    rows_out = []
    for oy in range(out_w):
        line = bytearray()
        for ox in range(out_w):
            sr = sg = sb = sa = 0
            for dy in range(factor):
                src = rows[oy * factor + dy]
                for dx in range(factor):
                    i = (ox * factor + dx) * 4
                    a = src[i + 3]
                    sr += src[i] * a; sg += src[i + 1] * a; sb += src[i + 2] * a
                    sa += a
            if sa == 0:
                line += bytes((0, 0, 0, 0))
            else:
                line += bytes((sr // sa, sg // sa, sb // sa, sa // (factor * factor)))
        rows_out.append(bytes(line))
    return rows_out, out_w


def png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(size):
    raw, stride = render(size)
    for factor, target in ((1, None)):  # placeholder; real path below
        pass
    body = b"".join(b"\x00" + row for row in raw)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) +
            png_chunk(b"IDAT", zlib.compress(body, 9)) + png_chunk(b"IEND", b""))


def png_from_rows(rows, w):
    body = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", w, w, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) +
            png_chunk(b"IDAT", zlib.compress(body, 9)) + png_chunk(b"IEND", b""))


def main():
    entries = []  # (side, png_bytes)
    rows256, _ = render(SIZE)
    entries.append((SIZE, png_from_rows(rows256, SIZE)))
    current = (rows256, SIZE)
    for size in (64, 32, 16):
        factor = current[1] // size
        cur_rows, cur_w = box_downscale(current[0], current[1], factor)
        entries.append((size, png_from_rows(cur_rows, size)))
        current = (cur_rows, cur_w)

    header = struct.pack("<HHH", 0, 1, len(entries))
    blob = b""
    offset = 6 + len(entries) * 16
    dir_data = b""
    for side, png in entries:
        first = side % 256  # 256 is encoded as 0
        dir_data += struct.pack("<BBBBHHII", first, first, 0, 0, 1, 32,
                                len(png), offset)
        blob += png
        offset += len(png)
    OUT.write_bytes(header + dir_data + blob)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(entries)} sizes)")


if __name__ == "__main__":
    main()
