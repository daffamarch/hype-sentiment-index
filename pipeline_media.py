#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRIKA Media - Automated Multi-Program Editorial System
========================================================
Platform media otomasi cerdas berbasis Jurnalisme Data & Komputasi Visual.
Menjalankan jadwal rubrikasi mingguan terstruktur:
- SENIN & KAMIS   : PROGRAM "INDEKS KERINGAT" (Kalkulasi Daya Beli: Gadget/Gaya Hidup vs Jam Kerja)
- SELASA & JUMAT  : PROGRAM "RADAR SENTIMEN" (Isu Berita Viral: Fakta Inti vs Kubu Pro vs Kubu Kontra)
- RABU, SABTU & MINGGU: PROGRAM "ANGKA BICARA" (Data Storytelling & Statistik Gaya Hidup / Finansial)

Rendering visual didelegasikan secara modular ke `metrika_render.py` untuk menjamin
standar visual editorial kelas dunia (anti-overflow, typography auto-scaling, dan dark matte palette).
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

from PIL import Image, ImageDraw, ImageFont

# Import Modul Render Editorial METRIKA
from metrika_render import (
    render_carousel_slides,
    render_vertical_video,
    words_from_edge_boundaries,
)

# ==============================================================================
# 1. KONFIGURASI GLOBAL & BENCHMARK RESMI
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
SLIDE2_IMG_PATH = OUTPUT_DIR / "editorial_slide2.jpg"
SLIDE3_IMG_PATH = OUTPUT_DIR / "editorial_verdict.jpg"
VERDICT_IMG_PATH = SLIDE3_IMG_PATH
FINAL_VIDEO_PATH = OUTPUT_DIR / "tiktok_reels_metrika.mp4"

# Regulasi & Benchmark Ekonomi Resmi Indonesia
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

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ==============================================================================
# 2. SISTEM PENJADWALAN PROGRAM MINGGUAN
# ==============================================================================
def get_daily_program_config() -> Dict[str, Any]:
    """
    Menentukan program harian berdasarkan hari dalam seminggu:
    - Senin (0) & Kamis (3) : INDEKS KERINGAT
    - Selasa (1) & Jumat (4) : RADAR SENTIMEN
    - Rabu (2), Sabtu (5), Minggu (6) : ANGKA BICARA
    """
    if PROGRAM_OVERRIDE in ("INDEKS_KERINGAT", "RADAR_SENTIMEN", "ANGKA_BICARA"):
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
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=harga+resmi+OR+tiket+konser+OR+gadget+resmi+OR+mobil+motor+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "Kepgub DKI No. 1026/2024 (UMP Rp 5.396.763)",
                "Kepmenhub No. KP 667/2022 (Tarif Ojol Zona II)",
                "Badan Pangan Nasional (Bapanas)",
                "PT Antam Tbk Logam Mulia",
            ],
        }
    elif p_id == "RADAR_SENTIMEN":
        return {
            "id": "RADAR_SENTIMEN",
            "name": "RADAR SENTIMEN",
            "subtitle": "PETA POLARISASI OPINI PUBLIK",
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/NATION?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=viral+OR+perdebatan+OR+netizen+indonesia+OR+pro+kontra&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "Pantauan Percakapan Media Sosial & Forum Publik",
                "Portal Berita Terverifikasi Dewan Pers",
            ],
        }
    else:
        return {
            "id": "ANGKA_BICARA",
            "name": "ANGKA BICARA",
            "subtitle": "DATA STORYTELLING & GAYA HIDUP",
            "feeds": [
                "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
                "https://news.google.com/rss/search?q=biaya+hidup+OR+survei+gaji+OR+riset+anak+muda+OR+bps+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "Badan Pusat Statistik (BPS)",
                "Bank Indonesia (BI)",
                "Survei Literasi Keuangan Nasional",
            ],
        }


# ==============================================================================
# 3. MODUL INGESTION BERITA & FOTO TERVALIDASI
# ==============================================================================
def format_rupiah(amount: int) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def load_posted_links() -> set:
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text("", encoding="utf-8")
        return set()
    lines = CACHE_FILE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip()}


def save_posted_link(link: str) -> None:
    with CACHE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{link.strip()}\n")


def clean_html(raw_html: str) -> str:
    clean_regex = re.compile("<.*?>")
    text = re.sub(clean_regex, " ", raw_html or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_latest_program_news(prog_cfg: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
    posted = load_posted_links()
    candidates: List[Dict[str, str]] = []

    if feedparser is not None:
        for rss_url in prog_cfg["feeds"]:
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
    print(f"[RSS] Topik Terpilih ({prog_cfg['name']}): {primary_item['title']}")
    return primary_item, supporting



ACRONYM_MAP = {
    "BBCA": "Bank Central Asia BCA gedung kantor Jakarta",
    "BBRI": "Bank Rakyat Indonesia BRI kantor gedung",
    "BMRI": "Bank Mandiri kantor pusat Jakarta",
    "BBNI": "Bank BNI kantor Jakarta",
    "IHSG": "Bursa Efek Indonesia saham IDX trading board",
    "MSCI": "Bursa Efek Indonesia pasar modal saham",
    "BEI": "Bursa Efek Indonesia gedung IDX",
    "KRL": "KRL Commuter Line Jabodetabek kereta stasiun",
    "OJOL": "Pengemudi ojek online jalanan Jakarta motor",
    "BPS": "Badan Pusat Statistik kantor Jakarta",
    "ANTAM": "Emas batangan Logam Mulia Antam",
    "TESLA": "Tesla Roadster electric car supercar",
}

def resolve_search_query(raw_query: str) -> str:
    words = raw_query.upper().split()
    for w in words:
        clean_w = re.sub(r'[^A-Z]', '', w)
        if clean_w in ACRONYM_MAP:
            return ACRONYM_MAP[clean_w]
    return raw_query

THEMATIC_PALETTES = {
    "automotive": ("Teknologi & Transportasi", (38, 24, 16), (185, 28, 28)),
    "finance": ("Pasar Modal & Finansial", (30, 20, 14), (140, 88, 53)),
    "labor": ("Upah & Ketenagakerjaan", (45, 30, 20), (166, 124, 82)),
    "lifestyle": ("Ekonomi & Gaya Hidup", (35, 25, 18), (180, 130, 90)),
}

def generate_curated_editorial_hero(topic_theme: str, headline: str, save_path: Path) -> Path:
    label, bg_rgb, accent_rgb = THEMATIC_PALETTES.get(topic_theme, THEMATIC_PALETTES["lifestyle"])
    im = Image.new("RGB", (1200, 800), bg_rgb)
    d = ImageDraw.Draw(im)
    d.rectangle([(0, 775), (1200, 800)], fill=accent_rgb)
    d.rectangle([(50, 50), (1150, 730)], outline=(40, 55, 75), width=2)
    for y in range(80, 700, 80):
        d.line([(60, y), (1140, y)], fill=(25, 35, 50), width=1)
    
    clean_h = re.sub(r'</?red>', '', headline)
    d.text((80, 320), f"METRIKA RISET DATA • {label.upper()}", fill=accent_rgb)
    d.text((80, 380), clean_h[:65], fill=(245, 245, 245))
    im.save(save_path, format="JPEG", quality=92)
    print(f"[Photo] Visual editorial tersusun rapi: {save_path.name}")
    return save_path

def fetch_editorial_photo_with_meta(
    news_item: Dict[str, str], subject_name: str, save_path: Path
) -> Tuple[Optional[Path], str]:
    candidate_urls: List[str] = []
    meta_text = f"{subject_name} {news_item['title']} {news_item.get('summary', '')}"

    # 1. Coba ikuti link asli artikel berita untuk ambil og:image
    if BeautifulSoup is not None:
        try:
            resp = requests.get(
                news_item["link"], headers=HTTP_HEADERS, timeout=8, allow_redirects=True
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
                            if not any(x in val.lower() for x in ["logo", "icon", "banner", "placeholder"]):
                                candidate_urls.append(val)
        except Exception:
            pass

    # 2. Coba cari foto resmi di Wikipedia API
    clean_entity = re.sub(r'[^\w\s]', '', subject_name).strip()
    if clean_entity:
        try:
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(clean_entity)}&prop=pageimages&format=json&pithumbsize=1200"
            w_res = requests.get(wiki_url, headers=HTTP_HEADERS, timeout=6)
            if w_res.status_code == 200:
                pages = w_res.json().get("query", {}).get("pages", {})
                for _, v in pages.items():
                    if "thumbnail" in v:
                        candidate_urls.append(v["thumbnail"]["source"])
        except Exception:
            pass

    # 3. Coba cari di Bing Image Search dengan filter ketat anti-channel logo
    search_q = f"{clean_entity} photo high resolution -logo -channel"
    bing_url = (
        "https://www.bing.com/images/search?q="
        + urllib.parse.quote(search_q)
        + "&qft=+filterui:imagesize-large"
    )
    try:
        b_resp = requests.get(bing_url, headers=HTTP_HEADERS, timeout=6)
        if b_resp.status_code == 200:
            matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', b_resp.text)
            for m in matches[:6]:
                m_low = m.lower()
                if not any(b in m_low for b in [".in/", "aajtak", "indiatoday", "zeenews", "ndtv", "espn", "sports", "cricket", "football", "baseball", "nfl", "nba", "logo", "icon", "channel", "banner"]):
                    candidate_urls.append(m)
    except Exception:
        pass

    # Validasi download
    for img_url in candidate_urls:
        try:
            r = requests.get(img_url, headers=HTTP_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.content) > 15_000:
                pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if pil_img.width >= 500 and pil_img.height >= 300:
                    pil_img.save(save_path, format="JPEG", quality=92)
                    print(f"[Photo] Foto berhasil diunduh: {img_url[:60]}...")
                    return save_path, f"{meta_text} {img_url}"
        except Exception:
            continue

    # Fallback Terkurasi: Jamin foto tidak pernah None!
    theme_key = "lifestyle"
    sub_low = subject_name.lower()
    if any(k in sub_low for k in ["mobil", "motor", "tesla", "kendaraan", "transportasi"]):
        theme_key = "automotive"
    elif any(k in sub_low for k in ["saham", "ihsg", "msci", "bursa", "investasi"]):
        theme_key = "finance"
    elif any(k in sub_low for k in ["gaji", "upah", "ojol", "buruh", "kerja"]):
        theme_key = "labor"

    generated = generate_curated_editorial_hero(theme_key, news_item["title"], save_path)
    return generated, meta_text


# ==============================================================================
# 4. ENGINE KALKULASI INDEKS KERINGAT DETERMINISTIK
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
# 5. OTAK AI: ANALISIS PROGRAM SPESIFIK KE SKEMA CLAUDE
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
        instructions = f"""
Kamu adalah Redaktur Riset media data "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi: Membedah harga barang/gadget/tiket/gaya hidup nyata terhadap jam kerja ojol dan upah UMP Jakarta.

GAYA HEADLINE EDITORIAL (@theeconomicinfluence):
- Wajib tulis kalimat hook provokatif, sedikit satir, atau pertanyaan tajam ala @theeconomicinfluence.
- Gunakan tag <red>...</red> untuk 2-4 kata kunci paling emosional/menohok (Contoh: 'IHSG Anjlok, <red>Danantara Justru Melihat Kesempatan</red> Lebih Besar').

ATURAN DENSITAS & ARGUMEN EDITORIAL:
1. WAJIB KAYA TEKS & ARGUMEN: Buat 3 sampai 4 butir poin mendalam per kolom (jangan hanya 1-2 kalimat pendek).
2. FORMAT BOLD LEAD-IN: Setiap poin wajib diawali frasa tebal diikuti uraian 20-30 kata (contoh: '**Dampak Pasar Ritel:** Penurunan indeks memicu aksi panic selling pada investor ritel...').
3. SERTAKAN OVERVIEW CONTEXT: Tulis 1 paragraf ringkas (25-35 kata) di field 'overview_context' yang merangkum dinamika isu.

ATURAN ANTI-AI-SLOP:
1. PRODUK WAJIB NYATA & RESMI DI INDONESIA: DILARANG mengarang barang masa depan. Harus produk nyata yang resmi beredar saat ini (contoh: iPhone 16 Pro Max 256GB, Vespa Sprint 150, Tiket Konser CAT 1, PS5 Slim, Sewa Kos Setahun).
2. HARGA VALID: Tentukan estimasi harga pasar wajar integer Rupiah (misal: 24999000).
3. DILARANG MENGGUNAKAN EMOJI.
4. NASKAH VOICEOVER: 50-70 kata narasi padat & mengalir.

Format output JSON:
{{
  "subject_title": "Nama produk resmi nyata di Indonesia (maks 26 karakter)",
  "price_idr": 24999000,
  "hook": "iPhone 16 Pro Resmi Rilis, <red>Berapa Bulan Gaji UMR</red> yang Harus Ditukar?",
  "keywords": ["gadget", "apple", "iphone", "hp"],
  "verdict": "Gadget bukan sekadar barang konsumsi; ia dibayar dengan ratusan jam kerja dan tetesan keringat.",
  "cta": "Berapa jam kerja yang rela kamu tukar untuk membeli barang ini? Tulis di komentar.",
  "voiceover_script": "Naskah narasi 50-70 kata lugas tanpa emoji."
}}
"""
    elif p_id == "RADAR_SENTIMEN":
        instructions = f"""
Kamu adalah Redaktur Opini Publik media data "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi: Membedah isu berita hangat yang viral di Indonesia secara objektif: Fakta Inti vs Kubu Pro vs Kubu Kontra.

GAYA HEADLINE EDITORIAL (@theeconomicinfluence):
- Wajib tulis kalimat hook provokatif, sedikit satir, atau pertanyaan tajam ala @theeconomicinfluence.
- Gunakan tag <red>...</red> untuk 2-4 kata kunci paling emosional/menohok (Contoh: 'IHSG Anjlok, <red>Danantara Justru Melihat Kesempatan</red> Lebih Besar').

ATURAN DENSITAS & ARGUMEN EDITORIAL:
1. WAJIB KAYA TEKS & ARGUMEN: Buat 3 sampai 4 butir poin mendalam per kolom (jangan hanya 1-2 kalimat pendek).
2. FORMAT BOLD LEAD-IN: Setiap poin wajib diawali frasa tebal diikuti uraian 20-30 kata (contoh: '**Dampak Pasar Ritel:** Penurunan indeks memicu aksi panic selling pada investor ritel...').
3. SERTAKAN OVERVIEW CONTEXT: Tulis 1 paragraf ringkas (25-35 kata) di field 'overview_context' yang merangkum dinamika isu.

ATURAN ANTI-AI-SLOP:
1. FAKTA BERITA NYATA: Ringkas fakta inti peristiwa dengan jernih tanpa sensasionalisme.
2. POLARISASI PERSENTASE REALISTIS: Tentukan angka persentase pro vs kontra (misal pro 62, kontra 38).
3. SUARA KUBU: Rangkum argumen utama Kubu Pro dan Kubu Kontra di media sosial (masing-masing 2-3 poin tajam).
4. DILARANG MENGGUNAKAN EMOJI.
5. NASKAH VOICEOVER: 50-70 kata membedah dua sudut pandang dan memancing diskusi.

Format output JSON:
{{
  "subject_title": "Isu atau Tokoh Utama (maks 26 karakter)",
  "hook": "IHSG Babak Belur, <red>Emangnya Ngaruh?</red> Kan Kita di Desa Gak Main Saham.",
  "pro_pct": 62,
  "contra_pct": 38,
  "keywords": ["kebijakan", "publik", "viral", "isu"],
  "fact_points": ["Fakta resmi peristiwa yang telah diverifikasi", "Konfirmasi dari pihak otoritas terkait"],
  "pro_points": ["Mendukung langkah percepatan efisiensi layanan", "Memberikan kepastian bagi masyarakat"],
  "contra_points": ["Mengkhawatirkan transparansi dan akuntabilitas", "Berdampak pada beban operasional masyarakat"],
  "verdict": "Perbedaan terbesar ada pada sudut pandang kepentingan, bukan pada fakta dasarnya.",
  "cta": "Kamu di kubu mana, dan data apa yang bisa mengubah pandanganmu? Tulis di komentar.",
  "voiceover_script": "Naskah narasi 50-70 kata lugas tanpa emoji."
}}
"""
    else:  # ANGKA_BICARA
        instructions = f"""
Kamu adalah Jurnalis Data media "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi: Menyajikan riset statistik, keuangan, pasar modal, dan tren ekonomi nyata secara infografis.

GAYA HEADLINE EDITORIAL:
- Kalimat hook harus tajam, provokatif, dan berbobot data.
- Gunakan tag <red>...</red> untuk 2-4 kata kunci paling emosional/menohok (Contoh: 'Investor Panik, <red>IHSG Terjun Bebas</red> Setelah Badai MSCI. Siapa Untung?').

ATURAN DENSITAS & ARGUMEN EDITORIAL:
1. WAJIB KAYA TEKS & ARGUMEN: Buat 3 sampai 4 butir poin mendalam per kolom (jangan hanya 1-2 kalimat pendek).
2. FORMAT BOLD LEAD-IN: Setiap poin wajib diawali frasa tebal diikuti uraian 20-30 kata (contoh: '**Dampak Pasar Ritel:** Penurunan indeks memicu aksi panic selling pada investor ritel...').
3. SERTAKAN OVERVIEW CONTEXT: Tulis 1 paragraf ringkas (25-35 kata) di field 'overview_context' yang merangkum dinamika isu.

ATURAN ANTI-AI-SLOP:
1. DATA VALID & RELEVAN SESUAI TOPIK BERITA: Seluruh data, judul slide, dan poin analisis WAJIB 100% relevan dengan berita yang diberikan. DILARANG mencampuradukkan topik yang tidak relevan (seperti biaya sewa kos saat membahas saham/IHSG/MSCI).
2. DILARANG MENGGUNAKAN EMOJI.
3. NASKAH VOICEOVER: 50-70 kata narasi data yang mengalir dan tajam.

Format output JSON:
{{
  "subject_title": "Topik Berita Utama (maks 26 karakter)",
  "hook": "Investor Panik, <red>IHSG Terjun Bebas</red> Setelah Badai MSCI. Siapa Untung?",
  "hero_value": "4.800",
  "hero_label": "level psikologis IHSG yang berpotensi diuji pasca sentimen pasar modal",
  "keywords": ["saham", "ihsg", "msci", "investasi"],
  "slide_heading": "Dampak Sentimen Terhadap Pasar & Portofolio Ritel",
  "metric_value": "Rp 12,4 Triliun",
  "metric_label": "total net sell investor asing dalam sepekan terakhir",
  "breakdown_left_title": "Dampak Pasar Modal",
  "breakdown_left_points": ["Penurunan nilai portofolio saham kapitalisasi besar", "Sentimen jual jangka pendek akibat penyesuaian bobot indeks"],
  "breakdown_right_title": "Strategi Investor",
  "breakdown_right_points": ["Evaluasi ulang valuasi dan fundamental emiten", "Disiplin alokasi aset dan tidak panik melakukan aksi jual massal"],
  "verdict": "Volatilitas pasar adalah bagian dari siklus; keputusan terbaik lahir dari data, bukan kepanikan sesaat.",
  "cta": "Bagaimana strategi portofoliomu menghadapi fluktuasi ini? Tulis di komentar.",
  "voiceover_script": "Naskah narasi 50-70 kata lugas tanpa emoji."
}}
"""

    prompt = f"""
{instructions}

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
                print(f"[Gemini] Analisis Sukses: {parsed.get('subject_title')}")
                return parsed
        except Exception:
            continue

    raise RuntimeError("Seluruh model Gemini gagal menganalisis topik ini.")


# ==============================================================================
# 6. PENYUSUN KONTEN UNTUK ENGINE CLAUDE (CONTENT ADAPTER)
# ==============================================================================
def build_metrika_content(
    analysis: Dict[str, Any],
    prog_cfg: Dict[str, Any],
    metrics: Optional[Dict[str, Any]],
    hero_img: Optional[Path],
    slide2_img: Optional[Path],
    slide3_img: Optional[Path],
    hero_meta: str,
) -> Dict[str, Any]:
    """
    Menyusun payload dictionary `content` yang presisi sesuai skema yang diminta
    oleh engine perender `metrika_render.py`.
    """
    p_id = prog_cfg["id"]
    today_str = datetime.datetime.now().strftime("%d %b %Y")
    subject_title = analysis.get("subject_title", "Topik Riset")

    if p_id == "INDEKS_KERINGAT" and metrics is not None:
        hero_val = f"Rp {metrics['price_idr'] / 1_000_000:.1f} jt".replace(".", ",") if metrics['price_idr'] >= 1_000_000 else metrics["price_str"]
        return {
            "program": "INDEKS_KERINGAT",
            "date": today_str,
            "hook": analysis.get("hook", f"Berapa hari kerja untuk membeli {subject_title} di Jakarta?"),
            "hero": {
                "value": hero_val,
                "label": f"estimasi harga resmi {subject_title} di pasar Indonesia",
            },
            "slides": [
                {
                    "heading": f"{subject_title} vs Upah Riil Pekerja",
                    "image": str(slide2_img) if slide2_img else None,
                    "overview_context": analysis.get("overview_context", "Perbandingan jam kerja riil pekerja dan pengemudi transportasi daring terhadap nilai barang konsumsi."),
                    "metric": {
                        "value": f"{metrics['ump_months']} Bulan",
                        "label": f"Gaji bersih UMP DKI Jakarta 2025 ({format_rupiah(UMP_JAKARTA_2025)}/bln)",
                    },
                    "columns": [
                        {
                            "title": "Beban Keringat Ojol",
                            "tone": "key",
                            "points": [
                                f"{metrics['ojol_trips']:,} Order perjalanan bersih".replace(",", "."),
                                f"Setara ~{metrics['ojol_days']} hari narik penuh di aspal",
                                f"Total {metrics['ojol_hours']} jam kerja aktif di jalanan",
                            ],
                        },
                        {
                            "title": "Pekerja UMP Jakarta",
                            "tone": "neutral",
                            "points": [
                                f"{metrics['ump_months']} Bulan gaji disisihkan 100%",
                                f"Setara {metrics['ump_days']} hari kerja kantor 8 jam/hari",
                                f"Menyerap {metrics['ump_pct']}% dari upah bulanan",
                            ],
                        },
                    ],
                },
                {
                    "heading": "Nilai Barang Setara Kebutuhan Pokok Apa Saja?",
                    "metric": {
                        "value": f"{metrics['karung_beras']} Karung",
                        "label": f"Beras Medium 5kg ({metrics['ton_beras']} Ton) - Acuan Bapanas",
                    },
                    "columns": [
                        {
                            "title": "Pangan & Hunian",
                            "tone": "fact",
                            "points": [
                                f"{metrics['karung_beras']} Karung beras medium 5kg",
                                f"{metrics['bulan_kos']} Bulan sewa kamar kos standar Jakarta",
                            ],
                        },
                        {
                            "title": "Aset Produktif",
                            "tone": "key",
                            "points": [
                                f"{metrics['gram_emas']} Gram emas murni PT Antam Tbk",
                                "Pilihan: Konsumsi gengsi atau aset masa depan?",
                            ],
                        },
                    ],
                },
            ],
            "verdict": analysis.get("verdict", "Gadget bukan sekadar barang konsumsi; ia dibayar dengan ratusan jam kerja nyata."),
            "cta": analysis.get("cta", "Berapa jam kerja yang rela kamu tukar untuk barang ini? Tulis di komentar."),
            "sources": prog_cfg["sources"],
            "keywords": analysis.get("keywords", ["gadget", "harga", "resmi"]),
            "hero_image": str(hero_img) if hero_img else None,
            "verdict_image": str(slide3_img) if slide3_img else None,
            "hero_image_meta": hero_meta,
            "narration": analysis.get("voiceover_script", ""),
        }

    elif p_id == "RADAR_SENTIMEN":
        pro_pct = int(analysis.get("pro_pct", 58))
        contra_pct = int(analysis.get("contra_pct", 42))
        return {
            "program": "RADAR_SENTIMEN",
            "date": today_str,
            "hook": analysis.get("hook", "Isu viral ini memecah publik jadi dua kubu. Apa faktanya?"),
            "hero": {
                "value": f"{pro_pct} : {contra_pct}",
                "label": "perbandingan persentase kubu pro vs kubu kontra dari percakapan publik",
            },
            "slides": [
                {
                    "heading": analysis.get("slide_heading", "Fakta di Balik Kehebohan Isu"),
                    "image": str(slide2_img) if slide2_img else None,
                    "overview_context": analysis.get("overview_context", "Latar belakang dan dinamika polarisasi opini publik yang berkembang di media sosial."),
                    "columns": [
                        {
                            "title": "Fakta Terverifikasi",
                            "tone": "fact",
                            "points": analysis.get("fact_points", ["Fakta kronologi peristiwa terkonfirmasi resmi", "Pernyataan resmi pihak berwenang"]),
                        }
                    ],
                },
                {
                    "heading": "Adu Argumen: Suara Dua Kubu",
                    "columns": [
                        {
                            "title": "Kubu Pro / Sepakat",
                            "tone": "pro",
                            "points": analysis.get("pro_points", ["Mendukung percepatan efisiensi", "Menilai kebijakan solutif"]),
                        },
                        {
                            "title": "Kubu Kontra / Kritis",
                            "tone": "con",
                            "points": analysis.get("contra_points", ["Mempertanyakan transparansi anggaran", "Khawatir dampak ke masyarakat"]),
                        },
                    ],
                },
            ],
            "verdict": analysis.get("verdict", "Perbedaan terbesar ada pada sudut pandang kepentingan, bukan pada datanya sendiri."),
            "cta": analysis.get("cta", "Kamu di kubu mana, dan data apa yang bisa mengubah pandanganmu? Tulis di komentar."),
            "sources": prog_cfg["sources"],
            "keywords": analysis.get("keywords", ["isu", "viral", "publik"]),
            "hero_image": str(hero_img) if hero_img else None,
            "verdict_image": str(slide3_img) if slide3_img else None,
            "hero_image_meta": hero_meta,
            "narration": analysis.get("voiceover_script", ""),
        }

    else:  # ANGKA_BICARA
        slide_heading = analysis.get("slide_heading") or analysis.get("subject_title", "Bedah Data & Implikasi")
        metric_val = analysis.get("metric_value") or analysis.get("hero_value", "100%")
        metric_lbl = analysis.get("metric_label") or analysis.get("hero_label", "Analisis data terverifikasi")
        left_title = analysis.get("breakdown_left_title", "Poin Analisis Utama")
        left_points = analysis.get("breakdown_left_points", ["Faktor penggerak utama dari temuan data", "Dampak langsung terhadap kondisi finansial publik"])
        right_title = analysis.get("breakdown_right_title", "Strategi & Implikasi")
        right_points = analysis.get("breakdown_right_points", ["Langkah antisipasi dan evaluasi keputusan", "Peluang jangka panjang berbasis data riil"])

        return {
            "program": "ANGKA_BICARA",
            "date": today_str,
            "hook": analysis.get("hook", "Temuan data penting yang perlu kamu ketahui hari ini."),
            "hero": {
                "value": analysis.get("hero_value", "70%"),
                "label": analysis.get("hero_label", "persentase temuan data resmi"),
            },
            "slides": [
                {
                    "heading": slide_heading,
                    "image": str(slide2_img) if slide2_img else None,
                    "overview_context": analysis.get("overview_context", "Analisis mendalam mengenai latar belakang data dan implikasi strategis terhadap masyarakat."),
                    "metric": {
                        "value": metric_val,
                        "label": metric_lbl,
                    },
                    "columns": [
                        {
                            "title": left_title,
                            "tone": "fact",
                            "points": left_points,
                        },
                        {
                            "title": right_title,
                            "tone": "key",
                            "points": right_points,
                        },
                    ],
                }
            ],
            "verdict": analysis.get("verdict", "Hambatan terbesar bukan niat menabung, melainkan tingginya biaya hidup perkotaan."),
            "cta": analysis.get("cta", "Menurut kamu, pos apa yang paling menguras gaji setiap bulan? Tulis di komentar."),
            "sources": prog_cfg["sources"],
            "keywords": analysis.get("keywords", ["gaji", "statistik", "anak muda"]),
            "hero_image": str(hero_img) if hero_img else None,
            "verdict_image": str(slide3_img) if slide3_img else None,
            "hero_image_meta": hero_meta,
            "narration": analysis.get("voiceover_script", ""),
        }


# ==============================================================================
# 7. SUARA NATURAL EKSPRESIF (EDGE-TTS)
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
                raw_boundaries.append(chunk)

    subtitle_out.write_text(
        json.dumps(raw_boundaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return raw_boundaries


def generate_voiceover_words(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    print(f"[Edge-TTS] Merekam suara narator ({TTS_VOICE}, {TTS_RATE})...")
    raw_boundaries = asyncio.run(
        _generate_voiceover_stream(script_text, audio_out, subtitle_out)
    )
    words = words_from_edge_boundaries(raw_boundaries)
    print(f"[Edge-TTS] Audio selesai ({len(words)} kata terindeks karaoke).")
    return words


# ==============================================================================
# 8. DISTRIBUSI KE TELEGRAM
# ==============================================================================
def send_outputs_to_telegram(
    video_path: Path,
    carousel_paths: List[Path],
    content: Dict[str, Any],
    news_item: Dict[str, str],
) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Token/Chat ID belum diset. Melewati kirim Telegram.")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    prog_label = content["program"].replace("_", " ")

    header_msg = (
        f"📊 *{MEDIA_NAME.upper()} • {prog_label}*\n"
        f"Topik: *{re.sub(r'</?red>', '', content['hook'])}*\n"
        f"Angka Kunci: *{content['hero']['value']}* ({content['hero']['label']})\n\n"
        f"⚖️ *Verdict Objektif:*\n_{content['verdict']}_\n\n"
        f"💬 *Diskusi Publik:*\n{content['cta']}\n\n"
        f"📌 *Rujukan Resmi:*\n" + "\n".join(f"• {s}" for s in content.get("sources", []))
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
            clean_h = re.sub(r"</?red>", "", content['hook'])
            item_obj["caption"] = f"🖼 {MEDIA_NAME} Carousel: {clean_h} ({len(carousel_paths)} Slide)"
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

    print("[Telegram] Seluruh paket media berhasil didistribusikan!")


# ==============================================================================
# 9. PIPELINE UTAMA
# ==============================================================================
def main() -> None:
    prog_cfg = get_daily_program_config()

    print("=" * 72)
    print(f"🚀 MEMULAI PIPELINE: {MEDIA_NAME.upper()} • {prog_cfg['name']}")
    print(f"📅 Rubrik: {prog_cfg['subtitle']}")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Ingestion berita RSS
    news_item, supporting = fetch_latest_program_news(prog_cfg)

    # 2. Analisis AI Gemini
    analysis = analyze_with_gemini(news_item, supporting, prog_cfg)

    # 3. Hitung metrik ekonomi jika program Indeks Keringat
    metrics = None
    if prog_cfg["id"] == "INDEKS_KERINGAT":
        metrics = compute_labor_metrics(analysis.get("price_idr", 24_999_000))

    # 4. Cari foto jurnalistik akurat untuk SETIAP slide
    q_slide1 = resolve_search_query(f"{analysis.get('subject_title', '')} {news_item['title']}")
    hero_img, hero_meta = fetch_editorial_photo_with_meta(news_item, q_slide1, HERO_IMG_PATH)

    q_slide2 = resolve_search_query(f"{analysis.get('slide_heading', '')} {analysis.get('subject_title', '')} data grafik")
    slide2_img, _ = fetch_editorial_photo_with_meta(news_item, q_slide2, SLIDE2_IMG_PATH)

    q_slide3 = resolve_search_query(f"investor analisis pasar modal {analysis.get('subject_title', '')}")
    slide3_img, _ = fetch_editorial_photo_with_meta(news_item, q_slide3, VERDICT_IMG_PATH)

    # 5. Adaptasi ke skema content metrika_render
    content = build_metrika_content(analysis, prog_cfg, metrics, hero_img, slide2_img, slide3_img, hero_meta)

    latest_json = OUTPUT_DIR / "latest_analysis.json"
    latest_json.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

    # 6. Generate voiceover narasi audio & timing kata
    voice_script = content.get("narration", f"Berikut ulasan data dari {MEDIA_NAME}.")
    words = generate_voiceover_words(voice_script, AUDIO_PATH, SUBTITLE_PATH)

    # 7. Render Carousel dengan Engine Baru (Anti-AI-Slop & Auto-Fit)
    print("[Render] Memulai render carousel 1080x1350...")
    carousel_files = render_carousel_slides(content, CAROUSEL_DIR)
    print(f"[Render] Sukses merender {len(carousel_files)} slide carousel.")

    # 8. Render Video Vertikal dengan Subtitle Karaoke & Counter
    print("[Render] Memulai render video vertikal 1080x1920...")
    video_file = render_vertical_video(
        content,
        FINAL_VIDEO_PATH,
        audio_path=AUDIO_PATH,
        words=words,
    )
    print(f"[Render] Sukses merender video: {video_file}")

    # 9. Kirim ke Telegram
    send_outputs_to_telegram(video_file, carousel_files, content, news_item)

    # 10. Update riwayat cache link
    save_posted_link(news_item["link"])
    print(f"[Cache] Link berhasil disimpan ke {CACHE_FILE}.")
    print(f"✅ PIPELINE {prog_cfg['name']} SELESAI DENGAN SUKSES!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌ [ERROR] Pipeline berhenti: {err}", file=sys.stderr)
        sys.exit(1)
