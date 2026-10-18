#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indeks Keringat - Labor & Purchasing Power Media (Evergreen Edition)
===================================================================
Media otomasi cerdas berbasis Data Science & Jurnalisme Komputasional.
Konsep: Menghitung nilai riil barang viral/gadget/gaya hidup terhadap
daya beli nyata masyarakat Indonesia:
1. Jam kerja / trip Driver Ojek Online (Gojek/Grab)
2. Hari kerja / porsi gaji Pekerja UMR Jakarta
3. Waktu menabung Fresh Graduate S1
4. Nilai alternatif riil (Beras, Emas Antam, Sewa Kos)

Keluaran:
- 6 Slide Carousel Instagram (4:5, 1080x1350) Dark Minimalist Infographic
- 1 Video Vertikal TikTok / Reels (9:16, 1080x1920) dengan animasi kalkulator
- Voiceover natural ekspresif via Edge-TTS (id-ID-GadisNeural, tempo +12%)
- Distribusi otomatis harian ke Bot Telegram pribadi
"""

import asyncio
import datetime
import io
import json
import math
import os
import re
import subprocess
import sys
import textwrap
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import feedparser
except ImportError:
    feedparser = None

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ==============================================================================
# 1. KONFIGURASI LINGKUNGAN & PARAMETER EKONOMI INDONESIA
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_OVERRIDE = os.environ.get("GEMINI_MODEL", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

PREFERRED_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
]

# RSS Feed untuk topik gaya hidup, gadget, otomotif, konser, dan ekonomi viral
RSS_FEEDS = [
    "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=harga+resmi+OR+tiket+konser+OR+gadget+viral+OR+mobil+motor+indonesia&hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=gaya+hidup+OR+belanja+OR+biaya+hidup+anak+muda&hl=id&gl=ID&ceid=ID:id",
]

BLOCKED_IMAGE_DOMAINS = [
    "amazon.com",
    "media-amazon.com",
    "shopee",
    "tokopedia",
    "lazada",
    "bukalapak",
    "aliexpress",
    "ebay",
]

CACHE_FILE = Path("posted_links.txt")
OUTPUT_DIR = Path("output_media")
CAROUSEL_DIR = OUTPUT_DIR / "carousel"
AUDIO_PATH = OUTPUT_DIR / "voiceover.mp3"
SUBTITLE_PATH = OUTPUT_DIR / "subtitles.json"
HERO_IMG_PATH = OUTPUT_DIR / "item_hero.jpg"
FINAL_VIDEO_PATH = OUTPUT_DIR / "tiktok_reels_indeks_keringat.mp4"

# Standar Ekonomi Riil Indonesia (Benchmark Deterministik)
UMR_JAKARTA = 5_067_381           # Rp 5.067.381/bulan
HARI_KERJA_SEBULAN = 22           # 22 hari kerja
UMR_PER_HARI = UMR_JAKARTA / HARI_KERJA_SEBULAN       # ~Rp 230.335/hari
UMR_PER_JAM = UMR_PER_HARI / 8                        # ~Rp 28.791/jam

OJOL_NET_PER_TRIP = 12_500        # Rata-rata laba bersih per order/trip
OJOL_NET_PER_HARI = 150_000       # Rata-rata 12 trip per hari (~Rp 150.000)
OJOL_NET_PER_JAM = 16_000         # Jam kerja jalanan aktif

FRESHGRAD_GAJI = 7_000_000        # Gaji rata-rata fresh graduate S1
TABUNGAN_FRESHGRAD_MO = 2_100_000 # Rasio tabungan wajar 30% per bulan

HARGA_BERAS_5KG = 75_000          # 1 karung beras 5kg
HARGA_EMAS_ANTAM_GRAM = 1_450_000 # 1 gram emas Antam
SEWA_KOS_JAKARTA_MO = 1_800_000   # 1 bulan sewa kos standar Jakarta

# TTS: Suara GadisNeural dengan intonasi lincah (+12%) agar tidak datar
TTS_VOICE = "id-ID-GadisNeural"
TTS_RATE = "+12%"

CAROUSEL_WIDTH = 1080
CAROUSEL_HEIGHT = 1350
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Palet Visual Dark Minimalist & Punchy Colors
COLOR_BG = (10, 15, 26)            # #0A0F1A Deep Midnight Slate
COLOR_CARD = (18, 26, 44)          # #121A2C Navy Card
COLOR_CARD_ALT = (26, 37, 62)      # #1A253E Highlight Panel
COLOR_BORDER = (42, 58, 92)        # #2A3A5C Clean Vector Border
COLOR_TEXT_MAIN = (248, 250, 252)  # #F8FAFC Crisp White
COLOR_TEXT_MUTED = (148, 163, 184) # #94A3B8 Slate Gray
COLOR_EMERALD = (16, 185, 129)     # #10B981 Money / Labor Success
COLOR_OJOL = (0, 170, 19)          # #00AA13 Hijau Khas Ojol
COLOR_AMBER = (245, 158, 11)       # #F59E0B Warning / High Effort
COLOR_CYBER_GOLD = (250, 204, 21)  # #FACC15 Golden Highlight
COLOR_ACCENT = (56, 189, 248)      # #38BDF8 Cyan Metric

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ==============================================================================
# 2. UTILITAS FORMAT RUPIAH & FONT
# ==============================================================================
def format_rupiah(amount: int) -> str:
    """Format angka rupiah rapi: Rp 24.999.000"""
    return f"Rp {amount:,.0f}".replace(",", ".")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def clean_html(raw_html: str) -> str:
    clean_regex = re.compile("<.*?>")
    text = re.sub(clean_regex, " ", raw_html or "")
    return re.sub(r"\s+", " ", text).strip()


# ==============================================================================
# 3. MODUL INGESTION TREN KONSUMEN & FOTO JURNALISTIK PRODUK/ITEM
# ==============================================================================
def load_posted_links() -> set:
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text("", encoding="utf-8")
        return set()
    lines = CACHE_FILE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip()}


def save_posted_link(link: str) -> None:
    with CACHE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{link.strip()}\n")


def fetch_latest_lifestyle_trend() -> Tuple[Dict[str, str], List[str]]:
    posted = load_posted_links()
    candidates: List[Dict[str, str]] = []

    if feedparser is not None:
        for rss_url in RSS_FEEDS:
            print(f"[RSS] Memindai feed tren: {rss_url[:65]}...")
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:15]:
                    link = entry.get("link", "").strip()
                    title = entry.get("title", "").strip()
                    summary = clean_html(entry.get("summary", ""))
                    published = entry.get("published", "")
                    if link and title and link not in posted:
                        candidates.append(
                            {
                                "title": title,
                                "link": link,
                                "summary": summary,
                                "published": published,
                            }
                        )
            except Exception:
                continue

    if not candidates:
        # Fallback evergreen jika feed belum update
        candidates.append(
            {
                "title": "Harga iPhone 16 Pro Max Resmi dan Fenomena Konsumerisme Gadget",
                "link": f"https://indekskeringat.internal/evergreen/{datetime.date.today()}",
                "summary": "Analisis harga resmi gadget flagship terhadap daya beli upah minimum dan jam kerja pekerja informal di Indonesia.",
                "published": str(datetime.date.today()),
            }
        )

    primary_item = candidates[0]
    supporting = [item["title"] for item in candidates[1:6]]
    print(f"[RSS] Topik terpilih: {primary_item['title']}")
    return primary_item, supporting


def fetch_editorial_photo(
    news_item: Dict[str, str], item_name: str, save_path: Path
) -> Optional[Image.Image]:
    """Mengambil foto produk/subjek dari portal berita atau media resmi."""
    candidate_urls: List[str] = []

    if BeautifulSoup is not None:
        try:
            resp = requests.get(
                news_item["link"], headers=HTTP_HEADERS, timeout=12, allow_redirects=True
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for prop in ("og:image", "twitter:image", "og:image:secure_url"):
                    meta = soup.find("meta", property=prop) or soup.find(
                        "meta", attrs={"name": prop}
                    )
                    if meta and meta.get("content", "").startswith("http"):
                        val = meta["content"].strip()
                        if not any(b in val.lower() for b in BLOCKED_IMAGE_DOMAINS):
                            candidate_urls.append(val)
        except Exception:
            pass

    # Pencarian cadangan via Bing Images
    search_q = f"{item_name} Indonesia resmi site:detik.com OR site:kompas.com OR site:kumparan.com"
    bing_url = (
        "https://www.bing.com/images/search?q="
        + urllib.parse.quote(search_q)
        + "&qft=+filterui:imagesize-large"
    )
    try:
        b_resp = requests.get(bing_url, headers=HTTP_HEADERS, timeout=12)
        if b_resp.status_code == 200:
            matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', b_resp.text)
            for m in matches[:6]:
                if not any(b in m.lower() for b in BLOCKED_IMAGE_DOMAINS):
                    candidate_urls.append(m)
    except Exception:
        pass

    for img_url in candidate_urls:
        try:
            r = requests.get(img_url, headers=HTTP_HEADERS, timeout=12)
            if r.status_code == 200 and len(r.content) > 20_000:
                pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if pil_img.width >= 400 and pil_img.height >= 250:
                    pil_img.save(save_path, format="JPEG", quality=92)
                    print(f"[Photo] Foto produk berhasil diunduh: {img_url[:65]}...")
                    return pil_img
        except Exception:
            continue

    print("[Photo] Menggunakan visual background data canvas dark-mode.")
    return None


def crop_and_banner_photo(
    photo: Optional[Image.Image],
    target_w: int,
    target_h: int,
    darken: float = 0.55,
) -> Image.Image:
    if photo is None:
        return Image.new("RGB", (target_w, target_h), color=COLOR_CARD)

    src_w, src_h = photo.size
    target_ratio = target_w / float(target_h)
    src_ratio = src_w / float(src_h)

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        new_h = src_h
    else:
        new_w = src_w
        new_h = int(src_w / target_ratio)

    left = (src_w - new_w) // 2
    top = (src_h - new_h) // 2
    cropped = photo.crop((left, top, left + new_w, top + new_h))
    resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    enhancer = ImageEnhance.Brightness(resized)
    darkened = enhancer.enhance(darken)

    # Gradient fade ke background bawah
    gradient = Image.new("L", (1, target_h), color=0)
    for y in range(target_h):
        if y < int(target_h * 0.45):
            alpha = 0
        else:
            prog = (y - target_h * 0.45) / (target_h * 0.55)
            alpha = int(min(255, prog * 250))
        gradient.putpixel((0, y), alpha)

    alpha_mask = gradient.resize((target_w, target_h))
    bg_layer = Image.new("RGB", (target_w, target_h), color=COLOR_BG)
    return Image.composite(bg_layer, darkened, alpha_mask)


# ==============================================================================
# 4. MODUL OTAK AI: EKSTRAKSI ITEM, HARGA RIIL & KALKULASI DAYA BELI
# ==============================================================================
def get_available_gemini_models() -> List[str]:
    if GEMINI_MODEL_OVERRIDE:
        clean_override = GEMINI_MODEL_OVERRIDE.replace("models/", "")
        return [clean_override] + [
            m for m in PREFERRED_GEMINI_MODELS if m != clean_override
        ]

    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    discovered: List[str] = []
    try:
        resp = requests.get(list_url, timeout=20)
        resp.raise_for_status()
        for m in resp.json().get("models", []):
            name = m.get("name", "").replace("models/", "")
            if "generateContent" in m.get("supportedGenerationMethods", []) and name.startswith("gemini-"):
                discovered.append(name)
    except Exception:
        return list(PREFERRED_GEMINI_MODELS)

    ordered = [m for m in PREFERRED_GEMINI_MODELS if m in discovered]
    for m in discovered:
        if m not in ordered:
            ordered.append(m)
    return ordered or list(PREFERRED_GEMINI_MODELS)


def analyze_purchasing_power_with_gemini(
    news_item: Dict[str, str], supporting_headlines: List[str]
) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY belum terpasang di environment variable / GitHub Secrets!")

    prompt = f"""
Kamu adalah Chief Economist & Data Journalist dari media visual Indonesia bernama "INDEKS KERINGAT" (Labor & Purchasing Power Media).
Misi media ini adalah membumikan harga barang viral/gadget/tiket/gaya hidup terhadap realitas jam kerja dan daya beli riil masyarakat Indonesia.

Berita / Topik Tren Hari Ini:
- Judul: {news_item['title']}
- Ringkasan: {news_item['summary']}

Tugasmu:
1. Identifikasi 1 objek/barang/pengeluaran spesifik yang sedang dibahas atau relevan (misal: "iPhone 16 Pro Max 256GB", "Tiket Konser Sheila on 7 CAT 1", "Motor Vespa Sprint 150", "Biaya Hidup Anak Kos Jaksel Sebulan", "Boneka Labubu V2").
2. Tentukan estimasi harga pasar resmi di Indonesia dalam Rupiah (integer, misal 24999000, 3500000, 42000000). Jika berita bersifat umum/makro, pilih 1 barang konsumsi viral paling representatif saat ini.
3. Rancang naskah voiceover 55-75 kata yang PUNCHY, kritis, dan komunikatif:
   - Kalimat pertama WAJIB HOOK detik pertama langsung menyebut nama barang & harga.
   - Tanpa salam basa-basi robot ("Halo sobat", "Tahukah kamu").
   - Akhiri dengan pertanyaan refleksi untuk memicu komentar netizen.

Kembalikan HANYA JSON murni tanpa markdown ```json dengan format persis:
{{
  "item_name": "Nama barang/pengeluaran spesifik (maks 30 karakter)",
  "item_category": "Kategori singkat (misal: GADGET FLAGSHIP / TIKET KONSER / OTOMOTIF / GAYA HIDUP)",
  "price_idr": 24999000,
  "verdict_fomo_score": 85,
  "verdict_label": "FOMO TINGGI",
  "one_sentence_takeaway": "1 kalimat tajam yang menyimpulkan apakah barang ini kebutuhan riil atau sekadar gengsi sesaat.",
  "voiceover_script": "Naskah narasi 55-75 kata bahasa Indonesia mengalir, tanpa simbol Rp atau angka jutaan yang rumit agar pelafalan TTS mulus.",
  "telegram_caption": "Caption Instagram & TikTok yang memancing diskusi lengkap dengan perbandingan angka dan 5 hashtag.",
  "carousel_slides": [
    {{
      "slide_number": 1,
      "tag": "INDEKS KERINGAT • EDISI SPESIAL",
      "headline": "Berapa Lama Harus Narik Ojol Buat Beli Ini?",
      "body": "Membedah nilai riil harga barang terhadap jam kerja nyata masyarakat.",
      "metric_label": "ESTIMASI HARGA RESMI"
    }},
    {{
      "slide_number": 2,
      "tag": "SPESIFIKASI & NILAI BARANG",
      "headline": "Apa yang Sebenarnya Kamu Beli?",
      "body": "Penjelasan fakta nilai guna barang ini di mata konsumen dan pemicu viralitasnya.",
      "metric_label": "KATALIS POPULARITAS"
    }},
    {{
      "slide_number": 3,
      "tag": "PERSPEKTIF DRIVER OJOL",
      "headline": "Beban Keringat di Jalanan",
      "body": "Penghitungan riil berapa trip dan hari kerja dari matahari terbit sampai malam untuk mengumpulkan uang sejumlah ini.",
      "metric_label": "LABA BERSIH HARIAN"
    }},
    {{
      "slide_number": 4,
      "tag": "PERSPEKTIF UMR JAKARTA",
      "headline": "Beban Upah Minimum Pekerja",
      "body": "Berapa bulan gaji penuh yang harus disisihkan tanpa makan dan minum demi satu barang ini.",
      "metric_label": "PORSI DARI GAJI BULANAN"
    }},
    {{
      "slide_number": 5,
      "tag": "OPPORTUNITY COST RIIL",
      "headline": "Bisa Dapat Apa Saja Sebenarnya?",
      "body": "Perbandingan alternatif kebutuhan pokok riil: beras, emas, atau sewa tempat tinggal.",
      "metric_label": "PERBANDINGAN NILAI RIIL"
    }},
    {{
      "slide_number": 6,
      "tag": "KESIMPULAN REDAKSI",
      "headline": "Worth It atau Sekadar FOMO?",
      "body": "Refleksi apakah nilai barang ini sebanding dengan waktu dan tenaga yang kamu korbankan.",
      "metric_label": "TULIS PENDAPATMU DI KOMENTAR"
    }}
  ]
}}
""".strip()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.45, "responseMimeType": "application/json"},
    }

    candidate_models = get_available_gemini_models()
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"[Gemini] Menghitung indeks daya beli dengan model: {model_name}...")
            res = requests.post(url, json=payload, timeout=50)
            if res.status_code == 200:
                raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                parsed = json.loads(cleaned)
                parsed["_model_used"] = model_name
                print(f"[Gemini] Sukses: {parsed['item_name']} | Harga: {format_rupiah(parsed['price_idr'])}")
                return parsed
        except Exception:
            continue

    raise RuntimeError("Seluruh model Gemini gagal menganalisis topik ini.")


# ==============================================================================
# 5. MODUL ENGINE KALKULASI DETERMINISTIK
# ==============================================================================
def compute_labor_metrics(price_idr: int) -> Dict[str, Any]:
    """Menghitung metrik jam kerja dan padanan daya beli secara deterministik."""
    price = max(int(price_idr), 100_000)

    # Metrik Ojol
    ojol_trips = int(math.ceil(price / OJOL_NET_PER_TRIP))
    ojol_days = int(math.ceil(price / OJOL_NET_PER_HARI))
    ojol_hours = int(math.ceil(price / OJOL_NET_PER_JAM))

    # Metrik UMR Jakarta
    umr_days = round(price / UMR_PER_HARI, 1)
    umr_months = round(price / UMR_JAKARTA, 1)
    umr_pct = round((price / UMR_JAKARTA) * 100, 1)

    # Metrik Fresh Graduate (Saving rate 30%)
    freshgrad_months_save = round(price / TABUNGAN_FRESHGRAD_MO, 1)

    # Opportunity Cost Alternatif
    karung_beras = int(price // HARGA_BERAS_5KG)
    ton_beras = round((karung_beras * 5) / 1000.0, 1)
    gram_emas = round(price / HARGA_EMAS_ANTAM_GRAM, 1)
    bulan_kos = round(price / SEWA_KOS_JAKARTA_MO, 1)

    return {
        "price_idr": price,
        "price_str": format_rupiah(price),
        "ojol_trips": ojol_trips,
        "ojol_days": ojol_days,
        "ojol_hours": ojol_hours,
        "umr_days": umr_days,
        "umr_months": umr_months,
        "umr_pct": umr_pct,
        "freshgrad_months_save": freshgrad_months_save,
        "karung_beras": karung_beras,
        "ton_beras": ton_beras,
        "gram_emas": gram_emas,
        "bulan_kos": bulan_kos,
    }


# ==============================================================================
# 6. MODUL SUARA NATURAL & TIMING KARAOKE (EDGE-TTS)
# ==============================================================================
async def _generate_voiceover_stream(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    if edge_tts is None:
        raise RuntimeError("Library edge-tts belum terinstall. Pastikan sudah menjalankan 'pip install edge-tts'.")

    communicate = edge_tts.Communicate(text=script_text, voice=TTS_VOICE, rate=TTS_RATE)
    raw_boundaries: List[Dict[str, Any]] = []

    with audio_out.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "word_boundary"):
                text_val = str(chunk.get("text", "")).strip()
                if text_val:
                    start_sec = float(chunk.get("offset", 0)) / 10_000_000.0
                    dur_sec = float(chunk.get("duration", 0)) / 10_000_000.0
                    raw_boundaries.append(
                        {
                            "word": text_val,
                            "start": start_sec,
                            "end": start_sec + max(dur_sec, 0.12),
                        }
                    )

    if not raw_boundaries:
        dur = 25.0
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_out),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, check=True)
            dur = max(float(r.stdout.strip()), 5.0)
        except Exception:
            pass

        words = [w.strip() for w in script_text.split() if w.strip()]
        total_w = max(len(words), 1)
        sec_per_word = dur / float(total_w)
        for idx, w in enumerate(words):
            s_time = idx * sec_per_word
            raw_boundaries.append(
                {"word": w, "start": s_time, "end": s_time + sec_per_word}
            )

    subtitle_out.write_text(
        json.dumps(raw_boundaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return raw_boundaries


def generate_voiceover(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    print(f"[Edge-TTS] Merekam suara narasi ekspresif ({TTS_VOICE}, {TTS_RATE})...")
    timings = asyncio.run(
        _generate_voiceover_stream(script_text, audio_out, subtitle_out)
    )
    print(f"[Edge-TTS] Audio selesai ({len(timings)} kata terindeks karaoke).")
    return timings


# ==============================================================================
# 7. KOMPONEN GRAFIS & RENDER CAROUSEL INSTAGRAM (4:5, 1080x1350)
# ==============================================================================
def render_carousel_slides(
    analysis: Dict[str, Any],
    metrics: Dict[str, Any],
    hero_photo: Optional[Image.Image],
    out_dir: Path,
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_data = analysis.get("carousel_slides", [])
    total_slides = len(slides_data)

    item_name = analysis.get("item_name", "Barang Viral")
    price_str = metrics["price_str"]
    ojol_trips = metrics["ojol_trips"]
    ojol_days = metrics["ojol_days"]
    umr_months = metrics["umr_months"]
    umr_days = metrics["umr_days"]
    karung_beras = metrics["karung_beras"]
    gram_emas = metrics["gram_emas"]
    bulan_kos = metrics["bulan_kos"]

    font_badge = load_font(26, bold=True)
    font_tag = load_font(24, bold=True)
    font_headline = load_font(48, bold=True)
    font_body = load_font(32, bold=False)
    font_price = load_font(68, bold=True)
    font_metric_val = load_font(52, bold=True)
    font_metric_lbl = load_font(25, bold=False)
    font_footer = load_font(22, bold=False)

    generated_files: List[Path] = []
    today_str = datetime.datetime.now().strftime("%d %b %Y").upper()

    for idx, slide in enumerate(slides_data, start=1):
        img = Image.new("RGB", (CAROUSEL_WIDTH, CAROUSEL_HEIGHT), color=COLOR_BG)

        # Header Image Banner pada slide 1
        if idx == 1 and hero_photo is not None:
            banner = crop_and_banner_photo(hero_photo, CAROUSEL_WIDTH, 560, darken=0.60)
            img.paste(banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # Header Bar Media
        draw.rounded_rectangle((60, 50, CAROUSEL_WIDTH - 60, 140), radius=16, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
        draw.text((88, 76), "INDEKS KERINGAT • DATA RUPIAH", font=font_badge, fill=COLOR_ACCENT)
        draw.rounded_rectangle((CAROUSEL_WIDTH - 380, 68, CAROUSEL_WIDTH - 85, 122), radius=10, fill=COLOR_EMERALD)
        draw.text((CAROUSEL_WIDTH - 360, 80), "ANALISIS DAYA BELI", font=font_badge, fill=COLOR_BG)

        curr_y = 440 if (idx == 1 and hero_photo is not None) else 190

        # Slide Tag
        slide_tag = slide.get("tag", f"BAGIAN #{idx}").upper()
        draw.text((70, curr_y), slide_tag, font=font_tag, fill=COLOR_CYBER_GOLD)
        curr_y += 42

        # Headline
        headline_text = slide.get("headline", "Kalkulasi Nilai Riil")
        for line in textwrap.wrap(headline_text, width=28)[:3]:
            draw.text((70, curr_y), line, font=font_headline, fill=COLOR_TEXT_MAIN)
            curr_y += 58

        curr_y += 18

        # Konten Dinamis Berdasarkan Nomor Slide
        if idx == 1:
            # Box Harga Utama
            p_box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 190)
            draw.rounded_rectangle(p_box, radius=20, fill=COLOR_CARD, outline=COLOR_EMERALD, width=3)
            draw.text((105, curr_y + 25), f"OBJEK: {item_name.upper()}", font=font_tag, fill=COLOR_TEXT_MUTED)
            draw.text((105, curr_y + 75), price_str, font=font_price, fill=COLOR_CYBER_GOLD)
            curr_y += 215

            # Dua Pilar Mini (Ojol vs UMR)
            w_col = (CAROUSEL_WIDTH - 140 - 25) // 2
            # Kolom Kiri: Ojol
            box_l = (70, curr_y, 70 + w_col, curr_y + 240)
            draw.rounded_rectangle(box_l, radius=18, fill=COLOR_CARD_ALT, outline=COLOR_OJOL, width=2)
            draw.text((95, curr_y + 25), "🛵 DRIVER OJOL", font=font_badge, fill=COLOR_OJOL)
            draw.text((95, curr_y + 75), f"{ojol_trips:,} Trip".replace(",", "."), font=font_metric_val, fill=COLOR_TEXT_MAIN)
            draw.text((95, curr_y + 155), f"Setara {ojol_days} hari narik penuh", font=font_metric_lbl, fill=COLOR_TEXT_MUTED)

            # Kolom Kanan: UMR
            box_r = (70 + w_col + 25, curr_y, CAROUSEL_WIDTH - 70, curr_y + 240)
            draw.rounded_rectangle(box_r, radius=18, fill=COLOR_CARD_ALT, outline=COLOR_ACCENT, width=2)
            draw.text((70 + w_col + 50, curr_y + 25), "💼 PEKERJA UMR", font=font_badge, fill=COLOR_ACCENT)
            draw.text((70 + w_col + 50, curr_y + 75), f"{umr_months} Bulan", font=font_metric_val, fill=COLOR_TEXT_MAIN)
            draw.text((70 + w_col + 50, curr_y + 155), f"Setara {umr_days} hari kerja", font=font_metric_lbl, fill=COLOR_TEXT_MUTED)

        elif idx == 3:
            # Breakdown Ojol Detail
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
            draw.rounded_rectangle(box, radius=22, fill=COLOR_CARD, outline=COLOR_OJOL, width=3)
            draw.text((105, curr_y + 35), "HITUNG-HITUNGAN KERINGAT DRIVER OJOL", font=font_tag, fill=COLOR_OJOL)
            draw.text((105, curr_y + 90), f"Total Order: {ojol_trips:,} Trip".replace(",", "."), font=font_metric_val, fill=COLOR_CYBER_GOLD)
            draw.text((105, curr_y + 175), f"• Estimasi Waktu di Jalan: {metrics['ojol_hours']} Jam Aktif", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 235), f"• Hari Narik (Target 12-14 Trip/Hari): {ojol_days} Hari Penuh", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 295), f"• Basis Pendapatan Bersih: Rp 12.500 per Trip", font=font_body, fill=COLOR_TEXT_MUTED)
            draw.text((105, curr_y + 355), "Tanpa libur, bensin, dan potongan aplikasi.", font=font_body, fill=COLOR_AMBER)
            curr_y += 465

        elif idx == 4:
            # Breakdown UMR Jakarta Detail
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
            draw.rounded_rectangle(box, radius=22, fill=COLOR_CARD, outline=COLOR_ACCENT, width=3)
            draw.text((105, curr_y + 35), "PERSPEKTIF PEKERJA UMR JAKARTA", font=font_tag, fill=COLOR_ACCENT)
            draw.text((105, curr_y + 90), f"{umr_months} Bulan Gaji Penuh", font=font_metric_val, fill=COLOR_CYBER_GOLD)
            draw.text((105, curr_y + 175), f"• Porsi dari Upah Sebulan: {metrics['umr_pct']}%", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 235), f"• Jam Kerja Formal: {int(umr_days * 8)} Jam Kerja Kantor", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 295), f"• Basis UMR DKI Jakarta: Rp 5.067.381/bulan", font=font_body, fill=COLOR_TEXT_MUTED)
            draw.text((105, curr_y + 355), "Kondisi: 100% gaji disisihkan tanpa makan/minum.", font=font_body, fill=COLOR_AMBER)
            curr_y += 465

        elif idx == 5:
            # Opportunity Cost Alternatif
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
            draw.rounded_rectangle(box, radius=22, fill=COLOR_CARD, outline=COLOR_EMERALD, width=3)
            draw.text((105, curr_y + 35), "UANG INI SETARA DENGAN KEBUTUHAN APA?", font=font_tag, fill=COLOR_EMERALD)
            draw.text((105, curr_y + 95), f"🍚 {karung_beras} Karung Beras 5kg ({metrics['ton_beras']} Ton Beras)", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 165), f"🥇 {gram_emas} Gram Emas Antam Murni", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 235), f"🏠 {bulan_kos} Bulan Sewa Kos Standar Jakarta", font=font_body, fill=COLOR_TEXT_MAIN)
            draw.text((105, curr_y + 305), f"📈 {metrics['freshgrad_months_save']} Bulan Tabungan Disiplin Fresh Graduate", font=font_body, fill=COLOR_CYBER_GOLD)
            draw.text((105, curr_y + 370), "Pilihan ada di tanganmu: Konsumtif atau Produktif?", font=font_body, fill=COLOR_TEXT_MUTED)
            curr_y += 465

        else:
            # Slide Narasi Umum / Kesimpulan
            body_text = slide.get("body", "")
            wrapped = textwrap.wrap(body_text, width=42)[:7]
            box_h = max(220, len(wrapped) * 48 + 70)
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + box_h)
            draw.rounded_rectangle(box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
            draw.rounded_rectangle((70, curr_y, 84, curr_y + box_h), radius=6, fill=COLOR_CYBER_GOLD)

            ty = curr_y + 35
            for line in wrapped:
                draw.text((115, ty), line, font=font_body, fill=COLOR_TEXT_MAIN)
                ty += 48
            curr_y += box_h + 30

        # Footer Metric Bar
        metric_lbl = slide.get("metric_label", "INDEKS KERINGAT").upper()
        draw.text((70, 1180), f"⚡ {metric_lbl}", font=font_badge, fill=COLOR_EMERALD)

        draw.line([(70, 1235), (CAROUSEL_WIDTH - 70, 1235)], fill=COLOR_BORDER, width=2)
        draw.text((70, 1260), f"INDEKS KERINGAT • {today_str}", font=font_footer, fill=COLOR_TEXT_MUTED)
        draw.text((CAROUSEL_WIDTH - 220, 1260), f"SLIDE {idx} / {total_slides}  →", font=font_footer, fill=COLOR_TEXT_MAIN)

        slide_file = out_dir / f"slide_{idx:02d}.png"
        img.save(slide_file, format="PNG", optimize=True)
        generated_files.append(slide_file)

    print(f"[Pillow] Berhasil merender {len(generated_files)} slide infografis Indeks Keringat.")
    return generated_files


# ==============================================================================
# 8. RENDER VIDEO VERTIKAL ANIMASI KALKULATOR (9:16, 1080x1920)
# ==============================================================================
def get_audio_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return max(float(res.stdout.strip()), 5.0)
    except Exception:
        return 25.0


def draw_karaoke_subtitle_box(
    draw: ImageDraw.ImageDraw,
    word_timings: List[Dict[str, Any]],
    current_sec: float,
    font_sub: ImageFont.FreeTypeFont,
) -> None:
    sub_box = (65, 1420, VIDEO_WIDTH - 65, 1700)
    draw.rounded_rectangle(sub_box, radius=24, fill=(15, 23, 42), outline=COLOR_EMERALD, width=3)

    group_size = 5
    active_idx = 0
    for i, item in enumerate(word_timings):
        if item["start"] <= current_sec <= item["end"] + 0.15:
            active_idx = i
            break
        if item["start"] <= current_sec:
            active_idx = i

    group_start = (active_idx // group_size) * group_size
    group_slice = word_timings[group_start : group_start + group_size]
    tokens = [
        (w["word"].upper(), (group_start + idx) == active_idx)
        for idx, w in enumerate(group_slice)
    ]

    full_line = " ".join(t[0] for t in tokens)
    bbox = draw.textbbox((0, 0), full_line, font=font_sub)
    line_w = bbox[2] - bbox[0]
    curr_x = (VIDEO_WIDTH - line_w) // 2
    curr_y = 1530

    for word_str, is_active in tokens:
        color = COLOR_CYBER_GOLD if is_active else COLOR_TEXT_MAIN
        draw.text((curr_x, curr_y), word_str, font=font_sub, fill=color)
        w_bbox = draw.textbbox((0, 0), word_str + " ", font=font_sub)
        curr_x += w_bbox[2] - w_bbox[0]


def render_vertical_video(
    analysis: Dict[str, Any],
    metrics: Dict[str, Any],
    hero_photo: Optional[Image.Image],
    word_timings: List[Dict[str, Any]],
    audio_path: Path,
    video_out: Path,
) -> Path:
    frames_dir = OUTPUT_DIR / "video_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    duration = get_audio_duration(audio_path)
    fps = 12
    total_frames = int(math.ceil(duration * fps))

    item_name = analysis.get("item_name", "Barang Viral")
    price_target = metrics["price_idr"]
    target_trips = metrics["ojol_trips"]
    target_umr_mo = metrics["umr_months"]

    font_header = load_font(34, bold=True)
    font_badge = load_font(26, bold=True)
    font_item = load_font(46, bold=True)
    font_counter = load_font(74, bold=True)
    font_card_val = load_font(50, bold=True)
    font_card_lbl = load_font(26, bold=False)
    font_sub = load_font(42, bold=True)
    font_small = load_font(24, bold=False)

    print(f"[Video] Merender {total_frames} frame animasi kalkulator ({duration:.1f} dtk @ {fps} fps)...")

    for f_idx in range(total_frames):
        current_sec = f_idx / float(fps)
        progress = f_idx / float(max(total_frames - 1, 1))

        # Animasi penghitung counter (angka naik dinamis)
        anim_factor = min(1.0, progress * 1.6)
        curr_price = int(price_target * (anim_factor ** 2))
        curr_trips = int(target_trips * (anim_factor ** 2))
        curr_umr_mo = round(target_umr_mo * (anim_factor ** 2), 1)

        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=COLOR_BG)

        # Foto Header
        banner = crop_and_banner_photo(hero_photo, VIDEO_WIDTH, 720, darken=0.62)
        img.paste(banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # Header Bar
        draw.rounded_rectangle((60, 75, VIDEO_WIDTH - 60, 175), radius=18, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
        draw.text((95, 105), "INDEKS KERINGAT", font=font_header, fill=COLOR_CYBER_GOLD)
        draw.rounded_rectangle((VIDEO_WIDTH - 380, 95, VIDEO_WIDTH - 85, 155), radius=12, fill=COLOR_EMERALD)
        draw.text((VIDEO_WIDTH - 355, 108), "DATA RUPIAH", font=font_header, fill=COLOR_BG)

        # Tag Judul & Nama Barang
        draw.rounded_rectangle((65, 205, 480, 255), radius=10, fill=COLOR_CARD_ALT, outline=COLOR_ACCENT, width=1)
        draw.text((85, 217), "KALKULASI DAYA BELI RIIL", font=font_badge, fill=COLOR_ACCENT)

        draw.text((65, 275), item_name.upper(), font=font_item, fill=COLOR_TEXT_MAIN)

        # Counter Box Animasi Rupiah
        p_card = (65, 470, VIDEO_WIDTH - 65, 680)
        draw.rounded_rectangle(p_card, radius=24, fill=COLOR_CARD, outline=COLOR_EMERALD, width=3)
        draw.text((100, 495), "HARGA BARANG:", font=font_badge, fill=COLOR_TEXT_MUTED)
        draw.text((100, 550), format_rupiah(curr_price), font=font_counter, fill=COLOR_CYBER_GOLD)

        # Dua Kartu Utama: Ojol vs UMR
        # 1. Kartu Ojol
        card_ojol = (65, 720, VIDEO_WIDTH - 65, 960)
        draw.rounded_rectangle(card_ojol, radius=22, fill=COLOR_CARD_ALT, outline=COLOR_OJOL, width=3)
        draw.text((105, 750), "🛵 BERAPA ORDERAN DRIVER OJOL?", font=font_badge, fill=COLOR_OJOL)
        draw.text((105, 805), f"{curr_trips:,} TRIP".replace(",", "."), font=font_card_val, fill=COLOR_TEXT_MAIN)
        draw.text((105, 890), f"Setara {metrics['ojol_days']} hari kerja penuh dari pagi sampai malam", font=font_card_lbl, fill=COLOR_TEXT_MUTED)

        # 2. Kartu UMR Jakarta
        card_umr = (65, 1000, VIDEO_WIDTH - 65, 1240)
        draw.rounded_rectangle(card_umr, radius=22, fill=COLOR_CARD_ALT, outline=COLOR_ACCENT, width=3)
        draw.text((105, 1030), "💼 BERAPA BULAN GAJI UMR JAKARTA?", font=font_badge, fill=COLOR_ACCENT)
        draw.text((105, 1085), f"{curr_umr_mo} BULAN GAJI", font=font_card_val, fill=COLOR_TEXT_MAIN)
        draw.text((105, 1170), f"Setara {metrics['umr_days']} hari kerja keras tanpa biaya hidup", font=font_card_lbl, fill=COLOR_TEXT_MUTED)

        # Subtitle Karaoke
        draw_karaoke_subtitle_box(draw, word_timings, current_sec, font_sub)

        # Progress bar bawah
        bar_bg = (65, 1740, VIDEO_WIDTH - 65, 1756)
        bar_fg = (65, 1740, 65 + int((VIDEO_WIDTH - 130) * progress), 1756)
        draw.rounded_rectangle(bar_bg, radius=8, fill=COLOR_CARD)
        draw.rounded_rectangle(bar_fg, radius=8, fill=COLOR_CYBER_GOLD)

        draw.text((65, 1780), "INDEKS KERINGAT • DATA STORYTELLING MEDIA", font=font_small, fill=COLOR_TEXT_MUTED)

        frame_path = frames_dir / f"frame_{f_idx:04d}.png"
        img.save(frame_path, format="PNG")

    # Sintesis Audio: Voiceover + Dinamis Lofi Beat Bass & Sound Effect Kaching
    filter_complex = (
        f"[1:a]volume=1.25[vocal];"
        f"aevalsrc='0.04*sin(2*PI*120*t)*exp(-2*mod(t,0.5))':s=44100:d={duration}[kick];"
        f"aevalsrc='0.015*sin(2*PI*330*t)+0.01*sin(2*PI*392*t)':s=44100:d={duration}[melody];"
        f"[kick][melody]amix=inputs=2[bgm];"
        f"[vocal][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-i",
        str(audio_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(video_out),
    ]

    print("[FFmpeg] Merender video akhir Indeks Keringat...")
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"[FFmpeg] Video berhasil dibuat: {video_out}")
    return video_out


# ==============================================================================
# 9. DISTRIBUSI TELEGRAM OTOMATIS
# ==============================================================================
def send_outputs_to_telegram(
    video_path: Path,
    carousel_paths: List[Path],
    analysis: Dict[str, Any],
    metrics: Dict[str, Any],
    news_item: Dict[str, str],
) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset. Melewati notifikasi Telegram.")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    item_name = analysis.get("item_name", "Barang Viral")
    price_str = metrics["price_str"]
    ojol_trips = metrics["ojol_trips"]
    ojol_days = metrics["ojol_days"]
    umr_months = metrics["umr_months"]
    umr_days = metrics["umr_days"]
    karung_beras = metrics["karung_beras"]
    gram_emas = metrics["gram_emas"]
    caption = analysis.get("telegram_caption", "")

    header_msg = (
        f"📊 *INDEKS KERINGAT HARI INI*\n"
        f"Objek: *{item_name}*\n"
        f"Harga Resmi: *{price_str}*\n\n"
        f"🛵 *Beban Driver Ojol:* `{ojol_trips:,}` Trip (~{ojol_days} hari kerja penuh)\n"
        f"💼 *Beban Pekerja UMR:* `{umr_months}` Bulan Gaji (~{umr_days} hari kerja)\n"
        f"⚖️ *Setara Kebutuhan Pokok:* {karung_beras} Karung Beras atau {gram_emas}g Emas Murni\n\n"
        f"📝 *Caption Rekomendasi Media:*\n{caption}"
    )

    print("[Telegram] Mengirim video vertikal (.mp4) ke Telegram...")
    with video_path.open("rb") as vf:
        requests.post(
            f"{base_url}/sendVideo",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": header_msg[:1024], "parse_mode": "Markdown"},
            files={"video": vf},
            timeout=120,
        )

    print("[Telegram] Mengirim album Carousel Infografis ke Telegram...")
    media_group = []
    files_payload = {}
    for idx, img_path in enumerate(carousel_paths[:10]):
        attach_key = f"slide_{idx}"
        files_payload[attach_key] = img_path.open("rb")
        item_obj: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_key}"}
        if idx == 0:
            item_obj["caption"] = f"🖼 Carousel Indeks Keringat: {item_name} ({len(carousel_paths)} Slide)"
        media_group.append(item_obj)

    try:
        requests.post(
            f"{base_url}/sendMediaGroup",
            data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media_group)},
            files=files_payload,
            timeout=120,
        )
    finally:
        for f in files_payload.values():
            f.close()

    print("[Telegram] Paket konten Indeks Keringat berhasil dikirim!")


# ==============================================================================
# 10. PIPELINE UTAMA
# ==============================================================================
def main() -> None:
    print("=" * 72)
    print("🚀 MEMULAI PIPELINE INDEKS KERINGAT (DATA & PURCHASING POWER MEDIA)")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    news_item, supporting = fetch_latest_lifestyle_trend()
    analysis = analyze_purchasing_power_with_gemini(news_item, supporting)

    metrics = compute_labor_metrics(analysis.get("price_idr", 20_000_000))
    analysis["metrics"] = metrics

    latest_json = OUTPUT_DIR / "latest_analysis.json"
    latest_json.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

    hero_photo = fetch_editorial_photo(news_item, analysis.get("item_name", ""), HERO_IMG_PATH)

    voice_script = analysis.get("voiceover_script", f"Berapa lama driver ojol harus narik untuk beli {analysis.get('item_name', '')}?")
    word_timings = generate_voiceover(voice_script, AUDIO_PATH, SUBTITLE_PATH)

    carousel_files = render_carousel_slides(analysis, metrics, hero_photo, CAROUSEL_DIR)

    video_file = render_vertical_video(analysis, metrics, hero_photo, word_timings, AUDIO_PATH, FINAL_VIDEO_PATH)

    send_outputs_to_telegram(video_file, carousel_files, analysis, metrics, news_item)

    save_posted_link(news_item["link"])
    print(f"[Cache] Link disimpan ke {CACHE_FILE}.")
    print("✅ PIPELINE INDEKS KERINGAT BERHASIL SELESAI!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌ [ERROR] Pipeline berhenti: {err}", file=sys.stderr)
        sys.exit(1)
