"""
metrika_render.py  --  Modul render grafis METRIKA (Jurnalisme Data & Riset Finansial).

STANDAR VISUAL:
- 5 slide carousel Instagram (1080x1350 px), setiap slide memakai FOTO NYATA.
- Palet coklat mewah: Espresso #1E140E, Cognac #8C5835, Ivory #FBF8F4, Kraft #E7DBCF, Crimson #B91C1C.
- 0% emoji: semua teks dibersihkan dari emoji; aksen memakai badge teks murni.
- Teks besar dan terbaca di layar HP; kanvas 1350 px terisi penuh (flex-fill).
- Auto-fit: jika konten melampaui kanvas, foto/teks dikecilkan bertahap (dengan batas bawah)
  sehingga tidak ada teks terpotong.
"""
from __future__ import annotations

import base64
import html
import io
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageOps

log = logging.getLogger("metrika")

W_IG, H_IG = 1080, 1350

# ==============================================================================
# PALET: LUXURY ESPRESSO & WARM LEATHER
# ==============================================================================
COLOR_BG = "#FBF8F4"            # Warm Ivory Linen (kanvas)
COLOR_CARD = "#FFFFFF"          # Kartu putih bersih
COLOR_TEXT_MAIN = "#1E140E"     # Deep Roasted Espresso (teks utama)
COLOR_TEXT_MUTED = "#6B584B"    # Warm Mocha Taupe
COLOR_BROWN_DARK = "#2B1A12"    # Dark Mahogany
COLOR_BROWN_ACCENT = "#8C5835"  # Warm Cognac Leather (aksen utama)
COLOR_BROWN_LIGHT = "#F3EBE1"   # Soft Kraft tint
COLOR_RED = "#B91C1C"           # Crimson (aksen kritis)
COLOR_BORDER = "#E7DBCF"        # Toasted Kraft border
COLOR_LINE = "#EFE4D8"          # Separator

PROGRAMS_THEME = {
    "INDEKS_KERINGAT": {"label": "INDEKS KERINGAT", "tag": "KALKULATOR DAYA BELI & JAM KERJA"},
    "RADAR_SENTIMEN": {"label": "RADAR SENTIMEN", "tag": "PETA POLARISASI OPINI PUBLIK"},
    "ANGKA_BICARA": {"label": "ANGKA BICARA", "tag": "DATA STORYTELLING & FINANSIAL"},
}

# ==============================================================================
# SANITASI TEKS: HAPUS EMOJI TOTAL
# ==============================================================================
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoji & piktograf
    "\U00002600-\U000027BF"   # simbol & dingbat
    "\U00002B00-\U00002BFF"   # panah & simbol tambahan
    "\U00002190-\U000021FF"   # panah
    "\U00002300-\U000023FF"   # teknis (jam, dll)
    "\U0000FE00-\U0000FE0F"   # variation selector
    "\U0000200D"              # zero width joiner
    "\U000020E3"              # keycap
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: Any) -> str:
    """Hapus semua emoji/piktograf dari teks, rapikan spasi ganda."""
    s = EMOJI_RE.sub("", "" if text is None else str(text))
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def strip_emoji_deep(obj: Any) -> Any:
    """Bersihkan emoji secara rekursif dari dict/list/str hasil AI."""
    if isinstance(obj, str):
        return strip_emoji(obj)
    if isinstance(obj, list):
        return [strip_emoji_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_emoji_deep(v) for k, v in obj.items()}
    return obj


def esc(text: Any) -> str:
    """Escape HTML + hapus emoji."""
    return html.escape(strip_emoji(text))


def bold_html(text: Any) -> str:
    """Konversi **teks** menjadi <b>teks</b> (setelah escape)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(text))


LEAD_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*(.*)$", re.S)


def split_lead_in(text: Any) -> Tuple[str, str]:
    """Pisahkan '**Judul:** isi' menjadi (judul, isi)."""
    t = strip_emoji(text)
    m = LEAD_RE.match(t)
    if not m:
        return "", t
    title = m.group(1).strip().rstrip(":").strip()
    body = m.group(2).lstrip(":").strip()
    if not body:
        return "", title
    return title, body


def format_hook_html(hook_text: str) -> str:
    """Hook editorial: teks espresso tebal dengan kata kunci MERAH CRIMSON."""
    clean = html.escape(strip_emoji(hook_text))
    clean = clean.replace("&lt;red&gt;", "<red>").replace("&lt;/red&gt;", "</red>")
    clean = clean.replace("&lt;highlight&gt;", "<red>").replace("&lt;/highlight&gt;", "</red>")

    if "<red>" in clean and "</red>" in clean:
        return re.sub(r"<red>(.*?)</red>", r'<span class="text-red">\1</span>', clean)
    if "**" in clean:
        return re.sub(r"\*\*(.*?)\*\*", r'<span class="text-red">\1</span>', clean)

    if "?" in clean:
        parts = clean.split("?")
        q_words = parts[0].strip().split()
        if len(q_words) > 3:
            first = " ".join(q_words[:-3])
            hl = " ".join(q_words[-3:]) + "?"
            after = "?".join(parts[1:]).strip()
            return f'{first} <span class="text-red">{hl}</span> {after}'.strip()

    words = clean.split()
    if len(words) >= 4:
        start = max(1, len(words) // 4)
        end = min(len(words), start + max(2, len(words) // 2))
        out = []
        if words[:start]:
            out.append(" ".join(words[:start]))
        out.append(f'<span class="text-red">{" ".join(words[start:end])}</span>')
        if words[end:]:
            out.append(" ".join(words[end:]))
        return " ".join(out)
    return f'<span class="text-red">{clean}</span>'


# ==============================================================================
# GAMBAR
# ==============================================================================
def get_image_data_uri(img_path: Optional[str | Path], max_w: int = 1600) -> Optional[str]:
    """Baca foto lokal, normalisasi (EXIF, RGB, maks lebar 1600), kembalikan Base64 Data URI."""
    if not img_path:
        return None
    p = Path(img_path)
    if not p.exists() or p.stat().st_size < 1000:
        return None
    try:
        im = Image.open(p)
        im = ImageOps.exif_transpose(im).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as err:
        log.warning(f"Gagal memproses gambar {img_path}: {err}")
        return None


def photo_html(uri: Optional[str], css_class: str, alt: str) -> str:
    """Tag <img> foto nyata. Jika file hilang, tampilkan blok coklat (bukan layar kosong)."""
    if uri:
        return f'<img src="{uri}" class="{css_class}" alt="{esc(alt)}" />'
    return (
        f'<div class="{css_class}" style="background:linear-gradient(135deg,#2B1A12 0%,#4A2F20 100%);"></div>'
    )


# ==============================================================================
# CSS
# ==============================================================================
def _root_css() -> str:
    return f""":root {{
  --bg: {COLOR_BG};
  --card: {COLOR_CARD};
  --text-main: {COLOR_TEXT_MAIN};
  --text-muted: {COLOR_TEXT_MUTED};
  --brown-dark: {COLOR_BROWN_DARK};
  --brown-accent: {COLOR_BROWN_ACCENT};
  --brown-light: {COLOR_BROWN_LIGHT};
  --border: {COLOR_BORDER};
  --line: {COLOR_LINE};
  --red: {COLOR_RED};
  --cover-fs: 52px;
  --hook-fs: 46px;
  --title-fs: 25px;
  --body-fs: 21px;
  --metric-fs: 68px;
  --photo-h: 380px;
  --col-min: 440px;
}}
"""


_BASE_CSS = r"""
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-font-smoothing: antialiased; }
html, body { width: 1080px; height: 1350px; }
body {
  overflow: hidden;
  background: var(--bg);
  font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', Arial, sans-serif;
  color: var(--text-main);
  display: flex;
  flex-direction: column;
  position: relative;
}
.text-red { color: var(--red) !important; font-weight: 900 !important; }

/* ---------- Brand header (75px) ---------- */
.brand-header {
  height: 75px; flex-shrink: 0;
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 52px; background: var(--bg);
}
.brand-left { display: flex; align-items: center; gap: 14px; }
.brand-monogram {
  width: 44px; height: 44px; background: var(--brown-dark);
  border: 1.5px solid var(--brown-accent); border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #FAF6F0; font-family: 'Outfit', sans-serif; font-size: 26px; font-weight: 900;
}
.brand-title-wrap { display: flex; flex-direction: column; }
.brand-title { font-size: 21px; font-weight: 900; letter-spacing: -0.01em; color: var(--brown-dark); line-height: 1.1; }
.brand-tagline { font-size: 12px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: var(--brown-accent); }
.program-chip {
  padding: 7px 18px; background: #FFFFFF; border: 1px solid var(--border); border-radius: 6px;
  font-size: 14px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted);
}

/* ---------- Wrapper konten (1275px) ---------- */
.slide-content-wrapper {
  height: 1275px; display: flex; flex-direction: column;
  padding: 4px 52px 28px 52px;
}
.slide-main-body {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex; flex-direction: column; gap: 14px;
}
.slide-header-box { flex-shrink: 0; }
.slide-eyebrow-pill {
  font-size: 15px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--brown-accent); margin-bottom: 6px;
}
.slide-hook-headline {
  font-size: var(--hook-fs); font-weight: 800; line-height: 1.18;
  letter-spacing: -0.015em; color: var(--brown-dark);
}

/* ---------- Photo card (dipakai slide 2, 4, 5) ---------- */
.photo-card {
  width: 100%; height: var(--photo-h); flex-shrink: 0;
  border-radius: 20px; overflow: hidden; position: relative;
  background: var(--brown-dark); border: 1.5px solid var(--border);
  box-shadow: 0 8px 24px rgba(43, 26, 18, 0.08);
}
.photo-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.photo-badge {
  position: absolute; top: 18px; left: 20px;
  background: rgba(27, 17, 12, 0.90); border: 1px solid rgba(231, 219, 207, 0.4);
  padding: 7px 14px; border-radius: 6px;
  font-size: 14px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: #FAF6F0;
}

/* ---------- Kartu info (slide 2) ---------- */
.card-stack { flex: 1; display: flex; flex-direction: column; gap: 14px; }
.info-card {
  flex: 1; background: #FFFFFF; border: 1.5px solid var(--border);
  border-left: 6px solid var(--brown-accent); border-radius: 16px;
  padding: 22px 24px; display: flex; align-items: center; gap: 18px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.04);
}
.num-badge {
  width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0;
  background: var(--brown-light); border: 1.5px solid var(--brown-accent); color: var(--brown-accent);
  font-family: 'Outfit', sans-serif; font-size: 18px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
}
.card-title { font-size: var(--title-fs); font-weight: 800; line-height: 1.25; color: var(--brown-dark); margin-bottom: 6px; }
.card-body { font-size: var(--body-fs); font-weight: 500; line-height: 1.45; color: var(--text-main); }
.card-body b { font-weight: 800; color: var(--brown-dark); }

/* ---------- Status bar (fakta kunci / catatan audit / prinsip utama) ---------- */
.status-bar {
  flex-shrink: 0; background: var(--brown-light); border: 1.5px solid var(--border);
  border-radius: 14px; padding: 16px 22px;
  display: flex; align-items: center; gap: 16px;
}
.status-bar.red { background: #FEF2F2; border-color: rgba(185, 28, 28, 0.35); }
.badge-tag {
  flex-shrink: 0; font-size: 15px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--brown-accent); white-space: nowrap;
}
.status-bar.red .badge-tag { color: var(--red); }
.status-text { font-size: 19px; font-weight: 600; line-height: 1.4; color: var(--brown-dark); }
.status-bar.red .status-text { color: #7F1D1D; }

/* ---------- Slide 1: Cover ---------- */
.cover-top-box { padding: 4px 52px 22px 52px; flex-shrink: 0; background: var(--bg); }
.cover-headline {
  font-size: var(--cover-fs); font-weight: 800; line-height: 1.18;
  letter-spacing: -0.02em; color: var(--brown-dark); margin-bottom: 18px;
}
.stat-pill {
  display: inline-flex; align-items: center; gap: 18px; max-width: 100%;
  background: #FFFFFF; border: 1.5px solid var(--border); border-left: 6px solid var(--brown-accent);
  border-radius: 18px; padding: 12px 26px; box-shadow: 0 4px 12px rgba(43, 26, 18, 0.05);
}
.stat-num { font-family: 'Outfit', sans-serif; font-size: 40px; font-weight: 900; color: var(--brown-accent); white-space: nowrap; }
.stat-lbl { font-size: 18px; font-weight: 700; line-height: 1.3; color: var(--text-main); }
.cover-photo-wrapper {
  flex: 1; min-height: 0; width: 100%; position: relative; overflow: hidden;
  background: var(--brown-dark); border-top: 2px solid var(--border);
}
.cover-photo { width: 100%; height: 100%; object-fit: cover; object-position: center 30%; display: block; }
.photo-gradient-overlay {
  position: absolute; left: 0; right: 0; bottom: 0; height: 230px; padding: 30px 52px;
  background: linear-gradient(to top, rgba(27, 17, 12, 0.95) 0%, rgba(35, 22, 15, 0.55) 60%, transparent 100%);
  display: flex; align-items: flex-end; justify-content: space-between;
}
.swipe-prompt { display: flex; align-items: center; gap: 14px; color: #FAF6F0; font-size: 20px; font-weight: 800; }
.swipe-chip {
  background: var(--brown-accent); color: #FFFFFF; padding: 8px 16px; border-radius: 6px;
  font-size: 15px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase;
}
.photo-credit { text-align: right; color: rgba(250, 246, 240, 0.8); font-size: 14px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; line-height: 1.5; }

/* ---------- Slide 3: Bedah data ---------- */
.split-metric-card {
  flex-shrink: 0; height: var(--photo-h); display: flex; overflow: hidden;
  background: #FFFFFF; border: 1.5px solid var(--border); border-radius: 20px;
  box-shadow: 0 6px 20px rgba(43, 26, 18, 0.05);
}
.split-img-pane { width: 400px; height: 100%; flex-shrink: 0; background: var(--brown-dark); border-right: 1.5px solid var(--border); }
.split-metric-pane {
  flex: 1; min-width: 0; padding: 22px 30px; display: flex; flex-direction: column; justify-content: center;
  border-left: 6px solid var(--brown-accent); margin-left: -6px;
}
.metric-kicker { font-size: 14px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: var(--red); margin-bottom: 6px; }
.metric-val {
  font-family: 'Outfit', sans-serif; font-size: var(--metric-fs); font-weight: 900;
  color: var(--brown-accent); line-height: 1.05; margin-bottom: 10px; white-space: nowrap;
}
.metric-lbl { font-size: 19px; font-weight: 700; line-height: 1.35; color: var(--text-main); }
.dual-columns { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 18px; min-height: var(--col-min); }
.column-card {
  background: #FFFFFF; border: 1.5px solid var(--border); border-radius: 18px; padding: 22px;
  display: flex; flex-direction: column; justify-content: space-between;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
}
.column-header {
  font-size: 16px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: var(--brown-accent);
  padding-bottom: 12px; border-bottom: 1.5px solid var(--line); margin-bottom: 16px; line-height: 1.3;
}
.column-body { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.points-list { flex: 1; display: flex; flex-direction: column; justify-content: space-evenly; gap: 14px; }
.point-item { display: flex; align-items: flex-start; gap: 12px; font-size: var(--body-fs); font-weight: 500; line-height: 1.45; color: var(--text-main); }
.point-item + .point-item { border-top: 1px solid var(--line); padding-top: 16px; }
.point-item b { font-weight: 800; color: var(--brown-dark); }
.bullet { width: 10px; height: 10px; border-radius: 50%; background: var(--brown-accent); margin-top: 10px; flex-shrink: 0; }
.column-footer {
  margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line);
  font-size: 13px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted);
  display: flex; justify-content: space-between;
}

/* ---------- Slide 4: Skenario ---------- */
.scenario-stack { flex: 1; display: flex; flex-direction: column; gap: 14px; }
.scenario-card {
  flex: 1; background: #FFFFFF; border: 1.5px solid var(--border); border-left: 6px solid var(--brown-accent);
  border-radius: 16px; padding: 22px 24px; display: flex; flex-direction: column; justify-content: center; gap: 8px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.04);
}
.scenario-tag { font-size: 15px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: var(--brown-accent); }
.scenario-body { font-size: var(--body-fs); font-weight: 500; line-height: 1.45; color: var(--text-main); }
.scenario-body b { font-weight: 800; color: var(--brown-dark); }

/* ---------- Slide 5: Verdict ---------- */
.verdict-overlay {
  position: absolute; inset: 0; padding: 32px 40px; display: flex; flex-direction: column; justify-content: flex-end;
  background: linear-gradient(to top, rgba(32, 20, 14, 0.96) 0%, rgba(43, 26, 18, 0.78) 55%, rgba(43, 26, 18, 0.38) 100%);
}
.verdict-tag { font-size: 15px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: #E2B792; margin-bottom: 12px; }
.verdict-quote { font-size: 27px; font-weight: 800; line-height: 1.38; color: #FAF6F0; }
.highlights-card {
  flex: 1; display: flex; flex-direction: column; background: #FFFFFF;
  border: 1.5px solid var(--border); border-radius: 18px; padding: 22px 26px;
  box-shadow: 0 4px 12px rgba(43, 26, 18, 0.04);
}
.highlights-title {
  font-size: 16px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; color: var(--brown-accent);
  padding-bottom: 12px; border-bottom: 1.5px solid var(--line);
}
.highlights-list { flex: 1; display: flex; flex-direction: column; justify-content: space-evenly; }
.highlight-item { display: flex; align-items: center; gap: 16px; padding: 10px 0; font-size: var(--body-fs); font-weight: 600; line-height: 1.42; color: var(--text-main); }
.highlight-item + .highlight-item { border-top: 1px solid var(--line); }
.highlight-num {
  width: 38px; height: 38px; flex-shrink: 0; border-radius: 8px; background: var(--brown-dark); color: #FAF6F0;
  font-family: 'Outfit', sans-serif; font-size: 18px; font-weight: 900; display: flex; align-items: center; justify-content: center;
}
.cta-card {
  flex-shrink: 0; display: flex; align-items: center; gap: 20px; background: #FFFFFF;
  border: 1.5px solid var(--border); border-left: 6px solid var(--red); border-radius: 18px; padding: 20px 24px;
  box-shadow: 0 4px 16px rgba(43, 26, 18, 0.04);
}
.cta-badge {
  width: 56px; height: 56px; border-radius: 50%; flex-shrink: 0; background: var(--brown-accent); color: #FFFFFF;
  font-family: 'Outfit', sans-serif; font-size: 30px; font-weight: 900; display: flex; align-items: center; justify-content: center;
}
.cta-text { font-size: 22px; font-weight: 700; line-height: 1.38; color: var(--brown-dark); }
.sources-card { flex-shrink: 0; background: var(--brown-light); border: 1px solid var(--border); border-radius: 14px; padding: 14px 20px; }
.sources-title { font-size: 14px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }
.sources-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.source-pill { background: #FFFFFF; border: 1px solid var(--border); border-radius: 6px; padding: 6px 14px; font-size: 14px; font-weight: 700; color: var(--brown-dark); }

/* ---------- Bottom bar ---------- */
.slide-bottom-bar { flex-shrink: 0; margin-top: 14px; }
.carousel-progress-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.progress-segment-item { flex: 1; height: 5px; border-radius: 3px; background: var(--border); }
.progress-segment-item.active { background: var(--brown-accent); }
.editorial-footer { display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 700; color: var(--text-muted); }
"""


def get_base_css() -> str:
    return _root_css() + _BASE_CSS


FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900'
    '&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">'
)

# Auto-fit: bila konten melampaui kanvas, kecilkan foto -> teks secara bertahap (dengan batas bawah).
FIT_JS = r"""
(function(){
  var root = document.documentElement;
  function cur(v){ return parseFloat(getComputedStyle(root).getPropertyValue(v)); }
  function put(v, n){ root.style.setProperty(v, n + 'px'); }
  var STEPS = [['--photo-h',0.80,6],['--col-min',0.85,10],['--body-fs',0.93,0.5],['--title-fs',0.92,0.5],['--hook-fs',0.92,0.5]];
  var base = {};
  function over(){ var b = document.querySelector('.slide-main-body'); return b ? b.scrollHeight - b.clientHeight : 0; }
  function fitCover(){
    var h = document.querySelector('.cover-headline'); if(!h) return false;
    var g = 0;
    while(h.offsetHeight > 312 && cur('--cover-fs') > 44 && g++ < 30){ put('--cover-fs', cur('--cover-fs') - 1); }
    return true;
  }
  function fitMetric(){
    var m = document.querySelector('.metric-val'); if(!m) return;
    var g = 0;
    while(m.scrollWidth > m.clientWidth + 1 && cur('--metric-fs') > 44 && g++ < 40){ put('--metric-fs', cur('--metric-fs') - 2); }
  }
  window.__fit = function(){
    if(fitCover()) return 0;
    fitMetric();
    STEPS.forEach(function(s){ var c = cur(s[0]); if(!isNaN(c) && !(s[0] in base)) base[s[0]] = c; });
    var g = 0;
    while(over() > 0 && g++ < 150){
      var moved = false;
      for(var i = 0; i < STEPS.length; i++){
        var s = STEPS[i], c = cur(s[0]);
        if(isNaN(c)) continue;
        if(c - s[2] >= base[s[0]] * s[1]){ put(s[0], c - s[2]); moved = true; break; }
      }
      if(!moved) break;
    }
    return over();
  };
  if(document.fonts && document.fonts.ready){ document.fonts.ready.then(function(){ window.__fit(); }); }
})();
"""


def page_shell(body: str, root_vars: str = "") -> str:
    return (
        '<!DOCTYPE html>\n<html lang="id" style="' + root_vars + '">\n<head>\n<meta charset="utf-8">\n'
        + FONT_LINKS + "\n<style>\n" + get_base_css() + "\n</style>\n</head>\n<body>\n"
        + body + "\n<script>" + FIT_JS + "</script>\n</body>\n</html>\n"
    )


# ==============================================================================
# KOMPONEN BERSAMA
# ==============================================================================
def brand_header(chip_text: str) -> str:
    return f"""
  <div class="brand-header">
    <div class="brand-left">
      <div class="brand-monogram">M</div>
      <div class="brand-title-wrap">
        <div class="brand-title">METRIKA</div>
        <div class="brand-tagline">JURNALISME DATA &amp; RISET FINANSIAL</div>
      </div>
    </div>
    <div class="program-chip">{esc(chip_text)}</div>
  </div>"""


def bottom_bar(active: int, total: int, right_text: str) -> str:
    segs = "".join(
        f'<div class="progress-segment-item {"active" if i < active else ""}"></div>' for i in range(total)
    )
    return f"""
    <div class="slide-bottom-bar">
      <div class="carousel-progress-bar">{segs}</div>
      <div class="editorial-footer"><div>@metrika.id</div><div>{esc(right_text)}</div></div>
    </div>"""


def header_box(eyebrow: str, hook: str) -> str:
    return f"""
      <div class="slide-header-box">
        <div class="slide-eyebrow-pill">{esc(eyebrow)}</div>
        <h2 class="slide-hook-headline">{esc(hook)}</h2>
      </div>"""


def status_bar(label: str, text: str, red: bool = False) -> str:
    return f"""
      <div class="status-bar{' red' if red else ''}">
        <span class="badge-tag">[{esc(label)}]</span>
        <span class="status-text">{esc(text)}</span>
      </div>"""


def wrap_slide(chip: str, main_inner: str, active: int, total: int, footer_text: str, root_vars: str) -> str:
    body = f"""{brand_header(chip)}
  <div class="slide-content-wrapper">
    <div class="slide-main-body">{main_inner}
    </div>{bottom_bar(active, total, footer_text)}
  </div>"""
    return page_shell(body, root_vars)


# ==============================================================================
# SLIDE 1: COVER
# ==============================================================================
def render_html_cover(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    hook_html = format_hook_html(content.get("hook", ""))
    hero = content.get("hero", {}) or {}
    hero_val = esc(hero.get("value", ""))
    hero_lbl = esc(hero.get("label", ""))
    date_str = esc(content.get("date", "")).upper()
    credit = esc(content.get("hero_image_credit", ""))

    uri = get_image_data_uri(content.get("hero_image"))
    stat_html = ""
    if hero_val:
        stat_html = f"""
    <div class="stat-pill">
      <span class="stat-num">{hero_val}</span>
      <span class="stat-lbl">{hero_lbl}</span>
    </div>"""

    credit_html = f"<div>Foto: {credit}</div>" if credit else ""
    body = f"""{brand_header(f"{date_str} | {theme['label']}")}
  <div class="cover-top-box">
    <h1 class="cover-headline">{hook_html}</h1>{stat_html}
  </div>
  <div class="cover-photo-wrapper">
    {photo_html(uri, "cover-photo", "Foto sampul")}
    <div class="photo-gradient-overlay">
      <div class="swipe-prompt"><span class="swipe-chip">Geser</span><span>untuk bedah data dan argumen lengkap</span></div>
      <div class="photo-credit">{credit_html}<div>@metrika.id</div></div>
    </div>
  </div>"""
    return page_shell(body, "--cover-fs:52px;")


# ==============================================================================
# SLIDE 2: KONTEKS FAKTA
# ==============================================================================
def render_html_context(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s = content.get("slide_context", {}) or {}
    uri = get_image_data_uri(content.get("slide2_image") or content.get("hero_image"))

    cards = []
    for i, pt in enumerate(list(s.get("points") or [])[:3], start=1):
        title, body = split_lead_in(pt)
        title_html = f'<div class="card-title">{esc(title)}</div>' if title else ""
        cards.append(
            f'<div class="info-card"><div class="num-badge">{i:02d}</div>'
            f'<div class="card-text">{title_html}<div class="card-body">{bold_html(body)}</div></div></div>'
        )

    main = f"""
      {header_box(s.get("eyebrow") or "01 / DOKUMENTASI FAKTA", s.get("hook") or "Kenapa Isu Ini Tiba-tiba Meledak?")}
      <div class="photo-card">
        {photo_html(uri, "photo-img", "Dokumentasi fakta lapangan")}
        <div class="photo-badge">Dokumentasi Fakta Lapangan</div>
      </div>
      <div class="card-stack">{"".join(cards)}</div>
      {status_bar("FAKTA KUNCI", s.get("takeaway") or "")}"""
    return wrap_slide(f"02 / {total_slides:02d}", main, 2, total_slides,
                      "Geser ke kanan untuk rincian angka", "--photo-h:380px;--body-fs:21px;--title-fs:25px;--hook-fs:46px;")


# ==============================================================================
# SLIDE 3: BEDAH DATA
# ==============================================================================
def _column_card(title: str, points: List[str], tag: str) -> str:
    items = "".join(
        f'<div class="point-item"><div class="bullet"></div><div>{bold_html(p)}</div></div>' for p in points[:3]
    )
    return f"""
        <div class="column-card">
          <div class="column-body">
            <div class="column-header">{esc(title)}</div>
            <div class="points-list">{items}</div>
          </div>
          <div class="column-footer"><span>METRIKA DATA AUDIT</span><span>{esc(tag)}</span></div>
        </div>"""


def render_html_metric(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s = content.get("slide_metric", {}) or {}
    uri = get_image_data_uri(content.get("slide3_image") or content.get("hero_image"))

    main = f"""
      {header_box(s.get("eyebrow") or "02 / BEDAH DATA RISET", s.get("hook") or "Berapa Besar Angka yang Selama Ini Tak Terlihat?")}
      <div class="split-metric-card">
        <div class="split-img-pane">{photo_html(uri, "photo-img", "Visual analisis data")}</div>
        <div class="split-metric-pane">
          <div class="metric-kicker">[DATA KUNCI]</div>
          <div class="metric-val">{esc(s.get("metric_value") or "")}</div>
          <div class="metric-lbl">{esc(s.get("metric_label") or "")}</div>
        </div>
      </div>
      <div class="dual-columns">
        {_column_card(s.get("col1_title") or "Dampak Konsumen", list(s.get("col1_points") or []), "Sisi konsumen")}
        {_column_card(s.get("col2_title") or "Dampak Pelaku Usaha", list(s.get("col2_points") or []), "Sisi usaha")}
      </div>
      {status_bar("CATATAN AUDIT", s.get("alert_text") or "", red=True)}"""
    return wrap_slide(f"03 / {total_slides:02d}", main, 3, total_slides,
                      "Geser untuk strategi eksekusi", "--photo-h:260px;--body-fs:20px;--hook-fs:46px;--metric-fs:68px;--col-min:440px;")


# ==============================================================================
# SLIDE 4: SKENARIO STRATEGIS
# ==============================================================================
def render_html_strategy(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s = content.get("slide_strategy", {}) or {}
    uri = get_image_data_uri(content.get("slide4_image") or content.get("hero_image"))

    cards = []
    for sc in list(s.get("scenarios") or [])[:3]:
        cards.append(
            f'<div class="scenario-card"><div class="scenario-tag">{esc(sc.get("tag") or "SKENARIO")}</div>'
            f'<div class="scenario-body">{bold_html(sc.get("text") or "")}</div></div>'
        )

    main = f"""
      {header_box(s.get("eyebrow") or "03 / SKENARIO STRATEGIS", s.get("hook") or "Tiga Langkah Menghadapi Perubahan Ini")}
      <div class="photo-card">
        {photo_html(uri, "photo-img", "Visual strategi")}
        <div class="photo-badge">Panduan Mitigasi Risiko</div>
      </div>
      <div class="scenario-stack">{"".join(cards)}</div>
      {status_bar("PRINSIP UTAMA", s.get("takeaway") or "")}"""
    return wrap_slide(f"04 / {total_slides:02d}", main, 4, total_slides,
                      "Geser untuk kesimpulan akhir dan diskusi", "--photo-h:340px;--body-fs:21px;--hook-fs:46px;")


# ==============================================================================
# SLIDE 5: VERDICT & DISKUSI
# ==============================================================================
def render_html_verdict(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    uri = get_image_data_uri(content.get("slide5_image") or content.get("hero_image"))
    highlights = list(content.get("slide5_highlights") or [])[:3]
    sources = content.get("sources") or []

    hl_html = "".join(
        f'<div class="highlight-item"><div class="highlight-num">{i}</div><div>{bold_html(h)}</div></div>'
        for i, h in enumerate(highlights, start=1)
    )
    src_html = "".join(f'<div class="source-pill">{esc(x)}</div>' for x in sources)

    main = f"""
      {header_box(content.get("slide5_eyebrow") or "04 / KESIMPULAN RISET", content.get("slide5_hook") or "Verdict Riset dan Ruang Diskusi Terbuka")}
      <div class="photo-card">
        {photo_html(uri, "photo-img", "Visual verdict")}
        <div class="verdict-overlay">
          <div class="verdict-tag">[VERDICT OBJEKTIF REDAKSI METRIKA]</div>
          <div class="verdict-quote">{esc(content.get("verdict", ""))}</div>
        </div>
      </div>
      <div class="highlights-card">
        <div class="highlights-title">3 Poin Investigasi Utama</div>
        <div class="highlights-list">{hl_html}</div>
      </div>
      <div class="cta-card">
        <div class="cta-badge">?</div>
        <div class="cta-text">{esc(content.get("cta", ""))}</div>
      </div>
      <div class="sources-card">
        <div class="sources-title">Sumber Data Terverifikasi</div>
        <div class="sources-grid">{src_html}</div>
      </div>"""
    return wrap_slide(f"05 / {total_slides:02d}", main, total_slides, total_slides,
                      "Data bicara. Kamu yang menilai.", "--photo-h:400px;--body-fs:21px;--hook-fs:46px;")


# ==============================================================================
# ENGINE RENDER (PLAYWRIGHT / CHROMIUM HEADLESS)
# ==============================================================================
def build_html_pages(content: Dict[str, Any], total_slides: int = 5) -> List[Tuple[str, str]]:
    prog_id = content.get("program", "ANGKA_BICARA")
    theme = PROGRAMS_THEME.get(prog_id, PROGRAMS_THEME["ANGKA_BICARA"])
    return [
        ("slide_01", render_html_cover(content, theme, total_slides)),
        ("slide_02", render_html_context(content, theme, total_slides)),
        ("slide_03", render_html_metric(content, theme, total_slides)),
        ("slide_04", render_html_strategy(content, theme, total_slides)),
        ("slide_05", render_html_verdict(content, theme, total_slides)),
    ]


def render_carousel_slides(content: Dict[str, Any], out_dir: str | Path, fmt: str = "PNG") -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_pages = build_html_pages(content, 5)
    for name, page_html in html_pages:
        (out_dir / f"{name}.html").write_text(page_html, encoding="utf-8")

    out_paths: List[Path] = []
    try:
        from playwright.sync_api import sync_playwright

        print("[Playwright] Memulai Chromium headless untuk render 5 slide carousel...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(viewport={"width": W_IG, "height": H_IG}, device_scale_factor=1)
            page = context.new_page()

            for name, page_html in html_pages:
                out_img = out_dir / f"{name}.png"
                try:
                    page.set_content(page_html, wait_until="networkidle", timeout=20000)
                except Exception as err:
                    log.warning(f"networkidle gagal ({err}); mencoba domcontentloaded.")
                    page.set_content(page_html, wait_until="domcontentloaded")
                try:
                    leftover = page.evaluate(
                        "document.fonts.ready.then(() => (window.__fit ? window.__fit() : 0))"
                    )
                    if leftover and leftover > 0:
                        print(f"[Playwright] PERINGATAN {name}: konten masih melebihi kanvas {leftover}px "
                              f"setelah auto-fit. Pendekkan teks dari AI.")
                except Exception as err:
                    log.warning(f"Auto-fit dilewati: {err}")
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
            d.text((80, 80), "METRIKA - install Playwright: pip install playwright && playwright install chromium",
                   fill=(43, 26, 18))
            im.save(fallback_img)
            out_paths.append(fallback_img)

    return out_paths
