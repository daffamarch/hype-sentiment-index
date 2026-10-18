"""
metrika_render.py  --  Modul render grafis METRIKA Kelas Agensi (Jurnalisme Data & Riset Finansial).

STANDAR VISUAL KELAS AGENSI DESAIN:
- 5 Slide Narrative Carousel Penuh (1080x1350 px).
- PALET COKLAT MEWAH (Luxury Espresso #1E140E, Warm Cognac Leather #8C5835, Warm Ivory Linen #FBF8F4, Toasted Kraft #E7DBCF).
- ZERO BLANK SPACE: Seluruh 1350px kanvas terisi proporsional, padat, berbobot, dan berimbang.
- SETIAP SLIDE MEMILIKI HOOK PENAHAN SCROLL (STOP-SCROLLING HOOK) DI ATAS.
- FOTO NYATA BERKUALITAS EDITORIAL DI SETIAP SLIDE (1 sampai 5).
"""
from __future__ import annotations

import base64
import html
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("metrika")

# Dimensi Standar Carousel Instagram
W_IG, H_IG = 1080, 1350

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
    """Format hook editorial: teks hitam espresso tebal dengan kata kunci MERAH CRIMSON."""
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
# CSS UTAMA: EDITORIAL PADAT, ZERO BLANK VOID (TINGGI TEPAT 1350px)
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

/* Top Brand Bar (Tinggi ~75px) */
.brand-header {{
  height: 75px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 52px;
  background-color: var(--bg);
  z-index: 10;
  flex-shrink: 0;
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

/* KONTENER SLIDE: MEMBENTANG PENUH 1275px DENGAN PADDING PRESISI */
.slide-content-wrapper {{
  height: 1275px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 4px 52px 28px 52px;
  box-sizing: border-box;
}}

.slide-main-body {{
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

/* HEADER HOOK PENAHAN SCROLL */
.slide-header-box {{
  flex-shrink: 0;
}}
.slide-eyebrow-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--brown-accent);
  margin-bottom: 6px;
}}
.slide-hook-headline {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 38px;
  font-weight: 800;
  line-height: 1.22;
  letter-spacing: -0.015em;
  color: var(--brown-dark);
}}

/* COVER SLIDE 1 */
.cover-top-box {{
  padding: 4px 52px 20px 52px;
  background-color: var(--bg);
  z-index: 10;
  flex-shrink: 0;
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
  height: 220px;
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

/* SLIDE 2: KONTEKS FAKTA LAPANGAN (PADAT PENUH) */
.slide2-media-card {{
  width: 100%;
  height: 390px;
  border-radius: 20px;
  overflow: hidden;
  position: relative;
  background-color: var(--brown-dark);
  border: 1.5px solid var(--border);
  box-shadow: 0 8px 24px rgba(43, 26, 18, 0.08);
  flex-shrink: 0;
}}
.slide2-media-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide2-media-badge {{
  position: absolute;
  top: 18px;
  left: 20px;
  background: rgba(27, 17, 12, 0.90);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(231, 219, 207, 0.4);
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #FAF6F0;
}}
.slide2-context-points {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.slide2-point-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-left: 5px solid var(--brown-accent);
  border-radius: 16px;
  padding: 18px 22px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.03);
}}
.slide2-point-num {{
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--brown-light);
  border: 1.5px solid var(--brown-accent);
  color: var(--brown-accent);
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.slide2-point-text {{
  font-size: 16px;
  font-weight: 500;
  line-height: 1.48;
  color: var(--text-main);
}}
.slide2-point-text b {{
  font-weight: 800;
  color: var(--brown-dark);
}}
.slide2-takeaway-pill {{
  background: var(--brown-light);
  border: 1.5px solid var(--border);
  border-radius: 14px;
  padding: 14px 20px;
  font-size: 14px;
  font-weight: 700;
  color: var(--brown-dark);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}}

/* SLIDE 3: BEDAH DATA (PADAT PENUH) */
.slide3-split-metric-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 20px;
  overflow: hidden;
  display: flex;
  height: 250px;
  box-shadow: 0 6px 20px rgba(43, 26, 18, 0.05);
  flex-shrink: 0;
}}
.slide3-img-pane {{
  width: 400px;
  height: 100%;
  position: relative;
  background-color: var(--brown-dark);
  border-right: 1.5px solid var(--border);
  flex-shrink: 0;
}}
.slide3-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide3-metric-pane {{
  flex: 1;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #FFFFFF;
  border-left: 5px solid var(--brown-accent);
}}
.slide3-metric-val {{
  font-family: 'Outfit', sans-serif;
  font-size: 52px;
  font-weight: 900;
  color: var(--brown-accent);
  line-height: 1.1;
  margin-bottom: 8px;
}}
.slide3-metric-lbl {{
  font-size: 17px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
}}
.slide3-dual-columns {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}}
.slide3-column-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 22px 22px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
  min-height: 380px;
}}
.slide3-column-header {{
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brown-accent);
  padding-bottom: 10px;
  border-bottom: 1.5px solid var(--line);
  margin-bottom: 14px;
}}
.slide3-points-list {{
  display: flex;
  flex-direction: column;
  gap: 14px;
}}
.slide3-point-item {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 15px;
  line-height: 1.48;
  color: var(--text-main);
}}
.slide3-bullet {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brown-accent);
  margin-top: 7px;
  flex-shrink: 0;
}}
.slide3-column-footer {{
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  display: flex;
  justify-content: space-between;
}}
.slide3-alert-banner {{
  background: #FEF2F2;
  border: 1.5px solid rgba(185, 28, 28, 0.3);
  border-radius: 14px;
  padding: 14px 20px;
  font-size: 14px;
  font-weight: 700;
  color: var(--red);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}}

/* SLIDE 4: SKENARIO STRATEGIS (PADAT PENUH) */
.slide4-media-card {{
  width: 100%;
  height: 330px;
  border-radius: 20px;
  overflow: hidden;
  position: relative;
  background-color: var(--brown-dark);
  border: 1.5px solid var(--border);
  box-shadow: 0 6px 18px rgba(43, 26, 18, 0.06);
  flex-shrink: 0;
}}
.slide4-media-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide4-media-badge {{
  position: absolute;
  top: 18px;
  left: 20px;
  background: rgba(27, 17, 12, 0.90);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(231, 219, 207, 0.4);
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #FAF6F0;
}}
.slide4-scenarios-container {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.slide4-scenario-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-left: 5px solid var(--brown-accent);
  border-radius: 16px;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.03);
}}
.slide4-scenario-tag {{
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brown-accent);
}}
.slide4-scenario-body {{
  font-size: 15px;
  line-height: 1.48;
  color: var(--text-main);
}}
.slide4-takeaway-bar {{
  background: var(--brown-light);
  border: 1.5px solid var(--border);
  border-radius: 14px;
  padding: 14px 20px;
  font-size: 14px;
  font-weight: 700;
  color: var(--brown-dark);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}}

/* SLIDE 5: VERDICT REDAKSI & DISKUSI (PADAT PENUH DENGAN HIGHLIGHTS BOX) */
.slide5-verdict-banner {{
  width: 100%;
  height: 400px;
  border-radius: 20px;
  overflow: hidden;
  position: relative;
  background-color: var(--brown-dark);
  border: 1.5px solid var(--border);
  box-shadow: 0 8px 24px rgba(43, 26, 18, 0.08);
  flex-shrink: 0;
}}
.slide5-verdict-img {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}
.slide5-verdict-overlay {{
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(32, 20, 14, 0.96) 0%, rgba(43, 26, 18, 0.75) 55%, rgba(43, 26, 18, 0.40) 100%);
  padding: 36px 40px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}}
.slide5-verdict-tag {{
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #E2B792;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}}
.slide5-verdict-quote {{
  font-size: 26px;
  font-weight: 800;
  line-height: 1.42;
  color: #FAF6F0;
}}

.slide5-highlights-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.03);
}}
.slide5-highlight-title {{
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--brown-accent);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}}
.slide5-highlight-item {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.4;
}}
.slide5-highlight-check {{
  color: var(--brown-accent);
  font-weight: 900;
}}

.cta-discussion-card {{
  background: #FFFFFF;
  border: 1.5px solid var(--border);
  border-radius: 18px;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  gap: 18px;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
  flex-shrink: 0;
}}
.cta-badge-icon {{
  width: 50px;
  height: 50px;
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
  font-size: 17px;
  font-weight: 700;
  line-height: 1.38;
  color: var(--brown-dark);
}}

.verified-sources-card {{
  background: var(--brown-light);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 20px;
  flex-shrink: 0;
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
  padding: 5px 14px;
  font-size: 12px;
  font-weight: 700;
  color: var(--brown-dark);
}}

/* Global Footer & Progress Bar (Tinggi ~60px) */
.slide-bottom-bar {{
  flex-shrink: 0;
  margin-top: 14px;
}}
.carousel-progress-bar {{
  display: flex;
  gap: 8px;
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


# ==============================================================================
# RENDERER SLIDE 1: COVER
# ==============================================================================
def render_html_cover(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
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


# ==============================================================================
# RENDERER SLIDE 2: KONTEKS FAKTA LAPANGAN
# ==============================================================================
def render_html_context(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s2 = content.get("slide_context", {})
    eyebrow = html.escape(s2.get("eyebrow", "01 / DOKUMENTASI FAKTA"))
    hook = html.escape(s2.get("hook", "Kenapa Masalah Ini Tiba-tiba Meledak di Lapangan?"))
    points = s2.get("points", [])
    takeaway = html.escape(s2.get("takeaway", "Fenomena ini bukan sekadar antrean fisik, tapi sinyal disrupsi distribusi yang merugikan publik."))

    img_uri = get_image_data_uri(content.get("slide2_image") or content.get("hero_image"))

    points_html = []
    for i, pt in enumerate(points[:3], start=1):
        formatted_pt = format_point_body_html(pt)
        points_html.append(f"""
        <div class="slide2-point-card">
          <div class="slide2-point-num">{i:02d}</div>
          <div class="slide2-point-text">{formatted_pt}</div>
        </div>
        """)

    prog_bars = "".join(
        f'<div class="progress-segment-item {"active" if idx < 2 else ""}"></div>'
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
    <div class="program-chip">02 / {total_slides:02d}</div>
  </div>

  <div class="slide-content-wrapper">
    <div class="slide-main-body">
      <div class="slide-header-box">
        <div class="slide-eyebrow-pill">{eyebrow}</div>
        <h2 class="slide-hook-headline">{hook}</h2>
      </div>

      <div class="slide2-media-card">
        <img src="{img_uri}" class="slide2-media-img" alt="Dokumentasi Fakta Lapangan" />
        <div class="slide2-media-badge">DOKUMENTASI FAKTA LAPANGAN</div>
      </div>

      <div class="slide2-context-points">
        {"".join(points_html)}
      </div>

      <div class="slide2-takeaway-pill">
        <span>⚡</span>
        <span><b>FAKTA KUNCI:</b> {takeaway}</span>
      </div>
    </div>

    <div class="slide-bottom-bar">
      <div class="carousel-progress-bar">
        {prog_bars}
      </div>
      <div class="editorial-footer">
        <div>@metrika.id</div>
        <div>Geser ke kanan untuk melihat rincian angka →</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# RENDERER SLIDE 3: BEDAH DATA & IMPLIKASI
# ==============================================================================
def render_html_metric(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s3 = content.get("slide_metric", {})
    eyebrow = html.escape(s3.get("eyebrow", "02 / BEDAH DATA RISET"))
    hook = html.escape(s3.get("hook", "Berapa Triliun Rupiah yang Diam-diam Disedot dari Kantong Kita?"))
    m_val = html.escape(str(s3.get("metric_value", "Rp 150 T+")))
    m_lbl = html.escape(str(s3.get("metric_label", "estimasi alokasi anggaran energi yang rentan bocor")))

    img_uri = get_image_data_uri(content.get("slide3_image") or content.get("hero_image"))

    col1_title = html.escape(s3.get("col1_title", "Beban Dompet Konsumen Ritel"))
    col1_points = s3.get("col1_points", [])
    col1_html = "".join(f'<div class="slide3-point-item"><div class="slide3-bullet"></div><div>{format_point_body_html(p)}</div></div>' for p in col1_points[:3])

    col2_title = html.escape(s3.get("col2_title", "Beban Sektor Usaha & Industri"))
    col2_points = s3.get("col2_points", [])
    col2_html = "".join(f'<div class="slide3-point-item"><div class="slide3-bullet"></div><div>{format_point_body_html(p)}</div></div>' for p in col2_points[:3])

    alert_text = html.escape(s3.get("alert_text", "Setiap liter subsidi yang salah sasaran adalah hak rakyat kecil yang terampas."))

    prog_bars = "".join(
        f'<div class="progress-segment-item {"active" if idx < 3 else ""}"></div>'
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
    <div class="program-chip">03 / {total_slides:02d}</div>
  </div>

  <div class="slide-content-wrapper">
    <div class="slide-main-body">
      <div class="slide-header-box">
        <div class="slide-eyebrow-pill">{eyebrow}</div>
        <h2 class="slide-hook-headline">{hook}</h2>
      </div>

      <div class="slide3-split-metric-card">
        <div class="slide3-img-pane">
          <img src="{img_uri}" class="slide3-img" alt="Visual Analisis Data" />
        </div>
        <div class="slide3-metric-pane">
          <div class="slide3-metric-val">{m_val}</div>
          <div class="slide3-metric-lbl">{m_lbl}</div>
        </div>
      </div>

      <div class="slide3-dual-columns">
        <div class="slide3-column-card">
          <div>
            <div class="slide3-column-header">{col1_title}</div>
            <div class="slide3-points-list">
              {col1_html}
            </div>
          </div>
          <div class="slide3-column-footer">
            <span>METRIKA DATA AUDIT</span>
            <span>BEBAN RITEL</span>
          </div>
        </div>
        <div class="slide3-column-card">
          <div>
            <div class="slide3-column-header">{col2_title}</div>
            <div class="slide3-points-list">
              {col2_html}
            </div>
          </div>
          <div class="slide3-column-footer">
            <span>METRIKA DATA AUDIT</span>
            <span>BEBAN INDUSTRI</span>
          </div>
        </div>
      </div>

      <div class="slide3-alert-banner">
        <span>⚠️</span>
        <span><b>CATATAN AUDIT:</b> {alert_text}</span>
      </div>
    </div>

    <div class="slide-bottom-bar">
      <div class="carousel-progress-bar">
        {prog_bars}
      </div>
      <div class="editorial-footer">
        <div>@metrika.id</div>
        <div>Geser untuk strategi eksekusi →</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# RENDERER SLIDE 4: SKENARIO STRATEGIS (ACTIONABLE PLAYBOOK)
# ==============================================================================
def render_html_strategy(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s4 = content.get("slide_strategy", {})
    eyebrow = html.escape(s4.get("eyebrow", "03 / SKENARIO STRATEGIS"))
    hook = html.escape(s4.get("hook", "Tiga Benteng Finansial Sebelum Subsidi Makin Mengetat"))
    scenarios = s4.get("scenarios", [])
    takeaway = html.escape(s4.get("takeaway", "Subsidi energi boleh menyusut, tapi strategi efisiensi biaya hidupmu tidak boleh ikut lumpuh."))

    img_uri = get_image_data_uri(content.get("slide4_image") or content.get("hero_image"))

    scenarios_html = []
    for sc in scenarios[:3]:
        tag = html.escape(sc.get("tag", "SKENARIO"))
        body = format_point_body_html(sc.get("text", ""))
        scenarios_html.append(f"""
        <div class="slide4-scenario-card">
          <div class="slide4-scenario-tag">{tag}</div>
          <div class="slide4-scenario-body">{body}</div>
        </div>
        """)

    prog_bars = "".join(
        f'<div class="progress-segment-item {"active" if idx < 4 else ""}"></div>'
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
    <div class="program-chip">04 / {total_slides:02d}</div>
  </div>

  <div class="slide-content-wrapper">
    <div class="slide-main-body">
      <div class="slide-header-box">
        <div class="slide-eyebrow-pill">{eyebrow}</div>
        <h2 class="slide-hook-headline">{hook}</h2>
      </div>

      <div class="slide4-media-card">
        <img src="{img_uri}" class="slide4-media-img" alt="Visual Strategi" />
        <div class="slide4-media-badge">PANDUAN MITIGASI RISIKO</div>
      </div>

      <div class="slide4-scenarios-container">
        {"".join(scenarios_html)}
      </div>

      <div class="slide4-takeaway-bar">
        <span>💡</span>
        <span><b>PRINSIP UTAMA:</b> {takeaway}</span>
      </div>
    </div>

    <div class="slide-bottom-bar">
      <div class="carousel-progress-bar">
        {prog_bars}
      </div>
      <div class="editorial-footer">
        <div>@metrika.id</div>
        <div>Geser untuk kesimpulan akhir & diskusi →</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# RENDERER SLIDE 5: VERDICT REDAKSI & RUANG DISKUSI (DENGAN HIGHLIGHTS BOX)
# ==============================================================================
def render_html_verdict(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    verdict_text = html.escape(content.get("verdict", ""))
    cta_text = html.escape(content.get("cta", ""))
    sources = content.get("sources", [])
    highlights = content.get("slide5_highlights", [
        "Antrean panjang membuktikan kegagalan tata kelola distribusi, bukan kelangkaan pasokan.",
        "Pemilik kendaraan mewah wajib beralih ke BBM non-subsidi demi keadilan sosial.",
        "Kunci pengawasan ada pada digitalisasi transaksi dan penegakan sanksi tegas di SPBU."
    ])

    img_uri = get_image_data_uri(content.get("slide5_image") or content.get("hero_image"))

    sources_html = []
    for s in sources:
        clean_s = html.escape(s)
        sources_html.append(f'<div class="source-pill">{clean_s}</div>')

    highlights_html = []
    for h in highlights[:3]:
        highlights_html.append(f"""
        <div class="slide5-highlight-item">
          <span class="slide5-highlight-check">✓</span>
          <span>{html.escape(h)}</span>
        </div>
        """)

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
    <div class="program-chip">05 / {total_slides:02d}</div>
  </div>

  <div class="slide-content-wrapper">
    <div class="slide-main-body">
      <div class="slide-header-box">
        <div class="slide-eyebrow-pill">04 / KESIMPULAN RISET</div>
        <h2 class="slide-hook-headline">Verdict Riset & Ruang Diskusi Terbuka</h2>
      </div>

      <div class="slide5-verdict-banner">
        <img src="{img_uri}" class="slide5-verdict-img" alt="Verdict Visual" />
        <div class="slide5-verdict-overlay">
          <div class="slide5-verdict-tag">
            <span>⚖️</span>
            <span>VERDICT OBJEKTIF REDAKSI METRIKA</span>
          </div>
          <div class="slide5-verdict-quote">{verdict_text}</div>
        </div>
      </div>

      <div class="slide5-highlights-card">
        <div class="slide5-highlight-title">TIGA POIN INVESTIGASI UTAMA</div>
        {"".join(highlights_html)}
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
    </div>

    <div class="slide-bottom-bar">
      <div class="carousel-progress-bar">
        {prog_bars}
      </div>
      <div class="editorial-footer">
        <div>@metrika.id</div>
        <div>Data Bicara. Kamu yang Menilai.</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# RENDERER ENGINE: PLAYWRIGHT HEADLESS CHROMIUM (5 SLIDES)
# ==============================================================================
def render_carousel_slides(
    content: Dict[str, Any], out_dir: str | Path, fmt: str = "PNG"
) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prog_id = content.get("program", "ANGKA_BICARA")
    theme = PROGRAMS_THEME.get(prog_id, PROGRAMS_THEME["ANGKA_BICARA"])
    total_slides = 5

    html_pages: List[Tuple[str, str]] = [
        ("slide_01", render_html_cover(content, theme, total_slides)),
        ("slide_02", render_html_context(content, theme, total_slides)),
        ("slide_03", render_html_metric(content, theme, total_slides)),
        ("slide_04", render_html_strategy(content, theme, total_slides)),
        ("slide_05", render_html_verdict(content, theme, total_slides)),
    ]

    for name, page_html in html_pages:
        html_file = out_dir / f"{name}.html"
        html_file.write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []

    try:
        from playwright.sync_api import sync_playwright

        print("[Playwright] Memulai Chromium headless untuk render 5 Slide Carousel (Agency Grade Padat)...")
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


def render_vertical_video(*args, **kwargs) -> Path:
    return Path("disabled_video.mp4")

def words_from_edge_boundaries(boundaries: Sequence[dict]) -> List[dict]:
    return []
