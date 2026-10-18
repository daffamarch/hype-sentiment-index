"""
metrika_render.py  --  Modul render grafis METRIKA Kelas Agensi (Jurnalisme Data & Riset Finansial).

Desain Grafis Editorial Profesional:
- PALET COKLAT MEWAH (Luxury Espresso, Warm Cognac Leather, & Antique Parchment Cream).
- Terinspirasi dari estetika jurnalisme investigasi klasik & majalah ekonomi premium:
  * Latar Belakang: Warm Ivory Linen (#FBF8F4) & Warm Parchment (#F5EFE6)
  * Tipografi Utama: Deep Roasted Espresso (#1E140E)
  * Aksen Mewah: Rich Cognac Leather (#8C5835) & Warm Bronze (#A67C52)
  * Aksen Provokatif: Crimson Wax Red (#B91C1C) sebagai penanda poin krusial & pin investigasi
  * Kartu & Garis: Warm Toasted Kraft (#E7DBCF)
- SETIAP SLIDE MEMILIKI GAMBAR AKURAT & RELEVAN:
  * Slide 1: Foto hero full-bleed di 60% bagian bawah cover dengan gradasi dark espresso.
  * Slide 2: Banner split visual analitis + kartu metrik spotlight di tengah + 2 kolom argumen padat.
  * Slide 3: Banner visual editorial terintegrasi dengan kutipan verdict redaksi & ruang diskusi.
- Rendered via Playwright (Headless Chromium) 1080x1350 px & Video Vertikal 1080x1920 px via FFmpeg.
"""
from __future__ import annotations

import base64
import html
import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("metrika")

# Dimensi Standar Media Sosial
W_IG, H_IG = 1080, 1350
W_V, H_V = 1080, 1920

# ==============================================================================
# PALET IDENTITAS VISUAL METRIKA: LUXURY ESPRESSO & WARM LEATHER (COKLAT MEWAH)
# ==============================================================================
COLOR_BG = "#FBF8F4"              # Warm Ivory Linen (Kertas majalah mewah, hangat, elegan)
COLOR_CARD = "#FFFFFF"            # Kartu putih bersih kontras tinggi
COLOR_CARD_WARM = "#FAF6F0"       # Kartu krem kertas polaroid hangat
COLOR_TEXT_MAIN = "#1E140E"       # Deep Roasted Espresso (Coklat sangat pekat, klasik & tajam)
COLOR_TEXT_MUTED = "#6B584B"      # Warm Mocha Taupe (Elegan, tidak silau)
COLOR_BROWN_DARK = "#2B1A12"      # Dark Mahogany / Espresso tua berwibawa
COLOR_BROWN_ACCENT = "#8C5835"    # Rich Cognac / Warm Caramel Leather
COLOR_BROWN_LIGHT = "#F3EBE1"     # Warm Latte / Soft Kraft tint
COLOR_RED = "#B91C1C"             # Crimson Wax Red (Aksen provokatif / pin investigasi tajam)
COLOR_BORDER = "#E7DBCF"          # Warm Toasted Kraft Border
COLOR_LINE = "#EFE4D8"            # Soft Cream Separator Line

PROGRAMS_THEME = {
    "INDEKS_KERINGAT": {
        "label": "INDEKS KERINGAT",
        "tag": "KALKULATOR DAYA BELI & JAM KERJA",
        "badge_icon": "⚖️",
    },
    "RADAR_SENTIMEN": {
        "label": "RADAR SENTIMEN",
        "tag": "PETA POLARISASI OPINI PUBLIK",
        "badge_icon": "📡",
    },
    "ANGKA_BICARA": {
        "label": "ANGKA BICARA",
        "tag": "DATA STORYTELLING & FINANSIAL",
        "badge_icon": "📊",
    },
}


def format_hook_html(hook_text: str) -> str:
    """
    Format hook editorial:
    Teks hitam espresso tebal dengan kata kunci penting diberi warna MERAH CRIMSON (#B91C1C).
    Mendukung tag <red>...</red>, **...**, atau auto-highlight cerdas.
    """
    clean_text = html.escape(hook_text.strip())
    clean_text = clean_text.replace("&lt;red&gt;", "<red>").replace("&lt;/red&gt;", "</red>")
    clean_text = clean_text.replace("&lt;highlight&gt;", "<red>").replace("&lt;/highlight&gt;", "</red>")

    if "<red>" in clean_text and "</red>" in clean_text:
        return re.sub(
            r"<red>(.*?)</red>",
            r'<span class="text-red">\1</span>',
            clean_text,
        )

    if "**" in clean_text:
        return re.sub(
            r"\*\*(.*?)\*\*",
            r'<span class="text-red">\1</span>',
            clean_text,
        )

    if "?" in clean_text:
        parts = clean_text.split("?")
        q_words = parts[0].strip().split()
        if len(q_words) > 3:
            first_part = " ".join(q_words[:-3])
            highlighted = " ".join(q_words[-3:]) + "?"
            after_part = ("?" + "?".join(parts[1:])).lstrip("?").strip()
            return f'{first_part} <span class="text-red">{highlighted}</span> {after_part}'.strip()

    words = clean_text.split()
    if len(words) >= 4:
        start = max(1, len(words) // 4)
        end = min(len(words), start + max(2, len(words) // 2))
        w_before = " ".join(words[:start])
        w_mid = " ".join(words[start:end])
        w_after = " ".join(words[end:])
        res = []
        if w_before: res.append(w_before)
        res.append(f'<span class="text-red">{w_mid}</span>')
        if w_after: res.append(w_after)
        return " ".join(res)

    return f'<span class="text-red">{clean_text}</span>'


def format_point_body_html(point_text: str) -> str:
    """Mengonversi markdown bold **teks** menjadi <b>teks</b> untuk point body."""
    escaped = html.escape(point_text.strip())
    return re.sub(r"\*\*(.*?)\*\*", r'<b>\1</b>', escaped)


def get_image_data_uri(img_path: Optional[str | Path]) -> Optional[str]:
    """Membaca file gambar lokal dan mengubahnya menjadi Base64 Data URI."""
    if not img_path:
        return None
    p = Path(img_path)
    if not p.exists() or p.stat().st_size < 1000:
        return None
    try:
        mime = "image/jpeg"
        if p.suffix.lower() == ".png":
            mime = "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception as err:
        log.warning(f"Gagal memproses gambar {img_path}: {err}")
        return None


# ==============================================================================
# 1. GENERATOR CSS & TATA LETAK EDITORIAL (LUXURY BROWN PALETTE)
# ==============================================================================
def get_base_css() -> str:
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Outfit:wght@600;700;800;900&display=swap');

:root {{
  --bg: {COLOR_BG};
  --card: {COLOR_CARD};
  --card-warm: {COLOR_CARD_WARM};
  --text-main: {COLOR_TEXT_MAIN};
  --text-muted: {COLOR_TEXT_MUTED};
  --brown-dark: {COLOR_BROWN_DARK};
  --brown-accent: {COLOR_BROWN_ACCENT};
  --brown-light: {COLOR_BROWN_LIGHT};
  --border: {COLOR_BORDER};
  --line: {COLOR_LINE};
  --red: {COLOR_RED};
}}

* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  -webkit-font-smoothing: antialiased;
}}

body {{
  width: 1080px;
  height: 1350px;
  overflow: hidden;
  background-color: var(--bg);
  font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
  color: var(--text-main);
  position: relative;
  display: flex;
  flex-direction: column;
}}

.text-red {{
  color: var(--red) !important;
  font-weight: 900 !important;
}}

.text-cognac {{
  color: var(--brown-accent) !important;
  font-weight: 800 !important;
}}

/* Top Brand Bar (Mewah & Berwibawa) */
.brand-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 34px 52px 16px 52px;
  background-color: var(--bg);
  z-index: 10;
}}
.brand-left {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
.brand-monogram {{
  width: 44px;
  height: 44px;
  background: var(--brown-dark);
  border: 1.5px solid var(--brown-accent);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FAF6F0;
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  box-shadow: 0 4px 10px rgba(43, 26, 18, 0.15);
}}
.brand-title-wrap {{
  display: flex;
  flex-direction: column;
}}
.brand-title {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.01em;
  color: var(--brown-dark);
  line-height: 1.1;
}}
.brand-tagline {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--brown-accent);
}}

.program-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 18px;
  background-color: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  box-shadow: 0 2px 6px rgba(43, 26, 18, 0.04);
}}

/* Cover Slide 1 (40% Text Atas & 60% Foto Full-Bleed Bawah) */
.cover-top-box {{
  padding: 6px 52px 22px 52px;
  background-color: var(--bg);
  z-index: 10;
}}
.cover-headline {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 48px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -0.02em;
  color: var(--brown-dark);
  margin-bottom: 16px;
}}
.stat-pill-row {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.stat-pill {{
  display: inline-flex;
  align-items: center;
  gap: 12px;
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-left: 5px solid var(--brown-accent);
  border-radius: 999px;
  padding: 8px 24px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.05);
}}
.stat-num {{
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  color: var(--brown-accent);
}}
.stat-lbl {{
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}}

.cover-photo-wrapper {{
  flex: 1;
  width: 100%;
  position: relative;
  overflow: hidden;
  background-color: var(--brown-dark);
  border-top: 2px solid var(--border);
}}
.cover-photo {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 25%;
  display: block;
}}
.photo-gradient-overlay {{
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(to top, rgba(27, 17, 12, 0.94) 0%, rgba(35, 22, 15, 0.50) 60%, transparent 100%);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 30px 52px;
}}
.photo-swipe-prompt {{
  color: #FAF6F0;
  font-size: 18px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 12px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6);
}}
.photo-swipe-arrow {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--brown-accent);
  color: #FFFFFF;
  font-weight: 900;
}}

/* Inside Content Slides (Padat & Kaya Argumen Berwarna Coklat Mewah) */
.inside-content-body {{
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 6px 52px 30px 52px;
}}
.slide-header-box {{
  margin-bottom: 16px;
}}
.slide-eyebrow-pill {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--brown-accent);
  margin-bottom: 6px;
}}
.slide-heading-text {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 38px;
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.015em;
  color: var(--brown-dark);
}}

/* Slide 2: Banner Split Visual (Image + Metric Spotlight) */
.slide2-visual-metric-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 20px;
  overflow: hidden;
  display: flex;
  height: 200px;
  margin-bottom: 18px;
  box-shadow: 0 6px 20px rgba(43, 26, 18, 0.05);
}}
.slide2-img-container {{
  width: 340px;
  height: 100%;
  position: relative;
  background-color: var(--brown-dark);
  border-right: 1.5px solid var(--border);
  flex-shrink: 0;
}}
.slide2-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide2-metric-content {{
  flex: 1;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #FFFFFF;
  border-left: 5px solid var(--brown-accent);
}}
.slide2-metric-val {{
  font-family: 'Outfit', sans-serif;
  font-size: 44px;
  font-weight: 900;
  color: var(--brown-accent);
  line-height: 1.1;
  margin-bottom: 6px;
}}
.slide2-metric-lbl {{
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

/* Fallback Metric Spotlight Bar */
.metric-spotlight-bar {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-left: 6px solid var(--brown-accent);
  border-radius: 18px;
  padding: 18px 26px;
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 18px;
  box-shadow: 0 4px 14px rgba(43, 26, 18, 0.04);
}}
.spotlight-value {{
  font-family: 'Outfit', sans-serif;
  font-size: 44px;
  font-weight: 900;
  color: var(--brown-accent);
  white-space: nowrap;
}}
.spotlight-divider {{
  width: 1.5px;
  height: 48px;
  background: var(--line);
}}
.spotlight-explanation {{
  font-size: 17px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

/* Dual Column Cards (Padat Argumen dengan Nuansa Kertas Mewah) */
.columns-container {{
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
  margin-bottom: 18px;
}}
.editorial-column-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 24px 22px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
}}
.column-card-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}}
.col-header-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--brown-light);
  border: 1px solid var(--border);
  color: var(--brown-dark);
}}
.col-header-pill.highlight {{
  background: #FAF0E6;
  border: 1px solid rgba(140, 88, 53, 0.35);
  color: var(--brown-accent);
}}

.points-list-wrap {{
  display: flex;
  flex-direction: column;
  gap: 14px;
}}
.point-item-row {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
}}
.point-bullet-box {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brown-accent);
  margin-top: 8px;
  flex-shrink: 0;
}}
.point-body-text {{
  font-size: 16px;
  font-weight: 500;
  line-height: 1.48;
  color: var(--text-main);
}}
.point-body-text b {{
  font-weight: 800;
  color: var(--brown-dark);
}}

.column-card-footer {{
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

/* Slide 3: Verdict Visual Banner (Image + Dark Espresso Gradient Overlay) */
.slide3-verdict-visual-banner {{
  width: 100%;
  height: 310px;
  border-radius: 20px;
  overflow: hidden;
  position: relative;
  background-color: var(--brown-dark);
  border: 1.5px solid var(--border);
  margin-bottom: 18px;
  box-shadow: 0 8px 24px rgba(43, 26, 18, 0.08);
}}
.slide3-verdict-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide3-verdict-overlay {{
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to top, rgba(32, 20, 14, 0.95) 0%, rgba(43, 26, 18, 0.72) 55%, rgba(43, 26, 18, 0.40) 100%);
  padding: 34px 38px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}}
.slide3-verdict-tag {{
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #E2B792;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}}
.slide3-verdict-quote {{
  font-size: 23px;
  font-weight: 700;
  line-height: 1.45;
  color: #FAF6F0;
}}

.cta-discussion-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 22px 28px;
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
}}
.cta-badge-icon {{
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--brown-accent);
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.cta-query-text {{
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--brown-dark);
}}

.verified-sources-card {{
  background: var(--brown-light);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 20px;
  margin-bottom: 18px;
}}
.sources-title-row {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
}}
.sources-chip-grid {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.source-pill {{
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--brown-dark);
}}

/* Progress Segments & Global Footer */
.carousel-progress-bar {{
  display: flex;
  gap: 8px;
  margin-top: auto;
  margin-bottom: 12px;
}}
.progress-segment-item {{
  flex: 1;
  height: 5px;
  border-radius: 3px;
  background-color: var(--border);
}}
.progress-segment-item.active {{
  background-color: var(--brown-accent);
}}

.editorial-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
}}
"""


def render_html_cover(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    """Merender Slide 1 Cover: Headline Hitam-Coklat di atas & Foto Full-Bleed di bawah."""
    hook_raw = content.get("hook", "")
    hook_formatted = format_hook_html(hook_raw)

    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", "")))
    hero_lbl = html.escape(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "18 OKT 2026"))).upper()

    img_uri = get_image_data_uri(content.get("hero_image"))

    stat_html = ""
    if hero_val:
        stat_html = f"""
        <div class="stat-pill-row">
          <div class="stat-pill">
            <span class="stat-num">{hero_val}</span>
            <span class="stat-lbl">{hero_lbl}</span>
          </div>
        </div>
        """

    if img_uri:
        photo_dom = f'<img src="{img_uri}" class="cover-photo" alt="Cover Visual" />'
    else:
        photo_dom = f"""
        <div style="width:100%; height:100%; background: linear-gradient(135deg, #2B1A12 0%, #3D2619 100%); display:flex; align-items:center; justify-content:center; flex-direction:column; padding:40px;">
          <div style="font-family:'Outfit', sans-serif; font-size:44px; font-weight:900; color:#FAF6F0; margin-bottom:12px;">{theme['label']}</div>
          <div style="font-size:20px; font-weight:700; color:#D4C4B5; text-align:center;">{hero_lbl}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css()}
</style>
</head>
<body>
  <div class="brand-header">
    <div class="brand-left">
      <div class="brand-monogram">M</div>
      <div class="brand-title-wrap">
        <div class="brand-title">METRIKA</div>
        <div class="brand-tagline">JURNALISME DATA & RISET FINANSIAL</div>
      </div>
    </div>
    <div class="program-chip">{date_str} • {theme['label']}</div>
  </div>

  <div class="cover-top-box">
    <h1 class="cover-headline">{hook_formatted}</h1>
    {stat_html}
  </div>

  <div class="cover-photo-wrapper">
    {photo_dom}
    <div class="photo-gradient-overlay">
      <div class="photo-swipe-prompt">
        <span class="photo-swipe-arrow">→</span>
        Geser untuk bedah data & argumen lengkap
      </div>
      <div style="color:rgba(250,246,240,0.7); font-size:13px; font-weight:700;">@metrika.id</div>
    </div>
  </div>
</body>
</html>
"""


def render_html_slide(
    content: Dict[str, Any],
    theme: Dict[str, Any],
    slide_data: Dict[str, Any],
    slide_idx: int,
    total_slides: int,
) -> str:
    """Merender Slide 2..N: Dilengkapi Banner Gambar Akurat + Metric Spotlight di tengah & Kolom Argumen."""
    heading = html.escape(slide_data.get("heading", ""))
    metric = slide_data.get("metric")

    slide_img_path = slide_data.get("image") or content.get("slide2_image") or content.get("hero_image")
    img_uri = get_image_data_uri(slide_img_path)

    m_val = html.escape(str(metric.get("value", ""))) if metric else ""
    m_lbl = html.escape(str(metric.get("label", ""))) if metric else ""

    if img_uri:
        visual_metric_banner = f"""
        <div class="slide2-visual-metric-card">
          <div class="slide2-img-container">
            <img src="{img_uri}" class="slide2-img" alt="Visual Analisis" />
          </div>
          <div class="slide2-metric-content">
            <div class="slide2-metric-val">{m_val}</div>
            <div class="slide2-metric-lbl">{m_lbl}</div>
          </div>
        </div>
        """
    else:
        visual_metric_banner = f"""
        <div class="metric-spotlight-bar">
          <div class="spotlight-value">{m_val}</div>
          <div class="spotlight-divider"></div>
          <div class="spotlight-explanation">{m_lbl}</div>
        </div>
        """

    columns = slide_data.get("columns", [])[:2]
    is_single = len(columns) == 1

    cards_html = []
    for i, col in enumerate(columns):
        col_title = html.escape(col.get("title", f"Argumen & Analisis {i+1}"))
        is_highlight = (i == 0)
        pill_cls = "col-header-pill highlight" if is_highlight else "col-header-pill"

        points = col.get("points", [])
        points_html = []
        for pt in points:
            formatted_pt = format_point_body_html(pt)
            points_html.append(f"""
            <div class="point-item-row">
              <div class="point-bullet-box"></div>
              <div class="point-body-text">{formatted_pt}</div>
            </div>
            """)

        footer_label = "FAKTA TERVERIFIKASI" if is_highlight else "IMPLIKASI STRATEGIS"

        cards_html.append(f"""
        <div class="editorial-column-card">
          <div>
            <div class="column-card-header">
              <div class="{pill_cls}">{col_title}</div>
            </div>
            <div class="points-list-wrap">
              {"".join(points_html)}
            </div>
          </div>
          <div class="column-card-footer">
            <span>METRIKA DATA AUDIT</span>
            <span>{footer_label}</span>
          </div>
        </div>
        """)

    grid_cls = "columns-container single-column" if is_single else "columns-container"

    prog_bars = "".join(
        f'<div class="progress-segment-item {"active" if idx < slide_idx else ""}"></div>'
        for idx in range(total_slides)
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css()}
</style>
</head>
<body>
  <div class="brand-header">
    <div class="brand-left">
      <div class="brand-monogram">M</div>
      <div class="brand-title-wrap">
        <div class="brand-title">METRIKA</div>
        <div class="brand-tagline">JURNALISME DATA & RISET FINANSIAL</div>
      </div>
    </div>
    <div class="program-chip">{slide_idx:02d} / {total_slides:02d}</div>
  </div>

  <div class="inside-content-body">
    <div class="slide-header-box">
      <div class="slide-eyebrow-pill">{theme['label']} • ANALISIS DATA</div>
      <h2 class="slide-heading-text">{heading}</h2>
    </div>

    {visual_metric_banner}

    <div class="{grid_cls}">
      {"".join(cards_html)}
    </div>

    <div class="carousel-progress-bar">
      {prog_bars}
    </div>

    <div class="editorial-footer">
      <div>@metrika.id</div>
      <div>Data Bicara. Kamu yang Menilai.</div>
    </div>
  </div>
</body>
</html>
"""


def render_html_verdict(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    """Merender Slide Terakhir: Dilengkapi Banner Visual Akurat + Kutipan Verdict Redaksi."""
    verdict_text = html.escape(content.get("verdict", ""))
    cta_text = html.escape(content.get("cta", ""))
    sources = content.get("sources", [])

    verdict_img_path = content.get("verdict_image") or content.get("slide3_image") or content.get("hero_image")
    img_uri = get_image_data_uri(verdict_img_path)

    sources_html = []
    for s in sources:
        clean_s = html.escape(s)
        sources_html.append(f'<div class="source-pill">{clean_s}</div>')

    if img_uri:
        verdict_visual_block = f"""
        <div class="slide3-verdict-visual-banner">
          <img src="{img_uri}" class="slide3-verdict-img" alt="Verdict Visual" />
          <div class="slide3-verdict-overlay">
            <div class="slide3-verdict-tag">
              <span>⚖️</span>
              <span>VERDICT OBJEKTIF REDAKSI</span>
            </div>
            <div class="slide3-verdict-quote">{verdict_text}</div>
          </div>
        </div>
        """
    else:
        verdict_visual_block = f"""
        <div style="background:#FFFFFF; border:1.5px solid var(--border); border-left:6px solid var(--brown-accent); border-radius:20px; padding:28px 32px; margin-bottom:18px; box-shadow:0 6px 18px rgba(43,26,18,0.05);">
          <div style="font-size:13px; font-weight:900; letter-spacing:0.12em; text-transform:uppercase; color:var(--brown-accent); margin-bottom:10px; display:flex; align-items:center; gap:8px;">
            <span>⚖️</span>
            <span>VERDICT OBJEKTIF REDAKSI</span>
          </div>
          <div style="font-size:22px; font-weight:700; line-height:1.45; color:var(--brown-dark);">{verdict_text}</div>
        </div>
        """

    prog_bars = "".join(
        '<div class="progress-segment-item active"></div>'
        for _ in range(total_slides)
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css()}
</style>
</head>
<body>
  <div class="brand-header">
    <div class="brand-left">
      <div class="brand-monogram">M</div>
      <div class="brand-title-wrap">
        <div class="brand-title">METRIKA</div>
        <div class="brand-tagline">JURNALISME DATA & RISET FINANSIAL</div>
      </div>
    </div>
    <div class="program-chip">{total_slides:02d} / {total_slides:02d}</div>
  </div>

  <div class="inside-content-body">
    <div class="slide-header-box">
      <div class="slide-eyebrow-pill">KESIMPULAN AKHIR</div>
      <h2 class="slide-heading-text">Verdict Riset & Ruang Diskusi</h2>
    </div>

    {verdict_visual_block}

    <div class="cta-discussion-card">
      <div class="cta-badge-icon">?</div>
      <div class="cta-query-text">{cta_text}</div>
    </div>

    <div class="verified-sources-card">
      <div class="sources-title-row">SUMBER DATA TERVERIFIKASI</div>
      <div class="sources-chip-grid">
        {"".join(sources_html)}
      </div>
    </div>

    <div class="carousel-progress-bar">
      {prog_bars}
    </div>

    <div class="editorial-footer">
      <div>@metrika.id</div>
      <div>Data Bicara. Kamu yang Menilai.</div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# 2. RENDERER ENGINE: PLAYWRIGHT (HEADLESS CHROMIUM)
# ==============================================================================
def render_carousel_slides(
    content: Dict[str, Any], out_dir: str | Path, fmt: str = "PNG"
) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    theme = PROGRAMS_THEME.get(prog_id, PROGRAMS_THEME["ANGKA_BICARA"])

    slides_data = content.get("slides", [])[:4]
    total_slides = 2 + len(slides_data)

    html_pages: List[Tuple[str, str]] = []

    # Slide 1: Cover
    html_pages.append(("slide_01", render_html_cover(content, theme, total_slides)))

    # Slides 2..N: Data Breakdown
    for i, s_data in enumerate(slides_data, start=2):
        html_pages.append((f"slide_{i:02d}", render_html_slide(content, theme, s_data, i, total_slides)))

    # Slide Final: Verdict & CTA
    html_pages.append((f"slide_{total_slides:02d}", render_html_verdict(content, theme, total_slides)))

    for name, page_html in html_pages:
        html_file = out_dir / f"{name}.html"
        html_file.write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []

    try:
        from playwright.sync_api import sync_playwright

        print("[Playwright] Memulai Chromium headless untuk render carousel (Luxury Brown Theme)...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
            context = browser.new_context(
                viewport={"width": W_IG, "height": H_IG},
                device_scale_factor=1,
            )
            page = context.new_page()

            for name, page_html in html_pages:
                out_img = out_dir / f"{name}.png"
                page.set_content(page_html, wait_until="networkidle")
                try:
                    page.evaluate("document.fonts.ready")
                except Exception:
                    pass
                page.screenshot(path=str(out_img), type="png")
                out_paths.append(out_img)
                print(f"[Playwright] Berhasil merender: {out_img.name}")

            browser.close()

    except ImportError:
        log.warning("Playwright belum terpasang. Menjalankan fallback visual.")
        for name, _ in html_pages:
            fallback_img = out_dir / f"{name}.png"
            im = Image.new("RGB", (W_IG, H_IG), (251, 248, 244))
            d = ImageDraw.Draw(im)
            d.text((80, 80), f"METRIKA • {theme['label']}\n(Silakan install Playwright)", fill=(43, 26, 18))
            im.save(fallback_img)
            out_paths.append(fallback_img)

    return out_paths


# ==============================================================================
# 3. GENERATOR VIDEO VERTIKAL (1080x1920) DENGAN SUBTITLE KARAOKE
# ==============================================================================
def words_from_edge_boundaries(boundaries: Sequence[dict]) -> List[dict]:
    return [
        {
            "text": b["text"],
            "start": b["offset"] / 1e7,
            "end": (b["offset"] + b["duration"]) / 1e7,
        }
        for b in boundaries
    ]


def render_vertical_video(
    content: Dict[str, Any],
    out_path: str | Path,
    audio_path: Optional[str | Path] = None,
    words: Optional[Sequence[dict]] = None,
    duration: Optional[float] = None,
    fps: int = 30,
    crf: int = 20,
    preset: str = "veryfast",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    theme = PROGRAMS_THEME.get(prog_id, PROGRAMS_THEME["ANGKA_BICARA"])

    if audio_path and Path(audio_path).exists():
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            duration = float(probe.stdout.strip())
        except Exception:
            pass

    if duration is None:
        duration = (words[-1]["end"] + 1.0) if words else 25.0

    carousel_dir = out_path.parent / "carousel"
    slide_files = sorted(list(carousel_dir.glob("slide_*.png")))

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W_V}x{H_V}",
        "-r",
        str(fps),
        "-i",
        "-",
    ]
    if audio_path and Path(audio_path).exists():
        cmd += ["-i", str(audio_path)]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-r",
        str(fps),
    ]
    if audio_path and Path(audio_path).exists():
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out_path)]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    slides_img = []
    if slide_files:
        for sf in slide_files:
            try:
                sim = Image.open(sf).convert("RGB")
                sim_fitted = sim.resize((W_V - 80, int((W_V - 80) * (H_IG / W_IG))), Image.LANCZOS)
                slides_img.append(sim_fitted)
            except Exception:
                continue

    if not slides_img:
        slides_img = [Image.new("RGB", (W_V - 80, 1250), (251, 248, 244))]

    n_slides = len(slides_img)
    slide_duration = duration / n_slides
    n_frames = int(math.ceil(duration * fps))

    try:
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        sub_font = ImageFont.load_default()

    try:
        for f in range(n_frames):
            t = f / fps

            slide_idx = min(int(t // slide_duration), n_slides - 1)
            active_slide = slides_img[slide_idx]

            # Warm Linen Video Background (251, 248, 244)
            frame = Image.new("RGB", (W_V, H_V), (251, 248, 244))
            frame.paste(active_slide, (40, 160))

            draw = ImageDraw.Draw(frame)

            # Subtitle Box dengan outline warm cognac / red
            sub_box = (60, 1530, W_V - 60, 1770)
            draw.rounded_rectangle(sub_box, radius=20, fill=(255, 255, 255), outline=(140, 88, 53), width=3)

            active_word_text = ""
            if words:
                for w in words:
                    if w["start"] <= t <= w["end"] + 0.15:
                        active_word_text = w["text"]
                        break

            if active_word_text:
                draw.text(
                    (W_V // 2, 1650),
                    active_word_text,
                    font=sub_font,
                    fill=(185, 28, 28),
                    anchor="mm",
                )
            else:
                draw.text(
                    (W_V // 2, 1650),
                    f"{theme['label']} • @metrika.id",
                    font=sub_font,
                    fill=(107, 88, 75),
                    anchor="mm",
                )

            # Progress Bar bernuansa warm caramel leather
            p_width = max(10, int((W_V - 120) * (t / duration)))
            draw.rounded_rectangle((60, 1820, W_V - 60, 1828), radius=4, fill=(231, 219, 207))
            draw.rounded_rectangle((60, 1820, 60 + p_width, 1828), radius=4, fill=(140, 88, 53))

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg gagal: {err}")
    finally:
        if proc.poll() is None:
            proc.kill()

    return out_path
