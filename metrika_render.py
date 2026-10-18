"""
metrika_render.py  --  Modul render grafis METRIKA Kelas Agensi (Jurnalisme Data & Riset Finansial).

Desain Grafis Editorial Profesional:
- Kanvas Bersih, Tajam, dan Berimbang (Tidak ada ruang kosong hampa / blank void).
- Cover Slide 1: Headline tajam hitam-merah di atas (40%) & Foto Full-Bleed di bawah (60%).
- Slide 2 & 3 (Data Breakdown): Penuh argumen, konteks makro, dan kartu data proporsional.
- Slide Final: Verdict analisis redaksi + Ruang diskusi publik + Rujukan resmi.
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

# Palet Identitas METRIKA (Clean Editorial Slate)
COLOR_BG = "#F8FAFC"           # Studio Slate Light (Bersih, modern, berwibawa)
COLOR_CARD = "#FFFFFF"         # Kartu putih kontras tinggi
COLOR_TEXT_MAIN = "#0F172A"    # Deep Charcoal / Hampir hitam
COLOR_TEXT_MUTED = "#475569"   # Slate Grey
COLOR_RED = "#DC2626"          # Merah Crimson Aksen Provokatif
COLOR_BORDER = "#E2E8F0"       # Border halus
COLOR_LINE = "#E2E8F0"

# Tema Rubrik METRIKA
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
    Teks hitam tebal dengan kata kunci penting diberi warna MERAH (#DC2626).
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

    # Auto-highlight jika tidak ada tag: sorot bagian pertanyaan atau frasa tengah
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
# 1. GENERATOR CSS & TATA LETAK EDITORIAL
# ==============================================================================
def get_base_css() -> str:
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Outfit:wght@600;700;800;900&display=swap');

:root {{
  --bg: {COLOR_BG};
  --card: {COLOR_CARD};
  --text-main: {COLOR_TEXT_MAIN};
  --text-muted: {COLOR_TEXT_MUTED};
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
  background-color: #FFFFFF;
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

/* Top Brand Bar */
.brand-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 38px 52px 18px 52px;
  background-color: #FFFFFF;
  z-index: 10;
}}
.brand-left {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
.brand-monogram {{
  width: 42px;
  height: 42px;
  background: var(--red);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
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
  color: var(--text-main);
  line-height: 1.1;
}}
.brand-tagline {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
}}

.program-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background-color: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}}

/* Cover Slide (40% Text Atas & 60% Foto Bawah) */
.cover-top-box {{
  padding: 8px 52px 24px 52px;
  background-color: #FFFFFF;
  z-index: 10;
}}
.cover-headline {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 50px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -0.02em;
  color: var(--text-main);
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
  background: #FEF2F2;
  border: 1.5px solid rgba(220, 38, 38, 0.25);
  border-radius: 999px;
  padding: 8px 22px;
}}
.stat-num {{
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  color: var(--red);
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
  background-color: #0F172A;
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
  height: 190px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.85) 0%, transparent 100%);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 30px 52px;
}}
.photo-swipe-prompt {{
  color: #FFFFFF;
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
  background-color: var(--red);
  color: #FFFFFF;
  font-weight: 900;
}}

/* Inside Content Slides (Padat & Kaya Argumen) */
.inside-content-body {{
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 10px 52px 34px 52px;
}}
.slide-header-box {{
  margin-bottom: 18px;
}}
.slide-eyebrow-pill {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
  margin-bottom: 6px;
}}
.slide-heading-text {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 40px;
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.015em;
  color: var(--text-main);
}}

/* Macro Context Overview Box */
.macro-context-box {{
  background: #F1F5F9;
  border-left: 4px solid var(--red);
  padding: 16px 22px;
  border-radius: 12px;
  margin-bottom: 18px;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text-main);
}}

/* Spotlight Banner Card */
.metric-spotlight-bar {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-left: 6px solid var(--red);
  border-radius: 18px;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 20px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.03);
}}
.spotlight-value {{
  font-family: 'Outfit', sans-serif;
  font-size: 46px;
  font-weight: 900;
  color: var(--red);
  white-space: nowrap;
}}
.spotlight-divider {{
  width: 1.5px;
  height: 50px;
  background: var(--line);
}}
.spotlight-explanation {{
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

/* Dual Column Cards (Mengisi Seluruh Ruang Vertikal) */
.columns-container {{
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}}
.columns-container.single-column {{
  grid-template-columns: 1fr;
}}
.editorial-column-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}}
.column-card-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}}
.col-header-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text-main);
}}
.col-header-pill.highlight {{
  background: #FEF2F2;
  border: 1px solid rgba(220, 38, 38, 0.25);
  color: var(--red);
}}

.points-list-wrap {{
  display: flex;
  flex-direction: column;
  gap: 18px;
}}
.point-item-row {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
}}
.point-bullet-box {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--red);
  margin-top: 8px;
  flex-shrink: 0;
}}
.point-body-text {{
  font-size: 18px;
  font-weight: 500;
  line-height: 1.48;
  color: var(--text-main);
}}
.point-body-text b {{
  font-weight: 800;
  color: var(--text-main);
}}

.column-card-footer {{
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

/* Slide Final (Verdict & Discussion) */
.verdict-main-card {{
  background: #FEF2F2;
  border: 2px solid var(--red);
  border-radius: 22px;
  padding: 32px 36px;
  margin-bottom: 20px;
  box-shadow: 0 8px 24px rgba(220, 38, 38, 0.08);
}}
.verdict-badge-header {{
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.verdict-core-text {{
  font-size: 23px;
  font-weight: 700;
  line-height: 1.45;
  color: var(--text-main);
}}

.cta-discussion-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 24px 30px;
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}}
.cta-badge-icon {{
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: var(--red);
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
  font-size: 19px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

.verified-sources-card {{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 22px;
  margin-bottom: 20px;
}}
.sources-title-row {{
  font-size: 12px;
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
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
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
  background-color: var(--red);
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
    """Merender Slide 1 Cover: Headline Hitam-Merah di atas & Foto Full-Bleed di bawah."""
    hook_raw = content.get("hook", "")
    hook_formatted = format_hook_html(hook_raw)

    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", "")))
    hero_lbl = html.escape(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "18 OKT 2026"))).upper()

    # Pastikan data gambar Base64 terambil
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
        # Fallback visual jika file foto tidak terbaca
        photo_dom = f"""
        <div style="width:100%; height:100%; background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); display:flex; align-items:center; justify-content:center; flex-direction:column; padding:40px;">
          <div style="font-family:'Outfit', sans-serif; font-size:44px; font-weight:900; color:#FFFFFF; margin-bottom:12px;">{theme['label']}</div>
          <div style="font-size:20px; font-weight:700; color:#94A3B8; text-align:center;">{hero_lbl}</div>
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
      <div style="color:rgba(255,255,255,0.7); font-size:13px; font-weight:700;">@metrika.id</div>
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
    """Merender Slide 2..N (Data Breakdown) padat teks dan argumen mendalam."""
    heading = html.escape(slide_data.get("heading", ""))
    metric = slide_data.get("metric")
    overview_context = slide_data.get("overview_context", "")

    context_html = ""
    if overview_context:
        context_html = f"""
        <div class="macro-context-box">
          {html.escape(overview_context)}
        </div>
        """

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

    {context_html}
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
    """Merender Slide Terakhir: Verdict Redaksi & Ruang Diskusi."""
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

            frame = Image.new("RGB", (W_V, H_V), (241, 245, 249))
            frame.paste(active_slide, (40, 160))

            draw = ImageDraw.Draw(frame)

            sub_box = (60, 1530, W_V - 60, 1770)
            draw.rounded_rectangle(sub_box, radius=20, fill=(255, 255, 255), outline=(220, 38, 38), width=3)

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
                    fill=(220, 38, 38),
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

            p_width = max(10, int((W_V - 120) * (t / duration)))
            draw.rounded_rectangle((60, 1820, W_V - 60, 1828), radius=4, fill=(226, 232, 240))
            draw.rounded_rectangle((60, 1820, 60 + p_width, 1828), radius=4, fill=(220, 38, 38))

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg gagal: {err}")
    finally:
        if proc.poll() is None:
            proc.kill()

    return out_path
