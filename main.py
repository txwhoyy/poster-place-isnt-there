#!/usr/bin/env python3
"""VELMARA — a travel poster for a place that isn't there.

Renders a 1024x1024 travel poster PNG to /output/entry.png using only the
Python standard library (zlib + struct), so it runs in a sandbox with no
network and no third-party packages.

The place: VELMARA, the Floating Isles, where the sea hangs in the sky
above the islands and the water falls upward. The poster's name is set
into the picture in large type at the top; the tagline sits at the bottom.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
SKY_TOP = (20, 29, 58)        # deep indigo
SKY_MID = (44, 95, 122)       # teal
SKY_LOW = (232, 169, 79)      # warm gold at the horizon
SEA_SKY = (23, 68, 110)       # the sea that hangs overhead
SEA_SKY_LT = (64, 140, 180)   # its sunlit edge
SUN = (255, 196, 92)
SUN_GLOW = (255, 214, 140)
ISLE = (26, 32, 54)           # island silhouettes
ISLE_RIM = (232, 169, 79)     # warm rim light on island tops
TOWER = (245, 235, 210)       # lighthouse tower
TOWER_CAP = (150, 60, 50)
BEAM = (255, 230, 160)
SEA_TOP = (18, 64, 84)
SEA_BOT = (10, 40, 60)
CREAM = (252, 244, 220)
SHADOW = (16, 20, 40)
FOAM = (235, 245, 250)

buf = bytearray(W * H * 3)


def _idx(x, y):
    return (y * W + x) * 3


def hspan(y, x0, x1, color):
    """Fill a horizontal run of pixels on row y (clipped)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    r, g, b = color
    start = _idx(x0, y)
    n = x1 - x0 + 1
    buf[start:start + 3 * n] = bytes((r, g, b)) * n


def blend_hspan(y, x0, x1, color, alpha):
    """Alpha-blend a horizontal run over the existing pixels."""
    if y < 0 or y >= H or alpha <= 0:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    r, g, b = color
    inv = 1.0 - alpha
    for x in range(x0, x1 + 1):
        i = _idx(x, y)
        buf[i] = int(r * alpha + buf[i] * inv)
        buf[i + 1] = int(g * alpha + buf[i + 1] * inv)
        buf[i + 2] = int(b * alpha + buf[i + 2] * inv)


def fill_rect(x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(H, y1 + 1)):
        hspan(y, x0, x1, color)


def lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def disc(cx, cy, r, color):
    """Filled circle."""
    r2 = r * r
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        hspan(y, cx - dx, cx + dx, color)


def ellipse(cx, cy, rx, ry, color):
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = 1.0 - (dy * dy) / float(ry * ry)
        dx = int(rx * math.sqrt(max(0.0, t)))
        hspan(y, cx - dx, cx + dx, color)


def tri(x0, y0, x1, y1, x2, y2, color):
    """Filled triangle, scanline fill."""
    pts = sorted([(x0, y0), (x1, y1), (x2, y2)], key=lambda p: p[1])
    (ax, ay), (bx, by), (cx, cy) = pts
    if ay == cy:
        return
    for y in range(max(0, ay), min(H, cy + 1)):
        if y < by:
            t1 = (y - ay) / float(by - ay) if by != ay else 0.0
            xa = ax + (bx - ax) * t1
        else:
            t1 = (y - by) / float(cy - by) if cy != by else 0.0
            xa = bx + (cx - bx) * t1
        t2 = (y - ay) / float(cy - ay)
        xb = ax + (cx - ax) * t2
        hspan(y, int(min(xa, xb)), int(max(xa, xb)), color)


# ------------------------------------------------------------------- font
# 5x7 bitmap font, '#' = on, '.' = off.
FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    "'": (".#...", ".#...", "..#..", ".....", ".....", ".....", "....."),
    '-': (".....", ".....", ".....", ".####", ".....", ".....", "....."),
    '&': (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, x, y, scale, color, shadow=True):
    """Draw text with its top-left at (x, y). Glyphs are 5x7, scaled."""
    if shadow:
        _draw_text_raw(s, x + max(2, scale // 4), y + max(2, scale // 4),
                       scale, SHADOW)
    _draw_text_raw(s, x, y, scale, color)


def _draw_text_raw(s, x, y, scale, color):
    cx = x
    for ch in s:
        glyph = FONT.get(ch.upper(), FONT[' '])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == '#':
                    fill_rect(cx + col * scale, y + row * scale,
                              cx + col * scale + scale - 1,
                              y + row * scale + scale - 1, color)
        cx += 6 * scale


def draw_text_centered(s, y, scale, color, shadow=True):
    x = (W - text_width(s, scale)) // 2
    draw_text(s, x, y, scale, color, shadow)
    return x


# ------------------------------------------------------------------ scene
def paint_sky():
    """Vertical gradient: indigo -> teal -> warm gold at the horizon."""
    for y in range(0, 800):
        if y < 420:
            t = y / 420.0
            c = lerp(SKY_TOP, SKY_MID, t)
        else:
            t = (y - 420) / 380.0
            c = lerp(SKY_MID, SKY_LOW, t)
        hspan(y, 0, W - 1, c)


def paint_sky_sea():
    """The sea hanging overhead: a great arch of water across the sky."""
    # Ring segment of a huge circle centred far below the frame.
    ccx, ccy = 512, 2600
    r_out, r_in = 2450, 2310
    for y in range(140, 380):
        dy = y - ccy
        a = r_out * r_out - dy * dy
        b = r_in * r_in - dy * dy
        if a <= 0:
            continue
        dx_out = int(math.sqrt(a))
        if b <= 0:
            hspan(y, ccx - dx_out, ccx + dx_out, SEA_SKY)
        else:
            dx_in = int(math.sqrt(b))
            hspan(y, ccx - dx_out, ccx - dx_in, SEA_SKY)
            hspan(y, ccx + dx_in, ccx + dx_out, SEA_SKY)
    # Sunlit rim along the arch's lower edge.
    for y in range(150, 380):
        dy = y - ccy
        b = r_in * r_in - dy * dy
        if b <= 0:
            continue
        dx_in = int(math.sqrt(b))
        hspan(y, ccx - dx_in - 3, ccx - dx_in + 3, SEA_SKY_LT)
        hspan(y, ccx + dx_in - 3, ccx + dx_in + 3, SEA_SKY_LT)
    # Foam curls along the inner edge.
    for k in range(13):
        t = k / 12.0
        ang = math.pi * (0.14 + 0.72 * t)
        fx = int(512 + 2310 * math.cos(ang + math.pi))
        fy = int(2600 - 2310 * math.sin(ang))
        if 0 <= fx < W and 150 <= fy < 380:
            disc(fx, fy, 7, FOAM)
    # Wave strokes inside the arch so it reads as water, not a stripe.
    for (wy, wx0, wx1) in ((196, 120, 300), (216, 700, 880), (248, 60, 180),
                           (268, 850, 980), (300, 240, 420), (322, 640, 820)):
        hspan(wy, wx0, wx1, SEA_SKY_LT)
        hspan(wy + 2, wx0 + 12, wx1 - 8, FOAM)


def paint_sun():
    # Soft glow rings, then the disc.
    for r, col in ((150, (255, 224, 160)), (125, SUN_GLOW)):
        for dy in range(-r, r + 1):
            y = 580 + dy
            if y < 0 or y >= H:
                continue
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            blend_hspan(y, 760 - dx, 760 + dx, col, 0.16)
    disc(760, 580, 96, SUN)
    disc(760, 580, 78, (255, 208, 120))


def paint_birds():
    for (bx, by, s) in ((240, 380, 12), (300, 350, 10), (700, 300, 11),
                        (880, 420, 10)):
        for i in range(s):
            hspan(by + i, bx - s + i, bx - s + i, SHADOW)
            hspan(by + i, bx + i, bx + i, SHADOW)


def paint_airship(cx, cy, s):
    """A small airship crossing the sky — the way you get to Velmara."""
    # Envelope.
    ellipse(cx, cy, 46 * s // 10, 15 * s // 10, (222, 158, 74))
    ellipse(cx, cy - 3 * s // 10, 46 * s // 10, 11 * s // 10, (240, 186, 104))
    # Gondola and tail fin.
    fill_rect(cx - 12 * s // 10, cy + 12 * s // 10, cx + 12 * s // 10,
              cy + 20 * s // 10, (84, 48, 40))
    tri(cx - 46 * s // 10, cy - 4 * s // 10, cx - 46 * s // 10,
        cy + 8 * s // 10, cx - 62 * s // 10, cy + 2 * s // 10, (150, 60, 50))
    # Tiny portholes.
    for px in (-24, -8, 8, 24):
        disc(cx + px * s // 10, cy + 2 * s // 10, 2, (40, 50, 70))


def paint_island(cx, top, rx, ry, with_lighthouse):
    """A floating island: ellipse top, tapered rock below."""
    ellipse(cx, top, rx, ry, ISLE)
    tri(cx - rx + 12, top + ry - 6, cx + rx - 12, top + ry - 6,
        cx, top + ry + 150, ISLE)
    # Warm rim light along the island's crown.
    for dy in range(0, 5):
        y = top - ry + dy
        t = 1.0 - (dy * dy) / float(ry * ry) if ry else 0.0
        dx = int(rx * math.sqrt(max(0.0, t)))
        hspan(y, cx - dx, cx + dx, ISLE_RIM) if dy == 0 else None
    if with_lighthouse:
        # Lighthouse tower on the crown.
        tx = cx - 14
        fill_rect(tx, top - ry - 78, tx + 28, top - ry, TOWER)
        fill_rect(tx - 4, top - ry - 92, tx + 32, top - ry - 78, TOWER_CAP)
        disc(tx + 14, top - ry - 96, 10, SUN)
        # Light beam sweeping right.
        for i in range(90):
            yy = top - ry - 96 + int(i * 0.18)
            blend_hspan(yy, tx + 30, tx + 30 + i * 3, BEAM, 0.10)
    # Water falling UP from the island's crown, rising into the sky-sea.
    for wx in (cx - rx // 2, cx + rx // 3):
        for i in range(0, 130, 3):
            y = top - ry - 8 - i
            if y < 340:
                break
            blend_hspan(y, wx, wx + 5, FOAM, 0.6)


def paint_sea():
    for y in range(800, H):
        t = (y - 800) / 224.0
        hspan(y, 0, W - 1, lerp(SEA_TOP, SEA_BOT, t))
    # Sun reflection column.
    for i in range(0, 224, 4):
        y = 800 + i
        w = 26 + i // 3
        blend_hspan(y, 760 - w, 760 + w, SUN, 0.10 + 0.10 * (i / 224.0))
    # Horizontal shimmer strokes.
    for (sy, sx0, sx1) in ((840, 120, 420), (880, 560, 940), (920, 80, 300),
                           (960, 620, 900), (1000, 200, 520)):
        blend_hspan(sy, sx0, sx1, (120, 190, 205), 0.35)
        blend_hspan(sy + 2, sx0 + 30, sx1 - 20, FOAM, 0.25)


def paint():
    paint_sky()
    paint_sky_sea()
    paint_sun()
    paint_birds()
    paint_airship(620, 400, 10)
    paint_airship(270, 460, 7)
    paint_island(430, 640, 175, 52, with_lighthouse=True)
    paint_island(880, 720, 95, 34, with_lighthouse=False)
    paint_island(150, 710, 90, 32, with_lighthouse=False)
    paint_sea()
    # Title and tagline.
    draw_text_centered("VELMARA", 36, 12, CREAM)
    draw_text_centered("WHERE THE SEA HANGS IN THE SKY", 952, 4, CREAM)


# -------------------------------------------------------------------- png
def chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        start = y * W * 3
        raw += buf[start:start + W * 3]
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    paint()
    os.makedirs("/output", exist_ok=True)
    size = write_png("/output/entry.png")
    print(f"wrote /output/entry.png: {W}x{H}, {size} bytes")


if __name__ == "__main__":
    main()
