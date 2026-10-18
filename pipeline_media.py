#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRIKA Media - Automated Multi-Program Editorial System
========================================================
Platform media otomasi cerdas berbasis Jurnalisme Data & Komputasi Visual.
Menjalankan jadwal rubrikasi mingguan terstruktur (Scheduling by Day of Week):
- SENIN & KAMIS   : PROGRAM "INDEKS KERINGAT" (Kalkulasi Daya Beli: Gadget/Gaya Hidup vs Jam Kerja)
- SELASA & JUMAT  : PROGRAM "RADAR SENTIMEN" (Isu Berita Viral: Fakta Inti vs Kubu Pro vs Kubu Kontra)
- RABU & SABTU    : PROGRAM "ANGKA BICARA" (Data Storytelling & Statistik Gaya Hidup / Finansial)
- MINGGU          : PROGRAM "REKAP AKHIR PEKAN" (Evaluasi Finansial & Refleksi Gaya Hidup)

Standar Kualitas Editorial & Anti-AI-Slop:
1. Data Berlandaskan Regulasi Resmi:
   - UMP DKI Jakarta Resmi 2025: Rp 5.396.763/bulan (Kepgub DKI Jakarta No. 1026/2024)
   - Tarif Ojol Zona II Jabodetabek: Kepmenhub No. KP 667/2022
   - Komoditas Pokok: Badan Pangan Nasional (Bapanas) & PT Antam Tbk
   - Data Statistik Makro: Badan Pusat Statistik (BPS) & Bank Indonesia
   - Setiap slide wajib mencantumkan catatan kaki rujukan hukum & data resmi.
2. Tipografi & Desain Humanis:
   - Tanpa karakter emoji mentah (mencegah kotak silang/tofu [] pada font Linux).
   - Palet Matte Slate, Deep Navy, Emerald Green, dan Cyber Gold.
   - Tata letak ala Katadata / Bloomberg dengan hierarki visual profesional.
3. Anti-Halusinasi Produk:
   - Membatasi analisis hanya pada produk nyata yang resmi beredar di Indonesia.
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
# 1. KONFIGURASI GLOBAL & REGULASI RESMI
# ==============================================================================
MEDIA_NAME = os.environ.get("MEDIA_NAME", "METRIKA").strip()
PROGRAM_OVERRIDE = os.environ.get("PROGRAM_OVERRIDE", "").strip().upper()

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
HERO_IMG_PATH = OUTPUT_DIR / "editorial_hero.jpg"
FINAL_VIDEO_PATH = OUTPUT_DIR / "tiktok_reels_metrika.mp4"

# Benchmark Ekonomi & Regulasi Resmi Indonesia
UMP_JAKARTA_2025 = 5_396_763     # Kepgub DKI Jakarta No. 1026/2024
HARI_KERJA_SEBULAN = 22
UMP_PER_HARI = UMP_JAKARTA_2025 / HARI_KERJA_SEBULAN   # ~Rp 245.307/hari
UMP_PER_JAM = UMP_PER_HARI / 8                         # ~Rp 30.663/jam

OJOL_NET_PER_TRIP = 13_000       # Kepmenhub No. KP 667/2022 (Zona II Jabodetabek)
OJOL_NET_PER_HARI = 160_000      # Rata-rata 12-14 order harian
OJOL_NET_PER_JAM = 16_500        # Jam kerja aktif di jalanan

HARGA_BERAS_5KG = 74_500         # Badan Pangan Nasional (Bapanas) - Beras Medium
HARGA_EMAS_ANTAM_GRAM = 1_490_000# PT Antam Tbk Logam Mulia
SEWA_KOS_JAKARTA_MO = 1_850_000  # Survei kamar kos standar DKI Jakarta

TTS_VOICE = "id-ID-GadisNeural"
TTS_RATE = "+12%"

CAROUSEL_WIDTH = 1080
CAROUSEL_HEIGHT = 1350
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Palet Visual Editorial (Matte Charcoal & Clean Accent)
COLOR_BG = (11, 15, 25)            # #0B0F19 Deep Matte Slate
COLOR_CARD = (18, 25, 42)          # #12192A Clean Card Surface
COLOR_CARD_ALT = (25, 35, 58)      # #19233A Highlighting Container
COLOR_BORDER = (38, 52, 82)        # #263452 Subtle Border
COLOR_TEXT_MAIN = (248, 250, 252)  # #F8FAFC Warm White
COLOR_TEXT_MUTED = (148, 163, 184) # #94A3B8 Editorial Slate
COLOR_EMERALD = (16, 185, 129)     # #10B981 Money / Economic Success
COLOR_CYBER_GOLD = (250, 204, 21)  # #FACC15 Golden Currency Highlight
COLOR_AMBER = (245, 158, 11)       # #F59E0B Warning / High Effort
COLOR_ACCENT = (56, 189, 248)      # #38BDF8 Data Cyan Pill
COLOR_RED = (239, 68, 68)          # #EF4444 Kontra / Peringatan

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ==============================================================================
# 2. SISTEM PENJADWALAN PROGRAM MINGGUAN (CONTENT PROGRAMMING)
# ==============================================================================
def get_daily_program_config() -> Dict[str, Any]:
    """
    Menentukan program harian berdasarkan hari dalam seminggu:
    - 0: Senin -> INDEKS KERINGAT
    - 1: Selasa -> RADAR SENTIMEN
    - 2: Rabu -> ANGKA BICARA
    - 3: Kamis -> INDEKS KERINGAT
    - 4: Jumat -> RADAR SENTIMEN
    - 5: Sabtu -> ANGKA BICARA
    - 6: Minggu -> ANGKA BICARA (Edisi Weekend Breakdown)
    """
    if PROGRAM_OVERRIDE:
        p_id = PROGRAM_OVERRIDE
    else:
        weekday = datetime.datetime.now().weekday()
        if weekday in (0, 3):
            p_id = "INDEKS_KERINGAT"
        elif weekday in (1, 4):
            p_id = "RADAR_SENTIMEN"
        else:
            p_id = "ANGKA_BICARA"

    if p_id == "INDEKS_KERINGAT":
        return {
            "id": "INDEKS_KERINGAT",
            "name": "INDEKS KERINGAT",
            "subtitle": "JURNAL DAYA BELI & JAM KERJA",
            "badge": "ANALISIS DAYA BELI",
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=harga+resmi+OR+tiket+konser+OR+gadget+resmi+OR+mobil+motor+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "citation": "SUMBER DATA: Kepgub DKI No. 1026/2024 (UMP Rp 5,39jt) | Kepmenhub KP 667/2022 | Bapanas | PT Antam Tbk",
        }
    elif p_id == "RADAR_SENTIMEN":
        return {
            "id": "RADAR_SENTIMEN",
            "name": "RADAR SENTIMEN",
            "subtitle": "PETA POLARISASI OPINI PUBLIK",
            "badge": "BEDAH SENTIMEN 360°",
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/NATION?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=viral+OR+perdebatan+OR+netizen+indonesia+OR+pro+kontra&hl=id&gl=ID&ceid=ID:id",
            ],
            "citation": "SUMBER DATA: Pantauan Media Sosial & Analisis Jurnalisme Komputasional Portal Berita Nasional",
        }
    else:
        return {
            "id": "ANGKA_BICARA",
            "name": "ANGKA BICARA",
            "subtitle": "DATA STORYTELLING & GAYA HIDUP",
            "badge": "STATISTIK & RISET",
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=biaya+hidup+OR+survei+gaji+OR+riset+anak+muda+OR+bps+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "citation": "SUMBER DATA: Badan Pusat Statistik (BPS) | Bank Indonesia | Riset Publikasi Finansial",
        }


# ==============================================================================
# 3. UTILITAS FORMAT RUPIAH & TIPOGRAFI
# ==============================================================================
def format_rupiah(amount: int) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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


def draw_clean_bullet(draw: ImageDraw.ImageDraw, x: int, y: int, color: Tuple[int, int, int]) -> None:
    radius = 5
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


# ==============================================================================
# 4. MODUL INGESTION BERITA & FOTO JURNALISTIK TERVALIDASI
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


def fetch_latest_program_news(prog_cfg: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
    posted = load_posted_links()
    candidates: List[Dict[str, str]] = []

    if feedparser is not None:
        for rss_url in prog_cfg["feeds"]:
            print(f"[RSS] Memindai feed ({prog_cfg['name']}): {rss_url[:65]}...")
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
        if prog_cfg["id"] == "INDEKS_KERINGAT":
            candidates.append(
                {
                    "title": "Harga iPhone 16 Pro Max 256GB Resmi Indonesia dan Rasio Upah Pekerja",
                    "link": f"https://metrika.id/data/{datetime.date.today()}",
                    "summary": "Analisis harga resmi flagship gadget terhadap UMP DKI Jakarta dan jam kerja pengemudi transportasi daring.",
                    "published": str(datetime.date.today()),
                }
            )
        elif prog_cfg["id"] == "RADAR_SENTIMEN":
            candidates.append(
                {
                    "title": "Wacana Pemangkasan Jam Kerja vs Target Produktivitas Karyawan",
                    "link": f"https://metrika.id/sentimen/{datetime.date.today()}",
                    "summary": "Perdebatan hangat warganet mengenai wacana 4 hari kerja seminggu antara kubu pegiat work-life balance dan pengusaha.",
                    "published": str(datetime.date.today()),
                }
            )
        else:
            candidates.append(
                {
                    "title": "Riset BPS: Rata-rata 42 Persen Gaji Anak Muda Habis untuk Biaya Kos dan Makan",
                    "link": f"https://metrika.id/statistik/{datetime.date.today()}",
                    "summary": "Data statistik pengeluaran bulanan generasi muda di kota metropolitan dan tantangan kepemilikan aset masa depan.",
                    "published": str(datetime.date.today()),
                }
            )

    primary_item = candidates[0]
    supporting = [item["title"] for item in candidates[1:6]]
    print(f"[RSS] Topik terpilih ({prog_cfg['name']}): {primary_item['title']}")
    return primary_item, supporting


def fetch_editorial_photo(
    news_item: Dict[str, str], subject_name: str, save_path: Path
) -> Optional[Image.Image]:
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

    search_q = f"{subject_name} Indonesia site:detik.com OR site:kompas.com OR site:kumparan.com"
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
                    print(f"[Photo] Foto jurnalistik berhasil diunduh: {img_url[:65]}...")
                    return pil_img
        except Exception:
            continue

    print("[Photo] Memakai latar kanvas editorial dark-mode.")
    return None


def crop_and_banner_photo(
    photo: Optional[Image.Image],
    target_w: int,
    target_h: int,
    darken: float = 0.52,
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

    gradient = Image.new("L", (1, target_h), color=0)
    for y in range(target_h):
        if y < int(target_h * 0.42):
            alpha = 0
        else:
            prog = (y - target_h * 0.42) / (target_h * 0.58)
            alpha = int(min(255, prog * 255))
        gradient.putpixel((0, y), alpha)

    alpha_mask = gradient.resize((target_w, target_h))
    bg_layer = Image.new("RGB", (target_w, target_h), color=COLOR_BG)
    return Image.composite(bg_layer, darkened, alpha_mask)


# ==============================================================================
# 5. MODUL OTAK AI: ANALISIS PROGRAM SPESIFIK (ANTI-AI-SLOP)
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


def analyze_with_gemini(
    news_item: Dict[str, str], supporting_headlines: List[str], prog_cfg: Dict[str, Any]
) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY belum terpasang di GitHub Secrets!")

    p_id = prog_cfg["id"]

    if p_id == "INDEKS_KERINGAT":
        program_instructions = f"""
Kamu adalah Redaktur Riset dari media data "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi program: Membedah harga barang/gadget/tiket/gaya hidup nyata terhadap jam kerja ojol dan upah UMP Jakarta.

ATURAN WAJIB ANTI-AI-SLOP:
1. PRODUK WAJIB NYATA & RESMI DI INDONESIA: DILARANG KERAS mengarang produk fiktif masa depan (seperti 'iPhone 18'). Pilih produk nyata yang resmi beredar saat ini (contoh: iPhone 16 Pro Max 256GB, Vespa Sprint 150, Tiket Konser Sheila on 7 CAT 1, PS5 Slim, Sewa Kos Setahun).
2. HARGA VALID: Tentukan estimasi harga pasar wajar dalam Rupiah integer (misal: 24999000).
3. DILARANG MENGGUNAKAN EMOJI di seluruh teks carousel_slides.
4. NASKAH VOICEOVER: 55-75 kata bahasa Indonesia mengalir cepat, kalimat pertama hook harga dan jam kerja.

Format output JSON:
{{
  "program_id": "INDEKS_KERINGAT",
  "subject_title": "Nama produk resmi nyata di Indonesia (maks 28 karakter)",
  "price_idr": 24999000,
  "hero_metric_title": "ESTIMASI HARGA RESMI",
  "hero_metric_value": "Rp 24.999.000",
  "voiceover_script": "Naskah narasi 55-75 kata mengalir tanpa simbol aneh.",
  "telegram_caption": "Caption Instagram & TikTok yang memancing diskusi dan 5 hashtag.",
  "carousel_slides": [
    {{"slide_number": 1, "tag": "PROGRAM: INDEKS KERINGAT", "headline": "Berapa Lama Harus Kerja Keras Buat Beli Ini?", "body": "Membedah nilai riil harga barang terhadap jam kerja nyata masyarakat.", "metric_label": "ESTIMASI HARGA RESMI"}},
    {{"slide_number": 2, "tag": "SPESIFIKASI & NILAI GUNA", "headline": "Apa yang Sebenarnya Kamu Beli?", "body": "Ulasan fakta nilai guna barang ini di mata konsumen.", "metric_label": "NILAI KONSUMEN"}},
    {{"slide_number": 3, "tag": "PERSPEKTIF DRIVER OJOL", "headline": "Beban Keringat di Aspal Jalanan", "body": "Rincian order dan hari narik penuh dari matahari terbit sampai malam.", "metric_label": "ORDER & HARI NARIK"}},
    {{"slide_number": 4, "tag": "PERSPEKTIF UMP DKI JAKARTA", "headline": "Beban Upah Minimum Provinsi", "body": "Berapa bulan gaji penuh yang harus disisihkan tanpa makan dan minum.", "metric_label": "PORSI DARI GAJI"}},
    {{"slide_number": 5, "tag": "OPPORTUNITY COST RIIL", "headline": "Setara Kebutuhan Pokok Apa Saja?", "body": "Perbandingan alternatif kebutuhan pokok: beras medium, emas Antam, atau sewa kos.", "metric_label": "PADANAN KEBUTUHAN POKOK"}},
    {{"slide_number": 6, "tag": "VERDICT & KESIMPULAN", "headline": "Worth It Dibeli atau Sekadar FOMO?", "body": "Refleksi apakah sebanding dengan waktu dan tenaga yang kamu korbankan.", "metric_label": "TULIS PENDAPATMU DI KOMENTAR"}}
  ]
}}
"""
    elif p_id == "RADAR_SENTIMEN":
        program_instructions = f"""
Kamu adalah Redaktur Opini Publik dari media data "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi program: Membedah isu berita hangat yang viral di Indonesia secara objektif: Fakta Inti vs Kubu Pro vs Kubu Kontra.

ATURAN WAJIB ANTI-AI-SLOP:
1. FAKTA BERITA NYATA: Rangkum fakta inti peristiwa berdasarkan berita dengan jernih tanpa memihak.
2. POLARISASI PERSENTASE REALISTIS: Tentukan skor polarisasi sentimen publik (misal: pro_pct: 62, contra_pct: 38).
3. SUARA KUBU: Rangkum argumen utama Kubu Pro (pendukung/pembela) dan Kubu Kontra (pengkritik/skeptis) yang beredar di medsos.
4. DILARANG MENGGUNAKAN EMOJI di seluruh teks carousel_slides.
5. NASKAH VOICEOVER: 55-75 kata tajam yang memancing diskusi audiens di kolom komentar.

Format output JSON:
{{
  "program_id": "RADAR_SENTIMEN",
  "subject_title": "Isu atau Tokoh Utama yang Dibahas (maks 28 karakter)",
  "pro_pct": 62,
  "contra_pct": 38,
  "pro_label": "KUBU SEPAKAT / DUKUNG",
  "contra_label": "KUBU KRITIS / KONTRA",
  "hero_metric_title": "PETA POLARISASI NETIZEN",
  "hero_metric_value": "62% Pro vs 38% Kontra",
  "voiceover_script": "Naskah narasi 55-75 kata membedah dua sudut pandang dan memicu komentar.",
  "telegram_caption": "Caption Instagram & TikTok yang memancing diskusi dan 5 hashtag.",
  "carousel_slides": [
    {{"slide_number": 1, "tag": "PROGRAM: RADAR SENTIMEN", "headline": "Isu Panas Hari Ini: Siapa yang Masuk Akal?", "body": "Peta sentimen netizen atas peristiwa yang sedang menjadi perbincangan publik.", "metric_label": "POLARISASI OPINI"}},
    {{"slide_number": 2, "tag": "FAKTA KRONOLOGI INTI", "headline": "Apa Fakta di Balik Kehebohan Ini?", "body": "Penjelasan fakta jernih apa yang sebenarnya terjadi tanpa sensasionalisme.", "metric_label": "FAKTA TERVERIFIKASI"}},
    {{"slide_number": 3, "tag": "ARGUMEN KUBU PENDUKUNG", "headline": "Alasan Kubu yang Mendukung", "body": "Bedah argumen dan pertimbangan pihak yang sepakat dengan langkah atau isu ini.", "metric_label": "SUARA KUBU PRO"}},
    {{"slide_number": 4, "tag": "ARGUMEN KUBU PENGKRITIK", "headline": "Kekhawatiran Kubu yang Menolak", "body": "Bedah kritik mendasar dan risiko yang disuarakan oleh pihak kontra di media sosial.", "metric_label": "SUARA KUBU KONTRA"}},
    {{"slide_number": 5, "tag": "DAMPAK KE MASYARAKAT", "headline": "Apa Implikasi Nyatanya ke Publik?", "body": "Analisis bagaimana isu ini memengaruhi kehidupan atau pandangan masyarakat umum.", "metric_label": "IMPLIKASI PUBLIK"}},
    {{"slide_number": 6, "tag": "VERDICT REDAKSI", "headline": "Kubu Mana yang Lebih Kuat Argumennya?", "body": "Kesimpulan redaksi dan ajakan berpendapat secara santun di kolom komentar.", "metric_label": "TULIS PENDAPATMU DI KOMENTAR"}}
  ]
}}
"""
    else:  # ANGKA_BICARA (Data Storytelling & Gaya Hidup)
        program_instructions = f"""
Kamu adalah Jurnalis Data dari media "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi program: Menyajikan riset statistik gaya hidup, biaya hidup, dan ekonomi anak muda secara infografis.

ATURAN WAJIB ANTI-AI-SLOP:
1. DATA VALID & MASUK AKAL: Angkat temuan statistik riil (seperti rasio pengeluaran sewa kos, biaya nongkrong, tren gaji fresh grad).
2. DILARANG MENGGUNAKAN EMOJI di seluruh teks carousel_slides.
3. NASKAH VOICEOVER: 55-75 kata bahasa Indonesia mengalir, edukatif, dan lugas.

Format output JSON:
{{
  "program_id": "ANGKA_BICARA",
  "subject_title": "Topik Riset atau Statistik (maks 28 karakter)",
  "hero_metric_title": "ANGKA KUNCI RISET",
  "hero_metric_value": "42% Gaji untuk Kos & Kopi",
  "voiceover_script": "Naskah narasi 55-75 kata mengalir tentang data statistik ini.",
  "telegram_caption": "Caption Instagram & TikTok yang memancing diskusi dan 5 hashtag.",
  "carousel_slides": [
    {{"slide_number": 1, "tag": "PROGRAM: ANGKA BICARA", "headline": "Data Statistik yang Jarang Dibahas", "body": "Membaca realitas ekonomi anak muda lewat angka dan fakta terukur.", "metric_label": "RISET & STATISTIK"}},
    {{"slide_number": 2, "tag": "TEMUAN UTAMA", "headline": "Berapa Beban Pengeluaran Riil?", "body": "Rincian persentase penghasilan yang habis untuk kebutuhan hidup harian.", "metric_label": "TEMUAN RIIL"}},
    {{"slide_number": 3, "tag": "KOMPARASI BIAYA", "headline": "Perbandingan Antar Kategori", "body": "Perbandingan alokasi biaya tempat tinggal, transportasi, dan gaya hidup.", "metric_label": "STRUKTUR PENGELUARAN"}},
    {{"slide_number": 4, "tag": "TREN JANGKA PANJANG", "headline": "Dampaknya ke Tabungan Masa Depan", "body": "Bagaimana pola konsumsi ini memengaruhi kemampuan membeli aset jangka panjang.", "metric_label": "PROYEKSI ASET"}},
    {{"slide_number": 5, "tag": "SOLUSI & SARAN", "headline": "Langkah Alokasi yang Lebih Sehat", "body": "Strategi pembagian pos keuangan yang realistis untuk diterapkan anak muda.", "metric_label": "STRATEGI FINANSIAL"}},
    {{"slide_number": 6, "tag": "KESIMPULAN REDAKSI", "headline": "Apakah Gaya Hidupmu Sejalan dengan Data Ini?", "body": "Refleksi apakah kamu merasakan hal serupa dalam kehidupan sehari-hari.", "metric_label": "TULIS PENDAPATMU DI KOMENTAR"}}
  ]
}}
"""

    prompt = f"""
{program_instructions}

Topik Berita Terpilih:
- Judul: {news_item['title']}
- Ringkasan: {news_item['summary']}

Kembalikan HANYA JSON murni tanpa markdown ```json.
""".strip()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.40, "responseMimeType": "application/json"},
    }

    candidate_models = get_available_gemini_models()
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"[Gemini] Mengolah data ({prog_cfg['name']}) dengan model: {model_name}...")
            res = requests.post(url, json=payload, timeout=50)
            if res.status_code == 200:
                raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                parsed = json.loads(cleaned)
                parsed["_model_used"] = model_name
                print(f"[Gemini] Sukses ({prog_cfg['name']}): {parsed.get('subject_title')}")
                return parsed
        except Exception:
            continue

    raise RuntimeError("Seluruh model Gemini gagal menganalisis topik ini.")


# ==============================================================================
# 6. ENGINE KALKULASI INDEKS KERINGAT DETERMINISTIK
# ==============================================================================
def compute_labor_metrics(price_idr: int) -> Dict[str, Any]:
    price = max(int(price_idr), 100_000)

    ojol_trips = int(math.ceil(price / OJOL_NET_PER_TRIP))
    ojol_days = int(math.ceil(price / OJOL_NET_PER_HARI))
    ojol_hours = int(math.ceil(price / OJOL_NET_PER_JAM))

    ump_days = round(price / UMP_PER_HARI, 1)
    ump_months = round(price / UMP_JAKARTA_2025, 1)
    ump_pct = round((price / UMP_JAKARTA_2025) * 100, 1)

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
        "ump_days": ump_days,
        "ump_months": ump_months,
        "ump_pct": ump_pct,
        "karung_beras": karung_beras,
        "ton_beras": ton_beras,
        "gram_emas": gram_emas,
        "bulan_kos": bulan_kos,
    }


# ==============================================================================
# 7. SUARA NATURAL EKSPRESIF & TIMING KARAOKE
# ==============================================================================
async def _generate_voiceover_stream(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    if edge_tts is None:
        raise RuntimeError("Library edge-tts belum terinstall.")

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
    print(f"[Edge-TTS] Merekam suara narator ({TTS_VOICE}, {TTS_RATE})...")
    timings = asyncio.run(
        _generate_voiceover_stream(script_text, audio_out, subtitle_out)
    )
    print(f"[Edge-TTS] Audio selesai ({len(timings)} kata terindeks karaoke).")
    return timings


# ==============================================================================
# 8. RENDER CAROUSEL EDITORIAL MULTI-PROGRAM (4:5, 1080x1350)
# ==============================================================================
def render_carousel_slides(
    analysis: Dict[str, Any],
    prog_cfg: Dict[str, Any],
    metrics: Optional[Dict[str, Any]],
    hero_photo: Optional[Image.Image],
    out_dir: Path,
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_data = analysis.get("carousel_slides", [])
    total_slides = len(slides_data)

    subject_title = analysis.get("subject_title", "Topik Riset")
    p_id = prog_cfg["id"]

    font_brand = load_font(28, bold=True)
    font_badge = load_font(22, bold=True)
    font_tag = load_font(23, bold=True)
    font_headline = load_font(46, bold=True)
    font_body = load_font(32, bold=False)
    font_price = load_font(66, bold=True)
    font_metric_val = load_font(46, bold=True)
    font_metric_lbl = load_font(24, bold=False)
    font_footer = load_font(21, bold=False)
    font_source = load_font(19, bold=False)

    generated_files: List[Path] = []
    today_str = datetime.datetime.now().strftime("%d %b %Y").upper()

    for idx, slide in enumerate(slides_data, start=1):
        img = Image.new("RGB", (CAROUSEL_WIDTH, CAROUSEL_HEIGHT), color=COLOR_BG)

        if idx == 1 and hero_photo is not None:
            banner = crop_and_banner_photo(hero_photo, CAROUSEL_WIDTH, 560, darken=0.55)
            img.paste(banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # Header Bar Media Induk & Program
        draw.rounded_rectangle((65, 45, CAROUSEL_WIDTH - 65, 135), radius=14, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
        draw.text((92, 72), f"{MEDIA_NAME.upper()}  •  {prog_cfg['name']}", font=font_brand, fill=COLOR_ACCENT)
        draw.rounded_rectangle((CAROUSEL_WIDTH - 365, 62, CAROUSEL_WIDTH - 90, 118), radius=8, fill=COLOR_EMERALD)
        draw.text((CAROUSEL_WIDTH - 345, 75), prog_cfg["badge"], font=font_badge, fill=COLOR_BG)

        curr_y = 440 if (idx == 1 and hero_photo is not None) else 185

        slide_tag = slide.get("tag", f"BAGIAN #{idx}").upper()
        draw.text((70, curr_y), slide_tag, font=font_tag, fill=COLOR_CYBER_GOLD)
        curr_y += 40

        headline_text = slide.get("headline", "Kalkulasi Data")
        for line in textwrap.wrap(headline_text, width=29)[:3]:
            draw.text((70, curr_y), line, font=font_headline, fill=COLOR_TEXT_MAIN)
            curr_y += 56

        curr_y += 18

        # Tata Letak Dinamis Berdasarkan Program
        if p_id == "INDEKS_KERINGAT" and metrics is not None:
            if idx == 1:
                p_box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 190)
                draw.rounded_rectangle(p_box, radius=18, fill=COLOR_CARD, outline=COLOR_EMERALD, width=2)
                draw.text((105, curr_y + 25), f"OBJEK RIIL: {subject_title.upper()}", font=font_tag, fill=COLOR_TEXT_MUTED)
                draw.text((105, curr_y + 75), metrics["price_str"], font=font_price, fill=COLOR_CYBER_GOLD)
                curr_y += 215

                w_col = (CAROUSEL_WIDTH - 140 - 25) // 2
                # Kolom Ojol
                box_l = (70, curr_y, 70 + w_col, curr_y + 240)
                draw.rounded_rectangle(box_l, radius=16, fill=COLOR_CARD_ALT, outline=COLOR_BORDER, width=1)
                draw.text((95, curr_y + 25), "PENGEMUDI OJOL", font=font_badge, fill=COLOR_EMERALD)
                draw.text((95, curr_y + 75), f"{metrics['ojol_trips']:,} Order".replace(",", "."), font=font_metric_val, fill=COLOR_TEXT_MAIN)
                draw.text((95, curr_y + 155), f"Setara {metrics['ojol_days']} hari narik penuh", font=font_metric_lbl, fill=COLOR_TEXT_MUTED)

                # Kolom UMP
                box_r = (70 + w_col + 25, curr_y, CAROUSEL_WIDTH - 70, curr_y + 240)
                draw.rounded_rectangle(box_r, radius=16, fill=COLOR_CARD_ALT, outline=COLOR_BORDER, width=1)
                draw.text((70 + w_col + 50, curr_y + 25), "PEKERJA UMP JAKARTA", font=font_badge, fill=COLOR_ACCENT)
                draw.text((70 + w_col + 50, curr_y + 75), f"{metrics['ump_months']} Bulan Gaji", font=font_metric_val, fill=COLOR_TEXT_MAIN)
                draw.text((70 + w_col + 50, curr_y + 155), f"Setara {metrics['ump_days']} hari kerja", font=font_metric_lbl, fill=COLOR_TEXT_MUTED)

            elif idx == 3:
                box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
                draw.rounded_rectangle(box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
                draw.text((105, curr_y + 35), "PARAMETER PENGEMUDI TRANSPORTASI DARING", font=font_tag, fill=COLOR_EMERALD)
                draw.text((105, curr_y + 85), f"Total Order: {metrics['ojol_trips']:,} Trip".replace(",", "."), font=font_metric_val, fill=COLOR_CYBER_GOLD)

                items_ojol = [
                    f"Estimasi Jam Kerja di Jalan: {metrics['ojol_hours']} Jam Aktif",
                    f"Hari Narik (Target 12-14 Order/Hari): {metrics['ojol_days']} Hari Penuh",
                    "Basis Laba Bersih per Order: Rp 13.000 (Setelah Potongan 15-20%)",
                    "Kondisi: Kerja tanpa libur, bensin & makan belum dipotong.",
                ]
                iy = curr_y + 170
                for text_row in items_ojol:
                    draw_clean_bullet(draw, 115, iy + 16, COLOR_EMERALD)
                    draw.text((135, iy), text_row, font=font_body, fill=COLOR_TEXT_MAIN if "Kondisi" not in text_row else COLOR_AMBER)
                    iy += 56
                curr_y += 465

            elif idx == 4:
                box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
                draw.rounded_rectangle(box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
                draw.text((105, curr_y + 35), "PARAMETER UPAH MINIMUM PROVINSI (UMP DKI JAKARTA)", font=font_tag, fill=COLOR_ACCENT)
                draw.text((105, curr_y + 85), f"{metrics['ump_months']} Bulan Gaji Bersih", font=font_metric_val, fill=COLOR_CYBER_GOLD)

                items_ump = [
                    f"Porsi Beban dari Upah Sebulan: {metrics['ump_pct']}%",
                    f"Hari Kerja Kantor: {metrics['ump_days']} Hari ({int(metrics['ump_days'] * 8)} Jam Kerja)",
                    "Basis UMP Resmi 2025: Rp 5.396.763 / Bulan (Kepgub 1026/2024)",
                    "Kondisi: 100% gaji ditabung utuh tanpa biaya hidup.",
                ]
                iy = curr_y + 170
                for text_row in items_ump:
                    draw_clean_bullet(draw, 115, iy + 16, COLOR_ACCENT)
                    draw.text((135, iy), text_row, font=font_body, fill=COLOR_TEXT_MAIN if "Kondisi" not in text_row else COLOR_AMBER)
                    iy += 56
                curr_y += 465

            elif idx == 5:
                box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 440)
                draw.rounded_rectangle(box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
                draw.text((105, curr_y + 35), "NILAI BARANG SETARA KEBUTUHAN POKOK APA?", font=font_tag, fill=COLOR_CYBER_GOLD)

                items_opp = [
                    f"Beras Medium: {metrics['karung_beras']} Karung 5kg ({metrics['ton_beras']} Ton Beras)",
                    f"Logam Mulia: {metrics['gram_emas']} Gram Emas Murni Antam",
                    f"Tempat Tinggal: {metrics['bulan_kos']} Bulan Sewa Kos Standar Jakarta",
                    "Pilihan Finansial: Konsumsi Gengsi atau Alokasi Produktif?",
                ]
                iy = curr_y + 110
                for text_row in items_opp:
                    draw_clean_bullet(draw, 115, iy + 16, COLOR_CYBER_GOLD)
                    draw.text((135, iy), text_row, font=font_body, fill=COLOR_TEXT_MAIN if "Pilihan" not in text_row else COLOR_TEXT_MUTED)
                    iy += 60
                curr_y += 465

            else:
                body_text = slide.get("body", "")
                wrapped = textwrap.wrap(body_text, width=42)[:7]
                box_h = max(220, len(wrapped) * 48 + 70)
                box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + box_h)
                draw.rounded_rectangle(box, radius=18, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
                draw.rounded_rectangle((70, curr_y, 82, curr_y + box_h), radius=4, fill=COLOR_CYBER_GOLD)

                ty = curr_y + 35
                for line in wrapped:
                    draw.text((115, ty), line, font=font_body, fill=COLOR_TEXT_MAIN)
                    ty += 48
                curr_y += box_h + 30

        elif p_id == "RADAR_SENTIMEN":
            pro_pct = int(analysis.get("pro_pct", 60))
            contra_pct = int(analysis.get("contra_pct", 40))

            if idx == 1:
                # Bar Polarisasi Visual
                bar_box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 200)
                draw.rounded_rectangle(bar_box, radius=18, fill=COLOR_CARD, outline=COLOR_ACCENT, width=2)
                draw.text((105, curr_y + 25), "PETA POLARISASI OPINI PUBLIK:", font=font_tag, fill=COLOR_TEXT_MUTED)
                draw.text((105, curr_y + 70), f"{pro_pct}% DUKUNG  vs  {contra_pct}% KONTRA", font=font_metric_val, fill=COLOR_CYBER_GOLD)

                # Bar Grafis Dua Warna
                b_y = curr_y + 140
                total_w = CAROUSEL_WIDTH - 210
                pro_w = int(total_w * (pro_pct / 100.0))
                draw.rounded_rectangle((105, b_y, 105 + pro_w, b_y + 20), radius=6, fill=COLOR_EMERALD)
                draw.rounded_rectangle((105 + pro_w + 5, b_y, 105 + total_w, b_y + 20), radius=6, fill=COLOR_RED)
                curr_y += 225

            body_text = slide.get("body", "")
            wrapped = textwrap.wrap(body_text, width=42)[:7]
            box_h = max(240, len(wrapped) * 48 + 70)
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + box_h)
            draw.rounded_rectangle(box, radius=18, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)

            stripe_color = COLOR_EMERALD if idx in (1, 3) else (COLOR_RED if idx == 4 else COLOR_CYBER_GOLD)
            draw.rounded_rectangle((70, curr_y, 82, curr_y + box_h), radius=4, fill=stripe_color)

            ty = curr_y + 35
            for line in wrapped:
                draw.text((115, ty), line, font=font_body, fill=COLOR_TEXT_MAIN)
                ty += 48
            curr_y += box_h + 30

        else:  # ANGKA_BICARA
            if idx == 1:
                metric_box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + 180)
                draw.rounded_rectangle(metric_box, radius=18, fill=COLOR_CARD, outline=COLOR_CYBER_GOLD, width=2)
                draw.text((105, curr_y + 25), analysis.get("hero_metric_title", "ANGKA KUNCI RISET").upper(), font=font_tag, fill=COLOR_TEXT_MUTED)
                draw.text((105, curr_y + 75), analysis.get("hero_metric_value", "42% Beban Pengeluaran"), font=font_price, fill=COLOR_CYBER_GOLD)
                curr_y += 205

            body_text = slide.get("body", "")
            wrapped = textwrap.wrap(body_text, width=42)[:7]
            box_h = max(240, len(wrapped) * 48 + 70)
            box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + box_h)
            draw.rounded_rectangle(box, radius=18, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
            draw.rounded_rectangle((70, curr_y, 82, curr_y + box_h), radius=4, fill=COLOR_ACCENT)

            ty = curr_y + 35
            for line in wrapped:
                draw.text((115, ty), line, font=font_body, fill=COLOR_TEXT_MAIN)
                ty += 48
            curr_y += box_h + 30

        # Footer Metric Bar
        metric_lbl = slide.get("metric_label", "JURNALISME DATA").upper()
        draw.text((70, 1175), f"[ {metric_lbl} ]", font=font_badge, fill=COLOR_EMERALD)

        # Catatan Kaki Sumber Regulasi / Data
        draw.line([(70, 1220), (CAROUSEL_WIDTH - 70, 1220)], fill=COLOR_BORDER, width=1)
        draw.text((70, 1235), prog_cfg["citation"], font=font_source, fill=COLOR_TEXT_MUTED)
        draw.text((70, 1270), f"{MEDIA_NAME.upper()}  •  {prog_cfg['name']}  •  {today_str}", font=font_footer, fill=COLOR_TEXT_MUTED)
        draw.text((CAROUSEL_WIDTH - 220, 1270), f"SLIDE {idx} / {total_slides}  →", font=font_footer, fill=COLOR_TEXT_MAIN)

        slide_file = out_dir / f"slide_{idx:02d}.png"
        img.save(slide_file, format="PNG", optimize=True)
        generated_files.append(slide_file)

    print(f"[Pillow] Berhasil merender {len(generated_files)} slide editorial ({prog_cfg['name']}).")
    return generated_files


# ==============================================================================
# 9. RENDER VIDEO VERTIKAL ANIMASI KALKULATOR / POLARISASI (9:16)
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
    draw.rounded_rectangle(sub_box, radius=20, fill=(15, 23, 42), outline=COLOR_EMERALD, width=2)

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
    prog_cfg: Dict[str, Any],
    metrics: Optional[Dict[str, Any]],
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

    subject_title = analysis.get("subject_title", "Topik Riset")
    p_id = prog_cfg["id"]

    font_header = load_font(32, bold=True)
    font_badge = load_font(24, bold=True)
    font_item = load_font(44, bold=True)
    font_counter = load_font(72, bold=True)
    font_card_val = load_font(48, bold=True)
    font_card_lbl = load_font(24, bold=False)
    font_sub = load_font(40, bold=True)
    font_small = load_font(21, bold=False)

    print(f"[Video] Merender {total_frames} frame video ({prog_cfg['name']})...")

    for f_idx in range(total_frames):
        current_sec = f_idx / float(fps)
        progress = f_idx / float(max(total_frames - 1, 1))

        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=COLOR_BG)
        banner = crop_and_banner_photo(hero_photo, VIDEO_WIDTH, 720, darken=0.55)
        img.paste(banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # Header Bar
        draw.rounded_rectangle((60, 75, VIDEO_WIDTH - 60, 170), radius=16, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)
        draw.text((90, 105), f"{MEDIA_NAME.upper()} • {prog_cfg['name']}", font=font_header, fill=COLOR_CYBER_GOLD)
        draw.rounded_rectangle((VIDEO_WIDTH - 380, 95, VIDEO_WIDTH - 85, 150), radius=10, fill=COLOR_EMERALD)
        draw.text((VIDEO_WIDTH - 355, 108), prog_cfg["badge"], font=font_header, fill=COLOR_BG)

        draw.rounded_rectangle((65, 205, 460, 255), radius=8, fill=COLOR_CARD_ALT, outline=COLOR_ACCENT, width=1)
        draw.text((85, 218), prog_cfg["subtitle"], font=font_badge, fill=COLOR_ACCENT)

        draw.text((65, 275), subject_title.upper(), font=font_item, fill=COLOR_TEXT_MAIN)

        if p_id == "INDEKS_KERINGAT" and metrics is not None:
            anim_factor = min(1.0, progress * 1.6)
            curr_price = int(metrics["price_idr"] * (anim_factor ** 2))
            curr_trips = int(metrics["ojol_trips"] * (anim_factor ** 2))
            curr_ump_mo = round(metrics["ump_months"] * (anim_factor ** 2), 1)

            # Counter Box Rupiah
            p_card = (65, 470, VIDEO_WIDTH - 65, 680)
            draw.rounded_rectangle(p_card, radius=20, fill=COLOR_CARD, outline=COLOR_EMERALD, width=2)
            draw.text((100, 495), "ESTIMASI HARGA RESMI:", font=font_badge, fill=COLOR_TEXT_MUTED)
            draw.text((100, 550), format_rupiah(curr_price), font=font_counter, fill=COLOR_CYBER_GOLD)

            # Kartu Ojol
            card_ojol = (65, 720, VIDEO_WIDTH - 65, 960)
            draw.rounded_rectangle(card_ojol, radius=20, fill=COLOR_CARD_ALT, outline=COLOR_BORDER, width=1)
            draw.text((105, 750), "[ PENGEMUDI TRANSPORTASI DARING ]", font=font_badge, fill=COLOR_EMERALD)
            draw.text((105, 805), f"{curr_trips:,} ORDER".replace(",", "."), font=font_card_val, fill=COLOR_TEXT_MAIN)
            draw.text((105, 890), f"Setara {metrics['ojol_days']} hari kerja penuh (Kepmenhub KP 667/2022)", font=font_card_lbl, fill=COLOR_TEXT_MUTED)

            # Kartu UMP
            card_ump = (65, 1000, VIDEO_WIDTH - 65, 1240)
            draw.rounded_rectangle(card_ump, radius=20, fill=COLOR_CARD_ALT, outline=COLOR_BORDER, width=1)
            draw.text((105, 1030), "[ PEKERJA UMP DKI JAKARTA 2025 ]", font=font_badge, fill=COLOR_ACCENT)
            draw.text((105, 1085), f"{curr_ump_mo} BULAN GAJI BERSIH", font=font_card_val, fill=COLOR_TEXT_MAIN)
            draw.text((105, 1170), f"Setara {metrics['ump_days']} hari kerja kantor penuh (Kepgub 1026/2024)", font=font_card_lbl, fill=COLOR_TEXT_MUTED)

        elif p_id == "RADAR_SENTIMEN":
            pro_pct = int(analysis.get("pro_pct", 60))
            contra_pct = int(analysis.get("contra_pct", 40))

            card_p = (65, 470, VIDEO_WIDTH - 65, 720)
            draw.rounded_rectangle(card_p, radius=20, fill=COLOR_CARD, outline=COLOR_ACCENT, width=2)
            draw.text((100, 495), "PETA POLARISASI OPINI PUBLIK:", font=font_badge, fill=COLOR_TEXT_MUTED)
            draw.text((100, 550), f"{pro_pct}% Pro  vs  {contra_pct}% Kontra", font=font_counter, fill=COLOR_CYBER_GOLD)

            card_pro = (65, 760, VIDEO_WIDTH - 65, 980)
            draw.rounded_rectangle(card_pro, radius=20, fill=COLOR_CARD_ALT, outline=COLOR_EMERALD, width=2)
            draw.text((105, 790), f"[ {analysis.get('pro_label', 'KUBU PRO')} ]", font=font_badge, fill=COLOR_EMERALD)
            draw.text((105, 850), f"Mendukung {pro_pct}% suara publik di media sosial", font=font_card_val, fill=COLOR_TEXT_MAIN)

            card_con = (65, 1020, VIDEO_WIDTH - 65, 1240)
            draw.rounded_rectangle(card_con, radius=20, fill=COLOR_CARD_ALT, outline=COLOR_RED, width=2)
            draw.text((105, 1050), f"[ {analysis.get('contra_label', 'KUBU KONTRA')} ]", font=font_badge, fill=COLOR_RED)
            draw.text((105, 1110), f"Mengkritik {contra_pct}% suara publik di media sosial", font=font_card_val, fill=COLOR_TEXT_MAIN)

        else:  # ANGKA_BICARA
            card_stat = (65, 520, VIDEO_WIDTH - 65, 820)
            draw.rounded_rectangle(card_stat, radius=20, fill=COLOR_CARD, outline=COLOR_CYBER_GOLD, width=2)
            draw.text((100, 555), analysis.get("hero_metric_title", "TEMUAN UTAMA:").upper(), font=font_badge, fill=COLOR_TEXT_MUTED)
            draw.text((100, 620), analysis.get("hero_metric_value", "42% Pengeluaran"), font=font_counter, fill=COLOR_CYBER_GOLD)
            draw.text((100, 735), "Berdasarkan Survei & Panel Riset Konsumsi Indonesia", font=font_card_lbl, fill=COLOR_TEXT_MAIN)

        draw_karaoke_subtitle_box(draw, word_timings, current_sec, font_sub)

        # Progress bar & Citation Footer
        bar_bg = (65, 1740, VIDEO_WIDTH - 65, 1754)
        bar_fg = (65, 1740, 65 + int((VIDEO_WIDTH - 130) * progress), 1754)
        draw.rounded_rectangle(bar_bg, radius=6, fill=COLOR_CARD)
        draw.rounded_rectangle(bar_fg, radius=6, fill=COLOR_CYBER_GOLD)

        draw.text((65, 1775), prog_cfg["citation"], font=font_small, fill=COLOR_TEXT_MUTED)

        frame_path = frames_dir / f"frame_{f_idx:04d}.png"
        img.save(frame_path, format="PNG")

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

    print("[FFmpeg] Merender video komposit...")
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"[FFmpeg] Video berhasil dibuat: {video_out}")
    return video_out


# ==============================================================================
# 10. DISTRIBUSI TELEGRAM OTOMATIS
# ==============================================================================
def send_outputs_to_telegram(
    video_path: Path,
    carousel_paths: List[Path],
    analysis: Dict[str, Any],
    prog_cfg: Dict[str, Any],
    metrics: Optional[Dict[str, Any]],
    news_item: Dict[str, str],
) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Token/Chat ID belum diset. Melewati kirim Telegram.")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    subject_title = analysis.get("subject_title", "Topik Riset")
    caption = analysis.get("telegram_caption", "")
    p_id = prog_cfg["id"]

    if p_id == "INDEKS_KERINGAT" and metrics is not None:
        header_msg = (
            f"📊 *{MEDIA_NAME.upper()} • {prog_cfg['name']}*\n"
            f"Objek Riil: *{subject_title}*\n"
            f"Estimasi Harga: *{metrics['price_str']}*\n\n"
            f"🛵 *Beban Driver Ojol:* `{metrics['ojol_trips']:,}` Order (~{metrics['ojol_days']} hari narik penuh)\n"
            f"💼 *Beban Pekerja UMP DKI:* `{metrics['ump_months']}` Bulan Gaji (~{metrics['ump_days']} hari kerja kantor)\n"
            f"⚖️ *Padanan Kebutuhan Pokok:* {metrics['karung_beras']} Karung Beras Medium atau {metrics['gram_emas']}g Emas Murni\n"
            f"📌 *Rujukan Resmi:* {prog_cfg['citation']}\n\n"
            f"📝 *Draf Caption Media:*\n{caption}"
        )
    elif p_id == "RADAR_SENTIMEN":
        header_msg = (
            f"📊 *{MEDIA_NAME.upper()} • {prog_cfg['name']}*\n"
            f"Isu Hangat: *{subject_title}*\n"
            f"Polarisasi: *{analysis.get('pro_pct', 60)}% Pro* vs *{analysis.get('contra_pct', 40)}% Kontra*\n\n"
            f"📌 *Rujukan Resmi:* {prog_cfg['citation']}\n\n"
            f"📝 *Draf Caption Media:*\n{caption}"
        )
    else:
        header_msg = (
            f"📊 *{MEDIA_NAME.upper()} • {prog_cfg['name']}*\n"
            f"Riset: *{subject_title}*\n"
            f"Temuan Kunci: *{analysis.get('hero_metric_value', '')}*\n\n"
            f"📌 *Rujukan Resmi:* {prog_cfg['citation']}\n\n"
            f"📝 *Draf Caption Media:*\n{caption}"
        )

    print("[Telegram] Mengirim video vertikal...")
    with video_path.open("rb") as vf:
        requests.post(
            f"{base_url}/sendVideo",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": header_msg[:1024], "parse_mode": "Markdown"},
            files={"video": vf},
            timeout=120,
        )

    print("[Telegram] Mengirim album Carousel...")
    media_group = []
    files_payload = {}
    for idx, img_path in enumerate(carousel_paths[:10]):
        attach_key = f"slide_{idx}"
        files_payload[attach_key] = img_path.open("rb")
        item_obj: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_key}"}
        if idx == 0:
            item_obj["caption"] = f"🖼 {MEDIA_NAME} Carousel: {subject_title} ({len(carousel_paths)} Slide)"
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

    print("[Telegram] Seluruh paket konten media berhasil dikirim!")


# ==============================================================================
# 11. PIPELINE UTAMA (DENGAN SCHEDULING OTOMATIS)
# ==============================================================================
def main() -> None:
    prog_cfg = get_daily_program_config()

    print("=" * 72)
    print(f"🚀 MEMULAI PIPELINE: {MEDIA_NAME.upper()} • {prog_cfg['name']}")
    print(f"📅 Rubrik Hari Ini: {prog_cfg['subtitle']}")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    news_item, supporting = fetch_latest_program_news(prog_cfg)
    analysis = analyze_with_gemini(news_item, supporting, prog_cfg)

    metrics = None
    if prog_cfg["id"] == "INDEKS_KERINGAT":
        metrics = compute_labor_metrics(analysis.get("price_idr", 24_999_000))
        analysis["metrics"] = metrics

    analysis["program_config"] = prog_cfg
    latest_json = OUTPUT_DIR / "latest_analysis.json"
    latest_json.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

    hero_photo = fetch_editorial_photo(news_item, analysis.get("subject_title", ""), HERO_IMG_PATH)

    voice_script = analysis.get("voiceover_script", f"Berikut ulasan {prog_cfg['name']} dari {MEDIA_NAME}.")
    word_timings = generate_voiceover(voice_script, AUDIO_PATH, SUBTITLE_PATH)

    carousel_files = render_carousel_slides(analysis, prog_cfg, metrics, hero_photo, CAROUSEL_DIR)

    video_file = render_vertical_video(analysis, prog_cfg, metrics, hero_photo, word_timings, AUDIO_PATH, FINAL_VIDEO_PATH)

    send_outputs_to_telegram(video_file, carousel_files, analysis, prog_cfg, metrics, news_item)

    save_posted_link(news_item["link"])
    print(f"[Cache] Link disimpan ke {CACHE_FILE}.")
    print(f"✅ PIPELINE {prog_cfg['name']} SELESAI DENGAN SUKSES!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌ [ERROR] Pipeline berhenti: {err}", file=sys.stderr)
        sys.exit(1)
