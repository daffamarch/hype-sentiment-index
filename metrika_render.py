"""
metrika_render.py  --  Modul render grafis METRIKA bergaya @theeconomicinfluence.

Estetika Editorial Kelas Dunia:
- Latar Putih Bersih (Clean White Editorial Canvas)
- Tipografi Hitam Kontras Tinggi dengan Aksen Merah Provokatif (The Economic Influence Red #DC2626)
- Foto Jurnalistik / Human Face / Meme Cutout Asli yang Mengisi 55-60% Cover Slide (Full-bleed)
- Card Layout Bersih, Minimalis, dan Tajam untuk Slide Analisis Data
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

# Palet Editorial The Economic Influence (TEI)
COLOR_BG = "#FFFFFF"
COLOR_BG_ALT = "#F8FAFC"
COLOR_TEXT_MAIN = "#111827"    # Hitam pekat tajam
COLOR_TEXT_MUTED = "#4B5563"   # Abu-abu gelap editorial
COLOR_RED = "#DC2626"          # Merah Crimson Khas TEI
COLOR_RED_BG = "#FEF2F2"       # Tint merah lembut
COLOR_BORDER = "#E5E7EB"       # Border abu-abu tipis
COLOR_LINE = "#D1D5DB"

PROGRAMS_META = {
    "INDEKS_KERINGAT": {
        "label": "INDEKS KERINGAT",
        "tag": "Daya Beli & Jam Kerja",
        "badge": "KALKULASI RUPIAH",
    },
    "RADAR_SENTIMEN": {
        "label": "RADAR SENTIMEN",
        "tag": "Polarisasi Opini Publik",
        "badge": "PETA OPINI PUBLIK",
    },
    "ANGKA_BICARA": {
        "label": "ANGKA BICARA",
        "tag": "Data Storytelling & Gaya Hidup",
        "badge": "DATA & EKONOMI",
    },
}


def format_hook_html(hook_text: str) -> str:
    """
    Memformat judul hook ala @theeconomicinfluence:
    Teks hitam tebal dengan frasa provokatif berwarna MERAH (#DC2626).
    Mendukung tag <red>...</red>, **...**, atau auto-highlight cerdas.
    """
    clean_text = html.escape(hook_text.strip())
    # Decode tag khusus jika ada
    clean_text = clean_text.replace("&lt;red&gt;", "<red>").replace("&lt;/red&gt;", "</red>")
    
    if "<red>" in clean_text and "</red>" in clean_text:
        return re.sub(r"<red>(.*?)</red>", r'<span class="text-red">\1</span>', clean_text)
    
    if "**" in clean_text:
        return re.sub(r"\*\*(.*?)\*\*", r'<span class="text-red">\1</span>', clean_text)

    # Auto-highlight: Beri warna merah pada bagian tengah atau pertanyaan inti
    if "?" in clean_text:
        parts = clean_text.split("?")
        q_words = parts[0].strip().split()
        if len(q_words) > 3:
            # Highlight 2-3 kata terakhir sebelum tanda tanya
            first_part = " ".join(q_words[:-3])
            red_part = " ".join(q_words[-3:]) + "?"
            after_part = ("?" + "?".join(parts[1:])).lstrip("?").strip()
            return f'{first_part} <span class="text-red">{red_part}</span> {after_part}'.strip()
        else:
            return f'<span class="text-red">{parts[0]}?</span> {"".join(parts[1:])}'.strip()

    words = clean_text.split()
    if len(words) >= 4:
        # Sorot frasa 2-4 kata di tengah
        start = max(1, len(words) // 4)
        end = min(len(words), start + max(2, len(words) // 2))
        w_before = " ".join(words[:start])
        w_red = " ".join(words[start:end])
        w_after = " ".join(words[end:])
        res = []
        if w_before: res.append(w_before)
        res.append(f'<span class="text-red">{w_red}</span>')
        if w_after: res.append(w_after)
        return " ".join(res)

    return f'<span class="text-red">{clean_text}</span>'


def get_image_data_uri(img_path: Optional[str | Path]) -> Optional[str]:
    """Membaca foto lokal dan mengonversinya ke Base64 Data URI."""
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
        log.warning(f"Gagal encode image {img_path}: {err}")
        return None


# ==============================================================================
# 1. GENERATOR HTML/CSS EDITORIAL @THEECONOMICINFLUENCE
# ==============================================================================
def get_editorial_css() -> str:
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Outfit:wght@700;800;900&display=swap');

:root {{
  --bg: {COLOR_BG};
  --bg-alt: {COLOR_BG_ALT};
  --text-main: {COLOR_TEXT_MAIN};
  --text-muted: {COLOR_TEXT_MUTED};
  --red: {COLOR_RED};
  --red-bg: {COLOR_RED_BG};
  --border: {COLOR_BORDER};
  --line: {COLOR_LINE};
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
}}

/* Top Brand Bar (Khas TEI) */
.tei-brand-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 40px 56px 20px 56px;
  background-color: var(--bg);
  z-index: 10;
}}
.tei-logo-group {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
.tei-logo-square {{
  width: 40px;
  height: 40px;
  background-color: var(--red);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 24px;
  font-weight: 900;
  letter-spacing: -0.02em;
}}
.tei-brand-text {{
  display: flex;
  flex-direction: column;
}}
.tei-brand-name {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.01em;
  color: var(--text-main);
  line-height: 1.1;
}}
.tei-brand-sub {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
}}

.tei-meta-tag {{
  padding: 6px 14px;
  background-color: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}

/* Cover Slide Specific */
.cover-headline-container {{
  padding: 10px 56px 24px 56px;
  background-color: var(--bg);
  z-index: 10;
}}
.cover-headline {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 50px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -0.02em;
  color: var(--text-main);
}}

.stat-pill-row {{
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}}
.stat-pill {{
  display: inline-flex;
  align-items: center;
  gap: 12px;
  background: var(--red-bg);
  border: 1.5px solid rgba(220, 38, 38, 0.25);
  border-radius: 999px;
  padding: 8px 22px;
}}
.stat-num {{
  font-family: 'Outfit', sans-serif;
  font-size: 24px;
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
  object-position: center 20%;
  display: block;
}}
.photo-gradient-overlay {{
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 180px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.75) 0%, transparent 100%);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 30px 56px;
}}
.photo-swipe-prompt {{
  color: #FFFFFF;
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6);
}}
.photo-swipe-arrow {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--red);
  color: #FFFFFF;
  font-weight: 900;
}}

/* Inside Slides Specific */
.inside-body {{
  flex: 1;
  padding: 20px 56px 40px 56px;
  display: flex;
  flex-direction: column;
}}
.slide-title-section {{
  margin-bottom: 24px;
}}
.slide-section-badge {{
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
  margin-bottom: 8px;
}}
.slide-main-heading {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 42px;
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.015em;
  color: var(--text-main);
}}

.metric-spotlight-card {{
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-left: 6px solid var(--red);
  border-radius: 18px;
  padding: 24px 30px;
  display: flex;
  align-items: center;
  gap: 28px;
  margin-bottom: 24px;
}}
.spotlight-big-val {{
  font-family: 'Outfit', sans-serif;
  font-size: 48px;
  font-weight: 900;
  color: var(--red);
  white-space: nowrap;
}}
.spotlight-vertical-line {{
  width: 1px;
  height: 54px;
  background: var(--line);
}}
.spotlight-label-text {{
  font-size: 19px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}

.cards-grid-layout {{
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}}
.cards-grid-layout.single-col {{
  grid-template-columns: 1fr;
}}
.editorial-card {{
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}}
.card-header-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 20px;
  align-self: flex-start;
}}
.card-header-pill.red {{
  background-color: var(--red-bg);
  color: var(--red);
  border: 1px solid rgba(220, 38, 38, 0.2);
}}
.card-header-pill.dark {{
  background-color: var(--bg-alt);
  color: var(--text-main);
  border: 1px solid var(--border);
}}
.points-vertical-list {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}
.point-row-item {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
}}
.point-bullet-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--red);
  margin-top: 9px;
  flex-shrink: 0;
}}
.point-text-content {{
  font-size: 18px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text-main);
}}

/* Slide Final / Verdict Specific */
.verdict-box-tei {{
  background-color: var(--red-bg);
  border: 2px solid var(--red);
  border-radius: 22px;
  padding: 34px 36px;
  margin-bottom: 22px;
}}
.verdict-label-tei {{
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--red);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.verdict-text-tei {{
  font-size: 23px;
  font-weight: 700;
  line-height: 1.45;
  color: var(--text-main);
}}

.cta-box-tei {{
  background: var(--bg-alt);
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 26px 30px;
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 22px;
}}
.cta-circle-q {{
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: var(--red);
  color: #FFFFFF;
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.cta-question-text {{
  font-size: 19px;
  font-weight: 700;
  line-height: 1.38;
  color: var(--text-main);
}}

.sources-box-tei {{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 22px;
  margin-bottom: 20px;
}}
.sources-title-tei {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
}}
.sources-list-tei {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}}
.source-tag {{
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}}

/* Progress Bar Red Segments */
.progress-segments-tei {{
  display: flex;
  gap: 6px;
  margin-top: auto;
  margin-bottom: 14px;
}}
.prog-seg-tei {{
  flex: 1;
  height: 5px;
  border-radius: 3px;
  background-color: var(--border);
}}
.prog-seg-tei.active {{
  background-color: var(--red);
}}
.tei-footer-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
}}
"""


def render_html_cover(content: Dict[str, Any], prog: Dict[str, Any], total_slides: int) -> str:
    """Merender Slide 1 Cover bergaya The Economic Influence."""
    hook_raw = content.get("hook", "")
    hook_formatted = format_hook_html(hook_raw)
    
    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", "")))
    hero_lbl = html.escape(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "18 OKT 2026"))).upper()
    
    # Foto Jurnalistik / Real World
    img_uri = get_image_data_uri(content.get("hero_image"))
    
    # Elemen stat pill jika ada data kunci
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

    # Image DOM
    if img_uri:
        photo_dom = f'<img src="{img_uri}" class="cover-photo" alt="Cover Photo" />'
    else:
        # Fallback grafis berita jika foto belum tersedia
        photo_dom = f"""
        <div style="width:100%; height:100%; background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); display:flex; align-items:center; justify-content:center; flex-direction:column; padding:40px;">
          <div style="font-family:'Outfit', sans-serif; font-size:48px; font-weight:900; color:#FFFFFF; margin-bottom:12px;">{prog['badge']}</div>
          <div style="font-size:20px; font-weight:600; color:#94A3B8; text-align:center;">{hero_lbl}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_editorial_css()}
</style>
</head>
<body>
  <!-- Top Brand Header -->
  <div class="tei-brand-bar">
    <div class="tei-logo-group">
      <div class="tei-logo-square">M</div>
      <div class="tei-brand-text">
        <div class="tei-brand-name">METRIKA</div>
        <div class="tei-brand-sub">ECONOMIC INFLUENCE & DATA</div>
      </div>
    </div>
    <div class="tei-meta-tag">{date_str} • {prog['label']}</div>
  </div>

  <!-- Headline Area -->
  <div class="cover-headline-container">
    <h1 class="cover-headline">{hook_formatted}</h1>
    {stat_html}
  </div>

  <!-- Lower 55-60%: Real World Photo -->
  <div class="cover-photo-wrapper">
    {photo_dom}
    <div class="photo-gradient-overlay">
      <div class="photo-swipe-prompt">
        <span class="photo-swipe-arrow">→</span>
        Geser untuk bedah data & perbandingan lengkap
      </div>
      <div style="color:rgba(255,255,255,0.7); font-size:14px; font-weight:700;">@metrika.id</div>
    </div>
  </div>
</body>
</html>
"""


def render_html_slide(
    content: Dict[str, Any],
    prog: Dict[str, Any],
    slide_data: Dict[str, Any],
    slide_idx: int,
    total_slides: int,
) -> str:
    """Merender Slide 2..N (Data Breakdown) bergaya The Economic Influence."""
    heading = html.escape(slide_data.get("heading", ""))
    metric = slide_data.get("metric")

    metric_html = ""
    if metric:
        m_val = html.escape(str(metric.get("value", "")))
        m_lbl = html.escape(str(metric.get("label", "")))
        metric_html = f"""
        <div class="metric-spotlight-card">
          <div class="spotlight-big-val">{m_val}</div>
          <div class="spotlight-vertical-line"></div>
          <div class="spotlight-label-text">{m_lbl}</div>
        </div>
        """

    columns = slide_data.get("columns", [])[:2]
    is_single = len(columns) == 1

    cards_html = []
    for i, col in enumerate(columns):
        col_title = html.escape(col.get("title", f"Poin Analisis {i+1}"))
        pill_class = "red" if i == 0 else "dark"

        points = col.get("points", [])
        points_html = []
        for pt in points:
            clean_pt = html.escape(pt)
            points_html.append(f"""
            <div class="point-row-item">
              <div class="point-bullet-dot"></div>
              <div class="point-text-content">{clean_pt}</div>
            </div>
            """)

        cards_html.append(f"""
        <div class="editorial-card">
          <div class="card-header-pill {pill_class}">
            {col_title}
          </div>
          <div class="points-vertical-list">
            {"".join(points_html)}
          </div>
        </div>
        """)

    grid_class = "cards-grid-layout single-col" if is_single else "cards-grid-layout"

    # Progress bar segments
    prog_segs = []
    for idx in range(total_slides):
        active_cls = "active" if idx < slide_idx else ""
        prog_segs.append(f'<div class="prog-seg-tei {active_cls}"></div>')

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_editorial_css()}
</style>
</head>
<body>
  <!-- Top Brand Header -->
  <div class="tei-brand-bar">
    <div class="tei-logo-group">
      <div class="tei-logo-square">M</div>
      <div class="tei-brand-text">
        <div class="tei-brand-name">METRIKA</div>
        <div class="tei-brand-sub">ECONOMIC INFLUENCE & DATA</div>
      </div>
    </div>
    <div class="tei-meta-tag">{slide_idx:02d} / {total_slides:02d}</div>
  </div>

  <div class="inside-body">
    <div class="slide-title-section">
      <div class="slide-section-badge">{prog['badge']}</div>
      <h2 class="slide-main-heading">{heading}</h2>
    </div>

    {metric_html}

    <div class="{grid_class}">
      {"".join(cards_html)}
    </div>

    <div class="progress-segments-tei">
      {"".join(prog_segs)}
    </div>

    <div class="tei-footer-bar">
      <div>@metrika.id</div>
      <div>Data & Jurnalisme Komputasi</div>
    </div>
  </div>
</body>
</html>
"""


def render_html_verdict(content: Dict[str, Any], prog: Dict[str, Any], total_slides: int) -> str:
    """Merender Slide Terakhir (Verdict & Diskusi) bergaya The Economic Influence."""
    verdict_text = html.escape(content.get("verdict", ""))
    cta_text = html.escape(content.get("cta", ""))
    sources = content.get("sources", [])

    sources_html = []
    for s in sources:
        clean_s = html.escape(s)
        sources_html.append(f'<span class="source-tag">{clean_s}</span>')

    prog_segs = ['<div class="prog-seg-tei active"></div>'] * total_slides

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_editorial_css()}
</style>
</head>
<body>
  <!-- Top Brand Header -->
  <div class="tei-brand-bar">
    <div class="tei-logo-group">
      <div class="tei-logo-square">M</div>
      <div class="tei-brand-text">
        <div class="tei-brand-name">METRIKA</div>
        <div class="tei-brand-sub">ECONOMIC INFLUENCE & DATA</div>
      </div>
    </div>
    <div class="tei-meta-tag">{total_slides:02d} / {total_slides:02d}</div>
  </div>

  <div class="inside-body">
    <div class="slide-title-section">
      <div class="slide-section-badge">KESIMPULAN DATA</div>
      <h2 class="slide-main-heading">Verdict Objektif & Ruang Diskusi</h2>
    </div>

    <div class="verdict-box-tei">
      <div class="verdict-label-tei">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--red);"></span>
        ANALISIS REDAKSI
      </div>
      <div class="verdict-text-tei">{verdict_text}</div>
    </div>

    <div class="cta-box-tei">
      <div class="cta-circle-q">?</div>
      <div class="cta-question-text">{cta_text}</div>
    </div>

    <div class="sources-box-tei">
      <div class="sources-title-tei">SUMBER DATA TERVERIFIKASI</div>
      <div class="sources-list-tei">
        {"".join(sources_html)}
      </div>
    </div>

    <div class="progress-segments-tei">
      {"".join(prog_segs)}
    </div>

    <div class="tei-footer-bar">
      <div>@metrika.id</div>
      <div>The Economic Influence of Data</div>
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
    Merender slide carousel 1080x1350 bergaya @theeconomicinfluence
    menggunakan Playwright Chromium Headless.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    prog = PROGRAMS_META.get(prog_id, PROGRAMS_META["ANGKA_BICARA"])

    slides_data = content.get("slides", [])[:4]
    total_slides = 2 + len(slides_data)  # Cover + N Slides + Verdict

    html_pages: List[Tuple[str, str]] = []

    # Slide 1: Cover dengan Foto Jurnalistik / Meme Humanis
    html_pages.append(("slide_01", render_html_cover(content, prog, total_slides)))

    # Slides 2..N: Breakdown Data Bersih
    for i, s_data in enumerate(slides_data, start=2):
        html_pages.append((f"slide_{i:02d}", render_html_slide(content, prog, s_data, i, total_slides)))

    # Slide Final: Verdict & CTA
    html_pages.append((f"slide_{total_slides:02d}", render_html_verdict(content, prog, total_slides)))

    # Simpan backup file HTML
    for name, page_html in html_pages:
        html_file = out_dir / f"{name}.html"
        html_file.write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []

    try:
        from playwright.sync_api import sync_playwright

        print("[Playwright] Merender carousel The Economic Influence via Chromium...")
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
                print(f"[Playwright] Berhasil render: {out_img.name}")

            browser.close()

    except ImportError:
        log.warning("Playwright belum terpasang. Menjalankan fallback visual.")
        for name, _ in html_pages:
            fallback_img = out_dir / f"{name}.png"
            im = Image.new("RGB", (W_IG, H_IG), (255, 255, 255))
            d = ImageDraw.Draw(im)
            d.text((100, 100), f"METRIKA • {prog['label']}\n(Silakan install Playwright)", fill=(17, 24, 39))
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
    prog = PROGRAMS_META.get(prog_id, PROGRAMS_META["ANGKA_BICARA"])

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
        slides_img = [Image.new("RGB", (W_V - 80, 1250), (255, 255, 255))]

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

            # Kanvas dasar vertikal putih abu-abu bersih
            frame = Image.new("RGB", (W_V, H_V), (243, 244, 246))
            frame.paste(active_slide, (40, 160))

            draw = ImageDraw.Draw(frame)

            # Subtitle Card Box (y=1530..1770)
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
                    f"{prog['label']} • @metrika.id",
                    font=sub_font,
                    fill=(75, 85, 99),
                    anchor="mm",
                )

            # Progress Bar Global Video
            p_width = max(10, int((W_V - 120) * (t / duration)))
            draw.rounded_rectangle((60, 1820, W_V - 60, 1828), radius=4, fill=(229, 231, 235))
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
