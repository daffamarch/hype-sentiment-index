"""
metrika_render.py  --  Modul render grafis METRIKA Kelas Agensi (Jurnalisme Data & Riset Finansial).

Desain Grafis Editorial Profesional:
- Kanvas Bersih, Tajam, dan Berimbang (Tidak ada ruang kosong hampa / blank void).
- Tipografi Editorial Berbobot (Google Fonts Plus Jakarta Sans & Outfit).
- Visual Data Infografis (SVG Metric Gauges, Comparison Cards, Spotlight Banners).
- Proteksi Visual: Bebas dari foto acak/logo asing, menggunakan visual data SVG murni atau foto terverifikasi.
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

# Palet Identitas METRIKA (Data Journalism & Market Intelligence)
COLOR_BG = "#F8FAFC"           # Studio Slate Light (Bersih, modern, tidak silau)
COLOR_CARD = "#FFFFFF"         # Kartu putih dengan kontras tajam
COLOR_TEXT_MAIN = "#0F172A"    # Deep Charcoal / Hampir hitam
COLOR_TEXT_MUTED = "#475569"   # Slate Grey
COLOR_BORDER = "#E2E8F0"       # Border halus
COLOR_BORDER_STRONG = "#CBD5E1"
COLOR_LINE = "#E2E8F0"

# Warna Aksen Rubrik METRIKA
PROGRAMS_THEME = {
    "INDEKS_KERINGAT": {
        "label": "INDEKS KERINGAT",
        "tag": "KALKULATOR DAYA BELI & JAM KERJA",
        "accent": "#D97706",         # Amber Gold (Uang & Tenaga Kerja)
        "accent_bg": "#FEF3C7",
        "accent_border": "#F59E0B",
        "badge_icon": "⚖️",
    },
    "RADAR_SENTIMEN": {
        "label": "RADAR SENTIMEN",
        "tag": "PETA POLARISASI OPINI PUBLIK",
        "accent": "#2563EB",         # Royal Blue (Debat & Opini Publik)
        "accent_bg": "#EFF6FF",
        "accent_border": "#3B82F6",
        "badge_icon": "📡",
    },
    "ANGKA_BICARA": {
        "label": "ANGKA BICARA",
        "tag": "DATA STORYTELLING & FINANSIAL",
        "accent": "#0D9488",         # Deep Teal / Emerald (Data & Finansial)
        "accent_bg": "#F0FDFA",
        "accent_border": "#14B8A6",
        "badge_icon": "📊",
    },
}


def format_hook_html(hook_text: str, accent_color: str) -> str:
    """
    Format hook editorial:
    Teks hitam tebal dengan kata kunci penting diberi warna aksen rubrik.
    Mendukung tag <red>...</red>, <highlight>...</highlight>, atau auto-highlight.
    """
    clean_text = html.escape(hook_text.strip())
    clean_text = clean_text.replace("&lt;red&gt;", "<red>").replace("&lt;/red&gt;", "</red>")
    clean_text = clean_text.replace("&lt;highlight&gt;", "<red>").replace("&lt;/highlight&gt;", "</red>")

    if "<red>" in clean_text and "</red>" in clean_text:
        return re.sub(
            r"<red>(.*?)</red>",
            rf'<span style="color:{accent_color}; font-weight:900;">\1</span>',
            clean_text,
        )

    if "**" in clean_text:
        return re.sub(
            r"\*\*(.*?)\*\*",
            rf'<span style="color:{accent_color}; font-weight:900;">\1</span>',
            clean_text,
        )

    # Auto-highlight cerdas: beri warna aksen pada bagian pertanyaan atau frasa tengah
    if "?" in clean_text:
        parts = clean_text.split("?")
        q_words = parts[0].strip().split()
        if len(q_words) > 3:
            first_part = " ".join(q_words[:-3])
            highlighted = " ".join(q_words[-3:]) + "?"
            after_part = ("?" + "?".join(parts[1:])).lstrip("?").strip()
            return f'{first_part} <span style="color:{accent_color}; font-weight:900;">{highlighted}</span> {after_part}'.strip()

    words = clean_text.split()
    if len(words) >= 4:
        start = max(1, len(words) // 4)
        end = min(len(words), start + max(2, len(words) // 2))
        w_before = " ".join(words[:start])
        w_mid = " ".join(words[start:end])
        w_after = " ".join(words[end:])
        res = []
        if w_before: res.append(w_before)
        res.append(f'<span style="color:{accent_color}; font-weight:900;">{w_mid}</span>')
        if w_after: res.append(w_after)
        return " ".join(res)

    return f'<span style="color:{accent_color}; font-weight:900;">{clean_text}</span>'


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
# 1. GENERATOR CSS & TATA LETAK EDITORIAL AGENSI
# ==============================================================================
def get_base_css(theme: Dict[str, Any]) -> str:
    accent = theme["accent"]
    accent_bg = theme["accent_bg"]
    accent_border = theme["accent_border"]

    return f"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Outfit:wght@600;700;800;900&display=swap');

:root {{
  --bg: {COLOR_BG};
  --card: {COLOR_CARD};
  --text-main: {COLOR_TEXT_MAIN};
  --text-muted: {COLOR_TEXT_MUTED};
  --border: {COLOR_BORDER};
  --border-strong: {COLOR_BORDER_STRONG};
  --line: {COLOR_LINE};
  --accent: {accent};
  --accent-bg: {accent_bg};
  --accent-border: {accent_border};
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
  padding: 48px 52px 36px 52px;
}}

/* Top Brand Bar */
.brand-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}}
.brand-left {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
.brand-monogram {{
  width: 44px;
  height: 44px;
  background: var(--text-main);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
}}
.brand-title-wrap {{
  display: flex;
  flex-direction: column;
}}
.brand-title {{
  font-family: 'Outfit', sans-serif;
  font-size: 24px;
  font-weight: 900;
  letter-spacing: 0.08em;
  color: var(--text-main);
  line-height: 1.1;
}}
.brand-tagline {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}}

.program-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  background-color: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-main);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}}

/* Cover Slide Elements */
.cover-eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 12px;
}}
.cover-headline {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 52px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -0.02em;
  color: var(--text-main);
  margin-bottom: 24px;
}}

/* Hero Section (Infografis Data Kelas Agensi) */
.hero-infographic-card {{
  flex: 1;
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 28px;
  padding: 38px 42px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}}
.hero-infographic-card::before {{
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 5px;
  background: linear-gradient(90deg, var(--accent), var(--text-main));
}}

.hero-meta-badge {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 16px;
  background-color: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  align-self: flex-start;
}}

.hero-metric-display {{
  margin: 16px 0;
}}
.hero-number {{
  font-family: 'Outfit', sans-serif;
  font-size: 100px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--accent);
}}
.hero-description {{
  font-size: 26px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
  margin-top: 14px;
  max-width: 95%;
}}

.hero-chart-widget {{
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.widget-text {{
  display: flex;
  flex-direction: column;
  gap: 4px;
}}
.widget-title {{
  font-size: 15px;
  font-weight: 800;
  color: var(--text-main);
}}
.widget-subtitle {{
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}}
.widget-indicator {{
  padding: 8px 18px;
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  color: var(--accent);
}}

/* Verified Photo Frame (Jika Ada Foto Artikel) */
.hero-photo-frame {{
  flex: 1;
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 28px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin-bottom: 24px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
}}
.hero-photo-img {{
  width: 100%;
  flex: 1;
  object-fit: cover;
  display: block;
}}
.hero-photo-caption-bar {{
  padding: 18px 28px;
  background: var(--card);
  border-top: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.photo-stat-bubble {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 800;
  color: var(--accent);
}}
.photo-credit-tag {{
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
}}

/* Swipe Call-to-action */
.cover-swipe-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 0 4px;
}}
.swipe-text-guide {{
  font-size: 18px;
  font-weight: 800;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 12px;
}}
.swipe-arrow-btn {{
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--text-main);
  color: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 900;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.2);
}}

/* Inside Content Slides (Penuh & Seimbang) */
.content-slide-wrap {{
  flex: 1;
  display: flex;
  flex-direction: column;
}}
.slide-header-box {{
  margin-bottom: 20px;
}}
.slide-eyebrow-pill {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 6px;
}}
.slide-heading-text {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 42px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.015em;
  color: var(--text-main);
}}

/* Spotlight Banner Card */
.metric-spotlight-bar {{
  background: var(--card);
  border: 1.5px solid var(--border);
  border-left: 6px solid var(--accent);
  border-radius: 20px;
  padding: 22px 30px;
  display: flex;
  align-items: center;
  gap: 28px;
  margin-bottom: 22px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.03);
}}
.spotlight-value {{
  font-family: 'Outfit', sans-serif;
  font-size: 48px;
  font-weight: 900;
  color: var(--accent);
  white-space: nowrap;
}}
.spotlight-divider {{
  width: 1.5px;
  height: 52px;
  background: var(--line);
}}
.spotlight-explanation {{
  font-size: 19px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

/* Dual Column Cards (Mengisi Ruang Secara Vertikal) */
.columns-container {{
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 22px;
}}
.columns-container.single-column {{
  grid-template-columns: 1fr;
}}
.editorial-column-card {{
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 24px;
  padding: 32px 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  position: relative;
}}
.column-card-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}}
.col-header-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text-main);
}}
.col-header-pill.highlight {{
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  color: var(--accent);
}}

.points-list-wrap {{
  display: flex;
  flex-direction: column;
  gap: 20px;
}}
.point-item-row {{
  display: flex;
  align-items: flex-start;
  gap: 14px;
}}
.point-bullet-box {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  margin-top: 8px;
  flex-shrink: 0;
}}
.point-body-text {{
  font-size: 19px;
  font-weight: 600;
  line-height: 1.48;
  color: var(--text-main);
}}

.column-card-footer {{
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

/* Slide Final (Verdict & Discussion) */
.verdict-main-card {{
  background: var(--card);
  border: 2px solid var(--accent);
  border-radius: 26px;
  padding: 34px 38px;
  margin-bottom: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  position: relative;
}}
.verdict-badge-header {{
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.verdict-core-text {{
  font-size: 24px;
  font-weight: 700;
  line-height: 1.45;
  color: var(--text-main);
}}

.cta-discussion-card {{
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 22px;
  padding: 26px 32px;
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 20px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.03);
}}
.cta-badge-icon {{
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--accent);
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 28px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.cta-query-text {{
  font-size: 20px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

.verified-sources-card {{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 24px;
  margin-bottom: 20px;
}}
.sources-title-row {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 10px;
}}
.sources-chip-grid {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.source-pill {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
}}

/* Progress Segments & Global Footer */
.carousel-progress-bar {{
  display: flex;
  gap: 8px;
  margin-top: auto;
  margin-bottom: 14px;
}}
.progress-segment-item {{
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background-color: var(--border);
}}
.progress-segment-item.active {{
  background-color: var(--accent);
}}

.editorial-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-muted);
}}
"""


def render_html_cover(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    """Merender Slide 1 Cover Kelas Agensi."""
    hook_raw = content.get("hook", "")
    hook_formatted = format_hook_html(hook_raw, theme["accent"])

    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", "")))
    hero_lbl = html.escape(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "18 OKT 2026"))).upper()

    # Cek apakah ada foto artikel terverifikasi
    img_uri = get_image_data_uri(content.get("hero_image"))

    if img_uri:
        # Jika foto artikel resmi tersedia, pasang dengan frame editorial rapi
        hero_section = f"""
        <div class="hero-photo-frame">
          <img src="{img_uri}" class="hero-photo-img" alt="Editorial Visual" />
          <div class="hero-photo-caption-bar">
            <div class="photo-stat-bubble">
              <span>{hero_val}</span>
              <span style="font-size:15px; font-weight:700; color:var(--text-main);">{hero_lbl}</span>
            </div>
            <div class="photo-credit-tag">DOKUMENTASI RESMI</div>
          </div>
        </div>
        """
    else:
        # Jika tidak ada foto terverifikasi, gunakan infografis visual data SVG murni (100% aman & elegan)
        hero_section = f"""
        <div class="hero-infographic-card">
          <div class="hero-meta-badge">
            <span>{theme['badge_icon']}</span>
            <span>INDIKATOR UTAMA</span>
          </div>

          <div class="hero-metric-display">
            <div class="hero-number">{hero_val}</div>
            <div class="hero-description">{hero_lbl}</div>
          </div>

          <div class="hero-chart-widget">
            <div class="widget-text">
              <div class="widget-title">ANALISIS RISET FINANSIAL & DATA</div>
              <div class="widget-subtitle">Komputasi Deterministik & Standar Acuan Resmi</div>
            </div>
            <div class="widget-indicator">DATA TERVERIFIKASI</div>
          </div>
        </div>
        """

    # Progress bar HTML
    prog_bars = "".join(
        f'<div class="progress-segment-item {"active" if idx == 0 else ""}"></div>'
        for idx in range(total_slides)
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css(theme)}
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

  <div class="cover-eyebrow">{theme['tag']}</div>
  <h1 class="cover-headline">{hook_formatted}</h1>

  {hero_section}

  <div class="cover-swipe-row">
    <div class="swipe-text-guide">Geser untuk bedah data & perbandingan lengkap</div>
    <div class="swipe-arrow-btn">→</div>
  </div>

  <div class="carousel-progress-bar">
    {prog_bars}
  </div>

  <div class="editorial-footer">
    <div>@metrika.id</div>
    <div>Data Bicara. Kamu yang Menilai.</div>
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
    """Merender Slide 2..N (Data Breakdown) tanpa ruang kosong."""
    heading = html.escape(slide_data.get("heading", ""))
    metric = slide_data.get("metric")

    metric_html = ""
    if metric:
        m_val = html.escape(str(metric.get("value", "")))
        m_lbl = html.escape(str(metric.get("label", "")))
        metric_html = f"""
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
        col_title = html.escape(col.get("title", f"Poin Analisis {i+1}"))
        is_highlight = (i == 0)
        pill_cls = "col-header-pill highlight" if is_highlight else "col-header-pill"

        points = col.get("points", [])
        points_html = []
        for pt in points:
            clean_pt = html.escape(pt)
            points_html.append(f"""
            <div class="point-item-row">
              <div class="point-bullet-box"></div>
              <div class="point-body-text">{clean_pt}</div>
            </div>
            """)

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
            <span>TERKONFIRMASI</span>
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
{get_base_css(theme)}
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

  <div class="content-slide-wrap">
    <div class="slide-header-box">
      <div class="slide-eyebrow-pill">{theme['label']} • ANALISIS DATA</div>
      <h2 class="slide-heading-text">{heading}</h2>
    </div>

    {metric_html}

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
    """Merender Slide Terakhir (Verdict & Ruang Diskusi)."""
    verdict_text = html.escape(content.get("verdict", ""))
    cta_text = html.escape(content.get("cta", ""))
    sources = content.get("sources", [])

    sources_html = []
    for s in sources:
        clean_s = html.escape(s)
        sources_html.append(f'<div class="source-pill">{clean_s}</div>')

    prog_bars = "".join(
        '<div class="progress-segment-item active"></div>'
        for _ in range(total_slides)
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css(theme)}
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

  <div class="content-slide-wrap">
    <div class="slide-header-box">
      <div class="slide-eyebrow-pill">KESIMPULAN AKHIR</div>
      <h2 class="slide-heading-text">Verdict Riset & Ruang Diskusi</h2>
    </div>

    <div class="verdict-main-card">
      <div class="verdict-badge-header">
        <span>⚖️</span>
        <span>VERDICT OBJEKTIF REDAKSI</span>
      </div>
      <div class="verdict-core-text">{verdict_text}</div>
    </div>

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
    """
    Merender slide carousel 1080x1350 kualitas agensi desain
    menggunakan Playwright Chromium Headless.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    theme = PROGRAMS_THEME.get(prog_id, PROGRAMS_THEME["ANGKA_BICARA"])

    slides_data = content.get("slides", [])[:4]
    total_slides = 2 + len(slides_data)  # 1 Cover + N Content + 1 Verdict

    html_pages: List[Tuple[str, str]] = []

    # Slide 1: Cover
    html_pages.append(("slide_01", render_html_cover(content, theme, total_slides)))

    # Slides 2..N: Data Breakdown
    for i, s_data in enumerate(slides_data, start=2):
        html_pages.append((f"slide_{i:02d}", render_html_slide(content, theme, s_data, i, total_slides)))

    # Slide Final: Verdict & CTA
    html_pages.append((f"slide_{total_slides:02d}", render_html_verdict(content, theme, total_slides)))

    # Simpan backup file HTML
    for name, page_html in html_pages:
        html_file = out_dir / f"{name}.html"
        html_file.write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []

    try:
        from playwright.sync_api import sync_playwright

        print("[Playwright] Memulai Chromium headless untuk render carousel...")
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
            im = Image.new("RGB", (W_IG, H_IG), (248, 250, 252))
            d = ImageDraw.Draw(im)
            d.text((80, 80), f"METRIKA • {theme['label']}\n(Silakan install Playwright)", fill=(15, 23, 42))
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
    """
    Merender video 1080x1920 vertikal yang menempatkan slide beresolusi tinggi di tengah
    dengan latar bersih dan subtitle karaoke berjalan aktif di bar bawah.
    """
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
        slides_img = [Image.new("RGB", (W_V - 80, 1250), (248, 250, 252))]

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

            # Kanvas dasar vertikal Studio Slate
            frame = Image.new("RGB", (W_V, H_V), (241, 245, 249))
            frame.paste(active_slide, (40, 160))

            draw = ImageDraw.Draw(frame)

            # Subtitle Card Box (y=1530..1770)
            sub_box = (60, 1530, W_V - 60, 1770)
            draw.rounded_rectangle(sub_box, radius=20, fill=(255, 255, 255), outline=(203, 213, 225), width=2)

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
                    fill=(15, 23, 42),
                    anchor="mm",
                )
            else:
                draw.text(
                    (W_V // 2, 1650),
                    f"{theme['label']} • @metrika.id",
                    font=sub_font,
                    fill=(100, 116, 139),
                    anchor="mm",
                )

            # Progress Bar Global Video
            p_width = max(10, int((W_V - 120) * (t / duration)))
            draw.rounded_rectangle((60, 1820, W_V - 60, 1828), radius=4, fill=(226, 232, 240))
            draw.rounded_rectangle((60, 1820, 60 + p_width, 1828), radius=4, fill=(15, 23, 42))

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg gagal: {err}")
    finally:
        if proc.poll() is None:
            proc.kill()

    return out_path
