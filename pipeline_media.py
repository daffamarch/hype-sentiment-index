"""
metrika_render.py  --  Modul render grafis METRIKA (Pillow + FFmpeg, headless Linux).

Pakai dari pipeline_media.py:

    from metrika_render import render_carousel_slides, render_vertical_video

    paths = render_carousel_slides(content, "out/carousel")
    render_vertical_video(content, "out/reels.mp4", audio_path="out/voice.mp3", words=words)

Skema `content` (dict):
    program   : "INDEKS_KERINGAT" | "RADAR_SENTIMEN" | "ANGKA_BICARA"
    hook      : str                         pertanyaan hook di cover
    hero      : {"value": "35%", "label": str, "caption": str(opsional)}
    slides    : list (maks 4) of {
                    "heading": str,
                    "metric":  {"value": "Rp 5,4 jt", "label": str}   (opsional)
                    "columns": [{"title": str, "tone": "fact|pro|con|key|neutral",
                                 "points": [str, ...]}, ...]          (1-2 kolom)
                    "video_points": [str, ...]                         (opsional, utk video)
                }
    verdict   : str
    cta       : str
    sources   : list[str]
    date      : str (opsional)
    keywords  : list[str] (opsional, untuk validasi relevansi foto hero)
    hero_image: path foto hero (opsional)
    hero_image_meta : teks sumber foto (title/alt/og:title/URL) untuk cek relevansi
    narration : str (opsional, dipakai hanya jika `words` tidak diberikan)
"""
from __future__ import annotations

import functools
import logging
import math
import random
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

log = logging.getLogger("metrika")

# --------------------------------------------------------------------------- #
# 1. TOKEN DESAIN
# --------------------------------------------------------------------------- #
PALETTE = {
    "bg": "#0A0E17", "bg_deep": "#06080D",
    "surface": "#151C2C", "surface_hi": "#1E293B",
    "line": "#334155", "line_soft": "#1E293B", "grid": "#111827",
    "text": "#F1F5F9", "text_dim": "#94A3B8", "text_mute": "#64748B",
    "emerald": "#10B981", "gold": "#FACC15", "amber": "#F59E0B",
    "sky": "#38BDF8", "crimson": "#EF4444",
}

TONES = {  # tone kolom -> warna aksen
    "fact": "sky", "pro": "emerald", "con": "crimson", "key": "gold", "neutral": "text_dim",
}

PROGRAMS = {
    "INDEKS_KERINGAT": {"label": "INDEKS KERINGAT", "tag": "Daya Beli & Jam Kerja",
                        "accent": "gold", "tones": ("key", "neutral")},
    "RADAR_SENTIMEN": {"label": "RADAR SENTIMEN", "tag": "Peta Polarisasi Opini",
                       "accent": "sky", "tones": ("pro", "con")},
    "ANGKA_BICARA": {"label": "ANGKA BICARA", "tag": "Data Storytelling",
                     "accent": "emerald", "tones": ("fact", "key")},
}

W_IG, H_IG = 1080, 1350
W_V, H_V = 1080, 1920


def rgb(color: str) -> tuple[int, int, int]:
    c = PALETTE.get(color, color).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def _first_existing(cands: Sequence[str]) -> str:
    for c in cands:
        if Path(c).exists():
            return c
    raise FileNotFoundError(f"Font tidak ditemukan. Dicoba: {cands}")


_FD = "/usr/share/fonts/truetype/dejavu/"
_FL = "/usr/share/fonts/truetype/liberation/"
# Heavy = angka & judul, LABEL = label/pill, BODY = isi. Taruh Inter/dll di assets/fonts/ untuk override.
FONT_HEAVY = _first_existing(["assets/fonts/Inter-ExtraBold.ttf", _FD + "DejaVuSans-Bold.ttf",
                              _FL + "LiberationSans-Bold.ttf"])
FONT_LABEL = _first_existing(["assets/fonts/Inter-SemiBold.ttf", _FL + "LiberationSans-Bold.ttf",
                              _FD + "DejaVuSans-Bold.ttf"])
FONT_BODY = _first_existing(["assets/fonts/Inter-Regular.ttf", _FL + "LiberationSans-Regular.ttf",
                             _FD + "DejaVuSans.ttf"])


@functools.lru_cache(maxsize=512)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, int(size))


# --------------------------------------------------------------------------- #
# 2. TIPOGRAFI: wrap + auto-fit (anti-overflow)
# --------------------------------------------------------------------------- #
@dataclass
class FitResult:
    font: ImageFont.FreeTypeFont
    size: int
    lines: list[str]
    line_h: int
    width: float
    height: int
    truncated: bool = False


def wrap_words(words: Sequence[str], font, max_w: float) -> list[list[str]]:
    """Word-wrap greedy; kata yang lebih lebar dari kontainer dipecah per karakter."""
    lines: list[list[str]] = []
    cur: list[str] = []
    for w in words:
        if font.getlength(" ".join(cur + [w])) <= max_w:
            cur.append(w)
            continue
        if cur:
            lines.append(cur)
            cur = []
        if font.getlength(w) <= max_w:
            cur = [w]
        else:
            chunk = ""
            for ch in w:
                if font.getlength(chunk + ch) <= max_w:
                    chunk += ch
                else:
                    lines.append([chunk])
                    chunk = ch
            cur = [chunk] if chunk else []
    if cur:
        lines.append(cur)
    return lines


def _layout(text: str, font, max_w: float) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        wl = wrap_words(para.split(), font, max_w)
        out += [" ".join(l) for l in wl] if wl else [""]
    return out


def _ellipsize(line: str, font, max_w: float) -> str:
    while line and font.getlength(line + "…") > max_w:
        line = line[:-1]
    return line.rstrip() + "…"


def fit_text(text: str, box_w: float, box_h: float, max_size: int, min_size: int,
             font_path: str, line_height: float = 1.4, max_lines: int | None = None) -> FitResult:
    """Binary search ukuran font terbesar yang muat penuh di (box_w x box_h)."""
    def attempt(size: int):
        font = load_font(font_path, size)
        lines = _layout(text, font, box_w)
        line_h = int(round(size * line_height))
        ok = (len(lines) * line_h <= box_h
              and (max_lines is None or len(lines) <= max_lines)
              and max((font.getlength(l) for l in lines), default=0) <= box_w + 0.5)
        return ok, font, lines, line_h

    lo, hi, best = min_size, max_size, None
    while lo <= hi:
        mid = (lo + hi) // 2
        ok, font, lines, line_h = attempt(mid)
        if ok:
            best = (mid, font, lines, line_h)
            lo = mid + 1
        else:
            hi = mid - 1
    truncated = False
    if best is None:  # pilihan terakhir: min size + ellipsis, tidak pernah overflow
        _, font, lines, line_h = attempt(min_size)
        cap = max(1, int(box_h // line_h))
        if max_lines:
            cap = min(cap, max_lines)
        if len(lines) > cap:
            lines = lines[:cap]
            lines[-1] = _ellipsize(lines[-1], font, box_w)
            truncated = True
        lines = [l if font.getlength(l) <= box_w else _ellipsize(l, font, box_w) for l in lines]
        best = (min_size, font, lines, line_h)
        log.warning("Teks dipotong di min_font_size: %r", text[:60])
    size, font, lines, line_h = best
    return FitResult(font, size, lines, line_h, max((font.getlength(l) for l in lines), default=0),
                     len(lines) * line_h, truncated)


def auto_fit_multiline_text(draw: ImageDraw.ImageDraw, text: str, box: tuple, max_font_size: int,
                            min_font_size: int, font_path: str, fill="text", line_height: float = 1.4,
                            align: str = "left", valign: str = "top", max_lines: int | None = None,
                            render: bool = True) -> FitResult:
    """Hitung wrapping + ukuran font terbaik, lalu (opsional) gambar. box = (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = box
    fit = fit_text(text, x1 - x0, y1 - y0, max_font_size, min_font_size, font_path, line_height, max_lines)
    if render:
        top = y0 if valign == "top" else (y1 - fit.height if valign == "bottom"
                                          else y0 + (y1 - y0 - fit.height) / 2)
        draw_lines(draw, fit, (x0, top, x1), fill, align)
    return fit


def draw_lines(draw, fit: FitResult, xy: tuple, fill, align="left", dy=0):
    x0, top, x1 = xy
    for i, line in enumerate(fit.lines):
        cy = top + fit.line_h * (i + 0.5) + dy
        if align == "left":
            draw.text((x0, cy), line, font=fit.font, fill=rgb(fill), anchor="lm")
        elif align == "center":
            draw.text(((x0 + x1) / 2, cy), line, font=fit.font, fill=rgb(fill), anchor="mm")
        else:
            draw.text((x1, cy), line, font=fit.font, fill=rgb(fill), anchor="rm")


def fit_text_stack(texts: Sequence[str], width: float, height: float, max_size: int, min_size: int,
                   font_path: str, line_height: float = 1.4, gap: int = 22):
    """Satu ukuran font untuk semua butir (konsisten). Jika tetap tidak muat, butir terakhir dibuang."""
    texts = list(texts)

    def attempt(items, size):
        font = load_font(font_path, size)
        lines = [_layout(t, font, width) for t in items]
        lh = int(round(size * line_height))
        total = sum(len(l) * lh for l in lines) + gap * max(0, len(items) - 1)
        return total <= height, font, lines, lh

    while texts:
        lo, hi, best = min_size, max_size, None
        while lo <= hi:
            mid = (lo + hi) // 2
            ok, font, lines, lh = attempt(texts, mid)
            if ok:
                best, lo = (mid, font, lines, lh), mid + 1
            else:
                hi = mid - 1
        if best:
            return texts, *best
        log.warning("Butir dibuang agar muat: %r", texts[-1][:50])
        texts = texts[:-1]
    return [], min_size, load_font(font_path, min_size), [], int(min_size * line_height)


def draw_tracked(draw, xy, text, font, fill, tracking=3.0, anchor="lm"):
    """Teks dengan letter-spacing (untuk brand & label kapital)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=rgb(fill), anchor=anchor)
        x += font.getlength(ch) + tracking
    return x


def tracked_width(text, font, tracking=3.0):
    return sum(font.getlength(c) + tracking for c in text) - tracking


# --- angka besar: pisah prefix/angka/suffix, counter-friendly --------------- #
_VAL_RE = re.compile(r"^(\D*?)(\d(?:[\d.,]*\d)?)(.*)$", re.S)


def split_value(value: str):
    m = _VAL_RE.match(value.strip())
    return (m.group(1), m.group(2), m.group(3)) if m else ("", value, "")


def parse_number(s: str):
    """'5.396.763' -> (5396763, 0, '.', None) ; '35,5' -> (35.5, 1, None, ',') (format Indonesia)."""
    th = dec = None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        th = "," if dec == "." else "."
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        parts = s.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:
            th = sep
        else:
            dec = sep
    clean = s.replace(th, "") if th else s
    if dec:
        clean = clean.replace(dec, ".")
    decimals = len(clean.split(".")[1]) if dec else 0
    return float(clean), decimals, th, dec


def format_number(v: float, decimals: int, th, dec) -> str:
    s = f"{v:,.{decimals}f}".replace(",", "\x00").replace(".", "\x01")
    return s.replace("\x00", th or "").replace("\x01", dec or ".")


def draw_metric_value(draw, value: str, box: tuple, color, max_size=260, min_size=60,
                      align="center", suffix_scale=0.46, live_number: str | None = None,
                      fit_cache: dict | None = None):
    """Angka Heavy raksasa + prefix/suffix kecil (Rp, %, jam). Selalu muat di box.
    live_number: ganti bagian angka (untuk animasi counter) tanpa mengubah ukuran font."""
    x0, y0, x1, y1 = box
    pre, num, suf = split_value(value)
    key = (value, x1 - x0, y1 - y0, max_size)
    if fit_cache is not None and key in fit_cache:
        size = fit_cache[key]
    else:
        size = max_size
        while size > min_size:
            fb, fs = load_font(FONT_HEAVY, size), load_font(FONT_HEAVY, int(size * suffix_scale))
            w = fb.getlength(num) + fs.getlength(pre + suf) + (14 if (pre or suf) else 0)
            if w <= x1 - x0 and size * 1.0 <= y1 - y0:
                break
            size -= 2
        if fit_cache is not None:
            fit_cache[key] = size
    fb, fs = load_font(FONT_HEAVY, size), load_font(FONT_HEAVY, max(14, int(size * suffix_scale)))
    shown = live_number if live_number is not None else num
    wp, ws = fs.getlength(pre), fs.getlength(suf)
    wn_final = fb.getlength(num)
    wn = fb.getlength(shown)
    gap = 10 if pre else 0
    gap2 = 10 if suf else 0
    total = wp + gap + wn_final + gap2 + ws
    x = x0 if align == "left" else (x0 + x1 - total) / 2
    cy = (y0 + y1) / 2
    base = cy + fb.getbbox("0")[3] / 2 - fb.getbbox("0")[1] / 2 - fb.getbbox("0")[1] / 2 + 0
    base = cy + (fb.getbbox("0")[3] - fb.getbbox("0")[1]) / 2   # baseline angka, tengah vertikal
    c = rgb(color)
    if pre:
        draw.text((x, base), pre, font=fs, fill=c, anchor="ls")
    draw.text((x + wp + gap, base), shown, font=fb, fill=c, anchor="ls")
    if suf:
        draw.text((x + wp + gap + wn_final + gap2, base), suf, font=fs, fill=c, anchor="ls")


# --------------------------------------------------------------------------- #
# 3. PRIMITIF GAMBAR (anti-aliased)
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=256)
def _rr_mask(w: int, h: int, r: int, ss: int = 4) -> Image.Image:
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@functools.lru_cache(maxsize=128)
def _circle_mask(d: int, ss: int = 6) -> Image.Image:
    m = Image.new("L", (d * ss, d * ss), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=255)
    return m.resize((d, d), Image.LANCZOS)


def _scale(mask: Image.Image, a: float) -> Image.Image:
    return mask if a >= 1 else mask.point([int(i * a) for i in range(256)])


def fill_rr(img, box, radius, fill=None, outline=None, width=1, alpha=1.0, outline_alpha=1.0):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    outer = _rr_mask(w, h, int(radius))
    if fill is not None:
        img.paste(rgb(fill), (x0, y0), _scale(outer, alpha))
    if outline is not None:
        inner = Image.new("L", (w, h), 0)
        iw, ih = w - 2 * width, h - 2 * width
        if iw > 0 and ih > 0:
            inner.paste(_rr_mask(iw, ih, max(0, int(radius) - width)), (width, width))
        ring = ImageChops.subtract(outer, inner)
        img.paste(rgb(outline), (x0, y0), _scale(ring, outline_alpha))


def fill_circle(img, cx, cy, r, color, alpha=1.0):
    d = int(round(r * 2))
    img.paste(rgb(color), (int(round(cx - r)), int(round(cy - r))), _scale(_circle_mask(d), alpha))


def glow(img, box, radius, color, blur=36, alpha=0.30, spread=0):
    x0, y0, x1, y1 = box
    pad = blur * 3
    w, h = int(x1 - x0 + 2 * pad), int(y1 - y0 + 2 * pad)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((pad - spread, pad - spread, w - pad + spread, h - pad + spread),
                                        radius, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    img.paste(rgb(color), (int(x0 - pad), int(y0 - pad)), _scale(m, alpha))


def soft_shadow(img, box, radius, blur=22, dy=14, alpha=0.55):
    x0, y0, x1, y1 = box
    glow(img, (x0, y0 + dy, x1, y1 + dy), radius, "#000000", blur=blur, alpha=alpha)


def vgradient_mask(w, h, top=0.0, bottom=1.0) -> Image.Image:
    g = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    return g.point([int(255 * (top + (bottom - top) * i / 255)) for i in range(256)])


def draw_pill(img, draw, x, cy, text, accent, size=26, pad_x=26, height=None, dot=True, tracking=2.0):
    font = load_font(FONT_LABEL, size)
    h = height or int(size * 2.1)
    tw = tracked_width(text, font, tracking)
    dot_w = (size * 0.55 + 14) if dot else 0
    w = int(tw + dot_w + pad_x * 2)
    box = (x, cy - h / 2, x + w, cy + h / 2)
    fill_rr(img, box, h // 2, fill=accent, alpha=0.14, outline=accent, width=2, outline_alpha=0.85)
    tx = x + pad_x
    if dot:
        fill_circle(img, tx + size * 0.2, cy, size * 0.2, accent)
        tx += dot_w
    draw_tracked(draw, (tx, cy), text, font, accent, tracking)
    return box


def draw_brand_mark(img, draw, x, cy, accent, size=30):
    s = size
    fill_rr(img, (x, cy - s // 2, x + s, cy + s // 2), 8, fill=accent)
    bar = s // 6
    for i, hgt in enumerate((0.35, 0.55, 0.78)):  # 3 bar naik = metrik
        bx = x + s * 0.18 + i * (bar + bar * 0.55)
        draw.rectangle((bx, cy + s * 0.3 - s * hgt * 0.7, bx + bar, cy + s * 0.3), fill=rgb("bg"))
    f = load_font(FONT_HEAVY, int(size * 0.95))
    draw_tracked(draw, (x + s + 16, cy), "METRIKA", f, "text", tracking=5)


def draw_arrow(draw, x, cy, color, length=44, th=4):
    c = rgb(color)
    draw.line((x, cy, x + length, cy), fill=c, width=th)
    draw.line((x + length - 14, cy - 12, x + length, cy), fill=c, width=th)
    draw.line((x + length - 14, cy + 12, x + length, cy), fill=c, width=th)


# --------------------------------------------------------------------------- #
# 4. BACKGROUND DATA-GRID & HERO FALLBACK
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=24)
def _bg_cached(size, accent, mode, seed, glow_pos):
    W, H = size
    img = Image.new("RGB", size, rgb("bg"))
    # glow aksen (radial)
    rg = Image.radial_gradient("L").point([int(255 * max(0.0, 1 - i / 181) ** 2) for i in range(256)])  # 0 di tepi: tanpa garis kotak
    gw = int(W * 1.1)
    rg = rg.resize((gw, gw), Image.BICUBIC)
    gx = int(W * 0.55) if glow_pos == "tr" else int(-W * 0.35)
    gy = int(-gw * 0.45) if glow_pos == "tr" else int(H - gw * 0.55)
    img.paste(rgb(accent), (gx, gy), _scale(rg, 0.13))
    if mode in ("dots", "grid"):
        pitch = 36
        ss = 8
        tile = Image.new("L", (pitch * ss, pitch * ss), 0)
        ImageDraw.Draw(tile).ellipse((pitch * ss / 2 - 1.5 * ss, pitch * ss / 2 - 1.5 * ss,
                                      pitch * ss / 2 + 1.5 * ss, pitch * ss / 2 + 1.5 * ss), fill=255)
        tile = tile.resize((pitch, pitch), Image.LANCZOS)
        mask = Image.new("L", size, 0)
        for yy in range(0, H, pitch):
            for xx in range(0, W, pitch):
                mask.paste(tile, (xx, yy))
        img.paste(rgb("#26324A"), (0, 0), _scale(mask, 0.75))
        d = ImageDraw.Draw(img)
        major = 180
        for xx in range(0, W + 1, major):
            d.line((xx, 0, xx, H), fill=rgb("grid"), width=1)
        for yy in range(0, H + 1, major):
            d.line((0, yy, W, yy), fill=rgb("grid"), width=1)
        for yy in range(major, H, major):  # tanda + di persimpangan
            for xx in range(major, W, major):
                d.line((xx - 7, yy, xx + 7, yy), fill=rgb("#2A3650"), width=1)
                d.line((xx, yy - 7, xx, yy + 7), fill=rgb("#2A3650"), width=1)
    if mode == "dots":  # tren abstrak sangat halus di bagian bawah
        rnd = random.Random(seed)
        ss = 2
        layer = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        n, v, pts = 14, 0.55, []
        for i in range(n):
            v = min(0.9, max(0.15, v + rnd.uniform(-0.14, 0.2)))
            pts.append((i * W / (n - 1) * ss, (H * 0.97 - v * H * 0.16) * ss))
        a = rgb(accent)
        ld.line(pts, fill=a + (38,), width=3 * ss, joint="curve")
        for p in pts:
            ld.ellipse((p[0] - 6 * ss, p[1] - 6 * ss, p[0] + 6 * ss, p[1] + 6 * ss), fill=a + (70,))
        layer = layer.resize((W, H), Image.LANCZOS)
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    vg = Image.radial_gradient("L").resize((W, H), Image.BICUBIC)  # vignette
    img.paste(rgb("bg_deep"), (0, 0), _scale(vg, 0.55))
    return img


def make_data_grid_background(size=(W_IG, H_IG), accent="gold", mode="dots", seed=7, glow_pos="tr"):
    """Background dot-matrix + koordinat grid ala koran finansial. Dipakai juga sebagai hero fallback."""
    return _bg_cached(tuple(size), accent, mode, seed, glow_pos).copy()


@dataclass
class HeroCheck:
    ok: bool
    reason: str
    image: Image.Image | None = None


def validate_hero_image(src, keywords: Sequence[str] = (), source_text: str = "", min_side=800,
                        min_sharpness=14.0, banned_terms=("logo", "icon", "favicon", "avatar",
                                                         "placeholder", "sprite", "thumbnail"),
                        require_keyword_match=True) -> HeroCheck:
    """Gerbang foto hero. TANPA model vision, relevansi hanya bisa dicek lewat kecocokan kata kunci
    antara topik dan metadata sumber (title/alt/og:title/URL). Default: ragu -> fallback grafis."""
    if src is None:
        return HeroCheck(False, "tidak ada gambar")
    try:
        im = src if isinstance(src, Image.Image) else Image.open(src)
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:  # noqa: BLE001
        return HeroCheck(False, f"gagal dibuka: {e}")
    w, h = im.size
    if min(w, h) < min_side:
        return HeroCheck(False, f"resolusi rendah {w}x{h}")
    if not 0.55 <= w / h <= 2.4:
        return HeroCheck(False, "aspek rasio ekstrem")
    meta = source_text.lower()
    if any(t in meta for t in banned_terms):
        return HeroCheck(False, "metadata mengindikasikan logo/ikon")
    if require_keyword_match:
        kws = [k.lower() for k in keywords if len(k) > 2]
        if not kws or not any(k in meta for k in kws):
            return HeroCheck(False, "tidak ada kecocokan kata kunci topik")
    g = ImageOps.grayscale(im)
    g.thumbnail((480, 480))
    sharp = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).stddev[0]
    if sharp < min_sharpness:
        return HeroCheck(False, f"buram/datar (sharpness {sharp:.1f})")
    if max(g.histogram()) / (g.width * g.height) > 0.45:
        return HeroCheck(False, "dominan satu warna (logo/grafis datar)")
    return HeroCheck(True, "ok", im)


def paste_cover(img, photo: Image.Image, box, radius, darken=0.55):
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    p = ImageOps.fit(photo, (w, h), Image.LANCZOS, centering=(0.5, 0.4))
    p = ImageOps.autocontrast(p, cutoff=1)
    base = Image.new("RGB", (w, h), rgb("bg"))
    p = Image.blend(p, base, darken)
    shade = vgradient_mask(w, h, 0.15, 1.0)
    p.paste(rgb("bg"), (0, 0), shade)
    img.paste(p, (x0, y0), _rr_mask(w, h, radius))


def draw_hero_backdrop(img, box, accent, photo=None, seed=3, radius=36):
    """Isi kartu hero: foto tervalidasi atau poster 'Big Data Number' (dot-matrix lokal + glow)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    if photo is not None:
        paste_cover(img, photo, box, radius)
        return
    fill_rr(img, box, radius, fill="surface")
    bg = make_data_grid_background((w, h), accent, "grid", seed, glow_pos="tr")
    img.paste(bg, (x0, y0), _rr_mask(w, h, radius))
    glow(img, (x0 + 40, y1 - 120, x1 - 40, y1 - 40), 30, accent, blur=50, alpha=0.10)


# --------------------------------------------------------------------------- #
# 5. KOMPONEN EDITORIAL
# --------------------------------------------------------------------------- #
def draw_editorial_card(img, draw, box, title: str | None = None, accent="sky", radius=30,
                        shadow=True, pad=32):
    """Kartu modern: shadow lembut, surface bertingkat, soft header pill, separator elegan.
    Return inner box (x0,y0,x1,y1) untuk konten."""
    x0, y0, x1, y1 = box
    if shadow:
        soft_shadow(img, box, radius)
    fill_rr(img, box, radius, fill="surface", outline="line", width=1, outline_alpha=0.9)
    top_hi = Image.new("L", (int(x1 - x0), int(radius * 2)), 0)  # highlight tipis di tepi atas
    img.paste(rgb("#FFFFFF"), (int(x0), int(y0)),
              ImageChops.multiply(_rr_mask(int(x1 - x0), int(radius * 2), radius).point(lambda v: v // 40),
                                  vgradient_mask(int(x1 - x0), int(radius * 2), 1.0, 0.0)))
    cy = y0 + 28
    inner_top = y0 + pad
    if title:
        f = fit_text(title.upper(), (x1 - x0) - pad * 2 - 90, 40, 24, 16, FONT_LABEL, 1.0, 1)
        font = f.font
        tw = tracked_width(f.lines[0], font, 2)
        ph = 46
        bw = int(tw + 26 * 2 + 22)
        cyp = cy + ph / 2
        fill_rr(img, (x0 + pad, cy, x0 + pad + bw, cy + ph), ph // 2, fill=accent, alpha=0.14,
                outline=accent, width=2, outline_alpha=0.8)
        fill_circle(img, x0 + pad + 24, cyp, 5, accent)
        draw_tracked(draw, (x0 + pad + 40, cyp), f.lines[0], font, accent, 2)
        sep_y = cy + ph + 22
        draw.line((x0 + pad, sep_y, x1 - pad, sep_y), fill=rgb("line"), width=1)
        draw.line((x0 + pad, sep_y, x0 + pad + 64, sep_y), fill=rgb(accent), width=3)
        inner_top = sep_y + 26
    return (x0 + pad, inner_top, x1 - pad, y1 - pad + 4)


def draw_bullet_points(img, draw, box, points: Sequence[str], accent, max_size=38, min_size=22,
                       gap=24, bullet_r=7):
    x0, y0, x1, y1 = box
    ind = 34
    items, size, font, lines, lh = fit_text_stack(points, (x1 - x0) - ind, y1 - y0, max_size, min_size,
                                                  FONT_BODY, 1.4, gap)
    y = y0
    for it_lines in lines:
        first_cy = y + lh / 2
        fill_circle(img, x0 + bullet_r, first_cy, bullet_r, accent)
        fill_circle(img, x0 + bullet_r, first_cy, bullet_r * 0.4, "surface")
        for i, ln in enumerate(it_lines):
            draw.text((x0 + ind, y + lh * (i + 0.5)), ln, font=font, fill=rgb("text"), anchor="lm")
        y += len(it_lines) * lh + gap


def _tone_color(tone: str, fallback: str) -> str:
    return TONES.get(tone, fallback)


def draw_header(img, draw, program: dict, idx: int, total: int, date: str = "", y=92, margin=72, W=W_IG):
    draw_brand_mark(img, draw, margin, y, program["accent"])
    f = load_font(FONT_LABEL, 26)
    label = f"{idx:02d} / {total:02d}" if idx else (date or "").upper()
    if label:
        draw.text((W - margin, y), label, font=f, fill=rgb("text_dim"), anchor="rm")


def draw_progress(img, draw, idx: int, total: int, accent: str, y=1262, margin=72, W=W_IG, handle="@metrika.id"):
    seg_gap = 10
    seg_w = (W - 2 * margin - seg_gap * (total - 1)) / total
    for i in range(total):
        x = margin + i * (seg_w + seg_gap)
        done = i < idx
        fill_rr(img, (x, y, x + seg_w, y + 8), 4, fill=accent if done else "surface_hi",
                alpha=1.0 if i == idx - 1 else (0.45 if done else 1.0))
    f = load_font(FONT_LABEL, 22)
    draw.text((margin, y + 46), handle, font=f, fill=rgb("text_mute"), anchor="lm")
    draw.text((W - margin, y + 46), "Data untuk kamu yang berpikir", font=load_font(FONT_BODY, 22),
              fill=rgb("text_mute"), anchor="rm")


# --------------------------------------------------------------------------- #
# 6. CAROUSEL (6 slide, 1080x1350)
# --------------------------------------------------------------------------- #
def _program(content) -> dict:
    p = content.get("program")
    if p not in PROGRAMS:
        raise ValueError(f"program harus salah satu dari {list(PROGRAMS)}")
    return PROGRAMS[p]


def _hero_photo(content) -> Image.Image | None:
    chk = validate_hero_image(content.get("hero_image"), content.get("keywords", ()),
                              content.get("hero_image_meta", ""))
    if content.get("hero_image"):
        log.info("Hero foto: %s (%s)", "dipakai" if chk.ok else "ditolak -> fallback grafis", chk.reason)
    return chk.image if chk.ok else None


def _slide_cover(content, prog, photo, total, M=72):
    W, H = W_IG, H_IG
    accent = prog["accent"]
    img = make_data_grid_background((W, H), accent, "dots", seed=len(content.get("hook", "")))
    d = ImageDraw.Draw(img)
    draw_header(img, d, prog, 0, total, content.get("date", ""))
    draw_pill(img, d, M, 214, f"PROGRAM  /  {prog['label']}", accent, size=30, pad_x=34, height=76)
    d.text((M, 290), prog["tag"].upper(), font=load_font(FONT_LABEL, 22), fill=rgb("text_mute"), anchor="lm")
    auto_fit_multiline_text(d, content["hook"], (M, 330, W - M, 700), 96, 50, FONT_HEAVY, "text",
                            line_height=1.2, valign="top")
    hb = (M, 730, W - M, 1170)
    soft_shadow(img, hb, 36)
    draw_hero_backdrop(img, hb, accent, photo)
    fill_rr(img, hb, 36, outline="line", width=1)
    hero = content["hero"]
    draw_tracked(d, (M + 40, hb[1] + 54), "ANGKA KUNCI", load_font(FONT_LABEL, 24), accent, 4)
    draw_metric_value(d, hero["value"], (M + 40, hb[1] + 90, W - M - 40, hb[1] + 300), "gold",
                      max_size=250, min_size=80, align="left")
    d.line((M + 40, hb[1] + 318, M + 40 + 90, hb[1] + 318), fill=rgb("gold"), width=4)
    auto_fit_multiline_text(d, hero["label"], (M + 40, hb[1] + 338, W - M - 40, hb[3] - 36), 38, 24,
                            FONT_LABEL, "text", line_height=1.35, valign="top")
    d.text((M, 1212), "Geser untuk breakdown data", font=load_font(FONT_LABEL, 28), fill=rgb("text_dim"),
           anchor="lm")
    draw_arrow(d, W - M - 56, 1212, accent)
    draw_progress(img, d, 1, total, accent)
    return img


def _slide_content(content, prog, sl, idx, total, M=72):
    W, H = W_IG, H_IG
    accent = prog["accent"]
    img = make_data_grid_background((W, H), accent, "grid", seed=idx, glow_pos="tr" if idx % 2 else "bl")
    d = ImageDraw.Draw(img)
    draw_header(img, d, prog, idx + 1, total)
    draw_pill(img, d, M, 168, prog["label"], accent, size=22, height=48, pad_x=22)
    auto_fit_multiline_text(d, sl["heading"], (M, 214, W - M, 410), 66, 36, FONT_HEAVY, "text",
                            line_height=1.2)
    top = 440
    m = sl.get("metric")
    if m:
        mb = (M, top, W - M, top + 168)
        draw_editorial_card(img, d, mb, None, accent, radius=26)
        glow(img, (M + 20, mb[1] + 150, M + 220, mb[3] - 6), 20, "gold", blur=30, alpha=0.10)
        draw_metric_value(d, m["value"], (M + 36, mb[1] + 14, M + 470, mb[3] - 14), "gold", 120, 48,
                          align="left")
        d.line((M + 500, mb[1] + 36, M + 500, mb[3] - 36), fill=rgb("line"), width=1)
        auto_fit_multiline_text(d, m["label"], (M + 530, mb[1] + 20, W - M - 36, mb[3] - 20), 34, 20,
                                FONT_LABEL, "text", line_height=1.35, valign="middle")
        top += 168 + 28
    cols = sl.get("columns", [])[:2]
    area = (M, top, W - M, 1208)
    gap = 32
    n = max(1, len(cols))
    cw = (area[2] - area[0] - gap * (n - 1)) / n
    for i, col in enumerate(cols):
        tone = col.get("tone") or prog["tones"][min(i, 1)]
        c = _tone_color(tone, accent)
        bx = (area[0] + i * (cw + gap), area[1], area[0] + i * (cw + gap) + cw, area[3])
        inner = draw_editorial_card(img, d, bx, col.get("title", ""), c)
        draw_bullet_points(img, d, inner, col.get("points", []), c, 40 if n == 1 else 36, 22)
    draw_progress(img, d, idx + 1, total, accent)
    return img


def _slide_verdict(content, prog, total, M=72):
    W, H = W_IG, H_IG
    accent = prog["accent"]
    img = make_data_grid_background((W, H), accent, "grid", seed=99, glow_pos="bl")
    d = ImageDraw.Draw(img)
    draw_header(img, d, prog, total, total)
    draw_pill(img, d, M, 168, prog["label"], accent, size=22, height=48, pad_x=22)
    d.text((M, 262), "Kesimpulan data", font=load_font(FONT_HEAVY, 58), fill=rgb("text"), anchor="lm")
    vb = (M, 330, W - M, 790)
    inner = draw_editorial_card(img, d, vb, "Verdict objektif", accent)
    auto_fit_multiline_text(d, content["verdict"], inner, 50, 26, FONT_LABEL, "text", line_height=1.4)
    cb = (M, 820, W - M, 1010)
    soft_shadow(img, cb, 30)
    fill_rr(img, cb, 30, fill=accent, alpha=0.12, outline=accent, width=2, outline_alpha=0.8)
    fill_circle(img, cb[0] + 62, (cb[1] + cb[3]) / 2, 26, accent)
    d.text((cb[0] + 62, (cb[1] + cb[3]) / 2), "?", font=load_font(FONT_HEAVY, 34), fill=rgb("bg"), anchor="mm")
    auto_fit_multiline_text(d, content["cta"], (cb[0] + 120, cb[1] + 24, cb[2] - 36, cb[3] - 24), 38, 22,
                            FONT_LABEL, "text", line_height=1.35, valign="middle")
    d.text((M, 1050), "SUMBER DATA", font=load_font(FONT_LABEL, 22), fill=rgb(accent), anchor="lm")
    d.line((M, 1078, W - M, 1078), fill=rgb("line"), width=1)
    src = "\n".join(f"{i + 1}.  {s}" for i, s in enumerate(content.get("sources", [])))
    auto_fit_multiline_text(d, src, (M, 1096, W - M, 1236), 26, 14, FONT_BODY, "text_dim", line_height=1.45)
    draw_progress(img, d, total, total, accent)
    return img


def render_carousel_images(content: dict) -> list[Image.Image]:
    prog = _program(content)
    photo = _hero_photo(content)
    slides = content.get("slides", [])[:4]
    total = 2 + len(slides)
    out = [_slide_cover(content, prog, photo, total)]
    for i, sl in enumerate(slides, start=1):
        out.append(_slide_content(content, prog, sl, i, total))
    out.append(_slide_verdict(content, prog, total))
    return out


def render_carousel_slides(content: dict, out_dir: str | Path, fmt: str = "PNG", quality: int = 95) -> list[Path]:
    """Render slide 1080x1350 untuk ketiga program. Return daftar path file."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, im in enumerate(render_carousel_images(content), start=1):
        p = out_dir / f"slide_{i:02d}.{fmt.lower().replace('jpeg', 'jpg')}"
        if fmt.upper() in ("JPG", "JPEG"):
            im.save(p, "JPEG", quality=quality, subsampling=0, optimize=True)
        else:
            im.save(p, "PNG", optimize=True)
        paths.append(p)
    return paths


# --------------------------------------------------------------------------- #
# 7. VIDEO VERTIKAL (1080x1920) -- frame dipipa langsung ke FFmpeg
# --------------------------------------------------------------------------- #
def words_from_edge_boundaries(boundaries: Sequence[dict]) -> list[dict]:
    """Edge-TTS WordBoundary {'offset','duration','text'} (satuan 100ns) -> [{'text','start','end'}]."""
    return [{"text": b["text"], "start": b["offset"] / 1e7, "end": (b["offset"] + b["duration"]) / 1e7}
            for b in boundaries]


def _estimate_words(text: str, duration: float) -> list[dict]:
    toks = text.split()
    if not toks:
        return []
    weights = [len(t) + 2 for t in toks]
    tot, t, out = sum(weights), 0.0, []
    for tok, wgt in zip(toks, weights):
        dt = duration * wgt / tot
        out.append({"text": tok, "start": t, "end": t + dt})
        t += dt
    return out


def chunk_words(words: Sequence[dict], max_chars=30, max_words=6, pause=0.45) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur:
            nchars = len(" ".join(x["text"] for x in cur + [w]))
            if (nchars > max_chars or len(cur) >= max_words or w["start"] - cur[-1]["end"] > pause
                    or cur[-1]["text"].endswith((".", "?", "!", ":"))):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def _prepare_subtitles(words, box_w, box_h, max_size=62, min_size=38):
    """Pra-hitung layout tiap chunk supaya per-frame hanya menggambar."""
    prepared = []
    for ch in chunk_words(words):
        texts = [w["text"] for w in ch]
        size = max_size
        while True:
            font = load_font(FONT_HEAVY, size)
            lines = wrap_words(texts, font, box_w)
            lh = int(size * 1.35)
            if (len(lines) * lh <= box_h and len(lines) <= 2) or size <= min_size:
                break
            size -= 2
        pos, k = [], 0
        space = font.getlength(" ")
        for li, ln in enumerate(lines):
            lw = font.getlength(" ".join(ln))
            x = (box_w - lw) / 2
            for _ in ln:
                wl = font.getlength(texts[k])
                pos.append((k, x, li, wl))
                x += wl + space
                k += 1
        prepared.append({"words": ch, "font": font, "lh": lh, "n_lines": len(lines), "pos": pos,
                         "start": ch[0]["start"]})
    return prepared


def _ease_out(p):  # cubic
    return 1 - (1 - min(1.0, max(0.0, p))) ** 3


class _Scene:
    def __init__(self, kind, data):
        self.kind, self.data = kind, data
        self.t0 = self.t1 = 0.0
        self.static: Image.Image | None = None
        self.counter = None      # (value_str, box, fit_cache)
        self.cards: list = []    # (tile, mask, (x,y), delay)


def _build_scenes(content, prog, photo) -> list[_Scene]:
    W, H, M = W_V, H_V, 72
    accent = prog["accent"]
    bg = make_data_grid_background((W, H), accent, "dots", seed=11)
    sub_box = (M, 1250, W - M, 1490)
    scenes: list[_Scene] = []

    def base(date=True):
        img = bg.copy()
        d = ImageDraw.Draw(img)
        draw_brand_mark(img, d, M, 168, accent, 34)
        d.text((W - M, 168), (content.get("date", "") or "").upper(), font=load_font(FONT_LABEL, 26),
               fill=rgb("text_dim"), anchor="rm")
        draw_pill(img, d, M, 252, f"PROGRAM  /  {prog['label']}", accent, size=26, height=60, pad_x=28)
        fill_rr(img, sub_box, 40, fill="surface", alpha=0.96, outline="line", width=1)
        return img, d

    # cover
    img, d = base()
    auto_fit_multiline_text(d, content["hook"], (M, 330, W - M, 790), 92, 50, FONT_HEAVY, "text", 1.2)
    hb = (M, 830, W - M, 1200)
    draw_hero_backdrop(img, hb, accent, photo)
    fill_rr(img, hb, 36, outline="line", width=1)
    draw_tracked(d, (M + 40, hb[1] + 50), "ANGKA KUNCI", load_font(FONT_LABEL, 24), accent, 4)
    auto_fit_multiline_text(d, content["hero"]["label"], (M + 40, hb[1] + 270, W - M - 40, hb[3] - 28), 34,
                            22, FONT_LABEL, "text", 1.3)
    s = _Scene("cover", content)
    s.static = img
    s.counter = (content["hero"]["value"], (M + 40, hb[1] + 80, W - M - 40, hb[1] + 255), "gold", {})
    scenes.append(s)

    # slide scenes
    for sl in content.get("slides", [])[:4]:
        img, d = base()
        auto_fit_multiline_text(d, sl["heading"], (M, 330, W - M, 560), 70, 38, FONT_HEAVY, "text", 1.2)
        s = _Scene("slide", sl)
        top = 590
        m = sl.get("metric")
        if m:
            mb = (M, top, W - M, top + 210)
            fill_rr(img, mb, 30, fill="surface", outline="line", width=1)
            auto_fit_multiline_text(d, m["label"], (M + 40, mb[1] + 150, W - M - 40, mb[3] - 14), 28, 18,
                                    FONT_LABEL, "text_dim", 1.25, align="center")
            s.counter = (m["value"], (M + 30, mb[1] + 12, W - M - 30, mb[1] + 150), "gold", {})
            top = mb[3] + 24
        pts = sl.get("video_points") or [p for c in sl.get("columns", []) for p in c.get("points", [])]
        pts = pts[:3]
        if pts:
            ah, gap = 1210 - top, 18
            ch = int((ah - gap * (len(pts) - 1)) / len(pts))
            ch = min(ch, 190)
            for i, p in enumerate(pts):
                cy0 = top + i * (ch + gap)
                box = (M, cy0, W - M, cy0 + ch)
                tile = img.crop(box)
                td = ImageDraw.Draw(tile)
                fill_rr(tile, (0, 0, W - 2 * M, ch), 26, fill="surface", outline="line", width=1)
                tone_c = _tone_color((sl.get("columns") or [{}])[0].get("tone", ""), accent)
                fill_rr(tile, (0, 22, 8, ch - 22), 4, fill=tone_c)
                auto_fit_multiline_text(td, p, (40, 12, W - 2 * M - 30, ch - 12), 36, 20, FONT_BODY, "text",
                                        1.35, valign="middle")
                s.cards.append((tile, _rr_mask(W - 2 * M, ch, 26), (M, cy0), 0.25 + 0.35 * i))
        s.static = img
        scenes.append(s)

    # verdict
    img, d = base()
    vb = (M, 330, W - M, 930)
    inner = draw_editorial_card(img, d, vb, "Verdict objektif", accent, shadow=False)
    auto_fit_multiline_text(d, content["verdict"], inner, 50, 26, FONT_LABEL, "text", 1.4)
    cb = (M, 960, W - M, 1200)
    fill_rr(img, cb, 30, fill=accent, alpha=0.12, outline=accent, width=2, outline_alpha=0.8)
    auto_fit_multiline_text(d, content["cta"], (cb[0] + 36, cb[1] + 20, cb[2] - 36, cb[3] - 20), 40, 22,
                            FONT_LABEL, "text", 1.35, align="center", valign="middle")
    s = _Scene("verdict", content)
    s.static = img
    scenes.append(s)
    return scenes


def render_vertical_video(content: dict, out_path: str | Path, audio_path: str | Path | None = None,
                          words: Sequence[dict] | None = None, duration: float | None = None, fps: int = 30,
                          crf: int = 20, preset: str = "veryfast", xfade: float = 0.28) -> Path:
    """Render video 1080x1920: counter angka halus, crossfade antar scene, subtitle karaoke.
    words: [{'text','start','end'}] (detik) dari Edge-TTS (lihat words_from_edge_boundaries)."""
    prog = _program(content)
    W, H, M = W_V, H_V, 72
    accent = prog["accent"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if audio_path:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                "default=nw=1:nk=1", str(audio_path)], capture_output=True, text=True, check=True)
        duration = float(probe.stdout.strip())
    if duration is None:
        duration = (words[-1]["end"] + 0.8) if words else 30.0
    if not words:
        words = _estimate_words(content.get("narration", content.get("hook", "")), duration * 0.95)

    scenes = _build_scenes(content, prog, _hero_photo(content))
    weights = [1.0] + [1.2] * (len(scenes) - 2) + [1.2]
    t = 0.0
    for sc, wgt in zip(scenes, weights):
        sc.t0, sc.t1 = t, t + duration * wgt / sum(weights)
        t = sc.t1

    sub_box_w, sub_box_h = W - 2 * M - 80, 240 - 50
    subs = _prepare_subtitles(words, sub_box_w, sub_box_h)
    sub_starts = [s["start"] for s in subs]

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-"]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-r", str(fps)]
    if audio_path:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    n_frames = int(math.ceil(duration * fps))
    cur_i = 0
    sub_y0, sub_h = 1250, 240
    try:
        for f in range(n_frames):
            t = f / fps
            while cur_i < len(scenes) - 1 and t >= scenes[cur_i].t1:
                cur_i += 1
            sc = scenes[cur_i]
            lt = t - sc.t0
            if cur_i > 0 and lt < xfade:
                frame = Image.blend(scenes[cur_i - 1].static, sc.static, _ease_out(lt / xfade))
            else:
                frame = sc.static.copy()
            d = ImageDraw.Draw(frame)

            if sc.counter:  # counter halus
                val, box, col, cache = sc.counter
                pre, num, suf = split_value(val)
                target, dec, th, ds = parse_number(num)
                p = _ease_out((lt - 0.15) / 1.5)
                draw_metric_value(d, val, box, col, 230 if sc.kind == "cover" else 130, 50,
                                  live_number=format_number(target * p, dec, th, ds), fit_cache=cache)
            for tile, mask, (x, y), delay in sc.cards:  # kartu masuk bertahap
                p = _ease_out((lt - delay) / 0.4)
                if p > 0:
                    frame.paste(tile, (x, int(y + (1 - p) * 40)), _scale(mask, p))

            # progress global
            px0, px1, py = M, W - M, 1532
            fill_rr(frame, (px0, py, px1, py + 8), 4, fill="surface_hi")
            if t > 0.05:
                fill_rr(frame, (px0, py, px0 + max(10, (px1 - px0) * t / duration), py + 8), 4, fill=accent)

            # subtitle karaoke
            k = max(0, sum(1 for s0 in sub_starts if s0 <= t + 0.02) - 1)
            if subs and t >= sub_starts[0] - 0.1:
                s = subs[k]
                font, lh = s["font"], s["lh"]
                total_h = s["n_lines"] * lh
                oy = sub_y0 + (sub_h - total_h) / 2
                ox = M + 40
                for (wi, x, li, wl) in s["pos"]:
                    w = s["words"][wi]
                    cy = oy + lh * (li + 0.5)
                    if w["start"] <= t < w["end"]:
                        fill_rr(frame, (ox + x - 12, cy - lh * 0.42, ox + x + wl + 12, cy + lh * 0.42), 16,
                                fill=accent)
                        col = "bg"
                    else:
                        col = "text" if t >= w["end"] else "text_dim"
                    d.text((ox + x, cy), w["text"], font=font, fill=rgb(col), anchor="lm")
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg gagal: {err}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out_path


# --------------------------------------------------------------------------- #
# 8. DEMO / SMOKE TEST
# --------------------------------------------------------------------------- #
DEMO = {
    "ANGKA_BICARA": {
        "program": "ANGKA_BICARA", "date": "18 Okt 2026",
        "hook": "Kenapa 35% investor muda memilih menunda investasi?",
        "hero": {"value": "35%", "label": "investor muda menunda investasi karena merasa dana belum cukup"},
        "slides": [
            {"heading": "Siapa yang menunda, dan apa alasannya?",
             "metric": {"value": "35,5%", "label": "responden usia 18-30 tahun belum mulai berinvestasi"},
             "columns": [{"title": "Alasan utama", "tone": "fact",
                          "points": ["Dana darurat belum terbentuk", "Takut rugi di pasar yang fluktuatif",
                                     "Merasa literasi keuangan belum cukup"]},
                         {"title": "Yang sudah mulai", "tone": "key",
                          "points": ["Mayoritas mulai dari reksa dana", "Nominal rutin di bawah Rp 500.000",
                                     "Lebih memilih aplikasi dengan setoran kecil"]}]},
            {"heading": "Seberapa besar porsinya terhadap gaji?",
             "columns": [{"title": "Rata-rata porsi investasi", "tone": "key",
                          "points": ["Sebagian besar mengalokasikan kurang dari 10% pendapatan bulanan.",
                                     "Biaya hidup perkotaan menyerap porsi terbesar dari gaji bulanan.",
                                     "Cicilan konsumtif menekan kapasitas menabung."]}]},
        ],
        "verdict": "Hambatan terbesar bukan niat, melainkan buffer keuangan. Data menunjukkan dana darurat menjadi "
                   "prasyarat psikologis sebelum anak muda berani masuk pasar.",
        "cta": "Menurut kamu, mana yang lebih dulu: dana darurat atau mulai investasi? Tulis di komentar.",
        "sources": ["Survei Literasi dan Inklusi Keuangan, OJK (contoh)", "Statistik Indonesia, BPS (contoh)"],
        "narration": "Tiga puluh lima persen investor muda memilih menunda investasi. Alasan utamanya adalah dana darurat "
                     "yang belum terbentuk. Data ini menunjukkan hambatan terbesar bukan niat, melainkan buffer keuangan.",
    },
    "INDEKS_KERINGAT": {
        "program": "INDEKS_KERINGAT", "date": "18 Okt 2026",
        "hook": "Berapa hari kerja untuk membeli satu smartphone flagship di Jakarta?",
        "hero": {"value": "5,4 hari", "label": "kerja penuh UMP DKI untuk harga satu smartphone kelas menengah-atas"},
        "slides": [{"heading": "UMP DKI vs harga gadget",
                    "metric": {"value": "Rp 5.396.763", "label": "UMP DKI Jakarta per bulan"},
                    "columns": [{"title": "Harga", "tone": "key", "points": ["Smartphone flagship Rp 15 jt-an",
                                                                                "Laptop kerja Rp 9 jt-an"]},
                                {"title": "Setara jam kerja", "tone": "neutral",
                                 "points": ["Sekitar 2,8 bulan gaji penuh", "Sekitar 1,7 bulan gaji penuh"]}]}],
        "verdict": "Gadget bukan sekadar barang; ia dibayar dengan ratusan jam kerja.",
        "cta": "Berapa jam kerja yang kamu rela tukar untuk satu gadget?",
        "sources": ["UMP DKI Jakarta 2026 (SK Gubernur)", "Harga resmi produsen (contoh)"],
    },
    "RADAR_SENTIMEN": {
        "program": "RADAR_SENTIMEN", "date": "18 Okt 2026",
        "hook": "Isu viral ini memecah publik jadi dua kubu. Apa faktanya?",
        "hero": {"value": "58 : 42", "label": "perbandingan sentimen pro vs kontra dari sampel percakapan (contoh)"},
        "slides": [{"heading": "Fakta vs dua kubu",
                    "columns": [{"title": "Kubu pro", "tone": "pro",
                                 "points": ["Menilai kebijakan mempercepat layanan", "Mengutip uji coba di beberapa kota"]},
                                {"title": "Kubu kontra", "tone": "con",
                                 "points": ["Mempertanyakan transparansi anggaran", "Khawatir dampak ke kelompok rentan"]}]}],
        "verdict": "Perbedaan terbesar ada pada tafsir data, bukan pada datanya sendiri.",
        "cta": "Kamu di kubu mana, dan data apa yang bisa mengubah pandanganmu?",
        "sources": ["Analisis sampel percakapan publik (contoh)"],
    },
}

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    prog = sys.argv[1] if len(sys.argv) > 1 else "ANGKA_BICARA"
    print(render_carousel_slides(DEMO[prog], f"out/{prog.lower()}"))
    if "--video" in sys.argv:
        print(render_vertical_video(DEMO[prog], f"out/{prog.lower()}.mp4", duration=12))
