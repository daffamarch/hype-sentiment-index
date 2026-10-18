"""
metrika_render.py  --  Modul render grafis METRIKA Kelas Agensi (HTML/CSS + Playwright + FFmpeg).

Menghasilkan grafis carousel Instagram (1080x1350) setara Canva/Figma/Photoshop menggunakan
modern CSS (Glassmorphism, Ambient Glow, Google Fonts, Flexbox, Dynamic Meters) yang dirender
secara headless menggunakan Chromium (Playwright).
Juga menyediakan generator video vertikal (1080x1920) dengan karaoke subtitle via FFmpeg.
"""
from __future__ import annotations

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

# Dimensi Standar
W_IG, H_IG = 1080, 1350
W_V, H_V = 1080, 1920

PROGRAMS_META = {
    "INDEKS_KERINGAT": {
        "label": "INDEKS KERINGAT",
        "tag": "Jurnal Daya Beli & Jam Kerja",
        "accent": "#FACC15",
        "accent_glow": "rgba(250, 204, 21, 0.35)",
        "tone_left": "Beban Narik Ojol",
        "tone_right": "Pekerja UMP Jakarta",
    },
    "RADAR_SENTIMEN": {
        "label": "RADAR SENTIMEN",
        "tag": "Peta Polarisasi Opini Publik",
        "accent": "#38BDF8",
        "accent_glow": "rgba(56, 189, 248, 0.35)",
        "tone_left": "Kubu Sepakat / Pro",
        "tone_right": "Kubu Kritis / Kontra",
    },
    "ANGKA_BICARA": {
        "label": "ANGKA BICARA",
        "tag": "Data Storytelling & Gaya Hidup",
        "accent": "#10B981",
        "accent_glow": "rgba(16, 185, 129, 0.35)",
        "tone_left": "Pengeluaran Esensial",
        "tone_right": "Kapasitas Tabungan",
    },
}

TONE_COLORS = {
    "key": "#FACC15",
    "fact": "#38BDF8",
    "pro": "#10B981",
    "con": "#EF4444",
    "neutral": "#94A3B8",
}


# ==============================================================================
# 1. GENERATOR HTML/CSS KELAS AGENSI
# ==============================================================================
def get_base_css(accent: str, accent_glow: str) -> str:
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {{
  --bg: #07090E;
  --bg-deep: #030508;
  --surface: rgba(20, 28, 45, 0.68);
  --surface-solid: #121826;
  --surface-hi: rgba(30, 42, 68, 0.85);
  --border: rgba(255, 255, 255, 0.08);
  --border-light: rgba(255, 255, 255, 0.16);
  --text: #F8FAFC;
  --text-dim: #94A3B8;
  --text-mute: #64748B;
  --accent: {accent};
  --accent-glow: {accent_glow};
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
  color: var(--text);
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 68px 60px 48px 60px;
}}

/* Ambient Glow & Grid Layer */
.ambient-glow-1 {{
  position: absolute;
  top: -120px;
  right: -80px;
  width: 620px;
  height: 620px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--accent-glow) 0%, rgba(0,0,0,0) 70%);
  filter: blur(80px);
  z-index: 0;
  pointer-events: none;
}}
.ambient-glow-2 {{
  position: absolute;
  bottom: -100px;
  left: -100px;
  width: 580px;
  height: 580px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.12) 0%, rgba(0,0,0,0) 70%);
  filter: blur(90px);
  z-index: 0;
  pointer-events: none;
}}
.grid-overlay {{
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(to right, rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
  background-size: 40px 40px;
  z-index: 1;
  pointer-events: none;
}}

.content-wrapper {{
  position: relative;
  z-index: 2;
  height: 100%;
  display: flex;
  flex-direction: column;
}}

/* Header Bar */
.header-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}}
.brand-group {{
  display: flex;
  align-items: center;
  gap: 16px;
}}
.brand-logo {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
.logo-icon {{
  width: 32px;
  height: 32px;
  background: var(--accent);
  border-radius: 8px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 4px;
  gap: 3px;
}}
.logo-bar {{
  width: 3.5px;
  background-color: var(--bg);
  border-radius: 2px;
}}
.logo-bar:nth-child(1) {{ height: 10px; }}
.logo-bar:nth-child(2) {{ height: 16px; }}
.logo-bar:nth-child(3) {{ height: 21px; }}

.logo-text {{
  font-family: 'Outfit', sans-serif;
  font-weight: 900;
  font-size: 26px;
  letter-spacing: 0.12em;
  color: var(--text);
}}
.program-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--accent);
  color: var(--accent);
}}
.status-dot {{
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}}
.header-meta {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
.meta-chip {{
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-dim);
  letter-spacing: 0.05em;
}}

/* Progress Bar Segments */
.progress-bar-container {{
  display: flex;
  gap: 8px;
  margin-top: auto;
  margin-bottom: 16px;
}}
.progress-bar-seg {{
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.1);
}}
.progress-bar-seg.active {{
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent-glow);
}}
.footer-text-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-mute);
}}
"""


def render_html_cover(content: Dict[str, Any], prog: Dict[str, Any], total_slides: int) -> str:
    accent = prog["accent"]
    accent_glow = prog["accent_glow"]
    hook = html.escape(content.get("hook", ""))
    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", "0%")))
    hero_label = html.escape(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "18 OKT 2026"))).upper()

    css = get_base_css(accent, accent_glow)

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{css}

.cover-tag {{
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-mute);
  margin-bottom: 14px;
}}
.cover-hook {{
  font-family: 'Outfit', sans-serif;
  font-size: 56px;
  font-weight: 800;
  line-height: 1.16;
  letter-spacing: -0.02em;
  color: #FFFFFF;
  margin-bottom: 28px;
}}
.cover-hook span {{
  background: linear-gradient(135deg, #FFFFFF 30%, var(--accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.hero-box {{
  flex: 1;
  background: linear-gradient(145deg, rgba(24, 33, 52, 0.75) 0%, rgba(13, 19, 32, 0.90) 100%);
  backdrop-filter: blur(28px);
  border: 1px solid var(--border-light);
  border-radius: 32px;
  padding: 42px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
  margin-bottom: 24px;
}}
.hero-box::before {{
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
}}
.hero-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.hero-title-pill {{
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 8px;
}}
.hero-val-wrap {{
  margin: 14px 0;
}}
.hero-big-number {{
  font-family: 'Outfit', sans-serif;
  font-size: 96px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--accent);
  text-shadow: 0 0 45px var(--accent-glow);
}}
.hero-desc {{
  font-size: 26px;
  font-weight: 600;
  line-height: 1.35;
  color: #E2E8F0;
  margin-top: 14px;
}}

.hero-visual-card {{
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 16px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.visual-card-text {{
  font-size: 15px;
  font-weight: 600;
  color: var(--text-dim);
}}
.visual-card-badge {{
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.08);
  color: var(--accent);
  border: 1px solid rgba(255, 255, 255, 0.1);
}}

.cover-swipe-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 0 4px;
}}
.swipe-instruction {{
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 12px;
}}
.swipe-arrow {{
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--surface-hi);
  border: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  font-size: 22px;
}}
</style>
</head>
<body>
<div class="ambient-glow-1"></div>
<div class="ambient-glow-2"></div>
<div class="grid-overlay"></div>

<div class="content-wrapper">
  <div class="header-bar">
    <div class="brand-group">
      <div class="brand-logo">
        <div class="logo-icon">
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
        </div>
        <div class="logo-text">METRIKA</div>
      </div>
      <div class="program-pill">
        <div class="status-dot"></div>
        {prog["label"]}
      </div>
    </div>
    <div class="header-meta">
      <div class="meta-chip">{date_str}</div>
    </div>
  </div>

  <div class="cover-tag">{prog["tag"]}</div>
  <div class="cover-hook"><span>{hook}</span></div>

  <div class="hero-box">
    <div class="hero-header">
      <div class="hero-title-pill">
        <div class="status-dot"></div>
        ANGKA KUNCI & INDIKATOR UTAMA
      </div>
    </div>

    <div class="hero-val-wrap">
      <div class="hero-big-number">{hero_val}</div>
      <div class="hero-desc">{hero_label}</div>
    </div>

    <div class="hero-visual-card">
      <div class="visual-card-text">Status Analisis Ekonomi & Opini Terkini</div>
      <div class="visual-card-badge">DATA RESMI & TERUJI</div>
    </div>
  </div>

  <div class="cover-swipe-row">
    <div class="swipe-instruction">Geser untuk breakdown data</div>
    <div class="swipe-arrow">→</div>
  </div>

  <div class="progress-bar-container">
    <div class="progress-bar-seg active"></div>
    {"".join('<div class="progress-bar-seg"></div>' for _ in range(total_slides - 1))}
  </div>

  <div class="footer-text-row">
    <div>@metrika.id</div>
    <div>Data untuk kamu yang berpikir</div>
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
    accent = prog["accent"]
    accent_glow = prog["accent_glow"]
    css = get_base_css(accent, accent_glow)

    heading = html.escape(slide_data.get("heading", ""))
    metric = slide_data.get("metric")

    metric_html = ""
    if metric:
        m_val = html.escape(str(metric.get("value", "")))
        m_lbl = html.escape(str(metric.get("label", "")))
        metric_html = f"""
        <div class="metric-spotlight-box">
          <div class="spotlight-val">{m_val}</div>
          <div class="spotlight-divider"></div>
          <div class="spotlight-lbl">{m_lbl}</div>
        </div>
        """

    columns = slide_data.get("columns", [])[:2]
    is_single = len(columns) == 1

    cards_html = []
    for i, col in enumerate(columns):
        col_title = html.escape(col.get("title", f"Poin Analisis {i+1}"))
        col_tone = col.get("tone", "key")
        tone_color = TONE_COLORS.get(col_tone, accent)

        points = col.get("points", [])
        points_html = []
        for pt in points:
            clean_pt = html.escape(pt)
            points_html.append(f"""
            <div class="point-row">
              <div class="point-bullet" style="background: {tone_color}; box-shadow: 0 0 8px {tone_color};"></div>
              <div class="point-text">{clean_pt}</div>
            </div>
            """)

        cards_html.append(f"""
        <div class="column-card" style="border-top: 4px solid {tone_color};">
          <div class="card-header-chip" style="color: {tone_color};">
            <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:{tone_color};"></span>
            {col_title}
          </div>
          <div class="points-wrapper">
            {"".join(points_html)}
          </div>
        </div>
        """)

    grid_class = "columns-layout single-col" if is_single else "columns-layout"

    # Progress bar HTML
    prog_segs = []
    for idx in range(total_slides):
        active_cls = "active" if idx < slide_idx else ""
        prog_segs.append(f'<div class="progress-bar-seg {active_cls}"></div>')

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{css}

.slide-heading {{
  font-family: 'Outfit', sans-serif;
  font-size: 46px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: var(--text);
  margin-bottom: 24px;
}}

.metric-spotlight-box {{
  background: linear-gradient(135deg, rgba(25, 34, 54, 0.7) 0%, rgba(14, 20, 34, 0.85) 100%);
  border: 1px solid var(--border-light);
  border-radius: 22px;
  padding: 22px 30px;
  display: flex;
  align-items: center;
  gap: 28px;
  margin-bottom: 22px;
  backdrop-filter: blur(20px);
}}
.spotlight-val {{
  font-family: 'Outfit', sans-serif;
  font-size: 48px;
  font-weight: 900;
  color: var(--accent);
  white-space: nowrap;
}}
.spotlight-divider {{
  width: 1px;
  height: 52px;
  background: var(--border-light);
}}
.spotlight-lbl {{
  font-size: 19px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text);
}}

.columns-layout {{
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}}
.columns-layout.single-col {{
  grid-template-columns: 1fr;
}}
.column-card {{
  background: linear-gradient(180deg, rgba(20, 27, 44, 0.70) 0%, rgba(12, 17, 28, 0.85) 100%);
  backdrop-filter: blur(22px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 26px 22px;
  display: flex;
  flex-direction: column;
}}
.card-header-chip {{
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.points-wrapper {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}
.point-row {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
}}
.point-bullet {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 8px;
  flex-shrink: 0;
}}
.point-text {{
  font-size: 18px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--text);
}}
</style>
</head>
<body>
<div class="ambient-glow-1"></div>
<div class="ambient-glow-2"></div>
<div class="grid-overlay"></div>

<div class="content-wrapper">
  <div class="header-bar">
    <div class="brand-group">
      <div class="brand-logo">
        <div class="logo-icon">
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
        </div>
        <div class="logo-text">METRIKA</div>
      </div>
      <div class="program-pill">
        <div class="status-dot"></div>
        {prog["label"]}
      </div>
    </div>
    <div class="header-meta">
      <div class="meta-chip">{slide_idx:02d} / {total_slides:02d}</div>
    </div>
  </div>

  <div class="slide-heading">{heading}</div>

  {metric_html}

  <div class="{grid_class}">
    {"".join(cards_html)}
  </div>

  <div class="progress-bar-container">
    {"".join(prog_segs)}
  </div>

  <div class="footer-text-row">
    <div>@metrika.id</div>
    <div>Data untuk kamu yang berpikir</div>
  </div>
</div>
</body>
</html>
"""


def render_html_verdict(content: Dict[str, Any], prog: Dict[str, Any], total_slides: int) -> str:
    accent = prog["accent"]
    accent_glow = prog["accent_glow"]
    css = get_base_css(accent, accent_glow)

    verdict_text = html.escape(content.get("verdict", ""))
    cta_text = html.escape(content.get("cta", ""))
    sources = content.get("sources", [])

    sources_html = []
    for s in sources:
        clean_s = html.escape(s)
        sources_html.append(f'<div class="src-item">• {clean_s}</div>')

    # All segments active
    prog_segs = ['<div class="progress-bar-seg active"></div>'] * total_slides

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{css}

.verdict-header-title {{
  font-family: 'Outfit', sans-serif;
  font-size: 46px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: var(--text);
  margin-bottom: 24px;
}}

.verdict-box {{
  background: linear-gradient(145deg, rgba(24, 33, 52, 0.72) 0%, rgba(13, 19, 32, 0.88) 100%);
  border: 1px solid var(--border-light);
  border-radius: 28px;
  padding: 34px 36px;
  margin-bottom: 20px;
  backdrop-filter: blur(24px);
}}
.verdict-badge {{
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.verdict-content {{
  font-size: 23px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text);
}}

.discussion-cta-box {{
  background: linear-gradient(135deg, rgba(28, 39, 64, 0.55) 0%, rgba(16, 23, 38, 0.75) 100%);
  border: 2px solid var(--accent);
  border-radius: 24px;
  padding: 26px 30px;
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 22px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.35);
}}
.cta-badge-circle {{
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--bg);
  font-family: 'Outfit', sans-serif;
  font-size: 30px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.cta-content-text {{
  font-size: 20px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text);
}}

.sources-card {{
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px 24px;
  margin-bottom: 22px;
}}
.sources-header {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 8px;
}}
.sources-entries {{
  display: flex;
  flex-direction: column;
  gap: 5px;
}}
.src-item {{
  font-size: 14px;
  font-weight: 500;
  color: var(--text-dim);
}}
</style>
</head>
<body>
<div class="ambient-glow-1"></div>
<div class="ambient-glow-2"></div>
<div class="grid-overlay"></div>

<div class="content-wrapper">
  <div class="header-bar">
    <div class="brand-group">
      <div class="brand-logo">
        <div class="logo-icon">
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
          <div class="logo-bar"></div>
        </div>
        <div class="logo-text">METRIKA</div>
      </div>
      <div class="program-pill">
        <div class="status-dot"></div>
        {prog["label"]}
      </div>
    </div>
    <div class="header-meta">
      <div class="meta-chip">{total_slides:02d} / {total_slides:02d}</div>
    </div>
  </div>

  <div class="verdict-header-title">Kesimpulan Data & Diskusi</div>

  <div class="verdict-box">
    <div class="verdict-badge">
      <div class="status-dot"></div>
      VERDICT OBJEKTIF
    </div>
    <div class="verdict-content">{verdict_text}</div>
  </div>

  <div class="discussion-cta-box">
    <div class="cta-badge-circle">?</div>
    <div class="cta-content-text">{cta_text}</div>
  </div>

  <div class="sources-card">
    <div class="sources-header">SUMBER DATA TERVERIFIKASI</div>
    <div class="sources-entries">
      {"".join(sources_html)}
    </div>
  </div>

  <div class="progress-bar-container">
    {"".join(prog_segs)}
  </div>

  <div class="footer-text-row">
    <div>@metrika.id</div>
    <div>Data untuk kamu yang berpikir</div>
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
    Merender slide carousel 1080x1350 menggunakan Playwright (Chromium Headless).
    Menghasilkan gambar berkelas agensi dengan font Google, glassmorphism, dan ambient glow.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    prog = PROGRAMS_META.get(prog_id, PROGRAMS_META["ANGKA_BICARA"])

    slides_data = content.get("slides", [])[:4]
    total_slides = 2 + len(slides_data)  # 1 cover + N content + 1 verdict

    # Generate HTML Strings
    html_pages: List[Tuple[str, str]] = []

    # Slide 1: Cover
    html_pages.append(("slide_01", render_html_cover(content, prog, total_slides)))

    # Slides 2..N: Content
    for i, s_data in enumerate(slides_data, start=2):
        html_pages.append((f"slide_{i:02d}", render_html_slide(content, prog, s_data, i, total_slides)))

    # Slide Final: Verdict
    html_pages.append((f"slide_{total_slides:02d}", render_html_verdict(content, prog, total_slides)))

    # Simpan file HTML untuk cadangan & transparansi
    for name, page_html in html_pages:
        html_file = out_dir / f"{name}.html"
        html_file.write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []

    # Eksekusi Render Playwright
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
                # Load HTML dan tunggu font render
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
            im = Image.new("RGB", (W_IG, H_IG), (10, 14, 23))
            d = ImageDraw.Draw(im)
            d.text((100, 100), f"METRIKA • {prog['label']}\n(Silakan install Playwright)", fill=(240, 240, 240))
            im.save(fallback_img)
            out_paths.append(fallback_img)

    return out_paths


# ==============================================================================
# 3. GENERATOR VIDEO VERTIKAL (1080x1920) DENGAN SUBTITLE KARAOKE
# ==============================================================================
def words_from_edge_boundaries(boundaries: Sequence[dict]) -> List[dict]:
    """Edge-TTS WordBoundary -> [{'text', 'start', 'end'}]."""
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
    Merender video 1080x1920 yang menyematkan slide carousel resolusi tinggi di tengah
    dengan latar dinamis dan subtitle karaoke aktif di bagian bawah.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    prog = PROGRAMS_META.get(prog_id, PROGRAMS_META["ANGKA_BICARA"])

    # Dapatkan durasi audio riil
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

    # Dapatkan slide carousel yang telah dirender
    carousel_dir = out_path.parent / "carousel"
    slide_files = sorted(list(carousel_dir.glob("slide_*.png")))

    # Bangun frame video dengan Pillow lalu dipipa ke FFmpeg
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

    # Pra-load gambar slide
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
        slides_img = [Image.new("RGB", (W_V - 80, 1250), (20, 28, 45))]

    n_slides = len(slides_img)
    slide_duration = duration / n_slides

    n_frames = int(math.ceil(duration * fps))

    # Font untuk subtitle
    try:
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        sub_font = ImageFont.load_default()

    try:
        for f in range(n_frames):
            t = f / fps

            slide_idx = min(int(t // slide_duration), n_slides - 1)
            active_slide = slides_img[slide_idx]

            frame = Image.new("RGB", (W_V, H_V), (7, 9, 14))
            frame.paste(active_slide, (40, 160))

            draw = ImageDraw.Draw(frame)

            # Subtitle Box (y=1530..1770)
            sub_box = (60, 1530, W_V - 60, 1770)
            draw.rounded_rectangle(sub_box, radius=24, fill=(18, 25, 40), outline=(50, 65, 95), width=2)

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
                    fill=(250, 204, 21),
                    anchor="mm",
                )
            else:
                draw.text(
                    (W_V // 2, 1650),
                    f"{prog['label']} • @metrika.id",
                    font=sub_font,
                    fill=(148, 163, 184),
                    anchor="mm",
                )

            # Progress Bar Global Video (y=1820)
            p_width = max(10, int((W_V - 120) * (t / duration)))
            draw.rounded_rectangle((60, 1820, W_V - 60, 1828), radius=4, fill=(30, 41, 59))
            draw.rounded_rectangle((60, 1820, 60 + p_width, 1828), radius=4, fill=(250, 204, 21))

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg gagal: {err}")
    finally:
        if proc.poll() is None:
            proc.kill()

    return out_path
