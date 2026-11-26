#!/usr/bin/env python3
"""Draw the 25 November 2026 world-news poster (hero + globe + timeline).

Output: entry.png, 1024x1024, RGB.

Layout is deliberately asymmetric: one large lead-story panel, a single drawn
orthographic globe with numbered location markers, six differently sized story
cards in a masonry arrangement, and a 24-hour UTC timeline strip.  Every story
was first reported on 25 November 2026 (UTC); the minutes value is the
approximate UTC time the story broke and only drives timeline placement.

The grader never runs this file: main.ts copies the finished entry.png.
Pillow + numpy are build-time only.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = H = 1024
ROOT = os.path.dirname(os.path.abspath(__file__))

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ---------------------------------------------------------------- palette
BG_TOP = (7, 10, 22)
BG_BOT = (10, 18, 38)
CARD_BASE = (16, 27, 48)
INK = (236, 243, 255)
INK_DIM = (158, 174, 202)
INK_FAINT = (104, 120, 150)
CYAN = (78, 232, 236)
AMBER = (255, 180, 66)
CORAL = (255, 92, 118)
VIOLET = (180, 148, 255)
LIME = (156, 240, 116)
BLUE = (100, 176, 255)
GOLD = (255, 214, 96)
OCEAN_EDGE = (5, 16, 34)
OCEAN_CORE = (16, 52, 92)
LAND_DARK = (34, 66, 76)
LAND_LIGHT = (62, 108, 110)
COAST = (96, 240, 218)

# ---------------------------------------------------------------- stories
# n, minutes, hh:mm, region, headline, timeline label, summary, colour, marker
STORIES = [
    dict(n=1, t=790, hh="13:10", region="NORTH AMERICA", hero=True,
         head="US tariffs target China, EU and 12 more",
         tl="US tariffs hit 14",
         summary="New Section 301 duties over 'overcapacity' hit 14 partners; US stocks fall.",
         col=CORAL),
    dict(n=2, t=120, hh="02:00", region="MIDDLE EAST",
         head="Houthis hit Riyadh, threaten Red Sea",
         tl="Riyadh hit; Red Sea threatened",
         summary="Drone strikes a Riyadh fund tower; Saudis bomb Hodeidah.",
         col=AMBER),
    dict(n=3, t=480, hh="08:00", region="EUROPE",
         head="Merz: Russia wants more than Ukraine",
         tl="Merz warns on Russia",
         summary="Germany says Putin's aims exceed Ukraine; 700k dead estimate.",
         col=VIOLET),
    dict(n=4, t=1020, hh="17:00", region="GLOBAL MARKETS",
         head="AI rout drags Wall Street lower",
         tl="AI selloff deepens",
         summary="Nvidia doubts return; S&P 500 slumps and Asia markets dive.",
         col=BLUE),
    dict(n=5, t=1035, hh="17:15", region="AFRICA",
         head="Ebola outbreak disrupts east Congo",
         tl="Ebola crisis in Congo",
         summary="UN peacekeepers evacuate trapped health workers in DR Congo.",
         col=LIME),
    dict(n=6, t=1285, hh="21:25", region="CLIMATE",
         head="Six days above 2\u00b0C; COP31 stalls",
         tl="Six days above 2\u00b0C",
         summary="First six-day run 2\u00b0C over pre-industrial; COP31 deadlocks.",
         col=GOLD),
]

# Marker set for the globe: one marker per story region (US covers two stories).
MARKERS = [
    dict(label="US EAST", lon=-74.0, lat=39.0, col=CORAL, extra=BLUE),
    dict(label="RIYADH", lon=46.7, lat=24.7, col=AMBER, extra=None),
    dict(label="MOSCOW", lon=37.6, lat=55.8, col=VIOLET, extra=None),
    dict(label="CONGO", lon=15.3, lat=-4.3, col=LIME, extra=None),
    dict(label="GLOBAL", lon=-20.0, lat=-40.0, col=GOLD, extra=None),
]

# ---------------------------------------------------------------- helpers
def font(path, size):
    return ImageFont.truetype(path, size)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def text(draw, xy, s, f, fill, anchor="la", spacing=0.0):
    """Draw text, optionally with letter spacing.  Returns the drawn width."""
    if spacing == 0:
        draw.text(xy, s, font=f, fill=fill, anchor=anchor)
        return f.getlength(s)
    total = sum(f.getlength(c) + spacing for c in s) - spacing
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c in s:
        draw.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += f.getlength(c) + spacing
    return total


def wrap(s, f, maxw):
    """Greedy word-wrap, returns a list of lines whose width <= maxw."""
    out, cur = [], ""
    for word in s.split():
        cand = (cur + " " + word).strip()
        if cur and f.getlength(cand) > maxw:
            out.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def fit_headline(s, maxw, sizes=(15, 14, 13, 12.5)):
    """Largest bold size wrapping to <=2 lines and leaving no one-word widow."""
    for sz in sizes:
        f = font(FONT_BOLD, sz)
        lines = wrap(s, f, maxw)
        if len(lines) == 1:
            return f, lines, sz
        if len(lines) == 2:
            tail = lines[-1]
            if len(tail.split()) >= 2 or f.getlength(tail) >= 0.40 * maxw:
                return f, lines, sz
    f = font(FONT_BOLD, sizes[-1])
    return f, wrap(s, f, maxw)[:2], sizes[-1]


def chip(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill[:3],
                           outline=outline[:3] if outline else None, width=width)


def grad_panel(size, top, bot, radius):
    """A rounded vertical-gradient RGBA tile, used for cards and the hero."""
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(h):
        t = y / max(1, h - 1)
        arr[y, :, :] = [top[k] + (bot[k] - top[k]) * t for k in range(3)]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def dashed_ellipse(draw, box, colour, dash=9, gap=7, width=1):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    steps = 360
    on, acc, prev = True, 0.0, None
    for i in range(steps + 1):
        a = 2 * math.pi * i / steps
        p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
        if prev is not None:
            acc += math.dist(p, prev)
            if on:
                draw.line([prev, p], fill=colour, width=width)
            if on and acc >= dash:
                on, acc = False, 0.0
            elif not on and acc >= gap:
                on, acc = True, 0.0
        prev = p


def load_land():
    im = Image.open(os.path.join(ROOT, "landmask.png")).convert("L")
    return np.asarray(im, dtype=np.float32) / 255.0


# ---------------------------------------------------------------- globe
def globe_rgba(land, cx, cy, R, lat0_deg, lon0_deg):
    pad = 12
    D = R * 2 + pad * 2
    yy, xx = np.mgrid[0:D, 0:D]
    nx = (xx - (R + pad)) / R
    ny = ((R + pad) - yy) / R
    r2 = nx * nx + ny * ny
    inside = r2 <= 1.0
    z = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))
    lat0 = math.radians(lat0_deg)
    lon0 = math.radians(lon0_deg)
    sinlat = z * math.sin(lat0) + ny * math.cos(lat0)
    lat = np.arcsin(np.clip(sinlat, -1.0, 1.0))
    lon = lon0 + np.arctan2(nx, z * math.cos(lat0) - ny * math.sin(lat0))
    u = ((lon + math.pi) % (2 * math.pi)) / (2 * math.pi)
    v = (math.pi / 2 - lat) / math.pi
    mh, mw = land.shape
    mx = np.clip((u * mw).astype(np.int32), 0, mw - 1)
    my = np.clip((v * mh).astype(np.int32), 0, mh - 1)
    landmask = (land[my, mx] > 0.5) & inside

    tt = np.clip(r2, 0.0, 1.0)
    ocean = np.zeros((D, D, 3), dtype=np.float32)
    for k in range(3):
        ocean[:, :, k] = OCEAN_CORE[k] + (OCEAN_EDGE[k] - OCEAN_CORE[k]) * (tt ** 0.6)
    hl = np.clip(1.0 - np.sqrt((nx + 0.35) ** 2 + (ny - 0.4) ** 2) / 1.25, 0, 1) ** 2
    ocean += (np.array([22, 34, 52], dtype=np.float32) * hl[:, :, None] * 0.35)

    land_rgb = np.zeros((D, D, 3), dtype=np.float32)
    shade = (0.5 + 0.5 * np.clip(1.0 - r2, 0, 1)) ** 0.7
    for k in range(3):
        land_rgb[:, :, k] = LAND_DARK[k] + (LAND_LIGHT[k] - LAND_DARK[k]) * shade
    land_rgb = land_rgb * landmask[:, :, None] + ocean * (~landmask)[:, :, None]

    rgba = np.zeros((D, D, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(land_rgb, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.where(inside, 255, 0).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")

    lmask = Image.fromarray((landmask * 255).astype(np.uint8), "L")
    edge = np.asarray(lmask.filter(ImageFilter.MaxFilter(3)), dtype=np.int16) - \
        np.asarray(lmask, dtype=np.int16)
    edge = np.clip(edge, 0, 255).astype(np.uint8)
    edge = np.asarray(Image.fromarray(edge).filter(ImageFilter.GaussianBlur(0.6)))
    glow = Image.new("RGBA", (D, D), COAST + (0,))
    glow.putalpha(Image.fromarray((edge * 0.85).astype(np.uint8), "L"))
    img = Image.alpha_composite(img, glow)

    atm = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    ad = ImageDraw.Draw(atm)
    for i, a in enumerate((28, 20, 14, 9, 5)):
        rr = R - i * 2
        ad.ellipse([R + pad - rr, R + pad - rr, R + pad + rr, R + pad + rr],
                   outline=(74, 174, 214, a), width=2)
    img = Image.alpha_composite(img, atm)
    return img, (cx - R - pad, cy - R - pad), R, pad


def project(lat, lon, lat0_deg, lon0_deg, cx, cy, R):
    lat, lon = math.radians(lat), math.radians(lon)
    lat0, lon0 = math.radians(lat0_deg), math.radians(lon0_deg)
    d = lon - lon0
    x = math.cos(lat) * math.sin(d)
    y = math.cos(lat0) * math.sin(lat) - math.sin(lat0) * math.cos(lat) * math.cos(d)
    z = math.sin(lat0) * math.sin(lat) + math.cos(lat0) * math.cos(lat) * math.cos(d)
    return cx + x * R, cy - y * R, z >= 0


def graticule(draw, lat0_deg, lon0_deg, cx, cy, R):
    for lat in range(-60, 61, 30):
        pts = []
        for i in range(181):
            x, y, vis = project(lat, -180 + i * 2, lat0_deg, lon0_deg, cx, cy, R)
            if vis:
                pts.append((x, y))
            else:
                if len(pts) > 1:
                    draw.line(pts, fill=(54, 100, 136, 80), width=1)
                pts = []
        if len(pts) > 1:
            draw.line(pts, fill=(54, 100, 136, 80), width=1)
    for lon in range(-180, 180, 30):
        pts = []
        for i in range(121):
            x, y, vis = project(-90 + i * 1.5, lon, lat0_deg, lon0_deg, cx, cy, R)
            if vis:
                pts.append((x, y))
            else:
                if len(pts) > 1:
                    draw.line(pts, fill=(54, 100, 136, 70), width=1)
                pts = []
        if len(pts) > 1:
            draw.line(pts, fill=(54, 100, 136, 70), width=1)


# ---------------------------------------------------------------- background
def background():
    arr = np.zeros((H, W, 3), dtype=np.float32)
    for y in range(H):
        t = y / (H - 1)
        arr[y, :, :] = [BG_TOP[k] + (BG_BOT[k] - BG_TOP[k]) * t for k in range(3)]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # soft colour fields behind the two main zones
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([40, 120, 520, 560], fill=(26, 130, 160, 30))
    gd.ellipse([560, 120, 1010, 520], fill=(255, 92, 118, 20))
    gd.ellipse([200, 560, 900, 840], fill=(60, 90, 180, 16))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img, glow)

    # faint diagonal hatch for texture
    hatch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for x in range(-H, W, 46):
        hd.line([(x, 0), (x + H, H)], fill=(120, 160, 210, 8), width=1)
    img = Image.alpha_composite(img, hatch)

    # grain
    rng = np.random.default_rng(25)
    na = np.asarray(img.convert("RGB"), dtype=np.int16)
    for _ in range(900):
        x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
        na[y, x] = np.clip(na[y, x] + int(rng.integers(-14, 22)), 0, 255)
    img = Image.fromarray(na.astype(np.uint8), "RGB").convert("RGBA")

    # vignette
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vig = np.clip(1.0 - 0.42 * np.clip(d - 0.55, 0, 1.4), 0, 1)
    vimg = Image.fromarray((vig * 255).astype(np.uint8), "L")
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(Image.fromarray((255 - vig * 255).astype(np.uint8), "L"))
    img = Image.alpha_composite(img, black)
    return img


# ---------------------------------------------------------------- header
def header(img):
    d = ImageDraw.Draw(img)
    f_small = font(FONT_BOLD, 10)
    f_date = font(FONT_BOLD, 42)
    f_tag = font(FONT_BOLD, 14)
    text(d, (44, 16), "WORLD NEWS DIGEST", f_small, INK_DIM, spacing=2.0)
    text(d, (980, 16), "WEDNESDAY \u00b7 25 NOV 2026 \u00b7 UTC", f_small, INK_DIM,
         anchor="ra", spacing=1.6)
    text(d, (W // 2, 36), "25 NOVEMBER 2026", f_date, INK, anchor="ma")
    tw = f_date.getlength("25 NOVEMBER 2026")
    d.rounded_rectangle([W // 2 - tw / 2, 86, W // 2 + tw / 2, 90], radius=2, fill=AMBER)
    text(d, (W // 2, 94), "THE WORLD IN ONE DAY", f_tag, CYAN, anchor="ma", spacing=3.0)
    d.line([44, 124, 980, 124], fill=(48, 72, 106), width=1)
    return img


# ---------------------------------------------------------------- globe block
def globe_block(img, land):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy, R = 292, 322, 166
    lat0, lon0 = 18.0, -25.0
    g, off, _, _ = globe_rgba(land, cx, cy, R, lat0, lon0)
    img.paste(g, off, g)
    graticule(d, lat0, lon0, cx, cy, R)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(86, 198, 222, 130), width=1)
    dashed_ellipse(d, [cx - R - 9, cy - R - 9, cx + R + 9, cy + R + 9],
                   (86, 198, 222, 90), dash=10, gap=8, width=1)
    text(d, (cx, cy + R + 14), "EARTH \u00b7 25 NOV 2026", font(FONT_BOLD, 10),
         INK_FAINT, anchor="ma", spacing=1.6)

    f_lab = font(FONT_BOLD, 11)
    for m in MARKERS:
        x, y, vis = project(m["lat"], m["lon"], lat0, lon0, cx, cy, R)
        if not vis:
            x = cx + (R - 6) * (1 if x > cx else -1)
        col = m["col"]
        d.line([(x, y), (x + (m.get("dx", 0)), y + (m.get("dy", 0)))],
               fill=mix(col, (10, 18, 34), 0.25), width=1)
        d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=col, width=1)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col)
        if m["extra"]:
            d.ellipse([x + 1, y + 1, x + 9, y + 9], outline=m["extra"], width=1)
            d.ellipse([x + 3, y + 3, x + 7, y + 7], fill=m["extra"])
        # text label on the side away from the globe centre
        tw = f_lab.getlength(m["label"])
        if x < cx:
            bx1 = x - 13
            box = [bx1 - tw - 6, y - 8, bx1 + 2, y + 8]
            d.rounded_rectangle(box, radius=3, fill=(9, 15, 28), outline=col, width=1)
            text(d, (bx1 - 2, y), m["label"], f_lab, col, anchor="rm")
        else:
            bx0 = x + 13
            box = [bx0 - 2, y - 8, bx0 + tw + 6, y + 8]
            d.rounded_rectangle(box, radius=3, fill=(9, 15, 28), outline=col, width=1)
            text(d, (bx0 + 2, y), m["label"], f_lab, col, anchor="lm")
    return img


# ---------------------------------------------------------------- hero
def icon_tariff(d, x, y, s, col):
    base = y + s
    for i, hh in enumerate((0.35, 0.55, 0.78, 1.0)):
        bx = x + 2 + i * (s - 4) / 4
        bw = (s - 4) / 4 - 3
        d.rectangle([bx, base - s * hh, bx + bw, base], fill=col if i == 3 else mix(col, (10, 18, 34), 0.45))


def hero_panel(img):
    x0, y0, x1, y1 = 500, 142, 988, 508
    w, h = x1 - x0, y1 - y0
    tint = mix(CARD_BASE, CORAL, 0.16)
    panel = grad_panel((w, h), mix(tint, (30, 40, 60), 0.35), CARD_BASE, 16)
    img.paste(panel, (x0, y0), panel)
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([x0, y0, x1, y1], radius=16, outline=mix(CORAL, (10, 18, 34), 0.15), width=2)
    d.rounded_rectangle([x0, y0, x0 + 8, y1], radius=4, fill=CORAL)

    pad = 20
    x = x0 + pad
    text(d, (x, y0 + 16), "LEAD STORY", font(FONT_BOLD, 11), CORAL, spacing=2.4)
    text(d, (x1 - pad, y0 + 16), "13:10 UTC \u00b7 WASHINGTON", font(FONT_BOLD, 11),
         INK_DIM, anchor="ra", spacing=1.2)

    f_head = font(FONT_BOLD, 29)
    lines = wrap(STORIES[0]["head"], f_head, w - pad * 2)
    yy = y0 + 40
    for ln in lines:
        d.text((x, yy), ln, font=f_head, fill=INK)
        yy += 34
    yy += 6
    f_sum = font(FONT_REG, 14)
    for ln in wrap(STORIES[0]["summary"], f_sum, w - pad * 2 - 4):
        d.text((x, yy), ln, font=f_sum, fill=INK_DIM)
        yy += 18

    # three stat chips fill the gap between the summary and the motif
    f_chip = font(FONT_BOLD, 11)
    chips = [("14 PARTNERS", CORAL), ("SECTION 301", AMBER), ("STOCKS FALL", BLUE)]
    cxp = x
    for label, col in chips:
        cw = f_chip.getlength(label) + 20
        d.rounded_rectangle([cxp, yy + 8, cxp + cw, yy + 30], radius=11,
                            fill=mix(CARD_BASE, col, 0.18), outline=col, width=1)
        text(d, (cxp + cw / 2, yy + 12), label, f_chip, col, anchor="ma", spacing=0.8)
        cxp += cw + 8

    # decorative graphic band: 14 partner "ports" on a dotted route field,
    # wired to a hub, with a tall bar strip -- reads as a trade-war chart.
    gy = y1 - 96
    text(d, (x, gy - 20), "14 PARTNERS \u00b7 SECTION 301", font(FONT_BOLD, 9),
         INK_FAINT, spacing=1.4)
    # dotted route field
    for row in range(3):
        ry = gy + 6 + row * 14
        for col in range(0, 34):
            px = x + col * 12
            if px > x1 - pad:
                break
            d.ellipse([px, ry, px + 1, ry + 1], fill=(64, 92, 120, 120))
    hub = (x + 92, gy + 66)
    n = 14
    span = w - pad * 2
    pitch = span / n
    for i in range(n):
        bx = x + i * pitch
        hh = 22 + (i * 37 % 40)
        col = mix(CORAL, AMBER, i / (n - 1))
        d.line([(bx + pitch / 2, gy + 50), hub], fill=mix(CORAL, (10, 18, 34), 0.62), width=1)
        d.rounded_rectangle([bx, gy + 86 - hh, bx + pitch - 5, gy + 86], radius=2, fill=col)
        d.ellipse([bx + pitch / 2 - 1.5, gy + 48, bx + pitch / 2 + 1.5, gy + 51], fill=col)
    d.ellipse([hub[0] - 4, hub[1] - 4, hub[0] + 4, hub[1] + 4], fill=AMBER)
    d.ellipse([hub[0] - 8, hub[1] - 8, hub[0] + 8, hub[1] + 8], outline=AMBER, width=1)
    d.line([x, gy + 86, x1 - pad, gy + 86], fill=(70, 98, 128), width=1)
    return img


# ---------------------------------------------------------------- cards
def card(img, s, box, compact=False):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    col = s["col"]
    tint = mix(CARD_BASE, col, 0.10)
    panel = grad_panel((w, h), mix(tint, (32, 44, 66), 0.30), CARD_BASE, 11)
    img.paste(panel, (x0, y0), panel)
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([x0, y0, x1, y1], radius=11, outline=mix(col, (10, 18, 34), 0.45), width=1)

    # small corner numeral: texture only, never under the headline
    fwm = font(FONT_BOLD, 34)
    d.text((x1 - 10, y1 - 8), str(s["n"]), font=fwm,
           fill=mix(CARD_BASE, col, 0.26) + (64,), anchor="rd")

    pad = 13
    # icon tile
    s_icon = 26
    ix, iy = x0 + pad, y0 + pad
    d.rounded_rectangle([ix, iy, ix + s_icon, iy + s_icon], radius=6,
                        fill=mix(CARD_BASE, col, 0.16), outline=col, width=1)
    draw_card_icon(d, s["n"], ix + 5, iy + 5, s_icon - 10, col)
    tx = ix + s_icon + 8
    text(d, (tx, y0 + pad - 1), s["hh"], font(FONT_BOLD, 13), col)
    text(d, (x1 - pad, y0 + pad - 1), s["region"], font(FONT_BOLD, 8),
         INK_FAINT, anchor="ra", spacing=1.2)

    f_head = font(FONT_BOLD, 15)
    hlines = wrap(s["head"], f_head, w - pad * 2 - 2)[:2]
    yy = y0 + pad + 30
    for ln in hlines:
        d.text((x0 + pad, yy), ln, font=f_head, fill=INK)
        yy += 18
    if not compact:
        f_sum = font(FONT_REG, 10.5)
        slines = wrap(s["summary"], f_sum, w - pad * 2 - 2)[:2]
        yy = max(yy + 1, y0 + pad + 30 + 2 * 18 + 1)
        for ln in slines:
            d.text((x0 + pad, yy), ln, font=f_sum, fill=INK_DIM)
            yy += 13

    # tall cards get a small area chart in the spare lower half
    if h > 200:
        ctop = y0 + 150
        cbot = y1 - 30
        cw = w - pad * 2
        d.line([x0 + pad, cbot, x0 + pad + cw, cbot], fill=(52, 78, 108), width=1)
        vals = [0.62, 0.55, 0.60, 0.40, 0.46, 0.30, 0.34, 0.18, 0.24, 0.12]
        pts = []
        for i, v in enumerate(vals):
            px = x0 + pad + cw * i / (len(vals) - 1)
            py = ctop + (cbot - ctop) * (1 - v)
            pts.append((px, py))
        area = pts + [(pts[-1][0], cbot), (pts[0][0], cbot)]
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.polygon([(px - x0, py - y0) for px, py in area], fill=col + (46,))
        img.alpha_composite(layer, (x0, y0))
        d = ImageDraw.Draw(img, "RGBA")
        d.line(pts, fill=col, width=2)
        for px, py in pts:
            d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=col)
        text(d, (x0 + pad, ctop - 16), "S&P 500 \u00b7 ASIA DOWN", font(FONT_BOLD, 8),
             INK_FAINT, spacing=1.0)
    return img


def draw_card_icon(d, n, x, y, s, col):
    cx, cy = x + s / 2, y + s / 2
    if n == 2:  # radar / strike arcs
        for rr in (3, 6, 9):
            d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 200, 340, fill=col, width=1)
        d.ellipse([cx - 1.5, cy - 1.5, cx + 1.5, cy + 1.5], fill=col)
    elif n == 3:  # shield
        d.polygon([(cx, y), (x + s, y + 3), (x + s, cy + 3), (cx, y + s), (x, cy + 3), (x, y + 3)],
                  outline=col)
    elif n == 4:  # falling sparkline
        pts = [(x, y + 2), (x + s * 0.3, y + s * 0.4), (x + s * 0.55, y + s * 0.3),
               (x + s * 0.8, y + s * 0.75), (x + s, y + s * 0.62)]
        d.line(pts, fill=col, width=1)
        for p in pts[1:]:
            d.ellipse([p[0] - 1.5, p[1] - 1.5, p[0] + 1.5, p[1] + 1.5], fill=col)
    elif n == 5:  # medical cross
        d.rectangle([cx - 2, y + 1, cx + 2, y + s - 1], fill=col)
        d.rectangle([x + 1, cy - 2, x + s - 1, cy + 2], fill=col)
    elif n == 6:  # thermometer
        d.rounded_rectangle([cx - 2, y + 1, cx + 2, cy + 3], radius=2, outline=col, width=1)
        d.ellipse([cx - 4, cy + 1, cx + 4, cy + 9], outline=col, width=1)
        d.ellipse([cx - 2, cy + 3, cx + 2, cy + 7], fill=col)


def cards_grid(img):
    left = (36, 352)
    mid = (364, 668)
    right = (680, 988)
    # story 2 + 3 stacked left, 5 + 6 stacked right, 4 tall in the middle
    card(img, STORIES[1], (left[0], 524, left[1], 634))
    card(img, STORIES[2], (left[0], 644, left[1], 760))
    card(img, STORIES[3], (mid[0], 524, mid[1], 760), compact=False)
    card(img, STORIES[4], (right[0], 524, right[1], 632))
    card(img, STORIES[5], (right[0], 644, right[1], 760))
    return img


# ---------------------------------------------------------------- timeline
def timeline(img):
    d = ImageDraw.Draw(img, "RGBA")
    f_title = font(FONT_BOLD, 11)
    f_tick = font(FONT_BOLD, 9)
    f_lab = font(FONT_BOLD, 12)
    x0, x1, yax = 56, 968, 906

    text(d, (44, 772), "THE DAY IN 24 HOURS", f_title, CYAN, spacing=2.4)
    text(d, (980, 772), "ALL TIMES UTC", f_title, INK_FAINT, anchor="ra", spacing=1.8)

    d.rounded_rectangle([x0, yax - 2, x1, yax + 2], radius=2, fill=(28, 50, 78))
    d.line([x0, yax, x1, yax], fill=(78, 152, 192), width=2)

    def xt(t):
        return x0 + (t / 1440.0) * (x1 - x0)

    for h in range(0, 25, 3):
        x = xt(h * 60)
        d.line([x, yax - 4, x, yax + 4], fill=(112, 162, 202), width=1)
        text(d, (x, yax + 10), f"{h:02d}:00", f_tick, INK_FAINT, anchor="ma")

    # label lane packing: if a label would collide in a lane, move it up one.
    lanes = [872, 838, 804]  # top y of each above-axis lane
    placed = [[] for _ in lanes]
    order = sorted(STORIES, key=lambda s: s["t"])
    plans = []
    for s in order:
        x = xt(s["t"])
        lines = wrap(s["tl"], f_lab, 132)[:2]
        bw = max(f_lab.getlength(ln) for ln in lines) + 12
        bh = 15 * len(lines) + 2
        bx0 = min(max(x - bw / 2, 46), 974 - bw)
        lane = 0
        while lane < len(lanes):
            top = lanes[lane]
            box = [bx0, top, bx0 + bw, top + bh]
            clash = any(not (box[2] < o[0] - 4 or box[0] > o[2] + 4) for o in placed[lane])
            if not clash:
                placed[lane].append(box)
                break
            lane += 1
        top = lanes[min(lane, len(lanes) - 1)]
        plans.append((s, x, lines, bx0, bw, top, bh))

    # pass 1: axis markers and leader lines (drawn under every label)
    for s, x, lines, bx0, bw, top, bh in plans:
        d.ellipse([x - 5, yax - 5, x + 5, yax + 5], fill=s["col"])
        d.ellipse([x - 9, yax - 9, x + 9, yax + 9], outline=s["col"] + (80,), width=1)
        d.line([(x, yax - 7), (x, top + bh)], fill=s["col"] + (110,), width=1)

    # pass 2: opaque label chips, so no leader can cut through a glyph
    for s, x, lines, bx0, bw, top, bh in plans:
        d.rounded_rectangle([bx0, top, bx0 + bw, top + bh], radius=3,
                            fill=(9, 15, 28), outline=mix(s["col"], (9, 15, 28), 0.35),
                            width=1)
        for k, ln in enumerate(lines):
            text(d, (bx0 + bw / 2, top + k * 15 + 2), ln, f_lab, s["col"], anchor="ma")
    return img


# ---------------------------------------------------------------- footer
def footer(img):
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (44, 992), "Sources: AP \u00b7 Reuters \u00b7 BBC \u00b7 The Guardian   |   "
         "All times UTC   |   make.fun bounty news-image-20261125",
         font(FONT_REG, 9), (78, 94, 120))
    return img


def main():
    land = load_land()
    img = background()
    img = header(img)
    img = globe_block(img, land)
    img = hero_panel(img)
    img = cards_grid(img)
    img = timeline(img)
    img = footer(img)
    out = os.path.join(ROOT, "entry.png")
    img.convert("RGB").save(out, "PNG", optimize=True)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
